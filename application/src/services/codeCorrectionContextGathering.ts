// Collecte du CONTEXTE d une passe de correction: recherche en ligne,
// auto-outillage WS14 et analyse de cause racine.
//
// Extrait de codeValidationCorrectionLoop pour tenir la limite de 400 lignes.
// Aucune decision de boucle ici: ce module ne fait que rassembler ce que le
// correcteur doit lire avant d ecrire.

import type { CodeIntent } from './codeIntent.ts'
import type { CorrectionPass, CorrectionStrategy, ErrorCategory } from './codeAutoCorrection.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { PhaseCallback } from './codeOrchestratorTypes.ts'
import { withTimeout } from './llmTimebox.ts'
import { RESEARCH_PHASE_TIMEOUT_MS } from './codePipelineRuntime.ts'

export type CorrectionContext = {
  researchContext: string
  reasoningContext: string
  toolingEvaluationUsed: boolean
}

export async function gatherCorrectionContext({
  prompt,
  attempt,
  strategy,
  intent,
  configuredCodeModel,
  correctionLog,
  errorCategories,
  failingOutputs,
  isFlatlining,
  toolingEvaluationUsed,
  pass,
  currentScore,
  setPhase,
  onCorrectionLogUpdate,
  signal,
}: {
  prompt: string
  attempt: number
  strategy: CorrectionStrategy
  intent: CodeIntent
  configuredCodeModel: string
  correctionLog: CorrectionPass[]
  errorCategories: ErrorCategory[]
  failingOutputs: string[]
  isFlatlining: boolean
  toolingEvaluationUsed: boolean
  pass: CorrectionPass
  currentScore: number
  setPhase: PhaseCallback
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  signal?: AbortSignal
}): Promise<CorrectionContext> {
  let researchContext = ''
  if (strategy.searchWeb) {
    setPhase(`Passe ${attempt} — recherche de solutions en ligne...`, Math.min(93, 72 + attempt * 3))
    try {
      const { searchForSolution } = await import('./codeResearch.ts')
      researchContext = await withTimeout(searchForSolution(failingOutputs.join('\n'), intent, configuredCodeModel), {
        label: 'Code correction research',
        timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
      })
    } catch {
      researchContext = ''
    }
  }

  let toolingContext = ''
  let nextToolingUsed = toolingEvaluationUsed
  if (isFlatlining && !toolingEvaluationUsed) {
    nextToolingUsed = true
    setPhase(`Passe ${attempt} — auto-outillage WS14 en venv isole...`, Math.min(93, 73 + attempt * 3))
    try {
      const {
        evaluateAutoToolingForCorrection,
        formatToolingReportForCorrection,
      } = await import('./codeToolingLoop.ts')
      const toolingReport = await evaluateAutoToolingForCorrection({
        correctionLog,
        errorCategories,
        failingOutputs,
        intent,
        signal,
      })
      if (toolingReport) {
        toolingContext = formatToolingReportForCorrection(toolingReport)
        pass.errors = [`[Auto-outillage WS14]\n${toolingContext}`, ...pass.errors]
        onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
      }
    } catch {
      toolingContext = ''
    }
  }

  let reasoningContext = ''
  if (attempt >= 2 || isFlatlining) {
    setPhase(`Passe ${attempt} — analyse de la cause racine...`, Math.min(93, 73 + attempt * 3))
    const {
      analyzeStuckCorrection,
      buildReasoningInstructions,
    } = await import('./codeReasoningEngine.ts')
    const reasoning = await analyzeStuckCorrection(
      prompt,
      correctionLog,
      intent,
      failingOutputs,
      configuredCodeModel,
    )
    if (reasoning) {
      reasoningContext = buildReasoningInstructions(reasoning)
      setPhase(`Passe ${attempt} — cause identifiee: ${reasoning.rootCause.slice(0, 80)}...`, Math.min(93, 74 + attempt * 3))
    }
  }
  if (toolingContext) {
    reasoningContext = [toolingContext, reasoningContext].filter(Boolean).join('\n\n')
  }

  return { researchContext, reasoningContext, toolingEvaluationUsed: nextToolingUsed }
}
