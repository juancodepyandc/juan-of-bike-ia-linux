import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseImageIntent } from '../utils/imagePromptParser.ts'
import {
  buildAppearanceClause,
  buildResearchProfile,
  buildResearchQueries,
  detectSubjectToResearch,
  resolveSubjectReference,
  type SubjectToResearch,
} from '../services/selfInformedReference.ts'

test('detectSubjectToResearch separates the character name from an article-led franchise context', () => {
  const prompt = 'ajoute le personnage Jax de The Amazing Digital Circus posant une main sur mon epaule'
  const target = detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: true }))

  assert.equal(target?.subject, 'Jax')
  assert.equal(target?.searchLabel, 'Jax The Amazing Digital Circus')
  assert.equal(target?.kind, 'character')
  assert.equal(target?.role, 'add_subject')
})

test('detectSubjectToResearch catches a proper-noun add without an explicit "personnage" cue', () => {
  const prompt = 'ajoute Pikachu en colère à côté de l\'homme'
  const target = detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: true }))
  assert.equal(target?.subject, 'Pikachu')
  assert.equal(target?.kind, 'character')
  assert.equal(target?.role, 'add_subject')
})

test('detectSubjectToResearch catches a named primary subject in pure creation', () => {
  const prompt = 'Goldorak devant la tour Eiffel, style anime fidele'
  const target = detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: false }))

  assert.equal(target?.subject, 'Goldorak')
  assert.equal(target?.kind, 'character')
  assert.equal(target?.role, 'primary_subject')
  assert.deepEqual(buildResearchQueries(target!), [
    'Goldorak official character reference full body',
    'Goldorak character design sheet',
    'Goldorak official art transparent png',
    'Goldorak',
  ])

  const clause = buildAppearanceClause(target!, 'white, black, red and gold super robot with horned helmet and angular chest armor')
  assert.match(clause, /main character \(Goldorak\)/i)
  assert.match(clause, /exact reference appearance/i)
})

test('detectSubjectToResearch still ignores a generic lowercase add', () => {
  for (const prompt of [
    'ajoute un chapeau rouge',
    'mets une plage en fond',
    'ajoute des fleurs',
    'ajoute un petit personnage photorealiste de jardinier adulte debout a droite du barbecue',
  ]) {
    assert.equal(detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: true })), null, prompt)
  }
})

test('detectSubjectToResearch uses acronym context for named character search', () => {
  const prompt = "ajout du personnage Jax de TADC a cote de facon amical avec la main sur l'epaule"
  const target = detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: true }))

  assert.equal(target?.subject, 'Jax')
  assert.equal(target?.searchLabel, 'Jax TADC')
})

test('detectSubjectToResearch understands a named pet/mascot with franchise context', () => {
  const prompt = 'suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite'
  const target = detectSubjectToResearch(prompt, parseImageIntent(prompt, { hasReference: true }))

  assert.equal(target?.subject, 'Happy')
  assert.equal(target?.searchLabel, 'Happy Fairy Tail')
  assert.equal(target?.kind, 'character')
  assert.equal(target?.role, 'add_subject')
  assert.deepEqual(buildResearchQueries(target!), [
    'Happy Fairy Tail official character reference full body',
    'Happy Fairy Tail character design sheet',
    'Happy Fairy Tail official art transparent png',
    'Happy Fairy Tail wiki appearance',
    'Happy Fairy Tail',
  ])
})

test('buildResearchQueries uses the disambiguated search label', () => {
  const target: SubjectToResearch = {
    subject: 'Jax',
    searchLabel: 'Jax TADC',
    kind: 'character',
    role: 'add_subject',
  }

  assert.deepEqual(buildResearchQueries(target), [
    'Jax TADC official character reference full body',
    'Jax TADC character design sheet',
    'Jax TADC official art transparent png',
    'Jax TADC wiki appearance',
    'Jax TADC',
  ])
})

test('buildResearchProfile keeps strict identity on the drawn subject only', () => {
  const target: SubjectToResearch = {
    subject: 'Jax',
    searchLabel: 'Jax TADC',
    kind: 'character',
    role: 'add_subject',
  }
  const profile = buildResearchProfile(target)

  assert.equal(profile.subjectLabel, 'Jax TADC')
  assert.deepEqual(profile.identityTerms, ['jax'])
  assert.deepEqual(profile.requiredPageTerms, ['tadc'])
  assert.equal(profile.strictIdentity, true)
  assert.equal(profile.allowAdditionalSubjects, false)
})

