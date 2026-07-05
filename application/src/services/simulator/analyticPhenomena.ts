// Analytic phenomena library for the simulator — paired with the closed-form
// integrators in `analyticIntegrators.ts`.
//
// Each phenomenon exposes:
//   • initial state (q, v)
//   • acceleration / derivative function with the physical equations inline
//   • energy diagnostic (so we can show conservation in the UI)
//   • channel descriptors for the DataRecorder (live graphs + CSV)
//   • a "didactic" payload (équation TeX + paramètres officiels STI2D)
//
// All units SI. No DOM, no Three.js. Deterministic.

import type { Acceleration, Derivative, EnergyFn } from './analyticIntegrators'
import type { Channel } from './dataRecorder'

export type Didactic = {
  /** TeX equations rendered in the panel (KaTeX) — already in the dependency list. */
  equationsTex: string[]
  /** Short one-line summary for tooltips. */
  hint: string
  /** STI2D/Première/Terminale BO references. */
  programReferences: string[]
}

export type PhenomenonParam = {
  id: string
  label: string
  unit: string
  min: number
  max: number
  step: number
  default: number
  /** Optional clamp behaviour for sliders that should snap (e.g. integer particle count). */
  integer?: boolean
}

export type AnalyticPhenomenon = {
  id: string
  label: string
  category: 'mecanique' | 'ondes' | 'thermo' | 'electromagnetisme' | 'optique' | 'chimie'
  difficulty: 'debutant' | 'intermediaire' | 'avance'
  params: PhenomenonParam[]
  didactic: Didactic
  /** Suggested fixed-dt simulation step (s). */
  suggestedDt: number
  /** Suggested total duration (s) for a "one-period" capture. */
  suggestedDuration: number
  /** Time-series channels exposed by this phenomenon. */
  channels: Channel[]
  /** Build initial (q, v). */
  initial: (p: Record<string, number>) => { q: number[]; v: number[] }
  /** Newtonian acceleration q'' = a(t, q, v). */
  acceleration: (p: Record<string, number>) => Acceleration
  /** Optional 1st-order derivative (if the system is not purely 2nd-order, e.g. RLC). */
  derivative?: (p: Record<string, number>) => Derivative
  /** Energy components — used to flag drift > 1%. */
  energy: (p: Record<string, number>) => EnergyFn
  /** Project current state to the named channels (e.g. compute Ec, Ep, etc.). */
  sample: (p: Record<string, number>, t: number, q: number[], v: number[]) => Record<string, number>
}

// --- Helpers ----------------------------------------------------------------
const G_TERRE = 9.81
const COULOMB_K = 8.9875517873681764e9

function clampParam(param: PhenomenonParam, raw: number | undefined): number {
  if (raw == null || !Number.isFinite(raw)) return param.default
  let v = Math.min(param.max, Math.max(param.min, raw))
  if (param.integer) v = Math.round(v)
  return v
}

export function resolveParams(phen: AnalyticPhenomenon, raw: Record<string, number> = {}): Record<string, number> {
  const out: Record<string, number> = {}
  for (const p of phen.params) out[p.id] = clampParam(p, raw[p.id])
  return out
}

