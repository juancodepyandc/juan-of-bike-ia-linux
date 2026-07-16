import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import { executeCodeGenerationQueue } from '../services/codeGenerationExecutor.ts'
import { buildGenerationQueueFromArchitecturePlan } from '../services/codeGenerationQueue.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function nextMetaFactory() {
  let sequence = 0
  return () => ({ runId: 11, sequence: ++sequence, timestamp: 1_700_000_000_000 + sequence })
}

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, content, language }
}

function queue() {
  const parsed = buildGenerationQueueFromArchitecturePlan(JSON.stringify({
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: 'Projet React avec executor WS3 fichier par fichier.',
    stack: {
      runtime: 'node',
      packageManager: 'npm',
      languages: ['TypeScript'],
      frameworks: ['React'],
      dependencies: [],
      scripts: [{ name: 'build', command: 'npm run build', purpose: 'validation' }],
    },
    files: [
      { path: 'package.json', role: 'manifest', language: 'json', required: true, imports: [], exports: [], notes: [] },
      { path: 'src/App.tsx', role: 'app', language: 'tsx', required: true, imports: [], exports: ['App'], notes: [] },
      { path: 'src/Optional.ts', role: 'bonus', language: 'ts', required: false, imports: [], exports: [], notes: [] },
    ],
    dataFlow: ['user -> ui'],
    execution: {
      install: ['npm install'],
      dev: ['npm run dev'],
      build: ['npm run build'],
      test: ['npm run build'],
      preview: 'vite',
    },
    generationOrder: ['package.json', 'src/App.tsx', 'src/Optional.ts'],
    validation: ['build vert', 'preview visible'],
    risks: [{ risk: 'fichier manquant', mitigation: 'executor queue' }],
    design: { palette: ['oklch'], typography: ['Inter'], ux: ['dense'], responsive: ['mobile'] },
  }))
  assert.ok(parsed)
  return parsed
}

describe('codeGenerationExecutor', () => {
  test('consomme la queue architecte fichier par fichier et emet file.written', async () => {
    const seen: string[] = []
    const result = await executeCodeGenerationQueue({
      queue: queue(),
      nextMeta: nextMetaFactory(),
      includeFileContentInEvents: true,
      produceActions: async ({ item }) => [
        {
          kind: 'write_file',
          path: item.path,
          language: item.language ?? undefined,
          content: item.path === 'package.json' ? '{"scripts":{"build":"vite build"}}' : `// ${item.path}`,
        },
      ],
      onEvent: (event) => seen.push(event.kind),
    })

    assert.equal(result.ok, true)
    assert.equal(result.completedItems, 3)
    assert.deepEqual(result.files.map((entry) => entry.name), ['package.json', 'src/App.tsx', 'src/Optional.ts'])
    assert.equal(result.events.filter((event) => event.kind === 'file.written').length, 3)
    assert.equal(result.events.at(-1)?.kind, 'done')
    assert.equal(seen.includes('file.written'), true)
  })

  test('stoppe sur un fichier requis non produit', async () => {
    const result = await executeCodeGenerationQueue({
      queue: queue(),
      nextMeta: nextMetaFactory(),
      produceActions: async ({ item }) => item.path === 'package.json'
        ? [{ kind: 'write_file', path: item.path, content: '{}' }]
        : [],
    })

    assert.equal(result.ok, false)
    assert.equal(result.error, 'required_item_actions_empty')
    assert.equal(result.failedItem?.path, 'src/App.tsx')
    assert.equal(result.events.at(-1)?.kind, 'error')
    assert.equal(result.files.some((entry) => entry.name === 'src/App.tsx'), false)
  })

  test('laisse passer un echec optionnel sans perdre les fichiers deja ecrits', async () => {
    const result = await executeCodeGenerationQueue({
      queue: queue(),
      nextMeta: nextMetaFactory(),
      initialFiles: [file('src/App.tsx', 'export function App() { return null }', 'tsx')],
      produceActions: async ({ item }) => {
        if (item.path === 'package.json') return [{ kind: 'write_file', path: item.path, content: '{}' }]
        if (item.path === 'src/App.tsx') return []
        return [{ kind: 'apply_patch', path: item.path, search: 'missing', replace: 'x' }]
      },
    })

    assert.equal(result.ok, true)
    assert.equal(result.toolResults.at(-1)?.result.ok, false)
    assert.equal(result.files.some((entry) => entry.name === 'package.json'), true)
    assert.equal(result.files.find((entry) => entry.name === 'src/App.tsx')?.content.includes('App'), true)
  })
})
