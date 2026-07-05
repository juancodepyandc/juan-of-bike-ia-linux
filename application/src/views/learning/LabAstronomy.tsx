import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Globe, Moon, Orbit, Play, Pause, RotateCcw, Sliders, Sparkles, Sun, Telescope } from 'lucide-react'

type SubTab = 'solar' | 'moon' | 'eclipse' | 'stars' | 'orbit'

export default function LabAstronomy() {
  const [sub, setSub] = useState<SubTab>('solar')
  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Lab astronomie</div>
          <h1 className="text-3xl font-black gradient-text-ocean">Système solaire · Lune · Éclipses · Orbites</h1>
          <p className="text-sm text-aurora-text-dim mt-1">Observe les lois qui régissent le ciel.</p>
        </div>
        <div className="flex gap-1.5 p-1 rounded-2xl border border-white/10 bg-white/5 backdrop-blur flex-wrap">
          <button onClick={() => setSub('solar')} className={`btn-pill ${sub === 'solar' ? 'is-active' : ''}`}><Sun size={12}/> Solaire</button>
          <button onClick={() => setSub('moon')} className={`btn-pill ${sub === 'moon' ? 'is-active' : ''}`}><Moon size={12}/> Lune</button>
          <button onClick={() => setSub('eclipse')} className={`btn-pill ${sub === 'eclipse' ? 'is-active' : ''}`}><Globe size={12}/> Éclipses</button>
          <button onClick={() => setSub('stars')} className={`btn-pill ${sub === 'stars' ? 'is-active' : ''}`}><Telescope size={12}/> Étoiles</button>
          <button onClick={() => setSub('orbit')} className={`btn-pill ${sub === 'orbit' ? 'is-active' : ''}`}><Orbit size={12}/> Kepler</button>
        </div>
      </div>

      {sub === 'solar' && <SolarSystem />}
      {sub === 'moon' && <MoonPhases />}
      {sub === 'eclipse' && <EclipseSim />}
      {sub === 'stars' && <StarExplorer />}
      {sub === 'orbit' && <KeplerLaws />}
    </div>
  )
}

// =====================================================================
// SOLAR SYSTEM — 8 planets, real-ish data, animated
// =====================================================================

type Planet = {
  name: string
  color: string
  radius: number // rendering radius
  dist: number // rendering distance in px
  period: number // orbital period in earth-years
  facts: string[]
  textureGrad: string
}

const PLANETS: Planet[] = [
  { name: 'Mercure', color: '#a8a29e', radius: 4, dist: 55, period: 0.24, facts: ['Plus proche du Soleil', 'Pas d’atmosphère', 'Journée = 176 jours terrestres'], textureGrad: 'from-stone-400 to-stone-600' },
  { name: 'Vénus', color: '#fbbf24', radius: 7, dist: 80, period: 0.62, facts: ['Planète la plus chaude (~465°C)', 'Atmosphère CO₂ dense', 'Rotation rétrograde'], textureGrad: 'from-yellow-300 to-orange-500' },
  { name: 'Terre', color: '#60a5fa', radius: 7.5, dist: 115, period: 1, facts: ['Seule planète avec vie connue', 'Eau liquide en surface', 'Satellite naturel : Lune'], textureGrad: 'from-blue-400 via-cyan-400 to-green-500' },
  { name: 'Mars', color: '#ef4444', radius: 5, dist: 150, period: 1.88, facts: ['Surface rouge (oxyde de fer)', 'Olympus Mons, plus haut volcan', 'Deux lunes : Phobos, Deimos'], textureGrad: 'from-red-400 to-orange-600' },
  { name: 'Jupiter', color: '#fb923c', radius: 18, dist: 205, period: 11.86, facts: ['Plus grosse planète', 'Grande tache rouge (tempête)', '79 lunes connues'], textureGrad: 'from-amber-300 via-orange-400 to-red-400' },
  { name: 'Saturne', color: '#fcd34d', radius: 15, dist: 255, period: 29.46, facts: ['Anneaux spectaculaires', 'Composée de H + He', 'Densité < eau'], textureGrad: 'from-yellow-200 via-amber-300 to-yellow-600' },
  { name: 'Uranus', color: '#67e8f9', radius: 10, dist: 300, period: 84.01, facts: ['Axe de rotation incliné 98°', 'Méthane → couleur cyan', 'Atmosphère la plus froide'], textureGrad: 'from-cyan-300 to-teal-500' },
  { name: 'Neptune', color: '#3b82f6', radius: 10, dist: 340, period: 164.8, facts: ['Vents à 2000 km/h', 'Bleu profond (méthane)', 'Découverte par calcul'], textureGrad: 'from-blue-500 to-indigo-700' },
]

