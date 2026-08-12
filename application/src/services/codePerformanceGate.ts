// Performance mesuree au RENDU.
//
// Le module juge deja le style, la composition et l accessibilite a l ecran.
// La performance manquait, et c est le dernier critere qui separe « joli » de
// « professionnel »: une page magnifique qui met trois secondes a peindre, qui
// saute pendant le chargement ou qui empile 4 000 noeuds est un mauvais
// livrable, quel que soit son score esthetique.
//
// Comme pour les autres portes: le navigateur mesure, ce module note. Aucun
// seuil n est invente — ils viennent des reperes publics de Web Vitals, adaptes
// au fait qu on mesure en local (pas de latence reseau), donc plus severes.

export type PerformanceMetrics = {
  /** First Contentful Paint (ms). */
  firstContentfulPaint: number
  /** Temps jusqu au DOM interactif (ms). */
  domInteractive: number
  /** Cumulative Layout Shift observe. */
  layoutShift: number
  /** Nombre de noeuds DOM. */
  domNodes: number
  /** Poids total transfere (octets). */
  transferredBytes: number
  /** Taches longues (> 50 ms) pendant le chargement. */
  longTasks: number
  /** Images servies sans dimensions explicites (source de saut de page). */
  imagesWithoutDimensions: number
}

export type PerformanceCheck = {
  id: string
  label: string
  passed: boolean
  weight: number
  evidence?: string
}

export type PerformanceVerdict = {
  score: number
  ok: boolean
  floor: number
  checks: PerformanceCheck[]
  failedChecks: string[]
  critique: string
}

// Reperes: en LOCAL il n y a ni reseau ni latence serveur, donc on attend
// nettement mieux que les seuils publics (FCP 1800 ms / CLS 0.1).
export const BUDGETS = {
  firstContentfulPaint: 1200,
  domInteractive: 1800,
  layoutShift: 0.1,
  domNodes: 2500,
  transferredBytes: 2_000_000,
  longTasks: 2,
} as const

const FLOOR = 70

function ko(value: number, unit: string): string {
  return unit === 'o' ? `${Math.round(value / 1024)} Ko` : `${Math.round(value)} ${unit}`
}

export function scorePerformance(metrics: PerformanceMetrics): PerformanceVerdict {
  const checks: PerformanceCheck[] = [
    {
      id: 'first_paint',
      label: `Premiere peinture < ${BUDGETS.firstContentfulPaint} ms`,
      passed: metrics.firstContentfulPaint > 0 && metrics.firstContentfulPaint <= BUDGETS.firstContentfulPaint,
      weight: 22,
      evidence: metrics.firstContentfulPaint > BUDGETS.firstContentfulPaint
        ? `mesure: ${ko(metrics.firstContentfulPaint, 'ms')}`
        : undefined,
    },
    {
      id: 'interactive',
      label: `DOM interactif < ${BUDGETS.domInteractive} ms`,
      passed: metrics.domInteractive > 0 && metrics.domInteractive <= BUDGETS.domInteractive,
      weight: 16,
      evidence: metrics.domInteractive > BUDGETS.domInteractive ? `mesure: ${ko(metrics.domInteractive, 'ms')}` : undefined,
    },
    {
      id: 'layout_stability',
      label: `Pas de saut de page (CLS <= ${BUDGETS.layoutShift})`,
      passed: metrics.layoutShift <= BUDGETS.layoutShift,
      weight: 20,
      evidence: metrics.layoutShift > BUDGETS.layoutShift ? `CLS mesure: ${metrics.layoutShift.toFixed(3)}` : undefined,
    },
    {
      id: 'image_dimensions',
      label: `Images dimensionnees (${metrics.imagesWithoutDimensions} sans)`,
      passed: metrics.imagesWithoutDimensions === 0,
      weight: 12,
      evidence: metrics.imagesWithoutDimensions > 0
        ? `${metrics.imagesWithoutDimensions} image(s) sans width/height ni aspect-ratio: cause directe du saut de page`
        : undefined,
    },
    {
      id: 'dom_weight',
      label: `Moins de ${BUDGETS.domNodes} noeuds DOM`,
      passed: metrics.domNodes <= BUDGETS.domNodes,
      weight: 12,
      evidence: metrics.domNodes > BUDGETS.domNodes ? `mesure: ${metrics.domNodes} noeuds` : undefined,
    },
    {
      id: 'payload_weight',
      label: `Poids transfere < ${Math.round(BUDGETS.transferredBytes / 1024)} Ko`,
      passed: metrics.transferredBytes <= BUDGETS.transferredBytes,
      weight: 10,
      evidence: metrics.transferredBytes > BUDGETS.transferredBytes ? `mesure: ${ko(metrics.transferredBytes, 'o')}` : undefined,
    },
    {
      id: 'main_thread',
      label: `Au plus ${BUDGETS.longTasks} tache(s) longue(s) au chargement`,
      passed: metrics.longTasks <= BUDGETS.longTasks,
      weight: 8,
      evidence: metrics.longTasks > BUDGETS.longTasks ? `${metrics.longTasks} taches > 50 ms bloquent le fil principal` : undefined,
    },
  ]

  const total = checks.reduce((sum, check) => sum + check.weight, 0)
  const earned = checks.filter((check) => check.passed).reduce((sum, check) => sum + check.weight, 0)
  const score = Math.round((earned / total) * 100)
  const failedChecks = checks.filter((check) => !check.passed).map((check) => check.id)

  const critique = failedChecks.length === 0
    ? `Performance mesuree au rendu: ${score}/100, dans les budgets.`
    : [
      `## PERFORMANCE (${score}/100, seuil ${FLOOR}) — mesuree sur la page RENDUE`,
      '',
      ...checks.filter((check) => !check.passed).map((check) => `- ${check.label}${check.evidence ? ` — ${check.evidence}` : ''}`),
      '',
      'Leviers, du plus rentable au moins rentable: donner width/height (ou',
      'aspect-ratio) aux images supprime le saut de page; alleger le DOM en',
      'sortant les listes repetitives; differer le JS non critique; et compresser',
      'ou redimensionner les images avant de les embarquer.',
    ].join('\n')

  return { score, ok: score >= FLOOR, floor: FLOOR, checks, failedChecks, critique }
}
