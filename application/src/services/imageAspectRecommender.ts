// Recommandeur d'aspect ratio + optimiseur dimensions SDXL. Si l'user
// décrit "un portrait", on suggère 2:3 (768×1152) ; "un paysage", 16:9 ;
// "un timbre-poste", 1:1.
//
// Heuristique multi-signal :
//   - mots-clés explicites (portrait, paysage, panoramique, carré)
//   - sujet typique (architecture haute → 9:16, scène large → 21:9)
//   - format de sortie (TikTok → 9:16, YouTube → 16:9, Instagram → 1:1)
//   - contraintes utilisateur explicites (#paysage, --ar 16:9)
//
// Sortie : recommendation classée par confidence.

import type { AspectRatio } from './imagePromptBuilder.ts'

export type AspectRecommendation = {
  ratio: AspectRatio
  width: number
  height: number
  confidence: number
  reason: string
}

// Mapping standard SDXL — multiples de 64, total ~= 1024² (mégapixels stable).
const SDXL_DIMS: Record<AspectRatio, { width: number; height: number }> = {
  '1:1': { width: 1024, height: 1024 },
  '3:2': { width: 1216, height: 832 },
  '2:3': { width: 832, height: 1216 },
  '16:9': { width: 1344, height: 768 },
  '9:16': { width: 768, height: 1344 },
  '4:3': { width: 1152, height: 896 },
  '21:9': { width: 1536, height: 640 },
}

const PORTRAIT_KEYWORDS = [
  'portrait', 'visage', 'face', 'tête', 'buste', 'tour', 'gratte-ciel',
  'cathédrale', 'silhouette debout', 'personnage', 'mannequin', 'tour Eiffel',
  'arbre élancé', 'verticale', 'cascade', 'mince', 'élancé',
]

const LANDSCAPE_KEYWORDS = [
  'paysage', 'horizon', 'panorama', 'vista', 'plaine', 'champ', 'lac',
  'mer', 'océan', 'plage', 'désert', 'savane', 'montagne', 'chaîne',
  'large vue', 'panoramique', 'horizontal',
]

const PANORAMIC_KEYWORDS = [
  'panoramique extra-large', 'cinemascope', 'cinematic',
  'défilé', 'ligne d horizon', '21:9', 'ultrawide',
]

const SQUARE_KEYWORDS = [
  'timbre', 'logo', 'icône', 'icon', 'avatar', 'profile picture',
  'pochette d album', 'album cover', 'square', 'carré', 'instagram post',
]

const VERTICAL_PLATFORM_KEYWORDS = [
  'tiktok', 'reels', 'shorts', 'story', 'instagram story',
]
const WIDE_PLATFORM_KEYWORDS = [
  'youtube', 'twitch', 'cinéma', 'tv',
]

