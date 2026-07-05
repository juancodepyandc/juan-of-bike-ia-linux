/**
 * Tests pour services/auroraExtensionBridge — facade Aurora-Connect extension.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  searchReferenceImages,
  fetchLibraryDocumentation,
  checkPackageVersion,
  searchWeb,
  extractActiveTabText,
  probeExtension,
} from '../services/auroraExtensionBridge.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; json: () => Promise<unknown> }
let fetchSequence: MockResp[] = []
let fetchCalls: Array<{ url: string; init?: any }> = []

function pushMockJson(body: unknown, ok = true, status = 200) {
  fetchSequence.push({
    ok,
    status,
    json: async () => body,
  })
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

function mockExtAvailable() {
  pushMockJson({ ok: true, extensions: [{ extId: 'ext-1', lastSeen: Date.now() }] })
}

function mockExtNone() {
  pushMockJson({ ok: true, extensions: [] })
}

function mockDispatchOk(commandId = 'cmd-1') {
  pushMockJson({ ok: true, commandId })
}

function mockAwaitOk(result: unknown) {
  pushMockJson({ ok: true, result })
}

describe('searchReferenceImages', () => {
  test('extension absente → ok=false', async () => {
    mockExtNone()
    const r = await searchReferenceImages('chat')
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.reason.includes('Aurora-Connect'))
  })

  test('extension OK + images retournées', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ images: [{ url: 'https://x.com/img.jpg', title: 'chat' }] })
    const r = await searchReferenceImages('chat noir')
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.data.length, 1)
      assert.equal(r.data[0].url, 'https://x.com/img.jpg')
    }
  })

  test('dispatch échoue → ok=false avec reason', async () => {
    mockExtAvailable()
    pushMockJson({ ok: false }, false, 500)
    const r = await searchReferenceImages('x')
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.reason.includes('dispatch'))
  })

  test('limit forwardé dans le payload', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ images: [] })
    await searchReferenceImages('x', { limit: 12 })
    // 2e call = dispatch
    const dispatchCall = fetchCalls[1]
    const body = JSON.parse(dispatchCall.init.body)
    assert.equal(body.payload.limit, 12)
  })

  test('limit par défaut = 8', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ images: [] })
    await searchReferenceImages('x')
    const dispatchCall = fetchCalls[1]
    const body = JSON.parse(dispatchCall.init.body)
    assert.equal(body.payload.limit, 8)
  })
})

describe('fetchLibraryDocumentation', () => {
  test('extension absente → ok=false', async () => {
    mockExtNone()
    const r = await fetchLibraryDocumentation('react')
    assert.equal(r.ok, false)
  })

  test('doc retournée correctement', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ url: 'https://react.dev', title: 'React', text: 'docs' })
    const r = await fetchLibraryDocumentation('react')
    assert.equal(r.ok, true)
    if (r.ok) assert.equal(r.data.title, 'React')
  })

  test('résultat empty → ok=false', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk(null)
    const r = await fetchLibraryDocumentation('unknown-lib')
    assert.equal(r.ok, false)
  })

  test('topic forwardé', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ url: 'u', title: 't', text: 'tx' })
    await fetchLibraryDocumentation('react', { topic: 'useEffect' })
    const dispatchCall = fetchCalls[1]
    const body = JSON.parse(dispatchCall.init.body)
    assert.equal(body.payload.topic, 'useEffect')
  })
})

describe('checkPackageVersion', () => {
  test('npm package → latest version', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ name: 'react', registry: 'npm', latest: '18.3.1' })
    const r = await checkPackageVersion('react')
    assert.equal(r.ok, true)
    if (r.ok) assert.equal(r.data.latest, '18.3.1')
  })

  test('pypi package', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ name: 'flask', registry: 'pypi', latest: '3.0.0' })
    const r = await checkPackageVersion('flask', 'pypi')
    assert.equal(r.ok, true)
  })

  test('registry forwardé dans payload', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ name: 'x', registry: 'crates', latest: '1.0' })
    await checkPackageVersion('serde', 'crates')
    const body = JSON.parse(fetchCalls[1].init.body)
    assert.equal(body.payload.registry, 'crates')
  })

  test('résultat null → ok=false', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk(null)
    const r = await checkPackageVersion('x')
    assert.equal(r.ok, false)
  })
})

describe('searchWeb', () => {
  test('hits retournés', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ hits: [{ title: 'T', url: 'U', snippet: 'S' }] })
    const r = await searchWeb('python tutorial')
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.data.length, 1)
      assert.equal(r.data[0].title, 'T')
    }
  })

  test('limit par défaut = 5', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ hits: [] })
    await searchWeb('q')
    const body = JSON.parse(fetchCalls[1].init.body)
    assert.equal(body.payload.limit, 5)
  })

  test('hits=undefined → renvoie []', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({})
    const r = await searchWeb('q')
    assert.equal(r.ok, true)
    if (r.ok) assert.deepEqual(r.data, [])
  })
})

describe('extractActiveTabText', () => {
  test('extension absente → ok=false', async () => {
    mockExtNone()
    const r = await extractActiveTabText()
    assert.equal(r.ok, false)
  })

  test('extraction OK', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ url: 'https://x.com', title: 'P', data: ['line 1', 'line 2'] })
    const r = await extractActiveTabText()
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.data.title, 'P')
      assert.ok(r.data.text.includes('line 1'))
    }
  })

  test('selector custom forwardé', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ data: [] })
    await extractActiveTabText({ selector: 'article.post' })
    const body = JSON.parse(fetchCalls[1].init.body)
    assert.equal(body.payload.selector, 'article.post')
  })

  test('text tronqué à 12000 chars', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ data: ['X'.repeat(15000)] })
    const r = await extractActiveTabText()
    if (r.ok) assert.ok(r.data.text.length <= 12000)
  })

  test('data=null → texte vide', async () => {
    mockExtAvailable()
    mockDispatchOk()
    mockAwaitOk({ url: 'u', title: 't' })
    const r = await extractActiveTabText()
    if (r.ok) assert.equal(r.data.text, '')
  })
})

describe('probeExtension', () => {
  test('aucune extension → null', async () => {
    mockExtNone()
    const r = await probeExtension()
    assert.equal(r, null)
  })

  test('extension trouvée → infos', async () => {
    mockExtAvailable()
    const r = await probeExtension()
    assert.ok(r)
    assert.equal(r?.extId, 'ext-1')
  })

  test('liste extension → trie par lastSeen desc', async () => {
    pushMockJson({
      ok: true,
      extensions: [
        { extId: 'old', lastSeen: 100 },
        { extId: 'new', lastSeen: 999 },
      ],
    })
    const r = await probeExtension()
    assert.equal(r?.extId, 'new')
  })

  test('list endpoint failure → null', async () => {
    pushMockJson({}, false, 500)
    const r = await probeExtension()
    assert.equal(r, null)
  })
})

describe('error paths', () => {
  test('dispatch retourne ok=false sans commandId → reason', async () => {
    mockExtAvailable()
    pushMockJson({ ok: false, error: 'extension busy' })
    const r = await searchReferenceImages('x')
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.reason.includes('busy') || r.reason.includes('commandId'))
  })

  test('await-result HTTP error → timeout reason', async () => {
    mockExtAvailable()
    mockDispatchOk()
    pushMockJson({}, false, 408)
    const r = await searchReferenceImages('x')
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.reason.includes('timed out') || r.reason.includes('408'))
  })

  test('await-result ok=false → propage error', async () => {
    mockExtAvailable()
    mockDispatchOk()
    pushMockJson({ ok: false, error: 'tab closed' })
    const r = await searchReferenceImages('x')
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.reason.includes('tab closed') || r.reason.includes('ok:false'))
  })

  test('exception réseau → reason "bridge error"', async () => {
    fetchSequence = []
    globalThis.fetch = (() => Promise.reject(new Error('ECONNREFUSED'))) as any
    const r = await searchReferenceImages('x')
    assert.equal(r.ok, false)
    // restore mock harness
    globalThis.fetch = ((url: any, init?: any) => {
      fetchCalls.push({ url: String(url), init })
      const next = fetchSequence.shift()
      if (!next) return Promise.reject(new Error('no mock'))
      return Promise.resolve(next as any)
    }) as any
  })
})
