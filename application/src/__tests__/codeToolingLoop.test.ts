import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeIntent } from '../services/codeIntent.ts'
import {
  CODE_TOOLING_EVAL_SCHEMA,
  buildToolRegistryLookupUrl,
  detectToolingPlateau,
  formatToolingReportForCorrection,
  isCodeToolingEvalReport,
  parseRegistryLatestVersion,
  resolveToolPackageVersion,
  runCodeToolingEval,
  selectToolingCandidateForCorrection,
  summarizeToolingEval,
} from '../services/codeToolingLoop.ts'

function pass(score: number, attempt = 1): CorrectionPass {
  return {
    attempt,
    score,
    errors: ['ModuleNotFoundError: No module named slugify'],
    strategy: attempt === 1 ? 'initial' : 'targeted_repair',
    modelUsed: 'qwen3-coder',
    resolved: false,
  }
}

function pythonIntent(): CodeIntent {
  return {
    projectType: 'cli_python',
    complexity: 'simple',
    languages: ['python'],
    frameworks: [],
    features: [],
    needsDevServer: false,
    needsBundling: false,
    previewType: 'console',
    devCommand: null,
    buildCommand: null,
    testCommand: 'pytest',
    primaryModelRole: 'code',
    needsArchitecturePlanning: false,
    estimatedFileCount: 3,
    assetPlan: {
      styleHints: [],
      objectMentions: [],
      effectMentions: [],
      paletteHints: [],
      wantsPremiumLook: false,
      wantsImages: false,
      wants3D: false,
      needsResearch: false,
    },
  }
}

function report() {
  return {
    schemaVersion: CODE_TOOLING_EVAL_SCHEMA,
    createdAt: 1,
    venvRoot: '/home/juan/.local/share/auroraia/venvs/code-auto-tools',
    appVenvPath: '/home/juan/AuroraIA/application/.venv',
    appVenvInstallForbidden: true,
    candidates: [
      {
        id: 'pypi-python-slugify',
        registry: 'pypi',
        packageName: 'python-slugify',
        version: '8.0.4',
        venvPath: '/home/juan/.local/share/auroraia/venvs/code-auto-tools/pypi-python-slugify',
        baselineScore: 72,
        toolScore: 100,
        improvement: 28,
        decision: 'kept',
        reason: 'Gain A/B reel mesure.',
        removed: false,
        actions: ['search_pkg', 'install_dep', 'run_tests'],
      },
    ],
  } as const
}

describe('codeToolingLoop registry resolver', () => {
  test('construit les URLs allow-list pour npm, PyPI, crates et Maven', () => {
    assert.equal(buildToolRegistryLookupUrl('npm', 'react'), 'https://registry.npmjs.org/react')
    assert.equal(buildToolRegistryLookupUrl('pypi', 'flask'), 'https://pypi.org/pypi/flask/json')
    assert.equal(buildToolRegistryLookupUrl('crates', 'serde'), 'https://crates.io/api/v1/crates/serde')
    assert.match(
      buildToolRegistryLookupUrl('maven', 'org.junit.jupiter:junit-jupiter'),
      /^https:\/\/search\.maven\.org\/solrsearch\/select\?/,
    )
  })

  test('parse la derniere version des quatre registres', () => {
    assert.equal(parseRegistryLatestVersion('npm', { 'dist-tags': { latest: '1.2.3' } }), '1.2.3')
    assert.equal(parseRegistryLatestVersion('pypi', { info: { version: '2.0.0' } }), '2.0.0')
    assert.equal(parseRegistryLatestVersion('crates', { crate: { max_version: '3.1.0' } }), '3.1.0')
    assert.equal(parseRegistryLatestVersion('maven', { response: { docs: [{ latestVersion: '5.10.2' }] } }), '5.10.2')
  })

  test('resolveToolPackageVersion utilise fetch injectable', async () => {
    const version = await resolveToolPackageVersion({
      registry: 'pypi',
      packageName: 'python-slugify',
      fetchImpl: async (input) => {
        assert.equal(String(input), 'https://pypi.org/pypi/python-slugify/json')
        return new Response(JSON.stringify({ info: { version: '8.0.4' } }), { status: 200 })
      },
    })
    assert.equal(version, '8.0.4')
  })
})

describe('codeToolingLoop correction selection', () => {
  test('detecte un plateau sur trois scores plats', () => {
    assert.equal(detectToolingPlateau([pass(40, 1), pass(42, 2), pass(41, 3)]), true)
    assert.equal(detectToolingPlateau([pass(20, 1), pass(60, 2), pass(90, 3)]), false)
  })

  test('selectionne python-slugify pour une limite Python slug Unicode', () => {
    const candidate = selectToolingCandidateForCorrection({
      errorCategories: ['import_missing'],
      failingOutputs: ['ModuleNotFoundError: No module named slugify while normalizing accents'],
      intent: pythonIntent(),
    })
    assert.equal(candidate?.registry, 'pypi')
    assert.equal(candidate?.packageName, 'python-slugify')
    assert.equal(candidate?.scenario, 'slugify_gain')
  })
})

describe('codeToolingLoop bridge contract', () => {
  test('valide et resume un rapport A/B', () => {
    const sample = report()
    assert.equal(isCodeToolingEvalReport(sample), true)
    assert.match(summarizeToolingEval(sample), /1 outil\(s\) conserve/)
    assert.match(formatToolingReportForCorrection(sample), /A\/B 72->100/)
    assert.ok(!sample.venvRoot.includes('/application/.venv'))
  })

  test('poste vers /api/code/tooling-eval avec timeout borne', async () => {
    let body: any = null
    const result = await runCodeToolingEval({
      bridgeUrl: 'http://127.0.0.1:3001',
      candidates: [{
        id: 'pypi-python-slugify',
        registry: 'pypi',
        packageName: 'python-slugify',
        version: '8.0.4',
        scenario: 'slugify_gain',
        reason: 'test',
      }],
      timeoutMs: 12345,
      fetchImpl: async (input, init) => {
        assert.equal(String(input), 'http://127.0.0.1:3001/api/code/tooling-eval')
        body = JSON.parse(String(init?.body))
        return new Response(JSON.stringify({ ok: true, report: report() }), { status: 200 })
      },
    })
    assert.equal(result.candidates[0].decision, 'kept')
    assert.equal(body.timeoutMs, 12345)
    assert.equal(body.candidates[0].packageName, 'python-slugify')
  })
})
