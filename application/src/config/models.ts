// Llama 4 Scout -- architecture MoE 16x17B, 10M context, Q4_K_M (~67GB)
import type { HardwareProfile } from '../types/app.ts'

// v82bp : guard import.meta.env so node --test (no vite replacement)
// can load this module from a regression test without crashing.
// Vite still substitutes the literal at build time ; at runtime in
// node, `(import.meta as any).env` is undefined so we fall back to {}.
const __env: Record<string, string | undefined> =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env || {}
const IS_CLOUD = __env.VITE_CLOUD_MODE === 'true'

// RTX 5070 Ti = 16GB VRAM -> qwen3:14b (9.3GB) est le modele optimal general
// qwen3-vl:30b (19GB) = qualite max vision avec offload CPU (32GB RAM disponibles)
export const DEFAULT_MAIN_MODEL = 'qwen3:14b'
export const DEFAULT_VISION_MODEL = 'qwen3:14b'
export const DOCUMENT_EXTRACTION_PACK_LABEL = 'PyMuPDF + pdfplumber + openpyxl + pandas'

// ---------------------------------------------------------------------------
// Modeles locaux -- optimises pour 16-24GB VRAM (RTX 5070 Ti / RTX 4090)
// qwen3:14b = meilleur ratio qualite/taille pour chat general (~8-9GB VRAM)
// qwen3-vl:30b = vision haute qualite (~19GB, offload CPU sur 16GB VRAM)
// qwen3-vl:8b = vision rapide en 16GB VRAM (~5-6GB) pour mode live
// Le code model (qwen3-coder:30b-a3b MoE, 3B actifs) fonctionne en offloading.
// ---------------------------------------------------------------------------
export const LOCAL_MAIN_MODEL = 'qwen3:14b'
export const LOCAL_VISION_MODEL = 'qwen3:14b'

// ---------------------------------------------------------------------------
// Vision multimodale -- 3 niveaux de qualite selon contexte
// HIGH_QUALITY: qwen3-vl:30b, analyses detaillees (image reference, video, academie)
// LIVE: qwen3-vl:8b si installe (capture camera temps reel, latence ciblee)
// FALLBACK: qwen3:14b (texte, fallback si aucun modele vision installe)
// ---------------------------------------------------------------------------
export const VISION_HIGH_QUALITY_MODEL = 'qwen3-vl:30b'
export const VISION_LIVE_MODEL = 'qwen3-vl:8b'
export const VISION_FALLBACK_MODEL = 'qwen3:14b'
export const VISION_MODEL_PACK_LABEL = 'Qwen3-VL (30B qualite + 8B rapide)'

// ---------------------------------------------------------------------------
// Code module -- EXPERT-MODEL ARCHITECTURE
// Le pipeline code privilegie le plus gros modele code installe.
// Les differents roles (Architecte, Codeur, Auditeur) sont obtenus en
// changeant le System Prompt, PAS en changeant de modele.
// Avantage: zero swap VRAM, latence reduite, coherence maximale.
// ---------------------------------------------------------------------------
export const CODE_NEXT_HIGH_MODEL = 'qwen3-coder-next:q8_0'
export const CODE_NEXT_MODEL = 'qwen3-coder-next:q4_K_M'
export const CODE_LEGACY_HIGH_MODEL = 'qwen3-coder:30b-a3b-q8_0'
export const CODE_LEGACY_MODEL = 'qwen3-coder:30b-a3b-q4_K_M'
export const CODE_PRIMARY_MODEL = CODE_NEXT_MODEL
export const CODE_CLOUD_HIGH_MODEL = CODE_NEXT_HIGH_MODEL
export const CODE_BALANCED_MODEL = 'hf.co/Qwen/Qwen3-32B-GGUF:Q6_K'
export const CODE_LIGHT_MODEL = 'qwen2.5-coder:7b'
export const CODE_MINI_MODEL = 'qwen2.5:7b'
export const CODE_SINGLE_MODEL = CODE_PRIMARY_MODEL

