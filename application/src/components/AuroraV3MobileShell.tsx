/**
 * AuroraV3MobileShell — Ricochet "polyphonie" entry for mobile.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-5.jsx
 * (MobileV3 mock): "10 IDENTITÉS · polyphonie" header with stacked
 * cards each in a different aesthetic per module — radar mission ctrl
 * (phosphor), typewriter dictaphone (paper + caret), studio VOX
 * (cream + waveform), polaroid lightbox (cork + tilted polaroids),
 * blueprint (cyan-on-navy + grid), sketchbook l'atelier (cream +
 * Caveat).
 *
 * Real wiring: any tap mounts MobileGrimoire (the 1000+ LOC mobile
 * shell with full feature set). The skin only re-styles the *cover*
 * before the user enters.
 */
import { lazy, Suspense, useState } from 'react'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'

const MobileGrimoire = lazy(() => import('./MobileGrimoire'))
const StudioRosterLazy = lazy(() => import('./studio/Roster'))
const FightCloudBadgeLazy = lazy(() => import('./studio/FightCloudBadge'))

// v3 modules → V1 fullscreen views (pas de V3 view dédiée pour la majorité ;
// le shell V3 réutilise les vues V1 fonctionnelles).
const ConversationViewV1 = lazy(() => import('../views/AuroraV1ChatView'))
const ImageViewV1        = lazy(() => import('../views/AuroraV1ImageView'))
const CodeViewV1         = lazy(() => import('../views/AuroraV1CodeView'))
const DrawingViewV1      = lazy(() => import('../views/AuroraV1DrawingView'))
const ModelViewV1        = lazy(() => import('../views/AuroraV13DView'))
const LearningViewV1     = lazy(() => import('../views/AuroraV1AcademyView'))
const CyberViewV1        = lazy(() => import('../views/AuroraV1CyberView'))
const V3_MODULE_VIEWS: Record<string, React.LazyExoticComponent<React.ComponentType>> = {
  conversation: ConversationViewV1,
  image: ImageViewV1, code: CodeViewV1,
  drawing: DrawingViewV1, '3d': ModelViewV1,
  learning: LearningViewV1, cyber: CyberViewV1,
}

const PHOSPHOR = '#7df9c4'
const PHOSPHOR_DIM = '#3eb89b'
const AMBER = '#ffb938'
const PAPER = '#f0e9d9'
const INK = '#1c1614'
const CREAM = '#e8d8a8'
const TAN = '#5a4a2a'
const STEEL = '#1a1a1a'
const RED = '#a8231d'
const CORK = '#b8956b'
const POLAROID = '#fbf6e8'
const POLAROID_DARK = '#1a1410'
const NAVY = '#0c2944'
const CYAN_LIGHT = '#cce8ff'
const CYAN = '#7dc8ff'
const SKETCH_PAPER = '#faf2e0'
const SKETCH_INK = '#2a1f15'

