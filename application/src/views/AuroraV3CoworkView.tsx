/**
 * AuroraV3CoworkView — Ricochet "mission control HUD" port.
 *
 * Source design: _design/aurora_design_screens_v3/screens-1.jsx · CoworkV3.
 * Phosphor-green CRT mission control with radar sweep, agent roster,
 * telemetry bars, mission log, command bar. Animated via rAF.
 *
 * Wiring: useCoworkStore (open/abortRun/isOpen) drives the EXEC/ABORT
 * buttons + the "ARMED" status. useChatStore.messages feeds the mission
 * log (recent assistant/user pairs as MISSION_LOG lines). Telemetry
 * values are static placeholders (would need a runtime-stats store to
 * make real — queued for a future iteration).
 */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useCoworkStore } from '../stores/coworkStore.ts'
import { useChatStore } from '../stores/chatStore.ts'
import { useAppStore } from '../stores/appStore.ts'
// v82ao : real agent roster from /api/agents/list (replaces hardcoded
// CDX-01 / PCT-04 / SCH-02 / CST-01 / VOX-03 mock callsigns)
import { useRealAgents } from '../hooks/useRealAgents.ts'
// v81p: parity boost — CoworkConfirmDialog mounted inside V3 overlay so
// destructive-action prompts always fire. "[CONSOLE]" button lazy-mounts
// the full manga CoworkOverlay (events stream + plan + audit drawer).
import CoworkConfirmDialog from '../components/CoworkConfirmDialog.tsx'
const CoworkOverlayLazy = lazy(() => import('../components/CoworkOverlay'))

const PHOSPHOR = '#7df9c4'
const PHOSPHOR_DIM = '#3eb89b'
const TEAL_LINE = '#15524d'
const AMBER = '#ffb938'
const BG = '#031a1a'

