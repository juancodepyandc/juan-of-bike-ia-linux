import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDesignRetryHint,
  checkGamePlayability,
  computeDesignPolishReport,
  isVisualProjectType,
} from '../services/codeQualityGates.ts'

describe('codeQualityGates', () => {
  test('detecte un jeu web sans controles clavier demandes', () => {
    const result = checkGamePlayability(
      [{ name: 'index.html', language: 'html', content: '<canvas id="game"></canvas><script>requestAnimationFrame(loop)</script>' }],
      'jeu avec deplacement clavier et score',
    )

    assert.equal(result.ok, false)
    assert.ok(result.missing.some((item) => item.includes('clavier')))
  })

  test('produit un rapport design exploitable pour retry', () => {
    const report = computeDesignPolishReport([
      { name: 'index.html', language: 'html', content: '<main><button>Go</button></main><style>body{font-family:Arial;color:blue;}</style>' },
    ])

    assert.ok(report.score < 70)
    assert.ok(report.missing.length > 0)
    assert.ok(buildDesignRetryHint(report).includes(`Score: ${report.score}/100`))
  })

  test('reconnait les projets visuels', () => {
    assert.equal(isVisualProjectType('spa_react'), true)
    assert.equal(isVisualProjectType('cli_python'), false)
  })
})
