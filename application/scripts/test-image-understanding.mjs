#!/usr/bin/env node
// Module Image : « il voit un mot et fait une action et ne comprend pas ; si la phrase n'est pas
// comme l'IA attend, il ne fera jamais un bon résultat… quitte à poser des questions intelligentes ».
// La décision création / retouche vient de la compréhension ; question si ambigu. Vraies sources.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseImageIntent } from '../src/utils/imagePromptParser.ts'
import { CONFIANCE_MIN, deciderIntentImage, validerLecture } from '../src/services/imageRequestUnderstanding.ts'

const SHOWN = { hasDisplayedImage: true, hasAttachedImage: false, previousRequests: ['un chien dans un jardin'] }
const answering = (payload) => async () => JSON.stringify(payload)
const PREVIOUS_ONLY = { hasReference: true, referenceIsPreviousOutput: true }

test('a retouche without an edit verb is understood as a retouche of the displayed image', async () => {
  const text = 'je la veux de nuit sous la pluie'
  const byWords = parseImageIntent(text, PREVIOUS_ONLY)
  const decision = await deciderIntentImage({
    texte: text, intentExpressions: byWords, contexte: SHOWN,
    generer: answering({ intention: 'retouche', confiance: 0.9, sujet: 'le chien dans le jardin, de nuit sous la pluie', changements: ['nuit', 'pluie'], a_conserver: ['le chien'] }),
    demander: null,
  })
  assert.equal(decision.decidePar, 'comprehension')
  assert.equal(decision.intent.isEditIntent, true)
  assert.notEqual(decision.intent.editMode, 'create')
})

test('a new subject after an earlier image is a new creation even if the words look like an edit', async () => {
  const text = 'ajoute-moi plutôt un chat roux sur un canapé'
  const byWords = parseImageIntent(text, PREVIOUS_ONLY)
  const decision = await deciderIntentImage({
    texte: text, intentExpressions: byWords, contexte: SHOWN,
    generer: answering({ intention: 'creation', confiance: 0.85, sujet: 'un chat roux sur un canapé', changements: [], a_conserver: [] }),
    demander: null,
  })
  assert.equal(decision.intent.isEditIntent, false)
  assert.equal(decision.intent.editMode, 'create')
})

test('a genuinely ambiguous request asks the user, and the answer decides', async () => {
  const text = 'un dragon'
  const byWords = parseImageIntent(text, PREVIOUS_ONLY)
  const asked = []
  const decision = await deciderIntentImage({
    texte: text, intentExpressions: byWords, contexte: SHOWN,
    generer: answering({ intention: 'ambigu', confiance: 0.4, sujet: 'un dragon', question: "Ajouter un dragon à l'image affichée, ou créer une nouvelle image de dragon ?", options: ['Ajouter à l’image', 'Nouvelle image'] }),
    demander: async (question, options) => { asked.push([question, options]); return 'retouche' },
  })
  assert.equal(asked.length, 1)
  assert.match(asked[0][0], /dragon/)
  assert.equal(decision.decidePar, 'utilisateur')
  assert.equal(decision.intent.isEditIntent, true)
})

test('a low-confidence reading never overrides the words; with no surface to ask, the words decide', async () => {
  const text = 'change le fond en bleu'
  const byWords = parseImageIntent(text, PREVIOUS_ONLY)
  const decision = await deciderIntentImage({
    texte: text, intentExpressions: byWords, contexte: SHOWN,
    generer: answering({ intention: 'creation', confiance: CONFIANCE_MIN - 0.2, sujet: 'fond bleu' }),
    demander: async () => null,
  })
  assert.equal(decision.decidePar, 'expressions')
  assert.equal(decision.intent, byWords)
})

test('an unreachable or off-contract model leaves the decision to the words, without inventing a reading', async () => {
  const byWords = parseImageIntent('un vase bleu', PREVIOUS_ONLY)
  for (const generer of [async () => { throw new Error('ollama down') }, async () => 'pas de json', answering({ intention: 'peut-être' })]) {
    const decision = await deciderIntentImage({ texte: 'un vase bleu', intentExpressions: byWords, contexte: SHOWN, generer, demander: null })
    assert.equal(decision.decidePar, 'expressions')
    assert.equal(decision.lecture.source, 'indisponible')
  }
  assert.equal(validerLecture({ intention: 'retouche', confiance: 7 }).confiance, 1)
})

test('with no image on screen there is nothing to retouch and no question is asked', async () => {
  const byWords = parseImageIntent('un dragon', {})
  let called = false
  const decision = await deciderIntentImage({
    texte: 'un dragon', intentExpressions: byWords,
    contexte: { hasDisplayedImage: false, hasAttachedImage: false, previousRequests: [] },
    generer: async () => { called = true; return '{}' }, demander: async () => { called = true; return null },
  })
  assert.equal(called, false)
  assert.equal(decision.intent.editMode, 'create')
})