const CODE_MODEL_CANDIDATES = [
  CODE_NEXT_HIGH_MODEL,
  CODE_NEXT_MODEL,
  CODE_LEGACY_HIGH_MODEL,
  CODE_LEGACY_MODEL,
  CODE_BALANCED_MODEL,
  CODE_LIGHT_MODEL,
  CODE_MINI_MODEL,
]

// Legacy aliases -- tout redirige vers le modele expert principal
export const DEFAULT_CODE_MODEL = CODE_SINGLE_MODEL
export const AUXILIARY_ANALYSIS_MODEL = CODE_SINGLE_MODEL
export const CODE_PLANNING_MODEL = CODE_SINGLE_MODEL
export const CODE_REVIEW_MODEL = CODE_SINGLE_MODEL

export const HEAVY_REASONING_MIN_RAM_GB = 48

export const IMAGE_UNET_MODEL = 'flux1-dev-fp8.safetensors'
export const IMAGE_T5_MODEL = 't5xxl_fp8_e4m3fn.safetensors'
export const IMAGE_CLIP_MODEL = 'clip_l.safetensors'
export const IMAGE_VAE_MODEL = 'ae.safetensors'
export const IMAGE_MODEL_PACK_LABEL = 'FLUX FP8 + T5 XXL FP8 + CLIP-L + AE'

export const VIDEO_T2V_MODEL = 'Wan-AI/Wan2.2-T2V-A14B-Diffusers'
export const VIDEO_I2V_MODEL = 'Wan-AI/Wan2.2-I2V-A14B-Diffusers'
// v84 : modele UNIFIE T2V+I2V reellement utilise par video_generate.py sur
// les cartes <22GB VRAM (l'A14B n'y charge jamais — strategie wan5b-primary).
// Le pack de preparation doit cacher CE modele, pas l'A14B de 28GB.
export const VIDEO_UNIFIED_5B_MODEL = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'
export const VIDEO_I2V_GGUF_MODEL = 'QuantStack/Wan2.2-I2V-A14B-GGUF'
export const VIDEO_FALLBACK_MODEL = 'Lightricks/LTX-Video'
export const VIDEO_MODEL_PACK_LABEL = 'Wan 2.2 T2V/I2V + UMT5 XXL + Wan VAE'

export const THREE_D_SHAPE_MODEL = 'tencent/Hunyuan3D-2.1'
export const THREE_D_SHAPE_SUBFOLDER = 'hunyuan3d-dit-v2-1'
export const THREE_D_MULTIVIEW_MODEL = 'tencent/Hunyuan3D-2mv'
export const THREE_D_MULTIVIEW_SUBFOLDER = 'hunyuan3d-dit-v2-mv'
export const THREE_D_TEXTURE_MODEL = 'tencent/Hunyuan3D-2'
export const THREE_D_MODEL_PACK_LABEL = 'Linux 3D: Hunyuan3D 2.1 PBR local + TRELLIS.2 experimental 24GB+ + Blender cleanup'

export const THREE_D_TRELLIS2_REPO = 'https://github.com/microsoft/TRELLIS.2'
export const THREE_D_TRELLIS2_MODEL = 'microsoft/TRELLIS.2-4B'
export const THREE_D_TRELLIS2_MIN_VRAM_GB = 24
export const THREE_D_TRELLIS2_STATUS = 'experimental-linux-24gb-plus'

// DreamGaussian -- MIT license, EU-safe alternative for stylized/creative generation
export const THREE_D_DREAMGAUSSIAN_REPO = 'https://github.com/dreamgaussian/dreamgaussian.git'
export const THREE_D_DREAMGAUSSIAN_LICENSE = 'MIT'

// Meshroom / AliceVision -- MPL-2.0, photogrammetry for faithful reproduction
export const THREE_D_MESHROOM_MIN_IMAGES = 3
export const THREE_D_MESHROOM_OPTIMAL_IMAGES = 30
export const THREE_D_MESHROOM_LICENSE = 'MPL-2.0'

// Blender -- GPL, procedural modeling + rigging + validation + cleanup
export const THREE_D_BLENDER_MIN_VERSION = '4.2'
export const THREE_D_BLENDER_RECOMMENDED_VERSION = '5.1'
export const THREE_D_BLENDER_LICENSE = 'GPL'

