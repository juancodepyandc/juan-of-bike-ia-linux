import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import type { CodeSandboxResult } from '../services/codeSandboxTypes.ts'
import {
  buildCodeStreamCorrectionEvent,
  buildCodeStreamDoneEvent,
  buildCodeStreamErrorEvent,
  buildCodeStreamFileWrittenEvents,
  buildCodeStreamPhaseEvent,
  buildCodeStreamTestResultEvent,
  type CodeStreamEvent,
  type CodeStreamEventMeta,
} from '../services/codeStreamEvents.ts'

const MAX_CODE_STREAM_EVENTS = 240

export function createCodeStreamEventMetaFactory(runId: number) {
  let sequence = 0
  return (): CodeStreamEventMeta => ({
    runId,
    sequence: ++sequence,
    timestamp: Date.now(),
  })
}

export function appendCodeStreamEvents(current: CodeStreamEvent[], next: CodeStreamEvent[]) {
  if (next.length === 0) return current
  return [...current, ...next].slice(-MAX_CODE_STREAM_EVENTS)
}

export function makeCodeStreamPhaseEvent(
  nextMeta: () => CodeStreamEventMeta,
  message: string,
  progress: number,
) {
  return buildCodeStreamPhaseEvent({ ...nextMeta(), message, progress })
}

export function makeInitialCodeStreamPhaseEvent(
  nextMeta: () => CodeStreamEventMeta,
  message: string,
) {
  return buildCodeStreamPhaseEvent({ ...nextMeta(), phase: 'planning', message, progress: 1 })
}

export function makeCodeStreamFileEvents(
  nextMeta: () => CodeStreamEventMeta,
  files: CodeFile[],
  previousFiles: CodeFile[],
) {
  return buildCodeStreamFileWrittenEvents({ files, previousFiles, nextMeta })
}

export function makeCodeStreamValidationEvent(
  nextMeta: () => CodeStreamEventMeta,
  result: CodeSandboxResult,
) {
  return buildCodeStreamTestResultEvent(result, nextMeta())
}

export function makeCodeStreamCorrectionEvent(
  nextMeta: () => CodeStreamEventMeta,
  log: CorrectionPass[],
  attempt: number,
  score: number,
) {
  return buildCodeStreamCorrectionEvent({
    ...nextMeta(),
    pass: log.length > 0 ? log[log.length - 1] : null,
    attempt,
    score,
  })
}

export function makeCodeStreamDoneEvent(
  nextMeta: () => CodeStreamEventMeta,
  files: CodeFile[],
  finalScore: number,
  totalAttempts: number,
  notes: string,
) {
  return buildCodeStreamDoneEvent({ ...nextMeta(), files, finalScore, totalAttempts, notes })
}

export function makeCodeStreamErrorEvent(
  nextMeta: () => CodeStreamEventMeta,
  message: string,
  recoverable = true,
) {
  return buildCodeStreamErrorEvent({ ...nextMeta(), message, recoverable })
}
