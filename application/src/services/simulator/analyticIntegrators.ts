// Analytic integrators for the AuroraIA simulator — pure compute layer.
// No DOM, no Three.js. Deterministic for a fixed dt and seed.
//
// These integrators are used for the closed-form phenomena (pendulum, spring,
// projectile, RLC, N-body…). The general rigid-body engine keeps its
// semi-implicit Euler with sub-stepping (good enough for collisions).
//
// References:
//  - Hairer, Lubich, Wanner — "Geometric Numerical Integration", 2006
//  - Press et al. — "Numerical Recipes", 3rd ed., chap. 17 (Cash-Karp)
//  - Verlet, "Computer Experiments on Classical Fluids", PR 159, 1967

/** State of a 1st-order ODE: y' = f(t, y) */
export type State = readonly number[]
export type Derivative = (t: number, y: State) => number[]

/** State of a 2nd-order ODE for separable Hamiltonian: q'' = a(t, q, q') */
export type Acceleration = (t: number, q: State, v: State) => number[]

/** Energy diagnostic — returns kinetic + potential. */
export type EnergyFn = (t: number, q: State, v: State) => { kinetic: number; potential: number }

// --- 4th-order Runge-Kutta (general ODE) ------------------------------------
// Workhorse for non-conservative systems (drag, dissipation) where symplectic
// methods don't pay off. Global error O(dt^4).
export function rk4(f: Derivative, t: number, y: State, dt: number): number[] {
  const n = y.length
  const k1 = f(t, y)
  const y2 = new Array<number>(n)
  for (let i = 0; i < n; i += 1) y2[i] = y[i] + 0.5 * dt * k1[i]
  const k2 = f(t + 0.5 * dt, y2)
  const y3 = new Array<number>(n)
  for (let i = 0; i < n; i += 1) y3[i] = y[i] + 0.5 * dt * k2[i]
  const k3 = f(t + 0.5 * dt, y3)
  const y4 = new Array<number>(n)
  for (let i = 0; i < n; i += 1) y4[i] = y[i] + dt * k3[i]
  const k4 = f(t + dt, y4)
  const out = new Array<number>(n)
  for (let i = 0; i < n; i += 1) {
    out[i] = y[i] + (dt / 6) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i])
  }
  return out
}

// --- Velocity-Verlet (symplectic, 2nd-order) --------------------------------
// Best for conservative mechanics (orbits, pendulum, spring without damping).
// Preserves energy bounded over very long horizons — Euler can't.
//
// Update rule for q'' = a(t, q, v):
//   q(t+dt) = q + v*dt + 0.5*a*dt^2
//   v(t+dt) = v + 0.5*(a(t,q,v) + a(t+dt,q_new,v))*dt
export function velocityVerlet(a: Acceleration, t: number, q: State, v: State, dt: number): { q: number[]; v: number[] } {
  const n = q.length
  const a0 = a(t, q, v)
  const qNew = new Array<number>(n)
  for (let i = 0; i < n; i += 1) qNew[i] = q[i] + v[i] * dt + 0.5 * a0[i] * dt * dt
  // Predictor for velocity-dependent forces (drag): use v_half then iterate.
  const vHalf = new Array<number>(n)
  for (let i = 0; i < n; i += 1) vHalf[i] = v[i] + 0.5 * a0[i] * dt
  const a1 = a(t + dt, qNew, vHalf)
  const vNew = new Array<number>(n)
  for (let i = 0; i < n; i += 1) vNew[i] = v[i] + 0.5 * (a0[i] + a1[i]) * dt
  return { q: qNew, v: vNew }
}

// --- Symplectic Euler (1st-order, momentum-preserving) ----------------------
// Cheapest stable integrator for orbits. Phase portraits stay closed.
export function symplecticEuler(a: Acceleration, t: number, q: State, v: State, dt: number): { q: number[]; v: number[] } {
  const n = q.length
  const aNow = a(t, q, v)
  const vNew = new Array<number>(n)
  for (let i = 0; i < n; i += 1) vNew[i] = v[i] + aNow[i] * dt
  const qNew = new Array<number>(n)
  for (let i = 0; i < n; i += 1) qNew[i] = q[i] + vNew[i] * dt
  return { q: qNew, v: vNew }
}

