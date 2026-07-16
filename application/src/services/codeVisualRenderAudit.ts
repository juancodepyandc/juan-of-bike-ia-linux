import type { VisualFidelityCheck, VisualFidelityReport } from './codeVisualFidelity.ts'

export const CODE_VISUAL_RENDER_AUDIT_SCHEMA = 'aurora.code.visual-render-audit/1'

export type RenderedContrastSample = {
  ratio: number
  source: 'pixel' | 'computed-style'
  viewport: string
  label?: string
}

export type RenderedVisionJudgement = {
  score: number
  verdict: 'tutorial' | 'studio' | 'mixed'
  summary: string
}

export type RenderedViewportAudit = {
  viewport: string
  width: number
  height: number
  screenshotPath?: string
  screenshotDataUrl?: string
  bodyTextLength: number
  consoleErrors: string[]
  exceptions: string[]
  failedRequests: string[]
  canvasPresent: boolean
  textNodeCount: number
  headingCount: number
  mediaCount: number
  interactiveCount: number
  cssVarCount: number
  fontFamilies: string[]
  verticalGapMedian: number | null
  contrastSamples: RenderedContrastSample[]
  vision?: RenderedVisionJudgement
}

export type CodeVisualRenderAudit = {
  schemaVersion: typeof CODE_VISUAL_RENDER_AUDIT_SCHEMA
  url?: string
  createdAt?: number
  viewports: RenderedViewportAudit[]
  references?: Array<{ title: string; url?: string; summary: string }>
}

const REQUIRED_WIDTHS = [390, 834, 1440]

function clampScore(score: number): number {
  if (!Number.isFinite(score)) return 0
  return Math.max(0, Math.min(100, Math.round(score)))
}

function check(id: string, label: string, passed: boolean, weight: number, evidence?: string): VisualFidelityCheck {
  return { id, label, passed, weight, evidence }
}

function hasScreenshot(viewport: RenderedViewportAudit): boolean {
  return Boolean(viewport.screenshotPath || viewport.screenshotDataUrl)
}

function viewportWidths(audit: CodeVisualRenderAudit): number[] {
  return [...new Set(audit.viewports.map((viewport) => Math.round(viewport.width)))].sort((a, b) => a - b)
}

function hasRequiredBreakpoints(audit: CodeVisualRenderAudit): boolean {
  const widths = viewportWidths(audit)
  return REQUIRED_WIDTHS.every((required) => widths.some((width) => Math.abs(width - required) <= 8))
}

function collectContrastSamples(audit: CodeVisualRenderAudit): RenderedContrastSample[] {
  return audit.viewports.flatMap((viewport) => viewport.contrastSamples ?? [])
}

function contrastPassRate(samples: RenderedContrastSample[]): number {
  if (samples.length === 0) return 0
  const passed = samples.filter((sample) => sample.ratio >= 4.5).length
  return passed / samples.length
}

function median(values: number[]): number | null {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return sorted[Math.floor(sorted.length / 2)]
}

function visionScores(audit: CodeVisualRenderAudit): RenderedVisionJudgement[] {
  return audit.viewports
    .map((viewport) => viewport.vision)
    .filter((vision): vision is RenderedVisionJudgement => Boolean(vision))
}

