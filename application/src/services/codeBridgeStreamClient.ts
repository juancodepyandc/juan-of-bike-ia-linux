import { getBridgeUrl } from '../utils/runtime.ts'
import {
  parseCodeStreamEventLine,
  type CodeStreamEvent,
} from './codeStreamEvents.ts'

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeBridgeStreamRequest = {
  prompt: string
  model: string
  signal?: AbortSignal
  bridgeUrl?: string
  fetchImpl?: FetchLike
  onEvent: (event: CodeStreamEvent) => void | Promise<void>
}

export async function consumeCodeStreamNdjson(
  body: Pick<ReadableStream<Uint8Array>, 'getReader'>,
  onEvent: (event: CodeStreamEvent) => void | Promise<void>,
) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  async function consumeLine(line: string) {
    if (!line.trim()) return
    const event = parseCodeStreamEventLine(line)
    if (!event) {
      throw new Error(`Evenement Code stream invalide: ${line.slice(0, 180)}`)
    }
    await onEvent(event)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let lineBreak = buffer.indexOf('\n')
    while (lineBreak >= 0) {
      await consumeLine(buffer.slice(0, lineBreak))
      buffer = buffer.slice(lineBreak + 1)
      lineBreak = buffer.indexOf('\n')
    }
  }

  buffer += decoder.decode()
  await consumeLine(buffer)
}

export async function streamCodeGenerationFromBridge({
  prompt,
  model,
  signal,
  bridgeUrl = getBridgeUrl(),
  fetchImpl = globalThis.fetch.bind(globalThis),
  onEvent,
}: CodeBridgeStreamRequest) {
  if (!prompt.trim()) throw new Error('prompt requis')
  const response = await fetchImpl(`${bridgeUrl}/api/code/generate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, model }),
    signal,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`Bridge Code stream HTTP ${response.status}${text ? `: ${text.slice(0, 240)}` : ''}`)
  }
  if (!response.body) throw new Error('Bridge Code stream sans corps lisible')

  await consumeCodeStreamNdjson(response.body, onEvent)
}
