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
  profileLooksLikeFront,
} from '../src/components/generationFx/hologramSources.ts'

/** White background, coloured ellipse (rx, ry) centred at (cx, cy), optionally leaning (x shift per row). */
function ellipseImage(w, h, cx, cy, rx, ry, rgb = [200, 40, 60], alpha = false, slant = 0) {
  const data = new Uint8ClampedArray(w * h * 4)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const k = (y * w + x) * 4
      const inside = ((x - cx - slant * (y - cy)) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
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
  const res = foregroundMask(blank)
  // never pass a mask object to assert.equal: diffing its typed array can exhaust memory
  assert.ok(res === null, `expected a refusal, got coverage ${res?.coverage}`)
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

test('a "profile" view that is really another front view is not used as depth', () => {
  const frontImg = ellipseImage(120, 160, 60, 80, 30, 60)
  const fakeSide = ellipseImage(120, 160, 62, 78, 31, 59)
  const realSide = ellipseImage(120, 160, 60, 80, 9, 60)
  const front = { img: frontImg, mask: foregroundMask(frontImg).mask }
  const fake = { img: fakeSide, mask: foregroundMask(fakeSide).mask }
  const real = { img: realSide, mask: foregroundMask(realSide).mask }
  assert.equal(profileLooksLikeFront(front.mask, fake.mask), true)
  assert.equal(profileLooksLikeFront(front.mask, real.mask), false)
  const cloud = buildSilhouetteCloud(front, { side: fake, maxPoints: 4000 })
  assert.equal(cloud.method, 'relief')
  assert.equal(cloud.sideRejected, true)
  assert.equal(buildSilhouetteCloud(front, { side: real, maxPoints: 4000 }).method, 'hull')
})

test('a profile almost as wide as the front can only thin the relief, never thicken or bend it', () => {
  const frontImg = ellipseImage(120, 160, 60, 80, 30, 60)
  const front = { img: frontImg, mask: foregroundMask(frontImg).mask }
  const view = (rx) => {
    const img = ellipseImage(120, 160, 60, 80, rx, 60, [200, 40, 60], false, 0.08)
    return { img, mask: foregroundMask(img).mask }
  }
  const lean = (cloud) => {
    let up = 0, nUp = 0, low = 0, nLow = 0
    for (let i = 0; i < cloud.count; i++) {
      const y = cloud.positions[i * 3 + 1], z = cloud.positions[i * 3 + 2]
      if (y > 0.4) { up += z; nUp++ } else if (y < -0.4) { low += z; nLow++ }
    }
    return Math.abs(up / nUp - low / nLow)
  }
  const relief = buildSilhouetteCloud(front, { maxPoints: 6000 })
  // leaning three-quarter view labelled "profile": ambiguous, not a true side silhouette
  const ambiguous = buildSilhouetteCloud(front, { side: view(18), maxPoints: 6000 })
  assert.equal(ambiguous.method, 'hull')
  assert.equal(ambiguous.profileAmbiguous, true)
  assert.ok(ambiguous.depth <= relief.depth * 1.001, `depth ${ambiguous.depth} vs relief ${relief.depth}`)
  assert.ok(lean(ambiguous) < 0.03, `ambiguous profile must not bend the hologram (${lean(ambiguous)})`)
  // a real thin leaning profile still drives both thickness and lean
  const real = buildSilhouetteCloud(front, { side: view(9), maxPoints: 6000 })
  assert.equal(real.profileAmbiguous, false)
  assert.ok(lean(real) > 0.08, `real profile lean ${lean(real)}`)
})

// --- Real-world backdrops seen on generated references (ground truth known) ---
function rng(seed) {
  let a = seed >>> 0
  return () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }
}
function scene(w, h, background, subject, seed = 3) {
  const rand = rng(seed)
  const data = new Uint8ClampedArray(w * h * 4)
  const truth = new Uint8Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const k = (y * w + x) * 4
      const s = subject(x, y)
      const c = s ?? background(x, y, rand)
      if (s) truth[y * w + x] = 1
      data[k] = c[0]; data[k + 1] = c[1]; data[k + 2] = c[2]; data[k + 3] = 255
    }
  }
  return { img: { width: w, height: h, data }, truth }
}
const iouTruth = (mask, truth) => {
  let i = 0, u = 0
  for (let k = 0; k < truth.length; k++) { if (mask[k] && truth[k]) i++; if (mask[k] || truth[k]) u++ }
  return u ? i / u : 0
}
const inEllipse = (cx, cy, rx, ry) => (x, y) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
const jitter = (c, r, rand) => c.map((v) => v + (rand() - 0.5) * 2 * r)

test('a spotlight behind the subject is backdrop, not a halo around it', () => {
  const { img, truth } = scene(160, 200, (x, y, rand) => {
    const t = Math.min(1, Math.hypot(x - 80, y - 100) / 128)
    return jitter([150 - 90 * t, 150 - 88 * t, 160 - 90 * t], 4, rand)
  }, (x, y) => (inEllipse(80, 105, 30, 70)(x, y) ? [210 - y * 0.2, 120, 40] : null))
  const res = foregroundMask(img)
  assert.ok(iouTruth(res.mask.data, truth) > 0.97, `IoU ${iouTruth(res.mask.data, truth)}`)
})

test('a wall and a textured floor are both removed, the subject standing across them is kept', () => {
  const { img, truth } = scene(160, 200, (x, y, rand) => {
    if (y < 140) return jitter([205, 195, 175], 10, rand)
    const plank = (y - 140) % 10 === 0 ? -35 : 0
    return jitter([125 + plank, 85 + plank, 52 + plank], 6, rand)
  }, (x, y) => (inEllipse(80, 110, 26, 75)(x, y) ? [40, 90, 200] : null))
  const res = foregroundMask(img)
  assert.ok(iouTruth(res.mask.data, truth) > 0.95, `IoU ${iouTruth(res.mask.data, truth)}`)
})

test('a subject cut by the frame keeps its cropped part', () => {
  const { img, truth } = scene(160, 200, (x, y, rand) => jitter([200, 215, 230], 8, rand), (x, y) => (inEllipse(80, 150, 35, 80)(x, y) ? [230, 190, 40] : null))
  const res = foregroundMask(img)
  assert.ok(iouTruth(res.mask.data, truth) > 0.97, `IoU ${iouTruth(res.mask.data, truth)}`)
})

test('an image filled edge to edge (close-up, pattern) has no usable silhouette', () => {
  const { img } = scene(160, 200, (x, y) => [((x >> 3) * 53) % 255, ((y >> 3) * 97) % 255, (((x + y) >> 3) * 31) % 255], () => null)
  const res = foregroundMask(img)
  assert.ok(res === null, `expected a refusal, got coverage ${res?.coverage}`)
})
