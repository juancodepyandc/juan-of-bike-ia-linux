/**
 * AuroraV1MobileShell — Editorial portrait entry for the mobile shell.
 *
 * Visual chrome from _design/aurora_design_screens_v1/mobile.jsx
 * (MobileGrimoire mock): status bar, sphere as masthead with greeting
 * "Bonjour Juan", 6-card module deck, Forge queue panel, bottom dock
 * (◐ ✺ ◌ ⌘) with active glow.
 *
 * Real wiring: a single tap mounts MobileGrimoire (the full mobile shell
 * with cover/canvas/create/chat/voice/forge pages, two-finger swipe
 * navigation, ink scroll notifications, voice overlay, character forge).
 * The skin only re-styles the *cover/welcome* before the user enters.
 */
import { lazy, Suspense, useState } from 'react'
import AuroraSphereV1 from './AuroraSphereV1.tsx'
import { useAppStore } from '../stores/appStore.ts'

const MobileGrimoire = lazy(() => import('./MobileGrimoire'))

// iter39 : on monte directement les vues V1 du module choisi sur mobile.
// Avant, chaque tap basculait vers MobileGrimoire (la vieille interface
// manga). Maintenant le tap va sur la vue V1 du module en plein écran,
// avec un bouton back pour revenir au cover.
const ConversationViewLazy = lazy(() => import('../views/AuroraV1ChatView'))
const ImageViewLazy        = lazy(() => import('../views/AuroraV1ImageView'))
const CodeViewLazy         = lazy(() => import('../views/AuroraV1CodeView'))
const DrawingViewLazy      = lazy(() => import('../views/AuroraV1DrawingView'))
const ModelViewLazy        = lazy(() => import('../views/AuroraV13DView'))
const LearningViewLazy     = lazy(() => import('../views/AuroraV1AcademyView'))
const CyberViewLazy        = lazy(() => import('../views/AuroraV1CyberView'))
const StudioRosterLazy     = lazy(() => import('./studio/Roster'))
const FightCloudBadgeLazy  = lazy(() => import('./studio/FightCloudBadge'))

const MODULE_VIEWS: Record<string, React.LazyExoticComponent<React.ComponentType>> = {
  conversation: ConversationViewLazy,
  image: ImageViewLazy,
  code: CodeViewLazy,
  drawing: DrawingViewLazy,
  '3d': ModelViewLazy,
  learning: LearningViewLazy,
  cyber: CyberViewLazy,
}

const EMBER = 'oklch(0.65 0.18 40)'
const TINTS: Record<string, string> = {
  conversation: 'oklch(0.72 0.14 350)',
  image: 'oklch(0.70 0.14 320)',
  code: 'oklch(0.72 0.12 145)',
  video: 'oklch(0.68 0.13 260)',
  drawing: 'oklch(0.62 0.14 30)',
  '3d': 'oklch(0.74 0.13 60)',
  learning: 'oklch(0.86 0.18 75)',  // gold (BAC academy)
  cyber: 'oklch(0.72 0.16 145)',
}

// iter39 : Académie ajoutée à la deck mobile. User a besoin du module
// pour préparer son BAC depuis son téléphone.
// v82s : "L'équipe" en tête — porte d'entrée illustrée vers les modules
// (7 portraits Bitmoji+Pixar qui respirent, tap → vue V1 du module).
const MODULES_V1: Array<{ id: string; glyph: string; label: string; tint: string }> = [
  { id: 'team', glyph: '⌬', label: 'L’équipe', tint: 'oklch(0.78 0.13 60)' },
  { id: 'conversation', glyph: '✺', label: 'Chat', tint: TINTS.conversation },
  { id: 'image', glyph: '◐', label: 'Image', tint: TINTS.image },
  { id: 'learning', glyph: '🎓', label: 'Académie', tint: TINTS.learning },
  { id: 'code', glyph: '◌', label: 'Code', tint: TINTS.code },
  { id: 'video', glyph: '▣', label: 'Vidéo', tint: TINTS.video },
  { id: 'drawing', glyph: '墨', label: 'Dessin', tint: TINTS.drawing },
  { id: '3d', glyph: '◇', label: '3D', tint: TINTS['3d'] },
  { id: 'cyber', glyph: '⚔', label: 'Cyber', tint: TINTS.cyber },
]

