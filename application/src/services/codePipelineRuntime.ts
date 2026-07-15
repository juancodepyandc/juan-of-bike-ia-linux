import type { CodeIntent } from './codeIntent.ts'

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

/**
 * Current WS1 extraction preserves the existing behavior exactly: one
 * configured code model is used for all phases. WS4 gives this function a real
 * multi-model implementation.
 */
export function selectModel(
  _phase: 'planning' | 'generation' | 'review' | 'correction',
  _intent: CodeIntent,
  _escalationLevel: number,
  configuredCodeModel: string,
): string {
  return configuredCodeModel
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