// Pipeline routing thresholds
export const THREE_D_PHOTOGRAMMETRY_MIN_IMAGES = 3
export const THREE_D_PHOTOGRAMMETRY_OPTIMAL_IMAGES = 30
export const THREE_D_PROCEDURAL_KINEMATIC_REQUIRED = true
export const DETOURAGE_MODEL = 'u2net'

// Voxtral-Small-24B-2507 : modele STT complet non-mini (remplace Mini-4B-Realtime)
export const VOICE_STT_MODEL = 'mistralai/Voxtral-Small-24B-2507'
export const VOICE_STT_FALLBACK = 'openai/whisper-large-v3-turbo'
export const VOICE_TTS_MODEL = 'hexgrad/Kokoro-82M'
export const VOICE_MODEL_PACK_LABEL = 'Voxtral-Small-24B STT + Kokoro TTS'

// Modeles legacy connus : tous redirigent vers le modele principal actuel.
const LEGACY_MAIN_MODELS = new Set([
  'qwen3:32b',
  'qwen3:32b-q4_K_M',
  'llama3.1:70b-instruct-q5_K_M',
  'llama3.1:70b-instruct-q4_K_M',
  'llama3.1:70b',
  'llama3.3:70b-instruct-q5_K_M',
  'llama3.3:70b-instruct-q4_K_M',
  'llama3.3:70b',
  'llama4:scout',
  'qwen3-vl:30b',
  'qwen3:14b-q8_0',
])

// Anciens modeles code supprimes -- tout redirige vers CODE_SINGLE_MODEL.
// Les modeles explicitement supportes ci-dessus restent selectionnables comme
// fallback installe quand Qwen3-Coder-Next n'est pas disponible.
const LEGACY_CODE_MODELS = new Set([
  'qwen3-coder:30b',
  'qwen3-coder:30b-a3b-q6_K_M',
  'qwen3-coder:30b-a3b-q6_K',
  'qwen2.5-coder:14b',
  'hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q6_K',
])

const MODEL_ALIASES = new Map<string, string>([
  // Tous les gros modeles -> qwen3:14b (seul modele chat installe)
  ['llama4:scout', DEFAULT_MAIN_MODEL],
  ['llama4:16x17b', DEFAULT_MAIN_MODEL],
  ['llama4:latest', DEFAULT_MAIN_MODEL],
  ['qwen3:14b-q8_0', DEFAULT_MAIN_MODEL],
  // NOTE: qwen3-vl:30b et qwen3-vl:8b sont des modeles vision DIFFERENTS du main.
  // Ne plus les rediriger vers DEFAULT_MAIN_MODEL (qwen3:14b texte-seul).
  // Ils restent accessibles tels quels pour les appels multimodaux (images).
  // llama3.x -> qwen3:14b
  ['llama3.3:70b-instruct-q5_K_M', DEFAULT_MAIN_MODEL],
  ['llama3.3:70b-instruct-q4_K_M', DEFAULT_MAIN_MODEL],
  ['llama3.3:70b', DEFAULT_MAIN_MODEL],
  ['hf.co/bartowski/Llama-3.3-70B-Instruct-GGUF:Q5_K_M', DEFAULT_MAIN_MODEL],
  ['llama3.1:70b-instruct-q5_K_M', DEFAULT_MAIN_MODEL],
  ['llama3.1:70b-instruct-q4_K_M', DEFAULT_MAIN_MODEL],
  ['llama3.1:70b', DEFAULT_MAIN_MODEL],
  // Modeles code: Next est prioritaire via la selection dynamique, mais les
  // anciens 30B restent des fallbacks installables quand Next manque.
  ['qwen3-coder:30b-a3b-q4_K_M', CODE_LEGACY_MODEL],
  ['qwen3-coder:30b-a3b-q8_0', CODE_LEGACY_HIGH_MODEL],
  ['hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:Q6_K', CODE_SINGLE_MODEL],
  ['qwen3-coder:30b', CODE_SINGLE_MODEL],
  ['qwen3-coder:30b-a3b-q6_K_M', CODE_SINGLE_MODEL],
  ['qwen3-coder:30b-a3b-q6_K', CODE_SINGLE_MODEL],
  ['qwen2.5-coder:14b', CODE_SINGLE_MODEL],
  ['qwen2.5-coder:7b', CODE_LIGHT_MODEL],
  ['hf.co/Qwen/Qwen3-32B-GGUF:Q6_K', CODE_BALANCED_MODEL],
  // vision model variants
  ['qwen3-vl:30b-a3b-q4_K_M', DEFAULT_VISION_MODEL],
  ['llava:latest', DEFAULT_VISION_MODEL],
  ['llava', DEFAULT_VISION_MODEL],
  // analysis model variants -> modele unique
  ['qwen3:32b-q6_K', CODE_BALANCED_MODEL],
  ['qwen3:32b-q6_K_M', CODE_BALANCED_MODEL],
  // voxtral STT variants (toutes versions anterieures -> Small-24B)
  ['mistralai/Voxtral-Mini-3B-2507', VOICE_STT_MODEL],
  ['mistralai/Voxtral-Mini-4B-Realtime-2602', VOICE_STT_MODEL],
])

