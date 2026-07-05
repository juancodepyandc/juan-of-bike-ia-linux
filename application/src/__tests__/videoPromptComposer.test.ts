import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  VIDEO_QUALITY_TAIL,
  analyzeVideoPrompt,
  composeWanPrompt,
} from '../services/videoPromptComposer.ts'

describe('analyzeVideoPrompt - detection FR', () => {
  test('camera : zoom avant + travelling', () => {
    const a = analyzeVideoPrompt('zoom avant sur un velo puis travelling lateral')
    assert.ok(a.camera.includes('slow cinematic zoom in'))
    assert.ok(a.camera.includes('steady dolly tracking shot'))
  })

  test('orbite et drone', () => {
    const a = analyzeVideoPrompt('la camera tourne autour du chateau, vue aerienne')
    assert.ok(a.camera.some((c) => c.includes('orbiting')))
    assert.ok(a.camera.some((c) => c.includes('drone')))
  })

  test('plan : gros plan vs plan large', () => {
    assert.equal(analyzeVideoPrompt('gros plan sur ses yeux').shot, 'close-up shot')
    assert.equal(analyzeVideoPrompt('plan large de la vallee').shot, 'wide establishing shot')
  })

  test('tres gros plan prioritaire sur gros plan', () => {
    assert.equal(analyzeVideoPrompt('tres gros plan sur la goutte').shot, 'extreme close-up shot')
  })

  test('lumiere : nuit + neon + pluie', () => {
    const a = analyzeVideoPrompt('rue cyberpunk la nuit sous la pluie, neons')
    assert.ok(a.lighting.some((l) => l.includes('night')))
    assert.ok(a.lighting.some((l) => l.includes('neon')))
    assert.ok(a.lighting.some((l) => l.includes('rain')))
    assert.equal(a.style, 'cyberpunk aesthetic, neon-soaked futuristic city')
  })

  test('style anime et ralenti', () => {
    const a = analyzeVideoPrompt('combat anime au ralenti')
    assert.ok(a.style?.includes('anime'))
    assert.ok(a.tempo?.includes('slow motion'))
  })

  test('camera fixe detectee', () => {
    assert.equal(analyzeVideoPrompt('plan fixe sur la fenetre').staticCamera, true)
    assert.equal(analyzeVideoPrompt('zoom avant').staticCamera, false)
  })

  test('coucher de soleil → golden hour', () => {
    const a = analyzeVideoPrompt('un chat au coucher de soleil')
    assert.ok(a.lighting.some((l) => l.includes('golden hour')))
  })
})

describe('composeWanPrompt - composition et dedoublonnage', () => {
  test('ajoute bloc Cinematography avec directives + queue qualite', () => {
    const a = analyzeVideoPrompt('zoom avant sur un dragon la nuit, style anime')
    const out = composeWanPrompt('A dragon breathing fire on a castle', a)
    assert.match(out, /^A dragon breathing fire on a castle/)
    assert.match(out, /Cinematography: /)
    assert.match(out, /slow cinematic zoom in/)
    assert.match(out, /night scene/)
    assert.match(out, /anime animation style/)
    assert.match(out, /professional video quality/)
  })

  test('camera fixe ecrase toute directive de mouvement', () => {
    const a = analyzeVideoPrompt('plan fixe, zoom avant impossible')
    const out = composeWanPrompt('A window with rain', a)
    assert.match(out, /static camera, locked tripod shot/)
    assert.ok(!out.includes('zoom in'))
  })

  test('ne duplique pas une directive deja posee par le LLM', () => {
    const a = analyzeVideoPrompt('zoom avant sur la foret')
    const distilled = 'Forest scene, slow cinematic zoom in toward the trees'
    const out = composeWanPrompt(distilled, a)
    const count = (out.match(/zoom in/gi) || []).length
    assert.equal(count, 1)
  })

  test('ne duplique pas le suffixe du preset motion', () => {
    const a = analyzeVideoPrompt('un robot qui danse')
    const motionSuffix = 'camera slowly orbiting around the subject, consistent radius, subject centered'
    const out = composeWanPrompt('A robot dancing', { ...a, camera: ['camera slowly orbiting around the subject'] }, { motionSuffix })
    const count = (out.match(/orbiting/gi) || []).length
    assert.equal(count, 0, 'directive deja dans motionSuffix, ne doit pas reapparaitre')
  })

  test('queue qualite toujours presente meme sans detection', () => {
    const a = analyzeVideoPrompt('une scene quelconque')
    const out = composeWanPrompt('A simple scene', a)
    for (const tail of VIDEO_QUALITY_TAIL.slice(0, 3)) {
      assert.ok(out.includes(tail), `queue manquante: ${tail}`)
    }
  })

  test('base preservee verbatim en tete', () => {
    const a = analyzeVideoPrompt('peu importe')
    const distilled = 'An orange gravel bike in a premium workshop'
    const out = composeWanPrompt(distilled, a)
    assert.ok(out.startsWith(distilled))
  })
})
