// Service centralise pour l analyse multimodale via qwen3-vl.
// Tous les modules (VoiceCopilote camera, Image reference, Learning video, Conversation)
// passent par ici pour transformer une image/frame en description textuelle
// exploitable par llama4:scout / FLUX / le pipeline de genereration.
//
// Architecture:
// - analyzeImage: 1 image -> 1 description (image de reference, capture ponctuelle)
// - analyzeImageStream: version streaming pour feedback UI en temps reel
// - analyzeVideoFrames: N frames -> 1 description temporelle (decrit l evolution)
// - analyzeLiveSnapshot: optimise pour latence faible (camera live, ~2s)
// - Utilitaires: blobToBase64, dataUrlToBase64, downscaleImage (reduit la latence)

import { ollamaChat, ollamaChatStream } from '../hooks/useTauri'
import {
  VISION_HIGH_QUALITY_MODEL,
  VISION_LIVE_MODEL,
  VISION_FALLBACK_MODEL,
} from '../config/models'
import type { OllamaMessage } from '../types/app'

// ---------------------------------------------------------------------------
// Type public
// ---------------------------------------------------------------------------

export type VisionInput =
  | { kind: 'blob'; data: Blob }
  | { kind: 'base64'; data: string }
  | { kind: 'dataUrl'; data: string }

export type VisionTask =
  | 'describe_reference'   // decrire un personnage/objet/scene pour FLUX
  | 'describe_live'        // decrire ce que voit la camera en temps reel
  | 'describe_video'       // decrire une sequence video (N frames)
  | 'answer_question'      // repondre a une question sur l image
  | 'extract_text'         // OCR / lecture de texte sur l image
  | 'classify_scene'       // classifier brievement (categorie, ambiance)

export interface VisionAnalysisOptions {
  task: VisionTask
  question?: string
  userPrompt?: string
  language?: 'fr' | 'en'
  maxTokens?: number
  temperature?: number
  preferQuality?: boolean  // true = qwen3-vl:30b, false = qwen3-vl:8b (rapide)
  signal?: AbortSignal
}

export interface VisionAnalysisResult {
  description: string
  modelUsed: string
  durationMs: number
}

// ---------------------------------------------------------------------------
// Selection du modele vision selon la tache
// ---------------------------------------------------------------------------

// Cache des modeles vision installes (refresh a chaque appel si vide)
let _installedVisionModelsCache: string[] | null = null
let _cacheAt = 0
const CACHE_TTL_MS = 30_000

async function getInstalledVisionModels(): Promise<string[]> {
  const now = Date.now()
  if (_installedVisionModelsCache && (now - _cacheAt) < CACHE_TTL_MS) {
    return _installedVisionModelsCache
  }
  try {
    const { ollamaListModels } = await import('../hooks/useTauri')
    const raw = await ollamaListModels()
    const allModels: string[] = Array.isArray(raw?.models)
      ? raw.models.map((m: any) => m?.name || m?.model).filter(Boolean)
      : []
    // Filtre les modeles vision (qwen3-vl, llava, bakllava, minicpm-v, moondream)
    const visionModels = allModels.filter((m) =>
      /qwen.*vl|llava|bakllava|minicpm-v|moondream|pixtral/i.test(m),
    )
    _installedVisionModelsCache = visionModels
    _cacheAt = now
    console.log('[visionService] installed vision models:', visionModels, 'all:', allModels.slice(0, 20))
    return visionModels
  } catch (err) {
    console.warn('[visionService] failed to list models:', err)
    return []
  }
}

function pickVisionModel(opts: VisionAnalysisOptions): string {
  if (opts.preferQuality === false) return VISION_LIVE_MODEL
  if (opts.preferQuality === true) return VISION_HIGH_QUALITY_MODEL

  // Defaut selon la tache
  switch (opts.task) {
    case 'describe_live':
      return VISION_LIVE_MODEL       // latence prioritaire
    case 'describe_reference':
    case 'describe_video':
    case 'answer_question':
    case 'extract_text':
      return VISION_HIGH_QUALITY_MODEL // precision prioritaire
    case 'classify_scene':
    default:
      return VISION_LIVE_MODEL
  }
}

/**
 * Retourne le meilleur modele vision INSTALLE dans Ollama.
 * Ordre de preference: celui passe en arg -> qwen3-vl:30b -> qwen3-vl:8b -> llava -> fallback.
 */
