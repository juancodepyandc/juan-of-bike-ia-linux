import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import {
  compareCodeCapabilities,
  formatCodeRegressionGuardReport,
  inspectCodePatchRegression,
  snapshotCodeCapabilities,
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
