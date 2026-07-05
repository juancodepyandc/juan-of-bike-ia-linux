// ---------------------------------------------------------------------------
// coworkConnectorPin — tiny localStorage-backed store for user-pinned
// connectors. Closes the audit-driven promote-connector UX loop opened by
// the v82m5 AuditDrawer CTA banner.
//
// Pure model :
//   - one ordered list of `{ connectorId, host, pinnedAt }` rows
//   - `pinConnector(id, host)` adds a row at the TOP (LRU semantics — pinning
//     reddit a second time moves it to the front rather than duplicating)
//   - `readPinnedConnectors()` returns the ordered list (stable identity per call)
//   - `clearPinnedConnectors()` empties the list (mostly for tests)
//
// Storage shape (localStorage key `cowork:connector_pins`) :
//   [{ id: 'reddit', host: 'reddit.com', pinnedAt: 1714e9 }, ...]
//
// Capped at MAX_PINS (8) entries — beyond that the oldest is evicted FIFO so
// the list never grows unbounded if a user pins many connectors over time.
//
// Why a dedicated module rather than fold into moduleConnectorRecommendations
// or the appStore zustand singleton ?
//   - moduleConnectorRecommendations is a static catalog (per-module curated
//     list) — pinning is dynamic user state and shouldn't pollute the catalog
//   - the appStore is React-only — this helper is pure TS and unit-tested
//     under node --test without spinning up React/zustand
//   - keeping the surface tiny (4 functions, 1 type) makes the pin model
//     obvious and easy to ban from the orchestrator if needed
//
// ZERO React, ZERO DOM, ZERO global mutation outside localStorage — passes
// the orchestrator-purity rule (no browser/Tauri imports).
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'cowork:connector_pins'
const MAX_PINS = 8

// v82m8 — chrome.storage.local mirror. The localStorage path always wins for
// reads (synchronous, single source of truth) ; chrome.storage.local is a
// best-effort SECONDARY mirror so the extension popup / service worker can
// read the same pins without going through window.localStorage (not
// available in service workers). The mirror is debounced 200 ms to avoid
// burning chrome.storage.local quota on rapid pin/unpin sequences.
const CHROME_STORAGE_DEBOUNCE_MS = 200

export type PinnedConnector = {
  // The connector identifier the user wants promoted (e.g. 'reddit').
  // We keep it loosely typed (string) so the helper composes with
  // ANY connector id without requiring the ConnectorId enum import.
  id: string
  // The host that triggered the promote-connector CTA (e.g. 'reddit.com').
  // Surfaced in audit so the user can later grep "I pinned reddit because
  // I kept clicking Configurer on reddit.com".
  host: string
  // Unix-ms timestamp at which the row was added/refreshed.
  pinnedAt: number
}

function load(): PinnedConnector[] {
  if (typeof localStorage === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    const rows: PinnedConnector[] = []
    for (const r of parsed) {
      if (!r || typeof r !== 'object') continue
      const obj = r as Record<string, unknown>
      const id = typeof obj.id === 'string' ? obj.id.trim() : ''
      const host = typeof obj.host === 'string' ? obj.host.trim() : ''
      const pinnedAt = typeof obj.pinnedAt === 'number' && Number.isFinite(obj.pinnedAt)
        ? obj.pinnedAt
        : 0
      if (!id) continue
      rows.push({ id, host, pinnedAt })
    }
    return rows.slice(0, MAX_PINS)
  } catch {
    return []
  }
}

function save(rows: PinnedConnector[]): void {
  if (typeof localStorage === 'undefined') return
  try {
    const trimmed = rows.slice(0, MAX_PINS)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
    _scheduleChromeStorageMirror(trimmed)
  } catch {
    // Quota / serialisation error : silently drop oldest half and retry once.
    try {
      const half = rows.slice(0, Math.floor(MAX_PINS / 2))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(half))
      _scheduleChromeStorageMirror(half)
    } catch { /* give up — pin state is non-critical */ }
  }
}

// v82m8 — chrome.storage.local mirror. Best-effort, debounced, never throws.
// Tests can swap the underlying storage facade via `_setChromeStorageForTesting`
// (see exports below). When `chrome.storage.local` isn't present (web runtime,
// non-extension context, jsdom, node), we silently no-op.

