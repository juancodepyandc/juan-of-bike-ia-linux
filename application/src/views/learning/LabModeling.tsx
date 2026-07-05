import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Brain, Bug, ChevronRight, Pause, Play, RotateCcw, Sliders, TreePine, TrendingUp } from 'lucide-react'

type Sub = 'sir' | 'lotka' | 'logistic' | 'neural'

const SUBS: Array<{ id: Sub; label: string; icon: typeof Activity; color: string; tagline: string }> = [
  { id: 'sir', label: 'Épidémie SIR', icon: Bug, color: 'from-rose-400 to-red-500', tagline: 'Modèle de propagation' },
  { id: 'lotka', label: 'Proie-prédateur', icon: TreePine, color: 'from-emerald-400 to-teal-500', tagline: 'Lotka-Volterra' },
  { id: 'logistic', label: 'Croissance logistique', icon: TrendingUp, color: 'from-cyan-400 to-blue-500', tagline: 'Population limitée' },
  { id: 'neural', label: 'Réseau de neurones', icon: Brain, color: 'from-violet-400 to-purple-500', tagline: 'XOR appris' },
]

export default function LabModeling() {
  const [sub, setSub] = useState<Sub>('sir')
  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Lab modélisation scientifique</div>
          <h1 className="text-3xl font-black gradient-text-cosmic">Équations différentielles & systèmes dynamiques</h1>
          <p className="text-sm text-aurora-text-dim mt-1">Modélise des phénomènes réels avec les bonnes équations.</p>
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        {SUBS.map((s) => {
          const Icon = s.icon
          const active = s.id === sub
          return (
            <motion.button
              key={s.id}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setSub(s.id)}
              className={`relative shrink-0 rounded-2xl border p-3 pr-4 text-left min-w-[180px] transition-all ${active ? 'border-violet-400/50 bg-violet-500/10 neon-outline' : 'border-white/10 bg-white/5 hover:border-violet-400/30'}`}
            >
              <div className="flex items-center gap-3">
                <div className={`rounded-xl bg-gradient-to-br ${s.color} p-2 shadow-lg`}><Icon size={16} className="text-white" /></div>
                <div>
                  <div className={`text-sm font-bold ${active ? 'text-violet-100' : 'text-aurora-text'}`}>{s.label}</div>
                  <div className="text-[10px] text-aurora-text-dim">{s.tagline}</div>
                </div>
              </div>
            </motion.button>
          )
        })}
      </div>
      {sub === 'sir' && <SirSim />}
      {sub === 'lotka' && <LotkaSim />}
      {sub === 'logistic' && <LogisticSim />}
      {sub === 'neural' && <NeuralXOR />}
    </div>
  )
}

function PlayBar({ playing, onToggle, onReset }: { playing: boolean; onToggle: () => void; onReset: () => void }) {
  return (
    <div className="flex gap-2">
      <button onClick={onToggle} className="btn-aurora text-xs py-1.5 px-3 flex-1 justify-center">{playing ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Lancer</>}</button>
      <button onClick={onReset} className="btn-ghost text-xs py-1.5"><RotateCcw size={12}/></button>
    </div>
  )
}

function Slider({ label, value, min, max, step, onChange, color = 'cyan', unit }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; color?: 'cyan' | 'violet' | 'pink' | 'emerald' | 'orange'; unit?: string }) {
  const map = { cyan: 'from-cyan-400 to-blue-500', violet: 'from-violet-400 to-purple-500', pink: 'from-pink-400 to-rose-500', emerald: 'from-emerald-400 to-teal-500', orange: 'from-orange-400 to-rose-500' }
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-aurora-text-muted">{label}</span>
        <span className="font-mono text-aurora-text font-bold">{value.toFixed(step < 1 ? 2 : 0)}{unit ? ` ${unit}` : ''}</span>
      </div>
      <div className="relative h-2 rounded-full bg-white/8 overflow-hidden border border-white/5">
        <div className={`absolute left-0 top-0 h-full bg-gradient-to-r ${map[color]}`} style={{ width: `${pct}%` }} />
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} className="absolute inset-0 w-full opacity-0 cursor-pointer" />
      </div>
    </div>
  )
}

// =====================================================================
// SIR EPIDEMIC
// =====================================================================

