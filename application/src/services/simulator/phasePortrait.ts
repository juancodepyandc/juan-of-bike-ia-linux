// Phase portrait : trace l'évolution d'un système dynamique dans l'espace
// (q, q̇) plutôt que (t, q). Outil clé en physique non linéaire pour repérer
// les attracteurs, les orbites fermées, les points stables.
//
// Pour un système 2D (un seul degré de liberté), q = position, q̇ = vitesse.
// Pour un système N-D, on peut projeter sur n'importe quelle paire (q_i, q̇_j).
//
// Module pur. Aucune dépendance.

import type { Acceleration } from './analyticIntegrators.ts'
import { velocityVerlet } from './analyticIntegrators.ts'

export type PhasePoint = {
  q: number
  v: number
  t: number
}

export type PhasePortrait = {
  /** Points (q, q̇) échantillonnés au cours du temps. */
  trajectory: PhasePoint[]
  /** Détecté : orbite fermée vs spirale vs divergence. */
  topology: 'closed-orbit' | 'damped-spiral' | 'amplified-spiral' | 'separatrix' | 'unbounded' | 'unknown'
  /** Énergie min/max sur la trajectoire (conservation = max-min faible). */
  energyMin: number
  energyMax: number
  /** Période détectée par auto-corrélation (s) si orbite fermée. */
  detectedPeriodS: number | null
}

export type PhasePortraitOptions = {
  duration: number
  dt: number
  /** Quel index q et v projeter (cas multi-DOF). Default 0/0. */
  qIndex?: number
  vIndex?: number
  /** Calcul d'énergie pour la détection (optionnel). */
  energy?: (q: number[], v: number[]) => number
  /** Sampling : 1 point tous les `stride` steps. */
  stride?: number
}

/**
 * Intègre le système puis classifie sa topologie.
 */
export function computePhasePortrait(
  accel: Acceleration,
  q0: number[],
  v0: number[],
  opts: PhasePortraitOptions,
): PhasePortrait {
  const qIdx = opts.qIndex ?? 0
  const vIdx = opts.vIndex ?? 0
  const stride = Math.max(1, opts.stride ?? 1)
  const trajectory: PhasePoint[] = []
  let q = q0.slice()
  let v = v0.slice()
  let t = 0
  let energyMin = Infinity
  let energyMax = -Infinity
  let step = 0
  const maxSteps = Math.ceil(opts.duration / opts.dt)
  while (t < opts.duration - 1e-12 && step < maxSteps * 2) {
    if (step % stride === 0) {
      trajectory.push({ q: q[qIdx], v: v[vIdx], t })
      if (opts.energy) {
        const e = opts.energy(q, v)
        if (e < energyMin) energyMin = e
        if (e > energyMax) energyMax = e
      }
    }
    const dt = Math.min(opts.dt, opts.duration - t)
    const result = velocityVerlet(accel, t, q, v, dt)
    q = result.q
    v = result.v
    t += dt
    step += 1
    // Bail-out si le système diverge (NaN ou très grand)
    if (!Number.isFinite(q[qIdx]) || !Number.isFinite(v[vIdx]) || Math.abs(q[qIdx]) > 1e6) {
      break
    }
  }
  if (!opts.energy) {
    energyMin = 0
    energyMax = 0
  }

  const topology = classifyTopology(trajectory)
  const period = topology === 'closed-orbit' ? detectPeriod(trajectory) : null

  return {
    trajectory,
    topology,
    energyMin,
    energyMax,
    detectedPeriodS: period,
  }
}

