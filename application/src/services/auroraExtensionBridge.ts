/**
 * Shared web access for Aurora modules.
 *
 * In a normal browser, this talks to Aurora-Connect. In the desktop app, the
 * same capabilities fall back to Tauri commands or the local bridge so the app
 * is not blocked by a missing browser extension.
 */

import { invoke } from '@tauri-apps/api/core'
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'

const extensionApiBase = () => `${getBridgeUrl()}/api/cowork/extension`
const DEFAULT_TIMEOUT_MS = 25_000

export type BridgeResult<T> =
  | { ok: true; data: T; extId?: string }
  | { ok: false; reason: string }

export type ExtensionInfo = {
  extId: string
  url?: string
  title?: string
  lastSeen?: number
}

async function listExtensions(signal?: AbortSignal): Promise<ExtensionInfo[]> {
  try {
    const response = await fetch(`${extensionApiBase()}/list`, { signal })
    if (!response.ok) return []
    const data = (await response.json()) as { ok?: boolean; extensions?: ExtensionInfo[] }
    if (!data.ok) return []
    return Array.isArray(data.extensions) ? data.extensions : []
  } catch {
    return []
  }
}

async function pickActiveExtension(signal?: AbortSignal): Promise<ExtensionInfo | null> {
  const extensions = await listExtensions(signal)
  if (extensions.length === 0) return null
  // Prefer the most recently seen extension.
  const ranked = [...extensions].sort((a, b) => (b.lastSeen ?? 0) - (a.lastSeen ?? 0))
  return ranked[0] ?? null
}

