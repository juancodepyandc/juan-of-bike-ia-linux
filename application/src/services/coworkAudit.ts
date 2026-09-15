// ---------------------------------------------------------------------------
// coworkAudit — persistent action log.
//
// Every action that the Cowork pipeline executes (or that is blocked / denied
// by the safety gate) is appended here. The log is kept in localStorage so
// the user can review what Aurora has done across sessions.
//
// We cap the log at 200 entries (FIFO). Each entry is small (~1KB max),
// keeping the storage footprint bounded.
// ---------------------------------------------------------------------------

import type { CoworkAction, CoworkActionResult } from './coworkTypes.ts'

const STORAGE_KEY = 'cowork:audit'
const MAX_ENTRIES = 200
const MAX_DETAIL_LENGTH = 1000

export type CoworkAuditEntry = {
  id: string
  at: number
  action: CoworkAction
  decision: 'allow' | 'confirm' | 'block' | 'skipped' | 'aborted'
  result?: { ok: boolean; output?: string; error?: string; durationMs: number }
  reason?: string
  // Identifier of the user prompt that triggered this entry. Lets the UI
  // group entries from the same Cowork run together when reviewing the log.
  promptId?: string
  // Truncated copy of the user prompt for context. Cap at 200 chars.
  prompt?: string
}

function load(): CoworkAuditEntry[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.slice(-MAX_ENTRIES) as CoworkAuditEntry[]
  } catch {
    return []
  }
}

function save(entries: CoworkAuditEntry[]): void {
  if (typeof localStorage === 'undefined') return
  try {
    const trimmed = entries.slice(-MAX_ENTRIES)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // Quota exceeded → drop oldest half and retry once
    try {
      const half = entries.slice(-Math.floor(MAX_ENTRIES / 2))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(half))
    } catch { /* give up silently */ }
  }
}

export function appendAuditEntry(entry: Omit<CoworkAuditEntry, 'id' | 'at'>): CoworkAuditEntry {
  const full: CoworkAuditEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    at: Date.now(),
    ...entry,
    prompt: entry.prompt ? entry.prompt.slice(0, 200) : undefined,
    result: entry.result
      ? {
          ...entry.result,
          output: trim(entry.result.output),
          error: trim(entry.result.error),
        }
      : undefined,
  }
  const list = load()
  list.push(full)
  save(list)
  return full
}

