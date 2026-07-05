import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Car, Plane, Train, Pause, Play, RotateCcw, Sliders, Wind, Gauge, Zap } from 'lucide-react'

type Vehicle = 'plane' | 'car' | 'train'

const VEHICLES: Array<{ id: Vehicle; label: string; icon: typeof Plane; color: string }> = [
  { id: 'plane', label: 'Avion RC', icon: Plane, color: 'from-cyan-400 to-blue-500' },
  { id: 'car', label: 'Voiture RC', icon: Car, color: 'from-orange-400 to-red-500' },
  { id: 'train', label: 'Train', icon: Train, color: 'from-emerald-400 to-teal-500' },
]

export default function LabModelism() {
  const [v, setV] = useState<Vehicle>('plane')
  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Lab modélisme</div>
          <h1 className="text-3xl font-black gradient-text-fire">Pilote des maquettes RC virtuelles</h1>
          <p className="text-sm text-aurora-text-dim mt-1">Aérodynamisme, traction, signalisation — physique réaliste.</p>
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        {VEHICLES.map((veh) => {
          const Icon = veh.icon
          const active = veh.id === v
          return (
            <motion.button
              key={veh.id}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setV(veh.id)}
              className={`relative shrink-0 rounded-2xl border p-3 pr-4 text-left min-w-[160px] transition-all ${active ? 'border-orange-400/50 bg-orange-500/10 neon-outline-warm' : 'border-white/10 bg-white/5 hover:border-orange-400/30'}`}
            >
              <div className="flex items-center gap-3">
                <div className={`rounded-xl bg-gradient-to-br ${veh.color} p-2 shadow-lg`}><Icon size={16} className="text-white" /></div>
                <div className="text-sm font-bold text-aurora-text">{veh.label}</div>
              </div>
            </motion.button>
          )
        })}
      </div>
      {v === 'plane' && <PlaneRC />}
      {v === 'car' && <CarRC />}
      {v === 'train' && <TrainSim />}
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
// PLANE RC — pitch, throttle, lift, drag
// =====================================================================

