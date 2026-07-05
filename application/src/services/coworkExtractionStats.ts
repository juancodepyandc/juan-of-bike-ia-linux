// ---------------------------------------------------------------------------
// coworkExtractionStats — pure consumption helpers for the bridge
// `/api/cowork/extraction-stats` endpoint (v82m2).
//
// Composes with the v82m1 backend ring buffer that records yields per
// extract_structured(card_iteration) call. This module exposes :
//
//   - `fetchExtractionStats()` : GET /api/cowork/extraction-stats and parse
//     the JSON envelope into a typed shape. Defensive — returns null on any
//     network/parse error so callers can render a "—" placeholder without
//     try/catching themselves.
//
//   - `colorToneForUnderExtractionRate(rate)` : map the under-extraction
//     ratio (0..1) to a 3-level color tone enum so the UI renders consistent
//     green/amber/red without duplicating thresholds across components.
//     Thresholds picked from the agenda :
//       rate < 0.10  → green (healthy)
//       rate < 0.30  → amber (drift to watch)
//       rate >= 0.30 → red   (degradation, escalate)
//
//   - `formatYieldPct(yieldFraction)` : convert a 0..1 ratio to a "62%"
//     short string. Stable rounding (Math.round, not toFixed) so the output
//     is "62%" not "62.0%".
//
// Pure observability — no mutation, no global state, no React. Tested via
// node --experimental-strip-types (see __tests__/coworkExtractionStats.test.ts).
// ---------------------------------------------------------------------------

export type CoworkExtractionStatsHostRow = {
  host: string
  count: number
  avg_yield: number
  // v82m4 — most-recent host-yield delta vs the host's own prior-entries
  // baseline, in percentage points (pp). Null when the host has fewer than
  // 2 entries in the bridge's `_HOST_YIELD_HISTORY` (no prior baseline).
  // Surfaces the same signal as the `X-Host-Yield-Delta-Pct` response
  // header but READ directly from /extraction-stats so the UI can paint
  // a "this host just degraded" badge without waiting for the next
  // extraction. Negative = degraded, positive = improved.
  last_delta_pct?: number | null
  // v82m5 — up to 5 chronological-asc deltas (each = entry - mean(prior)
  // in pp) for the per-host sparkline trajectory. Empty array when the
  // host has fewer than 2 entries (no delta computable). Lets the UI
  // render a 5-tick mini-bar trend ▁▂▄▆▇ next to the badge so the user
  // sees "drop is part of a downward trend" vs "drop is one-off".
  delta_history?: number[]
}

export type CoworkExtractionStats = {
  total: number
  under_extraction_rate: number
  avg_yield: number
  p50_yield: number
  p90_yield: number
  by_host_top5: CoworkExtractionStatsHostRow[]
  // v82m3 — `host` echoes the optional `host` query param when the
  // caller filtered to a single host. Null when no host filter applied.
  window: { since: number | null; host?: string | null }
}

export type ExtractionStatsTone = 'green' | 'amber' | 'red'

// Thresholds — single source of truth so the tile component, the tests, and
// future consumers (CLI, dashboards) all agree.
export const UNDER_EXTRACTION_GREEN_MAX = 0.10
export const UNDER_EXTRACTION_AMBER_MAX = 0.30

/**
 * Map an under-extraction ratio (0..1) to a 3-level color tone.
 *
 * Defensive : NaN / negative / non-finite ratios fall through to green so a
 * malformed bridge response doesn't paint the tile red on first paint.
 */
export function colorToneForUnderExtractionRate(rate: number): ExtractionStatsTone {
  if (typeof rate !== 'number' || !Number.isFinite(rate) || rate < 0) return 'green'
  if (rate < UNDER_EXTRACTION_GREEN_MAX) return 'green'
  if (rate < UNDER_EXTRACTION_AMBER_MAX) return 'amber'
  return 'red'
}

