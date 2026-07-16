import type { CodeFile, CodeOrchestrationPhase } from '../services/codeOrchestrator.ts'
import type { CodeStreamEvent } from '../services/codeStreamEvents.ts'
import { appendCodeStreamEvents } from './codeStreamEventLog.ts'
import { computeEta } from './codeStreamProgress.ts'
import type { CodeStreamState } from './codeStreamTypes.ts'

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function mergeFile(files: CodeFile[], file: CodeFile) {
  const normalized = normalizePath(file.name)
  const index = files.findIndex((candidate) => normalizePath(candidate.name) === normalized)
  if (index < 0) return [...files, file]
  const next = files.slice()
  next[index] = file
  return next
}

export function phaseFromRemoteEventPhase(phase: CodeOrchestrationPhase): CodeStreamState['phase'] {
  if (phase === 'research') return 'research'
  if (phase === 'validation' || phase === 'correction' || phase === 'dev_server') return 'validation'
  if (phase === 'generation') return 'streaming'
  if (phase === 'done') return 'done'
  if (phase === 'error') return 'error'
  return 'planning'
}

export function phaseFromRemoteCodeStreamEvent(event: CodeStreamEvent): CodeStreamState['phase'] {
  if (event.kind === 'phase') return phaseFromRemoteEventPhase(event.phase)
  if (event.kind === 'file.written') return 'streaming'
  if (event.kind === 'test.result' || event.kind === 'visual.score' || event.kind === 'correction') return 'validation'
  if (event.kind === 'done') return 'done'
  return 'error'
}

export function applyRemoteCodeStreamEvent(
  state: CodeStreamState,
  event: CodeStreamEvent,
  now = Date.now(),
): Partial<CodeStreamState> {
  const events = appendCodeStreamEvents(state.events, [event])

  if (event.kind === 'phase') {
    const progressPct = Math.max(state.progressPct, event.progress)
    const { remaining, total } = computeEta(state.genStartedAt, progressPct, state.etaSecondsRemaining)
    return {
      events,
      phase: phaseFromRemoteEventPhase(event.phase),
      phaseMessage: event.message,
      progressPct,
      etaSecondsRemaining: remaining,
      etaTotalSeconds: total,
    }
  }

  if (event.kind === 'file.written') {
    const files = typeof event.content === 'string'
      ? mergeFile(state.files, { name: event.path, language: event.language || 'text', content: event.content })
      : state.files
    return {
      events,
      files,
      phase: 'streaming',
      phaseMessage: `Fichier écrit: ${event.path}`,
      progressPct: Math.max(state.progressPct, 45),
    }
  }

  if (event.kind === 'test.result') {
    return {
      events,
      phase: 'validation',
      phaseMessage: event.summary,
      finalScore: event.score,
      progressPct: Math.max(state.progressPct, 85),
    }
  }

  if (event.kind === 'visual.score') {
    return {
      events,
      phase: 'validation',
      phaseMessage: event.summary,
      finalScore: event.score,
      progressPct: Math.max(state.progressPct, 88),
    }
  }

  if (event.kind === 'correction') {
    return {
      events,
      phase: 'validation',
      phaseMessage: `Correction ${event.attempt}: ${event.strategy}`,
      finalScore: event.score,
      totalAttempts: event.attempt,
      progressPct: Math.max(state.progressPct, 90),
    }
  }

  if (event.kind === 'done') {
    return {
      events,
      streaming: false,
      phase: 'done',
      phaseMessage: '',
      progressPct: 100,
      etaSecondsRemaining: 0,
      etaTotalSeconds: state.etaTotalSeconds,
      finalScore: event.finalScore,
      totalAttempts: event.totalAttempts,
      notes: event.notes,
      lastCompletedAt: now,
    }
  }

  return {
    events,
    error: event.message,
    streaming: false,
    phase: 'error',
    phaseMessage: '',
    errorDialog: {
      title: 'Flux Code interrompu',
      message: event.message,
      suggestion: event.recoverable ? 'Vérifie le bridge et relance la génération.' : undefined,
    },
  }
}
