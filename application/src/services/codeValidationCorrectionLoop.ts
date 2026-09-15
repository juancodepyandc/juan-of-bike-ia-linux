import type { CodeIntent } from './codeIntent.ts'
import type { CodeMissionDossier } from './codeMissionControl.ts'
import { buildCorrectionStrategy, classifyErrors, shouldContinueLoop, type CorrectionPass } from './codeAutoCorrection.ts'
import { countModelPasses } from './codeCorrectionBudget.ts' // escalade = passes modele
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import { extractNotes, parseCodeFiles } from './codeGeneratedFileParser.ts'
import { detectEnvironmentBlocker } from './codeGenerationDiagnostics.ts'
import { buildCorrectionMessages } from './codeCorrectionMessages.ts'
import { mergeExistingWithUpdates } from './codeSubjectAssets.ts'
import { attemptLocalFileRepair, validateOutputMatchesIntent } from './codeProjectValidation.ts'
import { formatCodeRegressionGuardReport, inspectCodePatchRegression } from './codeRegressionGuard.ts'
import {
  buildRegressionFeedbackBlock,
  filesImplicatedByFailures,
} from './codeCorrectionRegressionFeedback.ts'
import { gatherCorrectionContext } from './codeCorrectionContextGathering.ts'
import { normalizedFilesChanged, collectFailingStepOutputs, truncateCorrectionErrors, compactCorrectionLog } from './codeCorrectionLog.ts'
export { normalizedFilesChanged, collectFailingStepOutputs, truncateCorrectionErrors, compactCorrectionLog } from './codeCorrectionLog.ts'
import { RESERVED_OUTPUT_TOKENS } from './codeCorrectionPromptBudget.ts'
import {
  CODE_EXPERT_CONTEXT_TOKENS, CORRECTION_FIRST_BYTE_TIMEOUT_MS, CORRECTION_TIMEOUT_MS,
  getModelShortName, selectModel, type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'
import { computeSandboxScore } from './codeValidationScoring.ts'
import { handleSandboxInfrastructureFailure } from './codeInfrastructureFailure.ts'
import { runCorrectionQualityGates } from './codeCorrectionQualityGates.ts'

type ValidationCorrectionLoopResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  totalAttempts: number
  finalScore: number
  /**
   * La validation a-t-elle ete EMPECHEE (bridge arrete, reseau coupe) ?
   * Distinct d un echec de validation: ici le juge n a rien mesure.
   */
  infrastructureFailure: boolean
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
  let infrastructureFailure = false
  let rescueRegenerationUsed = false
  let toolingEvaluationUsed = false
  // Garde anti-regression: parlait a l UI, jamais au correcteur.
  let guardRejectionStreak = 0
  let lastGuardReport: string | null = null

  while (true) {
    attempt += 1

    if (signal?.aborted) break

    setPhase(`Sandbox passe ${attempt} — validation en cours...`, Math.min(88, 70 + attempt * 3))
    sandboxResult = await runCodeSandboxValidation({
      files: currentFiles,
      prompt,
      setPhase,
      setProgress: (detail) => setPhase(detail, Math.min(89, 72 + attempt * 3)),
    })

    if (normalizedFilesChanged(currentFiles, sandboxResult.normalizedFiles)) {
      currentFiles = sandboxResult.normalizedFiles!
      onFilesUpdate(currentFiles, currentNotes)
    }

    // Une validation qui n a pas pu s executer ne dit rien sur le code (mesure
    // reelle: 8 passes a score 0, ~17 min, lint degrade de 95 % a 80 %).
    const infraFailure = handleSandboxInfrastructureFailure({
      result: sandboxResult, files: currentFiles, notes: currentNotes,
      score: 0, onValidationUpdate, onFilesUpdate, setPhase,
    })
    if (infraFailure) {
      infrastructureFailure = true
      currentNotes = infraFailure.notes
      lastScore = computeSandboxScore(sandboxResult, currentFiles, intent)
      break
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
    // Escalade comptee en PASSES MODELE, pas en numero de passe (mesure v129).
    const strategy = sandboxResult.ok
      ? null
      : buildCorrectionStrategy(errorCategories, countModelPasses(correctionLog) + 1, correctionLog)

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
        guardRejectionStreak += 1
        lastGuardReport = reportText
        pass.errors = [`[Auto-reparation locale refusee]\n${reportText}`, ...pass.errors]
        onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
        setPhase(`Passe ${attempt} - auto-reparation refusee par anti-regression.`, Math.min(93, 71 + attempt * 3))
        lastScore = currentScore
        continue
      }

      currentFiles = localRepair.files
      pass.localRepairOnly = true // aucun modele charge: hors budget (codeCorrectionBudget)
      guardRejectionStreak = 0
      lastGuardReport = null
      currentNotes = `${currentNotes ? `${currentNotes}\n\n` : ''}Auto-reparation locale: ${localRepair.reason}`
      onFilesUpdate(currentFiles, currentNotes)
      setPhase(`Passe ${attempt} - auto-reparation locale appliquee.`, Math.min(93, 71 + attempt * 3))
      lastScore = currentScore
      continue
    }

    if (!shouldContinueLoop(correctionLog, attempt, errorCategories, currentFiles.length)) {
      lastScore = currentScore
      const reason = currentScore >= 100
        ? 'livraison validee a 100%'
        : `boucle infinie detectee sur la meme erreur apres ${attempt} passes`
      setPhase(`Arret de la boucle : ${reason}.`, 89)
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

    const gathered = await gatherCorrectionContext({
      prompt,
      attempt,
      strategy: strategy!,
      intent,
      configuredCodeModel,
      correctionLog,
      errorCategories,
      failingOutputs: collectFailingStepOutputs(sandboxResult),
      isFlatlining,
      toolingEvaluationUsed,
      pass,
      currentScore,
      setPhase,
      onCorrectionLogUpdate,
      signal,
    })
    const { researchContext, reasoningContext } = gathered
    toolingEvaluationUsed = gathered.toolingEvaluationUsed

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

      setPhase(`Passe ${attempt} — regeneration de secours complete...`, Math.min(94, 75 + attempt * 3))
      const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
      const rescueResponse = await resilientOllamaGenerate(correctionModel, rescuePrompt, {
        timeoutMs: CORRECTION_TIMEOUT_MS,
        firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
        signal,
        num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
        neverMemorySkip: true,
        onRecoveryAttempt: (ev) => {
          setPhase(`Passe ${attempt} — sauvetage Ollama: ${ev.action}...`, Math.min(94, 76 + attempt * 3))
        },
      })

      const rescueContent = rescueResponse?.response?.trim() || ''
      const rescueFiles = parseCodeFiles(rescueContent)
      if (rescueFiles.length > 0) {
        const mergedRescue = mergeExistingWithUpdates(currentFiles, rescueFiles)
        if (!validateOutputMatchesIntent(mergedRescue, intent)) {
          const regressionReport = inspectCodePatchRegression(currentFiles, mergedRescue)
          if (regressionReport.ok) {
            currentFiles = mergedRescue
            guardRejectionStreak = 0
            lastGuardReport = null
            currentNotes = extractNotes(rescueContent)
            onFilesUpdate(currentFiles, currentNotes)
            lastScore = currentScore
            continue
          }

          const reportText = formatCodeRegressionGuardReport(regressionReport)
          guardRejectionStreak += 1
          lastGuardReport = reportText
          pass.errors = [`[Regeneration de secours refusee]\n${reportText}`, ...pass.errors]
          onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
          setPhase(`Passe ${attempt} — regeneration refusee par anti-regression.`, Math.min(94, 76 + attempt * 3))
        }
      }
    }

    const { serializeCodeMissionDossier } = await import('./codeMissionControl.ts')
    const { serializeCodePreflightReport } = await import('./codePreflight.ts')
    const regressionFeedback = buildRegressionFeedbackBlock({
      guardReport: lastGuardReport,
      consecutiveRejections: guardRejectionStreak,
      implicatedFiles: filesImplicatedByFailures(currentFiles, collectFailingStepOutputs(sandboxResult)),
    })
    if (regressionFeedback) {
      setPhase(
        `Passe ${attempt} — ${guardRejectionStreak} refus anti-regression: portee resserree sur les fichiers fautifs...`,
        Math.min(94, 74 + attempt * 3),
      )
    }
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
      regressionFeedback,
    })

    setPhase(`Passe ${attempt} — ${modelShort} corrige le code...`, Math.min(94, 74 + attempt * 3))
    const { resilientOllamaChat } = await import('./ollamaResilience.ts')
    const repairResponse = await resilientOllamaChat(correctionModel, correctionMessages, 0.05, {
      timeoutMs: CORRECTION_TIMEOUT_MS,
      firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
      signal,
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      // Aucun plafond de sortie n etait pose ici, contrairement a la generation.
      // Un modele sans plafond, dans une fenetre deja pleine, genere jusqu a
      // epuiser le temps: 20 min pour la passe 4 du run 1141.
      num_predict: RESERVED_OUTPUT_TOKENS,
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
      guardRejectionStreak += 1
      lastGuardReport = reportText
      pass.errors = [`[Correction refusee]\n${reportText}`, ...pass.errors]
      onCorrectionLogUpdate([...correctionLog], attempt, currentScore)
      setPhase(`Passe ${attempt} — correction refusee par anti-regression (${guardRejectionStreak}e refus), rollback automatique.`, Math.min(94, 76 + attempt * 3))
      lastScore = currentScore
      continue
    }

    currentFiles = mergedCandidate
    guardRejectionStreak = 0
    lastGuardReport = null
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
    infrastructureFailure,
  }
}
