/**
 * Tests batchés : utils/randomChatStarters + randomCreativePrompts + theme + comfyui.
 */
import { test, describe, before } from 'node:test'
import assert from 'node:assert/strict'
import {
  RANDOM_CHAT_STARTERS,
  pickRandomStarter,
} from '../utils/randomChatStarters.ts'
import {
  RANDOM_IMAGE_PROMPTS,
  RANDOM_VIDEO_PROMPTS,
  RANDOM_VIDEO_STYLES,
  RANDOM_DRAW_PROMPTS,
  RANDOM_CODE_IDEAS,
  RANDOM_3D_PROMPTS,
  pickRandom,
} from '../utils/randomCreativePrompts.ts'
import {
  readTheme,
  applyTheme,
  installTheme,
} from '../utils/theme.ts'
import {
  extractComfyPromptId,
  extractComfyHistoryFailure,
  extractComfyImageOutput,
} from '../utils/comfyui.ts'

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
  // Polyfill document pour theme.applyTheme
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

describe('RANDOM_CHAT_STARTERS', () => {
  test('contient au moins 10 starters', () => {
    assert.ok(RANDOM_CHAT_STARTERS.length >= 10)
  })

  test('chaque starter est non vide', () => {
    for (const s of RANDOM_CHAT_STARTERS) {
      assert.ok(s.length > 10)
    }
  })

  test('pickRandomStarter renvoie un élément du pool', () => {
    for (let i = 0; i < 10; i++) {
      const s = pickRandomStarter()
      assert.ok(RANDOM_CHAT_STARTERS.includes(s))
    }
  })
})

describe('RANDOM_CREATIVE_PROMPTS — pools', () => {
  test('RANDOM_IMAGE_PROMPTS ≥ 15', () => {
    assert.ok(RANDOM_IMAGE_PROMPTS.length >= 15)
  })

  test('RANDOM_VIDEO_PROMPTS ≥ 10', () => {
    assert.ok(RANDOM_VIDEO_PROMPTS.length >= 10)
  })

  test('RANDOM_VIDEO_STYLES présents', () => {
    assert.ok(RANDOM_VIDEO_STYLES.includes('cinematic'))
    assert.ok(RANDOM_VIDEO_STYLES.includes('anime'))
  })

  test('RANDOM_DRAW_PROMPTS contient sumi-e references', () => {
    assert.ok(RANDOM_DRAW_PROMPTS.length >= 10)
    assert.ok(RANDOM_DRAW_PROMPTS.some((p) => /samurai|koi|monk|calligraphy/i.test(p)))
  })

  test('RANDOM_CODE_IDEAS ≥ 10', () => {
    assert.ok(RANDOM_CODE_IDEAS.length >= 10)
  })

  test('RANDOM_3D_PROMPTS contient low-poly', () => {
    assert.ok(RANDOM_3D_PROMPTS.some((p) => /low.?poly/i.test(p)))
  })

  test('aucune duplication dans IMAGE_PROMPTS', () => {
    assert.equal(new Set(RANDOM_IMAGE_PROMPTS).size, RANDOM_IMAGE_PROMPTS.length)
  })
})

describe('pickRandom', () => {
  test('pool vide → throw', () => {
    assert.throws(() => pickRandom([]), /empty/)
  })

  test('pool 1 élément → renvoie cet élément', () => {
    assert.equal(pickRandom(['unique']), 'unique')
  })

  test('avoid → essaie d éviter (best-effort)', () => {
    const pool = ['a', 'b', 'c', 'd', 'e']
    const counts: Record<string, number> = { a: 0, b: 0, c: 0, d: 0, e: 0 }
    for (let i = 0; i < 100; i++) {
      const r = pickRandom(pool, 'a')
      counts[r as string] += 1
    }
    // Sur 100 picks avec retry max 5, 'a' devrait être minoritaire
    // (probabilité d'être 5x de suite ≈ 1/3125)
    assert.ok(counts.a < counts.b + counts.c + counts.d + counts.e)
  })

  test('avoid sur pool 1 élément → renvoie l unique', () => {
    assert.equal(pickRandom(['unique'], 'unique'), 'unique')
  })

  test('sans avoid → uniforme', () => {
    const pool = ['x']
    assert.equal(pickRandom(pool), 'x')
  })
})

