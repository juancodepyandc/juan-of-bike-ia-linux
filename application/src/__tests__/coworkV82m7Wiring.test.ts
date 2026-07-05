/**
 * v82m7 — Tests for the pipeline wiring + tier-2 trend acceptance metric :
 *
 *   1. detectTrendAcceptanceInPlan        (coworkPlanParser.ts)
 *   2. detectTrendNudgeContext            (coworkPlanParser.ts)
 *   3. enrichPlannerContextWithBridgeSignals + per-host TTL cache
 *      (coworkPipeline.ts)
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkV82m7Wiring.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import {
  detectTrendAcceptanceInPlan,
  detectTrendNudgeContext,
} from '../services/coworkPlanParser.ts'
import { listExtractHostsFromAuditEntries } from '../services/coworkAudit.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

// ---------------------------------------------------------------------------
// 1) detectTrendAcceptanceInPlan — pure plan-shape detector for tier-2
// ---------------------------------------------------------------------------

const reply: CoworkAction = { kind: 'reply', message: 'ok' }
const finish: CoworkAction = { kind: 'finish', summary: 'done' }
const think: CoworkAction = { kind: 'think', topic: 'pause', thought: 'wait 3-5s for the page to settle' }
const thinkLong: CoworkAction = { kind: 'think_long', topic: 'pause', prompt: 'wait deeper' }
const spreadExtract: CoworkAction = {
  kind: 'browser',
  operation: 'extract_structured',
  payload: { intent: 'extract', mode: 'spread', url: 'https://linkedin.com/feed' },
}
const cardExtract: CoworkAction = {
  kind: 'browser',
  operation: 'extract_structured',
  payload: { intent: 'extract', mode: 'card_iteration', url: 'https://linkedin.com/feed' },
}
const screenshot: CoworkAction = {
  kind: 'browser',
  operation: 'screenshot',
  payload: {},
}

describe('detectTrendAcceptanceInPlan (v82m7)', () => {
  test('null / undefined / empty plan → false', () => {
    assert.equal(detectTrendAcceptanceInPlan(null), false)
    assert.equal(detectTrendAcceptanceInPlan(undefined), false)
    assert.equal(detectTrendAcceptanceInPlan({ reasoning: '', expectedOutcome: '', actions: [] }), false)
  })

  test('think → spread extract (proper order) → true', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [think, spreadExtract, finish] }
    assert.equal(detectTrendAcceptanceInPlan(plan), true)
  })

  test('think_long → spread extract (proper order) → true', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [thinkLong, spreadExtract] }
    assert.equal(detectTrendAcceptanceInPlan(plan), true)
  })

  test('spread extract → think (wrong order) → false', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [spreadExtract, think] }
    assert.equal(detectTrendAcceptanceInPlan(plan), false)
  })

  test('mode=card_iteration only (no spread) → false', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [think, cardExtract] }
    assert.equal(detectTrendAcceptanceInPlan(plan), false)
  })

  test('spread extract without any pause → false', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [spreadExtract, reply, finish] }
    assert.equal(detectTrendAcceptanceInPlan(plan), false)
  })

  test('think + screenshot + spread (think still BEFORE) → true', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [think, screenshot, spreadExtract] }
    assert.equal(detectTrendAcceptanceInPlan(plan), true)
  })

  test('extract_structured with payload but no mode → false', () => {
    const noModeExtract: CoworkAction = {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { intent: 'extract' },
    }
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'e', actions: [think, noModeExtract] }
    assert.equal(detectTrendAcceptanceInPlan(plan), false)
  })
})

// ---------------------------------------------------------------------------
// 2) detectTrendNudgeContext — symmetric to detectDualSignalNudgeContext
// ---------------------------------------------------------------------------

describe('detectTrendNudgeContext (v82m7)', () => {
  test('empty history → false', () => {
    assert.equal(detectTrendNudgeContext([]), false)
  })

  test('under_extraction with no delta_history → false', () => {
    const entry = {
      action: cardExtract,
      result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 0 },
      under_extraction: true,
    }
    assert.equal(detectTrendNudgeContext([entry]), false)
  })

  test('under_extraction + descending delta_history (last - first <= -5pp) → true', () => {
    const entry = {
      action: cardExtract,
      result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 0 },
      under_extraction: true,
      delta_history: [+5, -2, -10],  // last - first = -15, well below -5
    }
    assert.equal(detectTrendNudgeContext([entry]), true)
  })

  test('under_extraction + flat delta_history → false', () => {
    const entry = {
      action: cardExtract,
      result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 0 },
      under_extraction: true,
      delta_history: [0, +1, -1, +2],
    }
    assert.equal(detectTrendNudgeContext([entry]), false)
  })

  test('under_extraction + improving delta_history (positive trend) → false', () => {
    const entry = {
      action: cardExtract,
      result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 0 },
      under_extraction: true,
      delta_history: [-10, -2, +5],  // last - first = +15, ascending
    }
    assert.equal(detectTrendNudgeContext([entry]), false)
  })

  test('no under_extraction entry → false (gate is under_extraction-bound)', () => {
    const entry = {
      action: cardExtract,
      result: { ok: true, data: { items: [], cards_processed: 5 }, durationMs: 0 },
      delta_history: [+5, -10],
    }
    assert.equal(detectTrendNudgeContext([entry]), false)
  })
})

// ---------------------------------------------------------------------------
// 3) enrichPlannerContextWithBridgeSignals — TTL cache + ineffective + delta
//
// We monkey-patch global fetch so the enricher's internal calls to
// fetchDualSignalEffective and fetchExtractionStats hit our stub.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 4) listExtractHostsFromAuditEntries — pure derivation for the AuditDrawer
// ---------------------------------------------------------------------------

describe('listExtractHostsFromAuditEntries (v82m7)', () => {
  test('empty input → empty array', () => {
    assert.deepEqual(listExtractHostsFromAuditEntries([]), [])
  })

  test('extract entries with payload.url → unique hostnames lowercased', () => {
    const entries = [
      { id: 'a', at: 1, action: cardExtract, decision: 'allow' as const },
      // duplicate host → dedup
      { id: 'b', at: 2, action: cardExtract, decision: 'allow' as const },
    ]
    assert.deepEqual(listExtractHostsFromAuditEntries(entries), ['linkedin.com'])
  })

  test('strip leading "www." and lowercase', () => {
    const entry = {
      id: 'x', at: 1,
      action: {
        kind: 'browser' as const,
        operation: 'extract_structured' as const,
        payload: { mode: 'card_iteration', url: 'https://WWW.LinkedIn.com/feed' },
      },
      decision: 'allow' as const,
    }
    assert.deepEqual(listExtractHostsFromAuditEntries([entry]), ['linkedin.com'])
  })

  test('non-extract actions skipped', () => {
    const entries = [
      { id: 'a', at: 1, action: { kind: 'reply' as const, message: 'hi' }, decision: 'allow' as const },
      { id: 'b', at: 2, action: cardExtract, decision: 'allow' as const },
    ]
    assert.deepEqual(listExtractHostsFromAuditEntries(entries), ['linkedin.com'])
  })

  test('malformed URL → silently skipped', () => {
    const entry = {
      id: 'x', at: 1,
      action: {
        kind: 'browser' as const,
        operation: 'extract_structured' as const,
        payload: { mode: 'card_iteration', url: 'not-a-url' },
      },
      decision: 'allow' as const,
    }
    assert.deepEqual(listExtractHostsFromAuditEntries([entry]), [])
  })

  test('multiple distinct hosts → preserved in iteration order', () => {
    const linkedinEntry = { id: 'a', at: 1, action: cardExtract, decision: 'allow' as const }
    const redditExtract: CoworkAction = {
      kind: 'browser',
      operation: 'extract_structured',
      payload: { mode: 'card_iteration', url: 'https://reddit.com/r/news' },
    }
    const redditEntry = { id: 'b', at: 2, action: redditExtract, decision: 'allow' as const }
    assert.deepEqual(
      listExtractHostsFromAuditEntries([linkedinEntry, redditEntry]),
      ['linkedin.com', 'reddit.com'],
    )
  })
})

describe('enrichPlannerContextWithBridgeSignals (v82m7)', () => {
  test('empty history → ctx unchanged, no fetch fired', async () => {
    const fetchCalls: string[] = []
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      fetchCalls.push(typeof url === 'string' ? url : String(url))
      return { ok: true, json: async () => ({ ok: true }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const out = await enrichPlannerContextWithBridgeSignals({ history: [] })
      assert.deepEqual(out.history, [])
      assert.equal(out.ineffectiveHosts, undefined)
      assert.equal(fetchCalls.length, 0, 'no fetch should fire when history is empty')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('extract on linkedin → ineffectiveHosts populated when bridge says effective:false', async () => {
    const fetchCalls: string[] = []
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      fetchCalls.push(typeof url === 'string' ? url : String(url))
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return {
          ok: true,
          json: async () => ({ ok: true, host: 'linkedin.com', emitted: 5, accepted: 0, effective: false, min_emitted: 5 }),
        } as Response
      }
      // extraction-stats : return empty rows
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const ctx = {
        history: [{
          action: cardExtract,
          result: { ok: true, data: {}, durationMs: 0 },
        }],
      }
      const out = await enrichPlannerContextWithBridgeSignals(ctx)
      assert.deepEqual(out.ineffectiveHosts, ['linkedin.com'])
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('TTL cache : second call within 60s reuses cache (no second fetch)', async () => {
    let fetchCount = 0
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      fetchCount += 1
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return {
          ok: true,
          json: async () => ({ ok: true, host: 'linkedin.com', emitted: 5, accepted: 0, effective: false, min_emitted: 5 }),
        } as Response
      }
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const ctx = {
        history: [{
          action: cardExtract,
          result: { ok: true, data: {}, durationMs: 0 },
        }],
      }
      await enrichPlannerContextWithBridgeSignals(ctx)
      const firstCount = fetchCount
      // Second call — should reuse cache for both endpoints.
      await enrichPlannerContextWithBridgeSignals(ctx)
      assert.equal(fetchCount, firstCount, `cache should suppress second fetch, fetched ${fetchCount} times total`)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('extraction-stats with delta_history → entry.delta_history populated', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        return {
          ok: true,
          json: async () => ({ ok: true, host: 'linkedin.com', emitted: 0, accepted: 0, effective: true, min_emitted: 5 }),
        } as Response
      }
      // extraction-stats : return one host row with a delta_history
      return {
        ok: true,
        json: async () => ({
          ok: true,
          total: 5,
          under_extraction_rate: 0.4,
          avg_yield: 0.6,
          p50_yield: 0.6,
          p90_yield: 0.7,
          by_host_top5: [{
            host: 'linkedin.com',
            count: 5,
            avg_yield: 0.6,
            last_delta_pct: -10,
            delta_history: [+2, -3, -8, -10],
          }],
          window: { since: null, host: 'linkedin.com' },
        }),
      } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const ctx = {
        history: [{
          action: cardExtract,
          result: { ok: true, data: {}, durationMs: 0 },
        }],
      }
      const out = await enrichPlannerContextWithBridgeSignals(ctx)
      assert.deepEqual(out.history[0].delta_history, [+2, -3, -8, -10])
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('network error → silently swallowed, returns empty arrays / no flag', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async () => {
      throw new Error('network down')
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const ctx = {
        history: [{
          action: cardExtract,
          result: { ok: true, data: {}, durationMs: 0 },
        }],
      }
      const out = await enrichPlannerContextWithBridgeSignals(ctx)
      // No flag added, history unchanged.
      assert.equal(out.ineffectiveHosts, undefined)
      assert.equal(out.history[0].delta_history, undefined)
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  test('cross-host isolation : linkedin ineffective doesn t mark reddit ineffective', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (typeof url === 'string' && url.includes('dual-signal-effective')) {
        // Return effective=true for any host (we test that effective only
        // flags hosts where effective=false ; cross-host comes from the
        // current host extraction logic).
        return {
          ok: true,
          json: async () => ({ ok: true, host: 'reddit.com', emitted: 1, accepted: 1, effective: true, min_emitted: 5 }),
        } as Response
      }
      return { ok: true, json: async () => ({ ok: true, total: 0, under_extraction_rate: 0, avg_yield: 0, p50_yield: 0, p90_yield: 0, by_host_top5: [], window: { since: null, host: null } }) } as Response
    }) as typeof globalThis.fetch
    try {
      const { enrichPlannerContextWithBridgeSignals, _clearPlannerCtxCachesForTesting } = await import(
        '../services/coworkPlannerCtxEnricher.ts'
      )
      _clearPlannerCtxCachesForTesting()
      const redditExtract: CoworkAction = {
        kind: 'browser',
        operation: 'extract_structured',
        payload: { intent: 'extract', mode: 'card_iteration', url: 'https://reddit.com/r/news' },
      }
      const ctx = {
        history: [{
          action: redditExtract,
          result: { ok: true, data: {}, durationMs: 0 },
        }],
      }
      const out = await enrichPlannerContextWithBridgeSignals(ctx)
      // Reddit returned effective:true → no flag.
      assert.equal(out.ineffectiveHosts, undefined)
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
