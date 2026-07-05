/**
 * v82m2 — Tests for the coworkExtractionStats helpers
 * (`parseExtractionStatsEnvelope`, `colorToneForUnderExtractionRate`,
 *  `formatYieldPct`).
 *
 * Coverage :
 *   - parser extracts the typed shape from a healthy fixture
 *   - parser returns null on malformed envelopes (ok:false, missing total,
 *     wrong types)
 *   - tone thresholds : <0.10 green, <0.30 amber, >=0.30 red
 *   - tone defensive on NaN / negative / non-finite
 *   - formatYieldPct rounds correctly, "—" on bad input
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkExtractionStats.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  parseExtractionStatsEnvelope,
  colorToneForUnderExtractionRate,
  formatYieldPct,
  colorToneForLastDelta,
  formatLastDeltaPp,
  renderDeltaSparkline,
  sparklineToneForDeltaHistory,
  UNDER_EXTRACTION_GREEN_MAX,
  UNDER_EXTRACTION_AMBER_MAX,
  DELTA_BADGE_RED_MAX_PP,
  DELTA_BADGE_AMBER_MAX_PP,
  SPARKLINE_TREND_THRESHOLD_PP,
} from '../services/coworkExtractionStats.ts'

// ---------------------------------------------------------------------------
// parseExtractionStatsEnvelope
// ---------------------------------------------------------------------------

describe('parseExtractionStatsEnvelope (v82m2)', () => {
  test('healthy fixture --> typed envelope', () => {
    const raw = {
      ok: true,
      total: 13,
      under_extraction_rate: 0.31,
      avg_yield: 0.62,
      p50_yield: 0.65,
      p90_yield: 0.95,
      by_host_top5: [
        { host: 'linkedin.com', count: 7, avg_yield: 0.6 },
        { host: 'reddit.com',   count: 4, avg_yield: 0.7 },
      ],
      window: { since: null },
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out, 'expected non-null envelope')
    assert.equal(out!.total, 13)
    assert.equal(out!.by_host_top5.length, 2)
    assert.equal(out!.by_host_top5[0].host, 'linkedin.com')
    assert.equal(out!.window.since, null)
  })

  test('ok:false --> null', () => {
    const raw = { ok: false, total: 5 }
    assert.equal(parseExtractionStatsEnvelope(raw), null)
  })

  test('missing total --> null', () => {
    const raw = { ok: true, under_extraction_rate: 0.1 }
    assert.equal(parseExtractionStatsEnvelope(raw), null)
  })

  test('total non-numeric --> null', () => {
    const raw = { ok: true, total: 'five' }
    assert.equal(parseExtractionStatsEnvelope(raw), null)
  })

  test('null/undefined input --> null', () => {
    assert.equal(parseExtractionStatsEnvelope(null), null)
    assert.equal(parseExtractionStatsEnvelope(undefined), null)
  })

  test('missing optional fields default to 0/[]', () => {
    const raw = { ok: true, total: 0 }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.total, 0)
    assert.equal(out!.under_extraction_rate, 0)
    assert.equal(out!.avg_yield, 0)
    assert.deepEqual(out!.by_host_top5, [])
  })

  test('rejects non-object rows in by_host_top5 silently', () => {
    const raw = {
      ok: true,
      total: 2,
      by_host_top5: [
        { host: 'good.com', count: 2, avg_yield: 0.5 },
        null,
        'bad-row',
        { host: 'also-good.com', count: 1, avg_yield: 0.8 },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5.length, 2, 'two valid rows kept')
    assert.equal(out!.by_host_top5[0].host, 'good.com')
  })
})

// ---------------------------------------------------------------------------
// colorToneForUnderExtractionRate
// ---------------------------------------------------------------------------

describe('colorToneForUnderExtractionRate (v82m2)', () => {
  test('rate=0 --> green (healthy)', () => {
    assert.equal(colorToneForUnderExtractionRate(0), 'green')
  })

  test('rate just below green threshold --> green', () => {
    assert.equal(
      colorToneForUnderExtractionRate(UNDER_EXTRACTION_GREEN_MAX - 0.01),
      'green',
    )
  })

  test('rate at green threshold --> amber (boundary)', () => {
    // rate < 0.10 stays green. At 0.10 exactly we tip into amber.
    assert.equal(colorToneForUnderExtractionRate(UNDER_EXTRACTION_GREEN_MAX), 'amber')
  })

  test('rate just below amber threshold --> amber', () => {
    assert.equal(
      colorToneForUnderExtractionRate(UNDER_EXTRACTION_AMBER_MAX - 0.001),
      'amber',
    )
  })

  test('rate at amber threshold --> red', () => {
    assert.equal(colorToneForUnderExtractionRate(UNDER_EXTRACTION_AMBER_MAX), 'red')
  })

  test('rate above amber threshold --> red', () => {
    assert.equal(colorToneForUnderExtractionRate(0.55), 'red')
    assert.equal(colorToneForUnderExtractionRate(1.0), 'red')
  })

  test('NaN / negative / non-finite --> green (defensive)', () => {
    assert.equal(colorToneForUnderExtractionRate(NaN), 'green')
    assert.equal(colorToneForUnderExtractionRate(-0.1), 'green')
    // Number.isFinite(Infinity) is false → defensive fallback returns green
    // so a malformed bridge response doesn't paint the tile red on first paint.
    assert.equal(colorToneForUnderExtractionRate(Infinity), 'green')
  })
})

// ---------------------------------------------------------------------------
// formatYieldPct
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// v82m4 — last_delta_pct parsing + helpers
// ---------------------------------------------------------------------------

describe('parseExtractionStatsEnvelope last_delta_pct (v82m4)', () => {
  test('parses last_delta_pct as number when present', () => {
    const raw = {
      ok: true,
      total: 5,
      by_host_top5: [
        { host: 'reddit.com', count: 5, avg_yield: 0.5, last_delta_pct: -20.0 },
        { host: 'github.com', count: 3, avg_yield: 0.7, last_delta_pct: 5.0 },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].last_delta_pct, -20.0)
    assert.equal(out!.by_host_top5[1].last_delta_pct, 5.0)
  })

  test('parses last_delta_pct=null as null (host has no prior baseline)', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        { host: 'new.host', count: 1, avg_yield: 0.5, last_delta_pct: null },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].last_delta_pct, null)
  })

  test('absent last_delta_pct → undefined (back-compat)', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        { host: 'old.host', count: 1, avg_yield: 0.5 },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].last_delta_pct, undefined)
  })

  test('NaN / Infinity last_delta_pct → undefined (defensive)', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        { host: 'flaky.host', count: 1, avg_yield: 0.5, last_delta_pct: NaN },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].last_delta_pct, undefined)
  })
})

describe('colorToneForLastDelta (v82m4) — color-coded thresholds', () => {
  test('null → green (no baseline, no alarm)', () => {
    assert.equal(colorToneForLastDelta(null), 'green')
  })
  test('undefined → green (no baseline, no alarm)', () => {
    assert.equal(colorToneForLastDelta(undefined), 'green')
  })
  test('NaN / Infinity → green (defensive)', () => {
    assert.equal(colorToneForLastDelta(NaN), 'green')
    assert.equal(colorToneForLastDelta(Infinity), 'green')
  })
  test('+5.0pp (improved) → green', () => {
    assert.equal(colorToneForLastDelta(5.0), 'green')
  })
  test('0pp (flat) → green', () => {
    assert.equal(colorToneForLastDelta(0), 'green')
  })
  test('-3.0pp (mild) → green', () => {
    assert.equal(colorToneForLastDelta(-3.0), 'green')
  })
  test('-5.0pp (at amber boundary) → amber', () => {
    assert.equal(colorToneForLastDelta(DELTA_BADGE_AMBER_MAX_PP), 'amber')
  })
  test('-10.0pp (mid amber zone) → amber', () => {
    assert.equal(colorToneForLastDelta(-10.0), 'amber')
  })
  test('-15.0pp (at red boundary) → red', () => {
    assert.equal(colorToneForLastDelta(DELTA_BADGE_RED_MAX_PP), 'red')
  })
  test('-20.0pp (sharp drop) → red', () => {
    assert.equal(colorToneForLastDelta(-20.0), 'red')
  })
})

describe('formatLastDeltaPp (v82m4)', () => {
  test('+5.0 → "+5.0pp"', () => {
    assert.equal(formatLastDeltaPp(5.0), '+5.0pp')
  })
  test('-20.0 → "-20.0pp"', () => {
    assert.equal(formatLastDeltaPp(-20.0), '-20.0pp')
  })
  test('0 → "+0.0pp"', () => {
    assert.equal(formatLastDeltaPp(0), '+0.0pp')
  })
  test('null / undefined / NaN → null', () => {
    assert.equal(formatLastDeltaPp(null), null)
    assert.equal(formatLastDeltaPp(undefined), null)
    assert.equal(formatLastDeltaPp(NaN), null)
    assert.equal(formatLastDeltaPp(Infinity), null)
  })
  test('-15.123 rounds to 1 decimal → "-15.1pp"', () => {
    assert.equal(formatLastDeltaPp(-15.123), '-15.1pp')
  })
})

describe('formatYieldPct (v82m2)', () => {
  test('0.62 --> "62%"', () => {
    assert.equal(formatYieldPct(0.62), '62%')
  })

  test('1.0 --> "100%"', () => {
    assert.equal(formatYieldPct(1.0), '100%')
  })

  test('0 --> "0%"', () => {
    assert.equal(formatYieldPct(0), '0%')
  })

  test('rounds correctly (0.625 --> "63%", 0.624 --> "62%")', () => {
    assert.equal(formatYieldPct(0.625), '63%')
    assert.equal(formatYieldPct(0.624), '62%')
  })

  test('NaN / negative --> "—"', () => {
    assert.equal(formatYieldPct(NaN), '—')
    assert.equal(formatYieldPct(-0.5), '—')
    assert.equal(formatYieldPct(Infinity), '—')
  })
})

// ---------------------------------------------------------------------------
// v82m5 — delta_history parsing + sparkline helpers
// ---------------------------------------------------------------------------

describe('parseExtractionStatsEnvelope delta_history (v82m5)', () => {
  test('parses delta_history array when present', () => {
    const raw = {
      ok: true,
      total: 5,
      by_host_top5: [
        {
          host: 'reddit.com',
          count: 5,
          avg_yield: 0.5,
          last_delta_pct: -10.0,
          delta_history: [-5.0, -7.5, -8.0, -10.0],
        },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.deepEqual(out!.by_host_top5[0].delta_history, [-5.0, -7.5, -8.0, -10.0])
  })

  test('drops NaN / Infinity entries from delta_history', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        {
          host: 'mixed.com',
          count: 1,
          avg_yield: 0.5,
          delta_history: [1.0, NaN, 2.0, Infinity, 3.0],
        },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.deepEqual(out!.by_host_top5[0].delta_history, [1.0, 2.0, 3.0])
  })

  test('non-array delta_history → undefined (field absent)', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        { host: 'no-history.com', count: 1, avg_yield: 0.5, delta_history: 'not-array' },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].delta_history, undefined)
  })

  test('caps delta_history at 5 even if backend surfaces more', () => {
    const raw = {
      ok: true,
      total: 1,
      by_host_top5: [
        {
          host: 'long.com',
          count: 1,
          avg_yield: 0.5,
          delta_history: [1, 2, 3, 4, 5, 6, 7, 8],
        },
      ],
    }
    const out = parseExtractionStatsEnvelope(raw)
    assert.ok(out)
    assert.equal(out!.by_host_top5[0].delta_history!.length, 5)
    // Keeps the last 5 (most-recent).
    assert.deepEqual(out!.by_host_top5[0].delta_history, [4, 5, 6, 7, 8])
  })
})

describe('renderDeltaSparkline (v82m5)', () => {
  test('empty / null → empty string', () => {
    assert.equal(renderDeltaSparkline(null), '')
    assert.equal(renderDeltaSparkline(undefined), '')
    assert.equal(renderDeltaSparkline([]), '')
  })

  test('< 2 entries → empty string (no trend computable)', () => {
    assert.equal(renderDeltaSparkline([5.0]), '')
  })

  test('5 ascending values → 5 progressive bars', () => {
    const out = renderDeltaSparkline([0, 1, 2, 3, 4])
    assert.equal(out.length, 5)
    // First bar is the lowest (▁) and last is the highest (█)
    assert.equal(out[0], '▁')
    assert.equal(out[4], '█')
  })

  test('5 descending values → bars run high to low', () => {
    const out = renderDeltaSparkline([10, 8, 6, 4, 2])
    assert.equal(out.length, 5)
    assert.equal(out[0], '█')
    assert.equal(out[4], '▁')
  })

  test('flat values → all midline bars', () => {
    const out = renderDeltaSparkline([5.0, 5.0, 5.0])
    assert.equal(out.length, 3)
    // All same character (midline ▄)
    assert.equal(out[0], out[1])
    assert.equal(out[1], out[2])
  })

  test('drops non-finite entries before rendering', () => {
    const out = renderDeltaSparkline([1, NaN, 2, Infinity, 3])
    // Cleaned to [1, 2, 3] — 3 bars
    assert.equal(out.length, 3)
  })

  test('mock 5-tick history fixture renders 5 chars', () => {
    const out = renderDeltaSparkline([-5.0, -7.5, -10.0, -12.5, -15.0])
    assert.equal(out.length, 5, 'one bar per delta')
  })
})

describe('sparklineToneForDeltaHistory (v82m5)', () => {
  test('empty / < 2 → green (neutral fallback)', () => {
    assert.equal(sparklineToneForDeltaHistory(null), 'green')
    assert.equal(sparklineToneForDeltaHistory([]), 'green')
    assert.equal(sparklineToneForDeltaHistory([5.0]), 'green')
  })

  test('strongly ascending (last - first >= +5) → green', () => {
    assert.equal(sparklineToneForDeltaHistory([0, 5, 10]), 'green')
    assert.equal(sparklineToneForDeltaHistory([-10, 0, 10]), 'green')
  })

  test('strongly descending (last - first <= -5) → red', () => {
    assert.equal(sparklineToneForDeltaHistory([10, 5, 0]), 'red')
    assert.equal(sparklineToneForDeltaHistory([10, 0, -10]), 'red')
  })

  test('flat / mild change (between -5 and +5) → amber', () => {
    assert.equal(sparklineToneForDeltaHistory([5, 4, 5, 6, 5]), 'amber')
    assert.equal(sparklineToneForDeltaHistory([0, 1, -1, 2, 0]), 'amber')
  })

  test('threshold constant exposed', () => {
    assert.equal(SPARKLINE_TREND_THRESHOLD_PP, 5.0)
  })

  test('exact +5 boundary → green (>= threshold)', () => {
    assert.equal(sparklineToneForDeltaHistory([0, 5]), 'green')
  })

  test('exact -5 boundary → red (<= threshold)', () => {
    assert.equal(sparklineToneForDeltaHistory([5, 0]), 'red')
  })
})
