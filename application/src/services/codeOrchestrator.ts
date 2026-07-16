// Code orchestrator: public facade and multi-phase pipeline.

import type { OllamaMessage } from '../types/app'
import type { RecoveryEvent } from './ollamaResilience'
import { type CodeIntent, classifyCodeIntent } from './codeIntent'
import { buildAutonomousAssumptionNotes, buildCodeMissionDossier, type CodeMissionDossier } from './codeMissionControl'
import type { CorrectionPass } from './codeAutoCorrection'
import type { CodeSandboxResult } from './codeSandbox'
import type { CodePreflightReport } from './codePreflight'
import { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
import { buildEmptyGenerationDiagnostic } from './codeGenerationDiagnostics.ts'
import { runValidationAndCorrectionLoop } from './codeValidationCorrectionLoop.ts'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
export { upsertProjectSupportFilesForTest } from './codeProjectSupportFiles.ts'
import { selectModel, type CodeModelRoutingContext } from './codePipelineRuntime.ts'
import {
  isArchitecturePlanUsable,
  runIntentPhase,
  runPlanningPhase,
  runPreflightPhase,
} from './codePipelinePhases.ts'
import { prepareCodePlanningContext } from './codePipelinePreparation.ts'
import { runGeneratedOutputRetryLoop } from './codeGenerationOutputRetry.ts'
import { runInitialAgenticGeneration } from './codeInitialAgenticGeneration.ts'
import { prepareCodeFollowUpContext } from './codeFollowUpPreparation.ts'
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
import type {
  CodeFile,
  CodeOrchestrationResult,
  PhaseCallback,
} from './codeOrchestratorTypes.ts'
export type {
  CodeFile,
  CodeOrchestrationPhase,
  CodeOrchestrationResult,
  PhaseCallback,
} from './codeOrchestratorTypes.ts'

/**
 * Auto-generate a smart assumption instead of asking a vague question.
 * The code module should be autonomous and prefer assumptions over questions.
 */
export function buildAutonomousAssumption(prompt: string, intent: CodeIntent): string {
  return buildAutonomousAssumptionNotes(prompt, intent)
}

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
  const followUpContext = await prepareCodeFollowUpContext({
    prompt,
    enrichedPrompt,
    conversationHistory,
    existingFiles,
    configuredCodeModel,
    setPhase,
    onFollowUpAnalysis,
    signal,
  })
  const { followUp, reformulatedPrompt, reformulatedEnriched, intentContext } = followUpContext
  let { effectiveExistingFiles } = followUpContext
  const intent = await runIntentPhase(reformulatedEnriched, setPhase, intentContext, {
    configuredCodeModel,
    signal,
  })

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
  const fullContent = await runInitialAgenticGeneration({
    prompt: reformulatedEnriched,
    intent,
    architecturePlan,
    existingFiles: effectiveExistingFiles,
    contextImages,
    generationModel,
    userFileDataUrls,
    setPhase,
    onToken,
    onFilesUpdate,
    signal,
    modelRouting,
  })

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
