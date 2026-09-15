// Code orchestrator: public facade and multi-phase pipeline.

import type { OllamaMessage } from '../types/app.ts'
import type { RecoveryEvent } from './ollamaResilience.ts'
import { type CodeIntent, classifyCodeIntent } from './codeIntent.ts'
import { buildAutonomousAssumptionNotes, buildCodeMissionDossier, type CodeMissionDossier } from './codeMissionControl.ts'
import type { CorrectionPass } from './codeAutoCorrection.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export * from './codeOrchestratorReexports.ts'
import { buildEmptyGenerationDiagnostic } from './codeGenerationDiagnostics.ts'
import { runValidationAndCorrectionLoop } from './codeValidationCorrectionLoop.ts'
import { deliveryPhase } from './codeValidationScoring.ts'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
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
import {
  analyzeFollowUpIntent,
  type FollowUpAnalysis,
  type FollowUpKind,
} from './codeFollowUpAnalysis.ts'
import { invalidateModelResidencyCache } from './codeModelResidency.ts'
import { createFileStateCapture } from './codeFileStateCapture.ts'
import { buildInterruptedDelivery, buildInterruptedResult } from './codeInterruptedDelivery.ts'
import type {
  CodeFile,
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

export async function orchestrateCodeGeneration(
  options: import('./codeOrchestratorTypes.ts').OrchestrateCodeGenerationOptions,
): Promise<CodeOrchestrationResult> {
  const {
    prompt, enrichedPrompt, conversationHistory, existingFiles, contextImages,
    userFileDataUrls, configuredCodeModel, visionModel, setPhase, onToken,
    onFilesUpdate, onValidationUpdate, onCorrectionLogUpdate, onRecoveryEvent,
    onFollowUpAnalysis, signal, modelRouting,
  } = options
  const generationModel = contextImages.length > 0 ? visionModel : configuredCodeModel
  // Run 1041: 32 fichiers detruits par un `fetch failed`. On garde le dernier
  // etat connu pour pouvoir le livrer si le pipeline meurt en route.
  const fileState = createFileStateCapture(existingFiles, onFilesUpdate)
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
      onFilesUpdate: fileState.capture,
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

    // REGLE, symetrique de celle des portes de qualite: un juge qui ne peut pas
    // mesurer ne condamne pas — un generateur qui perd son modele ne detruit
    // pas ses fichiers. Une panne d infrastructure ne dit RIEN sur la valeur du
    // travail deja produit; le jeter est une erreur de categorie, et c est la
    // plus chere de toutes (run 1041: 32 fichiers perdus sur un `fetch failed`).
    const { files: lastKnownFiles, notes: lastKnownNotes } = fileState.snapshot()
    if (lastKnownFiles.length > 0) {
      const delivery = buildInterruptedDelivery(msg, lastKnownFiles, lastKnownNotes)
      console.warn(`[CodeOrchestrator] ${lastKnownFiles.length} fichier(s) preserves malgre la ${delivery.cause}.`)
      setPhase(delivery.phaseMessage, 0)
      return buildInterruptedResult(delivery, lastKnownFiles, classifyCodeIntent(enrichedPrompt), recoveryEvents)
    }

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
  // La phase d assets a pu charger le modele d un autre module.
  invalidateModelResidencyCache()
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

  setPhase('Finalisation du projet: fichiers support et manifest de conformite...', 92)
  const delivery = finalizeCodePipelineDelivery({
    files: validationResult.files, notes: validationResult.notes, score: validationResult.finalScore,
    intent, enrichedPrompt: reformulatedEnriched, architecturePlan, assetBundle: interModuleAssetBundle,
  })
  setPhase(`Projet ${intent.projectType} livre avec succes (score: ${delivery.score}/100).`, 100)

  return {
    files: delivery.files,
    notes: delivery.notes,
    sandboxResult: validationResult.sandboxResult,
    intent,
    preflightReport,
    correctionLog: validationResult.correctionLog,
    // Contrat de livraison: un projet n est `done` que si le sandbox et les
    // portes deterministes le disent EXECUTABLE. Les portes de STYLE pesent sur
    // le score, jamais sur ce verdict (cf. isDeliveryRunnable).
    // Validation EMPECHEE = pas un verdict de qualite (run 1151, cf.
    // codeInfrastructureFailure). Travail existant, non valide: `interrupted`.
    phase: deliveryPhase(validationResult),
    architecturePlan,
    totalAttempts: validationResult.totalAttempts,
    finalScore: delivery.score,
    recoveryEvents,
    followUp,
    designReport: delivery.designReport,
    visualFidelity: delivery.visualFidelity,
  }
}