describe('theme', () => {
  test('readTheme défaut → "dark"', () => {
    globalThis.localStorage?.removeItem('aurora-theme')
    assert.equal(readTheme(), 'dark')
  })

  test('applyTheme + readTheme round-trip', () => {
    applyTheme('light')
    assert.equal(readTheme(), 'light')
  })

  test('applyTheme sobre', () => {
    applyTheme('sobre')
    assert.equal(readTheme(), 'sobre')
  })

  test('migration "manga" → "dark"', () => {
    globalThis.localStorage?.setItem('aurora-theme', 'manga')
    assert.equal(readTheme(), 'dark')
  })

  test('valeur localStorage invalide → "dark"', () => {
    globalThis.localStorage?.setItem('aurora-theme', 'invalid-theme')
    assert.equal(readTheme(), 'dark')
  })

  test('installTheme applique sans crash', () => {
    assert.doesNotThrow(() => installTheme())
  })

  test('applyTheme écrit data-theme sur documentElement', () => {
    applyTheme('light')
    const el = (globalThis as any).document.documentElement
    assert.equal(el.getAttribute('data-theme'), 'light')
  })
})

describe('comfyui — extractComfyPromptId', () => {
  test('prompt_id présent → renvoyé', () => {
    assert.equal(extractComfyPromptId({ prompt_id: 'abc-123' }), 'abc-123')
  })

  test('node_errors → throw avec message lisible', () => {
    assert.throws(
      () => extractComfyPromptId({
        node_errors: {
          '5': {
            class_type: 'KSampler',
            errors: [{ message: 'invalid seed' }],
          },
        },
      } as any),
      /KSampler|invalid seed/,
    )
  })

  test('error.message → throw', () => {
    assert.throws(
      () => extractComfyPromptId({ error: { message: 'queue full' } } as any),
      /queue full/,
    )
  })

  test('vide → throw default', () => {
    assert.throws(() => extractComfyPromptId({} as any), /prompt_id/)
  })
})

describe('comfyui — extractComfyHistoryFailure', () => {
  test('messages avec execution_error → propage exception_message', () => {
    const r = extractComfyHistoryFailure({
      status: {
        completed: false,
        messages: [
          ['execution_start', { prompt_id: 'p' }],
          ['execution_error', { exception_message: 'CUDA OOM', node_type: 'KSampler' }],
        ],
      },
    } as any)
    assert.ok(r)
    assert.ok(r.includes('CUDA OOM'))
  })

  test('execution_interrupted → message dédié', () => {
    const r = extractComfyHistoryFailure({
      status: { messages: [['execution_interrupted', {}]] },
    } as any)
    assert.ok(r?.toLowerCase().includes('interrompue'))
  })

  test('aucune erreur + status_str="error" → fallback', () => {
    const r = extractComfyHistoryFailure({
      status: { status_str: 'error' },
    } as any)
    assert.ok(r?.includes('erreur'))
  })

  test('completed normal → null', () => {
    const r = extractComfyHistoryFailure({
      status: { completed: true, messages: [['execution_cached', {}]] },
    } as any)
    assert.equal(r, null)
  })

  test('messages absents + pas d erreur → null', () => {
    const r = extractComfyHistoryFailure({} as any)
    assert.equal(r, null)
  })
})

describe('comfyui — extractComfyImageOutput', () => {
  test('image trouvée → renvoie filename + subfolder', () => {
    const r = extractComfyImageOutput({
      outputs: {
        '9': {
          images: [{ filename: 'aurora_00001.png', subfolder: 'aurora', type: 'output' }],
        },
      },
    })
    assert.equal(r.filename, 'aurora_00001.png')
    assert.equal(r.subfolder, 'aurora')
  })

  test('plusieurs nodes → prend la première image', () => {
    const r = extractComfyImageOutput({
      outputs: {
        '9': { images: [{ filename: 'a.png', subfolder: '' }] },
        '10': { images: [{ filename: 'b.png', subfolder: '' }] },
      },
    })
    assert.ok(['a.png', 'b.png'].includes(r.filename))
  })

  test('subfolder absent → ""', () => {
    const r = extractComfyImageOutput({
      outputs: { '9': { images: [{ filename: 'x.png' }] } },
    })
    assert.equal(r.subfolder, '')
  })

  test('aucune image → throw', () => {
    assert.throws(
      () => extractComfyImageOutput({ outputs: {} }),
      /aucune image/i,
    )
  })

  test('outputs absent → throw', () => {
    assert.throws(() => extractComfyImageOutput({} as any), /aucune image/i)
  })
})
