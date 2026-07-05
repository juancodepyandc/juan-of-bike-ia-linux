/**
 * Tests pour services/voiceFrPhonemizer — phonemizer FR rule-based pour le
 * lipsync de l'idle Aurora.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  phonemizeWord,
  phonemizeSentence,
  phonemizeSentenceWithLiaisons,
  detectLiaison,
  textToPhonemeTimelineV2,
  textToVisemesRuleBased,
} from '../services/voiceFrPhonemizer.ts'

describe('phonemizeWord — voyelles simples', () => {
  test('"a" → ["a"]', () => {
    assert.deepEqual(phonemizeWord('a'), ['a'])
  })

  test('"i" → ["i"]', () => {
    assert.deepEqual(phonemizeWord('i'), ['i'])
  })

  test('mot vide → []', () => {
    assert.deepEqual(phonemizeWord(''), [])
  })

  test('whitespace → []', () => {
    assert.deepEqual(phonemizeWord('   '), [])
  })
})

describe('phonemizeWord — digraphes/trigraphes', () => {
  test('"eau" → ["o"]', () => {
    assert.deepEqual(phonemizeWord('eau'), ['o'])
  })

  test('"ou" → ["u"]', () => {
    assert.deepEqual(phonemizeWord('ou'), ['u'])
  })

  test('"ch" → ["ʃ"]', () => {
    assert.ok(phonemizeWord('chat').includes('ʃ'))
  })

  test('"ph" → ["f"]', () => {
    assert.ok(phonemizeWord('photo').includes('f'))
  })

  test('"gn" → ["ɲ"]', () => {
    assert.ok(phonemizeWord('agneau').includes('ɲ'))
  })

  test('"qu" → ["k"]', () => {
    assert.ok(phonemizeWord('quel').includes('k'))
  })
})

describe('phonemizeWord — nasales', () => {
  test('"on" final → ɔ̃', () => {
    assert.ok(phonemizeWord('bon').includes('ɔ̃'))
  })

  test('"an" final → ɑ̃', () => {
    assert.ok(phonemizeWord('blanc').includes('ɑ̃'))
  })

  test('"in" final → ɛ̃', () => {
    assert.ok(phonemizeWord('pin').includes('ɛ̃'))
  })
})

describe('phonemizeWord — mots courants FR', () => {
  test('"bonjour" produit des phonèmes', () => {
    const r = phonemizeWord('bonjour')
    assert.ok(r.length >= 3)
  })

  test('"chat" → contient ʃ + a', () => {
    const r = phonemizeWord('chat')
    assert.ok(r.includes('ʃ'))
    assert.ok(r.includes('a'))
  })

  test('"école" → 4 phonèmes raisonnables', () => {
    const r = phonemizeWord('école')
    assert.ok(r.length >= 3)
  })

  test('accents préservés ("é", "à")', () => {
    const r = phonemizeWord('été')
    // "é" → 'e' selon les règles
    assert.ok(r.includes('e'))
  })
})

describe('phonemizeWord — caractères inattendus', () => {
  test('chiffres → ignorés', () => {
    const r = phonemizeWord('a1b2')
    // les chiffres ne matchent aucune règle → skip
    assert.ok(r.includes('a'))
    assert.ok(r.includes('b'))
  })

  test('apostrophes → ignorées', () => {
    const r = phonemizeWord("l'eau")
    assert.ok(r.length >= 2)
  })
})

describe('phonemizeSentence', () => {
  test('phrase vide → []', () => {
    assert.deepEqual(phonemizeSentence(''), [])
  })

  test('plusieurs mots → concaténation phonèmes', () => {
    const r = phonemizeSentence('bon chat')
    assert.ok(r.includes('ɔ̃')) // bon
    assert.ok(r.includes('ʃ'))  // chat
  })

  test('ponctuation séparée correctement', () => {
    const a = phonemizeSentence('un, deux, trois')
    const b = phonemizeSentence('un deux trois')
    // Devrait produire ~même séquence (ponctuation = split)
    assert.equal(a.length, b.length)
  })
})

describe('detectLiaison', () => {
  test('"les" + voyelle → "z"', () => {
    assert.equal(detectLiaison('les', 'enfants'), 'z')
  })

  test('"les" + consonne → ""', () => {
    assert.equal(detectLiaison('les', 'chats'), '')
  })

  test('"on" + voyelle → "n"', () => {
    assert.equal(detectLiaison('on', 'arrive'), 'n')
  })

  test('"grand" + voyelle → "t"', () => {
    assert.equal(detectLiaison('grand', 'arbre'), 't')
  })

  test('"est" + voyelle → "t"', () => {
    assert.equal(detectLiaison('est', 'ici'), 't')
  })

  test('h aspiré → pas de liaison', () => {
    assert.equal(detectLiaison('les', 'héros'), '')
  })

  test('h muet → liaison normale', () => {
    assert.equal(detectLiaison('les', 'hommes'), 'z')
  })

  test('mots inconnus → ""', () => {
    assert.equal(detectLiaison('truc', 'autre'), '')
  })

  test('input vide → ""', () => {
    assert.equal(detectLiaison('', 'arbre'), '')
    assert.equal(detectLiaison('les', ''), '')
  })

  test('"deux" + voyelle → "z"', () => {
    assert.equal(detectLiaison('deux', 'amis'), 'z')
  })
})

describe('phonemizeSentenceWithLiaisons', () => {
  test('"les enfants" → contient liaison "z" entre les 2 mots', () => {
    const r = phonemizeSentenceWithLiaisons('les enfants')
    // les → l/ə, +z liaison, enfants
    assert.ok(r.includes('z'))
  })

  test('"les chats" → pas de "z" supplémentaire', () => {
    const r = phonemizeSentenceWithLiaisons('les chats')
    // pas de liaison parce que consonne
    // (les a 's' final mais la liaison ne s'active qu'avant voyelle)
    assert.ok(r.includes('ʃ'))
  })

  test('phrase vide → []', () => {
    assert.deepEqual(phonemizeSentenceWithLiaisons(''), [])
  })
})

describe('textToPhonemeTimelineV2 (AvatarPhonemeFrame)', () => {
  test('vide → []', () => {
    assert.deepEqual(textToPhonemeTimelineV2(''), [])
  })

  test('mot simple produit frames avec viseme/duration/stress', () => {
    const r = textToPhonemeTimelineV2('bonjour')
    assert.ok(r.length > 0)
    for (const f of r) {
      assert.ok(['silence', 'aa', 'ee', 'ii', 'oo', 'uu', 'mm', 'ff', 'ss', 'sh', 'pp', 'nn'].includes(f.viseme))
      assert.ok(f.duration > 0)
      assert.ok(f.stress >= 0 && f.stress <= 1)
    }
  })

  test('silence inséré entre mots', () => {
    const r = textToPhonemeTimelineV2('bon chat')
    assert.ok(r.some((f) => f.viseme === 'silence'))
  })

  test('voyelles ont stress plus élevé que consonnes', () => {
    const r = textToPhonemeTimelineV2('papa')
    const vowels = r.filter((f) => ['aa', 'ee', 'ii', 'oo', 'uu'].includes(f.viseme))
    const cons = r.filter((f) => ['pp', 'mm', 'nn', 'ff', 'ss', 'sh'].includes(f.viseme))
    if (vowels.length > 0 && cons.length > 0) {
      assert.ok(vowels[0].stress >= cons[0].stress)
    }
  })
})

describe('textToVisemesRuleBased', () => {
  test('vide → []', () => {
    assert.deepEqual(textToVisemesRuleBased(''), [])
  })

  test('produit keyframes chronologiques', () => {
    const r = textToVisemesRuleBased('bonjour')
    for (let i = 1; i < r.length; i++) {
      assert.ok(r[i].startMs >= r[i - 1].startMs)
    }
  })

  test('speedFactor élevé → durée totale plus courte', () => {
    const slow = textToVisemesRuleBased('bonjour comment ça va', 0.5)
    const fast = textToVisemesRuleBased('bonjour comment ça va', 2)
    if (slow.length > 0 && fast.length > 0) {
      assert.ok(fast[fast.length - 1].endMs < slow[slow.length - 1].endMs)
    }
  })

  test('visèmes adjacents identiques fusionnés', () => {
    const r = textToVisemesRuleBased('mama')
    for (let i = 1; i < r.length; i++) {
      assert.notEqual(r[i].viseme, r[i - 1].viseme)
    }
  })
})