// --- Adaptive RK45 (Cash-Karp) ----------------------------------------------
// For stiff or rapidly-changing systems (chemical kinetics, high-velocity
// collisions, double pendulum near singularity). Embedded 4th/5th estimator
// gives an error term we use to scale dt up/down.
//
// Coefficients from Cash & Karp, ACM TOMS 16(3), 1990.
const CK_A2 = 1 / 5
const CK_A3 = 3 / 10
const CK_A4 = 3 / 5
const CK_A5 = 1
const CK_A6 = 7 / 8
const CK_B21 = 1 / 5
const CK_B31 = 3 / 40, CK_B32 = 9 / 40
const CK_B41 = 3 / 10, CK_B42 = -9 / 10, CK_B43 = 6 / 5
const CK_B51 = -11 / 54, CK_B52 = 5 / 2, CK_B53 = -70 / 27, CK_B54 = 35 / 27
const CK_B61 = 1631 / 55296, CK_B62 = 175 / 512, CK_B63 = 575 / 13824, CK_B64 = 44275 / 110592, CK_B65 = 253 / 4096
// 5th-order solution
const CK_C1 = 37 / 378, CK_C3 = 250 / 621, CK_C4 = 125 / 594, CK_C6 = 512 / 1771
// Embedded 4th-order solution
const CK_D1 = 2825 / 27648, CK_D3 = 18575 / 48384, CK_D4 = 13525 / 55296, CK_D5 = 277 / 14336, CK_D6 = 1 / 4

export type AdaptiveResult = { y: number[]; tNext: number; dtUsed: number; dtNext: number; error: number; rejected: boolean }
export type AdaptiveOptions = {
  /** Absolute tolerance per component. */
  atol?: number
  /** Relative tolerance per component. */
  rtol?: number
  /** Min allowed dt (clamps if stiffness pushes lower — useful to bound CPU). */
  minDt?: number
  /** Max allowed dt (clamps if system is slow). */
  maxDt?: number
  /** Safety factor for dt growth (0.84-0.95 typical). */
  safety?: number
}

/**
 * Take one adaptive Cash-Karp step. If the error exceeds tolerance, the step is
 * rejected and a smaller dt is suggested via dtNext — the caller should retry.
 */
export function adaptiveRK45(
  f: Derivative,
  t: number,
  y: State,
  dt: number,
  opts: AdaptiveOptions = {},
): AdaptiveResult {
  const atol = opts.atol ?? 1e-6
  const rtol = opts.rtol ?? 1e-4
  const minDt = opts.minDt ?? 1e-7
  const maxDt = opts.maxDt ?? 1
  const safety = opts.safety ?? 0.9
  const n = y.length

  const k1 = f(t, y)
  const tmp = new Array<number>(n)

  for (let i = 0; i < n; i += 1) tmp[i] = y[i] + dt * CK_B21 * k1[i]
  const k2 = f(t + CK_A2 * dt, tmp)
  for (let i = 0; i < n; i += 1) tmp[i] = y[i] + dt * (CK_B31 * k1[i] + CK_B32 * k2[i])
  const k3 = f(t + CK_A3 * dt, tmp)
  for (let i = 0; i < n; i += 1) tmp[i] = y[i] + dt * (CK_B41 * k1[i] + CK_B42 * k2[i] + CK_B43 * k3[i])
  const k4 = f(t + CK_A4 * dt, tmp)
  for (let i = 0; i < n; i += 1) tmp[i] = y[i] + dt * (CK_B51 * k1[i] + CK_B52 * k2[i] + CK_B53 * k3[i] + CK_B54 * k4[i])
  const k5 = f(t + CK_A5 * dt, tmp)
  for (let i = 0; i < n; i += 1) tmp[i] = y[i] + dt * (CK_B61 * k1[i] + CK_B62 * k2[i] + CK_B63 * k3[i] + CK_B64 * k4[i] + CK_B65 * k5[i])
  const k6 = f(t + CK_A6 * dt, tmp)

  const y5 = new Array<number>(n)
  const y4 = new Array<number>(n)
  for (let i = 0; i < n; i += 1) {
    y5[i] = y[i] + dt * (CK_C1 * k1[i] + CK_C3 * k3[i] + CK_C4 * k4[i] + CK_C6 * k6[i])
    y4[i] = y[i] + dt * (CK_D1 * k1[i] + CK_D3 * k3[i] + CK_D4 * k4[i] + CK_D5 * k5[i] + CK_D6 * k6[i])
  }

  let errNorm = 0
  for (let i = 0; i < n; i += 1) {
    const sc = atol + rtol * Math.max(Math.abs(y[i]), Math.abs(y5[i]))
    const e = (y5[i] - y4[i]) / sc
    errNorm += e * e
  }
  errNorm = Math.sqrt(errNorm / n)

  const rejected = errNorm > 1
  // PI-style step-size controller (Gustafsson, BIT 31, 1991, simplified).
  let factor: number
  if (errNorm === 0) factor = 5
  else factor = safety * Math.pow(1 / errNorm, 1 / 5)
  factor = Math.max(0.1, Math.min(5, factor))
  let dtNext = dt * factor
  dtNext = Math.max(minDt, Math.min(maxDt, dtNext))

  return {
    y: rejected ? Array.from(y) : y5,
    tNext: rejected ? t : t + dt,
    dtUsed: dt,
    dtNext,
    error: errNorm,
    rejected,
  }
}

