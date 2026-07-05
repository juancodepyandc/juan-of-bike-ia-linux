export type ImageBrief = {
  subject: string
  context?: string
  style?: ImageStyle
  composition?: Composition
  lighting?: Lighting
  mood?: Mood
  paletteHints?: string[]
  negativeHints?: string[]
  exactText?: string[]
  countHints?: string[]
  layoutHints?: string[]
  backgroundHints?: string[]
  aspectRatio?: AspectRatio
  highResolution?: boolean
}

export type ImageStyle =
  | 'photorealistic'
  | 'cinematic'
  | 'studio-product'
  | 'anime-clean'
  | 'manga-bw'
  | 'aquarelle'
  | 'oil-painting'
  | 'isometric-3d'
  | 'pixel-art'
  | 'low-poly-3d'
  | 'flat-illustration'
  | 'concept-art'
  | 'technical-schema'
  | 'comic-american'

export const IMAGE_STYLES: ImageStyle[] = [
  'photorealistic',
  'cinematic',
  'studio-product',
  'anime-clean',
  'manga-bw',
  'aquarelle',
  'oil-painting',
  'isometric-3d',
  'pixel-art',
  'low-poly-3d',
  'flat-illustration',
  'concept-art',
  'technical-schema',
  'comic-american',
]

export type Composition =
  | 'centered'
  | 'rule-of-thirds'
  | 'symmetrical'
  | 'dutch-angle'
  | 'overhead'
  | 'wide-shot'
  | 'close-up'
  | 'extreme-close-up'

export type Lighting =
  | 'golden-hour'
  | 'blue-hour'
  | 'overcast-soft'
  | 'harsh-noon'
  | 'studio-three-point'
  | 'rim-light'
  | 'rembrandt'
  | 'volumetric-fog'
  | 'neon-cyberpunk'

export type Mood =
  | 'serene'
  | 'dramatic'
  | 'mysterious'
  | 'joyful'
  | 'somber'
  | 'epic'
  | 'cozy'
  | 'futuristic'
  | 'nostalgic'

export type AspectRatio = '1:1' | '3:2' | '2:3' | '16:9' | '9:16' | '4:3' | '21:9'

type StyleProfile = {
  qualifiers: string[]
  negative: string[]
  checklist: string[]
  engineHints: string[]
}

