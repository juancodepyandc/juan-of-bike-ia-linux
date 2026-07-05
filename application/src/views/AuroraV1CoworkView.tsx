/**
 * AuroraV1CoworkView — Editorial port of the Cowork orchestrator hero.
 *
 * Source design: _design/aurora_design_screens_v1/cowork.jsx (mock).
 * Wires the existing useCoworkStore (open/abortRun/isOpen) + useChatStore
 * (last user message → mission brief). The agent graph + log are
 * visually-faithful renderings; their data is currently static placeholder
 * with state binding to whether a cowork run is active. A future iteration
 * will wire real plan/log streams from the cowork orchestrator service.
 */
import { lazy, Suspense, useState } from 'react'
import AuroraSphereV1 from '../components/AuroraSphereV1'
import MachineConnectionsPanel from '../components/MachineConnectionsPanel'
import { useCoworkStore } from '../stores/coworkStore'
import { useChatStore } from '../stores/chatStore'
import { useAppStore } from '../stores/appStore'
// v82ao : useRealAgents extracted to a shared hook so V3 Cowork can
// reuse the same roundtrip + cache (one fetch, both consumers).
import { useRealAgents } from '../hooks/useRealAgents'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
// v81p: parity boost — CoworkConfirmDialog is mounted INSIDE the Aurora
// overlays so destructive-action approval prompts still fire correctly.
// A "Console technique" escape hatch lazy-loads the full manga CoworkOverlay
// when the user wants the streaming events log + plan + audit drawer that
// haven't yet been ported into the Aurora skins.
import CoworkConfirmDialog from '../components/CoworkConfirmDialog'
const CoworkOverlayLazy = lazy(() => import('../components/CoworkOverlay'))

function Eyebrow({ children, dot }: { children: React.ReactNode; dot?: string }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute)', display: 'flex', alignItems: 'center', gap: 8,
    }}>
      {dot && <span style={{
        width: 8, height: 8, borderRadius: 99, background: dot,
        boxShadow: `0 0 12px ${dot}`,
      }} />}
      {children}
    </div>
  )
}

function Display({ size = 36, children, style }: {
  size?: number; children: React.ReactNode; style?: React.CSSProperties
}) {
  return (
    <div style={{
      fontFamily: 'var(--font-display)', fontSize: size,
      fontStyle: 'italic', fontWeight: 400, lineHeight: 0.95,
      letterSpacing: '-0.02em', color: 'var(--fg)', ...style,
    }}>{children}</div>
  )
}

function Tag({ children, tint }: { children: React.ReactNode; tint?: string }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono)', fontSize: 10,
      letterSpacing: '0.08em', textTransform: 'uppercase',
      color: tint ?? 'var(--fg-dim)',
      padding: '3px 9px',
      border: `1px solid ${tint ? tint + '88' : 'var(--line-soft)'}`,
      borderRadius: 999, background: 'var(--bg-card)',
    }}>{children}</span>
  )
}

function Btn({ variant = 'ghost', children, onClick, disabled }: {
  variant?: 'primary' | 'ghost' | 'bare'
  children: React.ReactNode; onClick?: () => void; disabled?: boolean
}) {
  const fg = variant === 'primary' ? 'var(--ink-1000)' : 'var(--fg)'
  const bg = variant === 'primary' ? 'var(--ember-500)'
    : variant === 'bare' ? 'transparent' : 'var(--bg-card)'
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      style={{
        fontFamily: 'var(--font-sans)', fontSize: 13,
        padding: '9px 16px', background: bg, color: fg,
        border: variant === 'bare' ? 'none' : '1px solid var(--line)',
        borderRadius: 'var(--r-md)',
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
      }}>{children}</button>
  )
}

function Panel({ children, padded = true, raised, style }: {
  children: React.ReactNode; padded?: boolean; raised?: boolean
  style?: React.CSSProperties
}) {
  return (
    <div style={{
      background: raised ? 'var(--bg-raised)' : 'var(--bg-card)',
      border: '1px solid var(--line)',
      borderRadius: 'var(--r-lg)',
      padding: padded ? 18 : 0,
      ...style,
    }}>{children}</div>
  )
}

