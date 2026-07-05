// ---------------------------------------------------------------------------
// CoworkExtractionStatsTile (v82m2) — consolidated ops tile that surfaces
// the bridge's extraction-stats endpoint.
//
// Pure consumption :
//   - Polls GET /api/cowork/extraction-stats every 30 s (default ; configurable
//     via the `pollIntervalMs` prop for tests).
//   - Renders 3 fields :
//       1. under_extraction_rate (color-coded green/amber/red)
//       2. avg_yield as a short percentage
//       3. by_host_top5 mini list (host + per-host avg_yield)
//   - On mount fires an immediate fetch so the user doesn't wait 30 s for
//     the first paint.
//   - On unmount aborts the in-flight fetch and clears the interval.
//
// ZERO change to the bridge or the cowork pipeline — the tile only reads.
// Used by CoworkOverlay's audit/console panel ; can be reused anywhere
// (CoworkOverlay sidebar, dedicated ops view, settings dialog, ...).
//
// Tests (node --test) :
//   - tile renders with mocked stats fixture
//   - color tone follows the threshold rules
//   - polling interval triggers a fresh fetch
// ---------------------------------------------------------------------------

import { useEffect, useState, useCallback, useRef } from 'react'
import {
  fetchExtractionStats,
  fetchDualSignalEffective,
  shouldRenderIneffectiveBadge,
  colorToneForUnderExtractionRate,
  formatYieldPct,
  colorToneForLastDelta,
  formatLastDeltaPp,
  renderDeltaSparkline,
  sparklineToneForDeltaHistory,
  type CoworkExtractionStats,
  type CoworkDualSignalEffective,
  type ExtractionStatsTone,
  type DeltaBadgeTone,
  type SparklineTone,
} from '../services/coworkExtractionStats'

type CoworkExtractionStatsTileProps = {
  // Polling interval in ms. Defaults to 30 000 ms (30 s) to match the agenda
  // contract — 30 s is the right cadence for a non-critical observability
  // tile (low bridge load, fresh enough for the user to react to drift).
  pollIntervalMs?: number
  // Optional title override (defaults to "Cowork Extraction Quality").
  title?: string
  // Optional fetcher injection for tests — defaults to the real network call.
  // Tests pass a stub that returns a fixed fixture without touching fetch.
  fetcher?: typeof fetchExtractionStats
  // v82m8 — optional dual-signal-effective fetcher injection (per-host probe).
  // Tests pass a stub returning a CoworkDualSignalEffective fixture so the
  // per-host badge renders deterministically without hitting the bridge.
  effectiveFetcher?: typeof fetchDualSignalEffective
}

const DEFAULT_POLL_INTERVAL_MS = 30_000

const TONE_CLASSES: Record<ExtractionStatsTone, string> = {
  green: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/30',
  amber: 'bg-amber-500/10 text-amber-200 border-amber-500/30',
  red:   'bg-red-500/10 text-red-200 border-red-500/30',
}

const TONE_DOT_CLASSES: Record<ExtractionStatsTone, string> = {
  green: 'bg-emerald-400',
  amber: 'bg-amber-400',
  red:   'bg-red-400',
}

// v82m4 — per-host delta-badge colour map. Mirrors the under-extraction
// tone classes but applies only to the small `+5.0pp` / `-20.0pp` chip
// rendered next to a host name. Color-coded by `colorToneForLastDelta`.
const DELTA_BADGE_TONE_CLASSES: Record<DeltaBadgeTone, string> = {
  green: 'text-emerald-300/90',
  amber: 'text-amber-300/90',
  red:   'text-red-300/90',
}

// v82m5 — sparkline tone classes (slightly dimmer than badge so the chip
// stays the dominant signal — sparkline is supplementary trend hint).
const SPARKLINE_TONE_CLASSES: Record<SparklineTone, string> = {
  green: 'text-emerald-400/70',
  amber: 'text-amber-400/70',
  red:   'text-red-400/70',
}

// v82m8 — per-host effectiveness cache (client-side, in-memory only). Keeps
// the tile a single round-trip per host per poll cycle. No persistence — we
// always re-probe on mount + every poll tick to surface the freshest state.
type PerHostEffective = {
  effective: boolean
  emitted: number
  accepted: number
}

