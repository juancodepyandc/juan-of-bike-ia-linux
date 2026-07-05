/**
 * Frontend coordinator for ENT access.
 *
 * Browser runtime uses Aurora-Connect's encrypted vault. Desktop runtime uses
 * the local bridge to open a native web session, scrape authenticated pages,
 * download files, and store the extracted data locally.
 */
import { getBridgeUrl } from '../utils/runtime.ts'
import { detectAdapter, type EntAdapter, type EntSection } from './entAdapters.ts'
import { postHarvest } from './entHarvestService.ts'
import { useEntSessionStore } from '../stores/entSessionStore.ts'

export type AutoLoginResult = {
  ok: boolean
  reason?: 'captcha' | 'mfa' | 'no_password_field' | 'no_username_field' | 'no_submit_button' | 'auth_failed' | 'exception' | 'extension_unreachable' | 'vault_locked' | 'no_entry'
  message?: string
}

export type AnalyzeDomResult = {
  ok: boolean
  items: Array<Record<string, unknown>>
  extractedCount: number
  error?: string
}

export type NativeEntPipelineResult = {
  ok: boolean
  mode?: 'desktop_native_browser'
  totalItems?: number
  sectionResults: Record<string, { ok: boolean; itemsCount?: number; error?: string }>
  reason?: string
  error?: string
}

type ScrapedAttachment = {
  url?: string
  text?: string
  filename?: string
  download?: string
  type?: string
  mime?: string
  localPath?: string
  downloaded?: boolean
  sizeBytes?: number
  scope?: string
}

type EntSnapshot = {
  text: string
  title: string
  url: string
  containers: unknown[]
}

async function parseJsonResponse<T>(response: Response): Promise<{ data?: T; error?: string }> {
  const text = await response.text()
  if (!text.trim()) return { data: {} as T }
  try {
    return { data: JSON.parse(text) as T }
  } catch {
    const preview = text.replace(/\s+/g, ' ').slice(0, 180)
    return { error: `Réponse bridge illisible (${response.status}). ${preview || 'Aucun détail.'}` }
  }
}

function fileNameFromUrl(url: string): string {
  try {
    const u = new URL(url)
    const last = u.pathname.split('/').filter(Boolean).pop()
    return decodeURIComponent(last || 'document')
  } catch {
    return url.split('/').filter(Boolean).pop() || 'document'
  }
}

function fallbackItemsFromScrape(
  section: EntSection,
  snapshot: EntSnapshot,
  attachments: ScrapedAttachment[],
  error?: string,
): Array<Record<string, unknown>> {
  const files = attachments
    .filter((a) => a.url)
    .slice(0, 200)
    .map((a) => ({
      filename: a.filename || a.download || a.text || fileNameFromUrl(String(a.url)),
      url: a.url,
      localPath: a.localPath || '',
      downloaded: !!a.downloaded,
      sizeBytes: a.sizeBytes || 0,
      subject: '',
      chapter: snapshot.title || '',
      mime: a.mime || a.type || '',
      raw: a.text || '',
      source: 'attachment_link',
      scope: a.scope || '',
    }))

  if (files.length > 0) {
    if (section === 'fichiers') return files
    return [{
      title: snapshot.title || section,
      date: '',
      description: snapshot.text.slice(0, 4000),
      attachments: files.map((f) => ({
        url: f.url,
        filename: f.filename,
        localPath: f.localPath,
        downloaded: f.downloaded,
      })),
      raw: snapshot.text.slice(0, 8000),
      source: 'scrape_fallback',
      extractionError: error || '',
    }]
  }

  const raw = (snapshot.text || '').trim()
  if (!raw) return []
  return [{
    title: snapshot.title || section,
    url: snapshot.url,
    raw: raw.slice(0, 12000),
    source: 'raw_scrape_fallback',
    extractionError: error || '',
  }]
}