test('resolveSubjectReference merges several verified references and keeps the best ComfyUI source', async () => {
  const target: SubjectToResearch = {
    subject: 'Jax',
    searchLabel: 'Jax TADC',
    kind: 'character',
    role: 'add_subject',
  }

  const resolved = await resolveSubjectReference(target, {
    fetchReferenceImages: async () => [
      { comfyFilename: 'side.png', blob: new Blob(['side']), sourceUrl: 'side', score: 83 },
      { comfyFilename: 'best.png', blob: new Blob(['best']), sourceUrl: 'best', score: 97 },
      { comfyFilename: 'front.png', blob: new Blob(['front']), sourceUrl: 'front', score: 91 },
    ],
    describeReferenceImage: async (ref) => {
      if (ref.sourceUrl === 'best') return 'slim lavender rabbit, long ears, yellow gloves, red overalls, sly grin'
      if (ref.sourceUrl === 'front') return 'tall rubberhose rabbit with yellow teeth and pink-red overalls'
      return 'long-limbed purple rabbit character with upright ears'
    },
  })

  assert.equal(resolved.provenance, 'researched-image')
  assert.equal(resolved.referenceCount, 3)
  assert.equal(resolved.referenceComfyFilename, 'best.png')
  assert.match(resolved.appearanceDescription, /Primary reference: slim lavender rabbit/)
  assert.match(resolved.appearanceDescription, /Cross-check 1: tall rubberhose rabbit/)
})

test('resolveSubjectReference demotes a high-score visual outlier by consensus', async () => {
  const target: SubjectToResearch = {
    subject: 'Jax',
    searchLabel: 'Jax TADC',
    kind: 'character',
    role: 'add_subject',
  }

  const resolved = await resolveSubjectReference(target, {
    fetchReferenceImages: async () => [
      { comfyFilename: 'wrong.png', blob: new Blob(['wrong']), sourceUrl: 'wrong', score: 99 },
      { comfyFilename: 'rabbit-front.png', blob: new Blob(['front']), sourceUrl: 'front', score: 88 },
      { comfyFilename: 'rabbit-render.png', blob: new Blob(['render']), sourceUrl: 'render', score: 85 },
    ],
    describeReferenceImage: async (ref) => {
      if (ref.sourceUrl === 'wrong') return 'cartoon human with light blue spiky hair, yellow shirt, dark bow tie, green pants'
      if (ref.sourceUrl === 'front') return 'purple rabbit with long ears, yellow gloves, pink overalls, wide yellow grin, no shirt or accessories'
      return 'tall purple rabbit character, long ears, yellow teeth, yellow gloves, pink-red overalls'
    },
  })

  assert.equal(resolved.referenceComfyFilename, 'rabbit-front.png')
  assert.match(resolved.appearanceDescription, /Primary reference: purple rabbit/)
  assert.match(resolved.appearanceDescription, /Cross-check 1: tall purple rabbit/)
  assert.doesNotMatch(resolved.appearanceDescription, /blue spiky hair/)
})

test('resolveSubjectReference keeps the legacy single-reference fallback', async () => {
  const target: SubjectToResearch = {
    subject: 'Kora',
    kind: 'character',
    role: 'add_subject',
  }

  const resolved = await resolveSubjectReference(target, {
    fetchReferenceImage: async () => ({
      comfyFilename: 'single.png',
      blob: new Blob(['single']),
      sourceUrl: 'single',
      score: 88,
    }),
    describeReferenceImage: async () => 'blue jester with a crescent hat and white gloves',
  })

  assert.equal(resolved.provenance, 'researched-image')
  assert.equal(resolved.referenceCount, 1)
  assert.equal(resolved.referenceComfyFilename, 'single.png')
  assert.equal(resolved.appearanceDescription, 'blue jester with a crescent hat and white gloves')
})

test('resolveSubjectReference does not invent an LLM description for contextual subjects without references', async () => {
  const target: SubjectToResearch = {
    subject: 'Jax',
    searchLabel: 'Jax TADC',
    kind: 'character',
    role: 'add_subject',
  }
  let called = false

  const resolved = await resolveSubjectReference(target, {
    fetchReferenceImages: async () => [],
    generate: async () => {
      called = true
      return { response: 'muscular cyberpunk human named Jax' }
    },
    textModel: 'dummy',
  })

  assert.equal(called, false)
  assert.equal(resolved.provenance, 'none')
  assert.equal(resolved.appearanceDescription, '')
  assert.match(resolved.advisory || '', /Jax/)
})
