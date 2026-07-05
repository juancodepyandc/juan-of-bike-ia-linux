type ComfyQueueResult = {
  prompt_id?: string
  error?: {
    message?: string
    details?: string
    type?: string
    extra_info?: Record<string, unknown>
  }
  node_errors?: Record<string, {
    class_type?: string
    errors?: Array<{
      type?: string
      message?: string
      details?: string
      extra_info?: Record<string, unknown>
    }>
  }>
}

type ComfyHistoryEntry = {
  status?: {
    completed?: boolean
    status_str?: string
    messages?: unknown[]
  }
  outputs?: Record<string, {
    images?: Array<{
      filename: string
      subfolder?: string
      type?: string
    }>
  }>
}

/** Extrait un message lisible d'un objet ComfyUI (event payload, error, etc.) */
function stringifyComfyObject(obj: unknown): string {
  if (typeof obj === 'string') return obj
  if (typeof obj !== 'object' || obj === null) return String(obj)

  const o = obj as Record<string, unknown>

  // execution_error payload → extraire exception_message
  if (o.exception_message) {
    const nodeType = o.node_type ? `[${o.node_type}] ` : ''
    return `${nodeType}${o.exception_message}`
  }

  // Objet avec message/error/details
  for (const key of ['message', 'error', 'details', 'detail']) {
    if (typeof o[key] === 'string' && o[key]) return o[key] as string
  }

  // Derniere chance: JSON compact (max 200 chars)
  try {
    const json = JSON.stringify(obj)
    return json.length > 200 ? json.slice(0, 200) + '...' : json
  } catch {
    return '[objet non serialisable]'
  }
}

function collectNodeErrors(nodeErrors?: ComfyQueueResult['node_errors']) {
  if (!nodeErrors) return []

  const details: string[] = []
  for (const nodeId of Object.keys(nodeErrors)) {
    const nodeError = nodeErrors[nodeId]
    const nodeLabel = nodeError.class_type || `node ${nodeId}`
    for (const error of nodeError.errors || []) {
      const message = error.details || error.message
      if (message) details.push(`${nodeLabel}: ${message}`)
    }
  }

  return [...new Set(details)]
}

export function extractComfyPromptId(queueResult: ComfyQueueResult) {
  if (queueResult?.prompt_id) {
    return queueResult.prompt_id
  }

  const nodeErrors = collectNodeErrors(queueResult?.node_errors)
  const rootMessage = [
    queueResult?.error?.message,
    queueResult?.error?.details,
  ].filter(Boolean).join(' ')

  if (nodeErrors.length > 0) {
    throw new Error(`ComfyUI a refuse le workflow: ${nodeErrors.slice(0, 3).join(' | ')}`)
  }

  if (rootMessage) {
    throw new Error(`ComfyUI a refuse le workflow: ${rootMessage}`)
  }

  throw new Error('ComfyUI n a pas retourne de prompt_id.')
}

/**
 * Extrait un message d'erreur lisible depuis l'historique ComfyUI.
 * Les messages sont des tuples ["event_type", payload] :
 *   - ["execution_start", {prompt_id}]          → ignoré
 *   - ["execution_cached", {nodes: [...]}]      → ignoré
 *   - ["execution_error", {exception_message}]  → message d'erreur
 *   - ["execution_interrupted", {}]             → message d'erreur
 */
export function extractComfyHistoryFailure(entry: ComfyHistoryEntry): string | null {
  const messages = entry?.status?.messages
  if (!Array.isArray(messages) || messages.length === 0) {
    return entry?.status?.status_str === 'error'
      ? 'ComfyUI a signale une erreur pendant le rendu.'
      : null
  }

  const errorParts: string[] = []

  for (const message of messages) {
    if (!Array.isArray(message) || message.length < 2) continue

    const eventType = message[0] as string
    const payload = message[1]

    // Seuls les events d'erreur nous interessent
    if (eventType === 'execution_error') {
      errorParts.push(stringifyComfyObject(payload))
    } else if (eventType === 'execution_interrupted') {
      errorParts.push('Generation interrompue par ComfyUI.')
    }
    // execution_start, execution_cached → on les ignore (pas des erreurs)
  }

  if (errorParts.length > 0) {
    return errorParts.join(' | ')
  }

  // Aucun event d'erreur explicite mais status_str = error
  if (entry?.status?.status_str === 'error') {
    return 'ComfyUI a signale une erreur sans details exploitables.'
  }

  return null
}

