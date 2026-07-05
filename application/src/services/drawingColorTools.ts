// Outils couleur expert : conversion RGB ↔ HSL ↔ HSV ↔ Lab, distance
// perceptuelle ΔE (CIE76), génération de palettes harmoniques (complémentaire,
// triadique, analogue), extraction de palette dominante depuis une liste de
// pixels (clustering K-means light).
//
// Module pur. Pas de canvas. Le caller fournit les pixels.

export type RGB = { r: number; g: number; b: number }
export type HSL = { h: number; s: number; l: number }
export type HSV = { h: number; s: number; v: number }
export type LAB = { L: number; a: number; b: number }

export function hexToRgb(hex: string): RGB | null {
  const h = hex.replace(/^#/, '')
  if (h.length === 3) {
    return {
      r: parseInt(h[0] + h[0], 16),
      g: parseInt(h[1] + h[1], 16),
      b: parseInt(h[2] + h[2], 16),
    }
  }
  if (h.length === 6) {
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    }
  }
  return null
}

export function rgbToHex({ r, g, b }: RGB): string {
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')
  return `#${c(r)}${c(g)}${c(b)}`
}

export function rgbToHsl({ r, g, b }: RGB): HSL {
  const rr = r / 255, gg = g / 255, bb = b / 255
  const max = Math.max(rr, gg, bb), min = Math.min(rr, gg, bb)
  let h = 0, s = 0
  const l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === rr) h = (gg - bb) / d + (gg < bb ? 6 : 0)
    else if (max === gg) h = (bb - rr) / d + 2
    else h = (rr - gg) / d + 4
    h /= 6
  }
  return { h: h * 360, s, l }
}

export function hslToRgb({ h, s, l }: HSL): RGB {
  const hh = ((h % 360) + 360) % 360 / 360
  function hue2rgb(p: number, q: number, t: number) {
    if (t < 0) t += 1
    if (t > 1) t -= 1
    if (t < 1 / 6) return p + (q - p) * 6 * t
    if (t < 1 / 2) return q
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6
    return p
  }
  if (s === 0) return { r: l * 255, g: l * 255, b: l * 255 }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  return {
    r: hue2rgb(p, q, hh + 1 / 3) * 255,
    g: hue2rgb(p, q, hh) * 255,
    b: hue2rgb(p, q, hh - 1 / 3) * 255,
  }
}

export function rgbToHsv({ r, g, b }: RGB): HSV {
  const rr = r / 255, gg = g / 255, bb = b / 255
  const max = Math.max(rr, gg, bb), min = Math.min(rr, gg, bb)
  const d = max - min
  let h = 0
  const s = max === 0 ? 0 : d / max
  const v = max
  if (d !== 0) {
    if (max === rr) h = ((gg - bb) / d + (gg < bb ? 6 : 0)) / 6
    else if (max === gg) h = ((bb - rr) / d + 2) / 6
    else h = ((rr - gg) / d + 4) / 6
  }
  return { h: h * 360, s, v }
}

// RGB → CIE XYZ → CIE Lab (D65)
function srgbToLinear(c: number): number {
  const n = c / 255
  return n <= 0.04045 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4)
}

function rgbToXyz({ r, g, b }: RGB): { x: number; y: number; z: number } {
  const rl = srgbToLinear(r), gl = srgbToLinear(g), bl = srgbToLinear(b)
  return {
    x: rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375,
    y: rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750,
    z: rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041,
  }
}

const XN = 0.95047, YN = 1.0, ZN = 1.08883
function xyzToLab(x: number, y: number, z: number): LAB {
  const f = (t: number) => t > 0.008856 ? Math.cbrt(t) : (7.787 * t + 16 / 116)
  const fx = f(x / XN), fy = f(y / YN), fz = f(z / ZN)
  return {
    L: 116 * fy - 16,
    a: 500 * (fx - fy),
    b: 200 * (fy - fz),
  }
}

export function rgbToLab(rgb: RGB): LAB {
  const { x, y, z } = rgbToXyz(rgb)
  return xyzToLab(x, y, z)
}

/** Delta E CIE76 — différence perceptuelle de couleur. <2 = imperceptible. */
export function deltaE76(a: RGB, b: RGB): number {
  const la = rgbToLab(a), lb = rgbToLab(b)
  return Math.sqrt((la.L - lb.L) ** 2 + (la.a - lb.a) ** 2 + (la.b - lb.b) ** 2)
}

// --- Harmonies couleur ----------------------------------------------------
export type Harmony = 'complementary' | 'analogous' | 'triadic' | 'tetradic' | 'split-complementary' | 'monochromatic'

/**
 * Génère une palette harmonique à partir d'une couleur de base.
 *   - complementary : +180°
 *   - analogous     : +/-30°
 *   - triadic       : +120°, +240°
 *   - tetradic      : +90°, +180°, +270°
 *   - split-comp    : +150°, +210°
 *   - monochromatic : variations de L (lightness)
 */
