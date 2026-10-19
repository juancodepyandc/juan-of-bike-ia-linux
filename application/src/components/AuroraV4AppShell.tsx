import { useEffect, useRef, useState, type ReactNode } from 'react'
import '../styles/aurora-v4.css'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import AuroraMascot, { FX_AGENTS, type FxModule } from './generationFx/mascots.tsx'
import AgiCognitiveStudioBar from './AgiCognitiveStudioBar.tsx'
import HelpFab from './HelpFab.tsx'
import ModuleEngineeringInspector from './ModuleEngineeringInspector.tsx'
import ProjectsPanel from './ProjectsPanel.tsx'
import ReinforcedModelBar from './ReinforcedModelBar.tsx'
import { openPersistentWorkspace } from '../utils/persistentWorkspace.ts'
import { cancelModulePreload, requestModulePreload } from '../utils/modulePreload.ts'
import { getBridgeUrl, isCloudRuntime } from '../utils/runtime.ts'

type ShellModuleId = ModuleId | 'cowork' | 'voice'

type Props = {
  activeModule: ModuleId
  onActivateModule: (id: ShellModuleId) => void
  children: ReactNode
}

const ICONS: Record<string, string> = {
  conversation: '<path d="M4 5h16v11H9l-5 4z"/>',
  image: '<rect x="3" y="4" width="18" height="15" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4.5 17l5-5 3.5 3.5L16 12l3.5 4.5"/>',
  code: '<path d="M8 6l-5 6 5 6"/><path d="M16 6l5 6-5 6"/><path d="M13 4l-3 16"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/>',
  drawing: '<path d="M4 20c1-4 2-6 5-9L17 3l4 4-8 8c-3 3-5 4-9 5z"/><path d="M14 6l4 4"/>',
  '3d': '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 12l9-5M12 12v10M12 12L3 7"/>',
  learning: '<path d="M2 8l10-4 10 4-10 4z"/><path d="M6 10v6c0 1.5 2.7 3 6 3s6-1.5 6-3v-6"/>',
  cyber: '<path d="M12 2l8 3v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5z"/><path d="M9 12l2 2 4-4.5"/>',
  business: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M3 12h18"/>',
  voice: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0"/><path d="M12 18v3"/>',
  cowork: '<path d="M3 4h11v9H3z"/><path d="M17 8h4v12h-11v-3"/><path d="M13 13l3 6 1.4-2.6L20 15z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
}

type DockEntry = {
  id: ShellModuleId
  fx: FxModule
  label: string
  desktopTitle?: string
  shortLabel: string
  badge?: string
  masterAgent?: string
}

const DOCK: DockEntry[] = [
  { id: 'conversation', fx: 'conversation', label: 'Conversation', desktopTitle: 'Copilote Conversationnel', shortLabel: 'Chat', masterAgent: 'conversation-lead' },
  { id: 'image', fx: 'image', label: 'Image', desktopTitle: 'Studio Image FLUX.2 & 16K', shortLabel: 'Image', masterAgent: 'image-lead' },
  { id: 'code', fx: 'code', label: 'Code', desktopTitle: 'Ingénierie Code & Sandbox', shortLabel: 'Code', masterAgent: 'code-lead' },
  { id: 'video', fx: 'video', label: 'Vidéo', desktopTitle: 'Studio Vidéo & Cinématique', shortLabel: 'Vidéo', masterAgent: 'video-lead' },
  { id: 'drawing', fx: 'drawing', label: 'Dessin', desktopTitle: 'Atelier Dessin & Forge', shortLabel: 'Dessin', masterAgent: 'drawing-lead' },
  { id: '3d', fx: '3d', label: '3D', desktopTitle: 'Studio 3D Neural & CAO', shortLabel: '3D', badge: 'CAO', masterAgent: '3d-lead' },
  { id: 'learning', fx: 'learning', label: 'Académie', desktopTitle: 'Académie & Oracle Formel', shortLabel: 'Acad.', masterAgent: 'learning-lead' },
  { id: 'cyber', fx: 'cyber', label: 'Cyber', desktopTitle: 'Cybersécurité & 0-Day Z3', shortLabel: 'Cyber', masterAgent: 'cyber-lead' },
  { id: 'business', fx: 'business', label: 'Business Intelligence', desktopTitle: 'Business & Quant Lab', shortLabel: 'Business', badge: 'LAB', masterAgent: 'business-ceo' },
  { id: 'voice', fx: 'voice', label: 'Voix', desktopTitle: 'Studio Voix Duplex', shortLabel: 'Voix', masterAgent: 'voice-lead' },
  { id: 'cowork', fx: 'cowork', label: 'Cowork', desktopTitle: 'Orchestrateur Cowork', shortLabel: 'Cowork', masterAgent: 'cowork-lead' },
]