async function pickInstalledVisionModel(preferred: string): Promise<string> {
  const installed = await getInstalledVisionModels()
  if (installed.length === 0) {
    console.warn('[visionService] NO vision model installed. Install via: ollama pull qwen3-vl:30b')
    return preferred  // on essaie quand meme, ca echouera explicitement
  }

  // Normalisation: qwen3-vl:30b match qwen3-vl:30b-a3b-q4_K_M etc.
  const normalize = (s: string) => s.toLowerCase().split(':')[0]
  const preferredBase = normalize(preferred)
  // 1. Cherche un match exact
  const exact = installed.find((m) => m === preferred)
  if (exact) return exact
  // 2. Cherche un match sur le nom de base (qwen3-vl match qwen3-vl:30b-anything)
  const baseMatch = installed.find((m) => normalize(m) === preferredBase)
  if (baseMatch) {
    console.log(`[visionService] preferred=${preferred} not installed, using variant=${baseMatch}`)
    return baseMatch
  }
  // 3. Prendre le premier vision model installe
  console.log(`[visionService] preferred=${preferred} not installed, using first available=${installed[0]}`)
  return installed[0]
}

// ---------------------------------------------------------------------------
// Instructions par tache -- prompts optimises par cas d usage
// ---------------------------------------------------------------------------

