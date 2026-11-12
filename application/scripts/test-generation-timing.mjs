#!/usr/bin/env node
// Executes the real TypeScript module (Node type stripping); storage is an in-memory fixture.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  EtaCountdown,
  MIN_COMPARABLE_RUNS,
  RunTimeline,
  SmoothValue,
  accuracyLabel,
  calibrateEstimate,
  comparableRuns,
  estimateRemaining,
  etaAccuracy,
  recordEtaOutcome,
  etaHeadline,
  etaInterval,
  formatClock,
  formatWait,
  measuredRate,
  recordCompletedRun,
  summarize,
} from '../src/services/generationTiming.ts'

function memoryStorage() {
  const map = new Map()
  return { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)) }
}

const S = 1000
const runs = (...totals) => totals.map((t, i) => ({ id: `r${i}`, totalMs: t * S, at: i }))

test('no measurement never yields an invented countdown', () => {
  for (const history of [[], runs(60), runs(60, 70)]) {
    const est = estimateRemaining({ now: 100 * S, runStartedAt: 90 * S, runs: history, historyBasis: 'none' })
    assert.equal(est.state, 'estimating')
    assert.equal(est.remainingMs, null)
    assert.match(etaHeadline(est), new RegExp(`Estimation en préparation \\(${history.length}/${MIN_COMPARABLE_RUNS} runs mesurés\\)`))
  }
})

test('history median and quartiles give remaining time and interval', () => {
  const est = estimateRemaining({ now: 20 * S, runStartedAt: 0, runs: runs(60, 70, 80), historyBasis: 'model' })
  assert.equal(est.state, 'history')
  assert.equal(est.remainingMs, 50 * S)
  assert.equal(est.lowMs, 45 * S)
  assert.equal(est.highMs, 55 * S)
  assert.equal(est.expectedTotalMs, 70 * S)
  assert.match(est.basis, /médiane de 3 runs mesurés \(même modèle\)/)
  assert.equal(etaInterval(est), '45 s – 55 s')
})

test('between median and upper quartile only the upper bound is shown', () => {
  const est = estimateRemaining({ now: 72 * S, runStartedAt: 0, runs: runs(60, 70, 80), historyBasis: 'model' })
  assert.equal(est.state, 'history')
  assert.equal(est.remainingMs, 3 * S)
  assert.equal(est.lowMs, 0)
})

test('beyond the upper quartile the run is reported overdue, not as a negative countdown', () => {
  const est = estimateRemaining({ now: 90 * S, runStartedAt: 0, runs: runs(60, 70, 80), historyBasis: 'model' })
  assert.equal(est.state, 'overdue')
  assert.equal(est.remainingMs, null)
  assert.match(etaHeadline(est), /Plus long que d’habitude \(médiane 1 min 10 s\)/)
})

test('measured overall rate extrapolates the remaining work', () => {
  const overall = [0, 5, 10, 15, 20].map((t) => ({ t: t * S, f: 0.1 + 0.02 * t }))
  const est = estimateRemaining({ now: 20 * S, runStartedAt: 0, overall, runs: [], historyBasis: 'none' })
  assert.equal(est.state, 'live')
  assert.ok(Math.abs(est.remainingMs - 25 * S) < 300, `remaining ${est.remainingMs}`)
  // between samples the remaining time keeps counting down instead of freezing
  const later = estimateRemaining({ now: 24 * S, runStartedAt: 0, overall, runs: [], historyBasis: 'none' })
  assert.ok(Math.abs(later.remainingMs - 21 * S) < 300)
})

test('a rate needs real advance over a real span', () => {
  assert.equal(measuredRate([{ t: 0, f: 0.1 }, { t: 1000, f: 0.2 }], 2000), null, 'span too short')
  assert.equal(measuredRate([{ t: 0, f: 0.1 }, { t: 9000, f: 0.105 }], 9000), null, 'no advance')
  assert.ok(measuredRate([{ t: 0, f: 0.1 }, { t: 9000, f: 0.4 }], 9000))
})

test('per-phase history counts the current phase remainder plus later phases', () => {
  const history = [1, 2, 3].map((i) => ({ id: `p${i}`, totalMs: 60 * S, phaseMs: [10 * S, 20 * S, 30 * S], at: i }))
  const est = estimateRemaining({
    now: 15 * S, runStartedAt: 0, phaseIdx: 1, phaseCount: 3, phaseStartedAt: 10 * S, runs: history, historyBasis: 'model',
  })
  assert.equal(est.state, 'history')
  assert.equal(est.remainingMs, 45 * S)
  assert.match(est.basis, /par étape/)
})

