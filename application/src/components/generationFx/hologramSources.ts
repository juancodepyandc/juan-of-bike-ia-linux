/**
 * Sources géométriques de l'hologramme 3D.
 *
 * Seules les données réelles de la demande en cours sont utilisées : vues de
 * référence générées ou fournies, maillage produit, pièces STL mesurées. Aucun
 * objet, personnage ou squelette préfabriqué.
 *
 * Reconstruction depuis les vues (prévisualisation, pas le maillage final) :
 *  - forme : silhouette de la vue de face ;
 *  - épaisseur : largeur par rangée de la vue de profil quand elle existe
 *    (enveloppe visuelle symétrique, sans deviner le sens du profil), sinon
 *    relief « gonflé » d'après la distance au contour ;
 *  - couleurs : vue de face, vue de dos (miroir) pour la face arrière.
 * Le module est pur (aucun DOM) pour être testé sous Node.
 */

export type RGBAImage = { width: number; height: number; data: Uint8ClampedArray | Uint8Array }
export type Mask = { width: number; height: number; data: Uint8Array }
export type MaskResult = { mask: Mask; method: 'alpha' | 'background'; coverage: number }

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

function median(values: number[]): number {
  if (!values.length) return 0
  const s = values.slice().sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** Composantes 4-connexes ; garde les composantes significatives puis bouche les trous. */
function cleanMask(mask: Mask): number {
  const { width: w, height: h, data } = mask
  const n = w * h
  const label = new Int32Array(n).fill(-1)
  const sizes: number[] = []
  const queue = new Int32Array(n)
  for (let i = 0; i < n; i++) {
    if (!data[i] || label[i] >= 0) continue
    const id = sizes.length
    let head = 0
    let tail = 0
    queue[tail++] = i
    label[i] = id
    let size = 0
    while (head < tail) {
      const j = queue[head++]
      size++
      const x = j % w
      const y = (j - x) / w
      if (x > 0 && data[j - 1] && label[j - 1] < 0) { label[j - 1] = id; queue[tail++] = j - 1 }
      if (x < w - 1 && data[j + 1] && label[j + 1] < 0) { label[j + 1] = id; queue[tail++] = j + 1 }
      if (y > 0 && data[j - w] && label[j - w] < 0) { label[j - w] = id; queue[tail++] = j - w }
      if (y < h - 1 && data[j + w] && label[j + w] < 0) { label[j + w] = id; queue[tail++] = j + w }
    }
    sizes.push(size)
  }
  if (!sizes.length) return 0
  const largest = Math.max(...sizes)
  const keep = sizes.map((s) => s >= Math.max(largest * 0.04, 12))
  for (let i = 0; i < n; i++) data[i] = data[i] && keep[label[i]] ? 1 : 0
  // trous : fond non relié au bord
  const outside = new Uint8Array(n)
  let head = 0
  let tail = 0
  const push = (j: number) => {
    if (!data[j] && !outside[j]) { outside[j] = 1; queue[tail++] = j }
  }
  for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x) }
  for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1) }
  while (head < tail) {
    const j = queue[head++]
    const x = j % w
    const y = (j - x) / w
    if (x > 0) push(j - 1)
    if (x < w - 1) push(j + 1)
    if (y > 0) push(j - w)
    if (y < h - 1) push(j + w)
  }
  let fg = 0
  for (let i = 0; i < n; i++) {
    if (!data[i] && !outside[i]) data[i] = 1
    fg += data[i]
  }
  return fg
}

/**
 * Masque du sujet : canal alpha s'il est utilisé, sinon fond estimé sur le
 * bord de l'image puis remplissage depuis le bord (un fond uni, comme les
 * références générées pour la 3D, se sépare proprement). Null si l'image ne
 * permet pas d'isoler un sujet.
 */
