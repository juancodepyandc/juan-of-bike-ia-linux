/**
 * Tests aspect recommender.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  bestAspectRatio,
  detectBrandingPreset,
  recommendAspectRatio,
} from '../services/imageAspectRecommender.ts'

describe('Aspect recommender', () => {
  test('portrait → 2:3', () => {
    const r = bestAspectRatio('portrait dramatique d\'un samouraï')
    assert.equal(r.ratio, '2:3')
  })

  test('paysage → 3:2', () => {
    const r = bestAspectRatio('paysage de montagne avec horizon visible')
    assert.equal(r.ratio, '3:2')
  })

  test('panoramique → 21:9', () => {
    const r = bestAspectRatio('vue panoramique cinemascope')
    assert.equal(r.ratio, '21:9')
  })

  test('logo / icône → 1:1', () => {
    const r = bestAspectRatio('logo carré pour startup')
    assert.equal(r.ratio, '1:1')
  })

  test('TikTok mentionné → 9:16', () => {
    const r = bestAspectRatio('vidéo TikTok hype')
    assert.equal(r.ratio, '9:16')
  })

  test('YouTube mentionné → 16:9', () => {
    const r = bestAspectRatio('intro YouTube pour ma chaîne')
    assert.equal(r.ratio, '16:9')
  })

  test('--ar explicit override', () => {
    const r = bestAspectRatio('portrait d\'un chat --ar 16:9')
    assert.equal(r.ratio, '16:9')
  })

  test('rien spécifique → fallback 1:1', () => {
    const r = bestAspectRatio('un beau dessin')
    assert.equal(r.ratio, '1:1')
  })

  test('confidence ∈ [0..1]', () => {
    const rs = recommendAspectRatio('paysage cinemascope panoramique')
    for (const r of rs) {
      assert.ok(r.confidence >= 0 && r.confidence <= 1)
    }
  })

  test('width / height SDXL standards (multiples de 64)', () => {
    const r = bestAspectRatio('portrait')
    assert.equal(r.width % 64, 0)
    assert.equal(r.height % 64, 0)
  })

  test('alternatives classées par confidence desc', () => {
    const rs = recommendAspectRatio('portrait paysage panoramique')
    for (let i = 1; i < rs.length; i += 1) {
      assert.ok(rs[i].confidence <= rs[i - 1].confidence)
    }
  })
})

describe('Branding presets', () => {
  test('LinkedIn banner détecté', () => {
    const p = detectBrandingPreset('LinkedIn banner pour mon profil')
    assert.equal(p?.name, 'LinkedIn banner')
    assert.equal(p?.officialWidth, 1584)
  })

  test('YouTube thumbnail détecté', () => {
    const p = detectBrandingPreset('thumbnail YouTube pour ma vidéo')
    assert.equal(p?.officialWidth, 1280)
    assert.equal(p?.officialHeight, 720)
  })

  test('Album cover détecté → carré 3000', () => {
    const p = detectBrandingPreset('album cover pour mon EP')
    assert.equal(p?.officialWidth, 3000)
    assert.equal(p?.ratio, '1:1')
  })

  test('rien matché → null', () => {
    const p = detectBrandingPreset('image quelconque')
    assert.equal(p, null)
  })
})
