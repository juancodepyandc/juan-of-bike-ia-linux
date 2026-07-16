import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  consumeCodeStreamNdjson,
  streamCodeGenerationFromBridge,
} from '../services/codeBridgeStreamClient.ts'
import { serializeCodeStreamEvent, buildCodeStreamPhaseEvent, buildCodeStreamDoneEvent } from '../services/codeStreamEvents.ts'

function bodyFromChunks(chunks: string[]) {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

describe('codeBridgeStreamClient', () => {
  test('consomme un flux NDJSON fragmente en evenements types', async () => {
    const phase = buildCodeStreamPhaseEvent({
      runId: 1,
      sequence: 1,
      timestamp: 10,
      phase: 'planning',
      message: 'Plan',
      progress: 10,
    })
    const done = buildCodeStreamDoneEvent({
      runId: 1,
      sequence: 2,
      timestamp: 11,
      files: [],
      finalScore: 0,
      totalAttempts: 1,
      notes: 'ok',
    })
    const received = []
    const payload = serializeCodeStreamEvent(phase) + serializeCodeStreamEvent(done)

    await consumeCodeStreamNdjson(bodyFromChunks([payload.slice(0, 21), payload.slice(21)]), (event) => {
      received.push(event.kind)
    })

    assert.deepEqual(received, ['phase', 'done'])
  })

  test('poste sur /api/code/generate/stream et relaie les evenements', async () => {
    const event = buildCodeStreamPhaseEvent({
      runId: 3,
      sequence: 1,
      timestamp: 12,
      phase: 'generation',
      message: 'Generation',
      progress: 40,
    })
    let requestUrl = ''
    let requestBody = ''
    const fetchImpl = async (url: RequestInfo | URL, init?: RequestInit) => {
      requestUrl = String(url)
      requestBody = String(init?.body ?? '')
      return new Response(bodyFromChunks([serializeCodeStreamEvent(event)]), { status: 200 })
    }
    const received = []

    await streamCodeGenerationFromBridge({
      prompt: 'cree une app',
      model: 'qwen3-coder:30b',
      bridgeUrl: 'http://bridge',
      fetchImpl,
      onEvent: (streamEvent) => received.push(streamEvent.kind),
    })

    assert.equal(requestUrl, 'http://bridge/api/code/generate/stream')
    assert.deepEqual(JSON.parse(requestBody), { prompt: 'cree une app', model: 'qwen3-coder:30b' })
    assert.deepEqual(received, ['phase'])
  })

  test('rejette une ligne non conforme au schema stream', async () => {
    await assert.rejects(
      consumeCodeStreamNdjson(bodyFromChunks(['{"kind":"phase"}\n']), () => {}),
      /Evenement Code stream invalide/,
    )
  })
})
