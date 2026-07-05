import assert from 'node:assert/strict'
import test from 'node:test'
import {
  IMAGE_GENERATION_LOCK_KEY,
  claimImageGenerationLock,
  releaseImageGenerationLock,
  type ImageGenerationLockStorage,
} from '../services/imageGenerationSafety.ts'

function memoryStorage(): ImageGenerationLockStorage & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => { data.set(key, value) },
    removeItem: (key) => { data.delete(key) },
  }
}

test('image generation lock blocks concurrent UI renders', () => {
  const storage = memoryStorage()
  const first = claimImageGenerationLock('prompt a', { storage, now: 1000, token: 'run-a' })
  const second = claimImageGenerationLock('prompt b', { storage, now: 2000, token: 'run-b' })

  assert.equal(first, 'run-a')
  assert.equal(second, null)
  assert.match(storage.getItem(IMAGE_GENERATION_LOCK_KEY) ?? '', /run-a/)
})

test('image generation lock expires stale crashed renders', () => {
  const storage = memoryStorage()
  assert.equal(claimImageGenerationLock('old prompt', { storage, now: 1000, token: 'old', ttlMs: 5000 }), 'old')

  const next = claimImageGenerationLock('new prompt', { storage, now: 7001, token: 'new', ttlMs: 5000 })

  assert.equal(next, 'new')
  assert.match(storage.getItem(IMAGE_GENERATION_LOCK_KEY) ?? '', /new/)
})

test('image generation lock release cannot delete another active render', () => {
  const storage = memoryStorage()
  assert.equal(claimImageGenerationLock('prompt a', { storage, now: 1000, token: 'run-a' }), 'run-a')

  releaseImageGenerationLock('other-run', storage)

  assert.match(storage.getItem(IMAGE_GENERATION_LOCK_KEY) ?? '', /run-a/)
  releaseImageGenerationLock('run-a', storage)
  assert.equal(storage.getItem(IMAGE_GENERATION_LOCK_KEY), null)
})
