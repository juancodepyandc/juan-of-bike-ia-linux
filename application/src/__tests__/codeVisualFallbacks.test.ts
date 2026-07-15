import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { buildAuroraInlineSvgDataUri } from '../services/codeVisualFallbacks.ts'

describe('buildAuroraInlineSvgDataUri', () => {
  test('produit un data URI SVG deterministe', () => {
    const first = buildAuroraInlineSvgDataUri('hero product', { width: 1200, height: 800 })
    const second = buildAuroraInlineSvgDataUri('hero product', { width: 1200, height: 800 })

    assert.equal(first, second)
    assert.ok(first.startsWith('data:image/svg+xml;utf8,'))
    assert.ok(first.includes('%3Csvg'))
  })

  test('encode les caracteres dangereux pour url(...) CSS', () => {
    const uri = buildAuroraInlineSvgDataUri('produit (premium) detail', { width: 1600, height: 900 })

    assert.ok(!/[()'"]/.test(uri))
    assert.ok(uri.includes('%28') || uri.includes('%29'))
  })
})
