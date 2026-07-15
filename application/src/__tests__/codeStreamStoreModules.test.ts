import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { narrate, readNarrateVoice, writeNarrateVoice } from '../stores/codeStreamNarration.ts'
import { computeEta, phaseFromDetail, summariseDelivery } from '../stores/codeStreamProgress.ts'
import { captureSessionSnapshot, emptySessionSnapshot } from '../stores/codeStreamSessions.ts'
import { extractBrandHint, isCorrectionRequest, routeCodeStreamModel } from '../stores/codeStreamRouting.ts'
import type { CodeStreamState } from '../stores/codeStreamTypes.ts'

function installLocalStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial))
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem(key: string) {
        return values.get(key) ?? null
      },
      setItem(key: string, value: string) {
        values.set(key, value)
      },
    },
    configurable: true,
  })
}

function state(overrides: Partial<CodeStreamState> = {}): CodeStreamState {
  return {
    draft: '',
    streaming: false,
    streamOutput: '',
    error: null,
    history: [],
    lastCompletedAt: null,
    runId: 0,
    phase: 'idle',
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
    progressPct: 0,
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

describe('codeStreamNarration', () => {
  test('read/write narration voice persiste dans localStorage', () => {
    installLocalStorage()
    assert.equal(readNarrateVoice(), false)
    writeNarrateVoice(true)
    assert.equal(readNarrateVoice(), true)
    writeNarrateVoice(false)
    assert.equal(readNarrateVoice(), false)
  })

  test('narrate distingue correction et generation', () => {
    const correction = narrate('streaming', '', { followUp: null, repo: false, brand: null, correction: true })
    const generation = narrate('streaming', '', { followUp: null, repo: false, brand: null, correction: false })

    assert.match(correction, /corrige/)
    assert.match(generation, /J.écris/i)
  })
})

describe('codeStreamProgress', () => {
  test('computeEta garde le precedent si le progres est trop bas', () => {
    assert.deepEqual(computeEta(null, 1, 42), { remaining: 42, total: null })
  })

  test('computeEta borne les hausses brutales', () => {
    const eta = computeEta(Date.now() - 1_000, 5, 3)
    assert.equal(eta.remaining, 11)
  })

  test('phaseFromDetail mappe les phases textuelles puis le streaming par progres', () => {
    assert.equal(phaseFromDetail('Recherche de references', 5), 'research')
    assert.equal(phaseFromDetail('Validation sandbox', 92), 'validation')
    assert.equal(phaseFromDetail('Generation', 50), 'streaming')
  })

  test('summariseDelivery limite les noms de fichiers', () => {
    const files = Array.from({ length: 13 }, (_, index) => ({
      name: `src/file${index}.ts`,
      language: 'ts',
      content: '',
    }))
    const summary = summariseDelivery(files, 87)
    assert.match(summary, /13 fichier/)
    assert.match(summary, /\(\+1\)/)
    assert.match(summary, /Score 87%/)
  })
})

describe('codeStreamSessions', () => {
  test('emptySessionSnapshot initialise un projet online vide', () => {
    const snapshot = emptySessionSnapshot()
    assert.equal(snapshot.workMode, 'online')
    assert.deepEqual(snapshot.files, [])
    assert.equal(snapshot.phase, 'idle')
  })

  test('captureSessionSnapshot neutralise une generation en cours', () => {
    const snapshot = captureSessionSnapshot(state({
      streaming: true,
      phase: 'streaming',
      phaseMessage: 'Generation...',
      progressPct: 64,
      genStartedAt: 123,
      etaSecondsRemaining: 45,
      files: [{ name: 'index.html', language: 'html', content: '<main />' }],
    }))

    assert.equal(snapshot.phase, 'done')
    assert.equal(snapshot.phaseMessage, '')
    assert.equal(snapshot.progressPct, 0)
    assert.equal(snapshot.genStartedAt, null)
    assert.equal(snapshot.etaSecondsRemaining, null)
  })
})

describe('codeStreamRouting', () => {
  test('extractBrandHint ignore les mots generiques et retient une marque', () => {
    assert.equal(extractBrandHint('Nike landing premium'), 'Nike')
    assert.equal(extractBrandHint('Landing page simple'), null)
  })

  test('routeCodeStreamModel passe un projet visuel depuis coder vers generaliste', () => {
    const route = routeCodeStreamModel({
      baseModel: 'qwen3-coder:30b',
      installed: ['qwen3:14b', 'qwen3-coder:30b'],
      isVisual: true,
      text: 'Nike landing premium',
    })

    assert.equal(route.model, 'qwen3:14b')
    assert.equal(route.brandHint, 'Nike')
    assert.match(route.routeReason, /visual/)
  })

  test('routeCodeStreamModel passe un projet non visuel vers un coder installe', () => {
    const route = routeCodeStreamModel({
      baseModel: 'qwen3:14b',
      installed: ['qwen3-coder:30b', 'qwen3:14b'],
      isVisual: false,
      text: 'CLI Rust pour analyser des logs',
    })

    assert.equal(route.model, 'qwen3-coder:30b')
  })

  test('isCorrectionRequest detecte une demande de correction', () => {
    assert.equal(isCorrectionRequest('corrige le bug qui affiche un ecran noir'), true)
    assert.equal(isCorrectionRequest('cree une landing page'), false)
  })
})
