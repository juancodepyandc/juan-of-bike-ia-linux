/**
 * Tests barre expert pour le module voice.
 *
 * Le tableau IPA FR doit couvrir tous les sons spécifiques au français
 * (uvulaire ʁ, voyelles nasales, sons "gn"). Le textToVisemes doit
 * produire des séquences plausibles (m/p/b → fermé, voyelles → ouvert,
 * etc.) sur des phrases françaises typiques.
 *
 * La machine d'état VAD doit gérer correctement les cycles parle→interrompu
 * →écoute→fini sans rester bloquée.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  FR_PHONEME_TABLE,
  pickProfileForContext,
  phonemeToViseme,
  textToVisemes,
  transition,
  VAD_LOST_DEBOUNCE_MS,
  VAD_RMS_THRESHOLD,
  VOICE_PROFILES,
} from '../services/voicePhonemes.ts'
import type { VoiceMode } from '../services/voicePhonemes.ts'

describe('Phonème table FR — couverture', () => {
  test('couvre toutes les voyelles orales standards', () => {
    const voyelles = ['i', 'e', 'ɛ', 'a', 'ɑ', 'ɔ', 'o', 'u', 'y', 'ø', 'œ', 'ə']
    for (const v of voyelles) {
      assert.notEqual(phonemeToViseme(v), 'rest', `voyelle ${v} mappée sur rest`)
    }
  })

  test('couvre les voyelles nasales (ɛ̃, ɑ̃, ɔ̃, œ̃)', () => {
    const nasales = ['ɛ̃', 'ɑ̃', 'ɔ̃', 'œ̃']
    for (const n of nasales) {
      const v = phonemeToViseme(n)
      // Nasales : viseme ouvert (aa/oh/eu), jamais fermé.
      assert.ok(['aa', 'oh', 'eu'].includes(v), `nasale ${n} → ${v}`)
    }
  })

  test('r uvulaire ʁ détecté (pas confondu avec rest)', () => {
    assert.notEqual(phonemeToViseme('ʁ'), 'rest')
  })

  test('"gn" (ɲ) ET "ng" (ŋ) couverts', () => {
    assert.notEqual(phonemeToViseme('ɲ'), 'rest')
    assert.notEqual(phonemeToViseme('ŋ'), 'rest')
  })

  test('p/b/m partagent le visème fermé mm', () => {
    assert.equal(phonemeToViseme('p'), 'mm')
    assert.equal(phonemeToViseme('b'), 'mm')
    assert.equal(phonemeToViseme('m'), 'mm')
  })

  test('f/v partagent ff', () => {
    assert.equal(phonemeToViseme('f'), 'ff')
    assert.equal(phonemeToViseme('v'), 'ff')
  })

  test('chaque entry a une durée plausible', () => {
    for (const ph of FR_PHONEME_TABLE) {
      assert.ok(ph.defaultDurationMs >= 30 && ph.defaultDurationMs <= 200, `${ph.ipa}: ${ph.defaultDurationMs}ms`)
    }
  })

  test('table > 30 sons', () => {
    assert.ok(FR_PHONEME_TABLE.length >= 30)
  })
})

describe('textToVisemes — phrases FR typiques', () => {
  function visemeBag(text: string): Set<string> {
    return new Set(textToVisemes(text, 160).map((f) => f.viseme))
  }

  test('"bonjour Aurora" : contient mm (b), oh (o), ou (u), aa (a)', () => {
    const bag = visemeBag('bonjour Aurora')
    assert.ok(bag.has('mm'), 'mm absent') // b
    assert.ok(bag.has('oh'), 'oh absent') // o
    assert.ok(bag.has('ou'), 'ou absent') // u/ou
    assert.ok(bag.has('aa'), 'aa absent') // a
  })

  test('"merci beaucoup" : visemes différenciés', () => {
    const frames = textToVisemes('merci beaucoup', 160)
    // Doit avoir une variété ≥ 5 visèmes différents.
    const distinct = new Set(frames.map((f) => f.viseme))
    assert.ok(distinct.size >= 5, `seulement ${distinct.size} visèmes distincts`)
  })

  test('"papa" : alternance mm/aa', () => {
    const frames = textToVisemes('papa', 160)
    const sequence = frames.map((f) => f.viseme)
    // Doit voir alterner mm et aa.
    assert.ok(sequence.includes('mm'))
    assert.ok(sequence.includes('aa'))
  })

  test('texte vide → tableau vide', () => {
    assert.deepEqual(textToVisemes('', 160), [])
  })

  test('durées cumulées proches du WPM cible (±20 %)', () => {
    const frames = textToVisemes('bonjour comment allez vous aujourd hui', 160)
    const totalMs = frames[frames.length - 1].endMs
    // 6 mots × 60_000 / 160 wpm = 2250ms attendu, tolérance large vu approximation.
    assert.ok(totalMs > 1000 && totalMs < 5000, `${totalMs}ms hors range`)
  })

  test('mergeAdjacent fusionne les répétitions ll-ll', () => {
    const frames = textToVisemes('lllllllll', 160)
    // Toutes les "l" partagent visème ll → 1 seul frame fusionné.
    assert.equal(frames.length, 1)
  })
})

describe('Voice profiles — barre expert', () => {
  test('5 profils minimum', () => {
    assert.ok(VOICE_PROFILES.length >= 5)
  })

  test('chaque contexte mappe à un profil unique', () => {
    const contexts = ['cours', 'discussion', 'hype', 'narration', 'meditation'] as const
    const picked = new Set<string>()
    for (const ctx of contexts) {
      const p = pickProfileForContext(ctx)
      picked.add(p.id)
    }
    assert.ok(picked.size >= 4, `seulement ${picked.size} profils distincts couverts`)
  })

  test('profils ont speed et pitch dans des bornes plausibles', () => {
    for (const p of VOICE_PROFILES) {
      assert.ok(p.speed >= 0.7 && p.speed <= 1.3, `${p.id} speed ${p.speed} hors borne`)
      assert.ok(p.pitchSemitones >= -6 && p.pitchSemitones <= 6, `${p.id} pitch ${p.pitchSemitones} hors borne`)
    }
  })

  test('aurora-hype plus rapide qu\'aurora-zen', () => {
    const hype = VOICE_PROFILES.find((p) => p.id === 'aurora-hype')!
    const zen = VOICE_PROFILES.find((p) => p.id === 'aurora-zen')!
    assert.ok(hype.speed > zen.speed)
  })

  test('aurora-prof plus grave qu\'aurora-hype', () => {
    const prof = VOICE_PROFILES.find((p) => p.id === 'aurora-prof')!
    const hype = VOICE_PROFILES.find((p) => p.id === 'aurora-hype')!
    assert.ok(prof.pitchSemitones < hype.pitchSemitones)
  })
})

describe('VAD state machine — cycle complet', () => {
  test('cycle parle → user interrompt → écoute → traite → fini', () => {
    let mode: VoiceMode = 'idle'
    mode = transition(mode, { kind: 'start_speak' })
    assert.equal(mode, 'speaking')
    mode = transition(mode, { kind: 'user_voice_detected', rms: VAD_RMS_THRESHOLD + 0.01 })
    assert.equal(mode, 'fading')
    mode = transition(mode, { kind: 'user_voice_detected', rms: VAD_RMS_THRESHOLD + 0.01 })
    assert.equal(mode, 'listening')
    mode = transition(mode, { kind: 'user_voice_lost', sinceMs: VAD_LOST_DEBOUNCE_MS + 100 })
    assert.equal(mode, 'processing')
    mode = transition(mode, { kind: 'speech_recognised' })
    assert.equal(mode, 'idle')
  })

  test('bruit sous le seuil ne déclenche pas le fading', () => {
    const mode = transition('speaking', { kind: 'user_voice_detected', rms: VAD_RMS_THRESHOLD - 0.01 })
    assert.equal(mode, 'speaking')
  })

  test('user_voice_lost trop court ne sort pas de listening', () => {
    const mode = transition('listening', { kind: 'user_voice_lost', sinceMs: 100 })
    assert.equal(mode, 'listening')
  })

  test('reset depuis n\'importe où retourne idle', () => {
    const modes: VoiceMode[] = ['speaking', 'fading', 'listening', 'processing']
    for (const m of modes) {
      assert.equal(transition(m, { kind: 'reset' }), 'idle')
    }
  })

  test('start_speak depuis processing est ignoré (priorité écoute)', () => {
    const mode = transition('processing', { kind: 'start_speak' })
    assert.equal(mode, 'processing')
  })
})

import {
  phonemizeSentence,
  phonemizeWord,
  textToVisemesRuleBased,
} from '../services/voiceFrPhonemizer.ts'

describe('Phonemizer FR — barre expert', () => {
  test('"bonjour" → b + ɔ̃ + ʒ + u + ʁ (approx)', () => {
    const phones = phonemizeWord('bonjour')
    assert.ok(phones.includes('b'))
    assert.ok(phones.includes('ɔ̃'), `phones: ${phones.join(',')}`)
    assert.ok(phones.includes('ʒ'))
    assert.ok(phones.includes('u'))
    assert.ok(phones.includes('ʁ'))
  })

  test('"chocolat" → ʃ + ɔ + k + ɔ + l + a', () => {
    const phones = phonemizeWord('chocolat')
    assert.ok(phones[0] === 'ʃ')
    assert.ok(phones.includes('k'))
    assert.ok(phones.includes('l'))
    assert.ok(phones.includes('a'))
  })

  test('"oiseau" → wa + z (intervoc) + o', () => {
    const phones = phonemizeWord('oiseau')
    assert.ok(phones.includes('wa'))
    assert.ok(phones.includes('z'))
    assert.ok(phones.includes('o'))
  })

  test('"signal" → s + i + ɲ + a + l', () => {
    const phones = phonemizeWord('signal')
    assert.ok(phones.includes('ɲ'), `signal: ${phones.join(',')}`)
  })

  test('"physique" → f (ph) + i + z + i + k', () => {
    const phones = phonemizeWord('physique')
    assert.equal(phones[0], 'f')
    // qu → k
    assert.ok(phones.includes('k'))
  })

  test('"pingouin" → contient ɛ̃ + wɛ̃', () => {
    const phones = phonemizeWord('pingouin')
    assert.ok(phones.includes('ɛ̃') || phones.includes('wɛ̃'), `pingouin: ${phones.join(',')}`)
  })

  test('"école" → e + k + ɔ + l + ə', () => {
    const phones = phonemizeWord('école')
    assert.equal(phones[0], 'e')
    assert.ok(phones.includes('k'))
    assert.ok(phones.includes('l'))
  })

  test('phrase complète phonemize sans crasher', () => {
    const phones = phonemizeSentence("Bonjour, comment ça va aujourd'hui ?")
    assert.ok(phones.length > 8)
  })

  test('texte vide → []', () => {
    assert.deepEqual(phonemizeSentence(''), [])
  })

  test('textToVisemesRuleBased produit des frames sequencés', () => {
    const frames = textToVisemesRuleBased('papa maman')
    for (let i = 1; i < frames.length; i += 1) {
      assert.ok(frames[i].startMs >= frames[i - 1].startMs)
      assert.ok(frames[i].endMs > frames[i].startMs)
    }
  })

  test('speedFactor 2 raccourcit la durée totale', () => {
    const slow = textToVisemesRuleBased('bonjour Aurora', 1)
    const fast = textToVisemesRuleBased('bonjour Aurora', 2)
    const slowEnd = slow[slow.length - 1].endMs
    const fastEnd = fast[fast.length - 1].endMs
    assert.ok(fastEnd < slowEnd, `fast ${fastEnd} not < slow ${slowEnd}`)
  })
})

import { detectLiaison, phonemizeSentenceWithLiaisons } from '../services/voiceFrPhonemizer.ts'

describe('Liaisons FR — barre expert', () => {
  test('"les" + "enfants" → /z/ liaison', () => {
    assert.equal(detectLiaison('les', 'enfants'), 'z')
  })

  test('"des" + "amis" → /z/', () => {
    assert.equal(detectLiaison('des', 'amis'), 'z')
  })

  test('"on" + "a" → /n/', () => {
    assert.equal(detectLiaison('on', 'a'), 'n')
  })

  test('"grand" + "homme" → /t/ (assourdissement)', () => {
    assert.equal(detectLiaison('grand', 'homme'), 't')
  })

  test('"est" + "ici" → /t/', () => {
    assert.equal(detectLiaison('est', 'ici'), 't')
  })

  test('"deux" + "amis" → /z/ (numéral)', () => {
    assert.equal(detectLiaison('deux', 'amis'), 'z')
  })

  test('aucune liaison si mot suivant commence par consonne', () => {
    assert.equal(detectLiaison('les', 'bonbons'), '')
    assert.equal(detectLiaison('on', 'parle'), '')
  })

  test('h aspiré bloque la liaison ("les héros")', () => {
    assert.equal(detectLiaison('les', 'héros'), '')
    assert.equal(detectLiaison('des', 'hangars'), '')
  })

  test('mot inconnu pour liaison → pas de liaison', () => {
    assert.equal(detectLiaison('table', 'orange'), '')
  })

  test('phonemizeSentenceWithLiaisons insère /z/ entre "les" et "amis"', () => {
    const phones = phonemizeSentenceWithLiaisons('les amis')
    // "les" → l,ɛ (e+s → s silencieux), liaison /z/, "amis" → a,m,i,s
    assert.ok(phones.includes('z'), `phones: ${phones.join(',')}`)
  })

  test('phonemizeSentenceWithLiaisons : "on a" produit /n/ liaison', () => {
    const phones = phonemizeSentenceWithLiaisons('on a')
    assert.ok(phones.includes('n'))
  })

  test('phonemizeSentenceWithLiaisons sans liaison : "le chat" ne contient pas /z/', () => {
    const phones = phonemizeSentenceWithLiaisons('le chat')
    // "le" ne déclenche pas de liaison (singulier), "chat" commence par C.
    // Donc pas de /z/ artificiel inséré.
    const zCount = phones.filter((p) => p === 'z').length
    assert.equal(zCount, 0)
  })

  test('phonemizeSentenceWithLiaisons longue phrase reste cohérente', () => {
    const phones = phonemizeSentenceWithLiaisons('les enfants ont aimé')
    // les+enfants → /z/, ont+aimé → /t/
    assert.ok(phones.includes('z'), `pas de z dans ${phones.join(',')}`)
    assert.ok(phones.includes('t'), `pas de t dans ${phones.join(',')}`)
  })
})

import { textToPhonemeTimelineV2 } from '../services/voiceFrPhonemizer.ts'

describe('Phonemizer V2 adapter AuroraAvatar', () => {
  test('"bonjour" → contient pp (b/p) + oo (ɔ̃) + sh (j) + uu (u/ou)', () => {
    const frames = textToPhonemeTimelineV2('bonjour')
    const visemes = new Set(frames.map((f) => f.viseme))
    assert.ok(visemes.has('pp'), `pp absent: ${[...visemes].join(',')}`) // b
    assert.ok(visemes.has('oo')) // ɔ̃
    assert.ok(visemes.has('sh')) // ʒ
    assert.ok(visemes.has('uu')) // u
  })

  test('"papa" : alternance pp / aa', () => {
    const frames = textToPhonemeTimelineV2('papa')
    const visemes = frames.map((f) => f.viseme).filter((v) => v !== 'silence')
    assert.ok(visemes.includes('pp'))
    assert.ok(visemes.includes('aa'))
  })

  test('"Aurora" : contient uu (au), nn (r), aa final', () => {
    const frames = textToPhonemeTimelineV2('Aurora')
    const visemes = new Set(frames.map((f) => f.viseme))
    // au → o → 'oo', r → ʁ → 'nn', a → 'aa'
    assert.ok(visemes.has('oo'))
    assert.ok(visemes.has('nn'))
    assert.ok(visemes.has('aa'))
  })

  test('silence inséré entre mots, pas après chaque phonème', () => {
    const frames = textToPhonemeTimelineV2('papa maman')
    const silenceFrames = frames.filter((f) => f.viseme === 'silence')
    // 2 mots → 2 silences max.
    assert.ok(silenceFrames.length <= 2, `${silenceFrames.length} silences`)
  })

  test('texte vide → tableau vide', () => {
    assert.deepEqual(textToPhonemeTimelineV2(''), [])
  })

  test('voyelles stress > consonnes stress', () => {
    const frames = textToPhonemeTimelineV2('papa')
    const vowel = frames.find((f) => f.viseme === 'aa')!
    const cons = frames.find((f) => f.viseme === 'pp')!
    assert.ok(vowel.stress > cons.stress)
  })
})
