import { getBridgeUrl } from '../utils/runtime.ts'
import type { CorrectionPass, ErrorCategory } from './codeAutoCorrection.ts'
import type { CodeIntent } from './codeIntent.ts'

export const CODE_TOOLING_EVAL_SCHEMA = 'aurora.code.tooling-eval/1'

export const CODE_REACT_TOOL_NAMES = [
  'run_shell',
  'run_tests',
  'search_pkg',
  'install_dep',
  'add_model',
] as const

export type CodeReactToolName = typeof CODE_REACT_TOOL_NAMES[number]
export type CodeToolRegistry = 'npm' | 'pypi' | 'crates' | 'maven'
export type CodeToolDecision = 'kept' | 'removed' | 'unavailable' | 'blocked'

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeToolCandidateRequest = {
  id: string
  registry: CodeToolRegistry
  packageName: string
  version?: string
  scenario?: 'slugify_gain' | 'slugify_no_gain'
  reason: string
  minGain?: number
}

export type CodeToolCandidateReport = {
  id: string
  registry: CodeToolRegistry
  packageName: string
  version: string | null
  venvPath: string | null
  baselineScore: number
  toolScore: number
  improvement: number
  decision: CodeToolDecision
  reason: string
  removed: boolean
  installCommand?: string
  actions: CodeReactToolName[]
  stdoutTail?: string
  stderrTail?: string
}

export type CodeToolingEvalReport = {
  schemaVersion: typeof CODE_TOOLING_EVAL_SCHEMA
  createdAt: number
  venvRoot: string
  appVenvPath: string
  appVenvInstallForbidden: boolean
  candidates: CodeToolCandidateReport[]
}

export type CodeToolingEvalRequest = {
  candidates: CodeToolCandidateRequest[]
  timeoutMs?: number
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
}

export const CODE_TOOLING_NETWORK_ALLOWLIST: Record<CodeToolRegistry, string> = {
  npm: 'https://registry.npmjs.org/',
  pypi: 'https://pypi.org/pypi/',
  crates: 'https://crates.io/api/v1/crates/',
  maven: 'https://search.maven.org/solrsearch/select',
}

const APPROVED_PYPI_TOOLS = new Set(['python-slugify'])

function encodePkg(name: string): string {
  return encodeURIComponent(name.trim())
}

export function buildToolRegistryLookupUrl(registry: CodeToolRegistry, packageName: string): string {
  const normalized = packageName.trim()
  if (!normalized) throw new Error('Nom de package requis')
  if (registry === 'npm') return `${CODE_TOOLING_NETWORK_ALLOWLIST.npm}${encodePkg(normalized)}`
  if (registry === 'pypi') return `${CODE_TOOLING_NETWORK_ALLOWLIST.pypi}${encodePkg(normalized)}/json`
  if (registry === 'crates') return `${CODE_TOOLING_NETWORK_ALLOWLIST.crates}${encodePkg(normalized)}`

  const [group, artifact] = normalized.split(':')
  if (!group || !artifact) throw new Error('Package Maven attendu au format group:artifact')
  const query = encodeURIComponent(`g:"${group}" AND a:"${artifact}"`)
  return `${CODE_TOOLING_NETWORK_ALLOWLIST.maven}?q=${query}&rows=1&wt=json`
}

export function parseRegistryLatestVersion(registry: CodeToolRegistry, payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const data = payload as Record<string, any>
  if (registry === 'npm') return typeof data['dist-tags']?.latest === 'string' ? data['dist-tags'].latest : null
  if (registry === 'pypi') return typeof data.info?.version === 'string' ? data.info.version : null
  if (registry === 'crates') return typeof data.crate?.max_version === 'string' ? data.crate.max_version : null
  const docs = data.response?.docs
  if (Array.isArray(docs) && docs[0]) {
    return typeof docs[0].latestVersion === 'string'
      ? docs[0].latestVersion
      : typeof docs[0].v === 'string' ? docs[0].v : null
  }
  return null
}

export async function resolveToolPackageVersion({
  registry,
  packageName,
  fetchImpl = globalThis.fetch.bind(globalThis),
}: {
  registry: CodeToolRegistry
  packageName: string
  fetchImpl?: FetchLike
}): Promise<string | null> {
  const response = await fetchImpl(buildToolRegistryLookupUrl(registry, packageName))
  if (!response.ok) return null
  return parseRegistryLatestVersion(registry, await response.json().catch(() => null))
}

export function isCodeToolingEvalReport(value: unknown): value is CodeToolingEvalReport {
  if (!value || typeof value !== 'object') return false
  const report = value as Record<string, unknown>
  return report.schemaVersion === CODE_TOOLING_EVAL_SCHEMA
    && typeof report.createdAt === 'number'
    && typeof report.venvRoot === 'string'
    && typeof report.appVenvPath === 'string'
    && report.appVenvInstallForbidden === true
    && Array.isArray(report.candidates)
}

