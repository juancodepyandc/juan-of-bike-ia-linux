// Configuration des modeles d inference par module et profil materiel
import type { HardwareProfile } from '../types/app.ts'

const __env: Record<string, string | undefined> =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env || {}
const IS_CLOUD = __env.VITE_CLOUD_MODE === 'true'

// Modele principal (Chat, Cowork, Planification agentique, Vision native) :
// Qwen3.8-27B Uncensored (Abliterated, vision native, contexte 262K, tool-calling).
export const DEFAULT_MAIN_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const MAIN_FALLBACK_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const DEFAULT_VISION_MODEL = 'qwen3-vl:30b'
export const DOCUMENT_EXTRACTION_PACK_LABEL = 'PyMuPDF + pdfplumber + openpyxl + pandas'

// ---------------------------------------------------------------------------
// Modeles locaux -- qualite maximale sur RTX 5070 Ti (16GB VRAM + 30GB RAM)
// ---------------------------------------------------------------------------
export const LOCAL_MAIN_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const LOCAL_VISION_MODEL = 'qwen3-vl:30b'

// Modele pour evaluation semantique, sciences et validation inter-modules
export const LEARNING_EVAL_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const LEARNING_REASONING_MODEL = 'deepseek-r1:32b'

// ---------------------------------------------------------------------------
// Vision multimodale
// HIGH_QUALITY: qwen3-vl:30b (~19GB) — actif par defaut partout (Image, 3D, Code, Dessin, Chat)
// LIVE: qwen3-vl:8b (~6GB) uniquement pour flux camera temps reel basse latence
// ---------------------------------------------------------------------------
export const VISION_HIGH_QUALITY_MODEL = 'qwen3-vl:30b'
export const VISION_LIVE_MODEL = 'qwen3-vl:8b'
export const VISION_FALLBACK_MODEL = 'qwen3-vl:30b'
export const VISION_MODEL_PACK_LABEL = 'Qwen3-VL 30B (Qualité Max) + Qwen3.8 27B VLM + MoGe-2'

// ---------------------------------------------------------------------------
// Module Cyber -- modele offensif/defensif dedie 51 Go + DeepSeek-R1 32B
// ---------------------------------------------------------------------------
export const CYBER_PRIMARY_MODEL = 'qwen-cyber:latest'
export const CYBER_REASONING_MODEL = 'deepseek-r1:32b'
export const CYBER_FALLBACK_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const CYBER_MODEL_PACK_LABEL = 'Qwen-Cyber (51 Go) + DeepSeek-R1 32B + Z3 SMT'

// ---------------------------------------------------------------------------
// Module Code -- architecture multi-roles (Qwen3-Coder-Next + Qwen3-Coder 30B + DeepSeek-R1 32B)
// ---------------------------------------------------------------------------
export const CODE_NEXT_HIGH_MODEL = 'qwen3-coder-next:q8_0'
export const CODE_NEXT_MODEL = 'qwen3-coder-next:q4_K_M'
export const CODE_LEGACY_HIGH_MODEL = 'qwen3-coder:30b-a3b-q8_0'
export const CODE_LEGACY_MODEL = 'qwen3-coder:30b-a3b-q4_K_M'
export const CODE_FAST_EXPERT_MODEL = 'qwen3-coder:30b'
export const CODE_LOCAL_PRIMARY_MODEL = CODE_NEXT_MODEL
export const CODE_PRIMARY_MODEL = CODE_LOCAL_PRIMARY_MODEL
export const CODE_CLOUD_HIGH_MODEL = CODE_NEXT_HIGH_MODEL
export const CODE_BALANCED_MODEL = 'qwen3-coder:30b'
export const CODE_LIGHT_MODEL = 'qwen3-coder:30b'
export const CODE_MINI_MODEL = 'qwen3-coder:30b'
export const CODE_SINGLE_MODEL = CODE_PRIMARY_MODEL
export const CODE_REASONING_MODEL = 'deepseek-r1:32b'
export const CODE_VERIFIER_MODEL = CODE_REASONING_MODEL

const CODE_MODEL_CANDIDATES = [
  CODE_NEXT_MODEL,
  CODE_FAST_EXPERT_MODEL,
  CODE_REASONING_MODEL,
  CODE_LEGACY_HIGH_MODEL,
  CODE_LEGACY_MODEL,
  CODE_BALANCED_MODEL,
]

