/**
 * Tests crypto classique : détection + casse de chiffres.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  caesarShift,
  chiSquareScore,
  crackCaesar,
  crackSingleByteXor,
  decodeBase64,
  decodeHex,
  detectCipher,
  frequencyAnalysis,
  guessCaesarShift,
  guessVigenerePeriod,
  indexOfCoincidence,
} from '../services/cyber/classicalCipherAnalysis.ts'

const FR_SAMPLE = 'le pendule simple est un dispositif mecanique qui oscille autour de sa position d equilibre la periode depend de la longueur du fil et de la pesanteur cette experience est classique au lycee la formule connue donne deux pi racine de l sur g il faut faire attention aux petites oscillations seules pour cette formule valide la mecanique nous enseigne beaucoup'
const EN_SAMPLE = 'the quick brown fox jumps over the lazy dog this sentence contains every letter of the english alphabet at least once and we will repeat the experience to gain more text the energy of motion depends on velocity and mass while gravity pulls everything toward the center of the earth physics teaches us beautiful patterns about the universe'

describe('Fréquences + IC + chi²', () => {
  test('frequencyAnalysis somme à 1 sur texte FR', () => {
    const f = frequencyAnalysis(FR_SAMPLE)
    const total = Object.values(f).reduce((a, b) => a + b, 0)
    assert.ok(Math.abs(total - 1) < 1e-6)
  })

  test('lettre "e" la plus fréquente en FR', () => {
    const f = frequencyAnalysis(FR_SAMPLE)
    const maxLetter = Object.entries(f).sort((a, b) => b[1] - a[1])[0][0]
    assert.equal(maxLetter, 'e')
  })

  test('IC ≈ 0.07-0.08 sur texte FR', () => {
    const ic = indexOfCoincidence(FR_SAMPLE)
    assert.ok(ic > 0.06 && ic < 0.10, `IC = ${ic}`)
  })

  test('IC ≈ 0.038 sur texte random (crypto)', async () => {
    const { randomBytes } = await import('node:crypto')
    const buf = randomBytes(2000)
    let rnd = ''
    for (const b of buf) rnd += String.fromCharCode(97 + (b % 26))
    const ic = indexOfCoincidence(rnd)
    assert.ok(ic < 0.05, `IC random = ${ic}`)
  })

  test('chi² plus bas pour bonne langue', () => {
    const chiFr = chiSquareScore(FR_SAMPLE, 'fr')
    const chiEn = chiSquareScore(FR_SAMPLE, 'en')
    assert.ok(chiFr < chiEn, `chi² FR ${chiFr} vs EN ${chiEn}`)
  })
})

describe('César cipher', () => {
  test('caesarShift puis inverse rend l\'original', () => {
    const cipher = caesarShift(FR_SAMPLE, 7)
    const back = caesarShift(cipher, -7)
    assert.equal(back, FR_SAMPLE)
  })

  test('guessCaesarShift retrouve la clé', () => {
    const cipher = caesarShift(FR_SAMPLE, 13)
    const shift = guessCaesarShift(cipher, 'fr')
    assert.equal(shift, 13)
  })

  test('crackCaesar retrouve le plaintext', () => {
    const cipher = caesarShift(FR_SAMPLE, 5)
    const result = crackCaesar(cipher, 'fr')
    assert.equal(result.shift, 5)
    assert.equal(result.plaintext.toLowerCase(), FR_SAMPLE.toLowerCase())
  })

  test('César sur texte EN cassé avec lang=en', () => {
    const cipher = caesarShift(EN_SAMPLE, 11)
    const r = crackCaesar(cipher, 'en')
    assert.equal(r.shift, 11)
  })
})

describe('Détection automatique', () => {
  test('plaintext FR détecté', () => {
    const d = detectCipher(FR_SAMPLE, 'fr')
    assert.equal(d.type, 'plaintext-fr')
  })

  test('plaintext EN détecté', () => {
    const d = detectCipher(EN_SAMPLE, 'en')
    assert.equal(d.type, 'plaintext-en')
  })

  test('César détecté avec shift', () => {
    const cipher = caesarShift(FR_SAMPLE, 7)
    const d = detectCipher(cipher, 'fr')
    assert.ok(['caesar', 'rot13'].includes(d.type))
    assert.match(d.hint ?? '', /shift=7/)
  })

  test('ROT13 spécifiquement reconnu', () => {
    const cipher = caesarShift(FR_SAMPLE, 13)
    const d = detectCipher(cipher, 'fr')
    assert.equal(d.type, 'rot13')
  })

  test('Base64 reconnu', () => {
    const b64 = Buffer.from(FR_SAMPLE).toString('base64')
    const d = detectCipher(b64, 'fr')
    assert.equal(d.type, 'base64')
  })

  test('Hex reconnu', () => {
    const hex = Buffer.from(FR_SAMPLE).toString('hex')
    const d = detectCipher(hex, 'fr')
    assert.equal(d.type, 'hex')
  })

  test('Vigenère période détectée', () => {
    // Encode avec clé "ABC" (période 3)
    const key = 'ABC'
    let cipher = ''
    for (let i = 0; i < FR_SAMPLE.length; i += 1) {
      const ch = FR_SAMPLE[i]
      if (ch >= 'a' && ch <= 'z') {
        const k = key.charCodeAt(i % key.length) - 65
        cipher += String.fromCharCode(((ch.charCodeAt(0) - 97 + k) % 26) + 97)
      } else cipher += ch
    }
    const period = guessVigenerePeriod(cipher)
    // Période trouvée doit être multiple de 3 OU 3 lui-même
    assert.ok(period === 3 || period === 6 || period === 9 || period === 12, `period ${period}`)
  })

  test('texte trop court → unknown', () => {
    const d = detectCipher('ab', 'fr')
    assert.equal(d.type, 'unknown')
  })
})

describe('Décodeurs', () => {
  test('Base64 round-trip', () => {
    const b64 = Buffer.from('Hello Aurora').toString('base64')
    assert.equal(decodeBase64(b64), 'Hello Aurora')
  })

  test('Hex round-trip', () => {
    const hex = Buffer.from('Aurora 42').toString('hex')
    assert.equal(decodeHex(hex), 'Aurora 42')
  })

  test('Hex impair → null', () => {
    assert.equal(decodeHex('abc'), null)
  })

  test('crackSingleByteXor retrouve une clé', () => {
    const plaintext = FR_SAMPLE
    const key = 0x42
    const enc = new Uint8Array(plaintext.length)
    for (let i = 0; i < plaintext.length; i += 1) enc[i] = plaintext.charCodeAt(i) ^ key
    const r = crackSingleByteXor(enc, 'fr')
    assert.equal(r.key, key)
    assert.equal(r.plaintext, plaintext)
  })
})
