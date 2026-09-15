import { test } from 'node:test'
import assert from 'node:assert/strict'
import { scoreAttempt, type CodeAnswer, type CodeExerciseExercise } from '../services/learning/exerciseFormats.ts'

const exercise: CodeExerciseExercise = {
  id: 'addition', kind: 'code_exercise', prompt: 'Add two numbers', difficulty: 'decouverte',
  timeBudgetMin: 5, tags: ['arithmetic'], language: 'python', starter: 'def add(a, b): pass',
  tests: [
    { id: 'positive', input: '[1, 2]', expected: '3', hidden: false },
    { id: 'negative', input: '[-2, -1]', expected: '-3', hidden: true },
  ],
}
const score = (runs: CodeAnswer['runResults']) => scoreAttempt(exercise, { kind: 'code_exercise', source: '', runResults: runs })
const run = (testId: string, pass = true) => ({ testId, pass, output: '' })

test('duplicate and unknown results cannot inflate a programming grade', () => {
  const result = score([run('positive'), run('positive'), run('unknown')])
  assert.equal(result.ratio01, 0.5)
  assert.deepEqual(result.flagged, ['negative'])
  assert.equal(result.feedback, '1/2 tests passent.')
})

test('unknown successful tests give no credit', () => {
  const result = score([run('unknown')])
  assert.equal(result.ratio01, 0)
  assert.deepEqual(result.flagged, ['positive', 'negative'])
})

test('conflicting results fail the affected test regardless of order', () => {
  const runs = [run('positive'), run('positive', false), run('negative')]
  for (const results of [runs, [...runs].reverse()]) {
    assert.equal(score(results).ratio01, 0.5)
    assert.deepEqual(score(results).flagged, ['positive'])
  }
})

test('each expected passing test contributes once', () => {
  assert.equal(score([run('negative'), run('positive'), run('negative')]).ratio01, 1)
})
