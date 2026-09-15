// FSRS — Free Spaced Repetition Scheduler.
// Spec: https://github.com/open-spaced-repetition/fsrs4anki
//
// PRECISION DE VERSION. L'en-tete annoncait « FSRS-4.5 ». C'est inexact et il
// vaut mieux le dire que le laisser croire :
//   - la courbe d'oubli implementee ici est celle de FSRS v4,
//     R(t,S) = (1 + t/(9S))^-1, et `nextInterval` en est l'inverse EXACT —
//     l'ensemble est donc coherent, et R(S,S) = 0,9 par construction;
//   - FSRS-4.5 et 5 utilisent une loi de puissance differente
//     (R = (1 + FACTOR·t/S)^DECAY, DECAY = -0,5, FACTOR = 19/81);
//   - le vecteur de poids compte 21 coefficients, ce qui est le format
//     FSRS-6, et w20 y vaut 0 (valeur neutre, non ajustee).
// Autrement dit: courbe v4, poids au format v6. Les deux se tiennent parce
// que la courbe et son inverse sont accordees entre elles, mais il ne faut
// pas presenter ce scheduler comme une implementation fidele de 4.5.
//
// Why FSRS over SM-2 (Anki's classic algo):
//   • SM-2 over-schedules easy material (treats stability and difficulty as
//     one). FSRS separates them: D ∈ [1..10] tracks how hard the item is for
//     this learner, S tracks how long the memory survives.
//   • SM-2 has no real model of forgetting probability. FSRS uses an
//     exponential decay R(t) = exp(-t/S) and targets a desired retention rate.
//   • FSRS is the algorithm Anki shipped in 23.10+ — Juan will be on the
//     state of the art, not 1985 spaced repetition.
//
// Pure compute: no DOM, no Date.now() inside scheduling math — the caller
// supplies a clock so unit tests stay deterministic.

/** User rating on review — Anki-compatible. */
export type Rating = 1 | 2 | 3 | 4
export const RATING = { Again: 1, Hard: 2, Good: 3, Easy: 4 } as const

export type CardState = 'new' | 'learning' | 'review' | 'relearning'

export type FsrsCard = {
  /** Memory stability (days). Higher = the card survives longer. */
  stability: number
  /** Difficulty in [1, 10]. Drifts up on Again, down on Easy. */
  difficulty: number
  /** ISO timestamp of last review, or null for new cards. */
  lastReview: string | null
  /** ISO timestamp of next scheduled review. */
  due: string
  /** Lifecycle state. */
  state: CardState
  /** Lapses since the card entered review. */
  lapses: number
  /** Total reviews. */
  reps: number
  /** Last interval scheduled (days). */
  scheduledDays: number
  /** Elapsed days at last review (for retrievability). */
  elapsedDays: number
}

export type FsrsParameters = {
  /** 21-coefficient weight vector. Defaults from FSRS-4.5 reference fit. */
  w: number[]
  /** Desired retention probability when scheduling (0.7 - 0.97). */
  requestRetention: number
  /** Maximum interval in days (anti runaway). */
  maximumInterval: number
  /** When true, enables the "easy bonus" multiplier on Easy ratings. */
  enableShortTerm: boolean
}

// FSRS-4.5 default weights (Jarrett Ye, 2024). 21 params w0..w20.
export const FSRS_DEFAULT_WEIGHTS: number[] = [
  0.4072, 1.1829, 3.1262, 15.4722,
  7.2102, 0.5316, 1.0651, 0.0234,
  1.616, 0.1544, 1.0824, 1.9813,
  0.0953, 0.2975, 2.2042, 0.2407,
  2.9466, 0.5034, 0.6567, 0.0179,
  0.0,
]

export const DEFAULT_FSRS_PARAMS: FsrsParameters = {
  w: FSRS_DEFAULT_WEIGHTS,
  requestRetention: 0.9,
  maximumInterval: 36500, // 100 years
  enableShortTerm: true,
}

// --- Helpers ---------------------------------------------------------------
const DAY_MS = 86_400_000

