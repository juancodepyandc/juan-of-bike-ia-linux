import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import { executeCodeGenerationToolSequence } from '../services/codeGenerationTools.ts'
import {
  assertCodePatchNonRegression,
  buildCodeIncrementalPatchScope,
  formatCodeIncrementalPatchScope,
} from '../services/codeIncrementalPatchScope.ts'

function files(): CodeFile[] {
  return [
    { name: 'src/billing/pricing.ts', language: 'ts', content: 'export const currency = "EUR"\nexport const invoices = []' },
    { name: 'src/auth/login.ts', language: 'ts', content: 'export function login() { return true }' },
    { name: 'src/profile/Profile.tsx', language: 'tsx', content: 'export function Profile() { return null }' },
  ]
}

describe('codeIncrementalPatchScope', () => {
  test('selectionne les fichiers cibles et protege les fichiers hors sujet', () => {
    const scope = buildCodeIncrementalPatchScope({
      prompt: 'Change la devise de facturation invoices en USD',
      files: files(),
      maxTargetFiles: 2,
    })
    const formatted = formatCodeIncrementalPatchScope(scope)

    assert.deepEqual(scope.targetFiles, ['src/billing/pricing.ts'])
    assert.ok(scope.protectedFiles.includes('src/auth/login.ts'))
    assert.match(formatted, /Fichiers cibles autorises/)
  })

  test('prouve la non-regression des fichiers proteges apres apply_patch cible', async () => {
    const before = files()
    const scope = buildCodeIncrementalPatchScope({
      prompt: 'Change la devise de facturation invoices en USD',
      files: before,
      maxTargetFiles: 2,
    })
    const { files: after } = await executeCodeGenerationToolSequence(before, [
      { kind: 'apply_patch', path: 'src/billing/pricing.ts', search: '"EUR"', replace: '"USD"' },
    ])
    const guarded = assertCodePatchNonRegression({ before, after, scope })

    assert.equal(after.find((file) => file.name === 'src/billing/pricing.ts')?.content.includes('"USD"'), true)
    assert.equal(guarded.ok, true)
  })

  test('detecte une regression sur un fichier protege', async () => {
    const before = files()
    const scope = buildCodeIncrementalPatchScope({
      prompt: 'Change la devise de facturation invoices en USD',
      files: before,
      maxTargetFiles: 1,
    })
    const { files: after } = await executeCodeGenerationToolSequence(before, [
      { kind: 'apply_patch', path: 'src/auth/login.ts', search: 'true', replace: 'false' },
    ])
    const guarded = assertCodePatchNonRegression({ before, after, scope })

    assert.equal(guarded.ok, false)
    assert.deepEqual(guarded.errors, ['protected_file_modified:src/auth/login.ts'])
  })
})