function buildInstructions(opts: VisionAnalysisOptions): string {
  const lang = opts.language || 'fr'
  const isFr = lang === 'fr'
  const userPrompt = opts.userPrompt?.trim() || ''
  const question = opts.question?.trim() || ''

  const blocks: string[] = []

  switch (opts.task) {
    case 'describe_reference':
      blocks.push(
        isFr
          ? 'Tu analyses une image de reference fournie par l utilisateur pour un modele de generation d image (FLUX).'
          : 'You analyze a reference image provided by the user for an image generation model (FLUX).',
        '',
        isFr ? 'Ta mission:' : 'Your mission:',
        isFr
          ? '- Decris PRECISEMENT le sujet principal (personnage, objet, scene): morphologie, couleurs, vetements, pose, expression, style artistique.'
          : '- Describe PRECISELY the main subject (character, object, scene): morphology, colors, clothing, pose, expression, artistic style.',
        isFr
          ? '- Identifie les elements visuels distinctifs (logo, tatouage, accessoire, texture particuliere).'
          : '- Identify distinctive visual elements (logo, tattoo, accessory, distinctive texture).',
        isFr
          ? '- Sortie: description dense en ANGLAIS, 2-4 phrases, utilisable directement comme prompt FLUX.'
          : '- Output: dense description in ENGLISH, 2-4 sentences, directly usable as a FLUX prompt.',
        isFr
          ? '- NE JAMAIS dire "image", "photo", "picture": decris le sujet directement.'
          : '- NEVER say "image", "photo", "picture": describe the subject directly.',
      )
      if (userPrompt) {
        blocks.push('', isFr ? `Intention utilisateur: "${userPrompt}"` : `User intent: "${userPrompt}"`)
        blocks.push(isFr
          ? 'Integre cette intention dans ta description (ex: si "plus souriant", ajoute "with a bright smile").'
          : 'Integrate this intent into your description (e.g., if "more smiling", add "with a bright smile").')
      }
      break

    case 'describe_live':
      blocks.push(
        isFr
          ? 'Tu es la vision en direct d Aurora, copilote vocale. La camera capture ce que voit l utilisateur.'
          : 'You are Aurora\'s live vision, voice copilot. The camera captures what the user sees.',
        '',
        isFr
          ? 'Ta mission: en UNE phrase courte (max 25 mots), decris ce qui est visible en ce moment.'
          : 'Your mission: in ONE short sentence (max 25 words), describe what is currently visible.',
        isFr
          ? '- Concentre-toi sur le sujet principal, les objets, les actions, le contexte spatial.'
          : '- Focus on the main subject, objects, actions, spatial context.',
        isFr
          ? '- Si un texte est visible, cite-le textuellement entre guillemets.'
          : '- If text is visible, quote it verbatim in quotation marks.',
        isFr
          ? '- Ignore les details inutiles. Va droit au but.'
          : '- Ignore useless details. Go straight to the point.',
      )
      if (userPrompt) {
        blocks.push('', isFr ? `Contexte conversation: "${userPrompt}"` : `Conversation context: "${userPrompt}"`)
      }
      break

    case 'describe_video':
      blocks.push(
        isFr
          ? 'Tu analyses une sequence video (plusieurs frames consecutives).'
          : 'You analyze a video sequence (several consecutive frames).',
        '',
        isFr ? 'Ta mission:' : 'Your mission:',
        isFr
          ? '- Decris l evolution temporelle: que se passe-t-il du debut a la fin ?'
          : '- Describe the temporal evolution: what happens from start to end?',
        isFr
          ? '- Identifie le sujet principal, les actions, les changements de scene.'
          : '- Identify the main subject, actions, scene changes.',
        isFr
          ? '- Sortie: 3-5 phrases en francais, chronologiques.'
          : '- Output: 3-5 sentences in English, chronological.',
      )
      break

    case 'answer_question':
      blocks.push(
        isFr
          ? 'Tu analyses une image pour repondre PRECISEMENT a la question de l utilisateur.'
          : 'You analyze an image to answer the user question PRECISELY.',
        '',
        isFr ? `Question exacte: "${question}"` : `Exact question: "${question}"`,
        '',
        isFr ? 'REGLES DE CIBLAGE:' : 'TARGETING RULES:',
        isFr
          ? '- Si la question cite une POSITION ("sur la table", "a gauche", "en haut", "devant", "derriere", "a cote de X"), concentre-toi EXCLUSIVEMENT sur cette zone.'
          : '- If the question mentions a LOCATION ("on the table", "on the left", "in front", "behind", "next to X"), focus EXCLUSIVELY on that area.',
        isFr
          ? '- Si la question cite une COULEUR ou FORME ("le rouge", "le carre", "le rond", "le grand", "le petit"), identifie precisement l objet qui correspond.'
          : '- If the question mentions a COLOR or SHAPE ("the red one", "the square", "the round", "the big one"), identify the object matching these criteria.',
        isFr
          ? '- Si la question cite une INSCRIPTION / TEXTE / MARQUE visible ("avec ecrit X", "la marque X"), lis ce qui est inscrit et confirme.'
          : '- If the question mentions INSCRIPTION / TEXT / BRAND visible ("with X written", "the X brand"), read what is written and confirm.',
        isFr
          ? '- Si la question demande un AVIS SUR UNE PERSONNE (beau, belle, charme, attractif), decris LA PERSONNE: visage, traits, expression, posture, coiffure. NE PARLE PAS du vetement sauf si demande.'
          : '- If the question asks an OPINION ABOUT A PERSON (handsome, beautiful, attractive), describe THE PERSON: face, features, expression, posture, hair. DO NOT mention clothing unless asked.',
        isFr
          ? '- Si la question cite "cette plante", "cet animal", "cette voiture", etc., identifie l espece/modele le plus probable avec un degre de certitude.'
          : '- If the question mentions "this plant", "this animal", "this car", identify the most likely species/model with a certainty level.',
        isFr
          ? '- Si PLUSIEURS objets correspondent au critere, decris celui qui colle le mieux et ignore les autres.'
          : '- If MULTIPLE objects match, describe the best match and ignore others.',
        isFr
          ? '- Si AUCUN objet ne correspond, dis-le franchement: "je ne vois pas de [X] dans l image".'
          : '- If NO object matches, say bluntly: "I do not see [X] in the image".',
        isFr
          ? '- Sois factuel et precis. Jamais de description generique de toute l image quand la question porte sur un point specifique.'
          : '- Be factual and precise. NEVER generic description of the whole image when question is about a specific point.',
        '',
        isFr
          ? 'Sortie: 1 a 3 phrases courtes, ton naturel. Si incertain, dis "ca ressemble a X, mais je ne suis pas sur a 100%".'
          : 'Output: 1 to 3 short sentences, natural tone. If uncertain, say "it looks like X, but I am not 100% sure".',
      )
      break

    case 'extract_text':
      blocks.push(
        isFr
          ? 'Extrais TOUT le texte visible dans cette image (OCR).'
          : 'Extract ALL visible text from this image (OCR).',
        '',
        isFr
          ? '- Reproduis fidelement, en preservant l ordre et la structure.'
          : '- Reproduce faithfully, preserving order and structure.',
        isFr
          ? '- Si aucun texte n est visible, reponds "(aucun texte visible)".'
          : '- If no text is visible, answer "(no text visible)".',
      )
      break

    case 'classify_scene':
      blocks.push(
        isFr
          ? 'Classifie brievement cette scene en 1 phrase: categorie, ambiance, activite principale.'
          : 'Briefly classify this scene in 1 sentence: category, mood, main activity.',
      )
      break
  }

  return blocks.join('\n')
}

