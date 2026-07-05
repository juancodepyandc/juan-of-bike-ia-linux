/**
 * AuroraAgentMascot — avatars Bitmoji-like via DiceBear avataaars (V3 only).
 *
 * v82lkc : pivot vers DiceBear avataaars (Pablo Stanley, même esthétique
 * que Bitmoji originel). Avant on rendait du SVG fait-main qui ressemblait
 * à du stick-figure. Maintenant chaque agent a un avatar haute qualité
 * paramétrique (coiffure, lunettes, vêtements, peau, expression) chargé
 * depuis https://api.dicebear.com/9.x/avataaars/svg?seed=...
 *
 * Le wrapper garde tous les overlays cartoon par état :
 *   idle       bobbing 4s + blink 6s sur l'avatar
 *   thinking   blueprint/parchment qui se déroule à gauche
 *   working    billboard couleur agent + label + timer mm:ss réel
 *              + smoke puffs + sparks
 *   done       7 confettis qui montent en spirale
 *   error      head tilt + sweat drop
 */
import { useEffect, useRef, useState } from 'react'
import type { ModuleId } from '../types/app'
import {
  getAgent,
  getAvatarUrl,
  type AgentRuntimeState,
  type AgentState,
  type AuroraAgent,
  type ProductionAgentId,
} from '../services/auroraAgents'

// v82n2: map runtime state (8) → legacy mascot state (5) for CSS/animations.
function toMascotState(s: AgentRuntimeState | AgentState | undefined): AgentState {
  switch (s) {
    case 'planning':
    case 'verifying':
    case 'handoff':
      return 'working'
    case undefined:
      return 'idle'
    default:
      return s
  }
}

type Props = {
  // v82n2: accepte aussi ProductionAgentId ('manager') — fallback chat.
  moduleId: ModuleId | ProductionAgentId
  state?: AgentState | AgentRuntimeState
  size?: number
  showLabel?: boolean
  showScene?: boolean
  onClick?: () => void
  workStartedAt?: number | null
}

export default function AuroraAgentMascot({
  moduleId,
  state: rawState = 'idle',
  size = 180,
  showLabel = true,
  showScene = true,
  onClick,
  workStartedAt,
}: Props) {
  // 'manager' n a pas de fiche dans AURORA_AGENTS_DEFAULT — on retombe sur
  // l agent conversation (Lyra) pour l affichage avatar/CSS.
  const safeModuleId: ModuleId = (moduleId === 'manager' ? 'conversation' : moduleId) as ModuleId
  const state = toMascotState(rawState)
  const [agent, setAgent] = useState<AuroraAgent>(() => getAgent(safeModuleId))

  useEffect(() => {
    setAgent(getAgent(safeModuleId))
    const onUpdate = (ev: Event) => {
      const detail = (ev as CustomEvent<{ id?: ModuleId }>).detail
      if (!detail || !detail.id || detail.id === safeModuleId) {
        setAgent(getAgent(safeModuleId))
      }
    }
    window.addEventListener('aurora-agents-updated', onUpdate)
    return () => window.removeEventListener('aurora-agents-updated', onUpdate)
  }, [safeModuleId])

  // Real-time timer for working state — capture le start UNE fois.
  const [workStart, setWorkStart] = useState<number | null>(null)
  useEffect(() => {
    if (state === 'working') {
      setWorkStart(workStartedAt ?? Date.now())
    } else {
      setWorkStart(null)
    }
  }, [state, workStartedAt])
  const elapsed = useElapsed(workStart)

  return (
    <button
      type="button"
      className={`aurora-mascot is-${state} agent-${moduleId}`}
      onClick={onClick}
      title={`${agent.name} — ${agent.role}\n"${agent.motto}"\nClic pour configurer`}
      aria-label={`Agent ${agent.name}, état ${state}`}
      style={{
        background: 'transparent',
        border: 'none',
        padding: 0,
        cursor: onClick ? 'pointer' : 'default',
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
      }}
    >
      <div className="aurora-mascot-stage" style={{ width: size + 80, position: 'relative' }}>
        {/* working scene billboard with real timer */}
        {showScene && state === 'working' && (
          <SceneBillboard agent={agent} elapsed={elapsed} />
        )}
        {/* thinking blueprint / parchment overlay */}
        {showScene && state === 'thinking' && (
          <ThinkingProp agent={agent} />
        )}
        {/* avatar (DiceBear SVG) */}
        <AgentAvatar agent={agent} size={size} state={state} />
        {/* working extras (smoke, sparks) */}
        {showScene && state === 'working' && (
          <WorkingFx />
        )}
        {/* done confetti */}
        {showScene && state === 'done' && (
          <DoneConfetti color={agent.color} />
        )}
      </div>

      {showLabel && (
        <div style={{
          textAlign: 'center',
          fontFamily: '"Courier New", Courier, monospace',
          fontSize: 11,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          lineHeight: 1.3,
          color: agent.color,
          maxWidth: size + 80,
          textShadow: '0 1px 0 rgba(255,255,255,0.4)',
        }}>
          <div style={{ fontWeight: 700, fontSize: 12 }}>{agent.name}</div>
          <div style={{ opacity: 0.75, fontSize: 9 }}>{agent.role}</div>
        </div>
      )}
    </button>
  )
}

