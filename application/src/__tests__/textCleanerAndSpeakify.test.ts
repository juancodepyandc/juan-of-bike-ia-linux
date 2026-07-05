/**
 * Tests groupés pour utils/textCleaner + utils/speakify + utils/streak.
 * Trois petits utils purs liés au pipeline TTS et stats.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { cleanTextForVoice } from '../utils/textCleaner.ts'
import { speakify } from '../utils/speakify.ts'
import { computeStreak } from '../utils/streak.ts'

describe('cleanTextForVoice — markdown', () => {
  test('text vide → ""', () => {
    assert.equal(cleanTextForVoice(''), '')
  })

  test('code fences ``` retirés', () => {
    const r = cleanTextForVoice('Bonjour\n```js\nconst x = 1;\n```\nFin.')
    assert.ok(!r.includes('```'))
    assert.ok(!r.includes('const x'))
  })

  test('inline code `x` retiré', () => {
    const r = cleanTextForVoice('Voici `function()` à appeler')
    assert.ok(!r.includes('`'))
  })

  test('headings # retirés', () => {
    const r = cleanTextForVoice('# Titre\n## Sous-titre\nTexte')
    assert.ok(!r.includes('#'))
    assert.ok(r.includes('Titre'))
  })

  test('bold ** retirés mais texte préservé', () => {
    const r = cleanTextForVoice('Voici **important** dans la phrase')
    assert.ok(r.includes('important'))
    assert.ok(!r.includes('**'))
  })

  test('liens [text](url) → text seul', () => {
    const r = cleanTextForVoice('Voir [docs](https://example.com)')
    assert.ok(r.includes('docs'))
    assert.ok(!r.includes('https://'))
  })

  test('<think> tags supprimés', () => {
    const r = cleanTextForVoice('Hello <think>internal thought</think> world')
    assert.ok(!r.includes('internal thought'))
    assert.ok(r.includes('Hello'))
    assert.ok(r.includes('world'))
  })
})

describe('cleanTextForVoice — LaTeX', () => {
  test('\\frac{a}{b} → "a sur b"', () => {
    const r = cleanTextForVoice('\\frac{1}{2}')
    assert.ok(r.includes('sur'))
  })

  test('\\sqrt{x} → racine de', () => {
    const r = cleanTextForVoice('\\sqrt{2}')
    assert.ok(r.toLowerCase().includes('racine'))
  })

  test('\\sum → somme', () => {
    const r = cleanTextForVoice('\\sum x = 1')
    assert.ok(r.includes('somme'))
  })

  test('\\infty → l\'infini', () => {
    const r = cleanTextForVoice('lim → \\infty')
    assert.ok(r.includes("l'infini"))
  })

  test('\\alpha grec → alpha', () => {
    const r = cleanTextForVoice('\\alpha + \\beta')
    assert.ok(r.includes('alpha'))
    assert.ok(r.includes('beta'))
  })
})

describe('cleanTextForVoice — symbols Unicode', () => {
  test('≤ → "inferieur ou egal a"', () => {
    const r = cleanTextForVoice('x ≤ 5')
    assert.ok(r.includes('inferieur ou egal'))
  })

  test('≥ → "superieur ou egal a"', () => {
    const r = cleanTextForVoice('x ≥ 0')
    assert.ok(r.includes('superieur ou egal'))
  })

  test('≠ → "different de"', () => {
    const r = cleanTextForVoice('a ≠ b')
    assert.ok(r.includes('different'))
  })

  test('² → "au carre"', () => {
    const r = cleanTextForVoice('x²')
    assert.ok(r.includes('au carre'))
  })

  test('³ → "au cube"', () => {
    const r = cleanTextForVoice('x³')
    assert.ok(r.includes('au cube'))
  })

  test('∞ → l\'infini', () => {
    const r = cleanTextForVoice('vers ∞')
    assert.ok(r.includes("l'infini"))
  })

  test('ℝ → R', () => {
    const r = cleanTextForVoice('dans ℝ')
    assert.ok(r.includes('R'))
  })
})

describe('cleanTextForVoice — formules', () => {
  test('"E = mc²" → "E egale m c au carre"', () => {
    const r = cleanTextForVoice('E = mc²')
    assert.ok(r.includes('au carre'))
    assert.ok(r.includes('egale'))
  })

  test('sin/cos/tan → mots complets', () => {
    const r = cleanTextForVoice('sin(x) + cos(x) = tan(x)')
    assert.ok(r.includes('sinus'))
    assert.ok(r.includes('cosinus'))
    assert.ok(r.includes('tangente'))
  })

  test('ln → "logarithme neperien"', () => {
    const r = cleanTextForVoice('ln(x)')
    assert.ok(r.includes('logarithme neperien'))
  })

  test('emojis retirés', () => {
    const r = cleanTextForVoice('Salut 🚀 le monde 🌍')
    assert.ok(!/[\u{1F000}-\u{1FFFF}]/u.test(r))
  })

  test('monnaie € → euros', () => {
    const r = cleanTextForVoice('5€ par jour')
    assert.ok(r.includes('euros'))
  })
})

describe('speakify — wrappers similaires', () => {
  test('text vide → ""', () => {
    assert.equal(speakify(''), '')
  })

  test('LaTeX $$ ... $$ converti', () => {
    const r = speakify('Formule : $$\\frac{a}{b}$$')
    assert.ok(!r.includes('$$'))
    assert.ok(r.toLowerCase().includes('sur'))
  })

  test('LaTeX $ ... $ converti', () => {
    const r = speakify('inline $x^2$ math')
    assert.ok(!r.includes('$'))
    assert.ok(r.toLowerCase().includes('carré') || r.toLowerCase().includes('puissance'))
  })

  test('grec lettre α → alpha', () => {
    const r = speakify('θ = α + β')
    assert.ok(r.includes('thêta'))
    assert.ok(r.includes('alpha'))
    assert.ok(r.includes('bêta'))
  })

  test('symbole ∑ → somme de', () => {
    const r = speakify('∑ x_i')
    assert.ok(r.includes('somme'))
  })

  test('formule "Fe2O3" → décomposition partielle', () => {
    // Le regex \b([A-Z][a-z]?)(\d+) matche Fe2 → Fe 2 + reste O3 → O 3
    const r = speakify('Rouille = Fe2O3')
    assert.ok(r.includes('Fe 2') || r.includes('O 3'))
  })

  test('abréviation "av. J.-C." → avant Jésus-Christ', () => {
    const r = speakify('En 500 av. J.-C.')
    assert.ok(r.includes('avant Jésus-Christ'))
  })

  test('unités km/h → kilomètres par heure', () => {
    const r = speakify('100 km/h')
    assert.ok(r.includes('kilomètres par heure'))
  })

  test('% → "pour cent"', () => {
    const r = speakify('50%')
    assert.ok(r.includes('pour cent'))
  })

  test('°C → "degrés Celsius"', () => {
    const r = speakify('25 °C')
    assert.ok(r.includes('Celsius'))
  })

  test('Math step "c² = 25 + 49 = 74" → pauses', () => {
    const r = speakify('c² = 25 + 49 = 74')
    // chained = should become "égale ... soit égal à ..."
    assert.ok(r.includes('égale') || r.includes('soit égal'))
  })

  test('strip markdown links', () => {
    const r = speakify('Voir [doc](https://x.com) ici')
    assert.ok(r.includes('doc'))
    assert.ok(!r.includes('https'))
  })

  test('connecteur "Donc X" → "Donc, X"', () => {
    const r = speakify('Hello. Donc x = 5.')
    assert.ok(r.includes('Donc,'))
  })
})

describe('computeStreak', () => {
  test('liste vide → 0/0', () => {
    assert.deepEqual(computeStreak([]), { current: 0, longest: 0 })
  })

  test('liste avec nulls/undefined → 0/0', () => {
    assert.deepEqual(computeStreak([null, undefined, NaN as any]), { current: 0, longest: 0 })
  })

  test('un seul jour aujourd hui → 1/1', () => {
    const r = computeStreak([Date.now()])
    assert.equal(r.current, 1)
    assert.equal(r.longest, 1)
  })

  test('plusieurs runs même jour → 1 jour', () => {
    const now = Date.now()
    const r = computeStreak([now, now + 1000, now + 2000])
    assert.equal(r.current, 1)
  })

  test('2 jours consécutifs aujourd hui + hier → current 2', () => {
    const now = Date.now()
    const yesterday = now - 24 * 3600 * 1000
    const r = computeStreak([now, yesterday])
    assert.equal(r.current, 2)
    assert.equal(r.longest, 2)
  })

  test('streak interrompu → longest enregistré', () => {
    const now = Date.now()
    const oneWeekAgo = now - 7 * 24 * 3600 * 1000
    const sixDaysAgo = now - 6 * 24 * 3600 * 1000
    const fiveDaysAgo = now - 5 * 24 * 3600 * 1000
    const r = computeStreak([oneWeekAgo, sixDaysAgo, fiveDaysAgo, now])
    // 3 jours consécutifs avant → longest 3
    assert.ok(r.longest >= 3)
    // aujourd'hui seul actif → current 1
    assert.equal(r.current, 1)
  })

  test('current >= longest impossible (longest >= current par construction)', () => {
    const now = Date.now()
    const days = Array.from({ length: 5 }, (_, i) => now - i * 24 * 3600 * 1000)
    const r = computeStreak(days)
    assert.ok(r.longest >= r.current)
  })
})
