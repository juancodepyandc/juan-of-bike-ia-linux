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
      { name: 'package.json', language: 'json', content: '{"scripts":{"dev":"vite"},"dependencies":{"@vitejs/plugin-react":"^6","vite":"^8"}}' },
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

  test('le theme injecte utilise la couleur de MARQUE, jamais le violet generique', () => {
    // Regression: une landing "airpods pro 3" (Apple) sortait avec l accent
    // violet aurora 124 92 255 injecte en dur -> aspect template IA. Le theme
    // doit desormais reprendre primaryColor de la marque (#000000 pour Apple).
    const intent = {
      projectType: 'static_web',
      assetPlan: { subject: { source: 'brand', brandProfile: { primaryColor: '#000000' } } },
    } as unknown as CodeIntent
    const [html] = upsertProjectSupportFilesForTest([
      { name: 'index.html', language: 'html', content: '<head></head><body class="bg-accent text-fg flex"></body>' },
    ], intent, 'landing airpods pro 3', null)
    assert.ok(html.content.includes('--c-accent:0 0 0'), 'accent = noir Apple attendu')
    assert.equal(html.content.includes('124 92 255'), false, 'plus aucun violet generique')
  })

  test('sans marque, le theme injecte un neutre professionnel (pas de violet signature)', () => {
    const intent = { projectType: 'static_web' } as unknown as CodeIntent
    const [html] = upsertProjectSupportFilesForTest([
      { name: 'index.html', language: 'html', content: '<head></head><body class="bg-accent flex text-fg"></body>' },
    ], intent, 'une page', null)
    assert.equal(html.content.includes('124 92 255'), false, 'pas de violet-signature par defaut')
    assert.ok(html.content.includes('--c-accent:37 99 235'), 'neutre pro par defaut (#2563eb)')
  })
})
