/**
 * AuroraAgentScene — scène animée par module avec avatar embarqué dans
 * un décor thématique (V3 only).
 *
 * v82lke : remplace le simple "floater corner" par un PANEL DE SCÈNE
 * en bas du wrapper V3 (height ~280px) où l'agent est dans son
 * environnement de travail :
 *
 *   conversation  WriterScene  Lyra à son bureau + feuille où le texte
 *                              streamé apparaît en TEMPS RÉEL (lié à
 *                              chatStore.streamContent)
 *   3d            BuildScene   Atlas sur chantier + marteau qui frappe
 *                              + nuages de fumée + pancarte timer
 *   image         StudioScene  Iris devant chevalet, palette en main
 *   video         FilmScene    Cinéma derrière caméra avec clap
 *   code          DeskScene    Glyph devant moniteur avec scan-lines
 *   drawing       SumiScene    Sumi avec pinceau japonais sur parchemin
 *   learning      LectureScene Sage devant tableau noir
 *   cyber         WatchScene   Phantom devant terminal scrolling logs
 *
 * Multi-personnages : si voiceActive est passé, on rend un second
 * avatar qui "dicte" pendant que l'agent principal écrit (cas chat).
 */
import { useEffect, useState } from 'react'
import type { ModuleId } from '../types/app'
import { useChatStore } from '../stores/chatStore'
import { getAgent, type AgentState, type AuroraAgent } from '../services/auroraAgents'
// v82s-studio iter12 : on remplace les images statiques DiceBear par les
// avatars SVG vivants de la v10 (anatomie 35+ éléments, 40 keyframes Pixar :
// respiration, clignement, mèches qui suivent…). Le simple import injecte la
// feuille de keyframes <style id="a10-keyframes">, donc la figure « vit »
// dès qu'elle est montée.
import { Avatar as LiveAvatar } from './studio/avatars'

// ModuleId → persona v10 (7 personae pour 8 modules → mira/tess réutilisés).
const MODULE_PERSONA: Record<string, string> = {
  conversation: 'sage',  voice: 'diego',
  image: 'mira',         drawing: 'mira',
  video: 'tess',         '3d': 'tess',
  code: 'lou',           learning: 'sam',  cyber: 'yann',
}
function personaFor(agent: AuroraAgent): string {
  return MODULE_PERSONA[agent.id] || 'sage'
}
// AgentState → "gesture" v10 quand l'agent travaille (sinon geste signature).
const WORKING_GESTURE: Record<string, string> = {
  conversation: 'speaking', voice: 'speaking',
  image: 'painting', drawing: 'painting',
  video: 'pointing', '3d': 'pointing',
  code: 'typing', learning: 'reading', cyber: 'whiteboard',
}

type SceneProps = {
  moduleId: ModuleId
  state?: AgentState
  voiceActive?: boolean
  onAgentClick?: () => void
}

export default function AuroraAgentScene({
  moduleId,
  state = 'idle',
  voiceActive = false,
  onAgentClick,
}: SceneProps) {
  const agent = getAgent(moduleId)
  // Track elapsed seconds since work started (for billboard timer)
  const [workStart, setWorkStart] = useState<number | null>(null)
  const [now, setNow] = useState<number>(Date.now())

  useEffect(() => {
    if (state === 'working') {
      setWorkStart(Date.now())
    } else {
      setWorkStart(null)
    }
  }, [state])

  useEffect(() => {
    if (workStart === null) return
    const id = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(id)
  }, [workStart])

  const elapsed = workStart === null ? 0 : Math.max(0, Math.round((now - workStart) / 1000))

  // Dispatch per-module scene
  switch (moduleId) {
    case 'conversation':
      return <WriterScene agent={agent} state={state} elapsed={elapsed} voiceActive={voiceActive} onAgentClick={onAgentClick} />
    case '3d':
      return <BuildScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'image':
      return <StudioScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'video':
      return <FilmScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'code':
      return <DeskScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'drawing':
      return <SumiScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'learning':
      return <LectureScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    case 'cyber':
      return <WatchScene agent={agent} state={state} elapsed={elapsed} onAgentClick={onAgentClick} />
    default:
      return <WriterScene agent={agent} state={state} elapsed={elapsed} voiceActive={voiceActive} onAgentClick={onAgentClick} />
  }
}

