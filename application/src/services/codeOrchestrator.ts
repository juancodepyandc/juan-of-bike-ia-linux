// ---------------------------------------------------------------------------
// Code Orchestrator — Multi-phase pipeline with model routing
// Equivalent of conversationOrchestrator.ts but specialized for code generation
// ---------------------------------------------------------------------------

import type { OllamaMessage } from '../types/app'
import {
  resilientOllamaChat,
  resilientOllamaGenerate,
  type RecoveryEvent,
} from './ollamaResilience'
import {
  type CodeIntent,
  type CodeIntentContext,
  classifyCodeIntent,
} from './codeIntent'
import {
  buildAutonomousAssumptionNotes,
  buildCodeMissionDossier,
  buildDraftRegenerationPrompt,
  buildRescueRegenerationPrompt,
  reviewGeneratedCodeDraft,
  serializeCodeMissionDossier,
  type CodeMissionDossier,
} from './codeMissionControl'
import {
  type CorrectionPass,
  buildCorrectionStrategy,
  shouldContinueLoop,
  classifyErrors,
} from './codeAutoCorrection'
import { searchForSolution, researchBestPractices } from './codeResearch'
import { runCodeSandboxValidation, type CodeSandboxResult, type CodeSandboxStepResult } from './codeSandbox'
import { analyzeStuckCorrection, buildReasoningInstructions } from './codeReasoningEngine'
import {
  serializeCodePreflightReport,
  type CodePreflightReport,
} from './codePreflight'
import { withTimeout } from './llmTimebox'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { parseCodeFiles, serializeCodeFiles, extractNotes, detectNonCodePlanningNarrative } from './codeGeneratedFileParser.ts'
export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
import {
  buildEmptyGenerationDiagnostic,
  detectEnvironmentBlocker,
} from './codeGenerationDiagnostics.ts'
import { buildCorrectionMessages } from './codeCorrectionMessages.ts'
import {
  applySubjectImagePlaceholder,
  fetchBrandProfileFromBridge,
  fetchSubjectImages,
  mergeExistingWithUpdates,
} from './codeSubjectAssets.ts'
import { evaluateBrandFidelity, type BrandFidelityReport } from './codeFidelityGate'
import { compositeStaticCritic } from './codeStaticCritics'
import type { CritiqueReport } from './codeMultiPassCritique'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
export { upsertProjectSupportFilesForTest } from './codeProjectSupportFiles.ts'
import {
  attemptLocalFileRepair,
  validateOutputMatchesIntent,
} from './codeProjectValidation.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CORRECTION_FIRST_BYTE_TIMEOUT_MS,
  CORRECTION_TIMEOUT_MS,
  DOCUMENTATION_EXTENSIONS_EARLY,
  INTERACTIVE_3D_FIDELITY_MAX_PASSES,
  RESEARCH_PHASE_TIMEOUT_MS,
  clipText,
  getModelShortName,
  selectModel,
} from './codePipelineRuntime.ts'
import {
  runGenerationPhase,
  runIntentPhase,
  runPlanningPhase,
  runPreflightPhase,
  type GenerationPivotContext,
} from './codePipelinePhases.ts'
import {
  buildDesignRetryHint,
  checkGamePlayability,
  checkInteractive3DFidelity,
  checkWebPageIntegrity,
  computeContentQualityScore,
  computeDesignPolishReport,
  computeDesignPolishReportPublic,
  isVisualProjectType,
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

/** Calculate a granular score from sandbox results AND content quality */
function computeSandboxScore(sandboxResult: CodeSandboxResult, files: CodeFile[], intent: CodeIntent): number {
  // Content quality gate — if the content itself is garbage, sandbox pass is irrelevant
  const contentScore = computeContentQualityScore(files, intent)
  if (contentScore === 0) return 0   // Refusal or empty → 0% no matter what
  if (contentScore <= 10) return contentScore // Generic/docs-only → cap at 10%

  if (sandboxResult.ok) {
    // Sandbox passed, but cap by content quality
    return Math.min(100, contentScore)
  }

  const totalSteps = sandboxResult.steps.length
  if (totalSteps === 0) return Math.min(contentScore, 50)
  const passingSteps = sandboxResult.steps.filter((s) => s.ok).length
  // Base score from passing ratio (0-80 range)
  const passRatio = passingSteps / totalSteps
  const baseScore = Math.round(passRatio * 80)
  // Bonus points for partial success indicators in failing steps
  const failingOutputs = sandboxResult.steps.filter((s) => !s.ok).map((s) => s.output).join('\n')
  let bonus = 0
  if (/warning/i.test(failingOutputs) && !/error/i.test(failingOutputs)) bonus += 10
  if (/compiled/i.test(failingOutputs) || /built/i.test(failingOutputs)) bonus += 5
  return Math.min(99, baseScore + bonus)
}

function isStaticCritiqueBlocking(report: CritiqueReport): boolean {
  if (report.hasBlocker) return true
  if (report.issues.some((issue) => issue.severity === 'error')) return true
  if (report.scores.compile < 1) return true
  if (report.scores.security < 0.85) return true
  if (report.scores.lint < 0.65) return true
  return false
}

function formatStaticCritiqueReport(report: CritiqueReport): string {
  const scoreLine = [
    `overall=${Math.round(report.overallScore * 100)}%`,
    `compile=${Math.round(report.scores.compile * 100)}%`,
    `lint=${Math.round(report.scores.lint * 100)}%`,
    `security=${Math.round(report.scores.security * 100)}%`,
    `accessibility=${Math.round(report.scores.accessibility * 100)}%`,
  ].join(' | ')

  const issues = report.issues.slice(0, 20).map((issue) => {
    const where = issue.location
      ? `${issue.location.file}${issue.location.line ? `:${issue.location.line}` : ''}`
      : 'projet'
    const suggestion = issue.suggestion ? ` Suggestion: ${issue.suggestion}` : ''
    return `[${issue.severity}] ${where} - ${issue.message}.${suggestion}`
  })

  return [
    scoreLine,
    report.hasBlocker ? 'blocker=true' : 'blocker=false',
    issues.length > 0 ? issues.join('\n') : 'Aucun probleme statique bloquant detecte.',
  ].join('\n')
}

function withStaticCritiqueStep(
  sandboxResult: CodeSandboxResult,
  report: CritiqueReport,
): CodeSandboxResult {
  const blocking = isStaticCritiqueBlocking(report)
  const output = formatStaticCritiqueReport(report)
  const staticStep: CodeSandboxStepResult = {
    label: 'Critique statique Aurora',
    command: 'internal:static-critique',
    ok: !blocking,
    output,
  }

  if (!blocking) {
    return {
      ...sandboxResult,
      steps: [...sandboxResult.steps, staticStep],
    }
  }

  const staticSummary = 'La critique statique a detecte des erreurs de syntaxe, structure, securite ou complexite.'
  return {
    ...sandboxResult,
    ok: false,
    summary: sandboxResult.ok
      ? staticSummary
      : `${sandboxResult.summary}\n${staticSummary}`,
    steps: [...sandboxResult.steps, staticStep],
  }
}

/** Phase 4 + 5: Validation + Auto-correction loop */
async function runValidationAndCorrectionLoop(
  prompt: string,
  initialFiles: CodeFile[],
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  missionDossier: CodeMissionDossier,
  architecturePlan: string | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onFilesUpdate: (files: CodeFile[], notes: string) => void,
  onValidationUpdate: (result: CodeSandboxResult) => void,
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void,
  signal?: AbortSignal,
): Promise<{
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  totalAttempts: number
  finalScore: number
}> {
  let currentFiles = initialFiles
  let currentNotes = ''
  let sandboxResult: CodeSandboxResult | null = null
  const correctionLog: CorrectionPass[] = []
  let attempt = 0
  let lastScore = 0
  let rescueRegenerationUsed = false

  while (true) {
    attempt += 1

    // Check abort
    if (signal?.aborted) break

    // Validate in sandbox
    setPhase(`Sandbox passe ${attempt} — validation en cours...`, Math.min(85, 60 + attempt * 4))
    sandboxResult = await runCodeSandboxValidation({
      files: currentFiles,
      prompt,
      setPhase,
      setProgress: (detail) => setPhase(detail, Math.min(90, 65 + attempt * 4)),
    })

    if (sandboxResult.normalizedFiles && sandboxResult.normalizedFiles.length > 0) {
      const normalizedChanged = sandboxResult.normalizedFiles.length !== currentFiles.length
        || sandboxResult.normalizedFiles.some((file, index) =>
          file.name !== currentFiles[index]?.name || file.content !== currentFiles[index]?.content,
        )
      if (normalizedChanged) {
        currentFiles = sandboxResult.normalizedFiles
        onFilesUpdate(currentFiles, currentNotes)
      }
    }

    setPhase(`Sandbox passe ${attempt} - critique statique du code...`, Math.min(90, 66 + attempt * 4))
    const staticReport = await compositeStaticCritic({
      generationId: `validation-${attempt}`,
      files: currentFiles,
    }, intent)
    sandboxResult = withStaticCritiqueStep(sandboxResult, staticReport)

    const interactive3D = checkInteractive3DFidelity(currentFiles, prompt, intent)
    if (!interactive3D.ok && attempt <= INTERACTIVE_3D_FIDELITY_MAX_PASSES) {
      const fidelitySummary = 'La fidelite 3D interactive demandee est incomplete.'
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? fidelitySummary
          : `${sandboxResult.summary}\n${fidelitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Fidelite 3D interactive',
            command: 'interactive-3d-fidelity-gate',
            ok: false,
            output: interactive3D.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - fidelite 3D incomplete (${interactive3D.missing.join(', ')})...`,
        Math.min(90, 68 + attempt * 4),
      )
    }

    // Deterministic visual gates: a sandbox can say "ok" while a web page is a
    // non-functional shell or a game has no input/game loop. These gates must
    // run before score/strategy calculation so the correction pass can fix them.
    const gamePlay =
      intent.projectType === 'game_web'
        ? checkGamePlayability(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!gamePlay.ok) {
      const playabilitySummary = `Jeu incomplet: ${gamePlay.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? playabilitySummary
          : `${sandboxResult.summary}\n${playabilitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Jouabilité',
            command: 'playability-gate',
            ok: false,
            output: gamePlay.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - jeu incomplet (${gamePlay.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    const webIntegrity =
      intent.projectType === 'static_web'
        ? checkWebPageIntegrity(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!webIntegrity.ok) {
      const integritySummary = `Page non fonctionnelle: ${webIntegrity.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? integritySummary
          : `${sandboxResult.summary}\n${integritySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Intégrité page',
            command: 'web-integrity-gate',
            ok: false,
            output: webIntegrity.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - page non fonctionnelle (${webIntegrity.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    onValidationUpdate(sandboxResult)

    // Calculate score using granular formula + content quality gate
    const currentScore = computeSandboxScore(sandboxResult, currentFiles, intent)

    const errorCategories = sandboxResult.ok ? [] : classifyErrors(sandboxResult)
    const strategy = sandboxResult.ok
      ? null
      : buildCorrectionStrategy(errorCategories, attempt, correctionLog)

    // Trim agressif : on garde max 1.5KB par erreur pour la passe courante
    // (la passe courante est celle que le LLM va lire, donc on a besoin de
    // details). On tronque plus serre que 5KB pour proteger la RAM sur les
    // longues boucles.
    const truncatedErrors = sandboxResult.steps
      .filter((s) => !s.ok)
      .map((s) => s.output.length > 1500
        ? `${s.output.slice(0, 1000)}\n...[tronque: ${s.output.length} chars total]...\n${s.output.slice(-400)}`
        : s.output)

    const pass: CorrectionPass = {
      attempt,
      score: currentScore,
      errors: truncatedErrors,
      strategy: attempt === 1 ? 'initial' : (strategy?.level ?? 'initial'),
      modelUsed: configuredCodeModel,
      resolved: sandboxResult.ok,
    }
    correctionLog.push(pass)

    // Memory release : resume les passes > 4 en arriere en une ligne. Sans ca
    // un long run de 10 passes accumule 10 × 3-5KB d erreurs + retries +
    // metadata qui finit par saturer la RAM (cause #2 de crash PC).
    if (correctionLog.length > 4) {
      for (let i = 0; i < correctionLog.length - 4; i++) {
        const old = correctionLog[i]
        if (old.errors.length > 1 || (old.errors[0] && old.errors[0].length > 200)) {
          correctionLog[i] = {
            ...old,
            errors: [`[passe archivee: ${old.errors.length} erreurs, score ${old.score}%]`],
          }
        }
      }
    }

    // Push real-time update to UI
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    if (sandboxResult.ok) {
      lastScore = 100
      break
    }

    // Environment blocker detection: the sandbox reports that a runtime or
    // toolchain is missing. The user rule is "JAMAIS arreter tant qu il n
    // atteint pas son but" — so we DO NOT break here anymore. Instead we
    // surface the blocker as a warning note on the pass and keep iterating;
    // the Auditeur / web research can still rewrite the project to use a
    // different stack that does not require the missing tool.
    const environmentBlocker = detectEnvironmentBlocker(sandboxResult, errorCategories)
    if (environmentBlocker) {
      pass.errors = [
        `[Blocage environnement detecte - ${environmentBlocker}]`,
        ...pass.errors,
      ]
      setPhase(`Passe ${attempt} - ${environmentBlocker} (le module essaie une stack alternative)...`, Math.min(92, 70 + attempt * 3))
    }

    const localRepair = attemptLocalFileRepair(currentFiles, sandboxResult)
    if (localRepair) {
      currentFiles = localRepair.files
      currentNotes = `${currentNotes ? `${currentNotes}\n\n` : ''}Auto-reparation locale: ${localRepair.reason}`
      onFilesUpdate(currentFiles, currentNotes)
      setPhase(`Passe ${attempt} - auto-reparation locale appliquee.`, Math.min(93, 71 + attempt * 3))
      lastScore = currentScore
      continue
    }

    // Check if we should continue — only exits on score=100 or true infinite
    // loop (same exact error 8+ times). No "plateau" cutoff anymore.
    if (!shouldContinueLoop(correctionLog, attempt, errorCategories)) {
      lastScore = currentScore
      const reason = currentScore >= 100
        ? 'livraison validee a 100%'
        : `boucle infinie detectee sur la meme erreur apres ${attempt} passes`
      setPhase(`Arret de la boucle : ${reason}.`, 92)
      break
    }

    // Auto-correction attempt with clear status
    const correctionModel = selectModel('correction', intent, strategy!.escalation, configuredCodeModel)
    pass.modelUsed = correctionModel
    pass.strategy = strategy!.level
    // Update UI with mutated pass
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    const strategyLabel = strategy!.level.replace(/_/g, ' ')
    const modelShort = getModelShortName(correctionModel)
    setPhase(`Passe ${attempt} — ${strategyLabel} via ${modelShort}...`, Math.min(92, 70 + attempt * 3))

    // At high escalation, search the web for solutions
    let researchContext = ''
    if (strategy!.searchWeb) {
      setPhase(`Passe ${attempt} — recherche de solutions en ligne...`, Math.min(93, 72 + attempt * 3))
      const failingErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
        .join('\n')
      try {
        researchContext = await withTimeout(searchForSolution(failingErrors, intent, configuredCodeModel), {
          label: 'Code correction research',
          timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
        })
      } catch {
        researchContext = ''
      }
    }

    // Analyse de cause racine — activee DES la passe 2 pour comprendre
    // chaque erreur en profondeur, pas seulement quand on est bloque
    let reasoningContext = ''
    const recentScores = correctionLog.slice(-3).map((pass) => pass.score)
    const isFlatlining = recentScores.length >= 3 && Math.max(...recentScores) - Math.min(...recentScores) <= 4
    if (attempt >= 2 || isFlatlining) {
      setPhase(`Passe ${attempt} — analyse de la cause racine...`, Math.min(93, 73 + attempt * 3))
      const currentErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
      const reasoning = await analyzeStuckCorrection(
        prompt,
        correctionLog,
        intent,
        currentErrors,
        configuredCodeModel,
      )
      if (reasoning) {
        reasoningContext = buildReasoningInstructions(reasoning)
        setPhase(`Passe ${attempt} — cause identifiee: ${reasoning.rootCause.slice(0, 80)}...`, Math.min(93, 74 + attempt * 3))
      }
    }

    // Regeneration de secours: repart de zero quand strategy_change ou rewrite
    // Autorisee toutes les 4 passes pour ne pas boucler mais donner plusieurs chances
    const rescueEligible = (strategy!.level === 'rewrite' || strategy!.level === 'strategy_change')
      && (!rescueRegenerationUsed || attempt % 4 === 0)
    if (rescueEligible) {
      rescueRegenerationUsed = true
      const failingErrors = sandboxResult.steps
        .filter((step) => !step.ok)
        .map((step) => step.output)
      const rescuePrompt = buildRescueRegenerationPrompt({
        originalPrompt: prompt,
        missionDossier,
        architecturePlan,
        failingSummary: sandboxResult.summary,
        failingErrors,
        reasoningContext,
      })

      setPhase(`Passe ${attempt} â€” regeneration de secours complete...`, Math.min(94, 75 + attempt * 3))
      const rescueResponse = await resilientOllamaGenerate(correctionModel, rescuePrompt, {
        timeoutMs: CORRECTION_TIMEOUT_MS,
        firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
        signal,
        num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
        neverMemorySkip: true,
        onRecoveryAttempt: (ev) => {
          setPhase(`Passe ${attempt} â€” sauvetage Ollama: ${ev.action}...`, Math.min(94, 76 + attempt * 3))
        },
      })

      const rescueContent = rescueResponse?.response?.trim() || ''
      const rescueFiles = parseCodeFiles(rescueContent)
      if (rescueFiles.length > 0 && !validateOutputMatchesIntent(rescueFiles, intent)) {
        currentFiles = rescueFiles
        currentNotes = extractNotes(rescueContent)
        onFilesUpdate(currentFiles, currentNotes)
        lastScore = currentScore
        continue
      }
    }

    // Build correction messages
    const correctionMessages = buildCorrectionMessages({
      prompt,
      files: currentFiles,
      validationResult: sandboxResult,
      strategy: strategy!,
      researchContext,
      reasoningContext,
      missionDossierText: serializeCodeMissionDossier(missionDossier),
      architecturePlan,
      preflightReportText: preflightReport ? serializeCodePreflightReport(preflightReport) : null,
      intent,
    })

    setPhase(`Passe ${attempt} — ${modelShort} corrige le code...`, Math.min(94, 74 + attempt * 3))
    const repairResponse = await resilientOllamaChat(correctionModel, correctionMessages, 0.05, {
      timeoutMs: CORRECTION_TIMEOUT_MS,
      firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
      signal,
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      neverMemorySkip: true,
      onRecoveryAttempt: (ev) => {
        setPhase(`Passe ${attempt} — auto-reparation Ollama: ${ev.action}...`, Math.min(94, 75 + attempt * 3))
      },
    })
    const repairedContent = repairResponse?.message?.content?.trim() || ''
    const repairedFiles = parseCodeFiles(repairedContent)

    if (repairedFiles.length === 0) {
      // Correction produced nothing usable — continue to next strategy
      setPhase(`Passe ${attempt} — correction vide, tentative suivante...`, Math.min(94, 75 + attempt * 3))
      continue
    }

    // Validate the MERGED result, not the correction payload alone. v89b: a
    // legitimate single-file fix (e.g. the model returns only the repaired
    // script.js) used to be rejected here for "index.html absent" — index.html
    // already exists in currentFiles and is preserved by the merge, so the fix
    // was thrown away and the broken/truncated file kept. Validate what we'd
    // actually ship.
    const mergedCandidate = mergeExistingWithUpdates(currentFiles, repairedFiles)
    const correctionIssue = validateOutputMatchesIntent(mergedCandidate, intent)
    if (correctionIssue) {
      setPhase(`Passe ${attempt} — correction invalide (${correctionIssue.slice(0, 50)}...), on garde les fichiers actuels...`, Math.min(94, 76 + attempt * 3))
      continue
    }

    currentFiles = mergedCandidate
    currentNotes = extractNotes(repairedContent)
    onFilesUpdate(currentFiles, currentNotes)
    lastScore = currentScore
  }

  return {
    files: currentFiles,
    notes: currentNotes,
    sandboxResult,
    correctionLog,
    totalAttempts: attempt,
    finalScore: lastScore,
  }
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
  const effectiveExistingFiles = followUp?.shouldResetFiles ? [] : existingFiles

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
  )

  // Phase 1.75: Research best practices (non-blocking, enriches planning context)
  // Label is contextualized by the asset plan so the user understands WHY it takes time
  // ("recherche de references premium" >> "recherche generique").
  const ap = intent.assetPlan
  const researchPhaseLabel = ap?.researchQueries.length
    ? `Recherche de references visuelles en ligne (${ap.researchQueries.slice(0, 2).join(' | ')})... cela peut prendre jusqu a 30s`
    : ap?.wantsPremiumLook
      ? 'Recherche de tendances de design premium... cela peut prendre jusqu a 30s'
      : 'Recherche des meilleures pratiques pour ce type de projet...'
  setPhase(researchPhaseLabel, 14)
  let bestPracticesContext = ''
  try {
    bestPracticesContext = await withTimeout(researchBestPractices(prompt, intent, configuredCodeModel), {
      label: 'Code research best practices',
      timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
    })
    if (bestPracticesContext) {
      setPhase('Meilleures pratiques trouvees — integration dans la planification...', 16)
    }
  } catch {
    // Research is non-blocking — continue without it
  }

  // v77 — DYNAMIC BRAND ENRICHMENT. When the user prompt mentions a brand we
  // don't have in the in-memory dictionary (Lipton, Heineken, Audi, ...),
  // the codeIntent classifier marks the subject as `inferred_brand` with no
  // profile. We call the bridge `/api/brand/enrich` here to fetch a real
  // BrandProfile from Wikipedia + Ollama before the planning phase, so the
  // rest of the pipeline (image queries, productShape recipe, palette lock)
  // works the same way for ANY brand, not just our 47 cached ones.
  //
  // v84r FIX : on SKIP cette phase pour les prompts qui ressemblent à un brief
  // technique simple (mots "simple", "minimal", "page HTML", "bouton",
  // "fonction", "calcul" etc.) — un titre "Bonjour Aurora" ne devrait pas
  // déclencher 60s de Wikipedia + Ollama. Le brand enrich reste actif pour
  // les vrais briefs "fais-moi le site de Coca-Cola" etc.
  const promptLower = prompt.toLowerCase()
  const looksLikeSimpleTechBrief = (
    prompt.length < 300 &&
    /\b(simple|minimal|basique|petit|petite|un\s+bouton|une\s+page|index\.html|une\s+fonction|calcul|console|cli|script)\b/i.test(promptLower) &&
    !/\b(comme|pour|de la marque|site de|brand|logo de)\b/i.test(promptLower)
  )
  if (ap?.subject?.source === 'inferred_brand' && !ap.subject.brandProfile && ap.subject.canonical && !looksLikeSimpleTechBrief) {
    setPhase(`Enrichissement dynamique du profil de marque "${ap.subject.canonical}" (Wikipedia + Ollama)...`, 13)
    try {
      const enriched = await withTimeout(
        fetchBrandProfileFromBridge(ap.subject.canonical),
        // v84r : 55s → 20s. Si Wikipedia tarde, on n'a pas le luxe d'attendre.
        // Le code peut commencer à streamer avec la palette générique.
        { label: 'Brand enrich (bridge)', timeoutMs: 20_000 },
      )
      if (enriched) {
        // Mutate the subject in place — the rest of the pipeline now sees a
        // full BrandProfile and treats the page as a brand page.
        ap.subject.brandProfile = enriched
        ;(ap.subject as { source: string }).source = 'brand'
        // Also re-run the brand-aware research query injection that
        // classifyCodeAssetPlan does for cached brands, so the bridge
        // image fetch picks up the right queries from the new profile.
        if (enriched.imageQueries?.length && ap.researchQueries) {
          for (const q of enriched.imageQueries.slice(0, 3).reverse()) {
            ap.researchQueries.unshift(q)
          }
        }
        setPhase(`Profil "${ap.subject.canonical}" enrichi (palette ${enriched.primaryColor}, produit ${enriched.productShape ?? 'logo'}).`, 14)
      } else {
        setPhase(`Pas de profil enrichi trouve pour "${ap.subject.canonical}" — generic fallback.`, 14)
      }
    } catch (err) {
      console.warn('[CodeOrchestrator] brand enrich failed:', err)
    }
  }

  // Phase 1.8: Real image fetch for the detected subject — data URLs are inlined
  // in the prompt so the LLM reuses them as <img src="..."> directly.
  // This is how "il doit vraiment telecharger une image" happens, and it survives
  // the user saving the project anywhere since it is a data URL, not a remote link.
  // v71: multi-image — brand pages need 3-4 distinct shots (logo, product,
  // lifestyle, detail), not a single hero photo. The orchestrator queries the
  // Aurora-Connect extension first (real browser tab), then the Python bridge,
  // then a deterministic local SVG fallback.
  let subjectImageBlock = ''
  // v84r : skip pour les briefs simples — pas besoin d'aller chercher 4 images
  // si le user demande juste "page HTML avec un bouton qui calcule X".
  const wantsRealImage = ap && (ap.wantsImages || ap.subject?.source === 'brand' || (ap.objectMentions?.length ?? 0) > 0)
  if (wantsRealImage && !looksLikeSimpleTechBrief) {
    const isBrand = ap.subject?.source === 'brand'
    setPhase(
      isBrand
        ? 'Recuperation des images officielles de la marque (logo + produit + lifestyle)...'
        : 'Telechargement d images reelles du sujet (peut prendre 10-30s)...',
      17,
    )
    try {
      const images = await withTimeout(
        fetchSubjectImages(intent),
        { label: 'Subject images fetch (multi)', timeoutMs: 45_000 },
      )
      // Cap each data URL at ~280KB so we don't blow up the prompt — the Codeur
      // only needs the image to load at runtime, not to read its bytes during
      // planning. Anything longer is dropped silently.
      const acceptable = images.filter((img) => img.dataUrl.length <= 350_000)
      if (acceptable.length > 0) {
        const dataUrls = acceptable.map((img) => img.dataUrl)
        ;(intent as any).__subjectImageDataUrls = dataUrls
        // Keep the legacy single-marker field for any older prompt path.
        ;(intent as any).__subjectImageDataUrl = dataUrls[0]

        const sourcesLine = acceptable
          .map((img, idx) => `  ${idx + 1}. ${img.query || 'subject'} -> ${img.source || 'unknown'}`)
          .join('\n')
        subjectImageBlock = [
          `## IMAGES REELLES DU SUJET (telechargees pour toi en amont — ${acceptable.length})`,
          `- ${acceptable.length} photo(s) / illustration(s) du sujet ont ete trouvees et converties en data URLs.`,
          '- Tu DOIS les utiliser DIRECTEMENT dans la page avec ces markers literaux:',
          '  - `PLACEHOLDER_SUBJECT_IMG`     -> image principale (hero / produit central).',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_1`   -> image principale (alias du marker non numerote).' : '',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_2`   -> image secondaire (lifestyle / contexte).' : '',
          acceptable.length >= 3 ? '  - `PLACEHOLDER_SUBJECT_IMG_3`   -> image tertiaire (detail / texture / variante).' : '',
          acceptable.length >= 4 ? '  - `PLACEHOLDER_SUBJECT_IMG_4`   -> image complementaire (gallery).' : '',
          '- Au build final, chaque marker sera remplace par la data URL correspondante.',
          '- Tu peux reutiliser le meme marker plusieurs fois (hero + showcase + footer). Tout marker sans image associee sera neutralise.',
          '- Sources originales:',
          sourcesLine,
        ].filter(Boolean).join('\n')
        setPhase(
          isBrand
            ? `${acceptable.length} image(s) de la marque telechargees — injection dans le prompt...`
            : `${acceptable.length} image(s) du sujet telechargees — injection dans le prompt...`,
          19,
        )
      } else if (images.length > 0) {
        console.warn('[CodeOrchestrator] All fetched subject images exceed the 350KB inline budget — skipping.')
      }
    } catch (err) {
      // Non-blocking: we continue without a real image. The Codeur falls back to
      // its usual SVG-inline strategy thanks to the "PAS D IMAGES CASSEES" rules.
      console.warn('[CodeOrchestrator] Subject image fetch failed:', err)
    }
  }

  // Inject brand profile into planning context: colors, keywords, design vibe.
  let brandProfileBlock = ''
  const brandSubject = ap?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const profile = brandSubject.brandProfile
    const palette: string[] = []
    if (profile.primaryColor) palette.push(`primaire ${profile.primaryColor}`)
    if (profile.secondaryColor) palette.push(`secondaire ${profile.secondaryColor}`)
    if (profile.tertiaryColor) palette.push(`tertiaire ${profile.tertiaryColor}`)
    brandProfileBlock = [
      `## PROFIL DE MARQUE — ${brandSubject.canonical}`,
      `- Domaine: ${brandSubject.domain ?? 'inconnu'}.`,
      palette.length ? `- Palette canonique: ${palette.join(', ')}.` : '',
      profile.productKeywords.length ? `- Produits / mots-cles: ${profile.productKeywords.join(', ')}.` : '',
      profile.designVibe ? `- Vibe visuel: ${profile.designVibe}.` : '',
      profile.typoVibe ? `- Typo: ${profile.typoVibe}.` : '',
      `- Le plan d architecture et le code DOIVENT respecter cette identite. Les couleurs du starter generique ne s appliquent pas.`,
    ].filter(Boolean).join('\n')
  }

  // Phase 2: Deep reasoning + architecture planning via llama4.
  const planningExtras: string[] = []
  if (bestPracticesContext) planningExtras.push(`## MEILLEURES PRATIQUES TROUVEES (a integrer dans le plan):\n${bestPracticesContext}`)
  // Brand profile injected before image block so architect plan uses colors/keywords.
  if (brandProfileBlock) planningExtras.push(brandProfileBlock)
  if (subjectImageBlock) planningExtras.push(subjectImageBlock)
  if (followUp?.migrationSummary && followUp.kind === 'pivot_platform') {
    planningExtras.push(`## MIGRATION DE PROJET (conserve le concept, change la stack)\n${followUp.migrationSummary}`)
  }
  const planningPrompt = planningExtras.length
    ? `${reformulatedEnriched}\n\n${planningExtras.join('\n\n')}`
    : reformulatedEnriched
  // Skip planning only for genuinely small visual one-offs. Complex visual work
  // (multi-page, 3D, simulator, whole-product briefs) needs the architect pass:
  // the user's target is a real engineered project, not a pretty single screen.
  const skipPlanningForVisual =
    (intent.projectType === 'static_web' || intent.projectType === 'game_web') &&
    !intent.needsArchitecturePlanning
  const architecturePlan = skipPlanningForVisual
    ? null
    : await runPlanningPhase(
        planningPrompt,
        intent,
        preflightReport,
        configuredCodeModel,
        setPhase,
        trackRecovery,
      )
  if (skipPlanningForVisual) setPhase('Projet web direct — generation sans plan lourd...', 28)
  const missionDossier = await buildCodeMissionDossier({
    prompt: reformulatedPrompt,
    enrichedPrompt: reformulatedEnriched,
    intent,
    existingFiles: effectiveExistingFiles,
    architecturePlan,
    model: selectModel('planning', intent, 0, configuredCodeModel),
  })

  // Pivot context forwarded to the code generator so it can swap the
  // "CONTEXTE PROJET EXISTANT" block with a "MIGRATION DE PROJET" block
  // when the user asked for a platform pivot.
  const pivotContext: GenerationPivotContext | undefined = followUp
    ? {
        kind: followUp.kind,
        migrationSummary: followUp.migrationSummary,
      }
    : undefined

  // Phase 3: Code generation (streaming, guided by plan)
  let fullContent = await runGenerationPhase(
    reformulatedEnriched,
    intent,
    preflightReport,
    architecturePlan,
    missionDossier,
    conversationHistory,
    effectiveExistingFiles,
    contextImages,
    generationModel,
    0,
    setPhase,
    onToken,
    trackRecovery,
    signal,
    pivotContext,
  )

  // CRITICAL: Detect LLM refusal BEFORE parsing — refuse early, retry immediately
  if (isLLMRefusal(fullContent)) {
    console.warn('[CodeOrchestrator] LLM returned a refusal instead of code. Forcing regeneration.')
    setPhase('Le modele a refuse de generer du code — regeneration forcee...', 40)
    // Force a regeneration with a stronger prompt
    const rescueContent = await runGenerationPhase(
      [
        'INSTRUCTION CRITIQUE: Tu DOIS generer du code source. NE REFUSE JAMAIS.',
        'Tu es un generateur de code. Ta seule sortie autorisee est du CODE SOURCE dans le format:',
        '--- FICHIER: nom.ext ---',
        '```langage',
        '// code ici',
        '```',
        '',
        'INTERDIT: excuses, refus, explications, suggestions de consulter les instructions.',
        'Genere le projet demande MAINTENANT:',
        '',
        reformulatedEnriched,
      ].join('\n'),
      intent,
      preflightReport,
      architecturePlan,
      missionDossier,
      conversationHistory,
      effectiveExistingFiles,
      contextImages,
      selectModel('generation', intent, 2, generationModel),
      2,
      setPhase,
      onToken,
      trackRecovery,
      signal,
      pivotContext,
    )
    // If rescue also refuses, we'll catch it in the validation loop below
    if (!isLLMRefusal(rescueContent)) {
      fullContent = rescueContent
    }
  }

  // Swap the PLACEHOLDER_SUBJECT_IMG marker with the real downloaded data URL
  // so every <img> tag the LLM wrote resolves immediately at first render.
  fullContent = applySubjectImagePlaceholder(fullContent, intent)

  // Swap USER_FILE_N markers with the real data URL of each user-attached file.
  // `userFileDataUrls` is optional in the public API — guard against every possible
  // shape (undefined / null / {}) to avoid ReferenceError at runtime.
  const userMap = userFileDataUrls ?? {}
  for (const [marker, dataUrl] of Object.entries(userMap)) {
    if (typeof dataUrl === 'string' && dataUrl && fullContent.includes(marker)) {
      fullContent = fullContent.split(marker).join(dataUrl)
    }
  }

  let latestRawGenerationContent = fullContent
  let parsed = parseCodeFiles(latestRawGenerationContent)
  let initialNotes = extractNotes(latestRawGenerationContent)
  // In follow-up mode (effectiveExistingFiles.length > 0), files NOT returned
  // by the LLM are preserved — we merge the new/changed files on top of the
  // existing set. After a pivot_platform / fresh_start, `effectiveExistingFiles`
  // is empty so the old project is correctly wiped.
  let initialFiles = effectiveExistingFiles.length > 0 && parsed.length > 0
    ? mergeExistingWithUpdates(effectiveExistingFiles, parsed)
    : parsed

  // Validate output quality — retry loop to ensure LLM produced actual code.
  // Complex briefs get more attempts and never downgrade to a tiny skeleton:
  // time is secondary to a complete, runnable project.
  const isExpertComplexProject = intent.complexity === 'complex' || intent.complexity === 'enterprise'
  const MAX_OUTPUT_RETRIES = isExpertComplexProject ? 6 : 3
  const MAX_NETWORK_ERRORS = isExpertComplexProject ? 4 : 2
  let outputRetry = 0
  let networkErrors = 0
  // v71 — track the latest brand fidelity report so we can apply the score
  // penalty/cap at the end of the orchestration.
  let latestBrandFidelity: BrandFidelityReport | null = null
  // v85c : remember the best non-empty attempt across the retry loop so the
  // pipeline NEVER returns 0 files when the model actually produced usable
  // code that a quality gate merely flagged. "Imparfait mais livré" > "rien".
  let bestAttempt: { files: CodeFile[]; notes: string; score: number } | null = null

  while (outputRetry < MAX_OUTPUT_RETRIES) {
    const draftReview = await reviewGeneratedCodeDraft({
      prompt,
      intent,
      files: initialFiles,
      architecturePlan,
      missionDossier,
      // v85c : CRITICAL — without this, the draft critique defaulted to
      // CODE_SINGLE_MODEL (qwen3-coder:30b, 20 GB) mid-pipeline, evicting the
      // routed generation model and forcing a CPU-spill +
      // reload thrash on every run. Pin it to the same model the rest of the
      // pipeline uses → true single-model coherence, no swap, far faster.
      model: configuredCodeModel,
    })
    // v71 — brand fidelity gate. Catches the "Coca-Cola → restaurant" drift
    // BEFORE the sandbox/correction loop wastes minutes on a wrong-subject
    // build. Only fires when the prompt has a brand subject; no-op otherwise.
    const brandSubject = intent.assetPlan?.subject
    const brandFidelity = evaluateBrandFidelity(intent, initialFiles)
    latestBrandFidelity = brandFidelity
    const brandIssueLine = brandFidelity.shouldRetry && brandFidelity.retryHint
      ? `Fidelite sujet (BRAND): ${brandFidelity.retryHint}`
      : null

    const issueNarrative = detectNonCodePlanningNarrative(latestRawGenerationContent)
    const issueIntent = validateOutputMatchesIntent(initialFiles, intent)
    const issueDraft = draftReview.verdict === 'regenerate'
      ? [
          draftReview.summary,
          ...draftReview.criticalIssues,
          ...draftReview.missingFiles,
        ].filter(Boolean).join(' | ')
      : null
    // v85d : the draft critique runs on the generation model,
    // which the audit found false-flags 'regenerate' on perfectly valid projects.
    // Trust the DETERMINISTIC gates (narrative / intent / brand) as primary;
    // let the LLM-judge force a retry ONLY when the output is also thin
    // (< 2 real code files) — otherwise it just burns retries on good output.
    const realCodeFileCount = initialFiles.filter((f) => {
      const e = f.name.split('.').pop()?.toLowerCase() || ''
      return !DOCUMENTATION_EXTENSIONS_EARLY.has(e)
    }).length
    const draftBlocks = issueDraft && realCodeFileCount < 2 ? issueDraft : null
    const outputIssue = issueNarrative || issueIntent || brandIssueLine || draftBlocks

    // v85c : track the best non-empty attempt (most files, then content score).
    if (initialFiles.length > 0) {
      const q = computeContentQualityScore(initialFiles, intent)
      if (!bestAttempt
        || initialFiles.length > bestAttempt.files.length
        || (initialFiles.length === bestAttempt.files.length && q > bestAttempt.score)) {
        bestAttempt = { files: initialFiles, notes: initialNotes, score: q }
      }
    }
    if (outputIssue) {
      console.warn(
        `[CodeOrchestrator] outputIssue @retry ${outputRetry} | files=${initialFiles.length} | `
        + `narrative=${!!issueNarrative} intentMismatch=${issueIntent ? JSON.stringify(issueIntent.slice(0, 80)) : false} `
        + `brand=${!!brandIssueLine} draftRegenerate=${!!issueDraft}`,
      )
    }
    if (!outputIssue) break // Output is valid code

    outputRetry++
    const escalation = outputRetry + 1
    const retryModel = selectModel('generation', intent, escalation, generationModel)
    const modelShort = retryModel.split(':')[0]

    setPhase(
      `Sortie incorrecte (tentative ${outputRetry}/${MAX_OUTPUT_RETRIES}) — regeneration via ${modelShort}...`,
      48 + outputRetry * 4,
    )

    // On brand drift: lock subject + palette + keywords in retry prompt.
    const brandRetryBlock = (brandFidelity.shouldRetry && brandSubject?.source === 'brand' && brandSubject.brandProfile)
      ? [
          '## VERROUILLAGE SUJET — REGLE INVIOLABLE',
          `Le sujet de cette page EST ${brandSubject.canonical}. Pas un sujet adjacent.`,
          '',
          'Violations detectees au tour precedent:',
          brandFidelity.retryHint || '(pas de detail)',
          '',
          'Pour ce nouveau tour, applique strictement:',
          `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, dans le <h1> du hero, et dans au moins 3 sections.`,
          brandSubject.brandProfile.primaryColor ? `- Couleur primaire OBLIGATOIRE: ${brandSubject.brandProfile.primaryColor}. Utilise-la pour le hero, les CTAs et les accents.` : '',
          brandSubject.brandProfile.secondaryColor ? `- Couleur secondaire: ${brandSubject.brandProfile.secondaryColor}.` : '',
          brandSubject.brandProfile.productKeywords.length ? `- Mots-cles produit: ${brandSubject.brandProfile.productKeywords.join(', ')}. Au moins 2 dans les titres de section.` : '',
          brandSubject.brandProfile.designVibe ? `- Vibe visuel cible: ${brandSubject.brandProfile.designVibe}.` : '',
          '- Markers d images REELLES deja telechargees: PLACEHOLDER_SUBJECT_IMG, PLACEHOLDER_SUBJECT_IMG_1..4. Place-en au moins 2 dans la page.',
          '- INTERDIT: restaurant, menu du jour, blog culinaire, SaaS abstrait. C est une marque/produit emblematique, traite-la comme telle.',
        ].filter(Boolean).join('\n')
      : ''

    const retryPrompt = [
      `ERREUR CRITIQUE (tentative ${outputRetry + 1}): La sortie precedente etait INCORRECTE.`,
      `Probleme: ${outputIssue}`,
      '',
      brandRetryBlock,
      '',
      `DOSSIER EXECUTIF:\n${serializeCodeMissionDossier(missionDossier)}`,
      '',
      'RAPPEL ABSOLU:',
      '- Tu es un DEVELOPPEUR. Tu produis du CODE SOURCE, JAMAIS de la documentation.',
      '- Chaque fichier DOIT etre un VRAI fichier de code (html, css, js, py, etc.)',
      '- INTERDIT: fichiers .md, .txt, texte descriptif, listes de fonctionnalites',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? '- TA SORTIE PRECEDENTE ETAIT UN PLAN/PREFLIGHT. N envoie plus jamais de diagnostic: convertis directement la solution en fichiers.'
        : '',
      outputRetry >= 2 && !isExpertComplexProject
        ? '- SIMPLIFIE: produis le MINIMUM de fichiers necessaires pour que ca fonctionne'
        : '',
      outputRetry >= 2 && isExpertComplexProject
        ? '- NE SIMPLIFIE PAS LES FONCTIONNALITES: preserve le scope demande, corrige la structure et livre tous les fichiers necessaires.'
        : '',
      '',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? `SORTIE INTERDITE A NE PAS REPRODUIRE:\n${clipText(latestRawGenerationContent, 1400)}\n`
        : '',
      buildDraftRegenerationPrompt({
        originalPrompt: prompt,
        enrichedPrompt,
        missionDossier,
        draftReview,
        architecturePlan,
      }),
      '',
      architecturePlan ? `PLAN A SUIVRE:\n${architecturePlan.slice(0, 6000)}\n` : '',
      'Voici la demande originale. Genere les VRAIS FICHIERS DE CODE:',
      '',
      enrichedPrompt,
      '',
      'FORMAT OBLIGATOIRE (ne JAMAIS devier):',
      '--- FICHIER: nom_du_fichier.ext ---',
      '```langage',
      '// code source complet ici',
      '```',
      '',
      intent.projectType === 'static_web'
        ? 'Pour une page web, genere AU MINIMUM: index.html, style.css, et optionnellement script.js + README.md'
        : intent.projectType === 'desktop_tauri'
          ? 'Pour une application desktop Tauri, genere AU MINIMUM: package.json, src/*, src-tauri/Cargo.toml, src-tauri/tauri.conf.json, src-tauri/src/main.rs + README.md'
          : intent.projectType === 'desktop_electron'
            ? 'Pour une application desktop Electron, genere AU MINIMUM: package.json, main.ts|main.js, preload si utile, renderer src/* + README.md'
        : intent.projectType.startsWith('api_')
          ? 'Pour une API, genere les fichiers serveur: routes, models, config, entry point + README.md'
          : 'Genere tous les fichiers source necessaires au projet + README.md',
    ].filter(Boolean).join('\n')

    let retryContent = ''
    try {
      retryContent = await runGenerationPhase(
        retryPrompt,
        intent,
        preflightReport,
        architecturePlan,
        missionDossier,
        conversationHistory,
        effectiveExistingFiles,
        contextImages,
        retryModel,
        escalation,
        setPhase,
        onToken,
        trackRecovery,
        signal,
        pivotContext,
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (/failed to fetch|network|TypeError|524|connection closed/i.test(msg)) {
        networkErrors += 1
        setPhase(`Erreur reseau (${networkErrors}/${MAX_NETWORK_ERRORS}) pendant la regeneration — tentative ${outputRetry}...`, 50 + outputRetry * 4)
        if (networkErrors >= MAX_NETWORK_ERRORS) {
          setPhase('Trop d erreurs reseau consecutives — arret propre du pipeline.', 96)
          break
        }
        // Short pause then let the outer loop retry once more.
        await new Promise((r) => setTimeout(r, 2000))
        continue
      }
      throw err
    }

    latestRawGenerationContent = retryContent
    const retryFiles = parseCodeFiles(retryContent)
    initialFiles = effectiveExistingFiles.length > 0 && retryFiles.length > 0
      ? mergeExistingWithUpdates(effectiveExistingFiles, retryFiles)
      : retryFiles
    initialNotes = extractNotes(retryContent)
  }

  // v85c : if the retry loop exhausted while flagging issues but an earlier
  // attempt DID produce usable files, deliver the best one (with a quality
  // note) instead of returning nothing. The quality gates become advisory,
  // not fatal — the user always gets a project they can iterate on.
  if (initialFiles.length === 0 && bestAttempt && bestAttempt.files.length > 0) {
    console.warn(`[CodeOrchestrator] retry loop exhausted — delivering best attempt (${bestAttempt.files.length} fichiers) instead of 0.`)
    initialFiles = bestAttempt.files
    initialNotes = bestAttempt.notes
      ? `${bestAttempt.notes}\n\n[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.`
      : '[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.'
  }

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
  )

  const finalFiles = upsertProjectSupportFiles(validationResult.files, intent, reformulatedEnriched, architecturePlan)

  // v71 — re-evaluate the brand fidelity AFTER the validation loop has settled.
  // The auto-correction may have rewritten copy and undone an earlier brand
  // fix, so we score on the final files.
  const finalBrandFidelity = evaluateBrandFidelity(intent, finalFiles)
  let adjustedScore = validationResult.finalScore
  if (finalBrandFidelity.scoreCap !== null) {
    adjustedScore = Math.min(adjustedScore, finalBrandFidelity.scoreCap)
  }
  if (finalBrandFidelity.scorePenalty > 0) {
    adjustedScore = Math.max(0, adjustedScore - finalBrandFidelity.scorePenalty)
  }

  const augmentedNotes = finalBrandFidelity.retryHint
    ? `${validationResult.notes}\n\n## FIDELITE SUJET\n${finalBrandFidelity.retryHint}`
    : validationResult.notes

  // Suppress the latestBrandFidelity warning when no longer used after the
  // post-loop re-evaluation. (Keeps the linter quiet without losing state
  // we may want to surface in a future iteration.)
  void latestBrandFidelity

  // Compute design polish report for visual project types (badge for UI).
  const designReport = isVisualProjectType(intent.projectType)
    ? computeDesignPolishReport(finalFiles)
    : null

  return {
    files: finalFiles,
    notes: augmentedNotes,
    sandboxResult: validationResult.sandboxResult,
    intent,
    preflightReport,
    correctionLog: validationResult.correctionLog,
    // Expert delivery contract: files are not enough. A project is done only
    // when the sandbox and deterministic quality gates agree it is runnable.
    phase: validationResult.sandboxResult?.ok ? 'done' : 'error',
    architecturePlan,
    totalAttempts: validationResult.totalAttempts,
    finalScore: adjustedScore,
    recoveryEvents,
    followUp,
    designReport,
  }
}
