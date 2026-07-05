import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectNamedAddTarget,
  describeNamedEntity,
  buildEntityAppearanceClause,
  entityReferenceAdvisory,
  lookupKnownEntityAppearance,
} from '../utils/namedEntityEnrichment.ts'

test('detectNamedAddTarget extracts a named entity after the "personnage" cue', () => {
  assert.equal(
    detectNamedAddTarget("sur la photo ajoute le personnage Kora de Nebula de facon a montrer de l'amicalite"),
    'Kora de Nebula',
  )
})

test('detectNamedAddTarget handles mascot cues and stops before relation details', () => {
  assert.equal(
    detectNamedAddTarget('ajoute la mascotte Bibi a cote de la personne'),
    'Bibi',
  )
})

test('detectNamedAddTarget handles nominal "ajout du personnage" wording', () => {
  assert.equal(
    detectNamedAddTarget("ajout du personnage Jax de TADC a cote de facon amical avec la main sur l'epaule"),
    'Jax de TADC',
  )
})

test('detectNamedAddTarget stops the name before an article-led franchise', () => {
  // "de The/of the ..." marque une FRANCHISE, pas la suite du nom -> on coupe.
  assert.equal(
    detectNamedAddTarget("ajoute le personnage Jax de The Amazing Digital Circus posant une main sur mon epaule"),
    'Jax',
  )
  assert.equal(
    detectNamedAddTarget('add the character Spike from the Mystery Show next to me'),
    'Spike',
  )
  // ... mais un vrai nom composé "X de <Nom>" (sans article) reste intact.
  assert.equal(detectNamedAddTarget('ajoute le personnage Kora de Nebula a cote'), 'Kora de Nebula')
})

test('detectNamedAddTarget handles the English "character named" cue', () => {
  assert.equal(
    detectNamedAddTarget('add the character named Pixel holding a balloon'),
    'Pixel',
  )
})

test('detectNamedAddTarget does not trigger on common generic nouns', () => {
  assert.equal(detectNamedAddTarget('ajoute un chapeau rouge'), null)
  assert.equal(detectNamedAddTarget('ajoute des fleurs dans le fond'), null)
  assert.equal(detectNamedAddTarget('change le fond pour une plage'), null)
  assert.equal(
    detectNamedAddTarget('ajoute un petit personnage photorealiste de jardinier adulte debout a droite du barbecue'),
    null,
  )
})

test('detectNamedAddTarget keeps named subjects after style descriptors', () => {
  assert.equal(
    detectNamedAddTarget('ajoute le personnage photorealiste Goldorak devant la tour Eiffel'),
    'Goldorak',
  )
})

test('detectNamedAddTarget requires an add verb', () => {
  assert.equal(detectNamedAddTarget('le personnage Kora est cool'), null)
})

test('buildEntityAppearanceClause is empty without a description', () => {
  assert.equal(buildEntityAppearanceClause('Kora', ''), '')
  assert.match(
    buildEntityAppearanceClause('Kora', 'a tall slim jester with blue and white skin'),
    /must look exactly like this: a tall slim jester/,
  )
})

test('lookupKnownEntityAppearance stays empty so named subjects use the research pipeline', () => {
  assert.equal(lookupKnownEntityAppearance('Jax de TADC'), '')
})

test('describeNamedEntity calls the LLM fallback when no researched reference is available', async () => {
  let called = false
  const desc = await describeNamedEntity('Kora de Nebula', {
    model: 'dummy',
    generate: async () => {
      called = true
      return { response: 'a tall slim blue jester with white gloves and a silver crescent hat' }
    },
  })

  assert.equal(called, true)
  assert.match(desc, /blue jester/i)
})

test('describeNamedEntity returns empty when the model is unsure', async () => {
  const desc = await describeNamedEntity('Unknown Character', {
    model: 'dummy',
    generate: async () => ({ response: 'NONE' }),
  })

  assert.equal(desc, '')
})

test('entityReferenceAdvisory names the entity and points to reference upload', () => {
  const msg = entityReferenceAdvisory('Kora de Nebula')
  assert.match(msg, /Kora de Nebula/)
  assert.match(msg, /image/i)
})