function SirSim() {
  const [beta, setBeta] = useState(0.4)
  const [gamma, setGamma] = useState(0.08)
  const [N] = useState(1000)
  const [I0, setI0] = useState(5)
  const [playing, setPlaying] = useState(true)
  const [data, setData] = useState<Array<{ s: number; i: number; r: number }>>([{ s: N - I0, i: I0, r: 0 }])
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const reset = () => {
    setData([{ s: N - I0, i: I0, r: 0 }])
  }
  useEffect(() => { reset() }, [I0, N])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        setData((prev) => {
          if (prev.length > 600) return prev
          const last = prev[prev.length - 1]
          const ds = -beta * last.s * last.i / N
          const di = beta * last.s * last.i / N - gamma * last.i
          const dr = gamma * last.i
          return [...prev, { s: Math.max(0, last.s + ds), i: Math.max(0, last.i + di), r: last.r + dr }]
        })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, beta, gamma, N])

  const W = 540, H = 280
  const maxLen = data.length
  const xScale = (i: number) => (i / Math.max(50, maxLen)) * W
  const yScale = (v: number) => H - (v / N) * H
  const path = (key: 's' | 'i' | 'r') => data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(d[key])}`).join(' ')

  const R0 = beta / gamma
  const last = data[data.length - 1]

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox={`0 0 ${W} ${H + 40}`} className="w-full h-full">
          <line x1="0" y1={H} x2={W} y2={H} stroke="rgba(255,255,255,0.2)"/>
          <text x="10" y={H + 15} className="fill-cyan-300 text-[10px]">Sains</text>
          <text x="60" y={H + 15} className="fill-rose-300 text-[10px]">Infectés</text>
          <text x="120" y={H + 15} className="fill-emerald-300 text-[10px]">Rétablis</text>
          <text x={W - 100} y={H + 15} className="fill-violet-300 text-[10px]">R₀ = {R0.toFixed(2)}</text>
          <path d={path('s')} fill="none" stroke="#22d3ee" strokeWidth="2"/>
          <path d={path('i')} fill="none" stroke="#fb7185" strokeWidth="2.5" filter="drop-shadow(0 0 4px rgba(251,113,133,0.5))"/>
          <path d={path('r')} fill="none" stroke="#34d399" strokeWidth="2"/>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-rose-300"/> Paramètres</h3>
          <Slider label="β (transmission)" value={beta} min={0.05} max={1} step={0.01} onChange={setBeta} color="orange"/>
          <Slider label="γ (récupération)" value={gamma} min={0.01} max={0.5} step={0.01} onChange={setGamma} color="emerald"/>
          <Slider label="Infectés initiaux" value={I0} min={1} max={50} step={1} onChange={setI0} color="pink"/>
          <PlayBar playing={playing} onToggle={() => setPlaying(p => !p)} onReset={reset}/>
        </div>
        <div className="holo-card holo-card-pink p-4 space-y-2 text-xs">
          <h4 className="font-bold uppercase tracking-widest text-rose-300">Mesures</h4>
          {last && (
            <>
              <div className="flex justify-between"><span className="text-aurora-text-dim">Pic infectés</span><span className="font-mono text-rose-200">{Math.round(Math.max(...data.map(d => d.i)))}</span></div>
              <div className="flex justify-between"><span className="text-aurora-text-dim">% touchés</span><span className="font-mono text-aurora-text">{Math.round((last.r + last.i) / N * 100)}%</span></div>
              <div className="flex justify-between"><span className="text-aurora-text-dim">R₀ &gt; 1</span><span className={`font-mono ${R0 > 1 ? 'text-rose-300' : 'text-emerald-300'}`}>{R0 > 1 ? 'épidémie' : 'éteinte'}</span></div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// LOTKA-VOLTERRA
// =====================================================================

function LotkaSim() {
  const [a, setA] = useState(1.1)
  const [b, setB] = useState(0.4)
  const [c, setC] = useState(0.4)
  const [d, setD] = useState(0.1)
  const [playing, setPlaying] = useState(true)
  const [data, setData] = useState<Array<{ x: number; y: number }>>([{ x: 10, y: 5 }])
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const reset = () => setData([{ x: 10, y: 5 }])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        setData((prev) => {
          if (prev.length > 800) return prev
          const last = prev[prev.length - 1]
          const dx = (a * last.x - b * last.x * last.y) * dt
          const dy = (-c * last.y + d * last.x * last.y) * dt
          return [...prev, { x: Math.max(0.1, last.x + dx), y: Math.max(0.1, last.y + dy) }]
        })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, a, b, c, d])

  const W = 540, H = 280
  const maxV = Math.max(...data.flatMap(p => [p.x, p.y])) || 1
  const xScale = (i: number) => (i / Math.max(50, data.length)) * W
  const yScale = (v: number) => H - (v / maxV) * (H - 20)
  const path = (key: 'x' | 'y') => data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(d[key])}`).join(' ')

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox={`0 0 ${W} ${H + 30}`} className="w-full h-full">
          <line x1="0" y1={H} x2={W} y2={H} stroke="rgba(255,255,255,0.2)"/>
          <text x="10" y={H + 18} className="fill-emerald-300 text-[10px]">Proies</text>
          <text x="80" y={H + 18} className="fill-orange-300 text-[10px]">Prédateurs</text>
          <path d={path('x')} fill="none" stroke="#34d399" strokeWidth="2.5" filter="drop-shadow(0 0 4px rgba(52,211,153,0.5))"/>
          <path d={path('y')} fill="none" stroke="#fb923c" strokeWidth="2.5" filter="drop-shadow(0 0 4px rgba(251,146,60,0.5))"/>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-emerald-300"/> Paramètres</h3>
          <Slider label="α (croissance proies)" value={a} min={0.2} max={3} step={0.05} onChange={setA} color="emerald"/>
          <Slider label="β (prédation)" value={b} min={0.05} max={1} step={0.01} onChange={setB} color="orange"/>
          <Slider label="γ (mortalité prédateurs)" value={c} min={0.05} max={1} step={0.01} onChange={setC} color="pink"/>
          <Slider label="δ (efficacité)" value={d} min={0.01} max={0.5} step={0.01} onChange={setD} color="cyan"/>
          <PlayBar playing={playing} onToggle={() => setPlaying(p => !p)} onReset={reset}/>
        </div>
        <div className="holo-card holo-card-cyan p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-emerald-300">Équations</h4>
          <p className="font-mono text-aurora-text">dx/dt = αx − βxy</p>
          <p className="font-mono text-aurora-text">dy/dt = δxy − γy</p>
          <p className="text-aurora-text-muted">Cycle : proies augmentent → prédateurs grandissent → proies chutent → prédateurs meurent → proies repartent.</p>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// LOGISTIC GROWTH
