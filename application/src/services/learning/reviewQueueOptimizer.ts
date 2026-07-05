// Optimiseur de file de révision : ordonne les cartes dues selon plusieurs
// critères pour maximiser la valeur d'apprentissage par minute.
//
// Plus subtil qu'un simple "le plus en retard d'abord" :
//   - Cartes "à risque" (stability faible + due imminente) ont priorité —
//     les rater coûte le plus en termes d'oubli.
//   - Cartes "pointes" (difficulty élevée) sont espacées pour ne pas
//     épuiser le learner sur une rafale dure.
//   - Cartes "neuves" (state='new') sont insérées 1 sur 3 max pour ne pas
//     noyer le learner dans des cartes inconnues.
//   - Cartes "lapse" récentes (lapses ≥ 2) en avant pour leur donner une
//     2e chance rapide.
//
// Module pur — la queue est calculée à partir d'un tableau de cartes FSRS
// + horloge fournie.

import { isDue, retrievability, type FsrsCard } from './spacedRepetition.ts'

export type ReviewItem<T = unknown> = {
  /** ID propre au caller. */
  id: string
  card: FsrsCard
  /** Métadonnées libres : titre carte, tags… */
  meta?: T
}

export type RankedReviewItem<T = unknown> = ReviewItem<T> & {
  /** Score d'ordonnancement [0..∞], plus haut = plus prioritaire. */
  priority: number
  /** Raison condensée du rang. */
  reason: string
  /** Retrievability au moment de l'évaluation. */
  retrievability: number
}

export type QueueOptions = {
  /** Limite de cartes dans la queue. */
  maxItems?: number
  /** Ratio max de cartes neuves (state='new') dans la queue. */
  maxNewRatio?: number
  /** Espace minimum (en positions) entre 2 cartes difficiles consécutives. */
  toughCardSpacing?: number
  /** Date de référence. */
  now?: Date
}

const DEFAULTS: Required<QueueOptions> = {
  maxItems: 30,
  maxNewRatio: 0.33,
  toughCardSpacing: 2,
  now: new Date(0),
}

function basePriority(card: FsrsCard, now: Date): { score: number; reason: string; r: number } {
  const ageMs = card.lastReview ? now.getTime() - new Date(card.lastReview).getTime() : Infinity
  const elapsedDays = card.lastReview ? Math.max(0, ageMs / 86_400_000) : 0
  const r = retrievability(elapsedDays, card.stability)

  // Carte au bord de l'oubli (retrievability < 0.75) → super prioritaire.
  if (r > 0 && r < 0.75) {
    return { score: 100 + (1 - r) * 50, reason: `retrievability ${(r * 100).toFixed(0)}% — risque d'oubli`, r }
  }

  // Lapses ≥ 2 récemment → priorité haute pour récupérer.
  if (card.lapses >= 2 && card.state === 'relearning') {
    return { score: 90, reason: `${card.lapses} lapses — re-learn`, r }
  }

  // En retard (due dans le passé) → score = jours de retard + 50.
  const overdueMs = now.getTime() - new Date(card.due).getTime()
  if (overdueMs > 0) {
    const overdueDays = overdueMs / 86_400_000
    return { score: 50 + Math.min(50, overdueDays * 5), reason: `${overdueDays.toFixed(1)}j en retard`, r }
  }

  // À l'heure pile → score modéré.
  return { score: 40, reason: 'dû maintenant', r }
}

function isToughCard(card: FsrsCard): boolean {
  return card.difficulty >= 7
}

/**
 * Calcule la queue ordonnée. Garanties :
 *   - Cartes au bord de l'oubli en premier.
 *   - Cartes neuves diluées à maxNewRatio.
 *   - 2 cartes difficiles consécutives → au moins toughCardSpacing positions.
 *
 * `pickDueCards` reste l'API simple "qui est dû"; `optimizeReviewQueue`
 * raffine cet ordonnancement pour maximiser la valeur d'apprentissage.
 */
export function optimizeReviewQueue<T>(items: ReviewItem<T>[], opts: QueueOptions = {}): RankedReviewItem<T>[] {
  const cfg = {
    maxItems: opts.maxItems ?? DEFAULTS.maxItems,
    maxNewRatio: opts.maxNewRatio ?? DEFAULTS.maxNewRatio,
    toughCardSpacing: opts.toughCardSpacing ?? DEFAULTS.toughCardSpacing,
    now: opts.now ?? new Date(),
  }
  const now = cfg.now

  // 1. Filtrer les dues + scorer.
  const ranked: RankedReviewItem<T>[] = items
    .filter((it) => isDue(it.card, now))
    .map((it) => {
      const { score, reason, r } = basePriority(it.card, now)
      return { ...it, priority: score, reason, retrievability: r }
    })

  // 2. Trier par priority décroissante.
  ranked.sort((a, b) => b.priority - a.priority)

  // 3. Cap des cartes neuves : si > maxNewRatio, on en retire.
  const targetSize = Math.min(cfg.maxItems, ranked.length)
  const maxNew = Math.floor(targetSize * cfg.maxNewRatio)
  const newCards = ranked.filter((r) => r.card.state === 'new')
  if (newCards.length > maxNew) {
    // Retire les nouvelles cartes en surplus (les moins prioritaires en queue).
    const excess = newCards.length - maxNew
    const toRemove = new Set(newCards.slice(-excess).map((r) => r.id))
    const trimmed = ranked.filter((r) => !toRemove.has(r.id))
    ranked.length = 0
    ranked.push(...trimmed)
  }

  // 4. Espacement des tough cards : si 2+ consécutives, on intercale.
  if (cfg.toughCardSpacing > 0) {
    spaceToughCards(ranked, cfg.toughCardSpacing)
  }

  // 5. Cap au maxItems.
  return ranked.slice(0, targetSize)
}

function spaceToughCards<T>(queue: RankedReviewItem<T>[], spacing: number): void {
  for (let i = 0; i < queue.length - 1; i += 1) {
    if (!isToughCard(queue[i].card)) continue
    // Cherche dans [i+1, i+spacing] si on a une autre tough. Si oui, on
    // essaie de la swapper avec une easy hors window.
    for (let j = i + 1; j <= Math.min(i + spacing, queue.length - 1); j += 1) {
      if (!isToughCard(queue[j].card)) continue
      // Cherche un easy après i+spacing pour swap.
      let swapIdx = -1
      for (let k = i + spacing + 1; k < queue.length; k += 1) {
        if (!isToughCard(queue[k].card)) {
          swapIdx = k
          break
        }
      }
      if (swapIdx >= 0) {
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        const tmp = queue[j]
        queue[j] = queue[swapIdx]
        queue[swapIdx] = tmp
      }
    }
  }
}

/**
 * Stats de la queue construite : counts par catégorie, durée estimée de session.
 */
export type QueueStats = {
  total: number
  byState: Record<FsrsCard['state'], number>
  difficultyMean: number
  expectedSessionMinutes: number
}

const SECONDS_PER_REVIEW = 20 // approximation : 20s/carte en moyenne

export function queueStats<T>(queue: RankedReviewItem<T>[]): QueueStats {
  const byState: QueueStats['byState'] = { new: 0, learning: 0, review: 0, relearning: 0 }
  let totalDiff = 0
  for (const item of queue) {
    byState[item.card.state] += 1
    totalDiff += item.card.difficulty
  }
  return {
    total: queue.length,
    byState,
    difficultyMean: queue.length > 0 ? totalDiff / queue.length : 0,
    expectedSessionMinutes: (queue.length * SECONDS_PER_REVIEW) / 60,
  }
}