// --- Pendule simple (équation NON linéarisée) -------------------------------
// θ'' + (g/L) sin(θ) + (μ/(mL²)) θ' = 0
// Conservation: E = ½ m L² θ'² + m g L (1 - cos θ)  (sans frottement)
//
// Pourquoi pas Euler ? À grandes amplitudes l'énergie d'Euler dérive de +10%/s.
// Verlet borne la dérive à ~1e-4 sur 100 périodes.
const pendulumSimple: AnalyticPhenomenon = {
  id: 'pendulum-exact',
  label: 'Pendule simple (exact)',
  category: 'mecanique',
  difficulty: 'intermediaire',
  suggestedDt: 1 / 240,
  suggestedDuration: 20,
  params: [
    { id: 'length', label: 'Longueur L', unit: 'm', min: 0.05, max: 5, step: 0.01, default: 1 },
    { id: 'mass', label: 'Masse m', unit: 'kg', min: 0.01, max: 10, step: 0.01, default: 1 },
    { id: 'gravity', label: 'Pesanteur g', unit: 'm/s²', min: 1.62, max: 24.79, step: 0.01, default: G_TERRE },
    { id: 'theta0', label: 'Angle initial θ₀', unit: 'rad', min: -Math.PI, max: Math.PI, step: 0.01, default: 0.9 },
    { id: 'friction', label: 'Frottement μ', unit: 'N·m·s/rad', min: 0, max: 1, step: 0.001, default: 0.02 },
  ],
  didactic: {
    equationsTex: [
      '\\ddot{\\theta} + \\frac{g}{L}\\sin\\theta + \\frac{\\mu}{mL^{2}}\\dot{\\theta} = 0',
      'T_{\\text{petit angle}} = 2\\pi\\sqrt{L/g}',
    ],
    hint: 'Non linéaire pour |θ| > 15°. Verlet pour la conservation, RK4 si frottement.',
    programReferences: ['Première STI2D — physique des oscillateurs', 'Terminale STI2D — étude énergétique'],
  },
  channels: [
    { id: 'theta', label: 'θ', unit: 'rad', color: '#3aa4ff' },
    { id: 'omega', label: 'θ̇', unit: 'rad/s', color: '#ff5a1f' },
    { id: 'Ec', label: 'Énergie cinétique', unit: 'J', color: '#ffd166' },
    { id: 'Ep', label: 'Énergie potentielle', unit: 'J', color: '#37c7bf' },
    { id: 'Etot', label: 'Énergie totale', unit: 'J', color: '#ffffff' },
  ],
  initial: (p) => ({ q: [p.theta0], v: [0] }),
  acceleration: (p) => (_t, q, v) => {
    const theta = q[0]
    const omega = v[0]
    return [-(p.gravity / p.length) * Math.sin(theta) - (p.friction / (p.mass * p.length * p.length)) * omega]
  },
  energy: (p) => (_t, q, v) => {
    const theta = q[0]
    const omega = v[0]
    return {
      kinetic: 0.5 * p.mass * p.length * p.length * omega * omega,
      potential: p.mass * p.gravity * p.length * (1 - Math.cos(theta)),
    }
  },
  sample: (p, _t, q, v) => {
    const Ec = 0.5 * p.mass * p.length * p.length * v[0] * v[0]
    const Ep = p.mass * p.gravity * p.length * (1 - Math.cos(q[0]))
    return { theta: q[0], omega: v[0], Ec, Ep, Etot: Ec + Ep }
  },
}

// --- Oscillateur masse-ressort amorti ---------------------------------------
// m x'' + b x' + k x = 0  →  x'' = -(k/m) x - (b/m) x'
// ω₀ = √(k/m), ζ = b / (2√(km))
const dampedSpring: AnalyticPhenomenon = {
  id: 'spring-damped',
  label: 'Ressort amorti',
  category: 'mecanique',
  difficulty: 'debutant',
  suggestedDt: 1 / 240,
  suggestedDuration: 10,
  params: [
    { id: 'mass', label: 'Masse m', unit: 'kg', min: 0.05, max: 10, step: 0.01, default: 0.5 },
    { id: 'stiffness', label: 'Raideur k', unit: 'N/m', min: 1, max: 1000, step: 0.5, default: 80 },
    { id: 'damping', label: 'Amortissement b', unit: 'N·s/m', min: 0, max: 20, step: 0.01, default: 0.6 },
    { id: 'x0', label: 'Allongement initial x₀', unit: 'm', min: -1, max: 1, step: 0.01, default: 0.4 },
    { id: 'v0', label: 'Vitesse initiale v₀', unit: 'm/s', min: -5, max: 5, step: 0.01, default: 0 },
  ],
  didactic: {
    equationsTex: [
      'm\\ddot{x} + b\\dot{x} + kx = 0',
      '\\omega_{0} = \\sqrt{k/m}, \\quad \\zeta = \\dfrac{b}{2\\sqrt{km}}',
    ],
    hint: 'ζ < 1 pseudo-périodique • ζ = 1 critique • ζ > 1 apériodique.',
    programReferences: ['Première STI2D — oscillateurs', 'Terminale — analogie mécanique/RLC'],
  },
  channels: [
    { id: 'x', label: 'Allongement', unit: 'm', color: '#3aa4ff' },
    { id: 'v', label: 'Vitesse', unit: 'm/s', color: '#ff5a1f' },
    { id: 'Ec', label: 'Énergie cinétique', unit: 'J', color: '#ffd166' },
    { id: 'Ep', label: 'Énergie élastique', unit: 'J', color: '#37c7bf' },
    { id: 'Etot', label: 'Énergie totale', unit: 'J', color: '#ffffff' },
  ],
  initial: (p) => ({ q: [p.x0], v: [p.v0] }),
  acceleration: (p) => (_t, q, v) => [
    -(p.stiffness / p.mass) * q[0] - (p.damping / p.mass) * v[0],
  ],
  energy: (p) => (_t, q, v) => ({
    kinetic: 0.5 * p.mass * v[0] * v[0],
    potential: 0.5 * p.stiffness * q[0] * q[0],
  }),
  sample: (p, _t, q, v) => {
    const Ec = 0.5 * p.mass * v[0] * v[0]
    const Ep = 0.5 * p.stiffness * q[0] * q[0]
    return { x: q[0], v: v[0], Ec, Ep, Etot: Ec + Ep }
  },
}

