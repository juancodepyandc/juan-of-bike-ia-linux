import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { executeCodeGenerationQueue } from '../services/codeGenerationExecutor.ts'
import {
  buildCodeGenerationActionMessages,
  createCodeGenerationLLMActionProducer,
} from '../services/codeGenerationActionProducer.ts'
import type { CodeGenerationQueue, CodeGenerationQueueItem } from '../services/codeGenerationQueue.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import { CODE_GENERATION_ACTION_PROTOCOL_VERSION } from '../services/codeGenerationActionProtocol.ts'

function item(path: string, order: number): CodeGenerationQueueItem {
  return {
    path,
    order,
    required: true,
    role: order === 1 ? 'manifest' : 'app shell',
    language: path.endsWith('.json') ? 'json' : 'tsx',
    imports: path.endsWith('.tsx') ? ['./main'] : [],
    exports: path.endsWith('.tsx') ? ['App'] : [],
    notes: [],
  }
}

function queue(): CodeGenerationQueue {
  const items = [item('package.json', 1), item('src/App.tsx', 2)]
  return { source: 'architecture_plan', items, requiredCount: 2, optionalCount: 0, omittedOrderPaths: [] }
}

function meta() {
  let sequence = 0
  return () => ({ runId: 14, sequence: ++sequence, timestamp: 1_700_000_000_000 + sequence })
}

describe('codeGenerationActionProducer', () => {
  test('construit un contexte cible sans envoyer tout le projet', () => {
    const files: CodeFile[] = [
      { name: 'package.json', language: 'json', content: '{"name":"demo"}' },
      { name: 'src/App.tsx', language: 'tsx', content: 'export function App() { return null }' },
      { name: 'docs/huge.md', language: 'markdown', content: 'NEVER_SEND_FULL_DOC '.repeat(2000) },
    ]
    const messages = buildCodeGenerationActionMessages({
      item: item('src/App.tsx', 2),
      itemIndex: 1,
      queue: queue(),
      files,
      prompt: 'Ameliore app',
      architecturePlan: '{"files":[]}',
      maxFileContextChars: 300,
    })

    const body = messages.map((message) => message.content).join('\n')
    assert.match(body, /AURORA_CODE_ACTIONS\/1/)
    assert.match(body, /PORTEE PATCH INCREMENTAL WS5/)
    assert.match(body, /privilegie apply_patch/i)
    assert.match(body, /src\/App\.tsx/)
    assert.match(body, /package\.json/)
    assert.doesNotMatch(body, /NEVER_SEND_FULL_DOC/)
  })

  test('produit des actions depuis un client LLM injecte', async () => {
    const rawResponses: string[] = []
    const producer = createCodeGenerationLLMActionProducer({
      prompt: 'Cree le projet',
      model: 'fake-coder',
      onRawResponse: ({ raw }) => rawResponses.push(raw),
      chatClient: async (_model, messages) => {
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

    const result = await executeCodeGenerationQueue({
      queue: queue(),
      nextMeta: meta(),
      produceActions: producer,
    })

    assert.equal(result.ok, true)
    assert.deepEqual(result.files.map((file) => file.name), ['package.json', 'src/App.tsx'])
    assert.equal(rawResponses.length, 2)
  })

  test('rejette une reponse LLM hors protocole', async () => {
    const producer = createCodeGenerationLLMActionProducer({
      prompt: 'Cree le projet',
      model: 'fake-coder',
      chatClient: async () => ({ message: { role: 'assistant', content: 'Voici le code...' } }),
    })

    await assert.rejects(
      () => producer({ item: item('src/App.tsx', 1), itemIndex: 0, queue: queue(), files: [] }),
      /action_protocol_invalid:protocol_marker_missing/,
    )
  })

  test('REPLI tolerant: du code BRUT sans protocole est ecrit dans le fichier cible', async () => {
    // qwen3-coder & modeles locaux emettent souvent le code direct (fence) sans
    // le marqueur d actions -> le WS3 echouait a chaque generation. Desormais on
    // ecrit ce code brut dans le fichier cible au lieu d avorter.
    const html = '<!doctype html><html><head><title>Cafe Brume</title></head><body><h1>Bienvenue chez Brume</h1><button>Reserver</button></body></html>'
    const producer = createCodeGenerationLLMActionProducer({
      prompt: 'Cree la landing',
      model: 'qwen3-coder:30b',
      chatClient: async () => ({ message: { role: 'assistant', content: '```html\n' + html + '\n```' } }),
    })
    const actions = await producer({ item: item('index.html', 1), itemIndex: 0, queue: queue(), files: [] })
    assert.equal(actions.length, 1)
    assert.equal(actions[0].kind, 'write_file')
    assert.equal((actions[0] as { path: string }).path, 'index.html')
    assert.match((actions[0] as { content: string }).content, /Cafe Brume/)
  })
})
