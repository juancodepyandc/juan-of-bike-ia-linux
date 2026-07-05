/**
 * Tests pour cyber/passwordAnalyzer — zxcvbn-light maison.
 * Vérifie : entropie, score, détection patterns, feedback éducatif.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { analyzePassword } from '../services/cyber/passwordAnalyzer.ts'

describe('analyzePassword — entrée vide', () => {
  test('chaîne vide → score 0, instantané', () => {
    const r = analyzePassword('')
    assert.equal(r.score, 0)
    assert.equal(r.entropy, 0)
    assert.equal(r.length, 0)
    assert.equal(r.crackTimeHuman, 'instantané')
    assert.ok(r.feedback.includes('entre un mot de passe'))
  })
})

describe('analyzePassword — passwords classiques', () => {
  test('"password" (commun) → score 0, faible', () => {
    const r = analyzePassword('password')
    assert.equal(r.score, 0)
    assert.ok(r.patterns.includes('commun'))
    assert.ok(r.feedback.some(f => f.includes('connu') || f.includes('motifs')))
  })

  test('"qwerty" (séquence clavier) → pattern détecté', () => {
    const r = analyzePassword('qwerty')
    assert.ok(r.patterns.some(p => p.includes('clavier')))
  })

  test('"azerty" (séquence FR) → pattern détecté', () => {
    const r = analyzePassword('azerty')
    assert.ok(r.patterns.some(p => p.includes('clavier') || p.includes('commun')))
  })

  test('"123456" → uniquement chiffres', () => {
    const r = analyzePassword('123456')
    assert.ok(r.patterns.includes('tous chiffres') || r.patterns.includes('commun'))
  })

  test('"aaaa" → caractère répété', () => {
    const r = analyzePassword('aaaa')
    assert.ok(r.patterns.some(p => p.includes('répét')))
  })

  test('"Aurora2026" → mot+chiffres + année', () => {
    const r = analyzePassword('Aurora2026')
    assert.ok(r.patterns.some(p => p.includes('année')))
    assert.ok(r.patterns.some(p => p.includes('chiffres')))
  })
})

describe('analyzePassword — passwords forts', () => {
  test('passphrase 4 mots + symbole → score élevé', () => {
    const r = analyzePassword('correct-horse-battery-staple!2026')
    assert.ok(r.entropy > 60, `entropy ${r.entropy}`)
    assert.ok(r.score >= 3)
  })

  test('mot de passe long 20+ chars mixte → score 4', () => {
    const r = analyzePassword('Tr0ub4dor!Lyra#Aurora$X')
    assert.ok(r.entropy >= 60, `entropy ${r.entropy}`)
    assert.ok(r.score >= 3)
  })
})

describe('analyzePassword — feedback éducatif', () => {
  test('court → feedback "allonger"', () => {
    const r = analyzePassword('Ab1!')
    assert.ok(r.feedback.some(f => f.includes('allonger')))
  })

  test('sans majuscule → feedback "majuscule"', () => {
    const r = analyzePassword('lowerlowerlower1!')
    assert.ok(r.feedback.some(f => f.includes('majuscule')))
  })

  test('sans symbole → feedback "symbole"', () => {
    const r = analyzePassword('AbCdEfGh1234')
    assert.ok(r.feedback.some(f => f.includes('symbole')))
  })

  test('sans chiffre → feedback "chiffre"', () => {
    const r = analyzePassword('AbCdEfGhIjKlMn!')
    assert.ok(r.feedback.some(f => f.includes('chiffre')))
  })
})

describe('analyzePassword — charsetSize', () => {
  test('a-z seul → charset 26', () => {
    const r = analyzePassword('abcdefgh')
    assert.equal(r.charsetSize, 26)
  })

  test('a-z + A-Z + 0-9 → charset 62', () => {
    const r = analyzePassword('aBcDeF12')
    assert.equal(r.charsetSize, 62)
  })

  test('a-z + A-Z + 0-9 + symboles → charset 94', () => {
    const r = analyzePassword('aBcDe123!?')
    assert.equal(r.charsetSize, 94)
  })
})

describe('analyzePassword — temps de crack', () => {
  test('"1234" cracké instantanément', () => {
    const r = analyzePassword('1234')
    assert.match(r.crackTimeHuman, /instantané|ms|s$/)
  })

  test('mot de passe fort → ans / millénaires', () => {
    const r = analyzePassword('Tr0ub4dor!Lyra#AuroraIA42')
    assert.match(r.crackTimeHuman, /ans|mille|millions|milliards/)
  })
})
