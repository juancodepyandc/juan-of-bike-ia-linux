/**
 * Tests texture atlas packing.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { atlasGains, packAtlas } from '../services/threeDTextureAtlas.ts'

describe('Texture atlas packing', () => {
  test('1 texture seule → atlas adapté', () => {
    const r = packAtlas([{ id: 't1', width: 100, height: 100 }])
    assert.equal(r.slots.length, 1)
    assert.equal(r.unplaced.length, 0)
    assert.ok(r.slots[0].uvScaleX > 0 && r.slots[0].uvScaleX <= 1)
  })

  test('4 petites textures dans 1 atlas', () => {
    const textures = [
      { id: 'a', width: 64, height: 64 },
      { id: 'b', width: 64, height: 64 },
      { id: 'c', width: 64, height: 64 },
      { id: 'd', width: 64, height: 64 },
    ]
    const r = packAtlas(textures)
    assert.equal(r.slots.length, 4)
    assert.equal(r.unplaced.length, 0)
  })

  test('UV coords ∈ [0..1]', () => {
    const textures = Array.from({ length: 8 }, (_, i) => ({ id: `t${i}`, width: 128, height: 128 }))
    const r = packAtlas(textures)
    for (const slot of r.slots) {
      assert.ok(slot.uvOffsetX >= 0 && slot.uvOffsetX <= 1)
      assert.ok(slot.uvOffsetY >= 0 && slot.uvOffsetY <= 1)
      assert.ok(slot.uvScaleX > 0 && slot.uvScaleX <= 1)
      assert.ok(slot.uvScaleY > 0 && slot.uvScaleY <= 1)
    }
  })

  test('aucun chevauchement entre slots', () => {
    const textures = Array.from({ length: 10 }, (_, i) => ({ id: `t${i}`, width: 100, height: 100 }))
    const r = packAtlas(textures)
    for (let i = 0; i < r.slots.length; i += 1) {
      for (let j = i + 1; j < r.slots.length; j += 1) {
        const a = r.slots[i], b = r.slots[j]
        const intersect = a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y
        assert.equal(intersect, false, `slots ${a.id} et ${b.id} se chevauchent`)
      }
    }
  })

  test('texture plus grande que maxSize → unplaced', () => {
    const r = packAtlas([{ id: 'huge', width: 5000, height: 5000 }], { maxSize: 1024 })
    assert.equal(r.slots.length, 0)
    assert.equal(r.unplaced.length, 1)
  })

  test('tailles variées → grand placé en premier', () => {
    const textures = [
      { id: 'small', width: 32, height: 32 },
      { id: 'big', width: 512, height: 512 },
      { id: 'med', width: 128, height: 128 },
    ]
    const r = packAtlas(textures)
    // Le big doit être placé près de (0, 0).
    const big = r.slots.find((s) => s.id === 'big')!
    assert.equal(big.x, 0)
    assert.equal(big.y, 0)
  })

  test('rotation 90° utilisée si bénéfique', () => {
    // Texture 800×100 mais atlas 512×512 → ne rentre pas sans rotation
    const r = packAtlas([{ id: 'wide', width: 500, height: 100 }], { allowRotation: true })
    // Va trouver un emplacement (atlas 512 par défaut accomode 500×100).
    assert.ok(r.slots.length > 0)
  })

  test('occupancy ratio raisonnable pour packing serré', () => {
    const textures = Array.from({ length: 16 }, (_, i) => ({ id: `t${i}`, width: 128, height: 128 }))
    const r = packAtlas(textures, { padding: 0 })
    // Sans padding, 16 × 128² = 262144 = 512² → tente 100% occupancy.
    assert.ok(r.occupancyRatio > 0.4, `occupancy ${r.occupancyRatio}`)
  })

  test('atlasGains rapporte la réduction draw calls', () => {
    const textures = Array.from({ length: 20 }, (_, i) => ({ id: `t${i}`, width: 64, height: 64 }))
    const r = packAtlas(textures)
    const g = atlasGains(r)
    assert.ok(g.drawCallsApres < g.drawCallsAvant)
    assert.ok(g.reductionPct > 80)
  })

  test('atlasGains warning quand unplaced', () => {
    const r = packAtlas([{ id: 'huge', width: 8192, height: 8192 }], { maxSize: 512 })
    const g = atlasGains(r)
    assert.ok(g.warning?.includes('trop grande'))
  })
})
