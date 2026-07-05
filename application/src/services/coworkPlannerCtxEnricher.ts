// ---------------------------------------------------------------------------
// coworkPlannerCtxEnricher (v82m7) — pure pipeline-context enricher.
//
// Activates the `ineffectiveHosts` and `history[i].delta_history` planner
// signals that were typed in pass 36 but not populated in production.
//
// Two endpoints are queried each planning iteration (when the history shows
// a recent extract on a known host) :
//   - GET /api/cowork/dual-signal-effective?host=<h>  → ineffectiveHosts
//   - GET /api/cowork/extraction-stats?host=<h>        → delta_history per entry
//
// We cache responses by host with a 60-second TTL so a multi-action plan
// loop doesn't hit the bridge twice per host inside the same iteration set.
// Cache lives at module scope (single bridge per process). Pure best-effort —
// every fetch is wrapped in a try/catch that returns null on any error so
// the planner-context build never breaks the plan loop on a network hiccup.
//
// Extracted from coworkPipeline.ts so unit tests can import the enricher
// without dragging in coworkStore / Tauri runtime modules.
// ---------------------------------------------------------------------------

import {
  fetchDualSignalEffective,
  fetchExtractionStats,
  fetchTrendSignalStats,
} from './coworkExtractionStats.ts'
import type { CoworkAction } from './coworkTypes.ts'

const PLANNER_CTX_CACHE_TTL_MS = 60_000

// v82m8 — tier-2 trend-ineffective threshold mirrors the tier-1 contract :
// once a host has emitted at least N TREND nudges and accepted exactly 0,
// we flag it as ineffective so the planner can escalate to TIER_3. The
// number is INTENTIONALLY lower than tier-1's 5 because tier-2 fires only
// after tier-1 has already failed — by the time we get here, even 3 zero-
// acceptance attempts is strong evidence the strategy isn't working.
const TREND_INEFFECTIVE_MIN_EMITTED = 3

type EffectiveCacheEntry = { ts: number; effective: boolean }
type DeltaCacheEntry = { ts: number; deltaHistory: number[] }
type TrendIneffectiveCacheEntry = { ts: number; ineffectiveHosts: string[] }

const _effectiveCache: Map<string, EffectiveCacheEntry> = new Map()
const _deltaHistoryCache: Map<string, DeltaCacheEntry> = new Map()
// v82m8 — global cache (no per-host key, since trend-signal-stats returns
// the top5 in one shot). Cached for 60 s like the others.
let _trendIneffectiveCache: TrendIneffectiveCacheEntry | null = null

// Exported for tests so we can clear / reset between cases.
export function _clearPlannerCtxCachesForTesting(): void {
  _effectiveCache.clear()
  _deltaHistoryCache.clear()
  _trendIneffectiveCache = null
}

// Pure host extraction from a CoworkAction. Returns "" on any failure so
// the caller can short-circuit ("" → no fetch).
function _hostFromAction(action: CoworkAction | null | undefined): string {
  if (!action || typeof action !== 'object') return ''
  if ((action as { kind?: string }).kind !== 'browser') return ''
  if ((action as { operation?: string }).operation !== 'extract_structured') return ''
  const payload = (action as { payload?: unknown }).payload
  if (!payload || typeof payload !== 'object') return ''
  const url = (payload as { url?: unknown }).url
  if (typeof url !== 'string' || !url) return ''
  try {
    const u = new URL(url)
    let h = (u.hostname || '').toLowerCase()
    if (h.startsWith('www.')) h = h.slice(4)
    return h
  } catch {
    return ''
  }
}

// Resolve the per-host effectiveness via the cache, refreshing from the
// bridge on miss / TTL expiry. Returns true (default-trust) on any failure
// so a network hiccup never poisons the planner with a fake "ineffective"
// flag.
async function _isHostEffective(host: string, signal?: AbortSignal): Promise<boolean> {
  if (!host) return true
  const now = Date.now()
  const hit = _effectiveCache.get(host)
  if (hit && now - hit.ts < PLANNER_CTX_CACHE_TTL_MS) {
    return hit.effective
  }
  try {
    const env = await fetchDualSignalEffective(host, { signal })
    if (!env) {
      // Network hit failed — keep last cached value if any, otherwise default trust.
      if (hit) return hit.effective
      return true
    }
    _effectiveCache.set(host, { ts: now, effective: env.effective })
    return env.effective
  } catch {
    if (hit) return hit.effective
    return true
  }
}

// Resolve the per-host delta_history via the cache, refreshing from the
// bridge on miss / TTL expiry. Returns [] on any failure / empty signal.
async function _hostDeltaHistory(host: string, signal?: AbortSignal): Promise<number[]> {
  if (!host) return []
  const now = Date.now()
  const hit = _deltaHistoryCache.get(host)
  if (hit && now - hit.ts < PLANNER_CTX_CACHE_TTL_MS) {
    return hit.deltaHistory
  }
  try {
    const env = await fetchExtractionStats({ signal, host })
    if (!env) {
      if (hit) return hit.deltaHistory
      return []
    }
    // The bridge filters by host on the server side ; we want the row that
    // matches our queried host. The result.by_host_top5 already contains
    // only that host (single-host filter), so we take the first row's
    // delta_history. Defensive : empty on no rows.
    let dh: number[] = []
    if (env.by_host_top5.length > 0) {
      const row = env.by_host_top5[0]
      if (Array.isArray(row.delta_history)) dh = row.delta_history.slice(-5)
    }
    _deltaHistoryCache.set(host, { ts: now, deltaHistory: dh })
    return dh
  } catch {
    if (hit) return hit.deltaHistory
    return []
  }
}

