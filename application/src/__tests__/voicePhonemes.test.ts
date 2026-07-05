/**
 * Tests pour services/voicePhonemes — table FR phonèmes → visèmes,
 * profils voix, state machine d'interruption.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  FR_PHONEME_TABLE,
  phonemeToViseme,
  textToVisemes,
  VOICE_PROFILES,
  pickProfileForContext,
  transition,
  VAD_RMS_THRESHOLD,
  VAD_LOST_DEBOUNCE_MS,
} from '../services/voicePhonemes.ts'

describe('FR_PHONEME_TABLE', () => {
  test('contient au moins 30 phonèmes', () => {
    assert.ok(FR_PHONEME_TABLE.length >= 30)
  })

  test('chaque entrée a ipa/viseme/defaultDurationMs', () => {
    for (const p of FR_PHONEME_TABLE) {
      assert.ok(p.ipa)
      assert.ok(p.viseme)
      assert.ok(typeof p.defaultDurationMs === 'number')
      assert.ok(p.defaultDurationMs > 0)
    }
  })

  test('IPA uniques', () => {
    const ipas = FR_PHONEME_TABLE.map((p) => p.ipa)
    assert.equal(new Set(ipas).size, ipas.length)
  })

  test('phonèmes vocaliques FR principaux présents', () => {
    const ipas = FR_PHONEME_TABLE.map((p) => p.ipa)
    for (const v of ['a', 'e', 'i', 'o', 'u', 'y']) {
      assert.ok(ipas.includes(v), `phonème ${v} manquant`)
    }
  })

  test('consonnes principales présentes', () => {
    const ipas = FR_PHONEME_TABLE.map((p) => p.ipa)
    for (const c of ['p', 'b', 'm', 't', 'd', 'k', 'f', 'v', 'l']) {
      assert.ok(ipas.includes(c), `consonne ${c} manquante`)
    }
  })
})

describe('phonemeToViseme', () => {
  test('"a" → "aa"', () => {
    assert.equal(phonemeToViseme('a'), 'aa')
  })

  test('"i" → "ih"', () => {
    assert.equal(phonemeToViseme('i'), 'ih')
  })

  test('"u" → "ou"', () => {
    assert.equal(phonemeToViseme('u'), 'ou')
  })

  test('"p" → "mm" (lèvres fermées)', () => {
    assert.equal(phonemeToViseme('p'), 'mm')
  })

  test('"f" → "ff" (dents sur lèvre)', () => {
    assert.equal(phonemeToViseme('f'), 'ff')
  })

  test('phonème inconnu → "rest"', () => {
    assert.equal(phonemeToViseme('XYZ'), 'rest')
  })

  test('chaîne vide → "rest"', () => {
    assert.equal(phonemeToViseme(''), 'rest')
  })
})

describe('textToVisemes', () => {
  test('texte vide → []', () => {
    assert.deepEqual(textToVisemes(''), [])
  })

  test('texte simple → suite de keyframes', () => {
    const r = textToVisemes('papa')
    assert.ok(r.length >= 2)
    for (const f of r) {
      assert.ok(f.startMs >= 0)
      assert.ok(f.endMs > f.startMs)
    }
  })

  test('keyframes chronologiquement croissants', () => {
    const r = textToVisemes('bonjour')
    for (let i = 1; i < r.length; i++) {
      assert.ok(r[i].startMs >= r[i - 1].startMs)
    }
  })

  test('mergeAdjacent fusionne visèmes identiques', () => {
    const r = textToVisemes('aaa')
    // "aaa" → 3 fois 'aa' fusionnés en 1 seul keyframe
    assert.ok(r.length <= 2)
  })

  test('wpm élevé → keyframes plus courts', () => {
    const slow = textToVisemes('bonjour', 80)
    const fast = textToVisemes('bonjour', 240)
    const slowDur = slow[slow.length - 1].endMs
    const fastDur = fast[fast.length - 1].endMs
    assert.ok(fastDur < slowDur)
  })

  test('accents FR mappés', () => {
    const r = textToVisemes('été')
    assert.ok(r.length > 0)
    // é → 'ee'
    assert.ok(r.some((f) => f.viseme === 'ee'))
  })

  test('caractères inconnus → rest', () => {
    const r = textToVisemes('@#$')
    assert.ok(r.every((f) => f.viseme === 'rest'))
  })
})

describe('VOICE_PROFILES', () => {
  test('contient 5 profils', () => {
    assert.equal(VOICE_PROFILES.length, 5)
  })

  test('IDs uniques', () => {
    const ids = VOICE_PROFILES.map((p) => p.id)
    assert.equal(new Set(ids).size, ids.length)
  })

  test('chaque profil a tous les champs', () => {
    for (const p of VOICE_PROFILES) {
      assert.ok(p.id)
      assert.ok(p.label)
      assert.ok(p.ttsModel)
      assert.ok(typeof p.pitchSemitones === 'number')
      assert.ok(typeof p.speed === 'number')
      assert.ok(p.stylePrompt)
      assert.ok(Array.isArray(p.defaultFor))
    }
  })

  test('chaque contexte est couvert par au moins un profil', () => {
    const contexts = ['cours', 'discussion', 'hype', 'narration', 'meditation'] as const
    for (const c of contexts) {
      assert.ok(
        VOICE_PROFILES.some((p) => p.defaultFor.includes(c)),
        `contexte ${c} pas couvert`,
      )
    }
  })
})

describe('pickProfileForContext', () => {
  test('cours → aurora-prof', () => {
    assert.equal(pickProfileForContext('cours').id, 'aurora-prof')
  })

  test('hype → aurora-hype', () => {
    assert.equal(pickProfileForContext('hype').id, 'aurora-hype')
  })

  test('meditation → aurora-zen', () => {
    assert.equal(pickProfileForContext('meditation').id, 'aurora-zen')
  })

  test('discussion → aurora-pote', () => {
    assert.equal(pickProfileForContext('discussion').id, 'aurora-pote')
  })

  test('narration → aurora-narrateur', () => {
    assert.equal(pickProfileForContext('narration').id, 'aurora-narrateur')
  })
})

describe('transition state machine', () => {
  test('start_speak depuis idle → speaking', () => {
    assert.equal(transition('idle', { kind: 'start_speak' }), 'speaking')
  })

  test('finish_speak depuis speaking → idle', () => {
    assert.equal(transition('speaking', { kind: 'finish_speak' }), 'idle')
  })

  test('user_voice_detected pendant speaking (rms haut) → fading', () => {
    assert.equal(transition('speaking', { kind: 'user_voice_detected', rms: 0.1 }), 'fading')
  })

  test('user_voice_detected pendant speaking (rms bas) → speaking inchangé', () => {
    assert.equal(transition('speaking', { kind: 'user_voice_detected', rms: 0.01 }), 'speaking')
  })

  test('user_voice_detected depuis fading → listening', () => {
    assert.equal(transition('fading', { kind: 'user_voice_detected', rms: 0.1 }), 'listening')
  })

  test('user_voice_detected depuis idle → listening', () => {
    assert.equal(transition('idle', { kind: 'user_voice_detected', rms: 0.1 }), 'listening')
  })

  test('user_voice_lost après debounce → processing', () => {
    assert.equal(transition('listening', { kind: 'user_voice_lost', sinceMs: 800 }), 'processing')
  })

  test('user_voice_lost avant debounce → listening inchangé', () => {
    assert.equal(transition('listening', { kind: 'user_voice_lost', sinceMs: 100 }), 'listening')
  })

  test('speech_recognised depuis processing → idle', () => {
    assert.equal(transition('processing', { kind: 'speech_recognised' }), 'idle')
  })

  test('reset depuis n importe quel état → idle', () => {
    assert.equal(transition('speaking', { kind: 'reset' }), 'idle')
    assert.equal(transition('listening', { kind: 'reset' }), 'idle')
    assert.equal(transition('fading', { kind: 'reset' }), 'idle')
  })

  test('VAD_RMS_THRESHOLD raisonnable', () => {
    assert.ok(VAD_RMS_THRESHOLD > 0 && VAD_RMS_THRESHOLD < 1)
  })

  test('VAD_LOST_DEBOUNCE_MS raisonnable', () => {
    assert.ok(VAD_LOST_DEBOUNCE_MS >= 200 && VAD_LOST_DEBOUNCE_MS <= 2000)
  })
})