export default function AuroraV3MobileShell() {
  const [live, setLive] = useState(false)
  const [team, setTeam] = useState(false)
  const [liveModule, setLiveModule] = useState<string | null>(null)
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const now = new Date().toTimeString().slice(0, 5)
  const openMod = (m: ModuleId) => { setActiveModule(m); setLiveModule(m) }

  // Module fullscreen — V1 view + back arrow. Pareil que AuroraV1MobileShell.
  if (liveModule) {
    const ModuleView = V3_MODULE_VIEWS[liveModule]
    return (
      <div key={liveModule} className="aurora-mobile-slide-in" style={{ position: 'fixed', inset: 0, background: '#0a0a0a', color: '#fff', display: 'flex', flexDirection: 'column', fontFamily: 'JetBrains Mono, monospace' }}>
        <header style={{ flexShrink: 0, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${PHOSPHOR}33`, background: 'rgba(255,255,255,0.03)' }}>
          <button type="button" onClick={() => setLiveModule(null)} aria-label="Retour"
            style={{ width: 36, height: 36, borderRadius: 8, background: 'transparent', border: `1px solid ${PHOSPHOR}55`, color: PHOSPHOR, cursor: 'pointer', fontSize: 18 }}>←</button>
          <span style={{ fontStyle: 'italic', fontSize: 18, fontFamily: 'Georgia, serif', color: PHOSPHOR }}>{liveModule}</span>
        </header>
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <Suspense fallback={
            <div style={{ width:'100%', height:'100%', display:'flex', alignItems:'center', justifyContent:'center', color: PHOSPHOR, fontFamily:'JetBrains Mono, monospace', letterSpacing:'0.2em', fontSize:12 }}>
              CHARGEMENT · {liveModule.toUpperCase()}
            </div>
          }>
            {ModuleView ? <ModuleView /> : <div style={{ padding: 24, color: '#aaa' }}>Module "{liveModule}" indisponible.</div>}
          </Suspense>
        </div>
      </div>
    )
  }

  // L'équipe — Studio Roster fullscreen, tap d'un portrait → vue V1 du module.
  if (team) {
    return (
      <div className="aurora-mobile-slide-in" style={{ position: 'fixed', inset: 0, background: '#0a0a0a', color: '#fff', display: 'flex', flexDirection: 'column', fontFamily: 'JetBrains Mono, monospace' }}>
        <header style={{ flexShrink: 0, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${AMBER}55`, background: 'rgba(255,255,255,0.03)' }}>
          <button type="button" onClick={() => setTeam(false)} aria-label="Retour"
            style={{ width: 36, height: 36, borderRadius: 8, background: 'transparent', border: `1px solid ${AMBER}88`, color: AMBER, cursor: 'pointer', fontSize: 18 }}>←</button>
          <span style={{ fontStyle: 'italic', fontSize: 20, fontFamily: 'Georgia, serif', color: AMBER }}>L’équipe</span>
        </header>
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <Suspense fallback={<div style={{ padding: 24, color: '#888', fontFamily:'JetBrains Mono, monospace', letterSpacing:'0.2em' }}>L’ÉQUIPE · LOAD…</div>}>
            <StudioRosterLazy onPick={(_persona, _page, mod) => {
              setActiveModule(mod)
              setTeam(false)
              setLiveModule(mod)
            }} />
          </Suspense>
        </div>
      </div>
    )
  }

  if (live) {
    return (
      <Suspense fallback={
        <div style={{
          width: '100%', height: '100%', background: '#0a0a0a', color: PHOSPHOR,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16,
          fontFamily: 'JetBrains Mono, monospace',
          letterSpacing: '0.3em', fontSize: 13,
        }}>
          <div>POLYPHONIE · LOAD…</div>
          <button type="button" onClick={() => setLive(false)}
            style={{ marginTop: 18, padding: '8px 14px', background: 'transparent', color: PHOSPHOR, border: `1px solid ${PHOSPHOR}88`, fontFamily: 'inherit', fontSize: 11, letterSpacing: '0.2em', cursor: 'pointer' }}>
            ← RETOUR
          </button>
        </div>
      }>
        <MobileGrimoire />
      </Suspense>
    )
  }

  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#0a0a0a', color: '#fff',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      fontFamily: 'Helvetica Neue, Arial, sans-serif', position: 'relative',
    }}>
      {/* Top status */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        padding: '12px 18px 4px', fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace', color: '#999',
      }}>
        <span>{now}</span>
        <span>AURORA · POLY</span>
        <span>87%</span>
      </div>

      <div style={{ padding: '6px 18px 12px' }}>
        <div style={{ fontSize: 11, letterSpacing: '0.3em', color: '#888' }}>10 IDENTITÉS</div>
        <div style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 30, marginTop: 2 }}>polyphonie</div>
      </div>

      {/* Stack of cards */}
      <div style={{
        flex: 1, padding: '0 18px 18px', overflow: 'auto',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {/* L'équipe — entrée illustrée vers les modules (7 portraits qui respirent) */}
        <button type="button" onClick={() => setTeam(true)}
          style={{
            border: `1px solid ${AMBER}55`,
            background: `linear-gradient(135deg, ${AMBER}22 0%, transparent 60%), #1a1410`,
            padding: 14, color: AMBER,
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
            textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em', color: AMBER, marginBottom: 8 }}>★ · L’ÉQUIPE</div>
          <div style={{
            fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 26,
            color: '#fbf6e8', letterSpacing: '-0.01em', marginBottom: 4,
          }}>7 personae</div>
          <div style={{ color: '#9c8c70', fontSize: 11 }}>tap → portraits illustrés · respirent en boucle</div>
        </button>

        {/* Card I — radar mission ctrl → Académie */}
        <button type="button" onClick={() => openMod('learning')}
          style={{
            border: `1px solid #15524d`, background: '#031a1a',
            padding: 14, color: PHOSPHOR,
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
            textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em' }}>I · MISSION CTRL</div>
          <svg viewBox="0 0 200 80" width="100%" height="50">
            <circle cx="100" cy="40" r="34" fill="none" stroke="#15524d" />
            <circle cx="100" cy="40" r="2" fill={PHOSPHOR} />
            <circle cx="130" cy="30" r="2" fill={AMBER} />
            <line x1="100" y1="40" x2="140" y2="20" stroke={PHOSPHOR} strokeOpacity="0.5" />
          </svg>
          <div style={{ color: PHOSPHOR_DIM }}>Académie · parcours &amp; quiz · tap →</div>
        </button>

        {/* Card II — typewriter dictaphone → Chat */}
        <button type="button" onClick={() => openMod('conversation')}
          style={{
            background: PAPER, color: INK, padding: 14,
            fontFamily: 'Courier New, monospace', fontSize: 11, lineHeight: 1.6,
            border: `2px solid ${INK}`, textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em', borderBottom: '1px solid', paddingBottom: 4, marginBottom: 6 }}>
            II · DICTAPHONE
          </div>
          <div>EXPLIQUE-MOI LA <span style={{ background: '#fff7a8' }}>DIFFUSION</span></div>
          <div>EN VOCABULAIRE SUMI-E.<span style={{ animation: 'mob-caret 1s steps(2) infinite' }}>█</span></div>
          <div style={{ marginTop: 6, fontSize: 10, color: '#7a6a4a' }}>Conversation · tap →</div>
        </button>

        {/* Card III — studio vox → Vidéo */}
        <button type="button" onClick={() => openMod('video')}
          style={{
            background: STEEL, color: CREAM, padding: 14,
            border: `1px solid ${TAN}`, textAlign: 'left', cursor: 'pointer',
            fontFamily: 'inherit',
          }}>
          <div style={{ fontSize: 11, letterSpacing: '0.2em', color: '#8a7a4a' }}>III · STUDIO</div>
          <div style={{ fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 22, marginTop: 4 }}>vox</div>
          <svg width="100%" height="30" viewBox="0 0 300 30">
            {Array.from({ length: 60 }).map((_, i) => {
              const h = 4 + Math.abs(Math.sin(i * 0.5)) * 14
              return <rect key={i} x={i * 5} y={15 - h / 2} width="2" height={h} fill={RED} />
            })}
          </svg>
          <div style={{ marginTop: 4, fontSize: 10, color: '#8a7a4a' }}>Vidéo · Wan2.2 · talking-head · tap →</div>
        </button>

        {/* Card IV — polaroid lightbox → Image */}
        <button type="button" onClick={() => openMod('image')}
          style={{
            background: CORK, padding: 14, position: 'relative', minHeight: 140,
            border: 'none', cursor: 'pointer', textAlign: 'left',
          }}>
          <div style={{
            fontSize: 11, letterSpacing: '0.2em',
            fontFamily: 'JetBrains Mono, monospace', color: POLAROID_DARK,
          }}>IV · LIGHTBOX <span style={{ opacity: 0.7 }}>· Image FLUX · tap →</span></div>
          <div style={{
            position: 'absolute', top: 30, left: 18, width: 88,
            padding: '6px 6px 18px', background: POLAROID,
            transform: 'rotate(-4deg)',
            boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
          }}>
            <div style={{ aspectRatio: '1', background: POLAROID_DARK }} />
            <div style={{
              fontFamily: 'Permanent Marker, cursive', fontSize: 9, marginTop: 2,
              color: POLAROID_DARK,
            }}>bambou</div>
          </div>
          <div style={{
            position: 'absolute', top: 36, left: 122, width: 88,
            padding: '6px 6px 18px', background: POLAROID,
            transform: 'rotate(3deg)',
            boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
          }}>
            <div style={{ aspectRatio: '1', background: '#2a1f15' }} />
            <div style={{
              fontFamily: 'Permanent Marker, cursive', fontSize: 9, marginTop: 2,
              color: POLAROID_DARK,
            }}>grue</div>
          </div>
        </button>

        {/* Card V — Studio amber code → Code */}
        <button type="button" onClick={() => openMod('code')}
          style={{
            background: '#0a0500', color: AMBER, padding: 14,
            fontFamily: 'IBM Plex Mono, monospace', fontSize: 11,
            border: '1px solid #5a3a14', textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em' }}>V · CODEX <span style={{ opacity: 0.65 }}>· tap →</span></div>
          <pre style={{ margin: 0, fontSize: 10, lineHeight: 1.5 }}>
{`> aurora.codex
def diffuse(img):
    x = randn_like(img)
    return decode(x)`}
          </pre>
        </button>

        {/* Card VI — blueprint → 3D */}
        <button type="button" onClick={() => openMod('3d')}
          style={{
            background: NAVY, color: CYAN_LIGHT, padding: 14,
            fontFamily: 'Courier New, monospace', fontSize: 11,
            backgroundImage: `linear-gradient(rgba(120,200,255,0.07) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(120,200,255,0.07) 1px, transparent 1px)`,
            backgroundSize: '20px 20px',
            border: 'none', textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em' }}>VI · BLUEPRINT <span style={{ opacity: 0.7 }}>· 3D Hunyuan · tap →</span></div>
          <svg viewBox="0 0 200 60" width="100%" height="40">
            <rect x="60" y="10" width="80" height="40" fill="none" stroke={CYAN} />
            <line x1="60" y1="50" x2="140" y2="10" stroke={CYAN} strokeDasharray="2 2" />
          </svg>
          <div>verts 24,614 · faces 12,308</div>
        </button>

        {/* Card VII — sketchbook l'atelier → Dessin */}
        <button type="button" onClick={() => openMod('drawing')}
          style={{
            background: SKETCH_PAPER, color: SKETCH_INK, padding: 14,
            fontFamily: 'Caveat, cursive', fontSize: 18,
            transform: 'rotate(-0.5deg)',
            border: 'none', textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{
            fontSize: 11, letterSpacing: '0.2em',
            fontFamily: 'JetBrains Mono, monospace',
          }}>VII · L'ATELIER <span style={{ opacity: 0.6 }}>· tap →</span></div>
          <div style={{ fontSize: 24 }}>aurora suggère :</div>
          <span style={{ color: RED, borderBottom: `2px solid ${RED}` }}>épaissir le tronc</span>
        </button>

        {/* Card VIII — DEFCON cyber → Cyber */}
        <button type="button" onClick={() => openMod('cyber')}
          style={{
            background: '#0a0204', color: '#ff4a4a',
            padding: 14, border: '1px solid #5a1414',
            fontFamily: 'Space Mono, JetBrains Mono, monospace', fontSize: 11,
            textAlign: 'left', cursor: 'pointer',
          }}>
          <div style={{ letterSpacing: '0.2em' }}>VIII · DEFCON 3 <span style={{ opacity: 0.7 }}>· Cyber labs · tap →</span></div>
          <div style={{ marginTop: 4, color: '#ff8080', fontStyle: 'italic' }}>
            ◢ ARMED · KATA · MR. ROBOT ◣
          </div>
          <div style={{ marginTop: 4, color: PHOSPHOR }}>
            ✓ kata RESOLVED · sealed
          </div>
        </button>
      </div>

      {/* Sticky footer enter */}
      <div style={{
        padding: '10px 18px 14px',
        borderTop: '1px solid #222',
        background: '#0a0a0a',
        display: 'flex', gap: 8, alignItems: 'center',
      }}>
        <span style={{
          fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#666',
          flex: 1,
        }}>tap une identité → son module · ou le grimoire complet</span>
        <button type="button" onClick={() => setLive(true)}
          style={{
            background: '#fff', color: '#000', border: 'none',
            padding: '8px 14px', fontSize: 11, letterSpacing: '0.2em',
            fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
          }}>GRIMOIRE ▶</button>
      </div>

      <style>{`@keyframes mob-caret { 50% { opacity: 0 } }`}</style>

      {/* FightCloud overlay — visible quand un job de forge est en cours */}
      <Suspense fallback={null}>
        <FightCloudBadgeLazy onOpen={() => setLive(true)} />
      </Suspense>
    </div>
  )
}
