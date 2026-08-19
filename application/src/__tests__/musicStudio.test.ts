import { after, before, beforeEach, describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createMusic,
  importMusicVoice,
  musicStatus,
  readMusicJob,
  resolveMusicAsset,
} from '../services/musicStudio.ts'

const realFetch = globalThis.fetch
let calls: Array<{ url: string; init?: RequestInit }> = []
let responses: Array<{ ok: boolean; status: number; json: () => Promise<unknown> }> = []

function ok(body: unknown) {
  responses.push({ ok: true, status: 200, json: async () => body })
}

before(() => {
  globalThis.fetch = ((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init })
    const response = responses.shift()
    if (!response) return Promise.reject(new Error(`missing mock for ${url}`))
    return Promise.resolve(response as Response)
  }) as typeof fetch
})

after(() => { globalThis.fetch = realFetch })

beforeEach(() => {
  calls = []
  responses = []
})

describe('music studio API contract', () => {
  test('lit l état réel du moteur', async () => {
    ok({ ok: true, ready: true, models: [{ name: 'acestep-v15-xl-sft', is_default: true }] })
    const result = await musicStatus()
    assert.equal(result.ready, true)
    assert.ok(calls[0].url.includes('/api/music/status'))
  })

  test('soumet une composition complète sans état fictif', async () => {
    ok({ ok: true, id: 'music-1', status: 'queued', queue_position: 2 })
    const result = await createMusic({
      title: 'Nuit',
      prompt: 'cinematic piano',
      lyrics: '',
      mode: 'instrumental',
      duration: 45,
      bpm: 110,
      key: 'Am',
      timeSignature: '4',
      language: 'fr',
      quality: 'studio',
    })
    assert.equal(result.status, 'queued')
    assert.ok(calls[0].url.includes('/api/music/jobs'))
    assert.equal(calls[0].init?.method, 'POST')
    assert.match(String(calls[0].init?.body), /cinematic piano/)
  })

  test('suit une tâche et garde son URL de sortie', async () => {
    ok({ ok: true, id: 'music-1', status: 'completed', audio_url: '/api/music/exports/nuit.mp3' })
    const result = await readMusicJob('music-1')
    assert.equal(result.status, 'completed')
    assert.equal(result.audio_url, '/api/music/exports/nuit.mp3')
    assert.ok(calls[0].url.includes('/api/music/jobs/music-1'))
  })

  test('envoie l échantillon sous forme multipart sans content-type forcé', async () => {
    ok({ ok: true, jobId: 'voice-1', slug: 'ma_voix' })
    const file = new File(['wave'], 'voice.wav', { type: 'audio/wav' })
    const result = await importMusicVoice({ file, name: 'Ma voix', language: 'fr', consent: true })
    assert.equal(result.slug, 'ma_voix')
    assert.ok(calls[0].init?.body instanceof FormData)
    assert.equal((calls[0].init?.headers as Record<string, string> | undefined)?.['Content-Type'], undefined)
  })

  test('résout les exports via le bridge courant', () => {
    assert.match(resolveMusicAsset('/api/music/exports/nuit.mp3'), /\/api\/music\/exports\/nuit\.mp3$/)
  })
})
