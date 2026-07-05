/**
 * Tests prosodie FR.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyseProsody,
  detectEmphasisWords,
  generateSsml,
} from '../services/voiceProsody.ts'

describe('Prosodie — type de phrase', () => {
  test('phrase affirmative → statement', () => {
    const r = analyseProsody('Le pendule oscille.')
    assert.equal(r.sentenceKind, 'statement')
  })

  test('phrase interrogative → question', () => {
    const r = analyseProsody('Quelle est la période ?')
    assert.equal(r.sentenceKind, 'question')
  })

  test('phrase exclamative → exclamation', () => {
    const r = analyseProsody('Incroyable résultat !')
    assert.equal(r.sentenceKind, 'exclamation')
  })
})

describe('Pitch shift', () => {
  test('question → derniers mots avec pitch > 0', () => {
    const r = analyseProsody('Tu vas bien ?')
    const lastWord = [...r.segments].reverse().find((s) => s.kind === 'word')!
    assert.ok(lastWord.pitchShiftSemitones > 0)
  })

  test('exclamation → dernier mot avec pitch < 0 (descente)', () => {
    const r = analyseProsody('Bonjour Aurora !')
    const lastWord = [...r.segments].reverse().find((s) => s.kind === 'word')!
    assert.ok(lastWord.pitchShiftSemitones < 0)
  })

  test('affirmation → pitch normal partout', () => {
    const r = analyseProsody('Le ciel est bleu.')
    for (const seg of r.segments) {
      if (seg.kind === 'word') assert.equal(seg.pitchShiftSemitones, 0)
    }
  })
})

describe('Pauses', () => {
  test('virgule → pause 200ms', () => {
    const r = analyseProsody('Salut, ça va ?')
    const comma = r.segments.find((s) => s.text === ',')!
    assert.equal(comma.durationMs, 200)
  })

  test('point → pause 500ms', () => {
    const r = analyseProsody('Fin.')
    const dot = r.segments.find((s) => s.text === '.')!
    assert.equal(dot.durationMs, 500)
  })

  test('? → pause 600ms', () => {
    const r = analyseProsody('Quoi ?')
    const q = r.segments.find((s) => s.text === '?')!
    assert.equal(q.durationMs, 600)
  })
})

describe('Accent rythmique', () => {
  test('dernier mot d\'une phrase a stress', () => {
    const r = analyseProsody('Le pendule oscille')
    const lastWord = [...r.segments].reverse().find((s) => s.kind === 'word')!
    assert.equal(lastWord.hasStress, true)
  })

  test('mot avant virgule a stress', () => {
    const r = analyseProsody('Hier, j\'ai dormi.')
    const hier = r.segments.find((s) => s.text.toLowerCase() === 'hier')!
    assert.equal(hier.hasStress, true)
  })
})

describe('Énergie / emphase', () => {
  test('après "très" → energyGain > 1', () => {
    const r = analyseProsody('C\'est très important')
    const important = r.segments.find((s) => s.text === 'important')!
    assert.ok(important.energyGain > 1)
  })

  test('exclamation amplifie l\'énergie globale', () => {
    const exclaim = analyseProsody('Génial !')
    const normal = analyseProsody('Génial.')
    const eEx = exclaim.segments.find((s) => s.text === 'Génial')!
    const eNo = normal.segments.find((s) => s.text === 'Génial')!
    assert.ok(eEx.energyGain > eNo.energyGain)
  })
})

describe('Emphasis detection', () => {
  test('détecte les mots-clés longs hors stopwords', () => {
    const hints = detectEmphasisWords('Le pendule est très intéressant aujourd\'hui')
    assert.ok(hints.length >= 2)
    assert.ok(hints.some((h) => h.word.toLowerCase().startsWith('intéressant')))
  })

  test('détecte les chiffres', () => {
    const hints = detectEmphasisWords('La période vaut 2.5 secondes')
    assert.ok(hints.some((h) => h.reason === 'numeric'))
  })

  test('après intensifier → flag', () => {
    const hints = detectEmphasisWords('extrêmement utile')
    assert.ok(hints.some((h) => h.reason === 'after-intensifier'))
  })
})

describe('SSML generation', () => {
  test('output valide commence <speak> finit </speak>', () => {
    const ssml = generateSsml('Bonjour Aurora.')
    assert.match(ssml, /^<speak>/)
    assert.match(ssml, /<\/speak>$/)
  })

  test('contient <break time> pour pauses', () => {
    const ssml = generateSsml('Salut, comment vas-tu ?')
    assert.match(ssml, /<break time="\d+ms"\/>/)
  })

  test('question contient <prosody pitch>', () => {
    const ssml = generateSsml('Tu es prêt ?')
    assert.match(ssml, /<prosody[^>]*pitch="\+/)
  })

  test('caractères XML spéciaux filtrés du tokenizer (ne polluent pas le SSML)', () => {
    const ssml = generateSsml('A & <test> "ok"')
    // Tokens conservés : A, test, ok. Pas de & < > " dans la sortie.
    assert.ok(!ssml.includes('<test>'))
    assert.ok(!ssml.includes('"ok"'))
  })
})
