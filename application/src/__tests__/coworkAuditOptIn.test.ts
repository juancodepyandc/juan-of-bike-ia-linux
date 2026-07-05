/**
 * v82m2 — Tests for the connector_optin_clicked audit helper
 * (`appendConnectorOptInClicked`).
 *
 * Coverage :
 *   - helper writes an entry with kind='connector' so the existing audit
 *     drawer summariser renders it as "connector <id>.optin_clicked"
 *   - decision='allow' (user explicitly consented)
 *   - reason carries the OPTIN_CLICKED_REASON_MARKER for future grep/filter
 *   - params.host is preserved on the action payload
 *   - subsequent calls accumulate (no dedup so the user can see frequency)
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/coworkAuditOptIn.test.ts
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
  appendConnectorOptInClicked,
  appendAuditEntry,
  readAuditLog,
  OPTIN_CLICKED_REASON_MARKER,
  filterAuditEntriesForChip,
  summariseOptInClicksByHost,
} = await import('../services/coworkAudit.ts')

describe('appendConnectorOptInClicked (v82m2)', () => {
  beforeEach(() => storage.clear())

  test('writes a connector action entry with optin_clicked', () => {
    const e = appendConnectorOptInClicked('reddit', 'reddit.com')
    assert.equal(e.action.kind, 'connector')
    if (e.action.kind === 'connector') {
      assert.equal(e.action.connector, 'reddit')
      assert.equal(e.action.action, 'optin_clicked')
      assert.deepEqual(e.action.params, { host: 'reddit.com' })
    }
    assert.equal(e.decision, 'allow')
    assert.equal(e.reason, OPTIN_CLICKED_REASON_MARKER)
  })

  test('multiple clicks accumulate (no dedup)', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('github', 'github.com')
    const log = readAuditLog()
    assert.equal(log.length, 3, `expected 3 accumulated entries, got ${log.length}`)
    assert.equal(log.every((e) => e.reason === OPTIN_CLICKED_REASON_MARKER), true)
  })

  test('host is round-tripped via params', () => {
    const e = appendConnectorOptInClicked('hackernews', 'news.ycombinator.com')
    assert.equal(e.action.kind, 'connector')
    if (e.action.kind === 'connector') {
      assert.equal((e.action.params as { host?: string })?.host, 'news.ycombinator.com')
    }
  })

  test('entries surface in readAuditLog with id + at fields', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    const log = readAuditLog()
    assert.equal(log.length, 1)
    assert.equal(typeof log[0].id, 'string')
    assert.equal(typeof log[0].at, 'number')
    assert.ok(log[0].at <= Date.now())
  })

  test('marker is grep-able (user can pull just these from the log)', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('github', 'github.com')
    const log = readAuditLog()
    const optInOnly = log.filter((e) => e.reason === OPTIN_CLICKED_REASON_MARKER)
    assert.equal(optInOnly.length, 2)
  })
})

// ---------------------------------------------------------------------------
// v82m3 — filterAuditEntriesForChip : pure filter for the AuditDrawer
// "Tous" / "Opt-in clicks" chip toggle.
// ---------------------------------------------------------------------------

describe('filterAuditEntriesForChip (v82m3)', () => {
  beforeEach(() => storage.clear())

  test('mode "all" returns the full list (slice for fresh identity)', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendAuditEntry({
      action: { kind: 'reply', message: 'plain' },
      decision: 'allow',
    })
    const log = readAuditLog()
    const filtered = filterAuditEntriesForChip(log, 'all')
    assert.equal(filtered.length, 2, 'all → full list')
    assert.notEqual(filtered, log, 'returns a fresh slice not the same array reference')
  })

  test('mode "optin" filters to entries with OPTIN_CLICKED_REASON_MARKER', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendAuditEntry({
      action: { kind: 'reply', message: 'plain' },
      decision: 'allow',
    })
    appendConnectorOptInClicked('github', 'github.com')
    appendAuditEntry({
      action: { kind: 'shell', command: 'ls', args: [] },
      decision: 'block',
      reason: 'something_else',
    })
    const log = readAuditLog()
    const filtered = filterAuditEntriesForChip(log, 'optin')
    assert.equal(filtered.length, 2, 'only the 2 opt-in clicks must pass')
    assert.equal(filtered.every((e) => e.reason === OPTIN_CLICKED_REASON_MARKER), true)
  })

  test('mode "optin" on empty log → empty array', () => {
    const filtered = filterAuditEntriesForChip([], 'optin')
    assert.deepEqual(filtered, [])
  })

  test('mode "optin" with no opt-in entries → empty array', () => {
    appendAuditEntry({
      action: { kind: 'reply', message: 'plain' },
      decision: 'allow',
    })
    const log = readAuditLog()
    const filtered = filterAuditEntriesForChip(log, 'optin')
    assert.equal(filtered.length, 0)
  })

  test('mode "all" preserves entry order', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('github', 'github.com')
    const log = readAuditLog()
    const filtered = filterAuditEntriesForChip(log, 'all')
    assert.equal(filtered.length, 2)
    if (filtered[0].action.kind === 'connector') {
      assert.equal(filtered[0].action.connector, 'reddit')
    }
    if (filtered[1].action.kind === 'connector') {
      assert.equal(filtered[1].action.connector, 'github')
    }
  })

  test('chip filter integration : default Tous → full list, click Opt-in → narrow', () => { /* placeholder line replaced by suite below */
    return
  })
})

