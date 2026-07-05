/**
 * Tests pour services/imageVariationPicker — multi-axe scoring de variations FLUX.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  scoreVariation,
  pickBestVariation,
  measurePromptFidelity,
  measurePaletteMatch,
} from '../services/imageVariationPicker.ts'

function mkFeatures(overrides: Partial<{
  id: string
  promptFidelity: number
  compositionScore: number
  sharpnessScore: number
  paletteMatch: number
  artefactPenalty: number
}> = {}) {
  return {
    id: 'v1',
    promptFidelity: 0.8,
    compositionScore: 0.8,
    sharpnessScore: 0.8,
    paletteMatch: 0.8,
    artefactPenalty: 0,
    ...overrides,
  }
}

describe('scoreVariation', () => {
  test('toutes axes hautes + 0 artefacts → overall élevé', () => {
    const r = scoreVariation(mkFeatures({
      promptFidelity: 1, compositionScore: 1, sharpnessScore: 1, paletteMatch: 1, artefactPenalty: 0,
    }))
    assert.ok(r.overall > 0.95)
  })

  test('artefacts élevés → pénalité', () => {
    const a = scoreVariation(mkFeatures({ artefactPenalty: 0 }))
    const b = scoreVariation(mkFeatures({ artefactPenalty: 1 }))
    assert.ok(b.overall < a.overall)
  })

  test('axes clamp [0..1]', () => {
    const r = scoreVariation(mkFeatures({ promptFidelity: 2.5, sharpnessScore: -1 }))
    assert.equal(r.axes.fidelity, 1)
    assert.equal(r.axes.sharpness, 0)
  })

  test('rationale mentionne fidèle quand fidelity > 0.85', () => {
    const r = scoreVariation(mkFeatures({ promptFidelity: 0.9 }))
    assert.ok(r.rationale.includes('fidèle'))
  })

  test('rationale mentionne artefacts quand penalty > 0.4', () => {
    const r = scoreVariation(mkFeatures({ artefactPenalty: 0.5 }))
    assert.ok(r.rationale.includes('artefacts'))
  })

  test('rationale fallback "qualité moyenne" quand neutre', () => {
    const r = scoreVariation(mkFeatures({
      promptFidelity: 0.7, compositionScore: 0.7, sharpnessScore: 0.7, paletteMatch: 0.7, artefactPenalty: 0.1,
    }))
    assert.equal(r.rationale, 'qualité moyenne')
  })
})

describe('pickBestVariation', () => {
  test('aucun candidat → throw', () => {
    assert.throws(() => pickBestVariation([]))
  })

  test('1 candidat → winner = lui', () => {
    const r = pickBestVariation([mkFeatures({ id: 'only' })])
    assert.equal(r.winner.features.id, 'only')
    assert.equal(r.ambiguous, false)
  })

  test('3 candidats triés par overall desc', () => {
    const c = [
      mkFeatures({ id: 'low', promptFidelity: 0.3 }),
      mkFeatures({ id: 'high', promptFidelity: 0.95 }),
      mkFeatures({ id: 'mid', promptFidelity: 0.6 }),
    ]
    const r = pickBestVariation(c)
    assert.equal(r.winner.features.id, 'high')
    assert.equal(r.ranked[0].features.id, 'high')
    assert.equal(r.ranked[2].features.id, 'low')
  })

  test('2 candidats proches → ambiguous', () => {
    const c = [
      mkFeatures({ id: 'a', promptFidelity: 0.85, compositionScore: 0.85 }),
      mkFeatures({ id: 'b', promptFidelity: 0.86, compositionScore: 0.85 }),
    ]
    const r = pickBestVariation(c)
    assert.equal(r.ambiguous, true)
  })

  test('winner < 0.5 → regenerateAdvised true', () => {
    const r = pickBestVariation([
      mkFeatures({ promptFidelity: 0.2, compositionScore: 0.2, sharpnessScore: 0.2, paletteMatch: 0.2, artefactPenalty: 0.5 }),
    ])
    assert.equal(r.regenerateAdvised, true)
  })
})

describe('measurePromptFidelity', () => {
  test('texte identique → score haut', () => {
    const s = measurePromptFidelity('chat noir grand prairie', 'chat noir grand prairie sous le soleil')
    assert.ok(s > 0.5)
  })

  test('prompt vide → 0', () => {
    assert.equal(measurePromptFidelity('', 'something'), 0)
    assert.equal(measurePromptFidelity('chat', ''), 0)
  })

  test('aucun recouvrement → score bas', () => {
    const s = measurePromptFidelity('chat noir', 'voiture rouge moteur')
    assert.ok(s < 0.5)
  })

  test('bigrammes communs → boost', () => {
    const a = measurePromptFidelity('chat noir', 'chat noir absent')
    const b = measurePromptFidelity('chat noir', 'noir chat sans bigramme commun')
    assert.ok(a >= b)
  })
})

describe('measurePaletteMatch', () => {
  test('aucune contrainte → 1 (passthrough)', () => {
    assert.equal(measurePaletteMatch(['#ff0000'], []), 1)
  })

  test('aucun dominant → 0', () => {
    assert.equal(measurePaletteMatch([], ['#ff0000']), 0)
  })

  test('couleur exacte → score élevé', () => {
    const s = measurePaletteMatch(['#ff0000'], ['#ff0000'])
    assert.ok(s > 0.95)
  })

  test('couleurs opposées → score bas', () => {
    const s = measurePaletteMatch(['#000000'], ['#ffffff'])
    assert.ok(s < 0.2)
  })

  test('hex invalide → filtré', () => {
    // Pas d'hex valide ni demandé ni dominant → 0
    const s = measurePaletteMatch(['notahex'], ['alsonothex'])
    assert.equal(s, 0)
  })
})
