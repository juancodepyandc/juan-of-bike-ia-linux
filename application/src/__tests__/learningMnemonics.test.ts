/**
 * Tests pour le générateur de mnémotechniques.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  chooseStrategy,
  generateAcronymMnemonic,
  generateAuto,
  generateChunkingMnemonic,
  generateLociMnemonic,
  generatePhraseMnemonic,
  generateRimeMnemonic,
} from '../services/learning/mnemonicGenerator.ts'

describe('Acronyme', () => {
  test('planètes → MVTMSUPN (avec Pluton historique)', () => {
    const r = generateAcronymMnemonic(['Mercure', 'Vénus', 'Terre', 'Mars', 'Saturne', 'Uranus', 'Pluton', 'Neptune'])
    assert.match(r.text, /MVTMSUPN/i)
  })

  test('génère une phrase mnémo non vide', () => {
    const r = generateAcronymMnemonic(['Eau', 'Feu', 'Terre', 'Air'])
    assert.match(r.text, /EFTA/i)
    assert.ok(r.text.split('→')[1].trim().length > 5)
  })

  test('difficulty croît avec la longueur', () => {
    const easy = generateAcronymMnemonic(['A', 'B'])
    const hard = generateAcronymMnemonic(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'])
    assert.ok(hard.difficulty > easy.difficulty)
  })
})

describe('Phrase initiale', () => {
  test('génère une phrase utilisant les initiales', () => {
    const r = generatePhraseMnemonic(['Pomme', 'Banane', 'Cerise'])
    // Doit contenir des mots commençant par P, B, C.
    const words = r.text.split(/\s+/)
    const initials = words.map((w) => w[0]?.toLowerCase()).join('')
    assert.match(initials, /^p.*b.*c/i)
  })

  test('difficulty modéré', () => {
    const r = generatePhraseMnemonic(['Pomme', 'Banane'])
    assert.ok(r.difficulty >= 0.3 && r.difficulty <= 0.5)
  })
})

describe('Loci', () => {
  test('chaque item dans un emplacement différent', () => {
    const r = generateLociMnemonic(['Pendule', 'Ressort', 'Onde', 'Doppler'])
    const lines = r.text.split('\n')
    assert.equal(lines.length, 4)
    for (const line of lines) assert.match(line, /→/)
  })

  test('plus de 15 items → difficulty augmente', () => {
    const r = generateLociMnemonic(Array.from({ length: 20 }, (_, i) => `item${i}`))
    assert.ok(r.difficulty >= 0.5)
  })
})

describe('Chunking', () => {
  test('groupes de 4 par défaut', () => {
    const items = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
    const r = generateChunkingMnemonic(items)
    const lines = r.text.split('\n')
    // 9 items / 4 = 3 groupes (4 + 4 + 1)
    assert.equal(lines.length, 3)
  })

  test('groupSize personnalisable', () => {
    const items = Array.from({ length: 10 }, (_, i) => `i${i}`)
    const r = generateChunkingMnemonic(items, 3)
    // 10/3 = 4 groupes
    assert.equal(r.text.split('\n').length, 4)
  })
})

describe('Rime', () => {
  test('mot en -tion → rime trouvée', () => {
    const r = generateRimeMnemonic('attention')
    assert.match(r.text, /attention|ambition|passion/i)
  })

  test('mot en -age → rime trouvée', () => {
    const r = generateRimeMnemonic('image')
    assert.match(r.text, /sage|page|voyage/i)
  })

  test('mot sans rime connue → fallback', () => {
    const r = generateRimeMnemonic('chrysope')
    assert.ok(r.text.includes('rime'))
  })
})

describe('Auto strategy', () => {
  test('1 item → rime', () => {
    assert.equal(chooseStrategy(['attention']), 'rime')
  })

  test('3 items voyellés → acronyme', () => {
    assert.equal(chooseStrategy(['Eau', 'Feu', 'Air']), 'acronyme')
  })

  test('initiales consonnes-only → phrase', () => {
    // BCD → pas prononçable
    assert.equal(chooseStrategy(['Banane', 'Carotte', 'Drupe']), 'phrase-initiale')
  })

  test('liste > 7 → chunking', () => {
    const items = Array.from({ length: 10 }, (_, i) => `i${i}`)
    assert.equal(chooseStrategy(items), 'chunking')
  })

  test('generateAuto dispatch correctement', () => {
    const r = generateAuto(['attention'])
    assert.equal(r.strategy, 'rime')
  })

  test('generateAuto sur 10 items produit chunking', () => {
    const r = generateAuto(Array.from({ length: 12 }, (_, i) => `t${i}`))
    assert.equal(r.strategy, 'chunking')
  })
})
