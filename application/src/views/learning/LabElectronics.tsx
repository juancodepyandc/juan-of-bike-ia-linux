import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Battery,
  CircuitBoard,
  Cpu,
  Lightbulb,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Trash2,
  Zap,
} from 'lucide-react'

// =====================================================================
// SIN — Système d'Information Numérique
// Simulateur de circuit (Loi d'Ohm) + Arduino-like blink
// =====================================================================

type CompType = 'battery' | 'resistor' | 'led' | 'switch' | 'arduino'

interface Component {
  id: string
  type: CompType
  x: number
  y: number
  value?: number // ohms for resistor, volts for battery
  color?: string
  state?: boolean
}

const COMPS: Array<{ type: CompType; label: string; icon: typeof Battery; color: string; defaults: Partial<Component> }> = [
  { type: 'battery', label: 'Pile 9V', icon: Battery, color: 'from-yellow-400 to-orange-500', defaults: { value: 9 } },
  { type: 'resistor', label: 'Résistance', icon: Zap, color: 'from-amber-400 to-yellow-500', defaults: { value: 220 } },
  { type: 'led', label: 'LED', icon: Lightbulb, color: 'from-rose-400 to-red-500', defaults: { color: '#ec4899' } },
  { type: 'switch', label: 'Inter.', icon: Plus, color: 'from-cyan-400 to-blue-500', defaults: { state: true } },
  { type: 'arduino', label: 'Arduino', icon: Cpu, color: 'from-emerald-400 to-teal-500', defaults: {} },
]

type Mode = 'circuit' | 'arduino' | 'projects'

export default function LabElectronics() {
  const [mode, setMode] = useState<Mode>('circuit')

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">SIN — Lab électronique</div>
          <h1 className="text-3xl font-black gradient-text-fire">Construis ton circuit</h1>
          <p className="text-sm text-aurora-text-dim mt-1">Pose des composants, branche, simule. Pas besoin de matériel.</p>
        </div>
        <div className="flex gap-1.5 p-1 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
          <button
            onClick={() => setMode('circuit')}
            className={`btn-pill ${mode === 'circuit' ? 'is-active' : ''}`}
          >
            <CircuitBoard size={12} /> Circuit (Ohm)
          </button>
          <button
            onClick={() => setMode('arduino')}
            className={`btn-pill ${mode === 'arduino' ? 'is-active' : ''}`}
          >
            <Cpu size={12} /> Arduino
          </button>
          <button
            onClick={() => setMode('projects')}
            className={`btn-pill ${mode === 'projects' ? 'is-active' : ''}`}
          >
            <Lightbulb size={12} /> Projets
          </button>
        </div>
      </div>

      {mode === 'circuit' && <CircuitBuilder />}
      {mode === 'arduino' && <ArduinoSim />}
      {mode === 'projects' && <ArduinoProjects />}
    </div>
  )
}

// =====================================================================
// ARDUINO PROJECTS — preloaded hands-on scenarios
// =====================================================================

type ArdProject = {
  id: string
  title: string
  emoji: string
  brief: string
  parts: string[]
  code: string
  diagram: 'led' | 'servo' | 'buzzer' | 'lcd' | 'ultrasonic' | 'potentiometer' | 'pwm' | 'motor'
}

