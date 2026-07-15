import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildAcceptanceCriteriaStep,
  evaluateAcceptanceCriteria,
  scoreAcceptanceCriteria,
} from '../services/codeAcceptanceCriteria.ts'
import type { CodeFile } from '../services/codeSandboxTypes.ts'

function file(name: string, content: string, language = 'ts'): CodeFile {
  return { name, content, language }
}

describe('codeAcceptanceCriteria', () => {
  test('une fausse calculatrice ne passe pas a 100%', () => {
    const files = [file('index.html', `
<main>
  <output>0</output>
  <button>1</button><button>+</button><button>=</button>
</main>
<script>console.log('demo only')</script>
`, 'html')]

    const results = evaluateAcceptanceCriteria('creer une calculatrice complete', files)
    const score = scoreAcceptanceCriteria(results)

    assert.ok(score < 100, `score ${score}`)
    assert.ok(results.some((result) => result.id === 'calculator-operations' && !result.ok))
    assert.equal(buildAcceptanceCriteriaStep('calculatrice', files).ok, false)
  })

  test('une calculatrice avec logique quatre operations passe les criteres', () => {
    const files = [file('src/calculator.ts', `
let display = '0'
let operator = '+'
export function calculate(a: number, b: number, op = operator) {
  switch (op) {
    case '+': return a + b
    case '-': return a - b
    case '*': return a * b
    case '/': return b === 0 ? 'Error' : a / b
    default: return a
  }
}
export function equals(a: number, b: number) { display = String(calculate(a, b)); return display }
export function clear() { display = '0'; operator = '+' }
`)]

    const results = evaluateAcceptanceCriteria('calculator four function', files)

    assert.equal(scoreAcceptanceCriteria(results), 100, JSON.stringify(results))
    assert.equal(buildAcceptanceCriteriaStep('calculator four function', files).ok, true)
  })
})
