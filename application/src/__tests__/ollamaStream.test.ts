import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readOllamaStream } from '../services/ollamaStream.ts'
import { ollamaChat, ollamaChatStream, ollamaGenerate, comfyuiQueuePrompt } from '../hooks/useTauri.ts'

const encoder = new TextEncoder()
function byteStream(text: string, chunkSize = 1): ReadableStream<Uint8Array> {
  const bytes = encoder.encode(text)
  return new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize))
      controller.close()
    },
  })
}

describe('Ollama NDJSON transport', () => {
  it('preserves split Unicode and a terminal frame without a newline', async () => {
    let text = ''
    const body = byteStream(' \n{"response":"é🙂","done":false}\n{"response":" fin","done":true}')
    await readOllamaStream(body, (frame) => { text += frame.response || '' })
    assert.equal(text, 'é🙂 fin')
    assert.equal(body.locked, false)
  })

  it('rejects model errors delivered in a successful HTTP stream', async () => {
    await assert.rejects(readOllamaStream(byteStream('{"error":"out of memory"}\n'), () => {}), /out of memory/)
  })

  it('rejects truncation and invalid frames', async () => {
    for (const text of ['', '{"response":"partial","done":false}\n', '{"response":', '[]\n', 'null\n']) {
      const body = byteStream(text)
      await assert.rejects(readOllamaStream(body, () => {}))
      assert.equal(body.locked, false)
    }
  })

  it('cancels the underlying stream when the terminal frame arrives', async () => {
    let cancelled = false
    const body = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(encoder.encode('{"done":true}\n')) },
      cancel() { cancelled = true },
    })
    await readOllamaStream(body, () => {})
    assert.equal(cancelled, true)
    assert.equal(body.locked, false)
  })

  it('forwards the generation budget and retains the final response', async (t) => {
    let sent: Record<string, unknown> | undefined
    t.mock.method(globalThis, 'fetch', async (_url: unknown, init: RequestInit) => {
      sent = JSON.parse(String(init.body))
      return new Response(byteStream('{"response":"complet","done":true}'))
    })
    assert.deepEqual(await ollamaGenerate('test', 'prompt', { num_ctx: 4096, num_predict: 0 }), { response: 'complet', done: true })
    assert.deepEqual(sent?.options, { num_ctx: 4096, num_predict: 0 })
  })

  it('honors the chat endpoint and generation budget', async (t) => {
    let endpoint: unknown
    let sent: Record<string, unknown> | undefined
    t.mock.method(globalThis, 'fetch', async (url: unknown, init: RequestInit) => {
      endpoint = url
      sent = JSON.parse(String(init.body))
      return new Response(byteStream('{"message":{"content":"ok"},"done":true}'))
    })
    const result = await ollamaChat('test', [], 0, { baseUrl: 'http://example.invalid:11434/', num_predict: 256 })
    assert.equal(endpoint, 'http://example.invalid:11434/api/chat')
    assert.deepEqual(sent?.options, { temperature: 0, num_predict: 256 })
    assert.equal(result.message.content, 'ok')
  })

  it('never signals successful completion for a broken chat stream', async (t) => {
    let completed = false
    t.mock.method(globalThis, 'fetch', async () => new Response(byteStream('{"error":"model unavailable"}\n')))
    await assert.rejects(ollamaChatStream('test', [], () => {}, () => { completed = true }), /model unavailable/)
    assert.equal(completed, false)
  })

  it('uses a remote endpoint in Tauri without starting a local model', async (t) => {
    const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: { __TAURI_INTERNALS__: {}, location: { hostname: 'localhost' } },
    })
    t.after(() => {
      if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow)
      else Reflect.deleteProperty(globalThis, 'window')
    })
    const urls: string[] = []
    t.mock.method(globalThis, 'fetch', async (url: string) => {
      urls.push(url)
      return new Response(byteStream('{"message":{"content":"remote"},"done":true}'))
    })
    const result = await ollamaChat('remote-model', [], 0, { baseUrl: 'http://example.invalid:11434' })
    assert.equal(result.message.content, 'remote')
    assert.deepEqual(urls, ['http://example.invalid:11434/api/chat'])
  })

  it('delivers thinking tokens from the final frame and completes once', async (t) => {
    let completed = 0
    let thinking = ''
    t.mock.method(globalThis, 'fetch', async () => new Response(byteStream('{"message":{"thinking":"raisonnement"},"done":true}')))
    await ollamaChatStream('test', [], () => {}, () => { completed++ }, { onThinking: (token) => { thinking += token } })
    assert.equal(thinking, 'raisonnement')
    assert.equal(completed, 1)
  })
})

it('routes an audited model through the training bridge without falling back to Ollama', async (t) => {
  const urls: string[] = []
  t.mock.method(globalThis, 'fetch', async (url: unknown) => {
    urls.push(String(url))
    return new Response(byteStream('{"message":{"content":"adaptateur"},"done":true}\n'))
  })
  const result = await ollamaChat('aurora-rl-code:v1', [], 0)
  assert.equal(result.message.content, 'adaptateur')
  assert.equal(urls.length, 1)
  assert.match(urls[0], /(?:proxy\/trained|11435)\/api\/chat$/)
})

it('routes trained text generation through the adapter service', async (t) => {
  const urls: string[] = []
  t.mock.method(globalThis, 'fetch', async (url: unknown) => {
    urls.push(String(url))
    return new Response(byteStream('{"response":"entraîné","done":true}\n'))
  })
  assert.equal((await ollamaGenerate('aurora-rl-code:v1', 'test')).response, 'entraîné')
  assert.equal(urls.length, 1)
  assert.match(urls[0], /(?:proxy\/trained|11435)\/api\/generate$/)
})

it('submits the image graph prepared by the validation service', async (t) => {
  const calls: Array<{ url: string, body: Record<string, unknown> }> = []
  const graph = { audited: { class_type: 'LoraLoaderModelOnly' } }
  t.mock.method(globalThis, 'fetch', async (url: unknown, init: RequestInit) => {
    calls.push({ url: String(url), body: JSON.parse(String(init.body)) })
    return new Response(JSON.stringify(calls.length === 1 ? { workflow: graph } : { prompt_id: 'job' }))
  })
  assert.equal((await comfyuiQueuePrompt({ base: {} })).prompt_id, 'job')
  assert.match(calls[0].url, /api\/training\/image-workflow$/)
  assert.deepEqual(calls[1].body.prompt, graph)
})

it('does not submit an image when its recorded adapter fails validation', async (t) => {
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => {
    calls++
    return new Response('{}', { status: 409 })
  })
  await assert.rejects(comfyuiQueuePrompt({ base: {} }), /Validation/)
  assert.equal(calls, 1)
})