export function shouldPromoteToPrimaryMainModel(model: string | null | undefined) {
  return !model || LEGACY_MAIN_MODELS.has(model)
}

const LEGACY_BASE_NAMES = new Set(['llama3.1', 'llama3.3', 'llava', 'llama3'])

export function resolveConfiguredModel(model: string | null | undefined, fallback: string) {
  if (!model) {
    return fallback
  }

  const alias = MODEL_ALIASES.get(model)
  if (alias) {
    return alias
  }

  // Auto-correction: tout modele dont la base est legacy est redirige vers le fallback
  const base = model.split(':')[0].toLowerCase()
  if (LEGACY_BASE_NAMES.has(base) || LEGACY_MAIN_MODELS.has(model) || LEGACY_CODE_MODELS.has(model)) {
    return fallback
  }

  return model
}

export function normalizeVisionModel(model: string | null | undefined) {
  if (!model || model === 'llava') {
    return DEFAULT_VISION_MODEL
  }

  return MODEL_ALIASES.get(model) || model
}

/**
 * Selection adaptative du modele vision selon le hardware.
 * - qwen3-vl:30b (19GB): qualite max, offload CPU inevitable sur 16GB VRAM mais marche
 * - qwen3-vl:8b (5-6GB): rapide en VRAM pure, moins precis
 * - qwen3:14b: fallback texte-seul (pas vraiment vision)
 *
 * Mode `preferQuality=true` force qwen3-vl:30b si RAM >= 24GB (offload possible).
 */
export function selectAdaptiveVisionModel(
  hardware: Pick<HardwareProfile, 'vram_gb' | 'ram_gb'> | null | undefined,
  preferred?: string | null,
  options: { preferQuality?: boolean } = {},
): string {
  const resolved = normalizeVisionModel(preferred)
  const vramGb = Number(hardware?.vram_gb ?? 0)
  const ramGb = Number(hardware?.ram_gb ?? 0)

  if (IS_CLOUD) {
    if (vramGb >= 40) return resolved
    return LOCAL_VISION_MODEL
  }

  // Mode qualite max: qwen3-vl:30b si offload CPU possible (>=24GB RAM)
  if (options.preferQuality && ramGb >= 24) {
    return VISION_HIGH_QUALITY_MODEL
  }

  // Si l'utilisateur prefere deja un petit modele, respecter
  if (resolved === LOCAL_VISION_MODEL) return resolved

  // 24GB+ VRAM = qwen3-vl:30b en pure VRAM
  if (vramGb >= 24) return resolved

  // 16GB VRAM + RAM suffisante: qwen3-vl:8b pour mode live rapide
  if (vramGb >= 10) return VISION_LIVE_MODEL

  // Hardware tres limite: fallback texte
  return LOCAL_VISION_MODEL
}

function normalizeInstalledModelName(model: string) {
  return model.trim().replace(/:latest$/i, '')
}

function dedupeModels(models: Array<string | null | undefined>) {
  return Array.from(new Set(
    models
      .filter((value): value is string => Boolean(value && value.trim()))
      .map((value) => resolveConfiguredModel(value, CODE_SINGLE_MODEL)),
  ))
}