const STYLE_PROFILES: Record<ImageStyle, StyleProfile> = {
  photorealistic: {
    qualifiers: ['hyperrealistic', 'sharp focus', '8k', 'shot on Sony A7R IV', 'detailed skin texture', 'real lens imperfections', 'natural shadows'],
    negative: ['cartoon', '3d render', 'anime', 'low quality', 'blurry', 'extra fingers', 'malformed hands', 'watermark', 'signature', 'plastic skin', 'airbrushed face'],
    checklist: ['materiaux plausibles', 'textures fines visibles', 'ombres coherentes', 'pas de peau plastique'],
    engineHints: ['FLUX realistic: garder un sujet principal, details naturels, pas de lissage IA'],
  },
  cinematic: {
    qualifiers: ['anamorphic lens', 'film grain', 'wide cinematographic frame', 'color graded', 'motivated lighting', 'depth staging'],
    negative: ['flat', 'amateur', 'low contrast', 'over-saturated', 'jpeg artifacts', 'random text', 'multi-panel layout'],
    checklist: ['lumiere motivee', 'profondeur lisible', 'cadre cinema unique'],
    engineHints: ['FLUX cinematic: une seule vue continue, contraste controle, pas de montage en vignettes'],
  },
  'studio-product': {
    qualifiers: ['white seamless background', 'softbox lighting', 'commercial product photography', 'pristine', 'crisp product edges', 'accurate material finish'],
    negative: ['cluttered background', 'shadows on backdrop', 'noise', 'reflections of room', 'warped product shape'],
    checklist: ['silhouette produit nette', 'materiaux corrects', 'fond propre'],
    engineHints: ['FLUX product: sujet isole, proportions fideles, pas de decor parasite'],
  },
  'anime-clean': {
    qualifiers: ['anime key visual', 'clean line art', 'cel shading', 'Studio Ghibli inspired', 'on-model face', 'readable costume details'],
    negative: ['photorealistic', 'realistic skin pores', 'gritty', 'horror', 'low quality', 'muddy texture', 'off-model face'],
    checklist: ['linework stable', 'cel shading propre', 'identite personnage conservee'],
    engineHints: ['FLUX anime: contours propres, visage stable, pas de rendu photo'],
  },
  'manga-bw': {
    qualifiers: ['black and white', 'manga panel', 'screentone', 'ink wash', 'high contrast', 'expressive ink lines'],
    negative: ['color', 'pastel', '3d render', 'photograph', 'soft airbrush', 'muddy gray wash'],
    checklist: ['noir et blanc strict', 'trames lisibles', 'encrage propre'],
    engineHints: ['FLUX manga: contraste clair, trames propres, pas de couleur si non demandee'],
  },
  aquarelle: {
    qualifiers: ['watercolor painting', 'wet on wet', 'soft paper texture', 'gentle pigments', 'transparent washes', 'granulating pigment edges'],
    negative: ['digital flat', 'vector', 'hard outlines', 'CGI', 'plastic gradient', 'oil impasto'],
    checklist: ['papier visible', 'lavis transparent', 'bords pigmentes naturels'],
    engineHints: ['FLUX watercolor: texture papier, douceur, pas de rendu vectoriel'],
  },
  'oil-painting': {
    qualifiers: ['oil on canvas', 'impasto strokes', 'classic chiaroscuro', 'Caravaggio inspired', 'visible brushwork', 'varnished depth'],
    negative: ['photograph', 'digital flat', 'low detail', 'vector', 'watercolor wash'],
    checklist: ['coups de pinceau visibles', 'matiere huile', 'chiaroscuro coherent'],
    engineHints: ['FLUX oil: privilegier matiere et profondeur, pas de photo lisse'],
  },
  'isometric-3d': {
    qualifiers: ['isometric view', 'low poly', 'soft gradients', 'tilted at 30 degrees', 'orthographic camera', 'clean miniature scene'],
    negative: ['perspective distortion', 'photo', 'realism', 'wide angle lens', 'messy shadows'],
    checklist: ['camera orthographique', 'angles isometriques', 'silhouettes lisibles'],
    engineHints: ['FLUX iso: orthographique, volumes propres, pas de perspective photo'],
  },
  'pixel-art': {
    qualifiers: ['16-bit pixel art', '32x32 sprite', 'limited palette', 'pixel perfect edges', 'nearest-neighbor upscale', 'hard 1px square pixels', 'indexed 16 color palette', 'Aseprite style sprite readability'],
    negative: ['anti-aliasing', 'smooth gradients', 'photograph', '3d render', 'vector art', 'painterly brush strokes', 'blur', 'subpixel smoothing', 'high resolution texture', 'soft edges', 'AI smoothing'],
    checklist: ['grille de pixels visible', 'aucun antialiasing', 'palette limitee', 'silhouette lisible a petite taille'],
    engineHints: ['FLUX pixel: decrire une image basse resolution logique, puis agrandir en nearest-neighbor'],
  },
  'low-poly-3d': {
    qualifiers: ['low poly 3d render', 'flat shading', 'pastel palette', 'geometric', 'faceted surfaces', 'clean topology'],
    negative: ['high poly', 'subdivision', 'photorealistic', 'smooth sculpting', 'noisy texture'],
    checklist: ['facettes visibles', 'formes geometriques propres', 'palette controlee'],
    engineHints: ['FLUX low-poly: facettes nettes, pas de photorealisme'],
  },
  'flat-illustration': {
    qualifiers: ['flat 2d illustration', 'minimal shadows', 'crisp shapes', 'editorial vector style', 'clean negative space'],
    negative: ['photoreal', 'volumetric', 'detailed skin', '3d render', 'painterly texture'],
    checklist: ['formes nettes', 'ombres minimales', 'composition editoriale'],
    engineHints: ['FLUX flat: aplats propres, pas de volume photo'],
  },
  'concept-art': {
    qualifiers: ['matte painting', 'detailed environment', 'wide vista', 'epic scale', 'production concept art', 'clear focal path'],
    negative: ['amateur', 'unfinished', 'sketch lines visible', 'random clutter', 'flat lighting'],
    checklist: ['lecture de scene', 'echelle claire', 'direction artistique forte'],
    engineHints: ['FLUX concept: composition de production, pas de fouillis'],
  },
  'technical-schema': {
    qualifiers: ['line drawing', 'cross-section', 'labeled parts', 'mechanical blueprint', 'orthographic clarity', 'precise line hierarchy'],
    negative: ['photo', 'painting', 'shading', 'decorative clutter', 'illegible labels', 'perspective distortion'],
    checklist: ['lignes lisibles', 'hierarchie claire', 'vue technique comprehensible'],
    engineHints: ['FLUX schema: rester propre et lisible, eviter les labels inventes trop longs'],
  },
  'comic-american': {
    qualifiers: ['comic book', 'bold outlines', 'halftone shading', 'dynamic panel', 'high impact pose', 'controlled ink shadows'],
    negative: ['photoreal', '3d render', 'soft pastel', 'muddy anatomy', 'low contrast'],
    checklist: ['contours forts', 'halftone propre', 'action lisible'],
    engineHints: ['FLUX comic: contraste graphique, pose claire, pas de rendu photo'],
  },
}

