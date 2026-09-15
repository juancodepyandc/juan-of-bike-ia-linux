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
} from '../types/app.ts'
import {
  getBridgeUrl,
  isCloudRuntime,
  isTauriRuntime,
  toBrowserFileUrl,
} from '../utils/runtime.ts'
import { getErrorMessage, safeParseJson } from '../utils/errors.ts'
import { createFirstByteWatchdog, isCallerCancellation } from '../services/ollamaFirstByteWatchdog.ts'
import { readOllamaStream } from '../services/ollamaStream.ts'

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

/**
 * Le transport doit durer plus longtemps que la commande qu il porte.
 *
 * MESURE (runs v131 ET v132, meme cause, nommee des la premiere occurrence par
 * le diagnostic ajoute au commit precedent):
 *
 *   Bridge injoignable sur /api/command/run apres 301s: fetch failed
 *   (Headers Timeout Error). commande: sh -c exec 'podman' 'run' ...
 *
 * 301 s, c est le `headersTimeout` par defaut d undici: 300 000 ms. Le `fetch`
 * de Node abandonne en attendant les EN-TETES pendant qu une commande de
 * sandbox parfaitement legitime (podman + npm install + tsc + build) prend plus
 * de cinq minutes. Le pont n est jamais tombe: health 200 avant et apres, et le
 * processus vivant du debut a la fin des deux runs.
 *
 * Encore un plafond qui mesure autre chose que ce qu il nomme: il s appelle
 * « delai de reponse HTTP » et il borne en realite la duree d un build.
 *
 * `undici` n est pas installable ici (ERR_MODULE_NOT_FOUND), donc on ne peut
 * pas reconfigurer `fetch`. Sous Node on passe donc par `node:http`, dont le
 * delai est explicite et se cale sur celui de la COMMANDE.
 */
/**
 * ATTENTION: ne PAS tester `typeof window === 'undefined'`.
 *
 * Le harnais headless SHIME `globalThis.window` (harness_env.mjs) pour que le
 * code navigateur s importe sous Node. Ma premiere version de cette garde
 * testait l absence de `window`: elle etait donc TOUJOURS fausse sous le
 * harnais, le transport `node:http` n a jamais tourne, et le run v133 est mort
 * exactement comme les deux precedents — 301 s, Headers Timeout Error.
 *
 * Un correctif qui ne s execute pas est indiscernable d un correctif absent.
 * Seul `process.versions.node` distingue vraiment Node d un navigateur.
 */
const isNodeRuntime = () => Boolean(
  (globalThis as { process?: { versions?: { node?: string } } }).process?.versions?.node,
)

type NodeHttpModule = { request: (options: Record<string, unknown>, cb: (res: unknown) => void) => NodeRequestLike }
type NodeRequestLike = {
  setTimeout: (ms: number, cb: () => void) => void
  destroy: (error?: Error) => void
  on: (event: string, cb: (value: unknown) => void) => void
  end: (body: string) => void
}
type NodeResponseLike = {
  statusCode?: number
  setEncoding: (enc: string) => void
  on: (event: string, cb: (chunk: string) => void) => void
}

async function nodeHttpPost<T>(url: string, payload: string, timeoutMs: number): Promise<T> {
  const target = new URL(url)
  // Specificateur calcule: le bundler navigateur ne doit pas tenter de resoudre
  // un module Node, et TypeScript n exige alors pas @types/node.
  const moduleName = target.protocol === 'https:' ? 'node:https' : 'node:http'
  const mod = (await import(/* @vite-ignore */ moduleName)) as unknown as NodeHttpModule
  const contentLength = new TextEncoder().encode(payload).length

  return new Promise<T>((resolve, reject) => {
    const req = mod.request(
      {
        hostname: target.hostname,
        port: target.port || (target.protocol === 'https:' ? 443 : 80),
        path: `${target.pathname}${target.search}`,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': contentLength },
      },
      (raw: unknown) => {
        const res = raw as NodeResponseLike
        let body = ''
        res.setEncoding('utf8')
        res.on('data', (chunk: string) => { body += chunk })
        res.on('end', () => {
          if ((res.statusCode ?? 0) >= 400) {
            reject(new Error(`Bridge HTTP ${res.statusCode} sur ${target.pathname}: ${body.slice(0, 300)}`))
            return
          }
          try { resolve(JSON.parse(body) as T) } catch { reject(new Error(`Reponse illisible du bridge sur ${target.pathname}: ${body.slice(0, 200)}`)) }
        })
      },
    )
    // Le budget du transport DEPASSE celui de la commande: sans cette marge on
    // recreerait exactement le defaut qu on corrige.
    req.setTimeout(timeoutMs, () => { req.destroy(new Error(`Aucune reponse du bridge apres ${Math.round(timeoutMs / 1000)}s`)) })
    req.on('error', (error: unknown) => reject(error instanceof Error ? error : new Error(String(error))))
    req.end(payload)
  })
}

