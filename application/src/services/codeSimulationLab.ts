import { getBridgeUrl } from '../utils/runtime.ts'

export const CODE_SIMULATION_LAB_SCHEMA = 'aurora.code.simulation-lab/1'

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeSimulationStageStatus =
  | 'executed'
  | 'detected'
  | 'degraded'
  | 'unavailable'
  | 'deferred'

export type CodeSimulationStage = {
  id: string
  label: string
  family: 'web' | 'mobile_real' | 'embedded' | 'os_boot' | 'console' | string
  status: CodeSimulationStageStatus
  realExecution: boolean
  browser?: string
  viewport?: string
  width?: number
  height?: number
  dpr?: number
  touch?: boolean
  userAgent?: string
  throttling?: { cpu?: number; network?: unknown }
  screenshotPath?: string
  bodyTextLength?: number
  headingCount?: number
  mediaCount?: number
  interactiveCount?: number
  consoleErrors?: string[]
  exceptions?: string[]
  failedRequests?: string[]
  performanceMetrics?: Record<string, number>
  toolPath?: string
  artifactPath?: string
  deviceSerial?: string
  deviceProfile?: string
  interactionExecuted?: boolean
  interactionVerified?: boolean
  durationMs?: number
  detail?: string
  error?: string
}

export type CodeSimulationLabReport = {
  schemaVersion: typeof CODE_SIMULATION_LAB_SCHEMA
  url: string
  createdAt?: number
  outDir?: string
  stages: CodeSimulationStage[]
}

export type CodeSimulationLabSummary = {
  executed: number
  degraded: number
  unavailable: number
  deferred: number
  realExecutions: number
  webBrowsers: string[]
  summary: string
}

export type CodeSimulationLabRequest = {
  url: string
  waitMs?: number
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
}

function isStage(value: unknown): value is CodeSimulationStage {
  if (!value || typeof value !== 'object') return false
  const stage = value as Record<string, unknown>
  const statuses: CodeSimulationStageStatus[] = ['executed', 'detected', 'degraded', 'unavailable', 'deferred']
  return typeof stage.id === 'string'
    && typeof stage.label === 'string'
    && typeof stage.family === 'string'
    && statuses.includes(stage.status as CodeSimulationStageStatus)
    && typeof stage.realExecution === 'boolean'
    && (stage.status !== 'executed' || stage.realExecution === true)
    && (stage.realExecution !== true || stage.status === 'executed')
}

export function isCodeSimulationLabReport(value: unknown): value is CodeSimulationLabReport {
  if (!value || typeof value !== 'object') return false
  const report = value as Record<string, unknown>
  return report.schemaVersion === CODE_SIMULATION_LAB_SCHEMA
    && typeof report.url === 'string'
    && Array.isArray(report.stages)
    && report.stages.every(isStage)
}

export function summarizeCodeSimulationLab(report: CodeSimulationLabReport): CodeSimulationLabSummary {
  const executedStages = report.stages.filter((stage) => stage.status === 'executed')
  const degraded = report.stages.filter((stage) => stage.status === 'degraded' || stage.status === 'detected').length
  const unavailable = report.stages.filter((stage) => stage.status === 'unavailable').length
  const deferred = report.stages.filter((stage) => stage.status === 'deferred').length
  const realExecutions = report.stages.filter((stage) => stage.realExecution).length
  const webBrowsers = Array.from(new Set(
    executedStages
      .filter((stage) => stage.family === 'web')
      .map((stage) => stage.browser || stage.label)
      .filter(Boolean),
  ))

  return {
    executed: executedStages.length,
    degraded,
    unavailable,
    deferred,
    realExecutions,
    webBrowsers,
    summary: [
      `${executedStages.length} scenario(s) executes`,
      `${realExecutions} execution(s) reelle(s)`,
      webBrowsers.length ? `navigateurs: ${webBrowsers.join(', ')}` : 'aucun navigateur execute',
      unavailable ? `${unavailable} environnement(s) indisponible(s)` : 'aucun indisponible',
    ].join(' · '),
  }
}

export async function runCodeSimulationLab({
  url,
  waitMs = 1800,
  bridgeUrl = getBridgeUrl(),
  fetchImpl = globalThis.fetch.bind(globalThis),
  signal,
}: CodeSimulationLabRequest): Promise<CodeSimulationLabReport> {
  if (!url.trim()) throw new Error('URL de simulation requise')

  const response = await fetchImpl(`${bridgeUrl}/api/code/simulation-lab`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, waitMs }),
    signal,
  })
  const payload = await response.json().catch(() => null) as null | {
    ok?: boolean
    report?: unknown
    error?: string
  }
  if (!response.ok || !payload?.ok || !isCodeSimulationLabReport(payload.report)) {
    throw new Error(payload?.error || `Labo simulation HTTP ${response.status}`)
  }
  return payload.report
}
