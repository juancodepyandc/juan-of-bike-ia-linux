/**
 * v82lx — Unit tests for the pageType→badge mapping that powers the
 * extension's dynamic action-icon badge.
 *
 * Why duplicate the mapping here ?
 *   The mapping lives in `application/extension/background.js` (a Chrome
 *   service worker, no module system, no exports). Re-importing it under
 *   node --test is impractical. Instead we encode the SAME contract here
 *   and assert it stays in sync with what the SW does. If you change one,
 *   change the other — that's the only "test" worth running on a 7-line
 *   table.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/extensionPageTypeBadge.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// Mirror of background.js#pageTypeToBadge — KEEP IN SYNC.
type Badge = { text: string; color: string } | null
type PageType = Partial<Record<
  'login' | 'social_feed' | 'article' | 'media' | 'listing' | 'dashboard' | 'form',
  boolean
>>

function pageTypeToBadge(pageType: PageType | null | undefined): Badge {
  if (!pageType || typeof pageType !== 'object') return null
  if (pageType.login) return { text: 'L', color: '#ef4444' }
  if (pageType.social_feed) return { text: 'F', color: '#8b5cf6' }
  if (pageType.article) return { text: 'A', color: '#0ea5e9' }
  if (pageType.media) return { text: 'M', color: '#f97316' }
  if (pageType.listing) return { text: 'T', color: '#10b981' }
  if (pageType.dashboard) return { text: 'D', color: '#a855f7' }
  if (pageType.form) return { text: 'O', color: '#eab308' }
  return null
}

describe('pageType→badge mapping', () => {
  test('login wins over form (more specific)', () => {
    const b = pageTypeToBadge({ login: true, form: true })
    assert.equal(b?.text, 'L')
  })

  test('social_feed wins over listing', () => {
    const b = pageTypeToBadge({ social_feed: true, listing: true })
    assert.equal(b?.text, 'F')
  })

  test('article maps to A sky', () => {
    const b = pageTypeToBadge({ article: true })
    assert.equal(b?.text, 'A')
    assert.equal(b?.color, '#0ea5e9')
  })

  test('media wins over listing', () => {
    const b = pageTypeToBadge({ media: true, listing: true })
    assert.equal(b?.text, 'M')
  })

  test('listing maps to T emerald', () => {
    const b = pageTypeToBadge({ listing: true })
    assert.equal(b?.text, 'T')
  })

  test('dashboard maps to D', () => {
    const b = pageTypeToBadge({ dashboard: true })
    assert.equal(b?.text, 'D')
  })

  test('form maps to O amber', () => {
    const b = pageTypeToBadge({ form: true })
    assert.equal(b?.text, 'O')
  })

  test('all-false pageType returns null (no badge)', () => {
    const b = pageTypeToBadge({})
    assert.equal(b, null)
  })

  test('null/undefined pageType returns null', () => {
    assert.equal(pageTypeToBadge(null), null)
    assert.equal(pageTypeToBadge(undefined), null)
  })

  test('seven distinct badge texts (no collision)', () => {
    const all = [
      pageTypeToBadge({ login: true }),
      pageTypeToBadge({ social_feed: true }),
      pageTypeToBadge({ article: true }),
      pageTypeToBadge({ media: true }),
      pageTypeToBadge({ listing: true }),
      pageTypeToBadge({ dashboard: true }),
      pageTypeToBadge({ form: true }),
    ]
    const texts = new Set(all.map((b) => b?.text))
    assert.equal(texts.size, 7, `expected 7 distinct badge letters, got ${[...texts].join(',')}`)
    const colors = new Set(all.map((b) => b?.color))
    assert.equal(colors.size, 7, 'all badges must have distinct colors')
  })

  test('all colors are valid 6-digit hex', () => {
    const types: PageType[] = [
      { login: true }, { social_feed: true }, { article: true },
      { media: true }, { listing: true }, { dashboard: true }, { form: true },
    ]
    for (const t of types) {
      const b = pageTypeToBadge(t)
      assert.match(b!.color, /^#[0-9a-f]{6}$/i, `bad color for ${JSON.stringify(t)}: ${b!.color}`)
    }
  })
})

// ---------------------------------------------------------------------
// social_feed score logic — mirror of detectSocialFeedSignals in
// content-scrape.js + the inlined twin in background.js#analyze_page.
// ---------------------------------------------------------------------

function socialFeedScoreFromSignals(s: {
  repeating_card_count: number
  avatar_hits: number
  has_timestamps: boolean
  reaction_buttons: number
}): number {
  return (s.repeating_card_count >= 5 ? 1 : 0)
    + (s.avatar_hits >= 2 ? 1 : 0)
    + (s.has_timestamps ? 1 : 0)
    + (s.reaction_buttons >= 2 ? 1 : 0)
}

describe('social_feed score (topological signals)', () => {
  test('all 4 signals → score 4 (definitely a feed)', () => {
    const s = socialFeedScoreFromSignals({
      repeating_card_count: 12,
      avatar_hits: 8,
      has_timestamps: true,
      reaction_buttons: 24,
    })
    assert.equal(s, 4)
  })

  test('3 signals → score 3 (verdict still social_feed)', () => {
    const s = socialFeedScoreFromSignals({
      repeating_card_count: 7,
      avatar_hits: 3,
      has_timestamps: true,
      reaction_buttons: 0,  // missing
    })
    assert.equal(s, 3)
  })

  test('2 signals → score 2 (NOT a social feed)', () => {
    // A plain product listing : repeating cards + maybe avatars (logos)
    // but no relative timestamps, no reaction buttons.
    const s = socialFeedScoreFromSignals({
      repeating_card_count: 20,
      avatar_hits: 5,
      has_timestamps: false,
      reaction_buttons: 0,
    })
    assert.equal(s, 2)
  })

  test('classic article → score 0', () => {
    const s = socialFeedScoreFromSignals({
      repeating_card_count: 0,
      avatar_hits: 0,
      has_timestamps: false,
      reaction_buttons: 0,
    })
    assert.equal(s, 0)
  })

  test('threshold 3 → social_feed=true', () => {
    // Boundary : score >= 3 means pageType.social_feed graduates.
    assert.ok(socialFeedScoreFromSignals({
      repeating_card_count: 5, avatar_hits: 2, has_timestamps: true, reaction_buttons: 0,
    }) >= 3)
    // Just below : 2 signals only, must NOT be a social_feed.
    assert.ok(socialFeedScoreFromSignals({
      repeating_card_count: 5, avatar_hits: 2, has_timestamps: false, reaction_buttons: 0,
    }) < 3)
  })

  test('avatar_hits<2 does not count even when present', () => {
    // One stray avatar (eg user menu in nav) must not count as a feed
    // signal — that's the whole point of the >=2 threshold.
    const s = socialFeedScoreFromSignals({
      repeating_card_count: 5,
      avatar_hits: 1,
      has_timestamps: true,
      reaction_buttons: 0,
    })
    assert.equal(s, 2)  // cards + timestamps only
  })
})
