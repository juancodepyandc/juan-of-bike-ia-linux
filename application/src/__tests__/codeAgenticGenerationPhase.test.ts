import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import { runAgenticGenerationPhase } from '../services/codeAgenticGenerationPhase.ts'
import { parseCodeFiles } from '../services/codeGeneratedFileParser.ts'
import { CODE_GENERATION_ACTION_PROTOCOL_VERSION } from '../services/codeGenerationActionProtocol.ts'

function plan() {
  return JSON.stringify({
    schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
    projectType: 'spa_react',
    summary: 'Application React generee par executor agentique.',
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
    ],
    dataFlow: ['user -> app'],
    execution: {
      install: ['npm install'],
      dev: ['npm run dev'],
      build: ['npm run build'],
      test: ['npm run build'],
      preview: 'vite',
    },
    generationOrder: ['package.json', 'src/App.tsx'],
    validation: ['build vert', 'preview visible'],
    risks: [{ risk: 'missing file', mitigation: 'queue executor' }],
    design: { palette: ['oklch'], typography: ['Inter'], ux: ['complete'], responsive: ['mobile'] },
  })
}

const intent = {
  projectType: 'spa_react',
  complexity: 'complex',
  languages: ['typescript'],
  frameworks: ['react'],
  features: [],
  needsArchitecturePlanning: true,
  assetPlan: {},
} as any

describe('codeAgenticGenerationPhase', () => {
  test('retourne null sans plan architecte exploitable', async () => {
    const result = await runAgenticGenerationPhase({
      prompt: 'demo',
      intent,
      architecturePlan: null,
      existingFiles: [],
      contextImages: [],
      generationModel: 'fake',
      setPhase: () => undefined,
      onToken: () => undefined,
    })

    assert.equal(result, null)
  })

  test('execute une generation agentique et serialise en AURORA_CODE_VFS/1', async () => {
    const updates: number[] = []
    const tokens: string[] = []
    const result = await runAgenticGenerationPhase({
      prompt: 'demo',
      intent,
      architecturePlan: plan(),
      existingFiles: [],
      contextImages: [],
      generationModel: 'fake',
      modelRouting: { installedModels: ['fake'] },
      setPhase: () => undefined,
      onToken: (token) => tokens.push(token),
      onFilesUpdate: (files) => updates.push(files.length),
      chatClient: async (_model, messages) => {
        const body = messages.map((message) => message.content).join('\n')
        const path = body.match(/Fichier cible de cette etape: ([^\n]+)/)?.[1] ?? 'README.md'
        const content = path === 'package.json'
          ? '{"scripts":{"build":"vite build"}}'
          : 'export function App() { return <main>ok</main> }'
        return {
          message: {
            role: 'assistant',
            content: `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"${path}","content":${JSON.stringify(content)}}]`,
          },
        }
      },
    })

    assert.equal(result?.ok, true)
    assert.equal(tokens.length, 1)
    assert.deepEqual(updates, [1, 2])
    assert.deepEqual(parseCodeFiles(result?.content ?? '').map((file) => file.name), ['package.json', 'src/App.tsx'])
  })
})