// ---------------------------------------------------------------------------
// Utilitaires -- conversion et redimensionnement
// ---------------------------------------------------------------------------

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Lecture du blob echouee.'))
    reader.onload = () => {
      const result = reader.result as string
      // result: "data:image/png;base64,iVBOR..." -> extraire apres la virgule
      const comma = result.indexOf(',')
      resolve(comma >= 0 ? result.slice(comma + 1) : result)
    }
    reader.readAsDataURL(blob)
  })
}

export function dataUrlToBase64(dataUrl: string): string {
  const comma = dataUrl.indexOf(',')
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl
}

async function inputToBase64(input: VisionInput): Promise<string> {
  switch (input.kind) {
    case 'base64':
      return input.data
    case 'dataUrl':
      return dataUrlToBase64(input.data)
    case 'blob':
      return blobToBase64(input.data)
  }
}

/**
 * Redimensionne une image pour reduire la latence vision (max 1024px par cote).
 * Retourne un Blob JPEG qualite 0.85 (rapport taille/qualite optimal).
 */
export async function downscaleImage(blob: Blob, maxSize = 1024): Promise<Blob> {
  const bitmap = await createImageBitmap(blob).catch(() => null)
  if (!bitmap) return blob  // fallback: blob original

  try {
    const { width, height } = bitmap
    const largestSide = Math.max(width, height)
    if (largestSide <= maxSize) {
      bitmap.close?.()
      return blob
    }

    const scale = maxSize / largestSide
    const targetW = Math.round(width * scale)
    const targetH = Math.round(height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = targetW
    canvas.height = targetH
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      bitmap.close?.()
      return blob
    }
    ctx.drawImage(bitmap, 0, 0, targetW, targetH)
    bitmap.close?.()

    return await new Promise<Blob>((resolve) => {
      canvas.toBlob(
        (b) => resolve(b || blob),
        'image/jpeg',
        0.85,
      )
    })
  } catch {
    bitmap.close?.()
    return blob
  }
}

// ---------------------------------------------------------------------------
// API publique
// ---------------------------------------------------------------------------

/**
 * Analyse une image unique via qwen3-vl. Retourne une description textuelle.
 * Utilise pour: image de reference (FLUX), upload chat, capture ponctuelle.
 */
export async function analyzeImage(
  input: VisionInput,
  options: VisionAnalysisOptions,
): Promise<VisionAnalysisResult> {
  const t0 = Date.now()
  const preferred = pickVisionModel(options)
  // Resolve au modele realement installe (qwen3-vl:30b ou variante, puis qwen3-vl:8b, etc.)
  const model = await pickInstalledVisionModel(preferred)
  const base64 = await inputToBase64(input)
  const instructions = buildInstructions(options)
  const temperature = options.temperature ?? (options.task === 'describe_reference' ? 0.25 : 0.4)

  const messages: OllamaMessage[] = [
    {
      role: 'user',
      content: instructions,
      images: [base64],
    },
  ]

  try {
    console.log(`[visionService] analyzeImage using model=${model} task=${options.task}`)
    const response = await ollamaChat(model, messages, temperature, { signal: options.signal })
    const description = response?.message?.content?.trim() || ''
    console.log(`[visionService] analyzeImage OK model=${model} len=${description.length} ms=${Date.now() - t0}`)
    return {
      description,
      modelUsed: model,
      durationMs: Date.now() - t0,
    }
  } catch (err) {
    // Log DETAILLE de l erreur pour diagnostic
    const errMsg = err instanceof Error ? err.message : String(err)
    console.error(`[visionService] analyzeImage FAILED model=${model}:`, errMsg)

    // Fallback: essayer un autre modele installe si le preferred a foire
    const installed = await getInstalledVisionModels()
    const alternatives = installed.filter((m) => m !== model)
    for (const alt of alternatives) {
      try {
        console.log(`[visionService] trying alternative model=${alt}`)
        const response = await ollamaChat(alt, messages, temperature, { signal: options.signal })
        const description = response?.message?.content?.trim() || ''
        if (description.length > 5) {
          console.log(`[visionService] alternative OK model=${alt} len=${description.length}`)
          return {
            description,
            modelUsed: alt,
            durationMs: Date.now() - t0,
          }
        }
      } catch (altErr) {
        console.warn(`[visionService] alternative ${alt} also failed:`, altErr instanceof Error ? altErr.message : altErr)
      }
    }
    // Aucun modele n a marche -> throw original
    throw err
  }
}

