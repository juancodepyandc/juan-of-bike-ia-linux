/**
 * Règles pures de synchronisation de l'écran de génération : quelle étape est
 * réellement en cours, dans quel état se trouve le personnage, et quelle
 * progression l'animation doit montrer. Aucune de ces fonctions ne fait
 * avancer un pourcentage chiffré avec le temps.
 */
import type { FxModule } from './fxBus.ts'
import type { MascotState } from './mascots.tsx'

export type FxStage = 'queued' | 'preparing' | 'running' | 'finalizing' | 'done'

/** Plages de progression des producteurs dont le pourcentage suit les étapes. */
export const MODULE_PHASE_RANGES: Partial<Record<FxModule, [number, number][]>> = {
  '3d': [
    [0.0, 0.15],
    [0.15, 0.4],
    [0.4, 0.7],
    [0.7, 0.85],
    [0.85, 0.95],
    [0.95, 1.0],
  ],
  image: [
    [0.0, 0.2],
    [0.2, 0.35],
    [0.35, 0.8],
    [0.8, 0.92],
    [0.92, 1.0],
  ],
}

const CODE_PHASE_INDEX: Record<string, number> = {
  idle: 0, planning: 1, research: 2, brand: 2, streaming: 3, validation: 4, done: 6, error: 6,
}

/** Index d'étape de l'écran Code pour une phase du pipeline Code, si elle est connue. */
export function codePhaseIndex(phase: string | null | undefined): number | undefined {
  return phase && CODE_PHASE_INDEX[phase] !== undefined ? CODE_PHASE_INDEX[phase] : undefined
}

