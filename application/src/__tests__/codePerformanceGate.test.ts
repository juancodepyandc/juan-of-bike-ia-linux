// Performance mesuree au rendu.
//
// Le module jugeait le style, la composition et l accessibilite a l ecran. La
// performance manquait — et c est le dernier critere qui separe « joli » de
// « professionnel »: une page magnifique qui saute pendant le chargement ou qui
// empile 4 800 noeuds est un mauvais livrable, quel que soit son score
// esthetique.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { BUDGETS, scorePerformance, type PerformanceMetrics } from '../services/codePerformanceGate.ts'

// Valeurs reellement mesurees sur le convertisseur livre (run 971).
const healthy: PerformanceMetrics = {
  firstContentfulPaint: 244,
  domInteractive: 78,
  layoutShift: 0,
  domNodes: 22,
  transferredBytes: 7309,
  longTasks: 0,
  imagesWithoutDimensions: 0,
}

describe('performance — une page saine passe', () => {
  const verdict = scorePerformance(healthy)

  test('elle atteint 100 et passe le seuil', () => {
    assert.equal(verdict.score, 100)
    assert.equal(verdict.ok, true)
    assert.deepEqual(verdict.failedChecks, [])
  })

  test('la critique ne reproche rien', () => {
    assert.match(verdict.critique, /dans les budgets/)
  })
})

describe('performance — chaque defaut est attrape', () => {
  test('une premiere peinture lente', () => {
    const verdict = scorePerformance({ ...healthy, firstContentfulPaint: 2400 })
    assert.equal(verdict.failedChecks.includes('first_paint'), true)
    assert.match(verdict.critique, /2400 ms/)
  })

  test('un saut de page', () => {
    const verdict = scorePerformance({ ...healthy, layoutShift: 0.42 })
    assert.equal(verdict.failedChecks.includes('layout_stability'), true)
    assert.match(verdict.critique, /0\.420/)
  })

  test('un DOM trop lourd — mesure reelle sur une page de 1 200 lignes', () => {
    const verdict = scorePerformance({ ...healthy, domNodes: 4810 })
    assert.equal(verdict.failedChecks.includes('dom_weight'), true)
    assert.match(verdict.critique, /4810 noeuds/)
  })

  test('des images sans dimensions', () => {
    const verdict = scorePerformance({ ...healthy, imagesWithoutDimensions: 3 })
    assert.equal(verdict.failedChecks.includes('image_dimensions'), true)
    assert.match(verdict.critique, /saut de page/)
  })

  test('un fil principal bloque', () => {
    assert.equal(scorePerformance({ ...healthy, longTasks: 9 }).failedChecks.includes('main_thread'), true)
  })

  test('une charge trop lourde', () => {
    const verdict = scorePerformance({ ...healthy, transferredBytes: 9_000_000 })
    assert.equal(verdict.failedChecks.includes('payload_weight'), true)
    assert.match(verdict.critique, /8789 Ko/)
  })
})

describe('performance — la notation reste honnete', () => {
  test('une page catastrophique tombe a 0', () => {
    const verdict = scorePerformance({
      firstContentfulPaint: 5200,
      domInteractive: 7000,
      layoutShift: 0.9,
      domNodes: 12000,
      transferredBytes: 20_000_000,
      longTasks: 14,
      imagesWithoutDimensions: 8,
    })
    assert.equal(verdict.score, 0)
    assert.equal(verdict.ok, false)
  })

  test('une mesure absente ne compte pas comme une reussite', () => {
    // Un FCP a 0 signifie « non mesure », pas « instantane ».
    assert.equal(scorePerformance({ ...healthy, firstContentfulPaint: 0 }).failedChecks.includes('first_paint'), true)
  })

  test('un defaut isole ne condamne pas la page', () => {
    assert.equal(scorePerformance({ ...healthy, longTasks: 9 }).ok, true)
  })

  test('les budgets locaux sont plus severes que les reperes publics', () => {
    // En local il n y a ni reseau ni latence serveur: 1200 ms, pas 1800.
    assert.ok(BUDGETS.firstContentfulPaint < 1800)
    assert.equal(BUDGETS.layoutShift, 0.1)
  })
})