async function dispatchCommand(
  extId: string,
  kind: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<BridgeResult<unknown>> {
  try {
    const dispatchResponse = await fetch(`${extensionApiBase()}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extId, kind, payload }),
      signal,
    })
    if (!dispatchResponse.ok) {
      return { ok: false, reason: `dispatch failed: ${dispatchResponse.status}` }
    }
    const dispatchData = (await dispatchResponse.json()) as { ok?: boolean; commandId?: string; error?: string }
    if (!dispatchData.ok || !dispatchData.commandId) {
      return { ok: false, reason: dispatchData.error || 'dispatch returned no commandId' }
    }
    const commandId = dispatchData.commandId

    const awaitResponse = await fetch(
      `${extensionApiBase()}/await-result?commandId=${encodeURIComponent(commandId)}&wait=${DEFAULT_TIMEOUT_MS}`,
      { signal },
    )
    if (!awaitResponse.ok) {
      return { ok: false, reason: `extension command timed out (${awaitResponse.status})` }
    }
    const awaitData = (await awaitResponse.json()) as { ok?: boolean; result?: unknown; error?: string }
    if (!awaitData.ok) {
      return { ok: false, reason: awaitData.error || 'await-result returned ok:false' }
    }
    return { ok: true, data: awaitData.result, extId }
  } catch (error) {
    return { ok: false, reason: `bridge error: ${error instanceof Error ? error.message : String(error)}` }
  }
}

async function postBridgeJson<T>(
  path: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<BridgeResult<T>> {
  try {
    const response = await fetch(`${getBridgeUrl()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
    const text = await response.text()
    let data: T
    try {
      data = (text ? JSON.parse(text) : {}) as T
    } catch {
      return { ok: false, reason: `Bridge a renvoyé une réponse illisible (${response.status})` }
    }
    if (!response.ok) return { ok: false, reason: `Bridge HTTP ${response.status}` }
    return { ok: true, data }
  } catch (error) {
    return { ok: false, reason: `Bridge local indisponible: ${error instanceof Error ? error.message : String(error)}` }
  }
}

async function invokeTauriCommand<T>(command: string, args: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw new Error('Tauri runtime unavailable')
  }
  return await invoke<T>(command, args)
}

function parseDuckDuckGoSearchResults(raw: string): WebSearchHit[] {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => {
      const text = line.slice(2).trim()
      const urlMatch = text.match(/https?:\/\/[^\s]+/i)
      const url = urlMatch?.[0] ?? ''
      const title = url ? text.replace(url, '').trim() : text
      return {
        title: title || text,
        url,
        snippet: text,
      }
    })
}

async function tauriSearchWeb(query: string, limit?: number): Promise<BridgeResult<WebSearchHit[]>> {
  try {
    const response = await invokeTauriCommand<string>('search_duckduckgo', { query })
    const hits = parseDuckDuckGoSearchResults(response).slice(0, limit ?? 5)
    return { ok: true, data: hits }
  } catch (error) {
    return { ok: false, reason: `Recherche locale Tauri échouée: ${error instanceof Error ? error.message : String(error)}` }
  }
}

async function bridgeSearchWeb(
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<BridgeResult<WebSearchHit[]>> {
  const bridge = await postBridgeJson<{
    ok?: boolean
    hits?: WebSearchHit[]
    results?: WebSearchHit[]
    error?: string
  }>('/api/web/search', { query, limit: options.limit ?? 5 }, options.signal)
  if (!bridge.ok) return bridge
  if (bridge.data.ok === false) return { ok: false, reason: bridge.data.error || 'Recherche bridge echouee' }
  const hits = (bridge.data.hits ?? bridge.data.results ?? [])
    .filter((hit) => hit && typeof hit.url === 'string')
    .slice(0, options.limit ?? 5)
  return { ok: true, data: hits }
}

// ---------------------------------------------------------------------------
// High-level capabilities
// ---------------------------------------------------------------------------

export type ReferenceImage = {
  url: string
  title?: string
  source?: string
  width?: number
  height?: number
}

/**
 * Search the user's connected browser for reference images of a subject.
 * Routes via the Aurora extension which opens an image search tab and
 * extracts thumbnail URLs from the result page.
 */
export async function searchReferenceImages(
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<BridgeResult<ReferenceImage[]>> {
  const ext = await pickActiveExtension(options.signal)
  if (!ext) {
    if (isTauriRuntime()) {
      const bridge = await postBridgeJson<{ ok?: boolean; images?: ReferenceImage[]; error?: string }>(
        '/api/web/images',
        { query, limit: options.limit ?? 8 },
        options.signal,
      )
      if (!bridge.ok) return bridge
      if (bridge.data.ok === false) return { ok: false, reason: bridge.data.error || 'Recherche images native échouée' }
      return { ok: true, data: bridge.data.images ?? [] }
    }
    return { ok: false, reason: 'Aurora-Connect extension non détectée. Elle n’est requise que pour le mode navigateur.' }
  }
  const result = await dispatchCommand(
    ext.extId,
    'image_search',
    { query, limit: options.limit ?? 8 },
    options.signal,
  )
  if (!result.ok) return result
  const data = result.data as { images?: ReferenceImage[] } | null
  return { ok: true, data: data?.images ?? [], extId: ext.extId }
}

export type DocumentationSnippet = {
  url: string
  title: string
  text: string
  /** When the docs page exposes a stable version at fetch time. */
  version?: string
}

/**
 * Fetch the official documentation page for a library. The extension
 * resolves the canonical docs URL (e.g. "react" → react.dev/reference) and
 * extracts the readable text. Used by the Code module before generating
 * snippets that rely on a library API.
 */
export async function fetchLibraryDocumentation(
  libraryName: string,
  options: { topic?: string; signal?: AbortSignal } = {},
): Promise<BridgeResult<DocumentationSnippet>> {
  const ext = await pickActiveExtension(options.signal)
  if (!ext) {
    if (isTauriRuntime()) {
      const query = `${libraryName} ${options.topic ?? ''} official documentation`.trim()
      const search = await searchWeb(query, { limit: 3, signal: options.signal })
      if (!search.ok) return search as BridgeResult<DocumentationSnippet>
      const first = search.data.find((hit) => /^https?:\/\//i.test(hit.url))
      if (!first) return { ok: false, reason: 'Aucune documentation trouvée par la recherche native.' }
      const extracted = await postBridgeJson<Record<string, unknown>>(
        '/api/web/extract',
        { url: first.url, prompt: `Extract readable official documentation for ${libraryName} ${options.topic ?? ''}` },
        options.signal,
      )
      if (!extracted.ok) return extracted as BridgeResult<DocumentationSnippet>
      const raw = extracted.data
      const text = String(raw.text || raw.content || raw.markdown || raw.html || raw.result || first.snippet || '').slice(0, 20000)
      return {
        ok: true,
        data: {
          url: String(raw.url || first.url),
          title: String(raw.title || first.title || libraryName),
          text,
        },
      }
    }
    return { ok: false, reason: 'Aurora-Connect extension non détectée. Elle n’est requise que pour le mode navigateur.' }
  }
  const result = await dispatchCommand(
    ext.extId,
    'documentation_fetch',
    { library: libraryName, topic: options.topic ?? '' },
    options.signal,
  )
  if (!result.ok) return result
  const data = result.data as DocumentationSnippet | null
  if (!data) return { ok: false, reason: 'documentation_fetch returned empty result' }
  return { ok: true, data, extId: ext.extId }
}

export type PackageVersionInfo = {
  name: string
  registry: 'npm' | 'pypi' | 'crates'
  latest: string
  /** Release date when the registry exposes one. */
  releasedAt?: string
}

/**
 * Validate a package's latest stable version against npm/pypi/crates. Used
 * by the Code module before writing dependencies into manifests so we don't
 * generate broken `npm install` commands.
 */
export async function checkPackageVersion(
  packageName: string,
  registry: 'npm' | 'pypi' | 'crates' = 'npm',
  signal?: AbortSignal,
): Promise<BridgeResult<PackageVersionInfo>> {
  const ext = await pickActiveExtension(signal)
  if (!ext) {
    if (isTauriRuntime()) {
      return await checkPackageVersionNative(packageName, registry, signal)
    }
    return { ok: false, reason: 'Aurora-Connect extension non détectée. Elle n’est requise que pour le mode navigateur.' }
  }
  const result = await dispatchCommand(
    ext.extId,
    'package_version_check',
    { package: packageName, registry },
    signal,
  )
  if (!result.ok) return result
  const data = result.data as PackageVersionInfo | null
  if (!data) return { ok: false, reason: 'package_version_check returned empty result' }
  return { ok: true, data, extId: ext.extId }
}

export type WebSearchHit = {
  title: string
  url: string
  snippet: string
}

/**
 * Run a web search via the extension. Used as a generic anti-hallucination
 * lookup when a module needs to verify a fact and Wikipedia + DDG didn't
 * cover it.
 */
export async function searchWeb(
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<BridgeResult<WebSearchHit[]>> {
  if (isTauriRuntime()) {
    const bridge = await bridgeSearchWeb(query, options)
    if (bridge.ok && bridge.data.length > 0) return bridge
    const tauri = await tauriSearchWeb(query, options.limit)
    if (tauri.ok) return tauri
    return bridge.ok ? tauri : bridge
  }
  const ext = await pickActiveExtension(options.signal)
  if (!ext) {
    return { ok: false, reason: 'Aurora-Connect extension non détectée. Elle n’est requise que pour le mode navigateur.' }
  }
  const result = await dispatchCommand(
    ext.extId,
    'web_search',
    { query, limit: options.limit ?? 5 },
    options.signal,
  )
  if (!result.ok) return result
  const data = result.data as { hits?: WebSearchHit[] } | null
  return { ok: true, data: data?.hits ?? [], extId: ext.extId }
}

/**
 * Extract the visible main text of the current active tab. Used by the
 * Voice module ("lis-moi cette page") and the Conversation module
 * ("explique-moi cette page").
 */
export async function extractActiveTabText(
  options: { selector?: string; signal?: AbortSignal } = {},
): Promise<BridgeResult<{ url: string; title: string; text: string }>> {
  const ext = await pickActiveExtension(options.signal)
  if (!ext) {
    if (typeof document !== 'undefined') {
      const selector = options.selector ?? 'article, main, body'
      const element = document.querySelector(selector)
      if (element) {
        const text = element.textContent?.trim().replace(/\s+/g, ' ') ?? ''
        return {
          ok: true,
          data: {
            url: typeof window !== 'undefined' ? window.location.href : '',
            title: typeof document !== 'undefined' ? document.title : '',
            text: text.slice(0, 12000),
          },
        }
      }
    }
    return { ok: false, reason: 'Aucun onglet navigateur connecté. Dans l’app desktop, utilise les actions natives (fetch, recherche web, session ENT) ou ouvre le navigateur avec Aurora-Connect.' }
  }
  const result = await dispatchCommand(
    ext.extId,
    'read_dom',
    { selector: options.selector ?? 'article, main, body' },
    options.signal,
  )
  if (!result.ok) return result
  const raw = result.data as { url?: string; title?: string; data?: string[] } | null
  if (!raw) return { ok: false, reason: 'read_dom returned empty result' }
  return {
    ok: true,
    extId: ext.extId,
    data: {
      url: raw.url ?? ext.url ?? '',
      title: raw.title ?? ext.title ?? '',
      text: Array.isArray(raw.data) ? raw.data.join('\n').slice(0, 12000) : '',
    },
  }
}

/**
 * Lightweight check used by UI badges: is the extension reachable RIGHT NOW?
 * Returns null when not, or the picked extension info when yes.
 */
export async function probeExtension(signal?: AbortSignal): Promise<ExtensionInfo | null> {
  return pickActiveExtension(signal)
}

/** Fetch realistic physical parameters from web search snippets. */
export type PhysicsParams = {
  /** Volumetric mass density in kg/m3 (e.g. wood ~700, steel ~7850, water 1000) */
  densityKgPerM3?: number
  /** Friction coefficient (0..1) for the relevant material pair */
  frictionCoefficient?: number
  /** Restitution / bounciness (0..1) — 0 sticky, 1 perfectly elastic */
  restitution?: number
  /** Angular velocity typical of the subject in rad/s (e.g. wheel at 60 km/h) */
  angularVelocityRadPerS?: number
  /** Local gravitational acceleration in m/s2 (default 9.81) */
  gravityMPerS2?: number
  /** Natural pendulum period in seconds when applicable */
  pendulumPeriodSeconds?: number
  /** Free-form notes the LLM extracted (citation, reasoning) */
  notes?: string
}

export async function lookupPhysicsLaws(
  subject: string,
  options: { hint?: string; signal?: AbortSignal } = {},
): Promise<BridgeResult<PhysicsParams>> {
  const ext = await pickActiveExtension(options.signal)
  if (!ext) {
    if (isTauriRuntime()) {
      const query = options.hint
        ? `${subject} ${options.hint} density friction restitution angular velocity`
        : `${subject} physical properties density friction coefficient`
      const web = await searchWeb(query, { limit: 3, signal: options.signal })
      if (!web.ok) return web as BridgeResult<PhysicsParams>
      return extractPhysicsParams(web.data)
    }
    return { ok: false, reason: 'Aurora-Connect extension non détectée. Elle n’est requise que pour le mode navigateur.' }
  }
  const query = options.hint
    ? `${subject} ${options.hint} density friction restitution angular velocity`
    : `${subject} physical properties density friction coefficient`
  const result = await dispatchCommand(
    ext.extId,
    'web_search',
    { query, limit: 3 },
    options.signal,
  )
  if (!result.ok) return result
  const data = result.data as { hits?: WebSearchHit[] } | null
  return extractPhysicsParams(data?.hits ?? [], ext.extId)
}

async function checkPackageVersionNative(
  packageName: string,
  registry: 'npm' | 'pypi' | 'crates',
  signal?: AbortSignal,
): Promise<BridgeResult<PackageVersionInfo>> {
  try {
    if (registry === 'npm') {
      const response = await fetch(`https://registry.npmjs.org/${encodeURIComponent(packageName)}`, { signal })
      const data = await response.json() as { name?: string; ['dist-tags']?: { latest?: string }; time?: Record<string, string> }
      const latest = data['dist-tags']?.latest
      if (!latest) return { ok: false, reason: 'npm registry: latest introuvable' }
      return { ok: true, data: { name: data.name || packageName, registry, latest, releasedAt: data.time?.[latest] } }
    }
    if (registry === 'pypi') {
      const response = await fetch(`https://pypi.org/pypi/${encodeURIComponent(packageName)}/json`, { signal })
      const data = await response.json() as { info?: { name?: string; version?: string }; releases?: Record<string, Array<{ upload_time_iso_8601?: string }>> }
      const latest = data.info?.version
      if (!latest) return { ok: false, reason: 'PyPI: version introuvable' }
      return { ok: true, data: { name: data.info?.name || packageName, registry, latest, releasedAt: data.releases?.[latest]?.[0]?.upload_time_iso_8601 } }
    }
    const response = await fetch(`https://crates.io/api/v1/crates/${encodeURIComponent(packageName)}`, { signal })
    const data = await response.json() as { crate?: { id?: string; max_stable_version?: string; updated_at?: string } }
    const latest = data.crate?.max_stable_version
    if (!latest) return { ok: false, reason: 'crates.io: version introuvable' }
    return { ok: true, data: { name: data.crate?.id || packageName, registry, latest, releasedAt: data.crate?.updated_at } }
  } catch (error) {
    return { ok: false, reason: `Registry natif indisponible: ${error instanceof Error ? error.message : String(error)}` }
  }
}

function extractPhysicsParams(hits: WebSearchHit[], extId?: string): BridgeResult<PhysicsParams> {
  const text = hits
    .map((h) => `${h.title ?? ''} ${h.snippet ?? ''}`)
    .join(' ')
    .toLowerCase()
  const params: PhysicsParams = {}
  const densityMatch = text.match(/density[^0-9]{0,18}([0-9]{2,5})\s?kg\/?m\^?3/i)
  if (densityMatch) params.densityKgPerM3 = Number(densityMatch[1])
  const frictionMatch = text.match(/(?:friction\s*coefficient|coefficient\s*of\s*friction)[^0-9]{0,16}([0-9]\.[0-9]{1,3})/i)
  if (frictionMatch) params.frictionCoefficient = Number(frictionMatch[1])
  const restitutionMatch = text.match(/(?:restitution|bounciness|coefficient\s*of\s*restitution)[^0-9]{0,16}([0-9]\.[0-9]{1,3})/i)
  if (restitutionMatch) params.restitution = Number(restitutionMatch[1])
  const angularMatch = text.match(/([0-9]{1,4})\s*(?:rpm|rad\/s|tr\/min)/i)
  if (angularMatch) {
    const value = Number(angularMatch[1])
    params.angularVelocityRadPerS = /rpm|tr\/min/i.test(angularMatch[0]) ? (value * Math.PI) / 30 : value
  }
  if (text.includes('pendulum')) {
    const periodMatch = text.match(/period[^0-9]{0,12}([0-9]\.[0-9]{1,3})\s*s/i)
    if (periodMatch) params.pendulumPeriodSeconds = Number(periodMatch[1])
  }
  params.gravityMPerS2 = 9.81
  if (hits[0]) params.notes = (hits[0].snippet ?? '').slice(0, 200)
  return extId ? { ok: true, data: params, extId } : { ok: true, data: params }
}
