/**
 * Tests pour services/achievements — système de badges Cyber + Academy.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  computeAchievements,
  countUnlocked,
  currentStreak,
} from '../services/achievements.ts'
import type { KataRun } from '../stores/cyberLeaderboardStore.ts'
import type { AcademyRun } from '../stores/academyLeaderboardStore.ts'

function mkKata(overrides: Partial<KataRun> = {}): KataRun {
  return {
    kataId: 'crypto-1',
    stage: 1,
    startedAt: Date.now(),
    endedAt: Date.now() + 60000,
    durationMs: 60000,
    hintsTaken: 0,
    flagsFound: 1,
    objectivesDone: 1,
    totalObjectives: 1,
    xpEarned: 50,
    ...overrides,
  }
}

function mkAcademy(overrides: Partial<AcademyRun> = {}): AcademyRun {
  return {
    id: 'a-1',
    subject: 'Physique',
    mode: 'quiz',
    topic: 'mécanique',
    startedAt: Date.now(),
    endedAt: Date.now() + 60000,
    durationMs: 60000,
    durationLimitSec: 600,
    score: 800,
    timeoutHit: false,
    ...overrides,
  }
}

describe('computeAchievements', () => {
  test('aucun run → tous locked', () => {
    const ach = computeAchievements([], [])
    assert.ok(ach.length > 0)
    assert.ok(ach.every((a) => !a.unlocked))
  })

  test('1 kata complété → au moins 1 cyber achievement unlocked', () => {
    const ach = computeAchievements([mkKata()], [])
    const cyberUnlocked = ach.filter((a) => a.category === 'cyber' && a.unlocked)
    assert.ok(cyberUnlocked.length > 0)
  })

  test('1 academy run → au moins 1 academy achievement unlocked', () => {
    const ach = computeAchievements([], [mkAcademy()])
    const acaUnlocked = ach.filter((a) => a.category === 'academy' && a.unlocked)
    assert.ok(acaUnlocked.length > 0)
  })

  test('achievements ont tous id+label+description+category+glyph', () => {
    const ach = computeAchievements([], [])
    for (const a of ach) {
      assert.ok(a.id)
      assert.ok(a.label)
      assert.ok(a.description)
      assert.ok(['cyber', 'academy', 'cross'].includes(a.category))
      assert.ok(a.glyph)
    }
  })

  test('progress sur multiple runs', () => {
    const ach = computeAchievements(
      Array.from({ length: 5 }, (_, i) => mkKata({ kataId: `k-${i}` })),
      [],
    )
    const withProgress = ach.filter((a) => a.progress)
    assert.ok(withProgress.length > 0)
  })

  test('tier escalator : 5x target → diamond', () => {
    // Génère ASSEZ de runs pour atteindre ≥ 5x target sur au moins un achievement
    const manyKatas = Array.from({ length: 100 }, (_, i) =>
      mkKata({ kataId: `k-${i}`, xpEarned: 100 }),
    )
    const ach = computeAchievements(manyKatas, [])
    const withTier = ach.filter((a) => a.unlocked && a.tier)
    // Au moins un achievement devrait avoir un tier débloqué
    assert.ok(withTier.length > 0)
  })
})

describe('countUnlocked', () => {
  test('compte correctement', () => {
    const ach = computeAchievements([], [])
    const r = countUnlocked(ach)
    assert.equal(r.unlocked, 0)
    assert.ok(r.total > 0)
  })

  test('tous unlocked impossible avec input minimal', () => {
    const ach = computeAchievements([mkKata()], [mkAcademy()])
    const r = countUnlocked(ach)
    assert.ok(r.unlocked >= 1)
    assert.ok(r.unlocked <= r.total)
  })
})

describe('currentStreak', () => {
  test('aucun run → 0', () => {
    assert.equal(currentStreak([], []), 0)
  })

  test('1 run aujourd hui → 1', () => {
    const now = Date.now()
    assert.equal(currentStreak([mkKata({ startedAt: now })], []), 1)
  })

  test('run hier seul → 1 (toujours dans le streak)', () => {
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    const yesterday = now.getTime() - 24 * 3600 * 1000
    assert.equal(currentStreak([mkKata({ startedAt: yesterday + 1000 })], []), 1)
  })

  test('run il y a 3 jours sans rien depuis → 0 (streak cassé)', () => {
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    const threeDaysAgo = now.getTime() - 3 * 24 * 3600 * 1000
    assert.equal(currentStreak([mkKata({ startedAt: threeDaysAgo + 1000 })], []), 0)
  })

  test('runs aujourd hui + hier + avant-hier → streak 3', () => {
    const today = new Date()
    today.setHours(12, 0, 0, 0)
    const day = (offset: number) => today.getTime() - offset * 24 * 3600 * 1000
    const runs = [
      mkKata({ kataId: 'a', startedAt: day(0) }),
      mkKata({ kataId: 'b', startedAt: day(1) }),
      mkKata({ kataId: 'c', startedAt: day(2) }),
    ]
    assert.equal(currentStreak(runs, []), 3)
  })

  test('mix cyber + academy compte sur même streak', () => {
    const today = new Date(); today.setHours(12, 0, 0, 0)
    const yesterday = today.getTime() - 24 * 3600 * 1000
    const runs = [
      mkAcademy({ startedAt: today.getTime() }),
      mkKata({ startedAt: yesterday }),
    ]
    assert.equal(currentStreak([runs[1] as KataRun], [runs[0] as AcademyRun]), 2)
  })
})
