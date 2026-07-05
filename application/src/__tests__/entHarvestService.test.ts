/**
 * Tests pour services/entHarvestService — bridge ENT harvest API + utils.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  postHarvest,
  listHarvests,
  getHarvest,
  formatHarvestAge,
} from '../services/entHarvestService.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; json?: () => Promise<unknown> }
let fetchSequence: MockResp[] = []
let fetchCalls: Array<{ url: string; init?: any }> = []

function pushOk(body: unknown) {
  fetchSequence.push({ ok: true, status: 200, json: async () => body })
}

function pushErr(body: unknown, status = 500) {
  fetchSequence.push({ ok: false, status, json: async () => body })
}

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    fetchCalls.push({ url: String(url), init })
    const next = fetchSequence.shift()
    if (!next) return Promise.reject(new Error('no mock for ' + url))
    return Promise.resolve(next as any)
  }) as any
})

after(() => {
  globalThis.fetch = realFetch
})

beforeEach(() => {
  fetchSequence = []
  fetchCalls = []
})

describe('postHarvest', () => {
  test('succès → ok=true + count', async () => {
    pushOk({ ok: true, count: 5 })
    const r = await postHarvest({
      adapter: 'pronote',
      section: 'devoirs',
      ts: Date.now(),
      url: 'https://x',
      items: [],
    } as never)
    assert.equal(r.ok, true)
    assert.equal(r.count, 5)
  })

  test('endpoint = /api/ent/harvest', async () => {
    pushOk({ ok: true })
    await postHarvest({} as never)
    assert.ok(fetchCalls[0].url.includes('/api/ent/harvest'))
  })

  test('payload forwardé en JSON dans body', async () => {
    pushOk({ ok: true })
    await postHarvest({ adapter: 'pronote', section: 'devoirs', items: [] } as never)
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.adapter, 'pronote')
  })

  test('HTTP non-ok → ok=false avec error HTTP X', async () => {
    pushErr({}, 503)
    const r = await postHarvest({} as never)
    assert.equal(r.ok, false)
    assert.ok(r.error?.includes('503'))
  })

  test('exception réseau → ok=false avec error msg', async () => {
    globalThis.fetch = (() => Promise.reject(new Error('ECONNREFUSED'))) as any
    const r = await postHarvest({} as never)
    assert.equal(r.ok, false)
    assert.ok(r.error?.includes('ECONNREFUSED'))
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })
})

describe('listHarvests', () => {
  test('succès → array', async () => {
    pushOk({ ok: true, harvests: [{ adapter: 'pronote', section: 'devoirs', ts: 123, count: 5, hostname: 'h' }] })
    const r = await listHarvests()
    assert.equal(r.length, 1)
    assert.equal(r[0].adapter, 'pronote')
  })

  test('filter adapter → query string', async () => {
    pushOk({ ok: true, harvests: [] })
    await listHarvests({ adapter: 'pronote' })
    assert.ok(fetchCalls[0].url.includes('adapter=pronote'))
  })

  test('filter section → query string', async () => {
    pushOk({ ok: true, harvests: [] })
    await listHarvests({ section: 'notes' })
    assert.ok(fetchCalls[0].url.includes('section=notes'))
  })

  test('sans filter → URL sans qs', async () => {
    pushOk({ ok: true, harvests: [] })
    await listHarvests()
    assert.ok(!fetchCalls[0].url.includes('?'))
  })

  test('HTTP non-ok → []', async () => {
    pushErr({}, 500)
    const r = await listHarvests()
    assert.deepEqual(r, [])
  })

  test('exception réseau → []', async () => {
    globalThis.fetch = (() => Promise.reject(new Error('down'))) as any
    const r = await listHarvests()
    assert.deepEqual(r, [])
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })

  test('harvests=undefined dans réponse → []', async () => {
    pushOk({ ok: true })
    const r = await listHarvests()
    assert.deepEqual(r, [])
  })
})

describe('getHarvest', () => {
  test('succès → payload', async () => {
    const payload = { adapter: 'pronote', section: 'devoirs', ts: 1, url: 'u', items: [] }
    pushOk({ ok: true, data: payload })
    const r = await getHarvest('pronote', 'devoirs')
    assert.ok(r)
    assert.equal(r?.adapter, 'pronote')
  })

  test('data=null dans réponse → null', async () => {
    pushOk({ ok: true, data: null })
    const r = await getHarvest('pronote', 'x')
    assert.equal(r, null)
  })

  test('HTTP non-ok → null', async () => {
    pushErr({}, 404)
    const r = await getHarvest('pronote', 'x')
    assert.equal(r, null)
  })

  test('exception → null', async () => {
    globalThis.fetch = (() => Promise.reject(new Error('down'))) as any
    const r = await getHarvest('pronote', 'x')
    assert.equal(r, null)
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })

  test('adapter et section encodés URL', async () => {
    pushOk({ ok: true, data: null })
    await getHarvest('with space', 'with/slash')
    assert.ok(fetchCalls[0].url.includes('with%20space'))
    assert.ok(fetchCalls[0].url.includes('with%2Fslash'))
  })
})

describe('formatHarvestAge', () => {
  test('< 1 min → "à l\'instant"', () => {
    assert.equal(formatHarvestAge(Date.now() - 30_000), 'à l\'instant')
  })

  test('< 1h → "il y a X min"', () => {
    const ts = Date.now() - 5 * 60_000
    const r = formatHarvestAge(ts)
    assert.ok(r.includes('min'))
    assert.ok(r.includes('5'))
  })

  test('< 24h → "il y a X h"', () => {
    const ts = Date.now() - 3 * 3_600_000
    const r = formatHarvestAge(ts)
    assert.ok(r.includes('h'))
    assert.ok(r.includes('3'))
  })

  test('> 24h → "il y a X j"', () => {
    const ts = Date.now() - 5 * 86_400_000
    const r = formatHarvestAge(ts)
    assert.ok(r.includes('j'))
    assert.ok(r.includes('5'))
  })

  test('exactement maintenant → "à l\'instant"', () => {
    assert.equal(formatHarvestAge(Date.now()), 'à l\'instant')
  })
})