/** Send command to extension via bridge dispatch + poll for result. */
async function dispatchToExtension(
  extId: string,
  kind: string,
  payload: Record<string, unknown>,
  timeoutMs = 10000,
): Promise<{ ok: boolean; data?: unknown; error?: string }> {
  try {
    const res = await fetch(`${getBridgeUrl()}/api/cowork/extension/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ extId, kind, payload }),
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) return { ok: false, error: `dispatch HTTP ${res.status}` }
    const parsed = await parseJsonResponse<{ ok?: boolean; commandId?: string; error?: string }>(res)
    if (parsed.error || !parsed.data) {
      return { ok: false, error: parsed.error || 'dispatch returned no JSON' }
    }
    const data = parsed.data
    if (!data.ok || !data.commandId) {
      return { ok: false, error: data.error || 'dispatch fail' }
    }
    // Poll for result.
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const wait = await fetch(
        `${getBridgeUrl()}/api/cowork/extension/await-result?commandId=${data.commandId}&wait=2000`,
        { signal: AbortSignal.timeout(3000) },
      )
      if (wait.ok) {
        const parsed = await parseJsonResponse<{ ok?: boolean; result?: unknown; pending?: boolean }>(wait)
        if (parsed.error || !parsed.data) continue
        const r = parsed.data
        if (!r.pending && r.result !== undefined) {
          return { ok: true, data: r.result }
        }
      }
    }
    return { ok: false, error: 'timeout waiting for extension result' }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

/** Ask Aurora-Connect to fill and submit the saved login form. */
export async function requestAutoLogin(extId: string, siteKey: string): Promise<AutoLoginResult> {
  const r = await dispatchToExtension(extId, 'autologin', { siteKey }, 30000)
  if (!r.ok) return { ok: false, reason: 'extension_unreachable', message: r.error }
  const data = r.data as AutoLoginResult | undefined
  if (!data) return { ok: false, reason: 'extension_unreachable', message: 'no data' }
  return data
}

/** Check that the current tab looks authenticated before scraping. */
export async function verifyAuth(extId: string, adapter: EntAdapter): Promise<{
  ok: boolean
  score: number
  hint?: string
}> {
  const r = await dispatchToExtension(extId, 'verify-auth', {
    authMarkers: adapter.authMarkers,
  }, 8000)
  if (!r.ok) return { ok: false, score: 0, hint: r.error }
  const data = r.data as { ok?: boolean; score?: number } | undefined
  if (!data) return { ok: false, score: 0, hint: 'no data from ext' }
  return {
    ok: data.ok === true,
    score: typeof data.score === 'number' ? data.score : 0,
    hint: data.ok ? undefined : 'auth markers absent ou erreur visible',
  }
}

/** Scrape a school section, extract structured data, then persist it. */
export async function scrapeAndAnalyze(
  extId: string,
  adapter: EntAdapter,
  section: EntSection,
): Promise<{
  ok: boolean
  itemsCount?: number
  error?: string
}> {
  // Navigate to the requested section before scraping. Pronote and most ENT
  // portals are SPAs, so scraping the home page would otherwise return the
  // same content for homework, grades, files, and agenda.
  const sectionPath = adapter.sections?.[section]
  const scrape = await dispatchToExtension(
    extId,
    'scrape-page',
    { section, sectionPath },
    20000,
  )
  if (!scrape.ok) return { ok: false, error: scrape.error || 'scrape ext fail' }
  const scrapeData = scrape.data as {
    ok?: boolean
    snapshot?: EntSnapshot
    attachments?: ScrapedAttachment[]
    hostname?: string
    error?: string
  } | undefined
  if (!scrapeData?.snapshot) {
    return { ok: false, error: scrapeData?.error || 'no snapshot' }
  }

  // 3b. POST analyze-dom au bridge.
  let analyzed: AnalyzeDomResult
  try {
    const res = await fetch(`${getBridgeUrl()}/api/ent/analyze-dom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        adapter: adapter.id,
        section,
        snapshot: scrapeData.snapshot,
        hostname: scrapeData.hostname || '',
      }),
      signal: AbortSignal.timeout(180000),
    })
    if (!res.ok) return { ok: false, error: `analyze-dom HTTP ${res.status}` }
    const parsed = await parseJsonResponse<AnalyzeDomResult>(res)
    if (parsed.error || !parsed.data) return { ok: false, error: parsed.error || 'analyze-dom JSON fail' }
    analyzed = parsed.data
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'analyze-dom fail' }
  }

  const fallbackItems = !analyzed.ok || analyzed.extractedCount === 0
    ? fallbackItemsFromScrape(section, scrapeData.snapshot, scrapeData.attachments || [], analyzed.error || 'no items extracted')
    : []
  const itemsToPersist = fallbackItems.length > 0 ? fallbackItems : analyzed.items
  const itemsCount = fallbackItems.length > 0 ? fallbackItems.length : analyzed.extractedCount
  if (itemsToPersist.length === 0) {
    return { ok: false, error: analyzed.error || 'no items extracted' }
  }

  // 3c. Persist via harvest API.
  try {
    const harvest = await postHarvest({
      adapter: adapter.id,
      section,
      hostname: scrapeData.hostname || '',
      items: itemsToPersist,
    })
    if (harvest.ok) {
      // Update store.
      useEntSessionStore.getState().recordHarvest(adapter.id, section, {
        ts: Date.now(),
        count: itemsCount,
        hostname: scrapeData.hostname || '',
      })
      useEntSessionStore.getState().setActive(adapter.id, scrapeData.hostname || null)
    }
    return { ok: true, itemsCount }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'harvest fail' }
  }
}