// --- Tir balistique avec traînée quadratique --------------------------------
// m r'' = m g - ½ ρ Cd A |r'| r'      (drag quadratique)
// Cas idéal (sans drag): portée = v₀² sin(2α)/g
const projectileDrag: AnalyticPhenomenon = {
  id: 'projectile-drag',
  label: 'Tir balistique (traînée quadratique)',
  category: 'mecanique',
  difficulty: 'intermediaire',
  suggestedDt: 1 / 200,
  suggestedDuration: 6,
  params: [
    { id: 'speed', label: 'Vitesse initiale v₀', unit: 'm/s', min: 1, max: 80, step: 0.5, default: 30 },
    { id: 'angle', label: "Angle α", unit: 'rad', min: 0, max: Math.PI / 2, step: 0.01, default: Math.PI / 4 },
    { id: 'mass', label: 'Masse', unit: 'kg', min: 0.01, max: 50, step: 0.01, default: 0.145 },
    { id: 'cd', label: 'Coeff. de traînée Cd', unit: '', min: 0, max: 2, step: 0.01, default: 0.47 },
    { id: 'area', label: 'Section A', unit: 'm²', min: 1e-4, max: 1, step: 1e-4, default: 4.3e-3 },
    { id: 'rho', label: "Masse vol. air ρ", unit: 'kg/m³', min: 0.1, max: 1.5, step: 0.01, default: 1.225 },
    { id: 'gravity', label: 'g', unit: 'm/s²', min: 1.62, max: 24.79, step: 0.01, default: G_TERRE },
  ],
  didactic: {
    equationsTex: [
      'm\\ddot{\\vec{r}} = m\\vec{g} - \\tfrac{1}{2}\\rho C_{d}A\\,|\\vec{v}|\\,\\vec{v}',
      'P_{\\text{idéal}} = \\dfrac{v_{0}^{2}\\sin(2\\alpha)}{g}',
    ],
    hint: 'Trajectoire balistique : la traînée raccourcit la portée et casse la symétrie.',
    programReferences: ["Première STI2D — chute libre 2D", "Terminale — application du PFD"],
  },
  channels: [
    { id: 'x', label: 'Position x', unit: 'm', color: '#3aa4ff' },
    { id: 'y', label: 'Altitude y', unit: 'm', color: '#ff5a1f' },
    { id: 'vx', label: 'Vitesse vx', unit: 'm/s', color: '#ffd166' },
    { id: 'vy', label: 'Vitesse vy', unit: 'm/s', color: '#37c7bf' },
    { id: 'speed', label: 'Vitesse |v|', unit: 'm/s', color: '#ffffff' },
  ],
  initial: (p) => ({ q: [0, 0], v: [p.speed * Math.cos(p.angle), p.speed * Math.sin(p.angle)] }),
  acceleration: (p) => (_t, _q, v) => {
    const speed = Math.hypot(v[0], v[1])
    const dragCoef = (0.5 * p.rho * p.cd * p.area) / p.mass
    return [
      -dragCoef * speed * v[0],
      -p.gravity - dragCoef * speed * v[1],
    ]
  },
  energy: (p) => (_t, q, v) => ({
    kinetic: 0.5 * p.mass * (v[0] * v[0] + v[1] * v[1]),
    potential: p.mass * p.gravity * q[1],
  }),
  sample: (_p, _t, q, v) => ({
    x: q[0],
    y: q[1],
    vx: v[0],
    vy: v[1],
    speed: Math.hypot(v[0], v[1]),
  }),
}

