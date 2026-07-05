/**
 * videoPromptComposer — grammaire cinematique deterministe pour Wan2.2/LTX.
 *
 * La distillation LLM (taskIntelligence) traduit et ancre les sujets, mais
 * n'emet AUCUNE grammaire camera / eclairage / type de plan — or les modeles
 * video s'ancrent dessus pour produire un rendu professionnel (guide prompt
 * officiel Wan2.2 : subject + scene + motion + camera + lighting + style).
 * Et quand Ollama timeout, le fallback envoie le prompt FR brut au modele.
 *
 * Ce module est 100% deterministe (regex FR/EN), donc :
 *   - il fonctionne meme sans LLM (repare le fallback brut),
 *   - il est testable sous node sans service,
 *   - il n'ajoute jamais de latence.
 *
 * composeWanPrompt(distilled, analysis) = distilled + directives detectees
 * + queue qualite, avec dedoublonnage (jamais deux fois la meme directive
 * si le preset motion ou le LLM l'a deja posee).
 */

export interface VideoPromptAnalysis {
  camera: string[]
  shot: string | null
  lighting: string[]
  style: string | null
  tempo: string | null
  /** Vrai si l'utilisateur demande explicitement une camera fixe. */
  staticCamera: boolean
}

interface LexiconEntry {
  pattern: RegExp
  directive: string
}

