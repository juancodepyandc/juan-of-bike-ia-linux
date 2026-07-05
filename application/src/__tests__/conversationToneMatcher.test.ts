/**
 * Tests tone matcher.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyseTone,
  compareFormality,
  generateSystemHint,
} from '../services/conversationToneMatcher.ts'

describe('Detection registre', () => {
  test('phrase tres formelle → formality high + vouvoiement', () => {
    const t = analyseTone("Monsieur, pourriez-vous m'expliquer cordialement la formule, s'il vous plaît ?")
    assert.ok(t.formality > 0.5, `formality ${t.formality}`)
    assert.ok(t.tutoiement < 0.5)
    assert.equal(t.recommendedAddress, 'vous')
    assert.equal(t.recommendedStyle, 'professional')
  })

  test('phrase tres casual → tutoiement + casual', () => {
    const t = analyseTone("salut mec, t'as kiffé ce truc grave ouf ?")
    assert.ok(t.formality < 0.4)
    assert.equal(t.recommendedAddress, 'tu')
    assert.ok(['casual', 'enthusiastic'].includes(t.recommendedStyle))
  })

  test('argot detecté', () => {
    const t = analyseTone('Frérot, je kiffe ton taff !')
    assert.ok(t.argot > 0.2)
  })

  test('emotion : !!! amplifie', () => {
    const calm = analyseTone('Ok merci.')
    const loud = analyseTone('OK MERCI !!! incroyable !!!')
    assert.ok(loud.emotionalLoad > calm.emotionalLoad)
  })

  test('texte neutre → conversational', () => {
    const t = analyseTone('Explique-moi le pendule simple.')
    assert.equal(t.recommendedStyle, 'conversational')
  })

  test('vide → defaults', () => {
    const t = analyseTone('')
    assert.equal(t.formality, 0.5)
    assert.equal(t.tutoiement, 0.5)
  })
})

describe('Generate system hint', () => {
  test('hint pour vouvoiement contient "vouvoies"', () => {
    const t = analyseTone('Bonjour Monsieur, pourriez-vous me dire ?')
    const h = generateSystemHint(t)
    assert.match(h, /vouvoie/i)
  })

  test('hint pour tutoiement contient "tutoies"', () => {
    const t = analyseTone('salut t\'as kiffé ?')
    const h = generateSystemHint(t)
    assert.match(h, /tutoie/i)
  })

  test('hint pour professional mentionne pas d\'abréviations', () => {
    const t = analyseTone('Monsieur, voudriez-vous procéder à la vérification, cordialement ?')
    const h = generateSystemHint(t)
    assert.match(h, /soign|professionnel|abrév/i)
  })

  test('hint pour high emotion mentionne ressenti', () => {
    const t = analyseTone('OUI !!! C\'est trop bien !!! GENIAL !!!')
    const h = generateSystemHint(t)
    assert.match(h, /émotionnel|émotion|ressenti|expressif/i)
  })
})

describe('compareFormality', () => {
  test('phrase formelle > phrase casual', () => {
    const r = compareFormality(
      "Pourriez-vous, Monsieur, procéder à cette opération cordialement ?",
      "salut, t\'as fait ça ?",
    )
    assert.equal(r.aMoreFormal, true)
    assert.ok(r.delta > 0)
  })

  test('même registre → delta faible', () => {
    const r = compareFormality(
      'salut comment ça va',
      'salut comment ça roule',
    )
    assert.ok(r.delta < 0.3)
  })
})
