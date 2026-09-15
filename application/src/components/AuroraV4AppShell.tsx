import { useEffect, useRef, useState, type ReactNode } from 'react'
import '../styles/aurora-v4.css'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import AuroraMascot, { FX_AGENTS, type FxModule } from './generationFx/mascots.tsx'

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
  voice: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0"/><path d="M12 18v3"/>',
  cowork: '<path d="M3 4h11v9H3z"/><path d="M17 8h4v12h-11v-3"/><path d="M13 13l3 6 1.4-2.6L20 15z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
}

const DOCK: { id: ShellModuleId; fx: FxModule; label: string }[] = [
  { id: 'conversation', fx: 'conversation', label: 'Conversation' },
  { id: 'image', fx: 'image', label: 'Image' },
  { id: 'code', fx: 'code', label: 'Code' },
  { id: 'video', fx: 'video', label: 'Vidéo' },
  { id: 'drawing', fx: 'drawing', label: 'Dessin' },
  { id: '3d', fx: '3d', label: '3D' },
  { id: 'learning', fx: 'learning', label: 'Académie' },
  { id: 'cyber', fx: 'cyber', label: 'Cyber' },
  { id: 'voice', fx: 'voice', label: 'Voix' },
  { id: 'cowork', fx: 'cowork', label: 'Cowork' },
]

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
      const n = Math.min(150, Math.floor((W * H) / 13000))
      for (let i = 0; i < n; i++) stars.push({ x: Math.random() * W, y: Math.random() * H, r: Math.random() * 1.2 + 0.2, p: Math.random() * 6.28, s: 0.5 + Math.random() * 1.4 })
    }
    size()
    window.addEventListener('resize', size)
    const RB = [
      { c: '34,211,238', y: 0.2, amp: 60, sp: 0.00015, off: 0, w: 130 },
      { c: '139,92,246', y: 0.34, amp: 85, sp: 0.0001, off: 2.1, w: 170 },
      { c: '244,114,182', y: 0.5, amp: 55, sp: 0.00018, off: 4.4, w: 110 },
    ]
    let alive = true
    const draw = (t: number) => {
      if (!alive || !cv.isConnected) return
      ctx.clearRect(0, 0, W, H)
      const bg = ctx.createLinearGradient(0, 0, 0, H)
      bg.addColorStop(0, '#070B16')
      bg.addColorStop(0.6, '#05070D')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)
      for (const st of stars) {
        ctx.globalAlpha = 0.2 + 0.45 * (0.5 + 0.5 * Math.sin(t * 0.001 * st.s + st.p))
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
          const y = yB + Math.sin(x * 0.0022 + t * rb.sp * 6 + rb.off) * rb.amp + Math.sin(x * 0.0007 - t * rb.sp * 3.4 + rb.off * 2) * rb.amp * 0.7
          if (x === -20) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        const gr = ctx.createLinearGradient(0, yB - rb.w, 0, yB + rb.w)
        gr.addColorStop(0, `rgba(${rb.c},0)`)
        gr.addColorStop(0.5, `rgba(${rb.c},0.07)`)
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
    return () => { alive = false; cancelAnimationFrame(raf); window.removeEventListener('resize', size) }
  }, [])
  return <canvas ref={ref} style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} aria-hidden="true" />
}

function DockOrb({ entry, active, onClick }: { entry: { id: ShellModuleId; fx: FxModule; label: string }; active: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false)
  const accent = FX_AGENTS[entry.fx].accent
  return (
    <button
      type="button"
      aria-label={entry.label}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width: 44, height: 44, borderRadius: 14, position: 'relative', cursor: 'pointer', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: `1px solid ${active || hover ? accent : 'rgba(255,255,255,.07)'}`,
        background: active ? 'rgba(255,255,255,.05)' : 'rgba(255,255,255,.03)',
        boxShadow: active ? `0 0 16px ${accent}55` : hover ? `0 0 20px ${accent}44` : 'none',
        transform: hover ? 'scale(1.12)' : 'scale(1)',
        transition: 'all .3s cubic-bezier(.22,1,.36,1)',
      }}
    >
      {active && (
        <span style={{ position: 'absolute', left: -13, width: 3.5, height: 20, borderRadius: 3, background: accent, boxShadow: `0 0 10px ${accent}` }} />
      )}
      <svg
        viewBox="0 0 24 24"
        width={20}
        height={20}
        style={{ stroke: active || hover ? accent: '#8B93A7', fill: 'none', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', transition: 'stroke .3s', filter: active ? `drop-shadow(0 0 6px ${accent}88)` : 'none' }}
        dangerouslySetInnerHTML={{ __html: ICONS[entry.fx] }}
      />
      {hover && (
        <span style={{
          position: 'absolute', left: 58, top: '50%', transform: 'translateY(-50%)',
          display: 'flex', alignItems: 'center', gap: 9, whiteSpace: 'nowrap',
          padding: '7px 12px 7px 8px', borderRadius: 11, background: 'rgba(8,12,24,.97)',
          border: `1px solid ${accent}`, zIndex: 60, boxShadow: '0 10px 30px rgba(0,0,0,.55)',
          pointerEvents: 'none',
        }}>
          <AuroraMascot module={entry.fx} size={30} />
          <span style={{ textAlign: 'left' }}>
            <span style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#E6EAF5' }}>{entry.label}</span>
            <span style={{ display: 'block', fontSize: 9.5, fontFamily: "'Cascadia Code',Consolas,monospace", color: accent }}>
              agent {FX_AGENTS[entry.fx].name}
            </span>
          </span>
        </span>
      )}
    </button>
  )
}