const STYLE_EXECUTION_QUALIFIERS: Record<ImageStyle, string[]> = {
  photorealistic: ['physically plausible camera exposure', 'natural imperfections preserved', 'real-world material response'],
  cinematic: ['single continuous movie frame', 'motivated key light and fill light', 'foreground midground background depth'],
  'studio-product': ['commercial catalog cleanliness', 'true product geometry', 'controlled reflections and contact shadow'],
  'anime-clean': ['stable character design sheet fidelity', 'crisp cel shade separation', 'clean color blocks without muddy gradients'],
  'manga-bw': ['ink hierarchy from thick silhouette to fine detail', 'screen tones aligned with form', 'print-ready black and white contrast'],
  aquarelle: ['transparent pigment layering', 'paper grain visible through washes', 'natural water blooms and granulation'],
  'oil-painting': ['directional brushwork follows form', 'canvas grain and impasto highlights', 'deep layered color glazing'],
  'isometric-3d': ['orthographic camera discipline', 'consistent 30 degree isometric axes', 'miniature-scale readable volumes'],
  'pixel-art': ['integer pixel clusters', 'hand-placed highlights and shadows', 'sprite readable after nearest-neighbor upscale'],
  'low-poly-3d': ['intentional faceted topology', 'flat shaded planes', 'clean silhouette without subdivision smoothing'],
  'flat-illustration': ['vector-like shape economy', 'balanced negative space', 'editorial color hierarchy'],
  'concept-art': ['production-ready design intent', 'clear focal path and scale cues', 'material and atmosphere callouts'],
  'technical-schema': ['orthographic readability', 'line-weight hierarchy', 'parts separated enough to understand function'],
  'comic-american': ['bold ink contour', 'halftone or cel shadow discipline', 'dynamic action silhouette'],
}

const COMPOSITION_QUALIFIERS: Record<Composition, string> = {
  centered: 'centered composition, subject in middle of frame',
  'rule-of-thirds': 'rule of thirds composition, off-center subject',
  symmetrical: 'symmetrical, mirrored layout',
  'dutch-angle': 'dutch angle, tilted horizon, dynamic',
  overhead: 'top-down overhead shot, bird eye view',
  'wide-shot': 'wide establishing shot, full environment visible',
  'close-up': 'close-up shot, subject filling frame',
  'extreme-close-up': 'extreme close-up, intricate detail',
}

const LIGHTING_QUALIFIERS: Record<Lighting, string> = {
  'golden-hour': 'golden hour lighting, warm sunset glow, long shadows',
  'blue-hour': 'blue hour, twilight, deep blue sky, cool tones',
  'overcast-soft': 'overcast sky, soft diffused light, no harsh shadows',
  'harsh-noon': 'harsh noon sun, high contrast, sharp shadows',
  'studio-three-point': 'three-point studio lighting, key + fill + rim',
  'rim-light': 'strong rim light, subject outlined by backlight',
  rembrandt: 'rembrandt lighting, triangle of light on the cheek',
  'volumetric-fog': 'volumetric fog, light rays cutting through atmosphere',
  'neon-cyberpunk': 'cyberpunk neon lights, magenta and cyan glow, rainy reflections',
}

const MOOD_QUALIFIERS: Record<Mood, string> = {
  serene: 'serene mood, calm atmosphere',
  dramatic: 'dramatic, intense, high stakes',
  mysterious: 'mysterious, enigmatic, shadowed',
  joyful: 'joyful, bright, uplifting',
  somber: 'somber, melancholic, muted',
  epic: 'epic scale, grand, awe-inspiring',
  cozy: 'cozy, warm, intimate',
  futuristic: 'futuristic, sleek, cutting-edge',
  nostalgic: 'nostalgic, faded film, vintage tones',
}

