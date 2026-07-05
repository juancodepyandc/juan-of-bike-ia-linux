/**
 * v82m5 — Tests for the connector-pin store and the promote-connector
 * candidate selector.
 *
 * Coverage :
 *   - pinConnector adds at the top, dedup by id (LRU)
 *   - readPinnedConnectors returns the ordered list
 *   - isConnectorPinned reflects current state
 *   - clearPinnedConnectors empties the store
 *   - selectPromoteConnectorCandidate :
 *     - empty summary → null
 *     - top count < 3 → null
 *     - top count >= 3 → returns top {host, count}
 *     - multiple hosts >= 3 → returns ONLY the top (already sorted)
 *   - connectorIdForHost maps known hosts, falls back null on unknown
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkConnectorPin.test.ts
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

const {
  pinConnector,
  readPinnedConnectors,
  isConnectorPinned,
  clearPinnedConnectors,
  selectPromoteConnectorCandidate,
  connectorIdForHost,
  PROMOTE_CONNECTOR_MIN_COUNT,
} = await import('../services/coworkConnectorPin.ts')

describe('pinConnector / readPinnedConnectors (v82m5)', () => {
  beforeEach(() => storage.clear())

  test('pin a single connector → list has 1 entry at the top', () => {
    pinConnector('reddit', 'reddit.com')
    const rows = readPinnedConnectors()
    assert.equal(rows.length, 1)
    assert.equal(rows[0].id, 'reddit')
    assert.equal(rows[0].host, 'reddit.com')
    assert.equal(typeof rows[0].pinnedAt, 'number')
  })

  test('pin multiple distinct connectors → newer goes first (LRU semantics)', () => {
    pinConnector('reddit', 'reddit.com')
    pinConnector('github', 'github.com')
    pinConnector('linkedin', 'linkedin.com')
    const rows = readPinnedConnectors()
    assert.equal(rows.length, 3)
    assert.equal(rows[0].id, 'linkedin', 'most-recent first')
    assert.equal(rows[1].id, 'github')
    assert.equal(rows[2].id, 'reddit')
  })

  test('pin same connector twice → moves to top, no dup', () => {
    pinConnector('reddit', 'reddit.com')
    pinConnector('github', 'github.com')
    pinConnector('reddit', 'reddit.com')
    const rows = readPinnedConnectors()
    assert.equal(rows.length, 2, 'no duplicate')
    assert.equal(rows[0].id, 'reddit', 're-pinned moved to top')
    assert.equal(rows[1].id, 'github')
  })

  test('isConnectorPinned reflects state', () => {
    assert.equal(isConnectorPinned('reddit'), false)
    pinConnector('reddit', 'reddit.com')
    assert.equal(isConnectorPinned('reddit'), true)
    assert.equal(isConnectorPinned('github'), false)
  })

  test('clearPinnedConnectors empties the store', () => {
    pinConnector('reddit', 'reddit.com')
    pinConnector('github', 'github.com')
    clearPinnedConnectors()
    assert.equal(readPinnedConnectors().length, 0)
  })

  test('empty / whitespace id → no-op (returns current list unchanged)', () => {
    pinConnector('reddit', 'reddit.com')
    pinConnector('', 'whatever.com')
    pinConnector('   ', 'also.com')
    const rows = readPinnedConnectors()
    assert.equal(rows.length, 1, 'empty / whitespace id ignored')
    assert.equal(rows[0].id, 'reddit')
  })

  test('cap at MAX_PINS=8 — beyond, oldest evicted', () => {
    for (let i = 0; i < 12; i++) {
      pinConnector(`conn${i}`, `host${i}.com`)
    }
    const rows = readPinnedConnectors()
    assert.equal(rows.length, 8, 'capped at 8')
    // The 4 oldest (conn0..conn3) should be evicted ; conn11 is at top.
    assert.equal(rows[0].id, 'conn11')
    assert.equal(rows[7].id, 'conn4')
  })
})

describe('selectPromoteConnectorCandidate (v82m5)', () => {
  test('empty summary → null', () => {
    assert.equal(selectPromoteConnectorCandidate([]), null)
  })

  test('top count < threshold (=3) → null', () => {
    const summary = [{ host: 'reddit.com', count: 2 }, { host: 'github.com', count: 1 }]
    assert.equal(selectPromoteConnectorCandidate(summary), null)
  })

  test('top count == threshold → returns candidate', () => {
    const summary = [{ host: 'reddit.com', count: 3 }]
    const out = selectPromoteConnectorCandidate(summary)
    assert.deepEqual(out, { host: 'reddit.com', count: 3 })
  })

  test('top count > threshold → returns top only', () => {
    const summary = [
      { host: 'reddit.com', count: 5 },
      { host: 'github.com', count: 4 },
      { host: 'linkedin.com', count: 3 },
    ]
    const out = selectPromoteConnectorCandidate(summary)
    assert.deepEqual(out, { host: 'reddit.com', count: 5 }, 'top of sorted list')
  })

  test('agenda fixture : 4 reddit + 1 github → "Promouvoir reddit"', () => {
    // summariseOptInClicksByHost returns sorted by count desc.
    const summary = [
      { host: 'reddit.com', count: 4 },
      { host: 'github.com', count: 1 },
    ]
    const out = selectPromoteConnectorCandidate(summary)
    assert.equal(out!.host, 'reddit.com')
    assert.equal(out!.count, 4)
  })

  test('agenda fixture : 2 reddit (count<3) → null (no CTA)', () => {
    const summary = [{ host: 'reddit.com', count: 2 }]
    assert.equal(selectPromoteConnectorCandidate(summary), null)
  })

  test('threshold constant exposed as 3', () => {
    assert.equal(PROMOTE_CONNECTOR_MIN_COUNT, 3)
  })

  test('malformed summary entry (no count) → null', () => {
    // selectPromoteConnectorCandidate trusts the summary contract; if the
    // top entry is malformed we still return null (defensive).
    const summary = [{ host: 'reddit.com', count: NaN as unknown as number }]
    assert.equal(selectPromoteConnectorCandidate(summary), null)
  })
})

describe('connectorIdForHost (v82m5)', () => {
  test('known host maps to connector id', () => {
    assert.equal(connectorIdForHost('reddit.com'), 'reddit')
    assert.equal(connectorIdForHost('github.com'), 'github')
    assert.equal(connectorIdForHost('linkedin.com'), 'linkedin')
    assert.equal(connectorIdForHost('news.ycombinator.com'), 'hackernews')
  })

  test('strips leading "www."', () => {
    assert.equal(connectorIdForHost('www.reddit.com'), 'reddit')
    assert.equal(connectorIdForHost('www.github.com'), 'github')
  })

  test('subdomain falls through to parent', () => {
    assert.equal(connectorIdForHost('en.wikipedia.org'), 'wikipedia')
    assert.equal(connectorIdForHost('fr.wikipedia.org'), 'wikipedia')
  })

  test('unknown host → null', () => {
    assert.equal(connectorIdForHost('example.com'), null)
    assert.equal(connectorIdForHost('mywebsite.foo'), null)
  })

  test('empty / whitespace → null', () => {
    assert.equal(connectorIdForHost(''), null)
    assert.equal(connectorIdForHost('   '), null)
  })
})
