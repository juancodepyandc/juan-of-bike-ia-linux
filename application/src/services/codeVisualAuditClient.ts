import { getBridgeUrl } from '../utils/runtime.ts'
import {
  buildCodeStreamVisualScoreEvent,
  type CodeStreamEventMeta,
  type CodeStreamVisualScoreEvent,
} from './codeStreamEvents.ts'
import {
  CODE_VISUAL_RENDER_AUDIT_SCHEMA,
  scoreRenderedVisualAudit,
  type CodeVisualRenderAudit,
} from './codeVisualRenderAudit.ts'
import type { VisualFidelityReport } from './codeVisualFidelity.ts'

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
