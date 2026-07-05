/**
 * Tests pour utils/buildRecovery — détection chunk errors + recovery.
 */
import { test, describe, before } from 'node:test'
import assert from 'node:assert/strict'
import {
  CHUNK_ERR_RE,
  isChunkError,
} from '../utils/buildRecovery.ts'

before(() => {
  if (typeof globalThis.sessionStorage === 'undefined') {
    const store = new Map<string, string>()
    Object.defineProperty(globalThis, 'sessionStorage', {
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
})

describe('CHUNK_ERR_RE', () => {
  test('match "dynamically imported module"', () => {
    assert.ok(CHUNK_ERR_RE.test('dynamically imported module xyz.js failed'))
  })

  test('match "importing a module script failed"', () => {
    assert.ok(CHUNK_ERR_RE.test('importing a module script failed: 404'))
  })

  test('match "loading chunk"', () => {
    assert.ok(CHUNK_ERR_RE.test('Error loading chunk 142'))
  })

  test('match "ChunkLoadError"', () => {
    assert.ok(CHUNK_ERR_RE.test('ChunkLoadError at runtime'))
  })

  test('match "failed to fetch dynamically"', () => {
    assert.ok(CHUNK_ERR_RE.test('Failed to fetch dynamically imported module'))
  })

  test('case-insensitive', () => {
    assert.ok(CHUNK_ERR_RE.test('DYNAMICALLY IMPORTED MODULE failed'))
  })

  test('ne matche pas erreur normale', () => {
    assert.ok(!CHUNK_ERR_RE.test('TypeError: Cannot read property x'))
  })

  test('ne matche pas chaîne vide', () => {
    assert.ok(!CHUNK_ERR_RE.test(''))
  })
})

describe('isChunkError', () => {
  test('string avec pattern → true', () => {
    assert.equal(isChunkError('dynamically imported module failed'), true)
  })

  test('Error instance → check .message', () => {
    const err = new Error('Loading chunk 5 failed')
    assert.equal(isChunkError(err), true)
  })

  test('object avec message → check .message', () => {
    assert.equal(isChunkError({ message: 'chunkloaderror' }), true)
  })

  test('null → false', () => {
    assert.equal(isChunkError(null), false)
  })

  test('undefined → false', () => {
    assert.equal(isChunkError(undefined), false)
  })

  test('Error sans pattern → false', () => {
    assert.equal(isChunkError(new Error('TypeError x')), false)
  })

  test('object sans message → utilise String(obj)', () => {
    const fake = { toString: () => 'failed to fetch dynamically' }
    assert.equal(isChunkError(fake), true)
  })

  test('number → String(n) → false', () => {
    assert.equal(isChunkError(42), false)
  })

  test('object avec message non-string → toString', () => {
    assert.equal(isChunkError({ message: 123 }), false)
  })
})