const AR_RESOLUTIONS: Record<AspectRatio, { width: number; height: number }> = {
  '1:1': { width: 1024, height: 1024 },
  '3:2': { width: 1216, height: 832 },
  '2:3': { width: 832, height: 1216 },
  '16:9': { width: 1344, height: 768 },
  '9:16': { width: 768, height: 1344 },
  '4:3': { width: 1152, height: 896 },
  '21:9': { width: 1536, height: 640 },
}

export type BuiltPrompt = {
  positive: string
  negative: string
  width: number
  height: number
  exif: {
    description: string
    software: string
    artist: string
    userComment: string
  }
  upscalePlan: { kind: 'realesrgan-x4' | 'pixel-nearest-x4' | 'none'; targetWidth: number; targetHeight: number }
  qualityChecklist: string[]
  styleGuide: {
    style: ImageStyle | 'auto'
    engineHints: string[]
    mustHave: string[]
    avoid: string[]
  }
  fidelityContract: {
    mustPreserve: string[]
    mustAvoid: string[]
    exactText: string[]
    counts: string[]
    layout: string[]
  }
  renderProfile: {
    logicalCanvas: { width: number; height: number }
    outputCanvas: { width: number; height: number }
    upscaleMethod: 'none' | 'realesrgan-x4' | 'nearest-neighbor-x4'
    passes: string[]
  }
}

export function buildPrompt(brief: ImageBrief): BuiltPrompt {
  const style = brief.style
  const profile = style ? STYLE_PROFILES[style] : undefined
  const parts: string[] = []
  const subject = brief.subject.trim()

  if (subject) parts.push(subject)
  if (brief.context) parts.push(brief.context.trim())
  parts.push(...buildConstraintPositiveParts(brief))
  if (brief.composition) parts.push(COMPOSITION_QUALIFIERS[brief.composition])
  if (brief.lighting) parts.push(LIGHTING_QUALIFIERS[brief.lighting])
  if (brief.mood) parts.push(MOOD_QUALIFIERS[brief.mood])
  if (profile) {
    parts.push(...profile.qualifiers)
    parts.push(...STYLE_EXECUTION_QUALIFIERS[style!])
  }
  if (brief.paletteHints && brief.paletteHints.length > 0) {
    parts.push(`color palette: ${dedupe(brief.paletteHints).join(', ')}`)
  }

  const positive = dedupe(parts.filter(Boolean)).join(', ')
  const negative = buildNegative(style, brief)
  const ar = brief.aspectRatio ?? '1:1'
  const { width, height } = AR_RESOLUTIONS[ar]
  const renderProfile = buildRenderProfile(brief, width, height)
  const upscalePlan = buildUpscalePlan(brief, width, height)
  const fidelityContract = buildFidelityContract(brief, style)

  return {
    positive,
    negative,
    width,
    height,
    exif: {
      description: subject,
      software: 'AuroraIA v2 image module',
      artist: 'Juan via Aurora',
      userComment: positive,
    },
    upscalePlan,
    qualityChecklist: buildQualityChecklist(style, brief),
    styleGuide: {
      style: style ?? 'auto',
      engineHints: buildEngineHints(style, profile),
      mustHave: dedupe([...(profile?.checklist ?? ['sujet lisible', 'composition claire', 'pas de texte aleatoire']), ...fidelityContract.mustPreserve]),
      avoid: dedupe([...(profile?.negative ?? ['low quality', 'blurry', 'watermark']), ...fidelityContract.mustAvoid]),
    },
    fidelityContract,
    renderProfile,
  }
}

export function buildPromptContractBlock(brief: ImageBrief): string {
  const built = buildPrompt(brief)
  const lines = [
    'IMAGE PROMPT BUILDER CONTRACT - HARD REQUIREMENTS:',
    `Positive prompt: ${built.positive}`,
    `Avoid / negative traits: ${built.negative}`,
    built.fidelityContract.exactText.length
      ? `Exact text required: ${built.fidelityContract.exactText.map((text) => `"${text}"`).join(', ')}`
      : '',
    built.fidelityContract.counts.length
      ? `Count constraints: ${built.fidelityContract.counts.join('; ')}`
      : '',
    built.fidelityContract.layout.length
      ? `Layout constraints: ${built.fidelityContract.layout.join('; ')}`
      : '',
    `Validation checklist: ${built.qualityChecklist.join('; ')}`,
  ]
  return lines.filter(Boolean).join('\n')
}

