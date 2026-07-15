import { convertFileSrc, invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import type {
  HardwareProfile,
  HostRuntimeResources,
  HostPrivilegeStatus,
  LinuxRuntimeCheckReport,
  OllamaMessage,
  RuntimeProgressEvent,
  RuntimeServiceId,
  RuntimeServiceInfo,
  ServiceStatus,
} from '../types/app'
import {
  getBridgeUrl,
  isCloudRuntime,
  isTauriRuntime,
  toBrowserFileUrl,
} from '../utils/runtime.ts'
import { getErrorMessage, safeParseJson } from '../utils/errors.ts'

// ---------------------------------------------------------------------------
// Cloud mode helpers
// ---------------------------------------------------------------------------

function ollamaBaseUrl(): string {
  if (isTauriRuntime()) return 'http://127.0.0.1:11434'
  // En cloud avec bridge, proxier via le bridge pour nettoyer les headers CORS
  if (isCloudRuntime()) return `${getBridgeUrl()}/proxy/ollama`
  // En mode browser local, essayer le bridge s'il existe, sinon acces direct
  const bridge = getBridgeUrl()
  if (bridge) return `${bridge}/proxy/ollama`
  return 'http://127.0.0.1:11434'
}

function comfyBaseUrl(): string {
  if (isTauriRuntime()) return 'http://127.0.0.1:8188'
  if (isCloudRuntime()) return `${getBridgeUrl()}/proxy/comfy`
  const bridge = getBridgeUrl()
  if (bridge) return `${bridge}/proxy/comfy`
  return 'http://127.0.0.1:8188'
}

// Callback global pour les progress Python en mode cloud (polling)
let _cloudProgressCallback: ((progress: string) => void) | null = null
let _cloudProgressInterval: ReturnType<typeof setInterval> | null = null
let _cloudProgressCursor = 0

function _startCloudProgressPolling(callback: (progress: string) => void): () => void {
  _cloudProgressCallback = callback
  _cloudProgressCursor = 0

  _cloudProgressInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/python/progress?since=${_cloudProgressCursor}`)
      if (!resp.ok) return
      const text = await resp.text()
      if (!text || text.trimStart().startsWith('<')) return
      const data = JSON.parse(text) as { events: string[]; cursor: number }
      for (const event of data.events) {
        _cloudProgressCallback?.(event)
      }
      _cloudProgressCursor = data.cursor
    } catch {
      // Polling silencieux en cas d'erreur reseau
    }
  }, 400)

  return () => {
    if (_cloudProgressInterval) {
      clearInterval(_cloudProgressInterval)
      _cloudProgressInterval = null
    }
    _cloudProgressCallback = null
  }
}

async function cloudInvoke<T>(endpoint: string, args?: Record<string, unknown>): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${getBridgeUrl()}${endpoint}`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args || {}),
  })

  return safeParseJson<T>(response, `Cloud bridge ${endpoint}`)
}

// ---------------------------------------------------------------------------
// Tauri helpers (inchanges)
// ---------------------------------------------------------------------------

async function safeListen<T>(eventName: string, callback: (payload: T) => void) {
  try {
    return await listen<T>(eventName, (event) => {
      callback(event.payload)
    })
  } catch (error) {
    console.warn(`[TauriEvents] Listener indisponible pour ${eventName}:`, getErrorMessage(error, 'permission manquante'))
    return () => { }
  }
}

async function desktopInvoke<T>(command: string, args?: Record<string, unknown>) {
  if (isTauriRuntime()) {
    try {
      return await invoke<T>(command, args)
    } catch (error) {
      throw new Error(getErrorMessage(error, `Commande Tauri echouee: ${command}`))
    }
  }

  // Fallback bridge pour tunnel/browser/cloud
  return cloudInvoke<T>(`/api/tauri/${command}`, args)
}

async function parseJsonResponse(response: Response, label: string) {
  return safeParseJson(response, label)
}

// ---------------------------------------------------------------------------
// Ollama / ComfyUI fetch (cloud-aware URLs)
// ---------------------------------------------------------------------------

async function ollamaFetch(path: string, init: RequestInit, label: string, baseUrl?: string) {
  const host = baseUrl || ollamaBaseUrl()
  const fetchOpts: RequestInit = {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  }

  try {
    const response = await fetch(`${host}${path}`, fetchOpts)
    return await parseJsonResponse(response, label)
  } catch (firstErr) {
    // Si le bridge a echoue (HTML, 502, etc.), essayer Ollama directement
    if (!isTauriRuntime() && host !== 'http://127.0.0.1:11434') {
      try {
        const directResponse = await fetch(`http://127.0.0.1:11434${path}`, fetchOpts)
        return await parseJsonResponse(directResponse, label)
      } catch {
        // Le fallback direct a aussi echoue — propager l'erreur originale
      }
    }
    throw firstErr
  }
}

async function comfyFetch(path: string, init: RequestInit, label: string) {
  const host = comfyBaseUrl()

  // Mobile-over-tunnel reality: a backgrounded tab's fetch often lands on a
  // momentarily stale socket and rejects with Safari's "Load failed" even
  // though the tunnel is fine one tick later. Retry a few times with short
  // backoff before surfacing the error to the user — good enough to absorb
  // Cloudflare reconnects, Wi-Fi hiccups, iOS wake transitions.
  const attempt = async (): Promise<unknown> => {
    const response = await fetch(`${host}${path}`, init)
    const ct = response.headers.get('content-type') || ''
    if (ct.includes('text/html') && !response.ok) {
      throw new Error(`ComfyUI proxy a retourne HTML (${response.status}) — le tunnel ou le bridge est en erreur.`)
    }
    return await parseJsonResponse(response, label)
  }

  const BACKOFFS_MS = [0, 800, 2000] // 3 tries total — 0s, 0.8s, 2s
  let firstErr: unknown = null
  for (let i = 0; i < BACKOFFS_MS.length; i++) {
    if (BACKOFFS_MS[i] > 0) await new Promise((r) => setTimeout(r, BACKOFFS_MS[i]))
    try {
      return await attempt()
    } catch (err) {
      if (i === 0) firstErr = err
      const msg = err instanceof Error ? err.message : String(err)
      // Only retry on transient network-layer errors. HTTP errors (HTML from
      // proxy, JSON parse) already carry actionable info, no point spamming.
      if (!/Load failed|Failed to fetch|NetworkError|TypeError: (Network|Load)|aborted/i.test(msg)) {
        firstErr = err
        break
      }
    }
  }

  // Last-resort fallback: on a same-machine client (browser/Tauri NOT over a
  // tunnel), try ComfyUI directly in case the bridge itself is down.
  if (!isTauriRuntime() && !isCloudRuntime() && host !== 'http://127.0.0.1:8188') {
    try {
      const directResponse = await fetch(`http://127.0.0.1:8188${path}`, init)
      return await parseJsonResponse(directResponse, label)
    } catch {
      /* ignore */
    }
  }
  throw firstErr instanceof Error ? firstErr : new Error(String(firstErr))
}

async function ping(url: string) {
  try {
    const response = await fetch(url)
    return response.ok
  } catch {
    return false
  }
}

function buildBrowserHardwareProfile(): HardwareProfile {
  const deviceMemory = typeof navigator !== 'undefined' && 'deviceMemory' in navigator
    ? Number((navigator as Navigator & { deviceMemory?: number }).deviceMemory || 8)
    : 8

  return {
    os: navigator.userAgent,
    cpu: 'Navigateur local',
    cores: navigator.hardwareConcurrency || 4,
    ram_gb: deviceMemory,
    gpu: 'GPU non expose en mode navigateur',
    vram_gb: 0,
    vram_free_gb: 0,
  }
}

