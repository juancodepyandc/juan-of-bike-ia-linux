import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildAcceptanceCriteriaStep,
  detectInvertedCalculatorOperators,
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

  test('WS7: une calculatrice a operateur INVERSE echoue l acceptation (2+2 qui soustrait)', () => {
    // Toutes les operations sont "presentes" (les 4 symboles), mais '+' calcule
    // une soustraction: la presence regex passait, la correction non.
    const files = [file('src/calculator.ts', `
export function calculate(a: number, b: number, op: string) {
  switch (op) {
    case '+': return a - b
    case '-': return a - b
    case '*': return a * b
    case '/': return a / b
    default: return a
  }
}
let display = '0'; export function equals() { return display }
export function clear() { display = '0' }
`)]

    const results = evaluateAcceptanceCriteria('calculator four function', files)
    assert.ok(results.some((r) => r.id === 'calculator-operator-correctness' && !r.ok), 'l operateur inverse doit echouer')
    assert.ok(scoreAcceptanceCriteria(results) < 100)
    assert.equal(buildAcceptanceCriteriaStep('calculatrice', files).ok, false)
  })

  test('WS7: detectInvertedCalculatorOperators — table de fonctions et switch', () => {
    // Idiome table: '+' code avec soustraction.
    assert.ok(detectInvertedCalculatorOperators(`const ops = { '+': (a, b) => a - b, '-': (a, b) => a - b }`).length > 0)
    // Correct: aucun faux positif.
    assert.equal(detectInvertedCalculatorOperators(`const ops = { '+': (a, b) => a + b, '*': (a, b) => a * b }`).length, 0)
    assert.equal(detectInvertedCalculatorOperators(`switch(op){ case '/': return a / b }`).length, 0)
  })

  test('GARDE UNIFORMITE: un input placeholder legitime ne fait PAS echouer le critere no-placeholder', () => {
    // Une UI riche avec un champ de recherche etait plafonnee a 50% (punie pour
    // sa richesse) car "placeholder" matchait l'attribut HTML. Ne doit plus.
    const files = [file('index.html', `
<main>
  <header><h1>Tableau de bord</h1></header>
  <form><input type="search" placeholder="Rechercher un produit" aria-label="Recherche"></form>
  <section class="grid"><article>Produit A</article><article>Produit B</article></section>
  <style>input::placeholder{color:#888}.placeholder-glow{opacity:.5}</style>
  <script>document.querySelector('form').addEventListener('submit', (e)=>e.preventDefault())</script>
</main>`, 'html')]
    const results = evaluateAcceptanceCriteria('un dashboard produits avec recherche', files)
    const placeholderCriterion = results.find((r) => r.id === 'no-placeholder-code')
    assert.ok(placeholderCriterion && placeholderCriterion.ok, 'no-placeholder-code doit passer sur une UI a formulaire')
    assert.equal(scoreAcceptanceCriteria(results), 100)
  })

  test('un VRAI stub placeholder echoue toujours le critere', () => {
    const files = [file('app.js', `function render(){ /* placeholder: a implementer plus tard */ }`, 'js')]
    const results = evaluateAcceptanceCriteria('une petite app', files)
    const placeholderCriterion = results.find((r) => r.id === 'no-placeholder-code')
    assert.ok(placeholderCriterion && !placeholderCriterion.ok, 'un stub placeholder doit toujours echouer')
  })
})
