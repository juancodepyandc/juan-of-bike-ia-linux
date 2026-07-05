/**
 * v82m9 — Tests for pass 39 :
 *
 *   1. detectPinConflict pure helper                       (coworkConnectorPin.ts)
 *      - 4 cases : no pin, no reco, pin matches reco, pin differs from reco
 *      - host normalisation across both sides
 *      - empty inputs → null
 *
 *   2. postTrendSignalReset bridge wrapper                 (coworkExtractionStats.ts)
 *      - happy path returns parsed envelope
 *      - non-200 → null
 *      - bad JSON / ok:false → null
 *      - empty host → null without fetch
 *
 *   3. Cluster reset path semantics
 *      - both reset endpoints fire when invoked together (parallel)
 *      - the URL contains the host param (encodeURIComponent)
 *
 * Pure tests — no DOM, no React. Run :
 *   node --experimental-strip-types --test src/__tests__/coworkV82m9ResetClusterAndConflict.test.ts
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

class MemStorage {
  private store = new Map<string, string>()
  getItem(k: string) { return this.store.has(k) ? this.store.get(k)! : null }
  setItem(k: string, v: string) { this.store.set(k, v) }
  removeItem(k: string) { this.store.delete(k) }
  clear() { this.store.clear() }
  get length() { return this.store.size }
  key(i: number) { return Array.from(this.store.keys())[i] ?? null }
}

const storage = new MemStorage()
;(globalThis as unknown as { localStorage: MemStorage }).localStorage = storage

// ---------------------------------------------------------------------------
// 1) detectPinConflict pure helper
// ---------------------------------------------------------------------------

describe('detectPinConflict pure helper (v82m9)', () => {
  test('matching pin and reco → null (no conflict)', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'reddit', host: 'reddit.com', pinnedAt: 1 }],
      [{ host: 'reddit.com', connectorId: 'reddit' }],
      'reddit.com',
    )
    assert.equal(conflict, null)
  })

  test('mismatched pin vs reco → ConflictDescriptor', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'reddit-classic', host: 'reddit.com', pinnedAt: 1 }],
      [{ host: 'reddit.com', connectorId: 'reddit' }],
      'reddit.com',
    )
    assert.ok(conflict, 'conflict expected')
    assert.equal(conflict!.host, 'reddit.com')
    assert.equal(conflict!.pinnedId, 'reddit-classic')
    assert.equal(conflict!.suggestedId, 'reddit')
    assert.match(conflict!.message, /reddit-classic/)
    assert.match(conflict!.message, /reddit/)
  })

  test('no pin for the host → null', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'github', host: 'github.com', pinnedAt: 1 }],
      [{ host: 'reddit.com', connectorId: 'reddit' }],
      'reddit.com',
    )
    assert.equal(conflict, null)
  })

  test('no reco for the host → null', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'reddit-classic', host: 'reddit.com', pinnedAt: 1 }],
      [{ host: 'github.com', connectorId: 'github' }],
      'reddit.com',
    )
    assert.equal(conflict, null)
  })

  test('host normalisation : www.X.com matches x.com on both sides', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'reddit-classic', host: 'WWW.Reddit.com', pinnedAt: 1 }],
      [{ host: 'reddit.com', connectorId: 'reddit' }],
      'www.REDDIT.com',
    )
    assert.ok(conflict, 'conflict expected post-normalisation')
    assert.equal(conflict!.host, 'reddit.com')
  })

  test('multiple recos for same host : matched id wins → null', async () => {
    // If ANY reco matches the pin, treat the conflict as resolved (the
    // user pinned a connector the catalog also recommends — even if other
    // recos disagree).
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [{ id: 'reddit', host: 'reddit.com', pinnedAt: 1 }],
      [
        { host: 'reddit.com', connectorId: 'reddit' },
        { host: 'reddit.com', connectorId: 'reddit-alt' },
      ],
      'reddit.com',
    )
    assert.equal(conflict, null, 'matched reco resolves the conflict')
  })

  test('empty inputs → null', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    assert.equal(detectPinConflict([], [], 'reddit.com'), null)
    assert.equal(detectPinConflict([{ id: 'r', host: 'r.com', pinnedAt: 1 }], [], 'r.com'), null)
    assert.equal(detectPinConflict([], [{ host: 'r.com', connectorId: 'r' }], 'r.com'), null)
    assert.equal(
      detectPinConflict(
        [{ id: 'r', host: 'r.com', pinnedAt: 1 }],
        [{ host: 'r.com', connectorId: 'r2' }],
        '',
      ),
      null,
    )
  })

  test('most-recent (top) pin wins when multiple pins same host', async () => {
    const { detectPinConflict } = await import('../services/coworkConnectorPin.ts')
    const conflict = detectPinConflict(
      [
        // top-first ordering : reddit-classic pinned most recently
        { id: 'reddit-classic', host: 'reddit.com', pinnedAt: 2 },
        { id: 'reddit-old',     host: 'reddit.com', pinnedAt: 1 },
      ],
      [{ host: 'reddit.com', connectorId: 'reddit' }],
      'reddit.com',
    )
    assert.ok(conflict)
    assert.equal(conflict!.pinnedId, 'reddit-classic', 'top pin is the active one')
  })
})

// ---------------------------------------------------------------------------
// 2) postTrendSignalReset bridge wrapper
// ---------------------------------------------------------------------------

describe('postTrendSignalReset bridge wrapper (v82m9)', () => {
  test('happy path : returns parsed envelope', async () => {
    const original = globalThis.fetch
    const calls: string[] = []
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method || 'GET'} ${url}`)
      return {
        ok: true,
        json: async () => ({
          ok: true,
          host: 'linkedin.com',
          cleared_emitted: 5,
          cleared_accepted: 1,
        }),
      } as Response
    }) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      const result = await postTrendSignalReset('linkedin.com')
      assert.ok(result)
      assert.equal(result!.host, 'linkedin.com')
      assert.equal(result!.cleared_emitted, 5)
      assert.equal(result!.cleared_accepted, 1)
      assert.equal(calls.length, 1)
      assert.match(calls[0], /^POST \/api\/cowork\/trend-signal-reset\?host=linkedin\.com$/)
    } finally {
      globalThis.fetch = original
    }
  })

  test('non-200 → null', async () => {
    const original = globalThis.fetch
    globalThis.fetch = (async () => ({
      ok: false,
      json: async () => ({}),
    } as Response)) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      const result = await postTrendSignalReset('x.com')
      assert.equal(result, null)
    } finally {
      globalThis.fetch = original
    }
  })

  test('ok:false envelope → null', async () => {
    const original = globalThis.fetch
    globalThis.fetch = (async () => ({
      ok: true,
      json: async () => ({ ok: false, error: 'bad host' }),
    } as Response)) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      const result = await postTrendSignalReset('x.com')
      assert.equal(result, null)
    } finally {
      globalThis.fetch = original
    }
  })

  test('empty host → null without fetch', async () => {
    let called = false
    const original = globalThis.fetch
    globalThis.fetch = (async () => {
      called = true
      return { ok: true, json: async () => ({}) } as Response
    }) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      const result = await postTrendSignalReset('')
      assert.equal(result, null)
      assert.equal(called, false, 'empty host short-circuits before fetch')
    } finally {
      globalThis.fetch = original
    }
  })

  test('network throw → null (catches gracefully)', async () => {
    const original = globalThis.fetch
    globalThis.fetch = (async () => {
      throw new Error('bridge down')
    }) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      const result = await postTrendSignalReset('linkedin.com')
      assert.equal(result, null)
    } finally {
      globalThis.fetch = original
    }
  })

  test('host param is URL-encoded', async () => {
    const original = globalThis.fetch
    let lastUrl = ''
    globalThis.fetch = (async (url: string) => {
      lastUrl = url
      return {
        ok: true,
        json: async () => ({ ok: true, host: 'x', cleared_emitted: 0, cleared_accepted: 0 }),
      } as Response
    }) as typeof globalThis.fetch
    try {
      const { postTrendSignalReset } = await import('../services/coworkExtractionStats.ts')
      await postTrendSignalReset('weird host & query')
      assert.match(lastUrl, /weird%20host%20%26%20query/)
    } finally {
      globalThis.fetch = original
    }
  })
})

// ---------------------------------------------------------------------------
// 3) Cluster reset path semantics — both endpoints fire in parallel
// ---------------------------------------------------------------------------

describe('Cluster reset semantics (v82m9)', () => {
  test('Promise.all([dual reset, trend reset]) hits BOTH endpoints', async () => {
    const original = globalThis.fetch
    const hits: string[] = []
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      hits.push(url)
      assert.equal(init?.method, 'POST')
      return {
        ok: true,
        json: async () => ({ ok: true, host: 'linkedin.com', cleared_emitted: 3, cleared_accepted: 0 }),
      } as Response
    }) as typeof globalThis.fetch
    try {
      const { postDualSignalReset, postTrendSignalReset } = await import(
        '../services/coworkExtractionStats.ts'
      )
      const [tier1, tier2] = await Promise.all([
        postDualSignalReset('linkedin.com'),
        postTrendSignalReset('linkedin.com'),
      ])
      assert.ok(tier1)
      assert.ok(tier2)
      assert.equal(hits.length, 2)
      assert.equal(hits.some((u) => u.includes('/api/cowork/dual-signal-reset')), true)
      assert.equal(hits.some((u) => u.includes('/api/cowork/trend-signal-reset')), true)
    } finally {
      globalThis.fetch = original
    }
  })

  test('partial failure (tier-1 ok, tier-2 fails) → caller still gets tier-1 result', async () => {
    const original = globalThis.fetch
    globalThis.fetch = (async (url: string) => {
      if (url.includes('trend-signal-reset')) {
        return { ok: false, json: async () => ({}) } as Response
      }
      return {
        ok: true,
        json: async () => ({ ok: true, host: 'x', cleared_emitted: 1, cleared_accepted: 0 }),
      } as Response
    }) as typeof globalThis.fetch
    try {
      const { postDualSignalReset, postTrendSignalReset } = await import(
        '../services/coworkExtractionStats.ts'
      )
      const [tier1, tier2] = await Promise.all([
        postDualSignalReset('x.com'),
        postTrendSignalReset('x.com'),
      ])
      assert.ok(tier1, 'tier-1 succeeds')
      assert.equal(tier2, null, 'tier-2 fails gracefully')
    } finally {
      globalThis.fetch = original
    }
  })
})
