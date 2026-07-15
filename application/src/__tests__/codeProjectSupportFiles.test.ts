import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import { upsertProjectSupportFilesForTest } from '../services/codeProjectSupportFiles.ts'

describe('codeProjectSupportFiles', () => {
  test('ajoute les supports attendus pour une SPA Vite', () => {
    const intent = {
      projectType: 'spa_react',
      devCommand: 'npm run dev',
      buildCommand: 'npm run build',
      needsDevServer: true,
      needsBundling: true,
    } as unknown as CodeIntent

    const files = upsertProjectSupportFilesForTest([
      { name: 'package.json', language: 'json', content: '{"scripts":{"dev":"vite"},"dependencies":{"@vitejs/plugin-react":"^5.1.2","vite":"^8.1.3"}}' },
      { name: 'src/main.tsx', language: 'typescript', content: 'import "./App";' },
      { name: 'module-1.txt', language: 'text', content: 'synthetic fallback' },
      { name: 'lancement.bat', language: 'batch', content: '@echo off' },
    ], intent, 'cree une app React', null)

    const names = files.map((file) => file.name).sort()
    assert.ok(names.includes('index.html'))
    assert.ok(names.includes('vite.config.ts'))
    assert.ok(names.includes('README.md'))
    assert.ok(names.includes('start.sh'))
    assert.equal(names.includes('module-1.txt'), false)
    assert.equal(names.includes('lancement.bat'), false)
  })
})
