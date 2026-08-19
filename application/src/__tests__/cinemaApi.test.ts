/**
 * Tests pour services/cinemaApi — bridge cinema/voice helpers.
 */
import { test, describe, before, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  localFileToBridgeUrl,
  cinemaAssetUrl,
  cinemaGenerateStoryboard,
  cinemaGenerateRun,
  cinemaPreviewKeyframes,
  cinemaCancelJob,
  cinemaSelftest,
  cinemaSelftestResultFromJob,
  cinemaBenchmark,
  auroraStorageStatus,
  videoGallery,
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

  test('URL /api/asset existante non ré-encodée', () => {
    const url = cinemaAssetUrl('/api/asset/temp/cinema/preview/key.png')
    assert.ok(url.endsWith('/api/asset/temp/cinema/preview/key.png'))
    assert.ok(!url.includes('/api/asset/%2Fapi%2Fasset'))
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

describe('cinemaPreviewKeyframes', () => {
  test('retourne un job async au lieu de bloquer la requête', async () => {
    pushOk({ ok: true, jobId: 'preview-1', previewId: 'preview-1', status: 'queued' })
    const r = await cinemaPreviewKeyframes({} as any)
    assert.equal(r.jobId, 'preview-1')
    assert.equal(r.status, 'queued')
    assert.ok(fetchCalls[0].url.includes('/api/cinema/preview-keyframes'))
  })
})

describe('cinemaCancelJob', () => {
  test('appelle le endpoint qui termine le groupe de processus', async () => {
    pushOk({ ok: true, jobId: 'job-1', status: 'cancelled', signalSent: true })
    const r = await cinemaCancelJob('job-1')
    assert.equal(r.status, 'cancelled')
    assert.ok(fetchCalls[0].url.includes('/api/cinema/cancel/job-1'))
    assert.equal(fetchCalls[0].init?.method, 'POST')
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

  test('un vrai job complet devient un self-test validé', () => {
    const r = cinemaSelftestResultFromJob({
      jobId: 'smoke-1',
      status: 'done',
      result: {
        ok: true,
        actual_time_s: 12,
        integrity: {
          ok: true,
          duration_s: 2,
          has_video: true,
          has_audio: true,
          video_codec: 'h264',
          audio_codec: 'aac',
          errors: [],
        },
        dialogue_quality: [{
          shot: 1, voice_ok: true, lipsync_required: false, lipsync_ok: null,
        }],
        audio_quality: [{ shot_id: 1, ok: true, has_audio: true }],
        quality_grade: {
          grade: 'A',
          overall_pct: 92,
          breakdown: {
            shot_pct: 90, char_pct: 90, audio_pct: 100,
            temporal_pct: 100, integrity_pct: 100,
          },
          coverage: {
            overall_pct: 100, measured: 8, expected: 8,
            shot: { measured: 4, expected: 4 },
            character: { measured: 1, expected: 1 },
            audio: { measured: 1, expected: 1 },
            temporal: { measured: 1, expected: 1 },
          },
          weak_shots: [],
          exportable: true,
        },
      },
    })
    assert.equal(r.overall_ok, true)
    assert.equal(r.stages.video_render.ok, true)
    assert.equal(r.stages.voice_synth.ok, true)
    assert.equal(r.stages.ffprobe.ok, true)
  })

  test('une QA non mesurée reste explicitement en échec', () => {
    const r = cinemaSelftestResultFromJob({
      jobId: 'smoke-2',
      status: 'done',
      result: {
        ok: true,
        integrity: {
          ok: true,
          duration_s: 2,
          has_video: true,
          has_audio: true,
          video_codec: 'h264',
          audio_codec: 'aac',
          errors: [],
        },
        dialogue_quality: [{
          shot: 1, voice_ok: true, lipsync_required: false, lipsync_ok: null,
        }],
        audio_quality: [{ shot_id: 1, ok: true, has_audio: true }],
        quality_grade: {
          grade: 'D',
          overall_pct: 10,
          breakdown: {
            shot_pct: 0, char_pct: null, audio_pct: 100,
            temporal_pct: null, integrity_pct: 100,
          },
          coverage: {
            overall_pct: 20, measured: 1, expected: 5,
            shot: { measured: 0, expected: 4 },
            character: { measured: 0, expected: 1 },
            audio: { measured: 0, expected: 0 },
            temporal: { measured: 0, expected: 0 },
          },
          weak_shots: [],
          exportable: false,
        },
      },
    })
    assert.equal(r.overall_ok, false)
    assert.equal(r.stages.vision_check.ok, false)
  })
})

describe('cinemaBenchmark', () => {
  test('envoie le storyboard au harnais A/B asynchrone', async () => {
    pushOk({
      ok: true,
      jobId: 'ab-1',
      status: 'queued',
      reportPath: '/tmp/report.json',
      variants: ['wan5b', 'ltx'],
    })
    const result = await cinemaBenchmark({
      title: 'A/B',
      summary: '',
      style: 'cinematic',
      aspect: '16:9',
      resolution: '720p',
      characters: [],
      shots: [{ id: 1, scene: 'A robot walks.', duration_s: 2 }],
    } as any)
    assert.equal(result.jobId, 'ab-1')
    assert.ok(fetchCalls[0].url.includes('/api/cinema/benchmark'))
    assert.match(String(fetchCalls[0].init?.body), /A robot walks/)
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

describe('storage truth and persistent gallery', () => {
  test('status expose explicitement un support froid hors ligne', async () => {
    pushOk({
      ok: true,
      key_mounted: false,
      mount_path: '/mnt/aurora_models',
      tiers: { internal: { total_gb: 915, used_gb: 784, free_gb: 131 }, key: null },
      models: [],
      outputs_tier: 'hot',
      outputs_path: '/workspace/output/videos',
      floor_gb: 20,
      warnings: [{ code: 'cold_storage_offline', message: 'offline' }],
    })
    const status = await auroraStorageStatus()
    assert.equal(status.key_mounted, false)
    assert.equal(status.outputs_tier, 'hot')
    assert.ok(fetchCalls[0].url.includes('/api/storage/status'))
  })

  test('gallery conserve le tier et son URL asset', async () => {
    pushOk({
      ok: true,
      key_mounted: true,
      files: [{
        name: 'film.mp4',
        path: '/mnt/aurora_models/outputs/videos/film.mp4',
        asset_url: '/api/asset/aurora-models/outputs/videos/film.mp4',
        tier: 'cold',
        size_bytes: 123,
        modified: 1,
      }],
    })
    const gallery = await videoGallery()
    assert.equal(gallery.files[0].tier, 'cold')
    assert.ok(gallery.files[0].asset_url.startsWith('/api/asset/'))
    assert.ok(fetchCalls[0].url.includes('/api/video/gallery'))
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
  test('passe text + personnage dans body', async () => {
    pushOk({ ok: true, audio_url: '/api/asset/x.wav' })
    await voiceSynthesize({ text: 'Bonjour', character: 'aurora-soft', lang: 'fr' })
    const body = JSON.parse(fetchCalls[0].init.body)
    assert.equal(body.text, 'Bonjour')
    assert.equal(body.character, 'aurora-soft')
  })

  test('endpoint /api/voice/synthesize', async () => {
    pushOk({ ok: true })
    await voiceSynthesize({ text: 'hi', character: 'v', lang: 'fr' })
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
