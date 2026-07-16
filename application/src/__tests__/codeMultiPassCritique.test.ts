import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { buildReport, type CritiqueAxis } from '../services/codeMultiPassCritique.ts'

const AXES: CritiqueAxis[] = [
  'compile',
  'lint',
  'tests',
  'fidelity',
  'runtime',
  'preview',
  'security',
  'accessibility',
  'perf',
]

describe('buildReport actif', () => {
  test('les axes absents valent 1', () => {
    const report = buildReport({})
    assert.equal(report.overallScore, 1)
    assert.ok(AXES.every((axis) => report.scores[axis] === 1))
  })

  test('un blocker positionne hasBlocker', () => {
    const report = buildReport({ compile: 0 }, [
      { axis: 'compile', severity: 'block', message: 'tsc fail' },
    ])
    assert.equal(report.hasBlocker, true)
  })

  test('la moyenne respecte les poids', () => {
    const compileFailure = buildReport({ compile: 0 })
    const perfFailure = buildReport({ perf: 0 })
    assert.ok(compileFailure.overallScore < perfFailure.overallScore)
  })

  test('les incidents sont tries par severite', () => {
    const report = buildReport({}, [
      { axis: 'lint', severity: 'info', message: 'info' },
      { axis: 'tests', severity: 'warn', message: 'warn' },
      { axis: 'runtime', severity: 'error', message: 'error' },
      { axis: 'security', severity: 'block', message: 'block' },
    ])
    assert.deepEqual(report.issues.map((issue) => issue.severity), ['block', 'error', 'warn', 'info'])
  })

  for (const axis of AXES) {
    test(`borne ${axis} a zero`, () => {
      const report = buildReport({ [axis]: -10 })
      assert.equal(report.scores[axis], 0)
    })
  }

  test('un blocker plafonne le score global a 0.5', () => {
    const report = buildReport({}, [
      { axis: 'security', severity: 'block', message: 'execution arbitraire' },
    ])
    assert.equal(report.overallScore, 0.5)
  })

  test('un warning ne plafonne pas le score global', () => {
    const report = buildReport({}, [
      { axis: 'lint', severity: 'warn', message: 'style' },
    ])
    assert.equal(report.overallScore, 1)
  })

  test('ne mute pas le tableau d incidents fourni', () => {
    const issues = [
      { axis: 'lint' as const, severity: 'info' as const, message: 'a' },
      { axis: 'security' as const, severity: 'block' as const, message: 'b' },
    ]
    buildReport({}, issues)
    assert.equal(issues[0].message, 'a')
  })

  test('tous les axes a zero donnent un score global nul', () => {
    const scores = Object.fromEntries(AXES.map((axis) => [axis, 0])) as Record<CritiqueAxis, number>
    assert.equal(buildReport(scores).overallScore, 0)
  })

  test('borne les scores superieurs a un', () => {
    const report = buildReport({ compile: 4, security: 2 })
    assert.equal(report.scores.compile, 1)
    assert.equal(report.scores.security, 1)
  })

  test('un seul axe explicite ne degrade pas les autres', () => {
    const report = buildReport({ lint: 0.25 })
    assert.equal(report.scores.lint, 0.25)
    assert.equal(report.scores.compile, 1)
    assert.equal(report.scores.runtime, 1)
  })
})