const PROJECTS: ArdProject[] = [
  {
    id: 'blink',
    title: 'LED qui clignote',
    emoji: '💡',
    brief: 'Le « Hello World » d\'Arduino. Allume et éteint la LED de la pin 13 toutes les secondes.',
    parts: ['Arduino UNO', 'LED + résistance 220Ω', '2 fils'],
    code: `void setup() {\n  pinMode(13, OUTPUT);\n}\n\nvoid loop() {\n  digitalWrite(13, HIGH);\n  delay(1000);\n  digitalWrite(13, LOW);\n  delay(1000);\n}`,
    diagram: 'led',
  },
  {
    id: 'servo',
    title: 'Servo-moteur balayage',
    emoji: '⚙️',
    brief: 'Pilote un servo SG90 qui balaie de 0 à 180° en boucle.',
    parts: ['Arduino UNO', 'Servo SG90', 'Lib <Servo.h>'],
    code: `#include <Servo.h>\n\nServo monServo;\n\nvoid setup() {\n  monServo.attach(9);\n}\n\nvoid loop() {\n  for (int pos = 0; pos <= 180; pos++) {\n    monServo.write(pos);\n    delay(15);\n  }\n  for (int pos = 180; pos >= 0; pos--) {\n    monServo.write(pos);\n    delay(15);\n  }\n}`,
    diagram: 'servo',
  },
  {
    id: 'buzzer',
    title: 'Mélodie buzzer',
    emoji: '🎵',
    brief: 'Joue les premières notes d\'« Au clair de la lune » sur un buzzer passif.',
    parts: ['Arduino UNO', 'Buzzer passif', 'Résistance 100Ω'],
    code: `int notes[] = {262, 262, 262, 294, 330};\nint duree[] = {400, 400, 400, 400, 800};\n\nvoid setup() {\n  pinMode(8, OUTPUT);\n}\n\nvoid loop() {\n  for (int i = 0; i < 5; i++) {\n    tone(8, notes[i], duree[i]);\n    delay(duree[i] + 50);\n  }\n  delay(2000);\n}`,
    diagram: 'buzzer',
  },
  {
    id: 'lcd',
    title: 'LCD 16x2 — Hello',
    emoji: '📺',
    brief: 'Affiche du texte sur un écran LCD I2C ou parallèle.',
    parts: ['Arduino UNO', 'Écran LCD 16x2 + I2C', 'Lib <LiquidCrystal.h>'],
    code: `#include <LiquidCrystal.h>\n\nLiquidCrystal lcd(12, 11, 5, 4, 3, 2);\n\nvoid setup() {\n  lcd.begin(16, 2);\n  lcd.print("Bonjour Aurora!");\n}\n\nvoid loop() {\n  lcd.setCursor(0, 1);\n  lcd.print(millis() / 1000);\n  lcd.print(" sec");\n  delay(1000);\n}`,
    diagram: 'lcd',
  },
  {
    id: 'ultrasonic',
    title: 'Capteur ultrason HC-SR04',
    emoji: '📡',
    brief: 'Mesure la distance à un objet et affiche en cm.',
    parts: ['Arduino UNO', 'HC-SR04', '4 fils'],
    code: `const int trig = 9;\nconst int echo = 10;\n\nvoid setup() {\n  pinMode(trig, OUTPUT);\n  pinMode(echo, INPUT);\n  Serial.begin(9600);\n}\n\nvoid loop() {\n  digitalWrite(trig, LOW);\n  delayMicroseconds(2);\n  digitalWrite(trig, HIGH);\n  delayMicroseconds(10);\n  digitalWrite(trig, LOW);\n\n  long t = pulseIn(echo, HIGH);\n  float d = t * 0.034 / 2;  // cm\n  Serial.print("Distance: ");\n  Serial.print(d);\n  Serial.println(" cm");\n  delay(200);\n}`,
    diagram: 'ultrasonic',
  },
  {
    id: 'potentiometer',
    title: 'Potentiomètre + LED',
    emoji: '🎛️',
    brief: 'Lis la valeur d\'un potentiomètre et règle la luminosité d\'une LED via PWM.',
    parts: ['Arduino UNO', 'Potentiomètre 10kΩ', 'LED + résistance 220Ω'],
    code: `const int pot = A0;\nconst int led = 9;  // pin PWM\n\nvoid setup() {\n  pinMode(led, OUTPUT);\n}\n\nvoid loop() {\n  int val = analogRead(pot);  // 0 à 1023\n  int pwm = map(val, 0, 1023, 0, 255);\n  analogWrite(led, pwm);\n}`,
    diagram: 'potentiometer',
  },
  {
    id: 'pwm',
    title: 'PWM — fade LED',
    emoji: '🌅',
    brief: 'Fait varier doucement la luminosité d\'une LED par modulation de largeur d\'impulsion.',
    parts: ['Arduino UNO', 'LED + résistance 220Ω'],
    code: `int led = 9;  // pin PWM\nint fade = 5;\nint val = 0;\n\nvoid setup() {\n  pinMode(led, OUTPUT);\n}\n\nvoid loop() {\n  analogWrite(led, val);\n  val += fade;\n  if (val <= 0 || val >= 255) fade = -fade;\n  delay(30);\n}`,
    diagram: 'pwm',
  },
  {
    id: 'motor',
    title: 'Moteur DC + transistor',
    emoji: '🔄',
    brief: 'Fait tourner un moteur DC à vitesse variable via PWM et transistor 2N2222.',
    parts: ['Arduino UNO', 'Moteur DC 5V', 'Transistor 2N2222', 'Diode 1N4007', 'Résistance 1kΩ'],
    code: `int motor = 6;  // pin PWM\n\nvoid setup() {\n  pinMode(motor, OUTPUT);\n}\n\nvoid loop() {\n  for (int speed = 0; speed <= 255; speed++) {\n    analogWrite(motor, speed);\n    delay(20);\n  }\n  delay(1000);\n  analogWrite(motor, 0);\n  delay(1000);\n}`,
    diagram: 'motor',
  },
]