// --- Circuit RLC série ------------------------------------------------------
// L q'' + R q' + q/C = U(t)
// Ici U = 0 (oscillations libres). État y = [q, i = q'].
//
// Note BO: la décharge d'un condensateur dans (R, L) est au programme STI2D.
const rlcCircuit: AnalyticPhenomenon = {
  id: 'rlc-series',
  label: 'Circuit RLC (décharge)',
  category: 'electromagnetisme',
  difficulty: 'intermediaire',
  suggestedDt: 1 / 5000,
  suggestedDuration: 0.05,
  params: [
    { id: 'R', label: 'Résistance R', unit: 'Ω', min: 0, max: 1000, step: 0.5, default: 10 },
    { id: 'L', label: 'Inductance L', unit: 'H', min: 1e-4, max: 1, step: 1e-4, default: 1e-2 },
    { id: 'C', label: 'Capacité C', unit: 'F', min: 1e-8, max: 1e-3, step: 1e-8, default: 1e-6 },
    { id: 'q0', label: 'Charge initiale q₀', unit: 'C', min: 0, max: 1e-3, step: 1e-7, default: 1e-5 },
  ],
  didactic: {
    equationsTex: [
      'L\\ddot{q} + R\\dot{q} + \\dfrac{q}{C} = 0',
      '\\omega_{0} = \\dfrac{1}{\\sqrt{LC}}, \\quad \\zeta = \\dfrac{R}{2}\\sqrt{\\dfrac{C}{L}}',
    ],
    hint: 'Analogue électrique du ressort amorti — même équation, autre vocabulaire.',
    programReferences: ['Terminale STI2D — circuit RLC libre'],
  },
  channels: [
    { id: 'q', label: 'Charge', unit: 'C', color: '#3aa4ff' },
    { id: 'i', label: 'Courant', unit: 'A', color: '#ff5a1f' },
    { id: 'Uc', label: 'Tension condo', unit: 'V', color: '#ffd166' },
    { id: 'Ec', label: 'Énergie L', unit: 'J', color: '#37c7bf' },
    { id: 'Ep', label: 'Énergie C', unit: 'J', color: '#9d4eff' },
    { id: 'Etot', label: 'Énergie totale', unit: 'J', color: '#ffffff' },
  ],
  initial: (p) => ({ q: [p.q0], v: [0] }),
  acceleration: (p) => (_t, q, v) => [-(p.R / p.L) * v[0] - q[0] / (p.L * p.C)],
  energy: (p) => (_t, q, v) => ({
    kinetic: 0.5 * p.L * v[0] * v[0],
    potential: 0.5 * (q[0] * q[0]) / p.C,
  }),
  sample: (p, _t, q, v) => {
    const Ec = 0.5 * p.L * v[0] * v[0]
    const Ep = 0.5 * (q[0] * q[0]) / p.C
    return { q: q[0], i: v[0], Uc: q[0] / p.C, Ec, Ep, Etot: Ec + Ep }
  },
}

// --- Pendule double (chaos) -------------------------------------------------
// Lagrangien : voir Marion & Thornton, chap. 8.
// θ₁'' et θ₂'' couplés via la matrice de masse — bien sensible aux CI.
//
// On préfère RK45 adaptatif ici : Verlet déraille près des singularités où
// (3 - cos(2(θ₁-θ₂))) approche 2.
const doublePendulum: AnalyticPhenomenon = {
  id: 'pendulum-double',
  label: 'Pendule double (chaos)',
  category: 'mecanique',
  difficulty: 'avance',
  suggestedDt: 1 / 500,
  suggestedDuration: 30,
  params: [
    { id: 'L1', label: 'L₁', unit: 'm', min: 0.1, max: 2, step: 0.01, default: 1 },
    { id: 'L2', label: 'L₂', unit: 'm', min: 0.1, max: 2, step: 0.01, default: 1 },
    { id: 'm1', label: 'm₁', unit: 'kg', min: 0.1, max: 5, step: 0.01, default: 1 },
    { id: 'm2', label: 'm₂', unit: 'kg', min: 0.1, max: 5, step: 0.01, default: 1 },
    { id: 'theta1_0', label: 'θ₁ initial', unit: 'rad', min: -Math.PI, max: Math.PI, step: 0.01, default: 1.2 },
    { id: 'theta2_0', label: 'θ₂ initial', unit: 'rad', min: -Math.PI, max: Math.PI, step: 0.01, default: -0.5 },
    { id: 'gravity', label: 'g', unit: 'm/s²', min: 1.62, max: 24.79, step: 0.01, default: G_TERRE },
  ],
  didactic: {
    equationsTex: [
      "(m_{1}+m_{2})L_{1}\\ddot{\\theta}_{1} + m_{2}L_{2}\\ddot{\\theta}_{2}\\cos(\\theta_{1}-\\theta_{2}) + m_{2}L_{2}\\dot{\\theta}_{2}^{2}\\sin(\\theta_{1}-\\theta_{2}) + (m_{1}+m_{2})g\\sin\\theta_{1} = 0",
    ],
    hint: 'Système chaotique : un écart de 1e-3 sur les conditions initiales explose en quelques secondes.',
    programReferences: ['Approfondissement Terminale — physique non linéaire'],
  },
  channels: [
    { id: 'theta1', label: 'θ₁', unit: 'rad', color: '#3aa4ff' },
    { id: 'theta2', label: 'θ₂', unit: 'rad', color: '#ff5a1f' },
    { id: 'omega1', label: 'θ̇₁', unit: 'rad/s', color: '#ffd166' },
    { id: 'omega2', label: 'θ̇₂', unit: 'rad/s', color: '#37c7bf' },
    { id: 'Etot', label: 'Énergie totale', unit: 'J', color: '#ffffff' },
  ],
  initial: (p) => ({ q: [p.theta1_0, p.theta2_0], v: [0, 0] }),
  acceleration: (p) => (_t, q, v) => {
    const [t1, t2] = q
    const [w1, w2] = v
    const delta = t1 - t2
    const sinD = Math.sin(delta)
    const cosD = Math.cos(delta)
    const m = p.m1 + p.m2
    const denom1 = p.L1 * (m - p.m2 * cosD * cosD)
    const denom2 = p.L2 * (m - p.m2 * cosD * cosD)
    const a1Num =
      -p.gravity * (2 * p.m1 + p.m2) * Math.sin(t1)
      - p.m2 * p.gravity * Math.sin(t1 - 2 * t2)
      - 2 * sinD * p.m2 * (w2 * w2 * p.L2 + w1 * w1 * p.L1 * cosD)
    const a2Num =
      2 * sinD * (w1 * w1 * p.L1 * m + p.gravity * m * Math.cos(t1) + w2 * w2 * p.L2 * p.m2 * cosD)
    return [a1Num / (2 * denom1), a2Num / (2 * denom2)]
  },
  energy: (p) => (_t, q, v) => {
    const [t1, t2] = q
    const [w1, w2] = v
    const kinetic =
      0.5 * p.m1 * (p.L1 * w1) ** 2
      + 0.5 * p.m2 * ((p.L1 * w1) ** 2 + (p.L2 * w2) ** 2 + 2 * p.L1 * p.L2 * w1 * w2 * Math.cos(t1 - t2))
    const potential =
      -(p.m1 + p.m2) * p.gravity * p.L1 * Math.cos(t1)
      - p.m2 * p.gravity * p.L2 * Math.cos(t2)
    return { kinetic, potential }
  },
  sample: (p, _t, q, v) => {
    const { kinetic, potential } = doublePendulum.energy(p)(_t, q, v)
    return { theta1: q[0], theta2: q[1], omega1: v[0], omega2: v[1], Etot: kinetic + potential }
  },
}