export function scoreRenderedVisualAudit(audit: CodeVisualRenderAudit): VisualFidelityReport {
  const viewports = audit.viewports
  const screenshots = viewports.filter(hasScreenshot)
  const contrastSamples = collectContrastSamples(audit)
  const pixelContrastSamples = contrastSamples.filter((sample) => sample.source === 'pixel')
  const minContrast = contrastSamples.length
    ? Math.min(...contrastSamples.map((sample) => sample.ratio))
    : 0
  const contrastRate = contrastPassRate(contrastSamples)
  const textMedian = median(viewports.map((viewport) => viewport.bodyTextLength)) ?? 0
  const textNodeMedian = median(viewports.map((viewport) => viewport.textNodeCount)) ?? 0
  const headingMedian = median(viewports.map((viewport) => viewport.headingCount)) ?? 0
  const mediaMedian = median(viewports.map((viewport) => viewport.mediaCount + (viewport.canvasPresent ? 1 : 0))) ?? 0
  const interactiveMedian = median(viewports.map((viewport) => viewport.interactiveCount)) ?? 0
  const cssVarMedian = median(viewports.map((viewport) => viewport.cssVarCount)) ?? 0
  const rhythmMedian = median(viewports.map((viewport) => viewport.verticalGapMedian ?? Number.NaN))
  const allRuntimeIssues = viewports.flatMap((viewport) => [
    ...viewport.consoleErrors,
    ...viewport.exceptions,
    ...viewport.failedRequests,
  ])
  const visions = visionScores(audit)
  const avgVision = visions.length
    ? visions.reduce((sum, vision) => sum + vision.score, 0) / visions.length
    : null
  const studioVerdicts = visions.filter((vision) => vision.verdict === 'studio').length

  const checks: VisualFidelityCheck[] = [
    check(
      'rendered_screenshots',
      `Screenshots reels captures (${screenshots.length}/${viewports.length})`,
      viewports.length > 0 && screenshots.length === viewports.length,
      14,
    ),
    check(
      'rendered_breakpoints',
      `Breakpoints 390/834/1440 couverts (${viewportWidths(audit).join(', ') || 'aucun'})`,
      hasRequiredBreakpoints(audit),
      12,
    ),
    check(
      'pixel_contrast_wcag',
      `Contraste WCAG mesure sur pixels (min ${minContrast.toFixed(2)}, pass ${Math.round(contrastRate * 100)}%)`,
      pixelContrastSamples.length >= 3 && minContrast >= 3 && contrastRate >= 0.8,
      18,
      pixelContrastSamples.length === 0 ? 'Aucun echantillon pixel fourni par le rendu.' : undefined,
    ),
    check(
      'rendered_no_runtime_errors',
      `Aucune erreur console/exception/requete (${allRuntimeIssues.length})`,
      allRuntimeIssues.length === 0,
      12,
      allRuntimeIssues.slice(0, 3).join(' | ') || undefined,
    ),
    check(
      'rendered_hierarchy',
      `Hierarchie visible (titres medians: ${headingMedian}, texte median: ${textNodeMedian})`,
      headingMedian >= 3 && textNodeMedian >= 12,
      10,
    ),
    check(
      'rendered_density',
      `Densite contenu rendue (body median ${Math.round(textMedian)} chars)`,
      textMedian >= 900,
      8,
    ),
    check(
      'rendered_media_depth',
      `Medias/canvas rendus (median ${mediaMedian})`,
      mediaMedian >= 2,
      8,
    ),
    check(
      'rendered_interactions',
      `Elements interactifs rendus (median ${interactiveMedian})`,
      interactiveMedian >= 3,
      6,
    ),
    check(
      'rendered_design_tokens',
      `Tokens CSS calcules (median ${cssVarMedian})`,
      cssVarMedian >= 4,
      5,
    ),
    check(
      'rendered_rhythm',
      `Rythme vertical median (${rhythmMedian === null ? 'n/a' : Math.round(rhythmMedian)}px)`,
      rhythmMedian !== null && rhythmMedian >= 12 && rhythmMedian <= 96,
      5,
    ),
    check(
      'vision_studio_verdict',
      `Verdict vision studio (${avgVision === null ? 'n/a' : Math.round(avgVision)}/100)`,
      avgVision === null ? true : avgVision >= 72 && studioVerdicts >= Math.ceil(visions.length / 2),
      12,
      visions.length === 0 ? 'Vision non fournie: score base sur rendu + metriques.' : undefined,
    ),
  ]

  const totalWeight = checks.reduce((sum, item) => sum + item.weight, 0)
  const earned = checks.filter((item) => item.passed).reduce((sum, item) => sum + item.weight, 0)
  const score = clampScore((earned / totalWeight) * 100)
  const floor = 75
  const failedChecks = checks.filter((item) => !item.passed).map((item) => item.id)
  const blocking = ['rendered_screenshots', 'rendered_breakpoints', 'pixel_contrast_wcag']
  const passed = score >= floor && !blocking.some((id) => failedChecks.includes(id))
  const summary = passed
    ? `Rendu reel acceptable (${score}/100) sur ${viewports.length} viewport(s).`
    : `Rendu reel insuffisant (${score}/100, seuil ${floor}) sur ${viewports.length} viewport(s).`

  return {
    score,
    passed,
    floor,
    checks,
    failedChecks,
    summary,
    source: 'render_audit',
    viewports: viewports.map((viewport) => viewport.viewport),
  }
}

export function buildRenderedVisualAuditCritique(report: VisualFidelityReport): string {
  if (report.passed) return ''
  const failed = new Set(report.failedChecks)
  return [
    '## ECHEC DU JUGE VISUEL RENDER-IN-THE-LOOP',
    `Score rendu: ${report.score}/100 (seuil ${report.floor}).`,
    report.viewports?.length ? `Viewports audites: ${report.viewports.join(', ')}.` : '',
    failed.has('rendered_screenshots') ? '- Le rendu reel n a pas produit tous les screenshots attendus.' : '',
    failed.has('rendered_breakpoints') ? '- Corrige le responsive sur les breakpoints 390, 834 et 1440 px.' : '',
    failed.has('pixel_contrast_wcag') ? '- Corrige le contraste mesure sur pixels: texte/fond doit atteindre WCAG AA (ratio 4.5:1 pour texte courant).' : '',
    failed.has('rendered_no_runtime_errors') ? '- Corrige les erreurs console, exceptions et requetes cassees visibles au rendu.' : '',
    failed.has('rendered_hierarchy') ? '- Renforce la hierarchie visuelle: titres, sous-titres, sections et zones d action clairement differencies.' : '',
    failed.has('rendered_density') ? '- Ajoute du contenu utile rendu a l ecran; evite les pages vides ou trop aeriennes.' : '',
    failed.has('rendered_media_depth') ? '- Ajoute des medias visibles, canvas, SVG ou images reelles liees au sujet.' : '',
    failed.has('rendered_interactions') ? '- Ajoute des controles et etats interactifs visibles.' : '',
    failed.has('rendered_design_tokens') ? '- Stabilise le systeme visuel avec tokens CSS et styles calcules coherents.' : '',
    failed.has('rendered_rhythm') ? '- Revois les espacements verticaux: ni empilement serre, ni vide excessif.' : '',
    failed.has('vision_studio_verdict') ? '- Le juge vision classe le rendu comme tutoriel/mixte: augmente finition, harmonie, densite et composition.' : '',
  ].filter(Boolean).join('\n')
}
