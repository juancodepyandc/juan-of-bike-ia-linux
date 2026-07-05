import type { ModuleAssetDefinition } from '../types/app'
import {
  AUXILIARY_ANALYSIS_MODEL,
  IMAGE_CLIP_MODEL,
  IMAGE_T5_MODEL,
  IMAGE_UNET_MODEL,
  IMAGE_VAE_MODEL,
  THREE_D_MULTIVIEW_MODEL,
  THREE_D_SHAPE_MODEL,
  THREE_D_TEXTURE_MODEL,
  VIDEO_FALLBACK_MODEL,
  VIDEO_I2V_MODEL,
  VIDEO_T2V_MODEL,
  VIDEO_UNIFIED_5B_MODEL,
  VOICE_STT_MODEL,
  VOICE_TTS_MODEL,
} from './models'

const FLUX_UNET_REPO = 'Comfy-Org/flux1-dev'
const FLUX_TEXT_ENCODERS_REPO = 'comfyanonymous/flux_text_encoders'
const FLUX_AE_REPO = 'Comfy-Org/Lumina_Image_2.0_Repackaged'
const FLUX_AE_FILENAME = 'split_files/vae/ae.safetensors'

function buildFluxAssets(comfyuiPath: string | null): ModuleAssetDefinition[] {
  return [
    {
      id: 'flux-unet',
      label: 'FLUX UNet FP8',
      kind: 'hf_file',
      target: IMAGE_UNET_MODEL,
      detail: 'UNet principal ComfyUI pour Image, Drawing et reference 3D.',
      repoId: FLUX_UNET_REPO,
      filename: IMAGE_UNET_MODEL,
      destination: `models/unet/${IMAGE_UNET_MODEL}`,
    },
    {
      id: 'flux-t5',
      label: 'T5 XXL FP8',
      kind: 'hf_file',
      target: IMAGE_T5_MODEL,
      detail: 'Encodeur texte haute precision charge cote CPU.',
      repoId: FLUX_TEXT_ENCODERS_REPO,
      filename: IMAGE_T5_MODEL,
      destination: `models/clip/${IMAGE_T5_MODEL}`,
    },
    {
      id: 'flux-clip',
      label: 'CLIP-L',
      kind: 'hf_file',
      target: IMAGE_CLIP_MODEL,
      detail: 'Encodeur CLIP local pour renforcer la fidelite visuelle.',
      repoId: FLUX_TEXT_ENCODERS_REPO,
      filename: IMAGE_CLIP_MODEL,
      destination: `models/clip/${IMAGE_CLIP_MODEL}`,
    },
    {
      id: 'flux-ae',
      label: 'Autoencoder FLUX',
      kind: 'hf_file',
      target: IMAGE_VAE_MODEL,
      detail: 'AE/VAE local pour le rendu final du pipeline FLUX.',
      repoId: FLUX_AE_REPO,
      filename: FLUX_AE_FILENAME,
      destination: `models/vae/${IMAGE_VAE_MODEL}`,
    },
  ]
}

function buildPythonRuntimeAsset(id: string, label: string, detail: string, prepareMode: string): ModuleAssetDefinition {
  return {
    id,
    label,
    kind: 'python_runtime',
    target: `${prepareMode}-runtime`,
    detail,
    prepareMode,
  }
}

export function buildConversationModuleAssets(mainModel: string, visionModel: string, includeVision = true): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: 'conversation-main',
      label: 'LLM conversation',
      kind: 'ollama_model',
      target: mainModel,
      detail: 'Modele principal du copilote conversation.',
    },
  ]

  if (includeVision) {
    assets.push({
      id: 'conversation-vlm',
      label: 'VLM conversation',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Modele multimodal pour les pieces jointes et images.',
    })
  }

  return assets
}

/**
 * Modele code expert pour tout le pipeline.
 * Les roles (Architecte, Codeur, Auditeur) sont geres par les system prompts.
 */
