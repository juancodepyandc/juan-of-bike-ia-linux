import type { CorrectionPass } from './codeAutoCorrection.ts'
import type { CodeFile, CodeOrchestrationPhase } from './codeOrchestrator.ts'
import type { CodeSandboxResult } from './codeSandboxTypes.ts'

export const CODE_STREAM_EVENT_SCHEMA = 'aurora.code.stream/1' as const

export type CodeStreamEventKind =
  | 'phase'
  | 'file.written'
  | 'test.result'
  | 'visual.score'
  | 'correction'
  | 'done'
  | 'error'

export type CodeStreamEventMeta = {
  runId: number
  sequence: number
  timestamp: number
}

type CodeStreamEventBase<K extends CodeStreamEventKind> = CodeStreamEventMeta & {
  schema: typeof CODE_STREAM_EVENT_SCHEMA
  kind: K
}

export type CodeStreamPhaseEvent = CodeStreamEventBase<'phase'> & {
  phase: CodeOrchestrationPhase
  message: string
  progress: number
}

export type CodeStreamFileWrittenEvent = CodeStreamEventBase<'file.written'> & {
  path: string
  language: string
  bytes: number
  content?: string
}

export type CodeStreamTestResultEvent = CodeStreamEventBase<'test.result'> & {
  ok: boolean
  score: number
  summary: string
  detectedLanguage: string
  stepsPassed: number
  stepsTotal: number
  failedLabels: string[]
}

export type CodeStreamVisualScoreEvent = CodeStreamEventBase<'visual.score'> & {
  score: number
  viewport: string
  summary: string
  source?: 'source_static' | 'render_audit'
  viewports?: string[]
  failedChecks?: string[]
}

export type CodeStreamCorrectionEvent = CodeStreamEventBase<'correction'> & {
  attempt: number
  score: number
  strategy: string
  resolved: boolean
  errors: string[]
}

export type CodeStreamDoneEvent = CodeStreamEventBase<'done'> & {
  filesCount: number
  finalScore: number
  totalAttempts: number
  notes: string
}

export type CodeStreamErrorEvent = CodeStreamEventBase<'error'> & {
  message: string
  recoverable: boolean
}

export type CodeStreamEvent =
  | CodeStreamPhaseEvent
  | CodeStreamFileWrittenEvent
  | CodeStreamTestResultEvent
  | CodeStreamVisualScoreEvent
  | CodeStreamCorrectionEvent
  | CodeStreamDoneEvent
  | CodeStreamErrorEvent

const CODE_STREAM_PHASES = new Set<CodeOrchestrationPhase>([
  'intent',
  'preflight',
  'planning',
  'generation',
  'validation',
  'correction',
  'research',
  'dev_server',
  'done',
  'error',
])

function clampProgress(progress: number) {
  if (!Number.isFinite(progress)) return 0
  return Math.max(0, Math.min(100, Math.round(progress)))
}

function utf8ByteLength(text: string) {
  return new TextEncoder().encode(text).length
}

function normalizeEventPath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

export function codeStreamPhaseFromDetail(detail: string, progress: number): CodeOrchestrationPhase {
  const text = detail.toLowerCase()
  if (/marque|brand|reference|inspiration|recherche|research|meilleures pratiques/.test(text)) return 'research'
  if (/validation|sandbox|test|verif|v[ée]rif/.test(text)) return 'validation'
  if (/correction|patch|repair|r[ée]paration/.test(text)) return 'correction'
  if (/dev server|serveur/.test(text)) return 'dev_server'
  if (/plan|architecture|preflight|dossier|contexte|analyse/.test(text)) return 'planning'
  if (progress >= 30 && progress < 90) return 'generation'
  if (progress >= 90) return 'validation'
  return 'planning'
}

export function buildCodeStreamPhaseEvent(args: CodeStreamEventMeta & {
  phase?: CodeOrchestrationPhase
  message: string
  progress: number
}): CodeStreamPhaseEvent {
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'phase',
    runId: args.runId,
    sequence: args.sequence,
    timestamp: args.timestamp,
    phase: args.phase ?? codeStreamPhaseFromDetail(args.message, args.progress),
    message: args.message,
    progress: clampProgress(args.progress),
  }
}

export function buildCodeStreamFileWrittenEvents(args: {
  files: CodeFile[]
  previousFiles: CodeFile[]
  nextMeta: () => CodeStreamEventMeta
  includeContent?: boolean
}): CodeStreamFileWrittenEvent[] {
  const previous = new Map(args.previousFiles.map((file) => [normalizeEventPath(file.name), file.content]))
  const emitted = new Set<string>()
  const events: CodeStreamFileWrittenEvent[] = []

  for (const file of args.files) {
    const normalized = normalizeEventPath(file.name)
    if (!normalized || emitted.has(normalized)) continue
    emitted.add(normalized)
    if (previous.get(normalized) === file.content) continue

    events.push({
      schema: CODE_STREAM_EVENT_SCHEMA,
      kind: 'file.written',
      ...args.nextMeta(),
      path: file.name,
      language: file.language || 'text',
      bytes: utf8ByteLength(file.content),
      ...(args.includeContent ? { content: file.content } : {}),
    })
  }

  return events
}

export function buildCodeStreamTestResultEvent(
  result: CodeSandboxResult,
  meta: CodeStreamEventMeta,
): CodeStreamTestResultEvent {
  const stepsTotal = result.steps.length
  const stepsPassed = result.steps.filter((step) => step.ok).length
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'test.result',
    ...meta,
    ok: result.ok,
    score: stepsTotal > 0 ? Math.round((stepsPassed / stepsTotal) * 100) : (result.ok ? 100 : 0),
    summary: result.summary,
    detectedLanguage: result.detectedLanguage,
    stepsPassed,
    stepsTotal,
    failedLabels: result.steps.filter((step) => !step.ok).map((step) => step.label).slice(0, 12),
  }
}

