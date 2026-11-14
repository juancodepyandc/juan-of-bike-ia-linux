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

/** Flou boîte séparable (rayon r) des canaux RGB, en flottants : atténue les textures de fond. */
function blurRGB(data: Uint8ClampedArray | Uint8Array, w: number, h: number, r: number): Float32Array {
  const tmp = new Float32Array(w * h * 3)
  const out = new Float32Array(w * h * 3)
  const k = 2 * r + 1
  for (let y = 0; y < h; y++) {
    for (let c = 0; c < 3; c++) {
      let acc = 0
      for (let d = -r; d <= r; d++) acc += data[(y * w + clamp(d, 0, w - 1)) * 4 + c]
      for (let x = 0; x < w; x++) {
        tmp[(y * w + x) * 3 + c] = acc / k
        acc += data[(y * w + Math.min(w - 1, x + r + 1)) * 4 + c] - data[(y * w + Math.max(0, x - r)) * 4 + c]
      }
    }
  }
  for (let x = 0; x < w; x++) {
    for (let c = 0; c < 3; c++) {
      let acc = 0
      for (let d = -r; d <= r; d++) acc += tmp[(clamp(d, 0, h - 1) * w + x) * 3 + c]
      for (let y = 0; y < h; y++) {
        out[(y * w + x) * 3 + c] = acc / k
        acc += tmp[(Math.min(h - 1, y + r + 1) * w + x) * 3 + c] - tmp[(Math.max(0, y - r) * w + x) * 3 + c]
      }
    }
  }
  return out
}

/**
 * Écart de couleur en luminance + chrominance (YCbCr) : un gris reste mesuré par sa
 * luminance, mais une teinte différente (bois orangé sur mur beige, sujet bleu sur
 * ciel gris) compte vraiment, ce que la seule luminance pondérée écrasait.
 */
function yccDist(dr: number, dg: number, db: number): number {
  const dy = 0.3 * dr + 0.59 * dg + 0.11 * db
  const dcb = 0.564 * (db - dy)
  const dcr = 0.713 * (dr - dy)
  return Math.sqrt(dy * dy + dcb * dcb + dcr * dcr)
}

const colorDist = (a: ArrayLike<number>, i: number, b: ArrayLike<number>, j: number) =>
  yccDist(a[i] - b[j], a[i + 1] - b[j + 1], a[i + 2] - b[j + 2])

/** Couleur de décor et bande verticale où elle touche le bord (un sol ne monte pas sur le mur). */
type BackdropCluster = { color: Float32Array; spread: number; seedTol: number; gapTol: number; yMin: number; yMax: number }

/**
 * Couleurs du décor lues sur le bord de l'image (jusqu'à 4 : mur, sol, dégradé…).
 * La couleur dominante du bord est le décor. Une autre couleur n'est retenue comme
 * décor que si elle touche au moins deux côtés, occupe un coin du cadre et reste
 * absente du cœur de l'image : un sujet coupé par le cadre (bras des deux côtés,
 * main levée et pieds, véhicule coupé aux deux bouts, buste) a sa couleur au cœur
 * de l'image ou ne touche aucun coin, et reste donc sujet.
 */