function PlaneRC() {
  const [throttle, setThrottle] = useState(50)
  const [pitch, setPitch] = useState(0) // -30..+30°
  const [wind, setWind] = useState(0) // -10..+10
  const [playing, setPlaying] = useState(true)
  const stateRef = useRef({ x: 60, y: 200, vx: 0, vy: 0, alt: 0, trail: [] as Array<[number, number]> })
  const [tick, force] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  const reset = () => {
    stateRef.current = { x: 60, y: 200, vx: 0, vy: 0, alt: 0, trail: [] }
    force(t => t + 1)
  }

  useEffect(() => {
    const tickFn = (now: number) => {
      const dt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) {
        const s = stateRef.current
        const thrust = throttle / 50 * 80
        const rad = (pitch * Math.PI) / 180
        // Velocity components
        s.vx += (Math.cos(rad) * thrust + wind * 0.5 - s.vx * 0.6) * dt
        s.vy += (-Math.sin(rad) * thrust + 50 - s.vy * 0.6) * dt // gravity 50 down
        s.x += s.vx * dt
        s.y += s.vy * dt
        // Bound to canvas
        if (s.x > 540) s.x = 60
        if (s.x < 0) s.x = 540
        if (s.y > 300) { s.y = 300; s.vy = 0 }
        if (s.y < 30) { s.y = 30; s.vy = Math.abs(s.vy) }
        s.alt = Math.max(0, 300 - s.y)
        s.trail.push([s.x, s.y])
        if (s.trail.length > 80) s.trail.shift()
        force(t => t + 1)
      }
      reqRef.current = requestAnimationFrame(tickFn)
    }
    reqRef.current = requestAnimationFrame(tickFn)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, throttle, pitch, wind])

  const s = stateRef.current
  const speed = Math.sqrt(s.vx * s.vx + s.vy * s.vy)

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-4 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 600 340" className="w-full h-full">
          <defs>
            <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0c1325"/>
              <stop offset="60%" stopColor="#3b82f6" stopOpacity="0.1"/>
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.15"/>
            </linearGradient>
          </defs>
          <rect x="0" y="0" width="600" height="320" fill="url(#skyGrad)"/>
          {/* Ground */}
          <rect x="0" y="300" width="600" height="40" fill="#1a2331"/>
          <line x1="0" y1="300" x2="600" y2="300" stroke="#475569" strokeWidth="1.5"/>
          {/* Wind indicator */}
          <g transform={`translate(540, 30)`}>
            <Wind {...({} as any)}/>
            <text className="fill-cyan-300 text-[10px]" textAnchor="middle">Vent {wind > 0 ? '→' : wind < 0 ? '←' : '·'}</text>
          </g>
          {/* Trail */}
          {s.trail.length > 1 && (
            <polyline points={s.trail.map(([x, y]) => `${x},${y}`).join(' ')} fill="none" stroke="rgba(34,211,238,0.5)" strokeWidth="1.4" strokeDasharray="3 3"/>
          )}
          {/* Plane (simple silhouette) */}
          <g transform={`translate(${s.x}, ${s.y}) rotate(${-pitch})`}>
            <polygon points="-18,0 18,-3 24,0 18,3" fill="#a78bfa"/>
            <polygon points="-12,0 -2,-12 6,-12 0,0" fill="#22d3ee"/>
            <polygon points="-12,0 -2,12 6,12 0,0" fill="#22d3ee"/>
            <polygon points="-22,0 -16,-6 -10,0 -16,6" fill="#ec4899"/>
          </g>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-orange-300"/> Commandes RC</h3>
          <Slider label="Gaz" value={throttle} min={0} max={100} step={1} onChange={setThrottle} color="orange" unit="%"/>
          <Slider label="Tangage" value={pitch} min={-30} max={30} step={1} onChange={setPitch} color="cyan" unit="°"/>
          <Slider label="Vent" value={wind} min={-10} max={10} step={0.5} onChange={setWind} color="violet"/>
          <div className="flex gap-2">
            <button onClick={() => setPlaying(p => !p)} className="btn-aurora text-xs py-1.5 px-3 flex-1 justify-center">{playing ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Décollage</>}</button>
            <button onClick={reset} className="btn-ghost text-xs py-1.5"><RotateCcw size={12}/></button>
          </div>
        </div>
        <div className="holo-card holo-card-cyan p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-cyan-300">Télémétrie</h4>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Altitude</span><span className="font-mono text-cyan-200">{s.alt.toFixed(0)} m</span></div>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Vitesse</span><span className="font-mono text-violet-200">{speed.toFixed(1)} m/s</span></div>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Tangage</span><span className="font-mono text-pink-200">{pitch.toFixed(0)}°</span></div>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// CAR RC — top-down, steering, drift
// =====================================================================

