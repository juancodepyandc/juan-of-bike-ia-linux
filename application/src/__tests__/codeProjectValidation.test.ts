import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import {
  attemptLocalFileRepair,
  isSyntheticFallbackFile,
  validateOutputMatchesIntent,
  validateStructuredFiles,
} from '../services/codeProjectValidation.ts'

function intent(projectType: string): CodeIntent {
  return {
    projectType,
    needsDevServer: projectType.startsWith('spa_'),
    needsBundling: projectType.startsWith('spa_'),
  } as unknown as CodeIntent
}

describe('codeProjectValidation', () => {
  test('detecte les noms synthetiques generes par fallback', () => {
    assert.equal(isSyntheticFallbackFile('bloc-1.html'), true)
    assert.equal(isSyntheticFallbackFile('src/App.tsx'), false)

    const issue = validateOutputMatchesIntent([
      { name: 'bloc-1.html', language: 'html', content: '<main>Fallback generique</main>' },
      { name: 'script-2.js', language: 'javascript', content: 'console.log("fallback")' },
    ], intent('static_web'))

    assert.match(issue ?? '', /noms generiques/)
  })

  test('valide les fichiers machine structures', () => {
    const issue = validateStructuredFiles([
      { name: 'package.json', language: 'json', content: '{"scripts":{"build":"vite"}}' },
    ])

    assert.match(issue ?? '', /champ "name"/)
  })

  test('accepte une page statique executable', () => {
    const issue = validateOutputMatchesIntent([
      {
        name: 'index.html',
        language: 'html',
        content: '<!doctype html><html><body><main><h1>Produit complet</h1><p>Contenu reel et executable.</p></main><script>console.log("ready")</script></body></html>',
      },
    ], intent('static_web'))

    assert.equal(issue, null)
  })

  test('repare localement une incompatibilite TypeScript evidente', () => {
    const sandboxResult: CodeSandboxResult = {
      ok: false,
      rootPath: '/tmp/project',
      summary: 'tsc failed',
      question: null,
      detectedLanguage: 'node',
      steps: [
        {
          label: 'TypeScript',
          command: 'npm run build',
          ok: false,
          output: 'error TS1139: Type parameter declaration expected in @types/three',
        },
      ],
    }

    const repair = attemptLocalFileRepair([
      {
        name: 'package.json',
        language: 'json',
        content: `${JSON.stringify({
          name: 'demo',
          devDependencies: { typescript: '^4.9.5' },
        }, null, 2)}\n`,
      },
    ], sandboxResult)

    assert.ok(repair)
    const manifest = JSON.parse(repair.files.find((file) => file.name === 'package.json')!.content)
    assert.equal(manifest.devDependencies.typescript, '^6')
  })
})