function AgentNode({ x, y, role, label, status, delay = 0 }: {
  x: number; y: number; role: string; label: string
  status: 'queued' | 'running' | 'done'
  /** Stagger the entrance — matches the source's 0/0.1/0.2/0.3/0.4s offsets */
  delay?: number
}) {
  const c = status === 'running' ? 'var(--ember-500)'
    : status === 'done' ? 'oklch(0.72 0.12 145)'
    : 'var(--fg-mute)'
  return (
    <div style={{
      position: 'absolute', left: `${x}%`, top: `${y}%`,
      transform: 'translate(-50%,-50%)',
      animation: `aurora-fadeup .8s var(--ease-out, cubic-bezier(0.16,1,0.3,1)) ${delay}s both`,
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--line)',
        borderRadius: 10, padding: '8px 12px', minWidth: 160,
        boxShadow: status === 'running'
          ? `0 0 24px ${c}33, 0 8px 30px rgba(0,0,0,.4)`
          : '0 8px 24px rgba(0,0,0,.3)',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 6, height: 6, borderRadius: 99, background: c,
            boxShadow: status !== 'queued' ? `0 0 8px ${c}` : 'none',
          }} />
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 10,
            color: 'var(--fg-mute)', letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}>{role}</span>
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, marginTop: 2, color: 'var(--fg)' }}>{label}</div>
        {status === 'running' && (
          <div style={{
            position: 'absolute', bottom: 0, left: 12, right: 12, height: 2,
            background: 'var(--line)', borderRadius: 99, overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', width: '60%', background: c,
              animation: 'aurora-progress 2.4s ease-in-out infinite',
            }} />
          </div>
        )}
      </div>
    </div>
  )
}

function Connector({ x1, y1, x2, y2, active }: {
  x1: number; y1: number; x2: number; y2: number; active?: boolean
}) {
  const X1 = x1 * 10, Y1 = y1 * 6
  const X2 = x2 * 10, Y2 = y2 * 6
  const MX = (X1 + X2) / 2, MY = (Y1 + Y2) / 2 - 30
  const path = `M ${X1} ${Y1} Q ${MX} ${MY} ${X2} ${Y2}`
  const gradId = `cnx-${X1}-${Y1}-${X2}-${Y2}`
  return (
    <svg viewBox="0 0 1000 600" preserveAspectRatio="none"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
      <defs>
        <linearGradient id={gradId} x1={X1} y1={Y1} x2={X2} y2={Y2} gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--line-strong, rgba(255,255,255,0.18))" stopOpacity="0.3" />
          <stop offset="100%"
            stopColor={active ? 'var(--ember-500, #ff6a3d)' : 'var(--line-strong, rgba(255,255,255,0.18))'}
            stopOpacity={active ? 0.95 : 0.5} />
        </linearGradient>
      </defs>
      <path d={path}
        stroke={`url(#${gradId})`}
        strokeWidth="1.4" fill="none"
        strokeDasharray={active ? '0' : '5 5'} />
      {active && (
        <circle r="3" fill="var(--ember-500, #ff6a3d)">
          <animateMotion dur="2.6s" repeatCount="indefinite" path={path} />
        </circle>
      )}
    </svg>
  )
}

