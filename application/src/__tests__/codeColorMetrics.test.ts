import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  deltaE76,
  extractCssColors,
  hasPerceptualColorMatch,
  parseCssColor,
} from '../services/codeColorMetrics.ts'

describe('codeColorMetrics', () => {
  test('parse hex, rgb et oklch en Lab', () => {
    const hex = parseCssColor('#f40009')
    const rgb = parseCssColor('rgb(244, 0, 9)')
    const oklch = parseCssColor('oklch(0.62 0.26 29)')

    assert.ok(hex)
    assert.ok(rgb)
    assert.ok(oklch)
    assert.equal(hex.rgb.r, 244)
    assert.equal(rgb.rgb.g, 0)
    assert.equal(Number.isFinite(oklch.lab.l), true)
  })

  test('deltaE accepte une couleur brand proche sans exiger le hex litteral', () => {
    assert.equal(hasPerceptualColorMatch('.cta{background:#f51a20}', '#F40009'), true)
    assert.equal(hasPerceptualColorMatch('.cta{background:rgb(245 26 32)}', '#F40009'), true)
  })

  test('deltaE accepte une cible oklch sans prefixe hex artificiel', () => {
    assert.equal(
      hasPerceptualColorMatch(':root{--bg:oklch(0.13 0.012 252)}', 'oklch(0.13 0.012 252)'),
      true,
    )
  })

  test('deltaE rejette une couleur eloignee', () => {
    assert.equal(hasPerceptualColorMatch('.cta{background:#2563eb}', '#F40009'), false)
  })

  test('deduplique les couleurs CSS extraites', () => {
    const colors = extractCssColors('a{color:#f40009;background:rgb(244 0 9)} b{color:#2563eb}')
    const delta = deltaE76(colors[0].lab, colors[1].lab)

    assert.equal(colors.length, 2)
    assert.ok(delta > 40)
  })
})
