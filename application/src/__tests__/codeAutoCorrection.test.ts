/**
 * Tests pour services/codeAutoCorrection — escalation rule-based, error
 * classification, plateau detection.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyErrors,
  buildCorrectionStrategy,
  shouldContinueLoop,
  MAX_CORRECTION_PASSES,
  type CorrectionPass,
} from '../services/codeAutoCorrection.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'

function sandboxResult(failedOutputs: string[]): CodeSandboxResult {
  return {
    ok: failedOutputs.length === 0,
    rootPath: '/tmp',
    summary: '',
    question: null,
    steps: failedOutputs.map((output, i) => ({
      ok: false,
      label: `step-${i}`,
      output,
      durationMs: 100,
    } as any)),
    detectedLanguage: 'typescript',
  }
}

describe('classifyErrors — patterns', () => {
  test('SyntaxError → syntax', () => {
    const r = classifyErrors(sandboxResult(['SyntaxError: unexpected token']))
    assert.ok(r.includes('syntax'))
  })

  test('TypeError → type_error', () => {
    const r = classifyErrors(sandboxResult(['TypeError: Cannot read property']))
    assert.ok(r.includes('type_error'))
  })

  test('Cannot find module → import_missing', () => {
    const r = classifyErrors(sandboxResult(['Error: Cannot find module "foo"']))
    assert.ok(r.includes('import_missing'))
  })

  test('npm ERR! → dependency_missing', () => {
    const r = classifyErrors(sandboxResult(['npm ERR! code ENOENT']))
    assert.ok(r.includes('dependency_missing'))
  })

  test('JSONParseError → config_error', () => {
    const r = classifyErrors(sandboxResult(['JSONParseError in package.json']))
    assert.ok(r.includes('config_error'))
  })

  test('command not found → runtime_unavailable', () => {
    const r = classifyErrors(sandboxResult(['bash: rustc: command not found']))
    assert.ok(r.includes('runtime_unavailable'))
  })

  test('ReferenceError → runtime_crash', () => {
    const r = classifyErrors(sandboxResult(['ReferenceError: x is not defined']))
    assert.ok(r.includes('runtime_crash'))
  })

  test('panic → runtime_crash', () => {
    const r = classifyErrors(sandboxResult(['thread "main" panicked at']))
    assert.ok(r.includes('runtime_crash'))
  })

  test('AssertionError → test_failure', () => {
    const r = classifyErrors(sandboxResult(['AssertionError: expected 1 got 2']))
    assert.ok(r.includes('test_failure'))
  })

  test('Build failed → build_failure', () => {
    const r = classifyErrors(sandboxResult(['Build failed with 3 errors']))
    assert.ok(r.includes('build_failure'))
  })

  test('EACCES → permission_error', () => {
    const r = classifyErrors(sandboxResult(['EACCES: permission denied']))
    assert.ok(r.includes('permission_error'))
  })

  test('timeout → timeout', () => {
    const r = classifyErrors(sandboxResult(['ETIMEDOUT: process timeout']))
    assert.ok(r.includes('timeout'))
  })

  test('aucune erreur → unknown', () => {
    const r = classifyErrors(sandboxResult(['random text non-error']))
    assert.deepEqual(r, ['unknown'])
  })

  test('plusieurs erreurs → catégories multiples', () => {
    const r = classifyErrors(sandboxResult(['SyntaxError', 'Cannot find module "foo"']))
    assert.ok(r.includes('syntax'))
    assert.ok(r.includes('import_missing'))
  })

  test('catégories sans doublon', () => {
    const r = classifyErrors(sandboxResult(['SyntaxError', 'SyntaxError', 'IndentationError']))
    assert.equal(r.filter((c) => c === 'syntax').length, 1)
  })

  test('steps ok=true ignorés', () => {
    const result: CodeSandboxResult = {
      ok: true, rootPath: '/tmp', summary: '', question: null, detectedLanguage: 'ts',
      steps: [{ ok: true, label: 'a', output: 'SyntaxError but step ok', durationMs: 100 } as any],
    }
    const r = classifyErrors(result)
    // step.ok=true → ignored → unknown
    assert.deepEqual(r, ['unknown'])
  })
})

describe('buildCorrectionStrategy — niveaux escalation', () => {
  test('attempt 1 + syntax → quick_fix', () => {
    const s = buildCorrectionStrategy(['syntax'], 1, [])
    assert.equal(s.level, 'quick_fix')
    assert.equal(s.escalation, 1)
  })

  test('attempt 3 + dependency → targeted_repair', () => {
    const s = buildCorrectionStrategy(['dependency_missing'], 3, [
      { attempt: 1, score: 30, errors: ['e'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 40, errors: ['e'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
    ])
    assert.ok(['targeted_repair', 'partial_rewrite'].includes(s.level))
  })

  test('attempt 5 → partial_rewrite ou rewrite', () => {
    const s = buildCorrectionStrategy(['runtime_crash'], 5, [])
    assert.ok(['partial_rewrite', 'rewrite'].includes(s.level))
  })

  test('attempt 9 → strategy_change', () => {
    const s = buildCorrectionStrategy(['unknown'], 9, [])
    assert.equal(s.level, 'strategy_change')
  })

  test('runtime_unavailable → toujours targeted_repair même attempt 1', () => {
    const s = buildCorrectionStrategy(['runtime_unavailable'], 1, [])
    assert.equal(s.level, 'targeted_repair')
    assert.equal(s.searchWeb, true)
  })
})

describe('buildCorrectionStrategy — flags', () => {
  test('searchWeb=true par défaut sur quick_fix', () => {
    const s = buildCorrectionStrategy(['syntax'], 1, [])
    assert.equal(s.searchWeb, true)
  })

  test('strategy_change → switchModel=false (protection PC)', () => {
    const s = buildCorrectionStrategy(['unknown'], 9, [])
    assert.equal(s.switchModel, false)
  })

  test('partial_rewrite → switchModel=true', () => {
    const s = buildCorrectionStrategy(['runtime_crash'], 5, [])
    if (s.level === 'partial_rewrite') {
      assert.equal(s.switchModel, true)
    }
  })
})

describe('buildCorrectionStrategy — instructions', () => {
  test('quick_fix mentionne syntaxe/imports', () => {
    const s = buildCorrectionStrategy(['syntax', 'import_missing'], 1, [])
    assert.ok(/syntax/i.test(s.instructions))
    assert.ok(/import/i.test(s.instructions))
  })

  test('runtime_unavailable instructions mentionnent runtime/binaire', () => {
    const s = buildCorrectionStrategy(['runtime_unavailable'], 1, [])
    assert.ok(/runtime|binaire|installation/i.test(s.instructions))
  })

  test('strategy_change rotation au-delà attempt 5', () => {
    // Log avec scores stagnants → force escalation=attempt (et donc 5+ → strategy_change)
    const stagnatingLog: CorrectionPass[] = [
      { attempt: 1, score: 45, errors: ['e'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 46, errors: ['e'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
      { attempt: 3, score: 47, errors: ['e'], strategy: 'targeted_repair', modelUsed: 'm', resolved: false },
    ]
    const s6 = buildCorrectionStrategy(['unknown'], 6, stagnatingLog)
    assert.equal(s6.level, 'strategy_change')
    assert.ok(s6.instructions.includes('VARIATION'))
  })

  test('rotation cycle 4 → variations différentes', () => {
    const stagnatingLog: CorrectionPass[] = [
      { attempt: 1, score: 40, errors: ['e'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 41, errors: ['e'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
      { attempt: 3, score: 42, errors: ['e'], strategy: 'targeted_repair', modelUsed: 'm', resolved: false },
    ]
    const variations = new Set<string>()
    for (let attempt = 6; attempt <= 9; attempt++) {
      const s = buildCorrectionStrategy(['unknown'], attempt, stagnatingLog)
      const m = s.instructions.match(/VARIATION (\d)/)
      if (m) variations.add(m[1])
    }
    assert.ok(variations.size >= 2, `only ${variations.size} variations`)
  })
})

describe('buildCorrectionStrategy — stagnation', () => {
  test('stagnation détectée → escalation saute à attempt', () => {
    const log: CorrectionPass[] = [
      { attempt: 1, score: 40, errors: ['e'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 42, errors: ['e'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
      { attempt: 3, score: 41, errors: ['e'], strategy: 'targeted_repair', modelUsed: 'm', resolved: false },
    ]
    const s = buildCorrectionStrategy(['unknown'], 3, log)
    // Stagnation détectée → escalation devrait être Math.min(5, 3) = 3
    assert.ok(s.escalation >= 3)
  })

  test('progression normale → escalation = ceil(attempt/2)', () => {
    const log: CorrectionPass[] = [
      { attempt: 1, score: 10, errors: ['e'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 50, errors: ['e'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
      { attempt: 3, score: 80, errors: ['e'], strategy: 'targeted_repair', modelUsed: 'm', resolved: false },
    ]
    const s = buildCorrectionStrategy(['unknown'], 3, log)
    assert.equal(s.escalation, 2) // ceil(3/2)
  })
})

describe('shouldContinueLoop', () => {
  test('log vide → continuer', () => {
    assert.equal(shouldContinueLoop([], 0), true)
  })

  test('score 100 atteint → stop', () => {
    const log: CorrectionPass[] = [
      { attempt: 1, score: 100, errors: [], strategy: 'initial', modelUsed: 'm', resolved: true },
    ]
    assert.equal(shouldContinueLoop(log, 1), false)
  })

  test('cap MAX_CORRECTION_PASSES atteint → stop', () => {
    const log: CorrectionPass[] = Array.from({ length: MAX_CORRECTION_PASSES }, (_, i) => ({
      attempt: i + 1,
      score: 50,
      errors: ['e'],
      strategy: 'initial' as const,
      modelUsed: 'm',
      resolved: false,
    }))
    assert.equal(shouldContinueLoop(log, MAX_CORRECTION_PASSES), false)
  })

  test('même erreur 6× consécutivement → stop (loop prouvé impossible)', () => {
    const sameError = 'TypeError: cannot read x'
    const log: CorrectionPass[] = Array.from({ length: 6 }, (_, i) => ({
      attempt: i + 1,
      score: 30 + i,
      errors: [sameError],
      strategy: 'initial' as const,
      modelUsed: 'm',
      resolved: false,
    }))
    assert.equal(shouldContinueLoop(log, 6), false)
  })

  test('erreurs différentes 6× → continuer', () => {
    const log: CorrectionPass[] = Array.from({ length: 6 }, (_, i) => ({
      attempt: i + 1,
      score: 30 + i,
      errors: [`Error ${i} different message`],
      strategy: 'initial' as const,
      modelUsed: 'm',
      resolved: false,
    }))
    assert.equal(shouldContinueLoop(log, 6), true)
  })

  test('progression normale → continuer', () => {
    const log: CorrectionPass[] = [
      { attempt: 1, score: 20, errors: ['a'], strategy: 'initial', modelUsed: 'm', resolved: false },
      { attempt: 2, score: 70, errors: ['b'], strategy: 'quick_fix', modelUsed: 'm', resolved: false },
    ]
    assert.equal(shouldContinueLoop(log, 2), true)
  })

  test('MAX_CORRECTION_PASSES vaut 10', () => {
    assert.equal(MAX_CORRECTION_PASSES, 10)
  })
})