// --- Loi d'Ohm + diffusion thermique d'une barre (modèle nodal) -------------
// Discrétisation centrée 1D : T_i'' (en réalité 1er ordre) — ici on intègre
// l'équation de la chaleur par différences finies sur N nœuds.
//   ∂T/∂t = α ∂²T/∂x² ,    α = k/(ρcₚ)
// État : T(x_i) pour i = 0..N-1.
const thermalRod: AnalyticPhenomenon = {
  id: 'thermal-rod-1d',
  label: 'Diffusion thermique 1D',
  category: 'thermo',
  difficulty: 'intermediaire',
  suggestedDt: 0.05,
  suggestedDuration: 120,
  params: [
    { id: 'length', label: 'Longueur', unit: 'm', min: 0.05, max: 2, step: 0.01, default: 0.5 },
    { id: 'nodes', label: 'Nœuds', unit: '', min: 10, max: 80, step: 1, default: 30, integer: true },
    { id: 'alpha', label: 'Diffusivité α', unit: 'm²/s', min: 1e-7, max: 1e-3, step: 1e-7, default: 1.1e-4 },
    { id: 'tempHot', label: 'T chaude', unit: 'K', min: 273, max: 1500, step: 1, default: 500 },
    { id: 'tempCold', label: 'T froide', unit: 'K', min: 100, max: 400, step: 1, default: 293 },
  ],
  didactic: {
    equationsTex: [
      '\\partial_{t} T = \\alpha \\partial_{xx} T',
      '\\Delta t < \\dfrac{(\\Delta x)^{2}}{2\\alpha} \\text{ (CFL explicite)}',
    ],
    hint: 'Loi de Fourier. Si la simulation explose, baisse Δt ou augmente α — règle CFL.',
    programReferences: ['Première STI2D — transferts thermiques', 'Terminale — diffusion'],
  },
  channels: [
    { id: 'Tleft', label: 'T extrémité chaude', unit: 'K', color: '#ff5a1f' },
    { id: 'Tmid', label: 'T centre', unit: 'K', color: '#ffd166' },
    { id: 'Tright', label: 'T extrémité froide', unit: 'K', color: '#3aa4ff' },
  ],
  initial: (p) => {
    const n = Math.max(2, Math.round(p.nodes))
    const T = new Array<number>(n).fill(p.tempCold)
    T[0] = p.tempHot
    return { q: T, v: new Array<number>(n).fill(0) }
  },
  // We model T' directly via "acceleration" semantics — v stays 0; we only use
  // the symplectic path's first-derivative-as-acceleration trick (Euler is fine
  // for parabolic PDEs at sub-CFL dt). Callers should use the explicit step:
  // here we return ∂T/∂t in the "acceleration" slot and update q ← q + a*dt
  // via the dedicated stepDiffusion() helper exported below.
  acceleration: (p) => (_t, q) => {
    const n = q.length
    const dx = p.length / (n - 1)
    const out = new Array<number>(n).fill(0)
    for (let i = 1; i < n - 1; i += 1) {
      out[i] = (p.alpha * (q[i - 1] - 2 * q[i] + q[i + 1])) / (dx * dx)
    }
    // Dirichlet BCs: ends held fixed (achieved by leaving out[0]=out[n-1]=0).
    return out
  },
  energy: () => () => ({ kinetic: 0, potential: 0 }),
  sample: (_p, _t, q) => ({
    Tleft: q[0],
    Tmid: q[Math.floor(q.length / 2)],
    Tright: q[q.length - 1],
  }),
}

