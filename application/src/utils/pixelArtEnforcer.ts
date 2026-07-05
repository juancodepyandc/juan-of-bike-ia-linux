/**
 * pixelArtEnforcer — garantit un pixel art authentique en post-traitement.
 *
 * FLUX produit du "pseudo pixel art" : grille irreguliere, degrades doux,
 * milliers de couleurs. Les regles de prompt aident mais ne garantissent
 * rien. Ce module applique la definition mecanique du pixel art :
 *   1. downsample en grille entiere (moyenne par cellule),
 *   2. quantization de palette (median cut) vers N couleurs indexees,
 *   3. re-upscale nearest-neighbor → pixels carres durs alignes.
 *
 * Le coeur (quantizeToPixelGrid) est pur — testable sous node sans DOM.
 * Le wrapper enforcePixelArtBlob fait le tour canvas cote navigateur.
 */

export interface PixelArtOptions {
  /** Largeur de la grille en cellules (hauteur deduite du ratio). 16..512. */
  gridWidth: number
  /** Taille de palette indexee. 2..256. */
  paletteSize: number
}

export const PIXEL_ART_DEFAULTS: PixelArtOptions = {
  gridWidth: 128,
  paletteSize: 16,
}

/**
 * Extrait une taille de grille demandee dans le prompt ("32x32", "sprite 64",
 * "8 bit"...). Retourne les defaults ajustes si rien d'explicite.
 */
export function parsePixelArtOptions(prompt: string): PixelArtOptions {
  const normalized = prompt.toLowerCase()

  let gridWidth = PIXEL_ART_DEFAULTS.gridWidth
  const gridMatch = normalized.match(/\b(\d{1,3})\s*[x×]\s*(\d{1,3})\b/)
  if (gridMatch) {
    const w = Number(gridMatch[1])
    if (Number.isFinite(w)) gridWidth = w
  } else {
    const spriteMatch = normalized.match(/\bsprite\s+(\d{1,3})\b/)
    if (spriteMatch) gridWidth = Number(spriteMatch[1])
  }

  let paletteSize = PIXEL_ART_DEFAULTS.paletteSize
  if (/\b8[\s-]?bit\b/.test(normalized) || /\bgameboy|game boy\b/.test(normalized)) paletteSize = 8
  else if (/\b16[\s-]?bit\b/.test(normalized)) paletteSize = 32
  const paletteMatch = normalized.match(/\bpalette\s+(?:de\s+|of\s+)?(\d{1,3})\b/)
  if (paletteMatch) paletteSize = Number(paletteMatch[1])

  return {
    gridWidth: Math.min(512, Math.max(16, Math.round(gridWidth))),
    paletteSize: Math.min(256, Math.max(2, Math.round(paletteSize))),
  }
}

export interface QuantizedPixelGrid {
  width: number
  height: number
  /** RGBA aplati de la grille (width*height*4). */
  data: Uint8ClampedArray
  /** Palette finale [r,g,b] reellement utilisee. */
  palette: Array<[number, number, number]>
}

/** Downsample RGBA source vers une grille par moyenne de cellule. */
function downsampleToGrid(
  src: Uint8ClampedArray,
  srcW: number,
  srcH: number,
  gridW: number,
  gridH: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(gridW * gridH * 4)
  for (let gy = 0; gy < gridH; gy++) {
    const y0 = Math.floor((gy * srcH) / gridH)
    const y1 = Math.max(y0 + 1, Math.floor(((gy + 1) * srcH) / gridH))
    for (let gx = 0; gx < gridW; gx++) {
      const x0 = Math.floor((gx * srcW) / gridW)
      const x1 = Math.max(x0 + 1, Math.floor(((gx + 1) * srcW) / gridW))
      let r = 0, g = 0, b = 0, a = 0, n = 0
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          const i = (y * srcW + x) * 4
          r += src[i]; g += src[i + 1]; b += src[i + 2]; a += src[i + 3]
          n++
        }
      }
      const o = (gy * gridW + gx) * 4
      out[o] = Math.round(r / n)
      out[o + 1] = Math.round(g / n)
      out[o + 2] = Math.round(b / n)
      out[o + 3] = Math.round(a / n)
    }
  }
  return out
}