function backdropClusters(blur: Float32Array, w: number, h: number): { clusters: BackdropCluster[]; noise: number; gradTol: number; grad: Float32Array; borderRange: number } {
  const samples: number[] = []
  const sides: number[] = []
  const add = (x: number, y: number, side: number) => { samples.push((y * w + x) * 3); sides.push(side) }
  for (let x = 0; x < w; x++) for (let b = 0; b < 2; b++) { add(x, b, 0); add(x, h - 1 - b, 1) }
  for (let y = 2; y < h - 2; y++) for (let b = 0; b < 2; b++) { add(b, y, 2); add(w - 1 - b, y, 3) }
  const S = samples.length
  const lum = samples.map((k) => 0.3 * blur[k] + 0.59 * blur[k + 1] + 0.11 * blur[k + 2])
  const order = lum.map((_, i) => i).sort((a, b) => lum[a] - lum[b])
  const K = 4
  const centers = Array.from({ length: K }, (_, c) => Float32Array.from(blur.subarray(samples[order[Math.floor(((c + 0.5) / K) * S)]], samples[order[Math.floor(((c + 0.5) / K) * S)]] + 3)))
  const assign = new Int32Array(S)
  for (let it = 0; it < 8; it++) {
    const sum = Array.from({ length: K }, () => [0, 0, 0, 0])
    for (let i = 0; i < S; i++) {
      let best = 0
      let bd = Infinity
      for (let c = 0; c < K; c++) {
        const d = colorDist(blur, samples[i], centers[c], 0)
        if (d < bd) { bd = d; best = c }
      }
      assign[i] = best
      const acc = sum[best]
      acc[0] += blur[samples[i]]; acc[1] += blur[samples[i] + 1]; acc[2] += blur[samples[i] + 2]; acc[3]++
    }
    for (let c = 0; c < K; c++) if (sum[c][3]) for (let q = 0; q < 3; q++) centers[c][q] = sum[c][q] / sum[c][3]
  }
  const sideTotal = [0, 0, 0, 0]
  for (const sd of sides) sideTotal[sd]++
  // voisinage de chaque coin : 8 % de la longueur des deux côtés qui s'y rejoignent
  const cornerOf = (k: number): number => {
    const j = k / 3
    const x = j % w
    const y = (j - x) / w
    const cx = Math.max(2, Math.round(0.08 * w))
    const cy = Math.max(2, Math.round(0.08 * h))
    const left = x < cx
    const right = x >= w - cx
    const top = y < cy
    const bottom = y >= h - cy
    if (top && left) return 0
    if (top && right) return 1
    if (bottom && left) return 2
    if (bottom && right) return 3
    return -1
  }
  const cornerTotal = [0, 0, 0, 0]
  for (let i = 0; i < S; i++) { const c = cornerOf(samples[i]); if (c >= 0) cornerTotal[c]++ }
  const stats = centers.map((color, c) => {
    const members: number[] = []
    const perSide = [0, 0, 0, 0]
    const perCorner = [0, 0, 0, 0]
    const ys: number[] = []
    for (let i = 0; i < S; i++) {
      if (assign[i] !== c) continue
      members.push(colorDist(blur, samples[i], color, 0))
      perSide[sides[i]]++
      const corner = cornerOf(samples[i])
      if (corner >= 0) perCorner[corner]++
      if (sides[i] >= 2) ys.push(Math.floor(samples[i] / 3 / w))
    }
    members.sort((a, b) => a - b)
    ys.sort((a, b) => a - b)
    const spread = members.length ? members[Math.min(members.length - 1, Math.floor(0.8 * members.length))] : 0
    const seedTol = clamp(10 + 2 * spread, 14, 48)
    const touches = perSide.map((v, sd) => sideTotal[sd] > 0 && v / sideTotal[sd] >= 0.05)
    const corners = perCorner.filter((v, k) => cornerTotal[k] > 0 && v / cornerTotal[k] >= 0.6).length
    // présence de la couleur au cœur de l'image (là où se tient le sujet)
    let core = 0
    let coreHit = 0
    for (let y = Math.floor(0.25 * h); y < Math.ceil(0.75 * h); y += 2) {
      for (let x = Math.floor(0.3 * w); x < Math.ceil(0.7 * w); x += 2) {
        core++
        if (colorDist(blur, (y * w + x) * 3, color, 0) < seedTol) coreHit++
      }
    }
    const margin = Math.round(0.03 * h)
    const yMin = touches[0] ? 0 : ys.length ? Math.max(0, ys[Math.floor(0.02 * (ys.length - 1))] - margin) : 0
    const yMax = touches[1] ? h - 1 : ys.length ? Math.min(h - 1, ys[Math.ceil(0.98 * (ys.length - 1))] + margin) : h - 1
    return { color, spread, seedTol, share: members.length / S, sidesCovered: touches.filter(Boolean).length, corners, corePresence: core ? coreHit / core : 0, yMin, yMax }
  })
  const largest = stats.reduce((a, b) => (b.share > a.share ? b : a))
  const keptIdx = stats.map((st, c) => (st === largest || (st.share >= 0.04 && st.sidesCovered >= 2 && st.corners >= 1 && st.corePresence < 0.08) ? c : -1)).filter((c) => c >= 0)
  const clusters = keptIdx.map((c) => {
    const st = stats[c]
    return { color: st.color, spread: st.spread, seedTol: st.seedTol, gapTol: clamp(6 + 1.2 * st.spread, 8, 20), yMin: st.yMin, yMax: st.yMax }
  })
  // étendue de luminance du décor sur le bord (10e–90e centile, échantillons du décor seulement) :
  // un bord uniforme (fond blanc) ne justifie aucune dérive, un dégradé visible au bord en justifie une
  const keptSet = new Set(keptIdx)
  const backLum = lum.filter((_, i) => keptSet.has(assign[i])).sort((a, b) => a - b)
  const borderRange = backLum.length ? backLum[Math.floor(0.9 * (backLum.length - 1))] - backLum[Math.floor(0.1 * (backLum.length - 1))] : 0
  // bruit local du décor : écart entre pixels voisins le long du bord (image floutée)
  const steps: number[] = []
  for (let x = 1; x < w; x++) { steps.push(colorDist(blur, x * 3, blur, (x - 1) * 3)); steps.push(colorDist(blur, ((h - 1) * w + x) * 3, blur, ((h - 1) * w + x - 1) * 3)) }
  for (let y = 1; y < h; y++) { steps.push(colorDist(blur, y * w * 3, blur, (y - 1) * w * 3)); steps.push(colorDist(blur, (y * w + w - 1) * 3, blur, ((y - 1) * w + w - 1) * 3)) }
  // gradient local (différences centrées) : un contour, même pâle, est une marche ; un dégradé
  // de décor (projecteur, vignettage) n'en est pas une. Seuil tiré du gradient du bord lui-même.
  const grad = new Float32Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const j = y * w + x
      const xl = (y * w + Math.max(0, x - 1)) * 3
      const xr = (y * w + Math.min(w - 1, x + 1)) * 3
      const yu = (Math.max(0, y - 1) * w + x) * 3
      const yd = (Math.min(h - 1, y + 1) * w + x) * 3
      grad[j] = Math.max(colorDist(blur, xr, blur, xl), colorDist(blur, yd, blur, yu)) / 2
    }
  }
  const borderGrad = samples.map((k) => grad[k / 3]).sort((a, b) => a - b)
  const p90 = borderGrad.length ? borderGrad[Math.floor(0.9 * (borderGrad.length - 1))] : 0
  return { clusters, noise: median(steps), gradTol: clamp(1.5 + 2 * p90, 3, 24), grad, borderRange }
}