/** Explicit forward-Euler step for parabolic PDEs (heat equation). */
export function stepDiffusion(phen: AnalyticPhenomenon, params: Record<string, number>, T: number[], dt: number): number[] {
  const accel = phen.acceleration(params)
  const dT = accel(0, T, T.map(() => 0))
  return T.map((v, i) => v + dT[i] * dt)
}

// --- Corde vibrante (équation d'onde 1D) ------------------------------------
// ∂²y/∂t² = c² ∂²y/∂x² avec c = √(T/μ) la célérité, conditions aux limites
// fixées y(0,t) = y(L,t) = 0. Discrétisation centrée d'ordre 2 en espace
// et velocity-Verlet en temps.
// État : y(x_i) pour i = 0..N-1, vy(x_i) pour i = 0..N-1.
const vibratingString: AnalyticPhenomenon = {
  id: 'vibrating-string',
  label: 'Corde vibrante (équation d\'onde 1D)',
  category: 'ondes',
  difficulty: 'avance',
  suggestedDt: 0.0001,
  suggestedDuration: 0.5,
  params: [
    { id: 'length', label: 'Longueur L', unit: 'm', min: 0.1, max: 2, step: 0.01, default: 0.5 },
    { id: 'nodes', label: 'Nœuds', unit: '', min: 16, max: 128, step: 1, default: 64, integer: true },
    { id: 'celerity', label: 'Célérité c', unit: 'm/s', min: 10, max: 600, step: 1, default: 200 },
    { id: 'damping', label: 'Amortissement', unit: '1/s', min: 0, max: 5, step: 0.05, default: 0.5 },
    { id: 'pluckPos', label: 'Position du pincement', unit: '', min: 0.1, max: 0.9, step: 0.01, default: 0.3 },
    { id: 'pluckAmp', label: 'Amplitude pincement', unit: 'm', min: 0.001, max: 0.05, step: 0.001, default: 0.01 },
  ],
  didactic: {
    equationsTex: [
      '\\dfrac{\\partial^{2} y}{\\partial t^{2}} = c^{2} \\dfrac{\\partial^{2} y}{\\partial x^{2}} - 2\\gamma \\dfrac{\\partial y}{\\partial t}',
      'f_{n} = \\dfrac{n c}{2L}, \\quad n = 1, 2, 3, \\dots',
      'CFL : c \\Delta t \\le \\Delta x',
    ],
    hint: 'Modes propres d\'une corde de longueur L. f1 fondamentale, f2 octave, etc.',
    programReferences: ['Terminale STI2D — ondes mécaniques progressives'],
  },
  channels: [
    { id: 'yMid', label: 'Déplacement milieu', unit: 'm', color: '#3aa4ff' },
    { id: 'vyMid', label: 'Vitesse milieu', unit: 'm/s', color: '#ff5a1f' },
    { id: 'yQuarter', label: 'Déplacement L/4', unit: 'm', color: '#ffd166' },
    { id: 'energy', label: 'Énergie totale (relative)', unit: 'J', color: '#ffffff' },
  ],
  initial: (p) => {
    const n = Math.max(8, Math.round(p.nodes))
    const y = new Array<number>(n).fill(0)
    const vy = new Array<number>(n).fill(0)
    // Pincement triangulaire à pluckPos
    const pluckIdx = Math.max(1, Math.min(n - 2, Math.round(p.pluckPos * (n - 1))))
    for (let i = 0; i < n; i += 1) {
      if (i <= pluckIdx) y[i] = (p.pluckAmp * i) / pluckIdx
      else y[i] = (p.pluckAmp * (n - 1 - i)) / (n - 1 - pluckIdx)
    }
    y[0] = 0
    y[n - 1] = 0
    return { q: y, v: vy }
  },
  acceleration: (p) => (_t, q, v) => {
    const n = q.length
    const dx = p.length / (n - 1)
    const c2 = p.celerity * p.celerity
    const out = new Array<number>(n).fill(0)
    for (let i = 1; i < n - 1; i += 1) {
      out[i] = (c2 * (q[i - 1] - 2 * q[i] + q[i + 1])) / (dx * dx) - 2 * p.damping * v[i]
    }
    // Dirichlet BCs : extrémités fixées.
    return out
  },
  energy: (p) => (_t, q, v) => {
    // E = ½ μ Σ vy² dx + ½ T Σ (dy/dx)² dx, μ = 1 (relative).
    const n = q.length
    const dx = p.length / (n - 1)
    let kinetic = 0
    let potential = 0
    for (let i = 0; i < n; i += 1) kinetic += v[i] * v[i]
    kinetic *= 0.5 * dx
    for (let i = 0; i < n - 1; i += 1) {
      const slope = (q[i + 1] - q[i]) / dx
      potential += slope * slope
    }
    potential *= 0.5 * p.celerity * p.celerity * dx
    return { kinetic, potential }
  },
  sample: (p, _t, q, v) => {
    const mid = Math.floor(q.length / 2)
    const quarter = Math.floor(q.length / 4)
    const e = vibratingString.energy(p)(_t, q, v)
    return {
      yMid: q[mid],
      vyMid: v[mid],
      yQuarter: q[quarter],
      energy: e.kinetic + e.potential,
    }
  },
}