/** Median-cut sur les pixels RGB → palette de taille <= paletteSize. */
function medianCutPalette(pixels: Uint8ClampedArray, paletteSize: number): Array<[number, number, number]> {
  type Bucket = number[] // indices de pixels (offset/4)
  const count = pixels.length / 4
  const all: Bucket = []
  for (let i = 0; i < count; i++) all.push(i)

  const buckets: Bucket[] = [all]
  while (buckets.length < paletteSize) {
    // bucket avec la plus grande etendue de canal
    let bestBucket = -1
    let bestRange = -1
    let bestChannel = 0
    for (let b = 0; b < buckets.length; b++) {
      const bucket = buckets[b]
      if (bucket.length < 2) continue
      for (let c = 0; c < 3; c++) {
        let min = 255, max = 0
        for (const idx of bucket) {
          const v = pixels[idx * 4 + c]
          if (v < min) min = v
          if (v > max) max = v
        }
        const range = max - min
        if (range > bestRange) {
          bestRange = range
          bestBucket = b
          bestChannel = c
        }
      }
    }
    if (bestBucket < 0 || bestRange <= 0) break // plus rien a diviser
    const bucket = buckets[bestBucket]
    bucket.sort((p, q) => pixels[p * 4 + bestChannel] - pixels[q * 4 + bestChannel])
    const mid = Math.floor(bucket.length / 2)
    buckets.splice(bestBucket, 1, bucket.slice(0, mid), bucket.slice(mid))
  }

  return buckets
    .filter((bucket) => bucket.length > 0)
    .map((bucket) => {
      let r = 0, g = 0, b = 0
      for (const idx of bucket) {
        r += pixels[idx * 4]
        g += pixels[idx * 4 + 1]
        b += pixels[idx * 4 + 2]
      }
      const n = bucket.length
      return [Math.round(r / n), Math.round(g / n), Math.round(b / n)] as [number, number, number]
    })
}

function nearestPaletteColor(
  palette: Array<[number, number, number]>,
  r: number,
  g: number,
  b: number,
): [number, number, number] {
  let best = palette[0]
  let bestDist = Infinity
  for (const color of palette) {
    const dr = color[0] - r
    const dg = color[1] - g
    const db = color[2] - b
    const dist = dr * dr + dg * dg + db * db
    if (dist < bestDist) {
      bestDist = dist
      best = color
    }
  }
  return best
}

/**
 * Coeur pur : RGBA source → grille quantizee (downsample + median cut +
 * mapping nearest). L'alpha est binarise (>=128 opaque) pour des bords nets.
 */
export function quantizeToPixelGrid(
  src: Uint8ClampedArray,
  srcW: number,
  srcH: number,
  options: PixelArtOptions = PIXEL_ART_DEFAULTS,
): QuantizedPixelGrid {
  const gridW = Math.min(options.gridWidth, srcW)
  const gridH = Math.max(1, Math.round((gridW * srcH) / srcW))
  const grid = downsampleToGrid(src, srcW, srcH, gridW, gridH)
  const palette = medianCutPalette(grid, options.paletteSize)

  const used = new Map<string, [number, number, number]>()
  for (let i = 0; i < gridW * gridH; i++) {
    const o = i * 4
    const [r, g, b] = nearestPaletteColor(palette, grid[o], grid[o + 1], grid[o + 2])
    grid[o] = r
    grid[o + 1] = g
    grid[o + 2] = b
    grid[o + 3] = grid[o + 3] >= 128 ? 255 : 0
    used.set(`${r},${g},${b}`, [r, g, b])
  }

  return {
    width: gridW,
    height: gridH,
    data: grid,
    palette: Array.from(used.values()),
  }
}

/** Upscale nearest-neighbor de la grille vers la taille cible (pur). */
export function upscaleNearest(
  grid: QuantizedPixelGrid,
  targetW: number,
  targetH: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(targetW * targetH * 4)
  for (let y = 0; y < targetH; y++) {
    const gy = Math.min(grid.height - 1, Math.floor((y * grid.height) / targetH))
    for (let x = 0; x < targetW; x++) {
      const gx = Math.min(grid.width - 1, Math.floor((x * grid.width) / targetW))
      const s = (gy * grid.width + gx) * 4
      const o = (y * targetW + x) * 4
      out[o] = grid.data[s]
      out[o + 1] = grid.data[s + 1]
      out[o + 2] = grid.data[s + 2]
      out[o + 3] = grid.data[s + 3]
    }
  }
  return out
}

/**
 * Wrapper navigateur : Blob image → Blob PNG pixel-art-enforce a la meme
 * resolution de sortie. Echec silencieux = retourne le blob original
 * (jamais bloquer la generation pour un post-process).
 */
export async function enforcePixelArtBlob(blob: Blob, options: PixelArtOptions): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(blob)
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const ctx = canvas.getContext('2d')
    if (!ctx) return blob
    ctx.drawImage(bitmap, 0, 0)
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)

    const grid = quantizeToPixelGrid(imageData.data, canvas.width, canvas.height, options)
    const upscaled = upscaleNearest(grid, canvas.width, canvas.height)
    ctx.putImageData(new ImageData(upscaled, canvas.width, canvas.height), 0, 0)

    const result = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    return result ?? blob
  } catch {
    return blob
  }
}
