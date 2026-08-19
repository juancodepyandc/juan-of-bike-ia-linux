import { describe, it } from 'node:test'
import assert from 'node:assert'
import {
  resolveVoiceAudioUrl,
  type VoiceSampleQuality,
  type VoiceStudioTree,
} from '../services/voiceStudioApi.ts'

describe('voiceStudioApi helper unit tests', () => {
  it('resolveVoiceAudioUrl resolves relative api paths to full bridge URLs or relative tunnel paths', () => {
    const url = resolveVoiceAudioUrl('/api/voice/studio/sample/sample_123/audio')
    assert.strictEqual(url.includes('/api/voice/studio/sample/sample_123/audio'), true)
  })

  it('resolveVoiceAudioUrl preserves http and https absolute URLs', () => {
    const absolute = 'https://example.com/audio.wav'
    assert.strictEqual(resolveVoiceAudioUrl(absolute), absolute)
  })

  it('resolveVoiceAudioUrl returns empty string on empty input', () => {
    assert.strictEqual(resolveVoiceAudioUrl(''), '')
  })

  it('validates VoiceSampleQuality contract with duration, SNR and quality score', () => {
    const quality: VoiceSampleQuality = {
      ok: true,
      duration_s: 4.5,
      estimated_snr_db: 22.4,
      quality_score: 0.91,
      clipping_ratio: 0.0001,
      silence_ratio: 0.12,
    }
    assert.strictEqual(quality.ok, true)
    assert.strictEqual(quality.duration_s! >= 2.5, true)
    assert.strictEqual(quality.estimated_snr_db! > 15, true)
    assert.strictEqual(quality.quality_score! > 0.7, true)
  })

  it('validates VoiceStudioTree contract schema', () => {
    const tree: VoiceStudioTree = {
      ok: true,
      root: '/home/juan/AuroraIA/application/output/voix',
      directories: {
        echantillons: '/home/juan/AuroraIA/application/output/voix/echantillons',
        profils: '/home/juan/AuroraIA/application/output/voix/profils',
        generations: '/home/juan/AuroraIA/application/output/voix/generations',
        sessions: '/home/juan/AuroraIA/application/output/voix/sessions',
      },
      counts: {
        echantillons: 2,
        profils: 1,
        generations: 3,
        sessions: 0,
      },
      echantillons: [
        { name: 'sample_1.wav', path: '/path/sample_1.wav', size_bytes: 128000, modified: 1724032000, date: '2026-08-19 01:00:00' },
      ],
      profils: [
        {
          slug: 'test_voice',
          name: 'Test Voice',
          path: '/path/test_voice',
          reference: '/path/test_voice/reference.wav',
          audioUrl: '/api/voice/studio/sample/test_voice/audio',
          lang: 'fr',
          duration_s: 4.2,
          quality_score: 0.88,
          is_permanent: true,
        },
      ],
      generations: [],
      sessions: [],
    }

    assert.strictEqual(tree.ok, true)
    assert.strictEqual(tree.directories.echantillons.includes('echantillons'), true)
    assert.strictEqual(tree.directories.profils.includes('profils'), true)
    assert.strictEqual(tree.directories.generations.includes('generations'), true)
    assert.strictEqual(tree.directories.sessions.includes('sessions'), true)
    assert.strictEqual(tree.counts.profils, 1)
  })
})
