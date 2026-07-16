import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import {
  buildGenerationQueueFromArchitecturePlan,
  formatGenerationQueueForPrompt,
} from '../services/codeGenerationQueue.ts'

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
