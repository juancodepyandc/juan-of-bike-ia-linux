import type { CodeIntent } from './codeIntent.ts'
import type { CodeMissionDossier } from './codeMissionControl.ts'
import {
  buildCorrectionStrategy,
  classifyErrors,
  shouldContinueLoop,
  type CorrectionPass,
} from './codeAutoCorrection.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import { withTimeout } from './llmTimebox.ts'
import { extractNotes, parseCodeFiles } from './codeGeneratedFileParser.ts'
import { detectEnvironmentBlocker } from './codeGenerationDiagnostics.ts'
import { buildCorrectionMessages } from './codeCorrectionMessages.ts'
import { mergeExistingWithUpdates } from './codeSubjectAssets.ts'
import {
  attemptLocalFileRepair,
  validateOutputMatchesIntent,
} from './codeProjectValidation.ts'
import {
  formatCodeRegressionGuardReport,
  inspectCodePatchRegression,
} from './codeRegressionGuard.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS,
  CORRECTION_FIRST_BYTE_TIMEOUT_MS,
  CORRECTION_TIMEOUT_MS,
  RESEARCH_PHASE_TIMEOUT_MS,
  getModelShortName,
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'
import { computeSandboxScore } from './codeValidationScoring.ts'
import { runCorrectionQualityGates } from './codeCorrectionQualityGates.ts'

type ValidationCorrectionLoopResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  totalAttempts: number
  finalScore: number
}

export function normalizedFilesChanged(currentFiles: CodeFile[], normalizedFiles?: CodeFile[]): boolean {
  if (!normalizedFiles || normalizedFiles.length === 0) return false
  return normalizedFiles.length !== currentFiles.length
    || normalizedFiles.some((file, index) =>
      file.name !== currentFiles[index]?.name || file.content !== currentFiles[index]?.content,
    )
}

export function collectFailingStepOutputs(sandboxResult: CodeSandboxResult): string[] {
  return sandboxResult.steps
    .filter((step) => !step.ok)
    .map((step) => step.output)
}

export function truncateCorrectionErrors(sandboxResult: CodeSandboxResult): string[] {
  return collectFailingStepOutputs(sandboxResult).map((output) => output.length > 1500
    ? `${output.slice(0, 1000)}\n...[tronque: ${output.length} chars total]...\n${output.slice(-400)}`
    : output)
}

export function compactCorrectionLog(correctionLog: CorrectionPass[]): void {
  if (correctionLog.length <= 4) return

  for (let index = 0; index < correctionLog.length - 4; index++) {
    const old = correctionLog[index]
    if (old.errors.length > 1 || (old.errors[0] && old.errors[0].length > 200)) {
      correctionLog[index] = {
        ...old,
        errors: [`[passe archivee: ${old.errors.length} erreurs, score ${old.score}%]`],
      }
    }
  }
}

