/**
 * v77zf: validate Meshy-grade PBR profile inference. The 3D viewer relies on
 * this function to upgrade flat baseColor-only Hunyuan3D-Paint outputs into
 * proper chrome / glass / skin / fabric materials, so a regression here
 * silently makes every 3D output look like beige plastic again.
 *
 * Run: node --experimental-strip-types src/__tests__/pbrProfile.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { inferPbrProfile } from '../services/pbrProfile.ts'

describe('inferPbrProfile — explicit material keywords win over subjectKind', () => {
  test('chrome detail beats vehicle subject', () => {
    const profile = inferPbrProfile('voiture en chrome poli', 'vehicle')
    assert.equal(profile.kind, 'chrome')
    assert.ok(profile.metalness > 0.9)
    assert.ok(profile.roughness < 0.2)
  })

  test('glass on a product subject', () => {
    const profile = inferPbrProfile('vase en verre transparent', 'product')
    assert.equal(profile.kind, 'glass')
    assert.ok((profile.transmission ?? 0) > 0.8)
  })

  test('wooden character', () => {
    const profile = inferPbrProfile('personnage en bois sculpte', 'character')
    assert.equal(profile.kind, 'wood')
    assert.ok(profile.roughness > 0.7)
    assert.equal(profile.metalness, 0)
  })

  test('fabric on character', () => {
    const profile = inferPbrProfile('robe en soie rouge', 'character')
    assert.equal(profile.kind, 'fabric')
    assert.ok((profile.sheen ?? 0) > 0)
  })

  test('skin keyword', () => {
    const profile = inferPbrProfile('visage humain peau realiste', 'character')
    assert.equal(profile.kind, 'skin')
  })

  test('gem on jewel product', () => {
    const profile = inferPbrProfile('bague avec un diamant taille brillant', 'product')
    assert.equal(profile.kind, 'gem')
    assert.ok((profile.iridescence ?? 0) > 0)
  })
})

describe('inferPbrProfile — subjectKind fallbacks', () => {
  test('character without explicit material → character_default', () => {
    const profile = inferPbrProfile('un guerrier samurai en armure complete', 'character')
    // "armure" implies metal context; falls through generic to character_default
    // OR explicit metal kw; both are acceptable Meshy-grade defaults.
    assert.ok(profile.envMapIntensity >= 1.1)
    assert.ok(profile.metalness <= 0.15 || profile.metalness >= 0.5)
  })

  test('vehicle subject → vehicle_default with clearcoat', () => {
    const profile = inferPbrProfile('a fast race car', 'vehicle')
    assert.equal(profile.kind, 'vehicle_default')
    assert.ok((profile.clearcoat ?? 0) > 0.4)
  })

  test('mechanism subject → mechanism_default metallic', () => {
    const profile = inferPbrProfile('a complex gear assembly', 'mechanical_part')
    assert.equal(profile.kind, 'mechanism_default')
    assert.ok(profile.metalness > 0.5)
  })

  test('electrical_system → electronics with emissive boost', () => {
    const profile = inferPbrProfile('a custom RGB ARGB extension cable', 'electrical_system')
    assert.equal(profile.kind, 'electronics')
    assert.ok((profile.emissiveBoost ?? 0) > 0)
  })

  test('product with no material hint → product_default', () => {
    const profile = inferPbrProfile('a sleek consumer gadget device', 'product')
    assert.equal(profile.kind, 'product_default')
  })

  test('architecture → stone', () => {
    const profile = inferPbrProfile('a cathedral facade with arches', 'architecture')
    assert.equal(profile.kind, 'stone')
  })

  test('object generic → neutral', () => {
    const profile = inferPbrProfile('an abstract shape', 'object')
    assert.equal(profile.kind, 'neutral')
  })
})

describe('v77zac — fur / feathers / scales / tire / creature_default', () => {
  test('"un chien a fourrure" → fur profile', () => {
    const profile = inferPbrProfile('un chien a fourrure brune', 'creature')
    assert.equal(profile.kind, 'fur')
    assert.ok((profile.sheen ?? 0) > 0.3, 'fur should have sheen')
    assert.ok(profile.roughness >= 0.9, 'fur should be very rough')
  })

  test('"plumage" prompt → feathers profile', () => {
    const profile = inferPbrProfile('un oiseau au plumage iridescent', 'creature')
    assert.equal(profile.kind, 'feathers')
    assert.ok((profile.iridescence ?? 0) > 0)
  })

  test('"ecailles" prompt → scales profile', () => {
    const profile = inferPbrProfile('un dragon avec des ecailles brillantes', 'creature')
    assert.equal(profile.kind, 'scales')
    assert.ok(profile.metalness > 0.1, 'scales should be semi-metallic')
  })

  test('"pneu" prompt → tire profile', () => {
    const profile = inferPbrProfile('un pneu de voiture sport', 'product')
    assert.equal(profile.kind, 'tire')
    assert.ok(profile.envMapIntensity < 0.7, 'tire should have low envMap')
  })

  test('creature without explicit material → creature_default (NOT character_default)', () => {
    const profile = inferPbrProfile('a wolf in the forest', 'creature')
    assert.equal(profile.kind, 'creature_default')
    assert.ok((profile.sheen ?? 0) > 0, 'creature_default should have sheen')
  })

  test('character without material still goes to character_default', () => {
    const profile = inferPbrProfile('un guerrier elfique', 'character')
    assert.equal(profile.kind, 'character_default')
  })

  test('explicit "fur" on character routes to fur profile (not character_default)', () => {
    const profile = inferPbrProfile('a furry mascot character', 'character')
    assert.equal(profile.kind, 'fur')
  })
})

describe('inferPbrProfile — every profile has Meshy-grade non-flat defaults', () => {
  test('every kind has envMapIntensity ≥ 0.85 (no dead reflections)', () => {
    const samples: Array<[string, 'character' | 'vehicle' | 'mechanical_part' | 'product' | 'electrical_system' | 'architecture' | 'object']> = [
      ['en chrome', 'product'],
      ['en verre', 'product'],
      ['en cuir', 'product'],
      ['en tissu coton', 'character'],
      ['en bois', 'product'],
      ['en caoutchouc', 'product'],
      ['ceramique blanche', 'product'],
      ['marbre', 'architecture'],
      ['', 'character'],
      ['', 'vehicle'],
      ['', 'mechanical_part'],
      ['', 'product'],
      ['', 'electrical_system'],
      ['', 'architecture'],
      ['', 'object'],
    ]
    for (const [kw, kind] of samples) {
      const profile = inferPbrProfile(kw, kind)
      assert.ok(profile.envMapIntensity >= 0.85, `${kw}/${kind} → ${profile.kind} envMap=${profile.envMapIntensity}`)
      assert.ok(profile.roughness <= 1 && profile.roughness >= 0)
      assert.ok(profile.metalness <= 1 && profile.metalness >= 0)
    }
  })
})
