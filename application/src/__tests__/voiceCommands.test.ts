/**
 * Tests pour normalize + parseNavigation — le parser de commandes vocales globales.
 *
 * tryHandleVoiceCommand lui-même n'est pas testé directement ici car il a des
 * effets de bord (useAppStore, window.dispatchEvent) — les helpers internes
 * pures suffisent à verrouiller les patterns d'intention vocale.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { normalize, parseNavigation } from '../utils/voiceCommandsCore.ts'

describe('normalize', () => {
  test('lowercase', () => {
    assert.equal(normalize('OUVRE LE CHAT'), 'ouvre le chat')
  })

  test('strip diacritics', () => {
    assert.equal(normalize('Académie'), 'academie')
    assert.equal(normalize('Vidéo'), 'video')
    assert.equal(normalize('Cryptographie'), 'cryptographie')
  })

  test('strip ponctuation', () => {
    assert.equal(normalize('Aurora, ouvre le code !'), 'aurora ouvre le code')
  })

  test('collapse whitespace', () => {
    assert.equal(normalize('   ouvre   le   chat   '), 'ouvre le chat')
  })

  test('vide → vide', () => {
    assert.equal(normalize(''), '')
    assert.equal(normalize('   '), '')
  })
})

describe('parseNavigation', () => {
  test('"ouvre le chat" → conversation', () => {
    assert.equal(parseNavigation('ouvre le chat'), 'conversation')
  })

  test('"passe au code" → code', () => {
    assert.equal(parseNavigation('passe au code'), 'code')
  })

  test('"va dans la 3d" → 3d', () => {
    assert.equal(parseNavigation('va dans la 3d'), '3d')
  })

  test('"bascule vers cyber" → cyber', () => {
    assert.equal(parseNavigation('bascule vers cyber'), 'cyber')
  })

  test('"affiche academie" → learning', () => {
    assert.equal(parseNavigation('affiche academie'), 'learning')
  })

  test('"lance video" → video', () => {
    assert.equal(parseNavigation('lance video'), 'video')
  })

  test('"montre dessin" → drawing', () => {
    assert.equal(parseNavigation('montre dessin'), 'drawing')
  })

  test('"ouvre image" → image', () => {
    assert.equal(parseNavigation('ouvre image'), 'image')
  })

  test('"rejoins voix" → voice', () => {
    assert.equal(parseNavigation('rejoins voix'), 'voice')
  })

  test('sans verbe de navigation → null', () => {
    assert.equal(parseNavigation('je veux un chat'), null)
    assert.equal(parseNavigation('le code est cool'), null)
  })

  test('verbe sans cible → null', () => {
    assert.equal(parseNavigation('ouvre la porte'), null)
  })

  test('texte aléatoire → null', () => {
    assert.equal(parseNavigation('blah blah blah'), null)
    assert.equal(parseNavigation(''), null)
  })

  test('alias "forge" → code', () => {
    assert.equal(parseNavigation('ouvre la forge'), 'code')
  })

  test('alias "hunyuan" → 3d', () => {
    assert.equal(parseNavigation('lance hunyuan'), '3d')
  })

  test('alias "ctf" → cyber', () => {
    assert.equal(parseNavigation('passe au ctf'), 'cyber')
  })

  test('alias "quiz" → learning', () => {
    assert.equal(parseNavigation('demarre quiz'), 'learning')
  })
})
