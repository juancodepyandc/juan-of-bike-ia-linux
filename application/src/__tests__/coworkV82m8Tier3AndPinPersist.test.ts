/**
 * v82m8 — Tests for pass 38 :
 *
 *   1. buildIneffectiveHostHint tier-3 escalation        (coworkPlanParser.ts)
 *      - 4 cases : both effective, only tier-1 ineffective,
 *        only tier-2 ineffective, both ineffective
 *
 *   2. enrichPlannerContextWithBridgeSignals trend-list   (coworkPlannerCtxEnricher.ts)
 *      - populates `trendIneffectiveHosts` from bridge `/trend-signal-stats`
 *      - threshold (>=3 emitted, 0 accepted) honored
 *      - cache TTL preserved across calls
 *
 *   3. coworkConnectorPin chrome.storage.local mirror     (coworkConnectorPin.ts)
 *      - debounced 200 ms write
 *      - hydrate on cold start (localStorage empty → reads mirror)
 *      - reload simulation : pin → clear localStorage → hydrate → pin survives
 *
 * Pure tests — no DOM, no network, no React. Run :
 *   node --experimental-strip-types --test src/__tests__/coworkV82m8Tier3AndPinPersist.test.ts
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

import {
  buildIneffectiveHostHint,
} from '../services/coworkPlanParser.ts'
import {
  shouldRenderIneffectiveBadge,
} from '../services/coworkExtractionStats.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// 1) buildIneffectiveHostHint tier-3 escalation
// ---------------------------------------------------------------------------

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

describe('buildIneffectiveHostHint tier-3 escalation (v82m8)', () => {
  test('both effective (no ineffective lists) → empty string', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    assert.equal(buildIneffectiveHostHint(undefined, h, undefined), '')
    assert.equal(buildIneffectiveHostHint([], h, []), '')
  })

  test('only tier-1 ineffective (tier-2 empty) → DUAL_SIGNAL_INEFFECTIVE hint', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h, [])
    assert.match(hint, /DUAL_SIGNAL_INEFFECTIVE/)
    assert.equal(hint.includes('TIER_3'), false, 'no tier-3 nudge when only tier-1')
    assert.equal(hint.includes('TREND_INEFFECTIVE'), false)
  })

  test('only tier-2 ineffective (tier-1 empty) → TREND_INEFFECTIVE hint', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint([], h, ['linkedin.com'])
    assert.match(hint, /TREND_INEFFECTIVE/)
    assert.equal(hint.includes('TIER_3'), false, 'no tier-3 nudge when only tier-2')
    assert.equal(hint.includes('DUAL_SIGNAL_INEFFECTIVE'), false)
  })

  test('BOTH tiers ineffective → TIER_3_NO_AUTO_ESCALATION (terminal)', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h, ['linkedin.com'])
    assert.match(hint, /\[HINT\] TIER_3_NO_AUTO_ESCALATION/)
    assert.match(hint, /STOP automatic escalation/)
    assert.match(hint, /manual review/i)
    assert.match(hint, /anti-bot/)
    assert.match(hint, /opt-in connector/)
    assert.match(hint, /direct user assistance/)
    // Single-line semantics within body (the leading "\n" delimiter is OK).
    const body = hint.startsWith('\n') ? hint.slice(1) : hint
    assert.equal(body.includes('\n'), false)
  })

  test('TIER_3 supersedes single-tier hints (no double-emission)', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h, ['linkedin.com'])
    // Tier-3 wins ; tier-1 / tier-2 strings must NOT appear too.
    assert.equal(hint.includes('DUAL_SIGNAL_INEFFECTIVE'), false)
    assert.equal(hint.includes('TREND_INEFFECTIVE'), false)
  })

  test('host normalisation : strips www. and lowercases for both lists', () => {
    const h = [extractEntryWithUrl('https://www.LinkedIn.com/feed')]
    const hint = buildIneffectiveHostHint(['www.LINKEDIN.com'], h, ['LinkedIn.com'])
    assert.match(hint, /TIER_3_NO_AUTO_ESCALATION/)
  })

  test('current host NOT in either list → empty string', () => {
    const h = [extractEntryWithUrl('https://reddit.com/r/news')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h, ['github.com'])
    assert.equal(hint, '')
  })

  test('cross-host : tier-1 lists linkedin, tier-2 lists github, current=linkedin → tier-1 hint', () => {
    const h = [extractEntryWithUrl('https://linkedin.com/feed')]
    const hint = buildIneffectiveHostHint(['linkedin.com'], h, ['github.com'])
    assert.match(hint, /DUAL_SIGNAL_INEFFECTIVE/)
    assert.equal(hint.includes('TIER_3'), false)
  })

  test('empty history → empty string regardless of lists', () => {
    assert.equal(buildIneffectiveHostHint(['linkedin.com'], [], ['linkedin.com']), '')
  })
})

// ---------------------------------------------------------------------------
// 1b) shouldRenderIneffectiveBadge — pure tile decision helper
// ---------------------------------------------------------------------------

describe('shouldRenderIneffectiveBadge (v82m8)', () => {
  test('null / undefined → false (no snapshot, no badge)', () => {
    assert.equal(shouldRenderIneffectiveBadge(null), false)
    assert.equal(shouldRenderIneffectiveBadge(undefined), false)
  })

  test('emitted=0 (no events yet, default trust) → false', () => {
    assert.equal(shouldRenderIneffectiveBadge({ effective: true, emitted: 0, accepted: 0 }), false)
  })

  test('emitted>0, effective=true → false (silent default OK)', () => {
    assert.equal(shouldRenderIneffectiveBadge({ effective: true, emitted: 5, accepted: 1 }), false)
  })

  test('emitted>0, effective=false → true (RED badge)', () => {
    assert.equal(shouldRenderIneffectiveBadge({ effective: false, emitted: 5, accepted: 0 }), true)
  })

  test('emitted=NaN → false (defensive)', () => {
    assert.equal(shouldRenderIneffectiveBadge({ effective: false, emitted: NaN, accepted: 0 }), false)
  })

  test('emitted=Infinity → false (defensive)', () => {
    assert.equal(shouldRenderIneffectiveBadge({ effective: false, emitted: Infinity, accepted: 0 }), false)
  })
})

// ---------------------------------------------------------------------------
// 2) enrichPlannerContextWithBridgeSignals trend ineffective list
// ---------------------------------------------------------------------------

const cardExtract: CoworkAction = {
  kind: 'browser',
  operation: 'extract_structured',
  payload: { intent: 'extract', mode: 'card_iteration', url: 'https://linkedin.com/feed' },
}

describe('enrichPlannerContextWithBridgeSignals trendIneffectiveHosts (v82m8)', () => {
  test('trend-signal-stats with emitted>=3, accepted=0 → host added to trendIneffectiveHosts', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return {
          ok: true,
          json: async () => ({ ok: true, host: 'linkedin.com', emitted: 0, accepted: 0, effective: true, min_emitted: 5 }),
        } as Response
      }
      if (typeof url === 'string' && url.includes('trend-signal-stats')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            total_emitted: 5,
            total_accepted: 0,
            acceptance_rate: 0,
            by_host_top5: [
              { host: 'linkedin.com', emitted: 5, accepted: 0, rate: 0 },
              { host: 'reddit.com',   emitted: 1, accepted: 0, rate: 0 },  // below threshold
            ],
          }),
        } as Response
      }
      // extraction-stats : empty
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const out = await enrichPlannerContextWithBridgeSignals({
        history: [{ action: cardExtract, result: { ok: true, data: {}, durationMs: 0 } }],
      })
      assert.deepEqual(out.trendIneffectiveHosts, ['linkedin.com'])
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('trend-signal-stats with accepted>0 → NOT added (acceptance proves effective)', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, host: 'linkedin.com', emitted: 0, accepted: 0, effective: true, min_emitted: 5 }) } as Response
      }
      if (typeof url === 'string' && url.includes('trend-signal-stats')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            total_emitted: 4,
            total_accepted: 1,
            acceptance_rate: 0.25,
            by_host_top5: [{ host: 'linkedin.com', emitted: 4, accepted: 1, rate: 0.25 }],
          }),
        } as Response
      }
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const out = await enrichPlannerContextWithBridgeSignals({
        history: [{ action: cardExtract, result: { ok: true, data: {}, durationMs: 0 } }],
      })
      assert.equal(out.trendIneffectiveHosts, undefined, 'no trend ineffective when accepted > 0')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('trend-signal-stats fetch error → empty trend list (no crash)', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (typeof url === 'string' && url.includes('trend-signal-stats')) {
        throw new Error('bridge down')
      }
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, host: 'linkedin.com', emitted: 0, accepted: 0, effective: true, min_emitted: 5 }) } as Response
      }
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const out = await enrichPlannerContextWithBridgeSignals({
        history: [{ action: cardExtract, result: { ok: true, data: {}, durationMs: 0 } }],
      })
      assert.equal(out.trendIneffectiveHosts, undefined)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

// ---------------------------------------------------------------------------
// 3) coworkConnectorPin chrome.storage.local mirror + debounce + hydrate
// ---------------------------------------------------------------------------

class MemStorage {
  private store = new Map<string, string>()
  getItem(k: string) { return this.store.has(k) ? this.store.get(k)! : null }
  setItem(k: string, v: string) { this.store.set(k, v) }
  removeItem(k: string) { this.store.delete(k) }
  clear() { this.store.clear() }
  get length() { return this.store.size }
  key(i: number) { return Array.from(this.store.keys())[i] ?? null }
}

class FakeChromeStorage {
  store: Record<string, unknown> = {}
  setCalls: Array<Record<string, unknown>> = []
  set = (items: Record<string, unknown>, callback?: () => void) => {
    this.setCalls.push({ ...items })
    Object.assign(this.store, items)
    if (callback) callback()
  }
  get = (
    keys: string | string[] | null,
    callback: (items: Record<string, unknown>) => void,
  ) => {
    if (typeof keys === 'string') {
      callback({ [keys]: this.store[keys] })
    } else if (Array.isArray(keys)) {
      const out: Record<string, unknown> = {}
      for (const k of keys) out[k] = this.store[k]
      callback(out)
    } else {
      callback({ ...this.store })
    }
  }
}

const storage = new MemStorage()
;(globalThis as unknown as { localStorage: MemStorage }).localStorage = storage

describe('coworkConnectorPin chrome.storage.local mirror (v82m8)', () => {
  beforeEach(() => storage.clear())

  test('pinConnector schedules a debounced chrome.storage.local write', async () => {
    const fake = new FakeChromeStorage()
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(fake)
    try {
      pinModule.pinConnector('reddit', 'reddit.com')
      // Immediately after pin → mirror not flushed yet (debounced).
      assert.equal(fake.setCalls.length, 0, 'mirror is debounced, not flushed on pin')
      // Force flush (test seam) — production fires after 200 ms.
      pinModule.flushChromeStorageMirror()
      assert.equal(fake.setCalls.length, 1, 'mirror flushed once')
      const call = fake.setCalls[0]
      const rows = call['cowork:connector_pins'] as Array<{ id: string }>
      assert.equal(rows.length, 1)
      assert.equal(rows[0].id, 'reddit')
    } finally {
      pinModule._setChromeStorageForTesting(null)
      pinModule.flushChromeStorageMirror()  // drain any leftover timer
    }
  })

  test('debounce coalesces multiple pins into a single mirror write', async () => {
    const fake = new FakeChromeStorage()
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(fake)
    try {
      pinModule.pinConnector('reddit', 'reddit.com')
      pinModule.pinConnector('github', 'github.com')
      pinModule.pinConnector('linkedin', 'linkedin.com')
      assert.equal(fake.setCalls.length, 0, 'no flush yet (still debouncing)')
      pinModule.flushChromeStorageMirror()
      assert.equal(fake.setCalls.length, 1, 'single coalesced flush')
      const rows = fake.setCalls[0]['cowork:connector_pins'] as Array<{ id: string }>
      assert.equal(rows.length, 3, 'all three pins captured in the single write')
    } finally {
      pinModule._setChromeStorageForTesting(null)
      pinModule.flushChromeStorageMirror()
    }
  })

  test('hydratePinsFromChromeStorage : cold start with empty localStorage → adopts mirror', async () => {
    const fake = new FakeChromeStorage()
    fake.store['cowork:connector_pins'] = [
      { id: 'reddit', host: 'reddit.com', pinnedAt: 1_700_000_000_000 },
      { id: 'github', host: 'github.com', pinnedAt: 1_700_000_001_000 },
    ]
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(fake)
    storage.clear()  // localStorage empty (cold-start signal)
    try {
      const rows = await pinModule.hydratePinsFromChromeStorage()
      assert.equal(rows.length, 2, 'hydrated 2 pins from chrome.storage.local')
      assert.equal(rows[0].id, 'reddit')
      assert.equal(rows[1].id, 'github')
      // localStorage now reflects the hydrated state.
      const persisted = JSON.parse(storage.getItem('cowork:connector_pins') ?? '[]')
      assert.equal(persisted.length, 2)
    } finally {
      pinModule._setChromeStorageForTesting(null)
      pinModule.flushChromeStorageMirror()
    }
  })

  test('hydratePinsFromChromeStorage : localStorage non-empty → no clobber (web wins)', async () => {
    const fake = new FakeChromeStorage()
    fake.store['cowork:connector_pins'] = [
      { id: 'OLD-MIRROR-ID', host: 'old.com', pinnedAt: 1 },
    ]
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(fake)
    pinModule.clearPinnedConnectors()
    pinModule.pinConnector('NEWER', 'newer.com')
    pinModule.flushChromeStorageMirror()
    try {
      const rows = await pinModule.hydratePinsFromChromeStorage()
      assert.equal(rows.length, 1)
      assert.equal(rows[0].id, 'NEWER', 'localStorage wins over mirror when non-empty')
    } finally {
      pinModule._setChromeStorageForTesting(null)
      pinModule.flushChromeStorageMirror()
    }
  })

  test('reload simulation : pin → mirror → wipe localStorage → hydrate → pin survives', async () => {
    const fake = new FakeChromeStorage()
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(fake)
    pinModule.clearPinnedConnectors()
    try {
      // 1. User pins a connector.
      pinModule.pinConnector('reddit', 'reddit.com')
      pinModule.flushChromeStorageMirror()
      // 2. Page reload simulation : wipe localStorage (fresh navigation).
      storage.clear()
      assert.equal(pinModule.readPinnedConnectors().length, 0, 'localStorage wiped')
      // 3. Hydrate from chrome.storage.local mirror — pin returns.
      const rows = await pinModule.hydratePinsFromChromeStorage()
      assert.equal(rows.length, 1, 'pin survived the reload')
      assert.equal(rows[0].id, 'reddit')
      // 4. readPinnedConnectors() now reflects the hydrated state.
      assert.equal(pinModule.readPinnedConnectors().length, 1)
      assert.equal(pinModule.readPinnedConnectors()[0].id, 'reddit')
    } finally {
      pinModule._setChromeStorageForTesting(null)
      pinModule.flushChromeStorageMirror()
    }
  })

  test('no chrome.storage facade → mirror gracefully no-ops', async () => {
    const pinModule = await import('../services/coworkConnectorPin.ts')
    pinModule._setChromeStorageForTesting(null)
    pinModule.clearPinnedConnectors()
    // Should NOT throw even when chrome.storage is unavailable.
    pinModule.pinConnector('reddit', 'reddit.com')
    pinModule.flushChromeStorageMirror()
    // localStorage path still works.
    assert.equal(pinModule.readPinnedConnectors().length, 1)
  })
})
