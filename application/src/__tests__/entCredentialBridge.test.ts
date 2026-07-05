/**
 * Tests pour services/entCredentialBridge — orchestrateur ENT auto-login +
 * scrape + harvest persist.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectAdapterFromUrl,
  requestAutoLogin,
  scrapeAndAnalyze,
  verifyAuth,
} from '../services/entCredentialBridge.ts'
import { ENT_ADAPTERS } from '../services/entAdapters.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; json?: () => Promise<unknown>; text?: () => Promise<string> }
let fetchSequence: MockResp[] = []
let fetchCalls: Array<{ url: string; init?: any }> = []

function pushOk(body: unknown) {
  fetchSequence.push({
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
  })
}

function pushErr(body: unknown, status = 500) {
  fetchSequence.push({
    ok: false,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  })
}

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    fetchCalls.push({ url: String(url), init })
    const next = fetchSequence.shift()
    if (!next) return Promise.reject(new Error('no mock for ' + url))
    return Promise.resolve(next as any)
  }) as any
  // Polyfill localStorage pour le store
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
})

after(() => {
  globalThis.fetch = realFetch
})

beforeEach(() => {
  fetchSequence = []
  fetchCalls = []
})

describe('detectAdapterFromUrl', () => {
  test('URL Pronote → adapter pronote', () => {
    const r = detectAdapterFromUrl('https://0780015h.index-education.com/pronote')
    assert.ok(r)
    assert.equal(r?.id, 'pronote')
  })

  test('URL ÉcoleDirecte → adapter ecoledirecte', () => {
    const r = detectAdapterFromUrl('https://www.ecoledirecte.com/Login')
    assert.ok(r)
    assert.equal(r?.id, 'ecoledirecte')
  })

  test('URL inconnue → null', () => {
    const r = detectAdapterFromUrl('https://random-site.com')
    assert.equal(r, null)
  })

  test('URL malformée → null', () => {
    const r = detectAdapterFromUrl('pas une url valide')
    assert.equal(r, null)
  })

  test('chaîne vide → null', () => {
    assert.equal(detectAdapterFromUrl(''), null)
  })
})

describe('requestAutoLogin', () => {
  test('extension unreachable → ok=false avec reason extension_unreachable', async () => {
    pushErr({}, 500)
    const r = await requestAutoLogin('ext-1', 'pronote.fr')
    assert.equal(r.ok, false)
    assert.equal(r.reason, 'extension_unreachable')
  })

  test('dispatch ok mais sans commandId → reason extension_unreachable', async () => {
    pushOk({ ok: false, error: 'no commandId' })
    const r = await requestAutoLogin('ext-1', 'pronote.fr')
    assert.equal(r.ok, false)
    assert.equal(r.reason, 'extension_unreachable')
  })

  test('flow complet → renvoie data de l extension', async () => {
    pushOk({ ok: true, commandId: 'cmd-1' })
    pushOk({ ok: true, result: { ok: true } })
    const r = await requestAutoLogin('ext-1', 'pronote.fr')
    assert.equal(r.ok, true)
  })

  test('extension renvoie captcha → propagé', async () => {
    pushOk({ ok: true, commandId: 'cmd-1' })
    pushOk({ ok: true, result: { ok: false, reason: 'captcha', message: 'detected' } })
    const r = await requestAutoLogin('ext-1', 'pronote.fr')
    assert.equal(r.ok, false)
    assert.equal(r.reason, 'captcha')
  })

  test('payload contient siteKey', async () => {
    pushOk({ ok: true, commandId: 'cmd-1' })
    pushOk({ ok: true, result: { ok: true } })
    await requestAutoLogin('ext-1', 'mon-site-pronote')
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.payload.siteKey, 'mon-site-pronote')
  })

  test('extId forwardé dans dispatch', async () => {
    pushOk({ ok: true, commandId: 'cmd-1' })
    pushOk({ ok: true, result: { ok: true } })
    await requestAutoLogin('my-ext-abc', 'site')
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.extId, 'my-ext-abc')
  })
})

describe('verifyAuth', () => {
  const adapter = ENT_ADAPTERS[0]

  test('extension unreachable → ok=false score 0', async () => {
    pushErr({}, 500)
    const r = await verifyAuth('ext-1', adapter)
    assert.equal(r.ok, false)
    assert.equal(r.score, 0)
  })

  test('auth réussie → propage score', async () => {
    pushOk({ ok: true, commandId: 'cmd-v' })
    pushOk({ ok: true, result: { ok: true, score: 0.85 } })
    const r = await verifyAuth('ext-1', adapter)
    assert.equal(r.ok, true)
    assert.equal(r.score, 0.85)
  })

  test('auth échouée → hint inclus', async () => {
    pushOk({ ok: true, commandId: 'cmd-v' })
    pushOk({ ok: true, result: { ok: false, score: 0.2 } })
    const r = await verifyAuth('ext-1', adapter)
    assert.equal(r.ok, false)
    assert.ok(r.hint)
  })

  test('result sans score → 0 par défaut', async () => {
    pushOk({ ok: true, commandId: 'cmd-v' })
    pushOk({ ok: true, result: { ok: true } })
    const r = await verifyAuth('ext-1', adapter)
    assert.equal(r.score, 0)
  })

  test('authMarkers de l adapter forwardés', async () => {
    pushOk({ ok: true, commandId: 'cmd-v' })
    pushOk({ ok: true, result: { ok: true, score: 1 } })
    await verifyAuth('ext-1', adapter)
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.deepEqual(body.payload.authMarkers, adapter.authMarkers)
  })
})

describe('scrapeAndAnalyze', () => {
  const adapter = ENT_ADAPTERS[0]

  test('persiste les pieces jointes meme si le LLM ne sort aucun item', async () => {
    pushOk({ ok: true, commandId: 'cmd-scrape' })
    pushOk({
      ok: true,
      result: {
        ok: true,
        hostname: '0780015h.index-education.com',
        snapshot: {
          text: 'Cours de mathematiques chapitre fonctions. Document et exercice a telecharger.',
          title: 'Contenu de cours',
          url: 'https://0780015h.index-education.com/pronote/eleve.html',
          containers: [],
        },
        attachments: [
          { url: 'https://0780015h.index-education.com/file.pdf', text: 'Fiche fonctions', type: 'application/pdf' },
        ],
      },
    })
    pushOk({ ok: false, items: [], extractedCount: 0, error: 'no items extracted' })
    pushOk({ ok: true, count: 1 })

    const r = await scrapeAndAnalyze('ext-1', adapter, 'fichiers')

    assert.equal(r.ok, true)
    assert.equal(r.itemsCount, 1)
    const harvestBody = JSON.parse(fetchCalls[3].init.body)
    assert.equal(harvestBody.items[0].source, 'attachment_link')
    assert.equal(harvestBody.items[0].url, 'https://0780015h.index-education.com/file.pdf')
  })

  test('persiste un snapshot brut quand le scrape a du texte mais pas de structure', async () => {
    pushOk({ ok: true, commandId: 'cmd-scrape' })
    pushOk({
      ok: true,
      result: {
        ok: true,
        hostname: '0780015h.index-education.com',
        snapshot: {
          text: 'Devoir maison pour lundi. Lire le chapitre et preparer les exercices 4 a 8.',
          title: 'Travail a faire',
          url: 'https://0780015h.index-education.com/pronote/eleve.html',
          containers: [],
        },
        attachments: [],
      },
    })
    pushOk({ ok: false, items: [], extractedCount: 0, error: 'ollama unavailable' })
    pushOk({ ok: true, count: 1 })

    const r = await scrapeAndAnalyze('ext-1', adapter, 'devoirs')

    assert.equal(r.ok, true)
    const harvestBody = JSON.parse(fetchCalls[3].init.body)
    assert.equal(harvestBody.items[0].source, 'raw_scrape_fallback')
    assert.match(harvestBody.items[0].raw, /Devoir maison/)
  })
})

describe('Cohérence', () => {
  test('detectAdapterFromUrl + hostname → même adapter', () => {
    const adapter = ENT_ADAPTERS.find((a) => a.id === 'pronote')
    if (adapter) {
      const r = detectAdapterFromUrl('https://0780015h.index-education.com/test')
      assert.equal(r?.id, adapter.id)
    }
  })

  test('detectAdapterFromUrl gère URLs avec query string', () => {
    const r = detectAdapterFromUrl('https://www.ecoledirecte.com/Login?login=test&pwd=foo')
    assert.ok(r)
  })

  test('detectAdapterFromUrl ignore path', () => {
    const r = detectAdapterFromUrl('https://www.ecoledirecte.com/parents/eleve/cdt')
    assert.ok(r)
  })
})