export default function AuroraV3CoworkView({ open: openProp, onClose }: { open?: boolean; onClose?: () => void } = {}) {
  // Same skinned-overlay contract as AuroraV1CoworkView: when `openProp === false`
  // we render nothing (matches CoworkOverlay AnimatePresence semantics).
  const isOpen = useCoworkStore((s) => s.isOpen)
  const openCowork = useCoworkStore((s) => s.open)
  const abortRun = useCoworkStore((s) => s.abortRun)
  const messages = useChatStore((s) => s.messages)
  const mainModel = useAppStore((s) => s.mainModel)

  // rAF time for radar sweep + telemetry oscillation
  const [t, setT] = useState(0)
  const rafRef = useRef<number | null>(null)
  useEffect(() => {
    let stopped = false
    const loop = () => {
      if (stopped) return
      setT(performance.now() / 1000)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => {
      stopped = true
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [])
  const sweep = (t * 60) % 360

  const utc = new Date().toISOString().slice(11, 19)
  const armedColor = isOpen ? AMBER : PHOSPHOR_DIM

  // v82ao : roster fed from real /api/agents/list. The 5 first leads
  // map to the 5 fixed graph slots. Each lead's callsign is derived
  // from its name (e.g. "code-lead" → "CODE-01"), the role is the
  // lead's name uppercased, the model column is mainModel for the
  // active running lead, "LOCAL" for the others, and the status
  // depends on the cowork run state.
  const realAgents = useRealAgents()
  const leadNames = realAgents.leads.length > 0
    ? realAgents.leads
    : ['conversation-lead', 'image-lead', 'code-lead', '3d-lead', 'voice-lead']
  const agents: [string, string, string, string, string][] = leadNames.slice(0, 5).map((leadName, i) => {
    const tokens = leadName.replace('-lead', '').split('-')
    const callsign = `${tokens[0].toUpperCase().slice(0, 3)}-${String(i + 1).padStart(2, '0')}`
    const role = leadName.replace('-lead', '').toUpperCase()
    const isPrimary = i === 0
    const model = isPrimary ? mainModel.toUpperCase().slice(0, 10) : 'LOCAL'
    const status = isOpen
      ? (isPrimary ? 'RUN' : 'RDY')
      : (isPrimary ? 'IDLE' : 'IDLE')
    const color = isOpen
      ? (isPrimary ? AMBER : PHOSPHOR)
      : PHOSPHOR_DIM
    return [callsign, role, model, status, color]
  })

  const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')
  const missionBrief = lastUserMsg?.content
    ? lastUserMsg.content.toUpperCase().slice(0, 80) + (lastUserMsg.content.length > 80 ? '…' : '')
    : 'AUCUNE MISSION ACTIVE — DICTEZ UN BRIEF VIA CONVERSATION'

  const [showConsole, setShowConsole] = useState(false)

  if (openProp === false) return null

  if (showConsole) {
    return (
      <Suspense fallback={null}>
        <CoworkOverlayLazy open={openProp ?? true} onClose={() => {
          setShowConsole(false)
          onClose?.()
        }} />
      </Suspense>
    )
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 90,
      width: '100%', height: '100%', background: BG, color: PHOSPHOR,
      fontFamily: 'JetBrains Mono, monospace', fontSize: 12, padding: 20,
      display: 'grid', gridTemplateColumns: '300px 1fr 280px',
      gridTemplateRows: '40px 1fr 120px',
      gap: 12, overflow: 'hidden',
    }}>
      {/* Destructive-action approval modal — same store, fires regardless of skin */}
      <CoworkConfirmDialog />

      <button type="button" onClick={() => setShowConsole(true)}
        title="Console technique (events + plan + audit)"
        style={{
          position: 'absolute', top: 14, right: 130, zIndex: 95,
          background: 'transparent', color: AMBER,
          border: `1px solid ${AMBER}`, padding: '6px 12px', cursor: 'pointer',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10, letterSpacing: '0.2em',
        }}>[CONSOLE]</button>

      {onClose && (
        <button type="button" onClick={onClose}
          title="Fermer (Esc)"
          style={{
            position: 'absolute', top: 14, right: 16, zIndex: 95,
            background: 'transparent', color: PHOSPHOR,
            border: `1px solid ${PHOSPHOR}`, padding: '6px 12px', cursor: 'pointer',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10, letterSpacing: '0.2em',
          }}>[ESC] EXIT</button>
      )}
      {/* Scanlines */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,0,0,0.25) 2.5px, transparent 3px)',
        zIndex: 10,
      }} />
      {/* CRT vignette */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at center, transparent 50%, #000 110%)',
        zIndex: 11,
      }} />

      {/* Top header */}
      <header style={{
        gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', borderBottom: `1px solid ${TEAL_LINE}`, paddingBottom: 6,
      }}>
        <span>▣ AURORA / MISSIONCTRL · ORBIT {String(messages.length).padStart(4, '0')} · COWORK</span>
        <span>UTC {utc} · {isOpen ? 'LIVE' : 'STBY'}</span>
        <span style={{ color: armedColor }}>● {isOpen ? 'ARMED' : 'IDLE'}</span>
      </header>

      {/* Left: agent roster + throughput */}
      <div style={{ border: `1px solid ${TEAL_LINE}`, padding: 12, fontSize: 11 }}>
        <div style={{ color: PHOSPHOR_DIM, marginBottom: 10 }}>// AGENT_ROSTER</div>
        {agents.map(([id, n, m, s, c]) => (
          <div key={id} style={{
            display: 'grid', gridTemplateColumns: '60px 1fr 38px',
            padding: '6px 0', borderBottom: `1px dashed ${TEAL_LINE}`,
            alignItems: 'baseline',
          }}>
            <span style={{ color: PHOSPHOR_DIM }}>{id}</span>
            <span>
              <span style={{ color: PHOSPHOR }}>{n}</span>{' '}
              <span style={{ color: PHOSPHOR_DIM, fontSize: 9 }}>{m}</span>
            </span>
            <span style={{ color: c, textAlign: 'right' }}>{s}</span>
          </div>
        ))}
        <div style={{ marginTop: 14, color: PHOSPHOR_DIM }}>// THROUGHPUT</div>
        <div style={{ marginTop: 6 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', padding: '2px 0',
            }}>
              <span style={{ color: PHOSPHOR_DIM }}>T+{i}m</span>
              <span>
                {'█'.repeat(Math.max(2, Math.round(8 + Math.sin(t + i) * 6)))}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Center: radar */}
      <div style={{ border: `1px solid ${TEAL_LINE}`, position: 'relative', overflow: 'hidden' }}>
        <svg viewBox="0 0 400 400" width="100%" height="100%" style={{ display: 'block' }}>
          {[40, 80, 120, 160, 200].map((r) => (
            <circle key={r} cx="200" cy="200" r={r} fill="none" stroke={TEAL_LINE} strokeWidth="1" />
          ))}
          {[0, 30, 60, 90, 120, 150].map((a) => {
            const ra = a * Math.PI / 180
            return <line key={a}
              x1={200 - Math.cos(ra) * 200} y1={200 - Math.sin(ra) * 200}
              x2={200 + Math.cos(ra) * 200} y2={200 + Math.sin(ra) * 200}
              stroke={TEAL_LINE} strokeWidth="0.5" />
          })}
          <defs>
            <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={PHOSPHOR} stopOpacity="0.5" />
              <stop offset="100%" stopColor={PHOSPHOR} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={`M 200 200 L ${200 + Math.cos(sweep * Math.PI / 180) * 200} ${200 + Math.sin(sweep * Math.PI / 180) * 200} A 200 200 0 0 0 ${200 + Math.cos((sweep - 40) * Math.PI / 180) * 200} ${200 + Math.sin((sweep - 40) * Math.PI / 180) * 200} Z`}
            fill="url(#sweep)" opacity="0.6" />
          {/* v82ao : 4 radar blips reuse the first 4 real-agent callsigns
              from the roster above so the radar shows the user's actual
              leads instead of the design source mock callsigns. */}
          {[
            [120, 90, agents[0]?.[0] ?? 'CDX-01'],
            [260, 140, agents[1]?.[0] ?? 'PCT-04'],
            [180, 280, agents[2]?.[0] ?? 'SCH-02'],
            [310, 250, agents[3]?.[0] ?? 'CST-01'],
          ].map(([x, y, lbl]) => (
            <g key={lbl as string}>
              <circle cx={x as number} cy={y as number} r="4" fill={AMBER} />
              <circle cx={x as number} cy={y as number} r="10" fill="none"
                stroke={AMBER} opacity={0.4 + 0.4 * Math.sin(t * 3 + (x as number))} />
              <text x={(x as number) + 14} y={(y as number) + 4} fontSize="10" fill={AMBER}
                fontFamily="JetBrains Mono">{lbl}</text>
            </g>
          ))}
          <circle cx="200" cy="200" r="6" fill={PHOSPHOR} />
          <text x="200" y="395" textAnchor="middle" fontSize="9" fill={PHOSPHOR_DIM}
            fontFamily="JetBrains Mono">
            RANGE 200KM · BEARING {Math.round(sweep)}°
          </text>
        </svg>
      </div>

      {/* Right: telemetry + mission_log */}
      <div style={{ border: `1px solid ${TEAL_LINE}`, padding: 12, fontSize: 11,
                    display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ color: PHOSPHOR_DIM, marginBottom: 10 }}>// TELEMETRY</div>
        {[
          { k: 'VRAM', v: 22.4, max: 32, u: 'GiB' },
          { k: 'CPU', v: 41, max: 100, u: '%' },
          { k: 'NET', v: 0, max: 100, u: 'kb/s', off: true },
          { k: 'TOK', v: messages.reduce((a, m) => a + m.content.length, 0), max: 100000, u: '' },
        ].map(({ k, v, max, u, off }) => (
          <div key={k} style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: PHOSPHOR_DIM }}>{k}</span>
              <span style={{ color: off ? AMBER : PHOSPHOR }}>
                {off ? 'OFFLN' : `${v}${u}`}
              </span>
            </div>
            <div style={{ height: 8, background: '#0a2a26', marginTop: 4, position: 'relative' }}>
              <div style={{
                position: 'absolute', inset: 0, width: `${(v / max) * 100}%`,
                background: off ? AMBER : PHOSPHOR, opacity: 0.6,
              }} />
            </div>
          </div>
        ))}
        <div style={{ color: PHOSPHOR_DIM, margin: '14px 0 6px' }}>// MISSION_LOG</div>
        <div style={{ fontSize: 10, lineHeight: 1.6, flex: 1, overflow: 'auto', minHeight: 0 }}>
          {messages.slice(-5).map((m, i) => (
            <div key={m.id} style={{
              color: m.role === 'assistant' ? PHOSPHOR : PHOSPHOR_DIM,
            }}>
              {new Date(m.timestamp).toTimeString().slice(0, 8)} ►{' '}
              {(m.role === 'user' ? 'CDX' : 'AURORA')} {m.content.slice(0, 32).toUpperCase()}
              {m.content.length > 32 ? '…' : ''}
            </div>
          ))}
          {messages.length === 0 && (
            <div style={{ color: PHOSPHOR_DIM }}>
              {new Date().toTimeString().slice(0, 8)} ► STBY · NO ACTIVE MISSION
            </div>
          )}
          <div style={{ animation: 'blink 1s infinite' }}>
            {new Date().toTimeString().slice(0, 8)} ► _
          </div>
        </div>
      </div>

      {/* Bottom: command */}
      <footer style={{
        gridColumn: '1 / -1', border: `1px solid ${TEAL_LINE}`, padding: 10,
        display: 'grid', gridTemplateColumns: '1fr auto', gap: 12,
      }}>
        <div>
          <div style={{ color: PHOSPHOR_DIM, fontSize: 10 }}>&gt; MISSION_BRIEF</div>
          <div style={{ color: PHOSPHOR, fontSize: 13, marginTop: 4 }}>
            {missionBrief}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={isOpen ? abortRun : undefined} disabled={!isOpen}
            style={{
              background: 'transparent', color: PHOSPHOR,
              border: `1px solid ${PHOSPHOR}`, padding: '8px 18px',
              fontFamily: 'inherit', fontSize: 11,
              cursor: isOpen ? 'pointer' : 'not-allowed', opacity: isOpen ? 1 : 0.4,
            }}>[ABORT]</button>
          <button disabled={!isOpen}
            style={{
              background: 'transparent', color: PHOSPHOR,
              border: `1px solid ${PHOSPHOR}`, padding: '8px 18px',
              fontFamily: 'inherit', fontSize: 11,
              cursor: isOpen ? 'pointer' : 'not-allowed', opacity: isOpen ? 1 : 0.4,
            }}>[PAUSE]</button>
          <button onClick={() => openCowork('conversation')}
            style={{
              background: PHOSPHOR, color: BG, border: `1px solid ${PHOSPHOR}`,
              padding: '8px 18px', fontFamily: 'inherit', fontSize: 11,
              cursor: 'pointer', fontWeight: 700,
            }}>[EXEC]</button>
        </div>
      </footer>

      <style>{`@keyframes blink { 50% { opacity: 0 } }`}</style>
    </div>
  )
}
