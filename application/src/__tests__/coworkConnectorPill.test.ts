/**
 * v82m0 — Tests for the CoworkOverlay connector pill helpers
 * (`extractConnectorHintFromEventDetail`, `summariseConnectorHint`).
 *
 * The pill surfaces `payload.connector_hint` (set by
 * coworkPlanParser.buildCardIterationAction) on the action emission event
 * the orchestrator emits BEFORE executing each step. We assert :
 *   - hint extracted on a card_iteration action emission event
 *   - null on success/error events (only `info` emissions carry the action)
 *   - null on non-card_iteration extract_structured
 *   - null on non-extract_structured browser ops (analyze_page, screenshot)
 *   - null on non-browser actions (reply, finish, ...)
 *   - null on malformed JSON details
 *   - summary covers the three planner branches : known connector, known
 *     host without connector, generic fallback
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkConnectorPill.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  extractConnectorHintFromEventDetail,
  summariseConnectorHint,
  extractConnectorTargetFromHint,
} from '../services/coworkConnectorPill.ts'
import { buildConnectorHintReasoning } from '../services/coworkPlanParser.ts'
import type { CoworkActionEvent } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function actionEvent(partial: {
  kind?: CoworkActionEvent['kind']
  actionKind?: CoworkActionEvent['actionKind']
  detail?: string
  message?: string
}): CoworkActionEvent {
  return {
    kind: partial.kind ?? 'info',
    actionKind: partial.actionKind ?? 'browser',
    detail: partial.detail,
    message: partial.message ?? 'mock event',
    at: Date.now(),
  }
}

function cardIterationDetail(connectorHint: string | undefined): string {
  const payload: Record<string, unknown> = {
    intent: 'extract recent posts',
    mode: 'card_iteration',
    card_signals: { repeating_card_count: 12 },
  }
  if (connectorHint !== undefined) payload.connector_hint = connectorHint
  return JSON.stringify({
    kind: 'browser',
    operation: 'extract_structured',
    payload,
  })
}

// ---------------------------------------------------------------------------
// extractConnectorHintFromEventDetail
// ---------------------------------------------------------------------------

describe('extractConnectorHintFromEventDetail (v82m0)', () => {
  test('returns the hint when info event describes card_iteration with hint', () => {
    const hint = 'Detected social_feed page on LinkedIn — opt-in to linkedin connector'
    const ev = actionEvent({ detail: cardIterationDetail(hint) })
    assert.equal(extractConnectorHintFromEventDetail(ev), hint)
  })

  test('returns null on success event (only info events carry the action)', () => {
    const ev = actionEvent({
      kind: 'success',
      detail: cardIterationDetail('hint'),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null on error event', () => {
    const ev = actionEvent({
      kind: 'error',
      detail: cardIterationDetail('hint'),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null when actionKind != browser', () => {
    const ev = actionEvent({
      actionKind: 'reply',
      detail: cardIterationDetail('hint'),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null on missing detail', () => {
    const ev = actionEvent({ detail: undefined })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null on malformed JSON', () => {
    const ev = actionEvent({ detail: '{not valid json' })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null on browser.analyze_page (not extract_structured)', () => {
    const ev = actionEvent({
      detail: JSON.stringify({
        kind: 'browser',
        operation: 'analyze_page',
        payload: { connector_hint: 'foo' },
      }),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null on extract_structured without mode=card_iteration', () => {
    const ev = actionEvent({
      detail: JSON.stringify({
        kind: 'browser',
        operation: 'extract_structured',
        payload: { intent: 'free', connector_hint: 'foo' },
      }),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null when payload has no connector_hint key', () => {
    const ev = actionEvent({ detail: cardIterationDetail(undefined) })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null when connector_hint is empty string', () => {
    const ev = actionEvent({ detail: cardIterationDetail('   ') })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('returns null when connector_hint is non-string', () => {
    const ev = actionEvent({
      detail: JSON.stringify({
        kind: 'browser',
        operation: 'extract_structured',
        payload: { mode: 'card_iteration', connector_hint: 42 },
      }),
    })
    assert.equal(extractConnectorHintFromEventDetail(ev), null)
  })

  test('integrates with planner-emitted hint string', () => {
    // Bind the planner's actual reasoning to ensure no contract drift.
    const linkedinHint = buildConnectorHintReasoning('https://www.linkedin.com/feed/')
    const ev = actionEvent({ detail: cardIterationDetail(linkedinHint) })
    const out = extractConnectorHintFromEventDetail(ev)
    assert.ok(out, 'planner-emitted linkedin hint must round-trip')
    assert.match(out!, /linkedin/i)
  })
})

// ---------------------------------------------------------------------------
// summariseConnectorHint
// ---------------------------------------------------------------------------

describe('summariseConnectorHint (v82m0)', () => {
  test('linkedin (no dedicated connector) → "LinkedIn detected — generic extraction"', () => {
    // LinkedIn maps to connectorId:null in SOCIAL_HOST_TO_CONNECTOR — the
    // hint says "no dedicated connector, use topological scrape", so the
    // pill summary surfaces the brand label + the generic-extraction marker.
    const hint = buildConnectorHintReasoning('https://www.linkedin.com/feed/')
    const out = summariseConnectorHint(hint)
    assert.match(out, /LinkedIn/i)
    assert.match(out, /generic extraction/i)
  })

  test('reddit (dedicated connector) → "Reddit detected — connector available"', () => {
    // Reddit has connectorId='reddit' so the hint says "opt-in to reddit
    // connector". Pill summary surfaces "connector available".
    const hint = buildConnectorHintReasoning('https://www.reddit.com/r/programming')
    const out = summariseConnectorHint(hint)
    assert.match(out, /Reddit/i)
    assert.match(out, /connector available/i)
  })

  test('github (dedicated connector) → "GitHub detected — connector available"', () => {
    const hint = buildConnectorHintReasoning('https://github.com/orgs/foo/discussions')
    const out = summariseConnectorHint(hint)
    assert.match(out, /GitHub/i)
    assert.match(out, /connector available/i)
  })

  test('generic / unknown host → "social_feed (generic)"', () => {
    const hint = buildConnectorHintReasoning('https://example.com/feed')
    const out = summariseConnectorHint(hint)
    assert.match(out, /social_feed.*generic/i)
  })

  test('null/undefined-shaped url → generic', () => {
    const hint = buildConnectorHintReasoning(undefined)
    assert.match(summariseConnectorHint(hint), /generic/i)
  })
})

// ---------------------------------------------------------------------------
// extractConnectorTargetFromHint (v82m1)
// ---------------------------------------------------------------------------

describe('extractConnectorTargetFromHint (v82m1)', () => {
  test('reddit (dedicated connector) → { id:"reddit", label:"Reddit" }', () => {
    // Reddit has connectorId='reddit'. The pill becomes clickable, the
    // dialog opens, confirming navigates to settings → focus reddit row.
    const hint = buildConnectorHintReasoning('https://www.reddit.com/r/programming')
    const target = extractConnectorTargetFromHint(hint)
    assert.ok(target, 'expected a non-null target for reddit')
    assert.equal(target!.id, 'reddit')
    assert.equal(target!.label, 'Reddit')
  })

  test('github (dedicated connector) → { id:"github", label:"GitHub" }', () => {
    const hint = buildConnectorHintReasoning('https://github.com/orgs/x/discussions')
    const target = extractConnectorTargetFromHint(hint)
    assert.ok(target)
    assert.equal(target!.id, 'github')
    assert.equal(target!.label, 'GitHub')
  })

  test('hackernews (dedicated connector) → { id:"hackernews" }', () => {
    const hint = buildConnectorHintReasoning('https://news.ycombinator.com/')
    const target = extractConnectorTargetFromHint(hint)
    assert.ok(target)
    assert.equal(target!.id, 'hackernews')
  })

  test('linkedin (no dedicated connector) → null (pill not clickable)', () => {
    // LinkedIn maps to connectorId:null — the hint says "no dedicated
    // connector, use topological scrape", so no opt-in target exists.
    const hint = buildConnectorHintReasoning('https://www.linkedin.com/feed/')
    assert.equal(extractConnectorTargetFromHint(hint), null)
  })

  test('twitter/x (no dedicated connector) → null', () => {
    const hint = buildConnectorHintReasoning('https://x.com/home')
    assert.equal(extractConnectorTargetFromHint(hint), null)
  })

  test('generic / unknown host → null', () => {
    const hint = buildConnectorHintReasoning('https://example.com/feed')
    assert.equal(extractConnectorTargetFromHint(hint), null)
  })

  test('empty / non-string input → null (defensive)', () => {
    assert.equal(extractConnectorTargetFromHint(''), null)
    assert.equal(extractConnectorTargetFromHint(undefined as unknown as string), null)
    assert.equal(extractConnectorTargetFromHint(null as unknown as string), null)
  })
})
