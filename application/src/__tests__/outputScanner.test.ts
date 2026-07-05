/**
 * Tests pour utils/outputScanner — scan bridge des fichiers générés.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { scanOutputFiles } from '../utils/outputScanner.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; headers?: { get: (k: string) => string | null }; json?: () => Promise<unknown>; text?: () => Promise<string> }
let fetchMock: ((url: any, init?: any) => Promise<MockResp>) | null = null

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
})

after(() => {
  globalThis.fetch = realFetch
})

beforeEach(() => {
  fetchMock = null
})

function jsonResp(body: unknown, ok = true): MockResp {
  return {
    ok,
    status: ok ? 200 : 500,
    headers: { get: () => 'application/json' },
    text: async () => JSON.stringify(body),
    json: async () => body,
  }
}

describe('scanOutputFiles — via bridge (Node = not Tauri)', () => {
  test('réponse vide → []', async () => {
    fetchMock = async () => jsonResp([])
    const r = await scanOutputFiles('/tmp', Date.now() - 60000)
    assert.deepEqual(r, [])
  })

  test('files récents → filtre par timestamp + multiplie *1000', async () => {
    const nowSec = Math.floor(Date.now() / 1000)
    fetchMock = async () => jsonResp([
      { name: 'recent.png', path: '/out/recent.png', modified: nowSec, size: 1024 },
      { name: 'old.png', path: '/out/old.png', modified: nowSec - 3600, size: 2048 },
    ])
    const cutoff = (nowSec - 100) * 1000  // 100s ago
    const r = await scanOutputFiles('/tmp', cutoff)
    assert.equal(r.length, 1)
    assert.equal(r[0].name, 'recent.png')
    // timestamp doit être en ms (×1000)
    assert.ok(r[0].modified > 1_000_000_000_000)
  })

  test('pattern filter → match par regex', async () => {
    const nowSec = Math.floor(Date.now() / 1000)
    fetchMock = async () => jsonResp([
      { name: 'image_1.png', path: '/o/image_1.png', modified: nowSec, size: 100 },
      { name: 'video_1.mp4', path: '/o/video_1.mp4', modified: nowSec, size: 200 },
      { name: 'image_2.png', path: '/o/image_2.png', modified: nowSec, size: 150 },
    ])
    const r = await scanOutputFiles('/tmp', 0, 'image_')
    assert.equal(r.length, 2)
    assert.ok(r.every((f) => f.name.startsWith('image_')))
  })

  test('triés par modified desc', async () => {
    const now = Math.floor(Date.now() / 1000)
    fetchMock = async () => jsonResp([
      { name: 'a.png', path: '/a.png', modified: now - 30, size: 100 },
      { name: 'b.png', path: '/b.png', modified: now, size: 100 },
      { name: 'c.png', path: '/c.png', modified: now - 60, size: 100 },
    ])
    const r = await scanOutputFiles('/tmp', 0)
    assert.equal(r.length, 3)
    assert.equal(r[0].name, 'b.png')
    assert.equal(r[1].name, 'a.png')
    assert.equal(r[2].name, 'c.png')
  })

  test('HTTP non-ok → []', async () => {
    fetchMock = async () => jsonResp({}, false)
    const r = await scanOutputFiles('/tmp', 0)
    assert.deepEqual(r, [])
  })

  test('exception réseau → []', async () => {
    fetchMock = async () => { throw new Error('network down') }
    const r = await scanOutputFiles('/tmp', 0)
    assert.deepEqual(r, [])
  })

  test('endpoint = /api/generated-files', async () => {
    let endpoint = ''
    fetchMock = async (url) => { endpoint = String(url); return jsonResp([]) }
    await scanOutputFiles('/tmp', 0)
    assert.ok(endpoint.includes('/api/generated-files'))
  })

  test('AbortSignal.timeout court → []', async () => {
    fetchMock = (_url, init) => new Promise((_, reject) => {
      const sig = (init as any)?.signal
      sig?.addEventListener('abort', () => reject(new Error('aborted')))
    })
    // Le timeout interne (4s) finira par abort, donc retournera []
    // Mais le test serait long. On simule juste l'abort comme erreur réseau.
    fetchMock = async () => { throw new DOMException('aborted', 'AbortError') }
    const r = await scanOutputFiles('/tmp', 0)
    assert.deepEqual(r, [])
  })

  test('files mais modified = 0 → tous filtrés (cutoff > 0)', async () => {
    fetchMock = async () => jsonResp([
      { name: 'a.png', path: '/a.png', modified: 0, size: 100 },
    ])
    const r = await scanOutputFiles('/tmp', 1000)
    assert.deepEqual(r, [])
  })

  test('shape preserved (name, path, modified, size)', async () => {
    const nowSec = Math.floor(Date.now() / 1000)
    fetchMock = async () => jsonResp([
      { name: 'x.png', path: '/x.png', modified: nowSec, size: 42 },
    ])
    const r = await scanOutputFiles('/tmp', 0)
    assert.equal(r[0].name, 'x.png')
    assert.equal(r[0].path, '/x.png')
    assert.equal(r[0].size, 42)
    assert.ok(typeof r[0].modified === 'number')
  })
})