// ---------------------------------------------------------------------------
// Ollama
// ---------------------------------------------------------------------------

export async function ollamaChat(
  model: string,
  messages: OllamaMessage[],
  temperature?: number,
  extraOptions?: { num_ctx?: number; baseUrl?: string; signal?: AbortSignal; firstByteTimeoutMs?: number }
) {
  const baseUrl = extraOptions?.baseUrl

  if (isTauriRuntime()) {
    await runtimeEnsureService('ollama')
    await runtimePrepareOllamaModel(model)
    const result = await desktopInvoke<string>('ollama_chat', { model, messages, temperature })
    return JSON.parse(result)
  }

  return ollamaChatStreamAsNonStream(model, messages, {
    temperature,
    num_ctx: extraOptions?.num_ctx,
    baseUrl,
    signal: extraOptions?.signal,
    firstByteTimeoutMs: extraOptions?.firstByteTimeoutMs,
  })
}

export async function ollamaGenerate(
  model: string,
  prompt: string,
  extraOptions?: { num_ctx?: number; signal?: AbortSignal; firstByteTimeoutMs?: number },
) {
  if (isTauriRuntime()) {
    await runtimeEnsureService('ollama')
    await runtimePrepareOllamaModel(model)
    const result = await desktopInvoke<string>('ollama_generate', { model, prompt })
    return JSON.parse(result)
  }

  return ollamaGenerateStreamAsNonStream(
    model,
    prompt,
    extraOptions?.num_ctx,
    extraOptions?.signal,
    extraOptions?.firstByteTimeoutMs,
  )
}

// ---------------------------------------------------------------------------
// Stream-backed non-stream wrappers (cloud / tunnel 524 protection)
// ---------------------------------------------------------------------------

async function ollamaChatStreamAsNonStream(
  model: string,
  messages: OllamaMessage[],
  opts: {
    temperature?: number
    num_ctx?: number
    baseUrl?: string
    signal?: AbortSignal
    firstByteTimeoutMs?: number
  } = {},
): Promise<{ message: { role: string; content: string }; done?: boolean }> {
  let content = ''
  await ollamaChatStream(
    model,
    messages,
    (token) => { content += token },
    () => undefined,
    {
      temperature: opts.temperature,
      num_ctx: opts.num_ctx,
      signal: opts.signal,
      firstByteTimeoutMs: opts.firstByteTimeoutMs,
    },
  )
  return { message: { role: 'assistant', content }, done: true }
}

async function ollamaGenerateStreamAsNonStream(
  model: string,
  prompt: string,
  num_ctx?: number,
  signal?: AbortSignal,
  firstByteTimeoutMs?: number,
): Promise<{ response: string; done?: boolean }> {
  const body: Record<string, unknown> = { model, prompt, stream: true }
  if (num_ctx) body.options = { num_ctx }

  const bridge = getBridgeUrl()
  const endpoints = [
    `${bridge}/proxy/ollama/api/generate`,
    `${bridge}/api/ollama/generate`,
    'http://127.0.0.1:11434/api/generate',
  ]

  // v77zap/v90: same first-byte budget as ollamaChatStream. Heavy local code
  // models can override it; the default still protects tunnel calls.
  // v120: increased to 480_000 for heavy SWAP workloads (up to 70GB SWAP allowed).
  const HARD_TIMEOUT_MS = firstByteTimeoutMs ?? 480_000
  const internalAbort = new AbortController()
  const timeoutId = setTimeout(() => internalAbort.abort(), HARD_TIMEOUT_MS)
  if (signal) {
    if (signal.aborted) internalAbort.abort()
    else signal.addEventListener('abort', () => internalAbort.abort(), { once: true })
  }

  let response: Response | null = null
  let lastError: unknown = null
  try {
    for (const endpoint of endpoints) {
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: internalAbort.signal,
        })
        const ct = response.headers.get('content-type') || ''
        const fatal = ct.includes('text/html') || response.status >= 500
        if (fatal && endpoints.indexOf(endpoint) < endpoints.length - 1) {
          response = null
          continue
        }
        break
      } catch (err) {
        lastError = err
        if (endpoints.indexOf(endpoint) >= endpoints.length - 1) throw err
      }
    }
  } finally {
    clearTimeout(timeoutId)
  }
  if (!response) throw lastError ?? new Error('Ollama generate indisponible.')
  if (!response.ok || !response.body) {
    throw new Error(`Ollama generate a retourne ${response.status}.`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newlineIndex = buffer.indexOf('\n')
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)
      if (line) {
        try {
          const payload = JSON.parse(line)
          if (typeof payload.response === 'string') full += payload.response
          if (payload.done) break
        } catch {
          // Ignore partial JSON frames
        }
      }
      newlineIndex = buffer.indexOf('\n')
    }
  }
  return { response: full, done: true }
}

export async function ollamaListModels(baseUrl?: string) {
  if (isTauriRuntime()) {
    const result = await desktopInvoke<string>('ollama_list_models')
    return JSON.parse(result)
  }
  return ollamaFetch('/api/tags', { method: 'GET' }, 'Ollama list', baseUrl)
}

export async function ollamaPullModel(model: string) {
  if (isTauriRuntime()) {
    const result = await desktopInvoke<string>('ollama_pull_model', { model })
    return JSON.parse(result)
  }

  return ollamaFetch('/api/pull', {
    method: 'POST',
    body: JSON.stringify({ name: model, stream: false }),
  }, 'Ollama pull')
}

export interface PullProgress {
  status: string                 // "pulling manifest", "downloading", "verifying sha256 digest", "success"
  digest?: string
  total?: number                 // bytes, when provided
  completed?: number             // bytes received so far
}

/**
 * Stream a model pull with real progress. The caller gets per-layer download
 * updates suitable for a UI progress bar. Works in browser/cloud mode by
 * streaming the NDJSON body of /api/pull. Tauri mode falls back to a single
 * progress emit because the native command doesn't stream yet.
 */
