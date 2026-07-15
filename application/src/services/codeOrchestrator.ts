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
  buildDraftRegenerationPrompt,
  reviewGeneratedCodeDraft,
  serializeCodeMissionDossier,
  type CodeMissionDossier,
} from './codeMissionControl'
import type { CorrectionPass } from './codeAutoCorrection'
import type { CodeSandboxResult } from './codeSandbox'
import type { CodePreflightReport } from './codePreflight'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { parseCodeFiles, serializeCodeFiles, extractNotes, detectNonCodePlanningNarrative } from './codeGeneratedFileParser.ts'
export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
import {
  buildEmptyGenerationDiagnostic,
} from './codeGenerationDiagnostics.ts'
import { runValidationAndCorrectionLoop } from './codeValidationCorrectionLoop.ts'
import {
  applySubjectImagePlaceholder,
  mergeExistingWithUpdates,
} from './codeSubjectAssets.ts'
import { evaluateBrandFidelity, type BrandFidelityReport } from './codeFidelityGate'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
export { upsertProjectSupportFilesForTest } from './codeProjectSupportFiles.ts'
import { validateOutputMatchesIntent } from './codeProjectValidation.ts'
import {
  DOCUMENTATION_EXTENSIONS_EARLY,
  clipText,
  selectModel,
} from './codePipelineRuntime.ts'
import {
  runGenerationPhase,
  runIntentPhase,
  runPlanningPhase,
  runPreflightPhase,
  type GenerationPivotContext,
} from './codePipelinePhases.ts'
import { prepareCodePlanningContext } from './codePipelinePreparation.ts'
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

  const { planningPrompt } = await prepareCodePlanningContext({
    prompt,
    reformulatedEnriched,
    intent,
    followUp,
    configuredCodeModel,
    setPhase,
  })

  // Phase 2: Deep reasoning + architecture planning via llama4.
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
