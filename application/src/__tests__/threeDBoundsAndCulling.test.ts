/**
 * Tests bounds + culling.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  aabbCenter,
  aabbFromPoints,
  aabbIntersect,
  aabbInFrustum,
  aabbUnion,
  aabbVolume,
  frustumFromMatrix,
  pointInFrustum,
  rayAabbIntersect,
  sphereFromPoints,
} from '../services/threeDBoundsAndCulling.ts'

describe('AABB de base', () => {
  test('aabbFromPoints retourne min/max coordonnées', () => {
    const pts = [[1, 2, 3], [4, 5, 6], [-1, 0, 2]] as [number, number, number][]
    const b = aabbFromPoints(pts)
    assert.deepEqual(b.min, [-1, 0, 2])
    assert.deepEqual(b.max, [4, 5, 6])
  })

  test('aabbCenter milieu correct', () => {
    const c = aabbCenter({ min: [0, 0, 0], max: [10, 10, 10] })
    assert.deepEqual(c, [5, 5, 5])
  })

  test('aabbVolume = produit des côtés', () => {
    const v = aabbVolume({ min: [0, 0, 0], max: [2, 3, 4] })
    assert.equal(v, 24)
  })

  test('aabbIntersect overlapping', () => {
    const a = { min: [0, 0, 0] as const, max: [5, 5, 5] as const }
    const b = { min: [3, 3, 3] as const, max: [10, 10, 10] as const }
    assert.equal(aabbIntersect(a, b), true)
  })

  test('aabbIntersect séparés', () => {
    const a = { min: [0, 0, 0] as const, max: [1, 1, 1] as const }
    const b = { min: [2, 2, 2] as const, max: [3, 3, 3] as const }
    assert.equal(aabbIntersect(a, b), false)
  })

  test('aabbUnion englobe les deux', () => {
    const a = { min: [0, 0, 0] as const, max: [1, 1, 1] as const }
    const b = { min: [5, 5, 5] as const, max: [6, 6, 6] as const }
    const u = aabbUnion(a, b)
    assert.deepEqual(u.min, [0, 0, 0])
    assert.deepEqual(u.max, [6, 6, 6])
  })
})

describe('Sphère englobante (Ritter)', () => {
  test('1 point → rayon 0', () => {
    const s = sphereFromPoints([[1, 2, 3]])
    assert.equal(s.radius, 0)
  })

  test('2 points → rayon = distance/2', () => {
    const s = sphereFromPoints([[0, 0, 0], [10, 0, 0]])
    assert.ok(Math.abs(s.radius - 5) < 0.1)
  })

  test('cube : sphere englobe tous les sommets', () => {
    const cube = [
      [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
      [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1],
    ] as [number, number, number][]
    const s = sphereFromPoints(cube)
    // Rayon ≥ √3/2 ≈ 0.866 (diagonale du cube unité / 2).
    assert.ok(s.radius >= 0.85)
    // Tous les sommets sont dans la sphère (rayon + ε).
    for (const p of cube) {
      const d = Math.hypot(p[0] - s.center[0], p[1] - s.center[1], p[2] - s.center[2])
      assert.ok(d <= s.radius + 0.01, `point ${p} dist ${d}, radius ${s.radius}`)
    }
  })

  test('vide → radius 0', () => {
    const s = sphereFromPoints([])
    assert.equal(s.radius, 0)
  })
})

describe('Ray-AABB intersection', () => {
  test('rayon traverse l\'AABB → distance > 0', () => {
    const t = rayAabbIntersect([-10, 0.5, 0.5], [1, 0, 0], { min: [0, 0, 0], max: [1, 1, 1] })
    assert.ok(t !== null && Math.abs(t - 10) < 0.01)
  })

  test('rayon parallèle qui rate → null', () => {
    const t = rayAabbIntersect([0, 5, 0.5], [1, 0, 0], { min: [0, 0, 0], max: [1, 1, 1] })
    assert.equal(t, null)
  })

  test('origine à l\'intérieur → t = 0', () => {
    const t = rayAabbIntersect([0.5, 0.5, 0.5], [1, 0, 0], { min: [0, 0, 0], max: [1, 1, 1] })
    assert.equal(t, 0)
  })

  test('rayon part de derrière l\'AABB → null', () => {
    const t = rayAabbIntersect([10, 0.5, 0.5], [1, 0, 0], { min: [0, 0, 0], max: [1, 1, 1] })
    assert.equal(t, null)
  })
})

describe('Frustum', () => {
  // Frustum simplifié : "cube clip space" [-1..1]³
  const orthoFrustum = {
    planes: [
      [1, 0, 0, 1], // left  x ≥ -1
      [-1, 0, 0, 1], // right x ≤ 1
      [0, 1, 0, 1], // bottom y ≥ -1
      [0, -1, 0, 1], // top    y ≤ 1
      [0, 0, 1, 1], // near   z ≥ -1
      [0, 0, -1, 1], // far    z ≤ 1
    ] as Array<[number, number, number, number]>,
  }

  test('point au centre du frustum → dedans', () => {
    assert.equal(pointInFrustum([0, 0, 0], orthoFrustum), true)
  })

  test('point hors frustum → dehors', () => {
    assert.equal(pointInFrustum([5, 0, 0], orthoFrustum), false)
    assert.equal(pointInFrustum([0, 0, -5], orthoFrustum), false)
  })

  test('AABB entièrement dans frustum → visible', () => {
    const box = { min: [-0.5, -0.5, -0.5] as const, max: [0.5, 0.5, 0.5] as const }
    assert.equal(aabbInFrustum(box, orthoFrustum), true)
  })

  test('AABB entièrement hors frustum → cull (false)', () => {
    const box = { min: [10, 10, 10] as const, max: [11, 11, 11] as const }
    assert.equal(aabbInFrustum(box, orthoFrustum), false)
  })

  test('AABB qui chevauche un plan → visible (conservatif)', () => {
    const box = { min: [-0.5, -0.5, -0.5] as const, max: [2, 0.5, 0.5] as const }
    assert.equal(aabbInFrustum(box, orthoFrustum), true)
  })
})

describe('frustumFromMatrix', () => {
  test('identité produit 6 plans normalisés', () => {
    const identity = [
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1,
    ]
    const f = frustumFromMatrix(identity)
    assert.equal(f.planes.length, 6)
    // Les normales doivent avoir norme ≈ 1.
    for (const [a, b, c] of f.planes) {
      const norm = Math.hypot(a, b, c)
      assert.ok(Math.abs(norm - 1) < 1e-6)
    }
  })

  test('matrice de mauvaise taille → throw', () => {
    assert.throws(() => frustumFromMatrix([1, 2, 3]))
  })
})
