/**
 * v82ly — Tests for the deterministic auto-injection of
 * extract_structured(mode=card_iteration) when the prior analyze_page in
 * the orchestrator history reports pageType.social_feed=true with strong
 * topological signals.
 *
 * The injection is a PURE post-processor on the planner's output : it
 * fires when the predicate matches, otherwise the LLM-emitted plan flows
 * through unchanged. Goal of these tests :
 *   1. social_feed=true + cards>=5 → action injected with card_signals
 *      propagated.
 *   2. social_feed=false → plan untouched (no false-positive injection).
 *   3. social_feed=true but cards<5 → plan untouched (topological gate).
 *   4. plan already contains card_iteration → no double-emit.
 *   5. action inserted BEFORE reply/finish (synthesis pass survives).
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkSocialFeedAutoEmit.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCardIterationAction,
  findLatestAnalyzePageResult,
  injectCardIterationFollowUp,
  shouldAutoEmitCardIteration,
} from '../services/coworkPlanParser.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function analyzePageEntry(data: unknown) {
  return {
    action: { kind: 'browser', operation: 'analyze_page', payload: {} } as CoworkAction,
    result: { ok: true, data, durationMs: 12 },
  }
}

const SOCIAL_FEED_DATA = {
  pageType: { social_feed: true, listing: true, login: false },
  signals: {
    listLikeCount: 12,
    repeatingCardCount: 12,
    avatarHits: 8,
    hasTimestamps: true,
    reactionButtons: 24,
    socialFeedScore: 4,
  },
}

const ARTICLE_DATA = {
  pageType: { social_feed: false, article: true },
  signals: { listLikeCount: 0, articleTag: true },
}

const SOCIAL_FEED_LOW_CARDS = {
  pageType: { social_feed: true },
  signals: { listLikeCount: 3, repeatingCardCount: 3, avatarHits: 4, hasTimestamps: true, reactionButtons: 6 },
}

const BARE_PLAN: CoworkPlan = {
  reasoning: 'analyse',
  expectedOutcome: 'feed extrait',
  actions: [
    { kind: 'reply', message: 'voici le feed' },
    { kind: 'finish', summary: 'fait' },
  ],
}

const PLAN_NO_REPLY: CoworkPlan = {
  reasoning: 'lecture',
  expectedOutcome: 'donnees brutes',
  actions: [
    { kind: 'browser', operation: 'analyze_page', payload: {} },
  ],
}

// ---------------------------------------------------------------------------
// findLatestAnalyzePageResult
// ---------------------------------------------------------------------------

describe('findLatestAnalyzePageResult', () => {
  test('returns null on empty history', () => {
    assert.equal(findLatestAnalyzePageResult([]), null)
  })

  test('returns the most recent analyze_page result', () => {
    const history = [
      analyzePageEntry(ARTICLE_DATA),
      {
        action: { kind: 'browser', operation: 'screenshot', payload: {} } as CoworkAction,
        result: { ok: true, data: { dataUrl: 'x' }, durationMs: 0 },
      },
      analyzePageEntry(SOCIAL_FEED_DATA),
    ]
    const out = findLatestAnalyzePageResult(history)
    assert.ok(out)
    assert.equal(out!.pageType?.social_feed, true)
  })

  test('skips failed analyze_page results', () => {
    const history = [
      {
        action: { kind: 'browser', operation: 'analyze_page', payload: {} } as CoworkAction,
        result: { ok: false, durationMs: 0 },
      },
    ]
    assert.equal(findLatestAnalyzePageResult(history), null)
  })

  test('ignores non-analyze browser ops', () => {
    const history = [
      {
        action: { kind: 'browser', operation: 'read_html', payload: {} } as CoworkAction,
        result: { ok: true, data: SOCIAL_FEED_DATA, durationMs: 0 },
      },
    ]
    assert.equal(findLatestAnalyzePageResult(history), null)
  })
})

// ---------------------------------------------------------------------------
// shouldAutoEmitCardIteration
// ---------------------------------------------------------------------------

describe('shouldAutoEmitCardIteration — predicate', () => {
  test('fires when pageType.social_feed=true + cards>=5', () => {
    const should = shouldAutoEmitCardIteration(BARE_PLAN, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(should, true)
  })

  test('does NOT fire when pageType.social_feed=false', () => {
    const should = shouldAutoEmitCardIteration(BARE_PLAN, [analyzePageEntry(ARTICLE_DATA)])
    assert.equal(should, false, 'article page must not trigger card_iteration')
  })

  test('does NOT fire when repeating_card_count<5', () => {
    const should = shouldAutoEmitCardIteration(BARE_PLAN, [analyzePageEntry(SOCIAL_FEED_LOW_CARDS)])
    assert.equal(should, false, 'topological gate <5 cards must block injection')
  })

  test('does NOT fire when history has no analyze_page result', () => {
    const should = shouldAutoEmitCardIteration(BARE_PLAN, [])
    assert.equal(should, false)
  })

  test('does NOT fire when plan already contains extract_structured(card_iteration)', () => {
    const planWithIter: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        {
          kind: 'browser',
          operation: 'extract_structured',
          payload: { intent: 'feed', mode: 'card_iteration' },
        },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const should = shouldAutoEmitCardIteration(planWithIter, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(should, false, 'no double-emit when LLM already chose card_iteration')
  })

  test('still fires when plan contains a plain extract_structured (no mode)', () => {
    const planWithFreeExtract: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        {
          kind: 'browser',
          operation: 'extract_structured',
          payload: { intent: 'free' },
        },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const should = shouldAutoEmitCardIteration(planWithFreeExtract, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(should, true, 'free extract_structured (no mode) must not block card_iteration injection')
  })
})

// ---------------------------------------------------------------------------
// buildCardIterationAction — propagates card_signals from analyze_page data
// ---------------------------------------------------------------------------

describe('buildCardIterationAction — propagates card_signals', () => {
  test('all 4 signals → all booleans true', () => {
    const action = buildCardIterationAction(SOCIAL_FEED_DATA)
    assert.equal(action.kind, 'browser')
    if (action.kind !== 'browser') return
    assert.equal(action.operation, 'extract_structured')
    const payload = action.payload as Record<string, unknown>
    assert.equal(payload.mode, 'card_iteration')
    assert.equal(typeof payload.intent, 'string')
    const cs = payload.card_signals as Record<string, unknown>
    assert.equal(cs.repeating_card_count, 12)
    assert.equal(cs.has_avatars, true)
    assert.equal(cs.has_timestamps, true)
    assert.equal(cs.has_reactions, true)
  })

  test('avatars below threshold → has_avatars=false', () => {
    const action = buildCardIterationAction({
      pageType: { social_feed: true },
      signals: { listLikeCount: 7, avatarHits: 1, hasTimestamps: true, reactionButtons: 0 },
    })
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const cs = (action.payload as Record<string, unknown>).card_signals as Record<string, unknown>
    assert.equal(cs.has_avatars, false, 'avatarHits=1 below threshold of 2')
    assert.equal(cs.has_reactions, false, 'reactionButtons=0 below threshold of 2')
    assert.equal(cs.repeating_card_count, 7)
  })

  test('falls back to listLikeCount when repeatingCardCount is absent', () => {
    const action = buildCardIterationAction({
      pageType: { social_feed: true },
      signals: { listLikeCount: 9, hasTimestamps: false, reactionButtons: 0, avatarHits: 0 },
    })
    if (action.kind !== 'browser') return assert.fail('expected browser action')
    const cs = (action.payload as Record<string, unknown>).card_signals as Record<string, unknown>
    assert.equal(cs.repeating_card_count, 9)
  })
})

// ---------------------------------------------------------------------------
// injectCardIterationFollowUp — end-to-end behavior
// ---------------------------------------------------------------------------

describe('injectCardIterationFollowUp — end-to-end', () => {
  test('inserts action BEFORE reply/finish (synthesis pass survives)', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(out.actions.length, 3, 'one action injected before reply+finish')
    assert.equal(out.actions[0].kind, 'browser')
    if (out.actions[0].kind !== 'browser') return
    assert.equal(out.actions[0].operation, 'extract_structured')
    const payload = out.actions[0].payload as Record<string, unknown>
    assert.equal(payload.mode, 'card_iteration')
    // reply + finish still last in order
    assert.equal(out.actions[1].kind, 'reply')
    assert.equal(out.actions[2].kind, 'finish')
  })

  test('appends action when no reply/finish in plan', () => {
    const out = injectCardIterationFollowUp(PLAN_NO_REPLY, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(out.actions.length, 2)
    assert.equal(out.actions[1].kind, 'browser')
    if (out.actions[1].kind !== 'browser') return
    assert.equal(out.actions[1].operation, 'extract_structured')
  })

  test('returns plan unchanged when predicate fails (article page)', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzePageEntry(ARTICLE_DATA)])
    assert.equal(out, BARE_PLAN, 'same reference — no copy when noop')
  })

  test('returns plan unchanged when no analyze_page in history', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [])
    assert.equal(out, BARE_PLAN)
  })

  test('returns plan unchanged when card_iteration already chained', () => {
    const planAlready: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        {
          kind: 'browser',
          operation: 'extract_structured',
          payload: { intent: 'feed', mode: 'card_iteration', card_signals: {} },
        },
        { kind: 'finish', summary: 'done' },
      ],
    }
    const out = injectCardIterationFollowUp(planAlready, [analyzePageEntry(SOCIAL_FEED_DATA)])
    assert.equal(out, planAlready, 'no double-emit')
  })

  test('does NOT fire on social_feed with cards<5 (topological gate)', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzePageEntry(SOCIAL_FEED_LOW_CARDS)])
    assert.equal(out, BARE_PLAN, 'low card count must not trigger auto-emit')
  })

  test('uses most recent analyze_page when multiple in history', () => {
    // Even when an earlier analyze_page was an article, the LATEST one (a
    // social_feed) must drive the decision. Mirrors a SPA navigation where
    // the user navigates from an article page to a feed page in the same
    // cowork session.
    const history = [
      analyzePageEntry(ARTICLE_DATA),
      analyzePageEntry(SOCIAL_FEED_DATA),
    ]
    const out = injectCardIterationFollowUp(BARE_PLAN, history)
    assert.equal(out.actions.length, 3)
    assert.notEqual(out, BARE_PLAN)
  })
})

// ---------------------------------------------------------------------------
// content-scrape cards[] streaming — pure DOM signal contract.
//
// We don't have JSDOM here, but the snapshot.cards[] contract is simple
// enough to verify with hand-crafted minimal DOM stubs. The goal is to
// assert :
//   - When pageType.social_feed === true AND a parent container has >=5
//     repeating children of the same tag, snapshot.cards has length >= 5.
//   - When pageType.social_feed === false, snapshot.cards stays undefined.
//   - Each card outerHTML is capped at 5_000 chars.
//   - The list is capped at 20 cards.
//
// The tests below mirror the content-scrape extractTextSnapshot logic with
// a tiny DOM stub so we don't need a full browser env. KEEP IN SYNC with
// content-scrape.js.
// ---------------------------------------------------------------------------

type DomNode = {
  tagName: string
  outerHTML: string
  children: DomNode[]
}

function buildCardsArray(parent: DomNode, bestTag: string, max = 20, capChars = 5_000) {
  const out: Array<{ idx: number; outerHTML: string }> = []
  let idx = 0
  for (const child of parent.children) {
    if (out.length >= max) break
    if (child.tagName !== bestTag) continue
    const html = (child.outerHTML || '').slice(0, capChars)
    if (html.length < 80) continue
    out.push({ idx, outerHTML: html })
    idx++
  }
  return out
}

function pickBestParent(roots: DomNode[]): { parent: DomNode | null; tag: string | null } {
  let best: DomNode | null = null
  let bestCount = 0
  let bestTag: string | null = null
  for (const c of roots.slice(0, 8)) {
    const counts: Record<string, number> = {}
    for (const child of c.children) {
      counts[child.tagName] = (counts[child.tagName] || 0) + 1
    }
    for (const tag of Object.keys(counts)) {
      if (counts[tag] >= 5 && counts[tag] > bestCount) {
        best = c
        bestCount = counts[tag]
        bestTag = tag
      }
    }
  }
  return { parent: best, tag: bestTag }
}

describe('content-scrape cards[] contract', () => {
  test('feed with 8 article-cards → cards.length === 8', () => {
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: Array.from({ length: 8 }, (_, i) => ({
        tagName: 'ARTICLE',
        outerHTML: `<article data-idx="${i}">post ${i} ${'x'.repeat(150)}</article>`,
        children: [],
      })),
    }
    const { parent, tag } = pickBestParent([main])
    assert.equal(tag, 'ARTICLE')
    assert.ok(parent)
    const cards = buildCardsArray(parent!, tag!)
    assert.equal(cards.length, 8)
    assert.equal(cards[0].idx, 0)
    assert.equal(cards[7].idx, 7)
    assert.match(cards[0].outerHTML, /^<article data-idx="0"/)
  })

  test('cards capped at 20', () => {
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: Array.from({ length: 50 }, (_, i) => ({
        tagName: 'DIV',
        outerHTML: `<div idx="${i}">${'y'.repeat(200)}</div>`,
        children: [],
      })),
    }
    const { parent, tag } = pickBestParent([main])
    const cards = buildCardsArray(parent!, tag!)
    assert.equal(cards.length, 20, 'must cap at 20 even when 50 siblings present')
  })

  test('cards individual outerHTML capped at 5_000 chars', () => {
    const giant = 'a'.repeat(20_000)
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: Array.from({ length: 5 }, (_, i) => ({
        tagName: 'LI',
        outerHTML: `<li>${giant}</li>`,
        children: [],
      })),
    }
    const { parent, tag } = pickBestParent([main])
    const cards = buildCardsArray(parent!, tag!, 20, 5_000)
    assert.equal(cards.length, 5)
    for (const c of cards) {
      assert.ok(c.outerHTML.length <= 5_000, `card outerHTML must be <=5000 chars, got ${c.outerHTML.length}`)
    }
  })

  test('article (1 child, no repeats) → no card extraction', () => {
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: [
        { tagName: 'ARTICLE', outerHTML: '<article>long text...</article>', children: [] },
      ],
    }
    const { parent, tag } = pickBestParent([main])
    assert.equal(parent, null, 'article alone must not match the >=5 repeats rule')
    assert.equal(tag, null)
  })

  test('mixed siblings (3 articles + 2 divs) → no clear card pattern, no extraction', () => {
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: [
        ...Array.from({ length: 3 }, (_, i) => ({ tagName: 'ARTICLE', outerHTML: `<article ${i}>${'x'.repeat(150)}</article>`, children: [] })),
        ...Array.from({ length: 2 }, (_, i) => ({ tagName: 'DIV', outerHTML: `<div ${i}>${'x'.repeat(150)}</div>`, children: [] })),
      ],
    }
    const { parent, tag } = pickBestParent([main])
    assert.equal(parent, null, 'no tag reaches the >=5 threshold')
    assert.equal(tag, null)
  })

  test('cards with outerHTML <80 chars are skipped (noise filter)', () => {
    const main: DomNode = {
      tagName: 'MAIN',
      outerHTML: '<main>...</main>',
      children: Array.from({ length: 6 }, (_, i) => ({
        tagName: 'SPAN',
        // tiny markup — under 80 chars threshold
        outerHTML: `<span>${i}</span>`,
        children: [],
      })),
    }
    const { parent, tag } = pickBestParent([main])
    const cards = buildCardsArray(parent!, tag!)
    assert.equal(cards.length, 0, 'tiny markup must be filtered out')
  })
})