export function summarizeToolingEval(report: CodeToolingEvalReport): string {
  const kept = report.candidates.filter((candidate) => candidate.decision === 'kept')
  const removed = report.candidates.filter((candidate) => candidate.decision === 'removed')
  const unavailable = report.candidates.filter((candidate) => candidate.decision === 'unavailable')
  return [
    `${kept.length} outil(s) conserve(s)`,
    `${removed.length} outil(s) retire(s)`,
    unavailable.length ? `${unavailable.length} indisponible(s)` : 'aucun indisponible',
    `venv racine: ${report.venvRoot}`,
  ].join(' · ')
}

export function formatToolingReportForCorrection(report: CodeToolingEvalReport): string {
  const lines = [
    '## AUTO-OUTILLAGE WS14',
    summarizeToolingEval(report),
    `Installation interdite dans application/.venv: ${report.appVenvInstallForbidden ? 'oui' : 'non'}`,
  ]
  for (const candidate of report.candidates) {
    lines.push(
      `- ${candidate.packageName}@${candidate.version ?? 'unknown'}: ${candidate.decision}, `
      + `A/B ${candidate.baselineScore}->${candidate.toolScore} `
      + `(${candidate.improvement >= 0 ? '+' : ''}${candidate.improvement}). ${candidate.reason}`,
    )
  }
  return lines.join('\n')
}

export function detectToolingPlateau(correctionLog: CorrectionPass[]): boolean {
  const recent = correctionLog.slice(-3)
  if (recent.length < 3 || recent.some((pass) => pass.resolved)) return false
  const scores = recent.map((pass) => pass.score)
  return Math.max(...scores) - Math.min(...scores) <= 4
}

export function selectToolingCandidateForCorrection({
  errorCategories,
  failingOutputs,
  intent,
}: {
  errorCategories: ErrorCategory[]
  failingOutputs: string[]
  intent: CodeIntent
}): CodeToolCandidateRequest | null {
  const output = failingOutputs.join('\n')
  const pythonLike = intent.languages.includes('python')
    || intent.projectType === 'cli_python'
    || /ModuleNotFoundError|No module named|pip|pytest|python/i.test(output)
  const slugNeed = /slugify|slug|unicode|accent|transliteration|normalization/i.test(output)
  const dependencyNeed = errorCategories.some((category) =>
    category === 'import_missing' || category === 'dependency_missing' || category === 'test_failure')

  if (pythonLike && dependencyNeed && (slugNeed || /No module named ['"]slugify['"]/i.test(output))) {
    return {
      id: 'pypi-python-slugify',
      registry: 'pypi',
      packageName: 'python-slugify',
      version: '8.0.4',
      scenario: 'slugify_gain',
      reason: 'Correction bloquee sur normalisation/slug Unicode; evaluation A/B en venv isole.',
      minGain: 5,
    }
  }

  return null
}

export function assertToolingCandidateAllowed(candidate: CodeToolCandidateRequest): void {
  if (candidate.registry !== 'pypi' || !APPROVED_PYPI_TOOLS.has(candidate.packageName)) {
    throw new Error(`Outil non approuve pour auto-outillage Code: ${candidate.registry}:${candidate.packageName}`)
  }
}

export async function runCodeToolingEval({
  candidates,
  timeoutMs = 90_000,
  bridgeUrl = getBridgeUrl(),
  fetchImpl = globalThis.fetch.bind(globalThis),
  signal,
}: CodeToolingEvalRequest): Promise<CodeToolingEvalReport> {
  if (candidates.length === 0) throw new Error('Aucun outil candidat a evaluer')
  for (const candidate of candidates) assertToolingCandidateAllowed(candidate)

  const response = await fetchImpl(`${bridgeUrl}/api/code/tooling-eval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidates, timeoutMs }),
    signal,
  })
  const payload = await response.json().catch(() => null) as null | {
    ok?: boolean
    report?: unknown
    error?: string
  }
  if (!response.ok || !payload?.ok || !isCodeToolingEvalReport(payload.report)) {
    throw new Error(payload?.error || `Auto-outillage HTTP ${response.status}`)
  }
  return payload.report
}

export async function evaluateAutoToolingForCorrection({
  correctionLog,
  errorCategories,
  failingOutputs,
  intent,
  signal,
}: {
  correctionLog: CorrectionPass[]
  errorCategories: ErrorCategory[]
  failingOutputs: string[]
  intent: CodeIntent
  signal?: AbortSignal
}): Promise<CodeToolingEvalReport | null> {
  if (!detectToolingPlateau(correctionLog)) return null
  const candidate = selectToolingCandidateForCorrection({ errorCategories, failingOutputs, intent })
  if (!candidate) return null

  try {
    return await runCodeToolingEval({ candidates: [candidate], signal })
  } catch {
    return null
  }
}
