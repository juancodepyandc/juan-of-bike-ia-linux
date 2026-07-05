/**
 * Tests pour stores/cyberLeaderboardStore — leaderboard cyber katas.
 */
import { test, describe, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  useCyberLeaderboardStore,
  formatDuration,
  medalFor,
  type KataRun,
} from '../stores/cyberLeaderboardStore.ts'

before(() => {
  if (typeof globalThis.localStorage === 'undefined') {
    const store = new Map<string, string>()
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => store.set(k, String(v)),
        removeItem: (k: string) => store.delete(k),
        clear: () => store.clear(),
        get length() { return store.size },
        key: (i: number) => Array.from(store.keys())[i] ?? null,
      },
      writable: true,
      configurable: true,
    })
  }
})

beforeEach(() => {
  useCyberLeaderboardStore.getState().clearAll()
})

function mkRun(over: Partial<KataRun> = {}): KataRun {
  return {
    kataId: 'snake',
    stage: 1,
    startedAt: Date.now() - 60000,
    endedAt: Date.now(),
    durationMs: 60000,
    hintsTaken: 0,
    flagsFound: 1,
    objectivesDone: 3,
    totalObjectives: 3,
    xpEarned: 100,
    ...over,
  }
}

describe('formatDuration', () => {
  test('< 1 minute', () => {
    assert.equal(formatDuration(30_000), '0:30')
  })

  test('1 minute pile', () => {
    assert.equal(formatDuration(60_000), '1:00')
  })

  test('plusieurs minutes', () => {
    assert.equal(formatDuration(125_000), '2:05')
  })

  test('≥ 1h → format Xh MM', () => {
    assert.equal(formatDuration(3_600_000 + 5 * 60_000), '1h05')
  })

  test('2h30 exactement', () => {
    assert.equal(formatDuration(2 * 3_600_000 + 30 * 60_000), '2h30')
  })

  test('0ms → "0:00"', () => {
    assert.equal(formatDuration(0), '0:00')
  })

  test('padding secondes', () => {
    assert.equal(formatDuration(7_000), '0:07')
  })
})

describe('medalFor', () => {
  const ref: KataRun = mkRun({ durationMs: 60_000 })

  test('aucun best → 🥇', () => {
    assert.equal(medalFor(ref, null), '🥇')
  })

  test('run = best → 🥇', () => {
    assert.equal(medalFor(ref, ref), '🥇')
  })

  test('run plus rapide → 🥇', () => {
    const faster = mkRun({ durationMs: 30_000 })
    assert.equal(medalFor(faster, ref), '🥇')
  })

  test('run ≤ 125% best → 🥈', () => {
    const silver = mkRun({ durationMs: 70_000 })  // 116% du best
    assert.equal(medalFor(silver, ref), '🥈')
  })

  test('run ≤ 160% best → 🥉', () => {
    const bronze = mkRun({ durationMs: 90_000 })  // 150% du best
    assert.equal(medalFor(bronze, ref), '🥉')
  })

  test('run > 160% best → null', () => {
    const noMedal = mkRun({ durationMs: 200_000 })
    assert.equal(medalFor(noMedal, ref), null)
  })
})

describe('useCyberLeaderboardStore — addRun', () => {
  test('ajoute en tête', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'a' }))
    store.addRun(mkRun({ kataId: 'b' }))
    assert.equal(useCyberLeaderboardStore.getState().runs.length, 2)
    assert.equal(useCyberLeaderboardStore.getState().runs[0].kataId, 'b')
  })

  test('cap à 200 runs', () => {
    const store = useCyberLeaderboardStore.getState()
    for (let i = 0; i < 250; i++) store.addRun(mkRun({ kataId: `k${i}` }))
    assert.equal(useCyberLeaderboardStore.getState().runs.length, 200)
  })
})

describe('bestFor', () => {
  test('aucun run → null', () => {
    assert.equal(useCyberLeaderboardStore.getState().bestFor('snake'), null)
  })

  test('un seul run → renvoie ce run', () => {
    const store = useCyberLeaderboardStore.getState()
    const run = mkRun({ kataId: 'snake', durationMs: 60_000 })
    store.addRun(run)
    assert.equal(useCyberLeaderboardStore.getState().bestFor('snake')?.durationMs, 60_000)
  })

  test('plusieurs runs → meilleur (plus rapide)', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'snake', durationMs: 100_000 }))
    store.addRun(mkRun({ kataId: 'snake', durationMs: 50_000 }))
    store.addRun(mkRun({ kataId: 'snake', durationMs: 75_000 }))
    assert.equal(useCyberLeaderboardStore.getState().bestFor('snake')?.durationMs, 50_000)
  })

  test('filtre par stage', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'snake', stage: 1, durationMs: 50_000 }))
    store.addRun(mkRun({ kataId: 'snake', stage: 2, durationMs: 30_000 }))
    assert.equal(useCyberLeaderboardStore.getState().bestFor('snake', 1)?.durationMs, 50_000)
    assert.equal(useCyberLeaderboardStore.getState().bestFor('snake', 2)?.durationMs, 30_000)
  })

  test('kataId inconnu → null', () => {
    useCyberLeaderboardStore.getState().addRun(mkRun({ kataId: 'snake' }))
    assert.equal(useCyberLeaderboardStore.getState().bestFor('xyz'), null)
  })
})

describe('bestScoreFor (épreuve)', () => {
  test('aucun run épreuve → null', () => {
    useCyberLeaderboardStore.getState().addRun(mkRun({ kataId: 'snake', mode: 'libre' }))
    assert.equal(useCyberLeaderboardStore.getState().bestScoreFor('snake'), null)
  })

  test('runs épreuve seulement → meilleur score', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'snake', mode: 'epreuve', score: 50 }))
    store.addRun(mkRun({ kataId: 'snake', mode: 'epreuve', score: 80 }))
    store.addRun(mkRun({ kataId: 'snake', mode: 'libre', score: 99 }))  // ignoré
    assert.equal(useCyberLeaderboardStore.getState().bestScoreFor('snake')?.score, 80)
  })
})

describe('runsFor / epreuveRunsFor', () => {
  test('runsFor renvoie tous les runs d un kata', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'a' }))
    store.addRun(mkRun({ kataId: 'a' }))
    store.addRun(mkRun({ kataId: 'b' }))
    assert.equal(useCyberLeaderboardStore.getState().runsFor('a').length, 2)
    assert.equal(useCyberLeaderboardStore.getState().runsFor('b').length, 1)
  })

  test('epreuveRunsFor filtre par mode=epreuve', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ kataId: 'a', mode: 'libre' }))
    store.addRun(mkRun({ kataId: 'a', mode: 'epreuve' }))
    store.addRun(mkRun({ kataId: 'a', mode: 'epreuve' }))
    assert.equal(useCyberLeaderboardStore.getState().epreuveRunsFor('a').length, 2)
  })
})

describe('totalTimeMs + clearAll', () => {
  test('totalTimeMs somme toutes durées', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun({ durationMs: 30_000 }))
    store.addRun(mkRun({ durationMs: 60_000 }))
    assert.equal(useCyberLeaderboardStore.getState().totalTimeMs(), 90_000)
  })

  test('clearAll vide la liste', () => {
    const store = useCyberLeaderboardStore.getState()
    store.addRun(mkRun())
    store.clearAll()
    assert.equal(useCyberLeaderboardStore.getState().runs.length, 0)
  })
})
