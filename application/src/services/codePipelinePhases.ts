import type { RecoveryEvent } from './ollamaResilience.ts'
import {
  type CodeIntent,
  type CodeIntentContext,
  buildArchitecturePlanningPrompt,
  classifyCodeIntent,
} from './codeIntent.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import { buildArchitecteSystemPrompt } from './codeSystemPrompts.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import { withTimeout } from './llmTimebox.ts'
import { parseArchitecturePlanJson } from './codeArchitecturePlan.ts'
import {
  getArchitecturePlanCandidateCount,
  selectBestArchitecturePlan,
} from './codeArchitecturePlanSelection.ts'
import {
  CODE_PLANNING_CONTEXT_TOKENS,
  PLANNING_FIRST_BYTE_TIMEOUT_MS,
  PLANNING_TIMEOUT_MS,
  PREFLIGHT_PHASE_TIMEOUT_MS,
  getModelShortName,
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'

export function isArchitecturePlanUsable(plan: string | null) {
  return parseArchitecturePlanJson(plan).ok
}

/** Phase 1: classify intent locally, without an LLM call. */
export function runIntentPhase(
  prompt: string,
  setPhase: PhaseCallback,
  context?: CodeIntentContext,
): CodeIntent {
  setPhase('Classification du projet...', 5)
  return classifyCodeIntent(prompt, context)
}

/** Phase 1.5: inspect the machine and current project before planning. */
export async function runPreflightPhase(
  prompt: string,
  intent: CodeIntent,
  existingFiles: CodeFile[],
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  modelRouting?: CodeModelRoutingContext,
): Promise<CodePreflightReport | null> {
  try {
    setPhase('Preflight local: analyse machine, outils et fichiers existants...', 8)
    const { runCodePreflight } = await import('./codePreflight.ts')
    return await withTimeout(runCodePreflight({
      prompt,
      intent,
      existingFiles,
      model: selectModel('planning', intent, 0, configuredCodeModel, modelRouting),
      setPhase: (detail, progress) => setPhase(detail, Math.max(8, Math.min(18, progress))),
    }), {
      label: 'Code preflight',
      timeoutMs: PREFLIGHT_PHASE_TIMEOUT_MS,
    })
  } catch {
    setPhase('Preflight local indisponible - poursuite avec les informations connues...', 12)
    return null
  }
}

/** Phase 2: produce the structured plan required by the WS3 executor. */
export async function runPlanningPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onRecovery?: (event: RecoveryEvent) => void,
  modelRouting?: CodeModelRoutingContext,
): Promise<string> {
  const model = selectModel('planning', intent, 0, configuredCodeModel, modelRouting)
  setPhase(`Architecte en reflexion (${getModelShortName(model)})...`, 10)
  const preflightBlock = preflightReport
    ? [
        '### PREFLIGHT LOCAL OBLIGATOIRE',
        'Le plan doit s appuyer sur ce diagnostic local avant toute decision de stack ou de configuration.',
        (await import('./codePreflight.ts')).serializeCodePreflightReport(preflightReport),
      ].join('\n')
    : ''
  const planPrompt = [
    buildArchitecteSystemPrompt(intent),
    '',
    '---',
    '',
    buildArchitecturePlanningPrompt(prompt, intent),
    preflightBlock,
  ].filter(Boolean).join('\n\n')

  try {
    const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
    const candidateCount = getArchitecturePlanCandidateCount(intent)
    const rawCandidates: string[] = []
    for (let candidateIndex = 0; candidateIndex < candidateCount; candidateIndex++) {
      if (candidateCount > 1) {
        setPhase(`Architecte best-of-${candidateCount} - candidat ${candidateIndex + 1}/${candidateCount}...`, 12 + candidateIndex * 5)
      }
      const response = await resilientOllamaGenerate(
        model,
        candidateIndex === 0
          ? planPrompt
          : `${planPrompt}\n\nVARIANTE ${candidateIndex + 1}: produis une architecture alternative, toujours au meme schema JSON, avec une meilleure decomposition si possible.`,
        {
          timeoutMs: PLANNING_TIMEOUT_MS,
          firstByteTimeoutMs: PLANNING_FIRST_BYTE_TIMEOUT_MS,
          num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
          neverMemorySkip: true,
          onRecoveryAttempt: (event) => {
            if (event.action !== 'retry') {
              setPhase(`Architecte - ${event.action}...`, 16)
              onRecovery?.(event)
            }
          },
        },
      )
      rawCandidates.push(response?.response?.trim() || '')
    }

    const selection = selectBestArchitecturePlan(rawCandidates)
    if (selection.selected?.serialized) {
      const suffix = candidateCount > 1
        ? ` (best-of-${candidateCount}, candidat ${selection.selected.index + 1})`
        : ''
      setPhase(`Plan d architecture pret${suffix} - lancement de la generation agentique...`, 25)
      return selection.selected.serialized
    }

    const errors = selection.scored.flatMap((candidate) => candidate.errors).slice(0, 3)
    throw new Error(`architecture_plan_invalid:${errors.join(',') || 'empty_response'}`)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn('[CodeOrchestrator] Structured planning failed:', message)
    setPhase(`Plan d architecture inexploitable - generation bloquee (${message.slice(0, 80)})`, 22)
    throw new Error(`Echec du plan d architecture structure: ${message}`)
  }
}
