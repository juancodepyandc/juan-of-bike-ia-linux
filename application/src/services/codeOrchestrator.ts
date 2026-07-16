// ---------------------------------------------------------------------------
// Code Orchestrator — Multi-phase pipeline with model routing
// Equivalent of conversationOrchestrator.ts but specialized for code generation
// ---------------------------------------------------------------------------

import type { OllamaMessage } from '../types/app'
import type { RecoveryEvent } from './ollamaResilience'
import {
  type CodeIntent,
  type CodeIntentContext,
  classifyCodeIntent,
} from './codeIntent'
import {
  buildAutonomousAssumptionNotes,
  buildCodeMissionDossier,
  type CodeMissionDossier,
} from './codeMissionControl'
import type { CorrectionPass } from './codeAutoCorrection'
import type { CodeSandboxResult } from './codeSandbox'
import type { CodePreflightReport } from './codePreflight'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
import {
  buildEmptyGenerationDiagnostic,
} from './codeGenerationDiagnostics.ts'
import { runValidationAndCorrectionLoop } from './codeValidationCorrectionLoop.ts'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
export { upsertProjectSupportFilesForTest } from './codeProjectSupportFiles.ts'
import {
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'
import {
  isArchitecturePlanUsable,
  runIntentPhase,
  runPlanningPhase,
  runPreflightPhase,
} from './codePipelinePhases.ts'
import { prepareCodePlanningContext } from './codePipelinePreparation.ts'
import { runGeneratedOutputRetryLoop } from './codeGenerationOutputRetry.ts'
import { runAgenticGenerationPhase } from './codeAgenticGenerationPhase.ts'
import {
  runInterModuleAssetPhase,
  upsertAssetManifestFile,
  type CodeAssetBundle,
} from './codeInterModuleAssets.ts'
import { finalizeCodePipelineDelivery } from './codePipelineFinalization.ts'
import { materializeInterModuleAssetReferences } from './codeInterModuleAssetIntegration.ts'
import {
  buildDesignRetryHint,
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
  computeDesignPolishReportPublic,
  type DesignPolishReport,
} from './codeQualityGates.ts'
export {
  buildDesignRetryHint,
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
  computeDesignPolishReportPublic,
} from './codeQualityGates.ts'
export type { DesignPolishReport } from './codeQualityGates.ts'
import {
  analyzeFollowUpIntent,
  type FollowUpAnalysis,
  type FollowUpKind,
} from './codeFollowUpAnalysis.ts'
export {
  analyzeFollowUpIntent,
  classifyClarificationSeverity,
  isVagueClarification,
} from './codeFollowUpAnalysis.ts'
export type {
  ClarificationSeverity,
  FollowUpAnalysis,
  FollowUpKind,
} from './codeFollowUpAnalysis.ts'

/**
 * Auto-generate a smart assumption instead of asking a vague question.
 * The code module should be autonomous and prefer assumptions over questions.
 */
export function buildAutonomousAssumption(prompt: string, intent: CodeIntent): string {
  return buildAutonomousAssumptionNotes(prompt, intent)
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeOrchestrationPhase =
  | 'intent'
  | 'preflight'
  | 'planning'
  | 'generation'
  | 'validation'
  | 'correction'
  | 'research'
  | 'dev_server'
  | 'done'
  | 'error'

export type CodeOrchestrationResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  intent: CodeIntent
  preflightReport: CodePreflightReport | null
  correctionLog: CorrectionPass[]
  phase: CodeOrchestrationPhase
  architecturePlan: string | null
  totalAttempts: number
  finalScore: number
  recoveryEvents: RecoveryEvent[]
  /** Follow-up analysis — null when no conversation context was available. */
  followUp: FollowUpAnalysis | null
  /**
   * v73: design polish report attached when the project produced visual
   * output. Lets the UI surface a badge ("Design 82/100 — manque clamp(),
   * @keyframes") instead of leaving the score buried in retry logs.
   */
  designReport?: DesignPolishReport | null
}

export type PhaseCallback = (detail: string, progress: number) => void

// ---------------------------------------------------------------------------
// Main orchestration entry point
// ---------------------------------------------------------------------------

export async function orchestrateCodeGeneration({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  visionModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onRecoveryEvent,
  onFollowUpAnalysis,
  signal,
  modelRouting,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (USER_FILE_0 → data:image/jpeg;base64,...) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  visionModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onRecoveryEvent?: (event: RecoveryEvent) => void
  /** Fires as soon as the follow-up analyzer has decided the pivot kind. */
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  signal?: AbortSignal
  modelRouting?: CodeModelRoutingContext
}): Promise<CodeOrchestrationResult> {
  const generationModel = contextImages.length > 0 ? visionModel : configuredCodeModel
  const recoveryEvents: RecoveryEvent[] = []
  const trackRecovery = (ev: RecoveryEvent) => {
    recoveryEvents.push(ev)
    onRecoveryEvent?.(ev)
  }

  // Top-level crash guard — the pipeline NEVER crashes the app
  try {
    return await runFullPipeline({
      prompt,
      enrichedPrompt,
      conversationHistory,
      existingFiles,
      contextImages,
      userFileDataUrls,
      configuredCodeModel,
      generationModel,
      setPhase,
      onToken,
      onFilesUpdate,
      onValidationUpdate,
      onCorrectionLogUpdate,
      onFollowUpAnalysis,
      trackRecovery,
      recoveryEvents,
      signal,
      modelRouting,
    })
  } catch (fatalError) {
    // Absolute last resort — return error state instead of crashing
    const msg = fatalError instanceof Error ? fatalError.message : String(fatalError)
    console.error('[CodeOrchestrator] Pipeline fatal error (app NOT crashed):', msg)
    setPhase(`Erreur pipeline: ${msg.slice(0, 100)}`, 0)
    return {
      files: [],
      notes: `Erreur fatale du pipeline: ${msg}`,
      sandboxResult: null,
      intent: classifyCodeIntent(enrichedPrompt),
      preflightReport: null,
      correctionLog: [],
      phase: 'error',
      architecturePlan: null,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp: null,
    }
  }
}

// ---------------------------------------------------------------------------
// Full pipeline implementation (isolated for crash-proof wrapping)
// ---------------------------------------------------------------------------

async function runFullPipeline({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  generationModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onFollowUpAnalysis,
  trackRecovery,
  recoveryEvents,
  signal,
  modelRouting,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (forwarded from orchestrateCodeGeneration) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  trackRecovery: (event: RecoveryEvent) => void
  recoveryEvents: RecoveryEvent[]
  signal?: AbortSignal
  modelRouting?: CodeModelRoutingContext
}): Promise<CodeOrchestrationResult> {
  // Phase 0: Follow-up intent analysis — only runs when there is prior context.
  // Turns "la meme chose en python" into a reformulated prompt + pivotKind so
  // the rest of the pipeline does not accidentally carry a stale HTML project.
  const hasContext = conversationHistory.length > 0 || existingFiles.length > 0
  const followUp: FollowUpAnalysis | null = hasContext
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
        } catch (err) {
          console.warn('[CodeOrchestrator] follow-up analysis failed, continuing without:', err)
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

  // The prompt the remaining phases reason on is the reformulation when the
  // analyzer produced one. Keep the original `prompt`/`enrichedPrompt` for
  // places that need the raw user text.
  const reformulatedPrompt = followUp?.reformulatedPrompt?.trim() || prompt
  const reformulatedEnriched = followUp && followUp.reformulatedPrompt && followUp.reformulatedPrompt !== prompt
    ? `${enrichedPrompt}\n\n## REFORMULATION CONTEXTUELLE\n${followUp.reformulatedPrompt}`
    : enrichedPrompt

  // If the analyzer decided we are pivoting platforms or starting fresh,
  // drop the existing files so the Codeur does not see the old HTML while
  // the user actually asked for a Python backend. The migration summary
  // captures the business concept to carry over.
  let effectiveExistingFiles = followUp?.shouldResetFiles ? [] : [...existingFiles]

  // Phase 1: Intent classification (deterministic) — enriched with follow-up context.
  const intentContext: CodeIntentContext | undefined = followUp
    ? {
        previousProjectType: followUp.previousProjectType ?? undefined,
        previousLanguages: followUp.previousLanguages,
        previousFrameworks: followUp.previousFrameworks,
        pivotKind: followUp.kind === 'clarify_only' ? 'increment' : followUp.kind,
      }
    : undefined
  const intent = runIntentPhase(reformulatedEnriched, setPhase, intentContext)

  // Phase 1.5: Deterministic + model-assisted preflight before any code generation
  const preflightReport = await runPreflightPhase(
    prompt,
    intent,
    existingFiles,
    configuredCodeModel,
    setPhase,
    modelRouting,
  )

  const { planningPrompt } = await prepareCodePlanningContext({
    prompt,
    reformulatedEnriched,
    intent,
    followUp,
    configuredCodeModel,
    setPhase,
  })

  // Phase 2: every project needs a valid structured plan because WS3 executes
  // the resulting queue file by file. An invalid plan is a blocking quality gate.
  const architecturePlan = await runPlanningPhase(
    planningPrompt,
    intent,
    preflightReport,
    configuredCodeModel,
    setPhase,
    trackRecovery,
    modelRouting,
  )
  if (!isArchitecturePlanUsable(architecturePlan)) {
    throw new Error('Plan d architecture absent ou invalide: execution WS3 impossible')
  }

  const assetPhase = await runInterModuleAssetPhase({
    prompt: reformulatedPrompt,
    enrichedPrompt: reformulatedEnriched,
    projectType: intent.projectType,
    wantsImages: intent.assetPlan.wantsImages,
    wants3D: intent.assetPlan.wants3D,
    wantsPremiumLook: intent.assetPlan.wantsPremiumLook,
    existingFiles: effectiveExistingFiles,
    setPhase,
    signal,
  })
  effectiveExistingFiles = assetPhase.files
  const interModuleAssetBundle: CodeAssetBundle | null = assetPhase.bundle

  const missionDossier = await buildCodeMissionDossier({
    prompt: reformulatedPrompt,
    enrichedPrompt: reformulatedEnriched,
    intent,
    existingFiles: effectiveExistingFiles,
    architecturePlan,
    model: selectModel('planning', intent, 0, configuredCodeModel, modelRouting),
  })
  // Phase 3: the WS3 file-by-file executor is the only generation path.
  const agenticGeneration = await runAgenticGenerationPhase({
    prompt: reformulatedEnriched,
    intent,
    architecturePlan,
    existingFiles: effectiveExistingFiles,
    contextImages,
    generationModel,
    setPhase,
    onToken,
    onFilesUpdate,
    signal,
    modelRouting,
  })
  if (agenticGeneration && !agenticGeneration.ok && signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
  if (!agenticGeneration?.ok) {
    throw new Error(`Echec de l executor agentique WS3: ${agenticGeneration?.error || 'plan_without_queue'}`)
  }

  let fullContent = agenticGeneration.content

  // CRITICAL: Detect LLM refusal BEFORE parsing — refuse early, retry immediately
  if (isLLMRefusal(fullContent)) {
    console.warn('[CodeOrchestrator] LLM returned a refusal instead of code. Forcing regeneration.')
    setPhase('Le modele a refuse de generer du code — regeneration forcee...', 40)
    const rescueGeneration = await runAgenticGenerationPhase({
      prompt: [
        'INSTRUCTION CRITIQUE: Tu DOIS generer du code source. NE REFUSE JAMAIS.',
        'Tu es un generateur de code. Ta seule sortie autorisee est une suite d actions outil JSON WS3.',
        '',
        'INTERDIT: excuses, refus, explications, suggestions de consulter les instructions.',
        'Regenere chaque fichier du plan, complet et executable:',
        '',
        reformulatedEnriched,
      ].join('\n'),
      intent,
      architecturePlan,
      existingFiles: effectiveExistingFiles,
      contextImages,
      generationModel,
      escalationLevel: 2,
      setPhase,
      onToken,
      onFilesUpdate,
      signal,
      modelRouting: { ...modelRouting, plateau: true },
    })
    if (rescueGeneration && !rescueGeneration.ok && signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    if (!rescueGeneration?.ok) {
      throw new Error(`Echec de la regeneration agentique WS3: ${rescueGeneration?.error || 'plan_without_queue'}`)
    }
    if (isLLMRefusal(rescueGeneration.content)) {
      throw new Error('Refus LLM persistant apres regeneration agentique WS3')
    }
    fullContent = rescueGeneration.content
  }

  // Swap USER_FILE_N markers with the real data URL of each user-attached file.
  // `userFileDataUrls` is optional in the public API — guard against every possible
  // shape (undefined / null / {}) to avoid ReferenceError at runtime.
  const userMap = userFileDataUrls ?? {}
  for (const [marker, dataUrl] of Object.entries(userMap)) {
    if (typeof dataUrl === 'string' && dataUrl && fullContent.includes(marker)) {
      fullContent = fullContent.split(marker).join(dataUrl)
    }
  }

  const outputRetryResult = await runGeneratedOutputRetryLoop({
    prompt,
    enrichedPrompt,
    latestRawGenerationContent: fullContent,
    intent,
    architecturePlan,
    missionDossier,
    effectiveExistingFiles,
    contextImages,
    configuredCodeModel,
    generationModel,
    setPhase,
    onToken,
    signal,
    modelRouting,
  })
  let initialFiles = materializeInterModuleAssetReferences(
    outputRetryResult.files,
    interModuleAssetBundle,
  )
  let initialNotes = outputRetryResult.notes
  const latestRawGenerationContent = outputRetryResult.latestRawGenerationContent
  const outputRetry = outputRetryResult.outputRetry

  if (initialFiles.length === 0) {
    const diagnostic = buildEmptyGenerationDiagnostic(latestRawGenerationContent, intent, outputRetry)
    return {
      files: [],
      notes: diagnostic,
      sandboxResult: null,
      intent,
      preflightReport,
      correctionLog: [],
      phase: 'error',
      architecturePlan,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp,
    }
  }

  initialFiles = upsertAssetManifestFile(initialFiles, interModuleAssetBundle)
  initialFiles = upsertProjectSupportFiles(initialFiles, intent, reformulatedEnriched, architecturePlan)

  onFilesUpdate(initialFiles, initialNotes)

  // Phase 4+5: Validation + auto-correction loop
  const validationResult = await runValidationAndCorrectionLoop(
    prompt,
    initialFiles,
    intent,
    preflightReport,
    missionDossier,
    architecturePlan,
    configuredCodeModel,
    setPhase,
    onFilesUpdate,
    onValidationUpdate,
    onCorrectionLogUpdate,
    signal,
    modelRouting,
  )

  const delivery = finalizeCodePipelineDelivery({
    files: validationResult.files, notes: validationResult.notes, score: validationResult.finalScore,
    intent, enrichedPrompt: reformulatedEnriched, architecturePlan, assetBundle: interModuleAssetBundle,
  })

  return {
    files: delivery.files,
    notes: delivery.notes,
    sandboxResult: validationResult.sandboxResult,
    intent,
    preflightReport,
    correctionLog: validationResult.correctionLog,
    // Expert delivery contract: files are not enough. A project is done only
    // when the sandbox and deterministic quality gates agree it is runnable.
    phase: validationResult.sandboxResult?.ok ? 'done' : 'error',
    architecturePlan,
    totalAttempts: validationResult.totalAttempts,
    finalScore: delivery.score,
    recoveryEvents,
    followUp,
    designReport: delivery.designReport,
  }
}
