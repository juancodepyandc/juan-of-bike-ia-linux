import type { CodeSessionSnapshot, CodeStreamState } from './codeStreamTypes.ts'

export function emptySessionSnapshot(): CodeSessionSnapshot {
  return {
    draft: '',
    streamOutput: '',
    error: null,
    lastCompletedAt: null,
    phase: 'idle',
    phaseMessage: '',
    modelUsed: null,
    brandPrimary: null,
    files: [],
    notes: '',
    messages: [],
    followUpKind: null,
    finalScore: 0,
    totalAttempts: 0,
    events: [],
    progressPct: 0,
    genStartedAt: null,
    etaSecondsRemaining: null,
    etaTotalSeconds: null,
    narration: '',
    narrationLog: [],
    workMode: 'online',
    repoPath: null,
    repoLabel: null,
    repoLoaded: false,
    repoScan: null,
    repoMessage: null,
    repoWriteResult: null,
  }
}

export function captureSessionSnapshot(state: CodeStreamState): CodeSessionSnapshot {
  const settledPhase: CodeStreamState['phase'] = state.streaming
    ? (state.files.length > 0 || state.streamOutput ? 'done' : 'idle')
    : state.phase
  return {
    draft: state.draft,
    streamOutput: state.streamOutput,
    error: state.error,
    lastCompletedAt: state.lastCompletedAt,
    phase: settledPhase,
    phaseMessage: state.streaming ? '' : state.phaseMessage,
    modelUsed: state.modelUsed,
    brandPrimary: state.brandPrimary,
    files: state.files,
    notes: state.notes,
    messages: state.messages,
    followUpKind: state.followUpKind,
    finalScore: state.finalScore,
    totalAttempts: state.totalAttempts,
    events: state.events.slice(-240),
    progressPct: state.streaming ? 0 : state.progressPct,
    genStartedAt: state.streaming ? null : state.genStartedAt,
    etaSecondsRemaining: state.streaming ? null : state.etaSecondsRemaining,
    etaTotalSeconds: state.etaTotalSeconds,
    narration: state.narration,
    narrationLog: state.narrationLog,
    workMode: state.workMode,
    repoPath: state.repoPath,
    repoLabel: state.repoLabel,
    repoLoaded: state.repoLoaded,
    repoScan: state.repoScan,
    repoMessage: state.repoMessage,
    repoWriteResult: state.repoWriteResult,
  }
}