function buildNegative(style?: ImageStyle, brief: ImageBrief = { subject: '' }): string {
  const styleNegative = style ? [...STYLE_PROFILES[style].negative] : []
  const allowsText = Boolean(
    (brief.exactText && brief.exactText.length > 0)
    || style === 'technical-schema'
    || /\b(label|legend|legende|texte exact|typography|poster|affiche)\b/i.test(stripAccents(brief.subject)),
  )
  const genericText = allowsText
    ? ['random extra text', 'misspelled text', 'illegible typography', 'unrequested logo']
    : ['text', 'logo']
  const generic = style === 'pixel-art'
    ? ['jpeg artifacts', 'duplicate', 'text', 'logo', 'watermark', 'muddy silhouette']
    : ['lowres', 'jpeg artifacts', 'duplicate', ...genericText, 'watermark']
  const exactTextAvoid = (brief.exactText ?? []).length > 0
    ? ['wrong spelling', 'extra letters', 'garbled letters', 'text outside requested location']
    : []
  return dedupe([...styleNegative, ...generic, ...exactTextAvoid, ...(brief.negativeHints ?? [])]).join(', ')
}

function buildUpscalePlan(brief: ImageBrief, width: number, height: number): BuiltPrompt['upscalePlan'] {
  if (!brief.highResolution) return { kind: 'none', targetWidth: width, targetHeight: height }
  if (brief.style === 'pixel-art') {
    return { kind: 'pixel-nearest-x4', targetWidth: width * 4, targetHeight: height * 4 }
  }
  return { kind: 'realesrgan-x4', targetWidth: width * 4, targetHeight: height * 4 }
}

function buildRenderProfile(brief: ImageBrief, width: number, height: number): BuiltPrompt['renderProfile'] {
  if (brief.style === 'pixel-art') {
    const logical = detectPixelCanvas(brief.subject)
    const frameCount = detectSpriteFrameCount(brief)
    const sheetHorizontal = frameCount > 1 && hasHint(brief.layoutHints, /horizontal|sprite sheet|planche/i)
    return {
      logicalCanvas: { width: sheetHorizontal ? logical * frameCount : logical, height: logical },
      outputCanvas: { width, height },
      upscaleMethod: brief.highResolution ? 'nearest-neighbor-x4' : 'none',
      passes: dedupe([
        'silhouette',
        'palette limitee',
        frameCount > 1 ? `sprite sheet ${frameCount} frames` : '',
        'grille pixel',
        'upscale nearest-neighbor',
      ]),
    }
  }
  return {
    logicalCanvas: { width, height },
    outputCanvas: { width, height },
    upscaleMethod: brief.highResolution ? 'realesrgan-x4' : 'none',
    passes: dedupe([
      'composition',
      'style',
      'details',
      ...(brief.exactText?.length ? ['verification texte exact'] : []),
      ...(brief.countHints?.length ? ['verification comptages'] : []),
      ...(brief.layoutHints?.length ? ['verification layout'] : []),
      'verification artefacts',
    ]),
  }
}

function buildQualityChecklist(style?: ImageStyle, brief: ImageBrief = { subject: '' }): string[] {
  const multiViewRequested = hasHint(brief.layoutHints, /sprite sheet|turnaround|multi.?view|planche|frames/i)
  const base = [
    'sujet principal identifiable',
    multiViewRequested ? 'layout multi-vue respecte uniquement si demande' : 'composition unique sans multi-vue',
    'medium stylistique respecte',
    'artefacts visibles corriges',
    'pas de watermark',
    ...(brief.exactText?.length ? ['texte exact lisible sans lettres en plus'] : ['pas de texte aleatoire']),
    ...(brief.countHints?.length ? ['comptages explicites respectes'] : []),
    ...(brief.backgroundHints?.length ? ['fond demande respecte'] : []),
  ]
  const extra = style ? STYLE_PROFILES[style].checklist : []
  return dedupe([...extra, ...base])
}

function buildEngineHints(style?: ImageStyle, profile?: StyleProfile): string[] {
  if (!style || !profile) {
    return [
      'FLUX auto: respecter le sujet, la composition et les contraintes explicites',
      'verifier que le rendu final a un medium clair et pas seulement un filtre',
      'renforcer les details utiles sans inventer de nouveaux sujets',
    ]
  }

  return dedupe([
    ...profile.engineHints,
    `Controle ${style}: le rendu doit etre immediatement reconnaissable dans cette categorie`,
    'forcer le medium demande avant les effets decoratifs',
    'corriger les artefacts propres au style avant validation',
  ])
}