// Legacy aliases
export const DEFAULT_CODE_MODEL = CODE_SINGLE_MODEL
export const AUXILIARY_ANALYSIS_MODEL = DEFAULT_MAIN_MODEL

// Agent et planificateur : Qwen3.8 27B Uncensored (contexte 262k, multi-fichiers natif)
export const CODE_AGENT_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'
export const CODE_AGENT_FALLBACK_MODEL = 'orcarouter/Qwen3.8-27B-Uncensored'

// Verificateur independant pour le controle et l analyse logique
export const CODE_VERIFIER_REASONING_MODEL = 'deepseek-r1:32b'
export const CODE_PLANNING_MODEL = CODE_AGENT_MODEL
export const CODE_REVIEW_MODEL = CODE_VERIFIER_REASONING_MODEL

// 24 Go RAM suffisent pour Qwen3.8-27B (17 Go) et DeepSeek-R1 32B (19 Go) avec 16 Go VRAM
export const HEAVY_REASONING_MIN_RAM_GB = 24

// ---------------------------------------------------------------------------
// Module Image & Dessin -- UNIFIE SUR FLUX.2-dev + Mistral-3 Small FLUX.2 + RealESRGAN x4plus
// ---------------------------------------------------------------------------
export const IMAGE_PRIMARY_ENGINE = 'FLUX.2-dev'
export const IMAGE_UNET_MODEL = 'flux2-dev-Q4_K_M.gguf'
export const IMAGE_T5_MODEL = 'mistral_3_small_flux2_fp8.safetensors'
export const IMAGE_CLIP_MODEL = ''  // FLUX.2 = encodeur unique Mistral-3 Small
export const IMAGE_VAE_MODEL = 'flux2-vae.safetensors'
export const IMAGE_UPSCALER_MODEL = 'RealESRGAN_x4plus.pth'
export const IMAGE_TURBO_LORA_MODEL = 'Flux_2-Turbo-LoRA_comfyui.safetensors'
export const IMAGE_PANO360_LORA_MODEL = 'qwen-360-diffusion-2512-int8-bf16-v2.safetensors'
export const IMAGE_GEOMETRY_NORMAL_MODEL = 'moge_2_vitl_normal_fp16.safetensors'
export const IMAGE_MODEL_PACK_LABEL = 'FLUX.2-dev (Q4_K_M 20 Go) + Mistral-3 Small FLUX.2 + VAE FLUX.2 + RealESRGAN 8K'

export const VIDEO_T2V_MODEL = 'Wan-AI/Wan2.2-T2V-A14B-Diffusers'
export const VIDEO_I2V_MODEL = 'Wan-AI/Wan2.2-I2V-A14B-Diffusers'
export const VIDEO_UNIFIED_5B_MODEL = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'
export const VIDEO_I2V_GGUF_MODEL = 'QuantStack/Wan2.2-I2V-A14B-GGUF'
export const VIDEO_FALLBACK_MODEL = 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'
export const VIDEO_MODEL_PACK_LABEL = 'Wan 2.2 TI2V 5B FP16 + UMT5 XXL + Wan 2.2 VAE + SeedVR2 Upscaler'

export const THREE_D_SHAPE_MODEL = 'microsoft/TRELLIS.2-4B'
export const THREE_D_SHAPE_SUBFOLDER = 'hunyuan3d-dit-v2-1'
export const THREE_D_MULTIVIEW_MODEL = 'huanngzh/mv-adapter'
export const THREE_D_MULTIVIEW_SUBFOLDER = 'hunyuan3d-dit-v2-mv'
export const THREE_D_TEXTURE_MODEL = 'microsoft/TRELLIS.2-4B'
export const THREE_D_HUNYUAN_MODEL = 'tencent/Hunyuan3D-2.1'
export const THREE_D_WORLD_MODEL = 'tencent/HunyuanWorld-Mirror'
export const THREE_D_NORMAL_MODEL = 'moge_2_vitl_normal_fp16.safetensors'
export const THREE_D_MODEL_PACK_LABEL = 'TRELLIS.2-4B + Hunyuan3D-2.1 PBR + HunyuanWorld-Mirror (Scènes/Paysages) + MoGe-2 + FLUX.2-dev'

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

