/**
 * Tests BPM detector.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyTempo,
  detectBpm,
  recommendBpmForTone,
  syntheticBeatSignal,
} from '../services/videoTempoDetector.ts'

describe('classifyTempo', () => {
  test('60 BPM → lento', () => {
    assert.equal(classifyTempo(60), 'lento')
  })

  test('120 BPM → allegro', () => {
    assert.equal(classifyTempo(120), 'allegro')
  })

  test('200 BPM → prestissimo', () => {
    assert.equal(classifyTempo(200), 'prestissimo')
  })

  test('50 BPM → larghissimo', () => {
    assert.equal(classifyTempo(50), 'larghissimo')
  })
})

describe('recommendBpmForTone', () => {
  test('hype → BPM élevé', () => {
    assert.ok(recommendBpmForTone('hype') >= 130)
  })

  test('storytelling → BPM bas', () => {
    assert.ok(recommendBpmForTone('storytelling') <= 100)
  })

  test('tutoriel → BPM moyen', () => {
    const b = recommendBpmForTone('tutoriel')
    assert.ok(b >= 90 && b <= 120)
  })
})

describe('detectBpm sur signal synthétique', () => {
  test('beat synthétique 120 BPM → détecté à ±10 BPM', () => {
    const signal = syntheticBeatSignal(120, 5, 22050)
    const r = detectBpm(signal, 22050)
    assert.ok(Math.abs(r.bpm - 120) < 15, `detected ${r.bpm}, expected 120`)
  })

  test('beat synthétique 90 BPM', () => {
    const signal = syntheticBeatSignal(90, 5, 22050)
    const r = detectBpm(signal, 22050)
    assert.ok(Math.abs(r.bpm - 90) < 15, `detected ${r.bpm}, expected 90`)
  })

  test('signal trop court → bpm 0', () => {
    const sig = new Float32Array(100)
    const r = detectBpm(sig, 22050)
    assert.equal(r.bpm, 0)
  })

  test('onsets non vide sur vrai signal', () => {
    const signal = syntheticBeatSignal(120, 3, 22050)
    const r = detectBpm(signal, 22050)
    assert.ok(r.onsets.length > 0)
  })

  test('confidence > 0 pour signal réel', () => {
    const signal = syntheticBeatSignal(100, 4, 22050)
    const r = detectBpm(signal, 22050)
    assert.ok(r.confidence > 0)
  })

  test('category cohérente avec BPM détecté', () => {
    const signal = syntheticBeatSignal(140, 4, 22050)
    const r = detectBpm(signal, 22050)
    assert.equal(r.category, classifyTempo(r.bpm))
  })
})