/** Pourquoi une vue n'a pas donné de silhouette exploitable. */
export type MaskRefusal = 'empty' | 'fills-frame'

/**
 * Masque du sujet avec la raison d'un refus éventuel. Canal alpha s'il est utilisé
 * (exact : aucun refus de cadrage, une découpe peut toucher les quatre bords) ; sinon
 * le décor est retiré par croissance de région depuis le bord, sur l'image floutée.
 * Chaque pixel de décor transmet à ses voisins une couleur de référence qui suit
 * lentement les dégradés (projecteur, vignettage, mur puis sol) ; la croissance ne
 * franchit pas un contour (gradient local au-dessus de celui du bord), même pâle.
 * Le contour est ensuite affiné sur l'image nette et les interstices étroits du
 * décor (sous les bras, entre les jambes) sont rendus au fond.
 */
export function analyzeForeground(img: RGBAImage): { result: MaskResult | null; refusal: MaskRefusal | null } {
  const { width: w, height: h, data } = img
  const n = w * h
  if (w < 8 || h < 8 || data.length < n * 4) return { result: null, refusal: 'empty' }
  const out = new Uint8Array(n)
  let transparent = 0
  for (let i = 0; i < n; i++) if (data[i * 4 + 3] < 250) transparent++
  if (transparent > n * 0.02) {
    for (let i = 0; i < n; i++) out[i] = data[i * 4 + 3] >= 128 ? 1 : 0
    const mask: Mask = { width: w, height: h, data: out }
    const coverage = cleanMask(mask) / n
    return coverage < 0.01 ? { result: null, refusal: 'empty' } : { result: { mask, method: 'alpha', coverage }, refusal: null }
  }
  const radius = Math.max(1, Math.round(Math.min(w, h) / 256))
  const blur = blurRGB(data, w, h, radius)
  const { clusters, noise, gradTol, grad, borderRange } = backdropClusters(blur, w, h)
  const localTol = clamp(7 + 2 * noise, 9, 22)
  const maxSpread = Math.max(...clusters.map((c) => c.spread))
  // dérive permise de la couleur de référence loin des couleurs du décor : 18 sur un bord uniforme
  // (comme un seuil fixe : un objet pâle ou ombré sur fond blanc reste sujet), davantage quand le bord
  // montre lui-même un dégradé (projecteur, vignettage, mur puis sol)
  const driftTol = clamp(18 + maxSpread + 2.5 * borderRange, 18, 120)
  /** Couleur de décor la plus proche parmi celles dont la bande verticale contient la rangée y. */
  const nearestOf = (src: ArrayLike<number>, k: number, y: number) => {
    let best = Infinity
    let cl: BackdropCluster | null = null
    for (const c of clusters) {
      if (y < c.yMin || y > c.yMax) continue
      const d = colorDist(src, k, c.color, 0)
      if (d < best) { best = d; cl = c }
    }
    return { d: best, cl }
  }
  const background = new Uint8Array(n)
  const ref = new Float32Array(n * 3)
  const queue = new Int32Array(n)
  let head = 0
  let tail = 0
  const seed = (j: number) => {
    if (background[j]) return
    const nn = nearestOf(blur, j * 3, Math.floor(j / w))
    if (!nn.cl || nn.d >= nn.cl.seedTol) return
    background[j] = 1
    ref[j * 3] = blur[j * 3]; ref[j * 3 + 1] = blur[j * 3 + 1]; ref[j * 3 + 2] = blur[j * 3 + 2]
    queue[tail++] = j
  }
  for (let x = 0; x < w; x++) { seed(x); seed((h - 1) * w + x) }
  for (let y = 0; y < h; y++) { seed(y * w); seed(y * w + w - 1) }
  const grow = (i: number, j: number) => {
    if (background[j]) return
    if (grad[j] > gradTol) return
    if (colorDist(blur, j * 3, ref, i * 3) >= localTol) return
    if (nearestOf(blur, j * 3, Math.floor(j / w)).d >= driftTol) return
    background[j] = 1
    for (let q = 0; q < 3; q++) ref[j * 3 + q] = 0.8 * ref[i * 3 + q] + 0.2 * blur[j * 3 + q]
    queue[tail++] = j
  }
  const drain = (step: (i: number, j: number) => void) => {
    while (head < tail) {
      const j = queue[head++]
      const x = j % w
      const y = (j - x) / w
      if (x > 0) step(j, j - 1)
      if (x < w - 1) step(j, j + 1)
      if (y > 0) step(j, j - w)
      if (y < h - 1) step(j, j + w)
    }
  }
  drain(grow)
  // La croissance s'arrête avant la rampe du contour : on l'affine sur l'image nette, pixel de
  // bord par pixel de bord, en rattachant au fond les pixels plus proches du décor voisin que
  // du sujet (frange d'anticrénelage), sans jamais dépasser deux fois la tolérance locale.
  const sharpDist = (j: number, i: number) =>
    yccDist(data[j * 4] - ref[i * 3], data[j * 4 + 1] - ref[i * 3 + 1], data[j * 4 + 2] - ref[i * 3 + 2])
  const pixDist = (a: number, b: number) =>
    yccDist(data[a * 4] - data[b * 4], data[a * 4 + 1] - data[b * 4 + 1], data[a * 4 + 2] - data[b * 4 + 2])
  for (let pass = 0; pass <= radius + 1; pass++) {
    const flips: number[] = []
    for (let j = 0; j < n; j++) {
      if (background[j]) continue
      const x = j % w
      const y = (j - x) / w
      const nb = [x > 0 ? j - 1 : -1, x < w - 1 ? j + 1 : -1, y > 0 ? j - w : -1, y < h - 1 ? j + w : -1]
      for (let k = 0; k < 4; k++) {
        const i = nb[k]
        if (i < 0 || !background[i]) continue
        const toBack = sharpDist(j, i)
        const opposite = nb[k ^ 1]
        const toSubject = opposite >= 0 && !background[opposite] ? pixDist(j, opposite) : Infinity
        if (toBack < localTol || (toBack < 2 * localTol && toBack < toSubject)) { flips.push(j, i); break }
      }
    }
    if (!flips.length) break
    for (let f = 0; f < flips.length; f += 2) {
      background[flips[f]] = 1
      for (let q = 0; q < 3; q++) ref[flips[f] * 3 + q] = ref[flips[f + 1] * 3 + q]
    }
  }
  // Interstices étroits du décor (sous les bras, entre les jambes) : trop fins pour l'image floutée,
  // ils sont rendus au fond sur l'image nette s'ils ont presque exactement une couleur de décor.
  head = 0
  tail = 0
  for (let j = 0; j < n; j++) if (background[j]) queue[tail++] = j
  drain((_i, j) => {
    if (background[j]) return
    const nn = nearestOf(data, j * 4, Math.floor(j / w))
    if (!nn.cl || nn.d >= nn.cl.gapTol) return
    background[j] = 1
    queue[tail++] = j
  })
  for (let i = 0; i < n; i++) out[i] = background[i] ? 0 : 1
  const mask: Mask = { width: w, height: h, data: out }
  const coverage = cleanMask(mask) / n
  if (coverage < 0.01) return { result: null, refusal: 'empty' }
  // un « sujet » qui couvre presque tout le cadre, l'essentiel du pourtour ou les quatre côtés
  // remplit le cadre (gros plan, motif, image sans fond) : pas de silhouette exploitable
  let ring = 0
  let ringFg = 0
  const touch = [0, 0, 0, 0]
  for (let x = 0; x < w; x++) { ring += 2; ringFg += out[x] + out[(h - 1) * w + x]; touch[0] += out[x]; touch[1] += out[(h - 1) * w + x] }
  for (let y = 1; y < h - 1; y++) { ring += 2; ringFg += out[y * w] + out[y * w + w - 1]; touch[2] += out[y * w]; touch[3] += out[y * w + w - 1] }
  const sideLen = [w, w, h - 2, h - 2]
  if (coverage > 0.97 || ringFg / ring > 0.6 || touch.every((t, k) => t >= 0.03 * sideLen[k])) return { result: null, refusal: 'fills-frame' }
  return { result: { mask, method: 'background', coverage }, refusal: null }
}

