// Glue layer between the analytic phenomena library, the integrators, and the
// data recorder. Views import from here — they don't need to know about the
// integrator-vs-derivative dance.
//
// Pure compute: no DOM. The session runs at fixed dt by default; opt into
// adaptive Cash-Karp via `mode: 'adaptive'`.

import {
  adaptiveRK45,
  rk4,
  symplecticEuler,
  velocityVerlet,
} from './analyticIntegrators.ts'
import type {
  AnalyticPhenomenon,
} from './analyticPhenomena.ts'
import {
  resolveParams,
} from './analyticPhenomena.ts'
import { DataRecorder } from './dataRecorder.ts'
import type { Channel } from './dataRecorder.ts'

export type IntegratorKind = 'rk4' | 'verlet' | 'symplecticEuler' | 'adaptiveRK45'

export type AnalyticSessionOptions = {
  /** Step size (s). For adaptive, this is the initial guess. */
  dt?: number
  /** Integrator selection. Defaults from phenomenon difficulty. */
  integrator?: IntegratorKind
  /** Max samples kept in the recorder. */
  maxSamples?: number
  /** Minimum gap between recorded samples (s). Lower = denser graph. */
  recordEvery?: number
  /** Tolerance for adaptive integrator (default 1e-5 absolute, 1e-4 relative). */
  atol?: number
  rtol?: number
  /** Wall-clock cap per `advance()` call to keep the UI responsive (s). */
  maxStepsPerAdvance?: number
}

const ENERGY_CHANNEL: Channel = { id: '__energyDrift', label: 'dérive E/E₀', unit: '', color: '#ff9b9b' }

function defaultIntegrator(phen: AnalyticPhenomenon): IntegratorKind {
  if (phen.id === 'pendulum-double') return 'adaptiveRK45'
  if (phen.category === 'mecanique') return 'verlet'
  if (phen.category === 'electromagnetisme') return 'rk4'
  return 'rk4'
}

export class AnalyticSession {
  readonly phenomenon: AnalyticPhenomenon
  readonly params: Record<string, number>
  readonly recorder: DataRecorder
  private q: number[]
  private v: number[]
  private t = 0
  private dt: number
  private integrator: IntegratorKind
  private accel: ReturnType<AnalyticPhenomenon['acceleration']>
  private energyFn: ReturnType<AnalyticPhenomenon['energy']>
  private e0: number
  private maxStepsPerAdvance: number
  private atol: number
  private rtol: number

  constructor(phen: AnalyticPhenomenon, paramsRaw: Record<string, number> = {}, opts: AnalyticSessionOptions = {}) {
    this.phenomenon = phen
    this.params = resolveParams(phen, paramsRaw)
    this.dt = opts.dt ?? phen.suggestedDt
    this.integrator = opts.integrator ?? defaultIntegrator(phen)
    this.atol = opts.atol ?? 1e-5
    this.rtol = opts.rtol ?? 1e-4
    this.maxStepsPerAdvance = Math.max(1, opts.maxStepsPerAdvance ?? 5000)

    const { q, v } = phen.initial(this.params)
    this.q = q.slice()
    this.v = v.slice()

    this.accel = phen.acceleration(this.params)
    this.energyFn = phen.energy(this.params)
    const energy0 = this.energyFn(0, this.q, this.v)
    this.e0 = energy0.kinetic + energy0.potential

    this.recorder = new DataRecorder([...phen.channels, ENERGY_CHANNEL], {
      maxSamples: opts.maxSamples ?? 4096,
      minDtSeconds: opts.recordEvery ?? 0,
    })
    this.sampleNow()
  }

  /** Restart from initial conditions, keep params and integrator. */
  reset(): void {
    const { q, v } = this.phenomenon.initial(this.params)
    this.q = q.slice()
    this.v = v.slice()
    this.t = 0
    const e0 = this.energyFn(0, this.q, this.v)
    this.e0 = e0.kinetic + e0.potential
    this.recorder.reset()
    this.sampleNow()
  }

  setIntegrator(kind: IntegratorKind): void {
    this.integrator = kind
  }

  setDt(dt: number): void {
    if (Number.isFinite(dt) && dt > 0) this.dt = dt
  }