/* ---------- Real-time elapsed timer ---------- */
function useElapsed(startedAt: number | null): number {
  const [now, setNow] = useState<number>(() => Date.now())
  const startRef = useRef<number | null>(startedAt)

  useEffect(() => {
    startRef.current = startedAt
    if (startedAt === null) return
    const id = window.setInterval(() => setNow(Date.now()), 200)
    return () => window.clearInterval(id)
  }, [startedAt])

  if (startedAt === null) return 0
  return Math.max(0, Math.round((now - startedAt) / 1000))
}

function formatElapsed(s: number): string {
  const mm = Math.floor(s / 60).toString().padStart(2, '0')
  const ss = (s % 60).toString().padStart(2, '0')
  return `${mm}:${ss}`
}

/* ---------- Avatar : DiceBear avataaars ---------- */
function AgentAvatar({ agent, size, state: _state }: { agent: AuroraAgent; size: number; state: AgentState }) {
  const url = getAvatarUrl(agent.id, agent.name)
  return (
    <div className="aurora-mascot-body" style={{
      width: size,
      height: size,
      margin: '0 auto',
      position: 'relative',
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'center',
    }}>
      <img
        src={url}
        alt={`Avatar ${agent.name}`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          display: 'block',
          filter: 'drop-shadow(0 6px 10px rgba(0, 0, 0, 0.18))',
          borderRadius: '50%',
        }}
        onError={(e) => {
          // Fallback : cache l'image cassée pour ne pas afficher
          // l'icône broken-image. Le wrapper reste avec son aria.
          e.currentTarget.style.visibility = 'hidden'
        }}
      />
    </div>
  )
}

/* ---------- Working scene billboard ---------- */
function SceneBillboard({ agent, elapsed }: { agent: AuroraAgent; elapsed: number }) {
  const labels: Record<ModuleId, string> = {
    '3d':           'CONSTRUCTION',
    image:          'PEINTURE',
    video:          'TOURNAGE',
    code:           'COMPILATION',
    drawing:        'ESQUISSE',
    learning:       'COURS',
    cyber:          'ANALYSE',
    conversation:   'RÉFLEXION',
    voice:          'ÉCOUTE',
  }
  const label = labels[agent.id]
  return (
    <div
      className="m-billboard"
      style={{
        position: 'absolute',
        right: 0,
        top: 12,
        background: agent.color,
        color: '#fff',
        fontFamily: '"Courier New", Courier, monospace',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.1em',
        padding: '5px 10px',
        border: '2px solid #1c1614',
        borderRadius: 2,
        boxShadow: '3px 3px 0 #1c1614',
        textTransform: 'uppercase',
        textAlign: 'center',
        minWidth: 76,
        zIndex: 3,
      }}
    >
      <div style={{ fontSize: 9, opacity: 0.85 }}>{label}</div>
      <div style={{ fontSize: 15, marginTop: 2 }}>{formatElapsed(elapsed)}</div>
      {/* Stake under billboard */}
      <div style={{
        position: 'absolute',
        bottom: -16,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 4,
        height: 16,
        background: '#5a3a1a',
      }} />
    </div>
  )
}

