#!/usr/bin/env node
// Fidélité du module Image (FLUX.2) : la demande réelle signalée — « un vase en forme
// de coeur avec inscriptions rayen » donnait un flacon transparent avec une personne —
// et les règles qui empêchent cette dérive (Node, vraies sources TypeScript).
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parseImageIntent } from '../src/utils/imagePromptParser.ts'
import { detectSubjectToResearch } from '../src/services/selfInformedReference.ts'
import { buildFaithfulCreationPrompt, expandHumanImagePromptWithAI } from '../src/services/imagePromptBuilder.ts'
import { analyzeSubjectFidelity, checkExpansionFidelity } from '../src/services/imageSubjectFidelity.ts'
import { extractInscriptionTexts } from '../src/utils/inscriptionText.ts'
import { translateFrenchSubjectToEnglish } from '../src/services/cognitivePromptDirector.ts'
import { createFluxWorkflow } from '../src/utils/fluxWorkflow.ts'

const REQUEST = 'un vase en forme de coeur avec inscriptions rayen'
// une image précédente est affichée, aucune image jointe : la situation de l'utilisateur
const PREVIOUS_ONLY = { hasReference: true, referenceIsPreviousOutput: true }
const HUMAN_IN_POSITIVE = /\b(skin|pores?|face structure|facial|shoulders?|anatomy|fingers?|person identity|woman|man|people|human)\b/i

function encodedTexts(prompt, negative) {
  const wf = createFluxWorkflow({ prompt, negativePrompt: negative, style: 'realistic', width: 1024, height: 1024, steps: 34, filenamePrefix: 't' })
  const [positive, neg] = Object.values(wf).filter((n) => n.class_type === 'CLIPTextEncode').map((n) => n.inputs.text)
  return { positive, neg }
}

test('the reported request is a new creation, never an edit of the previous image', () => {
  for (const t of [REQUEST, "fais moi un vase en forme de cœur avec l'inscription Rayen", 'Vase en forme de cœur avec écrit Rayen dessus']) {
    const intent = parseImageIntent(t, PREVIOUS_ONLY)
    assert.equal(intent.editMode, 'create', t)
    assert.equal(intent.isEditIntent, false, t)
  }
})

test('explicit edits of the displayed image stay edits', () => {
  assert.equal(parseImageIntent('ajoute un chapeau', PREVIOUS_ONLY).editMode, 'add_element')
  assert.equal(parseImageIntent('change la couleur du vase en bleu', PREVIOUS_ONLY).isEditIntent, true)
  assert.equal(parseImageIntent('écris "Bonjour" sur la pancarte', PREVIOUS_ONLY).editMode, 'text_edit')
  assert.equal(parseImageIntent('fais moi ce personnage en anime', { hasReference: true }).isEditIntent, true)
})

test('a name to engrave is text, not a person to research on the web', () => {
  assert.deepEqual(extractInscriptionTexts(REQUEST), ['rayen'])
  assert.deepEqual(extractInscriptionTexts('une plaque gravée au nom de Léa Martin sur fond bois'), ['Léa Martin'])
  assert.deepEqual(extractInscriptionTexts('une tasse avec écrit "Bonne fête Maman" en rouge'), ['Bonne fête Maman'])
  assert.deepEqual(extractInscriptionTexts('un vase sans inscription'), [])
  for (const t of ['un vase en forme de coeur avec inscriptions Rayen', 'un vase en forme de coeur avec le prénom Rayen gravé']) {
    assert.equal(detectSubjectToResearch(t, parseImageIntent(t, PREVIOUS_ONLY)), null, t)
  }
  // un vrai personnage nommé reste recherché
  const pika = detectSubjectToResearch('ajoute Pikachu sur la table', parseImageIntent('ajoute Pikachu sur la table', PREVIOUS_ONLY))
  assert.equal(pika?.subject, 'Pikachu')
})

