import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Atom,
  Gauge,
  Pause,
  Play,
  RotateCcw,
  Sliders,
  Sparkles,
  Target,
  Wind,
  Zap,
} from 'lucide-react'
import { velocityVerlet } from '../../services/simulator/analyticIntegrators.ts'

type SimId = 'pendulum' | 'projectile' | 'spring' | 'collision' | 'gravity'

const SIMS: Array<{ id: SimId; label: string; color: string; icon: typeof Atom; tagline: string }> = [
  { id: 'pendulum', label: 'Pendule', color: 'from-cyan-400 to-blue-500', icon: Atom, tagline: 'Oscillations harmoniques' },
  { id: 'projectile', label: 'Projectile', color: 'from-orange-400 to-rose-500', icon: Target, tagline: 'Tir parabolique' },
  { id: 'spring', label: 'Ressort', color: 'from-emerald-400 to-teal-500', icon: Sparkles, tagline: 'Loi de Hooke' },
  { id: 'collision', label: 'Collisions', color: 'from-violet-400 to-purple-500', icon: Zap, tagline: 'Conservation P' },
  { id: 'gravity', label: 'Orbite', color: 'from-pink-400 to-fuchsia-500', icon: Wind, tagline: 'Loi de Kepler' },
]

export default function LabPhysics() {
  const [sim, setSim] = useState<SimId>('pendulum')

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Laboratoire de physique</div>
          <h1 className="text-3xl font-black gradient-text-ocean">Expériences interactives</h1>
          <p className="text-sm text-aurora-text-dim mt-1">Manipule les paramètres en temps réel — observe les lois de la nature.</p>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        {SIMS.map((s) => {
          const Icon = s.icon
          const active = s.id === sim
          return (
            <motion.button
              key={s.id}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setSim(s.id)}
              className={`relative shrink-0 rounded-2xl border p-3 pr-4 text-left min-w-[160px] transition-all ${
                active
                  ? 'border-cyan-400/50 bg-cyan-500/10 neon-outline-cyan'
                  : 'border-white/10 bg-white/5 hover:border-cyan-400/30'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`rounded-xl bg-gradient-to-br ${s.color} p-2 shadow-lg`}>
                  <Icon size={16} className="text-white" />
                </div>
                <div>
                  <div className={`text-sm font-bold ${active ? 'text-cyan-100' : 'text-aurora-text'}`}>{s.label}</div>
                  <div className="text-[10px] text-aurora-text-dim">{s.tagline}</div>
                </div>
              </div>
            </motion.button>
          )
        })}
      </div>

      {sim === 'pendulum' && <PendulumSim />}
      {sim === 'projectile' && <ProjectileSim />}
      {sim === 'spring' && <SpringSim />}
      {sim === 'collision' && <CollisionSim />}
      {sim === 'gravity' && <GravitySim />}
    </div>
  )
}

// =====================================================================
// SLIDER COMPONENT
// =====================================================================

function LabSlider({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
  color = 'cyan',
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit?: string
  onChange: (v: number) => void
  color?: 'cyan' | 'violet' | 'emerald' | 'orange' | 'pink'
}) {
  const colorMap = {
    cyan: 'from-cyan-400 to-blue-500',
    violet: 'from-violet-400 to-purple-500',
    emerald: 'from-emerald-400 to-teal-500',
    orange: 'from-orange-400 to-rose-500',
    pink: 'from-pink-400 to-fuchsia-500',
  }
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-aurora-text-muted">{label}</span>
        <span className={`font-mono font-bold text-${color === 'cyan' ? 'cyan' : color === 'violet' ? 'violet' : color === 'emerald' ? 'emerald' : color === 'orange' ? 'orange' : 'pink'}-300`}>
          {value.toFixed(step < 1 ? 2 : 0)}{unit ? ` ${unit}` : ''}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-white/8 overflow-hidden border border-white/5">
        <div
          className={`absolute left-0 top-0 h-full bg-gradient-to-r ${colorMap[color]} transition-all`}
          style={{ width: `${pct}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="absolute inset-0 w-full opacity-0 cursor-pointer"
        />
      </div>
    </div>
  )
}

function PlayBar({ playing, onToggle, onReset }: { playing: boolean; onToggle: () => void; onReset: () => void }) {
  return (
    <div className="flex items-center gap-2">
      <button onClick={onToggle} className="btn-aurora text-sm py-2 px-4">
        {playing ? <><Pause size={14} /> Pause</> : <><Play size={14} /> Lancer</>}
      </button>
      <button onClick={onReset} className="btn-ghost">
        <RotateCcw size={14} /> Reset
      </button>
    </div>
  )
}

// =====================================================================
// PENDULUM
// =====================================================================

function PendulumSim() {
  const [length, setLength] = useState(180)
  const [gravity, setGravity] = useState(9.81)
  const [damping, setDamping] = useState(0.005)
  const [angle0, setAngle0] = useState(35)
  const [playing, setPlaying] = useState(true)

  const angleRef = useRef((angle0 * Math.PI) / 180)
  const angleVRef = useRef(0)
  const [renderAngle, setRenderAngle] = useState(angleRef.current)
  const lastT = useRef(performance.now())
  // Fixed-dt accumulator — guarantees the same trajectory no matter the
  // frame rate (CLAUDE.md hard rule: "Don't use frame-time as dt — sim
  // explodes on lag").
  const accumRef = useRef(0)
  const reqRef = useRef<number>(0)
  const FIXED_DT = 1 / 240

  const reset = () => {
    angleRef.current = (angle0 * Math.PI) / 180
    angleVRef.current = 0
    accumRef.current = 0
    setRenderAngle(angleRef.current)
  }

  useEffect(() => { reset() }, [angle0])

  useEffect(() => {
    const tick = (t: number) => {
      const frameDt = Math.min(0.05, (t - lastT.current) / 1000)
      lastT.current = t
      if (playing) {
        accumRef.current += frameDt
        const L = length / 100
        // Velocity-Verlet (symplectic, 2nd-order) — bounded energy drift
        // across long sessions, where the previous semi-implicit Euler grew
        // energy by ~5%/s at large amplitudes.
        const accel = (_t: number, q: readonly number[], v: readonly number[]) => [
          -(gravity / L) * Math.sin(q[0]) - damping * v[0],
        ]
        let steps = 0
        while (accumRef.current >= FIXED_DT && steps < 32) {
          const step = velocityVerlet(accel, 0, [angleRef.current], [angleVRef.current], FIXED_DT)
          angleRef.current = step.q[0]
          angleVRef.current = step.v[0]
          accumRef.current -= FIXED_DT
          steps += 1
        }
        setRenderAngle(angleRef.current)
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, gravity, length, damping])

  const period = 2 * Math.PI * Math.sqrt((length / 100) / gravity)

  return (
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[420px]">
        <div className="absolute inset-0 dot-grid opacity-20" />
        <svg viewBox="-200 -20 400 460" className="w-full h-full relative">
          {/* Support */}
          <rect x="-60" y="-15" width="120" height="10" rx="3" fill="#475569" />
          <rect x="-2" y="-5" width="4" height="10" fill="#94a3b8" />
          <line x1="0" y1="0" x2="0" y2={length} stroke="#cbd5e1" strokeWidth="1.5" opacity="0.4" strokeDasharray="3 2" />
          <line
            x1="0" y1="0"
            x2={length * Math.sin(renderAngle)}
            y2={length * Math.cos(renderAngle)}
            stroke="url(#wireGrad)"
            strokeWidth="2.5"
          />
          <defs>
            <linearGradient id="wireGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="100%" stopColor="#a78bfa" />
            </linearGradient>
            <radialGradient id="ballGrad">
              <stop offset="0%" stopColor="#fde047" />
              <stop offset="60%" stopColor="#fb923c" />
              <stop offset="100%" stopColor="#ec4899" />
            </radialGradient>
          </defs>
          <circle
            cx={length * Math.sin(renderAngle)}
            cy={length * Math.cos(renderAngle)}
            r="22"
            fill="url(#ballGrad)"
            filter="drop-shadow(0 0 14px rgba(251,146,60,0.55))"
          />
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-cyan-300" /> Paramètres
          </h3>
          <LabSlider label="Longueur" value={length} min={50} max={300} step={5} unit="cm" onChange={setLength} color="cyan" />
          <LabSlider label="Gravité g" value={gravity} min={1} max={25} step={0.1} unit="m/s²" onChange={setGravity} color="violet" />
          <LabSlider label="Amortissement" value={damping} min={0} max={0.1} step={0.001} onChange={setDamping} color="orange" />
          <LabSlider label="Angle initial" value={angle0} min={5} max={80} step={1} unit="°" onChange={setAngle0} color="pink" />
          <PlayBar playing={playing} onToggle={() => setPlaying((p) => !p)} onReset={reset} />
        </div>
        <div className="holo-card holo-card-cyan p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-cyan-300">Mesures</h4>
          <Stat label="Période T = 2π·√(L/g)" value={`${period.toFixed(2)} s`} />
          <Stat label="Fréquence f = 1/T" value={`${(1 / period).toFixed(2)} Hz`} />
          <Stat label="Angle actuel" value={`${((renderAngle * 180) / Math.PI).toFixed(1)}°`} />
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-aurora-text-dim">{label}</span>
      <span className="font-mono font-bold text-aurora-text">{value}</span>
    </div>
  )
}

// =====================================================================
// PROJECTILE
// =====================================================================

function ProjectileSim() {
  const [v0, setV0] = useState(40)
  const [angle, setAngle] = useState(45)
  const [g, setG] = useState(9.81)
  const [playing, setPlaying] = useState(true)
  const [t, setT] = useState(0)

  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const trajectory = useMemo(() => {
    const points: Array<{ x: number; y: number }> = []
    const rad = (angle * Math.PI) / 180
    const vx = v0 * Math.cos(rad)
    const vy = v0 * Math.sin(rad)
    const tFlight = (2 * vy) / g
    for (let i = 0; i <= 60; i++) {
      const tt = (i / 60) * tFlight
      points.push({ x: vx * tt, y: vy * tt - 0.5 * g * tt * tt })
    }
    return { points, tFlight, vx, vy, range: vx * tFlight, hMax: (vy * vy) / (2 * g) }
  }, [v0, angle, g])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        setT((p) => {
          const next = p + dt
          if (next >= trajectory.tFlight) return 0
          return next
        })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, trajectory.tFlight])

  const x = trajectory.vx * t
  const y = trajectory.vy * t - 0.5 * g * t * t

  // Scale to viewport
  const xScale = 400 / Math.max(1, trajectory.range)
  const yScale = 200 / Math.max(1, trajectory.hMax)

  return (
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[420px]">
        <svg viewBox="-20 -240 480 280" className="w-full h-full">
          <defs>
            <linearGradient id="trailGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#fb923c" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0.9" />
            </linearGradient>
          </defs>
          {/* Ground */}
          <line x1="-20" y1="0" x2="460" y2="0" stroke="#475569" strokeWidth="1.5" />
          {/* Grid */}
          {Array.from({ length: 9 }).map((_, i) => (
            <line key={`vx-${i}`} x1={i * 50} y1="0" x2={i * 50} y2="-220" stroke="rgba(255,255,255,0.03)" />
          ))}
          {Array.from({ length: 5 }).map((_, i) => (
            <line key={`hy-${i}`} x1="-20" y1={-i * 50} x2="460" y2={-i * 50} stroke="rgba(255,255,255,0.03)" />
          ))}

          {/* Trajectory */}
          <polyline
            points={trajectory.points.map((p) => `${p.x * xScale},${-p.y * yScale}`).join(' ')}
            fill="none"
            stroke="url(#trailGrad)"
            strokeWidth="2"
            strokeDasharray="3 3"
            opacity="0.6"
          />
          {/* Cannon */}
          <g transform={`rotate(${-angle}) translate(0, -8)`}>
            <rect x="0" y="0" width="32" height="14" rx="3" fill="#a78bfa" />
          </g>
          <circle cx="0" cy="0" r="10" fill="#475569" />

          {/* Projectile */}
          <circle cx={x * xScale} cy={-y * yScale} r="9" fill="url(#ballGrad2)" filter="drop-shadow(0 0 12px rgba(251,146,60,0.6))" />
          <defs>
            <radialGradient id="ballGrad2">
              <stop offset="0%" stopColor="#fde047" />
              <stop offset="60%" stopColor="#fb923c" />
              <stop offset="100%" stopColor="#ec4899" />
            </radialGradient>
          </defs>
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-orange-300" /> Paramètres
          </h3>
          <LabSlider label="Vitesse initiale v₀" value={v0} min={10} max={100} step={1} unit="m/s" onChange={setV0} color="orange" />
          <LabSlider label="Angle θ" value={angle} min={5} max={85} step={1} unit="°" onChange={setAngle} color="pink" />
          <LabSlider label="Gravité g" value={g} min={1} max={25} step={0.1} unit="m/s²" onChange={setG} color="violet" />
          <PlayBar playing={playing} onToggle={() => setPlaying((p) => !p)} onReset={() => setT(0)} />
        </div>
        <div className="holo-card holo-card-warm p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-orange-300">Résultats</h4>
          <Stat label="Portée X = v₀²·sin(2θ)/g" value={`${trajectory.range.toFixed(1)} m`} />
          <Stat label="Hauteur max" value={`${trajectory.hMax.toFixed(1)} m`} />
          <Stat label="Temps de vol" value={`${trajectory.tFlight.toFixed(2)} s`} />
          <Stat label="Vitesse horiz." value={`${trajectory.vx.toFixed(1)} m/s`} />
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// SPRING (Hooke / mass-spring system)
// =====================================================================

function SpringSim() {
  const [k, setK] = useState(20)
  const [m, setM] = useState(1)
  const [x0, setX0] = useState(60)
  const [damp, setDamp] = useState(0.4)
  const [playing, setPlaying] = useState(true)

  const xRef = useRef(x0)
  const vRef = useRef(0)
  const [renderX, setRenderX] = useState(x0)
  const accumRef = useRef(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())
  const FIXED_DT = 1 / 240

  useEffect(() => {
    xRef.current = x0
    vRef.current = 0
    accumRef.current = 0
    setRenderX(x0)
  }, [x0])

  useEffect(() => {
    const tick = (now: number) => {
      const frameDt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        accumRef.current += frameDt
        // Velocity-Verlet on the damped harmonic oscillator m x'' + b x' + k x = 0.
        // Pixel-space scaling preserved (the original used raw px×k coefficients
        // and we keep the same convention to avoid changing on-screen amplitude).
        const accel = (_t: number, q: readonly number[], v: readonly number[]) => [
          (-k * q[0] - damp * v[0]) / m,
        ]
        let steps = 0
        while (accumRef.current >= FIXED_DT && steps < 32) {
          const step = velocityVerlet(accel, 0, [xRef.current], [vRef.current], FIXED_DT)
          xRef.current = step.q[0]
          vRef.current = step.v[0]
          accumRef.current -= FIXED_DT
          steps += 1
        }
        setRenderX(xRef.current)
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, k, m, damp])

  const omega = Math.sqrt(k / m)
  const period = (2 * Math.PI) / omega

  // SVG spring representation: zigzag scaled with stretch
  const baseX = 80
  const massX = baseX + 200 + renderX
  const coils = 12
  const springPath = useMemo(() => {
    const length = massX - baseX - 24
    const segLen = length / coils
    let d = `M ${baseX} 200 `
    for (let i = 0; i < coils; i++) {
      const sx = baseX + i * segLen
      const sy = i % 2 === 0 ? 188 : 212
      d += `L ${sx + segLen / 2} ${sy} `
    }
    d += `L ${massX - 24} 200 `
    return d
  }, [renderX, massX])

  return (
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 460 360" className="w-full h-full">
          {/* Wall */}
          <rect x="60" y="100" width="20" height="200" fill="#475569" />
          <line x1="80" y1="100" x2="80" y2="300" stroke="#94a3b8" strokeWidth="1" />
          {/* Floor */}
          <line x1="60" y1="240" x2="440" y2="240" stroke="#475569" strokeWidth="1" />
          {/* Spring */}
          <path d={springPath} fill="none" stroke="url(#springGrad)" strokeWidth="2.5" />
          <defs>
            <linearGradient id="springGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
          {/* Mass */}
          <rect x={massX - 24} y={170} width="48" height="48" rx="6" fill="url(#massGrad)" filter="drop-shadow(0 0 14px rgba(52,211,153,0.45))" />
          <defs>
            <linearGradient id="massGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#a78bfa" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
          </defs>
          <text x={massX} y="200" textAnchor="middle" className="fill-white text-[13px] font-bold" fontFamily="JetBrains Mono">{m.toFixed(1)} kg</text>
          {/* Equilibrium line */}
          <line x1={baseX + 200} y1="160" x2={baseX + 200} y2="240" stroke="rgba(255,255,255,0.25)" strokeDasharray="3 3" />
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-emerald-300" /> Paramètres
          </h3>
          <LabSlider label="Raideur k" value={k} min={5} max={100} step={1} unit="N/m" onChange={setK} color="emerald" />
          <LabSlider label="Masse m" value={m} min={0.1} max={5} step={0.1} unit="kg" onChange={setM} color="cyan" />
          <LabSlider label="Étirement initial x₀" value={x0} min={-100} max={100} step={1} unit="px" onChange={setX0} color="violet" />
          <LabSlider label="Amortissement" value={damp} min={0} max={5} step={0.1} onChange={setDamp} color="orange" />
          <PlayBar playing={playing} onToggle={() => setPlaying((p) => !p)} onReset={() => { xRef.current = x0; vRef.current = 0; setRenderX(x0) }} />
        </div>
        <div className="holo-card holo-card-cyan p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-emerald-300">Mesures</h4>
          <Stat label="Pulsation ω = √(k/m)" value={`${omega.toFixed(2)} rad/s`} />
          <Stat label="Période T" value={`${period.toFixed(2)} s`} />
          <Stat label="x(t)" value={`${renderX.toFixed(1)} px`} />
          <Stat label="Force F = -k·x" value={`${(-k * renderX).toFixed(1)} N`} />
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// COLLISIONS (1D élastique / inélastique)
// =====================================================================

function CollisionSim() {
  const [m1, setM1] = useState(1)
  const [m2, setM2] = useState(2)
  const [v1, setV1] = useState(40)
  const [v2, setV2] = useState(-10)
  const [elastic, setElastic] = useState(true)
  const [playing, setPlaying] = useState(true)

  const x1Ref = useRef(50)
  const x2Ref = useRef(360)
  const v1Ref = useRef(v1)
  const v2Ref = useRef(v2)
  const [renderX, setRenderX] = useState({ a: 50, b: 360 })
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const reset = () => {
    x1Ref.current = 50
    x2Ref.current = 360
    v1Ref.current = v1
    v2Ref.current = v2
    setRenderX({ a: 50, b: 360 })
  }
  useEffect(() => { reset() }, [v1, v2])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.04, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        x1Ref.current += v1Ref.current * dt
        x2Ref.current += v2Ref.current * dt
        const r1 = 18 + m1 * 4
        const r2 = 18 + m2 * 4
        // Collision detection
        if (x2Ref.current - x1Ref.current <= r1 + r2 && v1Ref.current > v2Ref.current) {
          if (elastic) {
            const nv1 = ((m1 - m2) * v1Ref.current + 2 * m2 * v2Ref.current) / (m1 + m2)
            const nv2 = ((m2 - m1) * v2Ref.current + 2 * m1 * v1Ref.current) / (m1 + m2)
            v1Ref.current = nv1
            v2Ref.current = nv2
          } else {
            const v = (m1 * v1Ref.current + m2 * v2Ref.current) / (m1 + m2)
            v1Ref.current = v
            v2Ref.current = v
          }
        }
        // Walls
        if (x1Ref.current < 30) v1Ref.current = Math.abs(v1Ref.current)
        if (x2Ref.current > 430) v2Ref.current = -Math.abs(v2Ref.current)
        setRenderX({ a: x1Ref.current, b: x2Ref.current })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, m1, m2, elastic])

  const r1 = 18 + m1 * 4
  const r2 = 18 + m2 * 4
  const p = m1 * v1Ref.current + m2 * v2Ref.current
  const ke = 0.5 * m1 * v1Ref.current ** 2 + 0.5 * m2 * v2Ref.current ** 2

  return (
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[280px]">
        <svg viewBox="0 0 460 200" className="w-full h-full">
          <line x1="20" y1="170" x2="440" y2="170" stroke="#475569" strokeWidth="2" />
          <rect x="20" y="40" width="6" height="130" fill="#94a3b8" />
          <rect x="434" y="40" width="6" height="130" fill="#94a3b8" />
          <circle cx={renderX.a} cy="110" r={r1} fill="url(#bGrad1)" filter="drop-shadow(0 0 16px rgba(34,211,238,0.45))" />
          <circle cx={renderX.b} cy="110" r={r2} fill="url(#bGrad2)" filter="drop-shadow(0 0 16px rgba(236,72,153,0.45))" />
          <text x={renderX.a} y="115" textAnchor="middle" className="fill-white text-[11px] font-bold">{m1}</text>
          <text x={renderX.b} y="115" textAnchor="middle" className="fill-white text-[11px] font-bold">{m2}</text>
          <defs>
            <radialGradient id="bGrad1"><stop offset="0%" stopColor="#67e8f9"/><stop offset="100%" stopColor="#0891b2"/></radialGradient>
            <radialGradient id="bGrad2"><stop offset="0%" stopColor="#f9a8d4"/><stop offset="100%" stopColor="#be185d"/></radialGradient>
          </defs>
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-violet-300" /> Paramètres
          </h3>
          <LabSlider label="Masse 1" value={m1} min={0.5} max={6} step={0.5} unit="kg" onChange={setM1} color="cyan" />
          <LabSlider label="Masse 2" value={m2} min={0.5} max={6} step={0.5} unit="kg" onChange={setM2} color="pink" />
          <LabSlider label="Vitesse 1" value={v1} min={-100} max={100} step={5} unit="px/s" onChange={setV1} color="cyan" />
          <LabSlider label="Vitesse 2" value={v2} min={-100} max={100} step={5} unit="px/s" onChange={setV2} color="pink" />
          <div className="flex items-center gap-2">
            <button
              onClick={() => setElastic(true)}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${elastic ? 'border-violet-400 bg-violet-500/15 text-violet-100' : 'border-white/10 bg-white/5 text-aurora-text-dim'}`}
            >
              Élastique
            </button>
            <button
              onClick={() => setElastic(false)}
              className={`flex-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${!elastic ? 'border-orange-400 bg-orange-500/15 text-orange-100' : 'border-white/10 bg-white/5 text-aurora-text-dim'}`}
            >
              Inélastique
            </button>
          </div>
          <PlayBar playing={playing} onToggle={() => setPlaying((p) => !p)} onReset={reset} />
        </div>
        <div className="holo-card p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-violet-300">Conservation</h4>
          <Stat label="P = m₁v₁ + m₂v₂" value={`${p.toFixed(1)}`} />
          <Stat label="Ec = ½m₁v₁² + ½m₂v₂²" value={`${ke.toFixed(1)} J`} />
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// GRAVITY ORBIT (2-body)
// =====================================================================

function GravitySim() {
  const [GM, setGM] = useState(8000)
  const [r0, setR0] = useState(120)
  const [v0, setV0] = useState(8)
  const [playing, setPlaying] = useState(true)

  const ref = useRef({ x: r0, y: 0, vx: 0, vy: v0, trail: [] as Array<[number, number]> })
  const [render, setRender] = useState({ x: r0, y: 0, trail: [] as Array<[number, number]> })
  const lastT = useRef(performance.now())
  const reqRef = useRef<number>(0)

  const reset = () => {
    ref.current = { x: r0, y: 0, vx: 0, vy: v0, trail: [] }
    setRender({ x: r0, y: 0, trail: [] })
  }
  useEffect(() => { reset() }, [r0, v0])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.04, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        const s = ref.current
        const r = Math.sqrt(s.x * s.x + s.y * s.y)
        const a = -GM / (r * r * r)
        s.vx += a * s.x * dt
        s.vy += a * s.y * dt
        s.x += s.vx * dt
        s.y += s.vy * dt
        if (s.trail.length === 0 || Math.hypot(s.x - s.trail[s.trail.length - 1][0], s.y - s.trail[s.trail.length - 1][1]) > 3) {
          s.trail.push([s.x, s.y])
          if (s.trail.length > 200) s.trail.shift()
        }
        setRender({ x: s.x, y: s.y, trail: [...s.trail] })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, GM])

  return (
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[420px]">
        <svg viewBox="-220 -220 440 440" className="w-full h-full">
          {/* Stars */}
          {Array.from({ length: 30 }).map((_, i) => (
            <circle key={i} cx={(Math.random() - 0.5) * 400} cy={(Math.random() - 0.5) * 400} r={Math.random() * 0.7} fill="white" opacity={0.6} />
          ))}
          {/* Trail */}
          {render.trail.length > 1 && (
            <polyline
              points={render.trail.map(([x, y]) => `${x},${y}`).join(' ')}
              fill="none"
              stroke="url(#orbitGrad)"
              strokeWidth="1.4"
              opacity="0.6"
            />
          )}
          <defs>
            <linearGradient id="orbitGrad">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity="0" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="1" />
            </linearGradient>
            <radialGradient id="sunGrad">
              <stop offset="0%" stopColor="#fef9c3" />
              <stop offset="50%" stopColor="#fb923c" />
              <stop offset="100%" stopColor="#dc2626" />
            </radialGradient>
            <radialGradient id="planetGrad">
              <stop offset="0%" stopColor="#67e8f9" />
              <stop offset="100%" stopColor="#3b82f6" />
            </radialGradient>
          </defs>
          {/* Sun */}
          <circle cx="0" cy="0" r="20" fill="url(#sunGrad)" filter="drop-shadow(0 0 30px rgba(251,146,60,0.7))" />
          {/* Planet */}
          <circle cx={render.x} cy={render.y} r="7" fill="url(#planetGrad)" filter="drop-shadow(0 0 12px rgba(34,211,238,0.7))" />
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-pink-300" /> Paramètres
          </h3>
          <LabSlider label="GM" value={GM} min={2000} max={20000} step={500} onChange={setGM} color="orange" />
          <LabSlider label="Distance r₀" value={r0} min={60} max={200} step={5} onChange={setR0} color="cyan" />
          <LabSlider label="Vitesse tangentielle v₀" value={v0} min={2} max={15} step={0.5} onChange={setV0} color="pink" />
          <PlayBar playing={playing} onToggle={() => setPlaying((p) => !p)} onReset={reset} />
        </div>
        <div className="holo-card holo-card-pink p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-pink-300">Lois de Kepler</h4>
          <p className="text-xs text-aurora-text-dim leading-relaxed">
            Les planètes décrivent des ellipses dont le Soleil est l'un des foyers.
            La vitesse augmente près du périhélie et chute à l'aphélie.
          </p>
        </div>
      </div>
    </div>
  )
}
