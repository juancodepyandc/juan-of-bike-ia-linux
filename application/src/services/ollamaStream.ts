export interface OllamaStreamFrame {
  response?: string
  message?: { content?: string; thinking?: string }
  done?: boolean
  error?: string
}

/** Read complete NDJSON frames, including the final line without a newline. */
export async function readOllamaStream(
  body: ReadableStream<Uint8Array>,
  onFrame: (frame: OllamaStreamFrame) => void,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let buffer = ''
  const consume = (line: string): boolean => {
    if (!line.trim()) return false
    const frame = JSON.parse(line) as OllamaStreamFrame
    if (!frame || typeof frame !== 'object' || Array.isArray(frame)) {
      throw new Error('Ollama: trame de réponse invalide')
    }
    if (frame.error) throw new Error(`Ollama: ${frame.error}`)
    onFrame(frame)
    return frame.done === true
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      let newline = buffer.indexOf('\n')
      while (newline >= 0) {
        const line = buffer.slice(0, newline)
        buffer = buffer.slice(newline + 1)
        if (consume(line)) return
        newline = buffer.indexOf('\n')
      }
      if (done) {
        if (consume(buffer)) return
        throw new Error('Ollama: flux interrompu avant la fin de la réponse')
      }
    }
  } finally {
    try { await reader.cancel() } catch { /* The transport may already be closed. */ }
    reader.releaseLock()
  }
}