// --- Energy drift diagnostic ------------------------------------------------
// For conservative systems, a good integrator keeps |E(t) - E0|/|E0| bounded.
// Drift > 1% per period usually means dt is too large or integrator is wrong.
export function energyDrift(energy: EnergyFn, t: number, q: State, v: State, e0: number): number {
  const { kinetic, potential } = energy(t, q, v)
  const e = kinetic + potential
  if (Math.abs(e0) < 1e-12) return Math.abs(e - e0)
  return (e - e0) / Math.abs(e0)
}

// --- Convenience: roll a fixed-dt simulation --------------------------------
export type FixedRollOptions = {
  duration: number
  dt: number
  integrator: 'rk4' | 'verlet' | 'symplecticEuler'
  /** Optional sample callback — fires every k steps for graphing. */
  onSample?: (t: number, q: State, v: State) => void
  sampleStride?: number
}

/**
 * Integrate a 2nd-order Newtonian system at fixed dt.
 * - `verlet` and `symplecticEuler` need an Acceleration; `rk4` needs Derivative.
 * - Returns final (q, v) and elapsed time.
 */
export function rollFixed(
  a: Acceleration,
  q0: State,
  v0: State,
  opts: FixedRollOptions,
): { q: number[]; v: number[]; t: number; steps: number } {
  let q = Array.from(q0)
  let v = Array.from(v0)
  let t = 0
  let steps = 0
  const sampleStride = Math.max(1, opts.sampleStride ?? 1)
  const f: Derivative = (tt: number, y: State) => {
    const half = y.length / 2
    const qq = y.slice(0, half)
    const vv = y.slice(half)
    const aa = a(tt, qq, vv)
    return [...vv, ...aa]
  }
  while (t < opts.duration - 1e-12) {
    const dt = Math.min(opts.dt, opts.duration - t)
    if (opts.integrator === 'rk4') {
      const y = [...q, ...v]
      const yNext = rk4(f, t, y, dt)
      const half = yNext.length / 2
      q = yNext.slice(0, half)
      v = yNext.slice(half)
    } else if (opts.integrator === 'verlet') {
      const step = velocityVerlet(a, t, q, v, dt)
      q = step.q
      v = step.v
    } else {
      const step = symplecticEuler(a, t, q, v, dt)
      q = step.q
      v = step.v
    }
    t += dt
    steps += 1
    if (opts.onSample && steps % sampleStride === 0) opts.onSample(t, q, v)
  }
  return { q, v, t, steps }
}