export function buildCodeStreamCorrectionEvent(args: CodeStreamEventMeta & {
  pass: CorrectionPass | null
  attempt: number
  score: number
}): CodeStreamCorrectionEvent {
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'correction',
    runId: args.runId,
    sequence: args.sequence,
    timestamp: args.timestamp,
    attempt: args.attempt,
    score: clampProgress(args.score),
    strategy: args.pass?.strategy ?? 'unknown',
    resolved: args.pass?.resolved ?? false,
    errors: (args.pass?.errors ?? []).slice(0, 8),
  }
}

export function buildCodeStreamVisualScoreEvent(args: CodeStreamEventMeta & {
  score: number
  viewport: string
  summary: string
  source?: CodeStreamVisualScoreEvent['source']
  viewports?: string[]
  failedChecks?: string[]
}): CodeStreamVisualScoreEvent {
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'visual.score',
    runId: args.runId,
    sequence: args.sequence,
    timestamp: args.timestamp,
    score: clampProgress(args.score),
    viewport: args.viewport,
    summary: args.summary,
    ...(args.source ? { source: args.source } : {}),
    ...(args.viewports ? { viewports: args.viewports.slice(0, 8) } : {}),
    ...(args.failedChecks ? { failedChecks: args.failedChecks.slice(0, 12) } : {}),
  }
}

export function buildCodeStreamDoneEvent(args: CodeStreamEventMeta & {
  files: CodeFile[]
  finalScore: number
  totalAttempts: number
  notes: string
}): CodeStreamDoneEvent {
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'done',
    runId: args.runId,
    sequence: args.sequence,
    timestamp: args.timestamp,
    filesCount: args.files.length,
    finalScore: clampProgress(args.finalScore),
    totalAttempts: Math.max(0, Math.round(args.totalAttempts)),
    notes: args.notes.slice(0, 2_000),
  }
}

export function buildCodeStreamErrorEvent(args: CodeStreamEventMeta & {
  message: string
  recoverable?: boolean
}): CodeStreamErrorEvent {
  return {
    schema: CODE_STREAM_EVENT_SCHEMA,
    kind: 'error',
    runId: args.runId,
    sequence: args.sequence,
    timestamp: args.timestamp,
    message: args.message.slice(0, 2_000),
    recoverable: args.recoverable ?? true,
  }
}

export function serializeCodeStreamEvent(event: CodeStreamEvent) {
  return `${JSON.stringify(event)}\n`
}

export function parseCodeStreamEventLine(line: string): CodeStreamEvent | null {
  const trimmed = line.trim()
  if (!trimmed) return null
  try {
    const parsed = JSON.parse(trimmed)
    return isCodeStreamEvent(parsed) ? parsed : null
  } catch {
    return null
  }
}

function hasValidMeta(value: Record<string, unknown>) {
  return value.schema === CODE_STREAM_EVENT_SCHEMA
    && Number.isInteger(value.runId)
    && Number.isInteger(value.sequence)
    && typeof value.timestamp === 'number'
    && typeof value.kind === 'string'
}

function isNumberInRange(value: unknown, min: number, max: number) {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
}

function isStringArray(value: unknown) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

export function isCodeStreamEvent(value: unknown): value is CodeStreamEvent {
  if (!value || typeof value !== 'object') return false
  const event = value as Record<string, unknown>
  if (!hasValidMeta(event)) return false

  switch (event.kind) {
    case 'phase':
      return typeof event.message === 'string'
        && typeof event.phase === 'string'
        && CODE_STREAM_PHASES.has(event.phase as CodeOrchestrationPhase)
        && isNumberInRange(event.progress, 0, 100)
    case 'file.written':
      return typeof event.path === 'string'
        && event.path.length > 0
        && typeof event.language === 'string'
        && isNumberInRange(event.bytes, 0, Number.MAX_SAFE_INTEGER)
        && (event.content === undefined || typeof event.content === 'string')
    case 'test.result':
      return typeof event.ok === 'boolean'
        && isNumberInRange(event.score, 0, 100)
        && typeof event.summary === 'string'
        && typeof event.detectedLanguage === 'string'
        && Number.isInteger(event.stepsPassed)
        && Number.isInteger(event.stepsTotal)
        && isStringArray(event.failedLabels)
    case 'visual.score':
      return isNumberInRange(event.score, 0, 100)
        && typeof event.viewport === 'string'
        && typeof event.summary === 'string'
        && (event.source === undefined || event.source === 'source_static' || event.source === 'render_audit')
        && (event.viewports === undefined || isStringArray(event.viewports))
        && (event.failedChecks === undefined || isStringArray(event.failedChecks))
    case 'correction':
      return Number.isInteger(event.attempt)
        && isNumberInRange(event.score, 0, 100)
        && typeof event.strategy === 'string'
        && typeof event.resolved === 'boolean'
        && isStringArray(event.errors)
    case 'done':
      return Number.isInteger(event.filesCount)
        && isNumberInRange(event.finalScore, 0, 100)
        && Number.isInteger(event.totalAttempts)
        && typeof event.notes === 'string'
    case 'error':
      return typeof event.message === 'string'
        && typeof event.recoverable === 'boolean'
    default:
      return false
  }
}