function Eyebrow({ children, dot, style }: { children: React.ReactNode; dot?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)', display: 'flex', alignItems: 'center', gap: 6,
      ...style,
    }}>
      {dot && <span style={{ width: 7, height: 7, borderRadius: 99, background: dot, boxShadow: `0 0 10px ${dot}` }} />}
      {children}
    </div>
  )
}

function Display({ size, children, style }: { size: number; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontSize: size,
      fontStyle: 'italic', fontWeight: 400, lineHeight: 0.95,
      letterSpacing: '-0.02em', color: 'var(--fg, #f5f5f5)', ...style,
    }}>{children}</div>
  )
}

export default function AuroraV1MobileShell() {
  // iter39 : on garde l'état legacy "live" pour les boutons du dock qui
  // ouvrent encore MobileGrimoire (forge / voice / etc.), MAIS le tap
  // sur un module ouvre désormais la vue V1 du module directement, en
  // plein écran. Plus de fallback sur la vieille interface manga.
  const [live, setLive] = useState(false)
  const [liveModule, setLiveModule] = useState<string | null>(null)
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const now = new Date().toTimeString().slice(0, 5)

  // Quand on tape un module : mémorise dans le store global ET monte la
  // vue plein écran. Le store est respecté côté shell desktop ; le mount
  // local évite de passer par MobileGrimoire (manga).
  const openModule = (id: string) => {
    // 'team' est une porte d'entrée locale — pas de module backend ni
    // d'appel setActiveModule. Reste fullscreen jusqu'au tap d'un portrait.
    if (id !== 'team') {
      setActiveModule(id as Parameters<typeof setActiveModule>[0])
    }
    setLiveModule(id)
  }

  if (liveModule) {
    // 'team' rend le Roster studio (7 portraits illustrés). Tap d'un
    // portrait → openModule(persona.module) → vue V1 du module.
    const isTeam = liveModule === 'team'
    const ModuleView = isTeam ? null : MODULE_VIEWS[liveModule]
    return (
      <div key={liveModule} className="aurora-mobile-slide-in" style={{
        position: 'fixed', inset: 0, zIndex: 5,
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
        display: 'flex', flexDirection: 'column',
        fontFamily: 'var(--font-sans, system-ui)',
      }}>
        <header style={{
          flexShrink: 0,
          padding: '10px 14px',
          display: 'flex', alignItems: 'center', gap: 10,
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
          background: 'var(--bg-raised, rgba(255,255,255,0.03))',
        }}>
          <button type="button" onClick={() => setLiveModule(null)}
            title="Retour"
            style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'transparent',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              color: 'var(--fg, #f5f5f5)',
              cursor: 'pointer', fontSize: 18,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
            ←
          </button>
          <span style={{
            fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
            fontStyle: 'italic', fontSize: 20,
            color: (TINTS[liveModule] || (isTeam ? 'oklch(0.78 0.13 60)' : 'var(--fg, #f5f5f5)')),
          }}>
            {MODULES_V1.find(m => m.id === liveModule)?.label || liveModule}
          </span>
        </header>
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <Suspense fallback={
            <div style={{
              width: '100%', height: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--fg-dim, #aaa)',
              fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 16,
            }}>Chargement…</div>
          }>
            {isTeam ? (
              <StudioRosterLazy onPick={(_persona, _page, mod) => openModule(mod)} />
            ) : ModuleView ? <ModuleView /> : (
              <div style={{ padding: 24, color: 'var(--fg-dim, #aaa)' }}>
                Module "{liveModule}" non disponible sur mobile (V1).
              </div>
            )}
          </Suspense>
        </div>
      </div>
    )
  }

  if (live) {
    return (
      <Suspense fallback={
        <div style={{
          width: '100%', height: '100%',
          background: 'var(--bg, #0c0a09)', color: 'var(--fg-dim, #aaa)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 18,
        }}>Le grimoire s'ouvre…</div>
      }>
        <MobileGrimoire />
      </Suspense>
    )
  }

  return (
    // v82p : grain class for the Editorial film overlay (matches the
    // source's `<MobileGrimoire className="grain">`).
    <div className="grain" style={{
      width: '100%', height: '100%',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      overflow: 'auto', position: 'relative',
      fontFamily: 'var(--font-sans, system-ui)',
    }}>
      {/* Status bar */}
      <div style={{
        height: 36, padding: '0 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 12, fontWeight: 600,
      }}>
        <span>{now}</span>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{
            width: 18, height: 10,
            border: '1px solid var(--fg, #f5f5f5)', borderRadius: 2, position: 'relative',
          }}>
            <span style={{
              position: 'absolute', inset: 1,
              background: 'var(--ember-500, #ff6a3d)', borderRadius: 1, width: '70%',
            }} />
          </span>
        </span>
      </div>

      {/* Sphere masthead — v82p mounts the real WebGL2 sphere
          (was a flat CSS gradient before). Matches the design source's
          <AuroraSphere tint="oklch(0.65 0.18 40)" state="thinking"
                        radius={0.42} glow={1.3}/>. */}
      <div style={{
        position: 'relative', height: 260, margin: '0 16px',
        overflow: 'hidden', borderRadius: 20,
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        background: 'oklch(0.10 0.012 250)',
      }}>
        <div style={{ position: 'absolute', inset: 0 }}>
          <AuroraSphereV1 tint={EMBER} state="thinking" radius={0.42} glow={1.3} />
        </div>
        <div style={{
          position: 'absolute', top: 16, left: 16, right: 16,
          display: 'flex', justifyContent: 'space-between',
        }}>
          <Eyebrow dot="var(--ember-500, #ff6a3d)">Grimoire · session {Date.now().toString().slice(-4)}</Eyebrow>
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            color: 'var(--fg-dim, #aaa)',
          }}>offline</span>
        </div>
        <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16 }}>
          <Display size={36}>Aurora<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }}>locale</em></Display>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            color: 'var(--fg-dim, #aaa)', marginTop: 4,
          }}>4 missions · 2 actives · cowork ETA 02:18</div>
        </div>
      </div>

      {/* Module deck */}
      <div style={{ padding: '20px 16px 8px' }}>
        <Eyebrow style={{ marginBottom: 10 }}>Modules</Eyebrow>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {MODULES_V1.map((m) => (
            <button key={m.id} type="button" onClick={() => openModule(m.id)}
              style={{
                padding: 14,
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 14,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                position: 'relative', overflow: 'hidden',
                textAlign: 'left', color: 'var(--fg, #f5f5f5)',
                cursor: 'pointer', fontFamily: 'inherit',
              }}>
              {/* v82ad : revert per-card spheres to CSS gradient blobs.
                  v82p had moved them to AuroraSphereV1 for design fidelity,
                  but 6 cards × WebGL2 + 1 masthead = 7 contexts on one
                  page. Browsers cap concurrent WebGL contexts at ~16 and
                  each costs ~5-10 MB GPU memory. On low-end devices that
                  exhausts resources and is one of the "modules crash au
                  bout d'un moment" / "pas fluide" causes. The masthead
                  keeps its real sphere ; the cards lose visual fidelity
                  but the perf gain is critical. */}
              <div style={{
                position: 'absolute', top: -20, right: -20,
                width: 70, height: 70, borderRadius: '50%',
                background: `radial-gradient(circle at 35% 35%, ${m.tint}, transparent 70%)`,
                opacity: 0.6, pointerEvents: 'none',
              }} />
              <div style={{
                width: 28, height: 28, borderRadius: 8, background: m.tint,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono, monospace)', fontWeight: 600,
                color: '#0a0a0a', marginBottom: 10,
                boxShadow: `0 0 18px ${m.tint}66`,
              }}>{m.glyph}</div>
              <div style={{
                fontFamily: 'var(--font-display, serif)', fontStyle: 'italic',
                fontSize: 22, letterSpacing: '-0.01em',
              }}>{m.label}</div>
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                color: 'var(--fg-mute, #777)', marginTop: 4,
              }}>tap →</div>
            </button>
          ))}
        </div>
      </div>

      {/* Forge queue */}
      <div style={{ padding: '10px 16px' }}>
        <div style={{
          padding: 14,
          background: 'var(--bg-raised, rgba(255,255,255,0.04))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 12,
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginBottom: 8,
          }}>
            <Eyebrow dot="var(--ember-500, #ff6a3d)">Forge · queue</Eyebrow>
            <span style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
              color: 'var(--fg-dim, #aaa)',
            }}>3 / 7</span>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} style={{
                flex: 1, height: 4, borderRadius: 99,
                background: i < 3 ? 'var(--ember-500, #ff6a3d)'
                  : i === 3 ? `${EMBER}99`
                  : 'var(--ink-800, rgba(255,255,255,0.06))',
              }} />
            ))}
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginTop: 8,
            fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-mute, #777)',
          }}>
            <span>portrait → variations</span><span>ETA 41s</span>
          </div>
        </div>
      </div>

      {/* Bottom dock — v82s-studio : raccourcis modules réels au lieu de
          4 boutons qui ouvraient tous MobileGrimoire (manga). Tap = ouvre
          directement la vue V1 du module en plein écran avec slide-in. */}
      <div style={{
        position: 'sticky', bottom: 16, left: 0, right: 0,
        display: 'flex', justifyContent: 'center', marginTop: 24, marginBottom: 16,
        zIndex: 10,
      }}>
        <div style={{
          display: 'flex', gap: 4, padding: 8,
          background: 'var(--bg-raised, rgba(20,16,12,0.92))',
          border: '1px solid var(--line, rgba(255,255,255,0.14))',
          borderRadius: 99,
          boxShadow: '0 12px 30px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(10px)',
        }}>
          {([
            { glyph: '⌬', id: 'team',         tip: 'L\'équipe' },
            { glyph: '◐', id: 'conversation', tip: 'Chat' },
            { glyph: '◉', id: 'image',        tip: 'Image' },
            { glyph: '◌', id: 'code',         tip: 'Code' },
            { glyph: '🎓', id: 'learning',     tip: 'Académie' },
          ] as const).map(({ glyph, id, tip }) => (
            <button key={id} type="button" onClick={() => openModule(id)} title={tip} aria-label={tip}
              style={{
                width: 42, height: 42, borderRadius: 99,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'transparent', color: 'var(--fg-dim, #ccc)',
                fontFamily: 'var(--font-mono, monospace)', fontSize: 17,
                border: 'none', cursor: 'pointer',
                transition: 'background 0.15s, color 0.15s',
              }}
              onTouchStart={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.1)' }}
              onTouchEnd={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}>
              {glyph}
            </button>
          ))}
        </div>
      </div>

      {/* FightCloud overlay — cartoon POW/BOOM/CRACK pendant les générations */}
      <Suspense fallback={null}>
        <FightCloudBadgeLazy onOpen={() => setLive(true)} />
      </Suspense>
      {/* v82s-studio mobile fluide : suppression de la grosse CTA flottante
          centrée "OUVRIR LE GRIMOIRE" — elle recouvrait les cartes de la
          deck (Chat / Image…) au milieu de l'écran. Le dock du bas + le tap
          direct sur une carte sont les vraies entrées. */}
    </div>
  )
}
