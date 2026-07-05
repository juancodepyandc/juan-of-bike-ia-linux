// Texture atlas planner : packe N textures rectangulaires dans une seule
// texture pour réduire les draw calls (1 binding GPU au lieu de N). Algo
// MaxRects (Jukka Jylänki, 2010) qui produit un packing très proche du
// gourmand-optimum.
//
// Sortie : positions + scales UV pour remapper chaque texture vers sa
// place dans l'atlas, plus le ratio d'occupation.

export type TextureInput = {
  id: string
  width: number
  height: number
}

export type TextureSlot = {
  id: string
  /** Coordonnées dans l'atlas (pixels). */
  x: number
  y: number
  width: number
  height: number
  /** UV remap pour le mesh : multiplier + offset. */
  uvOffsetX: number
  uvOffsetY: number
  uvScaleX: number
  uvScaleY: number
  /** True si rotation 90° appliquée pour mieux packer. */
  rotated: boolean
}

export type AtlasResult = {
  atlasWidth: number
  atlasHeight: number
  slots: TextureSlot[]
  /** Textures qui n'ont pas pu rentrer (skip). */
  unplaced: string[]
  /** Ratio d'utilisation = aire occupée / aire atlas. */
  occupancyRatio: number
}

export type AtlasOptions = {
  /** Taille max de l'atlas (pixels). Default 4096 (limite WebGL). */
  maxSize?: number
  /** Padding entre textures (px). */
  padding?: number
  /** Autoriser la rotation 90°. */
  allowRotation?: boolean
}

type FreeRect = { x: number; y: number; width: number; height: number }

/**
 * MaxRects packing avec heuristique "best short side fit" — la meilleure
 * en occupation moyenne selon le benchmark Jylänki.
 */
export function packAtlas(textures: TextureInput[], opts: AtlasOptions = {}): AtlasResult {
  const maxSize = opts.maxSize ?? 4096
  const padding = opts.padding ?? 2
  const allowRotation = opts.allowRotation ?? true

  // Étape 1 : choisis une taille d'atlas initiale = puissance de 2 supérieure
  // au max(largeur, hauteur) de toutes les textures, puis itère jusqu'à ce
  // que tout rentre OU on atteigne maxSize.
  let atlasSize = 256
  let result: AtlasResult | null = null
  while (atlasSize <= maxSize) {
    const tryResult = tryPack(textures, atlasSize, atlasSize, padding, allowRotation)
    if (tryResult.unplaced.length === 0) {
      result = tryResult
      break
    }
    atlasSize *= 2
  }
  if (!result) {
    // Garde le dernier essai (avec unplaced).
    result = tryPack(textures, maxSize, maxSize, padding, allowRotation)
  }
  return result
}

function tryPack(textures: TextureInput[], atlasW: number, atlasH: number, padding: number, allowRotation: boolean): AtlasResult {
  // Tri par max(width, height) décroissant.
  const sorted = [...textures].sort((a, b) => Math.max(b.width, b.height) - Math.max(a.width, a.height))
  const freeRects: FreeRect[] = [{ x: 0, y: 0, width: atlasW, height: atlasH }]
  const slots: TextureSlot[] = []
  const unplaced: string[] = []
  let usedArea = 0

  for (const tex of sorted) {
    const w = tex.width + padding
    const h = tex.height + padding
    const placement = findBestPlacement(freeRects, w, h, allowRotation)
    if (!placement) {
      unplaced.push(tex.id)
      continue
    }
    const realW = placement.rotated ? tex.height : tex.width
    const realH = placement.rotated ? tex.width : tex.height
    slots.push({
      id: tex.id,
      x: placement.rect.x,
      y: placement.rect.y,
      width: realW,
      height: realH,
      uvOffsetX: placement.rect.x / atlasW,
      uvOffsetY: placement.rect.y / atlasH,
      uvScaleX: realW / atlasW,
      uvScaleY: realH / atlasH,
      rotated: placement.rotated,
    })
    usedArea += realW * realH

    // Subdivise les free rects : retire celui utilisé, ajoute les 2 morceaux
    // restants (droite + bas), puis nettoie les rectangles enfermés.
    const placedRect: FreeRect = { x: placement.rect.x, y: placement.rect.y, width: w, height: h }
    splitFreeRects(freeRects, placedRect)
    pruneFreeRects(freeRects)
  }

  return {
    atlasWidth: atlasW,
    atlasHeight: atlasH,
    slots,
    unplaced,
    occupancyRatio: usedArea / (atlasW * atlasH),
  }
}

