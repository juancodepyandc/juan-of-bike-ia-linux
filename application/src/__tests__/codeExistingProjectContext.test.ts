import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import { buildExistingProjectPatchContext } from '../services/codeExistingProjectContext.ts'

describe('codeExistingProjectContext', () => {
  test('formate le contexte legacy avec portee WS5 et sans envoyer les fichiers proteges', () => {
    const files: CodeFile[] = [
      { name: 'src/billing/pricing.ts', language: 'ts', content: 'export const currency = "EUR"' },
      { name: 'src/auth/login.ts', language: 'ts', content: 'PROTECTED_LOGIN_CONTENT '.repeat(400) },
      { name: 'docs/notes.md', language: 'markdown', content: 'PROTECTED_DOC_CONTENT '.repeat(400) },
    ]
    const context = buildExistingProjectPatchContext({
      prompt: 'Passe la devise de facturation en USD',
      existingFiles: files,
      maxChars: 3000,
    })

    assert.match(context, /PORTEE PATCH INCREMENTAL WS5/)
    assert.match(context, /src\/billing\/pricing\.ts/)
    assert.match(context, /src\/auth\/login\.ts/)
    assert.doesNotMatch(context, /PROTECTED_LOGIN_CONTENT/)
    assert.doesNotMatch(context, /PROTECTED_DOC_CONTENT/)
  })
})
