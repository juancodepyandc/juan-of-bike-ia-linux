import assert from 'node:assert/strict'
import { test } from 'node:test'
import { claimImageGenerationLock, renewImageGenerationLock, releaseImageGenerationLock } from '../services/imageGenerationSafety.ts'

function storage() {
  const data = new Map<string, string>()
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value) },
    removeItem: (key: string) => { data.delete(key) },
  }
}

test('heartbeat protects an active render beyond the initial lock lifetime', () => {
  const store = storage()
  assert.equal(claimImageGenerationLock('first', { storage: store, now: 0, token: 'first' }), 'first')
  assert.equal(renewImageGenerationLock('first', store, 14 * 60_000), true)
  assert.equal(claimImageGenerationLock('second', { storage: store, now: 16 * 60_000 }), null)
  releaseImageGenerationLock('first', store)
  assert.equal(claimImageGenerationLock('second', { storage: store, now: 16 * 60_000, token: 'second' }), 'second')
})

test('an expired owner cannot renew or release a different render lock', () => {
  const store = storage()
  claimImageGenerationLock('new', { storage: store, now: 0, token: 'new' })
  assert.equal(renewImageGenerationLock('old', store, 1000), false)
  releaseImageGenerationLock('old', store)
  assert.equal(claimImageGenerationLock('third', { storage: store, now: 1000 }), null)
})