export function foregroundMask(img: RGBAImage): MaskResult | null {
  const { width: w, height: h, data } = img
  const n = w * h
  if (w < 8 || h < 8 || data.length < n * 4) return null
  const out = new Uint8Array(n)
  let transparent = 0
  for (let i = 0; i < n; i++) if (data[i * 4 + 3] < 250) transparent++
  let method: MaskResult['method'] = 'background'
  if (transparent > n * 0.02) {
    method = 'alpha'
    for (let i = 0; i < n; i++) out[i] = data[i * 4 + 3] >= 128 ? 1 : 0
  } else {
    const rs: number[] = []
    const gs: number[] = []
    const bs: number[] = []
    const sample = (x: number, y: number) => {
      const k = (y * w + x) * 4
      rs.push(data[k]); gs.push(data[k + 1]); bs.push(data[k + 2])
    }
    for (let x = 0; x < w; x++) { sample(x, 0); sample(x, 1); sample(x, h - 2); sample(x, h - 1) }
    for (let y = 2; y < h - 2; y++) { sample(0, y); sample(1, y); sample(w - 2, y); sample(w - 1, y) }
    const br = median(rs)
    const bg = median(gs)
    const bb = median(bs)
    const dist = (k: number) => {
      const dr = data[k] - br
      const dg = data[k + 1] - bg
      const db = data[k + 2] - bb
      return Math.sqrt(0.3 * dr * dr + 0.59 * dg * dg + 0.11 * db * db)
    }
    const borderDist: number[] = []
    for (let i = 0; i < rs.length; i++) {
      const dr = rs[i] - br
      const dg = gs[i] - bg
      const db = bs[i] - bb
      borderDist.push(Math.sqrt(0.3 * dr * dr + 0.59 * dg * dg + 0.11 * db * db))
    }
    const thr = clamp(14 + 3.5 * median(borderDist), 18, 80)
    const background = new Uint8Array(n)
    const queue = new Int32Array(n)
    let head = 0
    let tail = 0
    const push = (j: number) => {
      if (!background[j] && dist(j * 4) < thr) { background[j] = 1; queue[tail++] = j }
    }
    for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x) }
    for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1) }
    while (head < tail) {
      const j = queue[head++]
      const x = j % w
      const y = (j - x) / w
      if (x > 0) push(j - 1)
      if (x < w - 1) push(j + 1)
      if (y > 0) push(j - w)
      if (y < h - 1) push(j + w)
    }
    for (let i = 0; i < n; i++) out[i] = background[i] ? 0 : 1
  }
  const mask: Mask = { width: w, height: h, data: out }
  const fg = cleanMask(mask)
  const coverage = fg / n
  if (coverage < 0.01 || coverage > 0.97) return null
  return { mask, method, coverage }
}

export type Bounds = { x0: number; y0: number; x1: number; y1: number }

export function maskBounds(mask: Mask): Bounds | null {
  const { width: w, height: h, data } = mask
  let x0 = w
  let y0 = h
  let x1 = -1
  let y1 = -1
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!data[y * w + x]) continue
      if (x < x0) x0 = x
      if (x > x1) x1 = x
      if (y < y0) y0 = y
      if (y > y1) y1 = y
    }
  }
  return x1 < 0 ? null : { x0, y0, x1, y1 }
}

/** Distance au contour (chanfrein 3-4, en pixels) ; le bord de l'image compte comme fond. */
export function distanceTransform(mask: Mask): Float32Array {
  const { width: w, height: h, data } = mask
  const INF = 1e9
  const d = new Float32Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      d[i] = data[i] ? Math.min(INF, (x + 1) * 3, (w - x) * 3, (y + 1) * 3, (h - y) * 3) : 0
    }
  }
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      if (!d[i]) continue
      let v = d[i]
      if (x > 0) v = Math.min(v, d[i - 1] + 3)
      if (y > 0) {
        v = Math.min(v, d[i - w] + 3)
        if (x > 0) v = Math.min(v, d[i - w - 1] + 4)
        if (x < w - 1) v = Math.min(v, d[i - w + 1] + 4)
      }
      d[i] = v
    }
  }
  for (let y = h - 1; y >= 0; y--) {
    for (let x = w - 1; x >= 0; x--) {
      const i = y * w + x
      if (!d[i]) continue
      let v = d[i]
      if (x < w - 1) v = Math.min(v, d[i + 1] + 3)
      if (y < h - 1) {
        v = Math.min(v, d[i + w] + 3)
        if (x < w - 1) v = Math.min(v, d[i + w + 1] + 4)
        if (x > 0) v = Math.min(v, d[i + w - 1] + 4)
      }
      d[i] = v
    }
  }
  for (let i = 0; i < d.length; i++) d[i] /= 3
  return d
}

