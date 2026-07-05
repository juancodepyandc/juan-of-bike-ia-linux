/**
 * Tests export subtitles SRT / VTT / ASS + autoSplit.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  autoSplitSubtitles,
  exportAllSubtitles,
  exportAss,
  exportSrt,
  exportVtt,
} from '../services/videoSubtitleExport.ts'

const SAMPLE_CUES = [
  { startMs: 0, endMs: 2000, text: 'Premier sous-titre.' },
  { startMs: 2000, endMs: 4500, text: 'Deuxième cue, plus long.' },
  { startMs: 4500, endMs: 6000, text: 'Fin.' },
]

describe('SRT export', () => {
  test('format conforme : numéro + timecode --> + texte', () => {
    const srt = exportSrt(SAMPLE_CUES)
    assert.match(srt, /^1\n00:00:00,000 --> 00:00:02,000\nPremier sous-titre\./)
  })

  test('multiple cues séparés par blank line', () => {
    const srt = exportSrt(SAMPLE_CUES)
    const blocks = srt.split('\n\n').filter(Boolean)
    assert.equal(blocks.length, 3)
  })

  test('timecode avec heures correct', () => {
    const cue = { startMs: 3_600_500, endMs: 3_601_000, text: 'x' }
    const srt = exportSrt([cue])
    assert.match(srt, /01:00:00,500/)
  })
})

describe('VTT export', () => {
  test('header WEBVTT', () => {
    const vtt = exportVtt(SAMPLE_CUES)
    assert.match(vtt, /^WEBVTT/)
  })

  test('timecode utilise point (pas virgule)', () => {
    const vtt = exportVtt(SAMPLE_CUES)
    assert.ok(vtt.includes('00:00:00.000'))
    assert.ok(!vtt.includes('00:00:00,000'))
  })
})

describe('ASS export', () => {
  test('Script Info présent', () => {
    const ass = exportAss(SAMPLE_CUES)
    assert.match(ass, /\[Script Info\]/)
    assert.match(ass, /\[V4\+ Styles\]/)
    assert.match(ass, /\[Events\]/)
  })

  test('chaque cue produit une ligne Dialogue:', () => {
    const ass = exportAss(SAMPLE_CUES)
    const dialogues = ass.split('\n').filter((l) => l.startsWith('Dialogue:'))
    assert.equal(dialogues.length, 3)
  })

  test('timecode ASS : h:mm:ss.cs (centièmes)', () => {
    const ass = exportAss([{ startMs: 1234, endMs: 5678, text: 'x' }])
    assert.match(ass, /0:00:01\.23/)
    assert.match(ass, /0:00:05\.67/)
  })

  test('style Aurora par défaut bold + alignment 2', () => {
    const ass = exportAss(SAMPLE_CUES)
    assert.match(ass, /Style: Aurora/)
    // bold = -1, alignment = 2 (8e champ de fin)
    assert.match(ass, /Aurora,Inter,48/)
  })

  test('\\n dans texte converti en \\N', () => {
    const cue = { startMs: 0, endMs: 1000, text: 'ligne1\nligne2' }
    const ass = exportAss([cue])
    assert.match(ass, /ligne1\\Nligne2/)
  })
})

describe('autoSplitSubtitles', () => {
  test('phrase courte → 1 cue', () => {
    const cues = autoSplitSubtitles('Bonjour Aurora.', 0, 5000)
    assert.equal(cues.length, 1)
  })

  test('plusieurs phrases → plusieurs cues', () => {
    const text = 'Bonjour. Comment ça va ? Très bien merci.'
    const cues = autoSplitSubtitles(text, 0, 10000)
    assert.equal(cues.length, 3)
  })

  test('phrase > maxChars → split en plusieurs cues', () => {
    const text = 'Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore.'
    const cues = autoSplitSubtitles(text, 0, 20000, { maxChars: 30 })
    assert.ok(cues.length >= 3)
  })

  test('timestamps croissants strictement', () => {
    const cues = autoSplitSubtitles('A. B. C. D. E.', 0, 20000)
    for (let i = 1; i < cues.length; i += 1) {
      assert.ok(cues[i].startMs >= cues[i - 1].startMs)
    }
  })

  test('durée totale cible respectée pour des phrases courtes', () => {
    // 1 phrase, plus de 4s de durée min (1 word @ 2.5 wps + min 800ms)
    const cues = autoSplitSubtitles('Bonjour Aurora.', 0, 1500)
    const last = cues[cues.length - 1]
    assert.ok(last.endMs <= 1600, `last endMs ${last.endMs}`)
  })
})

describe('exportAllSubtitles', () => {
  test('retourne srt + vtt + ass', () => {
    const timeline = {
      format: '16:9' as const,
      totalDurationMs: 6000,
      clips: [],
      subtitles: SAMPLE_CUES,
      audioTracks: [],
      brollMarkers: [],
    }
    const out = exportAllSubtitles(timeline)
    assert.ok(out.srt.length > 0)
    assert.ok(out.vtt.length > 0)
    assert.ok(out.ass.length > 0)
    assert.match(out.vtt, /^WEBVTT/)
    assert.match(out.ass, /\[Script Info\]/)
  })
})