/* ---------- Helpers ---------- */
function formatElapsed(s: number): string {
  const mm = Math.floor(s / 60).toString().padStart(2, '0')
  const ss = (s % 60).toString().padStart(2, '0')
  return `${mm}:${ss}`
}

function StageFrame({ children, ground: _ground, agentColor }: {
  children: React.ReactNode
  ground: string
  agentColor: string
}) {
  // v82lkf : ne passe plus de ground colored au floor — la CSS gère
  // une simple ombre subtile pour suggérer le sol sans box.
  return (
    <div className="aurora-scene-stage" style={{ ['--agent-color' as string]: agentColor }}>
      <div className="aurora-scene-floor" />
      {children}
    </div>
  )
}

function AvatarFigure({ agent, pose, onClick, size = 200 }: {
  agent: AuroraAgent
  pose: 'idle' | 'thinking' | 'writing' | 'working' | 'standing' | 'dictating'
  onClick?: () => void
  size?: number
}) {
  const persona = personaFor(agent)
  const working = pose === 'working' || pose === 'writing'
  // ratio 2:3 comme la v10 — la figure dépasse vers le haut de la bande
  // scène (overflow:visible), donc elle « pose » au-dessus du dock.
  const w = size
  const h = Math.round(size * 1.46)
  return (
    <button
      type="button"
      className={`aurora-scene-figure pose-${pose}`}
      onClick={onClick}
      title={`${agent.name} — ${agent.role}\n« ${agent.motto} »`}
      style={{
        background: 'transparent',
        border: 'none',
        padding: 0,
        cursor: onClick ? 'pointer' : 'default',
        lineHeight: 0,
        filter: `drop-shadow(0 10px 18px rgba(0,0,0,0.28)) drop-shadow(0 0 14px ${agent.color}33)`,
      }}
    >
      <LiveAvatar
        persona={persona}
        gesture={working ? (WORKING_GESTURE[agent.id] || undefined) : undefined}
        mood={working ? 'concentrate' : pose === 'thinking' ? 'surprise' : undefined}
        light={{ color: agent.color, dir: 'right', intensity: 0.25 }}
        w={w}
        h={h}
      />
    </button>
  )
}

function Billboard({ label, elapsed, color }: { label: string; elapsed: number; color: string }) {
  return (
    <div className="aurora-scene-billboard" style={{ background: color }}>
      <div className="aurora-scene-billboard-label">{label}</div>
      <div className="aurora-scene-billboard-time">{formatElapsed(elapsed)}</div>
      <div className="aurora-scene-billboard-stake" />
    </div>
  )
}

/* ============================================================
 * Conversation — WriterScene (Lyra à son bureau + texte live)
 * ============================================================
 * Subscribe à chatStore.streamContent + isStreaming. Quand le
 * model streame, le texte apparaît caractère par caractère sur
 * le papier que Lyra "écrit". C'est lié au FLUX RÉEL des chunks.
 */