type ChromeStorageLikeFacade = {
  set: (items: Record<string, unknown>, callback?: () => void) => void
  get: (
    keys: string | string[] | null,
    callback: (items: Record<string, unknown>) => void,
  ) => void
}

let _chromeStorageOverride: ChromeStorageLikeFacade | null = null
let _mirrorTimer: ReturnType<typeof setTimeout> | null = null
let _mirrorPending: PinnedConnector[] | null = null

function _resolveChromeStorage(): ChromeStorageLikeFacade | null {
  if (_chromeStorageOverride) return _chromeStorageOverride
  // Real extension runtime : chrome.storage.local is the canonical API.
  // We accept any global that exposes the same shape (`browser` for Firefox).
  const g = globalThis as unknown as {
    chrome?: { storage?: { local?: ChromeStorageLikeFacade } }
    browser?: { storage?: { local?: ChromeStorageLikeFacade } }
  }
  if (g.chrome?.storage?.local) return g.chrome.storage.local
  if (g.browser?.storage?.local) return g.browser.storage.local
  return null
}

function _scheduleChromeStorageMirror(rows: PinnedConnector[]): void {
  _mirrorPending = rows
  if (_mirrorTimer) return
  _mirrorTimer = setTimeout(() => {
    _mirrorTimer = null
    const pending = _mirrorPending
    _mirrorPending = null
    if (!pending) return
    const fac = _resolveChromeStorage()
    if (!fac) return
    try {
      fac.set({ [STORAGE_KEY]: pending })
    } catch { /* best-effort mirror */ }
  }, CHROME_STORAGE_DEBOUNCE_MS)
}

/**
 * v82m8 — flush the pending chrome.storage.local mirror immediately. Tests
 * call this to assert the debounce write happened ; production callers can
 * call this on visibilitychange/unload to avoid losing unflushed pins.
 */
export function flushChromeStorageMirror(): void {
  if (_mirrorTimer) {
    clearTimeout(_mirrorTimer)
    _mirrorTimer = null
  }
  const pending = _mirrorPending
  _mirrorPending = null
  if (!pending) return
  const fac = _resolveChromeStorage()
  if (!fac) return
  try { fac.set({ [STORAGE_KEY]: pending }) } catch { /* noop */ }
}

/**
 * v82m8 — test seam : swap the chrome.storage.local facade for an in-memory
 * stub. Pass null to restore real-runtime behaviour. Production code should
 * never call this.
 */
export function _setChromeStorageForTesting(facade: ChromeStorageLikeFacade | null): void {
  _chromeStorageOverride = facade
}

/**
 * v82m8 — hydrate localStorage from the chrome.storage.local mirror on cold
 * start (extension service worker boot, popup open). Asynchronous — the
 * facade `get` returns through a callback so we wrap it in a Promise. When
 * the mirror is empty / unavailable, we leave localStorage untouched (the
 * "pure web" page reload path stays as-is).
 *
 * Idempotent : calling twice does NOT clobber a more-recent localStorage
 * write — we only adopt the mirror when localStorage is currently empty
 * (which is the cold-start signal). This keeps the web path canonical.
 */
export async function hydratePinsFromChromeStorage(): Promise<PinnedConnector[]> {
  const fac = _resolveChromeStorage()
  if (!fac) return load()
  // Skip hydration if localStorage already has rows (web reload path wins).
  if (typeof localStorage !== 'undefined') {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as unknown
        if (Array.isArray(parsed) && parsed.length > 0) return load()
      }
    } catch { /* fall through to chrome hydrate */ }
  }
  return new Promise<PinnedConnector[]>((resolve) => {
    try {
      fac.get(STORAGE_KEY, (items) => {
        try {
          const raw = items?.[STORAGE_KEY]
          if (!Array.isArray(raw) || raw.length === 0) {
            resolve(load())
            return
          }
          const rows: PinnedConnector[] = []
          for (const r of raw) {
            if (!r || typeof r !== 'object') continue
            const obj = r as Record<string, unknown>
            const id = typeof obj.id === 'string' ? obj.id.trim() : ''
            const host = typeof obj.host === 'string' ? obj.host.trim() : ''
            const pinnedAt = typeof obj.pinnedAt === 'number' && Number.isFinite(obj.pinnedAt)
              ? obj.pinnedAt
              : 0
            if (!id) continue
            rows.push({ id, host, pinnedAt })
          }
          const trimmed = rows.slice(0, MAX_PINS)
          if (typeof localStorage !== 'undefined' && trimmed.length > 0) {
            try { localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed)) } catch { /* noop */ }
          }
          resolve(trimmed)
        } catch {
          resolve(load())
        }
      })
    } catch {
      resolve(load())
    }
  })
}

