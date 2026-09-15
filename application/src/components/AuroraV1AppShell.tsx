/**
 * AuroraV1AppShell — faithful port of `_design/aurora_design_lib/app-shell.jsx`.
 *
 * The Editorial chrome that wraps every aurora_v1 view : AmbientBackdrop
 * (radial gradient wash + horizon line + technical SVG grid + film grain),
 * TopBar (Aurora logotype with ember sphere, v2.4 LOCAL chip, breadcrumb
 * `MODULE / Label`, status cluster `model · ctx · vram`, ⌘K / ⌘,),
 * Sidebar (232px : Modules eyebrow + 10 SideItem nav + Session card),
 * and a main content area that hosts the active module view.
 *
 * Real wiring : module clicks call `onActivateModule`, the active card
 * gets the tint glow + ink-800 background. Status cluster pulls live
 * data from useAppStore (mainModel, runtimeServices) instead of the
 * source's hardcoded "ollama:qwen3-vl ctx 14.2k vram 19.3gb".
 *
 * Module-id mapping vs the design's AURORA_MODULES :
 *   cowork  → overlay (no module page) — opens via dock
 *   chat    → conversation
 *   academy → learning
 *   image, video, code → unchanged
 *   draw    → drawing
 *   tdd     → 3d
 *   voice   → not in app's MODULES (sub-mode of conversation, opens via overlay)
 *   cyber   → unchanged
 */
import type { ReactNode } from 'react'
import { lazy, Suspense } from 'react'
import { Settings } from 'lucide-react'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import AuroraAmbientField from './AuroraAmbientField.tsx'

// v82s-studio iter13 : petit personnage vivant (v10 SVG) en bas de sidebar.
// Lazy → réutilise le chunk `avatars` déjà splitté.
const SidebarPersona = lazy(() => import('./studio/SidebarPersona'))

type SideEntry = {
  id: ModuleId | 'cowork' | 'voice'
  label: string
  glyph: string
  tint: string
  kbd: string
}

const SIDE_MODULES: SideEntry[] = [
  { id: 'cowork',       label: 'Cowork',       glyph: '✺', tint: 'var(--aura-cowork, oklch(0.70 0.150 40))',   kbd: '⌘`' },
  { id: 'conversation', label: 'Conversation', glyph: '◐', tint: 'var(--aura-chat, oklch(0.72 0.120 200))',    kbd: '⌘1' },
  { id: 'learning',     label: 'Academy',      glyph: '∎', tint: 'var(--aura-academy, oklch(0.74 0.110 90))',  kbd: '⌘8' },
  { id: 'image',        label: 'Image',        glyph: '◉', tint: 'var(--aura-image, oklch(0.70 0.140 320))',   kbd: '⌘2' },
  { id: 'video',        label: 'Vidéo',        glyph: '▷', tint: 'var(--aura-video, oklch(0.68 0.130 260))',   kbd: '⌘4' },
  { id: 'code',         label: 'Code',         glyph: '⌘', tint: 'var(--aura-code, oklch(0.72 0.120 145))',    kbd: '⌘3' },
  { id: 'drawing',      label: 'Dessin',       glyph: '墨', tint: 'var(--aura-draw, oklch(0.30 0.020 250))',    kbd: '⌘5' },
  { id: '3d',           label: '3D',           glyph: '◇', tint: 'var(--aura-3d, oklch(0.74 0.130 60))',       kbd: '⌘6' },
  { id: 'voice',        label: 'Voice',        glyph: '◌', tint: 'var(--aura-voice, oklch(0.72 0.140 350))',   kbd: '⌘V' },
  { id: 'cyber',        label: 'Cyber',        glyph: '※', tint: 'var(--aura-cyber, oklch(0.70 0.130 130))',   kbd: '⌘7' },
]

function Eyebrow({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div className="aurora-v1-eyebrow" style={{
      fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)',
      ...style,
    }}>{children}</div>
  )
}