// ---------------------------------------------------------------------------
// v82m4 — summariseOptInClicksByHost : per-host aggregation for the audit
// drawer summary chips. Pure, sorted by count desc + host asc tie-break.
// ---------------------------------------------------------------------------

describe('summariseOptInClicksByHost (v82m4)', () => {
  beforeEach(() => storage.clear())

  test('groups multiple clicks per host with count', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('github', 'github.com')
    const log = readAuditLog()
    const summary = summariseOptInClicksByHost(log)
    assert.equal(summary.length, 2)
    assert.deepEqual(summary[0], { host: 'reddit.com', count: 3 })
    assert.deepEqual(summary[1], { host: 'github.com', count: 1 })
  })

  test('sorts by count desc (most frequent first)', () => {
    appendConnectorOptInClicked('github', 'github.com')
    appendConnectorOptInClicked('linkedin', 'linkedin.com')
    appendConnectorOptInClicked('linkedin', 'linkedin.com')
    appendConnectorOptInClicked('linkedin', 'linkedin.com')
    appendConnectorOptInClicked('linkedin', 'linkedin.com')
    appendConnectorOptInClicked('linkedin', 'linkedin.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    const log = readAuditLog()
    const summary = summariseOptInClicksByHost(log)
    assert.equal(summary[0].host, 'linkedin.com')
    assert.equal(summary[0].count, 5)
    assert.equal(summary[1].host, 'reddit.com')
    assert.equal(summary[1].count, 3)
    assert.equal(summary[2].host, 'github.com')
    assert.equal(summary[2].count, 1)
  })

  test('agenda fixture : 3 reddit + 1 github → [reddit×3, github×1] sorted desc', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendConnectorOptInClicked('github', 'github.com')
    const summary = summariseOptInClicksByHost(readAuditLog())
    assert.equal(summary.length, 2)
    assert.equal(summary[0].host, 'reddit.com')
    assert.equal(summary[0].count, 3)
    assert.equal(summary[1].host, 'github.com')
    assert.equal(summary[1].count, 1)
  })

  test('empty log → []', () => {
    assert.deepEqual(summariseOptInClicksByHost([]), [])
  })

  test('no opt-in entries → []', () => {
    appendAuditEntry({
      action: { kind: 'reply', message: 'plain' },
      decision: 'allow',
    })
    appendAuditEntry({
      action: { kind: 'shell', command: 'ls', args: [] },
      decision: 'block',
    })
    assert.deepEqual(summariseOptInClicksByHost(readAuditLog()), [])
  })

  test('mixed log : ignores non-optin entries', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendAuditEntry({
      action: { kind: 'reply', message: 'plain' },
      decision: 'allow',
    })
    appendConnectorOptInClicked('github', 'github.com')
    const summary = summariseOptInClicksByHost(readAuditLog())
    assert.equal(summary.length, 2)
    assert.deepEqual(
      [summary[0].host, summary[1].host].sort(),
      ['github.com', 'reddit.com'],
    )
  })

  test('skips opt-in entry with malformed params (no host string)', () => {
    appendConnectorOptInClicked('reddit', 'reddit.com')
    // Manually craft a malformed opt-in entry (host missing)
    appendAuditEntry({
      action: { kind: 'connector', connector: 'broken', action: 'optin_clicked', params: {} },
      decision: 'allow',
      reason: OPTIN_CLICKED_REASON_MARKER,
    })
    const summary = summariseOptInClicksByHost(readAuditLog())
    assert.equal(summary.length, 1)
    assert.equal(summary[0].host, 'reddit.com')
  })

  test('tie on count → host alphabetical asc', () => {
    appendConnectorOptInClicked('zeta', 'zeta.com')
    appendConnectorOptInClicked('alpha', 'alpha.com')
    appendConnectorOptInClicked('mid', 'mid.com')
    const summary = summariseOptInClicksByHost(readAuditLog())
    assert.equal(summary.length, 3)
    assert.equal(summary[0].host, 'alpha.com')
    assert.equal(summary[1].host, 'mid.com')
    assert.equal(summary[2].host, 'zeta.com')
  })
})

// keep the old anchor below as the closing brace of describe was moved
describe('chip filter integration v82m3 anchor', () => {
  beforeEach(() => storage.clear())
  test('default Tous → full list, click Opt-in → narrow', () => {
    // Simulate : 1 opt-in + 2 random entries.
    appendConnectorOptInClicked('reddit', 'reddit.com')
    appendAuditEntry({
      action: { kind: 'reply', message: 'a' },
      decision: 'allow',
    })
    appendAuditEntry({
      action: { kind: 'reply', message: 'b' },
      decision: 'allow',
    })
    const log = readAuditLog()
    // Default mode 'all' → full list
    const allView = filterAuditEntriesForChip(log, 'all')
    assert.equal(allView.length, 3)
    // Click chip → mode 'optin' → only the opt-in entry
    const optInView = filterAuditEntriesForChip(log, 'optin')
    assert.equal(optInView.length, 1)
    assert.equal(optInView[0].reason, OPTIN_CLICKED_REASON_MARKER)
  })
})