function detectPixelCanvas(subject: string): number {
  const match = subject.match(/\b(16|24|32|48|64|128)\s*x\s*(16|24|32|48|64|128)\b/i)
  if (match) return Number(match[1])
  if (/\b(icon|icone|avatar|sprite)\b/i.test(stripAccents(subject))) return 32
  if (/\b(tileset|background|decor|scene)\b/i.test(stripAccents(subject))) return 64
  return 64
}

function detectSpriteFrameCount(brief: ImageBrief): number {
  const source = `${brief.subject} ${(brief.layoutHints ?? []).join(' ')}`
  const direct = source.match(/\b([2-9]|1[0-2])\s*(?:frames?|poses?|vignettes?)\b/i)
  if (direct) return Number(direct[1])
  return 1
}

function hasHint(values: string[] | undefined, pattern: RegExp): boolean {
  return (values ?? []).some((value) => pattern.test(value))
}

const STYLE_PATTERNS: Array<{ pattern: RegExp; style: ImageStyle }> = [
  { pattern: /\b(manga noir|manga en noir|bw|noir et blanc)\b/i, style: 'manga-bw' },
  { pattern: /\b(pixel art|pixelart|pixel-art|sprite|tileset|rpg maker|aseprite|gameboy|game boy|gba|snes|nes|8.?bit|16.?bit)\b/i, style: 'pixel-art' },
  { pattern: /\b(photo|photorealiste|realiste|hyperrealiste)\b/i, style: 'photorealistic' },
  { pattern: /\b(cinematic|cinematographique|cinematique|film)\b/i, style: 'cinematic' },
  { pattern: /\b(produit|packshot|studio)\b/i, style: 'studio-product' },
  { pattern: /\b(anime|manga)\b/i, style: 'anime-clean' },
  { pattern: /\b(aquarelle|watercolor)\b/i, style: 'aquarelle' },
  { pattern: /\b(huile|oil paint(ing)?)\b/i, style: 'oil-painting' },
  { pattern: /\b(isometrique|isometric)\b/i, style: 'isometric-3d' },
  { pattern: /\b(low.?poly)\b/i, style: 'low-poly-3d' },
  { pattern: /\b(flat|vector flat|editorial)\b/i, style: 'flat-illustration' },
  { pattern: /\b(concept art|matte painting)\b/i, style: 'concept-art' },
  { pattern: /\b(schema|blueprint|technique)\b/i, style: 'technical-schema' },
  { pattern: /\b(comic|comics|bd americaine)\b/i, style: 'comic-american' },
]

const LIGHTING_PATTERNS: Array<{ pattern: RegExp; lighting: Lighting }> = [
  { pattern: /\b(golden hour|coucher de soleil)\b/i, lighting: 'golden-hour' },
  { pattern: /\b(blue hour|heure bleue)\b/i, lighting: 'blue-hour' },
  { pattern: /\b(nuageux|overcast)\b/i, lighting: 'overcast-soft' },
  { pattern: /\b(midi|noon|harsh)\b/i, lighting: 'harsh-noon' },
  { pattern: /\b(studio|softbox)\b/i, lighting: 'studio-three-point' },
  { pattern: /\b(rim light|contre.?jour)\b/i, lighting: 'rim-light' },
  { pattern: /\b(rembrandt)\b/i, lighting: 'rembrandt' },
  { pattern: /\b(brouillard|fog|volumetric)\b/i, lighting: 'volumetric-fog' },
  { pattern: /\b(neon|cyberpunk)\b/i, lighting: 'neon-cyberpunk' },
]

const COMPOSITION_PATTERNS: Array<{ pattern: RegExp; composition: Composition }> = [
  { pattern: /\b(regle des tiers|rule of thirds|tiers)\b/i, composition: 'rule-of-thirds' },
  { pattern: /\b(symetrique|symmetry|symmetrical)\b/i, composition: 'symmetrical' },
  { pattern: /\b(centre|centered|center)\b/i, composition: 'centered' },
  { pattern: /\b(plongee|overhead|top.?down)\b/i, composition: 'overhead' },
  { pattern: /\b(grand angle|wide shot|plan large)\b/i, composition: 'wide-shot' },
  { pattern: /\b(close.?up|gros plan)\b/i, composition: 'close-up' },
]

