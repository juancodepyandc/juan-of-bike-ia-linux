import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Calculator, Compass, Pi, Sigma, Sliders, Sparkles, Target } from 'lucide-react'

type Mode = 'plotter' | 'geometry' | 'fourier'

export default function LabMath() {
  const [mode, setMode] = useState<Mode>('plotter')
  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Lab mathématique</div>
          <h1 className="text-3xl font-black gradient-text">Plotter · Géométrie · Fourier</h1>
        </div>
        <div className="flex gap-1.5 p-1 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
          <button onClick={() => setMode('plotter')} className={`btn-pill ${mode === 'plotter' ? 'is-active' : ''}`}>
            <Sigma size={12} /> Plotter
          </button>
          <button onClick={() => setMode('geometry')} className={`btn-pill ${mode === 'geometry' ? 'is-active' : ''}`}>
            <Compass size={12} /> Géométrie
          </button>
          <button onClick={() => setMode('fourier')} className={`btn-pill ${mode === 'fourier' ? 'is-active' : ''}`}>
            <Pi size={12} /> Fourier
          </button>
        </div>
      </div>

      {mode === 'plotter' && <FunctionPlotter />}
      {mode === 'geometry' && <GeometryLab />}
      {mode === 'fourier' && <FourierLab />}
    </div>
  )
}

// =====================================================================
// FUNCTION PLOTTER — sin/cos/poly with sliders
// =====================================================================

const PRESETS: Array<{ id: string; label: string; fn: (x: number, a: number, b: number, c: number) => number; eq: string }> = [
  { id: 'sin', label: 'Sinusoïde', fn: (x, a, b, c) => a * Math.sin(b * x + c), eq: 'a · sin(b·x + c)' },
  { id: 'parab', label: 'Parabole', fn: (x, a, b, c) => a * x * x + b * x + c, eq: 'a·x² + b·x + c' },
  { id: 'expo', label: 'Exponentielle', fn: (x, a, b, c) => a * Math.exp(b * x) + c, eq: 'a·eᵇˣ + c' },
  { id: 'log', label: 'Logarithme', fn: (x, a, b, c) => a * Math.log(Math.abs(b * x) + 0.0001) + c, eq: 'a·ln(b·x) + c' },
  { id: 'tan', label: 'Tangente', fn: (x, a, b, c) => a * Math.tan(b * x) + c, eq: 'a · tan(b·x) + c' },
  { id: 'cubic', label: 'Cubique', fn: (x, a, b, c) => a * x ** 3 + b * x + c, eq: 'a·x³ + b·x + c' },
]

function FunctionPlotter() {
  const [presetId, setPresetId] = useState('sin')
  const [a, setA] = useState(1)
  const [b, setB] = useState(1)
  const [c, setC] = useState(0)
  const [zoom, setZoom] = useState(1)

  const preset = PRESETS.find((p) => p.id === presetId)!
  const W = 600
  const H = 400
  const xRange = 8 / zoom
  const pxPerUnit = W / 2 / xRange

  const points = useMemo(() => {
    const pts: string[] = []
    for (let px = 0; px <= W; px += 2) {
      const x = (px - W / 2) / pxPerUnit
      const y = preset.fn(x, a, b, c)
      const py = H / 2 - y * pxPerUnit
      if (Math.abs(py) > 1e6) continue
      pts.push(`${px},${Math.max(-100, Math.min(H + 100, py))}`)
    }
    return pts.join(' ')
  }, [presetId, a, b, c, zoom, pxPerUnit])

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[420px]">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full">
          <defs>
            <linearGradient id="fnGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="50%" stopColor="#a78bfa" />
              <stop offset="100%" stopColor="#ec4899" />
            </linearGradient>
          </defs>
          {/* Grid */}
          {Array.from({ length: 17 }).map((_, i) => (
            <line key={`vx-${i}`} x1={i * (W / 16)} y1="0" x2={i * (W / 16)} y2={H} stroke="rgba(255,255,255,0.04)" />
          ))}
          {Array.from({ length: 11 }).map((_, i) => (
            <line key={`vy-${i}`} x1="0" y1={i * (H / 10)} x2={W} y2={i * (H / 10)} stroke="rgba(255,255,255,0.04)" />
          ))}
          {/* Axes */}
          <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
          <line x1={W / 2} y1="0" x2={W / 2} y2={H} stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
          {/* Axis labels */}
          {[-3, -2, -1, 1, 2, 3].map((n) => (
            <text key={n} x={W / 2 + n * pxPerUnit} y={H / 2 + 14} textAnchor="middle" className="fill-aurora-text-dim text-[9px]">{n}</text>
          ))}
          {/* Function */}
          <polyline
            points={points}
            fill="none"
            stroke="url(#fnGrad)"
            strokeWidth="2.5"
            filter="drop-shadow(0 0 6px rgba(167,139,250,0.5))"
          />
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-3">
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPresetId(p.id)}
                className={`rounded-xl border px-3 py-2.5 text-left transition-all ${p.id === presetId ? 'border-violet-400/60 bg-violet-500/15' : 'border-white/10 bg-white/5 hover:border-violet-400/30'}`}
              >
                <div className="text-xs font-semibold text-aurora-text">{p.label}</div>
                <div className="font-mono text-[10px] text-aurora-text-dim mt-0.5">{p.eq}</div>
              </button>
            ))}
          </div>
        </div>
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-violet-300" /> Paramètres
          </h3>
          <Slider label="a" value={a} min={-5} max={5} step={0.1} onChange={setA} color="violet" />
          <Slider label="b" value={b} min={-5} max={5} step={0.1} onChange={setB} color="cyan" />
          <Slider label="c" value={c} min={-5} max={5} step={0.1} onChange={setC} color="pink" />
          <Slider label="zoom" value={zoom} min={0.3} max={5} step={0.1} onChange={setZoom} color="emerald" />
        </div>
      </div>
    </div>
  )
}

