/**
 * Règles pures de lecture des événements ComfyUI (sans DOM, testables sous Node).
 *
 * Avant : seul le message `progress` (pas k/N) était lu, et appliqué à toute
 * exécution ComfyUI. Pendant le chargement du modèle FLUX.2 (20 Go GGUF) et
 * l'encodage du texte par Mistral-3 sur CPU — souvent plus long que la
 * diffusion elle-même — l'écran affichait « Diffusion en cours » sans bouger ;
 * les pas d'une super-résolution ou d'une autre file étaient lus comme ceux de
 * la diffusion, et une édition Kontext (étape 4) était ramenée à l'étape 3.
 *
 * Maintenant chaque nœud réellement exécuté (`executing`) est classé d'après
 * son type dans le graphe soumis, les pas ne comptent que pour le nœud
 * échantillonneur, et les messages d'une autre exécution sont ignorés.
 */

export type ComfyStage =
  | 'queued'
  | 'load_model'
  | 'load_text_encoder'
  | 'load_vae'
  | 'encode_text'
  | 'encode_reference'
  | 'sampling'
  | 'decode'
  | 'upscale'
  | 'save'
  | 'done'
  | 'error'
  | 'other'

export const COMFY_STAGE_LABEL: Record<ComfyStage, string> = {
  queued: 'En file ComfyUI',
  load_model: 'Chargement du modèle FLUX.2 en VRAM',
  load_text_encoder: 'Chargement de l’encodeur de texte Mistral-3',
  load_vae: 'Chargement du VAE FLUX.2',
  encode_text: 'Encodage du prompt (Mistral-3 Small)',
  encode_reference: 'Encodage de l’image de référence',
  sampling: 'Diffusion FLUX.2',
  decode: 'Décodage VAE de l’image',
  upscale: 'Super-résolution RealESRGAN',
  save: 'Enregistrement du PNG',
  done: 'Rendu ComfyUI terminé',
  error: 'Erreur ComfyUI',
  other: 'Calcul ComfyUI',
}

/** Classe d'un nœud du graphe d'après son `class_type`. */
export function classifyComfyNode(classType: string | undefined | null): ComfyStage {
  const c = String(classType || '')
  if (!c) return 'other'
  if (/^(UnetLoaderGGUF|UNETLoader|CheckpointLoader\w*|DiffusionModelLoader\w*|LoraLoader\w*)$/i.test(c)) return 'load_model'
  if (/CLIPLoader|TextEncoderLoader/i.test(c)) return 'load_text_encoder'
  if (/^VAELoader$/i.test(c)) return 'load_vae'
  if (/CLIPTextEncode|TextEncode/i.test(c)) return 'encode_text'
  if (/^(LoadImage\w*|VAEEncode\w*|ReferenceLatent|ImageStitch|FluxKontextImageScale)$/i.test(c)) return 'encode_reference'
  if (/Sampler|KSampler/i.test(c)) return 'sampling'
  if (/VAEDecode/i.test(c)) return 'decode'
  if (/Upscale|ImageScale/i.test(c)) return 'upscale'
  if (/^(SaveImage\w*|PreviewImage)$/i.test(c)) return 'save'
  return 'other'
}

/** Ordre des sous-étapes d'un rendu, pour qu'un message tardif ne fasse pas reculer l'écran. */
const STAGE_ORDER: Record<ComfyStage, number> = {
  queued: 0, load_model: 1, load_text_encoder: 1, load_vae: 1, encode_text: 2, encode_reference: 3,
  sampling: 4, decode: 5, upscale: 6, save: 7, done: 8, error: 8, other: -1,
}

export function stageRank(stage: ComfyStage): number {
  return STAGE_ORDER[stage]
}

/**
 * Fraction de l'étape « Diffusion » (ou « Édition Kontext ») réellement atteinte.
 * Chargements et encodage occupent le début, les pas k/N le cœur, le décodage la fin.
 * La super-résolution et l'enregistrement appartiennent à la Finalisation (null ici).
 */
export function diffusionPhaseFraction(stage: ComfyStage, step?: number, max?: number): number | null {
  switch (stage) {
    case 'queued': return 0
    case 'load_model':
    case 'load_text_encoder':
    case 'load_vae': return 0.04
    case 'encode_text': return 0.12
    case 'encode_reference': return 0.17
    case 'sampling': {
      const r = typeof step === 'number' && typeof max === 'number' && max > 0 ? Math.min(1, Math.max(0, step / max)) : 0
      return 0.2 + 0.7 * r
    }
    case 'decode': return 0.93
    default: return null
  }
}