const MOOD_PATTERNS: Array<{ pattern: RegExp; mood: Mood }> = [
  { pattern: /\b(serene|zen|calme)\b/i, mood: 'serene' },
  { pattern: /\b(dramatique|dramatic|intense)\b/i, mood: 'dramatic' },
  { pattern: /\b(mysterieux|mysterious|enigmatique)\b/i, mood: 'mysterious' },
  { pattern: /\b(joyeux|joyful|happy)\b/i, mood: 'joyful' },
  { pattern: /\b(sombre|somber|melancolique)\b/i, mood: 'somber' },
  { pattern: /\b(epique|epic)\b/i, mood: 'epic' },
  { pattern: /\b(cozy|chaleureux)\b/i, mood: 'cozy' },
  { pattern: /\b(futuriste|futuristic)\b/i, mood: 'futuristic' },
  { pattern: /\b(nostalgique|nostalgic|retro)\b/i, mood: 'nostalgic' },
]

const HEX_RE = /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b/g

const NEGATIVE_CLAUSE_RE = new RegExp(
  String.raw`\b(?:sans\s+|without\s+|no\s+|pas\s+(?:de\s+|d['’]?\s*)?|aucun(?:e|es|s)?\s+|ne\s+pas\s+|eviter\s+|evite\s+|avoid\s+)([^,.;!?\n]+?)(?=[,.;!?\n]|$)`,
  'giu',
)
const NEGATIVE_STRIP_RE = new RegExp(
  String.raw`(?:^|[,.;]\s*)\b(?:sans\s+|without\s+|no\s+|pas\s+(?:de\s+|d['’]?\s*)?|aucun(?:e|es|s)?\s+|ne\s+pas\s+|eviter\s+|evite\s+|avoid\s+)[^,.;!?\n]+`,
  'giu',
)
const EXACT_TEXT_QUOTED_RE = new RegExp(
  String.raw`\b(?:texte\s+exact|exact\s+text|ecris|ecrire|write|text\s+saying)\s+["'“«]([^"'”»\n]+)["'”»]`,
  'giu',
)
const EXACT_TEXT_UNQUOTED_RE = new RegExp(
  String.raw`\b(?:texte\s+exact|exact\s+text|ecris|ecrire|write|text\s+saying)\s+([^,.;!?\n]+?)(?=\s+(?:uniquement|seulement|sur|dans|au|a|à)\b|[,.;!?\n]|$)`,
  'giu',
)
const EXACT_TEXT_EDGE_QUOTES_RE = new RegExp(String.raw`^["'“«]+|["'”»]+$`, 'g')

function extractNegativeHints(raw: string): string[] {
  const out: string[] = []
  for (const match of raw.matchAll(NEGATIVE_CLAUSE_RE)) {
    const value = match[1]?.trim()
    if (value) out.push(value)
  }
  return dedupe(out.map((value) => value.replace(/\s+/g, ' ')))
}

function stripNegativeClauses(raw: string): string {
  return raw
    .replace(NEGATIVE_STRIP_RE, ' ')
    .replace(/\s+([,.;!?])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s,;.]+|[\s,;]+$/g, '')
    .trim()
}

function extractExactText(raw: string): string[] {
  const values: string[] = []
  for (const match of raw.matchAll(EXACT_TEXT_QUOTED_RE)) {
    const value = match[1]?.trim()
    if (value) values.push(value)
  }
  for (const match of raw.matchAll(EXACT_TEXT_UNQUOTED_RE)) {
    const value = match[1]?.replace(EXACT_TEXT_EDGE_QUOTES_RE, '').trim()
    if (value) values.push(value)
  }
  return dedupe(values.map((value) => value.replace(/\s+/g, ' ')))
}

function extractCountHints(raw: string): string[] {
  const hints: string[] = []
  const patterns = [
    /\b(\d{1,2})\s+(articulations?|joints?|axes?|connecteurs?|cables?|câbles?|vis|boutons?|fenetres?|fenêtres?)\b/giu,
    /\b(\d{1,2})\s*(frames?|poses?|vignettes?)\b/giu,
  ]
  for (const pattern of patterns) {
    for (const match of raw.matchAll(pattern)) {
      hints.push(`exactly ${match[1]} ${match[2]}`.replace(/\s+/g, ' '))
    }
  }
  return dedupe(hints)
}

function extractLayoutHints(raw: string): string[] {
  const normalised = stripAccents(raw).toLowerCase()
  const hints: string[] = []
  if (/\b(sprite sheet|planche sprite|spritesheet)\b/.test(normalised)) hints.push('sprite sheet layout')
  if (/\b(horizontal|horizontale|ligne unique|single row)\b/.test(normalised)) hints.push('horizontal layout')
  if (/\b(orthographique|orthographic)\b/.test(normalised)) hints.push('orthographic view')
  if (/\b(coupe|cross.?section|section view)\b/.test(normalised)) hints.push('cross-section view')
  if (/\b(legendes?|labels?|labeled|annote|annotated|numerotees?|numbered)\b/.test(normalised)) hints.push('short readable labels')
  return dedupe(hints)
}