export async function ollamaPullModelStream(
  model: string,
  onProgress: (p: PullProgress) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (isTauriRuntime()) {
    onProgress({ status: 'pulling manifest' })
    const result = await desktopInvoke<string>('ollama_pull_model', { model })
    try {
      const parsed = JSON.parse(result) as { status?: string }
      onProgress({ status: parsed.status || 'success' })
    } catch { onProgress({ status: 'success' }) }
    return
  }
  const baseUrl = ollamaBaseUrl()
  const resp = await fetch(`${baseUrl}/api/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: model, stream: true }),
    signal,
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`ollama pull HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let nl
    while ((nl = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (!line) continue
      try {
        const evt = JSON.parse(line) as PullProgress & { error?: string }
        if (evt.error) throw new Error(evt.error)
        onProgress(evt)
      } catch (err) {
        if (err instanceof SyntaxError) continue
        throw err
      }
    }
  }
}

export async function ollamaChatStream(
  model: string,
  messages: OllamaMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
  options?: {
    temperature?: number
    // Sampling nucleus / top-k / penalites. Necessaire pour appliquer les presets
    // officiels des modeles (ex. Qwen3-Instruct : temp 0.7, top_p 0.8, top_k 20).
    // Transmis tel quel dans body.options d'Ollama (fonctionne aussi via le proxy
    // bridge qui ne fait que relayer le corps).
    top_p?: number
    top_k?: number
    min_p?: number
    repeat_penalty?: number
    signal?: AbortSignal
    num_ctx?: number
    // v82nd : max tokens to GENERATE. Some models (qwen3-coder default,
    // certain Modelfile presets) cap num_predict at 256-1024 → output
    // truncates after a single fence opener. Pass 8000+ for code-gen.
    num_predict?: number
    firstByteTimeoutMs?: number
    // v82lg: callback optionnel pour les tokens de thinking (qwen3 / qwen3-vl
    // en mode reasoning). Permet à l'UI d'afficher une progression "le modèle
    // réfléchit..." au lieu d'une zone vide pendant que le content est encore
    // vide. Le content réel passe toujours par onToken.
    onThinking?: (token: string) => void
  }
) {
  if (isTauriRuntime()) {
    await runtimeEnsureService('ollama')
    await runtimePrepareOllamaModel(model)
  }

  const body: Record<string, unknown> = {
    model,
    messages,
    stream: true,
  }

  const streamOpts: Record<string, unknown> = {}
  if (options?.temperature !== undefined) streamOpts.temperature = options.temperature
  if (options?.top_p !== undefined) streamOpts.top_p = options.top_p
  if (options?.top_k !== undefined) streamOpts.top_k = options.top_k
  if (options?.min_p !== undefined) streamOpts.min_p = options.min_p
  if (options?.repeat_penalty !== undefined) streamOpts.repeat_penalty = options.repeat_penalty
  if (options?.num_ctx) streamOpts.num_ctx = options.num_ctx
  if (options?.num_predict !== undefined) streamOpts.num_predict = options.num_predict
  if (Object.keys(streamOpts).length > 0) body.options = streamOpts

  // Priorite: Tauri → bridge proxy (with keepalive) → direct Ollama fallback.
  // The cloud bridge exposes a generic `/proxy/ollama/{path:path}` that forwards
  // to Ollama with SSE keep-alive heartbeats so Cloudflare/RunPod never cut the
  // tunnel on cold model starts. The old `/api/ollama/chat` alias is kept for
  // backward compatibility only.
  const bridge = getBridgeUrl()
  const chatEndpoints = isTauriRuntime()
    ? [`${ollamaBaseUrl()}/api/chat`]
    : [
        `${bridge}/proxy/ollama/api/chat`,
        `${bridge}/api/ollama/chat`,
        'http://127.0.0.1:11434/api/chat',
      ]

  // v77zap: hard timeout via AbortController for EVERY Ollama call. The
  // Cloudflare tunnel kills slow requests at 125s with HTTP 524 + an HTML
  // body — which trips the legacy text/html fallback and cascades through
  // every endpoint, multiplying the wait by N. With a 90s default we always
  // abort BEFORE Cloudflare and BEFORE any cascade can start. Caller-provided
  // signal (if any) is composed via abort propagation.
  // v82lg: callers with heavy prompts (parcours-bac complet, long contexts on
  // a vision model) can override the first-byte timeout via firstByteTimeoutMs.
  // The timer is cleared as soon as the response headers arrive, so this only
  // bounds time-to-first-byte (TTFB), not the streaming duration.
  // v120: increased to 480_000 for heavy SWAP workloads (up to 70GB SWAP allowed).
  const HARD_TIMEOUT_MS = options?.firstByteTimeoutMs ?? 480_000
  const internalAbort = new AbortController()
  const timeoutId = setTimeout(() => internalAbort.abort(), HARD_TIMEOUT_MS)
  if (options?.signal) {
    if (options.signal.aborted) internalAbort.abort()
    else options.signal.addEventListener('abort', () => internalAbort.abort(), { once: true })
  }

  let response: Response | null = null
  let lastError: unknown = null

  try {
    for (const endpoint of chatEndpoints) {
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: internalAbort.signal,
        })
        // v77zap: a 5xx response from Cloudflare or the bridge often comes
        // with text/html error pages. Treat them as fatal for THIS endpoint
        // but still try the next one in the cascade. Without this, the loop
        // would `break` on a 524 (since ct=text/html only triggered for 2xx
        // pages) and then throw — but more importantly each call took 125s.
        // Now we abort early via internalAbort so this is a safety net only.
        const ct = response.headers.get('content-type') || ''
        const htmlLooking = ct.includes('text/html')
        const fatal5xx = response.status >= 500
        if ((htmlLooking || fatal5xx) && chatEndpoints.indexOf(endpoint) < chatEndpoints.length - 1) {
          response = null
          continue
        }
        break
      } catch (err) {
        lastError = err
        if (chatEndpoints.indexOf(endpoint) >= chatEndpoints.length - 1) throw err
      }
    }
  } finally {
    // Will be cleared earlier on success path inside while-loop, but safe to
    // clear here too so the timer never leaks if we throw before reading.
    clearTimeout(timeoutId)
  }

  if (!response) {
    throw lastError || new Error('Ollama non joignable (ni via bridge, ni directement)')
  }

  if (!response.ok) {
    const errBody = await response.text().catch(() => '')
    const detail = errBody ? `: ${errBody.slice(0, 300)}` : ''
    throw new Error(`Ollama error: ${response.status}${detail}`)
  }

  // Détecter réponse HTML au lieu de JSON stream (proxy qui renvoie index.html)
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    const htmlBody = await response.text().catch(() => '')
    throw new Error(
      `Ollama stream: reponse HTML au lieu de JSON stream (le service est peut-etre indisponible). ` +
      `Content-Type: ${contentType}. Debut: ${htmlBody.slice(0, 80)}...`
    )
  }

  if (!response.body) {
    throw new Error('No response body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    // Keep last (potentially incomplete) line in buffer
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        const json = JSON.parse(trimmed)
        if (json.message?.content) {
          try { onToken(json.message.content) } catch { /* callback error — never crash stream */ }
        }
        // v82lg: relayer les tokens de thinking (qwen3-vl reasoning mode) pour
        // que l'UI puisse afficher "le modèle réfléchit..." sans freeze visuel.
        if (json.message?.thinking && options?.onThinking) {
          try { options.onThinking(json.message.thinking) } catch { /* never crash stream */ }
        }
        if (json.done) {
          try { onDone() } catch { /* callback error — never crash stream */ }
          return
        }
      } catch {
        // Partial or non-JSON line, skip
      }
    }
  }

  // Process remaining buffer
  if (buffer.trim()) {
    try {
      const json = JSON.parse(buffer.trim())
      if (json.message?.content) {
        try { onToken(json.message.content) } catch { /* callback error — never crash stream */ }
      }
    } catch {
      // Ignore trailing partial data
    }
  }

  try { onDone() } catch { /* callback error — never crash stream */ }
}

// ---------------------------------------------------------------------------
// ComfyUI
// ---------------------------------------------------------------------------

export async function comfyuiRequest(endpoint: string) {
  if (isTauriRuntime()) {
    const result = await desktopInvoke<string>('comfyui_request', { endpoint })
    return JSON.parse(result)
  }

  return comfyFetch(endpoint, { method: 'GET' }, 'ComfyUI request')
}