export type ComfyRunInfo = {
  promptId: string
  module: string
  /** étape de l'écran pendant la diffusion de ce graphe (2 = Diffusion FLUX, 3 = Édition Kontext) */
  phaseIndex: number
  /** classe de chaque nœud du graphe soumis */
  nodeClass: Record<string, string>
  /** rendu n/total d'un lot */
  batchLabel?: string
}

export function nodeClassesOf(workflow: unknown): Record<string, string> {
  const out: Record<string, string> = {}
  if (!workflow || typeof workflow !== 'object') return out
  for (const [id, node] of Object.entries(workflow as Record<string, unknown>)) {
    const ct = node && typeof node === 'object' ? (node as { class_type?: unknown }).class_type : undefined
    if (typeof ct === 'string') out[id] = ct
  }
  return out
}

export type ComfyMessage = { type?: string; data?: Record<string, unknown> }

export type ComfyLiveEvent = {
  promptId?: string
  stage: ComfyStage
  label: string
  /** pas de diffusion réellement calculé (nœud échantillonneur uniquement) */
  step?: number
  max?: number
  /** tuile d'une super-résolution */
  subStep?: number
  subMax?: number
  queueRemaining?: number
  /** le message doit être journalisé (changement de sous-étape, 1er/dernier pas, tous les 4 pas) */
  log?: string
  /** nœuds sautés car déjà en cache (modèle déjà chargé…) */
  cached?: number
  error?: string
}

/**
 * Interprète un message JSON ComfyUI pour l'exécution suivie.
 * Rend null pour un message d'une autre exécution ou sans intérêt.
 */