export function makeNewCard(now: Date = new Date()): FsrsCard {
  return {
    stability: 0,
    difficulty: 0,
    lastReview: null,
    due: now.toISOString(),
    state: 'new',
    lapses: 0,
    reps: 0,
    scheduledDays: 0,
    elapsedDays: 0,
  }
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

function daysBetween(a: Date, b: Date): number {
  return (b.getTime() - a.getTime()) / DAY_MS
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * DAY_MS)
}

/**
 * Retrievability R(t, S) — probability of recall t days after a review.
 * FSRS-4.5 uses the power-law variant rather than pure exponential.
 *
 *   R(t, S) = (1 + t / (9 * S))^(-1)
 *
 * This better matches the long tail of forgetting curves on real data.
 */
export function retrievability(elapsedDays: number, stability: number): number {
  if (stability <= 0) return 0
  if (elapsedDays <= 0) return 1
  return Math.pow(1 + elapsedDays / (9 * stability), -1)
}

/** Interval s.t. R(I, S) = requestRetention. */
function nextInterval(stability: number, requestRetention: number, maximum: number): number {
  const intervalDays = 9 * stability * (1 / requestRetention - 1)
  const rounded = Math.max(1, Math.round(intervalDays))
  return Math.min(maximum, rounded)
}

// --- Initial stability / difficulty after the very first review ------------
function initStability(w: number[], rating: Rating): number {
  // w0..w3 = init stabilities for ratings 1..4
  const idx = rating - 1
  return Math.max(0.1, w[idx])
}

function initDifficulty(w: number[], rating: Rating): number {
  // D₀(G) = w4 - (G-3) * w5, clamped to [1, 10]
  return clamp(w[4] - (rating - 3) * w[5], 1, 10)
}

// --- Drift functions on subsequent reviews ---------------------------------
function nextDifficulty(w: number[], d: number, rating: Rating): number {
  // Amortissement lineaire (FSRS-5+): plus la carte est deja difficile, moins
  // une note supplementaire la deplace. Sans lui, quelques « Again » suffisent
  // a coller la difficulte au plafond et l'echelle perd toute resolution dans
  // le haut, la ou se trouvent justement les cartes qui posent probleme.
  const deltaD = -w[6] * (rating - 3)
  const damped = deltaD * (10 - d) / 9
  const dPrime = d + damped

  // Retour a la moyenne. La cible du barycentre est D₀(Easy), PAS D₀(Good):
  // c'est ce que fixe la reference FSRS. L'ancien code utilisait `w[4]`,
  // c'est-a-dire D₀(3) = 7,2102, au lieu de D₀(4) = w4 - w5 = 6,6786.
  // L'ecart parait minime par revision (0,0124) mais il deplace le POINT FIXE
  // de la suite : la difficulte d'equilibre s'etablissait a 7,21 au lieu de
  // 6,68, soit une demi-graduation de trop sur toute la collection — et des
  // intervalles systematiquement raccourcis.
  const d0Easy = w[4] - w[5]
  const next = w[7] * d0Easy + (1 - w[7]) * dPrime
  return clamp(next, 1, 10)
}

/** Stability after successful recall (Hard/Good/Easy). */
function nextStabilityRecall(w: number[], d: number, s: number, r: number, rating: Rating): number {
  const hardPenalty = rating === RATING.Hard ? w[15] : 1
  const easyBonus = rating === RATING.Easy ? w[16] : 1
  const factor =
    Math.exp(w[8])
    * (11 - d)
    * Math.pow(s, -w[9])
    * (Math.exp((1 - r) * w[10]) - 1)
    * hardPenalty
    * easyBonus
  return s * (1 + factor)
}

/** Stability after a lapse (Again). */
function nextStabilityForget(w: number[], d: number, s: number, r: number): number {
  return Math.max(
    0.1,
    w[11]
      * Math.pow(d, -w[12])
      * (Math.pow(s + 1, w[13]) - 1)
      * Math.exp((1 - r) * w[14]),
  )
}

// --- Scheduler -------------------------------------------------------------
export type ReviewLog = {
  rating: Rating
  state: CardState
  due: string
  stability: number
  difficulty: number
  elapsedDays: number
  reviewedAt: string
}

export type ReviewResult = {
  card: FsrsCard
  log: ReviewLog
}