function PulseDot({ color = 'var(--ember-500, #ff6a3d)', size = 8 }: { color?: string; size?: number }) {
  return (
    <span style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      <span style={{
        position: 'absolute', inset: 0, borderRadius: 99, background: color,
        animation: 'aurora-shell-pulse 1.6s ease-out infinite',
      }} />
      <span style={{
        position: 'absolute', inset: 0, borderRadius: 99, background: color,
      }} />
      <style>{`@keyframes aurora-shell-pulse {
        0% { transform: scale(1); opacity: 0.6 }
        100% { transform: scale(2.6); opacity: 0 }
      }`}</style>
    </span>
  )
}

function SideItem({ entry, active, onClick }: {
  entry: SideEntry; active: boolean; onClick: () => void
}) {
  return (
    <button
      type="button"
      className="aurora-v1-side-item"
      aria-label={entry.label}
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '9px 12px', borderRadius: 8, cursor: 'pointer',
        background: active ? 'var(--ink-800, rgba(255,255,255,0.04))' : 'transparent',
        border: active
          ? '1px solid var(--line, rgba(255,255,255,0.12))'
          : '1px solid transparent',
        color: active ? 'var(--fg, #f5f5f5)' : 'var(--fg-dim, #aaa)',
        transition: 'all .2s var(--ease-out, cubic-bezier(0.16,1,0.3,1))',
        textAlign: 'left', fontFamily: 'inherit',
        width: '100%',
      }}>
      <span className="aurora-v1-side-glyph" style={{
        width: 22, height: 22, borderRadius: 6,
        background: active ? entry.tint : 'var(--ink-800, rgba(255,255,255,0.04))',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11, fontWeight: 600,
        color: active ? 'var(--ink-1000, #0a0a0a)' : 'var(--fg-dim, #aaa)',
        boxShadow: active ? `0 0 18px ${entry.tint}` : 'none',
      }}>{entry.glyph}</span>
      <span className="aurora-v1-side-label" style={{
        fontSize: 13, fontWeight: 500, letterSpacing: '-0.005em', flex: 1,
      }}>{entry.label}</span>
      <span className="aurora-v1-side-kbd" style={{
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
        color: 'var(--fg-mute, #777)',
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        padding: '1px 5px', borderRadius: 4,
      }}>{entry.kbd}</span>
    </button>
  )
}

function AmbientBackdrop({ tint }: { tint: string }) {
  return (
    <div className="aurora-v1-topbar" style={{
      position: 'absolute', inset: 0,
      overflow: 'hidden', pointerEvents: 'none', zIndex: 0,
    }}>
      {/* gradient wash */}
      <div className="aurora-v1-status" style={{
        position: 'absolute', inset: '-20%',
        background: `radial-gradient(ellipse 60% 40% at 78% 12%, ${tint}, transparent 55%),
                     radial-gradient(ellipse 50% 30% at 12% 88%, var(--ember-700, #c5421d), transparent 60%)`,
        opacity: 0.35,
        filter: 'blur(40px)',
      }} />
      {/* v82y : particle field — port of `_design/aurora_design_lib/ambient-fx.jsx`.
          The source AppShell ships `<AmbientField tint={tint} density={0.8}/>`;
          this is the missing piece for full visual fidelity. */}
      <AuroraAmbientField tint={tint} density={0.8} />
      {/* faint horizon line */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: '50%',
        height: 1, background: 'var(--line-soft, rgba(255,255,255,0.06))',
        opacity: 0.5,
      }} />
      {/* technical grid */}
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.06 }}>
        <defs>
          <pattern id="aurora-shell-agrid" width="80" height="80" patternUnits="userSpaceOnUse">
            <path d="M 80 0 L 0 0 0 80" fill="none" stroke="var(--fg, #f5f5f5)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#aurora-shell-agrid)" />
      </svg>
    </div>
  )
}

