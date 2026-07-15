import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CritiqueReport } from '../services/codeMultiPassCritique.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import {
  computeSandboxScore,
  formatStaticCritiqueReport,
  isStaticCritiqueBlocking,
  withStaticCritiqueStep,
} from '../services/codeValidationScoring.ts'

const cliIntent = { projectType: 'cli_python' } as unknown as CodeIntent

const goodFiles = [
  {
    name: 'main.py',
    language: 'python',
    content: 'def main():\n    print("application complete")\n\nif __name__ == "__main__":\n    main()\n',
  },
]

function sandbox(overrides: Partial<CodeSandboxResult> = {}): CodeSandboxResult {
  return {
    ok: true,
    rootPath: '/tmp/project',
    summary: 'ok',
    question: null,
    detectedLanguage: 'python',
    steps: [],
    ...overrides,
  }
}

function report(overrides: Partial<CritiqueReport> = {}): CritiqueReport {
  return {
    overallScore: 1,
    hasBlocker: false,
    issues: [],
    scores: {
      compile: 1,
      lint: 1,
      tests: 1,
      fidelity: 1,
      runtime: 1,
      preview: 1,
      security: 1,
      accessibility: 1,
      perf: 1,
    },
    ...overrides,
  }
}

describe('codeValidationScoring', () => {
  test('plafonne le score sandbox par la qualite du contenu', () => {
    const score = computeSandboxScore(
      sandbox({ ok: true }),
      [{ name: 'README.md', language: 'markdown', content: '# Documentation seule' }],
      cliIntent,
    )

    assert.equal(score, 10)
  })

  test('calcule un score partiel depuis les etapes sandbox et les signaux positifs', () => {
    const score = computeSandboxScore(
      sandbox({
        ok: false,
        summary: 'partiel',
        steps: [
          { label: 'Install', command: 'npm install', ok: true, output: 'done' },
          { label: 'Build', command: 'npm run build', ok: false, output: 'warning: compiled with warnings' },
        ],
      }),
      goodFiles,
      cliIntent,
    )

    assert.equal(score, 55)
  })

  test('ajoute une etape de critique statique non bloquante sans casser le sandbox', () => {
    const enriched = withStaticCritiqueStep(sandbox(), report())

    assert.equal(enriched.ok, true)
    assert.equal(enriched.steps.at(-1)?.label, 'Critique statique Aurora')
    assert.equal(enriched.steps.at(-1)?.ok, true)
  })

  test('bloque le sandbox quand la critique statique detecte une erreur', () => {
    const blockingReport = report({
      hasBlocker: true,
      overallScore: 0.4,
      issues: [
        {
          axis: 'security',
          severity: 'block',
          message: 'eval interdit',
          location: { file: 'src/App.tsx', line: 12 },
          suggestion: 'Remplacer eval par un parseur strict',
        },
      ],
      scores: {
        ...report().scores,
        security: 0.2,
      },
    })

    assert.equal(isStaticCritiqueBlocking(blockingReport), true)
    const formatted = formatStaticCritiqueReport(blockingReport)
    assert.match(formatted, /blocker=true/)
    assert.match(formatted, /src\/App\.tsx:12/)

    const enriched = withStaticCritiqueStep(sandbox({ ok: true, summary: 'sandbox ok' }), blockingReport)
    assert.equal(enriched.ok, false)
    assert.match(enriched.summary, /critique statique/)
    assert.equal(enriched.steps.at(-1)?.ok, false)
  })
})