export async function runNativeEntPipeline(args: {
  adapter: EntAdapter
  loginUrl: string
  username: string
  password: string
  sections: EntSection[]
  profileKey?: string
}): Promise<NativeEntPipelineResult> {
  const { adapter, loginUrl, username, password, sections, profileKey } = args
  let hostname = ''
  try { hostname = new URL(loginUrl).hostname } catch { hostname = '' }
  try {
    const res = await fetch(`${getBridgeUrl()}/api/ent/native/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        adapter: adapter.id,
        loginUrl,
        username,
        password,
        sections,
        sectionPaths: adapter.sections,
        profileKey: profileKey || `${adapter.id}-${hostname || 'ent'}`,
      }),
      signal: AbortSignal.timeout(260000),
    })
    const parsed = await parseJsonResponse<NativeEntPipelineResult>(res)
    if (parsed.error || !parsed.data) {
      return { ok: false, error: parsed.error || `HTTP ${res.status}`, sectionResults: {} }
    }
    const data = parsed.data
    if (!res.ok) {
      return { ok: false, error: data.error || `HTTP ${res.status}`, sectionResults: {} }
    }
    if (data.ok) {
      for (const [section, result] of Object.entries(data.sectionResults || {})) {
        if (result.ok) {
          useEntSessionStore.getState().recordHarvest(adapter.id, section as EntSection, {
            ts: Date.now(),
            count: result.itemsCount || 0,
            hostname,
          })
        }
      }
      useEntSessionStore.getState().setActive(adapter.id, hostname || null)
    }
    return { ...data, sectionResults: data.sectionResults || {} }
  } catch (err) {
    return {
      ok: false,
      reason: 'native_bridge_error',
      error: err instanceof Error ? err.message : String(err),
      sectionResults: {},
    }
  }
}

/** Pipeline complet : login + verify + scrape multi-sections. */
export async function fullPipeline(args: {
  extId: string
  siteKey: string
  adapter: EntAdapter
  sections: EntSection[]
  onProgress?: (step: string, detail?: string) => void
}): Promise<{
  ok: boolean
  loginResult: AutoLoginResult
  authResult?: { ok: boolean; score: number }
  sectionResults: Record<string, { ok: boolean; itemsCount?: number; error?: string }>
}> {
  const { extId, siteKey, adapter, sections, onProgress } = args
  const sectionResults: Record<string, { ok: boolean; itemsCount?: number; error?: string }> = {}

  onProgress?.('login', 'Tentative auto-login...')
  const loginResult = await requestAutoLogin(extId, siteKey)
  if (!loginResult.ok) {
    return { ok: false, loginResult, sectionResults }
  }

  // Settle 3s.
  await new Promise((r) => setTimeout(r, 3000))

  onProgress?.('verify', 'Verification auth...')
  const authResult = await verifyAuth(extId, adapter)
  if (!authResult.ok) {
    return { ok: false, loginResult, authResult, sectionResults }
  }

  for (const section of sections) {
    onProgress?.('scrape', `Section ${section}...`)
    const r = await scrapeAndAnalyze(extId, adapter, section)
    sectionResults[section] = r
  }

  return { ok: true, loginResult, authResult, sectionResults }
}

/** Helper : detect adapter depuis URL et retourne null si inconnu. */
export function detectAdapterFromUrl(url: string): EntAdapter | null {
  try {
    const u = new URL(url)
    return detectAdapter(u.hostname)
  } catch { return null }
}