export type ViewInput = { img: RGBAImage; mask: Mask }

export type CloudBuild = {
  positions: Float32Array
  colors: Float32Array
  /** 0 surface, 1 intérieur (volume), 2 contour */
  kinds: Float32Array
  count: number
  method: 'hull' | 'relief'
  /** dimensions monde du nuage (hauteur, largeur, profondeur) */
  height: number
  width: number
  depth: number
}

function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Demi-largeur du masque par rangée (pixels) ; 0 si la rangée est vide. */
export function rowHalfWidths(mask: Mask): Float32Array {
  const { width: w, height: h, data } = mask
  const out = new Float32Array(h)
  for (let y = 0; y < h; y++) {
    let a = -1
    let b = -1
    for (let x = 0; x < w; x++) {
      if (!data[y * w + x]) continue
      if (a < 0) a = x
      b = x
    }
    out[y] = a < 0 ? 0 : (b - a + 1) / 2
  }
  return out
}

/**
 * Nuage de points 3D du sujet depuis ses vues. La base du sujet est posée en
 * y = -1, le sujet tient dans une boîte de 2 unités, centré en x et z.
 */
export function buildSilhouetteCloud(
  front: ViewInput,
  opts: { side?: ViewInput | null; back?: ViewInput | null; maxPoints?: number; seed?: number } = {},
): CloudBuild | null {
  const fb = maskBounds(front.mask)
  if (!fb) return null
  const w = front.mask.width
  const fm = front.mask.data
  const Hf = fb.y1 - fb.y0 + 1
  const Wf = fb.x1 - fb.x0 + 1
  const s = 2 / Math.max(Hf, Wf)
  const cx = (fb.x0 + fb.x1) / 2
  const dt = distanceTransform(front.mask)

  // relief par rangée : rayon local = distance maximale dans la course horizontale
  const reliefPx = new Float32Array(dt.length)
  for (let y = fb.y0; y <= fb.y1; y++) {
    let x = fb.x0
    while (x <= fb.x1) {
      if (!fm[y * w + x]) { x++; continue }
      let end = x
      let r = 0.5
      while (end <= fb.x1 && fm[y * w + end]) { r = Math.max(r, dt[y * w + end]); end++ }
      for (let k = x; k < end; k++) {
        const d = Math.min(dt[y * w + k], r)
        reliefPx[y * w + k] = Math.sqrt(Math.max(0, 2 * r * d - d * d))
      }
      x = end
    }
  }

  // épaisseur réelle lue sur la vue de profil, rangée par rangée
  let method: CloudBuild['method'] = 'relief'
  const rowScale = new Float32Array(front.mask.height).fill(0.92)
  const sb = opts.side ? maskBounds(opts.side.mask) : null
  if (opts.side && sb) {
    const sideHalf = rowHalfWidths(opts.side.mask)
    const Hs = sb.y1 - sb.y0 + 1
    const sideWorldPerPx = (Hf * s) / Hs
    const raw = new Float32Array(front.mask.height).fill(Number.NaN)
    let used = 0
    for (let y = fb.y0; y <= fb.y1; y++) {
      const t = Hf > 1 ? (y - fb.y0) / (Hf - 1) : 0
      const ys = Math.round(sb.y0 + t * (Hs - 1))
      const half = sideHalf[ys] * sideWorldPerPx
      let maxRelief = 0
      for (let x = fb.x0; x <= fb.x1; x++) maxRelief = Math.max(maxRelief, reliefPx[y * w + x] * s)
      if (half > 0 && maxRelief > 0) { raw[y] = clamp(half / maxRelief, 0.3, 3.5); used++ }
    }
    if (used >= Hf * 0.5) {
      method = 'hull'
      for (let y = fb.y0; y <= fb.y1; y++) {
        let sum = 0
        let cnt = 0
        for (let k = -2; k <= 2; k++) {
          const v = raw[y + k]
          if (y + k >= fb.y0 && y + k <= fb.y1 && Number.isFinite(v)) { sum += v; cnt++ }
        }
        rowScale[y] = cnt ? sum / cnt : 0.92
      }
    }
  }

  let fgCount = 0
  for (let y = fb.y0; y <= fb.y1; y++) for (let x = fb.x0; x <= fb.x1; x++) fgCount += fm[y * w + x]
  const maxPoints = Math.max(2000, opts.maxPoints ?? 30000)
  const perPixel = 2.3
  const stride = Math.max(1, Math.ceil(Math.sqrt((fgCount * perPixel) / maxPoints)))
  const rand = mulberry32(opts.seed ?? 1337)

  const pos: number[] = []
  const col: number[] = []
  const kind: number[] = []
  const fd = front.img.data
  const back = opts.back && maskBounds(opts.back.mask) ? opts.back : null
  const bbx = back ? (maskBounds(back.mask) as Bounds) : null
  let maxDepth = 0

  const colorAt = (img: RGBAImage, x: number, y: number): [number, number, number] => {
    const k = (y * img.width + x) * 4
    return [img.data[k] / 255, img.data[k + 1] / 255, img.data[k + 2] / 255]
  }

  for (let y = fb.y0; y <= fb.y1; y += stride) {
    for (let x = fb.x0; x <= fb.x1; x += stride) {
      const i = y * w + x
      if (!fm[i]) continue
      const jx = (rand() - 0.5) * stride
      const jy = (rand() - 0.5) * stride
      const wx = (x + jx - cx) * s
      const wy = (fb.y1 - (y + jy)) * s - 1
      const depth = reliefPx[i] * s * rowScale[y]
      maxDepth = Math.max(maxDepth, depth)
      const fc: [number, number, number] = [fd[i * 4] / 255, fd[i * 4 + 1] / 255, fd[i * 4 + 2] / 255]
      const edge = dt[i] < 1.25 ? 2 : 0
      pos.push(wx, wy, depth); col.push(fc[0], fc[1], fc[2]); kind.push(edge)
      let bc: [number, number, number] = [fc[0] * 0.7, fc[1] * 0.7, fc[2] * 0.7]
      if (back && bbx) {
        const u = Wf > 1 ? (x - fb.x0) / (Wf - 1) : 0
        const t = Hf > 1 ? (y - fb.y0) / (Hf - 1) : 0
        const bx = Math.round(bbx.x1 - u * (bbx.x1 - bbx.x0))
        const by = Math.round(bbx.y0 + t * (bbx.y1 - bbx.y0))
        if (bx >= 0 && by >= 0 && bx < back.mask.width && by < back.mask.height && back.mask.data[by * back.mask.width + bx]) {
          bc = colorAt(back.img, bx, by)
        }
      }
      pos.push(wx, wy, -depth); col.push(bc[0], bc[1], bc[2]); kind.push(edge)
      if (depth > 0.01 && rand() < 0.3) {
        const z = (rand() * 2 - 1) * depth * 0.85
        pos.push(wx, wy, z); col.push(fc[0] * 0.6, fc[1] * 0.6, fc[2] * 0.6); kind.push(1)
      }
    }
  }
  const count = kind.length
  if (!count) return null
  return {
    positions: Float32Array.from(pos),
    colors: Float32Array.from(col),
    kinds: Float32Array.from(kind),
    count,
    method,
    height: Hf * s,
    width: Wf * s,
    depth: maxDepth * 2,
  }
}

/** Rôle → usage géométrique. Les rôles inconnus servent de face par défaut. */
export function pickViews<T extends { role: string }>(refs: T[]): { front: T | null; side: T | null; back: T | null } {
  const byRole = (r: string) => refs.find((ref) => ref.role === r) ?? null
  const front = byRole('face') ?? byRole('trois_quarts') ?? refs.find((r) => !['dos', 'gauche', 'droite', 'haut', 'bas'].includes(r.role)) ?? null
  const side = byRole('droite') ?? byRole('gauche')
  const back = byRole('dos')
  return { front, side: side !== front ? side : null, back: back !== front ? back : null }
}
