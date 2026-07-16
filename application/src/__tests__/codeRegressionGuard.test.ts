import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import {
  compareCodeCapabilities,
  formatCodeRegressionGuardReport,
  inspectCodePatchRegression,
  snapshotCodeCapabilities,
  type CodeRegressionViolationKind,
} from '../services/codeRegressionGuard.ts'

function baselineFiles(): CodeFile[] {
  return [
    {
      name: 'package.json',
      language: 'json',
      content: JSON.stringify({
        scripts: {
          build: 'tsc -p tsconfig.json',
          test: 'node --test tests/api.test.js',
        },
      }),
    },
    {
      name: 'src/api.ts',
      language: 'ts',
      content: [
        'export function listUsers() { return [] }',
        'export const health = "ok"',
        'app.get("/api/users", listUsers)',
        'app.post("/api/users", (req, res) => res.end())',
      ].join('\n'),
    },
    {
      name: 'src/billing.ts',
      language: 'ts',
      content: 'export function invoiceTotal(items) { return items.length }',
    },
    {
      name: 'tests/api.test.ts',
      language: 'ts',
      content: 'import { listUsers } from "../src/api"; test("users", () => listUsers())',
    },
  ]
}

describe('codeRegressionGuard', () => {
  test('snapshot extrait scripts, exports, endpoints et tests', () => {
    const snapshot = snapshotCodeCapabilities(baselineFiles())

    assert.deepEqual(Object.keys(snapshot.packageScripts).sort(), [
      'package.json#build',
      'package.json#test',
    ])
    assert.deepEqual(snapshot.exportsByFile['src/api.ts'], ['health', 'listUsers'])
    assert.deepEqual(snapshot.endpointsByFile['src/api.ts'], [
      'GET /api/users',
      'POST /api/users',
    ])
    assert.deepEqual(snapshot.testFiles, ['tests/api.test.ts'])
  })

  test('accepte un patch cible qui preserve les capacites', () => {
    const before = baselineFiles()
    const after = before.map((file) => file.name === 'src/billing.ts'
      ? { ...file, content: 'export function invoiceTotal(items) { return items.reduce((sum, item) => sum + item.price, 0) }' }
      : file)

    const report = inspectCodePatchRegression(before, after)

    assert.equal(report.ok, true)
    assert.equal(formatCodeRegressionGuardReport(report), 'Aucune regression comportementale detectee.')
  })

  test('refuse une correction qui supprime capacites, tests et scripts', () => {
    const before = baselineFiles()
    const after: CodeFile[] = [
      {
        name: 'package.json',
        language: 'json',
        content: JSON.stringify({ scripts: { build: 'tsc -p tsconfig.json' } }),
      },
      {
        name: 'src/api.ts',
        language: 'ts',
        content: 'export const health = "ok"',
      },
      {
        name: 'src/billing.ts',
        language: 'ts',
        content: '',
      },
    ]

    const report = compareCodeCapabilities(
      snapshotCodeCapabilities(before),
      snapshotCodeCapabilities(after),
    )
    const kinds = report.violations.map((violation) => violation.kind)

    assert.equal(report.ok, false)
    assert.ok(kinds.includes('removed_test'))
    assert.ok(kinds.includes('removed_script'))
    assert.ok(kinds.includes('removed_export'))
    assert.ok(kinds.includes('removed_endpoint'))
    assert.ok(kinds.includes('emptied_file'))
    assert.match(formatCodeRegressionGuardReport(report), /Regression refusee/)
  })

  test('detecte une chute de taille fonctionnelle sur projet multi-fichiers', () => {
    const longSource = 'export const value = "' + 'x'.repeat(400) + '"'
    const before: CodeFile[] = Array.from({ length: 4 }, (_, index) => ({
      name: `src/feature${index}.ts`,
      language: 'ts',
      content: `${longSource}\nexport function feature${index}(){ return value }`,
    }))
    const after: CodeFile[] = [
      { name: 'src/feature0.ts', language: 'ts', content: 'export const value = "ok"' },
    ]

    const report = inspectCodePatchRegression(before, after)
    const kinds = report.violations.map((violation) => violation.kind)

    assert.ok(kinds.includes('source_file_drop'))
    assert.ok(kinds.includes('source_size_drop'))
  })
})

type RegressionCase = {
  name: string
  before: CodeFile[]
  after: CodeFile[]
  expectedKind: CodeRegressionViolationKind | null
}

const largeSources = Array.from({ length: 4 }, (_, index): CodeFile => ({
  name: `src/large-${index}.ts`,
  language: 'ts',
  content: `export function feature${index}() { return "${'x'.repeat(400)}" }`,
}))