// v82m4 — delta-badge thresholds. Drives both the colour tone and the
// formatted label of the per-host last-delta badge in
// CoworkExtractionStatsTile. Values mirror the orchestrator's
// HOST_BASELINE_DRIFT_THRESHOLD_PP=-15.0 — at or below -15.0 we paint red
// (matches escalation), -5.0..-15.0 amber (mild drift to watch), >= -5.0
// green (healthy / improved). Single source of truth.
export const DELTA_BADGE_RED_MAX_PP = -15.0
export const DELTA_BADGE_AMBER_MAX_PP = -5.0

export type DeltaBadgeTone = 'green' | 'amber' | 'red'

/**
 * v82m4 — map a signed delta (pp, e.g. +5.0 or -20.0) to a 3-level colour
 * tone for the per-host history badge.
 *
 * Boundaries (strict-less semantics matching the orchestrator) :
 *   - delta <= -15.0 → red    (sharp drop, escalation territory)
 *   - delta <= -5.0  → amber  (mild drift to watch)
 *   - delta >  -5.0  → green  (healthy or improving)
 *
 * Defensive : null / undefined / non-finite → 'green' so a missing baseline
 * never paints alarm. NaN guarded explicitly.
 */
export function colorToneForLastDelta(delta: number | null | undefined): DeltaBadgeTone {
  if (delta === null || delta === undefined) return 'green'
  if (typeof delta !== 'number' || !Number.isFinite(delta)) return 'green'
  if (delta <= DELTA_BADGE_RED_MAX_PP) return 'red'
  if (delta <= DELTA_BADGE_AMBER_MAX_PP) return 'amber'
  return 'green'
}

/**
 * v82m4 — format a signed delta (pp) as a short badge string : `+5.0pp`
 * (positive) or `-20.0pp` (negative) with one decimal. Returns null for
 * null / undefined / non-finite so the caller can skip rendering. Zero is
 * formatted as "+0.0pp" (explicit positive sign for the green tone).
 */
export function formatLastDeltaPp(delta: number | null | undefined): string | null {
  if (delta === null || delta === undefined) return null
  if (typeof delta !== 'number' || !Number.isFinite(delta)) return null
  const sign = delta >= 0 ? '+' : ''
  return `${sign}${delta.toFixed(1)}pp`
}

/**
 * Format a yield fraction (0..1+) as a short percentage string ("62%").
 *
 * Defensive : non-finite or negative inputs render as "—" so the tile shows
 * a neutral placeholder rather than "NaN%" / "-0%". Values >= 1 are clamped
 * to "100%" only for display purposes (the underlying number can exceed 1
 * if the LLM extracts more items than there are cards — possible when a
 * card spans multiple data points).
 */
export function formatYieldPct(yieldFraction: number): string {
  if (typeof yieldFraction !== 'number' || !Number.isFinite(yieldFraction) || yieldFraction < 0) {
    return '—'
  }
  const pct = Math.round(yieldFraction * 100)
  return `${pct}%`
}

/**
 * Parse a raw JSON envelope from /api/cowork/extraction-stats into the
 * typed `CoworkExtractionStats` shape, or null when the envelope is
 * malformed (missing fields, wrong types, ok:false).
 *
 * Pure : no fetch, no global state. Exported so unit tests can feed
 * fixtures directly without standing up an HTTP mock.
 */
