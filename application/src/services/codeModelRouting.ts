import type { HardwareProfile } from '../types/app.ts'
import {
  CODE_AGENT_MODEL,
  CODE_AGENT_FALLBACK_MODEL,
  CODE_BALANCED_MODEL,
  CODE_CLOUD_HIGH_MODEL,
  CODE_LOCAL_PRIMARY_MODEL,
  CODE_NEXT_MODEL,
  CODE_PLANNING_MODEL,
  CODE_REVIEW_MODEL,
  CODE_REASONING_MODEL,
  CODE_VERIFIER_MODEL,
  DEFAULT_MAIN_MODEL,
  MAIN_FALLBACK_MODEL,
  codeModelFitsRuntime,
  selectCodeModelForHardware,
} from '../config/models.ts'
import type { CodeIntent } from './codeIntent.ts'

export type CodeModelPhase = 'planning' | 'generation' | 'review' | 'correction'

export type CodeModelRoutingContext = {
  configuredCodeModel?: string | null
  installedModels?: string[]
  hardware?: Pick<HardwareProfile, 'ram_gb' | 'vram_gb'> | null
  plateau?: boolean
  /**
   * Tests and explicit preparation flows can opt into returning a role model
   * before /api/tags sees it. The live pipeline keeps this false: no blind swap
   * to a model that Ollama has not reported locally.
   */
  allowUninstalledRoleModels?: boolean
}

export type CodeModelRouteDecision = {
  phase: CodeModelPhase
  role: 'architect' | 'coder' | 'verifier'
  model: string
  coderModel: string
  distinctFromCoder: boolean
  reason: string
  installedMatch: boolean
}

const PLANNING_MODEL_CANDIDATES = [
  CODE_AGENT_MODEL,
  CODE_AGENT_FALLBACK_MODEL,
  CODE_PLANNING_MODEL,
  CODE_REASONING_MODEL,
  CODE_BALANCED_MODEL,
  'qwen3:32b-q4_K_M',
  'qwen3:32b-q6_K',
  'qwen3:32b-q6_K_M',
  DEFAULT_MAIN_MODEL,
  MAIN_FALLBACK_MODEL,
]

const REVIEW_MODEL_CANDIDATES = [
  CODE_REVIEW_MODEL,
  CODE_AGENT_MODEL,
  CODE_VERIFIER_MODEL,
  CODE_BALANCED_MODEL,
  'qwen3:32b-q4_K_M',
  'qwen3:32b-q6_K',
  'qwen3:32b-q6_K_M',
  DEFAULT_MAIN_MODEL,
  MAIN_FALLBACK_MODEL,
]

const PLATEAU_ESCALATION_CANDIDATES = [
  CODE_CLOUD_HIGH_MODEL,
  CODE_NEXT_MODEL,
  CODE_BALANCED_MODEL,
  CODE_REVIEW_MODEL,
  CODE_VERIFIER_MODEL,
]

function compactCandidates(candidates: string[]) {
  const seen = new Set<string>()
  const compacted: string[] = []
  for (const candidate of candidates) {
    const normalized = normalizeOllamaModelName(candidate)
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    compacted.push(candidate)
  }
  return compacted
}

export function normalizeOllamaModelName(model: string | null | undefined) {
  return (model ?? '').trim().replace(/:latest$/i, '').toLowerCase()
}

export function codeModelNamesEqual(a: string | null | undefined, b: string | null | undefined) {
  return normalizeOllamaModelName(a) === normalizeOllamaModelName(b)
}

function installedModelMatchesCandidate(installedModel: string, candidate: string) {
  const installed = normalizeOllamaModelName(installedModel)
  const target = normalizeOllamaModelName(candidate)
  if (!installed || !target) return false
  if (installed === target) return true
  if (target.startsWith('hf.co/')) return false
  if (installed.endsWith(`/${target}`) || target.endsWith(`/${installed}`)) return true
  return installed.startsWith(`${target}-`) || installed.startsWith(`${target}_`)
}

