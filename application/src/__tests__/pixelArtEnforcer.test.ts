import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  PIXEL_ART_DEFAULTS,
  parsePixelArtOptions,
  quantizeToPixelGrid,
  upscaleNearest,
} from '../utils/pixelArtEnforcer.ts'

function distinctColors(data: Uint8ClampedArray): Set<string> {
  const out = new Set<string>()
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] === 0) continue
    out.add(`${data[i]},${data[i + 1]},${data[i + 2]}`)
  }
  return out
}

/** Image synthetique : degrade RGB continu (beaucoup de couleurs). */
function makeGradient(w: number, h: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(w * h * 4)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      data[i] = Math.round((x / (w - 1)) * 255)
      data[i + 1] = Math.round((y / (h - 1)) * 255)
      data[i + 2] = Math.round(((x + y) / (w + h - 2)) * 255)
      data[i + 3] = 255
    }
  }
  return data
}

describe('parsePixelArtOptions', () => {
  test('defaults sans indication', () => {
    assert.deepEqual(parsePixelArtOptions('un chevalier'), PIXEL_ART_DEFAULTS)
  })

  test('"32x32 sprite" force la grille 32', () => {
    assert.equal(parsePixelArtOptions('sprite chevalier 32x32').gridWidth, 32)
  })

  test('"8 bit" reduit la palette a 8', () => {
    assert.equal(parsePixelArtOptions('paysage 8 bit').paletteSize, 8)
  })

  test('"16 bit" palette 32', () => {
    assert.equal(parsePixelArtOptions('rpg 16-bit').paletteSize, 32)
  })

  test('"palette 4" explicite gagne', () => {
    assert.equal(parsePixelArtOptions('gameboy palette 4').paletteSize, 4)
  })

  test('clamp grille minuscule a 16', () => {
    assert.equal(parsePixelArtOptions('icone 4x4').gridWidth, 16)
  })
})

describe('quantizeToPixelGrid', () => {
  test('reduit un degrade continu a la palette demandee', () => {
    const src = makeGradient(64, 64)
    assert.ok(distinctColors(src).size > 500, 'le degrade source doit etre riche')

    const grid = quantizeToPixelGrid(src, 64, 64, { gridWidth: 16, paletteSize: 4 })
    assert.equal(grid.width, 16)
    assert.equal(grid.height, 16)
    const colors = distinctColors(grid.data)
    assert.ok(colors.size <= 4, `palette depassee: ${colors.size} couleurs`)
    assert.ok(grid.palette.length <= 4)
  })

  test('alpha binarise pour des bords nets', () => {
    const src = makeGradient(32, 32)
    // bande semi-transparente
    for (let i = 0; i < 32 * 8 * 4; i += 4) src[i + 3] = 90
    const grid = quantizeToPixelGrid(src, 32, 32, { gridWidth: 16, paletteSize: 8 })
    for (let i = 3; i < grid.data.length; i += 4) {
      assert.ok(grid.data[i] === 0 || grid.data[i] === 255)
    }
  })

  test('ratio non carre preserve', () => {
    const src = makeGradient(64, 32)
    const grid = quantizeToPixelGrid(src, 64, 32, { gridWidth: 32, paletteSize: 8 })
    assert.equal(grid.width, 32)
    assert.equal(grid.height, 16)
  })
})

describe('upscaleNearest', () => {
  test('chaque cellule devient un bloc uniforme', () => {
    const src = makeGradient(8, 8)
    const grid = quantizeToPixelGrid(src, 8, 8, { gridWidth: 16, paletteSize: 4 })
    // gridWidth clampe a srcW=8 → grille 8x8
    assert.equal(grid.width, 8)

    const up = upscaleNearest(grid, 32, 32)
    // bloc (0,0) : les 4x4 premiers pixels identiques
    const first = [up[0], up[1], up[2], up[3]]
    for (let y = 0; y < 4; y++) {
      for (let x = 0; x < 4; x++) {
        const o = (y * 32 + x) * 4
        assert.deepEqual([up[o], up[o + 1], up[o + 2], up[o + 3]], first)
      }
    }
    // pas plus de couleurs apres upscale
    assert.ok(distinctColors(up).size <= distinctColors(grid.data).size)
  })
})
