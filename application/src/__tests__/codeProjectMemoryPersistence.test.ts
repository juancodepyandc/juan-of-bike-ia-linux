import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import {
  CODE_PROJECT_MEMORY_SCHEMA_VERSION,
  createCodeProjectMemorySnapshot,
  fingerprintCodeFiles,
  loadOrBuildCodeProjectMemory,
  parseCodeProjectMemorySnapshot,
  restoreCodeProjectMemorySnapshot,
} from '../services/codeProjectMemoryPersistence.ts'

class MemoryStorage {
  data = new Map<string, string>()
  getItem(key: string) { return this.data.get(key) ?? null }
  setItem(key: string, value: string) { this.data.set(key, value) }
  removeItem(key: string) { this.data.delete(key) }
}

describe('codeProjectMemoryPersistence', () => {
  test('serialise un index durable avec fingerprint et embeddings locaux', () => {
    const files: CodeFile[] = [
      { name: 'src/billing.ts', language: 'ts', content: 'export const currency = "EUR"' },
    ]
    const snapshot = createCodeProjectMemorySnapshot(files, 42)
    const parsed = parseCodeProjectMemorySnapshot(JSON.stringify(snapshot))
    const restored = restoreCodeProjectMemorySnapshot(parsed!)

    assert.equal(snapshot.schemaVersion, CODE_PROJECT_MEMORY_SCHEMA_VERSION)
    assert.equal(snapshot.fingerprint, fingerprintCodeFiles(files))
    assert.equal(snapshot.createdAt, 42)
    assert.equal(restored.byPath.get('src/billing.ts')?.embedding?.length, 64)
  })

  test('reutilise le cache persistant quand le fingerprint correspond', () => {
    const files: CodeFile[] = [
      { name: 'src/auth.ts', language: 'ts', content: 'export const login = true' },
    ]
    const storage = new MemoryStorage()
    const first = loadOrBuildCodeProjectMemory(files, storage)
    const second = loadOrBuildCodeProjectMemory(files, storage)

    assert.equal(storage.data.size, 1)
    assert.deepEqual(second.files, first.files)
  })
})