/**
 * Apply a single review to a card and produce the next state.
 *
 * Pure: takes `now` so tests can pass a fixed clock.
 *
 *   const next = review(card, RATING.Good, new Date('2026-05-17'))
 *   // next.card.due is the next scheduled date.
 */
export function review(
  card: FsrsCard,
  rating: Rating,
  now: Date = new Date(),
  params: FsrsParameters = DEFAULT_FSRS_PARAMS,
): ReviewResult {
  const w = params.w
  const lastReview = card.lastReview ? new Date(card.lastReview) : null
  const elapsedDays = lastReview ? Math.max(0, daysBetween(lastReview, now)) : 0

  let stability: number
  let difficulty: number
  let state: CardState = card.state
  let lapses = card.lapses

  if (card.state === 'new') {
    stability = initStability(w, rating)
    difficulty = initDifficulty(w, rating)
    state = rating === RATING.Again ? 'learning' : 'review'
  } else {
    const r = retrievability(elapsedDays, card.stability)
    difficulty = nextDifficulty(w, card.difficulty, rating)
    if (rating === RATING.Again) {
      stability = nextStabilityForget(w, card.difficulty, card.stability, r)
      lapses += 1
      state = 'relearning'
    } else {
      stability = nextStabilityRecall(w, card.difficulty, card.stability, r, rating)
      state = 'review'
    }
  }

  const scheduledDays = state === 'learning' || state === 'relearning'
    ? Math.min(1, params.maximumInterval)
    : nextInterval(stability, params.requestRetention, params.maximumInterval)

  const due = addDays(now, scheduledDays).toISOString()
  const nextCard: FsrsCard = {
    stability,
    difficulty,
    lastReview: now.toISOString(),
    due,
    state,
    lapses,
    reps: card.reps + 1,
    scheduledDays,
    elapsedDays,
  }
  const log: ReviewLog = {
    rating,
    state,
    due,
    stability,
    difficulty,
    elapsedDays,
    reviewedAt: now.toISOString(),
  }
  return { card: nextCard, log }
}

/** Returns true if the card is due (due ≤ now). */
export function isDue(card: FsrsCard, now: Date = new Date()): boolean {
  return new Date(card.due).getTime() <= now.getTime()
}

/** Cards in the order they should be reviewed: overdue first, then due. */
export function pickDueCards<T extends { card: FsrsCard }>(deck: T[], now: Date = new Date(), limit = Infinity): T[] {
  return deck
    .filter((entry) => isDue(entry.card, now))
    .sort((a, b) => new Date(a.card.due).getTime() - new Date(b.card.due).getTime())
    .slice(0, limit)
}

/** Convenience preview — how many cards would be due in the next N days. */
export function forecast<T extends { card: FsrsCard }>(deck: T[], horizonDays: number, now: Date = new Date()): number[] {
  const buckets = new Array<number>(horizonDays + 1).fill(0)
  for (const entry of deck) {
    const dueAt = new Date(entry.card.due).getTime()
    const days = Math.floor((dueAt - now.getTime()) / DAY_MS)
    if (days < 0) buckets[0] += 1
    else if (days <= horizonDays) buckets[days] += 1
  }
  return buckets
}

/**
 * Apply a "fuzz" to a freshly-scheduled interval so cards don't collide on the
 * same review day. Anki uses ±5%-ish for intervals over 2 days.
 */
export function fuzzInterval(intervalDays: number, seedString: string): number {
  if (intervalDays < 2.5) return intervalDays
  // Deterministic per-card jitter — FNV-1a on the seed string.
  let h = 0x811c9dc5
  for (let i = 0; i < seedString.length; i += 1) {
    h ^= seedString.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  const noise = ((h >>> 0) / 4294967296) - 0.5 // [-0.5, 0.5)
  // Le bruit vaut [-0,5 ; 0,5) : pour obtenir l'amplitude +/-5 % annoncee il
  // faut le multiplier par 0,10, pas par 0,05. L'ancienne constante donnait
  // +/-2,5 % — mesure sur 5000 cartes : [0,9750 ; 1,0250]. Deux fois moins
  // d'etalement que voulu, donc des paquets de revision qui restent groupes
  // le meme jour, ce que le brouillage doit precisement eviter.
  const factor = 1 + noise * 0.10
  return Math.max(1, Math.round(intervalDays * factor))
}
