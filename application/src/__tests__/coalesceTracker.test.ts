/**
 * Tests pour CoalesceTracker — utilitaire générique de fenêtrage temporel.
 * Utilisé par auroraVoice pour dédoublonner les annonces TTS rapprochées.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { CoalesceTracker } from '../utils/coalesceTracker.ts'

describe('CoalesceTracker', () => {
  test('première occurrence d une clé est acceptée', () => {
    const t = new CoalesceTracker(1000)
    assert.equal(t.shouldAllow('image:completed', 0), true)
  })

  test('seconde occurrence dans la fenêtre est refusée', () => {
    const t = new CoalesceTracker(2500)
    t.shouldAllow('image:completed', 0)
    assert.equal(t.shouldAllow('image:completed', 1500), false)
    assert.equal(t.shouldAllow('image:completed', 2499), false)
  })

  test('occurrence après la fenêtre est ré-acceptée', () => {
    const t = new CoalesceTracker(2500)
    t.shouldAllow('image:completed', 0)
    assert.equal(t.shouldAllow('image:completed', 2500), true)
    assert.equal(t.shouldAllow('image:completed', 5000), true)
  })

  test('clés indépendantes ne se bloquent pas mutuellement', () => {
    const t = new CoalesceTracker(2500)
    t.shouldAllow('image:completed', 0)
    assert.equal(t.shouldAllow('code:completed', 100), true)
    assert.equal(t.shouldAllow('3d:completed', 200), true)
    // image, lui, est toujours bloqué
    assert.equal(t.shouldAllow('image:completed', 300), false)
  })

  test('reset vide tout', () => {
    const t = new CoalesceTracker(2500)
    t.shouldAllow('a', 0)
    t.shouldAllow('b', 0)
    assert.equal(t.size(), 2)
    t.reset()
    assert.equal(t.size(), 0)
    // Après reset, on peut accepter à nouveau dans la même fenêtre
    assert.equal(t.shouldAllow('a', 100), true)
  })

  test('même clé sur deux occurrences successives strictement dans la fenêtre', () => {
    const t = new CoalesceTracker(2500)
    // T=0 accepted
    assert.equal(t.shouldAllow('x', 0), true)
    // T=1ms rejected
    assert.equal(t.shouldAllow('x', 1), false)
    // T=2499ms rejected (frontière exclusive)
    assert.equal(t.shouldAllow('x', 2499), false)
    // T=2500ms accepted (frontière inclusive)
    assert.equal(t.shouldAllow('x', 2500), true)
  })

  test('Date.now par défaut quand pas de now passé', () => {
    const t = new CoalesceTracker(2500)
    assert.equal(t.shouldAllow('y'), true)
    // immediately re-call: should be refused (we're within 2500ms of Date.now)
    assert.equal(t.shouldAllow('y'), false)
  })
})
