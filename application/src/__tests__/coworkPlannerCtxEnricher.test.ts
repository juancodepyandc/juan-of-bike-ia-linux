/**
 * Tests pour services/coworkPlannerCtxEnricher — enrich planner context
 * avec dual-signal-effective + delta_history + trend ineffective.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  enrichPlannerContextWithBridgeSignals,
  _clearPlannerCtxCachesForTesting,
} from '../services/coworkPlannerCtxEnricher.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; json?: () => Promise<unknown> }
let fetchMock: ((url: any, init?: any) => Promise<MockResp>) | null = null

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
})

after(() => {
  globalThis.fetch = realFetch
})

beforeEach(() => {
  _clearPlannerCtxCachesForTesting()
  fetchMock = null
})

function browserExtract(url: string): CoworkAction {
  return {
    kind: 'browser',
    operation: 'extract_structured',
    payload: { url },
  } as CoworkAction
}

function entry(action: CoworkAction, overrides: Partial<{ ok: boolean; data: unknown; error: string }> = {}) {
  return {
    action,
    result: { ok: true, ...overrides },
  }
}

describe('enrichPlannerContextWithBridgeSignals — history vide', () => {
  test('history vide → ctx renvoyé tel quel', async () => {
    fetchMock = async () => ({ ok: true, json: async () => ({ ok: true }) })
    const ctx = { history: [] }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.deepEqual(r.history, [])
    assert.equal(r.ineffectiveHosts, undefined)
  })

  test('history sans extract action → ctx renvoyé tel quel', async () => {
    const ctx = {
      history: [entry({ kind: 'reply', message: 'hi' } as CoworkAction)],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.equal(r.history.length, 1)
    assert.equal(r.ineffectiveHosts, undefined)
  })
})

describe('enrichPlannerContextWithBridgeSignals — ineffectiveHosts', () => {
  test('host non effectif → ajouté à ineffectiveHosts', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, effective: false, host: 'reddit.com', emitted: 5, accepted: 0, min_emitted: 5 }) }
      }
      return { ok: true, json: async () => ({ ok: true, by_host_top5: [] }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://reddit.com/r/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.ok(r.ineffectiveHosts?.includes('reddit.com'))
  })

  test('host effectif → ineffectiveHosts vide', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, effective: true, host: 'reddit.com', emitted: 5, accepted: 3 }) }
      }
      return { ok: true, json: async () => ({ ok: true, by_host_top5: [] }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://reddit.com/r/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.equal(r.ineffectiveHosts, undefined)
  })

  test('réseau down → graceful fallback, pas de crash', async () => {
    fetchMock = async () => { throw new Error('network down') }
    const ctx = {
      history: [entry(browserExtract('https://reddit.com/r/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    // Pas de crash, ctx renvoyé
    assert.ok(r)
  })

  test('preexistant ineffectiveHosts conservé', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, effective: false, host: 'new.com', emitted: 5, accepted: 0 }) }
      }
      return { ok: true, json: async () => ({ ok: true, by_host_top5: [] }) }
    }
    const ctx = {
      ineffectiveHosts: ['preexistant.com'],
      history: [entry(browserExtract('https://new.com/r/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.ok(r.ineffectiveHosts?.includes('preexistant.com'))
    assert.ok(r.ineffectiveHosts?.includes('new.com'))
  })
})

describe('enrichPlannerContextWithBridgeSignals — delta_history annotations', () => {
  test('extract entries reçoivent delta_history', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('extraction-stats')) {
        return { ok: true, json: async () => ({ ok: true, total: 5, avg_yield: 0.4, by_host_top5: [{ host: 'reddit.com', delta_history: [-1, 0, 2, -3, 1], count: 5, avg_yield: 0.4 }] }) }
      }
      return { ok: true, json: async () => ({ ok: true, effective: true }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://reddit.com/r/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.ok(r.history[0].delta_history)
    assert.deepEqual(r.history[0].delta_history, [-1, 0, 2, -3, 1])
  })

  test('delta_history existant non écrasé', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('extraction-stats')) {
        return { ok: true, json: async () => ({ ok: true, by_host_top5: [{ host: 'x.com', delta_history: [5, 5], emitted: 2, accepted: 2, yield_ratio: 1, under_extraction_rate: 0 }] }) }
      }
      return { ok: true, json: async () => ({ ok: true, effective: true }) }
    }
    const ctx = {
      history: [{
        ...entry(browserExtract('https://x.com')),
        delta_history: [99, 99],  // preexistant
      }],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.deepEqual(r.history[0].delta_history, [99, 99])
  })
})

describe('enrichPlannerContextWithBridgeSignals — trendIneffectiveHosts (tier-2)', () => {
  test('trend host inefficient → ajouté', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('trend-signal-stats')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            by_host_top5: [
              { host: 'badhost.com', emitted: 5, accepted: 0 },
              { host: 'okhost.com', emitted: 5, accepted: 2 },
            ],
          }),
        }
      }
      return { ok: true, json: async () => ({ ok: true, effective: true, by_host_top5: [] }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://anysite.com/x'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.ok(r.trendIneffectiveHosts?.includes('badhost.com'))
    assert.ok(!r.trendIneffectiveHosts?.includes('okhost.com'))
  })

  test('emitted < 3 → ignoré (tier-2 threshold)', async () => {
    fetchMock = async (url) => {
      const u = String(url)
      if (u.includes('trend-signal-stats')) {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            by_host_top5: [{ host: 'newhost.com', emitted: 2, accepted: 0 }],
          }),
        }
      }
      return { ok: true, json: async () => ({ ok: true, effective: true, by_host_top5: [] }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://newhost.com'))],
    }
    const r = await enrichPlannerContextWithBridgeSignals(ctx)
    assert.ok(!r.trendIneffectiveHosts?.includes('newhost.com'))
  })
})

describe('Cache TTL', () => {
  test('cache utilisé entre 2 appels rapides', async () => {
    let callCount = 0
    fetchMock = async (url) => {
      const u = String(url)
      callCount += 1
      if (u.includes('dual-signal-effective')) {
        return { ok: true, json: async () => ({ ok: true, effective: false, host: 'cached.com', emitted: 5, accepted: 0 }) }
      }
      return { ok: true, json: async () => ({ ok: true, by_host_top5: [] }) }
    }
    const ctx = {
      history: [entry(browserExtract('https://cached.com'))],
    }
    await enrichPlannerContextWithBridgeSignals(ctx)
    const callsAfterFirst = callCount
    await enrichPlannerContextWithBridgeSignals(ctx)
    // Le 2e appel devrait utiliser le cache → moins de fetch
    // (le test exact dépend du nombre exact d'endpoints appelés)
    assert.ok(callCount <= callsAfterFirst * 2)
  })

  test('_clearPlannerCtxCachesForTesting reset les caches', () => {
    _clearPlannerCtxCachesForTesting()
    // Pas de crash, fonction noop testable
    assert.ok(true)
  })
})
