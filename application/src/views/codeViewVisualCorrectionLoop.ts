import { startDevServer, type DevServerState } from '../services/codeDevServer'
import { blendRenderedVisualIntoFinalScore, runCodeVisualRenderAudit } from '../services/codeVisualAuditClient'
import { MAX_VISUAL_CORRECTION_PASSES, decideVisualCorrection } from '../services/codeVisualCorrectionDecision'
import type { CodeFile, CodeOrchestrationResult } from '../services/codeOrchestrator'
import { getErrorMessage } from '../utils/errors'

/**
 * WS9 — boucle du juge visuel DANS le cycle de livraison. Extrait de la vue pour
 * rester sous la limite de taille et isoler la logique. La vue fournit deux
 * callbacks (regenerer, appliquer un resultat) ; ce module orchestre dev-server
 * -> audit rendu -> decision -> regeneration ciblee, en bornant le budget.
 */

export type VisualCorrectionLoopDeps = {
  visionModel?: string
  signal: AbortSignal
  setProgress: (message: string) => void
  setPhase: (detail: string, progress: number) => void
  setDevServerState: (state: DevServerState) => void
  setDesignReport: (report: { score: number; missing: string[]; penalties: string[] }) => void
  setFinalScore: (score: number) => void
  /** Relance une orchestration ciblee esthetique a partir des fichiers livres. */
  regenerate: (directive: string, existingFiles: CodeFile[]) => Promise<CodeOrchestrationResult>
  /** Applique un resultat regenere dans l etat de la vue (fichiers, notes, ...). */
  applyRegenResult: (result: CodeOrchestrationResult) => void
}

export type VisualCorrectionLoopResult = {
  result: CodeOrchestrationResult
  effectiveFinalScore: number
  visualAuditSummary: string | null
}

export async function runVisualCorrectionLoop(
  initial: CodeOrchestrationResult,
  deps: VisualCorrectionLoopDeps,
): Promise<VisualCorrectionLoopResult> {
  let result = initial
  let effectiveFinalScore = result.finalScore
  let visualAuditSummary: string | null = null

  if (!result.intent.needsDevServer || !result.sandboxResult?.rootPath) {
    return { result, effectiveFinalScore, visualAuditSummary }
  }

  let previousVisualScore: number | null = null
  for (let visualPass = 0; visualPass <= MAX_VISUAL_CORRECTION_PASSES; visualPass++) {
    const rootPath = result.sandboxResult?.rootPath
    if (!rootPath) break
    deps.setProgress('Demarrage du serveur de dev pour preview...')
    deps.setPhase('Demarrage du dev server...', 95)
    const url = await startDevServer(rootPath, result.intent, deps.setDevServerState)
    if (!url) {
      deps.setProgress('Preview live indisponible. Les fichiers restent livres pour inspection manuelle.')
      break
    }

    deps.setProgress(`Dev server pret: ${url}. Audit visuel rendu reel...`)
    let auditReport
    try {
      const visualAudit = await runCodeVisualRenderAudit({
        url,
        includeVision: Boolean(deps.visionModel),
        visionModel: deps.visionModel,
        waitMs: 2500,
        signal: deps.signal,
      })
      auditReport = visualAudit.report
      visualAuditSummary = auditReport.summary
      deps.setDesignReport({
        score: auditReport.score,
        missing: auditReport.failedChecks,
        penalties: auditReport.checks.filter((check) => !check.passed).map((check) => check.label),
      })
      const blended = blendRenderedVisualIntoFinalScore(result.finalScore, auditReport)
      effectiveFinalScore = blended.score
      deps.setFinalScore(blended.score)
    } catch (auditError) {
      visualAuditSummary = `Audit visuel rendu indisponible: ${getErrorMessage(auditError, 'erreur inconnue')}`
      break
    }

    const decision = decideVisualCorrection({ report: auditReport, passIndex: visualPass, previousVisualScore })
    if (!decision.regenerate || !decision.directive) {
      if (auditReport.score < auditReport.floor) {
        visualAuditSummary = `${auditReport.summary} Qualite visuelle ${auditReport.score}/100 sous le seuil ${auditReport.floor}, livree apres ${visualPass} passe(s) esthetique(s).`
      }
      break
    }

    // Regeneration CIBLEE sur l apparence, en repartant des fichiers livres.
    previousVisualScore = auditReport.score
    deps.setProgress(`Qualite visuelle ${auditReport.score}/100 sous le seuil — passe esthetique ${visualPass + 1}/${MAX_VISUAL_CORRECTION_PASSES}...`)
    deps.setPhase('Correction visuelle ciblee...', 96)
    try {
      const regen = await deps.regenerate(decision.directive, result.files)
      if (regen.files.length === 0) break // regen infructueuse -> on garde le meilleur etat
      result = regen
      deps.applyRegenResult(regen)
      effectiveFinalScore = regen.finalScore
    } catch (regenError) {
      visualAuditSummary = `${visualAuditSummary ?? ''} (passe esthetique interrompue: ${getErrorMessage(regenError, 'erreur inconnue')})`.trim()
      break
    }
  }

  return { result, effectiveFinalScore, visualAuditSummary }
}
