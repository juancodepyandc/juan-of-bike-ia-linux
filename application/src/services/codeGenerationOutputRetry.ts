import type { OllamaMessage } from '../types/app'
import type { RecoveryEvent } from './ollamaResilience.ts'
import type { CodeIntent } from './codeIntent.ts'
import type { CodeMissionDossier } from './codeMissionControl.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import type { CodeFile, PhaseCallback } from './codeOrchestrator.ts'
import type { GenerationPivotContext } from './codePipelinePhases.ts'
import type { BrandFidelityReport } from './codeFidelityGate.ts'
import { evaluateBrandFidelity } from './codeFidelityGate.ts'
import { detectNonCodePlanningNarrative, extractNotes, parseCodeFiles } from './codeGeneratedFileParser.ts'
import { mergeExistingWithUpdates } from './codeSubjectAssets.ts'
import { validateOutputMatchesIntent } from './codeProjectValidation.ts'
import { computeContentQualityScore } from './codeQualityGates.ts'
import { buildStructuredEmissionInstructions } from './codeProjectEmission.ts'
import {
  DOCUMENTATION_EXTENSIONS_EARLY,
  clipText,
  selectModel,
  type CodeModelRoutingContext,
} from './codePipelineRuntime.ts'
import { runGenerationPhase } from './codePipelinePhases.ts'

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
    '- Markers d images REELLES deja telechargees: PLACEHOLDER_SUBJECT_IMG, PLACEHOLDER_SUBJECT_IMG_1..4. Place-en au moins 2 dans la page.',
    '- INTERDIT: restaurant, menu du jour, blog culinaire, SaaS abstrait. C est une marque/produit emblematique, traite-la comme telle.',
  ].filter(Boolean).join('\n')
}

export async function runGeneratedOutputRetryLoop({
  prompt,
  enrichedPrompt,
  latestRawGenerationContent,
  intent,
  preflightReport,
  architecturePlan,
  missionDossier,
  conversationHistory,
  effectiveExistingFiles,
  contextImages,
  configuredCodeModel,
  generationModel,
  setPhase,
  onToken,
  trackRecovery,
  signal,
  pivotContext,
  modelRouting,
}: {
  prompt: string
  enrichedPrompt: string
  latestRawGenerationContent: string
  intent: CodeIntent
  preflightReport: CodePreflightReport | null
  architecturePlan: string | null
  missionDossier: CodeMissionDossier
  conversationHistory: OllamaMessage[]
  effectiveExistingFiles: CodeFile[]
  contextImages: string[]
  configuredCodeModel: string
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  trackRecovery: (event: RecoveryEvent) => void
  signal?: AbortSignal
  pivotContext?: GenerationPivotContext
  modelRouting?: CodeModelRoutingContext
}): Promise<OutputRetryResult> {
  const parsed = parseCodeFiles(latestRawGenerationContent)
  let initialNotes = extractNotes(latestRawGenerationContent)
  let initialFiles = effectiveExistingFiles.length > 0 && parsed.length > 0
    ? mergeExistingWithUpdates(effectiveExistingFiles, parsed)
    : parsed

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
    const issueDraft = draftReview.verdict === 'regenerate'
      ? [
          draftReview.summary,
          ...draftReview.criticalIssues,
          ...draftReview.missingFiles,
        ].filter(Boolean).join(' | ')
      : null
    const draftBlocks = issueDraft && countRealCodeFiles(initialFiles) < 2 ? issueDraft : null
    const outputIssue = issueNarrative || issueIntent || brandIssueLine || draftBlocks

    bestAttempt = rememberBestAttempt(bestAttempt, {
      files: initialFiles,
      notes: initialNotes,
      score: computeContentQualityScore(initialFiles, intent),
    })
    if (outputIssue) {
      console.warn(
        `[CodeOrchestrator] outputIssue @retry ${outputRetry} | files=${initialFiles.length} | `
        + `narrative=${!!issueNarrative} intentMismatch=${issueIntent ? JSON.stringify(issueIntent.slice(0, 80)) : false} `
        + `brand=${!!brandIssueLine} draftRegenerate=${!!issueDraft}`,
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
        modelRouting,
      )
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
