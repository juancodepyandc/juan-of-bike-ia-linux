/**
 * v82n0 — Unit tests for article_quality detection + listing_subtype heuristic.
 *
 * The detection lives in two parity-locked twin files :
 *   - application/extension/content-scrape.js (snapshot path)
 *   - application/extension/background.js#analyze_page (the inlined twin)
 *
 * Re-importing those under node --test is impractical (Chrome SW + content
 * script context). Instead we encode the SAME contract here with hand-built
 * DOM stubs and assert the gating logic. KEEP IN SYNC with both files.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/extensionArticleQualityAndListingSubtype.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// ---------------------------------------------------------------------------
// article_quality detector — pure, mirrors detectArticleQuality() in
// content-scrape.js.
// ---------------------------------------------------------------------------

type DetectInput = {
  articleTag: boolean
  textLength: number
  longParagraphs: number
  hasHeading: boolean
  paywallOverlay: boolean
}

function detectArticleQuality(input: DetectInput): 'rich' | 'thin' | 'paywall' | 'unknown' {
  if (!input.articleTag) return 'unknown'
  if (input.paywallOverlay && input.textLength < 3000) return 'paywall'
  if (input.textLength >= 1500 && input.longParagraphs >= 2 && input.hasHeading) return 'rich'
  if (input.textLength < 800) return 'thin'
  return 'unknown'
}

describe('article_quality detection', () => {
  test('rich : article tag + 1500 chars + 2 long paragraphs + heading', () => {
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 2400,
      longParagraphs: 4,
      hasHeading: true,
      paywallOverlay: false,
    })
    assert.equal(verdict, 'rich')
  })

  test('thin : article tag but <800 chars (teaser)', () => {
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 320,
      longParagraphs: 1,
      hasHeading: true,
      paywallOverlay: false,
    })
    assert.equal(verdict, 'thin')
  })

  test('paywall : overlay >60% + auth keyword + article behind', () => {
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 800,  // teaser visible behind paywall
      longParagraphs: 1,
      hasHeading: true,
      paywallOverlay: true,
    })
    assert.equal(verdict, 'paywall')
  })

  test('paywall takes priority over rich when overlay + short visible text', () => {
    // Even with 2 paragraphs visible, an active paywall overlay must mark
    // the page as paywall (the user can't trust the synthesis).
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 1700,
      longParagraphs: 3,
      hasHeading: true,
      paywallOverlay: true,
    })
    assert.equal(verdict, 'paywall')
  })

  test('unknown : no article tag', () => {
    const verdict = detectArticleQuality({
      articleTag: false,
      textLength: 5000,
      longParagraphs: 8,
      hasHeading: true,
      paywallOverlay: false,
    })
    assert.equal(verdict, 'unknown')
  })

  test('edge : article tag, mid-length text (800-1500), no enough signal', () => {
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 1000,
      longParagraphs: 1,
      hasHeading: true,
      paywallOverlay: false,
    })
    assert.equal(verdict, 'unknown')
  })

  test('paywall ignored when text >= 3000 (full article available)', () => {
    // Article fully readable with a sticky promo widget (not a paywall) :
    // text >= 3000 disables the paywall verdict. We fall back to rich/unknown.
    const verdict = detectArticleQuality({
      articleTag: true,
      textLength: 5000,
      longParagraphs: 6,
      hasHeading: true,
      paywallOverlay: true,  // overlay detected but text is fully present
    })
    assert.equal(verdict, 'rich', 'long article supersedes overlay')
  })
})

// ---------------------------------------------------------------------------
// listing_subtype heuristic — mirror of detectListingSubtype() in content-
// scrape.js / background.js. We feed a synthetic items array (each item is
// just an object with text + structural booleans) so we don't need JSDOM.
// ---------------------------------------------------------------------------

type ListingItem = {
  text: string
  hasHeading: boolean
  hasLink: boolean
  hasSnippet: boolean  // text length > heading length + 80
}

function detectListingSubtype(
  listLikeCount: number,
  items: ListingItem[],
): 'search_results' | 'product_listing' | 'news_listing' | 'generic' {
  if (listLikeCount < 5) return 'generic'
  const priceRe = /[€$£¥₹₽]\s*\d|\d[\d.,]*\s*(?:€|\$|£|¥|EUR|USD|GBP|JPY)/i
  const tsRe = /\b\d+\s*(?:min|h|j|d|hour|hours|day|days|week|month|year|ago|hier)\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|fevr|mars|avr|mai|juin|juil|aout|sept|oct|nov|dec)[a-zé]*\.?\s+\d|\d{4}-\d{2}-\d{2}/i
  const authorRe = /\b(?:by|par|von|de|@)\s+[A-Z][a-zA-ZÀ-ÿ\-]+/
  let priceCount = 0, tsCount = 0, authorCount = 0, searchTriadCount = 0
  for (const it of items) {
    if (priceRe.test(it.text)) priceCount++
    if (tsRe.test(it.text)) tsCount++
    if (authorRe.test(it.text)) authorCount++
    if (it.hasHeading && it.hasLink && it.hasSnippet) searchTriadCount++
  }
  if (priceCount >= 3) return 'product_listing'
  if (tsCount >= 3 && authorCount >= 2) return 'news_listing'
  if (listLikeCount >= 8 && searchTriadCount >= Math.min(items.length, 6)) {
    return 'search_results'
  }
  return 'generic'
}

describe('listing_subtype heuristic', () => {
  test('product_listing : 5+ items with prices', () => {
    const items: ListingItem[] = Array.from({ length: 6 }, (_, i) => ({
      text: `Awesome Product ${i} — €${(19.99 + i).toFixed(2)} ★★★★`,
      hasHeading: true,
      hasLink: true,
      hasSnippet: true,
    }))
    assert.equal(detectListingSubtype(6, items), 'product_listing')
  })

  test('product_listing : USD prices also detected', () => {
    const items: ListingItem[] = Array.from({ length: 5 }, (_, i) => ({
      text: `Item ${i} $${(10 + i).toFixed(2)}`,
      hasHeading: false,
      hasLink: true,
      hasSnippet: true,
    }))
    assert.equal(detectListingSubtype(5, items), 'product_listing')
  })

  test('news_listing : timestamps + authors', () => {
    const items: ListingItem[] = [
      { text: 'Breaking news on AI — by Alice 3 hours ago', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'Stock crash — par Bob — il y a 2h', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'Election results @CharlieDoe — 5 days ago', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'Sports update — by Diana — yesterday', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'Tech feature — by Eve — 1 week ago', hasHeading: true, hasLink: true, hasSnippet: true },
    ]
    assert.equal(detectListingSubtype(5, items), 'news_listing')
  })

  test('search_results : 8+ items with heading + link + snippet, no price/news signals', () => {
    const items: ListingItem[] = Array.from({ length: 10 }, (_, i) => ({
      text: `Some heading text. And a longer snippet description that goes well beyond the heading length and provides context for the search result number ${i}.`,
      hasHeading: true,
      hasLink: true,
      hasSnippet: true,
    }))
    assert.equal(detectListingSubtype(10, items), 'search_results')
  })

  test('generic : listing without any subtype signal', () => {
    const items: ListingItem[] = Array.from({ length: 6 }, (_, i) => ({
      text: `Generic item ${i} no price no date`,
      hasHeading: false,
      hasLink: false,
      hasSnippet: false,
    }))
    assert.equal(detectListingSubtype(6, items), 'generic')
  })

  test('generic : listLikeCount<5 short-circuits', () => {
    const items: ListingItem[] = [
      { text: '€10', hasHeading: true, hasLink: true, hasSnippet: true },
    ]
    assert.equal(detectListingSubtype(3, items), 'generic')
  })

  test('priority : product wins over news when both signals present', () => {
    // 4 items with prices + 3 with timestamp+author hints. Product wins.
    const items: ListingItem[] = [
      { text: '€20.50 — by Alice — 2h ago', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: '€15 — by Bob — yesterday', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: '€8.99 — par Charlie — 3 days ago', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: '€42.00', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'Plain text item', hasHeading: false, hasLink: false, hasSnippet: false },
    ]
    assert.equal(detectListingSubtype(5, items), 'product_listing')
  })

  test('search_results requires triad on most items', () => {
    // 8 items but only 2 have heading+link+snippet → not enough → generic.
    const items: ListingItem[] = [
      { text: 'A', hasHeading: true, hasLink: true, hasSnippet: true },
      { text: 'B', hasHeading: true, hasLink: true, hasSnippet: true },
      ...Array.from({ length: 6 }, (_, i) => ({
        text: `noisy ${i}`, hasHeading: false, hasLink: false, hasSnippet: false,
      })),
    ]
    assert.equal(detectListingSubtype(8, items), 'generic')
  })
})

// ---------------------------------------------------------------------------
// listing-subtype injection — exercises the parser-side helper that injects
// the extract_structured action when analyze_page reports a non-generic
// listing subtype.
// ---------------------------------------------------------------------------

import {
  shouldAutoEmitListingIteration,
  buildListingIterationAction,
  injectCardIterationFollowUp,
} from '../services/coworkPlanParser.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

function analyzeEntry(data: unknown) {
  return {
    action: { kind: 'browser', operation: 'analyze_page', payload: {} } as CoworkAction,
    result: { ok: true, data, durationMs: 5 },
  }
}

const PRODUCT_LISTING = {
  pageType: { listing: true, social_feed: false, article: false },
  signals: { listLikeCount: 8, repeatingCardCount: 8, listingSubtype: 'product_listing' },
  url: 'https://example-shop.com/products',
}

const SEARCH_RESULTS = {
  pageType: { listing: true, social_feed: false },
  signals: { listLikeCount: 12, repeatingCardCount: 12, listingSubtype: 'search_results' },
  url: 'https://example-search.com/q?x=test',
}

const NEWS_LISTING = {
  pageType: { listing: true, social_feed: false },
  signals: { listLikeCount: 7, repeatingCardCount: 7, listingSubtype: 'news_listing' },
  url: 'https://example-news.com/',
}

const GENERIC_LISTING = {
  pageType: { listing: true, social_feed: false },
  signals: { listLikeCount: 6, repeatingCardCount: 6, listingSubtype: 'generic' },
  url: 'https://example.com/',
}

const SOCIAL_FEED_OVERRIDE = {
  pageType: { listing: true, social_feed: true },
  signals: { listLikeCount: 12, repeatingCardCount: 12, listingSubtype: 'news_listing', avatarHits: 8, hasTimestamps: true, reactionButtons: 24 },
  url: 'https://feed.example.com/',
}

const BARE_PLAN: CoworkPlan = {
  reasoning: 'r', expectedOutcome: 'o',
  actions: [
    { kind: 'reply', message: 'voici la liste' },
    { kind: 'finish', summary: 'fait' },
  ],
}

describe('shouldAutoEmitListingIteration', () => {
  test('fires on product_listing', () => {
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [analyzeEntry(PRODUCT_LISTING)]), true)
  })

  test('fires on search_results', () => {
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [analyzeEntry(SEARCH_RESULTS)]), true)
  })

  test('fires on news_listing', () => {
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [analyzeEntry(NEWS_LISTING)]), true)
  })

  test('does NOT fire on generic listing', () => {
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [analyzeEntry(GENERIC_LISTING)]), false)
  })

  test('does NOT fire when social_feed=true (social branch wins)', () => {
    assert.equal(
      shouldAutoEmitListingIteration(BARE_PLAN, [analyzeEntry(SOCIAL_FEED_OVERRIDE)]),
      false,
      'social_feed must take priority',
    )
  })

  test('does NOT fire when listing=false', () => {
    const articleEntry = analyzeEntry({
      pageType: { listing: false, article: true },
      signals: { listLikeCount: 0, articleQuality: 'rich' },
    })
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [articleEntry]), false)
  })

  test('does NOT fire when card count<5', () => {
    const lowCount = analyzeEntry({
      pageType: { listing: true },
      signals: { listLikeCount: 3, repeatingCardCount: 3, listingSubtype: 'product_listing' },
    })
    assert.equal(shouldAutoEmitListingIteration(BARE_PLAN, [lowCount]), false)
  })

  test('no double-emit when plan already has card_iteration', () => {
    const planWithIter: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { intent: 'x', mode: 'card_iteration' } },
        { kind: 'finish', summary: 'done' },
      ],
    }
    assert.equal(shouldAutoEmitListingIteration(planWithIter, [analyzeEntry(PRODUCT_LISTING)]), false)
  })
})

describe('buildListingIterationAction', () => {
  test('product_listing → intent contains product/price/currency keywords', () => {
    const a = buildListingIterationAction(PRODUCT_LISTING)
    assert.equal(a.kind, 'browser')
    if (a.kind !== 'browser') return
    assert.equal(a.operation, 'extract_structured')
    const p = a.payload as Record<string, unknown>
    assert.equal(p.mode, 'card_iteration')
    assert.match(String(p.intent), /product|price|currency/i)
    const cs = p.card_signals as Record<string, unknown>
    assert.equal(cs.listing_subtype, 'product_listing')
    assert.equal(cs.repeating_card_count, 8)
  })

  test('search_results → intent contains search/snippet/url', () => {
    const a = buildListingIterationAction(SEARCH_RESULTS)
    if (a.kind !== 'browser') return assert.fail('expected browser')
    const p = a.payload as Record<string, unknown>
    assert.match(String(p.intent), /search|snippet|url/i)
    const cs = p.card_signals as Record<string, unknown>
    assert.equal(cs.listing_subtype, 'search_results')
  })

  test('news_listing → intent contains news/date/author', () => {
    const a = buildListingIterationAction(NEWS_LISTING)
    if (a.kind !== 'browser') return assert.fail('expected browser')
    const p = a.payload as Record<string, unknown>
    assert.match(String(p.intent), /news|date|author/i)
    const cs = p.card_signals as Record<string, unknown>
    assert.equal(cs.listing_subtype, 'news_listing')
  })
})

describe('injectCardIterationFollowUp — listing branch', () => {
  test('product listing → action injected before reply/finish', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzeEntry(PRODUCT_LISTING)])
    assert.equal(out.actions.length, 3)
    assert.equal(out.actions[0].kind, 'browser')
    if (out.actions[0].kind !== 'browser') return
    assert.equal(out.actions[0].operation, 'extract_structured')
    const p = out.actions[0].payload as Record<string, unknown>
    assert.equal((p.card_signals as Record<string, unknown>).listing_subtype, 'product_listing')
  })

  test('generic listing → plan untouched', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzeEntry(GENERIC_LISTING)])
    assert.equal(out, BARE_PLAN)
  })

  test('social_feed wins over listing subtype (existing branch)', () => {
    const out = injectCardIterationFollowUp(BARE_PLAN, [analyzeEntry(SOCIAL_FEED_OVERRIDE)])
    assert.equal(out.actions.length, 3)
    if (out.actions[0].kind !== 'browser') return
    const p = out.actions[0].payload as Record<string, unknown>
    // Social feed action does NOT propagate listing_subtype — its card_signals
    // shape is { repeating_card_count, has_avatars, has_timestamps, has_reactions }.
    const cs = p.card_signals as Record<string, unknown>
    assert.equal(cs.has_avatars, true)
    assert.equal(cs.listing_subtype, undefined, 'social branch must NOT carry listing_subtype')
  })
})
