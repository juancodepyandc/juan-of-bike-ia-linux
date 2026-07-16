import type { CodeIntent } from './codeIntent.ts'
import type { CodeMissionDossier } from './codeMissionControl.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import type { BrandFidelityReport } from './codeFidelityGate.ts'
import { evaluateBrandFidelity } from './codeFidelityGate.ts'
import { detectNonCodePlanningNarrative, extractNotes, fatalEmissionIssues, parseCodeFiles, parseCodeFilesWithReport } from './codeGeneratedFileParser.ts'
import { mergeExistingWithUpdates } from './codeSubjectAssets.ts'
import { assertCodePatchNonRegression, buildCodeIncrementalPatchScope } from './codeIncrementalPatchScope.ts'
import { validateOutputMatchesIntent } from './codeProjectValidation.ts'
import { computeContentQualityScore } from './codeQualityGates.ts'
import { buildStructuredEmissionInstructions } from './codeProjectEmission.ts'
import { describeArchitecturePlanContractIssue } from './codeArchitecturePlanContract.ts'
import {
  DOCUMENTATION_EXTENSIONS_EARLY,
  clipText,
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'
import { runAgenticGenerationPhase } from './codeAgenticGenerationPhase.ts'

type BestAttempt = { files: CodeFile[]; notes: string; score: number }

export type OutputRetryResult = {
  files: CodeFile[]
  notes: string
  latestRawGenerationContent: string
  outputRetry: number
  latestBrandFidelity: BrandFidelityReport | null
}

export function countRealCodeFiles(files: CodeFile[]): number {
  return files.filter((file) => {
    const extension = file.name.split('.').pop()?.toLowerCase() || ''
    return !DOCUMENTATION_EXTENSIONS_EARLY.has(extension)
  }).length
}

export function isNetworkGenerationError(message: string): boolean {
  return /failed to fetch|network|TypeError|524|connection closed/i.test(message)
}

export function rememberBestAttempt(
  bestAttempt: BestAttempt | null,
  candidate: { files: CodeFile[]; notes: string; score: number },
): BestAttempt | null {
  if (candidate.files.length === 0) return bestAttempt
  if (!bestAttempt) return candidate
  if (candidate.files.length > bestAttempt.files.length) return candidate
  if (candidate.files.length === bestAttempt.files.length && candidate.score > bestAttempt.score) return candidate
  return bestAttempt
}

export function applyBestAttemptFallback(
  files: CodeFile[],
  notes: string,
  bestAttempt: BestAttempt | null,
): { files: CodeFile[]; notes: string } {
  if (files.length > 0 || !bestAttempt || bestAttempt.files.length === 0) {
    return { files, notes }
  }

  console.warn(`[CodeOrchestrator] retry loop exhausted — delivering best attempt (${bestAttempt.files.length} fichiers) instead of 0.`)
  return {
    files: bestAttempt.files,
    notes: bestAttempt.notes
      ? `${bestAttempt.notes}\n\n[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.`
      : '[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.',
  }
}

export function buildBrandRetryBlock(
  brandFidelity: BrandFidelityReport,
  brandSubject: CodeIntent['assetPlan']['subject'] | null | undefined,
): string {
  if (!brandFidelity.shouldRetry || brandSubject?.source !== 'brand' || !brandSubject.brandProfile) {
    return ''
  }

  return [
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
    '- Asset image inter-module disponible dans le manifeste: utilise PLACEHOLDER_SUBJECT_IMG dans le hero et une section showcase.',
    '- INTERDIT: restaurant, menu du jour, blog culinaire, SaaS abstrait. C est une marque/produit emblematique, traite-la comme telle.',
  ].filter(Boolean).join('\n')
}

export async function runGeneratedOutputRetryLoop({
  prompt,
  enrichedPrompt,
  latestRawGenerationContent,
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
}: {
  prompt: string
  enrichedPrompt: string
  latestRawGenerationContent: string
  intent: CodeIntent
  architecturePlan: string
  missionDossier: CodeMissionDossier
  effectiveExistingFiles: CodeFile[]
  contextImages: string[]
  configuredCodeModel: string
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  signal?: AbortSignal
  modelRouting?: CodeModelRoutingContext
}): Promise<OutputRetryResult> {
  const { files: parsed, issues: parseIssues } = parseCodeFilesWithReport(latestRawGenerationContent)
  let initialNotes = extractNotes(latestRawGenerationContent)
  // Ne PAS laisser tomber un fichier en silence: si le flux structure contient
  // des anomalies non recuperables (en-tete malforme, flux tronque sans marqueur
  // de fin), on le remonte a l utilisateur au lieu de perdre le fichier sans un mot.
  const fatalParseIssues = fatalEmissionIssues(parseIssues)
  if (fatalParseIssues.length > 0) {
    const kinds = [...new Set(fatalParseIssues.map((issue) => issue.type))].join(', ')
    const warning = `Avertissement extraction: ${fatalParseIssues.length} fichier(s) non extractible(s) du flux structure (${kinds}). Le contenu est probablement tronque ; regeneration ciblee recommandee.`
    initialNotes = initialNotes ? `${initialNotes}\n\n${warning}` : warning
    setPhase(warning, 12)
  }
  let initialFiles = effectiveExistingFiles.length > 0 && parsed.length > 0
    ? mergeExistingWithUpdates(effectiveExistingFiles, parsed)
    : parsed

  // WS5: en MODIFICATION d un projet existant, le scope de patch incremental
  // designe des fichiers proteges (hors cible). On ENFORCE ici que la generation
  // ne les a pas alteres/supprimes — le scope n etait jusqu ici qu un indice de
  // prompt jamais verifie. Une violation est remontee (non silencieuse).
  if (effectiveExistingFiles.length > 0 && parsed.length > 0) {
    const scope = buildCodeIncrementalPatchScope({ prompt, files: effectiveExistingFiles })
    const nonRegression = assertCodePatchNonRegression({
      before: effectiveExistingFiles,
      after: initialFiles,
      scope,
    })
    if (!nonRegression.ok) {
      const touched = nonRegression.errors.slice(0, 6).join(', ')
      const warning = `Regression de portee WS5: ${nonRegression.errors.length} fichier(s) protege(s) modifie(s)/supprime(s) hors cible (${touched}). Verifie que seuls les fichiers pertinents ont ete changes.`
      initialNotes = initialNotes ? `${initialNotes}\n\n${warning}` : warning
      setPhase(warning, 14)
    }
  }

  const isExpertComplexProject = intent.complexity === 'complex' || intent.complexity === 'enterprise'
  const maxOutputRetries = isExpertComplexProject ? 6 : 3
  const maxNetworkErrors = isExpertComplexProject ? 4 : 2
  let outputRetry = 0
  let networkErrors = 0
  let latestBrandFidelity: BrandFidelityReport | null = null
  let bestAttempt: BestAttempt | null = null
  const {
    buildDraftRegenerationPrompt,
    reviewGeneratedCodeDraft,
    serializeCodeMissionDossier,
  } = await import('./codeMissionControl.ts')

  while (outputRetry < maxOutputRetries) {
    const draftReview = await reviewGeneratedCodeDraft({
      prompt,
      intent,
      files: initialFiles,
      architecturePlan,
      missionDossier,
      model: configuredCodeModel,
    })
    const brandSubject = intent.assetPlan?.subject
    const brandFidelity = evaluateBrandFidelity(intent, initialFiles)
    latestBrandFidelity = brandFidelity
    const brandIssueLine = brandFidelity.shouldRetry && brandFidelity.retryHint
      ? `Fidelite sujet (BRAND): ${brandFidelity.retryHint}`
      : null

    const issueNarrative = detectNonCodePlanningNarrative(latestRawGenerationContent)
    const issueIntent = validateOutputMatchesIntent(initialFiles, intent)
    const issueArchitecturePlan = describeArchitecturePlanContractIssue(initialFiles, architecturePlan)
    const issueDraft = draftReview.verdict === 'regenerate'
      ? [
          draftReview.summary,
          ...draftReview.criticalIssues,
          ...draftReview.missingFiles,
        ].filter(Boolean).join(' | ')
      : null
    const draftBlocks = issueDraft && countRealCodeFiles(initialFiles) < 2 ? issueDraft : null
    const outputIssue = issueNarrative || issueIntent || issueArchitecturePlan || brandIssueLine || draftBlocks

    bestAttempt = rememberBestAttempt(bestAttempt, {
      files: initialFiles,
      notes: initialNotes,
      score: computeContentQualityScore(initialFiles, intent),
    })
    if (outputIssue) {
      console.warn(
        `[CodeOrchestrator] outputIssue @retry ${outputRetry} | files=${initialFiles.length} | `
        + `narrative=${!!issueNarrative} intentMismatch=${issueIntent ? JSON.stringify(issueIntent.slice(0, 80)) : false} `
        + `plan=${!!issueArchitecturePlan} brand=${!!brandIssueLine} draftRegenerate=${!!issueDraft}`,
      )
    }
    if (!outputIssue) break

    outputRetry++
    const escalation = outputRetry + 1
    const retryModel = selectModel('generation', intent, escalation, generationModel, modelRouting)
    const modelShort = retryModel.split(':')[0]

    setPhase(
      `Sortie incorrecte (tentative ${outputRetry}/${maxOutputRetries}) — regeneration via ${modelShort}...`,
      48 + outputRetry * 4,
    )

    const retryPrompt = [
      `ERREUR CRITIQUE (tentative ${outputRetry + 1}): La sortie precedente etait INCORRECTE.`,
      `Probleme: ${outputIssue}`,
      '',
      buildBrandRetryBlock(brandFidelity, brandSubject),
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
      '- NE SIMPLIFIE PAS LES FONCTIONNALITES: preserve le scope demande, corrige la structure et livre tous les fichiers necessaires.',
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
      buildStructuredEmissionInstructions(),
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
      const retryGeneration = await runAgenticGenerationPhase({
        prompt: retryPrompt,
        intent,
        architecturePlan,
        existingFiles: effectiveExistingFiles,
        contextImages,
        generationModel,
        escalationLevel: escalation,
        setPhase,
        onToken,
        signal,
        modelRouting: { ...modelRouting, plateau: escalation >= 4 },
      })
      if (retryGeneration && !retryGeneration.ok && signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError')
      }
      if (!retryGeneration?.ok) {
        throw new Error(`agentic_retry_failed:${retryGeneration?.error || 'plan_without_queue'}`)
      }
      retryContent = retryGeneration.content
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (isNetworkGenerationError(msg)) {
        networkErrors += 1
        setPhase(`Erreur reseau (${networkErrors}/${maxNetworkErrors}) pendant la regeneration — tentative ${outputRetry}...`, 50 + outputRetry * 4)
        if (networkErrors >= maxNetworkErrors) {
          setPhase('Trop d erreurs reseau consecutives — arret propre du pipeline.', 96)
          break
        }
        await new Promise((resolve) => setTimeout(resolve, 2000))
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

  const fallback = applyBestAttemptFallback(initialFiles, initialNotes, bestAttempt)

  return {
    files: fallback.files,
    notes: fallback.notes,
    latestRawGenerationContent,
    outputRetry,
    latestBrandFidelity,
  }
}
