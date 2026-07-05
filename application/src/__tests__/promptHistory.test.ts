/**
 * Tests pour utils/promptHistory — persistence localStorage par module
 * avec dédup + cap 12 + tri LRU.
 */
import { test, describe, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

// Polyfill localStorage minimal pour permettre l'exécution sous Node.
// Le module promptHistory ne fait pas autre chose que get/set/removeItem.
before(() => {
  if (typeof globalThis.window === 'undefined') {
    const store = new Map<string, string>()
    const fakeLS = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => { store.set(k, v) },
      removeItem: (k: string) => { store.delete(k) },
      clear: () => store.clear(),
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() { return store.size },
    }
    ;(globalThis as Record<string, unknown>).window = { localStorage: fakeLS }
  }
})

const { readHistory, pushHistory, clearHistory, removeHistoryEntry } = await import('../utils/promptHistory.ts')

beforeEach(() => {
  clearHistory('test')
  clearHistory('alt')
})

describe('promptHistory', () => {
  test('readHistory vide → []', () => {
    assert.deepEqual(readHistory('test'), [])
  })

  test('pushHistory ajoute en tête', () => {
    pushHistory('test', 'premier')
    const h = readHistory('test')
    assert.equal(h.length, 1)
    assert.equal(h[0].prompt, 'premier')
  })

  test('pushHistory dédoublonne sur le prompt brut', () => {
    pushHistory('test', 'duplicate')
    pushHistory('test', 'duplicate')
    const h = readHistory('test')
    assert.equal(h.length, 1)
  })

  test('pushHistory ordre LRU (récent en tête)', () => {
    pushHistory('test', 'A')
    pushHistory('test', 'B')
    pushHistory('test', 'C')
    const h = readHistory('test')
    assert.equal(h[0].prompt, 'C')
    assert.equal(h[1].prompt, 'B')
    assert.equal(h[2].prompt, 'A')
  })

  test('pushHistory + re-push existant remonte au top', () => {
    pushHistory('test', 'A')
    pushHistory('test', 'B')
    pushHistory('test', 'A') // re-push A
    const h = readHistory('test')
    assert.equal(h.length, 2)
    assert.equal(h[0].prompt, 'A')
    assert.equal(h[1].prompt, 'B')
  })

  test('pushHistory respecte le cap de 12', () => {
    for (let i = 0; i < 20; i++) pushHistory('test', `entry-${i}`)
    const h = readHistory('test')
    assert.equal(h.length, 12)
    // 12 plus récents : entry-19 à entry-8
    assert.equal(h[0].prompt, 'entry-19')
    assert.equal(h[11].prompt, 'entry-8')
  })

  test('pushHistory ignore les chaînes vides ou whitespace', () => {
    pushHistory('test', '')
    pushHistory('test', '   ')
    assert.equal(readHistory('test').length, 0)
  })

  test('pushHistory trim avant stockage', () => {
    pushHistory('test', '  hello  ')
    assert.equal(readHistory('test')[0].prompt, 'hello')
  })

  test('isolation entre modules', () => {
    pushHistory('test', 'x')
    pushHistory('alt', 'y')
    assert.equal(readHistory('test')[0].prompt, 'x')
    assert.equal(readHistory('alt')[0].prompt, 'y')
  })

  test('removeHistoryEntry retire une entrée', () => {
    pushHistory('test', 'A')
    pushHistory('test', 'B')
    pushHistory('test', 'C')
    removeHistoryEntry('test', 'B')
    const h = readHistory('test')
    assert.equal(h.length, 2)
    assert.ok(!h.some(e => e.prompt === 'B'))
  })

  test('clearHistory vide tout', () => {
    pushHistory('test', 'X')
    pushHistory('test', 'Y')
    clearHistory('test')
    assert.equal(readHistory('test').length, 0)
  })

  test('meta préservé', () => {
    pushHistory('test', 'prompt-with-meta', { style: 'cinematic', steps: 30 })
    const h = readHistory('test')
    assert.equal(h[0].meta?.style, 'cinematic')
    assert.equal(h[0].meta?.steps, 30)
  })
})
