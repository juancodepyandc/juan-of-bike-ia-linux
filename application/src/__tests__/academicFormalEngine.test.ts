import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  SI_DIMENSIONS,
  areDimensionsEqual,
  computeSecondOrderResponse,
  auditThermodynamicHeatEngine,
  auditMathematicalProof,
} from '../services/learning/academicFormalEngine.ts'

describe('Academic Formal Engine — Dimensional Analysis', () => {
  it('identifie correctement l equivalence travail/energie et force*distance', () => {
    const force = SI_DIMENSIONS.force
    const length = SI_DIMENSIONS.length
    const workCalculated = {
      length: force.length + length.length,
      mass: force.mass + length.mass,
      time: force.time + length.time,
      current: force.current + length.current,
      temp: force.temp + length.temp,
      amount: force.amount + length.amount,
      luminous: force.luminous + length.luminous,
    }
    assert.equal(areDimensionsEqual(workCalculated, SI_DIMENSIONS.energy), true)
  })

  it('detecte une incoherence dimensionnelle entre puissance et tension', () => {
    assert.equal(areDimensionsEqual(SI_DIMENSIONS.power, SI_DIMENSIONS.voltage), false)
  })
})

describe('Academic Formal Engine — Control Theory (Second Order)', () => {
  it('calcule exactement le depassement et la stabilite pour z=0.5, wn=10 rad/s', () => {
    const res = computeSecondOrderResponse(2.0, 0.5, 10)
    assert.equal(res.isStable, true)
    // Pour z=0.5, D% = 100 * exp(-pi*0.5 / sqrt(0.75)) = 100 * exp(-1.813799) = 16.3%
    assert.equal(res.overshootPercent, 16.3)
    assert.equal(res.peakTimeS, 0.363)
    assert.equal(res.settlingTime5PercentS, 0.6)
    assert.equal(res.poles.length, 2)
    assert.equal(res.poles[0].real, -5)
  })

  it('traite un systeme a amortissement critique (z=1)', () => {
    const res = computeSecondOrderResponse(1.0, 1.0, 5)
    assert.equal(res.isStable, true)
    assert.equal(res.overshootPercent, 0)
    assert.equal(res.poles[0].real, -5)
    assert.equal(res.poles[0].imag, 0)
  })
})

describe('Academic Formal Engine — Thermodynamics Laws Verification', () => {
  it('valide un moteur thermique reversible respectant les 2 principes', () => {
    // T_hot = 600 K, T_cold = 300 K -> Carnot = 50%
    // Qin = 1000 J, W = 500 J, Qout = 500 J -> eta = 50%
    const audit = auditThermodynamicHeatEngine(1000, 500, 500, 600, 300)
    assert.equal(audit.isValidFirstLaw, true)
    assert.equal(audit.isValidSecondLaw, true)
    assert.equal(audit.carnotEfficiency, 0.5)
    assert.equal(audit.actualEfficiency, 0.5)
    assert.equal(audit.discrepancies.length, 0)
  })

  it('rejette un moteur pretendument sur-unitaire (violation 2nd principe)', () => {
    // T_hot = 500 K, T_cold = 300 K -> Carnot = 40%
    // Qin = 1000 J, W = 600 J, Qout = 400 J -> eta = 60% > 40% (impossible)
    const audit = auditThermodynamicHeatEngine(1000, 400, 600, 500, 300)
    assert.equal(audit.isValidFirstLaw, true)
    assert.equal(audit.isValidSecondLaw, false)
    assert.equal(audit.discrepancies.length > 0, true)
  })
})

describe('Academic Formal Engine — Proof Rigour Verification', () => {
  it('valide une demonstration rigoureuse sans sophisme', () => {
    const audit = auditMathematicalProof(
      'La somme de deux entiers pairs est paire',
      ['Soit a et b deux entiers pairs'],
      [
        { stepNumber: 1, statement: 'Il existe k et p tels que a = 2k et b = 2p', justification: 'Definition d un entier pair' },
        { stepNumber: 2, statement: 'a + b = 2k + 2p = 2(k + p)', justification: 'Distributivite de la multiplication sur l addition' },
        { stepNumber: 3, statement: 'k + p est un entier m', justification: 'Stabilite de Z par addition' },
      ],
      'a + b = 2m avec m entier, donc a + b est pair',
    )
    assert.equal(audit.isSound, true)
    assert.equal(audit.score, 100)
    assert.equal(audit.flaws.length, 0)
  })

  it('detecte un raisonnement circulaire', () => {
    const audit = auditMathematicalProof(
      'Theoreme X',
      ['Hypothese H'],
      [
        { stepNumber: 1, statement: 'Etape 1', justification: 'D apres le Theoreme X' },
      ],
      'Donc Theoreme X est vrai',
    )
    assert.equal(audit.isSound, false)
    assert.equal(audit.flaws.some((f) => f.includes('circulaire')), true)
  })
})
