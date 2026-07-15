import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import {
  collectFailingStepOutputs,
  compactCorrectionLog,
  normalizedFilesChanged,
  truncateCorrectionErrors,
} from '../services/codeValidationCorrectionLoop.ts'

function sandbox(outputs: Array<{ ok: boolean; output: string }>): CodeSandboxResult {
  return {
    ok: outputs.every((step) => step.ok),
    rootPath: '/tmp/project',
    summary: 'sandbox',
    question: null,
    detectedLanguage: 'node',
    steps: outputs.map((step, index) => ({
      label: `Step ${index + 1}`,
      command: `cmd-${index + 1}`,
      ok: step.ok,
      output: step.output,
    })),
  }
}

function pass(attempt: number, errors: string[]): CorrectionPass {
  return {
    attempt,
    score: 10 * attempt,
    errors,
    strategy: attempt === 1 ? 'initial' : 'targeted_repair',
    modelUsed: 'qwen3-coder:30b',
    resolved: false,
  }
}

describe('codeValidationCorrectionLoop helpers', () => {
  test('detecte uniquement les fichiers normalises reellement changes', () => {
    const current = [
      { name: 'package.json', language: 'json', content: '{"name":"demo"}' },
    ]

    assert.equal(normalizedFilesChanged(current, undefined), false)
    assert.equal(normalizedFilesChanged(current, []), false)
    assert.equal(normalizedFilesChanged(current, current), false)
    assert.equal(normalizedFilesChanged(current, [
      { name: 'package.json', language: 'json', content: '{"name":"demo","scripts":{}}' },
    ]), true)
    assert.equal(normalizedFilesChanged(current, [
      ...current,
      { name: 'src/main.ts', language: 'ts', content: 'export {}' },
    ]), true)
  })

  test('collecte seulement les sorties des etapes en echec', () => {
    const result = sandbox([
      { ok: true, output: 'install ok' },
      { ok: false, output: 'build failed' },
      { ok: false, output: 'test failed' },
    ])

    assert.deepEqual(collectFailingStepOutputs(result), ['build failed', 'test failed'])
  })

  test('tronque les erreurs longues en conservant debut et fin', () => {
    const longError = `${'a'.repeat(1200)}MIDDLE${'z'.repeat(500)}`
    const truncated = truncateCorrectionErrors(sandbox([
      { ok: false, output: longError },
    ]))

    assert.equal(truncated.length, 1)
    assert.match(truncated[0], /tronque:/)
    assert.ok(truncated[0].startsWith('a'.repeat(1000)))
    assert.ok(truncated[0].endsWith('z'.repeat(400)))
  })

  test('compacte uniquement les passes archivees au-dela des quatre dernieres', () => {
    const log = [
      pass(1, ['x'.repeat(220)]),
      pass(2, ['erreur a', 'erreur b']),
      pass(3, ['courte']),
      pass(4, ['courte']),
      pass(5, ['courte']),
      pass(6, ['courte']),
    ]

    compactCorrectionLog(log)

    assert.match(log[0].errors[0], /passe archivee/)
    assert.match(log[1].errors[0], /passe archivee/)
    assert.deepEqual(log[2].errors, ['courte'])
    assert.deepEqual(log[5].errors, ['courte'])
  })
})