/**
 * Pin a connector at the TOP of the list (LRU semantics — re-pinning the
 * same id moves it to the front rather than duplicating). The host is
 * preserved so the audit trail can show "promoted reddit because of
 * reddit.com clicks". When the list is full, the oldest entry at the tail
 * is dropped automatically (slice(0, MAX_PINS)).
 *
 * Returns the updated full list so callers can render fresh state without
 * a second `readPinnedConnectors` round-trip.
 */
export function pinConnector(connectorId: string, host: string): PinnedConnector[] {
  const id = (connectorId || '').trim()
  if (!id) return load()
  const cleanHost = (host || '').trim()
  const rows = load().filter((r) => r.id !== id)
  rows.unshift({ id, host: cleanHost, pinnedAt: Date.now() })
  const trimmed = rows.slice(0, MAX_PINS)
  save(trimmed)
  return trimmed
}

/**
 * Read the ordered pin list (most-recent first). Always returns a fresh
 * array so React effects can rely on referential identity for diffing.
 */
export function readPinnedConnectors(): PinnedConnector[] {
  return load()
}

/**
 * Returns true when the connector id has been pinned at least once. Useful
 * for the AuditDrawer CTA banner to skip rendering when the user already
 * promoted this host (we don't want to keep nagging them).
 */
export function isConnectorPinned(connectorId: string): boolean {
  const id = (connectorId || '').trim()
  if (!id) return false
  return load().some((r) => r.id === id)
}

/**
 * Wipe all pins. Mostly for tests — production use should be rare since
 * pins are user intent.
 */
export function clearPinnedConnectors(): void {
  if (typeof localStorage === 'undefined') return
  try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
}

// ---------------------------------------------------------------------------
// Promote-connector CTA gate — pure helper consumed by the AuditDrawer.
//
// Given the per-host opt-in summary (sorted desc by count) returned by
// `summariseOptInClicksByHost`, decide whether to surface the CTA banner :
//
//   - empty summary → null (no CTA)
//   - top row count < THRESHOLD → null (signal too weak)
//   - else → { host, count } of the top row
//
// THRESHOLD = 3 per agenda. Pure : no DOM, no React, no global state.
// Caller layers a "dismissed for this session" gate on top so re-renders
// don't keep re-showing the CTA after the user clicked Plus tard.
// ---------------------------------------------------------------------------

export const PROMOTE_CONNECTOR_MIN_COUNT = 3

export type PromoteConnectorCandidate = {
  host: string
  count: number
}

export function selectPromoteConnectorCandidate(
  summary: ReadonlyArray<{ host: string; count: number }>,
): PromoteConnectorCandidate | null {
  if (!summary || summary.length === 0) return null
  // summary is already sorted by count desc with host asc tie-break, so
  // the first row is the "top host". We trust the input contract here so
  // the helper stays O(1).
  const top = summary[0]
  if (!top || typeof top.count !== 'number' || !Number.isFinite(top.count)) return null
  if (top.count < PROMOTE_CONNECTOR_MIN_COUNT) return null
  if (!top.host) return null
  return { host: top.host, count: top.count }
}

/**
 * Map a host (e.g. `reddit.com`, `news.ycombinator.com`) to the connector
 * id we want to pin. Pure heuristic — no network call, no host catalog
 * lookup. The mapping covers the connectors curated in
 * `moduleConnectorRecommendations.ts` plus a few generic OSS hosts.
 *
 * Returns null when no obvious mapping exists ; the caller can fall back
 * to using the host string itself as the connector id (still creates a
 * row in the pin store for future-promote workflows).
 */