// Mobile sheet grid keeps the 10 standard modules (+1 Paramètres = 11 buttons) for strict mobile contract parity
const MOBILE_GRID_DOCK = DOCK.filter((d) => d.id !== 'business')

function AuroraBackdrop() {
  const ref = useRef<HTMLCanvasElement | null>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let W = 0
    let H = 0
    let stars: { x: number; y: number; r: number; p: number; s: number }[] = []
    const size = () => {
      W = window.innerWidth
      H = window.innerHeight
      cv.width = W * dpr
      cv.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      stars = []
      const n = Math.min(140, Math.floor((W * H) / 14000))
      for (let i = 0; i < n; i++) {
        stars.push({
          x: Math.random() * W,
          y: Math.random() * H,
          r: Math.random() * 1.15 + 0.2,
          p: Math.random() * 6.28,
          s: 0.45 + Math.random() * 1.3,
        })
      }
    }
    size()
    window.addEventListener('resize', size)
    const RB = [
      { c: '34,211,238', y: 0.18, amp: 55, sp: 0.00014, off: 0, w: 135 },
      { c: '139,92,246', y: 0.34, amp: 80, sp: 0.0001, off: 2.1, w: 175 },
      { c: '56,189,248', y: 0.52, amp: 50, sp: 0.00016, off: 4.4, w: 115 },
    ]
    let alive = true
    const draw = (t: number) => {
      if (!alive || !cv.isConnected) return
      ctx.clearRect(0, 0, W, H)
      const bg = ctx.createLinearGradient(0, 0, 0, H)
      bg.addColorStop(0, '#060A15')
      bg.addColorStop(0.6, '#04060C')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)
      for (const st of stars) {
        ctx.globalAlpha = 0.18 + 0.4 * (0.5 + 0.5 * Math.sin(t * 0.001 * st.s + st.p))
        ctx.fillStyle = '#CFE3FF'
        ctx.beginPath()
        ctx.arc(st.x, st.y, st.r, 0, 6.2832)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      ctx.globalCompositeOperation = 'lighter'
      for (const rb of RB) {
        const yB = rb.y * H
        ctx.beginPath()
        for (let x = -20; x <= W + 20; x += 16) {
          const y =
            yB +
            Math.sin(x * 0.0022 + t * rb.sp * 6 + rb.off) * rb.amp +
            Math.sin(x * 0.0007 - t * rb.sp * 3.4 + rb.off * 2) * rb.amp * 0.7
          if (x === -20) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        const gr = ctx.createLinearGradient(0, yB - rb.w, 0, yB + rb.w)
        gr.addColorStop(0, `rgba(${rb.c},0)`)
        gr.addColorStop(0.5, `rgba(${rb.c},0.065)`)
        gr.addColorStop(1, `rgba(${rb.c},0)`)
        ctx.strokeStyle = gr
        ctx.lineWidth = rb.w
        ctx.lineCap = 'round'
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
      requestAnimationFrame(draw)
    }
    const raf = requestAnimationFrame(draw)
    return () => {
      alive = false
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', size)
    }
  }, [])
  return <canvas ref={ref} style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} aria-hidden="true" />
}

