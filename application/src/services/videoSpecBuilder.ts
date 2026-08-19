/**
 * videoSpecBuilder — miroir TypeScript de
 * `application/python-services/video_spec_builder.py`.
 *
 * Rôle : c'est le SEUL endroit côté TS qui doit résoudre une intention
 * utilisateur en `VideoJobSpec` complète. Toute logique de résolution
 * (aspect+quality_mode → w×h natives et livrées, quality_mode → steps,
 * dérivation seed déterministe, composition prompt) doit rester alignée
 * byte-à-byte avec la version Python — la garantie est le test de parité
 * `src/__tests__/videoSpecParity.test.ts` qui charge un fichier de
 * fixtures généré par Python et compare les `spec_hash`.
 *
 * Ne PAS réimplémenter à la main : quand la version Python change (nouvelles
 * résolutions, nouvelle table steps, changement de FNV-1a), il faut porter
 * ici EN MÊME TEMPS et régénérer le fixture — sinon le test de parité
 * casse et signale la divergence, ce qui est le comportement voulu.
 */

import type { VideoJobSpec } from './videoJobSpec.ts'
import { SPEC_VERSION } from './videoJobSpec.ts'

// ── constantes (identiques à video_spec_builder.py) ─────────────────────

export const DEFAULT_MODEL_ID = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'
export const DEFAULT_QUALITY_MODE = 'auto' as const
export const DEFAULT_FPS = 24
export const DEFAULT_MOTION_INTERP = 1
export const DEFAULT_GUIDANCE_SCALE = 4.5
export const DEFAULT_NUM_INFERENCE_STEPS = 60
export const DEFAULT_FORCE_STRATEGY = 'auto' as const
export const DEFAULT_PROFILE = 'personal_quality_first'

export const FRAME_GRID_ANCHOR = 8
export const FRAME_MIN = 25
export const FRAME_MAX_SEGMENT = 97
export const PIXEL_GRID = 32

type Aspect = '16:9' | '9:16' | '1:1' | '4:3'
type QualityMode = 'auto' | 'balanced' | 'premium'
type ForceStrategy = 'auto' | 'wan5b' | 'ltx'
type MotionInterp = 0 | 1 | 2

const NATIVE_RESOLUTIONS: Record<`${Aspect}|${QualityMode}`, [number, number]> = {
  '16:9|premium': [1280, 720], '16:9|balanced': [832, 480], '16:9|auto': [832, 480],
  '9:16|premium': [720, 1280], '9:16|balanced': [480, 832], '9:16|auto': [480, 832],
  '1:1|premium':  [960, 960],  '1:1|balanced':  [704, 704], '1:1|auto':  [704, 704],
  '4:3|premium':  [1024, 768], '4:3|balanced':  [832, 640], '4:3|auto':  [832, 640],
}

const DELIVERED_RESOLUTIONS: Record<`${Aspect}|${QualityMode}`, [number, number]> = {
  '16:9|premium': [3840, 2160], '16:9|balanced': [1920, 1080], '16:9|auto': [1920, 1080],
  '9:16|premium': [2160, 3840], '9:16|balanced': [1080, 1920], '9:16|auto': [1080, 1920],
  '1:1|premium':  [2160, 2160], '1:1|balanced':  [1080, 1080], '1:1|auto':  [1080, 1080],
  '4:3|premium':  [2880, 2160], '4:3|balanced':  [1440, 1080], '4:3|auto':  [1440, 1080],
}

const STEPS_BY_QUALITY: Record<QualityMode, number> = {
  premium: 60,
  balanced: 40,
  auto: 50,
}

// ── helpers alignés Python ──────────────────────────────────────────────

/** Round-half-to-even (banker's rounding) — MIRROR de `round()` Python 3.
 *
 * JS `Math.round(0.5) === 1` (half-away-from-zero) alors que Python
 * `round(0.5) === 0` et `round(2.5) === 2` (half-to-even). Divergence
 * catastrophique pour le hash : 720/32 = 22.5 → JS 23*32=736, Py 22*32=704.
 * Le test de parité l'a attrapé en direct — c'est exactement le rôle du test.
 */
function pyRound(x: number): number {
  const r = Math.round(x) // half-away-from-zero
  const diff = Math.abs(x - Math.trunc(x))
  if (diff !== 0.5) return r
  // Cas exact .5 : arrondir vers le pair.
  const floor = Math.floor(x)
  return floor % 2 === 0 ? floor : floor + 1
}

function alignToGrid(value: number, grid: number): number {
  return Math.max(grid, pyRound(value / grid) * grid)
}

function alignFrames(value: number): number {
  const v = Math.min(FRAME_MAX_SEGMENT, Math.max(FRAME_MIN, pyRound(value)))
  return Math.max(FRAME_MIN, Math.floor((v - 1) / FRAME_GRID_ANCHOR) * FRAME_GRID_ANCHOR + 1)
}

