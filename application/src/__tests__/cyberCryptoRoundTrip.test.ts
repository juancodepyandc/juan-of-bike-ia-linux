/**
 * Chiffres classiques — vecteurs normalisés et aller-retour par propriété.
 *
 * POURQUOI CE FICHIER EXISTE. Les tests du laboratoire crypto portaient sur
 * de l'ASCII. Trois défauts vivaient hors de ce périmètre :
 *
 *   1. `railFence` chiffrait en POINTS DE CODE (`for...of`) et déchiffrait en
 *      UNITÉS UTF-16 (`text.length`, `text[i]`). Dès qu'un caractère hors BMP
 *      — le moindre emoji — entrait, les deux côtés ne comptaient pas le même
 *      nombre de cases. Mesure : 254 aller-retours cassés sur 280 avec emoji,
 *      0 sur 700 en ASCII et BMP. Le déchiffrement rendait des demi-substituts.
 *   2. `toBase64` LEVAIT `URIError: URI malformed` sur un substitut isolé —
 *      exactement ce que produit un `slice()` au milieu d'un emoji, cas
 *      courant dès que l'interface tronque un message.
 *   3. `toMorse` jetait toute ponctuation en silence : « a,b » revenait « ab ».
 *
 * MÉTHODE. Deux étages. D'abord les vecteurs canoniques publiés, qui ancrent
 * l'implémentation sur une référence extérieure. Ensuite des tests de
 * PROPRIÉTÉ sur un alphabet couvrant les quatre classes d'UTF-8 (ASCII, latin
 * accentué, CJK, hors-BMP) : l'aller-retour doit rendre l'entrée, pour toute
 * longueur et tout paramètre.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/cyberCryptoRoundTrip.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  caesarShift, rot13, atbash, vigenere, railFence,
  toBase64, fromBase64, toHex, fromHex, toBinary, fromBinary,
  toMorse, fromMorse, morseUnsupported, modPow,
} from '../services/cyber/cryptoService.ts'

// --- Vecteurs canoniques ---------------------------------------------------
describe('vecteurs normalisés publiés', () => {
  test('Vigenère : ATTACKATDAWN + LEMON = LXFOPVEFRNHR', () => {
    assert.equal(vigenere('ATTACKATDAWN', 'LEMON'), 'LXFOPVEFRNHR')
    assert.equal(vigenere('LXFOPVEFRNHR', 'LEMON', true), 'ATTACKATDAWN')
  })

  test('Vigenère : le compteur de clé ignore les non-lettres', () => {
    assert.equal(vigenere('ATTACK AT DAWN', 'LEMON'), 'LXFOPV EF RNHR')
  })

  test('haie : WEAREDISCOVEREDFLEEATONCE / 3 rails', () => {
    assert.equal(railFence('WEAREDISCOVEREDFLEEATONCE', 3), 'WECRLTEERDSOEEFEAOCAIVDEN')
    assert.equal(railFence('WECRLTEERDSOEEFEAOCAIVDEN', 3, true), 'WEAREDISCOVEREDFLEEATONCE')
  })

  test('ROT13 est son propre inverse ; Atbash aussi', () => {
    assert.equal(rot13(rot13('Bonjour, Aurora !')), 'Bonjour, Aurora !')
    assert.equal(atbash(atbash('Bonjour, Aurora !')), 'Bonjour, Aurora !')
    assert.equal(rot13('Hello'), 'Uryyb')
  })

  test('César : décalage modulaire et négatif', () => {
    assert.equal(caesarShift('abc', 29), caesarShift('abc', 3))
    assert.equal(caesarShift('abc', -3), 'xyz')
    assert.equal(caesarShift('Attaque à l’aube !', 0), 'Attaque à l’aube !')
  })

  test('modPow : exposant nul, module 1, grandes valeurs', () => {
    assert.equal(modPow(7n, 0n, 13n), 1n)
    assert.equal(modPow(5n, 117n, 19n), 1n)
    assert.equal(modPow(2n, 1000n, 1n), 0n)
    // Petit Fermat : a^(p-1) ≡ 1 [p] pour p premier ne divisant pas a.
    for (const p of [7n, 13n, 97n, 1009n]) assert.equal(modPow(3n, p - 1n, p), 1n)
  })

  test('morse : vecteurs UIT-R M.1677-1', () => {
    assert.equal(toMorse('sos'), '... --- ...')
    assert.equal(fromMorse('... --- ...'), 'sos')
    assert.equal(toMorse(','), '--..--')
    assert.equal(toMorse('?'), '..--..')
  })
})

// --- Alphabet couvrant les quatre classes d'UTF-8 --------------------------
// Découpé PAR POINT DE CODE : sinon on fabrique des substituts isolés, qui
// sont un cas à part testé séparément.
const ALPHABET = [...'abcXYZ0123 éàüñ€漢字🙂🇫🇷!?,;:.']

function echantillons(n: number): string[] {
  const out: string[] = []
  for (let i = 0; i < n; i += 1) {
    let s = ''
    const len = 1 + ((i * 7) % 40)
    for (let j = 0; j < len; j += 1) s += ALPHABET[(i * 31 + j * 17) % ALPHABET.length]
    out.push(s)
  }
  return out
}

const ECHANTILLONS = echantillons(200)

describe('aller-retour sur 200 chaînes UTF-8 (ASCII, accents, CJK, hors-BMP)', () => {
  test('base64', () => {
    for (const s of ECHANTILLONS) assert.equal(fromBase64(toBase64(s)), s, JSON.stringify(s))
  })

  test('hexadécimal', () => {
    for (const s of ECHANTILLONS) assert.equal(fromHex(toHex(s)), s, JSON.stringify(s))
  })

  test('binaire', () => {
    for (const s of ECHANTILLONS) assert.equal(fromBinary(toBinary(s)), s, JSON.stringify(s))
  })

  test('Vigenère', () => {
    for (const s of ECHANTILLONS) assert.equal(vigenere(vigenere(s, 'clef'), 'clef', true), s)
  })

  test('haie, pour 2 à 8 rails — 1 400 aller-retours', () => {
    let cassés = 0
    const exemples: string[] = []
    for (const s of ECHANTILLONS) {
      for (let rails = 2; rails <= 8; rails += 1) {
        const retour = railFence(railFence(s, rails), rails, true)
        if (retour !== s) {
          cassés += 1
          if (exemples.length < 3) exemples.push(`${rails} rails : ${JSON.stringify(s)} → ${JSON.stringify(retour)}`)
        }
      }
    }
    assert.equal(cassés, 0, `${cassés} aller-retours cassés. Exemples :\n${exemples.join('\n')}`)
  })
})

describe('haie — balayage exhaustif ASCII / BMP / hors-BMP', () => {
  const familles: Array<[string, (j: number) => string]> = [
    ['ASCII', (j) => String.fromCharCode(97 + (j % 26))],
    ['BMP accentué et CJK', (j) => 'éàüñ€漢'[j % 6]],
    ['hors-BMP (emoji)', (j) => (j % 3 === 0 ? '🙂' : 'a')],
  ]
  for (const [nom, gen] of familles) {
    test(`${nom} : longueurs 1 à 40, rails 2 à 8`, () => {
      for (let len = 1; len <= 40; len += 1) {
        let s = ''
        for (let j = 0; j < len; j += 1) s += gen(j)
        for (let rails = 2; rails <= 8; rails += 1) {
          assert.equal(
            railFence(railFence(s, rails), rails, true), s,
            `${nom}, longueur ${len}, ${rails} rails`,
          )
        }
      }
    })
  }

  test('un rail ou moins laisse le texte inchangé', () => {
    for (const r of [0, 1, -3]) assert.equal(railFence('bonjour 🙂', r), 'bonjour 🙂')
  })
})

describe('substitut isolé — texte tronqué au milieu d’un emoji', () => {
  const tronqué = 'salut 🙂'.slice(0, 7) // coupe la paire de substitution

  test('toBase64 ne lève pas d’exception', () => {
    assert.doesNotThrow(() => toBase64(tronqué))
    assert.ok(toBase64(tronqué).length > 0)
  })

  test('toHex et toBinary non plus', () => {
    assert.doesNotThrow(() => toHex(tronqué))
    assert.doesNotThrow(() => toBinary(tronqué))
  })

  test('le substitut isolé devient U+FFFD, conformément à la norme', () => {
    assert.equal(fromBase64(toBase64(tronqué)), 'salut �')
  })

  test('fromBase64 rend la chaîne vide sur une entrée invalide, sans lever', () => {
    assert.equal(fromBase64('ceci n’est pas du base64 !!'), '')
    assert.equal(fromBase64(''), '')
  })
})

describe('morse — la ponctuation ne disparaît plus en silence', () => {
  const PHRASES = [
    'sos', 'hello world', 'a,b', 'attaque a l aube !',
    'rendez-vous : 8h30, porte 4 ?', 'operateur prive de creme',
  ]
  for (const phrase of PHRASES) {
    test(`aller-retour « ${phrase} »`, () => {
      const perdus = morseUnsupported(phrase)
      assert.deepEqual(perdus, [], `caractères non transcrits : ${perdus.join(' ')}`)
      assert.equal(fromMorse(toMorse(phrase)), phrase.toLowerCase())
    })
  }

  test('morseUnsupported nomme ce qui ne passe pas, au lieu de le jeter', () => {
    assert.deepEqual(morseUnsupported('漢字'), ['漢', '字'])
    assert.deepEqual(morseUnsupported('abc 123'), [])
  })

  test('un jeton morse inconnu ne casse pas le décodage', () => {
    assert.equal(fromMorse('... -------- ...'), 'ss')
  })
})