/** Masque du sujet, ou null si l'image ne permet pas d'isoler un sujet (voir analyzeForeground). */
export function foregroundMask(img: RGBAImage): MaskResult | null {
  return analyzeForeground(img).result
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
  /** sens du profil retenu (+1 avant à droite de la vue de profil) et marge du vote couleur */
  profileSign?: 1 | -1
  profileVote?: number
  /** la vue de profil fournie a été écartée : même silhouette que la face */
  sideRejected?: boolean
  /** profil presque aussi large que la face : il ne peut qu'amincir, pas épaissir ni décaler */
  profileAmbiguous?: boolean
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
  return rowExtents(mask).half
}

/** Étendue horizontale par rangée : demi-largeur et centre (pixels), -1 si vide. */
export function rowExtents(mask: Mask): { half: Float32Array; center: Float32Array; left: Int32Array; right: Int32Array } {
  const { width: w, height: h, data } = mask
  const half = new Float32Array(h)
  const center = new Float32Array(h).fill(-1)
  const left = new Int32Array(h).fill(-1)
  const right = new Int32Array(h).fill(-1)
  for (let y = 0; y < h; y++) {
    let a = -1
    let b = -1
    for (let x = 0; x < w; x++) {
      if (!data[y * w + x]) continue
      if (a < 0) a = x
      b = x
    }
    if (a < 0) continue
    half[y] = (b - a + 1) / 2
    center[y] = (a + b) / 2
    left[y] = a
    right[y] = b
  }
  return { half, center, left, right }
}

