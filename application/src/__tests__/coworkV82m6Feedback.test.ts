/**
 * v82m6 — Tests for the feedback-loop pure helpers added in pass 36 :
 *
 *   1. buildPinnedConnectorsHint     (coworkPlanner.ts)
 *   2. buildIneffectiveHostHint      (coworkPlanner.ts)
 *   3. didDeltaHistoryConfirmRedTrend (coworkPlanParser.ts)
 *   4. buildVisualRetryNudge tier-2 trend escalation (coworkPlanParser.ts)
 *   5. fetchDualSignalEffective parser (coworkExtractionStats.ts)
 *
 * Pure tests — no DOM, no network, no React. The helpers are designed to be
 * unit-testable under `node --experimental-strip-types --test`.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkV82m6Feedback.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildPinnedConnectorsHint,
  buildIneffectiveHostHint,
  buildVisualRetryNudge,
  didDeltaHistoryConfirmRedTrend,
} from '../services/coworkPlanParser.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// 1) buildPinnedConnectorsHint — pin propagation
// ---------------------------------------------------------------------------

describe('buildPinnedConnectorsHint (v82m6)', () => {
  test('empty pins → empty string (zero token overhead)', () => {
    assert.equal(buildPinnedConnectorsHint(undefined), '')
    assert.equal(buildPinnedConnectorsHint([]), '')
  })

  test('single pin → single-line USER_PROMOTED hint', () => {
    const hint = buildPinnedConnectorsHint(['reddit'])
    assert.notEqual(hint, '')
    assert.match(hint, /\[USER_PROMOTED\]/)
    assert.match(hint, /reddit/)
    assert.match(hint, /pinned these connectors as preferred/)
  })

  test('multiple pins → joined with comma+space, in order', () => {
    const hint = buildPinnedConnectorsHint(['reddit', 'github'])
    assert.match(hint, /\[USER_PROMOTED\]/)
    assert.match(hint, /reddit, github/)
  })

  test('pins removed mid-session (empty list passed) → empty string', () => {
    // Caller should re-read pins each iteration ; if user removed all, list
    // arrives empty → no hint emitted.
    assert.equal(buildPinnedConnectorsHint([]), '')
  })

  test('whitespace + dedup → trimmed, deduplicated, order preserved', () => {
    const hint = buildPinnedConnectorsHint(['  reddit  ', 'github', 'reddit', ''])
    assert.match(hint, /reddit, github/)
    // Should NOT contain the duplicate.
    assert.equal((hint.match(/reddit/g) || []).length, 1)
  })

  test('hint fits on a single line (no embedded newline within the hint body)', () => {
    const hint = buildPinnedConnectorsHint(['reddit', 'github', 'twitter', 'linkedin'])
    // The leading "\n" delimiter is allowed (it joins the surrounding sections),
    // but no further newline within.
    const body = hint.startsWith('\n') ? hint.slice(1) : hint
    assert.equal(body.includes('\n'), false, 'body should be single-line')
  })

  test('emits the LLM is free to ignore semantic — uses "prefer", not "must"', () => {
    const hint = buildPinnedConnectorsHint(['reddit'])
    assert.match(hint, /prefer/i)
    assert.equal(/\bMUST\b/.test(hint), false, 'pinned hint must not be imperative')
  })
})

// ---------------------------------------------------------------------------
// 2) didDeltaHistoryConfirmRedTrend — sparkline trajectory pure detector
// ---------------------------------------------------------------------------

function extractEntryWithDelta(opts: {
  under_extraction?: boolean
  reason?: string
  cards?: number
  items?: number
  delta_history?: number[]
  url?: string
}) {
  const items = Array.from({ length: opts.items ?? 0 }, (_, i) => ({ idx: i }))
  return {
    action: {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { mode: 'card_iteration', url: opts.url },
    } as CoworkAction,
    result: {
      ok: true,
      data: { items, cards_processed: opts.cards ?? 12 },
      durationMs: 800,
    },
    under_extraction: opts.under_extraction,
    reason: opts.reason,
    delta_history: opts.delta_history,
  }
}

describe('didDeltaHistoryConfirmRedTrend (v82m6)', () => {
  test('no under_extraction → false', () => {
    assert.equal(didDeltaHistoryConfirmRedTrend([]), false)
    assert.equal(
      didDeltaHistoryConfirmRedTrend([extractEntryWithDelta({ under_extraction: false })]),
      false,
    )
  })

  test('under_extraction without delta_history → false', () => {
    const h = [extractEntryWithDelta({ under_extraction: true })]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), false)
  })

  test('delta_history strongly descending (last - first <= -5pp) → true', () => {
    const h = [
      extractEntryWithDelta({
        under_extraction: true,
        delta_history: [10, 5, 0, -5, -10],
      }),
    ]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), true)
  })

  test('delta_history flat (last ~= first) → false (amber)', () => {
    const h = [
      extractEntryWithDelta({
        under_extraction: true,
        delta_history: [2, 1, 0, -1, 1],
      }),
    ]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), false)
  })

  test('delta_history ascending → false (green tone)', () => {
    const h = [
      extractEntryWithDelta({
        under_extraction: true,
        delta_history: [-10, -5, 0, 5, 10],
      }),
    ]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), false)
  })

  test('delta_history exactly -5pp boundary → true (inclusive at threshold)', () => {
    const h = [
      extractEntryWithDelta({
        under_extraction: true,
        delta_history: [3, -2],   // last - first = -5
      }),
    ]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), true)
  })

  test('non-finite values dropped before trend computation', () => {
    const h = [
      extractEntryWithDelta({
        under_extraction: true,
        delta_history: [10, Number.NaN, -10],
      }),
    ]
    // After cleaning: [10, -10] → trend = -20 → red
    assert.equal(didDeltaHistoryConfirmRedTrend(h), true)
  })

  test('< 2 valid entries → false (defensive)', () => {
    const h = [
      extractEntryWithDelta({ under_extraction: true, delta_history: [10] }),
    ]
    assert.equal(didDeltaHistoryConfirmRedTrend(h), false)
  })
})

// ---------------------------------------------------------------------------
// 3) buildVisualRetryNudge — tier-2 DUAL_SIGNAL_TREND escalation
// ---------------------------------------------------------------------------

const VISUAL_AVATARS_PAGE = {
  pageType: { social_feed: true },
  signals: {
    listLikeCount: 12,
    repeatingCardCount: 12,
    avatarHits: 8,
    hasTimestamps: true,
    reactionButtons: 1,
  },
}

function analyzePageEntry(data: unknown) {
  return {
    action: { kind: 'browser', operation: 'analyze_page', payload: {} } as CoworkAction,
    result: { ok: true, data, durationMs: 12 },
  }
}

describe('buildVisualRetryNudge tier-2 trend escalation (v82m6)', () => {
  test('no signal (under_extraction:false) → null', () => {
    const h = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithDelta({ under_extraction: false }),
    ]
    assert.equal(buildVisualRetryNudge(h), null)
  })

  test('under_extraction only (no red trend) → existing single hint', () => {
    const h = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithDelta({
        under_extraction: true,
        cards: 12,
        items: 3,
      }),
    ]
    const nudge = buildVisualRetryNudge(h)
    assert.ok(nudge, 'expected non-null nudge on yield-only signal')
    assert.equal(nudge!.includes('DUAL_SIGNAL'), false, 'no escalation token')
    assert.equal(nudge!.includes('TREND'), false)
    assert.match(nudge!, /under_extraction/)
  })

  test('red trend only (no under_extraction trip path) → null (under_extraction gate enforces)', () => {
    // Without under_extraction:true the visual-retry gate doesn't fire.
    const h = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithDelta({
        under_extraction: false,
        delta_history: [10, 5, 0, -5, -10],
      }),
    ]
    assert.equal(buildVisualRetryNudge(h), null)
  })

  test('dual (under_extraction + red trend) → DUAL_SIGNAL_TREND nudge', () => {
    const h = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithDelta({
        under_extraction: true,
        cards: 12,
        items: 3,
        delta_history: [10, 5, 0, -5, -10],
      }),
    ]
    const nudge = buildVisualRetryNudge(h)
    assert.ok(nudge, 'expected non-null nudge on dual (under + trend)')
    assert.match(nudge!, /^\[HINT\] DUAL_SIGNAL_TREND/)
    assert.match(nudge!, /sparkline trending down/i)
    assert.match(nudge!, /mode=spread/i)
    assert.match(nudge!, /pause 3-5 seconds/i)
    assert.equal(nudge!.includes('\n'), false, 'single-line for token economy')
  })

  test('TREND escalation OUTRANKS plain DUAL_SIGNAL when trend confirmed', () => {
    // All three signals present (yield + drift + red trend) → TREND wins.
    const h = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithDelta({
        under_extraction: true,
        reason: 'host_baseline_drift',
        cards: 12,
        items: 3,
        delta_history: [15, 10, 0, -10, -15],
      }),
    ]
    const nudge = buildVisualRetryNudge(h)
    assert.ok(nudge)
    assert.match(nudge!, /DUAL_SIGNAL_TREND/)
    // The non-trend dual-signal text must NOT appear.
    assert.equal(/host baseline drift detected/.test(nudge!), false)
  })
})

// ---------------------------------------------------------------------------
// 4) buildIneffectiveHostHint — DUAL_SIGNAL_INEFFECTIVE fallback
// ---------------------------------------------------------------------------

describe('buildIneffectiveHostHint (v82m6)', () => {
  function extractEntryWithUrl(url: string) {
    return {
      action: {
        kind: 'browser',
        operation: 'extract_structured',
        payload: { mode: 'card_iteration', url },
      } as CoworkAction,
      result: { ok: true, data: { items: [], cards_processed: 10 }, durationMs: 100 },
    }
  }

  test('empty ineffective list → empty string', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    assert.equal(buildIneffectiveHostHint(undefined, h), '')
    assert.equal(buildIneffectiveHostHint([], h), '')
  })

  test('empty history → empty string', () => {
    assert.equal(buildIneffectiveHostHint(['linkedin.com'], []), '')
  })

  test('current host matches ineffective list → DUAL_SIGNAL_INEFFECTIVE hint', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h)
    assert.match(hint, /\[HINT\] DUAL_SIGNAL_INEFFECTIVE/)
    assert.match(hint, /different strategy/)
    assert.match(hint, /focus_signal|connector/)
    // Single-line within body.
    const body = hint.startsWith('\n') ? hint.slice(1) : hint
    assert.equal(body.includes('\n'), false)
  })

  test('current host NOT in ineffective list → empty string', () => {
    const h = [extractEntryWithUrl('https://reddit.com/r/all')]
    assert.equal(buildIneffectiveHostHint(['linkedin.com'], h), '')
  })

  test('host normalisation : strips www. + lowercases', () => {
    const h = [extractEntryWithUrl('https://www.LinkedIn.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h)
    assert.match(hint, /DUAL_SIGNAL_INEFFECTIVE/)
  })

  test('host normalisation symmetric : ineffective list also normalised', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['www.LinkedIn.com'], h)
    assert.match(hint, /DUAL_SIGNAL_INEFFECTIVE/)
  })

  test('history without extract_structured → empty string', () => {
    const h = [
      {
        action: { kind: 'browser', operation: 'screenshot', payload: {} } as CoworkAction,
        result: { ok: true, durationMs: 12 },
      },
    ]
    assert.equal(buildIneffectiveHostHint(['linkedin.com'], h), '')
  })

  test('history with non-URL payload → empty string (defensive parsing)', () => {
    const h = [
      {
        action: {
          kind: 'browser',
          operation: 'extract_structured',
          payload: { mode: 'card_iteration' },
        } as CoworkAction,
        result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 50 },
      },
    ]
    assert.equal(buildIneffectiveHostHint(['linkedin.com'], h), '')
  })
})
