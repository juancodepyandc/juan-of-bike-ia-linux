/**
 * Tests pour services/videoCompositionPlanner — timeline planner FFmpeg.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  planTimeline,
  defaultExportPresets,
  type VideoBrief,
} from '../services/videoCompositionPlanner.ts'

function brief(over: Partial<VideoBrief> = {}): VideoBrief {
  return {
    script: 'Bonjour à tous. Aujourd hui on parle de Python. C est un langage facile à apprendre.',
    format: '16:9',
    tone: 'tutoriel',
    platform: 'youtube-long',
    ...over,
  }
}

describe('planTimeline — structure de base', () => {
  test('totalDurationMs > 0', () => {
    const t = planTimeline(brief())
    assert.ok(t.totalDurationMs > 0)
  })

  test('contient hook + jingle + body + outro', () => {
    const t = planTimeline(brief())
    const ids = t.clips.map((c) => c.id)
    assert.ok(ids.includes('hook'))
    assert.ok(ids.includes('jingle-in'))
    assert.ok(ids.includes('cta'))
    assert.ok(t.clips.some((c) => c.id.startsWith('body-')))
  })

  test('hook dure 3000ms', () => {
    const t = planTimeline(brief())
    const hook = t.clips.find((c) => c.id === 'hook')
    assert.equal(hook?.durationMs, 3000)
  })

  test('format respecté', () => {
    const t = planTimeline(brief({ format: '9:16' }))
    assert.equal(t.format, '9:16')
  })

  test('platform youtube-short → format 9:16 par défaut platform', () => {
    const t = planTimeline(brief({ platform: 'youtube-short', format: '9:16' }))
    assert.equal(t.format, '9:16')
  })
})

describe('planTimeline — body segments', () => {
  test('body alterne talking-head et b-roll-3d', () => {
    const t = planTimeline(brief({ script: 'test '.repeat(200) }))
    const body = t.clips.filter((c) => c.id.startsWith('body-'))
    // Premier = talking-head, deuxième = b-roll-3d
    assert.equal(body[0].kind, 'talking-head')
    if (body.length > 1) assert.equal(body[1].kind, 'b-roll-3d')
  })

  test('cadence youtube-long ~ 8s par cut', () => {
    const t = planTimeline(brief({ platform: 'youtube-long', script: 'mot '.repeat(500) }))
    const body = t.clips.filter((c) => c.id.startsWith('body-'))
    const avgDur = body.reduce((s, c) => s + c.durationMs, 0) / Math.max(1, body.length)
    // Cadence cible 8000ms, on tolère ±50%
    assert.ok(avgDur >= 4000 && avgDur <= 12000, `avg=${avgDur}`)
  })

  test('platform tiktok → cadence plus rapide', () => {
    const yt = planTimeline(brief({ platform: 'youtube-long', script: 'mot '.repeat(200) }))
    const tk = planTimeline(brief({ platform: 'tiktok', script: 'mot '.repeat(200) }))
    const ytBody = yt.clips.filter((c) => c.id.startsWith('body-'))
    const tkBody = tk.clips.filter((c) => c.id.startsWith('body-'))
    // Plus de cuts sur TikTok pour la même durée
    assert.ok(tkBody.length >= ytBody.length)
  })
})

describe('planTimeline — hook & CTA templates', () => {
  test('hook custom respecté', () => {
    const t = planTimeline(brief({ hook: 'Mon hook custom !' }))
    const hook = t.clips.find((c) => c.id === 'hook')
    assert.equal(hook?.text, 'Mon hook custom !')
  })

  test('CTA custom respecté', () => {
    const t = planTimeline(brief({ cta: 'Suis-moi !' }))
    const cta = t.clips.find((c) => c.id === 'cta')
    assert.equal(cta?.text, 'Suis-moi !')
  })

  test('hook auto interpolé avec {sujet}', () => {
    const t = planTimeline(brief({ tone: 'tutoriel' }))
    const hook = t.clips.find((c) => c.id === 'hook')
    assert.ok(hook?.text)
    assert.ok(!hook!.text!.includes('{sujet}'))
  })
})

describe('planTimeline — lower-third', () => {
  test('speakerName → lower-third clip ajouté', () => {
    const t = planTimeline(brief({ speakerName: 'Juan' }))
    const lower = t.clips.find((c) => c.kind === 'lower-third')
    assert.ok(lower)
    assert.equal(lower?.text, 'Juan')
  })

  test('sans speakerName → pas de lower-third', () => {
    const t = planTimeline(brief())
    const lower = t.clips.find((c) => c.kind === 'lower-third')
    assert.equal(lower, undefined)
  })
})

describe('planTimeline — subtitles', () => {
  test('subtitles générés depuis le script', () => {
    const t = planTimeline(brief())
    assert.ok(t.subtitles.length > 0)
  })

  test('subtitles chronologiquement croissants', () => {
    const t = planTimeline(brief({ script: 'mot '.repeat(60) }))
    for (let i = 1; i < t.subtitles.length; i++) {
      assert.ok(t.subtitles[i].startMs >= t.subtitles[i - 1].startMs)
    }
  })

  test('chaque cue a startMs < endMs', () => {
    const t = planTimeline(brief())
    for (const s of t.subtitles) {
      assert.ok(s.endMs > s.startMs)
    }
  })

  test('script vide → 0 sous-titre', () => {
    const t = planTimeline(brief({ script: '' }))
    assert.equal(t.subtitles.length, 0)
  })
})

describe('planTimeline — audio tracks', () => {
  test('toujours 2 tracks : voice-over + music', () => {
    const t = planTimeline(brief())
    const vo = t.audioTracks.find((a) => a.kind === 'voice-over')
    const mu = t.audioTracks.find((a) => a.kind === 'music')
    assert.ok(vo)
    assert.ok(mu)
  })

  test('music a duckOnVoiceOver=true', () => {
    const t = planTimeline(brief())
    const mu = t.audioTracks.find((a) => a.kind === 'music')!
    assert.equal(mu.duckOnVoiceOver, true)
    assert.ok(mu.duckDb !== undefined && mu.duckDb < 0)
  })

  test('voice-over dB plus haut que music', () => {
    const t = planTimeline(brief())
    const vo = t.audioTracks.find((a) => a.kind === 'voice-over')!
    const mu = t.audioTracks.find((a) => a.kind === 'music')!
    assert.ok(vo.baseDb > mu.baseDb)
  })
})

describe('planTimeline — brollMarkers', () => {
  test('au moins quelques markers générés', () => {
    const t = planTimeline(brief({ script: 'mot '.repeat(300) }))
    assert.ok(t.brollMarkers.length >= 1)
  })

  test('chaque marker a atMs >= 0', () => {
    const t = planTimeline(brief({ script: 'mot '.repeat(300) }))
    for (const m of t.brollMarkers) {
      assert.ok(m.atMs >= 0)
      assert.ok(m.cue.length > 0)
    }
  })
})

describe('planTimeline — wordsPerMinute', () => {
  test('wpm élevé → durée VO réduite', () => {
    const slow = planTimeline(brief({ wordsPerMinute: 80 }))
    const fast = planTimeline(brief({ wordsPerMinute: 200 }))
    assert.ok(fast.totalDurationMs < slow.totalDurationMs)
  })
})

describe('defaultExportPresets', () => {
  test('toujours inclut 16:9 1080p', () => {
    const t = planTimeline(brief({ format: '16:9' }))
    const presets = defaultExportPresets(t)
    assert.ok(presets.some((p) => p.format === '16:9' && p.width === 1920))
  })

  test('timeline 9:16 → inclut 9:16 export', () => {
    const t = planTimeline(brief({ format: '9:16', platform: 'tiktok' }))
    const presets = defaultExportPresets(t)
    assert.ok(presets.some((p) => p.format === '9:16'))
  })

  test('chaque preset a codec h264 + container mp4', () => {
    const t = planTimeline(brief())
    const presets = defaultExportPresets(t)
    for (const p of presets) {
      assert.equal(p.containerExt, 'mp4')
      assert.equal(p.videoCodec, 'h264')
    }
  })

  test('chaque preset a fps + bitrate raisonnables', () => {
    const t = planTimeline(brief())
    for (const p of defaultExportPresets(t)) {
      assert.ok(p.fps >= 24 && p.fps <= 60)
      assert.ok(p.bitrateMbps > 0)
    }
  })
})
