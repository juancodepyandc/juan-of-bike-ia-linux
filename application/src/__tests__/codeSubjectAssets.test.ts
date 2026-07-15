import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import { applySubjectImagePlaceholder, mergeExistingWithUpdates } from '../services/codeSubjectAssets.ts'

describe('codeSubjectAssets', () => {
  test('remplace les placeholders sujet par les images resolues', () => {
    const intent = {
      assetPlan: { subject: { canonical: 'Pepsi' } },
      __subjectImageDataUrls: ['data:image/png;base64,ONE', 'data:image/png;base64,TWO'],
    } as unknown as CodeIntent

    const next = applySubjectImagePlaceholder(
      '<img src="PLACEHOLDER_SUBJECT_IMG"><img src="PLACEHOLDER_SUBJECT_IMG_2">',
      intent,
    )

    assert.equal(next.includes('PLACEHOLDER_SUBJECT_IMG'), false)
    assert.equal(next, '<img src="data:image/png;base64,ONE"><img src="data:image/png;base64,TWO">')
  })

  test('garde les fichiers existants non remplaces lors d un follow-up', () => {
    const merged = mergeExistingWithUpdates(
      [
        { name: './src/App.tsx', language: 'typescript', content: 'old app' },
        { name: 'README.md', language: 'markdown', content: 'keep' },
      ],
      [
        { name: 'src/app.tsx', language: 'typescript', content: 'new app' },
        { name: 'src/theme.css', language: 'css', content: ':root{}' },
      ],
    )

    assert.deepEqual(merged.map((file) => file.name), ['README.md', 'src/app.tsx', 'src/theme.css'])
    assert.equal(merged[1].content, 'new app')
  })
})