// v82m8 — Resolve per-host trend ineffectiveness via global cache. Reads
// `/api/cowork/trend-signal-stats` once per TTL window and derives the set
// of hosts that have emitted >= TREND_INEFFECTIVE_MIN_EMITTED with zero
// accepted (symmetric with the tier-1 dual-signal-effective contract).
// Returns [] on any failure / empty signal — never breaks the planner.
async function _trendIneffectiveHosts(signal?: AbortSignal): Promise<string[]> {
  const now = Date.now()
  if (_trendIneffectiveCache && now - _trendIneffectiveCache.ts < PLANNER_CTX_CACHE_TTL_MS) {
    return _trendIneffectiveCache.ineffectiveHosts
  }
  try {
    const env = await fetchTrendSignalStats({ signal })
    if (!env) {
      if (_trendIneffectiveCache) return _trendIneffectiveCache.ineffectiveHosts
      return []
    }
    const ineffective: string[] = []
    for (const row of env.by_host_top5) {
      if (!row || typeof row.host !== 'string' || !row.host) continue
      if (row.emitted >= TREND_INEFFECTIVE_MIN_EMITTED && row.accepted === 0) {
        ineffective.push(row.host)
      }
    }
    _trendIneffectiveCache = { ts: now, ineffectiveHosts: ineffective }
    return ineffective
  } catch {
    if (_trendIneffectiveCache) return _trendIneffectiveCache.ineffectiveHosts
    return []
  }
}

/**
 * v82m7 — pipeline planner-context enricher. Pure: takes a base ctx (with
 * the orchestrator's raw history) and produces an enriched ctx where :
 *   - ineffectiveHosts is populated from the bridge for the current
 *     extract entry's host (when effective:false)
 *   - history[i].delta_history is annotated for entries that map to a
 *     known host (cached by host so multi-iter loops don't thrash)
 *
 * v82m8 — additionally populates `trendIneffectiveHosts` from the bridge's
 * `/api/cowork/trend-signal-stats` aggregate so the planner can detect when
 * BOTH tier-1 (DUAL_SIGNAL) and tier-2 (DUAL_SIGNAL_TREND) escalations have
 * been ineffective on the same host → terminal TIER_3 nudge.
 *
 * Generic over T (ctx shape) so the orchestrator's history typing flows
 * through. Errors silently swallowed → empty arrays / no flag, never
 * breaks the planner.
 */
export async function enrichPlannerContextWithBridgeSignals<T extends {
  history: Array<{
    action: CoworkAction
    result: { ok: boolean; data?: unknown; error?: string; durationMs?: number; output?: string }
    under_extraction?: boolean
    reason?: string
    delta_history?: number[]
  }>
  ineffectiveHosts?: string[]
  trendIneffectiveHosts?: string[]
  signal?: AbortSignal
}>(ctx: T): Promise<T & { ineffectiveHosts?: string[]; trendIneffectiveHosts?: string[] }> {
  const signal = ctx.signal
  // 1) Determine the current host from the LAST extract action (if any).
  let currentHost = ''
  for (let i = ctx.history.length - 1; i >= 0; i--) {
    const h = _hostFromAction(ctx.history[i].action)
    if (h) { currentHost = h; break }
  }
  // 2) Build an enriched history with delta_history annotations. We fetch
  //    delta_history per UNIQUE host present in the history (cached) so a
  //    long history doesn't fan out N fetches. Map<host, deltas[]>.
  const uniqueHosts = new Set<string>()
  for (const h of ctx.history) {
    const host = _hostFromAction(h.action)
    if (host) uniqueHosts.add(host)
  }
  const hostDeltas: Map<string, number[]> = new Map()
  await Promise.all(Array.from(uniqueHosts).map(async (host) => {
    const dh = await _hostDeltaHistory(host, signal)
    hostDeltas.set(host, dh)
  }))
  const enrichedHistory = ctx.history.map((entry) => {
    const host = _hostFromAction(entry.action)
    if (!host) return entry
    const dh = hostDeltas.get(host)
    if (!dh || dh.length === 0) return entry
    // Don't clobber an explicitly-set delta_history (defensive — should
    // not happen today since the orchestrator never sets it, but keeps
    // the function idempotent against future direct setters).
    if (Array.isArray(entry.delta_history) && entry.delta_history.length > 0) return entry
    return { ...entry, delta_history: dh }
  })
  // 3) Probe ineffectiveness ONLY for the current host (single-host probe
  //    so we don't fan-out to every host in history — the planner only
  //    cares about WHERE the next extract is going, which is the most-
  //    recent host).
  let ineffectiveHosts: string[] | undefined = ctx.ineffectiveHosts
  if (currentHost) {
    const effective = await _isHostEffective(currentHost, signal)
    if (!effective) {
      const merged = new Set<string>(ineffectiveHosts || [])
      merged.add(currentHost)
      ineffectiveHosts = Array.from(merged)
    }
  }
  // 4) v82m8 — fetch the tier-2 trend ineffective list (single global probe,
  //    cached). Merge with any caller-provided value so manual injection
  //    (tests, future feature flags) wins. Gate : only fire when we already
  //    have a current extract host (no point telling the planner about
  //    ineffective hosts when no extraction is in flight — keeps the
  //    "empty history → no fetch" contract from v82m7).
  let trendIneffectiveHosts: string[] | undefined = ctx.trendIneffectiveHosts
  if (currentHost) {
    const trendList = await _trendIneffectiveHosts(signal)
    if (trendList.length > 0) {
      const merged = new Set<string>(trendIneffectiveHosts || [])
      for (const h of trendList) merged.add(h)
      trendIneffectiveHosts = Array.from(merged)
    }
  }
  return {
    ...ctx,
    history: enrichedHistory,
    ineffectiveHosts,
    trendIneffectiveHosts,
  }
}
