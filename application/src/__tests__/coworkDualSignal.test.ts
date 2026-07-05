/**
 * v82m5 — Tests for the dual-signal escalation acceptance pure detectors
 * (`detectDualSignalNudgeContext`, `detectDualSignalAcceptanceInPlan`,
 * `pickHostFromHistoryForDualSignal`).
 *
 * Coverage :
 *   - nudge context : true when most-recent under_extraction entry has
 *     yield-ratio path AND host_baseline_drift reason
 *   - nudge context : false on missing under_extraction, missing reason,
 *     non-card_iteration shape, items >= cards*0.5
 *   - acceptance : true when plan has screenshot followed by
 *     extract_structured(includeImage:true)
 *   - acceptance : false when actions in wrong order, or includeImage absent
 *   - host pickup : extracts hostname (lowercase, no www.) from extract URL
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkDualSignal.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  detectDualSignalNudgeContext,
  detectDualSignalAcceptanceInPlan,
  pickHostFromHistoryForDualSignal,
} from '../services/coworkPlanParser.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// detectDualSignalNudgeContext
// ---------------------------------------------------------------------------

function extractEntry(opts: {
  under_extraction?: boolean
  reason?: string
  cards_processed?: number
  items_count?: number
  ok?: boolean
  url?: string
}) {
  const items = Array.from({ length: opts.items_count ?? 0 }, (_, i) => ({ idx: i }))
  return {
    action: {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { mode: 'card_iteration', url: opts.url },
    } as CoworkAction,
    result: {
      ok: opts.ok ?? true,
      data: { items, cards_processed: opts.cards_processed ?? 12 },
      durationMs: 800,
    },
    under_extraction: opts.under_extraction,
    reason: opts.reason,
  }
}

describe('detectDualSignalNudgeContext (v82m5)', () => {
  test('empty history → false', () => {
    assert.equal(detectDualSignalNudgeContext([]), false)
  })

  test('no under_extraction entries → false', () => {
    const history = [extractEntry({})]
    assert.equal(detectDualSignalNudgeContext(history), false)
  })

  test('under_extraction:true with reason=host_baseline_drift AND items < cards*0.5 → true', () => {
    const history = [
      extractEntry({
        under_extraction: true,
        reason: 'host_baseline_drift',
        cards_processed: 10,
        items_count: 3, // 3 < 5 (10*0.5) → yield-ratio fired
      }),
    ]
    assert.equal(detectDualSignalNudgeContext(history), true)
  })

  test('under_extraction:true but reason absent → false (no drift signal)', () => {
    const history = [
      extractEntry({
        under_extraction: true,
        cards_processed: 10,
        items_count: 3,
      }),
    ]
    assert.equal(detectDualSignalNudgeContext(history), false)
  })

  test('under_extraction:true with drift reason but yield-ratio NOT fired (items >= cards*0.5) → false', () => {
    const history = [
      extractEntry({
        under_extraction: true,
        reason: 'host_baseline_drift',
        cards_processed: 10,
        items_count: 6, // 6 >= 5 → yield-ratio path didn't fire
      }),
    ]
    assert.equal(detectDualSignalNudgeContext(history), false)
  })

  test('cards_processed < 5 → false (gate matches annotateUnderExtraction)', () => {
    const history = [
      extractEntry({
        under_extraction: true,
        reason: 'host_baseline_drift',
        cards_processed: 4,
        items_count: 1,
      }),
    ]
    assert.equal(detectDualSignalNudgeContext(history), false)
  })

  test('most-recent under_extraction entry wins (ignores older healthy entries)', () => {
    const history = [
      extractEntry({}), // healthy old
      extractEntry({ under_extraction: true, reason: 'host_baseline_drift', cards_processed: 10, items_count: 3 }),
      extractEntry({}), // healthy after — but the most-recent under_extraction:true is the second one
    ]
    assert.equal(detectDualSignalNudgeContext(history), true)
  })
})

// ---------------------------------------------------------------------------
// detectDualSignalAcceptanceInPlan
// ---------------------------------------------------------------------------

function plan(actions: CoworkAction[]): CoworkPlan {
  return {
    reasoning: 'test',
    expectedOutcome: 'test',
    actions,
  }
}

function browserAction(operation: string, payload: Record<string, unknown> = {}): CoworkAction {
  return { kind: 'browser', operation, payload } as unknown as CoworkAction
}

describe('detectDualSignalAcceptanceInPlan (v82m5)', () => {
  test('empty plan → false', () => {
    assert.equal(detectDualSignalAcceptanceInPlan(null), false)
    assert.equal(detectDualSignalAcceptanceInPlan(undefined), false)
    assert.equal(detectDualSignalAcceptanceInPlan(plan([])), false)
  })

  test('screenshot then extract_structured includeImage:true → true', () => {
    const p = plan([
      browserAction('screenshot'),
      browserAction('extract_structured', { mode: 'card_iteration', includeImage: true }),
    ])
    assert.equal(detectDualSignalAcceptanceInPlan(p), true)
  })

  test('screenshot then extract_structured WITHOUT includeImage → false', () => {
    const p = plan([
      browserAction('screenshot'),
      browserAction('extract_structured', { mode: 'card_iteration' }),
    ])
    assert.equal(detectDualSignalAcceptanceInPlan(p), false)
  })

  test('extract_structured BEFORE screenshot → false (wrong order)', () => {
    const p = plan([
      browserAction('extract_structured', { includeImage: true }),
      browserAction('screenshot'),
    ])
    assert.equal(detectDualSignalAcceptanceInPlan(p), false)
  })

  test('screenshot present but no extract_structured → false', () => {
    const p = plan([browserAction('screenshot')])
    assert.equal(detectDualSignalAcceptanceInPlan(p), false)
  })

  test('think action between screenshot and extract is OK (loose followed-by gate)', () => {
    const p = plan([
      browserAction('screenshot'),
      { kind: 'think', topic: 'whatever', thought: 'reasoning' } as CoworkAction,
      browserAction('extract_structured', { includeImage: true }),
    ])
    assert.equal(detectDualSignalAcceptanceInPlan(p), true)
  })

  test('includeImage:false explicitly → false', () => {
    const p = plan([
      browserAction('screenshot'),
      browserAction('extract_structured', { includeImage: false }),
    ])
    assert.equal(detectDualSignalAcceptanceInPlan(p), false)
  })
})

// ---------------------------------------------------------------------------
// pickHostFromHistoryForDualSignal
// ---------------------------------------------------------------------------

describe('pickHostFromHistoryForDualSignal (v82m5)', () => {
  test('empty history → ""', () => {
    assert.equal(pickHostFromHistoryForDualSignal([]), '')
  })

  test('extract entry with payload.url → returns hostname (lowercased)', () => {
    const history = [extractEntry({ url: 'https://www.LinkedIn.com/feed/' })]
    assert.equal(pickHostFromHistoryForDualSignal(history), 'linkedin.com')
  })

  test('strips leading "www."', () => {
    const history = [extractEntry({ url: 'https://www.reddit.com/r/aurora' })]
    assert.equal(pickHostFromHistoryForDualSignal(history), 'reddit.com')
  })

  test('most-recent extract wins (over older ones)', () => {
    const history = [
      extractEntry({ url: 'https://github.com/foo' }),
      extractEntry({ url: 'https://reddit.com/bar' }),
    ]
    assert.equal(pickHostFromHistoryForDualSignal(history), 'reddit.com')
  })

  test('non-extract entries ignored', () => {
    const history = [
      {
        action: { kind: 'reply', message: 'plain' } as CoworkAction,
        result: { ok: true, durationMs: 1 },
      },
      extractEntry({ url: 'https://example.com/page' }),
    ]
    assert.equal(pickHostFromHistoryForDualSignal(history), 'example.com')
  })

  test('malformed URL → ""', () => {
    const history = [extractEntry({ url: 'not-a-valid-url' })]
    assert.equal(pickHostFromHistoryForDualSignal(history), '')
  })

  test('missing URL → ""', () => {
    const history = [extractEntry({})]
    assert.equal(pickHostFromHistoryForDualSignal(history), '')
  })
})