export async function runValidationAndCorrectionLoop(
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
  modelRouting?: CodeModelRoutingContext,
): Promise<ValidationCorrectionLoopResult> {
  const { runCodeSandboxValidation } = await import('./codeSandbox.ts')
  let currentFiles = initialFiles
  let currentNotes = ''
  let sandboxResult: CodeSandboxResult | null = null
  const correctionLog: CorrectionPass[] = []
  let attempt = 0
  let lastScore = 0
  let functionalGreenPasses = 0
  let rescueRegenerationUsed = false
  let toolingEvaluationUsed = false

  while (true) {
    attempt += 1

    if (signal?.aborted) break

    setPhase(`Sandbox passe ${attempt} — validation en cours...`, Math.min(85, 60 + attempt * 4))
    sandboxResult = await runCodeSandboxValidation({
      files: currentFiles,
      prompt,
      setPhase,
      setProgress: (detail) => setPhase(detail, Math.min(90, 65 + attempt * 4)),
    })

    if (normalizedFilesChanged(currentFiles, sandboxResult.normalizedFiles)) {
      currentFiles = sandboxResult.normalizedFiles!
      onFilesUpdate(currentFiles, currentNotes)
    }

    // Fonctionnel-vert capture AVANT les gates (qui peuvent forcer ok=false):
    // budget design-spec relatif au fonctionnel, pas au numero absolu de passe.
    if (sandboxResult.ok) functionalGreenPasses += 1

    sandboxResult = await runCorrectionQualityGates({
      result: sandboxResult,
      files: currentFiles,
      prompt,
      intent,
      attempt,
      functionalGreenPasses,
      setPhase,
    })

    onValidationUpdate(sandboxResult)

    const currentScore = computeSandboxScore(sandboxResult, currentFiles, intent)
    const errorCategories = sandboxResult.ok ? [] : classifyErrors(sandboxResult)
    const strategy = sandboxResult.ok
      ? null
      : buildCorrectionStrategy(errorCategories, attempt, correctionLog)

    const pass: CorrectionPass = {
      attempt,
      score: currentScore,
      errors: truncateCorrectionErrors(sandboxResult),
      strategy: attempt === 1 ? 'initial' : (strategy?.level ?? 'initial'),
      modelUsed: configuredCodeModel,
      resolved: sandboxResult.ok,
    }
    correctionLog.push(pass)
    compactCorrectionLog(correctionLog)

    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    if (sandboxResult.ok) {
      // Le sandbox qui passe prouve seulement que le code TOURNE, pas qu il est
      // bon. Fixer 100 en dur masquait toute generation mediocre mais executable
      // (ex: une landing ratee "acceptee a 100%") -> c est le "ca accepte le 0%".
      // On conserve le VRAI score qualite (contenu + criteres d acceptation), pour
      // que le score affiche soit honnete et que les gates de fidelite/qualite en
      // aval puissent pousser une amelioration reelle au lieu de s arreter.
      lastScore = currentScore
      break
    }

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
      const regressionReport = inspectCodePatchRegression(currentFiles, localRepair.files)
      if (!regressionReport.ok) {
        const reportText = formatCodeRegressionGuardReport(regressionReport)
        pass.errors = [`[Auto-reparation locale refusee]\n${reportText}`, ...pass.errors]
        onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
        setPhase(`Passe ${attempt} - auto-reparation refusee par anti-regression.`, Math.min(93, 71 + attempt * 3))
        lastScore = currentScore
        continue
      }

      currentFiles = localRepair.files
      currentNotes = `${currentNotes ? `${currentNotes}\n\n` : ''}Auto-reparation locale: ${localRepair.reason}`
      onFilesUpdate(currentFiles, currentNotes)
      setPhase(`Passe ${attempt} - auto-reparation locale appliquee.`, Math.min(93, 71 + attempt * 3))
      lastScore = currentScore
      continue
    }

    if (!shouldContinueLoop(correctionLog, attempt, errorCategories)) {
      lastScore = currentScore
      const reason = currentScore >= 100
        ? 'livraison validee a 100%'
        : `boucle infinie detectee sur la meme erreur apres ${attempt} passes`
      setPhase(`Arret de la boucle : ${reason}.`, 92)
      break
    }

    const recentScores = correctionLog.slice(-3).map((passItem) => passItem.score)
    const isFlatlining = recentScores.length >= 3 && Math.max(...recentScores) - Math.min(...recentScores) <= 4
    const correctionRouting = isFlatlining ? { ...(modelRouting ?? {}), plateau: true } : modelRouting
    const correctionModel = selectModel('correction', intent, strategy!.escalation, configuredCodeModel, correctionRouting)
    pass.modelUsed = correctionModel
    pass.strategy = strategy!.level
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    const strategyLabel = strategy!.level.replace(/_/g, ' ')
    const modelShort = getModelShortName(correctionModel)
    setPhase(`Passe ${attempt} — ${strategyLabel} via ${modelShort}...`, Math.min(92, 70 + attempt * 3))

    let researchContext = ''
    if (strategy!.searchWeb) {
      setPhase(`Passe ${attempt} — recherche de solutions en ligne...`, Math.min(93, 72 + attempt * 3))
      const failingErrors = collectFailingStepOutputs(sandboxResult).join('\n')
      try {
        const { searchForSolution } = await import('./codeResearch.ts')
        researchContext = await withTimeout(searchForSolution(failingErrors, intent, configuredCodeModel), {
          label: 'Code correction research',
          timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
        })
      } catch {
        researchContext = ''
      }
    }

    let toolingContext = ''
    if (isFlatlining && !toolingEvaluationUsed) {
      toolingEvaluationUsed = true
      setPhase(`Passe ${attempt} — auto-outillage WS14 en venv isole...`, Math.min(93, 73 + attempt * 3))
      try {
        const {
          evaluateAutoToolingForCorrection,
          formatToolingReportForCorrection,
        } = await import('./codeToolingLoop.ts')
        const toolingReport = await evaluateAutoToolingForCorrection({
          correctionLog,
          errorCategories,
          failingOutputs: collectFailingStepOutputs(sandboxResult),
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
      const currentErrors = collectFailingStepOutputs(sandboxResult)
      const {
        analyzeStuckCorrection,
        buildReasoningInstructions,
      } = await import('./codeReasoningEngine.ts')
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
    if (toolingContext) {
      reasoningContext = [toolingContext, reasoningContext].filter(Boolean).join('\n\n')
    }

    const rescueEligible = (strategy!.level === 'rewrite' || strategy!.level === 'strategy_change')
      && (!rescueRegenerationUsed || attempt % 4 === 0)
    if (rescueEligible) {
      rescueRegenerationUsed = true
      const {
        buildRescueRegenerationPrompt,
      } = await import('./codeMissionControl.ts')
      const rescuePrompt = buildRescueRegenerationPrompt({
        originalPrompt: prompt,
        missionDossier,
        architecturePlan,
        failingSummary: sandboxResult.summary,
        failingErrors: collectFailingStepOutputs(sandboxResult),
        reasoningContext,
      })

      setPhase(`Passe ${attempt} â€” regeneration de secours complete...`, Math.min(94, 75 + attempt * 3))
      const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
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
        const regressionReport = inspectCodePatchRegression(currentFiles, rescueFiles)
        if (regressionReport.ok) {
          currentFiles = rescueFiles
          currentNotes = extractNotes(rescueContent)
          onFilesUpdate(currentFiles, currentNotes)
          lastScore = currentScore
          continue
        }

        const reportText = formatCodeRegressionGuardReport(regressionReport)
        pass.errors = [`[Regeneration de secours refusee]\n${reportText}`, ...pass.errors]
        onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
        setPhase(`Passe ${attempt} — regeneration refusee par anti-regression.`, Math.min(94, 76 + attempt * 3))
      }
    }

    const { serializeCodeMissionDossier } = await import('./codeMissionControl.ts')
    const { serializeCodePreflightReport } = await import('./codePreflight.ts')
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
    const { resilientOllamaChat } = await import('./ollamaResilience.ts')
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
      setPhase(`Passe ${attempt} — correction vide, tentative suivante...`, Math.min(94, 75 + attempt * 3))
      continue
    }

    const mergedCandidate = mergeExistingWithUpdates(currentFiles, repairedFiles)
    const correctionIssue = validateOutputMatchesIntent(mergedCandidate, intent)
    if (correctionIssue) {
      setPhase(`Passe ${attempt} — correction invalide (${correctionIssue.slice(0, 50)}...), on garde les fichiers actuels...`, Math.min(94, 76 + attempt * 3))
      continue
    }

    const regressionReport = inspectCodePatchRegression(currentFiles, mergedCandidate)
    if (!regressionReport.ok) {
      const reportText = formatCodeRegressionGuardReport(regressionReport)
      pass.errors = [`[Correction refusee]\n${reportText}`, ...pass.errors]
      onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
      setPhase(`Passe ${attempt} — correction refusee par anti-regression, rollback automatique.`, Math.min(94, 76 + attempt * 3))
      lastScore = currentScore
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