function classifyTopology(points: PhasePoint[]): PhasePortrait['topology'] {
  if (points.length < 10) return 'unknown'
  const last = points[points.length - 1]
  // Diverge ?
  if (!Number.isFinite(last.q) || Math.abs(last.q) > 1e5) return 'unbounded'
  // Mesure l'amplitude en début vs fin.
  const firstThird = points.slice(0, Math.floor(points.length / 3))
  const lastThird = points.slice(-Math.floor(points.length / 3))
  const ampFirst = amplitude(firstThird)
  const ampLast = amplitude(lastThird)
  const ratio = ampLast / Math.max(1e-9, ampFirst)
  if (ratio < 0.5) return 'damped-spiral'
  if (ratio > 2) return 'amplified-spiral'
  // Vérifie si la trajectoire revient près du point de départ → orbite fermée.
  const start = points[0]
  let minDistInWindow = Infinity
  const windowStart = Math.floor(points.length * 0.3)
  for (let i = windowStart; i < points.length; i += 1) {
    const d = Math.hypot(points[i].q - start.q, points[i].v - start.v)
    if (d < minDistInWindow) minDistInWindow = d
  }
  if (minDistInWindow < ampFirst * 0.2) return 'closed-orbit'
  return 'unknown'
}

function amplitude(points: PhasePoint[]): number {
  if (points.length === 0) return 0
  let minQ = Infinity, maxQ = -Infinity
  for (const p of points) {
    if (p.q < minQ) minQ = p.q
    if (p.q > maxQ) maxQ = p.q
  }
  return (maxQ - minQ) / 2
}

/**
 * Détecte la période par auto-corrélation sur le signal q(t). Renvoie null
 * si pas de période claire.
 */
function detectPeriod(points: PhasePoint[]): number | null {
  if (points.length < 20) return null
  const qs = points.map((p) => p.q)
  const ts = points.map((p) => p.t)
  // Compte les zero-crossings (en signe relatif au début).
  const mean = qs.reduce((a, b) => a + b, 0) / qs.length
  const crossings: number[] = []
  let prevSign = qs[0] - mean > 0 ? 1 : -1
  for (let i = 1; i < qs.length; i += 1) {
    const sign = qs[i] - mean > 0 ? 1 : -1
    if (sign !== prevSign) {
      // Interpolation linéaire pour estimer le temps exact.
      const ratio = (mean - qs[i - 1]) / (qs[i] - qs[i - 1])
      crossings.push(ts[i - 1] + ratio * (ts[i] - ts[i - 1]))
      prevSign = sign
    }
  }
  if (crossings.length < 3) return null
  // Différences inter-crossings, moyenne ↦ demi-période. Multiplier par 2.
  const diffs: number[] = []
  for (let i = 1; i < crossings.length; i += 1) diffs.push(crossings[i] - crossings[i - 1])
  const meanDiff = diffs.reduce((a, b) => a + b, 0) / diffs.length
  return meanDiff * 2
}

/**
 * FFT-light : transformée discrète O(N²) pour de petits signaux (jusqu'à
 * ~1000 points). Renvoie les amplitudes des harmoniques. Pour de gros
 * signaux, intégrer une vraie FFT.
 */
export function discreteSpectrum(signal: number[]): Array<{ frequency: number; amplitude: number }> {
  const N = signal.length
  if (N < 2) return []
  const out: Array<{ frequency: number; amplitude: number }> = []
  // n bins jusqu'à la fréquence de Nyquist N/2.
  for (let k = 0; k < N / 2; k += 1) {
    let re = 0, im = 0
    for (let n = 0; n < N; n += 1) {
      const angle = (2 * Math.PI * k * n) / N
      re += signal[n] * Math.cos(angle)
      im -= signal[n] * Math.sin(angle)
    }
    const amp = Math.sqrt(re * re + im * im) / N
    out.push({ frequency: k / N, amplitude: amp * 2 })
  }
  return out
}

/** Trouve les fréquences "pic" (résonances) au-dessus du seuil. */
export function findResonances(spectrum: Array<{ frequency: number; amplitude: number }>, threshold = 0.1): Array<{ frequency: number; amplitude: number }> {
  const max = spectrum.reduce((m, s) => Math.max(m, s.amplitude), 0)
  const peaks: Array<{ frequency: number; amplitude: number }> = []
  for (let i = 1; i < spectrum.length - 1; i += 1) {
    const cur = spectrum[i]
    const prev = spectrum[i - 1]
    const next = spectrum[i + 1]
    if (cur.amplitude > prev.amplitude && cur.amplitude > next.amplitude && cur.amplitude > max * threshold) {
      peaks.push(cur)
    }
  }
  return peaks.sort((a, b) => b.amplitude - a.amplitude)
}