test('measured in-phase speed refines the current phase', () => {
  const history = [1, 2, 3].map((i) => ({ id: `p${i}`, totalMs: 60 * S, phaseMs: [10 * S, 20 * S, 30 * S], at: i }))
  // the diffusion phase advances twice as fast as usual: 50 % in 5 s
  const phase = [10, 12, 15].map((t, i) => ({ t: t * S, f: [0, 0.2, 0.5][i] }))
  const est = estimateRemaining({
    now: 15 * S, runStartedAt: 0, phaseIdx: 1, phaseCount: 3, phaseStartedAt: 10 * S, phase, runs: history, historyBasis: 'model',
  })
  assert.ok(est.remainingMs < 45 * S, `live phase speed should shorten the estimate (${est.remainingMs})`)
  assert.ok(est.remainingMs > 30 * S, 'later phases still counted from history')
})

test('only the current phase measured: lower bound, later phases unknown', () => {
  const phase = [0, 4, 8].map((t, i) => ({ t: t * S, f: [0, 0.2, 0.4][i] }))
  const est = estimateRemaining({ now: 8 * S, runStartedAt: 0, phaseIdx: 2, phaseCount: 5, phaseStartedAt: 0, phase, runs: [], historyBasis: 'none' })
  assert.equal(est.state, 'partial')
  assert.ok(Math.abs(est.remainingMs - 12 * S) < 300)
  assert.equal(est.highMs, null)
  assert.match(etaHeadline(est), /^≥ 10 s \(étape en cours mesurée\)$/)
})

test('server median of comparable runs is used when local history is short', () => {
  const est = estimateRemaining({
    now: 30 * S, runStartedAt: 0, runs: runs(50), historyBasis: 'none', server: { medianTotalSec: 120, sampleCount: 5 },
  })
  assert.equal(est.state, 'history')
  assert.equal(est.remainingMs, 90 * S)
  assert.match(est.basis, /5 runs comparables mesurés par le PC/)
  const tooFew = estimateRemaining({ now: 30 * S, runStartedAt: 0, runs: [], historyBasis: 'none', server: { medianTotalSec: 120, sampleCount: 2 } })
  assert.equal(tooFew.state, 'estimating')
})

test('queued runs report position and only a PC-computed wait', () => {
  const queue = { position: 2, aheadCount: 1, waitSec: 40 }
  const est = estimateRemaining({ now: 0, runStartedAt: null, runs: [], historyBasis: 'none', queue })
  assert.equal(est.state, 'queued')
  assert.equal(etaHeadline(est, null, queue), 'En file · position 2 · attente ≈ 40 s')
  const unknown = estimateRemaining({ now: 0, runStartedAt: null, runs: [], historyBasis: 'none', queue: { ...queue, waitSec: null } })
  assert.equal(unknown.remainingMs, null)
  assert.equal(etaHeadline(unknown, null, queue), 'En file · position 2')
})

test('history store: dedupe, per-model then module fallback, bounded', () => {
  const storage = memoryStorage()
  assert.equal(recordCompletedRun('image', 'flux', { id: 'a', totalMs: 30 * S, at: 1 }, storage), true)
  assert.equal(recordCompletedRun('image', 'flux', { id: 'a', totalMs: 30 * S, at: 2 }, storage), false, 'same job twice')
  assert.equal(recordCompletedRun('image', 'flux', { totalMs: 10, at: 3 }, storage), false, 'implausible duration')
  recordCompletedRun('image', 'flux', { id: 'b', totalMs: 32 * S, at: 4 }, storage)
  recordCompletedRun('image', 'sdxl', { id: 'c', totalMs: 12 * S, at: 5 }, storage)
  assert.equal(comparableRuns('image', 'flux', storage).basis, 'module', 'two same-model runs are not enough')
  recordCompletedRun('image', 'flux', { id: 'd', totalMs: 31 * S, at: 6 }, storage)
  const own = comparableRuns('image', 'flux', storage)
  assert.equal(own.basis, 'model')
  assert.equal(own.runs.length, 3)
  assert.equal(comparableRuns('code', 'x', storage).basis, 'none')
  for (let i = 0; i < 40; i++) recordCompletedRun('code', 'x', { id: `k${i}`, totalMs: (5 + i) * S, at: 10 + i }, storage)
  assert.equal(comparableRuns('code', 'x', storage).runs.length, 24)
})

test('countdown decrements smoothly and re-anchors only on a clear change', () => {
  const cd = new EtaCountdown()
  const est = (ms) => ({ state: 'history', remainingMs: ms, lowMs: 0, highMs: ms, expectedTotalMs: null, confidence: 0.5, sampleCount: 3, basis: '' })
  assert.equal(cd.update(est(60 * S), 0), 60 * S)
  assert.equal(cd.update(est(61 * S), 2 * S), 58 * S, 'small jitter ignored')
  assert.equal(cd.update(est(30 * S), 3 * S), 30 * S, 'large change re-anchors')
  assert.equal(cd.update({ ...est(0), remainingMs: null, state: 'estimating' }, 4 * S), null)
})