function TopBar({ activeModule, tint }: { activeModule: ModuleId; tint: string }) {
  const mainModel = useAppStore((s) => s.mainModel)
  const services = useAppStore((s) => s.services)
  const runtimeServices = useAppStore((s) => s.runtimeServices)
  const ollamaOk = services?.ollama || runtimeServices?.ollama?.running || false
  const entry = SIDE_MODULES.find((m) => m.id === activeModule)
  const moduleLabel = entry?.label ?? activeModule
  const moduleId = String(activeModule).toUpperCase()
  const modelShort = mainModel.split('/').pop() || mainModel
  return (
    <div className="aurora-v1-topbar" style={{
      height: 56, padding: '0 22px',
      display: 'flex', alignItems: 'center', gap: 18,
      borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
      background: 'color-mix(in oklch, var(--bg, #0c0a09) 78%, transparent)',
      backdropFilter: 'blur(12px)',
      position: 'relative', zIndex: 5,
      flexShrink: 0,
    }}>
      {/* Logotype */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <span style={{
          width: 22, height: 22, borderRadius: 99, flexShrink: 0,
          background: `radial-gradient(circle at 30% 30%, var(--ember-200, #ffb195), var(--ember-600, #c5421d))`,
          boxShadow: '0 0 18px var(--ember-500, #ff6a3d)',
        }} />
        <span style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontStyle: 'italic',
          fontSize: 22, letterSpacing: '-0.02em', lineHeight: 1,
          color: 'var(--fg, #f5f5f5)',
        }}>Aurora</span>
        <span style={{
          fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
          color: 'var(--fg-mute, #888)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          padding: '2px 6px', borderRadius: 3, whiteSpace: 'nowrap',
        }}>v2.4 · LOCAL</span>
      </div>

      <span style={{ width: 1, height: 22, background: 'var(--line, rgba(255,255,255,0.12))', flexShrink: 0 }} />

      {/* Breadcrumb */}
      <div className="aurora-v1-status" style={{
        display: 'flex', alignItems: 'center', gap: 10,
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 12,
        whiteSpace: 'nowrap', minWidth: 0, overflow: 'hidden',
      }}>
        <span style={{
          color: 'var(--fg-mute, #888)',
          textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>{moduleId} /</span>
        <span style={{ color: 'var(--fg, #f5f5f5)' }}>{moduleLabel}</span>
      </div>

      <div style={{ flex: 1 }} />

      {/* Status cluster — real values */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16,
        fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11,
        color: 'var(--fg-dim, #aaa)',
      }}>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <PulseDot color={ollamaOk ? 'oklch(0.74 0.13 145)' : 'var(--fg-mute, #777)'} size={6} />
          ollama:{modelShort}
        </span>
        <span style={{ color: tint }}>● {moduleLabel.toLowerCase()}</span>
      </div>

      {/* ⌘K / ⌘, */}
      <button type="button"
        title="Recherche globale (⌘K)"
        style={{
          fontFamily: 'inherit', fontSize: 12,
          background: 'var(--bg-card, rgba(255,255,255,0.04))',
          color: 'var(--fg, #f5f5f5)',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8,
          padding: '6px 12px', cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}>⌘K</button>
      <button type="button"
        title="Paramètres (⌘,)"
        aria-label="Ouvrir les paramètres"
        onClick={() => window.dispatchEvent(new Event('aurora:open-settings'))}
        style={{
          background: 'transparent',
          border: 'none',
          padding: 4,
          cursor: 'pointer',
          color: 'var(--fg-dim, #aaa)',
          display: 'inline-flex',
          alignItems: 'center',
          transition: 'color 0.15s ease, transform 0.1s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = 'var(--fg, #f5f5f5)'
          e.currentTarget.style.transform = 'rotate(30deg)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = 'var(--fg-dim, #aaa)'
          e.currentTarget.style.transform = 'rotate(0deg)'
        }}
      ><Settings size={16} /></button>
    </div>
  )
}

function Sidebar({ activeModule, onActivateModule }: {
  activeModule: ModuleId
  onActivateModule: (id: ModuleId | 'cowork' | 'voice') => void
}) {
  return (
    <div className="aurora-v1-sidebar" style={{
      width: 232, padding: '20px 14px',
      borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
      background: 'color-mix(in oklch, var(--bg-raised, rgba(255,255,255,0.02)) 50%, transparent)',
      display: 'flex', flexDirection: 'column', gap: 4,
      position: 'relative', zIndex: 5,
      flexShrink: 0,
    }}>
      <Eyebrow style={{ padding: '0 12px 8px' }}>Modules</Eyebrow>
      {SIDE_MODULES.map((entry) => (
        <SideItem
          key={entry.id}
          entry={entry}
          active={entry.id === activeModule}
          onClick={() => onActivateModule(entry.id)}
        />
      ))}
      <div className="aurora-v1-sidebar-spacer" style={{ flex: 1 }} />
      {/* v82s-studio iter13 : l'agent du module actif, vivant (respiration,
          clignement). Décoratif — ouvrir le panneau d'agents via ⌘, ou TopBar. */}
      <Suspense fallback={<div style={{ height: 210 }} />}>
        <div className="aurora-v1-sidebar-persona">
          <SidebarPersona moduleId={activeModule} />
        </div>
      </Suspense>
      <div className="aurora-v1-sidebar-session">
      <Eyebrow style={{ padding: '14px 12px 6px' }}>Session</Eyebrow>
      <div style={{
        padding: 12,
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 10,
        display: 'flex', gap: 10, alignItems: 'center',
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 99,
          background: 'radial-gradient(circle at 30% 30%, var(--ember-200, #ffb195), var(--ember-700, #c5421d))',
        }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg, #f5f5f5)' }}>
            Aurora · solo
          </div>
          <div style={{
            fontSize: 10, color: 'var(--fg-mute, #777)',
            fontFamily: 'var(--font-mono, ui-monospace, monospace)',
          }}>session locale</div>
        </div>
      </div>
      </div>
    </div>
  )
}

export default function AuroraV1AppShell({
  activeModule,
  onActivateModule,
  children,
}: {
  activeModule: ModuleId
  onActivateModule: (id: ModuleId | 'cowork' | 'voice') => void
  children: ReactNode
}) {
  const entry = SIDE_MODULES.find((m) => m.id === activeModule)
  const tint = entry?.tint ?? 'var(--aura-cowork, oklch(0.70 0.150 40))'

  // v82v : the global ⌘1-⌘8 / ⌘` / ⌘V handler now lives up at the App
  // root so it works on every skin (V3 has no Sidebar). The AppShell's
  // own handler from v82u was redundant and removed.

  // Cowork and voice are not module pages — they open via overlay/store.
  // The shell hands their click to the consumer which dispatches as needed.
  return (
    <div className="grain aurora-v1-shell" style={{
      // v82m4 : fixe la hauteur à 100dvh pour empêcher le shell de dépasser
      // la viewport — sinon main overflow:auto ne pouvait jamais clamper et
      // le contenu (prompt video, etc.) sortait sous la taskbar OS.
      width: '100%', height: '100dvh', maxHeight: '100dvh',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      display: 'flex', flexDirection: 'column', position: 'relative',
      overflow: 'hidden',
      fontFamily: 'var(--font-sans, system-ui)',
    }}>
      <AmbientBackdrop tint={tint} />
      <TopBar activeModule={activeModule} tint={tint} />
      <div className="aurora-v1-body" style={{
        display: 'flex', flex: 1, minHeight: 0, position: 'relative', zIndex: 2,
      }}>
        <Sidebar activeModule={activeModule} onActivateModule={onActivateModule} />
        <main style={{
          // v82m3 : permet aux modules (Vidéo notamment) de scroller leur
          // contenu vertical. Avant overflow:hidden cachait tout dépassement
          // sous la viewport, le user voyait le prompt à moitié sous la
          // taskbar OS.
          flex: 1, minWidth: 0, position: 'relative',
          overflowY: 'auto', overflowX: 'hidden',
        }}>
          {children}
        </main>
      </div>
    </div>
  )
}