function WriterScene({ agent, state, elapsed: _elapsed, voiceActive, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; voiceActive?: boolean; onAgentClick?: () => void
}) {
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamContent = useChatStore((s) => s.streamContent)
  const messages = useChatStore((s) => s.messages)

  // Texte affiché : flux en cours OU dernière réponse assistant
  const lastAssistant = messages.filter((m) => m.role === 'assistant').slice(-1)[0]
  const writingText = isStreaming
    ? streamContent
    : (lastAssistant?.content ?? agent.motto)

  // Tail of text — affiche les ~120 derniers chars, scroll synthétique
  const visible = writingText.length > 220 ? '…' + writingText.slice(-220) : writingText

  // pose : standing if idle, writing if streaming/working, thinking if state=thinking
  const pose = isStreaming || state === 'working' ? 'writing'
             : state === 'thinking' ? 'thinking'
             : 'standing'

  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #2a221f 0%, #1c1614 100%)">
      <div className="aurora-scene-conv">
        <div className="aurora-scene-desk">
          <div className="aurora-scene-paper">
            <div className="aurora-scene-paper-content">
              {visible}
              {isStreaming && <span className="aurora-scene-cursor">▎</span>}
            </div>
          </div>
          <div className="aurora-scene-pen" />
        </div>
        <div className="aurora-scene-chair">
          <AvatarFigure agent={agent} pose={pose} onClick={onAgentClick} size={140} />
        </div>
        {/* Second character — dictateur — only when voice is active */}
        {voiceActive && (
          <div className="aurora-scene-dictator">
            <AvatarFigure
              agent={{ ...agent, name: 'Echo', role: 'Voix', color: '#ff6a3d' }}
              pose="dictating"
              size={115}
            />
            <div className="aurora-scene-speech">« {visible.slice(-40)}… »</div>
          </div>
        )}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * 3D — BuildScene (Atlas + chantier + marteau + fumée)
 * ============================================================
 */
function BuildScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  const thinking = state === 'thinking'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #5a3a1a 0%, #2a1a0d 100%)">
      <div className="aurora-scene-build">
        {/* Construction site bg : scaffolding lines */}
        <div className="aurora-scene-scaffold" />
        {/* Smoke clouds when working */}
        {working && (
          <>
            <div className="aurora-scene-smoke s1" />
            <div className="aurora-scene-smoke s2" />
            <div className="aurora-scene-smoke s3" />
            <div className="aurora-scene-smoke s4" />
          </>
        )}
        {/* Blueprint when thinking */}
        {thinking && (
          <div className="aurora-scene-blueprint">
            <div className="bp-grid" />
            <div className="bp-line bp-line-1" />
            <div className="bp-line bp-line-2" />
            <div className="bp-line bp-line-3" />
          </div>
        )}
        {/* Avatar */}
        <div className={`aurora-scene-builder ${working ? 'is-hammering' : ''}`}>
          <AvatarFigure agent={agent} pose={working ? 'working' : thinking ? 'thinking' : 'standing'} onClick={onAgentClick} size={140} />
          {/* Hammer — swings when working */}
          <div className={`aurora-scene-hammer ${working ? 'is-swinging' : ''}`}>
            <div className="hammer-handle" />
            <div className="hammer-head" />
          </div>
        </div>
        {/* Billboard timer when working */}
        {working && <Billboard label="CONSTRUCTION" elapsed={elapsed} color={agent.color} />}
        {/* Sparks */}
        {working && (
          <>
            <div className="aurora-scene-spark sp1">★</div>
            <div className="aurora-scene-spark sp2">✦</div>
            <div className="aurora-scene-spark sp3">★</div>
          </>
        )}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * Image — StudioScene (Iris devant chevalet)
 * ============================================================
 */
function StudioScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #f4ecd9 0%, #d4cab8 100%)">
      <div className="aurora-scene-studio">
        <div className={`aurora-scene-easel ${working ? 'is-painting' : ''}`}>
          <div className="easel-canvas">
            {working ? <PaintStrokes color={agent.color} /> : <span className="easel-vacant">∅</span>}
          </div>
          <div className="easel-leg easel-leg-l" />
          <div className="easel-leg easel-leg-r" />
        </div>
        <div className="aurora-scene-painter">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={140} />
          <div className="aurora-scene-palette">
            <div className="palette-blob b1" />
            <div className="palette-blob b2" />
            <div className="palette-blob b3" />
            <div className="palette-blob b4" />
          </div>
        </div>
        {working && <Billboard label="PEINTURE" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}

function PaintStrokes({ color }: { color: string }) {
  return (
    <div className="paint-strokes">
      <div className="paint-stroke ps1" style={{ background: color }} />
      <div className="paint-stroke ps2" style={{ background: '#5ba4d4' }} />
      <div className="paint-stroke ps3" style={{ background: '#ffd54a' }} />
    </div>
  )
}

/* ============================================================
 * Video — FilmScene (Cinéma derrière caméra avec clap)
 * ============================================================
 */
function FilmScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #1c1614 0%, #0a0808 100%)">
      <div className="aurora-scene-film">
        {/* Spotlight */}
        <div className="aurora-scene-spotlight" />
        {/* Camera tripod */}
        <div className="aurora-scene-camera">
          <div className="cam-lens" />
          <div className="cam-body" />
          <div className="cam-tripod" />
        </div>
        {/* Director */}
        <div className="aurora-scene-director">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={140} />
          {/* Clapboard */}
          <div className={`aurora-scene-clap ${working ? 'is-clapping' : ''}`}>
            <div className="clap-top" />
            <div className="clap-body">
              <div className="clap-stripes" />
            </div>
          </div>
        </div>
        {working && <Billboard label="TOURNAGE" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * Code — DeskScene (Glyph devant moniteur)
 * ============================================================
 */
function DeskScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #1a2a1f 0%, #0a1208 100%)">
      <div className="aurora-scene-code">
        <div className="aurora-scene-monitor">
          <div className="monitor-screen">
            {working ? (
              <>
                <div className="code-line cl1" />
                <div className="code-line cl2" />
                <div className="code-line cl3" />
                <div className="code-line cl4" />
                <div className="code-cursor">|</div>
              </>
            ) : (
              <span style={{ color: '#5fa37e', fontFamily: 'monospace', opacity: 0.5 }}>$ ready_</span>
            )}
          </div>
          <div className="monitor-stand" />
        </div>
        <div className="aurora-scene-coder">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={130} />
        </div>
        {working && <Billboard label="COMPILATION" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * Drawing — SumiScene (Sumi avec pinceau)
 * ============================================================
 */
function SumiScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #f4ecd9 0%, #c4b89a 100%)">
      <div className="aurora-scene-sumi">
        <div className="aurora-scene-scroll">
          {working && <div className="sumi-stroke" />}
        </div>
        <div className="aurora-scene-calligrapher">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={140} />
        </div>
        {working && <Billboard label="ESQUISSE" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * Learning — LectureScene (Sage devant tableau)
 * ============================================================
 */
function LectureScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #3d322e 0%, #1c1614 100%)">
      <div className="aurora-scene-lecture">
        <div className="aurora-scene-blackboard">
          {working && (
            <>
              <div className="chalk chalk-1">∫ x dx = x²/2</div>
              <div className="chalk chalk-2">→ Q.E.D.</div>
              <div className="chalk chalk-3">y = mx + b</div>
            </>
          )}
        </div>
        <div className="aurora-scene-prof">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={140} />
        </div>
        {working && <Billboard label="COURS" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}

/* ============================================================
 * Cyber — WatchScene (Phantom devant terminal)
 * ============================================================
 */
function WatchScene({ agent, state, elapsed, onAgentClick }: {
  agent: AuroraAgent; state: AgentState; elapsed: number; onAgentClick?: () => void
}) {
  const working = state === 'working'
  return (
    <StageFrame agentColor={agent.color} ground="linear-gradient(180deg, #1c1614 0%, #0a0606 100%)">
      <div className="aurora-scene-watch">
        <div className="aurora-scene-terminal">
          {working ? (
            <>
              <div className="term-line tl1">$ scan --target 0x7f3 --depth 4</div>
              <div className="term-line tl2">[+] Found 3 vectors of interest</div>
              <div className="term-line tl3">[*] Inspecting CVE-2024-XXXX...</div>
              <div className="term-line tl4">[OK] No critical exposure detected.</div>
            </>
          ) : (
            <span style={{ color: '#c44', fontFamily: 'monospace' }}>// idle</span>
          )}
        </div>
        <div className="aurora-scene-watcher">
          <AvatarFigure agent={agent} pose={working ? 'working' : 'standing'} onClick={onAgentClick} size={140} />
        </div>
        {working && <Billboard label="ANALYSE" elapsed={elapsed} color={agent.color} />}
      </div>
    </StageFrame>
  )
}
