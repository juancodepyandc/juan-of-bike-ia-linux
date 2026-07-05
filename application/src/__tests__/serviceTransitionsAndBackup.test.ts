/**
 * Tests batchés : utils/serviceTransitions + utils/backup.
 * Passe 100 — milestone du loop.
 */
import { test, describe, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  readTransitions,
  pushTransition,
  clearTransitions,
} from '../utils/serviceTransitions.ts'
import {
  captureSnapshot,
} from '../utils/backup.ts'

before(() => {
  if (typeof globalThis.localStorage === 'undefined') {
    const store = new Map<string, string>()
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => store.set(k, String(v)),
        removeItem: (k: string) => store.delete(k),
        clear: () => store.clear(),
        get length() { return store.size },
        key: (i: number) => Array.from(store.keys())[i] ?? null,
      },
      writable: true,
      configurable: true,
    })
  }
  if (typeof globalThis.window === 'undefined') {
    Object.defineProperty(globalThis, 'window', {
      value: globalThis,
      writable: true,
      configurable: true,
    })
  }
})

beforeEach(() => {
  globalThis.localStorage?.clear?.()
})

describe('serviceTransitions — read/push/clear', () => {
  test('readTransitions vide → []', () => {
    assert.deepEqual(readTransitions(), [])
  })

  test('pushTransition ajoute en tête', () => {
    pushTransition({ service: 'bridge', kind: 'up' })
    const r = readTransitions()
    assert.equal(r.length, 1)
    assert.equal(r[0].service, 'bridge')
    assert.equal(r[0].kind, 'up')
  })

  test('pushTransition timestamp inclus', () => {
    pushTransition({ service: 'ollama', kind: 'down' })
    const r = readTransitions()
    assert.ok(typeof r[0].ts === 'number')
    assert.ok(r[0].ts > 0)
  })

  test('LRU cap à 30', () => {
    for (let i = 0; i < 40; i++) {
      pushTransition({ service: 'bridge', kind: i % 2 === 0 ? 'up' : 'down' })
    }
    const r = readTransitions()
    assert.equal(r.length, 30)
  })

  test('ordre LIFO (plus récent en tête)', () => {
    pushTransition({ service: 'bridge', kind: 'up' })
    pushTransition({ service: 'ollama', kind: 'down' })
    pushTransition({ service: 'comfy', kind: 'up' })
    const r = readTransitions()
    assert.equal(r[0].service, 'comfy')
    assert.equal(r[1].service, 'ollama')
    assert.equal(r[2].service, 'bridge')
  })

  test('clearTransitions vide la liste', () => {
    pushTransition({ service: 'bridge', kind: 'up' })
    clearTransitions()
    assert.deepEqual(readTransitions(), [])
  })

  test('service "all" avec downList', () => {
    pushTransition({ service: 'all', kind: 'down', downList: ['bridge', 'ollama'] })
    const r = readTransitions()
    assert.equal(r[0].service, 'all')
    assert.deepEqual(r[0].downList, ['bridge', 'ollama'])
  })

  test('entrées invalides filtrées', () => {
    globalThis.localStorage?.setItem('aurora-service-transitions-v1', JSON.stringify([
      { ts: Date.now(), service: 'bridge', kind: 'up' },
      { ts: 'invalid', service: 'x', kind: 'up' },
      { service: 'no-ts', kind: 'down' },
      { ts: 123, service: 'bridge', kind: 'invalid-kind' },
    ]))
    const r = readTransitions()
    assert.equal(r.length, 1)
  })

  test('localStorage corrompu → []', () => {
    globalThis.localStorage?.setItem('aurora-service-transitions-v1', 'not json')
    assert.deepEqual(readTransitions(), [])
  })

  test('JSON non-array → []', () => {
    globalThis.localStorage?.setItem('aurora-service-transitions-v1', '{"x":1}')
    assert.deepEqual(readTransitions(), [])
  })
})

describe('captureSnapshot', () => {
  test('snapshot vide → entries={}', () => {
    const snap = captureSnapshot()
    assert.equal(snap.app, 'juan-of-bike-ia')
    assert.equal(snap.version, 1)
    assert.deepEqual(snap.entries, {})
    assert.ok(snap.createdAt)
  })

  test('clés aurora-* capturées', () => {
    globalThis.localStorage?.setItem('aurora-chat', '{"x":1}')
    globalThis.localStorage?.setItem('aurora-theme', 'dark')
    const snap = captureSnapshot()
    assert.equal(snap.entries['aurora-chat'], '{"x":1}')
    assert.equal(snap.entries['aurora-theme'], 'dark')
  })

  test('clés forge-* capturées', () => {
    globalThis.localStorage?.setItem('forge-queue', 'data')
    const snap = captureSnapshot()
    assert.equal(snap.entries['forge-queue'], 'data')
  })

  test('clés non-aurora skippées', () => {
    globalThis.localStorage?.setItem('random-other-app', 'value')
    globalThis.localStorage?.setItem('aurora-chat', 'a')
    const snap = captureSnapshot()
    assert.ok(!('random-other-app' in snap.entries))
    assert.ok('aurora-chat' in snap.entries)
  })

  test('clés SAFE_KEYS captures (ft-who, ios_install_dismissed)', () => {
    globalThis.localStorage?.setItem('ft-who', 'juan')
    globalThis.localStorage?.setItem('ios_install_dismissed', '1')
    const snap = captureSnapshot()
    assert.equal(snap.entries['ft-who'], 'juan')
    assert.equal(snap.entries['ios_install_dismissed'], '1')
  })

  test('module-drafts-* capturées', () => {
    globalThis.localStorage?.setItem('module-drafts-image', 'draft1')
    globalThis.localStorage?.setItem('module-drafts-code', 'draft2')
    const snap = captureSnapshot()
    assert.equal(snap.entries['module-drafts-image'], 'draft1')
    assert.equal(snap.entries['module-drafts-code'], 'draft2')
  })

  test('ay-* (Academy progress) capturées', () => {
    globalThis.localStorage?.setItem('ay-exo-1', 'progress')
    const snap = captureSnapshot()
    assert.equal(snap.entries['ay-exo-1'], 'progress')
  })

  test('createdAt est ISO valide', () => {
    const snap = captureSnapshot()
    assert.ok(/^\d{4}-\d{2}-\d{2}T/.test(snap.createdAt))
  })
})
