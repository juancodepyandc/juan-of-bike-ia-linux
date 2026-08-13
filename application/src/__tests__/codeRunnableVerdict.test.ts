import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  isEmptyTestSuiteOutput,
  reclassifyEmptyTestSuiteStep,
} from '../services/codeSandboxEmptyTestSuite.ts'
import { isDeliveryRunnable, isStaticCritiqueBlocking } from '../services/codeValidationScoring.ts'
import type { CritiqueReport } from '../services/codeMultiPassCritique.ts'

describe('suite de tests absente — une absence n est pas un echec', () => {
  test('reconnait les lanceurs qui declarent n avoir rien trouve', () => {
    const outputs = [
      'No test files found, exiting with code 1',
      'No tests found, exiting with code 1',
      'collected 0 items',
      'no tests ran in 0.01s',
      '?   github.com/x/y  [no test files]',
      'running 0 tests',
      '  0 passing (2ms)',
    ]
    for (const output of outputs) assert.equal(isEmptyTestSuiteOutput(output), true, output)
  })

  test('un test ROUGE n est jamais requalifie', () => {
    const failing = [
      'FAIL src/App.test.tsx > affiche le titre\nAssertionError: expected 2 to be 3',
      'Tests:       1 failed, 3 passed, 4 total',
      'collected 4 items\n\nsrc/test_x.py F\n1 failed, 3 passed',
      '  2 passing (10ms)\n  1 failing',
    ]
    for (const output of failing) assert.equal(isEmptyTestSuiteOutput(output), false, output)
  })

  test('l etape est requalifiee NON APPLICABLE, avec la raison ecrite', () => {
    const verdict = reclassifyEmptyTestSuiteStep({
      label: 'Verifier test',
      ok: false,
      output: '> brulerie@0.0.0 test\n> vitest\n\nNo test files found, exiting with code 1',
    })
    assert.equal(verdict.notApplicable, true)
    assert.match(verdict.output, /SUITE DE TESTS ABSENTE/)
    assert.match(verdict.output, /n a donc rien mesure du code livre/)
    // La sortie d origine est conservee: on n efface pas la preuve.
    assert.match(verdict.output, /No test files found/)
  })

  test('un test qui echoue reste bloquant, et une etape non-test est intouchee', () => {
    assert.equal(reclassifyEmptyTestSuiteStep({
      label: 'Verifier test', ok: false, output: 'Tests: 1 failed, 3 passed',
    }).notApplicable, false)
    assert.equal(reclassifyEmptyTestSuiteStep({
      label: 'Verifier build', ok: false, output: 'No test files found',
    }).notApplicable, false)
    assert.equal(reclassifyEmptyTestSuiteStep({
      label: 'Verifier test', ok: true, output: 'No test files found',
    }).notApplicable, false)
  })
})

function report(issues: CritiqueReport['issues']): CritiqueReport {
  return {
    scores: { compile: 1, runtime: 1, lint: 1, security: 1, accessibility: 1, preview: 0.5 } as CritiqueReport['scores'],
    overallScore: 0.9,
    issues,
    hasBlocker: false,
  } as CritiqueReport
}

describe('verdict d executabilite — le juge aveugle ne condamne pas celui qui voit', () => {
  // Run 1091: `axis: 'preview'`, severite `error` (« Classes Tailwind sans
  // configuration Tailwind ») a bloque 9 passes, pendant que le navigateur
  // notait le rendu 92/100 et la page rendait 1 492 caracteres.
  test('un defaut d APPARENCE lu dans la source ne bloque plus l executabilite', () => {
    assert.equal(isStaticCritiqueBlocking(report([{
      axis: 'preview', severity: 'error',
      message: 'Classes Tailwind detectees sans configuration Tailwind (22 utilities)',
    }])), false)
  })

  test('tout autre axe en erreur reste bloquant', () => {
    for (const axis of ['compile', 'runtime', 'security', 'lint'] as const) {
      assert.equal(isStaticCritiqueBlocking(report([{
        axis, severity: 'error', message: `probleme ${axis}`,
      }])), true, axis)
    }
  })

  test('une severite `block` reste bloquante meme sur l axe apparence', () => {
    assert.equal(isStaticCritiqueBlocking(report([{
      axis: 'preview', severity: 'block', message: 'aucun apercu productible',
    }])), true)
  })

  test('un livrable dont seule une etape de style echoue reste executable', () => {
    assert.equal(isDeliveryRunnable({
      ok: false,
      steps: [
        { label: 'Verifier build', command: 'npm run build', ok: true, output: '' },
        { label: 'Design-spec', command: 'design-spec-gate', ok: false, output: 'ecart palette' },
      ],
    } as Parameters<typeof isDeliveryRunnable>[0]), true)
  })
})
