/**
 * Typed client for the local ENT harvest endpoints.
 *
 * Aurora uses this service to save and read school data scraped by the
 * browser extension: homework, grades, course files, agenda items, and related
 * attachments.
 */
import { getBridgeUrl } from '../utils/runtime.ts'
import type { EntSection } from './entAdapters.ts'

/** Homework item after DOM extraction and before optional enrichment. */
export type HarvestDevoirItem = {
  title: string
  subject?: string
  date?: string                 // ISO or raw scraped date
  description?: string
  attachments?: Array<{ url?: string; filename?: string }>
  isEval?: boolean
  raw?: string                  // raw fallback text
}

/** Item note */
export type HarvestNoteItem = {
  subject: string
  grade: number | null          // ex: 12.5 (sur scale)
  scale?: number
  classAverage?: number | null
  date?: string
  title?: string
  type?: string                 // DST, DM, oral, etc.
  raw?: string
}

/** Item fichier de cours */
export type HarvestFichierItem = {
  filename: string
  url?: string
  subject?: string
  chapter?: string
  date?: string
  size?: number
  mime?: string
  raw?: string
}

export type HarvestPayload = {
  adapter: string
  section: EntSection
  hostname: string
  ts?: number
  items: Array<HarvestDevoirItem | HarvestNoteItem | HarvestFichierItem | Record<string, unknown>>
}

export type HarvestSummary = {
  adapter: string
  section: string
  ts: number
  count: number
  hostname: string
}

/** Save a scraped ENT section through the local bridge. */
export async function postHarvest(payload: HarvestPayload): Promise<{ ok: boolean; count?: number; error?: string }> {
  try {
    const res = await fetch(`${getBridgeUrl()}/api/ent/harvest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    })
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` }
    return await res.json()
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

/** List locally saved ENT harvests. */
export async function listHarvests(filter?: { adapter?: string; section?: string }): Promise<HarvestSummary[]> {
  try {
    const qs = new URLSearchParams()
    if (filter?.adapter) qs.set('adapter', filter.adapter)
    if (filter?.section) qs.set('section', filter.section)
    const url = `${getBridgeUrl()}/api/ent/list${qs.toString() ? '?' + qs.toString() : ''}`
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
    if (!res.ok) return []
    const data = await res.json() as { ok?: boolean; harvests?: HarvestSummary[] }
    return data.harvests ?? []
  } catch { return [] }
}

/** Read the full payload for one locally saved section. */
export async function getHarvest(adapter: string, section: string): Promise<HarvestPayload | null> {
  try {
    const url = `${getBridgeUrl()}/api/ent/get?adapter=${encodeURIComponent(adapter)}&section=${encodeURIComponent(section)}`
    const res = await fetch(url, { signal: AbortSignal.timeout(10000) })
    if (!res.ok) return null
    const data = await res.json() as { ok?: boolean; data?: HarvestPayload | null }
    return data.data ?? null
  } catch { return null }
}

/** Format a timestamp as a short French relative age. */
export function formatHarvestAge(ts: number): string {
  const dt = Date.now() - ts
  if (dt < 60_000) return 'à l\'instant'
  if (dt < 3_600_000) return `il y a ${Math.floor(dt / 60_000)} min`
  if (dt < 86_400_000) return `il y a ${Math.floor(dt / 3_600_000)} h`
  return `il y a ${Math.floor(dt / 86_400_000)} j`
}