function ArduinoProjects() {
  const [picked, setPicked] = useState<ArdProject>(PROJECTS[0])
  const [time, setTime] = useState(0)
  const reqRef = useRef<number>(0)
  const lastT = useRef(performance.now())

  useEffect(() => {
    const tick = (now: number) => {
      const dt = (now - lastT.current) / 1000
      lastT.current = now
      setTime(t => t + dt)
      reqRef.current = requestAnimationFrame(tick)
    }
    reqRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(reqRef.current)
  }, [])

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <div className="holo-card p-3 max-h-[640px] overflow-y-auto scroll-shell">
        <p className="mono-kicker text-[10px] text-aurora-text-dim mb-3 px-2">{PROJECTS.length} projets</p>
        <div className="space-y-1.5">
          {PROJECTS.map(p => (
            <button
              key={p.id}
              onClick={() => setPicked(p)}
              className={`w-full rounded-xl border p-3 text-left transition-all ${
                p.id === picked.id ? 'border-orange-400/50 bg-orange-500/15 neon-outline-warm' : 'border-white/10 bg-white/5 hover:border-orange-400/30'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className="text-2xl shrink-0">{p.emoji}</span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-aurora-text leading-tight">{p.title}</div>
                  <div className="text-[10px] text-aurora-text-dim mt-0.5 line-clamp-1">{p.brief}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="holo-card holo-card-warm p-5">
          <div className="flex items-start gap-3">
            <div className="text-4xl">{picked.emoji}</div>
            <div className="flex-1">
              <h3 className="text-2xl font-black gradient-text-fire">{picked.title}</h3>
              <p className="text-sm text-aurora-text-muted mt-1">{picked.brief}</p>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {picked.parts.map(p => (
                  <span key={p} className="btn-pill text-[10px]">{p}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="holo-card p-4 lab-background relative overflow-hidden min-h-[260px]">
            <ProjectDiagram kind={picked.diagram} time={time} />
          </div>
          <div className="holo-card p-0 overflow-hidden">
            <div className="bg-emerald-500/10 border-b border-emerald-400/20 px-4 py-2 text-xs text-emerald-100 flex items-center gap-2">
              <Cpu size={12}/>
              <span className="font-bold">{picked.id}.ino</span>
            </div>
            <pre className="bg-black/40 p-4 max-h-[300px] overflow-auto">
              <code className="font-mono text-[11px] text-emerald-100 whitespace-pre">{picked.code}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProjectDiagram({ kind, time }: { kind: ArdProject['diagram']; time: number }) {
  const blink = Math.floor(time) % 2 === 0
  const pwmFade = (Math.sin(time * 0.7) + 1) / 2 // 0..1
  const servoAngle = ((time * 60) % 360 < 180) ? (time * 60) % 180 : 180 - ((time * 60) % 180)
  const sound = Math.abs(Math.sin(time * 6)) > 0.3
  const dist = 10 + Math.abs(Math.sin(time * 0.8)) * 80

  return (
    <svg viewBox="0 0 400 280" className="w-full h-full">
      {/* Arduino board placeholder */}
      <rect x="20" y="100" width="120" height="80" rx="6" fill="#155e75" stroke="#22d3ee" strokeWidth="1"/>
      <text x="80" y="145" textAnchor="middle" className="fill-cyan-100 text-[10px] font-bold">ARDUINO</text>
      <text x="80" y="160" textAnchor="middle" className="fill-cyan-300 text-[8px]">UNO</text>

      {kind === 'led' && (
        <>
          <line x1="140" y1="120" x2="220" y2="120" stroke="#ef4444" strokeWidth="1.5"/>
          <line x1="140" y1="170" x2="220" y2="170" stroke="#1e293b" strokeWidth="1.5"/>
          <rect x="220" y="130" width="40" height="30" fill="#a78bfa" rx="2"/>
          <text x="240" y="148" textAnchor="middle" className="fill-white text-[8px]">220Ω</text>
          <line x1="260" y1="145" x2="300" y2="145" stroke="#ef4444" strokeWidth="1.5"/>
          <circle cx="320" cy="145" r="18" fill={blink ? '#ec4899' : '#1e293b'} stroke="#ec4899" strokeWidth="2" className={blink ? 'led-on' : ''} style={{ color: '#ec4899' }}/>
          {blink && [0, 60, 120, 180, 240, 300].map(d => <line key={d} x1="320" y1="125" x2="320" y2="115" stroke="#ec4899" strokeWidth="2" transform={`rotate(${d} 320 145)`}/>)}
        </>
      )}

      {kind === 'servo' && (
        <>
          <line x1="140" y1="140" x2="240" y2="140" stroke="#fb923c" strokeWidth="1.5"/>
          <rect x="240" y="120" width="50" height="50" rx="4" fill="#1e293b" stroke="#fb923c" strokeWidth="1"/>
          <circle cx="265" cy="145" r="14" fill="#475569" stroke="#fb923c" strokeWidth="1"/>
          <line x1="265" y1="145" x2={265 + 25 * Math.cos(((servoAngle - 90) * Math.PI) / 180)} y2={145 + 25 * Math.sin(((servoAngle - 90) * Math.PI) / 180)} stroke="#fde047" strokeWidth="3" strokeLinecap="round"/>
          <text x="265" y="195" textAnchor="middle" className="fill-orange-300 text-[10px]">{Math.round(servoAngle)}°</text>
        </>
      )}

      {kind === 'buzzer' && (
        <>
          <line x1="140" y1="140" x2="240" y2="140" stroke="#fde047" strokeWidth="1.5"/>
          <circle cx="280" cy="140" r="22" fill="#0f172a" stroke="#fde047" strokeWidth="2"/>
          <circle cx="280" cy="140" r="8" fill="#fde047"/>
          {sound && [25, 35, 45].map(r => <circle key={r} cx="280" cy="140" r={r} fill="none" stroke="#fde047" strokeWidth="1" opacity={1 - r / 60} className="animate-aurora-pulse"/>)}
        </>
      )}

      {kind === 'lcd' && (
        <>
          <rect x="200" y="80" width="180" height="80" rx="4" fill="#22c55e" stroke="#0f172a" strokeWidth="2"/>
          <rect x="208" y="88" width="164" height="64" fill="#0f172a"/>
          <text x="216" y="110" className="fill-emerald-300 text-[11px] font-mono">Bonjour Aurora!</text>
          <text x="216" y="130" className="fill-emerald-300 text-[11px] font-mono">{Math.floor(time)} sec</text>
        </>
      )}

      {kind === 'ultrasonic' && (
        <>
          <line x1="140" y1="130" x2="200" y2="130" stroke="#22d3ee" strokeWidth="1.5"/>
          <line x1="140" y1="160" x2="200" y2="160" stroke="#a78bfa" strokeWidth="1.5"/>
          <rect x="200" y="120" width="60" height="50" rx="3" fill="#1e293b" stroke="#22d3ee" strokeWidth="1"/>
          <circle cx="215" cy="145" r="10" fill="#0f172a" stroke="#22d3ee"/>
          <circle cx="245" cy="145" r="10" fill="#0f172a" stroke="#22d3ee"/>
          {/* Ultrasound waves */}
          {[0, 1, 2, 3, 4].map(i => {
            const x = 270 + i * 18
            const o = ((time * 80 - i * 30) % 100) / 100
            return o > 0 && o < 1 ? <path key={i} d={`M ${x} 140 Q ${x + 6} 130 ${x + 12} 140 Q ${x + 6} 150 ${x} 140`} fill="none" stroke="#22d3ee" strokeWidth="1.5" opacity={1 - o}/> : null
          })}
          {/* Object */}
          <rect x={345} y="115" width="20" height="60" fill="#475569" stroke="#94a3b8"/>
          <text x="270" y="220" className="fill-cyan-300 text-[10px] font-mono">{dist.toFixed(1)} cm</text>
        </>
      )}

      {kind === 'potentiometer' && (
        <>
          <line x1="140" y1="120" x2="200" y2="120" stroke="#a78bfa" strokeWidth="1.5"/>
          <line x1="140" y1="160" x2="200" y2="160" stroke="#1e293b" strokeWidth="1.5"/>
          <circle cx="215" cy="140" r="22" fill="#1e293b" stroke="#a78bfa" strokeWidth="2"/>
          <line x1="215" y1="140" x2={215 + 16 * Math.cos((time * 1.5) % (Math.PI * 2))} y2={140 + 16 * Math.sin((time * 1.5) % (Math.PI * 2))} stroke="#fde047" strokeWidth="2.5"/>
          <text x="215" y="180" textAnchor="middle" className="fill-violet-300 text-[9px]">POT 10kΩ</text>
          <line x1="237" y1="140" x2="290" y2="140" stroke="#22c55e" strokeWidth="1.5"/>
          <circle cx="320" cy="140" r="14" fill="#fde047" opacity={pwmFade} className={pwmFade > 0.3 ? 'led-on' : ''} style={{ color: '#fde047' }}/>
        </>
      )}

      {kind === 'pwm' && (
        <>
          <line x1="140" y1="140" x2="240" y2="140" stroke="#fb923c" strokeWidth="1.5"/>
          <rect x="240" y="125" width="40" height="30" fill="#a78bfa"/>
          <text x="260" y="143" textAnchor="middle" className="fill-white text-[8px]">220Ω</text>
          <line x1="280" y1="140" x2="320" y2="140" stroke="#fb923c"/>
          <circle cx="340" cy="140" r="16" fill="#fde047" opacity={pwmFade} className={pwmFade > 0.2 ? 'led-on' : ''} style={{ color: '#fde047', filter: `brightness(${0.5 + pwmFade})` }}/>
          {/* PWM waveform */}
          <path d={`M 200 220 ${Array.from({ length: 30 }).map((_, i) => {
            const x = 200 + i * 6
            const y = (i * 0.5 + time * 4) % 4 < 2 + pwmFade * 2 ? 200 : 230
            return `L ${x} ${y}`
          }).join(' ')}`} fill="none" stroke="#fde047" strokeWidth="1"/>
        </>
      )}

      {kind === 'motor' && (
        <>
          <line x1="140" y1="140" x2="220" y2="140" stroke="#22c55e" strokeWidth="1.5"/>
          <rect x="220" y="125" width="40" height="30" fill="#1e293b" stroke="#22c55e"/>
          <text x="240" y="144" textAnchor="middle" className="fill-emerald-200 text-[8px]">2N2222</text>
          <line x1="260" y1="140" x2="290" y2="140" stroke="#ef4444" strokeWidth="2"/>
          <g transform={`translate(330, 140) rotate(${(time * 360 * pwmFade) % 360})`}>
            <circle cx="0" cy="0" r="22" fill="#475569" stroke="#94a3b8" strokeWidth="2"/>
            <line x1="-22" y1="0" x2="22" y2="0" stroke="#0f172a" strokeWidth="3"/>
            <line x1="0" y1="-22" x2="0" y2="22" stroke="#0f172a" strokeWidth="3"/>
            <circle cx="0" cy="0" r="6" fill="#0f172a"/>
          </g>
          <text x="330" y="195" textAnchor="middle" className="fill-emerald-300 text-[10px]">{Math.round(pwmFade * 100)}%</text>
        </>
      )}
    </svg>
  )
}

// =====================================================================
// CIRCUIT BUILDER — drag & drop on breadboard, ohm's law
// =====================================================================

function CircuitBuilder() {
  const [comps, setComps] = useState<Component[]>([
    { id: 'b1', type: 'battery', x: 80, y: 200, value: 9 },
    { id: 'r1', type: 'resistor', x: 240, y: 100, value: 220 },
    { id: 'l1', type: 'led', x: 400, y: 200, color: '#ec4899', state: true },
  ])
  const [selected, setSelected] = useState<string | null>(null)
  const [running, setRunning] = useState(true)

  const totalR = comps.filter((c) => c.type === 'resistor').reduce((acc, c) => acc + (c.value || 0), 0) + 50 // + LED ~50Ω
  const totalV = comps.filter((c) => c.type === 'battery').reduce((acc, c) => acc + (c.value || 0), 0)
  const open = comps.some((c) => c.type === 'switch' && c.state === false)
  const I = !open && totalR > 0 ? totalV / totalR : 0
  const P = totalV * I

  const ledOn = running && !open && I > 0.005

  const addComp = (type: CompType) => {
    const cfg = COMPS.find((c) => c.type === type)!
    const id = `${type[0]}${Date.now().toString(36).slice(-4)}`
    setComps((cs) => [...cs, { id, type, x: 200 + Math.random() * 100, y: 150 + Math.random() * 100, ...cfg.defaults }])
  }

  const removeComp = (id: string) => {
    setComps((cs) => cs.filter((c) => c.id !== id))
    if (selected === id) setSelected(null)
  }

  const updateValue = (id: string, value: number) => {
    setComps((cs) => cs.map((c) => (c.id === id ? { ...c, value } : c)))
  }

  const toggleSwitch = (id: string) => {
    setComps((cs) => cs.map((c) => (c.id === id ? { ...c, state: !c.state } : c)))
  }

  const sel = comps.find((c) => c.id === selected)

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="space-y-3">
        {/* Toolbar */}
        <div className="holo-card p-3 flex flex-wrap gap-2">
          {COMPS.map((cfg) => {
            const Icon = cfg.icon
            return (
              <button
                key={cfg.type}
                onClick={() => addComp(cfg.type)}
                className="group rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-aurora-text hover:border-violet-400/40 hover:bg-violet-500/10 transition-all flex items-center gap-2"
              >
                <div className={`rounded-lg bg-gradient-to-br ${cfg.color} p-1.5`}>
                  <Icon size={12} className="text-white" />
                </div>
                {cfg.label}
              </button>
            )
          })}
          <div className="flex-1" />
          <button onClick={() => setRunning((r) => !r)} className="btn-aurora text-xs py-1.5 px-3">
            {running ? <><Pause size={12} /> Pause</> : <><Play size={12} /> Run</>}
          </button>
        </div>

        {/* Breadboard */}
        <div className="holo-card p-5 lab-background breadboard-grid relative overflow-hidden min-h-[420px]">
          <svg viewBox="0 0 700 400" className="w-full h-full">
            <defs>
              <linearGradient id="wireGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#22d3ee" />
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>
            {/* Wires (auto-routed between sequential components) */}
            {comps.length > 1 && comps.map((c, i) => {
              const next = comps[(i + 1) % comps.length]
              return (
                <line
                  key={`w-${i}`}
                  x1={c.x} y1={c.y}
                  x2={next.x} y2={next.y}
                  stroke="url(#wireGrad)"
                  strokeWidth={ledOn ? 2.5 : 1.6}
                  className={ledOn && running ? 'wire-anim' : ''}
                  opacity={ledOn ? 0.8 : 0.4}
                />
              )
            })}
            {/* Components */}
            {comps.map((c) => (
              <CompNode
                key={c.id}
                c={c}
                ledOn={ledOn}
                I={I}
                selected={selected === c.id}
                onSelect={() => setSelected(c.id)}
                onMove={(x, y) => setComps((cs) => cs.map((p) => (p.id === c.id ? { ...p, x, y } : p)))}
                onToggle={() => toggleSwitch(c.id)}
              />
            ))}
          </svg>
        </div>
      </div>

      {/* INSPECTOR */}
      <div className="space-y-3">
        <div className="holo-card holo-card-cyan p-5">
          <h3 className="text-sm font-bold text-aurora-text inline-flex items-center gap-2 mb-3">
            <Zap size={14} className="text-cyan-300" />
            Mesures (loi d'Ohm)
          </h3>
          <div className="space-y-2 text-sm">
            <RowMetric label="Tension U" value={`${totalV.toFixed(2)} V`} />
            <RowMetric label="Résistance totale R" value={`${totalR.toFixed(0)} Ω`} />
            <RowMetric label="Courant I = U / R" value={`${(I * 1000).toFixed(1)} mA`} />
            <RowMetric label="Puissance P = U·I" value={`${(P * 1000).toFixed(1)} mW`} />
          </div>
          <div className={`mt-4 rounded-xl border p-3 text-xs ${ledOn ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-100' : 'border-rose-400/40 bg-rose-500/10 text-rose-100'}`}>
            {open ? 'Circuit ouvert (interrupteur)' : ledOn ? '✓ La LED s\'allume — circuit valide' : 'Courant trop faible — vérifie les composants'}
          </div>
        </div>

        {sel ? (
          <div className="holo-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-aurora-text">Composant</h4>
              <button onClick={() => removeComp(sel.id)} className="rounded-lg p-1.5 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-400/30 text-rose-300">
                <Trash2 size={12} />
              </button>
            </div>
            <p className="text-xs text-aurora-text-dim mb-3">{COMPS.find((c) => c.type === sel.type)?.label} · {sel.id}</p>
            {sel.type === 'resistor' && (
              <div className="space-y-2">
                <label className="text-xs text-aurora-text-muted">Valeur (Ω)</label>
                <input
                  type="number"
                  value={sel.value}
                  onChange={(e) => updateValue(sel.id, parseFloat(e.target.value) || 0)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-aurora-text"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[100, 220, 470, 1000, 4700, 10000].map((v) => (
                    <button key={v} onClick={() => updateValue(sel.id, v)} className="btn-pill">{v >= 1000 ? `${v / 1000}kΩ` : `${v}Ω`}</button>
                  ))}
                </div>
              </div>
            )}
            {sel.type === 'battery' && (
              <div className="space-y-2">
                <label className="text-xs text-aurora-text-muted">Tension (V)</label>
                <input
                  type="number"
                  value={sel.value}
                  onChange={(e) => updateValue(sel.id, parseFloat(e.target.value) || 0)}
                  className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-aurora-text"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {[1.5, 3, 5, 9, 12].map((v) => (
                    <button key={v} onClick={() => updateValue(sel.id, v)} className="btn-pill">{v}V</button>
                  ))}
                </div>
              </div>
            )}
            {sel.type === 'switch' && (
              <button onClick={() => toggleSwitch(sel.id)} className="btn-aurora w-full">
                {sel.state ? 'Ouvrir' : 'Fermer'}
              </button>
            )}
            {sel.type === 'led' && (
              <div className="space-y-2">
                <label className="text-xs text-aurora-text-muted">Couleur</label>
                <div className="flex gap-2">
                  {['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7', '#ec4899'].map((c) => (
                    <button
                      key={c}
                      onClick={() => setComps((cs) => cs.map((p) => (p.id === sel.id ? { ...p, color: c } : p)))}
                      className="h-8 w-8 rounded-full border-2"
                      style={{ background: c, borderColor: sel.color === c ? 'white' : 'transparent' }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="holo-card p-5 text-center">
            <CircuitBoard size={28} className="mx-auto text-violet-300/60 mb-2" />
            <p className="text-xs text-aurora-text-dim">Clique sur un composant pour l'éditer</p>
          </div>
        )}

        <div className="holo-card holo-card-warm p-4">
          <h4 className="text-[11px] font-bold uppercase tracking-widest text-orange-300 mb-2">Astuce</h4>
          <p className="text-xs text-aurora-text-muted leading-relaxed">
            La résistance limite le courant pour protéger la LED.
            <br />Pour LED 2V/20mA, R = (9V − 2V) / 0.02 ≈ <strong className="text-orange-200">350 Ω</strong>.
          </p>
        </div>
      </div>
    </div>
  )
}

function RowMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-aurora-text-dim">{label}</span>
      <span className="font-mono font-bold text-aurora-text">{value}</span>
    </div>
  )
}

function CompNode({
  c, ledOn, I, selected, onSelect, onMove, onToggle,
}: {
  c: Component; ledOn: boolean; I: number; selected: boolean
  onSelect: () => void; onMove: (x: number, y: number) => void; onToggle: () => void
}) {
  const draggingRef = useRef(false)
  const offsetRef = useRef({ x: 0, y: 0 })
  return (
    <g
      transform={`translate(${c.x}, ${c.y})`}
      onMouseDown={(e) => {
        draggingRef.current = true
        const svg = (e.target as SVGElement).ownerSVGElement!
        const pt = svg.createSVGPoint()
        pt.x = e.clientX
        pt.y = e.clientY
        const cursor = pt.matrixTransform(svg.getScreenCTM()!.inverse())
        offsetRef.current = { x: cursor.x - c.x, y: cursor.y - c.y }
        onSelect()
      }}
      onMouseMove={(e) => {
        if (!draggingRef.current) return
        const svg = (e.target as SVGElement).ownerSVGElement!
        const pt = svg.createSVGPoint()
        pt.x = e.clientX
        pt.y = e.clientY
        const cursor = pt.matrixTransform(svg.getScreenCTM()!.inverse())
        onMove(Math.max(40, Math.min(660, cursor.x - offsetRef.current.x)), Math.max(40, Math.min(360, cursor.y - offsetRef.current.y)))
      }}
      onMouseUp={() => { draggingRef.current = false }}
      onMouseLeave={() => { draggingRef.current = false }}
      onClick={c.type === 'switch' ? onToggle : undefined}
      className={selected ? 'cursor-grab' : 'cursor-pointer'}
      style={{ outline: selected ? '2px solid white' : 'none' }}
    >
      {c.type === 'battery' && (
        <>
          <rect x="-26" y="-18" width="52" height="36" rx="4" fill="url(#battGrad)" stroke="#fde047" strokeWidth="1.5" />
          <defs><linearGradient id="battGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#fde047"/><stop offset="100%" stopColor="#fb923c"/></linearGradient></defs>
          <text x="0" y="3" textAnchor="middle" className="fill-white text-[10px] font-bold">{c.value}V</text>
        </>
      )}
      {c.type === 'resistor' && (
        <>
          <rect x="-32" y="-9" width="64" height="18" rx="9" fill="#a78bfa" />
          {[0, 1, 2, 3].map((i) => (
            <rect key={i} x={-22 + i * 12} y="-9" width="6" height="18" fill={i === 0 ? '#dc2626' : i === 1 ? '#f97316' : i === 2 ? '#fde047' : '#22c55e'} />
          ))}
          <text x="0" y="22" textAnchor="middle" className="fill-aurora-text-dim text-[9px]">{(c.value || 0) >= 1000 ? `${(c.value || 0) / 1000}kΩ` : `${c.value}Ω`}</text>
        </>
      )}
      {c.type === 'led' && (
        <>
          <circle cx="0" cy="0" r="13" fill={ledOn ? c.color : '#1e293b'} stroke={c.color} strokeWidth="2" className={ledOn ? 'led-on' : ''} style={{ color: c.color }} />
          {ledOn && (
            <>
              {[0, 60, 120, 180, 240, 300].map((d) => (
                <line key={d} x1="0" y1="-15" x2="0" y2="-22" stroke={c.color} strokeWidth="2" transform={`rotate(${d})`} />
              ))}
            </>
          )}
        </>
      )}
      {c.type === 'switch' && (
        <>
          <rect x="-22" y="-12" width="44" height="24" rx="4" fill="#1e293b" stroke="#22d3ee" strokeWidth="1.5" />
          <line x1="-15" y1="0" x2={c.state ? 15 : 5} y2={c.state ? 0 : -8} stroke="#22d3ee" strokeWidth="2.5" />
          <circle cx="-15" cy="0" r="2" fill="#22d3ee" />
          <circle cx="15" cy="0" r="2" fill="#22d3ee" />
          <text x="0" y="22" textAnchor="middle" className="fill-aurora-text-dim text-[9px]">{c.state ? 'ON' : 'OFF'}</text>
        </>
      )}
      {c.type === 'arduino' && (
        <>
          <rect x="-30" y="-22" width="60" height="44" rx="5" fill="url(#arduGrad)" stroke="#34d399" strokeWidth="1.5" />
          <defs><linearGradient id="arduGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#16a34a"/><stop offset="100%" stopColor="#0e7490"/></linearGradient></defs>
          <rect x="-22" y="-14" width="22" height="14" rx="2" fill="#0f172a" />
          <text x="0" y="3" textAnchor="middle" className="fill-white text-[8px] font-bold">UNO</text>
        </>
      )}
    </g>
  )
}

// =====================================================================
// ARDUINO — Blink simulator with code editor
// =====================================================================

const SAMPLE_CODE = `// LED qui clignote
// Branche une LED + résistance 220Ω sur la PIN 13

void setup() {
  pinMode(13, OUTPUT);
}

void loop() {
  digitalWrite(13, HIGH);
  delay(500);
  digitalWrite(13, LOW);
  delay(500);
}`

function ArduinoSim() {
  const [code, setCode] = useState(SAMPLE_CODE)
  const [delayMs, setDelayMs] = useState(500)
  const [running, setRunning] = useState(true)
  const [pin13, setPin13] = useState(false)
  const [console_, setConsole] = useState<string[]>([])

  // Parse the delay() call from the code (very basic)
  useEffect(() => {
    const m = code.match(/delay\((\d+)\)/)
    if (m) setDelayMs(parseInt(m[1], 10))
  }, [code])

  useEffect(() => {
    if (!running) return
    let cancelled = false
    let state = false
    const tick = () => {
      if (cancelled) return
      state = !state
      setPin13(state)
      setConsole((c) => [`[${new Date().toLocaleTimeString('fr-FR', { hour12: false })}] PIN 13 → ${state ? 'HIGH' : 'LOW'}`, ...c].slice(0, 12))
      setTimeout(tick, Math.max(50, delayMs))
    }
    const t = setTimeout(tick, Math.max(50, delayMs))
    return () => { cancelled = true; clearTimeout(t) }
  }, [running, delayMs])

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Code editor + board */}
      <div className="space-y-4">
        <div className="holo-card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-emerald-500/10 border-b border-emerald-400/20">
            <div className="flex items-center gap-2 text-xs text-emerald-100">
              <Cpu size={12} />
              <span className="font-bold">sketch.ino</span>
              <span className="text-emerald-300/70">· Arduino UNO</span>
            </div>
            <button onClick={() => setRunning((r) => !r)} className="btn-aurora text-xs py-1 px-3">
              {running ? <><Pause size={12} /> Stop</> : <><Play size={12} /> Compile & Run</>}
            </button>
          </div>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            className="w-full h-[260px] resize-none bg-black/40 px-4 py-3 font-mono text-xs text-emerald-100 outline-none"
          />
        </div>

        <div className="holo-card p-3">
          <h4 className="text-[10px] mono-kicker text-aurora-text-dim mb-2 px-1">Console série</h4>
          <div className="rounded-xl bg-black/50 px-3 py-2 max-h-[140px] overflow-auto font-mono text-[11px] text-emerald-200/90 space-y-0.5">
            {console_.length === 0 ? <span className="text-aurora-text-dim italic">En attente…</span> : console_.map((line, i) => <div key={i}>{line}</div>)}
          </div>
        </div>
      </div>

      {/* Board visualization */}
      <div className="holo-card holo-card-cyan p-5 lab-background relative overflow-hidden min-h-[420px]">
        <svg viewBox="0 0 360 460" className="w-full h-full">
          <defs>
            <linearGradient id="boardGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#0e7490" />
              <stop offset="100%" stopColor="#155e75" />
            </linearGradient>
          </defs>
          {/* Board outline */}
          <rect x="40" y="40" width="280" height="380" rx="14" fill="url(#boardGrad)" stroke="#22d3ee" strokeWidth="1.5" />
          {/* USB port */}
          <rect x="80" y="20" width="50" height="34" rx="3" fill="#94a3b8" />
          <rect x="86" y="26" width="38" height="22" rx="2" fill="#475569" />
          {/* Power jack */}
          <rect x="160" y="22" width="38" height="32" rx="3" fill="#1e293b" stroke="#475569" />

          {/* Microcontroller chip */}
          <rect x="120" y="180" width="120" height="60" rx="3" fill="#0f172a" stroke="#22d3ee" strokeWidth="0.5" />
          <text x="180" y="207" textAnchor="middle" className="fill-cyan-200 text-[8px]">ATmega328P</text>
          <text x="180" y="222" textAnchor="middle" className="fill-cyan-300/60 text-[7px]">UNO R3</text>

          {/* Digital pins (top) */}
          {Array.from({ length: 14 }).map((_, i) => (
            <g key={`dp-${i}`}>
              <rect x={50 + i * 18} y="80" width="12" height="14" fill="#0f172a" stroke="#22d3ee" strokeWidth="0.5" />
              <text x={56 + i * 18} y="76" textAnchor="middle" className="fill-cyan-300/70 text-[6px]">{13 - i}</text>
            </g>
          ))}
          {/* Analog pins */}
          {Array.from({ length: 6 }).map((_, i) => (
            <g key={`ap-${i}`}>
              <rect x={80 + i * 18} y="380" width="12" height="14" fill="#0f172a" stroke="#22d3ee" strokeWidth="0.5" />
              <text x={86 + i * 18} y="408" textAnchor="middle" className="fill-cyan-300/70 text-[6px]">A{i}</text>
            </g>
          ))}

          {/* On-board LED PIN 13 */}
          <circle cx="200" cy="120" r="6" fill={pin13 ? '#fde047' : '#1e293b'} stroke="#fde047" strokeWidth="1" className={pin13 ? 'led-on' : ''} style={{ color: '#fde047' }} />
          <text x="215" y="124" className="fill-cyan-100 text-[8px]">L (pin 13)</text>

          {/* External LED */}
          <line x1="62" y1="80" x2="62" y2="280" stroke="#ef4444" strokeWidth="1.5" />
          <line x1="62" y1="280" x2="20" y2="280" stroke="#ef4444" strokeWidth="1.5" />
          <circle cx="20" cy="300" r="14" fill={pin13 ? '#ec4899' : '#1e293b'} stroke="#ec4899" strokeWidth="2" className={pin13 ? 'led-on' : ''} style={{ color: '#ec4899' }} />
          {pin13 && (
            <>
              {[0, 60, 120, 180, 240, 300].map((d) => (
                <line key={d} x1="20" y1="280" x2="20" y2="270" stroke="#ec4899" strokeWidth="2" transform={`rotate(${d} 20 300)`} />
              ))}
            </>
          )}
        </svg>
        <div className="absolute bottom-4 left-4 right-4 rounded-xl bg-black/60 backdrop-blur p-3 border border-white/10">
          <div className="flex items-center justify-between text-xs">
            <span className="text-aurora-text-dim">PIN 13</span>
            <span className={`font-mono font-bold ${pin13 ? 'text-yellow-300' : 'text-slate-400'}`}>{pin13 ? 'HIGH (5V)' : 'LOW (0V)'}</span>
          </div>
          <div className="flex items-center justify-between text-xs mt-1">
            <span className="text-aurora-text-dim">Délai</span>
            <span className="font-mono text-cyan-300">{delayMs} ms</span>
          </div>
        </div>
      </div>
    </div>
  )
}