/**
 * Ask ComfyUI to unload every cached model and release GPU memory.
 *
 * Modern ComfyUI exposes POST /free with `{unload_models, free_memory}`. This is
 * the ONLY reliable way to clear VRAM between successive FLUX queues — otherwise
 * the UNet + T5 XXL + CLIP stay pinned and the next CLIPTextEncodeFlux step
 * blows up with "Allocation would exceed allowed memory" on 16 GB cards.
 * Best-effort: older ComfyUI builds return 404, in which case we swallow it.
 */
export async function comfyuiFreeVram(): Promise<boolean> {
  try {
    await comfyFetch('/free', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ unload_models: true, free_memory: true }),
    }, 'ComfyUI free')
    return true
  } catch {
    return false
  }
}

export async function comfyuiInterrupt(): Promise<boolean> {
  const host = comfyBaseUrl()
  const endpoints = [`${host}/interrupt`]
  if (!isCloudRuntime() && host !== 'http://127.0.0.1:8188') {
    endpoints.push('http://127.0.0.1:8188/interrupt')
  }
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        signal: AbortSignal.timeout(5000),
      })
      if (response.ok) return true
    } catch {
      continue
    }
  }
  return false
}

/**
 * Evict an Ollama model from VRAM immediately by issuing a zero-length generate
 * with keep_alive=0. Used before long FLUX sequences to avoid the vision /
 * reasoning LLM and FLUX competing for the same GPU.
 */
export async function releaseOllamaModel(model: string): Promise<boolean> {
  if (!model) return false
  const bridge = getBridgeUrl()
  const endpoints = [
    `${bridge}/proxy/ollama/api/generate`,
    `${bridge}/api/ollama/generate`,
    'http://127.0.0.1:11434/api/generate',
  ]
  const body = JSON.stringify({ model, prompt: '', keep_alive: 0, stream: false })
  for (const endpoint of endpoints) {
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: AbortSignal.timeout(10_000),
      })
      const ct = resp.headers.get('content-type') || ''
      if (ct.includes('text/html')) continue
      if (resp.ok) return true
    } catch {
      continue
    }
  }
  return false
}

export async function listLoadedOllamaModels(): Promise<string[]> {
  const bridge = getBridgeUrl()
  const endpoints = [
    `${bridge}/proxy/ollama/api/ps`,
    'http://127.0.0.1:11434/api/ps',
  ]
  for (const endpoint of endpoints) {
    try {
      const resp = await fetch(endpoint, { signal: AbortSignal.timeout(6_000) })
      const ct = resp.headers.get('content-type') || ''
      if (!resp.ok || ct.includes('text/html')) continue
      const data = await resp.json() as { models?: Array<{ name?: string; model?: string }> }
      if (Array.isArray(data?.models)) {
        return data.models.map((m) => m.name || m.model || '').filter(Boolean)
      }
    } catch {
      continue
    }
  }
  return []
}

export async function freeGpuBeforeFlux(ollamaModelsToEvict: string[] = []): Promise<void> {
  await comfyuiFreeVram()
  let loaded: string[] = []
  try { loaded = await listLoadedOllamaModels() } catch { /* ignore */ }
  const targets = Array.from(new Set([...ollamaModelsToEvict, ...loaded].filter(Boolean)))
  for (const model of targets) {
    await releaseOllamaModel(model)
  }
}

export async function comfyuiQueuePrompt(workflow: Record<string, unknown>) {
  if (isTauriRuntime()) {
    const result = await desktopInvoke<string>('comfyui_queue_prompt', {
      workflow: JSON.stringify(workflow),
    })
    return JSON.parse(result)
  }

  // comfyFetch a deja le fallback bridge → direct 8188
  return comfyFetch('/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow }),
  }, 'ComfyUI queue')
}

/**
 * Upload an image to ComfyUI's input folder so a workflow can then reference
 * it by filename (LoadImage node). Returns `{ name }` — the filename to pass
 * into `referenceImage.filename` in `createFluxWorkflow`.
 */
export async function comfyuiUploadImage(file: File | Blob, filename?: string): Promise<{ name: string; subfolder?: string }> {
  const name = filename || (file instanceof File ? file.name : `ref_${Date.now()}.png`)
  const form = new FormData()
  form.append('image', file, name)
  form.append('overwrite', 'true')

  const bridgeUrl = getBridgeUrl()
  const base = bridgeUrl
  const endpoints = [
    `${base}/api/comfyui/upload`,
    `${base}/proxy/comfy/upload/image`,
  ]
  if (!isCloudRuntime()) endpoints.push('http://127.0.0.1:8188/upload/image')

  const errors: string[] = []
  for (const url of endpoints) {
    try {
      const resp = await fetch(url, { method: 'POST', body: form, signal: AbortSignal.timeout(30_000) })
      if (resp.ok) {
        const data = await resp.json().catch(() => ({ name }))
        return { name: data.name || name, subfolder: data.subfolder }
      }
      errors.push(`${url}: HTTP ${resp.status}`)
    } catch (err) {
      errors.push(`${url}: ${err instanceof Error ? err.message : String(err)}`)
    }
  }
  throw new Error(`ComfyUI upload échoué : ${errors.join(' | ')}`)
}

export async function comfyuiGetHistory(promptId: string) {
  if (isTauriRuntime()) {
    const result = await desktopInvoke<string>('comfyui_get_history', { promptId })
    return JSON.parse(result)
  }

  // comfyFetch a deja le fallback bridge → direct 8188
  return comfyFetch(`/history/${promptId}`, { method: 'GET' }, 'ComfyUI history')
}

export async function comfyuiGetImage(filename: string, subfolder: string = ''): Promise<Blob> {
  if (isTauriRuntime()) {
    const bytes = await desktopInvoke<number[]>('comfyui_get_image', { filename, subfolder })
    return new Blob([new Uint8Array(bytes)], { type: 'image/png' })
  }

  const qs = `filename=${encodeURIComponent(filename)}&subfolder=${encodeURIComponent(subfolder)}&type=output`

  // BUGFIX: `getBridgeUrl()` returns `''` in cloud/tunnel mode (the empty
  // string is intentional — it means "use relative paths so Vite's proxy
  // forwards /api → bridge:3001"). The old code did `bridgeUrl ? [...] : [...]`
  // which treated `''` as "no bridge" and fell back to `http://127.0.0.1:8188`,
  // the client machine's localhost — always unreachable over a Cloudflare
  // tunnel. Hence the "ComfyUI image indisponible apres 1 endpoint(s)" loop.
  //
  // Fix: always try the bridge-backed routes FIRST (with an empty base on
  // cloud, with the explicit URL on local browser), then fall back to the
  // direct ComfyUI URL only when we are running on the same machine.
  const bridgeUrl = getBridgeUrl()
  const base = bridgeUrl // '' in cloud, 'http://127.0.0.1:3001' in local browser, '' in Tauri (already handled above)
  const endpoints = [
    `${base}/api/comfyui/image?${qs}`,
    `${base}/proxy/comfy/view?${qs}`,
  ]
  // Only tack on the direct ComfyUI URL if the client is ALSO the server
  // (local browser or Tauri — same machine). In tunnel/remote we skip it,
  // it can never work and produces misleading "Load failed" noise.
  if (!isCloudRuntime()) {
    endpoints.push(`http://127.0.0.1:8188/view?${qs}`)
  }

  const errors: string[] = []
  // Chaque endpoint: jusqu'a 3 tentatives (backoff 500ms, 1500ms) pour absorber les lags de flush.
  for (const url of endpoints) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      if (attempt > 0) {
        await new Promise((resolve) => setTimeout(resolve, 500 * attempt))
      }
      try {
        const response = await fetch(url, { signal: AbortSignal.timeout(20_000) })
        if (response.ok) {
          const ct = response.headers.get('content-type') || ''
          if (ct.includes('text/html')) {
            errors.push(`${url}: reponse HTML (proxy error)`)
            break
          }
          const blob = await response.blob()
          if (blob.size < 100) {
            errors.push(`${url}: blob vide (${blob.size} octets)`)
            continue
          }
          return blob
        }
        errors.push(`${url}: HTTP ${response.status}`)
        if (response.status < 500) break // 4xx: inutile de retenter le meme endpoint
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        errors.push(`${url}: ${message}`)
      }
    }
  }

  throw new Error(
    `ComfyUI image indisponible apres ${endpoints.length} endpoint(s). Details: ${errors.slice(0, 4).join(' | ')}`,
  )
}