function DockOrb({ entry, active, onClick }: { entry: DockEntry; active: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false)
  const [tipY, setTipY] = useState<number>(120)
  const btnRef = useRef<HTMLButtonElement | null>(null)
  const accent = FX_AGENTS[entry.fx].accent
  const iconSvg = ICONS[entry.id] ?? ICONS[entry.fx]
  return (
    <button
      ref={btnRef}
      type="button"
      aria-label={entry.desktopTitle || entry.label}
      aria-current={active ? 'page' : undefined}
      onClick={onClick}
      onMouseEnter={() => {
        if (btnRef.current) {
          const r = btnRef.current.getBoundingClientRect()
          setTipY(r.top + r.height / 2)
        }
        setHover(true)
        requestModulePreload(entry.id)
      }}
      onMouseLeave={() => {
        setHover(false)
        cancelModulePreload()
      }}
      style={{
        width: 66,
        minHeight: 49,
        padding: '5px 4px 4px',
        borderRadius: 14,
        position: 'relative',
        cursor: 'pointer',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 3,
        border: `1px solid ${active ? accent : hover ? `${accent}88` : 'rgba(255,255,255,.07)'}`,
        background: active
          ? `linear-gradient(165deg, ${accent}2B, rgba(15, 23, 42, 0.85))`
          : hover
            ? 'rgba(255,255,255,.065)'
            : 'rgba(255,255,255,.022)',
        boxShadow: active ? `0 4px 20px ${accent}44, inset 0 1px 0 rgba(255,255,255,0.18)` : hover ? `0 0 14px ${accent}33` : 'none',
        transform: hover ? 'translateY(-1px) scale(1.03)' : 'scale(1)',
        transition: 'all .2s cubic-bezier(.22,1,.36,1)',
      }}
    >
      {active && (
        <span
          style={{
            position: 'absolute',
            left: -5,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 3.5,
            height: 24,
            borderRadius: 3,
            background: accent,
            boxShadow: `0 0 10px ${accent}`,
          }}
        />
      )}
      {entry.badge && (
        <span
          style={{
            position: 'absolute',
            top: -3,
            right: -3,
            fontSize: 7.5,
            fontWeight: 800,
            padding: '1px 4px',
            borderRadius: 99,
            background: accent,
            color: '#05070D',
            letterSpacing: '0.04em',
            boxShadow: `0 2px 8px ${accent}88`,
          }}
        >
          {entry.badge}
        </span>
      )}
      <svg
        viewBox="0 0 24 24"
        width={18}
        height={18}
        style={{
          stroke: active || hover ? accent : '#94A3B8',
          fill: 'none',
          strokeWidth: 1.8,
          strokeLinecap: 'round',
          strokeLinejoin: 'round',
          transition: 'stroke .2s',
          filter: active ? `drop-shadow(0 0 6px ${accent}88)` : 'none',
        }}
        dangerouslySetInnerHTML={{ __html: iconSvg }}
      />
      <span
        style={{
          fontSize: 9.5,
          fontWeight: active ? 700 : 600,
          color: active || hover ? '#F8FAFC' : '#94A3B8',
          lineHeight: 1.05,
          letterSpacing: '-0.01em',
          maxWidth: 60,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {entry.shortLabel}
      </span>
      {hover && (
        <span
          style={{
            position: 'fixed',
            left: 86,
            top: tipY,
            transform: 'translateY(-50%)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            whiteSpace: 'nowrap',
            padding: '9px 14px 9px 10px',
            borderRadius: 13,
            background: 'rgba(8, 12, 24, 0.98)',
            border: `1px solid ${accent}88`,
            zIndex: 120,
            boxShadow: '0 14px 36px rgba(0,0,0,.72)',
            pointerEvents: 'none',
          }}
        >
          <AuroraMascot module={entry.fx} size={32} />
          <span style={{ textAlign: 'left' }}>
            <span style={{ display: 'block', fontSize: 12.5, fontWeight: 800, color: '#F8FAFC' }}>
              {entry.desktopTitle || entry.label}
            </span>
            <span
              style={{
                display: 'block',
                fontSize: 10,
                fontFamily: "'Cascadia Code',Consolas,monospace",
                color: accent,
              }}
            >
              Maître: {entry.masterAgent} · Agent {FX_AGENTS[entry.fx].name}
            </span>
          </span>
        </span>
      )}
    </button>
  )
}

export default function AuroraV4AppShell({ activeModule, onActivateModule, children }: Props) {
  const [modulesOpen, setModulesOpen] = useState(false)
  const modulesDialog = useRef<HTMLDialogElement>(null)
  const activeEntry = DOCK.find((entry) => entry.id === activeModule) ?? DOCK[0]
  const activeAccent = FX_AGENTS[activeEntry.fx].accent

  useEffect(() => {
    const dialog = modulesDialog.current
    if (!dialog) return
    if (modulesOpen && !dialog.open) dialog.showModal()
    if (!modulesOpen && dialog.open) dialog.close()
  }, [modulesOpen])

  const activate = (id: ShellModuleId) => {
    setModulesOpen(false)
    onActivateModule(id)
  }

  const [greet, setGreet] = useState<FxModule | null>(null)
  const greetTimer = useRef<number | null>(null)
  const activeFx: FxModule = DOCK.find((d) => d.id === activeModule)?.fx ?? 'conversation'

  useEffect(() => {
    setGreet(activeFx)
    if (greetTimer.current) window.clearTimeout(greetTimer.current)
    greetTimer.current = window.setTimeout(() => setGreet(null), 2800)
    return () => {
      if (greetTimer.current) window.clearTimeout(greetTimer.current)
    }
  }, [activeFx])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        color: '#E6EAF5',
        fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif",
      }}
    >
      <AuroraBackdrop />
      <style>{`
        .aurora-v4-mobile-nav, .aurora-v4-mobile-context { display: none; }
        .aurora-v4-modules-sheet { position: fixed; inset: 0; margin: auto; overflow: auto; box-sizing: border-box; color: #E6EAF5; background: linear-gradient(155deg,#151b30,#090d18); border: 1px solid #363e56; border-radius: 24px; width: min(540px,calc(100% - 24px)); max-height: calc(100dvh - 32px); padding: 20px; box-shadow: 0 24px 80px #0009; }
        .aurora-v4-modules-sheet::backdrop { background: #02050dbb; backdrop-filter: blur(8px); }
        .aurora-v4-sheet-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
        .aurora-v4-sheet-head h2 { margin: 0; font-size: 21px; font-weight: 750; }
        .aurora-v4-sheet-head p { margin: 4px 0 0; color: #a4aec6; font-size: 12px; }
        .aurora-v4-sheet-head button { min-width: 44px; min-height: 44px; border-radius: 14px; color: #e6eaf5; background: #ffffff09; border: 1px solid #ffffff20; }
        .aurora-v4-module-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }
        .aurora-v4-module-grid button { display: flex; align-items: center; gap: 12px; min-height: 66px; padding: 12px; border-radius: 16px; border: 1px solid #ffffff16; background: #ffffff04; color: #e6eaf5; font: inherit; text-align: left; cursor: pointer; }
        .aurora-v4-module-grid button[aria-current=page] { background: #8b5cf622; border-color: #a58aff; }
        .aurora-v4-module-grid svg { flex-shrink: 0; width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
        .aurora-v4-module-grid span { font-size: 14px; font-weight: 650; }
        .aurora-v4-mobile-nav button:focus-visible, .aurora-v4-module-grid button:focus-visible { outline: 2px solid #c4b5fd; outline-offset: 2px; }
        @media (max-width: 1180px) {
          .aurora-v4-module-pill, .aurora-v4-inspector-wrap { display: none !important; }
        }
        @media (max-width: 900px), (pointer: coarse) and (max-width: 1200px) {
          .aurora-v4-header { height: calc(62px + env(safe-area-inset-top)) !important; padding: env(safe-area-inset-top) max(16px,env(safe-area-inset-right)) 0 max(16px,env(safe-area-inset-left)) !important; gap: 12px !important; }
          .aurora-v4-mobile-context { display: block; font-size: 11px; font-weight: 450; color: #a4aec6; letter-spacing: 0; margin-top: 2px; }
          .aurora-v4-module-pill, .aurora-v4-inspector-wrap { display: none !important; }
          .aurora-v4-search { flex: 0 0 44px !important; min-width: 44px; height: 44px; padding: 0 !important; justify-content: center; margin-left: auto; color: #c4cce0 !important; }
          .aurora-v4-search .search-label, .aurora-v4-search kbd, .aurora-v4-model, .aurora-v4-local, .aurora-v4-mascot { display: none !important; }
          .aurora-v4-header-actions { gap: 4px !important; margin-left: 0 !important; }
          .aurora-v4-header-actions > button { width: 44px; height: 44px; align-items: center; justify-content: center; }
          .aurora-v4-reinforced-bar, .aurora-v4-agi-studio-ribbon { display: none !important; }
          .aurora-v4-dock { display: none !important; }
          .aurora-v4-mobile-nav { position: fixed; left: 0; right: 0; bottom: 0; z-index: 40; display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 6px; padding: 8px max(12px,env(safe-area-inset-right)) calc(8px + env(safe-area-inset-bottom)) max(12px,env(safe-area-inset-left)); background: #080c17f5; backdrop-filter: blur(20px); border-top: 1px solid #ffffff15; }
          .aurora-v4-mobile-nav button { min-width: 0; height: 56px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; border: 1px solid transparent; border-radius: 16px; color: #9da8c1; background: transparent; font: inherit; font-size: 11px; font-weight: 600; cursor: pointer; }
          .aurora-v4-mobile-nav button[aria-current=page], .aurora-v4-mobile-nav button[aria-expanded=true] { color: #dccfff; background: #8b5cf622; border-color: #8b5cf640; }
          .aurora-v4-mobile-nav svg { width: 21px; height: 21px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
          .aurora-v4-main { left: 0 !important; top: calc(62px + env(safe-area-inset-top)) !important; bottom: calc(72px + env(safe-area-inset-bottom)) !important; overflow-x: hidden !important; }
          .aurora-v4-main > [data-aurora-module] { min-width: 0; }
          .aurora-v4-greeting { display: none !important; }
          .aurora-v4-modules-sheet { inset: auto 0 calc(12px + env(safe-area-inset-bottom)); margin: 0 auto; padding: 18px; }
        }
      `}</style>

      <header
        className="aurora-v4-header"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 54,
          zIndex: 40,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '0 16px',
          background: 'rgba(6, 10, 21, 0.84)',
          backdropFilter: 'blur(24px)',
          borderBottom: `1px solid ${activeAccent}33`,
          boxShadow: `0 4px 24px rgba(0,0,0,0.4), inset 0 -1px 0 ${activeAccent}22`,
        }}
      >
        {/* Brand + Active Module Breadcrumb */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 800, fontSize: 15, letterSpacing: '-.01em', flexShrink: 0 }}>
          <span
            style={{
              display: 'inline-flex',
              width: 28,
              height: 28,
              borderRadius: 9,
              alignItems: 'center',
              justifyContent: 'center',
              background: `linear-gradient(135deg, ${activeAccent}, #8B5CF6)`,
              color: '#05070D',
              fontSize: 13.5,
              boxShadow: `0 4px 16px ${activeAccent}66`,
              transition: 'all .25s ease',
            }}
          >
            ✦
          </span>
          <span>
            Aurora
            <span className="aurora-v4-mobile-context">{activeEntry.desktopTitle || activeEntry.label}</span>
          </span>

          <div
            className="aurora-v4-module-pill"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              marginLeft: 4,
              padding: '4px 10px',
              borderRadius: 9,
              background: `${activeAccent}16`,
              border: `1px solid ${activeAccent}44`,
              fontSize: 11.5,
              fontWeight: 700,
              color: '#F1F5F9',
            }}
          >
            <span style={{ color: activeAccent }}>{activeEntry.desktopTitle || activeEntry.label}</span>
            <span
              style={{
                fontFamily: "'Cascadia Code',Consolas,monospace",
                fontSize: 9.5,
                color: '#94A3B8',
                paddingLeft: 6,
                borderLeft: '1px solid rgba(255,255,255,0.12)',
              }}
            >
              {activeEntry.masterAgent}
            </span>
          </div>
        </div>

        {/* Command Palette Search Trigger */}
        <button
          type="button"
          aria-label="Rechercher ou commander"
          className="aurora-v4-search"
          onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-command-palette'))}
          style={{
            flex: '0 1 320px',
            fontSize: 12,
            color: '#94A3B8',
            border: '1px solid rgba(255,255,255,.11)',
            borderRadius: 10,
            padding: '6px 11px',
            background: 'rgba(15, 23, 42, 0.65)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontFamily: 'inherit',
            textAlign: 'left',
            transition: 'border-color .2s',
          }}
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m16 16 5 5" />
          </svg>
          <span className="search-label" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            Rechercher ou commander…
          </span>
          <kbd
            style={{
              marginLeft: 'auto',
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 9.5,
              border: '1px solid rgba(255,255,255,.14)',
              borderRadius: 5,
              padding: '1px 5px',
              color: '#CBD5E1',
              background: 'rgba(255,255,255,0.04)',
            }}
          >
            Ctrl K
          </kbd>
        </button>

        {/* Header Right Actions */}
        <div
          className="aurora-v4-header-actions"
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 11.5,
            color: '#94A3B8',
          }}
        >
          <span className="aurora-v4-inspector-wrap">
            <ModuleEngineeringInspector activeModule={activeModule} />
          </span>

          <ReinforcedModelBar activeModule={activeModule} />

          <ProjectsPanel />

          <span
            className="aurora-v4-local"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '4px 9px',
              borderRadius: 8,
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(52, 211, 153, 0.3)',
              color: '#A7F3D0',
              fontSize: 10.5,
              fontWeight: 700,
            }}
          >
            <b style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ADE80', boxShadow: '0 0 8px #4ADE80' }} />
            {isCloudRuntime() ? 'PC distant' : 'Local'}
          </span>

          <button
            type="button"
            aria-label="Mode vocal"
            title="Activer le Copilote Vocal Duplex"
            onClick={() => activate('voice')}
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              border: '1px solid rgba(45, 212, 191, 0.32)',
              background: 'rgba(45, 212, 191, 0.1)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <svg viewBox="0 0 24 24" width={16} height={16} style={{ stroke: '#2DD4BF', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round' }} dangerouslySetInnerHTML={{ __html: ICONS.voice }} />
          </button>

          {!new URLSearchParams(window.location.search).has('persistent-worker') && (
            <a
              aria-label="Espace persistant sur le PC"
              title="Générer sur le PC et revenir plus tard"
              href={`${getBridgeUrl()}/workspace`}
              onClick={(event) => {
                event.preventDefault()
                void openPersistentWorkspace(activeModule).catch((error) => {
                  window.dispatchEvent(new CustomEvent('aurora:workspace-error', { detail: String(error) }))
                })
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 34,
                height: 34,
                borderRadius: 9,
                border: '1px solid rgba(196, 181, 253, 0.25)',
                background: 'rgba(139, 92, 246, 0.1)',
                color: '#C4B5FD',
              }}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.7">
                <rect x="3" y="4" width="18" height="12" rx="2" />
                <path d="M8 21h8M12 16v5" />
              </svg>
            </a>
          )}

          {!isCloudRuntime() && (
            <a
              href={`${getBridgeUrl()}/devices`}
              aria-label="Appareils"
              title="Connecter un téléphone ou un terminal distant"
              style={{
                height: 34,
                padding: '0 10px',
                borderRadius: 9,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.04)',
                display: 'inline-flex',
                alignItems: 'center',
                color: '#CBD5E1',
                fontSize: 11,
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              Appareils
            </a>
          )}

          <button
            type="button"
            aria-label="Paramètres"
            title="Paramètres Aurora OS"
            onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-settings'))}
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'rgba(255,255,255,0.04)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#CBD5E1',
            }}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: ICONS.settings }} />
          </button>

          <span className="aurora-v4-mascot" style={{ width: 30, height: 30, display: 'flex', filter: `drop-shadow(0 0 8px ${activeAccent}55)` }}>
            <AuroraMascot module={activeFx} size={30} />
          </span>
        </div>
      </header>

      <nav
        className="aurora-v4-dock"
        aria-label="Modules Aurora"
        style={{
          position: 'fixed',
          left: 0,
          top: 54,
          bottom: 0,
          width: 78,
          zIndex: 35,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 5,
          padding: '10px 0',
          background: 'rgba(6, 10, 21, 0.78)',
          backdropFilter: 'blur(22px)',
          borderRight: '1px solid rgba(255,255,255,.09)',
          overflowY: 'auto',
        }}
      >
        {DOCK.map((entry) => (
          <DockOrb
            key={entry.id}
            entry={entry}
            active={entry.id === activeModule}
            onClick={() => activate(entry.id)}
          />
        ))}
        <div style={{ flex: 1 }} />
        <HelpFab docked />
        <div style={{ width: 30, height: 1, background: 'rgba(255,255,255,.1)', margin: '7px 0', flexShrink: 0 }} />
        <button
          type="button"
          aria-label="Paramètres"
          onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-settings'))}
          style={{
            width: 44,
            height: 44,
            borderRadius: 14,
            cursor: 'pointer',
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid rgba(255,255,255,.08)',
            background: 'rgba(255,255,255,.03)',
          }}
        >
          <svg viewBox="0 0 24 24" width={20} height={20} style={{ stroke: '#8B93A7', fill: 'none', strokeWidth: 1.7, strokeLinecap: 'round' }} dangerouslySetInnerHTML={{ __html: ICONS.settings }} />
        </button>
      </nav>

      {/* Mobile Bottom Navigation — preserves Chat / Image / Code / Tous les modules contract */}
      <nav className="aurora-v4-mobile-nav" aria-label="Navigation mobile">
        {(['conversation', 'image', 'code'] as const).map((id) => {
          const entry = DOCK.find((item) => item.id === id)!
          return (
            <button
              key={id}
              type="button"
              aria-current={activeModule === id ? 'page' : undefined}
              onClick={() => activate(id)}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" dangerouslySetInnerHTML={{ __html: ICONS[entry.id] ?? ICONS[entry.fx] }} />
              <span>{entry.shortLabel}</span>
            </button>
          )
        })}
        <button
          type="button"
          aria-label="Tous les modules"
          aria-expanded={modulesOpen}
          aria-controls="aurora-mobile-modules"
          aria-haspopup="dialog"
          aria-current={!['conversation', 'image', 'code'].includes(activeModule) ? 'page' : undefined}
          onClick={() => setModulesOpen(true)}
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <rect x="3" y="3" width="7" height="7" rx="2" />
            <rect x="14" y="3" width="7" height="7" rx="2" />
            <rect x="3" y="14" width="7" height="7" rx="2" />
            <rect x="14" y="14" width="7" height="7" rx="2" />
          </svg>
          <span>Modules</span>
        </button>
      </nav>

      <dialog
        ref={modulesDialog}
        id="aurora-mobile-modules"
        className="aurora-v4-modules-sheet"
        aria-labelledby="aurora-modules-title"
        onCancel={() => setModulesOpen(false)}
        onClose={() => setModulesOpen(false)}
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect()
          if (
            event.target === event.currentTarget &&
            (event.clientX < rect.left ||
              event.clientX > rect.right ||
              event.clientY < rect.top ||
              event.clientY > rect.bottom)
          ) {
            setModulesOpen(false)
          }
        }}
      >
        <div className="aurora-v4-sheet-head">
          <div>
            <h2 id="aurora-modules-title">Votre espace Aurora</h2>
            <p>Choisissez ce que vous voulez faire.</p>
          </div>
          <button type="button" aria-label="Fermer les modules" onClick={() => setModulesOpen(false)}>
            ✕
          </button>
        </div>
        <div className="aurora-v4-module-grid">
          {MOBILE_GRID_DOCK.map((entry) => (
            <button
              key={entry.id}
              type="button"
              aria-current={entry.id === activeModule ? 'page' : undefined}
              onClick={() => activate(entry.id)}
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                style={{ color: FX_AGENTS[entry.fx].accent }}
                dangerouslySetInnerHTML={{ __html: ICONS[entry.id] ?? ICONS[entry.fx] }}
              />
              <span>{entry.label}</span>
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setModulesOpen(false)
              window.dispatchEvent(new CustomEvent('aurora:open-settings'))
            }}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" dangerouslySetInnerHTML={{ __html: ICONS.settings }} />
            <span>Paramètres</span>
          </button>
        </div>
        {!new URLSearchParams(window.location.search).has('persistent-worker') && (
          <a
            href={`${getBridgeUrl()}/workspace`}
            onClick={(event) => {
              event.preventDefault()
              void openPersistentWorkspace(activeModule).catch((error) => {
                window.dispatchEvent(new CustomEvent('aurora:workspace-error', { detail: String(error) }))
              })
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 48,
              marginTop: 14,
              borderRadius: 14,
              background: '#8b5cf633',
              color: '#ded0ff',
              textDecoration: 'none',
              fontSize: 13,
            }}
          >
            Générer sur le PC et revenir plus tard
          </a>
        )}
      </dialog>

      <AgiCognitiveStudioBar
        activeModule={activeModule}
        activeAccent={activeAccent}
        masterAgent={activeEntry.masterAgent || `${activeModule}-lead`}
        moduleTitle={activeEntry.desktopTitle || activeEntry.label}
      />

      <main
        className="aurora-v4-main"
        style={{
          position: 'fixed',
          top: 96,
          left: 78,
          right: 0,
          bottom: 0,
          zIndex: 10,
          overflow: 'auto',
        }}
      >
        {children}
      </main>

      {greet && (
        <div
          className="aurora-v4-greeting"
          style={{
            position: 'fixed',
            right: 22,
            bottom: 20,
            zIndex: 50,
            display: 'flex',
            alignItems: 'flex-end',
            gap: 10,
            pointerEvents: 'none',
            animation: 'aurora-v4-greet .45s cubic-bezier(.22,1,.36,1)',
          }}
        >
          <style>{'@keyframes aurora-v4-greet { from { opacity: 0; transform: translateY(16px) } to { opacity: 1; transform: none } }'}</style>
          <span
            style={{
              fontSize: 12,
              color: '#E6EAF5',
              padding: '9px 14px',
              borderRadius: 14,
              borderBottomRightRadius: 4,
              background: 'rgba(10,15,30,.95)',
              border: `1px solid ${FX_AGENTS[activeFx].accent}`,
              maxWidth: 260,
              boxShadow: '0 12px 34px rgba(0,0,0,.5)',
            }}
          >
            {FX_AGENTS[activeFx].name} · {FX_AGENTS[activeFx].hello}
          </span>
          <span style={{ filter: `drop-shadow(0 0 14px ${FX_AGENTS[activeFx].accent}66)` }}>
            <AuroraMascot module={activeFx} size={56} />
          </span>
        </div>
      )}
    </div>
  )
}