function findInstalledModel(installedModels: string[], candidate: string) {
  return installedModels.find((installed) => installedModelMatchesCandidate(installed, candidate)) ?? null
}

function pickIndependentRoleModel(
  candidates: string[],
  installedModels: string[],
  coderModel: string,
  allowUninstalled: boolean,
  hardware?: CodeModelRoutingContext['hardware'],
) {
  // Garde anti-gel: on ne considere jamais un modele qui ne tient pas en memoire
  // rapide locale (sinon pagination disque -> gel du poste, vecu avec le 80B).
  const compacted = compactCandidates(candidates).filter((candidate) =>
    codeModelFitsRuntime(candidate, hardware),
  )
  for (const candidate of compacted) {
    const installed = findInstalledModel(installedModels, candidate)
    if (installed && !codeModelNamesEqual(installed, coderModel)) {
      return { model: installed, installedMatch: true }
    }
  }

  if (allowUninstalled) {
    const uninstalled = compacted.find((candidate) => !codeModelNamesEqual(candidate, coderModel))
    if (uninstalled) return { model: uninstalled, installedMatch: false }
  }

  return null
}

function roleForPhase(phase: CodeModelPhase): CodeModelRouteDecision['role'] {
  if (phase === 'planning') return 'architect'
  if (phase === 'generation') return 'coder'
  return 'verifier'
}

export function selectCodeRoleModel(
  phase: CodeModelPhase,
  intent: CodeIntent,
  escalationLevel: number,
  context: CodeModelRoutingContext = {},
): CodeModelRouteDecision {
  const installedModels = context.installedModels ?? []
  const configured = context.configuredCodeModel || CODE_LOCAL_PRIMARY_MODEL
  const coderModel = selectCodeModelForHardware(context.hardware, installedModels, configured)

  if (phase === 'generation') {
    if (context.plateau && escalationLevel > 0) {
      const escalated = pickIndependentRoleModel(
        PLATEAU_ESCALATION_CANDIDATES,
        installedModels,
        coderModel,
        Boolean(context.allowUninstalledRoleModels),
        context.hardware,
      )
      if (escalated) {
        return {
          phase,
          role: 'coder',
          model: escalated.model,
          coderModel,
          distinctFromCoder: true,
          reason: `generation:plateau-cloud-escalation:${escalationLevel}`,
          installedMatch: escalated.installedMatch,
        }
      }
    }
    return {
      phase,
      role: 'coder',
      model: coderModel,
      coderModel,
      distinctFromCoder: false,
      reason: 'generation:selectCodeModelForHardware',
      installedMatch: installedModels.length === 0
        ? false
        : Boolean(findInstalledModel(installedModels, coderModel)),
    }
  }

  const candidates = phase === 'planning'
    ? PLANNING_MODEL_CANDIDATES
    : context.plateau
      ? [...PLATEAU_ESCALATION_CANDIDATES, ...REVIEW_MODEL_CANDIDATES]
      : REVIEW_MODEL_CANDIDATES
  const selected = pickIndependentRoleModel(
    candidates,
    installedModels,
    coderModel,
    Boolean(context.allowUninstalledRoleModels),
    context.hardware,
  )

  if (selected) {
    return {
      phase,
      role: roleForPhase(phase),
      model: selected.model,
      coderModel,
      distinctFromCoder: true,
      reason: [
        phase,
        context.plateau ? 'plateau-cloud-escalation' : 'independent-role-model',
        escalationLevel > 0 ? `escalation-${escalationLevel}` : '',
      ].filter(Boolean).join(':'),
      installedMatch: selected.installedMatch,
    }
  }

  const complexity = intent.complexity ? `:${intent.complexity}` : ''
  return {
    phase,
    role: roleForPhase(phase),
    model: coderModel,
    coderModel,
    distinctFromCoder: false,
    reason: `${phase}:fallback-coder-no-independent-model${complexity}`,
    installedMatch: installedModels.length === 0
      ? false
      : Boolean(findInstalledModel(installedModels, coderModel)),
  }
}