// ---------------------------------------------------------------------------
// ComfyUI lifecycle (cloud / bridge mode)
// ---------------------------------------------------------------------------

export async function ensureComfyUIRunning(): Promise<{ ok: boolean; error?: string }> {
  // Mode Tauri: ComfyUI est gere par le runtime Rust via executeWithRuntime
  if (isTauriRuntime()) {
    return { ok: true }
  }

  // --- Modes non-Tauri (browser, cloud, tunnel) ---
  //
  // En mode cloud/tunnel, le 127.0.0.1 du navigateur client n'est PAS le serveur
  // qui heberge ComfyUI — il faut passer par le bridge. On skip donc le ping direct.
  // En mode browser-local (pas tunnel), le ping 127.0.0.1 peut fonctionner comme court-circuit.
  if (!isCloudRuntime()) {
    const directOk = await ping('http://127.0.0.1:8188/system_stats')
    if (directOk) return { ok: true }
  }

  // Via le bridge (URL vide en cloud → Vite proxy relaye /api → bridge:3001)
  const bridgeUrl = getBridgeUrl()
  const base = bridgeUrl || ''

  // 1. Verifier si ComfyUI tourne deja (timeout large pour absorber la latence tunnel)
  try {
    const statusResp = await fetch(`${base}/api/comfyui/status`, {
      signal: AbortSignal.timeout(10_000),
    })
    if (statusResp.ok) {
      const status = await safeParseJson<{ running?: boolean; ok?: boolean }>(statusResp, 'ComfyUI status')
      if (status.running) return { ok: true }
    }
  } catch {
    // Le bridge a peut-etre mis du temps; on tolere et on tente quand meme /start
  }

  // 2. Demander auto-start (le bridge est idempotent: si deja running il renvoie ready:true tout de suite)
  try {
    const startResp = await fetch(`${base}/api/comfyui/start`, {
      method: 'POST',
      signal: AbortSignal.timeout(90_000),
    })
    if (startResp.ok) {
      const result = await safeParseJson<{ ok?: boolean; ready?: boolean; error?: string }>(startResp, 'ComfyUI start')
      if (result.ready || result.ok) return { ok: true }
      if (result.error) return { ok: false, error: result.error }
    }
  } catch {
    // bridge timeout — on retente status apres delai
  }

  // 3. Dernier essai: re-status apres petit delai (ComfyUI a pu finir son boot)
  await new Promise((resolve) => setTimeout(resolve, 2000))
  try {
    const retryResp = await fetch(`${base}/api/comfyui/status`, {
      signal: AbortSignal.timeout(5000),
    })
    if (retryResp.ok) {
      const status = await safeParseJson<{ running?: boolean }>(retryResp, 'ComfyUI retry status')
      if (status.running) return { ok: true }
    }
  } catch {
    // ignore
  }

  // 4. Fallback ultime: ping direct (cas browser-local)
  if (!isCloudRuntime()) {
    const lastOk = await ping('http://127.0.0.1:8188/system_stats')
    if (lastOk) return { ok: true }
  }

  return {
    ok: false,
    error: 'Le service image (ComfyUI) ne repond pas via le bridge. Verifie que bridge_server.py tourne cote serveur et que ComfyUI est bien demarre.',
  }
}

// ---------------------------------------------------------------------------
// Hardware
// ---------------------------------------------------------------------------

export async function detectHardware(): Promise<HardwareProfile> {
  if (isTauriRuntime()) {
    return desktopInvoke<HardwareProfile>('detect_hardware')
  }

  try {
    const resp = await fetch(`${getBridgeUrl()}/api/hardware`)
    if (resp.ok) return safeParseJson<HardwareProfile>(resp, 'Hardware detect')
  } catch {
    // Bridge unreachable — use browser fallback
  }

  return buildBrowserHardwareProfile()
}

export async function inspectHostResources(): Promise<HostRuntimeResources> {
  if (isTauriRuntime()) {
    return desktopInvoke<HostRuntimeResources>('inspect_host_resources')
  }

  if (isCloudRuntime()) {
    const hw = await detectHardware()
    return {
      total_ram_gb: hw.ram_gb,
      free_ram_gb: hw.ram_gb,
      memory_pressure: 'low',
    }
  }

  const browserHardware = buildBrowserHardwareProfile()
  return {
    total_ram_gb: browserHardware.ram_gb,
    free_ram_gb: browserHardware.ram_gb,
    memory_pressure: 'medium',
  }
}

// ---------------------------------------------------------------------------
// Service status
// ---------------------------------------------------------------------------

export async function checkServiceStatus(): Promise<ServiceStatus> {
  if (isTauriRuntime()) {
    return desktopInvoke<ServiceStatus>('check_service_status')
  }

  try {
    const resp = await fetch(`${getBridgeUrl()}/api/services/status`)
    if (resp.ok) return safeParseJson<ServiceStatus>(resp, 'Service status')
  } catch {
    // Bridge unreachable — fall through to direct ping
  }

  // Tester directement les services locaux (sans passer par le bridge)
  const [ollama, comfyui] = await Promise.all([
    ping('http://127.0.0.1:11434/api/tags'),
    ping('http://127.0.0.1:8188/system_stats'),
  ])

  return { ollama, comfyui }
}

// ---------------------------------------------------------------------------
// Python scripts
// ---------------------------------------------------------------------------

// Persisted jobs — key → jobId lets a module pick a long-running Python job
// back up after a tab kill (iOS backgrounding, Vite HMR, manual refresh…).
// The PC bridge keeps the subprocess alive regardless of the tab lifecycle,
// so all we need on the client is the jobId to re-join the poll loop.
const JOB_STORAGE_PREFIX = 'aurora.pendingJob.v1:'

function recallJobId(key: string): string | null {
  try { return localStorage.getItem(JOB_STORAGE_PREFIX + key) } catch { return null }
}
function rememberJobId(key: string, jobId: string) {
  try { localStorage.setItem(JOB_STORAGE_PREFIX + key, jobId) } catch { /* private mode */ }
}
function forgetJobId(key: string) {
  try { localStorage.removeItem(JOB_STORAGE_PREFIX + key) } catch { /* ignore */ }
}

export interface RunPythonOptions {
  /**
   * When set, the jobId is persisted to localStorage under this key so a
   * reload/backgrounding mid-generation can transparently reattach to the
   * same subprocess on the next mount instead of spawning a duplicate run
   * or surfacing a "Load failed" error.
   *
   * One key per module (e.g. 'video', 'model', 'image') — calling this with
   * the same key while another job is live on the bridge will reattach to
   * THAT job and return its output, which is exactly what we want when the
   * user comes back to a refreshed tab.
   */
  resumeKey?: string
}

