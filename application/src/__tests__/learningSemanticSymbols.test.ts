import { test } from 'node:test'
import assert from 'node:assert/strict'
import { evaluateAnswerSemantically } from '../services/learningSemanticEval.ts'

test('different signs, operators and symbols require an actual evaluation', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls += 1
    return new Response(JSON.stringify({ message: { content: '{"score":0,"feedback":"Incorrect"}' } }))
  })
  const cases = [
    ['-5', '5'], ['x > 0', 'x < 0'], ['2 + 2', '2 - 2'],
    ['1.25', '1,25'], ['α', 'β'], ['⚡', '☀️'], ['C++', 'C'],
  ]
  for (const [expected, userAnswer] of cases) {
    const result = await evaluateAnswerSemantically({ question: 'Compare', expected, userAnswer })
    assert.equal(result.score, 0, `${JSON.stringify(userAnswer)} must not exactly match ${JSON.stringify(expected)}`)
  }
  assert.equal(calls, cases.length)
})

test('identical mathematical expressions still take the exact-match path', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => assert.fail('unexpected model request'))
  const result = await evaluateAnswerSemantically({ question: 'Q', expected: 'x ≤ -5', userAnswer: 'x   ≤ -5' })
  assert.equal(result.score, 100)
})

test('missing and non-finite model scores report an unavailable evaluation', async (t) => {
  let content = '{}'
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ message: { content } })))
  for (const response of ['{}', '{"score":1e309}', '{"score":"100"}']) {
    content = response
    const result = await evaluateAnswerSemantically({ question: 'Q', expected: 'photosynthese plante', userAnswer: 'sans rapport' })
    assert.equal(result.error, 'parse-fail')
    assert.equal(result.ok, false)
  }
})