function hasInstalledModel(installedModels: string[], model: string) {
  const normalizedTarget = normalizeInstalledModelName(model)
  return installedModels.some((entry) => normalizeInstalledModelName(entry) === normalizedTarget)
}

export function shouldAvoidHeavyReasoningModel(
  hardware: Pick<HardwareProfile, 'ram_gb'> | null | undefined,
  minimumRamGb = HEAVY_REASONING_MIN_RAM_GB,
) {
  const ramGb = Number(hardware?.ram_gb ?? 0)
  if (!Number.isFinite(ramGb) || ramGb <= 0) {
    return true
  }

  return ramGb < minimumRamGb
}

export function selectAdaptiveReasoningModel(
  hardware: Pick<HardwareProfile, 'ram_gb'> | null | undefined,
  heavyModel = DEFAULT_MAIN_MODEL,
  fallbackModel = AUXILIARY_ANALYSIS_MODEL,
) {
  return shouldAvoidHeavyReasoningModel(hardware) ? fallbackModel : heavyModel
}

// ---------------------------------------------------------------------------
// Cloud GPU Tiers -- selection automatique par VRAM detectee
// ---------------------------------------------------------------------------

export const CLOUD_MODEL_TIERS = {
  high: {
    label: 'HIGH (A100 80GB+)',
    main: 'qwen3:14b',
    code: CODE_NEXT_HIGH_MODEL,
    vision: 'qwen3:14b',
    image: 'flux1-dev-fp8.safetensors',
    video: 'Wan-AI/Wan2.2-T2V-A14B-Diffusers',
    threeD: 'tencent/Hunyuan3D-2.1',
    stt: 'mistralai/Voxtral-Small-24B-2507',
    tts: 'hexgrad/Kokoro-82M',
  },
  mid: {
    label: 'MID (A40/A6000 48GB)',
    main: 'qwen3:14b',
    code: CODE_NEXT_MODEL,
    vision: 'qwen3:14b',
    image: 'flux1-dev-fp8.safetensors',
    video: 'Wan-AI/Wan2.2-T2V-A14B-Diffusers',
    threeD: 'tencent/Hunyuan3D-2.1',
    stt: 'mistralai/Voxtral-Small-24B-2507',
    tts: 'hexgrad/Kokoro-82M',
  },
  low: {
    label: 'LOW (RTX 5070 Ti 16GB)',
    main: 'qwen3:14b',
    code: CODE_NEXT_MODEL,
    vision: 'qwen3:14b',
    image: 'flux1-schnell-fp8.safetensors',
    video: 'Lightricks/LTX-Video',
    threeD: 'tencent/Hunyuan3D-2.1',
    stt: 'openai/whisper-large-v3',
    tts: 'hexgrad/Kokoro-82M',
  },
} as const

export type CloudTier = keyof typeof CLOUD_MODEL_TIERS

export function detectCloudTier(vramGb: number): CloudTier {
  if (vramGb >= 70) return 'high'
  if (vramGb >= 40) return 'mid'
  return 'low'
}

export function getCloudMainModel(vramGb: number): string {
  return CLOUD_MODEL_TIERS[detectCloudTier(vramGb)].main
}

export function getCloudTierModels(vramGb: number) {
  return CLOUD_MODEL_TIERS[detectCloudTier(vramGb)]
}

export function selectAdaptivePrimaryModel(hardware: Pick<HardwareProfile, 'ram_gb' | 'vram_gb'> | null | undefined) {
  return LOCAL_MAIN_MODEL
}

// ---------------------------------------------------------------------------
// Auto-detection du meilleur modele LLM installe dans Ollama
// Priorite: qwen3:14b > qwen3:32b > gemma3:27b > qwen2.5 > llama > mistral
// ---------------------------------------------------------------------------