export function makePromptId(): string {
  return `p-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

export function readAuditLog(): CoworkAuditEntry[] {
  return load()
}

export function clearAuditLog(): void {
  if (typeof localStorage === 'undefined') return
  try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
}

// ---------------------------------------------------------------------------
// v82m2 — opt-in click telemetry
//
// When the user clicks "Configurer" in the connector pill opt-in dialog
// (CoworkOverlay v82m1), we want a persistent record of which sites
// prompted them most often. The audit log is the natural surface :
//   - it already survives reloads (localStorage)
//   - the user can review it via the audit drawer
//   - the entry shape we synthesise reuses the existing `connector` action
//     kind (params.host carries the page hostname), so the existing
//     drawer summariser renders it as "connector <id>.optin_clicked" without
//     a UI change.
//
// We use decision='allow' (the user explicitly consented) and prefix the
// reason with a stable marker so future filters/grep can pull just these
// entries out of the log.
// ---------------------------------------------------------------------------

export const OPTIN_CLICKED_REASON_MARKER = 'connector_optin_clicked'

export function appendConnectorOptInClicked(
  connectorId: string,
  host: string,
): CoworkAuditEntry {
  return appendAuditEntry({
    action: {
      kind: 'connector',
      connector: connectorId,
      action: 'optin_clicked',
      params: { host },
    },
    decision: 'allow',
    reason: OPTIN_CLICKED_REASON_MARKER,
  })
}

export function summariseResultForAudit(result: CoworkActionResult): {
  ok: boolean
  output?: string
  error?: string
  durationMs: number
} {
  return {
    ok: result.ok,
    output: trim(result.output),
    error: trim(result.error),
    durationMs: result.durationMs,
  }
}

// v82m3 — pure filter helper used by the AuditDrawer chip toggle. When
// mode === 'optin', return only entries whose `reason` carries the
// OPTIN_CLICKED_REASON_MARKER. When mode === 'all', return the full list
// (slice for stable identity so callers can rely on a fresh array).
//
// Pure : no React, no DOM, no global state. Tested directly in
// __tests__/coworkAuditOptIn.test.ts so the filter survives any UI
// refactor of the drawer.
export type AuditChipMode = 'all' | 'optin'

export function filterAuditEntriesForChip(
  entries: ReadonlyArray<CoworkAuditEntry>,
  mode: AuditChipMode,
): CoworkAuditEntry[] {
  if (mode === 'all') return entries.slice()
  return entries.filter((e) => e.reason === OPTIN_CLICKED_REASON_MARKER)
}

// v82m4 — per-host opt-in click summary. Pure aggregation of audit entries
// flagged with `OPTIN_CLICKED_REASON_MARKER` (the connector_optin_clicked
// audit helper writes these with `params.host` carrying the page hostname).
// Returns one row per distinct host, sorted by count descending then host
// asc for stable rendering. Empty input or no-opt-in entries → [].
//
// Used by the AuditDrawer to render summary chips
// `[reddit.com x 3] [github.com x 1]` above the entry list when the
// chip filter is active. Pure : no React, no DOM, no global state.
export type OptInHostSummaryRow = {
  host: string
  count: number
}

export function summariseOptInClicksByHost(
  entries: ReadonlyArray<CoworkAuditEntry>,
): OptInHostSummaryRow[] {
  const counts: Record<string, number> = {}
  for (const e of entries) {
    if (e.reason !== OPTIN_CLICKED_REASON_MARKER) continue
    if (e.action.kind !== 'connector') continue
    const params = e.action.params
    if (!params || typeof params !== 'object') continue
    const rawHost = (params as { host?: unknown }).host
    if (typeof rawHost !== 'string') continue
    const host = rawHost.trim()
    if (!host) continue
    counts[host] = (counts[host] || 0) + 1
  }
  const rows: OptInHostSummaryRow[] = Object.entries(counts).map(([host, count]) => ({
    host,
    count,
  }))
  // Sort by count desc, tie-break by host asc for deterministic ordering.
  rows.sort((a, b) => (b.count - a.count) || a.host.localeCompare(b.host))
  return rows
}

function trim(s: string | undefined): string | undefined {
  if (!s) return undefined
  if (s.length <= MAX_DETAIL_LENGTH) return s
  return s.slice(0, MAX_DETAIL_LENGTH) + `\n…[tronque · ${s.length - MAX_DETAIL_LENGTH} octets supprimes]`
}

// v82m7 — pure helper : derive the set of hosts on which Cowork has
// recently issued an `extract_structured` browser action. Used by the
// AuditDrawer to fetch dual-signal-effective per host for the ineffective
// chip surface. Returns a unique, lowercase, www-stripped list. Defensive :
// malformed URLs, missing payloads, non-extract actions are silently
// skipped.
//
// Pure (no React, no localStorage, no fetch) so unit tests can feed
// fixtures directly.
export function listExtractHostsFromAuditEntries(
  entries: ReadonlyArray<CoworkAuditEntry>,
): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const e of entries) {
    if (!e || !e.action) continue
    const a = e.action as { kind?: string; operation?: string; payload?: unknown }
    if (a.kind !== 'browser') continue
    if (a.operation !== 'extract_structured') continue
    const payload = a.payload
    if (!payload || typeof payload !== 'object') continue
    const url = (payload as { url?: unknown }).url
    if (typeof url !== 'string' || !url) continue
    try {
      const u = new URL(url)
      let h = (u.hostname || '').toLowerCase()
      if (h.startsWith('www.')) h = h.slice(4)
      if (!h || seen.has(h)) continue
      seen.add(h)
      out.push(h)
    } catch {
      continue
    }
  }
  return out
}