export function parseExtractionStatsEnvelope(raw: unknown): CoworkExtractionStats | null {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  if (obj.ok !== true) return null
  const total = typeof obj.total === 'number' && Number.isFinite(obj.total) ? obj.total : null
  if (total === null) return null
  const under = typeof obj.under_extraction_rate === 'number' ? obj.under_extraction_rate : 0
  const avg = typeof obj.avg_yield === 'number' ? obj.avg_yield : 0
  const p50 = typeof obj.p50_yield === 'number' ? obj.p50_yield : 0
  const p90 = typeof obj.p90_yield === 'number' ? obj.p90_yield : 0
  const rawHosts = Array.isArray(obj.by_host_top5) ? obj.by_host_top5 : []
  const hosts: CoworkExtractionStatsHostRow[] = []
  for (const r of rawHosts) {
    if (!r || typeof r !== 'object') continue
    const row = r as Record<string, unknown>
    const host = typeof row.host === 'string' ? row.host : ''
    const count = typeof row.count === 'number' ? row.count : 0
    const avgYield = typeof row.avg_yield === 'number' ? row.avg_yield : 0
    // v82m4 — last_delta_pct may be null (host < 2 entries) or a signed
    // float (pp). Defensive : non-numeric / NaN / Infinity → undefined so
    // the tile renders no badge for that host. Stable shape : we keep the
    // field absent when missing (rather than null) so consumers can rely
    // on `typeof === 'number'` to gate badge rendering.
    let lastDeltaPct: number | null | undefined = undefined
    if (row.last_delta_pct === null) {
      lastDeltaPct = null
    } else if (typeof row.last_delta_pct === 'number' && Number.isFinite(row.last_delta_pct)) {
      lastDeltaPct = row.last_delta_pct
    }
    // v82m5 — delta_history (sparkline). Defensive : non-array → undefined,
    // non-numeric / NaN / Infinity entries dropped, capped at 5 items even
    // if backend somehow surfaces more. Stable shape : we keep the field
    // absent (rather than empty array) when the bridge didn't surface it
    // so the tile can rely on `Array.isArray(row.delta_history)` to gate
    // sparkline rendering.
    let deltaHistory: number[] | undefined = undefined
    if (Array.isArray(row.delta_history)) {
      const cleaned: number[] = []
      for (const v of row.delta_history) {
        if (typeof v === 'number' && Number.isFinite(v)) cleaned.push(v)
      }
      // Backend caps at 5 ; we mirror the cap in case a future change
      // accidentally surfaces more, the UI doesn't blow up.
      deltaHistory = cleaned.slice(-5)
    }
    hosts.push({ host, count, avg_yield: avgYield, last_delta_pct: lastDeltaPct, delta_history: deltaHistory })
  }
  const win = obj.window && typeof obj.window === 'object' ? obj.window as Record<string, unknown> : {}
  const since = typeof win.since === 'number' ? win.since : null
  // v82m3 — read the optional `host` window field if the bridge echoed it.
  const host = typeof win.host === 'string' ? win.host : null
  return {
    total,
    under_extraction_rate: under,
    avg_yield: avg,
    p50_yield: p50,
    p90_yield: p90,
    by_host_top5: hosts,
    window: { since, host },
  }
}

// ---------------------------------------------------------------------------
// v82m5 — sparkline helpers for the per-host delta_history trajectory.
//
// Pure transforms : take the raw deltas array and produce :
//   - bar characters using progressive unicode blocks (▁▂▃▄▅▆▇█)
//   - a single `SparklineTone` (green/amber/red) reflecting overall trend
//
// Tested directly via __tests__/coworkExtractionStats.test.ts so the
// rendering survives any UI refactor.
// ---------------------------------------------------------------------------

const SPARKLINE_BARS = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'] as const

export type SparklineTone = 'green' | 'amber' | 'red'

/**
 * v82m5 — render a deltas array as a 5-bar unicode sparkline string.
 *
 * Mapping rule : we map each delta to one of 8 progressive bars based on its
 * RANK within the deltas array (lowest delta → ▁, highest → █). Using rank
 * rather than absolute scale keeps the sparkline readable across very
 * different yield regimes (a +5pp move in a 0..+10pp window looks the same
 * as a +50pp move in a 0..+100pp window — both reveal the SHAPE of the
 * trend, which is what the user actually cares about).
 *
 * Defensive : empty / null input → empty string. <2 valid entries → empty
 * string (caller skips rendering). Non-finite entries dropped before the
 * rank computation.
 */
