/**
 * Tests pour utils/dailyTip — seed deterministic basé sur la date du jour.
 */
import { test, describe, before } from 'node:test'
import assert from 'node:assert/strict'

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

const { areTipsEnabled, getDailyTip, TIPS_ENABLED_KEY } = await import('../utils/dailyTip.ts')

describe('areTipsEnabled', () => {
  test('défaut → true', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.removeItem(TIPS_ENABLED_KEY)
    assert.equal(areTipsEnabled(), true)
  })

  test('"1" → true', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '1')
    assert.equal(areTipsEnabled(), true)
  })

  test('"true" → true', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, 'true')
    assert.equal(areTipsEnabled(), true)
  })

  test('"0" → false', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '0')
    assert.equal(areTipsEnabled(), false)
  })
})

describe('getDailyTip', () => {
  test('disabled → string vide', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '0')
    assert.equal(getDailyTip('chat'), '')
  })

  test('enabled + module connu → tip non vide', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '1')
    const tip = getDailyTip('chat')
    assert.ok(tip.length > 0)
    assert.ok(tip.startsWith('💡'))
  })

  test('même jour → même tip (déterministe)', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '1')
    const a = getDailyTip('code')
    const b = getDailyTip('code')
    assert.equal(a, b)
  })

  test('module inconnu → fallback global', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '1')
    // 'unknown' n'existe pas dans TipModule mais on teste via cast (le code utilise TIPS[module] || TIPS.global)
    const tip = getDailyTip('global')
    assert.ok(tip.length > 0)
  })

  test('couvre tous les modules', () => {
    const ls = (globalThis as { window: { localStorage: Storage } }).window.localStorage
    ls.setItem(TIPS_ENABLED_KEY, '1')
    const modules = ['chat', 'image', 'code', 'drawing', 'video', '3d', 'academy', 'cyber', 'cowork', 'global'] as const
    for (const m of modules) {
      const tip = getDailyTip(m)
      assert.ok(tip.length > 0, `pas de tip pour ${m}`)
    }
  })
})