export function interpretComfyMessage(
  msg: ComfyMessage,
  run: ComfyRunInfo | null,
  state: { stage: ComfyStage; lastLoggedStep: number },
): ComfyLiveEvent | null {
  const type = msg?.type
  const data = (msg?.data ?? {}) as Record<string, unknown>
  const pid = typeof data.prompt_id === 'string' ? data.prompt_id : undefined
  if (run && pid && pid !== run.promptId) return null
  const nodeId = data.node == null ? null : String(data.node)
  const classOf = (id: string | null) => (id && run ? run.nodeClass[id] : undefined)
  const batch = run?.batchLabel ? ` (${run.batchLabel})` : ''

  if (type === 'status') {
    const q = (data.status as { exec_info?: { queue_remaining?: number } } | undefined)?.exec_info?.queue_remaining
    if (typeof q === 'number' && run && stageRank(state.stage) <= 0) {
      return { promptId: run.promptId, stage: 'queued', label: q > 1 ? `En file ComfyUI — ${q - 1} rendu(s) devant` : COMFY_STAGE_LABEL.queued, queueRemaining: q }
    }
    return null
  }
  if (type === 'execution_start') {
    return { promptId: pid, stage: 'load_model', label: `Démarrage du graphe FLUX.2${batch}`, log: `ComfyUI démarre l’exécution${pid ? ` #${pid.slice(0, 8)}` : ''}` }
  }
  if (type === 'execution_cached') {
    const nodes = Array.isArray(data.nodes) ? data.nodes.length : 0
    if (!nodes) return null
    return { promptId: pid, stage: state.stage, label: COMFY_STAGE_LABEL[state.stage], cached: nodes, log: `${nodes} nœud(s) déjà en cache (modèles déjà chargés)` }
  }
  if (type === 'executing') {
    if (nodeId == null) {
      return pid ? { promptId: pid, stage: 'done', label: COMFY_STAGE_LABEL.done } : null
    }
    const cls = classOf(nodeId)
    const stage = run ? classifyComfyNode(cls) : 'other'
    if (stage === 'other' || stageRank(stage) < stageRank(state.stage)) return null
    if (stage === state.stage) return null
    return { promptId: pid, stage, label: `${COMFY_STAGE_LABEL[stage]}${batch}`, log: `${COMFY_STAGE_LABEL[stage]}${cls ? ` (${cls})` : ''}` }
  }
  if (type === 'progress') {
    const value = typeof data.value === 'number' ? data.value : NaN
    const max = typeof data.max === 'number' ? data.max : NaN
    if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return null
    const cls = classOf(nodeId)
    const stage = cls ? classifyComfyNode(cls) : run ? state.stage : 'sampling'
    if (stage === 'upscale') {
      return { promptId: pid, stage, label: `${COMFY_STAGE_LABEL.upscale} — tuile ${value}/${max}${batch}`, subStep: value, subMax: max }
    }
    if (stage !== 'sampling' && cls) return null
    const pct = Math.round((value / max) * 100)
    const shouldLog = value === 1 || value === max || value - state.lastLoggedStep >= 4
    return {
      promptId: pid,
      stage: 'sampling',
      label: `${COMFY_STAGE_LABEL.sampling} — pas ${value}/${max} (${pct} %)${batch}`,
      step: value,
      max,
      log: shouldLog ? `Diffusion FLUX.2 : pas ${value}/${max} (${pct} %)` : undefined,
    }
  }
  if (type === 'executed') {
    const cls = classOf(nodeId)
    if (run && cls && classifyComfyNode(cls) !== 'save') return null
    return { promptId: pid, stage: 'save', label: `${COMFY_STAGE_LABEL.save}${batch}`, log: 'Image écrite par ComfyUI' }
  }
  if (type === 'execution_success') return { promptId: pid, stage: 'done', label: COMFY_STAGE_LABEL.done }
  if (type === 'execution_error' || type === 'execution_interrupted') {
    const err = typeof data.exception_message === 'string' ? data.exception_message : type === 'execution_interrupted' ? 'interrompu' : 'erreur'
    return { promptId: pid, stage: 'error', label: COMFY_STAGE_LABEL.error, error: err, log: `ComfyUI : ${err}` }
  }
  return null
}

/**
 * Patch d'écran pour le module Image d'après un événement : l'étape vient du
 * graphe enregistré (Diffusion ou Kontext), jamais d'une valeur codée en dur ;
 * la super-résolution et l'enregistrement passent à la Finalisation.
 */
export function imagePatchForEvent(ev: ComfyLiveEvent, run: ComfyRunInfo | null, ranges: [number, number][]): {
  phaseIndex: number
  progress?: number
  phaseFraction?: number
  progressKind?: 'fine' | 'stage'
} | null {
  const diffusionIdx = run?.phaseIndex ?? 2
  const finalIdx = Math.max(0, ranges.length - 1)
  if (ev.stage === 'upscale' || ev.stage === 'save' || ev.stage === 'done') {
    const [a, b] = ranges[finalIdx] ?? [0.92, 1]
    const f = ev.stage === 'upscale'
      ? 0.1 + 0.5 * (ev.subMax ? Math.min(1, (ev.subStep ?? 0) / ev.subMax) : 0)
      : ev.stage === 'save' ? 0.65 : 0.7
    const fine = ev.stage === 'upscale' && Boolean(ev.subMax)
    // seule une mesure continue (tuiles) nourrit la vitesse de l'étape ; un jalon non
    return { phaseIndex: finalIdx, progress: a + (b - a) * f, phaseFraction: fine ? f : undefined, progressKind: fine ? 'fine' : 'stage' }
  }
  if (ev.stage === 'error' || ev.stage === 'other') return null
  const frac = diffusionPhaseFraction(ev.stage, ev.step, ev.max)
  if (frac == null) return { phaseIndex: diffusionIdx }
  const [a, b] = ranges[diffusionIdx] ?? [0.35, 0.8]
  const fine = ev.stage === 'sampling' && typeof ev.step === 'number'
  return {
    phaseIndex: diffusionIdx,
    progress: a + (b - a) * frac,
    // les jalons (chargement, encodage, décodage) ne sont pas une vitesse mesurée
    phaseFraction: fine ? frac : undefined,
    progressKind: fine ? 'fine' : 'stage',
  }
}

/** Durée médiane mesurée d'un pas de diffusion (s), ou null avant deux pas reçus. */
export function medianStepSeconds(stepTimes: number[]): number | null {
  if (stepTimes.length < 2) return null
  const d: number[] = []
  for (let i = 1; i < stepTimes.length; i++) {
    const v = stepTimes[i] - stepTimes[i - 1]
    if (v > 0 && v < 600000) d.push(v)
  }
  if (!d.length) return null
  d.sort((a, b) => a - b)
  return d[Math.floor(d.length / 2)] / 1000
}

/** Sous-étapes affichées par le pipeline de l'écran Image, dans l'ordre réel d'exécution. */
export const IMAGE_PIPELINE: Array<{ stages: ComfyStage[]; label: string }> = [
  { stages: ['queued'], label: 'File ComfyUI' },
  { stages: ['load_model', 'load_text_encoder', 'load_vae'], label: 'Chargement des poids' },
  { stages: ['encode_text', 'encode_reference'], label: 'Encodage du prompt' },
  { stages: ['sampling'], label: 'Diffusion' },
  { stages: ['decode'], label: 'Décodage VAE' },
  { stages: ['upscale'], label: 'Super-résolution' },
  { stages: ['save', 'done'], label: 'Enregistrement' },
]

/**
 * Niveau de bruit d'un planificateur à décalage (flow matching de FLUX) au pas k/N.
 * Approximation (décalage 3) : sert à montrer la courbe et la position du pas réel,
 * pas à mesurer le bruit effectif du rendu.
 */
export function fluxSigmaAt(step: number, max: number, shift = 3): number {
  if (!max || max <= 0) return 1
  const t = Math.max(0, Math.min(1, 1 - step / max))
  return (shift * t) / (1 + (shift - 1) * t)
}
