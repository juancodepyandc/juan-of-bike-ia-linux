/**
 * Tests color tools.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  deltaE76,
  extractPalette,
  generateHarmony,
  hexToRgb,
  hslToRgb,
  rgbToHex,
  rgbToHsl,
  rgbToLab,
  wcagContrast,
} from '../services/drawingColorTools.ts'

describe('Conversions RGB ↔ HEX', () => {
  test('hex 6 chars → RGB', () => {
    const r = hexToRgb('#3aa4ff')
    assert.deepEqual(r, { r: 58, g: 164, b: 255 })
  })

  test('hex 3 chars → RGB', () => {
    const r = hexToRgb('#abc')
    assert.deepEqual(r, { r: 170, g: 187, b: 204 })
  })

  test('hex invalide → null', () => {
    assert.equal(hexToRgb('#xy'), null)
  })

  test('RGB → hex round-trip', () => {
    const c = { r: 58, g: 164, b: 255 }
    assert.equal(rgbToHex(c), '#3aa4ff')
  })

  test('clamp dans rgbToHex', () => {
    assert.equal(rgbToHex({ r: 300, g: -10, b: 128 }), '#ff0080')
  })
})

describe('RGB ↔ HSL', () => {
  test('rouge pur', () => {
    const hsl = rgbToHsl({ r: 255, g: 0, b: 0 })
    assert.ok(Math.abs(hsl.h - 0) < 1 || Math.abs(hsl.h - 360) < 1)
    assert.ok(Math.abs(hsl.s - 1) < 0.01)
    assert.ok(Math.abs(hsl.l - 0.5) < 0.01)
  })

  test('vert pur', () => {
    const hsl = rgbToHsl({ r: 0, g: 255, b: 0 })
    assert.ok(Math.abs(hsl.h - 120) < 1)
  })

  test('HSL → RGB round-trip approximé', () => {
    const orig = { r: 100, g: 150, b: 200 }
    const hsl = rgbToHsl(orig)
    const back = hslToRgb(hsl)
    assert.ok(Math.abs(back.r - 100) < 2)
    assert.ok(Math.abs(back.g - 150) < 2)
    assert.ok(Math.abs(back.b - 200) < 2)
  })

  test('gris → s = 0', () => {
    const hsl = rgbToHsl({ r: 128, g: 128, b: 128 })
    assert.equal(hsl.s, 0)
  })
})

describe('deltaE76', () => {
  test('même couleur → 0', () => {
    const r = deltaE76({ r: 100, g: 100, b: 100 }, { r: 100, g: 100, b: 100 })
    assert.ok(r < 0.5)
  })

  test('blanc vs noir → ΔE élevé', () => {
    const r = deltaE76({ r: 0, g: 0, b: 0 }, { r: 255, g: 255, b: 255 })
    assert.ok(r > 90, `ΔE ${r}`)
  })

  test('rouge vs orange : différence perceptible', () => {
    const r = deltaE76({ r: 255, g: 0, b: 0 }, { r: 255, g: 128, b: 0 })
    assert.ok(r > 20)
  })
})

describe('Harmonies', () => {
  test('complementary → 2 couleurs', () => {
    const p = generateHarmony('#3aa4ff', 'complementary')
    assert.equal(p.length, 2)
  })

  test('triadic → 3 couleurs', () => {
    const p = generateHarmony('#3aa4ff', 'triadic')
    assert.equal(p.length, 3)
  })

  test('tetradic → 4 couleurs', () => {
    const p = generateHarmony('#3aa4ff', 'tetradic')
    assert.equal(p.length, 4)
  })

  test('monochromatic → 3 luminosités', () => {
    const p = generateHarmony('#3aa4ff', 'monochromatic')
    assert.equal(p.length, 3)
    // 3 couleurs avec H similaire mais L différent
    const hsls = p.map((hex) => rgbToHsl(hexToRgb(hex)!))
    const ls = hsls.map((h) => h.l)
    assert.ok(Math.max(...ls) - Math.min(...ls) > 0.2)
  })
})

describe('extractPalette K-means', () => {
  test('cluster de 3 couleurs distinctes → 3 swatches', () => {
    const pixels = [
      ...Array.from({ length: 100 }, () => ({ r: 255, g: 0, b: 0 })),
      ...Array.from({ length: 50 }, () => ({ r: 0, g: 255, b: 0 })),
      ...Array.from({ length: 30 }, () => ({ r: 0, g: 0, b: 255 })),
    ]
    const palette = extractPalette(pixels, 3)
    assert.equal(palette.length, 3)
    // Rouge (le plus de pixels) doit être en tête.
    assert.ok(palette[0].weight > 0.4)
  })

  test('pixels uniformes → 1 swatch dominant', () => {
    const pixels = Array.from({ length: 200 }, () => ({ r: 100, g: 100, b: 100 }))
    const palette = extractPalette(pixels, 3)
    // Le top swatch concentre tous les pixels.
    assert.ok(palette[0].weight > 0.8)
  })

  test('liste vide → []', () => {
    const palette = extractPalette([], 5)
    assert.equal(palette.length, 0)
  })

  test('moins de pixels que k → retourne tous', () => {
    const pixels = [{ r: 1, g: 1, b: 1 }, { r: 2, g: 2, b: 2 }]
    const palette = extractPalette(pixels, 5)
    assert.equal(palette.length, 2)
  })
})

describe('WCAG contrast', () => {
  test('noir vs blanc → 21', () => {
    const r = wcagContrast({ r: 0, g: 0, b: 0 }, { r: 255, g: 255, b: 255 })
    assert.ok(Math.abs(r - 21) < 0.5)
  })

  test('même couleur → 1', () => {
    const r = wcagContrast({ r: 100, g: 100, b: 100 }, { r: 100, g: 100, b: 100 })
    assert.ok(Math.abs(r - 1) < 0.01)
  })

  test('contraste minimum AA pour normal text (4.5)', () => {
    // #767676 sur blanc = 4.54
    const r = wcagContrast({ r: 118, g: 118, b: 118 }, { r: 255, g: 255, b: 255 })
    assert.ok(r > 4.4 && r < 4.7, `contrast ${r}`)
  })
})

describe('rgbToLab', () => {
  test('blanc → L ≈ 100', () => {
    const lab = rgbToLab({ r: 255, g: 255, b: 255 })
    assert.ok(lab.L > 99)
  })

  test('noir → L ≈ 0', () => {
    const lab = rgbToLab({ r: 0, g: 0, b: 0 })
    assert.ok(lab.L < 1)
  })
})