test('smoothed value is a pure function of time (HUD and animation agree)', () => {
  const v = new SmoothValue(0, 500)
  v.set(1, 1000)
  const a = v.valueAt(1400)
  const b = v.valueAt(1400)
  assert.equal(a, b)
  assert.ok(a > 0.5 && a < 1)
  assert.ok(v.valueAt(5000) > 0.999)
})

test('timeline accumulates real phase durations and ignores small measurement jitter', () => {
  const tl = new RunTimeline(0, 3)
  tl.noteProgress(0.3, 1000, false)
  tl.noteProgress(0.28, 2000, false)
  assert.equal(tl.display.goal, 0.3, 'tiny regression does not move the display back')
  tl.noteProgress(0.05, 3000, false)
  assert.equal(tl.display.goal, 0.05, 'a new pass is shown honestly')
  assert.equal(tl.notePhase(1, 4000), true)
  assert.equal(tl.notePhase(1, 5000), false)
  assert.equal(tl.notePhase(2, 9000), true)
  assert.deepEqual(tl.phaseDurations(10000), [4000, 5000, 1000])
})

test('readable durations', () => {
  assert.equal(formatWait(4 * S), 'quelques secondes')
  assert.equal(formatWait(47 * S), '45 s')
  assert.equal(formatWait(200 * S), '3 min 20 s')
  assert.equal(formatWait(1500 * S), '25 min')
  assert.equal(formatWait(3900 * S), '1 h 05')
  assert.equal(formatClock(65 * S), '1 min 05 s')
  assert.deepEqual(summarize([3, 1, 2]), { n: 3, median: 2, q1: 1.5, q3: 2.5, min: 1, max: 3 })
})

test('accuracy is measured only from real completed runs, then shown and used', () => {
  const storage = memoryStorage()
  // a run of 100 s: predictions taken at 10 s and 50 s
  const snaps = (pred10, pred50, band = 0.1) => [
    { elapsedMs: 10 * S, remainingMs: pred10 * S, lowMs: pred10 * S * (1 - band), highMs: pred10 * S * (1 + band) },
    { elapsedMs: 50 * S, remainingMs: pred50 * S, lowMs: pred50 * S * (1 - band), highMs: pred50 * S * (1 + band) },
  ]
  assert.equal(etaAccuracy('3d', storage), null, 'no real run yet: no accuracy claimed')
  assert.equal(recordEtaOutcome('3d', 'run-a', snaps(90, 50), 100 * S, storage), true)
  assert.equal(recordEtaOutcome('3d', 'run-a', snaps(90, 50), 100 * S, storage), false, 'same run twice')
  recordEtaOutcome('3d', 'run-b', snaps(60, 30), 100 * S, storage)
  assert.equal(etaAccuracy('3d', storage), null, 'two runs are not enough')
  recordEtaOutcome('3d', 'run-c', snaps(120, 70), 100 * S, storage)
  const acc = etaAccuracy('3d', storage)
  assert.equal(acc.runs, 3)
  assert.equal(acc.predictions, 6)
  // errors: 0, 0, .333, .4, .333, .4 -> median .333
  assert.ok(Math.abs(acc.medianError - 0.333) < 0.01, `median error ${acc.medianError}`)
  assert.ok(Math.abs(acc.coverage - 2 / 6) < 1e-9)
  assert.match(accuracyLabel(acc), /précision mesurée sur 3 vraies générations : écart médian 33 %, 33 % dans l’intervalle/)
})

test('a too narrow interval is widened by the measured error after 5 real runs', () => {
  const storage = memoryStorage()
  for (let i = 0; i < 5; i++) {
    recordEtaOutcome('image', `r${i}`, [{ elapsedMs: 10 * S, remainingMs: 50 * S, lowMs: 48 * S, highMs: 52 * S }], 100 * S, storage)
  }
  const acc = etaAccuracy('image', storage)
  assert.equal(acc.coverage, 0)
  const est = { state: 'history', remainingMs: 40 * S, lowMs: 38 * S, highMs: 42 * S, expectedTotalMs: 60 * S, confidence: 0.5, sampleCount: 5, basis: 'médiane' }
  const widened = calibrateEstimate(est, acc)
  assert.ok(widened.lowMs < 38 * S && widened.highMs > 42 * S, `${widened.lowMs} – ${widened.highMs}`)
  assert.match(widened.basis, /intervalle élargi d’après l’écart mesuré \(44 %\)/)
  assert.equal(calibrateEstimate({ ...est, state: 'estimating', remainingMs: null }, acc).lowMs, 38 * S, 'nothing invented without an estimate')
  const good = { runs: 6, predictions: 6, medianError: 0.1, coverage: 0.8 }
  assert.equal(calibrateEstimate(est, good), est, 'a well calibrated interval is kept')
})