export function CoworkExtractionStatsTile(props: CoworkExtractionStatsTileProps) {
  const pollIntervalMs = props.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS
  const fetcher = props.fetcher ?? fetchExtractionStats
  const effectiveFetcher = props.effectiveFetcher ?? fetchDualSignalEffective
  const title = props.title ?? 'Cowork Extraction Quality'

  const [stats, setStats] = useState<CoworkExtractionStats | null>(null)
  const [lastFetchAt, setLastFetchAt] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  // v82m8 — host → effectiveness map. Refreshed alongside the stats poll
  // tick so the badge stays in lock-step with the host rows. Key = host
  // string from `by_host_top5`.
  const [effectiveByHost, setEffectiveByHost] = useState<Record<string, PerHostEffective>>({})
  const abortRef = useRef<AbortController | null>(null)

  const tick = useCallback(async () => {
    // Cancel any prior in-flight fetch so we never race two polls.
    if (abortRef.current) {
      try { abortRef.current.abort() } catch { /* noop */ }
    }
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true)
    try {
      const out = await fetcher({ signal: ctrl.signal })
      // If the fetch was aborted (controller swap) the result is null and
      // we shouldn't update state — but `out` would be null anyway, so a
      // simple guard on signal.aborted keeps the last good stats visible.
      if (!ctrl.signal.aborted) {
        setStats(out)
        setLastFetchAt(Date.now())
      }
      // v82m8 — fan out a per-host effectiveness probe ONLY for the hosts
      // present in the top5. Single-flight via Promise.all so the user
      // sees all badges paint together. Bridge errors → host falls back
      // to default-trust (effective=true) so we never paint alarm on a
      // network hiccup. We re-build the map fresh each tick so a host
      // that drops out of top5 stops showing a stale badge.
      if (out && !ctrl.signal.aborted) {
        const hosts = out.by_host_top5.map((r) => r.host).filter((h) => !!h)
        if (hosts.length > 0) {
          const probes = await Promise.all(hosts.map(async (h) => {
            const env: CoworkDualSignalEffective | null = await effectiveFetcher(h, { signal: ctrl.signal })
            return [h, env] as const
          }))
          if (!ctrl.signal.aborted) {
            const next: Record<string, PerHostEffective> = {}
            for (const [h, env] of probes) {
              if (env) {
                next[h] = { effective: env.effective, emitted: env.emitted, accepted: env.accepted }
              } else {
                next[h] = { effective: true, emitted: 0, accepted: 0 }
              }
            }
            setEffectiveByHost(next)
          }
        } else if (!ctrl.signal.aborted) {
          setEffectiveByHost({})
        }
      }
    } finally {
      if (!ctrl.signal.aborted) {
        setLoading(false)
      }
    }
  }, [fetcher, effectiveFetcher])

  useEffect(() => {
    void tick()
    const id = setInterval(() => { void tick() }, pollIntervalMs)
    return () => {
      clearInterval(id)
      if (abortRef.current) {
        try { abortRef.current.abort() } catch { /* noop */ }
      }
    }
  }, [tick, pollIntervalMs])

  const tone: ExtractionStatsTone = stats
    ? colorToneForUnderExtractionRate(stats.under_extraction_rate)
    : 'green'

  return (
    <div
      data-testid="cowork-extraction-stats-tile"
      data-tone={tone}
      className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] uppercase tracking-[0.18em] text-white/40">
          {title}
        </p>
        <div className="flex items-center gap-2">
          {loading && (
            <span className="text-[9px] text-white/40">…</span>
          )}
          <button
            type="button"
            onClick={() => { void tick() }}
            data-testid="cowork-extraction-stats-tile-refresh"
            className="px-2 py-0.5 rounded-full text-[10px] bg-white/[0.04] text-white/60 border border-white/10 hover:bg-white/[0.08] transition-colors"
            title="Rafraichir maintenant"
          >
            Refresh
          </button>
        </div>
      </div>
      {!stats ? (
        <p className="text-[12px] text-white/45 py-4 text-center" data-testid="cowork-extraction-stats-tile-empty">
          {loading ? 'Chargement des stats d extraction...' : 'Pas encore de stats. La tuile se remplit des qu une extraction tourne.'}
        </p>
      ) : (
        <div className="space-y-3">
          <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${TONE_CLASSES[tone]}`}>
            <div className="flex items-center gap-2">
              <span className={`inline-block h-2 w-2 rounded-full ${TONE_DOT_CLASSES[tone]}`} aria-hidden />
              <span className="text-[11px] font-medium">Sous-extraction</span>
            </div>
            <span
              data-testid="cowork-extraction-stats-tile-under-rate"
              className="font-mono text-[12px]"
            >
              {(stats.under_extraction_rate * 100).toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px] text-white/70">
            <span>Yield moyen</span>
            <span
              data-testid="cowork-extraction-stats-tile-avg-yield"
              className="font-mono text-white/90"
            >
              {formatYieldPct(stats.avg_yield)}
            </span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-white/40">
            <span>Total entries</span>
            <span className="font-mono">{stats.total}</span>
          </div>
          {stats.by_host_top5.length > 0 && (
            <div className="pt-2 border-t border-white/6">
              <p className="text-[9px] uppercase tracking-[0.16em] text-white/35 mb-1.5">
                Top hosts
              </p>
              <ul className="space-y-1" data-testid="cowork-extraction-stats-tile-by-host">
                {stats.by_host_top5.map((row) => {
                  // v82m4 — per-host history badge. When the bridge surfaces
                  // a `last_delta_pct` (host has >= 2 entries), render an
                  // inline colored chip next to the host name so the user
                  // sees "+5.0pp" / "-20.0pp" without opening the drawer.
                  // Tone follows the same threshold as the orchestrator's
                  // host_baseline_drift escalation (-15.0pp red).
                  const deltaLabel = formatLastDeltaPp(row.last_delta_pct)
                  const deltaTone = colorToneForLastDelta(row.last_delta_pct)
                  // v82m5 — sparkline trajectory rendered IF the bridge
                  // surfaced `delta_history` with >= 2 entries. Empty
                  // string fallback when the host has < 2 entries (no
                  // delta computable). Tone reflects the OVERALL trend
                  // (last - first) so the user sees not just the most-
                  // recent point but the trajectory direction.
                  const sparkline = renderDeltaSparkline(row.delta_history)
                  const sparklineTone = sparklineToneForDeltaHistory(row.delta_history)
                  // v82m8 — per-host effective badge. Render only when the
                  // bridge has emitted at least one DUAL_SIGNAL on this host
                  // (otherwise default-trust → silent / no badge so the row
                  // stays clean). When ineffective → red INEFFECTIVE chip.
                  // Decision delegated to `shouldRenderIneffectiveBadge` so
                  // the visibility logic is unit-testable without React.
                  const eff = effectiveByHost[row.host]
                  const showIneffectiveBadge = shouldRenderIneffectiveBadge(eff)
                  return (
                    <li
                      key={row.host}
                      className="flex items-center justify-between text-[11px]"
                      data-testid="cowork-extraction-stats-tile-by-host-row"
                      data-host={row.host}
                      data-effective={eff ? String(eff.effective) : 'unknown'}
                    >
                      <span className="flex items-center gap-1.5 min-w-0">
                        <span className="truncate text-white/70">{row.host || '(unknown)'}</span>
                        {showIneffectiveBadge && eff && (
                          <span
                            data-testid="cowork-extraction-stats-tile-by-host-effective"
                            data-tone="red"
                            className="font-mono text-[9px] shrink-0 px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-300 border border-red-500/30 uppercase tracking-wider"
                            title={`Dual-signal escalations on this host emitted ${eff.emitted}x with ${eff.accepted} acceptance — strategy is ineffective`}
                          >
                            INEFFECTIVE
                          </span>
                        )}
                        {deltaLabel !== null && (
                          <span
                            data-testid="cowork-extraction-stats-tile-by-host-delta"
                            data-tone={deltaTone}
                            className={`font-mono text-[10px] shrink-0 ${DELTA_BADGE_TONE_CLASSES[deltaTone]}`}
                            title={`Variation vs baseline du host : ${deltaLabel}`}
                          >
                            {deltaLabel}
                          </span>
                        )}
                        {sparkline.length > 0 && (
                          <span
                            data-testid="cowork-extraction-stats-tile-by-host-sparkline"
                            data-tone={sparklineTone}
                            data-ticks={sparkline.length}
                            className={`font-mono text-[12px] leading-none shrink-0 tabular-nums ${SPARKLINE_TONE_CLASSES[sparklineTone]}`}
                            title={`Trajectoire delta (last ${sparkline.length} ticks) : ${sparkline}`}
                            aria-label={`Trajectoire delta ${sparkline}`}
                          >
                            {sparkline}
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-white/55 ml-2 shrink-0">
                        {formatYieldPct(row.avg_yield)} · {row.count}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
          {lastFetchAt && (
            <p className="text-[9px] text-white/30 text-right">
              maj {new Date(lastFetchAt).toLocaleTimeString()}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default CoworkExtractionStatsTile