function findBestPlacement(freeRects: FreeRect[], w: number, h: number, allowRotation: boolean): { rect: FreeRect; rotated: boolean } | null {
  let best: { rect: FreeRect; rotated: boolean; score: number } | null = null
  for (const r of freeRects) {
    if (r.width >= w && r.height >= h) {
      const shortSide = Math.min(r.width - w, r.height - h)
      if (!best || shortSide < best.score) {
        best = { rect: { x: r.x, y: r.y, width: w, height: h }, rotated: false, score: shortSide }
      }
    }
    if (allowRotation && r.width >= h && r.height >= w) {
      const shortSide = Math.min(r.width - h, r.height - w)
      if (!best || shortSide < best.score) {
        best = { rect: { x: r.x, y: r.y, width: h, height: w }, rotated: true, score: shortSide }
      }
    }
  }
  return best ? { rect: best.rect, rotated: best.rotated } : null
}

function splitFreeRects(freeRects: FreeRect[], used: FreeRect): void {
  const newRects: FreeRect[] = []
  for (let i = 0; i < freeRects.length; i += 1) {
    const free = freeRects[i]
    if (!rectsIntersect(used, free)) {
      newRects.push(free)
      continue
    }
    // Split : produit jusqu'à 4 sous-rectangles autour de `used`.
    if (used.x > free.x) {
      newRects.push({ x: free.x, y: free.y, width: used.x - free.x, height: free.height })
    }
    if (used.x + used.width < free.x + free.width) {
      newRects.push({ x: used.x + used.width, y: free.y, width: free.x + free.width - (used.x + used.width), height: free.height })
    }
    if (used.y > free.y) {
      newRects.push({ x: free.x, y: free.y, width: free.width, height: used.y - free.y })
    }
    if (used.y + used.height < free.y + free.height) {
      newRects.push({ x: free.x, y: used.y + used.height, width: free.width, height: free.y + free.height - (used.y + used.height) })
    }
  }
  freeRects.length = 0
  freeRects.push(...newRects)
}

function rectsIntersect(a: FreeRect, b: FreeRect): boolean {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y
}

function pruneFreeRects(freeRects: FreeRect[]): void {
  // Retire les rects qui sont entièrement contenus dans un autre.
  for (let i = freeRects.length - 1; i >= 0; i -= 1) {
    for (let j = 0; j < freeRects.length; j += 1) {
      if (i === j) continue
      if (rectContains(freeRects[j], freeRects[i])) {
        freeRects.splice(i, 1)
        break
      }
    }
  }
}

function rectContains(outer: FreeRect, inner: FreeRect): boolean {
  return outer.x <= inner.x && outer.y <= inner.y
    && outer.x + outer.width >= inner.x + inner.width
    && outer.y + outer.height >= inner.y + inner.height
}

/**
 * Calcule le savings d'utiliser l'atlas vs binder N textures séparées.
 * Hypothèses : binding coûte ~ N appels GPU = X ms à 60fps, atlas = 1.
 */
export function atlasGains(result: AtlasResult): {
  drawCallsAvant: number
  drawCallsApres: number
  reductionPct: number
  warning: string | null
} {
  const before = result.slots.length + result.unplaced.length
  const after = result.unplaced.length + (result.slots.length > 0 ? 1 : 0)
  const reduction = before > 0 ? (1 - after / before) * 100 : 0
  let warning: string | null = null
  if (result.unplaced.length > 0) warning = `${result.unplaced.length} texture(s) trop grande(s) pour l'atlas — restent séparées.`
  else if (result.occupancyRatio < 0.5) warning = `Occupation ${(result.occupancyRatio * 100).toFixed(0)}% — atlas surdimensionné, gaspille de la VRAM.`
  return {
    drawCallsAvant: before,
    drawCallsApres: after,
    reductionPct: reduction,
    warning,
  }
}