function Slider({
  label, value, min, max, step, onChange, color = 'cyan',
}: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void
  color?: 'cyan' | 'violet' | 'pink' | 'emerald' | 'orange'
}) {
  const colorClass = {
    cyan: 'from-cyan-400 to-blue-500',
    violet: 'from-violet-400 to-purple-500',
    pink: 'from-pink-400 to-rose-500',
    emerald: 'from-emerald-400 to-teal-500',
    orange: 'from-orange-400 to-rose-500',
  }[color]
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-aurora-text-muted font-mono">{label}</span>
        <span className="font-mono font-bold text-aurora-text">{value.toFixed(step < 1 ? 2 : 0)}</span>
      </div>
      <div className="relative h-2 rounded-full bg-white/8 overflow-hidden border border-white/5">
        <div className={`absolute left-0 top-0 h-full bg-gradient-to-r ${colorClass}`} style={{ width: `${pct}%` }} />
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

// =====================================================================
// GEOMETRY — interactive triangle / circle
// =====================================================================

function GeometryLab() {
  const [a, setA] = useState(120)
  const [b, setB] = useState(160)
  const [angle, setAngle] = useState(60)
  const rad = (angle * Math.PI) / 180
  const c = Math.sqrt(a * a + b * b - 2 * a * b * Math.cos(rad))
  const area = 0.5 * a * b * Math.sin(rad)
  const perim = a + b + c

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[420px]">
        <svg viewBox="0 0 480 360" className="w-full h-full">
          <defs>
            <linearGradient id="triangleGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="rgba(167,139,250,0.25)" />
              <stop offset="100%" stopColor="rgba(34,211,238,0.20)" />
            </linearGradient>
          </defs>
          {/* Grid */}
          {Array.from({ length: 13 }).map((_, i) => (
            <line key={`g-${i}`} x1={i * 40} y1="0" x2={i * 40} y2="360" stroke="rgba(255,255,255,0.04)" />
          ))}
          {Array.from({ length: 10 }).map((_, i) => (
            <line key={`h-${i}`} x1="0" y1={i * 40} x2="480" y2={i * 40} stroke="rgba(255,255,255,0.04)" />
          ))}
          {/* Triangle */}
          {(() => {
            const A = { x: 100, y: 280 }
            const B = { x: A.x + a * 1.2, y: A.y }
            const C = { x: A.x + b * 1.2 * Math.cos(rad), y: A.y - b * 1.2 * Math.sin(rad) }
            return (
              <>
                <polygon points={`${A.x},${A.y} ${B.x},${B.y} ${C.x},${C.y}`} fill="url(#triangleGrad)" stroke="url(#fnGrad)" strokeWidth="2" />
                <defs>
                  <linearGradient id="fnGrad"><stop offset="0%" stopColor="#22d3ee"/><stop offset="100%" stopColor="#ec4899"/></linearGradient>
                </defs>
                <circle cx={A.x} cy={A.y} r="5" fill="#fde047" />
                <circle cx={B.x} cy={B.y} r="5" fill="#22d3ee" />
                <circle cx={C.x} cy={C.y} r="5" fill="#ec4899" />
                <text x={A.x - 14} y={A.y + 18} className="fill-yellow-300 text-[12px] font-bold">A</text>
                <text x={B.x + 8} y={B.y + 18} className="fill-cyan-300 text-[12px] font-bold">B</text>
                <text x={C.x - 6} y={C.y - 10} className="fill-pink-300 text-[12px] font-bold">C</text>
                <text x={(A.x + B.x) / 2} y={A.y + 22} textAnchor="middle" className="fill-aurora-text-muted text-[10px]">a = {a}</text>
                <text x={(A.x + C.x) / 2 - 14} y={(A.y + C.y) / 2} className="fill-aurora-text-muted text-[10px]">b = {b}</text>
                <text x={(B.x + C.x) / 2 + 8} y={(B.y + C.y) / 2} className="fill-aurora-text-muted text-[10px]">c = {c.toFixed(1)}</text>
                {/* Angle arc */}
                <path
                  d={`M ${A.x + 26} ${A.y} A 26 26 0 0 0 ${A.x + 26 * Math.cos(rad)} ${A.y - 26 * Math.sin(rad)}`}
                  fill="none" stroke="#fde047" strokeWidth="1.5"
                />
                <text x={A.x + 36} y={A.y - 12} className="fill-yellow-300 text-[10px]">{angle}°</text>
              </>
            )
          })()}
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-cyan-300" /> Côtés & angle
          </h3>
          <Slider label="Côté a" value={a} min={50} max={220} step={5} onChange={setA} color="cyan" />
          <Slider label="Côté b" value={b} min={50} max={220} step={5} onChange={setB} color="pink" />
          <Slider label="Angle Â" value={angle} min={10} max={170} step={1} onChange={setAngle} color="violet" />
        </div>
        <div className="holo-card holo-card-cyan p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-cyan-300">Mesures</h4>
          <Stat label="c² = a² + b² − 2ab·cos(Â)" value={`${c.toFixed(2)}`} />
          <Stat label="Périmètre" value={`${perim.toFixed(1)}`} />
          <Stat label="Aire (½·a·b·sin(Â))" value={`${area.toFixed(1)}`} />
          <Stat label="Type" value={Math.abs(c * c - (a * a + b * b)) < 1 ? 'Rectangle' : a === b ? 'Isocèle' : 'Quelconque'} />
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
// FOURIER — square wave from sine sums
// =====================================================================

function FourierLab() {
  const [n, setN] = useState(5)
  const W = 600
  const H = 320

  const points = useMemo(() => {
    const arr: string[] = []
    for (let px = 0; px <= W; px += 2) {
      const x = ((px - W / 2) / W) * 4 * Math.PI
      let y = 0
      for (let k = 1; k <= n; k++) {
        const m = 2 * k - 1
        y += Math.sin(m * x) / m
      }
      const py = H / 2 - (y * 4) / Math.PI * 60
      arr.push(`${px},${py}`)
    }
    return arr.join(' ')
  }, [n])

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full">
          {/* Axes */}
          <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="rgba(255,255,255,0.3)" />
          {/* Target square wave */}
          {Array.from({ length: 5 }).map((_, i) => {
            const x = i * (W / 4)
            const yTop = H / 2 - 80
            const yBot = H / 2 + 80
            const isTop = i % 2 === 0
            return (
              <line key={i} x1={x} y1={isTop ? yTop : yBot} x2={x + W / 4} y2={isTop ? yTop : yBot} stroke="rgba(167,139,250,0.25)" strokeWidth="1" strokeDasharray="3 3" />
            )
          })}
          <polyline
            points={points}
            fill="none"
            stroke="url(#fourierGrad)"
            strokeWidth="2.5"
            filter="drop-shadow(0 0 6px rgba(34,211,238,0.5))"
          />
          <defs>
            <linearGradient id="fourierGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="100%" stopColor="#a78bfa" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5">
          <h3 className="text-sm font-bold text-aurora-text">Synthèse de Fourier</h3>
          <p className="text-xs text-aurora-text-dim mt-1">
            Une onde carrée = somme infinie d'ondes sinusoïdales impaires.
            Plus on ajoute de termes, plus la forme devient nette.
          </p>
        </div>
        <div className="holo-card p-5">
          <Slider label={`Termes : ${n}`} value={n} min={1} max={50} step={1} onChange={setN} color="violet" />
          <div className="mt-3 font-mono text-xs text-aurora-text-muted">
            f(x) ≈ (4/π) · Σ sin((2k−1)x)/(2k−1) pour k = 1 à {n}
          </div>
        </div>
      </div>
    </div>
  )
}
