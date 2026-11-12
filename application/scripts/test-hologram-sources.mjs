#!/usr/bin/env node
// Real TypeScript module (Node type stripping) on synthetic reference views.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildSilhouetteCloud,
  distanceTransform,
  foregroundMask,
  maskBounds,
  pickViews,
} from '../src/components/generationFx/hologramSources.ts'

/** White background, coloured ellipse (rx, ry) centred at (cx, cy). */
function ellipseImage(w, h, cx, cy, rx, ry, rgb = [200, 40, 60], alpha = false) {
  const data = new Uint8ClampedArray(w * h * 4)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const k = (y * w + x) * 4
      const inside = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
      const c = inside ? rgb : [250, 250, 248]
      data[k] = c[0]; data[k + 1] = c[1]; data[k + 2] = c[2]
      data[k + 3] = alpha ? (inside ? 255 : 0) : 255
    }
  }
  return { width: w, height: h, data }
}

test('a plain background is separated from the subject', () => {
  const img = ellipseImage(120, 160, 60, 80, 30, 60)
  const res = foregroundMask(img)
  assert.ok(res, 'subject found')
  assert.equal(res.method, 'background')
  const expected = (Math.PI * 30 * 60) / (120 * 160)
  assert.ok(Math.abs(res.coverage - expected) < 0.02, `coverage ${res.coverage} vs ${expected}`)
  const b = maskBounds(res.mask)
  assert.deepEqual([b.x0, b.y0, b.x1, b.y1], [30, 20, 90, 140])
})

test('an alpha channel is used when present', () => {
  const res = foregroundMask(ellipseImage(100, 100, 50, 50, 20, 30, [10, 200, 90], true))
  assert.equal(res.method, 'alpha')
})

test('an image without a separable subject is refused instead of inventing a shape', () => {
  const blank = ellipseImage(80, 80, -100, -100, 1, 1)
  assert.equal(foregroundMask(blank), null)
})

test('distance to the contour peaks on the medial axis', () => {
  const res = foregroundMask(ellipseImage(120, 160, 60, 80, 30, 60))
  const d = distanceTransform(res.mask)
  const centre = d[80 * 120 + 60]
  assert.ok(centre > 25 && centre < 33, `centre distance ${centre}`)
  assert.equal(d[0], 0)
})

test('front view only gives a relief cloud standing on the emitter', () => {
  const img = ellipseImage(120, 160, 60, 80, 30, 60)
  const front = { img, mask: foregroundMask(img).mask }
  const cloud = buildSilhouetteCloud(front, { maxPoints: 6000 })
  assert.equal(cloud.method, 'relief')
  assert.ok(cloud.count > 2000 && cloud.count < 9000, `count ${cloud.count}`)
  let minY = Infinity
  let maxY = -Infinity
  for (let i = 0; i < cloud.count; i++) {
    minY = Math.min(minY, cloud.positions[i * 3 + 1])
    maxY = Math.max(maxY, cloud.positions[i * 3 + 1])
  }
  assert.ok(Math.abs(minY + 1) < 0.08, `base at ${minY}`)
  assert.ok(maxY > 0.85 && maxY <= 1.05, `top at ${maxY}`)
  // colours come from the reference, not from a preset palette
  assert.ok(Math.abs(cloud.colors[0] - 200 / 255) < 0.01)
})

test('a profile view drives the real thickness (visual hull)', () => {
  const frontImg = ellipseImage(120, 160, 60, 80, 30, 60)
  const thinSide = ellipseImage(120, 160, 60, 80, 8, 60)
  const front = { img: frontImg, mask: foregroundMask(frontImg).mask }
  const side = { img: thinSide, mask: foregroundMask(thinSide).mask }
  const relief = buildSilhouetteCloud(front, { maxPoints: 6000 })
  const hull = buildSilhouetteCloud(front, { side, maxPoints: 6000 })
  assert.equal(hull.method, 'hull')
  assert.ok(hull.depth < relief.depth * 0.6, `hull depth ${hull.depth} vs relief ${relief.depth}`)
  const expectedDepth = (8 / 60) * hull.height
  assert.ok(Math.abs(hull.depth - expectedDepth) < expectedDepth * 0.3, `depth ${hull.depth} vs ${expectedDepth}`)
})

test('the back view colours the rear surface', () => {
  const frontImg = ellipseImage(120, 160, 60, 80, 30, 60, [200, 40, 60])
  const backImg = ellipseImage(120, 160, 60, 80, 30, 60, [20, 60, 220])
  const front = { img: frontImg, mask: foregroundMask(frontImg).mask }
  const back = { img: backImg, mask: foregroundMask(backImg).mask }
  const cloud = buildSilhouetteCloud(front, { back, maxPoints: 4000 })
  let rearBlue = 0
  let rear = 0
  for (let i = 0; i < cloud.count; i++) {
    if (cloud.kinds[i] === 0 && cloud.positions[i * 3 + 2] < -0.05) {
      rear++
      if (cloud.colors[i * 3 + 2] > 0.8) rearBlue++
    }
  }
  assert.ok(rear > 100 && rearBlue / rear > 0.9, `${rearBlue}/${rear} rear points take the back colour`)
})

test('reference roles map to front, side and back views', () => {
  const v = pickViews([{ role: 'dos', url: 'b' }, { role: 'face', url: 'f' }, { role: 'droite', url: 's' }])
  assert.equal(v.front.url, 'f')
  assert.equal(v.side.url, 's')
  assert.equal(v.back.url, 'b')
  assert.equal(pickViews([{ role: 'inconnu', url: 'x' }]).front.url, 'x')
  assert.equal(pickViews([]).front, null)
})
