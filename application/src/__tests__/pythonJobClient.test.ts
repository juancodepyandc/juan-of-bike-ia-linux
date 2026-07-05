/**
 * Tests pour services/pythonJobClient — wrapper async des bridge Python jobs.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  launchPythonJob,
  fetchPythonJob,
  waitForPythonJob,
  isBridgeReachable,
} from '../services/pythonJobClient.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; json?: () => Promise<unknown>; text?: () => Promise<string>; headers?: { get: (k: string) => string | null } }
let fetchSequence: MockResp[] = []
let fetchCalls: Array<{ url: string; init?: any }> = []

function pushMockJson(body: unknown, ok = true, status = 200) {
  fetchSequence.push({
    ok,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
    headers: { get: () => 'application/json' },
  })
}

function pushMockReject(err: Error) {
  fetchSequence.push({ ok: false } as any)
  // sentinel — actual rejection happens in fetch mock
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

describe('launchPythonJob', () => {
  test('renvoie jobId au succès', async () => {
    pushMockJson({ ok: true, jobId: 'job-abc-123' })
    const id = await launchPythonJob('/scripts/run.py', ['--arg=1'])
    assert.equal(id, 'job-abc-123')
  })

  test('forwarde scriptPath + args dans body', async () => {
    pushMockJson({ ok: true, jobId: 'x' })
    await launchPythonJob('/scripts/x.py', ['a', 'b'])
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.scriptPath, '/scripts/x.py')
    assert.deepEqual(body.args, ['a', 'b'])
  })

  test('endpoint = /api/python/run-async', async () => {
    pushMockJson({ ok: true, jobId: 'x' })
    await launchPythonJob('/x.py', [])
    assert.ok(fetchCalls[0].url.includes('/api/python/run-async'))
  })

  test('HTTP non-ok → throw avec status', async () => {
    pushMockJson({}, false, 500)
    await assert.rejects(
      () => launchPythonJob('/x.py', []),
      /HTTP 500/,
    )
  })

  test('ok=false sans jobId → throw avec error message', async () => {
    pushMockJson({ ok: false, error: 'script not found' })
    await assert.rejects(
      () => launchPythonJob('/x.py', []),
      /script not found/,
    )
  })

  test('réseau down → friendly error mentionne bridge', async () => {
    globalThis.fetch = (() => Promise.reject(new Error('Failed to fetch'))) as any
    await assert.rejects(
      () => launchPythonJob('/x.py', []),
      /bridge|injoignable/i,
    )
    // restore mock
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })
})

describe('fetchPythonJob', () => {
  test('jobId tauri: → unknown immédiat (pas de fetch)', async () => {
    const r = await fetchPythonJob('tauri:script.py:abc')
    assert.equal(r.status, 'unknown')
    assert.equal(r.jobId, 'tauri:script.py:abc')
    assert.equal(fetchCalls.length, 0)
  })

  test('status done renvoyé', async () => {
    pushMockJson({ status: 'done', output: 'hello', error: '', exitCode: 0 })
    const r = await fetchPythonJob('job-123')
    assert.equal(r.status, 'done')
    assert.equal(r.output, 'hello')
    assert.equal(r.exitCode, 0)
  })

  test('status running', async () => {
    pushMockJson({ status: 'running', output: 'progress', error: '', exitCode: -1 })
    const r = await fetchPythonJob('job-x')
    assert.equal(r.status, 'running')
  })

  test('404 → status unknown', async () => {
    pushMockJson({}, false, 404)
    const r = await fetchPythonJob('job-gone')
    assert.equal(r.status, 'unknown')
    assert.equal(r.exitCode, -1)
  })

  test('exception réseau → status unknown', async () => {
    fetchSequence = []
    globalThis.fetch = (() => Promise.reject(new Error('ECONNREFUSED'))) as any
    const r = await fetchPythonJob('job-net')
    assert.equal(r.status, 'unknown')
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })

  test('exitCode non-number → -1 par défaut', async () => {
    pushMockJson({ status: 'done', output: '', error: '', exitCode: 'invalid' })
    const r = await fetchPythonJob('job-x')
    assert.equal(r.exitCode, -1)
  })
})

describe('waitForPythonJob', () => {
  test('done immédiat → renvoie status', async () => {
    pushMockJson({ events: [], cursor: 0 })  // /progress poll
    pushMockJson({ status: 'done', output: 'ok', error: '', exitCode: 0 })
    const r = await waitForPythonJob('job-1', { intervalMs: 10 })
    assert.equal(r.status, 'done')
  })

  test('running → done en 2 polls', async () => {
    pushMockJson({ events: [], cursor: 0 })
    pushMockJson({ status: 'running', output: '', error: '', exitCode: -1 })
    pushMockJson({ events: [], cursor: 0 })
    pushMockJson({ status: 'done', output: 'fini', error: '', exitCode: 0 })
    const r = await waitForPythonJob('job-2', { intervalMs: 10 })
    assert.equal(r.status, 'done')
    assert.equal(r.output, 'fini')
  })

  test('onProgress callback appelé sur events', async () => {
    const events: string[] = []
    pushMockJson({ events: ['PROGRESS:50:halfway', 'PROGRESS:100:done'], cursor: 2 })
    pushMockJson({ status: 'done', output: '', error: '', exitCode: 0 })
    await waitForPythonJob('job-3', { intervalMs: 10, onProgress: (e) => events.push(e) })
    assert.equal(events.length, 2)
    assert.ok(events[0].includes('50'))
  })

  test('unknown 4× consécutifs → throw', async () => {
    for (let i = 0; i < 4; i++) {
      pushMockJson({ events: [], cursor: 0 })
      pushMockJson({}, false, 404)  // unknown
    }
    await assert.rejects(
      () => waitForPythonJob('job-gone', { intervalMs: 10 }),
      /Bridge.*injoignable/i,
    )
  })

  test('maxMs dépassé → throw timeout', async () => {
    // Pas besoin de mocker — le timeout doit déclencher avant le 1er fetch
    await assert.rejects(
      () => waitForPythonJob('job-x', { intervalMs: 100, maxMs: 10 }),
      /timeout/i,
    )
  })

  test('cursor incrémenté entre polls', async () => {
    pushMockJson({ events: ['e1'], cursor: 5 })
    pushMockJson({ status: 'running', output: '', error: '', exitCode: -1 })
    pushMockJson({ events: [], cursor: 5 })
    pushMockJson({ status: 'done', output: '', error: '', exitCode: 0 })
    await waitForPythonJob('job-c', { intervalMs: 10, onProgress: () => {} })
    // Vérifie que le 2nd progress poll inclut since=5
    const progressCalls = fetchCalls.filter((c) => c.url.includes('/api/python/progress'))
    assert.ok(progressCalls.length >= 2)
    assert.ok(progressCalls[1].url.includes('since=5'))
  })
})

describe('isBridgeReachable', () => {
  test('200 OK → true', async () => {
    pushMockJson({ ok: true })
    const r = await isBridgeReachable()
    assert.equal(r, true)
  })

  test('500 → false', async () => {
    pushMockJson({}, false, 500)
    const r = await isBridgeReachable()
    assert.equal(r, false)
  })

  test('exception → false', async () => {
    fetchSequence = []
    globalThis.fetch = (() => Promise.reject(new Error('down'))) as any
    const r = await isBridgeReachable()
    assert.equal(r, false)
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })

  test('endpoint = /api/ping', async () => {
    pushMockJson({ ok: true })
    await isBridgeReachable()
    assert.ok(fetchCalls[0].url.includes('/api/ping'))
  })
})