const MAIN_MODEL_PRIORITY: string[] = [
  'qwen3:14b',
  'qwen3:14b-q4_K_M',
  'qwen3:32b',
  'gemma3:27b',
  'gemma3:27b-it-q4_K_M',
  'qwen2.5:14b',
  'qwen2.5:32b',
  'qwen3:7b',
  'qwen2.5:7b',
  'llama3.3:70b',
  'llama3.1:70b',
  'mistral-small3.1:22b',
  'qwen2.5-coder:7b',
  'mistral',
  'llama3.1',
  'llama3',
]

export function detectBestMainModel(installedModels: string[]): string {
  const normalized = installedModels.map((m) => m.replace(/:latest$/, '').trim().toLowerCase())
  for (const candidate of MAIN_MODEL_PRIORITY) {
    const candidateLower = candidate.toLowerCase()
    if (normalized.some((m) => m === candidateLower || m.startsWith(candidateLower.split(':')[0]))) {
      // Return the exact installed name that matched
      const idx = normalized.findIndex((m) => m === candidateLower || m.startsWith(candidateLower.split(':')[0]))
      return installedModels[idx] || candidate
    }
  }
  return DEFAULT_MAIN_MODEL
}

/**
 * Retourne le modele code expert operationnel.
 * Si le Q8 est installe il est prioritaire, sinon le Q4_K_M local reste le
 * modele production plutot qu un fallback 7B.
 */
export function selectCodeModelForHardware(
  hardware?: Pick<HardwareProfile, 'ram_gb' | 'vram_gb'> | null,
  installedModels: string[] = [],
  preferredModel?: string | null,
): string {
  const orderedCandidates = getCodeRecoveryFallbackModels(hardware, installedModels, preferredModel)
  const preferredResolved = orderedCandidates[0] || resolveConfiguredModel(preferredModel, CODE_SINGLE_MODEL)
  return selectOperationalOllamaModel(preferredResolved, installedModels, orderedCandidates)
}

export function selectOperationalOllamaModel(
  preferred: string,
  installedModels: string[],
  fallbacks: string[] = [],
) {
  const preferredResolved = resolveConfiguredModel(preferred, CODE_SINGLE_MODEL)
  const candidates = dedupeModels([preferredResolved, ...fallbacks])
  const installedCandidates = candidates.filter((candidate) => hasInstalledModel(installedModels, candidate))

  if (installedCandidates.length > 0) {
    return installedCandidates[0]
  }

  return candidates[0] || preferredResolved
}

/**
 * Pipeline code expert: on privilegie le modele code le plus qualitatif deja
 * installe, puis on retombe vers le modele principal installe sans basculer sur
 * un petit 7B pour les projets complexes.
 */
export function getCodeRecoveryFallbackModels(
  hardware?: Pick<HardwareProfile, 'ram_gb' | 'vram_gb'> | null,
  installedModels: string[] = [],
  preferredModel?: string | null,
) {
  const vramGb = Number(hardware?.vram_gb ?? 0)

  if (IS_CLOUD && vramGb >= 70) {
    const ordered = dedupeModels([
      CODE_NEXT_HIGH_MODEL,
      CODE_NEXT_MODEL,
      CODE_LEGACY_HIGH_MODEL,
      CODE_LEGACY_MODEL,
      CODE_BALANCED_MODEL,
      preferredModel,
      CODE_LIGHT_MODEL,
      CODE_MINI_MODEL,
    ])
    const installedOnly = ordered.filter((candidate) => hasInstalledModel(installedModels, candidate))
    return installedOnly.length > 0 ? installedOnly : ordered
  }

  const strongestInstalled = CODE_MODEL_CANDIDATES.find((candidate) => hasInstalledModel(installedModels, candidate))
  const ordered = strongestInstalled
    ? [strongestInstalled, ...CODE_MODEL_CANDIDATES, preferredModel]
    : [preferredModel, CODE_PRIMARY_MODEL, CODE_BALANCED_MODEL, CODE_LEGACY_HIGH_MODEL, CODE_LEGACY_MODEL, CODE_LIGHT_MODEL, CODE_MINI_MODEL]

  const deduped = dedupeModels([...ordered, ...CODE_MODEL_CANDIDATES])
  const installedOnly = deduped.filter((candidate) => hasInstalledModel(installedModels, candidate))
  return installedOnly.length > 0 ? installedOnly : deduped
}