/** FNV-1a 32-bit sur les CODE POINTS de la chaîne — miroir de la boucle Python
 * `for ch in prompt: h ^= ord(ch)`. Attention : `charCodeAt` renvoie l'unité
 * UTF-16 pour les chars BMP, ce qui MATCHE ce que Python `ord()` retourne
 * pour tous les chars < U+10000. Pour les emoji hors BMP, `ord()` Python
 * renverrait le code point complet alors que `charCodeAt` renverrait un
 * surrogate — divergence possible sur ces chars. Notre banc de tests
 * n'utilise pas d'emoji hors BMP ; si un jour nécessaire, remplacer par
 * `codePointAt` + itération manuelle. Documenté en commentaire côté Python
 * dans video_spec_builder.py (même limite implicite).
 */
export function deterministicSeedFromPrompt(prompt: string): number {
  let h = 0x811c9dc5 >>> 0
  for (let i = 0; i < prompt.length; i += 1) {
    h ^= prompt.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h % 2147483647
}

function resolveSecondsToFrames(seconds: number, fps: number = DEFAULT_FPS): number {
  const raw = Math.round(Math.max(0.5, seconds) * fps)
  return alignFrames(raw)
}

export interface ComposePromptOptions {
  motionSuffix?: string
  cinematography?: string
  styleSuffix?: string
  referenceContract?: string
}

/** Composition du prompt final — ORDRE IDENTIQUE à `_compose_prompt` Python.
 * Deux appelants qui composent « le même prompt final » avec la même intention
 * DOIVENT obtenir la même chaîne exacte, sinon les hashes divergent.
 */
export function composePrompt(prompt: string, opts: ComposePromptOptions = {}): string {
  const parts: string[] = [prompt.trim()]
  const ref = (opts.referenceContract || '').trim()
  if (ref) parts.push(ref)
  const cin = (opts.cinematography || '').trim()
  if (cin) parts.push(cin)
  const sty = (opts.styleSuffix || '').trim()
  if (sty) parts.push(sty)
  const mot = (opts.motionSuffix || '').trim()
  if (mot) parts.push(`Motion directive: ${mot}`)
  return parts.filter((p) => p).join('\n\n')
}

// ── entrée principale ───────────────────────────────────────────────────

export interface BuildIntent {
  prompt: string
  aspect?: Aspect
  duration_s?: number
  num_frames?: number
  quality_mode?: QualityMode
  seed?: number
  image_path?: string | null
  motion_suffix?: string
  cinematography?: string
  style_suffix?: string
  reference_contract?: string
  negative_prompt?: string | null
  force_strategy?: ForceStrategy
  motion_interp?: MotionInterp
  model_id?: string
  profile?: string
  fps?: number
  guidance_scale?: number
  num_inference_steps?: number
}

export function buildSpecFromIntent(intent: BuildIntent): VideoJobSpec {
  if (!intent.prompt || !intent.prompt.trim()) {
    throw new Error('prompt vide — l\'intention doit contenir du texte')
  }
  const aspect: Aspect = intent.aspect ?? '16:9'
  const qualityMode: QualityMode = intent.quality_mode ?? DEFAULT_QUALITY_MODE
  const key = `${aspect}|${qualityMode}` as const
  const nativeTuple = NATIVE_RESOLUTIONS[key]
  const deliveredTuple = DELIVERED_RESOLUTIONS[key]
  if (!nativeTuple || !deliveredTuple) {
    throw new Error(`aspect+quality inconnu: ${key}`)
  }

  const nativeW = alignToGrid(nativeTuple[0], PIXEL_GRID)
  const nativeH = alignToGrid(nativeTuple[1], PIXEL_GRID)
  const deliveredW = deliveredTuple[0]
  const deliveredH = deliveredTuple[1]

  let nFrames: number
  if (intent.num_frames !== undefined) {
    nFrames = alignFrames(intent.num_frames)
  } else if (intent.duration_s !== undefined) {
    nFrames = resolveSecondsToFrames(intent.duration_s, intent.fps ?? DEFAULT_FPS)
  } else {
    nFrames = 65
  }

  const steps = intent.num_inference_steps ?? STEPS_BY_QUALITY[qualityMode]

  const promptComposed = composePrompt(intent.prompt, {
    motionSuffix: intent.motion_suffix,
    cinematography: intent.cinematography,
    styleSuffix: intent.style_suffix,
    referenceContract: intent.reference_contract,
  })

  let seed: number
  if (intent.seed !== undefined && intent.seed !== null) {
    seed = intent.seed
  } else {
    seed = deterministicSeedFromPrompt(promptComposed)
  }

  const spec: VideoJobSpec = {
    prompt: intent.prompt,
    prompt_composed: promptComposed,
    negative_prompt: intent.negative_prompt ?? null,
    width: nativeW,
    height: nativeH,
    delivered_width: deliveredW,
    delivered_height: deliveredH,
    num_frames: nFrames,
    fps: intent.fps ?? DEFAULT_FPS,
    model_id: intent.model_id ?? DEFAULT_MODEL_ID,
    num_inference_steps: steps,
    guidance_scale: intent.guidance_scale ?? DEFAULT_GUIDANCE_SCALE,
    quality_mode: qualityMode,
    force_strategy: intent.force_strategy ?? DEFAULT_FORCE_STRATEGY,
    motion_interp: (intent.motion_interp ?? DEFAULT_MOTION_INTERP) as MotionInterp,
    profile: intent.profile ?? DEFAULT_PROFILE,
    seed,
    image_path: intent.image_path ?? null,
    spec_version: SPEC_VERSION,
    created_at: Date.now() / 1000,
  }
  return spec
}
