import type { OllamaMessage } from '../types/app.ts'
import {
  analyzeFollowUpIntent,
  type FollowUpAnalysis,
} from './codeFollowUpAnalysis.ts'
import type { CodeIntentContext } from './codeIntent.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestratorTypes.ts'

export async function prepareCodeFollowUpContext({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  configuredCodeModel,
  setPhase,
  onFollowUpAnalysis,
  signal,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  configuredCodeModel: string
  setPhase: PhaseCallback
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  signal?: AbortSignal
}): Promise<{
  followUp: FollowUpAnalysis | null
  reformulatedPrompt: string
  reformulatedEnriched: string
  effectiveExistingFiles: CodeFile[]
  intentContext: CodeIntentContext | undefined
}> {
  const hasContext = conversationHistory.length > 0 || existingFiles.length > 0
  const followUp = hasContext
    ? await (async () => {
        setPhase('Analyse du contexte de la discussion...', 3)
        try {
          return await analyzeFollowUpIntent({
            newPrompt: prompt,
            conversationHistory,
            existingFiles,
            model: configuredCodeModel,
            signal,
          })
        } catch (error) {
          console.warn('[CodeOrchestrator] follow-up analysis failed, continuing without:', error)
          return null
        }
      })()
    : null

  if (followUp) {
    onFollowUpAnalysis?.(followUp)
    setPhase(
      `Mode: ${followUp.kind}${followUp.pivotReason ? ` — ${followUp.pivotReason.slice(0, 60)}` : ''}`,
      5,
    )
  }

  const reformulatedPrompt = followUp?.reformulatedPrompt?.trim() || prompt
  const reformulatedEnriched = followUp?.reformulatedPrompt && followUp.reformulatedPrompt !== prompt
    ? `${enrichedPrompt}\n\n## REFORMULATION CONTEXTUELLE\n${followUp.reformulatedPrompt}`
    : enrichedPrompt
  const effectiveExistingFiles = followUp?.shouldResetFiles ? [] : [...existingFiles]
  const intentContext: CodeIntentContext | undefined = followUp
    ? {
        previousProjectType: followUp.previousProjectType ?? undefined,
        previousLanguages: followUp.previousLanguages,
        previousFrameworks: followUp.previousFrameworks,
        pivotKind: followUp.kind === 'clarify_only' ? 'increment' : followUp.kind,
      }
    : undefined

  return {
    followUp,
    reformulatedPrompt,
    reformulatedEnriched,
    effectiveExistingFiles,
    intentContext,
  }
}
