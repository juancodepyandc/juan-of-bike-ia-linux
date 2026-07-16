import { getBridgeUrl } from '../utils/runtime.ts'
import {
  buildCodeStreamVisualScoreEvent,
  type CodeStreamEventMeta,
  type CodeStreamVisualScoreEvent,
} from './codeStreamEvents.ts'
import {
  buildRenderedVisualAuditCritique,
  CODE_VISUAL_RENDER_AUDIT_SCHEMA,
  scoreRenderedVisualAudit,
  type CodeVisualRenderAudit,
} from './codeVisualRenderAudit.ts'
import type { VisualFidelityReport } from './codeVisualFidelity.ts'

export type BlendedFinalScore = {
  score: number
  visualScore: number
  belowThreshold: boolean
  hint: string | null
}

/**
 * WS9: fait COMPTER le juge visuel dans le score final livre. L audit rendu
 * (screenshot multi-viewport + metriques WCAG + vision) etait purement
 * decoratif (setDesignReport) et n alimentait pas le finalScore. Ici il pondere
 * le score du modele: un rendu visuellement insuffisant (report.passed=false)
 * plafonne le score livre et marque belowThreshold pour recommander/declencher
 * une regeneration ciblee avec la critique de rendu en indice.
 */
export function blendRenderedVisualIntoFinalScore(
  modelScore: number,
  report: VisualFidelityReport,
): BlendedFinalScore {
  const clampedModel = Math.max(0, Math.min(100, Math.round(modelScore)))
  const visualScore = Math.max(0, Math.min(100, Math.round(report.score)))
  // Correctness (modele) dominante, apparence (visuel) significative.
  let blended = Math.round(clampedModel * 0.65 + visualScore * 0.35)
  // Un rendu qui echoue son seuil ne peut pas etre livre comme "excellent".
  if (!report.passed) blended = Math.min(blended, Math.min(clampedModel, 84))
  const belowThreshold = !report.passed || visualScore < (report.floor || 70)
  return {
    score: Math.max(0, Math.min(100, blended)),
    visualScore,
    belowThreshold,
    hint: belowThreshold ? buildRenderedVisualAuditCritique(report) : null,
  }
}

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeVisualAuditRequest = {
  url: string
  waitMs?: number
  includeVision?: boolean
  visionModel?: string
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
  eventMeta?: CodeStreamEventMeta
}

export type CodeVisualAuditResult = {
  audit: CodeVisualRenderAudit
  report: VisualFidelityReport
  event?: CodeStreamVisualScoreEvent
}

function isAudit(value: unknown): value is CodeVisualRenderAudit {
  if (!value || typeof value !== 'object') return false
  const audit = value as Record<string, unknown>
  return audit.schemaVersion === CODE_VISUAL_RENDER_AUDIT_SCHEMA
    && Array.isArray(audit.viewports)
}

export function buildVisualScoreEventFromReport(
  report: VisualFidelityReport,
  meta: CodeStreamEventMeta,
): CodeStreamVisualScoreEvent {
  const viewports = report.viewports ?? []
  return buildCodeStreamVisualScoreEvent({
    ...meta,
    score: report.score,
    viewport: viewports.join(', ') || report.source || 'visual',
    summary: report.summary,
    source: report.source,
    viewports,
    failedChecks: report.failedChecks,
  })
}

export async function runCodeVisualRenderAudit({
  url,
  waitMs = 2500,
  includeVision = false,
  visionModel,
  bridgeUrl = getBridgeUrl(),
  fetchImpl = globalThis.fetch.bind(globalThis),
  signal,
  eventMeta,
}: CodeVisualAuditRequest): Promise<CodeVisualAuditResult> {
  if (!url.trim()) throw new Error('URL de rendu requise')

  const response = await fetchImpl(`${bridgeUrl}/api/code/visual-audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url,
      waitMs,
      vision: includeVision,
      visionModel,
    }),
    signal,
  })

  const payload = await response.json().catch(() => null) as null | {
    ok?: boolean
    audit?: unknown
    error?: string
  }
  if (!response.ok || !payload?.ok || !isAudit(payload.audit)) {
    const error = payload?.error || `Audit visuel HTTP ${response.status}`
    throw new Error(error)
  }

  const audit = payload.audit
  const report = scoreRenderedVisualAudit(audit)
  return {
    audit,
    report,
    ...(eventMeta ? { event: buildVisualScoreEventFromReport(report, eventMeta) } : {}),
  }
}
