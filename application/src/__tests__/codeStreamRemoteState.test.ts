import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyRemoteCodeStreamEvent,
  phaseFromRemoteCodeStreamEvent,
} from '../stores/codeStreamRemoteState.ts'
import { shouldUseCodeBridgeStream } from '../stores/codeStreamRemoteTurn.ts'
import {
  buildCodeStreamDoneEvent,
  buildCodeStreamFileWrittenEvents,
  buildCodeStreamPhaseEvent,
} from '../services/codeStreamEvents.ts'
import type { CodeStreamState } from '../stores/codeStreamTypes.ts'

function state(overrides: Partial<CodeStreamState> = {}): CodeStreamState {
  return {
    draft: '',
    streaming: true,
    streamOutput: '',
    error: null,
    history: [],
    lastCompletedAt: null,
    runId: 1,
    phase: 'planning',
    phaseMessage: '',
    errorDialog: null,
    modelUsed: null,
    brandPrimary: null,
    files: [],
    notes: '',
    messages: [],
    followUpKind: null,
    finalScore: 0,
    totalAttempts: 0,
    events: [],
    progressPct: 1,
    genStartedAt: null,
    etaSecondsRemaining: null,
    etaTotalSeconds: null,
    narration: '',
    narrationLog: [],
    narrateVoice: false,
    workMode: 'online',
    repoPath: null,
    repoLabel: null,
    repoLoaded: false,
    repoScan: null,
    repoBusy: false,
    repoMessage: null,
    repoWriteResult: null,
    activeSessionId: null,
    sessionSnapshots: {},
    ...overrides,
  }
}

describe('codeStreamRemoteState', () => {
  test('applique phase puis file.written avec contenu au state UI', () => {
    const phase = buildCodeStreamPhaseEvent({
      runId: 1,
      sequence: 1,
      timestamp: 1,
      phase: 'generation',
      message: 'Generation',
      progress: 40,
    })
    const fileEvent = buildCodeStreamFileWrittenEvents({
      previousFiles: [],
      files: [{ name: 'src/App.tsx', language: 'tsx', content: 'export default null' }],
      nextMeta: () => ({ runId: 1, sequence: 2, timestamp: 2 }),
      includeContent: true,
    })[0]

    const afterPhase = { ...state(), ...applyRemoteCodeStreamEvent(state(), phase, 10) }
    const afterFile = { ...afterPhase, ...applyRemoteCodeStreamEvent(afterPhase, fileEvent, 11) }

    assert.equal(afterPhase.phase, 'streaming')
    assert.equal(afterPhase.progressPct, 40)
    assert.equal(afterFile.files[0].name, 'src/App.tsx')
    assert.equal(afterFile.events.length, 2)
  })

  test('applique done et conserve la note finale', () => {
    const done = buildCodeStreamDoneEvent({
      runId: 1,
      sequence: 3,
      timestamp: 3,
      files: [{ name: 'package.json', language: 'json', content: '{}' }],
      finalScore: 91,
      totalAttempts: 2,
      notes: 'build vert',
    })
    const next = applyRemoteCodeStreamEvent(state(), done, 123)

    assert.equal(next.streaming, false)
    assert.equal(next.phase, 'done')
    assert.equal(next.progressPct, 100)
    assert.equal(next.finalScore, 91)
    assert.equal(next.lastCompletedAt, 123)
    assert.equal(next.notes, 'build vert')
  })

  test('garde le planner-executor local par defaut meme en mode online', () => {
    assert.equal(shouldUseCodeBridgeStream({
      workMode: 'online',
      isCorrection: false,
      priorMessagesCount: 0,
      existingFilesCount: 0,
    }), false)
    assert.equal(shouldUseCodeBridgeStream({
      workMode: 'repo',
      isCorrection: false,
      priorMessagesCount: 0,
      existingFilesCount: 0,
    }), false)
    assert.equal(phaseFromRemoteCodeStreamEvent(doneEvent()), 'done')
  })
})

function doneEvent() {
  return buildCodeStreamDoneEvent({
    runId: 1,
    sequence: 1,
    timestamp: 1,
    files: [],
    finalScore: 0,
    totalAttempts: 1,
    notes: '',
  })
}
