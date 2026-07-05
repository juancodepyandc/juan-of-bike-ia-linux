/**
 * Tests Bezier + RDP + smooth.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  bezierLength,
  bezierPoint,
  beziersToSvgPath,
  polylineToBeziers,
  rdp,
  smoothPolyline,
} from '../services/drawingCurveSmoothing.ts'

describe('RDP simplification', () => {
  test('ligne droite → 2 points', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }]
    const out = rdp(pts, 1)
    assert.equal(out.length, 2)
  })

  test('triangle → 3 points préservés avec epsilon faible', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 10 }, { x: 10, y: 0 }]
    const out = rdp(pts, 0.5)
    assert.equal(out.length, 3)
  })

  test('triangle large → 2 points avec epsilon élevé', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 1 }, { x: 10, y: 0 }]
    const out = rdp(pts, 10)
    assert.equal(out.length, 2)
  })

  test('< 3 points → inchangé', () => {
    assert.equal(rdp([{ x: 0, y: 0 }, { x: 1, y: 1 }], 1).length, 2)
    assert.equal(rdp([{ x: 0, y: 0 }], 1).length, 1)
  })
})

describe('polylineToBeziers', () => {
  test('2 points → 1 Bezier dégénéré', () => {
    const b = polylineToBeziers([{ x: 0, y: 0 }, { x: 10, y: 0 }])
    assert.equal(b.length, 1)
  })

  test('N points → N-1 segments', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 5 }, { x: 10, y: 0 }, { x: 15, y: 5 }]
    const b = polylineToBeziers(pts)
    assert.equal(b.length, 3)
  })

  test('chaque segment commence où le précédent finit', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 5 }, { x: 10, y: 0 }, { x: 15, y: 5 }]
    const b = polylineToBeziers(pts)
    for (let i = 1; i < b.length; i += 1) {
      assert.equal(b[i].start.x, b[i - 1].end.x)
      assert.equal(b[i].start.y, b[i - 1].end.y)
    }
  })

  test('vide → []', () => {
    assert.deepEqual(polylineToBeziers([]), [])
  })
})

describe('beziersToSvgPath', () => {
  test('format M ... C ... attendu', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 5 }, { x: 10, y: 0 }]
    const b = polylineToBeziers(pts)
    const path = beziersToSvgPath(b)
    assert.match(path, /^M 0 0/)
    assert.match(path, /C \d/)
  })

  test('beziers vides → ""', () => {
    assert.equal(beziersToSvgPath([]), '')
  })
})

describe('bezierPoint + bezierLength', () => {
  test('bezierPoint à t=0 → start', () => {
    const curve = { start: { x: 0, y: 0 }, control1: { x: 5, y: 5 }, control2: { x: 10, y: 5 }, end: { x: 15, y: 0 } }
    const p = bezierPoint(curve, 0)
    assert.equal(p.x, 0)
    assert.equal(p.y, 0)
  })

  test('bezierPoint à t=1 → end', () => {
    const curve = { start: { x: 0, y: 0 }, control1: { x: 5, y: 5 }, control2: { x: 10, y: 5 }, end: { x: 15, y: 0 } }
    const p = bezierPoint(curve, 1)
    assert.equal(p.x, 15)
    assert.equal(p.y, 0)
  })

  test('longueur d\'une ligne droite Bezier ≈ distance start-end', () => {
    const straight = { start: { x: 0, y: 0 }, control1: { x: 3, y: 0 }, control2: { x: 7, y: 0 }, end: { x: 10, y: 0 } }
    const len = bezierLength(straight, 64)
    assert.ok(Math.abs(len - 10) < 0.1, `len ${len}`)
  })
})

describe('smoothPolyline pipeline', () => {
  test('produit path + simplifiedPoints + beziers', () => {
    const noisy = [
      { x: 0, y: 0 }, { x: 1, y: 1 }, { x: 2, y: 0.5 }, { x: 5, y: 4 },
      { x: 8, y: 3 }, { x: 10, y: 0 }, { x: 11, y: -1 },
    ]
    const r = smoothPolyline(noisy, { epsilon: 1 })
    assert.ok(r.simplifiedPoints.length <= noisy.length)
    assert.ok(r.beziers.length >= 1)
    assert.match(r.path, /^M /)
  })

  test('epsilon élevé → plus de simplification', () => {
    const noisy = Array.from({ length: 20 }, (_, i) => ({ x: i, y: Math.sin(i) }))
    const tight = smoothPolyline(noisy, { epsilon: 0.01 })
    const loose = smoothPolyline(noisy, { epsilon: 0.5 })
    assert.ok(loose.simplifiedPoints.length <= tight.simplifiedPoints.length)
  })
})
