/**
 * Tests sentiment FR + digression.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeSentiment,
  checkContextRelevance,
  detectDigression,
} from '../services/conversationSentiment.ts'

describe('Sentiment FR', () => {
  test('phrase positive franche → positive', () => {
    const r = analyzeSentiment("C'est génial, j'adore ce projet !")
    assert.equal(r.polarity, 'positive')
    assert.ok(r.score > 2)
  })

  test('phrase négative franche → negative', () => {
    const r = analyzeSentiment("C'est nul, ça plante, je suis frustré")
    assert.equal(r.polarity, 'negative')
    assert.ok(r.score < -2)
  })

  test('phrase neutre → neutral', () => {
    const r = analyzeSentiment("Le pendule oscille avec une période T.")
    assert.equal(r.polarity, 'neutral')
  })

  test('phrase avec négation : "pas bien" → négatif', () => {
    const r = analyzeSentiment("Ce n'est pas bien du tout.")
    assert.ok(r.score < 0, `score ${r.score}`)
    assert.ok(r.negations.length > 0)
  })

  test('phrase mixte → mixed', () => {
    const r = analyzeSentiment("C'est super mais aussi un peu nul.")
    assert.equal(r.polarity, 'mixed')
  })

  test('emphase ! amplifie le score', () => {
    const calm = analyzeSentiment("C'est génial")
    const loud = analyzeSentiment("C'est génial !!!")
    assert.ok(Math.abs(loud.score) > Math.abs(calm.score))
  })

  test('CAPS amplifie aussi', () => {
    const r = analyzeSentiment("C'est SUPER GENIAL")
    assert.ok(r.emphasis >= 2)
  })

  test('vide → neutral', () => {
    const r = analyzeSentiment('')
    assert.equal(r.polarity, 'neutral')
    assert.equal(r.score, 0)
  })

  test('intensity ∈ [0..1]', () => {
    const r = analyzeSentiment("Super génial fantastique magnifique !")
    assert.ok(r.intensity >= 0 && r.intensity <= 1)
  })
})

describe('Détection de digression', () => {
  test('même sujet → continuation', () => {
    const r = detectDigression(
      "Explique-moi le pendule simple s'il te plaît",
      "Et comment calculer la période d'un pendule ?",
    )
    assert.equal(r.kind, 'continuation')
    assert.equal(r.digressed, false)
    assert.ok(r.sharedTokens.includes('pendule'))
  })

  test('sujets totalement différents → topic-shift', () => {
    const r = detectDigression(
      "Explique-moi le pendule simple en physique",
      "Quel est le meilleur restaurant à Paris ?",
    )
    assert.equal(r.kind, 'topic-shift')
    assert.equal(r.digressed, true)
  })

  test('lien partiel → tangent ou continuation (similarité présente)', () => {
    const r = detectDigression(
      "Comment calculer la vitesse d'un objet en chute libre",
      "Et la vitesse d'un avion ?",
    )
    assert.ok(['continuation', 'tangent'].includes(r.kind))
    assert.equal(r.digressed, false)
  })

  test('similarity ∈ [0..1]', () => {
    const r = detectDigression("test test test", "test test")
    assert.ok(r.similarity >= 0 && r.similarity <= 1)
  })

  test('messages vides → 0', () => {
    const r = detectDigression('', 'salut')
    assert.equal(r.similarity, 0)
  })
})

describe('Context relevance', () => {
  test('question reprenant un terme du contexte → match élevé', () => {
    const ctx = [
      "Explique-moi le pendule",
      "Le pendule oscille avec une période T",
      "On peut calculer T avec 2π√(L/g)",
    ]
    const r = checkContextRelevance("Quelle est la période d'un pendule simple ?", ctx)
    assert.ok(r.topMatch > 0.1, `topMatch ${r.topMatch}`)
    assert.ok(r.matchedTokens.includes('pendule') || r.matchedTokens.includes('periode'))
  })

  test('question hors-sujet → topMatch faible', () => {
    const ctx = ['Le pendule est étudié en physique']
    const r = checkContextRelevance('Capitale du Japon ?', ctx)
    assert.ok(r.topMatch < 0.1)
  })

  test('context vide → 0', () => {
    const r = checkContextRelevance('question', [])
    assert.equal(r.topMatch, 0)
  })
})