function colorDistance(img: RGBAImage, x: number, y: number, rgb: [number, number, number]): number {
  const k = (y * img.width + x) * 4
  return Math.hypot(img.data[k] - rgb[0], img.data[k + 1] - rgb[1], img.data[k + 2] - rgb[2])
}

function meanRowColor(view: ViewInput, y: number): [number, number, number] | null {
  const { width: w } = view.mask
  let r = 0, g = 0, b = 0, n = 0
  for (let x = 0; x < w; x++) {
    if (!view.mask.data[y * w + x]) continue
    const k = (y * w + x) * 4
    r += view.img.data[k]; g += view.img.data[k + 1]; b += view.img.data[k + 2]; n++
  }
  return n ? [r / n, g / n, b / n] : null
}

/** Symétrie gauche-droite d'une silhouette cadrée sur sa boîte (IoU avec son miroir). */
export function mirrorSymmetry(m: Mask): number {
  const bd = maskBounds(m)
  if (!bd) return 0
  const w = bd.x1 - bd.x0 + 1
  const h = bd.y1 - bd.y0 + 1
  const N = 48
  let inter = 0, uni = 0
  for (let j = 0; j < N; j++) {
    const y = Math.min(bd.y1, Math.floor(bd.y0 + ((j + 0.5) / N) * h))
    for (let i = 0; i < N; i++) {
      const xa = Math.min(bd.x1, Math.floor(bd.x0 + ((i + 0.5) / N) * w))
      const xb = Math.min(bd.x1, Math.floor(bd.x0 + ((N - 1 - i + 0.5) / N) * w))
      const a = m.data[y * m.width + xa], b = m.data[y * m.width + xb]
      if (a && b) inter++
      if (a || b) uni++
    }
  }
  return uni ? inter / uni : 0
}