export function generateHarmony(baseHex: string, harmony: Harmony): string[] {
  const rgb = hexToRgb(baseHex)
  if (!rgb) return [baseHex]
  const hsl = rgbToHsl(rgb)
  const shifts = (() => {
    switch (harmony) {
      case 'complementary': return [{ dh: 180 }]
      case 'analogous': return [{ dh: -30 }, { dh: 30 }]
      case 'triadic': return [{ dh: 120 }, { dh: 240 }]
      case 'tetradic': return [{ dh: 90 }, { dh: 180 }, { dh: 270 }]
      case 'split-complementary': return [{ dh: 150 }, { dh: 210 }]
      case 'monochromatic': return [{ dh: 0, dl: -0.25 }, { dh: 0, dl: 0.25 }]
    }
  })()
  const out = [baseHex]
  for (const sh of shifts) {
    const dh = (sh as { dh: number }).dh
    const dl = (sh as { dl?: number }).dl ?? 0
    const newL = Math.max(0.05, Math.min(0.95, hsl.l + dl))
    out.push(rgbToHex(hslToRgb({ h: hsl.h + dh, s: hsl.s, l: newL })))
  }
  return out
}

// --- Extraction de palette par K-means -------------------------------------

export type PaletteSwatch = {
  hex: string
  rgb: RGB
  /** Fraction de pixels qui sont assignés à ce centroïde. */
  weight: number
}

/**
 * K-means light pour extraire les k couleurs dominantes d'un set de pixels.
 * - k = 5 par défaut
 * - 10 itérations max (rapide)
 * - initialisation k-means++ (meilleure convergence)
 */
export function extractPalette(pixels: RGB[], k = 5, iterations = 10): PaletteSwatch[] {
  if (pixels.length === 0) return []
  if (pixels.length <= k) return pixels.map((p) => ({ hex: rgbToHex(p), rgb: p, weight: 1 / pixels.length }))

  // Init k-means++.
  const centroids: RGB[] = [pixels[Math.floor(pixels.length / 2)]]
  while (centroids.length < k) {
    const distances = pixels.map((p) => {
      let min = Infinity
      for (const c of centroids) {
        const d = sqRGBDist(p, c)
        if (d < min) min = d
      }
      return min
    })
    const sumD = distances.reduce((a, b) => a + b, 0)
    if (sumD === 0) break
    let r = Math.random() * sumD
    for (let i = 0; i < distances.length; i += 1) {
      r -= distances[i]
      if (r <= 0) {
        centroids.push(pixels[i])
        break
      }
    }
  }

  // Boucle k-means.
  const assignments = new Array<number>(pixels.length).fill(0)
  for (let it = 0; it < iterations; it += 1) {
    // Assignment.
    for (let i = 0; i < pixels.length; i += 1) {
      let best = 0
      let bestDist = Infinity
      for (let c = 0; c < centroids.length; c += 1) {
        const d = sqRGBDist(pixels[i], centroids[c])
        if (d < bestDist) {
          bestDist = d
          best = c
        }
      }
      assignments[i] = best
    }
    // Update.
    const sums: Array<{ r: number; g: number; b: number; n: number }> = centroids.map(() => ({ r: 0, g: 0, b: 0, n: 0 }))
    for (let i = 0; i < pixels.length; i += 1) {
      const a = assignments[i]
      sums[a].r += pixels[i].r
      sums[a].g += pixels[i].g
      sums[a].b += pixels[i].b
      sums[a].n += 1
    }
    let stable = true
    for (let c = 0; c < centroids.length; c += 1) {
      if (sums[c].n === 0) continue
      const newR = sums[c].r / sums[c].n
      const newG = sums[c].g / sums[c].n
      const newB = sums[c].b / sums[c].n
      if (Math.abs(newR - centroids[c].r) > 0.5 || Math.abs(newG - centroids[c].g) > 0.5 || Math.abs(newB - centroids[c].b) > 0.5) stable = false
      centroids[c] = { r: newR, g: newG, b: newB }
    }
    if (stable) break
  }

  // Final counts.
  const counts = new Array(centroids.length).fill(0)
  for (const a of assignments) counts[a] += 1
  const palette: PaletteSwatch[] = centroids.map((c, i) => ({
    rgb: c, hex: rgbToHex(c), weight: counts[i] / pixels.length,
  }))
  palette.sort((a, b) => b.weight - a.weight)
  return palette
}

function sqRGBDist(a: RGB, b: RGB): number {
  return (a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2
}

/**
 * Contraste WCAG : ratio entre 2 couleurs. < 4.5 = échec normal, < 3 = échec
 * gros texte, ≥ 7 = AAA.
 */
export function wcagContrast(c1: RGB, c2: RGB): number {
  const l1 = relativeLuminance(c1), l2 = relativeLuminance(c2)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

function relativeLuminance({ r, g, b }: RGB): number {
  const rl = srgbToLinear(r), gl = srgbToLinear(g), bl = srgbToLinear(b)
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
}