/* ---------- Thinking prop (blueprint / parchment) ---------- */
function ThinkingProp({ agent }: { agent: AuroraAgent }) {
  return (
    <div className="m-think-prop" style={{
      position: 'absolute',
      left: 0,
      top: 36,
      width: 60,
      height: 44,
      background: agent.id === '3d' ? '#5ba4d4' : agent.id === 'drawing' ? '#f4ecd9' : '#fff',
      border: '2px solid #1c1614',
      borderRadius: 2,
      transform: 'rotate(-6deg)',
      zIndex: 3,
      padding: 6,
    }}>
      <div style={{ height: 1.8, background: agent.color, marginBottom: 4 }} />
      <div style={{ height: 1.5, background: agent.color, opacity: 0.6, marginBottom: 4, width: '70%' }} />
      <div style={{ height: 1.5, background: agent.color, opacity: 0.6, marginBottom: 4, width: '85%' }} />
      <div style={{ height: 1.5, background: agent.color, opacity: 0.4, width: '60%' }} />
    </div>
  )
}

/* ---------- Working effects (smoke + sparks) ---------- */
function WorkingFx() {
  return (
    <div className="m-working-fx" style={{
      position: 'absolute',
      left: 8, right: 8, bottom: 8, top: 60,
      pointerEvents: 'none',
      zIndex: 1,
    }}>
      <div className="m-puff m-puff-1" style={puffStyle(8, 70)} />
      <div className="m-puff m-puff-2" style={puffStyle(2, 56)} />
      <div className="m-puff m-puff-3" style={puffStyle(-4, 44)} />
      <div className="m-spark" style={sparkStyle(20, 80, 0)}>★</div>
      <div className="m-spark" style={sparkStyle(36, 96, 0.2)}>✦</div>
    </div>
  )
}

function puffStyle(left: number, top: number): React.CSSProperties {
  return {
    position: 'absolute',
    left, top,
    width: 18, height: 18,
    borderRadius: '50%',
    background: 'rgba(120, 120, 120, 0.45)',
  }
}
function sparkStyle(left: number, top: number, delay: number): React.CSSProperties {
  return {
    position: 'absolute',
    left, top,
    fontSize: 16,
    color: '#ffd54a',
    animationDelay: `${delay}s`,
    textShadow: '0 0 6px rgba(255, 213, 74, 0.6)',
  }
}

/* ---------- Done confetti ---------- */
function DoneConfetti({ color }: { color: string }) {
  const items = [
    { x: 14, y: 24, c: color, delay: 0 },
    { x: 130, y: 14, c: '#ffd54a', delay: 0.1 },
    { x: 170, y: 50, c: color, delay: 0.2 },
    { x: 18, y: 100, c: '#5ba4d4', delay: 0.3 },
    { x: 168, y: 110, c: '#5fa37e', delay: 0.4 },
    { x: 80, y: 6, c: color, delay: 0.5 },
    { x: 120, y: 6, c: '#9b7eb5', delay: 0.6 },
  ]
  return (
    <div className="m-confetti" style={{
      position: 'absolute',
      left: 0, right: 0, top: 0, bottom: 0,
      pointerEvents: 'none',
      zIndex: 4,
    }}>
      {items.map((it, i) => (
        <div
          key={i}
          className="m-confetti-piece"
          style={{
            position: 'absolute',
            left: it.x, top: it.y,
            width: 8, height: 12,
            background: it.c,
            transform: `rotate(${i * 25}deg)`,
            animationDelay: `${it.delay}s`,
          }}
        />
      ))}
    </div>
  )
}
