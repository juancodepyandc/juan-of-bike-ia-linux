import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCodeStreamCorrectionEvent,
  buildCodeStreamDoneEvent,
  buildCodeStreamErrorEvent,
  buildCodeStreamFileWrittenEvents,
  buildCodeStreamPhaseEvent,
  buildCodeStreamTestResultEvent,
  buildCodeStreamVisualScoreEvent,
  isCodeStreamEvent,
  parseCodeStreamEventLine,
  serializeCodeStreamEvent,
} from '../services/codeStreamEvents.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function meta() {
  let sequence = 0
  return () => ({ runId: 7, sequence: ++sequence, timestamp: 1_700_000_000_000 + sequence })
}

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, language, content }
}

describe('codeStreamEvents', () => {
  test('serialise et relit un evenement phase en NDJSON', () => {
    const nextMeta = meta()
    const event = buildCodeStreamPhaseEvent({
      ...nextMeta(),
      message: 'Validation sandbox',
      progress: 92,
    })

    assert.equal(event.kind, 'phase')
    assert.equal(event.phase, 'validation')
    assert.equal(event.progress, 92)

    const parsed = parseCodeStreamEventLine(serializeCodeStreamEvent(event))
    assert.deepEqual(parsed, event)
  })

  test('detecte uniquement les fichiers nouveaux ou modifies', () => {
    const nextMeta = meta()
    const events = buildCodeStreamFileWrittenEvents({
      previousFiles: [
        file('src/App.tsx', 'same', 'tsx'),
        file('README.md', 'old'),
      ],
      files: [
        file('./src/App.tsx', 'same', 'tsx'),
        file('README.md', 'new'),
        file('src/main.tsx', 'boot', 'tsx'),
      ],
      nextMeta,
      includeContent: true,
    })

    assert.deepEqual(events.map((event) => event.path), ['README.md', 'src/main.tsx'])
    assert.equal(events[0].content, 'new')
    assert.equal(events[1].bytes, 4)
  })

  test('convertit un resultat sandbox en test.result non gameable', () => {
    const nextMeta = meta()
    const event = buildCodeStreamTestResultEvent({
      ok: false,
      rootPath: '/tmp/project',
      summary: '1 commande echouee',
      question: null,
      detectedLanguage: 'node',
      steps: [
        { label: 'install', command: 'npm install', ok: true, output: 'ok' },
        { label: 'test', command: 'npm test', ok: false, output: 'fail' },
      ],
    }, nextMeta())

    assert.equal(event.kind, 'test.result')
    assert.equal(event.ok, false)
    assert.equal(event.score, 50)
    assert.deepEqual(event.failedLabels, ['test'])
    assert.equal(isCodeStreamEvent(event), true)
  })

  test('valide les evenements obligatoires du contrat /api/code/*', () => {
    const nextMeta = meta()
    const events = [
      buildCodeStreamPhaseEvent({ ...nextMeta(), phase: 'planning', message: 'Plan', progress: 10 }),
      buildCodeStreamCorrectionEvent({
        ...nextMeta(),
        pass: { attempt: 1, score: 80, errors: ['TS2307'], strategy: 'targeted_repair', modelUsed: 'qwen3-coder', resolved: false },
        attempt: 1,
        score: 80,
      }),
      buildCodeStreamDoneEvent({
        ...nextMeta(),
        files: [file('package.json', '{}', 'json')],
        finalScore: 100,
        totalAttempts: 1,
        notes: 'ok',
      }),
      buildCodeStreamVisualScoreEvent({ ...nextMeta(), score: 82, viewport: '1440x900', summary: 'hierarchie correcte' }),
      buildCodeStreamErrorEvent({ ...nextMeta(), message: 'timeout', recoverable: true }),
    ]

    assert.equal(events.every(isCodeStreamEvent), true)
    assert.equal(parseCodeStreamEventLine('{"kind":"phase"}'), null)
    assert.equal(parseCodeStreamEventLine('not json'), null)
  })
})
