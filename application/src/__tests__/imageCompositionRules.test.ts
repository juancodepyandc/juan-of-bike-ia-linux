/**
 * Tests règles de composition.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeComposition,
  recommendPlacement,
} from '../services/imageCompositionRules.ts'

describe('analyzeComposition', () => {
  test('sujet à 1/3 1/3 → rule-of-thirds bon score', () => {
    const r = analyzeComposition([{ x: 1 / 3, y: 1 / 3, weight: 1 }])
    const thirds = r.scores.find((s) => s.rule === 'rule-of-thirds')!
    assert.ok(thirds.score > 0.8, `score thirds ${thirds.score}`)
  })

  test('sujet pile au centre → rule centered bon score', () => {
    const r = analyzeComposition([{ x: 0.5, y: 0.5, weight: 1 }])
    const centered = r.scores.find((s) => s.rule === 'centered')!
    assert.ok(centered.score > 0.8)
  })

  test('sujet sur golden ratio → golden-ratio bon score', () => {
    const r = analyzeComposition([{ x: 1 / 1.618, y: 1 / 1.618, weight: 1 }])
    const golden = r.scores.find((s) => s.rule === 'golden-ratio')!
    assert.ok(golden.score > 0.8)
  })

  test('sujet dans un coin → toutes règles bas score', () => {
    const r = analyzeComposition([{ x: 0.05, y: 0.05, weight: 1 }])
    assert.ok(r.bestRule.score < 0.5)
    assert.equal(r.isWellComposed, false)
  })

  test('aucun focal → indéterminé', () => {
    const r = analyzeComposition([])
    assert.equal(r.isWellComposed, false)
  })

  test('bestRule prend le meilleur score', () => {
    const r = analyzeComposition([{ x: 0.5, y: 0.5, weight: 1 }])
    const max = Math.max(...r.scores.map((s) => s.score))
    assert.equal(r.bestRule.score, max)
  })

  test('verdict text contient le nom de la règle', () => {
    const r = analyzeComposition([{ x: 1 / 3, y: 1 / 3, weight: 1 }])
    assert.match(r.bestRule.verdict, /rule-of-thirds|thirds/)
  })

  test('plusieurs focals pondérés respectent le weight', () => {
    const r = analyzeComposition([
      { x: 0.5, y: 0.5, weight: 0.1 }, // peu important, centré
      { x: 1 / 3, y: 1 / 3, weight: 1.0 }, // important, sur thirds
    ])
    const thirds = r.scores.find((s) => s.rule === 'rule-of-thirds')!
    assert.ok(thirds.score > 0.7)
  })
})

describe('recommendPlacement', () => {
  test('classic → thirds top-left', () => {
    const p = recommendPlacement('classic')
    assert.ok(Math.abs(p.x - 1 / 3) < 0.01)
    assert.ok(Math.abs(p.y - 1 / 3) < 0.01)
  })

  test('landscape → horizon dans le tiers bas (y = 2/3)', () => {
    const p = recommendPlacement('landscape')
    assert.ok(Math.abs(p.y - 2 / 3) < 0.01)
  })

  test('portrait → légèrement au-dessus du centre', () => {
    const p = recommendPlacement('portrait')
    assert.ok(p.y < 0.5)
  })

  test('cinematic → décalé vers centre-bas', () => {
    const p = recommendPlacement('cinematic')
    assert.ok(p.y > 0.5)
  })
})