// --- Doppler 1D : observateur fixe, source mobile ---------------------------
// f' = f * c / (c - v_s)  (source approchant) ; f * c / (c + v_s) (s'éloigne)
// État : position et vitesse de la source, fréquence émise, fréquence perçue.
const dopplerSourceMoving: AnalyticPhenomenon = {
  id: 'doppler-1d',
  label: 'Effet Doppler — source mobile, observateur fixe',
  category: 'ondes',
  difficulty: 'intermediaire',
  suggestedDt: 0.005,
  suggestedDuration: 8,
  params: [
    { id: 'c', label: 'Célérité du son', unit: 'm/s', min: 100, max: 1500, step: 1, default: 343 },
    { id: 'fSource', label: 'Fréquence émise', unit: 'Hz', min: 50, max: 4000, step: 1, default: 440 },
    { id: 'vSource', label: 'Vitesse source', unit: 'm/s', min: -100, max: 100, step: 0.1, default: 25 },
    { id: 'xObserver', label: 'Position observateur', unit: 'm', min: 0, max: 200, step: 0.5, default: 100 },
    { id: 'xSourceInit', label: 'Position source initiale', unit: 'm', min: -200, max: 200, step: 0.5, default: -50 },
  ],
  didactic: {
    equationsTex: [
      "f' = f \\cdot \\dfrac{c}{c - v_{s,r}}",
      "v_{s,r} = \\vec{v}_{s} \\cdot \\hat{r}_{s \\to o}",
    ],
    hint: 'Source qui s\'approche : f\' > f. Source qui s\'éloigne : f\' < f.',
    programReferences: ['Terminale STI2D — Doppler', 'Première — application acoustique'],
  },
  channels: [
    { id: 'xSource', label: 'Position source', unit: 'm', color: '#3aa4ff' },
    { id: 'fPerceived', label: 'Fréquence perçue', unit: 'Hz', color: '#ff5a1f' },
    { id: 'deltaF', label: 'Δf', unit: 'Hz', color: '#ffd166' },
    { id: 'distance', label: 'Distance source-observateur', unit: 'm', color: '#37c7bf' },
  ],
  initial: (p) => ({ q: [p.xSourceInit], v: [p.vSource] }),
  acceleration: () => () => [0], // vitesse constante
  energy: () => () => ({ kinetic: 0, potential: 0 }), // non-conservatif sur cet observable
  sample: (p, _t, q, v) => {
    const xs = q[0]
    const vs = v[0]
    const distance = Math.abs(p.xObserver - xs)
    // Composante radiale de la vitesse source vers l'observateur :
    const sign = p.xObserver - xs >= 0 ? 1 : -1
    const vRadial = vs * sign // +ve = approche, -ve = s'éloigne
    // f' = f * c / (c - vRadial)
    const denom = p.c - vRadial
    const fPerceived = Math.abs(denom) > 1e-6 ? (p.fSource * p.c) / denom : p.fSource
    return {
      xSource: xs,
      fPerceived,
      deltaF: fPerceived - p.fSource,
      distance,
    }
  },
}

