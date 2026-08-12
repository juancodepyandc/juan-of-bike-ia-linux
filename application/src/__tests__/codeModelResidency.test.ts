import { describe, test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { ensureExclusiveCodeModel, __resetModelResidencyCacheForTest } from '../services/codeModelResidency.ts'

type FetchCall = { url: string; body?: unknown }

function mockFetch(loaded: string[]) {
  const calls: FetchCall[] = []
  const fn = async (url: string, init?: { body?: string }) => {
    calls.push({ url, body: init?.body ? JSON.parse(init.body) : undefined })
    if (url.endsWith('/api/ps')) {
      return { json: async () => ({ models: loaded.map((name) => ({ name })) }) }
    }
    return { json: async () => ({ done: true }) }
  }
  return { fn: fn as unknown as typeof fetch, calls }
}

describe('codeModelResidency', () => {
  beforeEach(() => __resetModelResidencyCacheForTest())

  test('decharge les AUTRES gros modeles code avant de charger le modele cible', async () => {
    // Scenario crash: devstral (agent) encore charge quand le codeur prend la main.
    const { fn, calls } = mockFetch(['devstral:latest', 'qwen3-vl:30b', 'nomic-embed-text:latest'])
    const orig = globalThis.fetch
    globalThis.fetch = fn
    try {
      await ensureExclusiveCodeModel('qwen3-coder:30b')
    } finally { globalThis.fetch = orig }

    const unloads = calls.filter((c) => c.url.endsWith('/api/generate'))
    const unloaded = unloads.map((u) => (u.body as { model: string }).model)

    // devstral (gros modele code) doit etre decharge (keep_alive:0).
    assert.ok(unloaded.includes('devstral:latest'))
    assert.equal((unloads[0].body as { keep_alive: number }).keep_alive, 0)

    // qwen3-vl:30b AUSSI. Ce test affirmait l inverse — « vision, legere,
    // coexiste » — et cette hypothese a ete dementie par la mesure: un 30B pese
    // autant qu un gros modele code, et le run 1041 est mort sur `fetch failed`
    // avec 0 octet de RAM libre. Un modele se juge a sa TAILLE, pas a sa
    // famille. Quand la vision est elle-meme la cible (generation avec images),
    // elle n est evidemment pas dechargee: le test suivant le couvre.
    assert.ok(unloaded.includes('qwen3-vl:30b'))

    // Les embeddings, eux, sont reellement legers et continuent de coexister.
    assert.ok(!unloaded.some((m) => /nomic/.test(m)))
  })

  test('ne decharge jamais le modele cible, meme quand c est la vision', async () => {
    const { fn, calls } = mockFetch(['qwen3-vl:30b', 'nomic-embed-text:latest'])
    const orig = globalThis.fetch
    globalThis.fetch = fn
    try {
      await ensureExclusiveCodeModel('qwen3-vl:30b')
    } finally { globalThis.fetch = orig }
    assert.equal(calls.filter((c) => c.url.endsWith('/api/generate')).length, 0)
  })

  test('ne decharge rien si seul le modele cible est charge (idempotent)', async () => {
    const { fn, calls } = mockFetch(['qwen3-coder:30b'])
    const orig = globalThis.fetch
    globalThis.fetch = fn
    try {
      await ensureExclusiveCodeModel('qwen3-coder:30b')
    } finally { globalThis.fetch = orig }
    assert.equal(calls.filter((c) => c.url.endsWith('/api/generate')).length, 0)
  })

  test('ne bloque jamais la generation si Ollama est injoignable', async () => {
    const orig = globalThis.fetch
    globalThis.fetch = (async () => { throw new Error('ECONNREFUSED') }) as unknown as typeof fetch
    try {
      await assert.doesNotReject(() => ensureExclusiveCodeModel('devstral'))
    } finally { globalThis.fetch = orig }
  })
})
