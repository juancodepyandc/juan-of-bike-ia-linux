import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import { runAgenticGenerationPhase } from '../services/codeAgenticGenerationPhase.ts'
import { parseCodeFiles } from '../services/codeGeneratedFileParser.ts'
import { CODE_GENERATION_ACTION_PROTOCOL_VERSION } from '../services/codeGenerationActionProtocol.ts'
import { CODE_CLOUD_HIGH_MODEL } from '../config/models.ts'

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
  test('REPLI: sans plan exploitable, utilise une file par defaut (jamais 0 fichier)', async () => {
    // Regression du vrai pipeline: un plan non parseable faisait echouer la
    // generation a 0 fichier ("Erreur fatale: plan_without_queue"). Desormais on
    // retombe sur une file par defaut derivee de l intent.
    const files: string[] = []
    const result = await runAgenticGenerationPhase({
      prompt: 'demo',
      intent,
      architecturePlan: null,
      existingFiles: [],
      contextImages: [],
      generationModel: 'fake',
      modelRouting: { installedModels: ['fake'] },
      setPhase: () => undefined,
      onToken: () => undefined,
      onFilesUpdate: (fs) => { files.length = 0; files.push(...fs.map((f) => f.name)) },
      chatClient: async (_model, messages) => {
        const body = messages.map((m) => m.content).join('\n')
        const path = body.match(/Fichier cible de cette etape: ([^\n]+)/)?.[1] ?? 'index.html'
        return {
          message: {
            role: 'assistant',
            content: `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"${path}","content":"<!doctype html><html><body>ok</body></html>"}]`,
          },
        }
      },
    })

    assert.equal(result?.ok, true)
    // spa_react -> file de repli avec les fichiers d entree React
    assert.ok(files.includes('src/App.tsx'), `attendu src/App.tsx dans ${files.join(',')}`)
    assert.ok((result?.files.length ?? 0) >= 3, 'au moins 3 fichiers produits par le repli')
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

  test('transmet l escalade plateau au modele de chaque action', async () => {
    const models: string[] = []
    const result = await runAgenticGenerationPhase({
      prompt: 'demo en echec repete',
      intent,
      architecturePlan: plan(),
      existingFiles: [],
      contextImages: [],
      generationModel: 'qwen3-coder:30b',
      escalationLevel: 4,
      modelRouting: {
        configuredCodeModel: 'qwen3-coder:30b',
        installedModels: ['qwen3-coder:30b', CODE_CLOUD_HIGH_MODEL],
        // machine costaude: le gros modele cloud tient -> escalade autorisee
        // (garde anti-gel: un poste local le refuserait).
        hardware: { ram_gb: 128, vram_gb: 80 },
        plateau: true,
      },
      setPhase: () => undefined,
      onToken: () => undefined,
      chatClient: async (model, messages) => {
        models.push(model)
        const body = messages.map((message) => message.content).join('\n')
        const path = body.match(/Fichier cible de cette etape: ([^\n]+)/)?.[1] ?? 'README.md'
        return {
          message: {
            role: 'assistant',
            content: `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"${path}","content":"ok"}]`,
          },
        }
      },
    })

    assert.equal(result?.ok, true)
    assert.deepEqual(models, [CODE_CLOUD_HIGH_MODEL, CODE_CLOUD_HIGH_MODEL])
  })
})