const regressionCases: RegressionCase[] = [
  {
    name: 'detecte un fichier retire',
    before: baselineFiles(),
    after: baselineFiles().filter((file) => file.name !== 'src/billing.ts'),
    expectedKind: 'removed_file',
  },
  {
    name: 'detecte un fichier vide',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/billing.ts' ? { ...file, content: '' } : file),
    expectedKind: 'emptied_file',
  },
  {
    name: 'detecte un test retire',
    before: baselineFiles(),
    after: baselineFiles().filter((file) => file.name !== 'tests/api.test.ts'),
    expectedKind: 'removed_test',
  },
  {
    name: 'detecte le script build retire',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'package.json'
      ? { ...file, content: JSON.stringify({ scripts: { test: 'node --test tests/api.test.js' } }) }
      : file),
    expectedKind: 'removed_script',
  },
  {
    name: 'detecte le script test retire',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'package.json'
      ? { ...file, content: JSON.stringify({ scripts: { build: 'tsc -p tsconfig.json' } }) }
      : file),
    expectedKind: 'removed_script',
  },
  {
    name: 'detecte une fonction exportee retiree',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/api.ts'
      ? { ...file, content: file.content.replace('export function listUsers()', 'function listUsers()') }
      : file),
    expectedKind: 'removed_export',
  },
  {
    name: 'detecte une constante exportee retiree',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/api.ts'
      ? { ...file, content: file.content.replace('export const health', 'const health') }
      : file),
    expectedKind: 'removed_export',
  },
  {
    name: 'detecte une route GET retiree',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/api.ts'
      ? { ...file, content: file.content.replace('app.get("/api/users", listUsers)', '') }
      : file),
    expectedKind: 'removed_endpoint',
  },
  {
    name: 'detecte une route POST retiree',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/api.ts'
      ? { ...file, content: file.content.replace('app.post("/api/users", (req, res) => res.end())', '') }
      : file),
    expectedKind: 'removed_endpoint',
  },
  {
    name: 'detecte une chute du nombre de sources',
    before: largeSources,
    after: largeSources.slice(0, 1),
    expectedKind: 'source_file_drop',
  },
  {
    name: 'detecte une chute du volume fonctionnel',
    before: largeSources,
    after: largeSources.map((file, index) => ({ ...file, content: `export const value${index} = ${index}` })),
    expectedKind: 'source_size_drop',
  },
  {
    name: 'accepte un fichier ajoute',
    before: baselineFiles(),
    after: [...baselineFiles(), { name: 'src/new.ts', language: 'ts', content: 'export const added = true' }],
    expectedKind: null,
  },
  {
    name: 'accepte une implementation enrichie',
    before: baselineFiles(),
    after: baselineFiles().map((file) => file.name === 'src/billing.ts'
      ? { ...file, content: `${file.content}\nexport function invoiceTax() { return 0 }` }
      : file),
    expectedKind: null,
  },
  {
    name: 'normalise la casse des chemins',
    before: [{ name: 'SRC/API.TS', language: 'ts', content: 'export const ok = true' }],
    after: [{ name: 'src/api.ts', language: 'ts', content: 'export const ok = true' }],
    expectedKind: null,
  },
  {
    name: 'normalise les separateurs Windows sans produire d artefact Windows',
    before: [{ name: 'src\\api.ts', language: 'ts', content: 'export const ok = true' }],
    after: [{ name: 'src/api.ts', language: 'ts', content: 'export const ok = true' }],
    expectedKind: null,
  },
  {
    name: 'detecte une route Next retiree',
    before: [{ name: 'app/api/users/route.ts', language: 'ts', content: 'export function GET() { return Response.json([]) }' }],
    after: [{ name: 'app/api/users/route.ts', language: 'ts', content: 'export const helper = true' }],
    expectedKind: 'removed_endpoint',
  },
  {
    name: 'detecte une route FastAPI retiree',
    before: [{ name: 'api.py', language: 'py', content: '@app.get("/health")\ndef health(): return {"ok": True}' }],
    after: [{ name: 'api.py', language: 'py', content: 'def health(): return {"ok": True}' }],
    expectedKind: 'removed_endpoint',
  },
  {
    name: 'detecte un export CommonJS retire',
    before: [{ name: 'index.js', language: 'js', content: 'module.exports.run = () => true' }],
    after: [{ name: 'index.js', language: 'js', content: 'const run = () => true' }],
    expectedKind: 'removed_export',
  },
]

describe('codeRegressionGuard cas de non-regression migres', () => {
  for (const sample of regressionCases) {
    test(sample.name, () => {
      const report = inspectCodePatchRegression(sample.before, sample.after)
      if (sample.expectedKind === null) {
        assert.equal(report.ok, true, formatCodeRegressionGuardReport(report))
      } else {
        assert.ok(
          report.violations.some((violation) => violation.kind === sample.expectedKind),
          JSON.stringify(report.violations),
        )
      }
    })
  }
})