export function renderDeltaSparkline(deltas: number[] | null | undefined): string {
  if (!deltas || !Array.isArray(deltas) || deltas.length < 2) return ''
  const cleaned: number[] = []
  for (const v of deltas) {
    if (typeof v === 'number' && Number.isFinite(v)) cleaned.push(v)
  }
  if (cleaned.length < 2) return ''
  const min = Math.min(...cleaned)
  const max = Math.max(...cleaned)
  const span = max - min
  // Degenerate case : all values equal → render flat midline.
  if (span <= 0) return cleaned.map(() => SPARKLINE_BARS[3]).join('')
  return cleaned.map((v) => {
    const ratio = (v - min) / span
    // Map [0,1] to bar index [0,7]. clamp defensive against floating-point.
    const idx = Math.max(0, Math.min(SPARKLINE_BARS.length - 1, Math.round(ratio * (SPARKLINE_BARS.length - 1))))
    return SPARKLINE_BARS[idx]
  }).join('')
}

/**
 * v82m5 — pick a sparkline tone based on the OVERALL trend of the deltas
 * array. Compares last - first to decide :
 *   - last - first >= +5  → green  (ascending / improving)
 *   - last - first <= -5  → red    (descending / degrading)
 *   - else                → amber  (flat-ish)
 *
 * The 5-pp threshold mirrors the existing delta-badge amber boundary.
 *
 * Defensive : empty / <2 entries → 'green' (neutral default — caller likely
 * skips rendering anyway).
 */
export const SPARKLINE_TREND_THRESHOLD_PP = 5.0

export function sparklineToneForDeltaHistory(deltas: number[] | null | undefined): SparklineTone {
  if (!deltas || !Array.isArray(deltas) || deltas.length < 2) return 'green'
  const cleaned: number[] = []
  for (const v of deltas) {
    if (typeof v === 'number' && Number.isFinite(v)) cleaned.push(v)
  }
  if (cleaned.length < 2) return 'green'
  const trend = cleaned[cleaned.length - 1] - cleaned[0]
  if (trend >= SPARKLINE_TREND_THRESHOLD_PP) return 'green'
  if (trend <= -SPARKLINE_TREND_THRESHOLD_PP) return 'red'
  return 'amber'
}

/**
 * GET /api/cowork/extraction-stats and parse the response.
 *
 * Returns the typed envelope on success, or null on any failure
 * (network error, non-200, malformed JSON, ok:false). Optional `signal`
 * for abort handling so polling components can cancel an in-flight fetch
 * on unmount or interval reset.
 *
 * URL is relative — the caller's runtime resolves it against the current
 * origin (Vite proxy / cloudflare tunnel / localhost). No env-var lookup,
 * no hardcoded host.
 */
