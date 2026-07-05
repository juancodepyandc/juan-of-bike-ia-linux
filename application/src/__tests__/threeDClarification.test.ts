/**
 * v77zg: validate targeted 3D clarification questions. The 3D pipeline goes
 * silent and ships arbitrary defaults when these are wrong, so a regression
 * here means real-person reproductions revert to T-pose mannequins, vehicles
 * to static turntables, etc.
 *
 * Run: node --experimental-strip-types src/__tests__/threeDClarification.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { detectThreeDClarification, isPersonReproductionPrompt } from '../services/threeDClarification.ts'

const baseContext = {
  prompt: '',
  purpose: 'visual_preview' as const,
  subjectKind: 'object' as const,
  systemClass: 'generic',
  motionReadiness: 'static_only' as const,
  motionVerbHint: null,
  hasImageReference: false,
  hasDimensionalSignal: false,
  hasMaterialHint: false,
}

describe('detectThreeDClarification — person_reproduction has highest priority', () => {
  test('portrait keyword on character → person_reproduction', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'portrait realiste de Marie en 3D',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'person_reproduction')
    assert.ok(result!.options.some((opt) => /multi-vues|multi vues|profil/i.test(opt)))
  })

  test('"ressemble a" keyword triggers person_reproduction', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'un personnage qui ressemble a un homme connu',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'person_reproduction')
  })

  test('lookalike keyword in english', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a 3D lookalike model of a real person',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'person_reproduction')
  })
})

describe('detectThreeDClarification — character_anatomy when no anatomy hint', () => {
  test('"un guerrier" no gender/pose → character_anatomy', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'un guerrier elfique',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'character_anatomy')
    assert.ok(result!.options.some((opt) => /T-?pose|A-?pose/i.test(opt)))
  })

  test('character with explicit "homme" skips clarification', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'un homme guerrier en T-pose',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.notEqual(result?.category, 'character_anatomy')
  })

  test('character with explicit pose skips anatomy clarification', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'un personnage hero en pose dynamique de combat',
      purpose: 'character',
      subjectKind: 'character',
    })
    // pose hint present → not anatomy ambiguity
    assert.notEqual(result?.category, 'character_anatomy')
  })
})

describe('detectThreeDClarification — mechanism_motion', () => {
  test('articulated mechanism without motion verb → mechanism_motion', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a complex gearbox assembly',
      purpose: 'mechanical_part',
      subjectKind: 'assembly',
      motionReadiness: 'articulated',
    })
    assert.equal(result?.category, 'mechanism_motion')
    assert.ok(result!.options.some((opt) => /rotation|engrenage|pendule/i.test(opt)))
  })

  test('articulated mechanism with motion verb skips mechanism clarification', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a gearbox that rotates continuously',
      purpose: 'mechanical_part',
      subjectKind: 'assembly',
      motionReadiness: 'articulated',
      motionVerbHint: 'rotating',
    })
    assert.notEqual(result?.category, 'mechanism_motion')
  })
})

describe('detectThreeDClarification — vehicle_motion', () => {
  test('vehicle without motion verb → vehicle_motion', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a sleek sports car',
      purpose: 'product',
      subjectKind: 'vehicle',
    })
    assert.equal(result?.category, 'vehicle_motion')
    assert.ok(result!.options.some((opt) => /roues|wheel|rolling/i.test(opt)))
  })

  test('vehicle with rolling verb skips clarification', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'voiture qui roule sur la route',
      purpose: 'product',
      subjectKind: 'vehicle',
      motionVerbHint: 'rolling',
    })
    assert.notEqual(result?.category, 'vehicle_motion')
  })

  test('parked vehicle skips clarification', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a parked truck displayed in a showroom',
      purpose: 'product',
      subjectKind: 'vehicle',
    })
    assert.notEqual(result?.category, 'vehicle_motion')
  })
})

describe('detectThreeDClarification — material_ambiguous', () => {
  test('"un vase" without material → material_ambiguous', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'un vase decoratif',
      purpose: 'product',
      subjectKind: 'product',
    })
    assert.equal(result?.category, 'material_ambiguous')
    assert.ok(result!.options.some((opt) => /ceramique|verre|metal/i.test(opt)))
  })

  test('"epee en acier" with material → no clarification needed', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'epee en acier poli avec garde dorée',
      purpose: 'product',
      subjectKind: 'product',
    })
    // explicit material → no material ambiguity
    assert.notEqual(result?.category, 'material_ambiguous')
  })
})

describe('detectThreeDClarification — dimensional_precision is last resort', () => {
  test('mechanical part without dimensions → dimensional_precision', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a small precision bracket',
      purpose: 'mechanical_part',
      subjectKind: 'mechanical_part',
    })
    assert.equal(result?.category, 'dimensional_precision')
  })

  test('mechanical part with explicit dimension skips', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a precision bracket 50mm x 30mm',
      purpose: 'mechanical_part',
      subjectKind: 'mechanical_part',
      hasDimensionalSignal: true,
    })
    assert.equal(result, null)
  })
})

describe('isPersonReproductionPrompt — multi-view forcing predicate (v77zk)', () => {
  test('"portrait" matches', () => {
    assert.equal(isPersonReproductionPrompt('portrait realiste de Marie'), true)
  })

  test('"ressemble a" matches', () => {
    assert.equal(isPersonReproductionPrompt('un personnage qui ressemble a un homme connu'), true)
  })

  test('"lookalike" matches', () => {
    assert.equal(isPersonReproductionPrompt('a 3D lookalike model'), true)
  })

  test('"recreate a person" matches', () => {
    assert.equal(isPersonReproductionPrompt('recreate a person from this photo'), true)
  })

  test('"moi en 3d" matches', () => {
    assert.equal(isPersonReproductionPrompt('je veux moi en 3d'), true)
  })

  test('"deepfake" matches', () => {
    assert.equal(isPersonReproductionPrompt('a deepfake style 3d model'), true)
  })

  test('first-name + "en 3d" matches', () => {
    assert.equal(isPersonReproductionPrompt('Jean en 3d model'), true)
  })

  test('generic "personnage fictif" does NOT match', () => {
    assert.equal(isPersonReproductionPrompt('un personnage fictif elfique'), false)
  })

  test('object prompt does NOT match', () => {
    assert.equal(isPersonReproductionPrompt('a vase decoratif en ceramique'), false)
  })

  test('empty prompt does NOT match', () => {
    assert.equal(isPersonReproductionPrompt(''), false)
  })
})

describe('detectThreeDClarification — v77zz motion_intensity', () => {
  test('"saute" on character with no modifier → motion_intensity', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'le perso saute',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'motion_intensity')
    assert.match(result!.question, /intensite/i)
    assert.equal(result!.options.length, 4)
  })

  test('"danse" with "rapidement" → no motion_intensity (modifier present)', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'danse rapidement',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.notEqual(result?.category, 'motion_intensity')
  })

  test('"chien galope" without modifier → motion_intensity', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'le chien galope',
      purpose: 'visual_preview',
      subjectKind: 'creature',
    })
    assert.equal(result?.category, 'motion_intensity')
  })

  test('"saute haut" → no motion_intensity (intensity already present)', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'le perso saute haut',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.notEqual(result?.category, 'motion_intensity')
  })

  test('motion verb on object subject → no motion_intensity (rule character/creature only)', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a generic dancing object',
      purpose: 'visual_preview',
      subjectKind: 'object',
    })
    assert.notEqual(result?.category, 'motion_intensity')
  })

  test('character without motion verb → no motion_intensity', () => {
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a fantasy elf with armor',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.notEqual(result?.category, 'motion_intensity')
  })

  test('English motion verb still triggers (no fictional-character hint)', () => {
    // Need to dodge character_anatomy (which catches generic fictional
    // characters without anatomy/pose hints) — "muscular man" provides an
    // anatomy hint so character_anatomy doesn't fire, letting motion_intensity
    // pick up the "jumping" verb.
    const result = detectThreeDClarification({
      ...baseContext,
      prompt: 'a muscular man jumping',
      purpose: 'character',
      subjectKind: 'character',
    })
    assert.equal(result?.category, 'motion_intensity')
  })
})

describe('detectThreeDClarification — empty / trivial input', () => {
  test('empty prompt → null', () => {
    assert.equal(detectThreeDClarification({ ...baseContext, prompt: '' }), null)
  })

  test('whitespace prompt → null', () => {
    assert.equal(detectThreeDClarification({ ...baseContext, prompt: '   ' }), null)
  })

  test('1-char prompt → null', () => {
    assert.equal(detectThreeDClarification({ ...baseContext, prompt: 'a' }), null)
  })
})