// ---------------------------------------------------------------------------
// v82m9 — pin promotion conflict resolver. Pure helper consumed by the
// AuditDrawer to surface a chip when the user has pinned connector X for a
// host but the planner / module-connector recommendations propose a
// DIFFERENT connector Y for the same host.
//
// Inputs :
//   - pinnedConnectors  : the current pin store (from `readPinnedConnectors()`)
//   - plannerRecommendations : a flat list of `{host, connectorId}` rows the
//                              planner / catalog believes apply for this host
//   - host              : the host being evaluated (e.g. 'reddit.com')
//
// Returns :
//   - ConflictDescriptor when (1) a pin matches `host` AND (2) at least one
//     planner reco for the same host names a DIFFERENT connectorId
//   - null when pin matches reco, no pin exists, or no reco surfaces
//
// Pure — no React, no DOM, no store dependencies. Unit-testable under
// node --test without spinning up React/zustand/jsdom.
// ---------------------------------------------------------------------------

export type PinConflictDescriptor = {
  host: string
  pinnedId: string
  suggestedId: string
  message: string
}

export type PlannerConnectorRecommendation = {
  host: string
  connectorId: string
}

export function detectPinConflict(
  pinnedConnectors: ReadonlyArray<PinnedConnector>,
  plannerRecommendations: ReadonlyArray<PlannerConnectorRecommendation>,
  host: string,
): PinConflictDescriptor | null {
  const h = (host || '').toLowerCase().trim()
  if (!h) return null
  const norm = h.startsWith('www.') ? h.slice(4) : h
  if (!Array.isArray(pinnedConnectors) || pinnedConnectors.length === 0) return null
  if (!Array.isArray(plannerRecommendations) || plannerRecommendations.length === 0) return null
  // Find the most-recent pin matching this host (pin store is LRU-ordered
  // top-first, so we take the FIRST match — that's the active pin).
  let pinned: PinnedConnector | null = null
  for (const p of pinnedConnectors) {
    if (!p || typeof p.host !== 'string' || typeof p.id !== 'string') continue
    const ph = p.host.toLowerCase().trim()
    const pNorm = ph.startsWith('www.') ? ph.slice(4) : ph
    if (pNorm === norm) { pinned = p; break }
  }
  if (!pinned) return null
  // Find planner recs for this host. We accept the FIRST suggestion that
  // names a DIFFERENT connector id from the pin — if a reco matches the
  // pin, we treat the conflict as resolved (matched precedence).
  let suggestedId: string | null = null
  for (const r of plannerRecommendations) {
    if (!r || typeof r.host !== 'string' || typeof r.connectorId !== 'string') continue
    const rh = r.host.toLowerCase().trim()
    const rNorm = rh.startsWith('www.') ? rh.slice(4) : rh
    if (rNorm !== norm) continue
    const rid = r.connectorId.trim()
    if (!rid) continue
    if (rid === pinned.id) {
      // Reco matches pin → not a conflict ; short-circuit (the matched
      // case wins over a later mismatched reco for the same host).
      return null
    }
    if (suggestedId === null) suggestedId = rid
  }
  if (!suggestedId) return null
  return {
    host: norm,
    pinnedId: pinned.id,
    suggestedId,
    message: `Tu as épinglé ${pinned.id} mais Aurora suggère ${suggestedId} — confirmer ?`,
  }
}

export function connectorIdForHost(host: string): string | null {
  const h = (host || '').toLowerCase().trim()
  if (!h) return null
  // Strip leading "www." to mirror bridge-side host normalisation.
  const norm = h.startsWith('www.') ? h.slice(4) : h
  // Static lookup table — tiny, audited, no regex, no glob. Keeps the
  // promote-connector path deterministic. Add new entries when a new
  // connector is curated in moduleConnectorRecommendations.
  const TABLE: Record<string, string> = {
    'reddit.com': 'reddit',
    'github.com': 'github',
    'linkedin.com': 'linkedin',
    'twitter.com': 'twitter',
    'x.com': 'twitter',
    'news.ycombinator.com': 'hackernews',
    'stackoverflow.com': 'stackoverflow',
    'huggingface.co': 'huggingface',
    'replicate.com': 'replicate',
    'wikipedia.org': 'wikipedia',
    'arxiv.org': 'arxiv',
  }
  if (TABLE[norm]) return TABLE[norm]
  // Tail-match common parents (e.g. en.wikipedia.org → wikipedia.org).
  for (const [parent, id] of Object.entries(TABLE)) {
    if (norm.endsWith('.' + parent)) return id
  }
  return null
}