  getState(): { t: number; q: readonly number[]; v: readonly number[] } {
    return { t: this.t, q: this.q, v: this.v }
  }

  /** Advance the session up to `duration` seconds (real-time simulation time). */
  advance(duration: number): { stepsTaken: number; clippedByBudget: boolean } {
    if (!(duration > 0) || !Number.isFinite(duration)) return { stepsTaken: 0, clippedByBudget: false }
    let remaining = duration
    let steps = 0
    while (remaining > 1e-12 && steps < this.maxStepsPerAdvance) {
      const dt = Math.min(this.dt, remaining)
      this.takeStep(dt)
      remaining -= dt
      steps += 1
      this.sampleNow()
    }
    return { stepsTaken: steps, clippedByBudget: remaining > 1e-9 }
  }

  /** Trigger a CSV-ready snapshot (returns string, view can save it). */
  exportCsv(): string {
    return this.recorder.toCsv()
  }

  /**
   * CSV "rapport" pour dossier BAC : header avec phénomène, intégrateur,
   * durée, params + résumé statistique par canal, puis CSV brut. Excel /
   * LibreOffice / Numbers le décodent.
   */
  exportCsvReport(): string {
    return this.recorder.toCsvReport({
      phenomenon: this.phenomenon.id,
      integrator: this.integrator,
      durationS: this.t,
      params: this.params,
    })
  }

  /** Quick diagnostics summary: per-channel statistics + energy drift. */
  diagnostics(): { phenomenon: string; integrator: IntegratorKind; samples: number; channels: ReturnType<DataRecorder['diagnostics']> } {
    return {
      phenomenon: this.phenomenon.id,
      integrator: this.integrator,
      samples: this.recorder.size(),
      channels: this.recorder.diagnostics(),
    }
  }

  private takeStep(dt: number): void {
    if (this.integrator === 'rk4') {
      const y = [...this.q, ...this.v]
      const half = this.q.length
      const derivative = (tt: number, yy: readonly number[]) => {
        const qq = yy.slice(0, half)
        const vv = yy.slice(half)
        const aa = this.accel(tt, qq, vv)
        return [...vv, ...aa]
      }
      const next = rk4(derivative, this.t, y, dt)
      this.q = next.slice(0, half)
      this.v = next.slice(half)
      this.t += dt
    } else if (this.integrator === 'verlet') {
      const step = velocityVerlet(this.accel, this.t, this.q, this.v, dt)
      this.q = step.q
      this.v = step.v
      this.t += dt
    } else if (this.integrator === 'symplecticEuler') {
      const step = symplecticEuler(this.accel, this.t, this.q, this.v, dt)
      this.q = step.q
      this.v = step.v
      this.t += dt
    } else if (this.integrator === 'adaptiveRK45') {
      const y = [...this.q, ...this.v]
      const half = this.q.length
      const derivative = (tt: number, yy: readonly number[]) => {
        const qq = yy.slice(0, half)
        const vv = yy.slice(half)
        const aa = this.accel(tt, qq, vv)
        return [...vv, ...aa]
      }
      const res = adaptiveRK45(derivative, this.t, y, dt, { atol: this.atol, rtol: this.rtol, minDt: dt / 1024, maxDt: dt * 8 })
      if (!res.rejected) {
        this.q = res.y.slice(0, half)
        this.v = res.y.slice(half)
        this.t = res.tNext
      }
      this.dt = res.dtNext
    }
  }

  private sampleNow(): void {
    const sample = this.phenomenon.sample(this.params, this.t, this.q, this.v)
    const { kinetic, potential } = this.energyFn(this.t, this.q, this.v)
    const drift = Math.abs(this.e0) < 1e-12 ? kinetic + potential - this.e0 : (kinetic + potential - this.e0) / Math.abs(this.e0)
    this.recorder.push(this.t, { ...sample, [ENERGY_CHANNEL.id]: drift })
  }
}

/** Build a session for the given phenomenon id, throwing if unknown. */
export function startSession(
  phenomenon: AnalyticPhenomenon,
  params: Record<string, number> = {},
  opts: AnalyticSessionOptions = {},
): AnalyticSession {
  return new AnalyticSession(phenomenon, params, opts)
}