function CarRC() {
  const [accel, setAccel] = useState(0)
  const [steer, setSteer] = useState(0)
  const [grip, setGrip] = useState(0.85)
  const stateRef = useRef({ x: 280, y: 200, vx: 0, vy: 0, heading: 0, trail: [] as Array<[number, number]> })
  const [, force] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())
  const keys = useRef<Record<string, boolean>>({})

  const reset = () => { stateRef.current = { x: 280, y: 200, vx: 0, vy: 0, heading: 0, trail: [] }; force(t => t + 1) }

  useEffect(() => {
    const onDown = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = true }
    const onUp = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = false }
    window.addEventListener('keydown', onDown)
    window.addEventListener('keyup', onUp)
    return () => { window.removeEventListener('keydown', onDown); window.removeEventListener('keyup', onUp) }
  }, [])

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      const s = stateRef.current
      let a = accel
      let st = steer
      // Keyboard overrides
      if (keys.current['w'] || keys.current['arrowup']) a = 100
      else if (keys.current['s'] || keys.current['arrowdown']) a = -60
      if (keys.current['a'] || keys.current['arrowleft']) st = -30
      else if (keys.current['d'] || keys.current['arrowright']) st = 30
      // Forward velocity component
      const speed = Math.sqrt(s.vx * s.vx + s.vy * s.vy)
      const forward = Math.cos(s.heading) * s.vx + Math.sin(s.heading) * s.vy
      const lateral = -Math.sin(s.heading) * s.vx + Math.cos(s.heading) * s.vy
      // Apply accel (axis: heading)
      const aThrust = a * 0.8
      s.vx += Math.cos(s.heading) * aThrust * dt
      s.vy += Math.sin(s.heading) * aThrust * dt
      // Steering (heading change scaled by speed)
      s.heading += (st * Math.PI / 180) * (speed / 100) * dt * 2
      // Friction
      s.vx -= s.vx * 0.5 * dt
      s.vy -= s.vy * 0.5 * dt
      // Lateral grip — cancel lateral velocity proportionally
      const newLat = lateral * (1 - grip)
      s.vx = Math.cos(s.heading) * forward + Math.cos(s.heading + Math.PI / 2) * newLat
      s.vy = Math.sin(s.heading) * forward + Math.sin(s.heading + Math.PI / 2) * newLat
      // Move
      s.x += s.vx * dt
      s.y += s.vy * dt
      if (s.x < 30) s.x = 30
      if (s.x > 540) s.x = 540
      if (s.y < 30) s.y = 30
      if (s.y > 300) s.y = 300
      s.trail.push([s.x, s.y])
      if (s.trail.length > 80) s.trail.shift()
      force(t => t + 1)
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [accel, steer, grip])

  const s = stateRef.current
  const speed = Math.sqrt(s.vx * s.vx + s.vy * s.vy)

  return (
    <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
      <div className="holo-card p-4 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 580 340" className="w-full h-full">
          <rect x="20" y="20" width="540" height="300" rx="20" fill="rgba(20,27,46,0.6)" stroke="#475569" strokeWidth="1" strokeDasharray="6 6"/>
          {/* Trail (skid marks) */}
          {s.trail.length > 1 && (
            <polyline points={s.trail.map(([x, y]) => `${x},${y}`).join(' ')} fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="2"/>
          )}
          {/* Cones */}
          {[[120, 80], [460, 80], [120, 260], [460, 260], [290, 60], [290, 280]].map(([cx, cy], i) => (
            <polygon key={i} points={`${cx},${cy - 8} ${cx - 6},${cy + 6} ${cx + 6},${cy + 6}`} fill="#fb923c"/>
          ))}
          {/* Car */}
          <g transform={`translate(${s.x}, ${s.y}) rotate(${(s.heading * 180) / Math.PI})`}>
            <rect x="-18" y="-9" width="36" height="18" rx="3" fill="#ef4444" stroke="#fbbf24" strokeWidth="1"/>
            <rect x="-10" y="-7" width="14" height="14" rx="1" fill="#0f172a"/>
            <circle cx="-12" cy="-12" r="3" fill="#1e293b"/>
            <circle cx="12" cy="-12" r="3" fill="#1e293b"/>
            <circle cx="-12" cy="12" r="3" fill="#1e293b"/>
            <circle cx="12" cy="12" r="3" fill="#1e293b"/>
          </g>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-3">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-orange-300"/> Commandes</h3>
          <p className="text-[10px] text-aurora-text-dim">Tu peux aussi piloter au clavier : WASD ou flèches.</p>
          <Slider label="Accélération" value={accel} min={-100} max={100} step={5} onChange={setAccel} color="orange" unit="%"/>
          <Slider label="Direction" value={steer} min={-30} max={30} step={1} onChange={setSteer} color="violet" unit="°"/>
          <Slider label="Adhérence" value={grip} min={0.4} max={0.99} step={0.01} onChange={setGrip} color="emerald"/>
          <button onClick={reset} className="btn-ghost text-xs py-1.5 w-full justify-center"><RotateCcw size={12}/> Reset</button>
        </div>
        <div className="holo-card holo-card-warm p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-orange-300">Télémétrie</h4>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Vitesse</span><span className="font-mono text-orange-200">{speed.toFixed(1)} u/s</span></div>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Cap</span><span className="font-mono text-violet-200">{((s.heading * 180) / Math.PI % 360).toFixed(0)}°</span></div>
          <div className="flex justify-between"><span className="text-aurora-text-dim">Drift</span><span className="font-mono text-pink-200">{grip < 0.7 ? 'oui' : 'non'}</span></div>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// TRAIN SIM — circuit closed loop with switching
// =====================================================================

function TrainSim() {
  const [speed, setSpeed] = useState(50)
  const [route, setRoute] = useState<'circle' | 'eight'>('circle')
  const [t, setT] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  useEffect(() => {
    const tick = (now: number) => {
      const dt = (now - lastT.current) / 1000
      lastT.current = now
      setT(p => p + dt * (speed / 30))
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [speed])

  const trackPath = route === 'circle'
    ? 'M 290 60 A 240 130 0 1 1 290 280 A 240 130 0 1 1 290 60'
    : 'M 290 60 C 460 60 460 200 290 200 C 120 200 120 340 290 340 C 460 340 460 200 290 200'

  // Compute position along path using SVGGeometryElement
  const pathRef = useRef<SVGPathElement>(null)
  const [pos, setPos] = useState({ x: 290, y: 60, angle: 0 })
  useEffect(() => {
    if (!pathRef.current) return
    const len = pathRef.current.getTotalLength()
    const at = (t * 60) % len
    const p = pathRef.current.getPointAtLength(at)
    const p2 = pathRef.current.getPointAtLength((at + 5) % len)
    const angle = Math.atan2(p2.y - p.y, p2.x - p.x) * 180 / Math.PI
    setPos({ x: p.x, y: p.y, angle })
  }, [t, route])

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-4 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 580 380" className="w-full h-full">
          {/* Grass ground */}
          <rect x="0" y="0" width="580" height="380" fill="rgba(34,197,94,0.04)"/>
          {/* Track outer rail */}
          <path ref={pathRef} d={trackPath} fill="none" stroke="#475569" strokeWidth="20" strokeLinecap="round"/>
          <path d={trackPath} fill="none" stroke="#94a3b8" strokeWidth="14" strokeLinecap="round"/>
          <path d={trackPath} fill="none" stroke="#1e293b" strokeWidth="2" strokeLinecap="round" strokeDasharray="8 6"/>
          {/* Stations */}
          <g transform="translate(290, 60)">
            <rect x="-20" y="-12" width="40" height="24" rx="3" fill="#fbbf24" stroke="#dc2626" strokeWidth="1"/>
            <text x="0" y="3" textAnchor="middle" className="fill-white text-[8px] font-bold">GARE</text>
          </g>
          {/* Train cars */}
          {[0, -1, -2].map((dx, i) => {
            const cx = pos.x - Math.cos((pos.angle * Math.PI) / 180) * dx * 28
            const cy = pos.y - Math.sin((pos.angle * Math.PI) / 180) * dx * 28
            return (
              <g key={i} transform={`translate(${cx}, ${cy}) rotate(${pos.angle})`}>
                <rect x="-12" y="-6" width="24" height="12" rx="2" fill={i === 0 ? '#dc2626' : '#3b82f6'} stroke="#fbbf24" strokeWidth="0.6"/>
                {i === 0 && <rect x="-10" y="-4" width="6" height="8" fill="#0f172a"/>}
              </g>
            )
          })}
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-3">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2"><Sliders size={14} className="text-emerald-300"/> Régulation</h3>
          <Slider label="Vitesse" value={speed} min={10} max={120} step={5} onChange={setSpeed} color="emerald" unit="km/h"/>
          <div className="flex gap-2">
            <button onClick={() => setRoute('circle')} className={`btn-pill flex-1 justify-center ${route === 'circle' ? 'is-active' : ''}`}>Boucle</button>
            <button onClick={() => setRoute('eight')} className={`btn-pill flex-1 justify-center ${route === 'eight' ? 'is-active' : ''}`}>Huit</button>
          </div>
        </div>
        <div className="holo-card holo-card-cyan p-4 text-xs space-y-2">
          <h4 className="font-bold uppercase tracking-widest text-emerald-300">Info</h4>
          <p className="text-aurora-text-muted leading-relaxed">
            Modèle simplifié de circuit ferroviaire HO. La locomotive (rouge) tracte 2 wagons.
            Change de tracé pour expérimenter avec des aiguillages — bientôt en mode édition.
          </p>
        </div>
      </div>
    </div>
  )
}