function SolarSystem() {
  const [speed, setSpeed] = useState(3)
  const [playing, setPlaying] = useState(true)
  const [selected, setSelected] = useState<string | null>('Terre')
  const [timeYear, setTimeYear] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  useEffect(() => {
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - lastT.current) / 1000)
      lastT.current = now
      if (playing) setTimeYear((t) => t + dt * speed * 0.1)
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing, speed])

  const sel = PLANETS.find((p) => p.name === selected)

  return (
    <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
      <div className="holo-card p-4 lab-background relative overflow-hidden min-h-[540px]">
        <svg viewBox="-380 -380 760 760" className="w-full h-full">
          {/* Stars background */}
          {Array.from({ length: 90 }).map((_, i) => (
            <circle key={`s-${i}`} cx={(Math.random() - 0.5) * 760} cy={(Math.random() - 0.5) * 760} r={Math.random() * 0.9} fill="white" opacity={0.3 + Math.random() * 0.5} />
          ))}
          {/* Orbit rings */}
          {PLANETS.map((p) => (
            <circle key={`orb-${p.name}`} cx="0" cy="0" r={p.dist} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" strokeDasharray="2 3" />
          ))}
          {/* Sun */}
          <defs>
            <radialGradient id="sunGradA"><stop offset="0%" stopColor="#fef3c7"/><stop offset="40%" stopColor="#fbbf24"/><stop offset="100%" stopColor="#dc2626"/></radialGradient>
          </defs>
          <motion.circle cx="0" cy="0" r="28" fill="url(#sunGradA)" filter="drop-shadow(0 0 30px rgba(251,191,36,0.9))" animate={{ scale: [1, 1.04, 1] }} transition={{ repeat: Infinity, duration: 3 }} />
          {/* Planets */}
          {PLANETS.map((p) => {
            const angle = (timeYear / p.period) * 2 * Math.PI
            const x = Math.cos(angle) * p.dist
            const y = Math.sin(angle) * p.dist
            return (
              <g key={p.name} onClick={() => setSelected(p.name)} style={{ cursor: 'pointer' }}>
                <circle cx={x} cy={y} r={p.radius} fill={p.color} filter={`drop-shadow(0 0 ${p.radius / 2}px ${p.color})`} />
                {p.name === 'Saturne' && (
                  <ellipse cx={x} cy={y} rx={p.radius + 6} ry={p.radius / 2 + 1} fill="none" stroke="#fde68a" strokeWidth="0.8" opacity="0.7" />
                )}
                <text x={x} y={y - p.radius - 5} textAnchor="middle" className="fill-white text-[8px]" opacity={selected === p.name ? 1 : 0.6}>{p.name}</text>
              </g>
            )
          })}
        </svg>
        <div className="absolute bottom-4 left-4 right-4 flex flex-wrap items-center gap-2">
          <button onClick={() => setPlaying((p) => !p)} className="btn-aurora text-xs py-1.5 px-3">
            {playing ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Jouer</>}
          </button>
          <button onClick={() => setTimeYear(0)} className="btn-ghost text-xs py-1.5"><RotateCcw size={12}/> Reset</button>
          <div className="ml-auto rounded-xl bg-black/50 backdrop-blur px-3 py-1.5 text-xs text-cyan-100 font-mono border border-cyan-400/20">
            T = {timeYear.toFixed(1)} années
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="holo-card p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold text-aurora-text">Vitesse</h3>
            <span className="text-xs text-cyan-300 font-mono">×{speed.toFixed(1)}</span>
          </div>
          <input type="range" min="0.2" max="10" step="0.2" value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))} className="w-full" />
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {PLANETS.map((p) => (
            <button
              key={p.name}
              onClick={() => setSelected(p.name)}
              className={`group relative rounded-xl border p-2 transition-all ${p.name === selected ? 'border-cyan-400/50 bg-cyan-500/10 neon-outline-cyan' : 'border-white/10 bg-white/5 hover:border-violet-400/30'}`}
            >
              <div className={`h-10 w-10 rounded-full bg-gradient-to-br ${p.textureGrad} mx-auto shadow-lg`} style={{ filter: `drop-shadow(0 0 8px ${p.color})` }} />
              <div className="text-[10px] text-center mt-1 text-aurora-text">{p.name}</div>
            </button>
          ))}
        </div>
        {sel && (
          <AnimatePresence mode="wait">
            <motion.div
              key={sel.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="holo-card holo-card-cyan p-5"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={`h-14 w-14 rounded-full bg-gradient-to-br ${sel.textureGrad} shadow-xl`} style={{ filter: `drop-shadow(0 0 12px ${sel.color})` }} />
                <div>
                  <h3 className="text-xl font-black gradient-text-ocean">{sel.name}</h3>
                  <p className="text-[11px] text-cyan-300 font-mono">Orbite : {sel.period} ans · Distance : {sel.dist}·10⁶ km (échelle)</p>
                </div>
              </div>
              <div className="space-y-1.5">
                {sel.facts.map((f, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-aurora-text-muted">
                    <Sparkles size={11} className="mt-0.5 shrink-0 text-violet-300"/><span>{f}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}

// =====================================================================
// MOON PHASES
// =====================================================================

function MoonPhases() {
  const [phase, setPhase] = useState(0) // 0..1
  const [auto, setAuto] = useState(true)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  useEffect(() => {
    const tick = (now: number) => {
      const dt = (now - lastT.current) / 1000
      lastT.current = now
      if (auto) setPhase((p) => (p + dt * 0.08) % 1)
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [auto])

  // phase 0 = new moon, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter
  const label = phase < 0.03 ? 'Nouvelle lune' : phase < 0.22 ? 'Premier croissant' : phase < 0.28 ? 'Premier quartier' : phase < 0.47 ? 'Gibbeuse croissante' : phase < 0.53 ? 'Pleine lune' : phase < 0.72 ? 'Gibbeuse décroissante' : phase < 0.78 ? 'Dernier quartier' : 'Dernier croissant'

  // moon render: circle with terminator
  const r = 100
  const illumFrac = Math.abs(Math.cos(phase * 2 * Math.PI - Math.PI)) // 0..1
  const waxing = phase < 0.5

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[420px] flex items-center justify-center">
        <svg viewBox="-150 -150 300 300" className="w-full h-full max-w-[420px]">
          {Array.from({ length: 40 }).map((_, i) => (
            <circle key={i} cx={(Math.random() - 0.5) * 300} cy={(Math.random() - 0.5) * 300} r={Math.random() * 0.6} fill="white" opacity="0.3"/>
          ))}
          <defs>
            <radialGradient id="moonLit">
              <stop offset="0%" stopColor="#fefce8"/>
              <stop offset="70%" stopColor="#e2e8f0"/>
              <stop offset="100%" stopColor="#94a3b8"/>
            </radialGradient>
            <mask id="illuminated">
              <rect x="-150" y="-150" width="300" height="300" fill="black"/>
              {/* Full moon mask */}
              <circle cx="0" cy="0" r={r} fill="white"/>
              {/* Terminator ellipse cuts the shadow */}
              <ellipse
                cx="0" cy="0"
                rx={r * (1 - 2 * illumFrac)}
                ry={r}
                fill={waxing ? 'black' : 'white'}
              />
              <rect x={waxing ? -r : 0} y={-r} width={r} height={r * 2} fill="black"/>
            </mask>
          </defs>
          <circle cx="0" cy="0" r={r} fill="#1e293b" stroke="#475569" strokeWidth="1"/>
          <circle cx="0" cy="0" r={r} fill="url(#moonLit)" mask="url(#illuminated)"/>
          {/* Craters for texture */}
          {[[30, -40, 8], [-40, 20, 6], [10, 50, 5], [-20, -30, 4]].map(([cx, cy, cr], i) => (
            <circle key={i} cx={cx} cy={cy} r={cr} fill="#64748b" opacity="0.3"/>
          ))}
        </svg>
      </div>

      <div className="space-y-4">
        <div className="holo-card holo-card-cyan p-5">
          <h3 className="text-2xl font-black gradient-text-ocean">{label}</h3>
          <p className="text-xs text-aurora-text-dim mt-1">Illumination : {Math.round(illumFrac * 100)}% · Âge lunaire : {(phase * 29.5).toFixed(1)} jours</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-2.5">
              <div className="text-[10px] text-cyan-300 mono-kicker">Cycle</div>
              <div className="font-mono text-aurora-text">29.5 jours</div>
            </div>
            <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-2.5">
              <div className="text-[10px] text-cyan-300 mono-kicker">Marées</div>
              <div className="font-mono text-aurora-text">{waxing ? 'Montantes' : 'Descendantes'}</div>
            </div>
          </div>
        </div>

        <div className="holo-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-aurora-text">Phase manuelle</h4>
            <button onClick={() => setAuto(a => !a)} className="btn-pill">{auto ? 'Auto ON' : 'Auto OFF'}</button>
          </div>
          <input type="range" min="0" max="1" step="0.001" value={phase} onChange={(e) => { setAuto(false); setPhase(parseFloat(e.target.value)) }} className="w-full"/>
          <div className="grid grid-cols-4 gap-1.5">
            {[
              { v: 0, l: 'Nouvelle' },
              { v: 0.25, l: 'Prem. Q' },
              { v: 0.5, l: 'Pleine' },
              { v: 0.75, l: 'Dern. Q' },
            ].map(p => (
              <button key={p.v} onClick={() => { setAuto(false); setPhase(p.v) }} className="btn-pill text-[10px]">{p.l}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// ECLIPSE
// =====================================================================

function EclipseSim() {
  const [kind, setKind] = useState<'solar' | 'lunar'>('solar')
  const [align, setAlign] = useState(0.5) // 0 = left, 1 = right, 0.5 centered = total
  const offset = (align - 0.5) * 240

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="-250 -140 500 280" className="w-full h-full">
          {Array.from({ length: 30 }).map((_, i) => (
            <circle key={i} cx={(Math.random() - 0.5) * 500} cy={(Math.random() - 0.5) * 280} r={Math.random() * 0.7} fill="white" opacity="0.4"/>
          ))}
          {kind === 'solar' ? (
            <>
              <defs>
                <radialGradient id="sunE"><stop offset="0%" stopColor="#fef3c7"/><stop offset="50%" stopColor="#fb923c"/><stop offset="100%" stopColor="#dc2626"/></radialGradient>
              </defs>
              <circle cx="-150" cy="0" r="45" fill="url(#sunE)" filter="drop-shadow(0 0 24px rgba(251,146,60,0.8))"/>
              <circle cx={offset} cy="0" r="22" fill="#1e293b" stroke="#475569" strokeWidth="1"/>
              <text x={offset} y="50" textAnchor="middle" className="fill-slate-300 text-[10px]">Lune</text>
              <text x="-150" y="60" textAnchor="middle" className="fill-orange-300 text-[10px]">Soleil</text>
              <circle cx="190" cy="0" r="20" fill="#60a5fa" filter="drop-shadow(0 0 14px rgba(96,165,250,0.7))"/>
              <text x="190" y="30" textAnchor="middle" className="fill-cyan-300 text-[10px]">Terre</text>
            </>
          ) : (
            <>
              <defs>
                <radialGradient id="sunL"><stop offset="0%" stopColor="#fef3c7"/><stop offset="50%" stopColor="#fb923c"/><stop offset="100%" stopColor="#dc2626"/></radialGradient>
              </defs>
              <circle cx="-180" cy="0" r="38" fill="url(#sunL)" filter="drop-shadow(0 0 20px rgba(251,146,60,0.7))"/>
              <text x="-180" y="52" textAnchor="middle" className="fill-orange-300 text-[10px]">Soleil</text>
              <circle cx="0" cy="0" r="28" fill="#60a5fa" filter="drop-shadow(0 0 14px rgba(96,165,250,0.7))"/>
              <text x="0" y="42" textAnchor="middle" className="fill-cyan-300 text-[10px]">Terre</text>
              {/* Shadow cone */}
              <polygon points={`-152,-26 0,-8 180,${-8 + (1 - align) * 14} 180,${8 + (1 - align) * 14} 0,8 -152,26`} fill="rgba(15,23,42,0.75)"/>
              <circle cx={180} cy={(1 - align) * 14 + 2} r="12" fill="#94a3b8" opacity={align > 0.3 && align < 0.7 ? 0.4 : 1} stroke="#cbd5e1" strokeWidth="0.5"/>
              <text x={180} y="45" textAnchor="middle" className="fill-slate-200 text-[10px]">Lune</text>
            </>
          )}
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-3">
          <div className="flex gap-2">
            <button onClick={() => setKind('solar')} className={`btn-pill flex-1 justify-center ${kind === 'solar' ? 'is-active' : ''}`}><Sun size={12}/> Solaire</button>
            <button onClick={() => setKind('lunar')} className={`btn-pill flex-1 justify-center ${kind === 'lunar' ? 'is-active' : ''}`}><Moon size={12}/> Lunaire</button>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-aurora-text-muted">Alignement</span>
              <span className="font-mono text-cyan-300">{(align * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min="0" max="1" step="0.01" value={align} onChange={(e) => setAlign(parseFloat(e.target.value))} className="w-full"/>
          </div>
        </div>
        <div className="holo-card holo-card-warm p-5">
          <h4 className="text-sm font-bold text-orange-200">{kind === 'solar' ? 'Éclipse solaire' : 'Éclipse lunaire'}</h4>
          <p className="text-xs text-aurora-text-muted mt-2 leading-relaxed">
            {kind === 'solar'
              ? 'La Lune passe entre la Terre et le Soleil. Se produit à la nouvelle lune quand l’alignement est parfait (~2×/an).'
              : 'La Terre passe entre le Soleil et la Lune. Se produit à la pleine lune. La Lune devient rouge (Lune de sang) à cause de la réfraction atmosphérique.'}
          </p>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// STAR EXPLORER — Hertzsprung-Russell mini
// =====================================================================

const STARS: Array<{ name: string; type: string; mass: number; temp: number; lum: number; color: string }> = [
  { name: 'Soleil', type: 'G2V', mass: 1, temp: 5778, lum: 1, color: '#fde047' },
  { name: 'Sirius', type: 'A1V', mass: 2.02, temp: 9940, lum: 25, color: '#dbeafe' },
  { name: 'Betelgeuse', type: 'M1', mass: 17, temp: 3500, lum: 140000, color: '#fb7185' },
  { name: 'Rigel', type: 'B8', mass: 23, temp: 12100, lum: 120000, color: '#93c5fd' },
  { name: 'Proxima Cen', type: 'M5.5V', mass: 0.12, temp: 3042, lum: 0.0017, color: '#ef4444' },
  { name: 'Vega', type: 'A0V', mass: 2.13, temp: 9602, lum: 40, color: '#eff6ff' },
  { name: 'Aldébaran', type: 'K5III', mass: 1.16, temp: 3910, lum: 518, color: '#fb923c' },
  { name: 'Polaris', type: 'F7Ib', mass: 5.4, temp: 6015, lum: 2500, color: '#fef3c7' },
]

function StarExplorer() {
  const [picked, setPicked] = useState<string>('Soleil')
  const sel = STARS.find((s) => s.name === picked)!
  // Transform log scales for plotting: x = log(T) reversed, y = log(L)
  const xScale = (t: number) => 400 - ((Math.log10(t) - 3) / 2) * 400 // 3..5
  const yScale = (l: number) => 300 - ((Math.log10(l) + 4) / 10) * 300

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="0 0 440 340" className="w-full h-full">
          <text x="220" y="20" textAnchor="middle" className="fill-aurora-text text-[11px] font-bold">Diagramme Hertzsprung-Russell</text>
          <line x1="20" y1="320" x2="420" y2="320" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5"/>
          <line x1="20" y1="20" x2="20" y2="320" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5"/>
          <text x="220" y="335" textAnchor="middle" className="fill-aurora-text-dim text-[9px]">← Chaud (K)       Froid →</text>
          <text x="10" y="170" textAnchor="middle" className="fill-aurora-text-dim text-[9px]" transform="rotate(-90 10 170)">Luminosité (L⊙)</text>
          {/* Main sequence */}
          <path d="M 50 280 Q 180 220 260 140 T 400 50" fill="none" stroke="rgba(167,139,250,0.25)" strokeWidth="6" strokeLinecap="round"/>
          {STARS.map((s) => (
            <g key={s.name} onClick={() => setPicked(s.name)} style={{ cursor: 'pointer' }}>
              <circle cx={xScale(s.temp) / 1.1 + 30} cy={yScale(s.lum) / 1 + 20} r={picked === s.name ? 8 : 5} fill={s.color} filter={`drop-shadow(0 0 10px ${s.color})`} stroke={picked === s.name ? 'white' : 'none'} strokeWidth="1.5"/>
              <text x={xScale(s.temp) / 1.1 + 30} y={yScale(s.lum) / 1 + 8} textAnchor="middle" className="fill-white text-[9px]" opacity={picked === s.name ? 1 : 0.6}>{s.name}</text>
            </g>
          ))}
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card holo-card-cyan p-5">
          <div className="flex items-center gap-3">
            <div className="h-14 w-14 rounded-full" style={{ background: sel.color, boxShadow: `0 0 20px ${sel.color}` }} />
            <div>
              <h3 className="text-2xl font-black gradient-text">{sel.name}</h3>
              <p className="text-xs text-cyan-300 font-mono">Type {sel.type}</p>
            </div>
          </div>
          <div className="mt-4 space-y-1.5 text-xs">
            <div className="flex justify-between"><span className="text-aurora-text-dim">Masse</span><span className="font-mono text-aurora-text">{sel.mass} M⊙</span></div>
            <div className="flex justify-between"><span className="text-aurora-text-dim">Température</span><span className="font-mono text-aurora-text">{sel.temp} K</span></div>
            <div className="flex justify-between"><span className="text-aurora-text-dim">Luminosité</span><span className="font-mono text-aurora-text">{sel.lum} L⊙</span></div>
          </div>
        </div>
        <div className="holo-card p-3">
          <div className="grid grid-cols-2 gap-1.5">
            {STARS.map((s) => (
              <button key={s.name} onClick={() => setPicked(s.name)} className={`rounded-lg border p-2 text-left text-[10px] transition-all ${s.name === picked ? 'border-cyan-400/50 bg-cyan-500/10' : 'border-white/10 bg-white/5 hover:border-violet-400/30'}`}>
                <div className="flex items-center gap-1.5">
                  <div className="h-3 w-3 rounded-full" style={{ background: s.color, boxShadow: `0 0 4px ${s.color}` }} />
                  <span className="text-aurora-text font-medium">{s.name}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// =====================================================================
// KEPLER LAWS — elliptical orbit with variable speed
// =====================================================================

function KeplerLaws() {
  const [a, setA] = useState(180) // semi-major axis
  const [e, setE] = useState(0.4) // eccentricity
  const [playing, setPlaying] = useState(true)
  const [t, setT] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  useEffect(() => {
    const tick = (now: number) => {
      const dt = (now - lastT.current) / 1000
      lastT.current = now
      if (playing) setT((p) => p + dt)
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [playing])

  const b = a * Math.sqrt(1 - e * e)
  // Eccentric anomaly ≈ mean anomaly iteration (one step ok for demo)
  const M = t * 1.5
  let E = M
  for (let i = 0; i < 5; i++) E = E - (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E))
  const x = a * (Math.cos(E) - e)
  const y = b * Math.sin(E)
  const v = Math.sqrt((1 + e * Math.cos(E)) / (1 - e * Math.cos(E))) // normalized speed proxy

  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="holo-card p-6 lab-background relative overflow-hidden min-h-[380px]">
        <svg viewBox="-250 -200 500 400" className="w-full h-full">
          <ellipse cx={0} cy={0} rx={a} ry={b} fill="none" stroke="rgba(167,139,250,0.25)" strokeDasharray="3 3"/>
          {/* Focus (Sun) */}
          <circle cx={a * e} cy={0} r="14" fill="url(#sunKepGrad)" filter="drop-shadow(0 0 22px rgba(251,146,60,0.7))"/>
          <defs>
            <radialGradient id="sunKepGrad"><stop offset="0%" stopColor="#fef3c7"/><stop offset="60%" stopColor="#fb923c"/><stop offset="100%" stopColor="#dc2626"/></radialGradient>
          </defs>
          <circle cx={-a * e} cy={0} r="2.5" fill="#94a3b8"/>
          {/* Planet */}
          <motion.circle
            cx={x + a * e}
            cy={y}
            r="7"
            fill="#67e8f9"
            filter="drop-shadow(0 0 12px rgba(34,211,238,0.7))"
          />
          {/* Radius vector */}
          <line x1={a * e} y1={0} x2={x + a * e} y2={y} stroke="rgba(255,255,255,0.2)" strokeWidth="0.7" strokeDasharray="2 2"/>
        </svg>
      </div>
      <div className="space-y-4">
        <div className="holo-card p-5 space-y-4">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2">
            <Sliders size={14} className="text-violet-300"/> Orbite
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between text-xs"><span className="text-aurora-text-muted">Demi-axe a</span><span className="font-mono text-cyan-300">{a}</span></div>
            <input type="range" min="80" max="220" step="1" value={a} onChange={(e) => setA(parseInt(e.target.value))} className="w-full"/>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between text-xs"><span className="text-aurora-text-muted">Excentricité e</span><span className="font-mono text-pink-300">{e.toFixed(2)}</span></div>
            <input type="range" min="0" max="0.85" step="0.01" value={e} onChange={(e2) => setE(parseFloat(e2.target.value))} className="w-full"/>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setPlaying(p => !p)} className="btn-aurora text-xs py-1.5 px-3 flex-1 justify-center">{playing ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Play</>}</button>
            <button onClick={() => setT(0)} className="btn-ghost text-xs py-1.5"><RotateCcw size={12}/></button>
          </div>
        </div>
        <div className="holo-card holo-card-pink p-4 space-y-2">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-pink-300">Lois de Kepler</h4>
          <p className="text-xs text-aurora-text-muted leading-relaxed">
            <strong className="text-pink-200">1.</strong> Orbite = ellipse, Soleil au foyer.<br/>
            <strong className="text-pink-200">2.</strong> Aires balayées égales en temps égal ⇒ vitesse variable.<br/>
            <strong className="text-pink-200">3.</strong> T² / a³ = constante.
          </p>
          <div className="text-xs font-mono text-cyan-300 mt-2">Vitesse relative ≈ {v.toFixed(2)}</div>
        </div>
      </div>
    </div>
  )
}