export function buildCodeModuleAssets(
  codeModel: string,
  visionModel: string,
  _planningModel?: string,
  includeVision = true,
): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: 'code-single',
      label: `LLM code (${codeModel})`,
      kind: 'ollama_model',
      target: codeModel,
      detail: 'Modele code operationnel: generation, correction et planification via prompts specialises.',
    },
  ]

  if (includeVision) {
    assets.push({
      id: 'code-vlm',
      label: 'VLM code',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Vision locale pour captures, PDF et references visuelles.',
    })
  }

  return assets
}

export function buildLearningModuleAssets(mainModel: string, visionModel: string, includeVision = true): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: 'learning-main',
      label: 'LLM academie',
      kind: 'ollama_model',
      target: mainModel,
      detail: 'Modele principal pour quiz, cours et parcours.',
    },
    {
      id: 'learning-analysis',
      label: 'Analyse academique',
      kind: 'ollama_model',
      target: AUXILIARY_ANALYSIS_MODEL,
      detail: 'Analyse pedagogique et contrat de precision.',
    },
  ]

  if (includeVision) {
    assets.splice(1, 0, {
      id: 'learning-vlm',
      label: 'VLM academie',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Lecture multimodale des images, PDF et tableurs.',
    })
  }

  return assets
}

export function buildImageModuleAssets(visionModel: string, comfyuiPath: string | null, includeVision = true): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: 'image-analysis',
      label: 'Analyse image',
      kind: 'ollama_model',
      target: AUXILIARY_ANALYSIS_MODEL,
      detail: 'Analyse de scene et contrat visuel avant FLUX.',
    },
    ...buildFluxAssets(comfyuiPath),
  ]

  if (includeVision) {
    assets.unshift({
      id: 'image-vlm',
      label: 'VLM image',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Vision locale pour references, moodboards et captures.',
    })
  }

  return assets
}

export function buildDrawingModuleAssets(visionModel: string, comfyuiPath: string | null, includeVision = true): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: 'drawing-analysis',
      label: 'Analyse drawing',
      kind: 'ollama_model',
      target: AUXILIARY_ANALYSIS_MODEL,
      detail: 'Analyse du brief et du croquis avant rendu.',
    },
    ...buildFluxAssets(comfyuiPath),
  ]

  if (includeVision) {
    assets.unshift({
      id: 'drawing-vlm',
      label: 'VLM drawing',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Vision locale pour croquis, references et contexte joint.',
    })
  }

  return assets
}

export function buildVideoModuleAssets(
  visionModel: string,
  useImageToVideo: boolean,
  includeVision = true,
  vramGb = 0,
): ModuleAssetDefinition[] {
  // v84 : sur <22GB VRAM, video_generate.py route vers TI2V-5B (unifie
  // T2V+I2V) — preparer l'A14B de 28GB etait un telechargement inutile qui
  // saturait le disque avant meme le premier rendu.
  const useUnified5B = vramGb > 0 && vramGb < 22
  const activeVideoModel = useUnified5B
    ? VIDEO_UNIFIED_5B_MODEL
    : (useImageToVideo ? VIDEO_I2V_MODEL : VIDEO_T2V_MODEL)
  const activeLabel = useUnified5B
    ? 'Wan 2.2 TI2V-5B (unifie)'
    : (useImageToVideo ? 'Wan 2.2 I2V' : 'Wan 2.2 T2V')

  const assets: ModuleAssetDefinition[] = [
    {
      id: 'video-analysis',
      label: 'Analyse video',
      kind: 'ollama_model',
      target: AUXILIARY_ANALYSIS_MODEL,
      detail: 'Analyse de scene, rythme et coherence avant rendu.',
    },
    buildPythonRuntimeAsset(
      'video-runtime',
      'Runtime video CUDA',
      'Python CUDA, diffusers et dependances Wan verifies pour le module video.',
      'video',
    ),
    {
      id: useImageToVideo ? 'video-wan-i2v' : 'video-wan-t2v',
      label: activeLabel,
      kind: 'hf_snapshot',
      target: activeVideoModel,
      detail: 'Pipeline diffusers local mis en cache avant execution.',
      repoId: activeVideoModel,
    },
    {
      id: 'video-ltx-fallback',
      label: 'LTX Video secours',
      kind: 'hf_snapshot',
      target: VIDEO_FALLBACK_MODEL,
      detail: 'Fallback haut de gamme plus stable si Wan 2.2 depasse le budget memoire machine.',
      repoId: VIDEO_FALLBACK_MODEL,
    },
  ]

  if (includeVision) {
    assets.unshift({
      id: 'video-vlm',
      label: 'VLM video',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Vision locale pour references image, storyboard et PDF.',
    })
  }

  return assets
}

