import { test } from 'node:test'
import assert from 'node:assert/strict'
import { addMemory, createMemoryStore, prune, removeMemory, retrieve, tokenFrequencies } from '../services/conversationMemory.ts'

const NOW = new Date('2026-09-05T12:00:00Z')

test('tokens matching Object properties retain numeric frequencies', () => {
  const counts = tokenFrequencies('constructor constructor __proto__ prototype')
  assert.equal(counts.constructor, 2)
  assert.equal(counts.__proto__, 1)
  assert.equal(counts.prototype, 1)
  assert.equal(Object.getPrototypeOf(counts), Object.prototype)
})

test('reserved tokens remain searchable across persistence, pruning and deletion', () => {
  let store = addMemory(createMemoryStore(), { kind: 'fact', text: 'constructor __proto__' }, NOW)
  store = addMemory(store, { kind: 'fact', text: 'constructor TypeScript' }, NOW)
  store = JSON.parse(JSON.stringify(store))
  store = prune(store, { now: NOW })
  assert.equal(store.documentFrequency.constructor, 2)
  assert.equal(store.documentFrequency.__proto__, 1)
  const results = retrieve(store, '__proto__', NOW)
  assert.ok(results.every((result) => Number.isFinite(result.score)))
  assert.equal(results[0].entry.text, 'constructor __proto__')
  store = removeMemory(store, results[0].entry.id)
  assert.equal(store.documentFrequency.constructor, 1)
  assert.equal(Object.hasOwn(store.documentFrequency, '__proto__'), false)
  assert.ok(retrieve(store, '__proto__', NOW).every((result) => Number.isFinite(result.score)))
})

test('quota eviction preserves a low-importance pinned memory', () => {
  let store = addMemory(createMemoryStore(), { kind: 'pinned', text: 'Preference', importance: 0 }, NOW)
  store = addMemory(store, { kind: 'fact', text: 'Ordinary fact', importance: 1 }, NOW)
  assert.deepEqual(prune(store, { now: NOW, maxEntries: 1 }).entries.map((entry) => entry.kind), ['pinned'])
  assert.equal(store.entries.length, 2)
})

test('pinned memories survive even when they exceed the quota', () => {
  let store = addMemory(createMemoryStore(), { kind: 'pinned', text: 'First' }, NOW)
  store = addMemory(store, { kind: 'pinned', text: 'Second' }, NOW)
  assert.equal(prune(store, { now: NOW, maxEntries: 1 }).entries.length, 2)
})