// --- Lentille mince — formule de conjugaison --------------------------------
// 1/d_image - 1/d_object = 1/f (convention algébrique)
// État : position object, position image, grandissement (sortie statique).
// Note : ce phénomène est ÉTATIQUE — pas d'intégration, juste un calcul
// dépendant des params. On utilise advance() comme "step" mais l'état reste
// identique. Pédagogique.
const thinLens: AnalyticPhenomenon = {
  id: 'thin-lens',
  label: 'Lentille mince (conjugaison)',
  category: 'optique',
  difficulty: 'debutant',
  suggestedDt: 0.05,
  suggestedDuration: 3, // pour avoir quelques samples graphés sur les sliders
  params: [
    { id: 'focal', label: 'Focale f', unit: 'm', min: -1, max: 1, step: 0.005, default: 0.1 },
    { id: 'objectDistance', label: 'Distance objet d_o (algébrique)', unit: 'm', min: -2, max: -0.05, step: 0.001, default: -0.2 },
    { id: 'objectHeight', label: 'Hauteur objet', unit: 'm', min: 0.001, max: 0.1, step: 0.001, default: 0.02 },
  ],
  didactic: {
    equationsTex: [
      '\\dfrac{1}{d_{i}} - \\dfrac{1}{d_{o}} = \\dfrac{1}{f}',
      '\\gamma = -\\dfrac{d_{i}}{d_{o}}',
    ],
    hint: 'Convention : d_o algébrique négatif (objet à gauche). f > 0 : convergente.',
    programReferences: ['Première — optique géométrique', 'Terminale — instruments optiques'],
  },
  channels: [
    { id: 'di', label: 'Distance image d_i', unit: 'm', color: '#3aa4ff' },
    { id: 'gamma', label: 'Grandissement γ', unit: '', color: '#ff5a1f' },
    { id: 'imageHeight', label: 'Hauteur image', unit: 'm', color: '#ffd166' },
  ],
  initial: (p) => ({ q: [p.objectDistance], v: [0] }),
  acceleration: () => () => [0],
  energy: () => () => ({ kinetic: 0, potential: 0 }),
  sample: (p, _t, q) => {
    const dObj = q[0]
    // 1/di - 1/do = 1/f → di = 1 / (1/f + 1/do)
    const inv = 1 / p.focal + 1 / dObj
    const di = Math.abs(inv) > 1e-9 ? 1 / inv : Infinity
    const gamma = -di / dObj
    return {
      di,
      gamma,
      imageHeight: gamma * p.objectHeight,
    }
  },
}

// --- Catalogue --------------------------------------------------------------
export const ANALYTIC_PHENOMENA: readonly AnalyticPhenomenon[] = [
  pendulumSimple,
  dampedSpring,
  projectileDrag,
  rlcCircuit,
  doublePendulum,
  thermalRod,
  vibratingString,
  dopplerSourceMoving,
  thinLens,
]

export function getAnalyticPhenomenon(id: string): AnalyticPhenomenon | undefined {
  return ANALYTIC_PHENOMENA.find((p) => p.id === id)
}

// --- Theoretical references (used to display "expected period" badge) ------

/** Théorique petite oscillation : T = 2π√(L/g). Diverge à grand angle. */
export function pendulumPeriodSmallAngle(length: number, gravity: number): number {
  return 2 * Math.PI * Math.sqrt(length / gravity)
}

/** Période exacte par série elliptique (4ᵉ ordre en sin²(θ₀/2)). */
export function pendulumPeriodExact(length: number, gravity: number, theta0: number): number {
  const s = Math.sin(theta0 / 2)
  const s2 = s * s
  const T0 = pendulumPeriodSmallAngle(length, gravity)
  // K(k) ≈ (π/2)(1 + (1/4)k² + (9/64)k⁴ + …)
  return T0 * (1 + s2 / 4 + (9 / 64) * s2 * s2)
}

/** Pulsation propre RLC : ω₀ = 1/√(LC). */
export function rlcPulsation(L: number, C: number): number {
  return 1 / Math.sqrt(L * C)
}

/** Coefficient d'amortissement réduit ζ = R/2 · √(C/L). */
export function rlcZeta(R: number, L: number, C: number): number {
  return (R / 2) * Math.sqrt(C / L)
}

/** Vitesse limite (corps en chute libre avec drag quadratique). */
export function terminalVelocity(mass: number, gravity: number, rho: number, cd: number, area: number): number {
  if (cd * area * rho <= 0) return Infinity
  return Math.sqrt((2 * mass * gravity) / (rho * cd * area))
}

// re-export Coulomb constant in case callers want it
export const PHYSICS_CONSTANTS = {
  G_TERRE,
  COULOMB_K,
  C_LIGHT: 299_792_458,
  EPSILON_0: 8.854_187_8128e-12,
  MU_0: 1.256_637_062e-6,
  PLANCK: 6.626_070_15e-34,
  BOLTZMANN: 1.380_649e-23,
  ELEMENTARY_CHARGE: 1.602_176_634e-19,
  AVOGADRO: 6.022_140_76e23,
} as const
