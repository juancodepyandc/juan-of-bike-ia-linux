// Bridge entre le store Leitner existant (flashcardsStore) et le scheduler
// FSRS-4.5 que j'ai ajouté. Lecture seule — pas de migration de schéma,
// le store reste source de vérité. Le bridge expose une projection FSRS
// utilisable côté UI pour afficher "FSRS prédit X cartes dues dans 7j".
//
// Convention de conversion Leitner → FSRS :
//   - Stability (jours) approximée depuis la boîte : box 1 = 0.5j,
//     box 2 = 1j, box 3 = 3j, box 4 = 7j, box 5 = 21j (alignement
//     LEITNER_DELAYS_MS du store).
//   - Difficulty estimée depuis le ratio timesWrong/(timesCorrect+timesWrong),
//     mappé sur [3..9] : carte jamais ratée → 3, ratée systématiquement → 9.
//   - State : new si reps=0, review si box ≥ 3, learning sinon.

import { forecast, RATING, type FsrsCard } from './spacedRepetition.ts'

const DAY_MS = 86_400_000

const LEITNER_BOX_TO_STABILITY_DAYS: Record<1 | 2 | 3 | 4 | 5, number> = {
  1: 0.5,
  2: 1,
  3: 3,
  4: 7,
  5: 21,
}

export type LeitnerLikeCard = {
  box: 1 | 2 | 3 | 4 | 5
  streak: number
  dueAt: number
  lastReviewedAt?: number
  timesCorrect: number
  timesWrong: number
  createdAt: number
}

export function leitnerToFsrs(card: LeitnerLikeCard, now: Date = new Date()): FsrsCard {
  const reps = card.timesCorrect + card.timesWrong
  const totalAttempts = Math.max(1, reps)
  const errorRate = card.timesWrong / totalAttempts
  const difficulty = clampRange(3 + errorRate * 6, 1, 10)
  const stability = LEITNER_BOX_TO_STABILITY_DAYS[card.box] ?? 0.5
  const state: FsrsCard['state'] = reps === 0 ? 'new' : (card.box >= 3 ? 'review' : 'learning')
  const lastReview = card.lastReviewedAt ? new Date(card.lastReviewedAt) : null
  const elapsedDays = lastReview ? Math.max(0, (now.getTime() - lastReview.getTime()) / DAY_MS) : 0
  const scheduledDays = Math.max(0, (card.dueAt - now.getTime()) / DAY_MS)
  return {
    stability,
    difficulty,
    lastReview: lastReview ? lastReview.toISOString() : null,
    due: new Date(card.dueAt).toISOString(),
    state,
    lapses: card.timesWrong,
    reps,
    scheduledDays,
    elapsedDays,
  }
}

function clampRange(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

/**
 * Forecast réutilisable par n'importe quel composant : combien de cartes
 * du deck (ou de l'app entière) sont dues dans les `horizonDays` prochains
 * jours, bucket par bucket.
 *
 * Retourne un tableau de longueur horizonDays+1 :
 *   buckets[0] = cartes en retard maintenant
 *   buckets[i] = cartes dues le jour i
 */
export function forecastFromLeitner(cards: LeitnerLikeCard[], horizonDays = 14, now: Date = new Date()): number[] {
  const wrapped = cards.map((c) => ({ card: leitnerToFsrs(c, now) }))
  return forecast(wrapped, horizonDays, now)
}

/** Total de cartes dues à l'instant t. */
export function dueNowCount(cards: LeitnerLikeCard[], now: Date = new Date()): number {
  return cards.filter((c) => c.dueAt <= now.getTime()).length
}

/**
 * Suggère un rating Anki à partir d'un résultat binaire correct/incorrect :
 *   - correct + streak ≥ 3 → Easy
 *   - correct           → Good
 *   - !correct + streak > 0 → Hard (peut-être un trou ponctuel)
 *   - !correct          → Again
 *
 * Sert quand on a un événement booléen (legacy answerCard) et qu'on veut
 * néanmoins enrichir une trace FSRS en parallèle.
 */
export function correctToFsrsRating(correct: boolean, streakBefore: number): typeof RATING.Again | typeof RATING.Hard | typeof RATING.Good | typeof RATING.Easy {
  if (correct) return streakBefore >= 3 ? RATING.Easy : RATING.Good
  if (streakBefore > 0) return RATING.Hard
  return RATING.Again
}
