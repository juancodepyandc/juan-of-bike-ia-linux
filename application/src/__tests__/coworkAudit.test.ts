/**
 * Unit tests for the Cowork audit log.
 * Run: node --experimental-strip-types --test src/__tests__/coworkAudit.test.ts
 *
 * The audit module reads and writes localStorage. We stub a tiny
 * in-memory implementation so the module can run under Node.
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

// Stub localStorage before importing the module.
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
  appendAuditEntry,
  readAuditLog,
  clearAuditLog,
  makePromptId,
  summariseResultForAudit,
} = await import('../services/coworkAudit.ts')

describe('audit log basics', () => {
  beforeEach(() => storage.clear())

  test('starts empty', () => {
    assert.deepEqual(readAuditLog(), [])
  })

  test('append + read returns the entry', () => {
    const e = appendAuditEntry({
      action: { kind: 'reply', message: 'salut' },
      decision: 'allow',
      reason: 'message',
    })
    assert.equal(typeof e.id, 'string')
    assert.equal(typeof e.at, 'number')
    const list = readAuditLog()
    assert.equal(list.length, 1)
    assert.equal(list[0].decision, 'allow')
    assert.equal(list[0].action.kind, 'reply')
  })

  test('clearAuditLog wipes everything', () => {
    appendAuditEntry({ action: { kind: 'reply', message: 'x' }, decision: 'allow' })
    appendAuditEntry({ action: { kind: 'reply', message: 'y' }, decision: 'allow' })
    assert.equal(readAuditLog().length, 2)
    clearAuditLog()
    assert.equal(readAuditLog().length, 0)
  })
})

describe('audit log capping', () => {
  beforeEach(() => storage.clear())

  test('caps at 200 entries (FIFO)', () => {
    for (let i = 0; i < 250; i++) {
      appendAuditEntry({
        action: { kind: 'reply', message: `msg ${i}` },
        decision: 'allow',
      })
    }
    const list = readAuditLog()
    assert.equal(list.length, 200)
    // Oldest entries should have been dropped.
    const firstAction = list[0].action
    assert.equal(firstAction.kind, 'reply')
    if (firstAction.kind === 'reply') {
      // First retained should be #50 (250 - 200 = 50)
      assert.match(firstAction.message, /^msg 5\d$/)
    }
  })
})

describe('audit log payload sanitisation', () => {
  beforeEach(() => storage.clear())

  test('truncates long output', () => {
    const big = 'x'.repeat(2000)
    appendAuditEntry({
      action: { kind: 'reply', message: 'r' },
      decision: 'allow',
      result: { ok: true, output: big, durationMs: 1 },
    })
    const e = readAuditLog()[0]
    assert.ok(e.result)
    assert.ok(e.result!.output!.length < 2000)
    assert.match(e.result!.output!, /tronque/)
  })

  test('truncates long error', () => {
    const big = 'e'.repeat(2000)
    appendAuditEntry({
      action: { kind: 'shell', command: 'ls', args: [] },
      decision: 'allow',
      result: { ok: false, error: big, durationMs: 1 },
    })
    const e = readAuditLog()[0]
    assert.ok(e.result!.error!.length < 2000)
  })

  test('caps prompt at 200 chars', () => {
    const longPrompt = 'q'.repeat(500)
    const e = appendAuditEntry({
      action: { kind: 'reply', message: 'hi' },
      decision: 'allow',
      prompt: longPrompt,
    })
    assert.equal(e.prompt!.length, 200)
  })

  test('result undefined stays undefined', () => {
    const e = appendAuditEntry({
      action: { kind: 'reply', message: 'hi' },
      decision: 'allow',
    })
    assert.equal(e.result, undefined)
  })
})

describe('makePromptId', () => {
  test('generates unique ids', () => {
    const a = makePromptId()
    const b = makePromptId()
    assert.notEqual(a, b)
    assert.match(a, /^p-\d+-[a-z0-9]+$/)
  })
})

describe('summariseResultForAudit', () => {
  test('passes ok + durationMs', () => {
    const r = summariseResultForAudit({ ok: true, durationMs: 42 })
    assert.equal(r.ok, true)
    assert.equal(r.durationMs, 42)
  })
  test('truncates oversize fields', () => {
    const r = summariseResultForAudit({
      ok: true,
      output: 'a'.repeat(2000),
      error: 'b'.repeat(2000),
      durationMs: 1,
    })
    assert.ok((r.output ?? '').length < 2000)
    assert.ok((r.error ?? '').length < 2000)
  })
})
