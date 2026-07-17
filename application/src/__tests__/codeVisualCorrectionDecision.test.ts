import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  MAX_VISUAL_CORRECTION_PASSES,
  buildVisualFixDirective,
  decideVisualCorrection,
} from '../services/codeVisualCorrectionDecision.ts'
import type { VisualFidelityReport } from '../services/codeVisualFidelity.ts'

function report(overrides: Partial<VisualFidelityReport> = {}): VisualFidelityReport {
  return {
    score: 55,
    passed: false,
    floor: 70,
    checks: [
      { id: 'contrast', label: 'Contraste insuffisant', passed: false, weight: 30 },
      { id: 'spacing', label: 'Espacement irregulier', passed: false, weight: 20 },
    ],
    failedChecks: ['contrast', 'spacing'],
    summary: 'Rendu terne, contraste faible.',
    source: 'render_audit',
    viewports: ['desktop', 'mobile'],
    ...overrides,
  }
}

describe('codeVisualCorrectionDecision', () => {
  test('un rendu au-dessus du seuil est accepte sans regen', () => {
    const decision = decideVisualCorrection({
      report: report({ score: 88, passed: true }),
      passIndex: 0,
    })
    assert.equal(decision.regenerate, false)
    assert.equal(decision.reason, 'visual:passed')
  })

  test('un projet non visuel (passed, floor 0) est accepte', () => {
    const decision = decideVisualCorrection({
      report: report({ score: 100, passed: true, floor: 0, failedChecks: [] }),
      passIndex: 0,
    })
    assert.equal(decision.regenerate, false)
    assert.equal(decision.reason, 'visual:passed')
  })

  test('un rendu sous le seuil declenche une regen ciblee avec directive', () => {
    const decision = decideVisualCorrection({ report: report(), passIndex: 0 })
    assert.equal(decision.regenerate, true)
    assert.match(decision.reason, /below-threshold:55<70/)
    assert.ok(decision.directive && decision.directive.includes('CORRECTION VISUELLE'))
    // La directive porte le score et le plancher pour cadrer la correction.
    assert.match(decision.directive!, /55\/100/)
  })

  test('le budget de passes est borne', () => {
    const decision = decideVisualCorrection({
      report: report(),
      passIndex: MAX_VISUAL_CORRECTION_PASSES,
    })
    assert.equal(decision.regenerate, false)
    assert.equal(decision.reason, 'visual:budget-exhausted')
  })

  test('on n insiste pas si la regen precedente n a pas assez ameliore', () => {
    const decision = decideVisualCorrection({
      report: report({ score: 56 }),
      passIndex: 1,
      previousVisualScore: 55, // +1 seulement -> sous le seuil d amelioration
    })
    assert.equal(decision.regenerate, false)
    assert.equal(decision.reason, 'visual:no-improvement')
  })

  test('on continue si la regen precedente a nettement ameliore mais reste sous le seuil', () => {
    const decision = decideVisualCorrection({
      report: report({ score: 64 }),
      passIndex: 1,
      previousVisualScore: 55, // +9 -> ca progresse, on tente encore
    })
    assert.equal(decision.regenerate, true)
  })

  test('buildVisualFixDirective cible l apparence sans casser le contenu', () => {
    const directive = buildVisualFixDirective(report())
    assert.match(directive, /UNIQUEMENT l apparence/)
    assert.match(directive, /Ne casse aucune fonctionnalite/)
  })
})