// STT reel : faster-whisper large-v3-turbo (ce que voice_service.py charge vraiment ;
// l'ancien pointeur Voxtral-Small-24B ~55GB n'est ni installe ni appele — chemin commente).
export const VOICE_STT_MODEL = 'openai/whisper-large-v3-turbo'
export const VOICE_STT_FALLBACK = 'openai/whisper-large-v3-turbo'
// TTS reel : Kokoro-82M (Apache-2.0, local, haute qualite). L'ancien pointeur
// fishaudio/fish-speech-1.5 etait mort (jamais charge) et sous licence non-commerciale.
export const VOICE_TTS_MODEL = 'hexgrad/Kokoro-82M'
export const VOICE_MODEL_PACK_LABEL = 'faster-whisper large-v3-turbo STT + Kokoro-82M TTS'

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
// NOTE: 'qwen3-coder:30b' N'EST PLUS legacy — c'est desormais CODE_LOCAL_PRIMARY_MODEL,
// le modele code de production sur cette machine. L'y remettre le redirigerait vers un
// fallback absent (regression).
const LEGACY_CODE_MODELS = new Set([
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
  // 'qwen3-coder:30b' n'est plus alias : c'est le modele code primaire installe.
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
 * - qwen3-vl:30b (19GB): qualite maximale par defaut partout
 * - qwen3-vl:8b (6GB): uniquement si liveStream=true est demande explicitement
 */
export function selectAdaptiveVisionModel(
  hardware: Pick<HardwareProfile, 'vram_gb' | 'ram_gb'> | null | undefined,
  preferred?: string | null,
  options: { preferQuality?: boolean; liveStream?: boolean } = {},
): string {
  if (options.liveStream) {
    return VISION_LIVE_MODEL
  }
  const resolved = normalizeVisionModel(preferred)
  const vramGb = Number(hardware?.vram_gb ?? 0)
  const ramGb = Number(hardware?.ram_gb ?? 0)

  // Qualite maximale par defaut : qwen3-vl:30b des que VRAM+RAM >= 24 Go (ou hardware non encore sonde)
  if (options.preferQuality !== false && (ramGb + vramGb >= 24 || (ramGb === 0 && vramGb === 0))) {
    return VISION_HIGH_QUALITY_MODEL
  }

  if (vramGb >= 24 || ramGb >= 24) return VISION_HIGH_QUALITY_MODEL
  if (resolved === VISION_LIVE_MODEL) return resolved
  return VISION_HIGH_QUALITY_MODEL
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
    return false
  }

  return ramGb < minimumRamGb
}

export function selectAdaptiveReasoningModel(
  hardware: Pick<HardwareProfile, 'ram_gb'> | null | undefined,
  heavyModel = DEFAULT_MAIN_MODEL,
  fallbackModel = AUXILIARY_ANALYSIS_MODEL,
) {
  if (heavyModel.startsWith('aurora-rl-')) return heavyModel
  return shouldAvoidHeavyReasoningModel(hardware) ? fallbackModel : heavyModel
}

export function selectCyberModel(
  installedModels: string[] = [],
  preferredModel?: string | null,
): string {
  const candidates = [
    preferredModel,
    CYBER_PRIMARY_MODEL,
    CYBER_REASONING_MODEL,
    CYBER_FALLBACK_MODEL,
  ].filter((m): m is string => Boolean(m && m.trim()))
  if (installedModels.length > 0) {
    const found = candidates.find((c) => hasInstalledModel(installedModels, c))
    if (found) return found
  }
  return CYBER_PRIMARY_MODEL
}

// ---------------------------------------------------------------------------
// Cloud & Local GPU Tiers -- unifies sur FLUX.2-dev et les meilleurs modeles
// ---------------------------------------------------------------------------

export const CLOUD_MODEL_TIERS = {
  high: {
    label: 'HIGH (A100 80GB+)',
    main: DEFAULT_MAIN_MODEL,
    code: CODE_NEXT_HIGH_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    image: IMAGE_UNET_MODEL,
    video: VIDEO_T2V_MODEL,
    threeD: THREE_D_SHAPE_MODEL,
    cyber: CYBER_PRIMARY_MODEL,
    stt: VOICE_STT_MODEL,
    tts: VOICE_TTS_MODEL,
  },
  mid: {
    label: 'MID (A40/A6000 48GB)',
    main: DEFAULT_MAIN_MODEL,
    code: CODE_NEXT_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    image: IMAGE_UNET_MODEL,
    video: VIDEO_T2V_MODEL,
    threeD: THREE_D_SHAPE_MODEL,
    cyber: CYBER_PRIMARY_MODEL,
    stt: VOICE_STT_MODEL,
    tts: VOICE_TTS_MODEL,
  },
  low: {
    label: 'MAX LOCAL (RTX 5070 Ti 16GB + 30GB RAM)',
    main: DEFAULT_MAIN_MODEL,
    code: CODE_NEXT_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    image: IMAGE_UNET_MODEL,
    video: VIDEO_UNIFIED_5B_MODEL,
    threeD: THREE_D_SHAPE_MODEL,
    cyber: CYBER_PRIMARY_MODEL,
    stt: VOICE_STT_MODEL,
    tts: VOICE_TTS_MODEL,
  },
} as const

export const ALL_MODULES_BEST_MODELS = {
  image: {
    primary: IMAGE_UNET_MODEL,
    textEncoder: IMAGE_T5_MODEL,
    vae: IMAGE_VAE_MODEL,
    upscaler: IMAGE_UPSCALER_MODEL,
    normalEstimator: IMAGE_GEOMETRY_NORMAL_MODEL,
    pano360Lora: IMAGE_PANO360_LORA_MODEL,
    visionDirector: VISION_HIGH_QUALITY_MODEL,
    promptDirector: DEFAULT_MAIN_MODEL,
    label: IMAGE_MODEL_PACK_LABEL,
  },
  '3d': {
    primary: THREE_D_SHAPE_MODEL,
    hunyuanPbr: THREE_D_HUNYUAN_MODEL,
    worldScenes: THREE_D_WORLD_MODEL,
    multiview: THREE_D_MULTIVIEW_MODEL,
    normalEstimator: THREE_D_NORMAL_MODEL,
    conceptSynth: IMAGE_UNET_MODEL,
    visionQa: VISION_HIGH_QUALITY_MODEL,
    label: THREE_D_MODEL_PACK_LABEL,
  },
  code: {
    primary: CODE_NEXT_MODEL,
    fastExpert: CODE_FAST_EXPERT_MODEL,
    architect: CODE_AGENT_MODEL,
    verifier: CODE_VERIFIER_REASONING_MODEL,
    visualInspector: VISION_HIGH_QUALITY_MODEL,
    label: 'Qwen3-Coder-Next (51 Go) + Qwen3-Coder 30B + DeepSeek-R1 32B + Qwen3-VL 30B',
  },
  cyber: {
    primary: CYBER_PRIMARY_MODEL,
    reasoning: CYBER_REASONING_MODEL,
    planner: CYBER_FALLBACK_MODEL,
    label: CYBER_MODEL_PACK_LABEL,
  },
  conversation: {
    primary: DEFAULT_MAIN_MODEL,
    reasoning: LEARNING_REASONING_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    embeddings: 'nomic-embed-text:latest',
    label: 'Qwen3.8-27B Uncensored (262K) + DeepSeek-R1 32B + Qwen3-VL 30B',
  },
  learning: {
    primary: LEARNING_REASONING_MODEL,
    eval: LEARNING_EVAL_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    label: 'DeepSeek-R1 32B + Qwen3.8-27B + Qwen3-VL 30B + SymPy/Z3',
  },
  drawing: {
    primary: IMAGE_UNET_MODEL,
    vision: VISION_HIGH_QUALITY_MODEL,
    label: 'FLUX.2-dev + Qwen3-VL 30B + MoGe-2',
  },
  video: {
    primary: VIDEO_UNIFIED_5B_MODEL,
    upscaler: 'SeedVR2 VideoUpscaler',
    label: VIDEO_MODEL_PACK_LABEL,
  },
  voice: {
    stt: VOICE_STT_MODEL,
    tts: VOICE_TTS_MODEL,
    llm: DEFAULT_MAIN_MODEL,
    label: VOICE_MODEL_PACK_LABEL,
  },
  business: {
    primary: DEFAULT_MAIN_MODEL,
    reasoning: LEARNING_REASONING_MODEL,
    label: 'Qwen3.8-27B Uncensored + DeepSeek-R1 32B (Analyse & Simulation Temps Réel)',
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
// Auto-detection du meilleur modele conversationnel installe dans Ollama.
// Priorite: Qwen3.8-27B Uncensored > Qwen3.8 > Qwen3.6 > fallback
// ---------------------------------------------------------------------------

const MAIN_MODEL_PRIORITY: string[] = [
  'orcarouter/Qwen3.8-27B-Uncensored',
  'orcarouter/qwen3.8-27b-uncensored',
  'qwen3.8:27b',
  'qwen3.8',
  'qwen3.6:27b',
  'qwen3:30b-a3b-instruct-2507-q4_K_M',
  'qwen3:30b-a3b-instruct-2507',
  'qwen3.5:35b',
  'qwen3.5:27b',
  'qwen3:32b',
  'gemma3:27b',
  'mistral-small3.2:24b',
  'qwen3:14b',
  'qwen2.5:14b',
  'qwen2.5:32b',
  'qwen3:7b',
  'qwen2.5:7b',
  'mistral',
  'llama3.1',
  'llama3',
]

// Un modele CHAT generaliste n'est ni un modele vision (-vl) ni un modele code
// (-coder), ni un modele d'embedding. Sans ce filtre, le prefixe 'qwen3' matchait
// qwen3-vl / qwen3-coder et le chat tournait sur un modele du mauvais role.
function isGeneralChatModel(normalizedName: string): boolean {
  return (
    !normalizedName.includes('-vl') &&
    !normalizedName.includes('coder') &&
    !normalizedName.includes('embed') &&
    !normalizedName.includes('rerank')
  )
}

export function detectBestMainModel(installedModels: string[]): string {
  const chatEntries = installedModels
    .map((raw) => ({ raw, norm: raw.replace(/:latest$/, '').trim().toLowerCase() }))
    .filter((entry) => isGeneralChatModel(entry.norm))

  for (const candidate of MAIN_MODEL_PRIORITY) {
    const candidateLower = candidate.toLowerCase()
    const family = candidateLower.split(':')[0]
    // Le set est deja filtre (pas de -vl/-coder), on peut donc matcher soit le tag
    // exact, soit la famille par prefixe sans risque de croiser un autre role.
    const match = chatEntries.find(
      (entry) => entry.norm === candidateLower || entry.norm.startsWith(family),
    )
    if (match) {
      return match.raw
    }
  }
  return DEFAULT_MAIN_MODEL
}

// ---------------------------------------------------------------------------
// GARDE ANTI-GEL. Un modele code qui depasse la memoire rapide (VRAM+RAM)
// pagaie le disque et FIGE le poste (vecu: qwen3-coder-next 51GB charge sur
// 16GB VRAM + 30GB RAM = gel dur). La table ne liste QUE les modeles LOURDS a
// surveiller ; tout autre modele (le codeur 30b 18GB, qwen3.6, deepseek, ...)
// passe toujours. Sur un build desktop local ces familles sont refusees quel
// que soit leur statut installe -> le gel devient structurellement impossible.
const CODE_HEAVY_MODEL_GB: Array<{ match: string; gb: number }> = [
  { match: 'coder-next:q8', gb: 85 },
  { match: 'coder-next:q6', gb: 66 },
]

/** Taille approx (Go) si le modele est dans la table des LOURDS, sinon null. */
export function codeModelApproxHeavyGb(model: string | null | undefined): number | null {
  const n = (model ?? '').trim().toLowerCase().replace(/:latest$/, '')
  if (!n) return null
  for (const entry of CODE_HEAVY_MODEL_GB) {
    if (n.includes(entry.match)) return entry.gb
  }
  return null
}

/**
 * true si le modele tient en memoire rapide locale. qwen3-coder-next:q4_K_M et
 * qwen3-coder:30b sont tous deux autorises sur le poste (16GB VRAM + 30GB RAM + NVMe).
 */
export function codeModelFitsRuntime(
  model: string,
  hardware?: Pick<HardwareProfile, 'ram_gb' | 'vram_gb'> | null,
): boolean {
  const gb = codeModelApproxHeavyGb(model)
  if (gb == null) return true
  const budget = (Number(hardware?.vram_gb ?? 0) + Number(hardware?.ram_gb ?? 0)) * 0.85
  if (budget > 0) return gb <= budget
  return true
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
  if (preferredModel?.startsWith('aurora-rl-') && hasInstalledModel(installedModels, preferredModel)) return preferredModel
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