/**
 * Attend le resultat d'un prompt ComfyUI via WebSocket (temps reel) avec fallback polling.
 * Centralise la logique de suivi — plus besoin de setInterval dans chaque module.
 */
export async function waitForComfyResult(
  promptId: string,
  opts: {
    getHistory: (id: string) => Promise<Record<string, ComfyHistoryEntry>>
    onProgress?: (pct: number, detail: string) => void
    timeoutMs?: number
  },
): Promise<{ filename: string; subfolder: string }> {
  const timeout = opts.timeoutMs ?? 300_000
  const deadline = Date.now() + timeout

  // --- Tenter WebSocket pour progress temps reel ---
  // Essayer direct 8188 d'abord, puis via le proxy Vite /ws, puis fallback polling pur
  let wsResolved = false
  const wsPromise = new Promise<void>((resolve) => {
    const wsUrls = [
      'ws://127.0.0.1:8188/ws?clientId=aurora',
      `ws://${typeof window !== 'undefined' ? window.location.host : '127.0.0.1:1420'}/ws?clientId=aurora`,
    ]

    let connected = false
    let wsIndex = 0

    function tryConnect() {
      if (wsIndex >= wsUrls.length) { resolve(); return }
      try {
        const ws = new WebSocket(wsUrls[wsIndex])
        const cleanup = () => { try { ws.close() } catch {} }
        const connectTimer = setTimeout(() => {
          if (!connected) { cleanup(); wsIndex++; tryConnect() }
        }, 3000)

        ws.onopen = () => {
          connected = true
          clearTimeout(connectTimer)
          const overallTimer = setTimeout(() => { cleanup(); resolve() }, timeout)

          ws.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data)
              if (msg.type === 'progress' && msg.data?.prompt_id === promptId) {
                const pct = Math.round((msg.data.value / msg.data.max) * 100)
                opts.onProgress?.(pct, `Rendu ComfyUI: ${pct}%`)
              }
              if ((msg.type === 'executed' || msg.type === 'execution_error') && msg.data?.prompt_id === promptId) {
                wsResolved = true
                clearTimeout(overallTimer)
                cleanup()
                resolve()
              }
            } catch {}
          }
          ws.onclose = () => { clearTimeout(overallTimer); resolve() }
        }
        ws.onerror = () => {
          clearTimeout(connectTimer)
          if (!connected) { wsIndex++; tryConnect() }
          else resolve()
        }
      } catch {
        wsIndex++; tryConnect()
      }
    }

    tryConnect()
  })

  // --- Polling history en parallele (fallback + detection finale) ---
  let lastPollEntry: ComfyHistoryEntry | null = null

  const poll = async () => {
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, wsResolved ? 200 : 1500))
      try {
        const history = await opts.getHistory(promptId)
        const entry = history?.[promptId]
        if (!entry) continue

        lastPollEntry = entry

        if (entry.status?.status_str === 'error') {
          throw new Error(extractComfyHistoryFailure(entry) || 'ComfyUI a signale une erreur.')
        }

        if (entry.status?.completed) {
          return extractComfyImageOutput(entry)
        }

        // Pas encore fini — update progress si pas de WebSocket
        if (!wsResolved) {
          opts.onProgress?.(50, 'Rendu en cours...')
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : ''
        if (msg.includes('aucune image') || msg.includes('erreur') || msg.includes('refuse')) {
          throw err
        }
        // Erreur reseau transitoire → on continue
      }
    }

    throw new Error('Timeout: ComfyUI n a pas termine dans le delai imparti.')
  }

  // Lancer les deux en parallele
  const [result] = await Promise.all([poll(), wsPromise])
  return result
}

export function extractComfyImageOutput(entry: ComfyHistoryEntry) {
  for (const nodeId of Object.keys(entry?.outputs || {})) {
    const outputImages = entry.outputs?.[nodeId]?.images
    if (outputImages?.length) {
      return {
        filename: outputImages[0].filename,
        subfolder: outputImages[0].subfolder || '',
      }
    }
  }

  throw new Error('ComfyUI n a renvoye aucune image exploitable.')
}

