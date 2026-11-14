import type { CodeIntent } from './codeIntent.ts'
import {
  type CodeModelPhase,
  type CodeModelRouteDecision,
  type CodeModelRoutingContext,
  selectCodeRoleModel,
} from './codeModelRouting.ts'

export const PREFLIGHT_PHASE_TIMEOUT_MS = 180_000
export const RESEARCH_PHASE_TIMEOUT_MS = 90_000
export const STREAM_GENERATION_TOTAL_TIMEOUT_MS = 3_600_000
export const PLANNING_TIMEOUT_MS = 1_800_000
export const CORRECTION_TIMEOUT_MS = 1_200_000
export const PLANNING_FIRST_BYTE_TIMEOUT_MS = 1_200_000
export const GENERATION_FIRST_BYTE_TIMEOUT_MS = 1_800_000
export const CORRECTION_FIRST_BYTE_TIMEOUT_MS = 900_000
export const DOCUMENTATION_EXTENSIONS_EARLY = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
export const CODE_PLANNING_CONTEXT_TOKENS = 32768
export const CODE_EXPERT_CONTEXT_TOKENS = 32768
export const CODE_EXPERT_OUTPUT_TOKENS = 16384
export const INTERACTIVE_3D_FIDELITY_MAX_PASSES = 6

export type { CodeModelPhase, CodeModelRouteDecision, CodeModelRoutingContext }

export function selectModelDecision(
  phase: CodeModelPhase,
  intent: CodeIntent,
  escalationLevel: number,
  configuredCodeModel: string,
  routingContext: CodeModelRoutingContext = {},
): CodeModelRouteDecision {
  return selectCodeRoleModel(phase, intent, escalationLevel, {
    ...routingContext,
    configuredCodeModel: routingContext.configuredCodeModel ?? configuredCodeModel,
  })
}

export function selectModel(
  phase: CodeModelPhase,
  intent: CodeIntent,
  escalationLevel: number,
  configuredCodeModel: string,
  routingContext: CodeModelRoutingContext = {},
): string {
  return selectModelDecision(phase, intent, escalationLevel, configuredCodeModel, routingContext).model
}

export function getModelShortName(model: string) {
  const tail = model.split('/').pop() || model
  return tail.split(':')[0]
}

export function clipText(text: string, maxLength = 2400) {
  const normalized = text.trim()
  return normalized.length <= maxLength
    ? normalized
    : `${normalized.slice(0, maxLength)}\n...[sortie tronquee]`
}