function extractBackgroundHints(raw: string): string[] {
  const normalised = stripAccents(raw).toLowerCase()
  const hints: string[] = []
  if (/\b(fond transparent|transparent background|background transparent)\b/.test(normalised)) hints.push('transparent background')
  if (/\b(fond blanc|white background)\b/.test(normalised)) hints.push('clean white background')
  return hints
}

function stripAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

export function parseBrief(raw: string): ImageBrief {
  const trimmed = raw.trim()
  const subject = stripNegativeClauses(trimmed)
  const normalised = stripAccents(subject)
  const negativeHints = extractNegativeHints(trimmed)
  const exactText = extractExactText(trimmed)
  const countHints = extractCountHints(trimmed)
  const layoutHints = extractLayoutHints(trimmed)
  const backgroundHints = extractBackgroundHints(trimmed)
  const style = STYLE_PATTERNS.find((p) => p.pattern.test(normalised))?.style
  const lighting = LIGHTING_PATTERNS.find((p) => p.pattern.test(normalised))?.lighting
  const composition = COMPOSITION_PATTERNS.find((p) => p.pattern.test(normalised))?.composition
  const mood = MOOD_PATTERNS.find((p) => p.pattern.test(normalised))?.mood
  const palette = trimmed.match(HEX_RE) ?? []
  const highResolution = /\b(haute resolution|haute definition|4k|8k|high res|hi.?res)\b/i.test(normalised)

  let aspectRatio: AspectRatio | undefined
  if (/\b(portrait|9:16|tiktok|reels|vertical)\b/i.test(normalised)) aspectRatio = '9:16'
  else if (/\b(16:9|paysage|landscape|wide)\b/i.test(normalised)) aspectRatio = '16:9'
  else if (/\b(carre|square|1:1|sprite|icon|icone)\b/i.test(normalised)) aspectRatio = '1:1'
  else if (/\b(21:9|ultra.?wide|cinemascope)\b/i.test(normalised)) aspectRatio = '21:9'

  return {
    subject,
    style,
    lighting,
    composition,
    mood,
    paletteHints: palette.length > 0 ? dedupe(palette.map((c) => c.startsWith('#') ? c : `#${c}`)) : undefined,
    negativeHints: negativeHints.length > 0 ? negativeHints : undefined,
    exactText: exactText.length > 0 ? exactText : undefined,
    countHints: countHints.length > 0 ? countHints : undefined,
    layoutHints: layoutHints.length > 0 ? layoutHints : undefined,
    backgroundHints: backgroundHints.length > 0 ? backgroundHints : undefined,
    aspectRatio,
    highResolution,
  }
}

function buildConstraintPositiveParts(brief: ImageBrief): string[] {
  return dedupe([
    ...(brief.exactText ?? []).map((text) => `exact readable text "${text}" only, no extra lettering`),
    ...(brief.countHints ?? []).map((hint) => `respect count constraint: ${hint}`),
    ...(brief.layoutHints ?? []).map((hint) => `layout constraint: ${hint}`),
    ...(brief.backgroundHints ?? []).map((hint) => `background constraint: ${hint}`),
  ])
}

function buildFidelityContract(brief: ImageBrief, style?: ImageStyle): BuiltPrompt['fidelityContract'] {
  const mustPreserve = dedupe([
    'all explicit user constraints',
    ...(brief.exactText ?? []).map((text) => `exact text "${text}"`),
    ...(brief.countHints ?? []),
    ...(brief.layoutHints ?? []),
    ...(brief.backgroundHints ?? []),
    ...(style ? [`requested medium ${style}`] : []),
  ])
  const mustAvoid = dedupe([
    ...(brief.negativeHints ?? []),
    'unrequested extra objects',
    'default generic composition',
  ])
  return {
    mustPreserve,
    mustAvoid,
    exactText: brief.exactText ?? [],
    counts: brief.countHints ?? [],
    layout: dedupe([...(brief.layoutHints ?? []), ...(brief.backgroundHints ?? [])]),
  }
}

function dedupe(values: string[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const raw of values) {
    const value = raw.trim()
    if (!value) continue
    const key = value.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(value)
  }
  return out
}