/**
 * Analyse une image en streaming (feedback UI temps reel).
 * Le callback onToken est appele pour chaque token genere.
 */
export async function analyzeImageStream(
  input: VisionInput,
  options: VisionAnalysisOptions,
  onToken: (token: string) => void,
  onDone?: () => void,
): Promise<string> {
  const model = pickVisionModel(options)
  const base64 = await inputToBase64(input)
  const instructions = buildInstructions(options)
  const temperature = options.temperature ?? 0.4

  let full = ''
  await ollamaChatStream(
    model,
    [{ role: 'user', content: instructions, images: [base64] }],
    (token) => {
      full += token
      onToken(token)
    },
    () => onDone?.(),
    { temperature, signal: options.signal },
  )
  return full
}

/**
 * Snapshot live camera -> description 1 phrase optimisee latence.
 * Retourne une description courte utilisable comme contexte pour le LLM principal.
 */
export async function analyzeLiveSnapshot(
  dataUrl: string,
  userPromptContext?: string,
  signal?: AbortSignal,
): Promise<string> {
  try {
    const result = await analyzeImage(
      { kind: 'dataUrl', data: dataUrl },
      {
        task: 'describe_live',
        userPrompt: userPromptContext,
        language: 'fr',
        preferQuality: false,  // LIVE -> 8b pour latence
        temperature: 0.35,
        signal,
      },
    )
    return result.description
  } catch (err) {
    console.warn('[visionService] analyzeLiveSnapshot failed:', err)
    return ''
  }
}

/**
 * Analyse une sequence video (plusieurs frames) -> description temporelle.
 * Les frames sont envoyees ensemble dans un seul message multimodal.
 */
export async function analyzeVideoFrames(
  frames: Array<{ kind: 'base64' | 'dataUrl'; data: string; timestamp?: number }>,
  options: Omit<VisionAnalysisOptions, 'task'> & { task?: VisionTask } = { task: 'describe_video' },
): Promise<VisionAnalysisResult> {
  const t0 = Date.now()
  const fullOptions: VisionAnalysisOptions = { ...options, task: options.task || 'describe_video' }
  const model = pickVisionModel(fullOptions)
  const instructions = buildInstructions(fullOptions)
  const temperature = options.temperature ?? 0.35

  const base64Frames = frames.map((f) =>
    f.kind === 'dataUrl' ? dataUrlToBase64(f.data) : f.data,
  )

  try {
    const response = await ollamaChat(
      model,
      [
        {
          role: 'user',
          content: [
            instructions,
            '',
            `Les ${frames.length} frames suivantes sont chronologiques (frame 1 = debut, frame ${frames.length} = fin).`,
          ].join('\n'),
          images: base64Frames,
        },
      ],
      temperature,
      { signal: options.signal },
    )
    const description = response?.message?.content?.trim() || ''
    return {
      description,
      modelUsed: model,
      durationMs: Date.now() - t0,
    }
  } catch (err) {
    console.warn('[visionService] analyzeVideoFrames failed:', err)
    throw err
  }
}

/**
 * Pose une question precise sur une image.
 * Utilise pour: chat conversationnel avec image uploadee.
 */
export async function askAboutImage(
  input: VisionInput,
  question: string,
  options: Partial<VisionAnalysisOptions> = {},
): Promise<string> {
  const result = await analyzeImage(input, {
    task: 'answer_question',
    question,
    language: options.language || 'fr',
    preferQuality: options.preferQuality ?? true,
    signal: options.signal,
  })
  return result.description
}

// ---------------------------------------------------------------------------
// Detection des traits du visage (pour Avatar Live 2D depuis image FLUX)
// ---------------------------------------------------------------------------

export interface FaceFeatures {
  // Coordonnees normalisees [0..1] relatives a l image
  eyeL: { x: number; y: number; w: number; h: number } | null
  eyeR: { x: number; y: number; w: number; h: number } | null
  mouth: { x: number; y: number; w: number; h: number } | null
  faceColor: string | null   // couleur hex de la peau au centre visage
  hairColor: string | null   // couleur hex des cheveux
  hasFace: boolean
}

const DEFAULT_FEATURES: FaceFeatures = {
  // Valeurs par defaut typiques pour un portrait frontal recadre
  eyeL: { x: 0.38, y: 0.42, w: 0.08, h: 0.045 },
  eyeR: { x: 0.62, y: 0.42, w: 0.08, h: 0.045 },
  mouth: { x: 0.50, y: 0.60, w: 0.13, h: 0.04 },
  faceColor: '#f0c9a0',
  hairColor: '#3a2518',
  hasFace: true,
}