/**
 * Corrélation des largeurs par rangée (sur la hauteur cadrée) entre deux vues.
 * Une vue de face ou de trois quarts reproduit le profil de largeur de la face
 * (épaules, bras écartés…) ; un vrai profil a une autre répartition.
 */
export function rowWidthCorrelation(a: Mask, b: Mask): number {
  const ba = maskBounds(a)
  const bb = maskBounds(b)
  if (!ba || !bb) return 0
  const N = 48
  const prof = (m: Mask, bd: Bounds) => {
    const ext = rowExtents(m)
    const h = bd.y1 - bd.y0 + 1
    const out: number[] = []
    for (let j = 0; j < N; j++) out.push(ext.half[Math.min(bd.y1, Math.floor(bd.y0 + ((j + 0.5) / N) * h))])
    return out
  }
  const pa = prof(a, ba)
  const pb = prof(b, bb)
  const mean = (v: number[]) => v.reduce((x, y) => x + y, 0) / v.length
  const ma = mean(pa), mb = mean(pb)
  let num = 0, da = 0, db = 0
  for (let k = 0; k < N; k++) {
    num += (pa[k] - ma) * (pb[k] - mb)
    da += (pa[k] - ma) ** 2
    db += (pb[k] - mb) ** 2
  }
  return da > 0 && db > 0 ? num / Math.sqrt(da * db) : 0
}

/**
 * Ressemblance de deux silhouettes cadrées sur leur boîte : rapport des
 * proportions (largeur/hauteur de b sur celles de a) et IoU normalisée, miroir
 * compris. Sert à reconnaître une vue « de profil » qui est en fait une autre
 * vue de face — cas réel des générateurs qui suivent mal la consigne de vue.
 */
export function silhouetteSimilarity(a: Mask, b: Mask): { aspectRatio: number; iou: number; symmetryA: number; symmetryB: number; widthCorrelation: number } | null {
  const ba = maskBounds(a)
  const bb = maskBounds(b)
  if (!ba || !bb) return null
  const wa = ba.x1 - ba.x0 + 1, ha = ba.y1 - ba.y0 + 1
  const wb = bb.x1 - bb.x0 + 1, hb = bb.y1 - bb.y0 + 1
  const N = 48
  const grid = (m: Mask, bd: Bounds, w: number, h: number, mirror: boolean) => {
    const g = new Uint8Array(N * N)
    for (let j = 0; j < N; j++) {
      for (let i = 0; i < N; i++) {
        const u = mirror ? N - 1 - i : i
        const x = Math.min(bd.x1, Math.floor(bd.x0 + ((u + 0.5) / N) * w))
        const y = Math.min(bd.y1, Math.floor(bd.y0 + ((j + 0.5) / N) * h))
        g[j * N + i] = m.data[y * m.width + x]
      }
    }
    return g
  }
  const ga = grid(a, ba, wa, ha, false)
  const iouWith = (gb: Uint8Array) => {
    let inter = 0, uni = 0
    for (let k = 0; k < ga.length; k++) {
      if (ga[k] && gb[k]) inter++
      if (ga[k] || gb[k]) uni++
    }
    return uni ? inter / uni : 0
  }
  const iou = Math.max(iouWith(grid(b, bb, wb, hb, false)), iouWith(grid(b, bb, wb, hb, true)))
  return { aspectRatio: (wb / hb) / (wa / ha), iou, symmetryA: mirrorSymmetry(a), symmetryB: mirrorSymmetry(b), widthCorrelation: rowWidthCorrelation(a, b) }
}

/**
 * Sujets dont le producteur FLUX.2 audite le profil (`audit_multiview_consistency`) : un
 * personnage ou une créature vu de profil est nettement plus étroit que de face, donc un
 * « profil » presque aussi large que la face est un trois-quarts ou une autre vue de face.
 * Pour un objet (vase, casque, chaise, théière…), un profil aussi large que la face est normal.
 */
export function isCharacterKind(kind: string | null | undefined): boolean {
  return /character|humanoid|creature|quadruped|person|personnage|animal|body_part/i.test(kind ?? '')
}

/** Un « profil » de personnage qui a la silhouette et les proportions de la face n'apporte pas de profondeur. */
export function profileLooksLikeFront(front: Mask, side: Mask): boolean {
  const sim = silhouetteSimilarity(front, side)
  return Boolean(sim && sim.aspectRatio >= 0.85 && sim.aspectRatio <= 1.18 && sim.iou >= 0.6)
}