/** Probe whether a previously-launched job under `resumeKey` is still live on
 * the bridge. Modules use this on mount to decide whether to show a "Reprendre
 * la generation" banner. Returns null when nothing is pending. */
export async function peekResumableJob(resumeKey: string): Promise<{ jobId: string; status: 'queued' | 'running' | 'done' } | null> {
  if (isTauriRuntime()) return null
  const persisted = recallJobId(resumeKey)
  if (!persisted) return null
  try {
    const r = await fetch(`${getBridgeUrl()}/api/python/job/${persisted}`)
    if (!r.ok) { forgetJobId(resumeKey); return null }
    const ct = r.headers.get('content-type') || ''
    if (ct.includes('text/html')) { forgetJobId(resumeKey); return null }
    const d = await r.json() as { status?: string }
    if (d.status === 'queued' || d.status === 'running' || d.status === 'done') {
      return { jobId: persisted, status: d.status }
    }
    forgetJobId(resumeKey)
    return null
  } catch {
    // Bridge unreachable — don't wipe the key yet, the user may come back when
    // the tunnel is restored.
    return null
  }
}

export function clearResumableJob(resumeKey: string) {
  forgetJobId(resumeKey)
}

export async function runPythonScript(scriptPath: string, args: string[], options: RunPythonOptions = {}) {
  if (isTauriRuntime()) {
    return desktopInvoke<string>('run_python_script', { scriptPath, args })
  }

  // In cloud/tunnel mode we MUST go async. A direct POST /api/python/run takes
  // longer than Cloudflare's 100s tunnel timeout and fails with HTTP 524.
  // Async path: spawn → job_id → poll every 2.5s (each poll is < 100ms so it
  // never times out, no matter how long the subprocess takes).
  const useAsync = isCloudRuntime()
  let result: { output: string; error: string; exitCode: number } | null = null

  if (useAsync) {
    const base = getBridgeUrl() // '' in cloud, relative paths via Vite proxy
    let jobId: string | null = null

    // Resume path: if a previous tab left an in-flight job, try to reattach
    // instead of spawning a duplicate. Done → return cached output. Still
    // running → rejoin the poll loop. Unknown → forget and spawn fresh.
    if (options.resumeKey) {
      const persisted = recallJobId(options.resumeKey)
      if (persisted) {
        try {
          const r = await fetch(`${base}/api/python/job/${persisted}`)
          if (r.ok) {
            const ct = r.headers.get('content-type') || ''
            if (!ct.includes('text/html')) {
              const d = await r.json() as { status?: string; output?: string; error?: string; exitCode?: number }
              if (d.status === 'done') {
                forgetJobId(options.resumeKey)
                result = { output: d.output ?? '', error: d.error ?? '', exitCode: d.exitCode ?? 0 }
              } else if (d.status === 'queued' || d.status === 'running') {
                console.info(`[runPythonScript] reattaching to in-flight job ${persisted.slice(0, 12)}… (${options.resumeKey})`)
                jobId = persisted
              } else {
                forgetJobId(options.resumeKey)
              }
            } else {
              forgetJobId(options.resumeKey)
            }
          } else {
            forgetJobId(options.resumeKey)
          }
        } catch {
          forgetJobId(options.resumeKey)
        }
      }
    }

    // Spawn a new job only if we didn't resume a done/running one.
    if (!result && !jobId) {
      const spawnResp = await fetch(`${base}/api/python/run-async`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scriptPath, args }),
      })

      if (spawnResp.status === 404) {
        // Older bridge build without /run-async — fall back to sync endpoint.
        console.warn('[runPythonScript] /api/python/run-async absent du bridge — fallback sur /api/python/run sync (timeout Cloudflare possible sur jobs > 100s).')
        result = await cloudInvoke<{ output: string; error: string; exitCode: number }>('/api/python/run', { scriptPath, args })
      } else if (!spawnResp.ok) {
        const text = await spawnResp.text().catch(() => '')
        throw new Error(`Bridge /api/python/run-async a retourne ${spawnResp.status}: ${text.slice(0, 200)}`)
      } else {
        const ct = spawnResp.headers.get('content-type') || ''
        if (ct.includes('text/html')) {
          // HTML on 2xx → reverse proxy misrouted. Same fallback as 404.
          console.warn('[runPythonScript] /api/python/run-async a retourne du HTML — fallback sur /api/python/run sync.')
          result = await cloudInvoke<{ output: string; error: string; exitCode: number }>('/api/python/run', { scriptPath, args })
        } else {
          const spawnData = await spawnResp.json() as { jobId?: string }
          if (!spawnData.jobId) throw new Error('Bridge n a pas retourne de jobId pour le job Python.')
          jobId = spawnData.jobId
          if (options.resumeKey) rememberJobId(options.resumeKey, jobId)
        }
      }
    }

    // Shared poll loop — drives both fresh spawn and resumed jobId.
    // HEARTBEAT-BASED watchdog instead of an absolute deadline. The prior
    // 15-min absolute timeout killed perfectly valid Wan 2.2 A14B Q6_K
    // premium runs (which legitimately take 20-40 min). We now consider a
    // job frozen only when there is NO progress for 12 consecutive minutes
    // AND the total runtime exceeds a hard safety cap of 2 hours.
    if (!result && jobId) {
      const pollIntervalMs = 2500
      const startedAt = Date.now()
      const hardCapMs = 120 * 60 * 1000
      const stalledThresholdMs = 12 * 60 * 1000
      let lastProgressAt = Date.now()
      let lastProgressCursor = 0
      let transientFetchFails = 0
      const TRANSIENT_FAIL_LIMIT = 24 // ~60s of silence before we bail

      const readProgressCursor = async (): Promise<number> => {
        try {
          const r = await fetch(`${base}/api/python/progress?since=${lastProgressCursor}`, {
            signal: AbortSignal.timeout(8000),
          })
          if (!r.ok) return lastProgressCursor
          const ct = r.headers.get('content-type') || ''
          if (ct.includes('text/html')) return lastProgressCursor
          const d = await r.json() as { events?: string[]; cursor?: number }
          return typeof d.cursor === 'number' && d.cursor > lastProgressCursor ? d.cursor : lastProgressCursor
        } catch {
          return lastProgressCursor
        }
      }

      try {
        while (true) {
          await new Promise((resolve) => setTimeout(resolve, pollIntervalMs))

          // Wrap the poll fetch so a transient "Load failed" (Safari on
          // backgrounding, Wi-Fi blip, tunnel reconnect) doesn't tank the
          // whole generation — the job keeps running on the PC, we just
          // missed one poll. Only bail after many consecutive misses.
          let pollResp: Response | null = null
          try {
            pollResp = await fetch(`${base}/api/python/job/${jobId}`)
          } catch {
            transientFetchFails += 1
            if (transientFetchFails > TRANSIENT_FAIL_LIMIT) {
              throw new Error(
                `Bridge injoignable pendant le suivi du job (${transientFetchFails} tentatives consecutives sur ~${Math.round(transientFetchFails * pollIntervalMs / 1000)}s). ` +
                'Le job continue sur le PC, recharge l onglet pour reprendre.',
              )
            }
            continue
          }
          transientFetchFails = 0

          if (pollResp.ok) {
            const pollCt = pollResp.headers.get('content-type') || ''
            if (!pollCt.includes('text/html')) {
              const data = await pollResp.json() as { status?: string; output?: string; error?: string; exitCode?: number }
              if (data.status === 'done') {
                result = { output: data.output ?? '', error: data.error ?? '', exitCode: data.exitCode ?? -1 }
                break
              }
            }
          }

          const newCursor = await readProgressCursor()
          if (newCursor > lastProgressCursor) {
            lastProgressCursor = newCursor
            lastProgressAt = Date.now()
          }

          const now = Date.now()
          const totalElapsed = now - startedAt
          const sinceProgress = now - lastProgressAt

          if (totalElapsed > hardCapMs) {
            throw new Error(`Script Python depasse le plafond de securite (${Math.round(hardCapMs / 60000)} min). Abandonne.`)
          }
          if (sinceProgress > stalledThresholdMs) {
            throw new Error(
              `Script Python fige (aucun progres depuis ${Math.round(sinceProgress / 60000)} min). `
              + `Temps total ecoule ${Math.round(totalElapsed / 60000)} min. `
              + 'Verifie la VRAM/RAM libre — si la carte est saturee a 99 %+ sans avancer, tente une resolution plus basse.',
            )
          }
        }
      } finally {
        // Whether we finished cleanly or blew up, the persisted jobId is no
        // longer useful — a future call should start fresh.
        if (options.resumeKey) forgetJobId(options.resumeKey)
      }
    }
  } else {
    result = await cloudInvoke<{ output: string; error: string; exitCode: number }>('/api/python/run', { scriptPath, args })
  }

  if (!result) {
    throw new Error('runPythonScript: pas de resultat recupere (cas imprevu).')
  }

  // Strip Python warning lines — they appear in stderr but are not fatal errors
  const filteredError = (result.error || '')
    .split('\n')
    .filter((line) => !((line.includes('Warning') || line.trimStart().startsWith('warnings.warn('))
      && !line.includes('Error') && !line.includes('Traceback')))
    .join('\n')
    .trim()
  if (result.exitCode !== 0 && filteredError) {
    throw new Error(`Script echoue (code ${result.exitCode}): ${filteredError.slice(0, 1200)}`)
  }
  return result.output
}