// =====================================================================

function LogisticSim() {
  const [r, setR] = useState(0.3)
  const [K, setK] = useState(1000)
  const [N0, setN0] = useState(20)
  const [playing, setPlaying] = useState(true)
  const [data, setData] = useState<number[]>([N0])
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const reset = () => setData([N0])
  useEffect(() => { reset() }, [N0])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        setData((prev) => {
          if (prev.length > 500) return prev
          const last = prev[prev.length - 1]
          const dN = r * last * (1 - last / K) * dt
          return [...prev, last + dN]
        })
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, r, K])

  const W = 540, H = 280
  const maxV = K * 1.1
  const xScale = (i: number) => (i / Math.max(50, data.length)) * W
  const yScale = (v: number) => H - (v / maxV) * H
  const path = data.map((v, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i)} ${yScale(v)}`).join(' ')

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox={`0 0 ${W} ${H + 20}`} className="w-full h-full">
          <line x1="0" y1={yScale(K)} x2={W} y2={yScale(K)} stroke="rgba(167,139,250,0.4)" strokeDasharray="4 4"/>
          <text x={W - 80} y={yScale(K) - 5} className="fill-violet-300 text-[10px]">Capacité K = {K}</text>
          <line x1="0" y1={H} x2={W} y2={H} stroke="rgba(255,255,255,0.2)"/>
          <path d={path} fill="none" stroke="url(#logiGrad)" strokeWidth="3" filter="drop-shadow(0 0 6px rgba(34,211,238,0.6))"/>
          <defs><linearGradient id="logiGrad"><stop offset="0%" stopColor="#22d3ee"/><stop offset="100%" stopColor="#a78bfa"/></linearGradient></defs>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-cyan-300"/> Paramètres</h3>
          <Slider label="r (taux de croissance)" value={r} min={0.05} max={1} step={0.01} onChange={setR} color="cyan"/>
          <Slider label="K (capacité)" value={K} min={100} max={2000} step={50} onChange={setK} color="violet"/>
          <Slider label="N₀ (population init.)" value={N0} min={1} max={200} step={1} onChange={setN0} color="emerald"/>
          <PlayBar playing={playing} onToggle={() => setPlaying(p => !p)} onReset={reset}/>
        </div>
        <div className="holo-card holo-card-cyan p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-cyan-300">Équation logistique</h4>
          <p className="font-mono text-aurora-text">dN/dt = r·N·(1 − N/K)</p>
          <p className="text-aurora-text-muted">Modèle de Verhulst (1838) : croissance exponentielle au début, frein quand N → K.</p>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// NEURAL XOR — train a tiny MLP live
// =====================================================================

function NeuralXOR() {
  // 2-3-1 MLP trained with backprop on XOR
  const [epoch, setEpoch] = useState(0)
  const [loss, setLoss] = useState(0.5)
  const [training, setTraining] = useState(true)
  const stateRef = useRef({
    w1: [[Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5], [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5]],
    b1: [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5],
    w2: [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5],
    b2: Math.random() - 0.5,
  })
  const reqRef = useRef<number>(0)

  const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))

  const forward = (x: number[], s = stateRef.current) => {
    const z1 = [0, 0, 0]
    for (let j = 0; j < 3; j++) {
      z1[j] = s.b1[j]
      for (let i = 0; i < 2; i++) z1[j] += x[i] * s.w1[i][j]
    }
    const a1 = z1.map(sigmoid)
    let z2 = s.b2
    for (let j = 0; j < 3; j++) z2 += a1[j] * s.w2[j]
    return { a1, a2: sigmoid(z2) }
  }

  const reset = () => {
    stateRef.current = {
      w1: [[Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5], [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5]],
      b1: [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5],
      w2: [Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5],
      b2: Math.random() - 0.5,
    }
    setEpoch(0)
    setLoss(0.5)
  }

  useEffect(() => {
    const lr = 1.5
    const data = [
      [[0, 0], 0],
      [[0, 1], 1],
      [[1, 0], 1],
      [[1, 1], 0],
    ] as const
    const tick = () => {
      if (training) {
        const s = stateRef.current
        // 200 mini-epochs per frame for speed
        let totalLoss = 0
        for (let k = 0; k < 200; k++) {
          for (const [x, y] of data) {
            const { a1, a2 } = forward([...x] as number[])
            const err = a2 - (y as number)
            totalLoss += err * err
            const dz2 = err * a2 * (1 - a2)
            const grad_w2 = a1.map((a) => a * dz2)
            const grad_b2 = dz2
            const dz1 = a1.map((a, j) => dz2 * s.w2[j] * a * (1 - a))
            const grad_w1 = [
              dz1.map((d) => d * x[0]),
              dz1.map((d) => d * x[1]),
            ]
            const grad_b1 = dz1
            for (let j = 0; j < 3; j++) {
              s.w2[j] -= lr * grad_w2[j]
              s.b1[j] -= lr * grad_b1[j]
              s.w1[0][j] -= lr * grad_w1[0][j]
              s.w1[1][j] -= lr * grad_w1[1][j]
            }
            s.b2 -= lr * grad_b2
          }
        }
        setEpoch((e) => e + 200)
        setLoss(totalLoss / 4)
      }
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [training])

  // Render decision surface
  const grid = useMemo(() => {
    const cells: Array<{ x: number; y: number; v: number }> = []
    const N = 24
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      const x = i / (N - 1)
      const y = j / (N - 1)
      const { a2 } = forward([x, y])
      cells.push({ x, y, v: a2 })
    }
    return cells
  }, [epoch])

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="holo-card p-5 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 360 360" className="w-full h-full max-w-[440px] mx-auto">
          {grid.map((c, i) => (
            <rect
              key={i}
              x={c.x * 320 + 20}
              y={c.y * 320 + 20}
              width={320 / 24}
              height={320 / 24}
              fill={`hsl(${c.v < 0.5 ? 200 : 350}, 60%, ${30 + Math.abs(c.v - 0.5) * 80}%)`}
              opacity="0.7"
            />
          ))}
          {/* Training points */}
          {[
            { x: 0, y: 0, label: 0 },
            { x: 1, y: 1, label: 0 },
            { x: 0, y: 1, label: 1 },
            { x: 1, y: 0, label: 1 },
          ].map((p, i) => (
            <circle
              key={i}
              cx={p.x * 320 + 20}
              cy={p.y * 320 + 20}
              r="9"
              fill={p.label === 1 ? '#fb7185' : '#22d3ee'}
              stroke="white"
              strokeWidth="2"
            />
          ))}
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card holo-card-warm p-5 space-y-2">
          <h3 className="text-sm font-bold text-aurora-text">Entraînement live</h3>
          <div className="flex justify-between text-xs"><span className="text-aurora-text-dim">Epoch</span><span className="font-mono text-violet-300 font-bold">{epoch}</span></div>
          <div className="flex justify-between text-xs"><span className="text-aurora-text-dim">Loss MSE</span><span className="font-mono text-pink-300 font-bold">{loss.toFixed(5)}</span></div>
          <div className="flex gap-2 mt-2">
            <button onClick={() => setTraining(t => !t)} className="btn-aurora text-xs py-1.5 px-3 flex-1 justify-center">{training ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Train</>}</button>
            <button onClick={reset} className="btn-ghost text-xs py-1.5"><RotateCcw size={12}/></button>
          </div>
        </div>
        <div className="holo-card p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-violet-300">Réseau 2-3-1</h4>
          <p className="text-aurora-text-muted leading-relaxed">
            Tu vois la surface de décision d'un MLP qui apprend XOR — un problème impossible pour un perceptron linéaire.
            Les 4 points (cyan = 0, rose = 1) sont les exemples. Les couleurs représentent la confiance du réseau.
          </p>
        </div>
        <div className="holo-card holo-card-cyan p-4">
          <p className="text-xs font-mono text-aurora-text">XOR: 0⊕0=0 · 0⊕1=1 · 1⊕0=1 · 1⊕1=0</p>
        </div>
      </div>
    </div>
  )
}
