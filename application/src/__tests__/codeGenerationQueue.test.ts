import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import {
  buildGenerationQueueFromArchitecturePlan,
  buildGenerationQueueWithFallback,
  formatGenerationQueueForPrompt,
} from '../services/codeGenerationQueue.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

function plan() {
  return JSON.stringify({
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: 'Application React complete avec file execution fichier par fichier.',
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['TypeScript'],
      frameworks: ['React'],
      dependencies: [{ name: 'react', type: 'runtime', reason: 'ui' }],
      scripts: [{ name: 'build', command: 'npm run build', purpose: 'validation' }],
    },
    files: [
      { path: 'src/App.tsx', role: 'app shell', language: 'tsx', required: true, imports: ['./main'], exports: ['App'], notes: ['UI complete'] },
      { path: 'package.json', role: 'manifest', language: 'json', required: true, imports: [], exports: [], notes: [] },
      { path: 'src/Optional.tsx', role: 'bonus', language: 'tsx', required: false, imports: [], exports: [], notes: [] },
    ],
    dataFlow: ['user -> app -> state'],
    execution: {
      install: ['npm install'],
      dev: ['npm run dev'],
      build: ['npm run build'],
      test: ['npm run build'],
      preview: 'vite',
    },
    generationOrder: ['package.json', './src/App.tsx', 'missing.ts', 'package.json'],
    validation: ['build vert', 'preview visible'],
    risks: [{ risk: 'fichier oublie', mitigation: 'queue contractuelle' }],
    design: { palette: ['oklch'], typography: ['Inter'], ux: ['fluide'], responsive: ['mobile'] },
  })
}

describe('codeGenerationQueue', () => {
  test('derive une file ordonnee depuis generationOrder puis append les fichiers restants', () => {
    const queue = buildGenerationQueueFromArchitecturePlan(plan())

    assert.equal(queue?.requiredCount, 2)
    assert.equal(queue?.optionalCount, 1)
    assert.deepEqual(queue?.items.map((item) => item.path), [
      'package.json',
      'src/App.tsx',
      'src/Optional.tsx',
    ])
    assert.deepEqual(queue?.omittedOrderPaths, ['missing.ts'])
  })

  test('ignore les plans invalides', () => {
    assert.equal(buildGenerationQueueFromArchitecturePlan('### fichiers'), null)
  })

  test('REPLI: un plan non parseable ne fait JAMAIS 0 fichier (fin de plan_without_queue)', () => {
    // Regression: le vrai pipeline echouait fatalement ("Erreur fatale: plan_without_queue")
    // quand qwen3-coder rendait du markdown au lieu du JSON attendu.
    const web = buildGenerationQueueWithFallback('du texte pas du json', { projectType: 'static_web', languages: ['html'] } as unknown as CodeIntent)
    assert.equal(web.usedFallback, true)
    assert.deepEqual(web.queue.items.map((i) => i.path), ['index.html', 'style.css', 'script.js'])
    assert.ok(web.queue.items.every((i) => i.required))

    const react = buildGenerationQueueWithFallback(null, { projectType: 'spa_react', languages: ['TypeScript'] } as unknown as CodeIntent)
    assert.equal(react.usedFallback, true)
    assert.ok(react.queue.items.some((i) => i.path === 'src/App.tsx'))

    const py = buildGenerationQueueWithFallback('', { projectType: 'cli_tool', languages: ['Python'] } as unknown as CodeIntent)
    assert.deepEqual(py.queue.items.map((i) => i.path), ['main.py'])
  })

  test('REPLI: un plan VALIDE est prefere au repli', () => {
    const res = buildGenerationQueueWithFallback(plan(), { projectType: 'spa_react', languages: ['TypeScript'] } as unknown as CodeIntent)
    assert.equal(res.usedFallback, false)
    assert.equal(res.queue.items[0].path, 'package.json')
  })

  test('formate un manifeste exploitable par le futur executeur outil-par-outil', () => {
    const queue = buildGenerationQueueFromArchitecturePlan(plan())
    assert.ok(queue)
    const formatted = formatGenerationQueueForPrompt(queue)

    assert.match(formatted, /FILE-BY-FILE EXECUTION MANIFEST/)
    assert.match(formatted, /1\. package\.json/)
    assert.match(formatted, /2\. src\/App\.tsx/)
    assert.match(formatted, /required=true/)
    assert.match(formatted, /imports: \.\/main/)
    assert.match(formatted, /missing\.ts/)
  })
})