// ---------------------------------------------------------------------------
// Workspace commands
// ---------------------------------------------------------------------------

export async function runWorkspaceCommand(
  executable: string,
  args: string[],
  cwd: string,
  timeoutMs?: number,
) {
  if (isTauriRuntime()) {
    return desktopInvoke<{
      ok: boolean
      exitCode: number
      output: string
      command: string
    }>('run_workspace_command', {
      executable,
      args,
      cwd,
      timeoutMs,
    })
  }

  return cloudInvoke<{
    ok: boolean
    exitCode: number
    output: string
    command: string
  }>('/api/command/run', { executable, args, cwd, timeoutMs })
}

export async function spawnWorkspaceCommand(
  executable: string,
  args: string[],
  cwd: string,
  stdoutLog?: string | null,
  stderrLog?: string | null,
) {
  if (isTauriRuntime()) {
    return desktopInvoke<{
      ok: boolean
      pid: number
      command: string
      stdoutLog: string | null
      stderrLog: string | null
    }>('spawn_workspace_command_detached', {
      executable,
      args,
      cwd,
      stdoutLog,
      stderrLog,
    })
  }

  return cloudInvoke<{
    ok: boolean
    pid: number
    command: string
    stdoutLog: string | null
    stderrLog: string | null
  }>('/api/command/spawn', { executable, args, cwd })
}

// ---------------------------------------------------------------------------
// Runtime services
// ---------------------------------------------------------------------------

export async function runtimeInspectServices() {
  if (isTauriRuntime()) {
    return desktopInvoke<RuntimeServiceInfo[]>('runtime_inspect_services')
  }

  try {
    const resp = await fetch(`${getBridgeUrl()}/api/runtime/inspect`)
    if (resp.ok) return safeParseJson<RuntimeServiceInfo[]>(resp, 'Runtime inspect')
  } catch {
    // Bridge unreachable — return empty
  }
  return []
}

export async function runtimeEnsureService(service: RuntimeServiceId) {
  if (isTauriRuntime()) {
    return desktopInvoke<RuntimeServiceInfo>('runtime_ensure_service', { service })
  }

  // In non-Tauri modes (browser local OR cloud/tunnel) the bridge actually
  // owns the process lifecycle. We must NOT lie by returning running:true
  // blindly — that made the image/3d/dessin modules throw misleading
  // "ComfyUI local ne repond pas encore" errors without ever attempting a
  // real restart. Instead we:
  //  1) ask the bridge for the honest status,
  //  2) if down, POST /api/{service}/start with a generous timeout,
  //  3) verify again and return the real state.
  const base = getBridgeUrl() // '' on cloud/tunnel (relative = via Vite proxy)

  async function probe(): Promise<boolean> {
    try {
      if (service === 'comfyui') {
        const r = await fetch(`${base}/api/comfyui/status`, { signal: AbortSignal.timeout(6000) })
        if (!r.ok) return false
        const ct = r.headers.get('content-type') || ''
        if (ct.includes('text/html')) return false
        const data = await r.json() as { running?: boolean }
        return Boolean(data?.running)
      }
      if (service === 'ollama') {
        const r = await fetch(`${base}/proxy/ollama/api/tags`, { signal: AbortSignal.timeout(6000) })
        return r.ok
      }
      return false
    } catch {
      return false
    }
  }

  async function tryStart(): Promise<{ ok: boolean; detail: string }> {
    if (service === 'comfyui') {
      try {
        const r = await fetch(`${base}/api/comfyui/start`, {
          method: 'POST',
          signal: AbortSignal.timeout(90_000),
        })
        if (!r.ok) {
          const text = await r.text().catch(() => '')
          return { ok: false, detail: `start HTTP ${r.status}: ${text.slice(0, 160)}` }
        }
        const ct = r.headers.get('content-type') || ''
        if (ct.includes('text/html')) {
          return { ok: false, detail: 'start proxy retourne HTML (tunnel/bridge indisponible)' }
        }
        const data = await r.json() as { ok?: boolean; ready?: boolean; error?: string }
        if (data?.ready || data?.ok) return { ok: true, detail: 'ComfyUI demarre par le bridge' }
        return { ok: false, detail: data?.error || 'start: reponse sans ready/ok' }
      } catch (err) {
        return { ok: false, detail: err instanceof Error ? err.message : String(err) }
      }
    }
    // Ollama auto-start via bridge (best effort — generally already managed by start.sh).
    return { ok: await probe(), detail: 'ollama: pas de bootstrap explicite cote bridge' }
  }

  // 1) Honest probe first.
  if (await probe()) {
    return {
      id: service, label: service, available: true, running: true,
      startedByApp: false, progress: 100, detail: 'Service actif (probe OK)',
      path: null, processId: null,
    } satisfies RuntimeServiceInfo
  }

  // 2) Ask the bridge to start it and wait — up to 3 probe rounds for ~20 s total
  //    because ComfyUI needs a few seconds to bind its port after start.sh spawn.
  const startResult = await tryStart()
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (await probe()) {
      return {
        id: service, label: service, available: true, running: true,
        startedByApp: startResult.ok, progress: 100,
        detail: startResult.ok ? 'Demarre a la demande du module' : 'Actif (probe OK)',
        path: null, processId: null,
      } satisfies RuntimeServiceInfo
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }

  // 3) Still down: return a truthful failing state with the actual error from the bridge.
  return {
    id: service, label: service, available: false, running: false,
    startedByApp: false, progress: 0,
    detail: startResult.detail || 'Service indisponible apres tentative de demarrage',
    path: null, processId: null,
  } satisfies RuntimeServiceInfo
}

