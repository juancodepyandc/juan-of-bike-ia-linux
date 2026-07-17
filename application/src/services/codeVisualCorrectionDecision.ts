import { buildRenderedVisualAuditCritique } from './codeVisualRenderAudit.ts'
import type { VisualFidelityReport } from './codeVisualFidelity.ts'

/**
 * WS9 — juge visuel DANS la boucle. Avant, l'audit rendu ne faisait que
 * "recommander" une regeneration (message decoratif). Ici on decide reellement
 * s'il faut relancer une passe ciblee sur l'apparence, en bornant le budget et
 * en s'arretant si une passe n'ameliore plus (pas de churn infini).
 *
 * Module PUR (aucun I/O, aucune dependance React) -> entierement teste; la vue
 * se contente d'orchestrer regen + re-audit autour de cette decision.
 */

export const MAX_VISUAL_CORRECTION_PASSES = 2

// Gain de score visuel minimal pour justifier une passe supplementaire.
export const MIN_VISUAL_IMPROVEMENT = 2

export type VisualCorrectionInput = {
  report: VisualFidelityReport
  /** 0 = audit initial ; 1 = apres la 1re regen ; ... */
  passIndex: number
  maxPasses?: number
  /** Score visuel de la passe precedente (null au 1er audit). */
  previousVisualScore?: number | null
}

export type VisualCorrectionDecision = {
  regenerate: boolean
  directive: string | null
  reason: string
}

export function decideVisualCorrection(input: VisualCorrectionInput): VisualCorrectionDecision {
  const maxPasses = input.maxPasses ?? MAX_VISUAL_CORRECTION_PASSES
  const { report, passIndex } = input

  // Gate au-dessus du seuil (ou projet non visuel: passed=true, floor=0) -> accepte.
  if (report.passed && report.score >= report.floor) {
    return { regenerate: false, directive: null, reason: 'visual:passed' }
  }
  // Budget epuise -> on livre le meilleur etat avec la critique en note.
  if (passIndex >= maxPasses) {
    return { regenerate: false, directive: null, reason: 'visual:budget-exhausted' }
  }
  // Une regen precedente n'a pas assez ameliore -> inutile d'insister.
  if (
    passIndex > 0 &&
    typeof input.previousVisualScore === 'number' &&
    report.score - input.previousVisualScore < MIN_VISUAL_IMPROVEMENT
  ) {
    return { regenerate: false, directive: null, reason: 'visual:no-improvement' }
  }
  return {
    regenerate: true,
    directive: buildVisualFixDirective(report),
    reason: `visual:below-threshold:${report.score}<${report.floor}`,
  }
}

/** Directive de regeneration ciblee UNIQUEMENT sur l'apparence rendue. */
export function buildVisualFixDirective(report: VisualFidelityReport): string {
  const critique = buildRenderedVisualAuditCritique(report)
  return [
    'CORRECTION VISUELLE CIBLEE — le rendu reel a ete juge sous le seuil esthetique.',
    `Score visuel actuel: ${report.score}/100 (plancher requis ${report.floor}).`,
    critique,
    'Ameliore UNIQUEMENT l apparence rendue: mise en page, hierarchie visuelle,',
    'contraste et lisibilite, espacement/rythme, responsive multi-viewport, etats',
    'interactifs (hover/focus). Ne casse aucune fonctionnalite ni le contenu',
    'existant; conserve la structure et renforce l esthetique jusqu au niveau pro.',
  ].filter(Boolean).join('\n')
}
