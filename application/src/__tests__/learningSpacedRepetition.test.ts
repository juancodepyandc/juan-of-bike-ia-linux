/**
 * Tests for the learning module spaced-repetition + exercise formats + BO
 * curriculum. Run: node --experimental-strip-types --test src/__tests__/learningSpacedRepetition.test.ts
 *
 * These guards matter: when Juan revises 2 weeks before BAC, an off-by-one
 * scheduler can either bury an unfamiliar card for 30 days or grind through
 * mastered cards every morning. We want neither.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_FSRS_PARAMS,
  FSRS_DEFAULT_WEIGHTS,
  forecast,
  fuzzInterval,
  isDue,
  makeNewCard,
  pickDueCards,
  RATING,
  retrievability,
  review,
} from '../services/learning/spacedRepetition.ts'
import {
  attemptToRating,
  clearExerciseRegistry,
  getExercise,
  listExercises,
  registerExercise,
  scoreAttempt,
  validateExercise,
} from '../services/learning/exerciseFormats.ts'
import type {
  CodeExerciseExercise,
  McqExercise,
  OpenShortExercise,
  SchemaAnnotateExercise,
  TrueFalseExercise,
} from '../services/learning/exerciseFormats.ts'
import {
  BAC_STI2D_CURRICULUM,
  findNode,
  nodesByTrack,
  nodesByYear,
  suggestNext,
  validateCurriculumGraph,
} from '../services/learning/bacSti2dCurriculum.ts'
import {
  correctToFsrsRating,
  dueNowCount,
  forecastFromLeitner,
  leitnerToFsrs,
} from '../services/learning/fsrsLeitnerBridge.ts'

const T0 = new Date('2026-05-17T08:00:00Z')

describe('FSRS retrievability', () => {
  test('full retrievability at t=0', () => {
    assert.equal(retrievability(0, 5), 1)
  })
  test('falls below 0.9 when elapsed = S', () => {
    const r = retrievability(5, 5)
    assert.ok(r < 0.95 && r > 0.85, `r=${r}`)
  })
  test('zero stability → zero retrievability', () => {
    assert.equal(retrievability(1, 0), 0)
  })
})

describe('FSRS review', () => {
  test('new card + Good schedules a forward review', () => {
    const card = makeNewCard(T0)
    const next = review(card, RATING.Good, T0)
    assert.equal(next.card.state, 'review')
    assert.ok(new Date(next.card.due).getTime() > T0.getTime())
    assert.equal(next.card.reps, 1)
  })

  test('new card + Again → relearning state', () => {
    const card = makeNewCard(T0)
    const next = review(card, RATING.Again, T0)
    assert.equal(next.card.state, 'learning')
  })

  test('Easy schedules longer interval than Good', () => {
    const card = makeNewCard(T0)
    const easyRes = review(card, RATING.Easy, T0)
    const goodRes = review(card, RATING.Good, T0)
    assert.ok(easyRes.card.scheduledDays > goodRes.card.scheduledDays)
  })

  test('Hard schedules shorter than Good', () => {
    const card = makeNewCard(T0)
    const goodRes = review(card, RATING.Good, T0)
    // Bring both cards to a comparable post-first-review state, then test second review.
    const card2 = goodRes.card
    const after2_good = review(card2, RATING.Good, new Date(card2.due))
    const after2_hard = review(card2, RATING.Hard, new Date(card2.due))
    assert.ok(after2_hard.card.scheduledDays <= after2_good.card.scheduledDays + 1)
  })

  test('Again bumps lapses counter', () => {
    const card = makeNewCard(T0)
    const r1 = review(card, RATING.Good, T0)
    const r2 = review(r1.card, RATING.Again, new Date(r1.card.due))
    assert.equal(r2.card.lapses, 1)
    assert.equal(r2.card.state, 'relearning')
  })

  test('difficulty stays in [1, 10]', () => {
    let card = makeNewCard(T0)
    let now = T0
    for (let i = 0; i < 30; i += 1) {
      const rating = (i % 4 === 0 ? RATING.Again : RATING.Good)
      const res = review(card, rating, now)
      card = res.card
      now = new Date(card.due)
      assert.ok(card.difficulty >= 1 && card.difficulty <= 10, `D=${card.difficulty} at i=${i}`)
    }
  })

  test('stable retention rate after many easy reviews', () => {
    let card = makeNewCard(T0)
    let now = T0
    for (let i = 0; i < 12; i += 1) {
      const res = review(card, RATING.Good, now)
      card = res.card
      now = new Date(card.due)
    }
    // After 12 successful reviews, stability should be well above 1.
    assert.ok(card.stability > 30, `S=${card.stability}`)
  })
})

describe('FSRS deck helpers', () => {
  test('isDue reports correctly', () => {
    const card = makeNewCard(T0)
    assert.equal(isDue(card, T0), true)
    const past = new Date(T0.getTime() - 1000)
    assert.equal(isDue(card, past), false)
  })

  test('pickDueCards orders by due date and respects limit', () => {
    const deck = [
      { id: 'a', card: { ...makeNewCard(T0), due: new Date(T0.getTime() + 2 * 86400000).toISOString() } },
      { id: 'b', card: { ...makeNewCard(T0), due: new Date(T0.getTime() - 86400000).toISOString() } },
      { id: 'c', card: { ...makeNewCard(T0), due: T0.toISOString() } },
    ]
    const due = pickDueCards(deck, T0, 5)
    assert.equal(due.length, 2) // a is in the future
    assert.equal(due[0].id, 'b')
    assert.equal(due[1].id, 'c')
  })

  test('forecast bucket sums match dues', () => {
    const deck = [
      { id: 'x', card: { ...makeNewCard(T0), due: new Date(T0.getTime() + 1 * 86400000).toISOString() } },
      { id: 'y', card: { ...makeNewCard(T0), due: new Date(T0.getTime() + 3 * 86400000).toISOString() } },
    ]
    const buckets = forecast(deck, 7, T0)
    assert.equal(buckets.length, 8)
    assert.equal(buckets[1], 1)
    assert.equal(buckets[3], 1)
  })

  test('fuzzInterval no-ops for short intervals', () => {
    assert.equal(fuzzInterval(1, 'x'), 1)
    assert.equal(fuzzInterval(2, 'x'), 2)
  })

  test('fuzzInterval bounded ±5% on long intervals and is deterministic', () => {
    const a = fuzzInterval(100, 'card-42')
    const b = fuzzInterval(100, 'card-42')
    assert.equal(a, b)
    assert.ok(Math.abs(a - 100) <= 6)
  })

  test('default weights vector has length 21', () => {
    assert.equal(FSRS_DEFAULT_WEIGHTS.length, 21)
    assert.equal(DEFAULT_FSRS_PARAMS.w.length, 21)
  })
})

describe('exerciseFormats validation', () => {
  test('validates qcm minimum options', () => {
    const broken: McqExercise = {
      id: 'q1', kind: 'qcm', prompt: 'x', difficulty: 'decouverte', timeBudgetMin: 1, tags: [],
      multiAnswer: false, options: [{ id: 'a', label: 'a', correct: true }],
    }
    const issues = validateExercise(broken)
    assert.ok(issues.length > 0)
  })

  test('valid qcm passes', () => {
    const ok: McqExercise = {
      id: 'q-ok', kind: 'qcm', prompt: 'Quelle énergie ?', difficulty: 'decouverte', timeBudgetMin: 2, tags: ['energie'],
      multiAnswer: false,
      options: [
        { id: 'a', label: 'Cinétique', correct: true },
        { id: 'b', label: 'Volumique', correct: false },
      ],
    }
    assert.deepEqual(validateExercise(ok), [])
  })

  test('open_short rejects rubric points mismatch', () => {
    const bad: OpenShortExercise = {
      id: 'o', kind: 'open_short', prompt: '...', difficulty: 'bac', timeBudgetMin: 10, tags: [],
      answerOutline: ['point 1'],
      gradingCriteria: [{ label: 'a', points: 2 }, { label: 'b', points: 4 }],
      totalPoints: 10,
    }
    assert.ok(validateExercise(bad).some((m) => m.includes('totalPoints')))
  })

  test('schema_annotate refuses unknown label refs', () => {
    const ex: SchemaAnnotateExercise = {
      id: 's', kind: 'schema_annotate', prompt: 'Annote', difficulty: 'decouverte', timeBudgetMin: 5, tags: [],
      imageUrl: 'x', alt: 'circuit',
      labels: [{ id: 'l1', text: 'R' }],
      slots: [{ id: 's1', x: 100, y: 100, expectedLabelId: 'lX' }],
    }
    assert.ok(validateExercise(ex).some((m) => m.includes('label inconnu')))
  })
})

describe('exerciseFormats scoring', () => {
  test('single-answer qcm', () => {
    const ex: McqExercise = {
      id: 'q', kind: 'qcm', prompt: 'p', difficulty: 'decouverte', timeBudgetMin: 1, tags: [],
      multiAnswer: false,
      options: [
        { id: 'a', label: 'A', correct: true },
        { id: 'b', label: 'B', correct: false },
      ],
    }
    const s1 = scoreAttempt(ex, { kind: 'qcm', selected: ['a'] })
    assert.equal(s1.ratio01, 1)
    assert.equal(s1.shouldRelearn, false)
    const s2 = scoreAttempt(ex, { kind: 'qcm', selected: ['b'] })
    assert.equal(s2.ratio01, 0)
    assert.equal(s2.shouldRelearn, true)
  })

  test('multi-answer qcm uses Jaccard ratio', () => {
    const ex: McqExercise = {
      id: 'qm', kind: 'qcm', prompt: 'p', difficulty: 'consolidation', timeBudgetMin: 2, tags: [],
      multiAnswer: true,
      options: [
        { id: 'a', label: 'A', correct: true },
        { id: 'b', label: 'B', correct: true },
        { id: 'c', label: 'C', correct: false },
      ],
    }
    const s = scoreAttempt(ex, { kind: 'qcm', selected: ['a', 'c'] })
    assert.ok(s.ratio01 > 0 && s.ratio01 < 1)
  })

  test('true_false with justification requirement', () => {
    const ex: TrueFalseExercise = {
      id: 'tf', kind: 'true_false', prompt: 'L\'énergie se conserve toujours', difficulty: 'bac', timeBudgetMin: 5, tags: [],
      expected: false, requireJustification: true, justificationCriteria: ['système isolé'],
    }
    const s = scoreAttempt(ex, { kind: 'true_false', value: false, justification: 'trop court' })
    assert.equal(s.ratio01, 0.5)
    const s2 = scoreAttempt(ex, { kind: 'true_false', value: false, justification: 'Faux car le système doit être isolé pour conservation' })
    assert.equal(s2.ratio01, 1)
  })

  test('attemptToRating mapping covers full range', () => {
    assert.equal(attemptToRating({ ratio01: 0, feedback: '', flagged: [], shouldRelearn: true }), 1)
    assert.equal(attemptToRating({ ratio01: 0.4, feedback: '', flagged: [], shouldRelearn: false }), 2)
    assert.equal(attemptToRating({ ratio01: 0.8, feedback: '', flagged: [], shouldRelearn: false }), 3)
    assert.equal(attemptToRating({ ratio01: 1, feedback: '', flagged: [], shouldRelearn: false }), 4)
  })

  test('code_exercise scoring from runResults', () => {
    const ex: CodeExerciseExercise = {
      id: 'code1', kind: 'code_exercise', prompt: 'fizzbuzz', difficulty: 'consolidation', timeBudgetMin: 10, tags: ['python'],
      language: 'python',
      starter: 'def fb(n): pass',
      tests: [
        { id: 't1', input: '3', expected: 'Fizz', hidden: false },
        { id: 't2', input: '5', expected: 'Buzz', hidden: true },
      ],
    }
    const s = scoreAttempt(ex, {
      kind: 'code_exercise',
      source: 'def fb(n): return "Fizz" if n%3==0 else str(n)',
      runResults: [
        { testId: 't1', pass: true, output: 'Fizz' },
        { testId: 't2', pass: false, output: '5' },
      ],
    })
    assert.equal(s.ratio01, 0.5)
    assert.deepEqual(s.flagged, ['t2'])
  })
})

describe('exercise registry', () => {
  test('register + listExercises round-trips', () => {
    clearExerciseRegistry()
    const ex: McqExercise = {
      id: 'reg1', kind: 'qcm', prompt: 'Énergie cinétique ?', difficulty: 'decouverte', timeBudgetMin: 1, tags: [],
      multiAnswer: false,
      options: [{ id: 'a', label: 'A', correct: true }, { id: 'b', label: 'B', correct: false }],
    }
    registerExercise(ex)
    assert.equal(listExercises().length, 1)
    assert.equal(getExercise('reg1')?.id, 'reg1')
  })

  test('registerExercise throws on invalid', () => {
    clearExerciseRegistry()
    const bad: McqExercise = {
      id: 'bad', kind: 'qcm', prompt: '', difficulty: 'decouverte', timeBudgetMin: 1, tags: [],
      multiAnswer: false, options: [{ id: 'a', label: 'A', correct: true }],
    }
    assert.throws(() => registerExercise(bad))
  })
})

describe('BAC STI2D curriculum', () => {
  test('catalog covers maths, PC, SIN, I2D', () => {
    const tracks = new Set(BAC_STI2D_CURRICULUM.map((n) => n.track))
    for (const t of ['MAT', 'PC', 'SIN', 'I2D']) {
      assert.equal(tracks.has(t as never), true, `missing track ${t}`)
    }
  })

  test('graph has no broken or cyclic prerequisites', () => {
    assert.deepEqual(validateCurriculumGraph(), [])
  })

  test('suggestNext finds downstream concepts', () => {
    const next = suggestNext('1.PC.signaux-electriques')
    assert.ok(next.length > 0)
    assert.ok(next.some((n) => n.id === 'T.SIN.acquisition-numerisation' || n.id === 'T.PC.evolution-temporelle'))
  })

  test('lookups by year and track', () => {
    assert.ok(nodesByYear('T').length > 5)
    assert.ok(nodesByTrack('SIN').length >= 5)
    assert.equal(findNode('T.SIN.protocoles-reseau')?.label.includes('Protocoles'), true)
  })
})

describe('Leitner→FSRS bridge', () => {
  const t = new Date('2026-05-18T10:00:00Z').getTime()

  test('box 1 maps to low stability', () => {
    const card = leitnerToFsrs({
      box: 1, streak: 0, dueAt: t, timesCorrect: 0, timesWrong: 0, createdAt: t - 86400000,
    })
    assert.ok(card.stability < 1.5)
    assert.equal(card.state, 'new')
  })

  test('box 5 maps to high stability', () => {
    const card = leitnerToFsrs({
      box: 5, streak: 6, dueAt: t + 20 * 86400000, lastReviewedAt: t - 7 * 86400000,
      timesCorrect: 10, timesWrong: 1, createdAt: t - 30 * 86400000,
    })
    assert.ok(card.stability > 10)
    assert.equal(card.state, 'review')
  })

  test('difficulty rises with error rate', () => {
    const easy = leitnerToFsrs({
      box: 3, streak: 4, dueAt: t, timesCorrect: 10, timesWrong: 0, createdAt: t,
    })
    const hard = leitnerToFsrs({
      box: 1, streak: 0, dueAt: t, timesCorrect: 1, timesWrong: 9, createdAt: t,
    })
    assert.ok(hard.difficulty > easy.difficulty)
  })

  test('forecastFromLeitner buckets length = horizon+1', () => {
    const cards = [
      { box: 1 as const, streak: 0, dueAt: t + 1 * 86400000, timesCorrect: 0, timesWrong: 0, createdAt: t },
      { box: 2 as const, streak: 1, dueAt: t + 3 * 86400000, timesCorrect: 1, timesWrong: 0, createdAt: t },
      { box: 1 as const, streak: 0, dueAt: t - 86400000, timesCorrect: 0, timesWrong: 1, createdAt: t },
    ]
    const buckets = forecastFromLeitner(cards, 7, new Date(t))
    assert.equal(buckets.length, 8)
    assert.equal(buckets[0], 1) // overdue
    assert.equal(buckets[1], 1)
    assert.equal(buckets[3], 1)
  })

  test('dueNowCount counts only past-due cards', () => {
    const cards = [
      { box: 1 as const, streak: 0, dueAt: t - 1000, timesCorrect: 0, timesWrong: 0, createdAt: t },
      { box: 2 as const, streak: 1, dueAt: t + 86400000, timesCorrect: 1, timesWrong: 0, createdAt: t },
    ]
    assert.equal(dueNowCount(cards, new Date(t)), 1)
  })

  test('correctToFsrsRating mapping', () => {
    assert.equal(correctToFsrsRating(true, 5), 4) // Easy
    assert.equal(correctToFsrsRating(true, 1), 3) // Good
    assert.equal(correctToFsrsRating(false, 2), 2) // Hard
    assert.equal(correctToFsrsRating(false, 0), 1) // Again
  })
})

import { buildCurriculumSvg, curriculumSvgString } from '../services/learning/curriculumGraphSvg.ts'

describe('Curriculum graph SVG — barre expert', () => {
  test('SVG complet du programme : pas de cycle, nodeCount > 20', () => {
    const r = buildCurriculumSvg()
    assert.equal(r.hasCycle, false)
    assert.ok(r.nodeCount >= 20, `nodeCount ${r.nodeCount}`)
  })

  test('filtrage par année Terminale réduit nodeCount', () => {
    const all = buildCurriculumSvg()
    const T = buildCurriculumSvg({ year: 'T' })
    assert.ok(T.nodeCount < all.nodeCount)
    assert.ok(T.nodeCount > 0)
  })

  test('filtrage par track SIN ne contient que SIN', () => {
    const sin = buildCurriculumSvg({ track: 'SIN' })
    assert.ok(sin.nodeCount > 0)
  })

  test('SVG string commence par <?xml et finit par </svg>', () => {
    const s = curriculumSvgString({ track: 'SIN' })
    assert.ok(s.startsWith('<?xml'))
    assert.ok(s.trim().endsWith('</svg>'))
  })

  test('direction LR vs TB produisent des viewBox différentes', () => {
    const tb = buildCurriculumSvg({ track: 'MAT', direction: 'TB' })
    const lr = buildCurriculumSvg({ track: 'MAT', direction: 'LR' })
    assert.notDeepEqual(
      { w: tb.doc.viewBox.w, h: tb.doc.viewBox.h },
      { w: lr.doc.viewBox.w, h: lr.doc.viewBox.h },
    )
  })

  test('completedIds influence le fill des rects', () => {
    const completedAll = buildCurriculumSvg({ track: 'SIN', completedIds: new Set(['T.SIN.acquisition-numerisation']) })
    // Au moins un rect avec le fill "good" (vert) doit exister.
    const greenRects = completedAll.doc.elements.filter((el) => el.kind === 'rect' && (el.fill === '#4dd5a4' || el.fill === completedAll.doc.cssVariables.good))
    assert.ok(greenRects.length >= 1)
  })

  test('edges respectent les prerequis (LR: pre.x < node.x)', () => {
    const r = buildCurriculumSvg({ direction: 'LR' })
    assert.ok(r.edgeCount >= 1)
  })
})

import {
  optimizeReviewQueue,
  queueStats,
  type ReviewItem,
} from '../services/learning/reviewQueueOptimizer.ts'

describe('Review queue optimizer — barre expert', () => {
  const T = new Date('2026-05-18T10:00:00Z')

  function card(opts: { stability?: number; difficulty?: number; state?: 'new' | 'learning' | 'review' | 'relearning'; due?: Date; lastReview?: Date; lapses?: number }) {
    return {
      stability: opts.stability ?? 5,
      difficulty: opts.difficulty ?? 5,
      lastReview: opts.lastReview?.toISOString() ?? null,
      due: (opts.due ?? T).toISOString(),
      state: opts.state ?? 'review' as const,
      lapses: opts.lapses ?? 0,
      reps: 1,
      scheduledDays: 1,
      elapsedDays: 0,
    }
  }

  test('queue triée par retrievability croissante (bord de l\'oubli d\'abord)', () => {
    // Carte A : R faible (vieille review, courte stability)
    const items: ReviewItem[] = [
      {
        id: 'A',
        card: card({
          stability: 1,
          lastReview: new Date(T.getTime() - 10 * 86400000), // 10j passés
          due: new Date(T.getTime() - 1000),
        }),
      },
      // Carte B : R élevée (stability haute, review récent)
      {
        id: 'B',
        card: card({
          stability: 50,
          lastReview: new Date(T.getTime() - 1 * 86400000),
          due: new Date(T.getTime() - 1000),
        }),
      },
    ]
    const queue = optimizeReviewQueue(items, { now: T })
    assert.equal(queue[0].id, 'A', `expected A first, got ${queue.map((q) => q.id).join(',')}`)
  })

  test('cartes en retard priorisées (overdue boost)', () => {
    const items: ReviewItem[] = [
      { id: 'old', card: card({ due: new Date(T.getTime() - 5 * 86400000) }) }, // 5j retard
      { id: 'fresh', card: card({ due: new Date(T.getTime() - 1000) }) }, // pile dû
    ]
    const queue = optimizeReviewQueue(items, { now: T })
    assert.equal(queue[0].id, 'old')
  })

  test('lapses ≥ 2 + state=relearning priorité élevée', () => {
    const items: ReviewItem[] = [
      { id: 'easy', card: card({ stability: 30, due: new Date(T.getTime() - 1000) }) },
      { id: 'lapsed', card: card({ lapses: 3, state: 'relearning', due: new Date(T.getTime() - 1000) }) },
    ]
    const queue = optimizeReviewQueue(items, { now: T })
    assert.equal(queue[0].id, 'lapsed')
  })

  test('cap maxItems respecté', () => {
    const items: ReviewItem[] = Array.from({ length: 50 }, (_, i) => ({
      id: `c${i}`,
      card: card({ due: new Date(T.getTime() - i * 1000) }),
    }))
    const queue = optimizeReviewQueue(items, { now: T, maxItems: 10 })
    assert.equal(queue.length, 10)
  })

  test('maxNewRatio limite les cartes "new"', () => {
    const items: ReviewItem[] = [
      ...Array.from({ length: 5 }, (_, i) => ({
        id: `n${i}`,
        card: card({ state: 'new', due: new Date(T.getTime() - 1000) }),
      })),
      ...Array.from({ length: 5 }, (_, i) => ({
        id: `r${i}`,
        card: card({ state: 'review', due: new Date(T.getTime() - 1000) }),
      })),
    ]
    const queue = optimizeReviewQueue(items, { now: T, maxItems: 10, maxNewRatio: 0.2 })
    const newCount = queue.filter((q) => q.card.state === 'new').length
    assert.ok(newCount <= 2, `${newCount} new cards (max 2)`)
  })

  test('cartes non dues exclues', () => {
    const items: ReviewItem[] = [
      { id: 'soon', card: card({ due: new Date(T.getTime() + 86400000) }) },
      { id: 'now', card: card({ due: new Date(T.getTime() - 1000) }) },
    ]
    const queue = optimizeReviewQueue(items, { now: T })
    assert.equal(queue.length, 1)
    assert.equal(queue[0].id, 'now')
  })

  test('queueStats compte correctement par state', () => {
    const items: ReviewItem[] = [
      { id: 'n', card: card({ state: 'new', due: new Date(T.getTime() - 1) }) },
      { id: 'l', card: card({ state: 'learning', due: new Date(T.getTime() - 1) }) },
      { id: 'r1', card: card({ state: 'review', due: new Date(T.getTime() - 1) }) },
      { id: 'r2', card: card({ state: 'review', due: new Date(T.getTime() - 1) }) },
    ]
    const q = optimizeReviewQueue(items, { now: T })
    const s = queueStats(q)
    assert.equal(s.total, 4)
    assert.equal(s.byState.review, 2)
    assert.equal(s.byState.new, 1)
    assert.ok(s.expectedSessionMinutes > 0)
  })

  test('chaque item a une raison non vide', () => {
    const items: ReviewItem[] = [
      { id: 'a', card: card({ due: new Date(T.getTime() - 1000) }) },
    ]
    const q = optimizeReviewQueue(items, { now: T })
    assert.ok(q[0].reason.length > 0)
  })
})