export async function runtimePrepareOllamaModel(model: string) {
  if (isTauriRuntime()) {
    return desktopInvoke<{ ok: boolean; detail: string }>('runtime_prepare_ollama_model', { model })
  }

  if (isCloudRuntime()) {
    return { ok: true, detail: 'Cloud Ready' }
  }

  return { ok: true, detail: 'Browser mode — no model prep needed' }
}

export async function runtimeEnsureOllamaModelAvailable(model: string) {
  if (isTauriRuntime()) {
    return desktopInvoke<{ ok: boolean; detail: string }>('runtime_ensure_ollama_model_available', { model })
  }

  return cloudInvoke<{ ok: boolean; detail: string }>('/api/runtime/prepare-model', { model })
}

export async function getHostPrivilegeStatus() {
  if (isTauriRuntime()) {
    return desktopInvoke<HostPrivilegeStatus>('get_host_privilege_status')
  }

  try {
    const resp = await fetch(`${getBridgeUrl()}/api/runtime/privilege`)
    if (resp.ok) return safeParseJson<HostPrivilegeStatus>(resp, 'Host privilege')
  } catch {
    // Bridge unreachable
  }

  return { isAdmin: false, canElevate: false, detail: 'Browser mode' } as HostPrivilegeStatus
}

export async function restartApplicationAsAdmin() {
  if (isTauriRuntime()) {
    return desktopInvoke<{ ok: boolean; detail: string }>('restart_application_as_admin')
  }

  // Pas besoin en cloud — deja root
  return { ok: true, detail: 'Cloud mode — already root' }
}

export async function linuxRuntimeCheck() {
  if (isTauriRuntime()) {
    return desktopInvoke<LinuxRuntimeCheckReport>('linux_runtime_check')
  }

  return {
    platform: 'browser',
    isLinux: false,
    ready: true,
    needsInstall: false,
    workspacePath: null,
    markerPath: null,
    logPath: null,
    installCommand: null,
    detail: 'Browser mode',
    items: [],
  } satisfies LinuxRuntimeCheckReport
}

export async function linuxRuntimeInstallMissing(options?: {
  maxQuality?: boolean
  installNvidiaDriver?: boolean
}) {
  if (isTauriRuntime()) {
    return desktopInvoke<{ ok: boolean; detail: string }>('linux_runtime_install_missing', {
      maxQuality: options?.maxQuality ?? true,
      installNvidiaDriver: options?.installNvidiaDriver ?? false,
    })
  }

  return { ok: true, detail: 'Browser mode' }
}

export async function runtimeReleaseService(service: RuntimeServiceId, model?: string) {
  if (isTauriRuntime()) {
    return desktopInvoke<RuntimeServiceInfo>('runtime_release_service', { service, model })
  }

  // Cloud : services permanents, pas de release
  return {
    id: service, label: service, available: true, running: true,
    startedByApp: false, progress: 100, detail: 'Cloud permanent', path: null, processId: null,
  } satisfies RuntimeServiceInfo
}

// ---------------------------------------------------------------------------
// Event listeners (progress)
// ---------------------------------------------------------------------------

export async function onPythonProgress(callback: (progress: string) => void) {
  if (isTauriRuntime()) {
    return safeListen<string>('python-progress', callback)
  }

  if (isCloudRuntime()) {
    return _startCloudProgressPolling(callback)
  }

  return () => { }
}

export async function onRuntimeProgress(callback: (payload: RuntimeProgressEvent) => void) {
  if (isTauriRuntime()) {
    return safeListen<RuntimeProgressEvent>('runtime-progress', callback)
  }

  // Cloud : pas d'evenements runtime natifs, le start.sh gere tout
  return () => { }
}

// ---------------------------------------------------------------------------
// Filesystem
// ---------------------------------------------------------------------------

export async function getWorkspacePath(): Promise<string> {
  if (isTauriRuntime()) {
    return desktopInvoke<string>('get_workspace_path')
  }

  const resp = await fetch(`${getBridgeUrl()}/api/fs/workspace-path`)
  const result = await safeParseJson<{ path: string }>(resp, 'Workspace path')
  return result.path
}

export async function fsExists(path: string): Promise<boolean> {
  if (isTauriRuntime()) {
    return desktopInvoke<boolean>('fs_exists', { path })
  }

  const result = await cloudInvoke<{ exists: boolean }>('/api/fs/exists', { path })
  return result.exists
}

export async function fsMkdir(path: string): Promise<void> {
  if (isTauriRuntime()) {
    return desktopInvoke<void>('fs_mkdir', { path })
  }

  await cloudInvoke<{ ok: boolean }>('/api/fs/mkdir', { path })
}

export async function fsListDir(path: string): Promise<string[]> {
  if (isTauriRuntime()) {
    return desktopInvoke<string[]>('fs_list_dir', { path })
  }

  const result = await cloudInvoke<{ entries: string[] }>('/api/fs/list', { path })
  return result.entries
}

export async function fsRemoveDirAll(path: string): Promise<void> {
  if (isTauriRuntime()) {
    return desktopInvoke<void>('fs_remove_dir_all', { path })
  }

  await cloudInvoke<{ ok: boolean }>('/api/fs/remove-dir', { path })
}

export async function fsReadText(path: string): Promise<string> {
  if (isTauriRuntime()) {
    return desktopInvoke<string>('fs_read_text', { path })
  }

  const result = await cloudInvoke<{ content: string }>('/api/fs/read-text', { path })
  return result.content
}

export async function fsWriteText(path: string, content: string): Promise<void> {
  if (isTauriRuntime()) {
    return desktopInvoke<void>('fs_write_text', { path, content })
  }

  await cloudInvoke<{ ok: boolean }>('/api/fs/write-text', { path, content })
}

export async function fsWriteBinary(path: string, bytes: number[]): Promise<void> {
  if (isTauriRuntime()) {
    return desktopInvoke<void>('fs_write_binary', { path, bytes })
  }

  await cloudInvoke<{ ok: boolean }>('/api/fs/write-binary', { path, bytes })
}

export async function fsReadBinary(path: string): Promise<number[]> {
  if (isTauriRuntime()) {
    return desktopInvoke<number[]>('fs_read_binary', { path })
  }

  const result = await cloudInvoke<{ bytes: number[] }>('/api/fs/read-binary', { path })
  return result.bytes
}

// ---------------------------------------------------------------------------
// Asset URL
// ---------------------------------------------------------------------------

export function toAssetUrl(path: string) {
  if (isTauriRuntime()) {
    return convertFileSrc(path)
  }

  if (!path) return path
  if (/^(https?:|data:|blob:|file:)/i.test(path)) return path

  // Cloud/tunnel/browser-local: route through bridge
  const cleaned = path
    .replace(/\\/g, '/')
    .replace(/^\/workspace\/output\//, '')
    .replace(/^\/workspace\/aurora\//, '')

  // Encode each segment so espaces, accents et #/? n'explosent pas le fetch
  const encoded = cleaned
    .split('/')
    .map((segment) => (segment ? encodeURIComponent(segment) : segment))
    .join('/')
  return `${getBridgeUrl()}/api/asset/${encoded}`
}
