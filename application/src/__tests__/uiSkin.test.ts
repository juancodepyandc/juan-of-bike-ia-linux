import { test, describe, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  readUiSkin,
  applyUiSkin,
  USER_PICKABLE_SKINS,
  UI_SKIN_LABELS,
} from '../utils/uiSkin.ts'

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
  if (typeof (globalThis as any).window === 'undefined') {
    Object.defineProperty(globalThis, 'window', {
      value: {
        localStorage: globalThis.localStorage,
        addEventListener: () => {},
        dispatchEvent: () => true,
        location: { reload: () => {}, href: 'http://localhost/' },
      },
      writable: true,
      configurable: true,
    })
  }
  if (typeof (globalThis as any).document === 'undefined') {
    Object.defineProperty(globalThis, 'document', {
      value: {
        documentElement: {
          attributes: {} as Record<string, string>,
          setAttribute(name: string, value: string) {
            ;(this as any).attributes[name] = value
          },
          getAttribute(name: string) {
            return (this as any).attributes[name] ?? null
          },
        },
      },
      writable: true,
      configurable: true,
    })
  }
})

beforeEach(() => {
  globalThis.localStorage?.removeItem('aurora-ui-skin')
  globalThis.localStorage?.removeItem('aurora-ui-skin-choice')
})

describe('readUiSkin', () => {
  test('localStorage vide → DEFAUT (aurora_v4)', () => {
    assert.equal(readUiSkin(), 'aurora_v4')
  })

  test('skin écrit SANS marqueur de choix (vieux bundle) → re-migré vers aurora_v4', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'aurora_v1')
    assert.equal(readUiSkin(), 'aurora_v4')
    assert.equal(globalThis.localStorage?.getItem('aurora-ui-skin'), 'aurora_v4')
  })

  test('choix explicite aurora_v3 → respecté', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'aurora_v3')
    globalThis.localStorage?.setItem('aurora-ui-skin-choice', 'aurora_v3')
    assert.equal(readUiSkin(), 'aurora_v3')
  })

  test('choix explicite aurora_v1 → respecté', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'aurora_v1')
    globalThis.localStorage?.setItem('aurora-ui-skin-choice', 'aurora_v1')
    assert.equal(readUiSkin(), 'aurora_v1')
  })

  test('skin ≠ choix (écrasé par un vieux bundle) → retour au DEFAUT', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'aurora_v1')
    globalThis.localStorage?.setItem('aurora-ui-skin-choice', 'aurora_v3')
    assert.equal(readUiSkin(), 'aurora_v4')
  })

  test('"manga" stale → migré vers DEFAUT', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'manga')
    assert.equal(readUiSkin(), 'aurora_v4')
  })

  test('valeur invalide → DEFAUT + auto-migration', () => {
    globalThis.localStorage?.setItem('aurora-ui-skin', 'invalid-skin')
    assert.equal(readUiSkin(), 'aurora_v4')
  })
})

describe('applyUiSkin', () => {
  test('aurora_v4 → data-ui-skin sur documentElement', () => {
    applyUiSkin('aurora_v4')
    const el = (globalThis as any).document.documentElement
    assert.equal(el.getAttribute('data-ui-skin'), 'aurora_v4')
  })

  test('aurora_v3 round-trip (choix explicite = intro marquée)', () => {
    applyUiSkin('aurora_v3')
    assert.equal(readUiSkin(), 'aurora_v3')
  })

  test('persiste en localStorage', () => {
    applyUiSkin('aurora_v3')
    assert.equal(globalThis.localStorage?.getItem('aurora-ui-skin'), 'aurora_v3')
  })
})

describe('USER_PICKABLE_SKINS', () => {
  test('contient aurora_v4, aurora_v1 et aurora_v3', () => {
    assert.ok(USER_PICKABLE_SKINS.includes('aurora_v4'))
    assert.ok(USER_PICKABLE_SKINS.includes('aurora_v1'))
    assert.ok(USER_PICKABLE_SKINS.includes('aurora_v3'))
  })

  test('n inclut pas manga (legacy fallback non pickable)', () => {
    assert.ok(!USER_PICKABLE_SKINS.includes('manga' as never))
  })

  test('longueur = 3', () => {
    assert.equal(USER_PICKABLE_SKINS.length, 3)
  })
})

describe('UI_SKIN_LABELS', () => {
  test('contient 4 skins (manga + v1 + v3 + v4)', () => {
    assert.equal(Object.keys(UI_SKIN_LABELS).length, 4)
  })

  test('chaque skin a title + subtitle', () => {
    for (const id of ['manga', 'aurora_v1', 'aurora_v3', 'aurora_v4'] as const) {
      assert.ok(UI_SKIN_LABELS[id].title)
      assert.ok(UI_SKIN_LABELS[id].subtitle)
    }
  })

  test('aurora_v1 mentionne Editorial', () => {
    assert.equal(UI_SKIN_LABELS.aurora_v1.title, 'Editorial')
  })

  test('aurora_v4 mentionne Aurora OS', () => {
    assert.equal(UI_SKIN_LABELS.aurora_v4.title, 'Aurora OS')
  })
})