async function cloudInvoke<T>(endpoint: string, args?: Record<string, unknown>): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${getBridgeUrl()}${endpoint}`
  const startedAt = Date.now()
  if (isNodeRuntime()) {
    const commandBudget = typeof args?.timeoutMs === 'number' ? args.timeoutMs : 0
    const transportBudget = Math.max(commandBudget + 120_000, 1_800_000)
    try {
      return await nodeHttpPost<T>(url, JSON.stringify(args || {}), transportBudget)
    } catch (error) {
      // `node:http` indisponible (navigateur reel, bundler): on retombe sur
      // fetch plutot que d echouer — la degradation reste fonctionnelle.
      if (error instanceof Error && /Cannot find module|ERR_MODULE_NOT_FOUND|not supported/i.test(error.message)) {
        return safeParseJson<T>(await fetch(url, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args || {}),
        }), `Cloud bridge ${endpoint}`)
      }
      const elapsed = Math.round((Date.now() - startedAt) / 1000)
      const detail = error instanceof Error ? error.message : String(error)
      throw new Error(`Bridge injoignable sur ${endpoint} apres ${elapsed}s: ${detail}`)
    }
  }
  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(args || {}),
    })
  } catch (error) {
    // Un `fetch failed` NU ne nomme ni l appel, ni sa duree, ni sa cause.
    //
    // Mesure (run v131): la validation sandbox est morte sur « fetch failed »
    // 302 s apres « Verifier test dans le sandbox », alors que le processus du
    // bridge etait vivant du debut a la fin du run (demarre 02:29:19, run
    // 02:43:54 -> 03:05:31). Impossible de trancher entre un test qui pend, une
    // connexion fermee par le relais, ou une contention: le message ne portait
    // rien. Deuxieme occurrence de cette panne, et toujours rien a diagnostiquer.
    //
    // On ne DEVINE pas la cause ici — on la rend mesurable a la prochaine.
    const elapsed = Math.round((Date.now() - startedAt) / 1000)
    const cause = (error as { cause?: unknown })?.cause
    const causeText = cause instanceof Error ? ` (${cause.message})` : ''
    const detail = error instanceof Error ? `${error.message}${causeText}` : String(error)
    const command = typeof args?.executable === 'string'
      ? ` commande: ${args.executable} ${Array.isArray(args.args) ? (args.args as unknown[]).slice(0, 4).join(' ') : ''}`.trimEnd()
      : ''
    throw new Error(`Bridge injoignable sur ${endpoint} apres ${elapsed}s: ${detail}.${command}`)
  }

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
  extraOptions?: { num_ctx?: number; num_predict?: number; baseUrl?: string; signal?: AbortSignal; firstByteTimeoutMs?: number }
) {
  const baseUrl = extraOptions?.baseUrl

  if (isTauriRuntime() && !extraOptions && !model.startsWith('aurora-rl-')) {
    await runtimeEnsureService('ollama')
    await runtimePrepareOllamaModel(model)
    const result = await desktopInvoke<string>('ollama_chat', { model, messages, temperature })
    return JSON.parse(result)
  }

  return ollamaChatStreamAsNonStream(model, messages, {
    temperature,
    num_ctx: extraOptions?.num_ctx,
    num_predict: extraOptions?.num_predict,
    baseUrl,
    signal: extraOptions?.signal,
    firstByteTimeoutMs: extraOptions?.firstByteTimeoutMs,
  })
}

export async function ollamaGenerate(
  model: string,
  prompt: string,
  extraOptions?: { num_ctx?: number; num_predict?: number; signal?: AbortSignal; firstByteTimeoutMs?: number },
) {
  if (isTauriRuntime() && !extraOptions && !model.startsWith('aurora-rl-')) {
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
    extraOptions?.num_predict,
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
    num_predict?: number
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
      num_predict: opts.num_predict,
      baseUrl: opts.baseUrl,
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
  num_predict?: number,
): Promise<{ response: string; done?: boolean }> {
  if (isTauriRuntime() && !model.startsWith('aurora-rl-')) {
    await runtimeEnsureService('ollama')
    await runtimePrepareOllamaModel(model)
  }
  const body: Record<string, unknown> = { model, prompt, stream: true }
  const generationOptions: Record<string, number> = {}
  if (num_ctx !== undefined) generationOptions.num_ctx = num_ctx
  if (num_predict !== undefined) generationOptions.num_predict = num_predict
  if (Object.keys(generationOptions).length) body.options = generationOptions

  const bridge = getBridgeUrl()
  const endpoints = model.startsWith('aurora-rl-')
    ? [bridge ? `${bridge}/proxy/trained/api/generate` : 'http://127.0.0.1:11435/api/generate']
    : isTauriRuntime() ? [`${ollamaBaseUrl()}/api/generate`] : [
    `${bridge}/proxy/ollama/api/generate`,
    `${bridge}/api/ollama/generate`,
    'http://127.0.0.1:11434/api/generate',
  ]

  // v77zap/v90: same first-byte budget as ollamaChatStream. Heavy local code
  // models can override it; the default still protects tunnel calls.
  // v120: increased to 480_000 for heavy SWAP workloads (up to 70GB SWAP allowed).
  // v126: meme correction que ollamaChatStream — budget REARME par tentative et
  // abandon porteur d une raison nommee. Voir ollamaFirstByteWatchdog.ts.
  const HARD_TIMEOUT_MS = firstByteTimeoutMs ?? 480_000
  const watchdog = createFirstByteWatchdog({ model, budgetMs: HARD_TIMEOUT_MS, callerSignal: signal })

  let response: Response | null = null
  let lastError: unknown = null
  try {
    for (const endpoint of endpoints) {
      watchdog.arm(endpoint)
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: watchdog.signal,
        })
        const ct = response.headers.get('content-type') || ''
        const fatal = ct.includes('text/html') || response.status >= 500 || response.status === 404
        if (fatal && endpoints.indexOf(endpoint) < endpoints.length - 1) {
          await response.body?.cancel().catch(() => {})
          response = null
          continue
        }
        break
      } catch (err) {
        lastError = err
        if (isCallerCancellation(err)) throw err
        if (endpoints.indexOf(endpoint) >= endpoints.length - 1) throw err
      }
    }
  } catch (error) {
    watchdog.dispose()
    throw error
  } finally {
    watchdog.disarm()
  }
  try {
    if (!response) throw lastError ?? new Error('Ollama generate indisponible.')
    if (!response.ok || !response.body) {
      const errText = await response.text().catch(() => '')
      throw new Error(`Ollama generate a retourne ${response.status}: ${errText.slice(0, 300)}`)
    }
    let full = ''
    await readOllamaStream(response.body, (payload) => {
      if (typeof payload.response === 'string') full += payload.response
    })
    return { response: full, done: true }
  } finally {
    watchdog.dispose()
  }
}

export async function ollamaListModels(baseUrl?: string) {
  const result = isTauriRuntime()
    ? JSON.parse(await desktopInvoke<string>('ollama_list_models'))
    : await ollamaFetch('/api/tags', { method: 'GET' }, 'Ollama list', baseUrl)
  if (baseUrl) return result
  try {
    const bridge = getBridgeUrl()
    const url = bridge ? `${bridge}/api/training/models` : 'http://127.0.0.1:11435/api/tags'
    const response = await fetch(url, { signal: AbortSignal.timeout(2000) })
    if (response.ok) {
      const trained = await response.json()
      const seen = new Set((result.models || []).map((m: { name: string }) => m.name))
      result.models = [...(result.models || []), ...(trained.models || []).filter((m: { name: string }) => !seen.has(m.name))]
    }
  } catch { /* The base models remain available while the training service is stopped. */ }
  return result
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
    baseUrl?: string
    firstByteTimeoutMs?: number
    // v82lg: callback optionnel pour les tokens de thinking (qwen3 / qwen3-vl
    // en mode reasoning). Permet à l'UI d'afficher une progression "le modèle
    // réfléchit..." au lieu d'une zone vide pendant que le content est encore
    // vide. Le content réel passe toujours par onToken.
    onThinking?: (token: string) => void
  }
) {
  if (isTauriRuntime() && !options?.baseUrl && !model.startsWith('aurora-rl-')) {
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
  const chatEndpoints = options?.baseUrl
    ? [`${options.baseUrl.replace(/\/$/, '')}/api/chat`]
    : model.startsWith('aurora-rl-')
    ? [bridge ? `${bridge}/proxy/trained/api/chat` : 'http://127.0.0.1:11435/api/chat']
    : isTauriRuntime()
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
  // v126: le budget est REARME a chaque point d entree. Mesure (run v125): le
  // bridge relaie Ollama avec `requests(timeout=180)`, donc deux points d entree
  // condamnes pouvaient bruler 360 s des 480 s avant que l appel direct — le seul
  // capable d aboutir — soit tente; le chien de garde coupait alors en pleine
  // generation avec un `abort()` NU, d ou le « This operation was aborted »
  // anonyme qui a tue un run de 39 minutes et 41 fichiers. Voir
  // ollamaFirstByteWatchdog.ts pour les trois mesures qui excluent les autres
  // pistes.
  const HARD_TIMEOUT_MS = options?.firstByteTimeoutMs ?? 480_000
  const watchdog = createFirstByteWatchdog({
    model,
    budgetMs: HARD_TIMEOUT_MS,
    callerSignal: options?.signal,
  })

  let response: Response | null = null
  let lastError: unknown = null

  try {
    for (const endpoint of chatEndpoints) {
      watchdog.arm(endpoint)
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: watchdog.signal,
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
          await response.body?.cancel().catch(() => {})
          response = null
          continue
        }
        break
      } catch (err) {
        lastError = err
        // Une annulation demandee par l appelant traverse la cascade sans etre
        // reessayee: reessayer un arret explicite sur le point d entree suivant
        // n a aucun sens et masquait la demande de l utilisateur.
        if (isCallerCancellation(err)) throw err
        if (chatEndpoints.indexOf(endpoint) >= chatEndpoints.length - 1) throw err
      }
    }
  } catch (error) {
    watchdog.dispose()
    throw error
  } finally {
    // Desarme des les en-tetes recues: le budget borne le PREMIER OCTET, jamais
    // la duree du flux. Le rearmement, lui, a lieu au debut de chaque tentative.
    watchdog.disarm()
  }

  if (!response) {
    watchdog.dispose()
    throw lastError || new Error('Ollama non joignable (ni via bridge, ni directement)')
  }

  if (!response.ok) {
    watchdog.dispose()
    const errBody = await response.text().catch(() => '')
    const detail = errBody ? `: ${errBody.slice(0, 300)}` : ''
    throw new Error(`Ollama error: ${response.status}${detail}`)
  }

  // Détecter réponse HTML au lieu de JSON stream (proxy qui renvoie index.html)
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    watchdog.dispose()
    const htmlBody = await response.text().catch(() => '')
    throw new Error(
      `Ollama stream: reponse HTML au lieu de JSON stream (le service est peut-etre indisponible). ` +
      `Content-Type: ${contentType}. Debut: ${htmlBody.slice(0, 80)}...`
    )
  }

  if (!response.body) {
    watchdog.dispose()
    throw new Error('No response body')
  }

  try {
    await readOllamaStream(response.body, (json) => {
      if (typeof json.message?.content === 'string') {
        try { onToken(json.message.content) } catch { /* callback error — never crash stream */ }
      }
      if (typeof json.message?.thinking === 'string' && options?.onThinking) {
        try { options.onThinking(json.message.thinking) } catch { /* callback error — never crash stream */ }
      }
    })
    try { onDone() } catch { /* callback error — never crash stream */ }
  } finally {
    watchdog.dispose()
  }
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
  // Apply only a locally audited adapter, before either desktop or tunnel routing.
  let prepared: Response | undefined
  try {
    prepared = await fetch(`${getBridgeUrl()}/api/training/image-workflow`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow }), signal: AbortSignal.timeout(15_000),
    })
  } catch { /* Bridge unavailable: the normal ComfyUI path remains usable. */ }
  if (prepared?.ok) {
    workflow = (await prepared.json()).workflow
  } else if (prepared && prepared.status !== 404) {
    throw new Error(`Validation de l’adaptateur image impossible : HTTP ${prepared.status}`)
  }
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
  /** Plafond absolu du suivi. Les rendus video premium peuvent durer une nuit. */
  maxWaitMs?: number
  /** Delai sans aucun evenement PROGRESS avant de considerer le job fige. */
  stalledTimeoutMs?: number
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
      const hardCapMs = options.maxWaitMs ?? 120 * 60 * 1000
      const stalledThresholdMs = options.stalledTimeoutMs ?? 12 * 60 * 1000
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
              if (data.status === 'cancelled') {
                throw new Error(data.error || 'Job annulé.')
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

  // 31/07 (audit): en navigateur local (ni Tauri ni cloud), on rendait un
  // no-op — le pipeline posait alors ses questions de validation dans le
  // vide et bouclait « validation attendue » jusqu'au timeout. Le bridge est
  // joignable sur 127.0.0.1:3001: on branche le meme polling que le cloud.
  return _startCloudProgressPolling(callback)
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
