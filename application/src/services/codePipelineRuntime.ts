import type { CodeIntent } from './codeIntent.ts'
import {
  type CodeModelPhase,
  type CodeModelRouteDecision,
  type CodeModelRoutingContext,
  selectCodeRoleModel,
} from './codeModelRouting.ts'

export const PREFLIGHT_PHASE_TIMEOUT_MS = 55_000
export const RESEARCH_PHASE_TIMEOUT_MS = 25_000
export const STREAM_GENERATION_TOTAL_TIMEOUT_MS = 2_700_000
export const PLANNING_TIMEOUT_MS = 900_000
export const CORRECTION_TIMEOUT_MS = 1_200_000
export const PLANNING_FIRST_BYTE_TIMEOUT_MS = 720_000
export const GENERATION_FIRST_BYTE_TIMEOUT_MS = 900_000
export const CORRECTION_FIRST_BYTE_TIMEOUT_MS = 900_000
export const DOCUMENTATION_EXTENSIONS_EARLY = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
export const CODE_PLANNING_CONTEXT_TOKENS = 16_384
export const CODE_EXPERT_CONTEXT_TOKENS = 24_576
export const CODE_EXPERT_OUTPUT_TOKENS = 16_000
export const INTERACTIVE_3D_FIDELITY_MAX_PASSES = 4

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
