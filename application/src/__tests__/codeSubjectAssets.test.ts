import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { mergeExistingWithUpdates } from '../services/codeSubjectAssets.ts'

describe('codeSubjectAssets', () => {
  test('la derniere mise a jour gagne aussi avec chemins Windows normalises', () => {
    const merged = mergeExistingWithUpdates(
      [{ name: 'src\\App.tsx', language: 'typescript', content: 'ancien' }],
      [{ name: 'src/App.tsx', language: 'typescript', content: 'nouveau' }],
    )
    assert.deepEqual(merged, [{ name: 'src/App.tsx', language: 'typescript', content: 'nouveau' }])
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
