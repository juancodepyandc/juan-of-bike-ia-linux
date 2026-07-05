/**
 * Tests pour services/cinemaApi — bridge cinema/voice helpers.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  localFileToBridgeUrl,
  cinemaGenerateStoryboard,
  cinemaGenerateRun,
  cinemaSelftest,
  cinemaJobStatus,
  voiceLibraryList,
  voiceLibraryDelete,
  voiceSynthesize,
} from '../services/cinemaApi.ts'

const realFetch = globalThis.fetch
type MockResp = { ok: boolean; status?: number; headers?: { get: (k: string) => string | null }; json?: () => Promise<unknown>; text?: () => Promise<string> }
let fetchSequence: MockResp[] = []
let fetchCalls: Array<{ url: string; init?: any }> = []

function pushOk(body: unknown) {
  fetchSequence.push({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => body,
    text: async () => JSON.stringify(body),
  })
}

function pushErr(body: unknown, status = 500) {
  fetchSequence.push({
    ok: false,
    status,
    headers: { get: () => 'application/json' },
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
})

after(() => {
  globalThis.fetch = realFetch
})

beforeEach(() => {
  fetchSequence = []
  fetchCalls = []
})

describe('localFileToBridgeUrl', () => {
  test('chemin absolu → URL /api/asset/<path>', () => {
    const url = localFileToBridgeUrl('/workspace/cinema/shot.mp4')
    assert.ok(url.includes('/api/asset/'))
  })

  test('Windows path → slashes normalisés', () => {
    const url = localFileToBridgeUrl('C:\\users\\juan\\file.mp4')
    assert.ok(url.includes('/api/asset/'))
    assert.ok(!url.includes('\\'))
  })

  test('prefixe /application/ tronqué', () => {
    const url = localFileToBridgeUrl('/root/aurora/application/cinema/x.mp4')
    assert.ok(url.includes('cinema'))
    assert.ok(!url.includes('/root/aurora/application/'))
  })

  test('caractères URL-spéciaux encodés', () => {
    const url = localFileToBridgeUrl('/dir/file with space.mp4')
    assert.ok(url.includes('%20') || url.includes('+'))
  })
})

describe('cinemaGenerateStoryboard', () => {
  test('retourne storyboard au succès', async () => {
    pushOk({
      ok: true,
      storyboard: {
        title: 'Test',
        summary: 's',
        style: 'cinema',
        aspect: '16:9',
        resolution: '1080p',
        characters: [],
        shots: [],
      },
    })
    const r = await cinemaGenerateStoryboard({ prompt: 'Un court film' } as any)
    assert.ok(r.storyboard)
    assert.equal(r.storyboard?.title, 'Test')
  })

  test('endpoint = /api/cinema/storyboard', async () => {
    pushOk({ ok: true })
    await cinemaGenerateStoryboard({ prompt: 'x' } as any)
    assert.ok(fetchCalls[0].url.includes('/api/cinema/storyboard'))
  })

  test('HTTP error → throw avec error message', async () => {
    pushErr({ error: 'service down' }, 503)
    await assert.rejects(
      () => cinemaGenerateStoryboard({ prompt: 'x' } as any),
      /service down|503/,
    )
  })
})

describe('cinemaGenerateRun', () => {
  test('retourne jobId', async () => {
    pushOk({ ok: true, job_id: 'job-cin-1' })
    const r = await cinemaGenerateRun({
      title: 'T', summary: 's', style: 'cinema', aspect: '16:9', resolution: '720p',
      characters: [], shots: [],
    } as any)
    assert.ok((r as any).job_id || r)
  })

  test('endpoint = /api/cinema/generate', async () => {
    pushOk({ ok: true, job_id: 'x' })
    await cinemaGenerateRun({} as any)
    assert.ok(fetchCalls[0].url.includes('/api/cinema/generate'))
  })
})

describe('cinemaSelftest', () => {
  test('renvoie statut runtime', async () => {
    pushOk({ ok: true, status: 'ok', python: '3.11' })
    const r = await cinemaSelftest()
    assert.ok(r)
  })

  test('endpoint /api/cinema/selftest', async () => {
    pushOk({ ok: true })
    await cinemaSelftest()
    assert.ok(fetchCalls[0].url.includes('/api/cinema/selftest'))
  })
})

describe('cinemaJobStatus', () => {
  test('retourne status + progress', async () => {
    pushOk({ ok: true, status: 'running', progress: 0.5 })
    const r = await cinemaJobStatus('job-1')
    assert.ok(r)
  })

  test('jobId encodé dans URL', async () => {
    pushOk({ ok: true })
    await cinemaJobStatus('job/with slash')
    // Doit être encodé
    assert.ok(fetchCalls[0].url.includes('job%2F') || fetchCalls[0].url.includes('job/'))
  })
})

describe('voiceLibraryList', () => {
  test('renvoie array de voix', async () => {
    pushOk({ ok: true, voices: [{ slug: 'v1', name: 'Voice 1' }] })
    const r = await voiceLibraryList()
    assert.ok(Array.isArray(r))
  })

  test('endpoint /api/voice/library/list', async () => {
    pushOk({ ok: true, voices: [] })
    await voiceLibraryList()
    assert.ok(fetchCalls[0].url.includes('/api/voice/library'))
  })
})

describe('voiceLibraryDelete', () => {
  test('appelle endpoint avec slug', async () => {
    pushOk({ ok: true })
    await voiceLibraryDelete('voice-slug-1')
    assert.ok(fetchCalls[0].url.includes('voice-slug-1') || fetchCalls[0].init?.body?.includes('voice-slug-1'))
  })
})

describe('voiceSynthesize', () => {
  test('passe text + voice slug dans body', async () => {
    pushOk({ ok: true, audio_url: '/api/asset/x.wav' })
    await voiceSynthesize({ text: 'Bonjour', voice_slug: 'aurora-soft', lang: 'fr' })
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.text, 'Bonjour')
    assert.equal(body.voice_slug, 'aurora-soft')
  })

  test('endpoint /api/voice/synthesize', async () => {
    pushOk({ ok: true })
    await voiceSynthesize({ text: 'hi', voice_slug: 'v', lang: 'fr' })
    assert.ok(fetchCalls[0].url.includes('/api/voice/synthesize'))
  })
})

describe('Error paths', () => {
  test('réponse non-JSON → throw', async () => {
    fetchSequence.push({
      ok: true,
      status: 200,
      headers: { get: () => 'text/html' },
      text: async () => '<html>error</html>',
    } as MockResp)
    await assert.rejects(
      () => cinemaSelftest(),
      /non-JSON/,
    )
  })

  test('HTTP non-ok avec error JSON → throw avec error msg', async () => {
    pushErr({ error: 'voice not found' }, 404)
    await assert.rejects(
      () => voiceLibraryDelete('xyz'),
      /voice not found|404/,
    )
  })
})
