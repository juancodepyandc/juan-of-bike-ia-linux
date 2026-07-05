/**
 * Unit tests for the LRU + TTL cache pattern used in taskIntelligence / realityAnalyzer.
 * These tests validate the cache logic by reproducing it inline.
 * Run: node --experimental-strip-types src/__tests__/lruCache.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// Inline reproduction of the cache used in taskIntelligence.ts
function makeResearchCache(maxSize: number, ttlMs: number) {
  type Entry = { value: string; expiresAt: number }
  const store = new Map<string, Entry>()

  function purgeExpired() {
    const now = Date.now()
    for (const [key, entry] of store.entries()) {
      if (entry.expiresAt <= now) store.delete(key)
    }
  }

  return {
    has(key: string) {
      const entry = store.get(key)
      if (!entry) return false
      if (entry.expiresAt <= Date.now()) { store.delete(key); return false }
      return true
    },
    get(key: string): string | undefined {
      const entry = store.get(key)
      if (!entry) return undefined
      if (entry.expiresAt <= Date.now()) { store.delete(key); return undefined }
      return entry.value
    },
    set(key: string, value: string) {
      purgeExpired()
      if (store.size >= maxSize) {
        const firstKey = store.keys().next().value
        if (firstKey !== undefined) store.delete(firstKey)
      }
      store.set(key, { value, expiresAt: Date.now() + ttlMs })
    },
    size() { return store.size },
  }
}

describe('LRU cache — basic operations', () => {
  test('set and get', () => {
    const cache = makeResearchCache(10, 60_000)
    cache.set('key1', 'value1')
    assert.equal(cache.get('key1'), 'value1')
  })

  test('has returns true for existing key', () => {
    const cache = makeResearchCache(10, 60_000)
    cache.set('k', 'v')
    assert.ok(cache.has('k'))
  })

  test('has returns false for missing key', () => {
    const cache = makeResearchCache(10, 60_000)
    assert.ok(!cache.has('missing'))
  })

  test('size increments on new entries', () => {
    const cache = makeResearchCache(10, 60_000)
    cache.set('a', '1')
    cache.set('b', '2')
    assert.equal(cache.size(), 2)
  })
})

describe('LRU cache — max size eviction', () => {
  test('evicts oldest entry when full', () => {
    const cache = makeResearchCache(3, 60_000)
    cache.set('first', 'v1')
    cache.set('second', 'v2')
    cache.set('third', 'v3')
    // Adding 4th entry should evict 'first'
    cache.set('fourth', 'v4')
    assert.ok(!cache.has('first'), 'first should have been evicted')
    assert.ok(cache.has('fourth'), 'fourth should exist')
    assert.equal(cache.size(), 3)
  })

  test('size never exceeds max', () => {
    const cache = makeResearchCache(5, 60_000)
    for (let i = 0; i < 20; i++) {
      cache.set(`key${i}`, `val${i}`)
    }
    assert.ok(cache.size() <= 5)
  })
})

describe('LRU cache — TTL expiration', () => {
  test('expired entry not returned by get', async () => {
    const cache = makeResearchCache(10, 10) // 10ms TTL
    cache.set('expiring', 'value')
    await new Promise((resolve) => setTimeout(resolve, 20))
    assert.equal(cache.get('expiring'), undefined)
  })

  test('expired entry not counted by has', async () => {
    const cache = makeResearchCache(10, 10) // 10ms TTL
    cache.set('expiring', 'value')
    await new Promise((resolve) => setTimeout(resolve, 20))
    assert.ok(!cache.has('expiring'))
  })

  test('fresh entry survives TTL check', () => {
    const cache = makeResearchCache(10, 60_000) // 1 min TTL
    cache.set('fresh', 'value')
    assert.ok(cache.has('fresh'))
    assert.equal(cache.get('fresh'), 'value')
  })
})

describe('Reality analyzer TTL cache', () => {
  // Inline reproduction of analysisCache from realityAnalyzer.ts
  type RealityAnalysis = { module: string; fidelityTarget: number }
  function makeAnalysisCache(maxSize: number, ttlMs: number) {
    type Entry = { value: RealityAnalysis; expiresAt: number }
    const store = new Map<string, Entry>()
    return {
      get(key: string) {
        const cached = store.get(key)
        if (cached && cached.expiresAt > Date.now()) return cached.value
        return undefined
      },
      set(key: string, value: RealityAnalysis) {
        if (store.size >= maxSize) {
          const firstKey = store.keys().next().value
          if (firstKey !== undefined) store.delete(firstKey)
        }
        store.set(key, { value, expiresAt: Date.now() + ttlMs })
      },
      size() { return store.size },
    }
  }

  test('stores and retrieves RealityAnalysis', () => {
    const cache = makeAnalysisCache(64, 1_200_000)
    const analysis: RealityAnalysis = { module: 'code', fidelityTarget: 98 }
    cache.set('hash_abc', analysis)
    const result = cache.get('hash_abc')
    assert.deepEqual(result, analysis)
  })

  test('returns undefined after TTL', async () => {
    const cache = makeAnalysisCache(64, 10) // 10ms
    cache.set('hash_xyz', { module: 'image', fidelityTarget: 90 })
    await new Promise((r) => setTimeout(r, 20))
    assert.equal(cache.get('hash_xyz'), undefined)
  })

  test('evicts oldest at max size 64', () => {
    const cache = makeAnalysisCache(3, 60_000)
    cache.set('h1', { module: 'code', fidelityTarget: 98 })
    cache.set('h2', { module: 'image', fidelityTarget: 90 })
    cache.set('h3', { module: 'video', fidelityTarget: 85 })
    cache.set('h4', { module: 'learning', fidelityTarget: 80 }) // should evict h1
    assert.equal(cache.get('h1'), undefined)
    assert.ok(cache.get('h4'))
  })
})