// --- Camera (mouvements) --------------------------------------------------
const CAMERA_LEXICON: LexiconEntry[] = [
  { pattern: /\b(zoom\s*avant|zoom\s*in|zoome?r?\s+vers)\b/i, directive: 'slow cinematic zoom in' },
  { pattern: /\b(zoom\s*arriere|zoom\s*arrière|zoom\s*out|dezoom)\b/i, directive: 'slow cinematic zoom out' },
  { pattern: /\b(panoramique|camera\s+pan|pan\s+(gauche|droite|lateral)|balayage)\b/i, directive: 'smooth horizontal camera pan' },
  { pattern: /\b(travelling|dolly)\b/i, directive: 'steady dolly tracking shot' },
  { pattern: /\b(orbite|orbital|orbit|tourne\s+autour|rotation\s+autour)\b/i, directive: 'camera slowly orbiting around the subject' },
  { pattern: /\b(drone|vue\s+a[eé]rienne|aerial|survol)\b/i, directive: 'aerial drone shot, high altitude perspective' },
  { pattern: /\b(plong[eé]e)\b/i, directive: 'high-angle shot looking down' },
  { pattern: /\b(contre[-\s]?plong[eé]e)\b/i, directive: 'low-angle shot looking up, imposing perspective' },
  { pattern: /\b(pov|premi[eè]re\s+personne|first\s+person|vue\s+subjective)\b/i, directive: 'first-person POV shot' },
  { pattern: /\b(suit|suivre|poursuite|tracking|follow)\b/i, directive: 'tracking shot following the subject' },
  { pattern: /\b(camera\s+[aà]\s+l[' ]?[eé]paule|handheld|cam[eé]ra\s+port[eé]e)\b/i, directive: 'handheld camera, subtle natural shake' },
]

const STATIC_CAMERA_PATTERN = /\b(plan\s+fixe|cam[eé]ra\s+fixe|static\s+(camera|shot)|sans\s+mouvement\s+de\s+cam[eé]ra)\b/i

// --- Type de plan ----------------------------------------------------------
const SHOT_LEXICON: LexiconEntry[] = [
  { pattern: /\b(tr[eè]s\s+gros\s+plan|extreme\s+close[-\s]?up|macro)\b/i, directive: 'extreme close-up shot' },
  { pattern: /\b(gros\s+plan|close[-\s]?up|portrait\s+serr[eé])\b/i, directive: 'close-up shot' },
  { pattern: /\b(plan\s+moyen|medium\s+shot|[aà]\s+mi[-\s]corps)\b/i, directive: 'medium shot' },
  { pattern: /\b(plan\s+large|plan\s+d[' ]?ensemble|wide\s+shot|vue\s+d[' ]?ensemble|panorama)\b/i, directive: 'wide establishing shot' },
]

// --- Eclairage / ambiance ---------------------------------------------------
const LIGHTING_LEXICON: LexiconEntry[] = [
  { pattern: /\b(coucher\s+de\s+soleil|golden\s+hour|cr[eé]puscule|sunset)\b/i, directive: 'golden hour lighting, warm tones' },
  { pattern: /\b(aube|lever\s+de\s+soleil|sunrise)\b/i, directive: 'soft sunrise light, cool-to-warm gradient' },
  { pattern: /\b(nuit|nocturne|night)\b/i, directive: 'night scene, controlled low-key lighting' },
  { pattern: /\bn[eé]ons?\b/i, directive: 'neon lighting reflecting on surfaces' },
  { pattern: /\b(pluie|rain|orage|storm|temp[eê]te)\b/i, directive: 'rain atmosphere, wet reflective surfaces' },
  { pattern: /\b(brouillard|brume|fog|mist)\b/i, directive: 'volumetric fog, atmospheric depth' },
  { pattern: /\b(neige|hiver|snow)\b/i, directive: 'snowy scene, soft diffuse winter light' },
  { pattern: /\b(bougie|candle|feu\s+de\s+camp|campfire)\b/i, directive: 'warm flickering firelight' },
  { pattern: /\b(studio)\b/i, directive: 'clean studio lighting' },
  { pattern: /\b(sous[-\s]?marin|underwater|sous\s+l[' ]?eau)\b/i, directive: 'underwater light rays and caustics' },
]

// --- Style -------------------------------------------------------------------
const STYLE_LEXICON: LexiconEntry[] = [
  { pattern: /\b(anime|manga)\b/i, directive: 'high quality anime animation style, clean linework, expressive motion' },
  { pattern: /\b(cartoon|dessin\s+anim[eé])\b/i, directive: '2D cartoon animation style, bold shapes' },
  { pattern: /\b(pixar|3d\s+anim[eé]|animation\s+3d)\b/i, directive: 'polished 3D animated film style, soft global illumination' },
  { pattern: /\b(noir\s+et\s+blanc|black\s+and\s+white|monochrome)\b/i, directive: 'black and white film, rich grayscale contrast' },
  { pattern: /\b(vintage|r[eé]tro|pellicule|film\s+grain|super\s*8)\b/i, directive: 'vintage film look, analog grain' },
  { pattern: /\b(cyberpunk)\b/i, directive: 'cyberpunk aesthetic, neon-soaked futuristic city' },
  { pattern: /\b(aquarelle|watercolor)\b/i, directive: 'watercolor painting animation style' },
  { pattern: /\b(r[eé]aliste|photo[-\s]?r[eé]aliste|realistic|photoreal)\b/i, directive: 'photorealistic live-action footage, real camera optics' },
  { pattern: /\b(documentaire|documentary)\b/i, directive: 'documentary cinematography, natural framing' },
]

// --- Tempo -------------------------------------------------------------------
const TEMPO_LEXICON: LexiconEntry[] = [
  { pattern: /\b(ralenti|slow\s*motion|slow[-\s]?mo)\b/i, directive: 'slow motion, fluid high-frame-rate look' },
  { pattern: /\b(time[-\s]?lapse|acc[eé]l[eé]r[eé])\b/i, directive: 'timelapse, accelerated time flow' },
  { pattern: /\b(boucle|loop|seamless)\b/i, directive: 'seamless loop, last frame matches first frame' },
]

/** Queue qualite universelle Wan/LTX — courte, les negatifs font le reste. */
export const VIDEO_QUALITY_TAIL = [
  'cinematic composition',
  'high detail',
  'sharp focus',
  'natural color grading',
  'coherent physics',
  'stable subject identity',
  'smooth natural motion',
  'professional video quality',
]

function matchAll(text: string, lexicon: LexiconEntry[]): string[] {
  const out: string[] = []
  for (const entry of lexicon) {
    if (entry.pattern.test(text)) out.push(entry.directive)
  }
  return out
}

export function analyzeVideoPrompt(raw: string): VideoPromptAnalysis {
  const text = raw.normalize('NFC')
  const camera = matchAll(text, CAMERA_LEXICON)
  const shots = matchAll(text, SHOT_LEXICON)
  const lighting = matchAll(text, LIGHTING_LEXICON)
  const styles = matchAll(text, STYLE_LEXICON)
  const tempos = matchAll(text, TEMPO_LEXICON)

  return {
    camera,
    shot: shots[0] ?? null,
    lighting,
    style: styles[0] ?? null,
    tempo: tempos[0] ?? null,
    staticCamera: STATIC_CAMERA_PATTERN.test(text),
  }
}

/** Vrai si `directive` est deja exprimee (sous-chaine significative) dans base. */
function alreadyPresent(base: string, directive: string): boolean {
  const lowered = base.toLowerCase()
  if (lowered.includes(directive.toLowerCase())) return true
  // heuristique : 2 premiers mots significatifs deja presents ensemble
  const tokens = directive.toLowerCase().split(/[,\s]+/).filter((t) => t.length > 3)
  if (tokens.length < 2) return false
  return lowered.includes(tokens[0]) && lowered.includes(tokens[1])
}

export interface ComposeOptions {
  /** Suffixe du preset motion deja choisi dans l'UI (deduplique). */
  motionSuffix?: string
  /** i2v : la camera par defaut reste discrete pour proteger la reference. */
  mode?: 't2v' | 'i2v'
}

/**
 * Compose le prompt final pour le modele video :
 * distilled (LLM ou brut) + directives detectees dans le prompt ORIGINAL
 * + queue qualite. Jamais de doublon, jamais de directive contradictoire
 * (camera fixe explicite => aucune directive de mouvement camera).
 */
export function composeWanPrompt(
  distilled: string,
  analysis: VideoPromptAnalysis,
  options: ComposeOptions = {},
): string {
  const base = distilled.replace(/\s+$/g, '').trim()
  const parts: string[] = []
  const merged = options.motionSuffix ? `${base}\n${options.motionSuffix}` : base

  const push = (directive: string) => {
    if (!directive) return
    if (alreadyPresent(merged, directive)) return
    if (parts.some((p) => p === directive)) return
    parts.push(directive)
  }

  if (analysis.shot) push(analysis.shot)

  if (analysis.staticCamera) {
    push('static camera, locked tripod shot, no camera movement')
  } else {
    for (const cam of analysis.camera) push(cam)
  }

  for (const light of analysis.lighting) push(light)
  if (analysis.style) push(analysis.style)
  if (analysis.tempo) push(analysis.tempo)

  // Queue qualite — filtree contre ce que le LLM a deja emis.
  for (const tail of VIDEO_QUALITY_TAIL) push(tail)

  if (parts.length === 0) return base
  return `${base}\n\nCinematography: ${parts.join(', ')}.`
}