/** Étapes réelles du run de conversation (`AssistantStage`). */
export const CHAT_STAGE_INDEX: Record<string, number> = {
  understand: 0, plan: 1, draft: 2, verify: 3, refine: 4, done: 5,
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

export type PhaseSignal = {
  text?: string
  index?: number
  progress?: number
  prev: number
  /** le producteur a déjà fourni un index explicite : on ne le déduit plus des pourcentages */
  explicit?: boolean
}

/**
 * Étape réellement atteinte. Priorité : index explicite, « Étape k/n », nom
 * d'étape, état connu du module, plage du pourcentage. Sans indice, l'étape
 * précédente est conservée (jamais un retour arbitraire à la première).
 */
export function resolvePhaseIndex(module: FxModule, phases: string[], s: PhaseSignal): number {
  const last = Math.max(0, phases.length - 1)
  if (typeof s.index === 'number' && Number.isFinite(s.index)) return clamp(Math.round(s.index), 0, last)
  const text = (s.text || '').trim()
  if (text) {
    const needle = text.toLowerCase()
    const step = needle.match(/[eé]tape\s*(\d{1,2})\s*\/\s*(\d{1,2})/)
    if (step) {
      const k = Number(step[1])
      const n = Math.max(1, Number(step[2]))
      if (n === phases.length) return clamp(k - 1, 0, last)
      return clamp(Math.round(((k - 1) / Math.max(1, n - 1)) * last), 0, last)
    }
    if (module === 'code' && CODE_PHASE_INDEX[needle] !== undefined) return clamp(CODE_PHASE_INDEX[needle], 0, last)
    if (module === 'conversation' && CHAT_STAGE_INDEX[needle] !== undefined) return clamp(CHAT_STAGE_INDEX[needle], 0, last)
    const direct = phases.findIndex((p) => needle.includes(p.toLowerCase()) || (needle.length >= 4 && p.toLowerCase() === needle))
    if (direct >= 0) return direct
  }
  const ranges = MODULE_PHASE_RANGES[module]
  if (!s.explicit && typeof s.progress === 'number' && Number.isFinite(s.progress) && ranges) {
    const p = clamp(s.progress, 0, 0.999)
    const i = ranges.findIndex(([a, b]) => p >= a && p < b)
    if (i >= 0) return clamp(i, 0, last)
  }
  return clamp(s.prev, 0, last)
}

/** Lignes de contrôle imprimées à plusieurs moments du run (contrôle qualité intermédiaire, rendu de
 * géométrie de vérification, validation et nettoyage du pont Blender, post-traitement du maillage lancé
 * après le pipeline) et lignes de fin de sous-étape (export d'un moteur, contrôle « perfection », rangement
 * de la livraison, suivis de l'animation et de la finalisation de ModelView) : journalisées, sans déplacer
 * l'étape. La Finalisation vient de l'étape « Finalisation » de ModelView. */
export const THREE_D_CONTROL_STAGES = [
  'qualite', 'geometrie', 'validate', 'cleanup',
  'post_start', 'post_warn', 'post_done', 'decimate', 'symmetry', 'symmetry_skip', 'volume_restore', 'target_dimension', 'floaters',
  'export', 'export_fallback', 'perfection', 'livraison', 'finalisation',
]

/**
 * Étape de l'écran 3D d'après le nom d'étape d'une ligne `PROGRESS:<étape>:…`
 * du pipeline Python. Null pour les lignes de service (mémoire, VRAM…) et pour les
 * lignes de contrôle qui apparaissent à plusieurs moments (THREE_D_CONTROL_STAGES).
 */
export function threeDPhaseForStage(stage: string): number | null {
  const s = (stage || '').toLowerCase()
  if (!s || THREE_D_CONTROL_STAGES.includes(s)) return null
  // référence : vues ou photos d'entrée (y compris l'analyse des photos de photogrammétrie)
  if (['reference', 'confirm_req', 'ref', 'web', 'source', 'scan'].includes(s)) return 1
  // sculpture : moteurs neuronaux, scène multi-entités, Blender procédural, photogrammétrie, géométrie
  if (['install', 'device', 'bg', 'asset_scan', 'asset_download', 'shape_fallback', 'shape_load', 'shape_run', 'gaussian', 'procedural', 'sfm', 'photogrammetry', 'mesh_extract', 'shape', 'trellis', 'hunyuan', 'engine', 'scene', 'blender', 'preprocess'].includes(s)) return 2
  // matières : peinture, cuisson, zones de matière, fidélité de texture
  if (['texture_load', 'texture_run', 'texture_retry', 'texture_warn', 'paint', 'bake', 'bake_normal', 'bake_ao', 'texture', 'color', 'matieres', 'fidelity', 'texture_fidelity'].includes(s)) return 3
  if (['animation', 'rig', 'motion'].includes(s)) return 4
  if (['final', 'done'].includes(s)) return 5
  return null
}

/**
 * Étape affichée après une nouvelle indication. La 3D ne recule pas : ses producteurs impriment des
 * lignes de suivi tardives (confirmation de forme après l'arrivée du maillage…). Seule une remise à
 * zéro explicite (refus du contrôle « perfection » suivi d'une régénération) la fait revenir en arrière.
 */
export function monotonicPhase(module: FxModule, prev: number, next: number, reset = false): number {
  if (module !== '3d' || reset) return next
  return Math.max(prev, next)
}

const CHECK_WORDS = /v[ée]rif|valid|sandbox|correction|contr[ôo]le|audit|examen|finalis|livraison|r[ée]v[ée]lation/i

export function mascotStateFor(input: {
  ask?: boolean
  reveal?: boolean
  error?: boolean
  stage: FxStage
  phaseIdx: number
  phaseName?: string
}): MascotState {
  if (input.error) return 'error'
  if (input.ask) return 'asking'
  if (input.reveal || input.stage === 'done') return 'success'
  if (input.stage === 'queued') return 'waiting'
  if (input.stage === 'preparing') return 'thinking'
  if (input.stage === 'finalizing') return 'checking'
  if (input.phaseName && CHECK_WORDS.test(input.phaseName)) return 'checking'
  if (input.phaseIdx === 0) return 'thinking'
  return 'working'
}

export function stageForJob(job: { status: string; phase: string } | null | undefined): FxStage {
  if (!job) return 'running'
  if (job.status === 'queued') return 'queued'
  if (job.status === 'done') return 'done'
  if (job.phase === 'prepare') return 'preparing'
  if (job.phase === 'cleanup') return 'finalizing'
  return 'running'
}

/**
 * Progression montrée par l'animation (pas par les chiffres) : la mesure
 * lissée quand elle existe ; sinon l'étape réelle atteinte, plus un léger
 * mouvement d'ambiance dans l'étape, borné pour ne jamais annoncer la fin.
 */
export function animationProgress(input: {
  measured: number | null
  phaseIdx: number
  phaseCount: number
  phaseAgeMs: number
  elapsedMs: number
  phaseReported: boolean
}): number {
  if (input.measured != null) return clamp(input.measured, 0, 1)
  const n = Math.max(1, input.phaseCount)
  if (!input.phaseReported) return 0.6 * (1 - Math.exp(-input.elapsedMs / 22000))
  const inPhase = 0.45 * (1 - Math.exp(-input.phaseAgeMs / 14000))
  return clamp((input.phaseIdx + inPhase) / n, 0, 0.97)
}