export function buildVoiceModuleAssets(): ModuleAssetDefinition[] {
  return [
    buildPythonRuntimeAsset(
      'voice-runtime',
      'Runtime vocal',
      'Python, faster-whisper, Kokoro et transformers verifies pour le module vocal.',
      'voice',
    ),
    {
      id: 'voice-voxtral',
      label: 'Voxtral STT',
      kind: 'hf_snapshot',
      target: VOICE_STT_MODEL,
      detail: 'Modele Voxtral-Small-24B pour la transcription vocale haute precision.',
      repoId: VOICE_STT_MODEL,
      allowPatterns: ['*.safetensors', '*.json', 'tokenizer*', 'config*', 'special_tokens*'],
    },
    {
      id: 'voice-kokoro',
      label: 'Kokoro TTS',
      kind: 'hf_snapshot',
      target: VOICE_TTS_MODEL,
      detail: 'Modele Kokoro-82M pour la synthese vocale locale naturelle.',
      repoId: VOICE_TTS_MODEL,
    },
  ]
}

export function buildThreeDModuleAssets(visionModel: string, comfyuiPath: string | null, includeVision = true): ModuleAssetDefinition[] {
  const assets: ModuleAssetDefinition[] = [
    {
      id: '3d-analysis',
      label: 'Analyse 3D',
      kind: 'ollama_model',
      target: AUXILIARY_ANALYSIS_MODEL,
      detail: 'Analyse du brief objet et du contrat de reconstruction.',
    },
    buildPythonRuntimeAsset(
      '3d-runtime',
      'Runtime 3D CUDA',
      'Python CUDA, Hunyuan3D et dependances mesh verifies pour le module 3D.',
      '3d',
    ),
    ...buildFluxAssets(comfyuiPath),
    {
      id: '3d-shape',
      label: 'Hunyuan3D shape',
      kind: 'hf_snapshot',
      target: THREE_D_SHAPE_MODEL,
      detail: 'Pipeline shape mis en cache local avant reconstruction.',
      repoId: THREE_D_SHAPE_MODEL,
      allowPatterns: ['hunyuan3d-dit-v2-1/*'],
    },
    {
      id: '3d-shape-mv',
      label: 'Hunyuan3D multivue',
      kind: 'hf_snapshot',
      target: THREE_D_MULTIVIEW_MODEL,
      detail: 'Pipeline shape multi-vues 1-4 images pour les references front/left/back/right.',
      repoId: THREE_D_MULTIVIEW_MODEL,
      allowPatterns: ['hunyuan3d-dit-v2-mv/*'],
    },
    {
      id: '3d-texture',
      label: 'Hunyuan3D texture',
      kind: 'hf_snapshot',
      target: THREE_D_TEXTURE_MODEL,
      detail: 'Pipeline texture paint mis en cache local avant export.',
      repoId: THREE_D_TEXTURE_MODEL,
      allowPatterns: [
        'hunyuan3d-delight-v2-0/*',
        'hunyuan3d-paint-v2-0/*',
        'hunyuan3d-dit-v2-0/*',
      ],
    },
  ]

  if (includeVision) {
    assets.unshift({
      id: '3d-vlm',
      label: 'VLM 3D',
      kind: 'ollama_model',
      target: visionModel,
      detail: 'Vision locale pour images de reference et contexte joint.',
    })
  }

  return assets
}