/**
 * Sens du profil : +1 si l'avant du sujet est à droite de l'image de profil,
 * -1 s'il est à gauche. Décidé par les couleurs quand la vue de dos existe
 * (le bord du profil qui ressemble à la face est l'avant), sinon par la
 * convention du rôle (vue « droite » : avant à droite ; « gauche » : à gauche).
 * Retourne aussi la marge du vote (0 = convention seule).
 */
export function profileOrientation(
  front: ViewInput,
  side: ViewInput,
  back: ViewInput | null,
  sideRole: 'droite' | 'gauche' = 'droite',
): { sign: 1 | -1; margin: number } {
  const fallback: 1 | -1 = sideRole === 'gauche' ? -1 : 1
  if (!back) return { sign: fallback, margin: 0 }
  const fb = maskBounds(front.mask), sb = maskBounds(side.mask), bb = maskBounds(back.mask)
  if (!fb || !sb || !bb) return { sign: fallback, margin: 0 }
  const ext = rowExtents(side.mask)
  let vote = 0
  let rows = 0
  const Hs = sb.y1 - sb.y0 + 1
  for (let ys = sb.y0; ys <= sb.y1; ys += 2) {
    const a = ext.left[ys], b = ext.right[ys]
    if (a < 0 || b - a < 6) continue
    const t = Hs > 1 ? (ys - sb.y0) / (Hs - 1) : 0
    const fy = Math.round(fb.y0 + t * (fb.y1 - fb.y0))
    const by = Math.round(bb.y0 + t * (bb.y1 - bb.y0))
    const fc = meanRowColor(front, fy)
    const bc = meanRowColor(back, by)
    if (!fc || !bc) continue
    const contrast = Math.hypot(fc[0] - bc[0], fc[1] - bc[1], fc[2] - bc[2])
    if (contrast < 24) continue // la face et le dos se ressemblent sur cette rangée : pas d'indice
    const inset = Math.max(1, Math.round((b - a) * 0.12))
    const leftFrontish = colorDistance(side.img, a + inset, ys, bc) - colorDistance(side.img, a + inset, ys, fc)
    const rightFrontish = colorDistance(side.img, b - inset, ys, bc) - colorDistance(side.img, b - inset, ys, fc)
    vote += Math.sign(rightFrontish - leftFrontish)
    rows++
  }
  if (rows < 4 || Math.abs(vote) < Math.max(2, rows * 0.15)) return { sign: fallback, margin: rows ? vote / rows : 0 }
  return { sign: vote > 0 ? 1 : -1, margin: vote / rows }
}

/**
 * Nuage de points 3D du sujet depuis ses vues. La base du sujet est posée en
 * y = -1, le sujet tient dans une boîte de 2 unités, centré en x et z.
 */