function normalise(text: string): string {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function countKeywords(text: string, list: string[]): number {
  const n = normalise(text)
  let count = 0
  for (const kw of list) {
    if (n.includes(normalise(kw))) count += 1
  }
  return count
}

function explicit(text: string): AspectRatio | null {
  // Patterns --ar X:Y ou #ratio explicit.
  const m = /(?:--ar\s+|#)(\d+):(\d+)/.exec(text)
  if (m) {
    const w = parseInt(m[1], 10), h = parseInt(m[2], 10)
    if (w === h) return '1:1'
    if (w === 16 && h === 9) return '16:9'
    if (w === 9 && h === 16) return '9:16'
    if (w === 3 && h === 2) return '3:2'
    if (w === 2 && h === 3) return '2:3'
    if (w === 4 && h === 3) return '4:3'
    if (w === 21 && h === 9) return '21:9'
  }
  return null
}

/**
 * Recommandation principale. Retourne le candidat le plus confident +
 * alternatives classées.
 */
export function recommendAspectRatio(subject: string): AspectRecommendation[] {
  const candidates = new Map<AspectRatio, { score: number; reasons: string[] }>()
  const add = (r: AspectRatio, score: number, reason: string) => {
    if (!candidates.has(r)) candidates.set(r, { score: 0, reasons: [] })
    const cur = candidates.get(r)!
    cur.score += score
    cur.reasons.push(reason)
  }

  // Explicite : priorité absolue.
  const ex = explicit(subject)
  if (ex) {
    add(ex, 100, 'paramètre explicite --ar')
  }

  const portrait = countKeywords(subject, PORTRAIT_KEYWORDS)
  const landscape = countKeywords(subject, LANDSCAPE_KEYWORDS)
  const panoramic = countKeywords(subject, PANORAMIC_KEYWORDS)
  const square = countKeywords(subject, SQUARE_KEYWORDS)
  const vertical = countKeywords(subject, VERTICAL_PLATFORM_KEYWORDS)
  const wide = countKeywords(subject, WIDE_PLATFORM_KEYWORDS)

  if (portrait > 0) add('2:3', 10 * portrait, `${portrait} mot(s)-clé portrait`)
  if (landscape > 0) add('3:2', 10 * landscape, `${landscape} mot(s)-clé paysage`)
  if (panoramic > 0) add('21:9', 15 * panoramic, `${panoramic} mot(s)-clé panoramique`)
  if (square > 0) add('1:1', 12 * square, `${square} mot(s)-clé carré/logo`)
  if (vertical > 0) add('9:16', 20 * vertical, 'plateforme vertical')
  if (wide > 0) add('16:9', 15 * wide, 'plateforme widescreen')

  // Fallback : si rien matché, propose 1:1.
  if (candidates.size === 0) {
    add('1:1', 5, 'fallback carré (rien de spécifique détecté)')
  }

  const sorted = Array.from(candidates.entries())
    .map(([ratio, data]) => ({
      ratio,
      width: SDXL_DIMS[ratio].width,
      height: SDXL_DIMS[ratio].height,
      confidence: Math.min(1, data.score / 30),
      reason: data.reasons.join(' • '),
    }))
    .sort((a, b) => b.confidence - a.confidence)

  return sorted
}

/**
 * Suggère le meilleur ratio + retourne aussi la liste des alternatives.
 */
export function bestAspectRatio(subject: string): AspectRecommendation {
  return recommendAspectRatio(subject)[0]
}

/**
 * Détermine si le subject contient une référence à un produit/branding
 * spécifique qui dicte un ratio particulier (LinkedIn cover, Twitch banner…).
 */
export type BrandingPreset = {
  name: string
  ratio: AspectRatio
  width: number
  height: number
  /** Dimensions "officielles" pour cette plateforme (en fait utile pour upscale). */
  officialWidth: number
  officialHeight: number
}

const BRANDING_PRESETS: Array<{ pattern: RegExp; preset: BrandingPreset }> = [
  {
    pattern: /linkedin (banner|cover|bannière)/i,
    preset: { name: 'LinkedIn banner', ratio: '21:9', ...SDXL_DIMS['21:9'], officialWidth: 1584, officialHeight: 396 },
  },
  {
    pattern: /youtube (banner|bannière|art)/i,
    preset: { name: 'YouTube channel art', ratio: '16:9', ...SDXL_DIMS['16:9'], officialWidth: 2560, officialHeight: 1440 },
  },
  {
    pattern: /twitch (banner|cover)/i,
    preset: { name: 'Twitch banner', ratio: '3:2', ...SDXL_DIMS['3:2'], officialWidth: 1200, officialHeight: 480 },
  },
  {
    pattern: /thumbnail youtube|miniature youtube/i,
    preset: { name: 'YouTube thumbnail', ratio: '16:9', ...SDXL_DIMS['16:9'], officialWidth: 1280, officialHeight: 720 },
  },
  {
    pattern: /spotify cover|album cover|pochette/i,
    preset: { name: 'Album cover', ratio: '1:1', ...SDXL_DIMS['1:1'], officialWidth: 3000, officialHeight: 3000 },
  },
  {
    pattern: /tiktok (cover|profile|vidéo|video)/i,
    preset: { name: 'TikTok video', ratio: '9:16', ...SDXL_DIMS['9:16'], officialWidth: 1080, officialHeight: 1920 },
  },
]

export function detectBrandingPreset(subject: string): BrandingPreset | null {
  for (const { pattern, preset } of BRANDING_PRESETS) {
    if (pattern.test(subject)) return preset
  }
  return null
}