test('the French shape is translated instead of "into forme de coeur"', () => {
  const en = translateFrenchSubjectToEnglish(REQUEST)
  assert.match(en, /heart-shaped/)
  assert.match(en, /"rayen"/)
  assert.doesNotMatch(en, /into forme|forme de/)
})

test('the prompt sent to FLUX.2 locks the vase and contains no human cue', async () => {
  const exp = await expandHumanImagePromptWithAI(REQUEST, { mode: 'create', requestedStyle: 'none', hasReference: false })
  const faithful = buildFaithfulCreationPrompt({ request: REQUEST, expanded: exp.expandedPrompt })
  const { positive, neg } = encodedTexts(faithful.positive, faithful.negativeTerms.join(', '))
  assert.match(positive, /^.*Main subject: a single heart-shaped vase/s)
  assert.match(positive, /open-topped vessel/)
  assert.match(positive, /inscription "rayen"/)
  assert.match(positive, /« un vase en forme de coeur avec inscriptions rayen »/)
  assert.doesNotMatch(positive, HUMAN_IN_POSITIVE)
  assert.doesNotMatch(positive, /Avoid \/ negative|SESSION CONTRACT|HUMAN PHOTO PRESERVATION/)
  for (const term of ['person', 'woman', 'hands', 'bottle', 'perfume bottle', 'flask', 'flacon']) assert.ok(neg.split(', ').includes(term), term)
  // le texte demandé n'est pas interdit par le négatif
  assert.doesNotMatch(neg, /(^|, )(text|logo)(,|$)/)
})

test('an LLM expansion that drifts (bottle, woman) is rejected for the deterministic one', async () => {
  const drift = async () => 'A heart-shaped transparent glass perfume bottle held gently in the hands of a young woman, soft window light.'
  const exp = await expandHumanImagePromptWithAI(REQUEST, { mode: 'create', requestedStyle: 'none', hasReference: false, generateText: drift })
  assert.equal(exp.wasExpandedByAI, false)
  assert.match(exp.sceneCompletionNote, /personne inventée/)
  assert.doesNotMatch(exp.expandedPrompt, /woman|bottle|perfume/i)
  const good = async () => 'A heart-shaped glazed ceramic vase engraved with the word "rayen", resting on an oak table in soft daylight.'
  const ok = await expandHumanImagePromptWithAI(REQUEST, { mode: 'create', requestedStyle: 'none', hasReference: false, generateText: good })
  assert.equal(ok.wasExpandedByAI, true)
  assert.match(ok.expandedPrompt, /ceramic vase/)
})

test('a requested person keeps its freedom; an object alone excludes people', () => {
  const holding = analyzeSubjectFidelity('une femme qui tient un vase')
  assert.equal(holding.wantsHuman, true)
  assert.equal(holding.objectOnly, false)
  assert.ok(!buildFaithfulCreationPrompt({ request: 'une femme qui tient un vase' }).negativeTerms.includes('woman'))
  const statue = analyzeSubjectFidelity('une statue en marbre')
  assert.equal(statue.objectOnly, false)
  const f = analyzeSubjectFidelity(REQUEST)
  assert.equal(checkExpansionFidelity('A hand-painted heart-shaped vase with "rayen" lettering.', f).ok, true)
})

test('native, web/tunnel (same hook), Manga view and CLI build the same locked prompt', () => {
  const read = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')
  assert.match(read('../src/hooks/useImageViewLogic.ts'), /buildFaithfulCreationPrompt\(/)
  assert.match(read('../src/hooks/useImageViewLogic.ts'), /referenceIsPreviousOutput: !refFilename && Boolean\(current\)/)
  assert.match(read('../src/views/MangaImageView.tsx'), /buildFaithfulCreationPrompt\(/)
  assert.match(read('../src/views/MangaImageView.tsx'), /detectSubjectToResearch\(text, intent\)/)
  assert.match(read('./image_cli.mjs'), /buildFaithfulCreationPrompt\(/)
})