export default function AuroraV1CoworkView({ open: openProp, onClose }: { open?: boolean; onClose?: () => void } = {}) {
  // When mounted as the global cowork overlay (via skinned launcher),
  // `openProp` controls visibility. When mounted standalone (legacy),
  // default to useCoworkStore.isOpen so behavior matches CoworkOverlay 1:1.
  const isOpen = useCoworkStore((s) => s.isOpen)
  const openCowork = useCoworkStore((s) => s.open)
  const abortRun = useCoworkStore((s) => s.abortRun)
  const messages = useChatStore((s) => s.messages)
  const mainModel = useAppStore((s) => s.mainModel)
  const agents = useRealAgents()

  // v82aa : the mission brief used to fall back to a fictitious sumi-e
  // sentence from the design source's mock. The user flagged that all
  // fictitious copy must go. Now : real last-user-message if present,
  // otherwise an empty-state prompt that invites typing the mission.
  const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')
  const [draftMission, setDraftMission] = useState('')
  // v82fv : drop fichier → injecte le contenu (texte/PDF/DOCX) dans
  // draftMission. Permet de coller un brief client ou cahier des
  // charges pour démarrer une mission Cowork orchestrée.
  const drop = useFileDrop({
    onFiles: async (files) => {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (const f of files) {
        try {
          const text = await readTextFile(f)
          const clamped = text.length > 6000
            ? text.slice(0, 6000) + '\n[... tronqué à 6 KB ...]'
            : text
          sections.push(`--- ${f.name} ---\n${clamped.trim()}`)
        } catch {
          sections.push(`--- ${f.name} ---\n(lecture impossible)`)
        }
      }
      const inject = sections.join('\n\n')
      setDraftMission((prev) => prev ? `${inject}\n\n${prev}` : inject)
    },
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: isOpen,
  })
  const missionBrief = lastUserMsg?.content || ''
  const missionShort = missionBrief.length > 90
    ? missionBrief.slice(0, 87) + '…' : missionBrief
  const noMission = !missionBrief.trim()

  // Agent statuses are derived from cowork state (running if open, queued otherwise)
  const baseStatus: 'queued' | 'running' | 'done' = isOpen ? 'running' : 'queued'

  // Skinned-overlay mode: when `openProp === false` we render nothing (matching
  // CoworkOverlay AnimatePresence semantics). When `openProp === undefined`
  // (legacy mount) the view always renders — useful for standalone preview.
  // Console technique = manga CoworkOverlay full-feature escape hatch.
  // Aurora skins re-skin the surface but the streaming events log, plan
  // steps and audit drawer are deeply coupled to CoworkOverlay's pipeline
  // — we delegate when the user explicitly wants them.
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
    <div {...drop.bind} style={{
      position: 'fixed', inset: 0, zIndex: 90,
      width: '100%', height: '100%',
      overflow: 'hidden', background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fv : hint visuel pendant drag-over */}
      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
          zIndex: 100, pointerEvents: 'none',
          padding: '8px 16px', borderRadius: 99,
          background: 'oklch(0.74 0.13 60 / 0.95)',
          color: 'var(--bg, #0c0a09)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          boxShadow: '0 6px 24px rgba(0,0,0,0.4)',
        }}>
          ⚙ Déposer brief de mission · txt / md / pdf / docx
        </div>
      )}
      {/* Destructive-action approval modal — same store, fires regardless of skin */}
      <CoworkConfirmDialog />

      {/* v82bb : Console technique escape hatch — restores the full
          monolithic feature set (events stream + plan + audit drawer +
          eval gate). Tooltip texte purgé du mot "manga" — le V1 ne
          doit plus exposer cette terminologie héritée à l'utilisateur. */}
      <button type="button" onClick={() => setShowConsole(true)}
        title="Ouvrir la console technique (events stream + plan + audit drawer)"
        style={{
          position: 'absolute', top: 18, right: 110, zIndex: 95,
          background: 'var(--bg-card, rgba(255,255,255,0.06))',
          color: 'var(--fg-dim, #aaa)',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8, padding: '8px 12px', cursor: 'pointer',
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: 11, letterSpacing: '0.16em',
        }}>⚙ CONSOLE TECHNIQUE</button>
      {onClose && (
        <button type="button" onClick={onClose}
          title="Fermer (Esc)"
          style={{
            position: 'absolute', top: 18, right: 24, zIndex: 95,
            background: 'var(--bg-card, rgba(255,255,255,0.06))',
            color: 'var(--fg, #f5f5f5)',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            borderRadius: 8, padding: '8px 12px', cursor: 'pointer',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: 11, letterSpacing: '0.16em',
          }}>× FERMER</button>
      )}
      {/* Hero band */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.05fr 1fr',
        gap: 0, padding: '40px 48px 24px', position: 'relative',
        height: '58%',
      }}>
        {/* Sphere placeholder + tech labels */}
        <div style={{ position: 'relative', minHeight: 420 }}>
          <Eyebrow dot="var(--ember-500)">◊ Cowork · Orchestrator</Eyebrow>
          <div style={{
            position: 'absolute', inset: '24px 24px 80px 0',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: 320, height: 320,
              filter: 'drop-shadow(0 0 80px oklch(0.70 0.15 40 / 0.3))',
            }}>
              <AuroraSphereV1
                tint="oklch(0.70 0.15 40)"
                state={isOpen ? 'thinking' : 'idle'}
                radius={0.42}
                glow={1.2}
              />
            </div>
          </div>
          <div style={{ position: 'absolute', top: 90, right: 36, textAlign: 'right' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--fg-dim)', marginBottom: 4 }}>state</div>
            <Display size={26}>{isOpen ? 'thinking' : 'ready'}</Display>
          </div>
          <div style={{ position: 'absolute', bottom: 110, left: 18 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--fg-dim)', marginBottom: 4 }}>agents · 4 active</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12,
              color: 'var(--fg)' }}>planner · fetcher · reader · writer</div>
          </div>
        </div>

        {/* Editorial mission */}
        <div style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
          paddingLeft: 32, borderLeft: '1px solid var(--line)',
        }}>
          <div>
            <Eyebrow>Mission · {String(messages.length).padStart(4, '0')}</Eyebrow>
            {noMission ? (
              // v82aa : real input zone replaces the fictitious display.
              // User explicitly said "j'ai pas de zone d'écrit" — fixed.
              <textarea
                value={draftMission}
                onChange={(e) => setDraftMission(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault()
                    if (draftMission.trim()) openCowork('conversation')
                  }
                }}
                placeholder="Décris ta mission · ⌘↵ pour lancer"
                rows={3}
                style={{
                  width: '100%', maxWidth: 520,
                  marginTop: 14, marginBottom: 20,
                  background: 'var(--bg-card, rgba(255,255,255,0.03))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  borderRadius: 10,
                  padding: '14px 16px',
                  color: 'var(--fg, #f5f5f5)',
                  fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                  fontStyle: 'italic',
                  fontSize: 24, lineHeight: 1.25,
                  letterSpacing: '-0.01em',
                  resize: 'vertical',
                  outline: 'none',
                }}
              />
            ) : (
              <Display size={56} style={{ marginTop: 14, marginBottom: 20 }}>
                {missionShort}
              </Display>
            )}
            {/* v82fv : daily tip Cowork quand pas de mission encore */}
            {noMission && (
              <div style={{
                marginTop: 12, padding: '6px 10px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                color: 'var(--fg-dim, #aaa)',
                background: 'oklch(0.74 0.13 60 / 0.06)',
                border: '1px solid oklch(0.74 0.13 60 / 0.22)',
                borderRadius: 6, maxWidth: 520, lineHeight: 1.55,
              }}>
                {getDailyTip('cowork')}
              </div>
            )}
            <p style={{
              fontFamily: 'var(--font-sans)', fontSize: 15, lineHeight: 1.55,
              color: 'var(--fg-dim)', maxWidth: 480,
            }}>
              Aurora orchestre{' '}
              {agents.count > 0 ? (
                <em style={{ color: 'var(--fg)' }}>
                  {agents.leads.length} leads · {agents.count} agents
                </em>
              ) : (
                <em style={{ color: 'var(--fg)' }}>tes agents locaux</em>
              )}{' '}
              pour traiter ta mission via{' '}
              <em style={{ color: 'var(--fg)' }}>{mainModel}</em>.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 24, alignItems: 'center' }}>
            {isOpen ? (
              <Btn variant="primary" onClick={abortRun}>Pause mission</Btn>
            ) : (
              <Btn variant="primary"
                onClick={() => openCowork('conversation')}
                disabled={noMission && !draftMission.trim()}>
                Lancer mission
              </Btn>
            )}
            <Btn variant="ghost">Voir le plan</Btn>
            <Btn variant="bare">Annuler</Btn>
            <span style={{ flex: 1 }} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--fg-dim)' }}>
              {isOpen ? 'live' : `prêt · ${mainModel}`}
            </span>
          </div>
        </div>
      </div>

      <div style={{ height: 1, background: 'var(--line)', margin: '0 48px' }} />

      {/* Lower band */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr',
        gap: 24, padding: '24px 48px', height: 'calc(42% - 1px)',
      }}>
        {/* Agent graph */}
        <Panel padded={false} style={{ position: 'relative', overflow: 'hidden', minHeight: 240 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 18px', borderBottom: '1px solid var(--line)',
          }}>
            <Eyebrow>Agent graph · {isOpen ? 'live' : 'idle'}</Eyebrow>
            <div style={{ display: 'flex', gap: 6 }}>
              <Tag>compact</Tag>
              <Tag tint="var(--ember-500)">flow</Tag>
            </div>
          </div>
          <div style={{ position: 'relative', height: 'calc(100% - 50px)' }}>
            <Connector x1={12} y1={50} x2={36} y2={28} active={isOpen} />
            <Connector x1={12} y1={50} x2={36} y2={75} active={isOpen} />
            <Connector x1={36} y1={28} x2={64} y2={50} active={isOpen} />
            <Connector x1={36} y1={75} x2={64} y2={50} active={isOpen} />
            <Connector x1={64} y1={50} x2={88} y2={50} active={isOpen} />
            <AgentNode x={12} y={50} role="planner" label={mainModel + ' · plan'} status={baseStatus} delay={0} />
            <AgentNode x={36} y={28} role="fetcher" label="web · arxiv + scholar" status={baseStatus} delay={0.1} />
            <AgentNode x={36} y={75} role="reader" label="qwen3-vl · extract" status={baseStatus} delay={0.2} />
            <AgentNode x={64} y={50} role="critic" label="self-critique loop" status={baseStatus} delay={0.3} />
            <AgentNode x={88} y={50} role="writer" label="streaming synthesis" status={isOpen ? 'running' : 'queued'} delay={0.4} />
          </div>
        </Panel>

        {/* Log + metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
          <Panel raised style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <Eyebrow dot="oklch(0.74 0.12 145)">Live · console</Eyebrow>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-dim)' }}>
                tail · {messages.length}
              </span>
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.8,
              maxHeight: 200, overflow: 'auto',
            }}>
              {messages.slice(-7).map((m, i) => (
                <div key={m.id} style={{
                  display: 'grid', gridTemplateColumns: '64px 80px 1fr', gap: 12,
                  color: m.role === 'assistant' ? 'var(--fg)' : 'var(--fg-dim)',
                }}>
                  <span style={{ color: 'var(--fg-mute)' }}>
                    {new Date(m.timestamp).toTimeString().slice(0, 8)}
                  </span>
                  <span style={{ color: 'var(--fg-dim)' }}>[{m.role}]</span>
                  <span>{m.content.slice(0, 60)}{m.content.length > 60 ? '…' : ''}</span>
                </div>
              ))}
              {messages.length === 0 && (
                <div style={{ color: 'var(--fg-mute)' }}>
                  Aucun tour en cours. Lance une mission pour activer la console.
                </div>
              )}
            </div>
          </Panel>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            {[
              { l: 'Tours', v: String(messages.length), s: 'session' },
              { l: 'Coût', v: '0,00 €', s: 'local' },
              { l: 'Modèle', v: mainModel.slice(0, 8), s: 'main' },
            ].map((k) => (
              <Panel key={k.l} style={{ padding: 12 }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: 'var(--fg-dim)', marginBottom: 4 }}>{k.l}</div>
                <Display size={26}>{k.v}</Display>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11,
                  color: 'var(--ember-500)', marginTop: 2 }}>{k.s}</div>
              </Panel>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes aurora-pulse {
          0%, 100% { transform: scale(1); filter: brightness(1) }
          50%      { transform: scale(1.04); filter: brightness(1.15) }
        }
        @keyframes aurora-fadeup {
          from { opacity: 0; transform: translate(-50%, -45%) }
          to   { opacity: 1; transform: translate(-50%, -50%) }
        }
        @keyframes aurora-progress {
          0%   { transform: translateX(-100%) }
          100% { transform: translateX(280%) }
        }
      `}</style>
      <div style={{ padding: 16, maxWidth: 1200, margin: '0 auto' }}>
        <CoworkMachineSection />
      </div>
    </div>
  )
}

function CoworkMachineSection() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} style={{
        background: 'rgba(94,124,222,.2)', color: '#e6e8eb',
        border: '1px solid rgba(94,124,222,.4)', borderRadius: 6,
        padding: '8px 14px', fontSize: 13, cursor: 'pointer',
        marginBottom: 10,
      }}>{open ? '▾' : '▸'} Machines à piloter (SSH / Pi / VPS / NAS) — Aurora prend le contrôle</button>
      {open && <MachineConnectionsPanel embed />}
    </div>
  )
}