export async function fetchExtractionStats(
  options: { signal?: AbortSignal; sinceSec?: number; host?: string } = {},
): Promise<CoworkExtractionStats | null> {
  // v82m3 — host param is optional ; both since and host AND-compose on
  // the bridge side. Empty / falsy host is omitted from the URL so we
  // don't accidentally trigger an empty-host filter on the backend.
  const params: string[] = []
  if (options.sinceSec && options.sinceSec > 0) {
    params.push(`since=${options.sinceSec}`)
  }
  if (options.host && typeof options.host === 'string' && options.host.trim()) {
    params.push(`host=${encodeURIComponent(options.host.trim())}`)
  }
  const url = params.length > 0
    ? `/api/cowork/extraction-stats?${params.join('&')}`
    : '/api/cowork/extraction-stats'
  try {
    const r = await fetch(url, { signal: options.signal })
    if (!r.ok) return null
    const raw = await r.json().catch(() => null)
    return parseExtractionStatsEnvelope(raw)
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// v82m8 — pure helper : decide whether to render the per-host INEFFECTIVE
// badge in the tile. Returns true when the bridge has emitted at least one
// dual-signal event on the host AND the effective verdict is false. When
// the host has zero emissions yet (default-trust state), we render NO
// badge so the row stays clean.
//
// Pure : no DOM, no React, no fetch. Composes with the React tile, which
// passes a per-host snapshot of `{ effective, emitted, accepted }` from
// the dual-signal-effective probe.
// ---------------------------------------------------------------------------
export type PerHostEffectivenessSnapshot = {
  effective: boolean
  emitted: number
  accepted: number
}

export function shouldRenderIneffectiveBadge(
  snapshot: PerHostEffectivenessSnapshot | undefined | null,
): boolean {
  if (!snapshot) return false
  if (typeof snapshot.emitted !== 'number' || !Number.isFinite(snapshot.emitted)) return false
  if (snapshot.emitted <= 0) return false
  return snapshot.effective === false
}

// ---------------------------------------------------------------------------
// v82m6 — dual-signal effectiveness probe.
//
// Wraps the bridge `GET /api/cowork/dual-signal-effective?host=<name>`
// endpoint. The response shape :
//   { ok:true, host, emitted, accepted, effective:bool, min_emitted }
//
// Returns the parsed envelope on success, or null on any failure (network
// error, non-200, malformed JSON, ok:false). Pure : no localStorage, no
// React, no DOM. Caller (pipeline) bridges this into the planner's
// `ineffectiveHosts` PlannerContext field.
// ---------------------------------------------------------------------------

export type CoworkDualSignalEffective = {
  host: string
  emitted: number
  accepted: number
  effective: boolean
  min_emitted: number
}

export async function fetchDualSignalEffective(
  host: string,
  options: { signal?: AbortSignal } = {},
): Promise<CoworkDualSignalEffective | null> {
  const h = (host || '').trim()
  if (!h) return null
  try {
    const url = `/api/cowork/dual-signal-effective?host=${encodeURIComponent(h)}`
    const r = await fetch(url, { signal: options.signal })
    if (!r.ok) return null
    const raw = await r.json().catch(() => null)
    if (!raw || typeof raw !== 'object') return null
    const env = raw as {
      ok?: unknown
      host?: unknown
      emitted?: unknown
      accepted?: unknown
      effective?: unknown
      min_emitted?: unknown
    }
    if (env.ok !== true) return null
    return {
      host: typeof env.host === 'string' ? env.host : h,
      emitted: typeof env.emitted === 'number' && Number.isFinite(env.emitted) ? env.emitted : 0,
      accepted: typeof env.accepted === 'number' && Number.isFinite(env.accepted) ? env.accepted : 0,
      effective: env.effective === true || env.effective === undefined,
      min_emitted: typeof env.min_emitted === 'number' && Number.isFinite(env.min_emitted) ? env.min_emitted : 5,
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// v82m7 — dual-signal cool-down reset.
//
// POST /api/cowork/dual-signal-reset?host=<name> — clears the per-host slice
// of the bridge's dual-signal ring buffers so the AuditDrawer "Reset signals"
// button can give the planner ANOTHER try after a manual strategy change.
// Returns the count of cleared events on success ; null on any failure.
// ---------------------------------------------------------------------------

export type CoworkDualSignalResetResult = {
  host: string
  cleared_emitted: number
  cleared_accepted: number
}

export async function postDualSignalReset(
  host: string,
  options: { signal?: AbortSignal } = {},
): Promise<CoworkDualSignalResetResult | null> {
  const h = (host || '').trim()
  if (!h) return null
  try {
    const url = `/api/cowork/dual-signal-reset?host=${encodeURIComponent(h)}`
    const r = await fetch(url, { method: 'POST', signal: options.signal })
    if (!r.ok) return null
    const raw = await r.json().catch(() => null)
    if (!raw || typeof raw !== 'object') return null
    const env = raw as {
      ok?: unknown
      host?: unknown
      cleared_emitted?: unknown
      cleared_accepted?: unknown
    }
    if (env.ok !== true) return null
    return {
      host: typeof env.host === 'string' ? env.host : h,
      cleared_emitted: typeof env.cleared_emitted === 'number' && Number.isFinite(env.cleared_emitted) ? env.cleared_emitted : 0,
      cleared_accepted: typeof env.cleared_accepted === 'number' && Number.isFinite(env.cleared_accepted) ? env.cleared_accepted : 0,
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// v82m9 — trend-signal cool-down reset (symmetric to postDualSignalReset).
//
// POST /api/cowork/trend-signal-reset?host=<name> — clears the per-host slice
// of the bridge's TREND ring buffers so the AuditDrawer "Reset all signals"
// cluster button can fire BOTH the tier-1 and tier-2 reset endpoints in
// parallel when both DUAL_SIGNAL_INEFFECTIVE and TREND_INEFFECTIVE are
// flagged on the same host (terminal TIER_3 state). Returns the count of
// cleared events on success ; null on any failure.
// ---------------------------------------------------------------------------

export type CoworkTrendSignalResetResult = {
  host: string
  cleared_emitted: number
  cleared_accepted: number
}

export async function postTrendSignalReset(
  host: string,
  options: { signal?: AbortSignal } = {},
): Promise<CoworkTrendSignalResetResult | null> {
  const h = (host || '').trim()
  if (!h) return null
  try {
    const url = `/api/cowork/trend-signal-reset?host=${encodeURIComponent(h)}`
    const r = await fetch(url, { method: 'POST', signal: options.signal })
    if (!r.ok) return null
    const raw = await r.json().catch(() => null)
    if (!raw || typeof raw !== 'object') return null
    const env = raw as {
      ok?: unknown
      host?: unknown
      cleared_emitted?: unknown
      cleared_accepted?: unknown
    }
    if (env.ok !== true) return null
    return {
      host: typeof env.host === 'string' ? env.host : h,
      cleared_emitted: typeof env.cleared_emitted === 'number' && Number.isFinite(env.cleared_emitted) ? env.cleared_emitted : 0,
      cleared_accepted: typeof env.cleared_accepted === 'number' && Number.isFinite(env.cleared_accepted) ? env.cleared_accepted : 0,
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// v82m7 — tier-2 trend acceptance metric (read-only).
//
// GET /api/cowork/trend-signal-stats — symmetric to dual-signal-stats but
// for the DUAL_SIGNAL_TREND nudge (sustained host degradation). Lets
// monitoring tools surface the tier-2 acceptance rate alongside tier-1.
// ---------------------------------------------------------------------------

export type CoworkTrendSignalHostRow = {
  host: string
  emitted: number
  accepted: number
  rate: number
}

export type CoworkTrendSignalStats = {
  total_emitted: number
  total_accepted: number
  acceptance_rate: number
  by_host_top5: CoworkTrendSignalHostRow[]
}

export async function fetchTrendSignalStats(
  options: { signal?: AbortSignal } = {},
): Promise<CoworkTrendSignalStats | null> {
  try {
    const r = await fetch('/api/cowork/trend-signal-stats', { signal: options.signal })
    if (!r.ok) return null
    const raw = await r.json().catch(() => null)
    if (!raw || typeof raw !== 'object') return null
    const env = raw as {
      ok?: unknown
      total_emitted?: unknown
      total_accepted?: unknown
      acceptance_rate?: unknown
      by_host_top5?: unknown
    }
    if (env.ok !== true) return null
    const totalEmitted = typeof env.total_emitted === 'number' && Number.isFinite(env.total_emitted) ? env.total_emitted : 0
    const totalAccepted = typeof env.total_accepted === 'number' && Number.isFinite(env.total_accepted) ? env.total_accepted : 0
    const rate = typeof env.acceptance_rate === 'number' && Number.isFinite(env.acceptance_rate) ? env.acceptance_rate : 0
    const rawHosts = Array.isArray(env.by_host_top5) ? env.by_host_top5 : []
    const hosts: CoworkTrendSignalHostRow[] = []
    for (const r of rawHosts) {
      if (!r || typeof r !== 'object') continue
      const row = r as Record<string, unknown>
      const host = typeof row.host === 'string' ? row.host : ''
      const emitted = typeof row.emitted === 'number' && Number.isFinite(row.emitted) ? row.emitted : 0
      const accepted = typeof row.accepted === 'number' && Number.isFinite(row.accepted) ? row.accepted : 0
      const hostRate = typeof row.rate === 'number' && Number.isFinite(row.rate) ? row.rate : 0
      hosts.push({ host, emitted, accepted, rate: hostRate })
    }
    return {
      total_emitted: totalEmitted,
      total_accepted: totalAccepted,
      acceptance_rate: rate,
      by_host_top5: hosts,
    }
  } catch {
    return null
  }
}