export function buildSilhouetteCloud(
  front: ViewInput,
  opts: { side?: ViewInput | null; back?: ViewInput | null; sideRole?: 'droite' | 'gauche'; maxPoints?: number; seed?: number; subjectKind?: string | null } = {},
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
  // décalage avant/arrière de chaque rangée lu sur le profil (tête qui avance, cheveux en arrière…)
  const rowOffset = new Float32Array(front.mask.height)
  let profileSign: 1 | -1 | undefined
  let profileVote: number | undefined
  let profileAmbiguous = false
  // règles de vue mal étiquetée réservées aux personnages et créatures (voir isCharacterKind)
  const character = isCharacterKind(opts.subjectKind)
  const sideRejected = Boolean(character && opts.side && profileLooksLikeFront(front.mask, opts.side.mask))
  const sb = opts.side && !sideRejected ? maskBounds(opts.side.mask) : null
  if (opts.side && sb) {
    const ext = rowExtents(opts.side.mask)
    const Hs = sb.y1 - sb.y0 + 1
    const sideWorldPerPx = (Hf * s) / Hs
    const sideCenter = (sb.x0 + sb.x1) / 2
    const backView = opts.back && maskBounds(opts.back.mask) ? opts.back : null
    const orient = profileOrientation(front, opts.side, backView, opts.sideRole ?? 'droite')
    // Personnage : un générateur qui suit mal la consigne de vue produit souvent un trois-quarts
    // étiqueté « profil ». Même règle que l'audit du producteur FLUX.2 (profil plus large que
    // 0,82 × la face, proportions rapportées à la hauteur) : la vue peut alors seulement amincir
    // le relief, jamais l'épaissir ni l'incliner. Un objet garde son vrai profil.
    const sim = silhouetteSimilarity(front.mask, opts.side.mask)
    profileAmbiguous = Boolean(character && sim && sim.aspectRatio > 0.82)
    const raw = new Float32Array(front.mask.height).fill(Number.NaN)
    const rawOff = new Float32Array(front.mask.height).fill(Number.NaN)
    let used = 0
    for (let y = fb.y0; y <= fb.y1; y++) {
      const t = Hf > 1 ? (y - fb.y0) / (Hf - 1) : 0
      const ys = Math.round(sb.y0 + t * (Hs - 1))
      const half = ext.half[ys] * sideWorldPerPx
      let maxRelief = 0
      for (let x = fb.x0; x <= fb.x1; x++) maxRelief = Math.max(maxRelief, reliefPx[y * w + x] * s)
      if (half > 0 && maxRelief > 0) {
        const k = clamp(half / maxRelief, 0.3, 3.5)
        raw[y] = profileAmbiguous ? Math.min(0.92, k) : k
        rawOff[y] = profileAmbiguous ? 0 : orient.sign * (ext.center[ys] - sideCenter) * sideWorldPerPx
        used++
      }
    }
    if (used >= Hf * 0.5) {
      method = 'hull'
      profileSign = orient.sign
      profileVote = Math.round(orient.margin * 100) / 100
      for (let y = fb.y0; y <= fb.y1; y++) {
        let sum = 0
        let off = 0
        let cnt = 0
        for (let k = -2; k <= 2; k++) {
          const v = raw[y + k]
          if (y + k >= fb.y0 && y + k <= fb.y1 && Number.isFinite(v)) { sum += v; off += rawOff[y + k]; cnt++ }
        }
        rowScale[y] = cnt ? sum / cnt : 0.92
        rowOffset[y] = cnt ? off / cnt : 0
      }
    }
  }

  let fgCount = 0
  for (let y = fb.y0; y <= fb.y1; y++) for (let x = fb.x0; x <= fb.x1; x++) fgCount += fm[y * w + x]
  const maxPoints = Math.max(2000, opts.maxPoints ?? 30000)
  const perPixel = 3.4 // face + dos + intérieur + parois
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
      const zc = rowOffset[y]
      maxDepth = Math.max(maxDepth, depth)
      const fc: [number, number, number] = [fd[i * 4] / 255, fd[i * 4 + 1] / 255, fd[i * 4 + 2] / 255]
      const edge = dt[i] < 1.25 ? 2 : 0
      pos.push(wx, wy, zc + depth); col.push(fc[0], fc[1], fc[2]); kind.push(edge)
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
      pos.push(wx, wy, zc - depth); col.push(bc[0], bc[1], bc[2]); kind.push(edge)
      if (depth > 0.01 && rand() < 0.3) {
        const z = (rand() * 2 - 1) * depth * 0.85
        pos.push(wx, wy, zc + z); col.push(fc[0] * 0.6, fc[1] * 0.6, fc[2] * 0.6); kind.push(1)
      }
      // parois : entre deux échantillons voisins dont la profondeur diffère
      // fortement (flancs du corps, contour), la surface est complétée pour
      // que l'hologramme reste plein vu de profil
      const step = stride * s
      for (const [nx, ny] of [[x + stride, y], [x, y + stride]] as const) {
        const inside = nx <= fb.x1 && ny <= fb.y1 && fm[ny * w + nx]
        const d2 = inside ? reliefPx[ny * w + nx] * s * rowScale[ny] : 0
        const z2 = inside ? rowOffset[ny] : zc
        const gap = Math.abs(depth - d2)
        if (gap <= step * 1.5) continue
        const k = Math.min(24, Math.floor(gap / step))
        for (let j = 1; j < k; j++) {
          const f = j / k
          const ix = wx + (nx - x) * s * 0.5
          const iy = wy - (ny - y) * s * 0.5
          const dd = depth + (d2 - depth) * f
          const cz = zc + (z2 - zc) * f
          pos.push(ix, iy, cz + dd); col.push(fc[0], fc[1], fc[2]); kind.push(0)
          pos.push(ix, iy, cz - dd); col.push(bc[0], bc[1], bc[2]); kind.push(0)
        }
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
    profileSign,
    profileVote,
    sideRejected,
    profileAmbiguous,
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