/**
 * Analyse une image via qwen3-vl pour extraire la position des yeux et de la bouche.
 * Utilise pour animer un avatar 2D (blink, lip-sync) directement sur l image FLUX.
 *
 * Retourne les coordonnees normalisees [0..1] en (x, y, w, h) ou centre est le point central.
 */
export async function detectFacialFeatures(
  input: VisionInput,
  options: { signal?: AbortSignal } = {},
): Promise<FaceFeatures> {
  const base64 = await inputToBase64(input)
  const instructions = [
    'You analyze a portrait image to extract facial feature coordinates for 2D animation.',
    '',
    'Return STRICTLY this JSON (no prose, no markdown):',
    '{',
    '  "hasFace": true|false,',
    '  "eyeL":  { "x": <0..1>, "y": <0..1>, "w": <0..1>, "h": <0..1> },',
    '  "eyeR":  { "x": <0..1>, "y": <0..1>, "w": <0..1>, "h": <0..1> },',
    '  "mouth": { "x": <0..1>, "y": <0..1>, "w": <0..1>, "h": <0..1> },',
    '  "faceColor": "#rrggbb",',
    '  "hairColor": "#rrggbb"',
    '}',
    '',
    'Rules:',
    '- Coordinates are NORMALIZED (0=left/top, 1=right/bottom) relative to the whole image.',
    '- (x, y) is the CENTER of the feature box, (w, h) is the width/height of the bounding box.',
    '- eyeL = viewer-LEFT eye (user-left when looking at the portrait).',
    '- eyeR = viewer-RIGHT eye.',
    '- mouth covers the lips closed/neutral position.',
    '- faceColor = skin tone at the cheek (hex).',
    '- hairColor = dominant hair color on top of the head (hex).',
    '- If no clear face is detected, set hasFace=false and use null for eye/mouth.',
    '- OUTPUT ONLY THE JSON OBJECT. No explanations, no markdown fences.',
  ].join('\n')

  try {
    const response = await ollamaChat(
      VISION_HIGH_QUALITY_MODEL,
      [{ role: 'user', content: instructions, images: [base64] }],
      0.15,
      { signal: options.signal },
    )
    const raw = response?.message?.content?.trim() || ''
    // Extraire le JSON meme si entoure de markdown fences
    const jsonMatch = raw.match(/\{[\s\S]*\}/)
    if (!jsonMatch) {
      console.warn('[detectFacialFeatures] no JSON in response:', raw.slice(0, 200))
      return DEFAULT_FEATURES
    }
    const parsed = JSON.parse(jsonMatch[0])
    const clampBox = (b: any) => {
      if (!b || typeof b.x !== 'number') return null
      const clamp = (v: number) => Math.max(0, Math.min(1, Number(v)))
      return {
        x: clamp(b.x), y: clamp(b.y),
        w: clamp(b.w || 0.05), h: clamp(b.h || 0.04),
      }
    }
    return {
      hasFace: Boolean(parsed.hasFace),
      eyeL: clampBox(parsed.eyeL),
      eyeR: clampBox(parsed.eyeR),
      mouth: clampBox(parsed.mouth),
      faceColor: typeof parsed.faceColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(parsed.faceColor) ? parsed.faceColor : DEFAULT_FEATURES.faceColor,
      hairColor: typeof parsed.hairColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(parsed.hairColor) ? parsed.hairColor : DEFAULT_FEATURES.hairColor,
    }
  } catch (err) {
    console.warn('[detectFacialFeatures] failed, using defaults:', err)
    return DEFAULT_FEATURES
  }
}

/**
 * Verifie qu un modele vision est accessible via Ollama.
 * Retourne le premier modele disponible de la liste, ou null.
 */
export async function detectAvailableVisionModel(): Promise<string | null> {
  try {
    const { ollamaListModels } = await import('../hooks/useTauri')
    const raw = await ollamaListModels()
    const installed: string[] = Array.isArray(raw?.models)
      ? raw.models.map((m: any) => m?.name || m?.model).filter(Boolean)
      : []

    const priority = [VISION_HIGH_QUALITY_MODEL, VISION_LIVE_MODEL, VISION_FALLBACK_MODEL]
    for (const candidate of priority) {
      if (installed.some((m) => m === candidate || m.startsWith(candidate.split(':')[0]))) {
        return candidate
      }
    }
    return null
  } catch {
    return null
  }
}