export default function AuroraV4AppShell({ activeModule, onActivateModule, children }: Props) {
  const mainModel = useAppStore((s) => s.mainModel)
  const [greet, setGreet] = useState<FxModule | null>(null)
  const greetTimer = useRef<number | null>(null)
  const activeFx: FxModule = (DOCK.find((d) => d.id === activeModule)?.fx ?? 'conversation')

  useEffect(() => {
    setGreet(activeFx)
    if (greetTimer.current) window.clearTimeout(greetTimer.current)
    greetTimer.current = window.setTimeout(() => setGreet(null), 3400)
    return () => { if (greetTimer.current) window.clearTimeout(greetTimer.current) }
  }, [activeFx])

  return (
    <div style={{ position: 'fixed', inset: 0, color: '#E6EAF5', fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif" }}>
      <AuroraBackdrop />

      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 52, zIndex: 40,
        display: 'flex', alignItems: 'center', gap: 16, padding: '0 18px',
        background: 'rgba(5,7,13,.65)', backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,.09)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, fontWeight: 800, fontSize: 15, letterSpacing: '-.01em' }}>
          <span style={{
            display: 'inline-flex', width: 27, height: 27, borderRadius: 8, alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(135deg,#22D3EE,#8B5CF6)', color: '#0A0F1E', fontSize: 13,
            boxShadow: '0 4px 18px rgba(139,92,246,.5)',
          }}>✦</span>
          Aurora
        </div>
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-command-palette'))}
          style={{
            flex: '0 1 380px', fontSize: 12.5, color: '#5A6377', border: '1px solid rgba(255,255,255,.1)',
            borderRadius: 10, padding: '7px 12px', background: 'rgba(10,15,30,.55)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'inherit', textAlign: 'left',
          }}
        >
          <span>⌕</span> Rechercher ou commander…
          <kbd style={{ marginLeft: 'auto', fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10, border: '1px solid rgba(255,255,255,.14)', borderRadius: 5, padding: '1px 6px', color: '#8B93A7' }}>Ctrl K</kbd>
        </button>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16, fontSize: 11.5, color: '#8B93A7' }}>
          <span style={{ fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10.5, color: '#8B5CF6' }}>{mainModel || 'modèle local'}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <b style={{ width: 7, height: 7, borderRadius: '50%', background: '#4ADE80', boxShadow: '0 0 8px #4ADE80' }} />
            local
          </span>
          <button
            type="button"
            aria-label="Mode vocal"
            onClick={() => onActivateModule('voice')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex' }}
          >
            <svg viewBox="0 0 24 24" width={17} height={17} style={{ stroke: '#2DD4BF', fill: 'none', strokeWidth: 1.8, strokeLinecap: 'round' }} dangerouslySetInnerHTML={{ __html: ICONS.voice }} />
          </button>
          <span style={{ width: 32, height: 32, display: 'flex', filter: 'drop-shadow(0 0 10px rgba(139,92,246,.4))' }}>
            <AuroraMascot module={activeFx} size={32} />
          </span>
        </div>
      </header>

      <nav style={{
        position: 'fixed', left: 0, top: 52, bottom: 0, width: 68, zIndex: 35,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, padding: '14px 0',
        background: 'rgba(5,7,13,.55)', backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(255,255,255,.09)',
      }}>
        {DOCK.map((entry) => (
          <DockOrb
            key={entry.id}
            entry={entry}
            active={entry.id === activeModule}
            onClick={() => onActivateModule(entry.id)}
          />
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ width: 30, height: 1, background: 'rgba(255,255,255,.1)', margin: '7px 0', flexShrink: 0 }} />
        <button
          type="button"
          aria-label="Paramètres"
          onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-settings'))}
          style={{
            width: 44, height: 44, borderRadius: 14, cursor: 'pointer', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '1px solid rgba(255,255,255,.07)', background: 'rgba(255,255,255,.03)',
          }}
        >
          <svg viewBox="0 0 24 24" width={20} height={20} style={{ stroke: '#8B93A7', fill: 'none', strokeWidth: 1.7, strokeLinecap: 'round' }} dangerouslySetInnerHTML={{ __html: ICONS.settings }} />
        </button>
      </nav>

      <main style={{
        position: 'fixed', top: 52, left: 68, right: 0, bottom: 0, zIndex: 10,
        overflow: 'auto',
      }}>
        {children}
      </main>

      {greet && (
        <div style={{
          position: 'fixed', right: 22, bottom: 20, zIndex: 50,
          display: 'flex', alignItems: 'flex-end', gap: 10, pointerEvents: 'none',
          animation: 'aurora-v4-greet .5s cubic-bezier(.22,1,.36,1)',
        }}>
          <style>{'@keyframes aurora-v4-greet { from { opacity: 0; transform: translateY(16px) } to { opacity: 1; transform: none } }'}</style>
          <span style={{
            fontSize: 12, color: '#E6EAF5', padding: '9px 14px', borderRadius: 14, borderBottomRightRadius: 4,
            background: 'rgba(10,15,30,.95)', border: `1px solid ${FX_AGENTS[activeFx].accent}`,
            maxWidth: 240, boxShadow: '0 12px 34px rgba(0,0,0,.5)',
          }}>
            {FX_AGENTS[activeFx].name} · {FX_AGENTS[activeFx].hello}
          </span>
          <span style={{ filter: `drop-shadow(0 0 14px ${FX_AGENTS[activeFx].accent}66)` }}>
            <AuroraMascot module={activeFx} size={58} />
          </span>
        </div>
      )}
    </div>
  )
}
