/**
 * v82lz — Tests for the connector-recommendation hint surfaced in
 * `buildCardIterationAction`'s payload when the planner detects a
 * social_feed pageType. ZERO selectors hardcoded — only hostname →
 * connector-id mapping (UX hint, not adapter wiring).
 *
 * Goals :
 *   - pickConnectorHintForHost matches subdomains correctly (www.linkedin.com
 *     and m.linkedin.com both resolve to LinkedIn).
 *   - pickConnectorHintForHost rejects unknown hosts with null.
 *   - buildConnectorHintReasoning produces the 3 expected branches : known
 *     host with connector / known host without connector / generic feed.
 *   - buildCardIterationAction embeds the hint string in payload.connector_hint
 *     and the hint reflects the analyze.url provided.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkConnectorRecommendations.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCardIterationAction,
  buildConnectorHintReasoning,
  pickConnectorHintForHost,
} from '../services/coworkPlanParser.ts'

const FEED_DATA_BASE = {
  pageType: { social_feed: true },
  signals: {
    listLikeCount: 10,
    repeatingCardCount: 10,
    avatarHits: 5,
    hasTimestamps: true,
    reactionButtons: 12,
  },
}

describe('pickConnectorHintForHost — host → connector mapping', () => {
  test('linkedin.com (root) maps to LinkedIn (no dedicated connector)', () => {
    const out = pickConnectorHintForHost('https://linkedin.com/feed')
    assert.ok(out)
    assert.equal(out!.label, 'LinkedIn')
    assert.equal(out!.connectorId, null)
  })

  test('www.linkedin.com matches via suffix endsWith', () => {
    const out = pickConnectorHintForHost('https://www.linkedin.com/feed')
    assert.ok(out)
    assert.equal(out!.label, 'LinkedIn')
  })

  test('m.linkedin.com (mobile subdomain) also matches', () => {
    const out = pickConnectorHintForHost('https://m.linkedin.com/feed/')
    assert.ok(out)
    assert.equal(out!.label, 'LinkedIn')
  })

  test('twitter.com maps to Twitter/X (no connector)', () => {
    const out = pickConnectorHintForHost('https://twitter.com/home')
    assert.ok(out)
    assert.equal(out!.label, 'Twitter/X')
    assert.equal(out!.connectorId, null)
  })

  test('x.com (rebranded Twitter) also maps to Twitter/X', () => {
    const out = pickConnectorHintForHost('https://x.com/home')
    assert.ok(out)
    assert.equal(out!.label, 'Twitter/X')
  })

  test('reddit.com maps to reddit connector (id=reddit)', () => {
    const out = pickConnectorHintForHost('https://reddit.com/r/programming')
    assert.ok(out)
    assert.equal(out!.label, 'Reddit')
    assert.equal(out!.connectorId, 'reddit')
  })

  test('old.reddit.com (subdomain) also maps to reddit', () => {
    const out = pickConnectorHintForHost('https://old.reddit.com/r/all')
    assert.ok(out)
    assert.equal(out!.connectorId, 'reddit')
  })

  test('news.ycombinator.com → hackernews connector', () => {
    const out = pickConnectorHintForHost('https://news.ycombinator.com/')
    assert.ok(out)
    assert.equal(out!.connectorId, 'hackernews')
  })

  test('mastodon.social → no connector (extension-only)', () => {
    const out = pickConnectorHintForHost('https://mastodon.social/explore')
    assert.ok(out)
    assert.equal(out!.connectorId, null)
    assert.equal(out!.label, 'Mastodon')
  })

  test('unknown host (generic feed site) → null', () => {
    const out = pickConnectorHintForHost('https://example-feed.example.com/posts')
    assert.equal(out, null)
  })

  test('malformed url → null (no throw)', () => {
    assert.equal(pickConnectorHintForHost('not-a-url'), null)
    assert.equal(pickConnectorHintForHost(''), null)
    assert.equal(pickConnectorHintForHost(undefined), null)
    assert.equal(pickConnectorHintForHost(null), null)
  })

  test('host comparison is case-insensitive', () => {
    const out = pickConnectorHintForHost('https://WWW.LinkedIn.COM/feed')
    assert.ok(out)
    assert.equal(out!.label, 'LinkedIn')
  })
})

describe('buildConnectorHintReasoning — three branches', () => {
  test('LinkedIn (known host, no connector) → mentions LinkedIn label', () => {
    const r = buildConnectorHintReasoning('https://linkedin.com/feed')
    assert.match(r, /linkedin/i, 'reasoning must mention LinkedIn')
    assert.match(r, /no dedicated connector|extension/i, 'should mention extension-only fallback')
  })

  test('Reddit (known host with connector) → mentions reddit + opt-in hint', () => {
    const r = buildConnectorHintReasoning('https://reddit.com/r/programming')
    assert.match(r, /reddit/i)
    assert.match(r, /opt-in|connector/i)
  })

  test('GitHub (known host with connector) → mentions github + opt-in', () => {
    const r = buildConnectorHintReasoning('https://github.com/explore')
    assert.match(r, /github/i)
    assert.match(r, /connector/i)
  })

  test('generic / unknown host → mentions "generic" branch', () => {
    const r = buildConnectorHintReasoning('https://example-feed.example.com/posts')
    assert.match(r, /generic/i)
    assert.match(r, /topological/i)
  })

  test('undefined url → still produces a generic-branch string', () => {
    const r = buildConnectorHintReasoning(undefined)
    assert.match(r, /generic/i)
  })
})

describe('buildCardIterationAction — embeds connector_hint in payload', () => {
  test('payload.connector_hint mentions linkedin when url is LinkedIn', () => {
    const action = buildCardIterationAction({ ...FEED_DATA_BASE, url: 'https://linkedin.com/feed' })
    assert.equal(action.kind, 'browser')
    if (action.kind !== 'browser') return
    const payload = action.payload as Record<string, unknown>
    assert.ok(typeof payload.connector_hint === 'string', 'connector_hint must be a string')
    assert.match(payload.connector_hint as string, /linkedin/i)
  })

  test('payload.connector_hint generic when url is unknown', () => {
    const action = buildCardIterationAction({ ...FEED_DATA_BASE, url: 'https://random-feed-site.example/' })
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const payload = action.payload as Record<string, unknown>
    assert.match(payload.connector_hint as string, /generic/i)
  })

  test('payload.connector_hint generic when url is missing entirely', () => {
    const action = buildCardIterationAction(FEED_DATA_BASE)
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const payload = action.payload as Record<string, unknown>
    assert.match(payload.connector_hint as string, /generic/i)
  })

  test('reddit url → connector_hint mentions reddit + opt-in', () => {
    const action = buildCardIterationAction({ ...FEED_DATA_BASE, url: 'https://reddit.com/r/all' })
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const payload = action.payload as Record<string, unknown>
    assert.match(payload.connector_hint as string, /reddit/i)
    assert.match(payload.connector_hint as string, /opt-in|connector/i)
  })

  test('connector_hint does NOT replace card_signals (both must coexist)', () => {
    const action = buildCardIterationAction({ ...FEED_DATA_BASE, url: 'https://linkedin.com/' })
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const payload = action.payload as Record<string, unknown>
    assert.ok(payload.card_signals, 'card_signals still present')
    assert.ok(payload.connector_hint, 'connector_hint added alongside card_signals')
    assert.equal(payload.mode, 'card_iteration')
  })
})
