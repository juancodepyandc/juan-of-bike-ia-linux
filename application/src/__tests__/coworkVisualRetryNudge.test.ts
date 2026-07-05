/**
 * v82m1 — Tests for the token-aware visual-retry system-prompt nudge.
 *
 * The planner's `buildSystemPrompt` appends a single-line educational hint
 * when :
 *   - the most-recent under_extraction:true entry in history is preceded
 *     by an analyze_page whose signals report has_avatars OR has_reactions
 *
 * Otherwise the function returns null and the caller appends nothing →
 * ZERO token overhead on the 99% no-under-extraction case.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkVisualRetryNudge.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildVisualRetryNudge,
  shouldAppendVisualRetryNudge,
  didUnderExtractionTripYieldRatio,
  didUnderExtractionTripHostBaselineDrift,
} from '../services/coworkPlanParser.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function analyzePageEntry(data: unknown) {
  return {
    action: { kind: 'browser', operation: 'analyze_page', payload: {} } as CoworkAction,
    result: { ok: true, data, durationMs: 12 },
  }
}

function extractEntry(under_extraction: boolean) {
  return {
    action: {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { mode: 'card_iteration' },
    } as CoworkAction,
    result: { ok: true, data: { items: [], cards_processed: 12 }, durationMs: 800 },
    under_extraction,
  }
}

const VISUAL_AVATARS_PAGE = {
  pageType: { social_feed: true },
  signals: {
    listLikeCount: 12,
    repeatingCardCount: 12,
    avatarHits: 8,         // → has_avatars true
    hasTimestamps: true,
    reactionButtons: 1,    // → has_reactions false (need >= 2)
  },
}

const VISUAL_REACTIONS_PAGE = {
  pageType: { social_feed: true },
  signals: {
    listLikeCount: 12,
    repeatingCardCount: 12,
    avatarHits: 0,         // → has_avatars false
    hasTimestamps: true,
    reactionButtons: 24,   // → has_reactions true
  },
}

const NON_VISUAL_PAGE = {
  pageType: { social_feed: true },
  signals: {
    listLikeCount: 8,
    repeatingCardCount: 8,
    avatarHits: 0,         // → has_avatars false
    hasTimestamps: true,
    reactionButtons: 1,    // → has_reactions false
  },
}

const ARTICLE_PAGE = {
  pageType: { social_feed: false, article: true },
  signals: { listLikeCount: 0 },
}

// ---------------------------------------------------------------------------
// shouldAppendVisualRetryNudge — pure predicate
// ---------------------------------------------------------------------------

describe('shouldAppendVisualRetryNudge (v82m1)', () => {
  test('under_extraction:true + has_avatars:true → true', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntry(true),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), true)
  })

  test('under_extraction:true + has_reactions:true → true', () => {
    const history = [
      analyzePageEntry(VISUAL_REACTIONS_PAGE),
      extractEntry(true),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), true)
  })

  test('under_extraction:false → false (no nudge appended)', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntry(false),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), false)
  })

  test('under_extraction:true but has_avatars:false AND has_reactions:false → false', () => {
    const history = [
      analyzePageEntry(NON_VISUAL_PAGE),
      extractEntry(true),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), false)
  })

  test('under_extraction:true but no analyze_page in history → false', () => {
    const history = [
      extractEntry(true),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), false)
  })

  test('analyze_page on a non-social article page → false (signals absent)', () => {
    const history = [
      analyzePageEntry(ARTICLE_PAGE),
      extractEntry(true),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), false)
  })

  test('empty history → false', () => {
    assert.equal(shouldAppendVisualRetryNudge([]), false)
  })

  test('analyze_page must precede the under_extraction entry (chronological order)', () => {
    // analyze_page comes AFTER the under_extraction → planner had no signals
    // when extracting → not a valid signal-coupled retry context.
    const history = [
      extractEntry(true),
      analyzePageEntry(VISUAL_AVATARS_PAGE),
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), false)
  })

  test('multiple under_extraction entries → uses most-recent for analyze lookup', () => {
    const history = [
      analyzePageEntry(NON_VISUAL_PAGE),       // first analyze : not visual
      extractEntry(true),                       // first under-ext (would be miss)
      analyzePageEntry(VISUAL_AVATARS_PAGE),    // second analyze : visual
      extractEntry(true),                       // most-recent under-ext (matches)
    ]
    assert.equal(shouldAppendVisualRetryNudge(history), true)
  })
})

// ---------------------------------------------------------------------------
// buildVisualRetryNudge — pure builder
// ---------------------------------------------------------------------------

describe('buildVisualRetryNudge (v82m1)', () => {
  test('returns null when gate doesn\'t fire (zero token overhead)', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntry(false),
    ]
    assert.equal(buildVisualRetryNudge(history), null)
  })

  test('returns the [HINT] string when gate fires', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntry(true),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge, 'expected non-null nudge')
    assert.match(nudge!, /^\[HINT\]/)
    assert.match(nudge!, /under_extraction/)
    assert.match(nudge!, /browser\.screenshot/)
    assert.match(nudge!, /includeImage:\s*true/)
  })

  test('nudge is a single line (no embedded newlines)', () => {
    const history = [
      analyzePageEntry(VISUAL_REACTIONS_PAGE),
      extractEntry(true),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge)
    assert.equal(nudge!.includes('\n'), false, 'nudge must be single-line for prompt token economy')
  })

  test('returns null on non-visual under_extraction (avoids unwarranted retries)', () => {
    const history = [
      analyzePageEntry(NON_VISUAL_PAGE),
      extractEntry(true),
    ]
    assert.equal(buildVisualRetryNudge(history), null)
  })

  test('returns null on empty history', () => {
    assert.equal(buildVisualRetryNudge([]), null)
  })
})

// ---------------------------------------------------------------------------
// v82m4 — dual-signal escalation
// ---------------------------------------------------------------------------

// Helper : extract entry with cards_processed AND items length ; the optional
// `reason` flag tags it with host_baseline_drift for the dual case.
function extractEntryWithYield(opts: {
  cards: number
  items: number
  reason?: string
  under_extraction?: boolean
}) {
  const e: {
    action: CoworkAction
    result: { ok: boolean; data: { items: unknown[]; cards_processed: number }; durationMs: number }
    under_extraction?: boolean
    reason?: string
  } = {
    action: {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { mode: 'card_iteration' },
    } as CoworkAction,
    result: {
      ok: true,
      data: {
        items: new Array(opts.items).fill({}),
        cards_processed: opts.cards,
      },
      durationMs: 800,
    },
    under_extraction: opts.under_extraction ?? true,
  }
  if (opts.reason !== undefined) e.reason = opts.reason
  return e
}

describe('didUnderExtractionTripYieldRatio (v82m4)', () => {
  test('cards=10, items=3, under_extraction=true → true', () => {
    const history = [extractEntryWithYield({ cards: 10, items: 3 })]
    assert.equal(didUnderExtractionTripYieldRatio(history), true)
  })
  test('cards=10, items=7, under_extraction=true → false (yield healthy)', () => {
    const history = [extractEntryWithYield({ cards: 10, items: 7 })]
    assert.equal(didUnderExtractionTripYieldRatio(history), false)
  })
  test('cards=4 (below floor), items=1 → false (cards < 5 → no yield-ratio path)', () => {
    const history = [extractEntryWithYield({ cards: 4, items: 1 })]
    assert.equal(didUnderExtractionTripYieldRatio(history), false)
  })
  test('no under_extraction entry → false', () => {
    assert.equal(didUnderExtractionTripYieldRatio([]), false)
  })
  test('uses MOST-RECENT under_extraction entry', () => {
    const history = [
      extractEntryWithYield({ cards: 10, items: 7 }),  // healthy yield (false)
      extractEntryWithYield({ cards: 10, items: 2 }),  // under (true)
    ]
    assert.equal(didUnderExtractionTripYieldRatio(history), true)
  })
})

describe('didUnderExtractionTripHostBaselineDrift (v82m4)', () => {
  test('reason=host_baseline_drift on under_extraction entry → true', () => {
    const history = [
      extractEntryWithYield({ cards: 10, items: 7, reason: 'host_baseline_drift' }),
    ]
    assert.equal(didUnderExtractionTripHostBaselineDrift(history), true)
  })
  test('no reason field → false', () => {
    const history = [extractEntryWithYield({ cards: 10, items: 3 })]
    assert.equal(didUnderExtractionTripHostBaselineDrift(history), false)
  })
  test('different reason marker → false', () => {
    const history = [
      extractEntryWithYield({ cards: 10, items: 3, reason: 'something_else' }),
    ]
    assert.equal(didUnderExtractionTripHostBaselineDrift(history), false)
  })
  test('no under_extraction entry → false', () => {
    assert.equal(didUnderExtractionTripHostBaselineDrift([]), false)
  })
})

describe('buildVisualRetryNudge dual-signal escalation (v82m4)', () => {
  // To trip dual signal, we need :
  //  - analyze_page with visual signals (avatars/reactions) so the
  //    visualRetry gate passes
  //  - under_extraction:true with BOTH cards>=5 && items < cards*0.5 (yield)
  //    AND reason='host_baseline_drift' (drift)
  test('NO signal (under_extraction false) → null (gate off)', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntry(false),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.equal(nudge, null)
  })

  test('YIELD only (under_extraction:true, no reason) → existing single hint', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      // Yield trips : cards=12, items=3 (< 6) ; no reason
      extractEntryWithYield({ cards: 12, items: 3 }),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge, 'expected non-null nudge on yield-only signal')
    assert.equal(nudge!.includes('DUAL_SIGNAL'), false, 'single-signal hint must NOT contain DUAL_SIGNAL')
    assert.match(nudge!, /under_extraction/)
    assert.match(nudge!, /browser\.screenshot/)
    assert.match(nudge!, /includeImage:\s*true/)
  })

  test('DRIFT only (reason=host_baseline_drift, no yield trip) → existing single hint', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      // Drift only : healthy yield (cards=10, items=8 = 80%) BUT reason set
      extractEntryWithYield({ cards: 10, items: 8, reason: 'host_baseline_drift' }),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge, 'expected non-null nudge on drift-only signal')
    assert.equal(nudge!.includes('DUAL_SIGNAL'), false, 'single-signal hint must NOT contain DUAL_SIGNAL')
    assert.match(nudge!, /under_extraction/)
    assert.match(nudge!, /browser\.screenshot/)
  })

  test('DUAL signal (yield trip + reason=host_baseline_drift) → DUAL_SIGNAL hint', () => {
    const history = [
      analyzePageEntry(VISUAL_AVATARS_PAGE),
      extractEntryWithYield({
        cards: 12,
        items: 3,
        reason: 'host_baseline_drift',
      }),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge, 'expected non-null nudge on dual signal')
    assert.match(nudge!, /^\[HINT\] DUAL_SIGNAL/)
    assert.match(nudge!, /host baseline drift/i)
    assert.match(nudge!, /browser\.screenshot/)
    assert.match(nudge!, /includeImage:\s*true/)
    assert.match(nudge!, /mode=spread/i)
  })

  test('DUAL signal hint is single-line (no embedded newlines)', () => {
    const history = [
      analyzePageEntry(VISUAL_REACTIONS_PAGE),
      extractEntryWithYield({
        cards: 10,
        items: 2,
        reason: 'host_baseline_drift',
      }),
    ]
    const nudge = buildVisualRetryNudge(history)
    assert.ok(nudge)
    assert.equal(nudge!.includes('\n'), false)
  })
})
