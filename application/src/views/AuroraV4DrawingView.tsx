import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import AuroraMascot from '../components/generationFx/mascots.tsx'
import { useDrawingViewLogic, PALETTE, PORTRAITS } from '../hooks/useDrawingViewLogic.ts'
import { useModuleStreak } from '../hooks/useModuleStreak.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { getDailyTip } from '../utils/dailyTip.ts'
import { loadBlobUrl } from '../utils/blobStore.ts'
import type { PromptHistoryEntry } from '../utils/promptHistory.ts'
import FavoriteButton from '../components/FavoriteButton.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'

const ACCENT = '#A3E635'
const PAPER = '#F5F1E6'
const MONO = "'Cascadia Code',Consolas,monospace"
const SANS = "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif"
const STAGE_H = 'clamp(440px, calc(100vh - 340px), 860px)'

const ICONS = {
  brush: 'M9.06 11.9l8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08 M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z',
  eraser: 'M7 21l-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21 M22 21H7 M5 11l9 9',
  mirror: 'M12 3v18 M16 8l4 4-4 4 M8 8l-4 4 4 4',
  undo: 'M3 7v6h6 M21 17a9 9 0 0 0-15-6.7L3 13',
  redo: 'M21 7v6h-6 M3 17a9 9 0 0 1 15-6.7L21 13',
  sheet: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3',
  spark: 'M12 3l1.9 5.9L20 10.8l-6.1 1.9L12 19l-1.9-6.3L4 10.8l6.1-1.9z',
  stop: 'M7 7h10v10H7z',
  shuffle: 'M16 3h5v5 M4 20L21 3 M21 16v5h-5 M15 15l6 6 M4 4l5 5',
  x: 'M18 6L6 18 M6 6l12 12',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 3',
  flame: 'M12 22c4.4 0 7.5-2.9 7.5-6.8 0-3.1-2-5.2-3.6-6.8C14.4 7 13.2 5.2 13.2 2.5c-3.3 2.1-5.6 4.9-5.6 8-1-1-1.6-2.1-1.7-3.2C4.4 9.3 4 11.6 4 13.6 4 18.6 7.6 22 12 22z',
  alert: 'M12 3L2 20h20z M12 10v4 M12 17v.01',
}

function Ico({ name, size = 14 }: { name: keyof typeof ICONS; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d={ICONS[name]} />
    </svg>
  )
}

function Glass({ children, style, className }: { children?: ReactNode; style?: CSSProperties; className?: string }) {
  return (
    <div className={className} style={{
      background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
      border: '1px solid rgba(255,255,255,.09)',
      borderRadius: 18,
      backdropFilter: 'blur(18px)',
      boxShadow: '0 24px 60px -42px rgba(0,0,0,.65)',
      ...style,
    }}>{children}</div>
  )
}

function Tech({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      fontFamily: MONO, fontSize: 10, letterSpacing: '.2em',
      textTransform: 'uppercase', color: '#8B93A7', ...style,
    }}>{children}</div>
  )
}

function GradNum({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <span style={{
      fontFamily: MONO, fontWeight: 800,
      background: `linear-gradient(120deg, ${ACCENT}, #F4FDE2 85%)`,
      WebkitBackgroundClip: 'text', backgroundClip: 'text',
      WebkitTextFillColor: 'transparent', color: 'transparent',
      ...style,
    }}>{children}</span>
  )
}

function Kbd({ children }: { children: ReactNode }) {
  return (
    <span style={{
      fontFamily: MONO, fontSize: 9, letterSpacing: '.1em',
      padding: '2px 7px', borderRadius: 6,
      border: '1px solid rgba(255,255,255,.14)',
      background: 'rgba(255,255,255,.04)', color: '#8B93A7',
    }}>{children}</span>
  )
}

function Chip({ active, onClick, children, disabled, title }: {
  active?: boolean; onClick?: () => void; children: ReactNode; disabled?: boolean; title?: string
}) {
  return (
    <button type="button" className="v4d-chip" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontSize: 11, padding: '5px 11px', borderRadius: 999,
        border: `1px solid ${active ? ACCENT : 'rgba(255,255,255,.1)'}`,
        background: active ? ACCENT : 'rgba(255,255,255,.03)',
        color: active ? '#0A0F1E' : '#8B93A7',
        fontWeight: active ? 700 : 500,
        fontFamily: SANS,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        boxShadow: active ? `0 4px 16px -6px ${ACCENT}AA` : 'none',
        display: 'inline-flex', alignItems: 'center', gap: 6,
        transition: 'all .25s',
      }}>{children}</button>
  )
}

function SecBtn({ onClick, children, disabled, title }: {
  onClick?: () => void; children: ReactNode; disabled?: boolean; title?: string
}) {
  return (
    <button type="button" className="v4d-sec" onClick={onClick} disabled={disabled} title={title}
      style={{
        border: '1px solid rgba(255,255,255,.14)',
        background: 'rgba(255,255,255,.03)',
        color: '#8B93A7', borderRadius: 11,
        padding: '8px 12px', fontSize: 12, fontFamily: SANS, fontWeight: 600,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 7,
        transition: 'all .25s',
      }}>{children}</button>
  )
}

function HistoryThumb({ entry, onClick }: { entry: PromptHistoryEntry; onClick: () => void }) {
  const [url, setUrl] = useState<string | null>(null)
  const renderBlobId = typeof entry.meta?.renderBlobId === 'string' ? entry.meta.renderBlobId : ''

  useEffect(() => {
    if (!renderBlobId) {
      setUrl(null)
      return
    }
    let alive = true
    let objectUrl: string | null = null
    void loadBlobUrl(renderBlobId).then((loaded) => {
      if (!alive) {
        if (loaded) URL.revokeObjectURL(loaded)
        return
      }
      objectUrl = loaded
      setUrl(loaded)
    })
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [renderBlobId])

  if (!url) return null

  return (
    <button type="button" onClick={onClick} title="Rappeler ce rendu"
      style={{
        width: 36, height: 36, padding: 0, borderRadius: 8,
        border: '1px solid rgba(255,255,255,.12)',
        background: 'rgba(10,15,30,.6)',
        cursor: 'pointer', overflow: 'hidden',
      }}>
      <img src={url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
    </button>
  )
}

export default function AuroraV4DrawingView() {
  const D = useDrawingViewLogic({ paperColor: PAPER })
  const latestD = useRef(D)
  latestD.current = D
  const streak = useModuleStreak('drawing')
  const fileRef = useRef<HTMLInputElement>(null)
  const [promptFocus, setPromptFocus] = useState(false)

  useEffect(() => {
    const PRESETS = [1, 2, 4, 6, 12]
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return
      const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const idx = ['1', '2', '3', '4', '5'].indexOf(e.key)
      if (idx !== -1) {
        e.preventDefault()
        D.setBrushSize(PRESETS[idx])
        return
      }
      const k = e.key.toLowerCase()
      if (k === 'b') { e.preventDefault(); D.setBrush('ink') }
      else if (k === 'e') { e.preventDefault(); D.setBrush('eraser') }
      else if (k === 's') { e.preventDefault(); D.setSymmetry(!D.symmetry) }
      else if (k === 'x') {
        e.preventDefault()
        D.setBrush(D.brush === 'ink' ? 'eraser' : 'ink')
      }
      else if (e.key === '[') {
        e.preventDefault()
        D.setBrushSize(Math.max(1, D.brushSize - 1))
      }
      else if (e.key === ']') {
        e.preventDefault()
        D.setBrushSize(Math.min(12, D.brushSize + 1))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [D])

  const drop = useFileDrop({
    onFile: (file) => void D.loadImageToCanvas(file),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: D.rendering,
  })

  const recents = D.colorHistory.filter((c) => !D.pinnedColors.includes(c))

  return (
    <div {...drop.bind} className="v4d-root" style={{
      padding: '22px 26px', minHeight: '100%', color: '#E6EAF5',
      fontFamily: SANS, position: 'relative',
      outline: drop.isDraggingOver ? `2px dashed ${ACCENT}` : 'none',
      outlineOffset: -8,
    }}>
      <style>{`
        @keyframes v4dPulse { 0%,100%{opacity:.45;transform:scale(1)} 50%{opacity:1;transform:scale(1.3)} }
        @keyframes v4dRise { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
        @keyframes v4dFade { from{opacity:0} to{opacity:1} }
        @keyframes v4dSweep { 0%{left:-55%;opacity:0} 12%{opacity:.85} 100%{left:135%;opacity:0} }
        @keyframes v4dScan { 0%{transform:translateX(-110%)} 100%{transform:translateX(320%)} }
        @keyframes v4dBreath { 0%,100%{opacity:.55;transform:scale(.96)} 50%{opacity:1;transform:scale(1.05)} }
        @keyframes v4dFloat { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
        @keyframes v4dOrbA { 0%,100%{transform:translate(0,0) scale(1)} 33%{transform:translate(48px,36px) scale(1.12)} 66%{transform:translate(-32px,16px) scale(.94)} }
        @keyframes v4dOrbB { 0%,100%{transform:translate(0,0) scale(1)} 40%{transform:translate(-54px,-28px) scale(1.08)} 75%{transform:translate(28px,-42px) scale(.9)} }
        @keyframes v4dBeam { 0%{top:-28%} 100%{top:110%} }
        @keyframes v4dBand { 0%,100%{background-position:0% 50%} 50%{background-position:100% 50%} }
        .v4d-root { position: relative; isolation: isolate }
        .v4d-root::before {
          content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
          background:
            radial-gradient(640px 420px at 10% -8%, ${ACCENT}14, transparent 62%),
            radial-gradient(520px 460px at 94% 4%, ${ACCENT}0d, transparent 65%),
            radial-gradient(760px 540px at 46% 114%, ${ACCENT}0a, transparent 62%);
        }
        .v4d-root::after {
          content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none; opacity: .55;
          background-image: radial-gradient(rgba(230,234,245,.07) 1px, transparent 1.4px), radial-gradient(${ACCENT}14 1px, transparent 1.4px);
          background-size: 34px 34px, 56px 56px;
          background-position: 0 0, 17px 29px;
          -webkit-mask-image: radial-gradient(ellipse 95% 75% at 50% 0%, #000 25%, transparent 100%);
          mask-image: radial-gradient(ellipse 95% 75% at 50% 0%, #000 25%, transparent 100%);
        }
        .v4d-rise { animation: v4dRise .55s cubic-bezier(.22,1,.36,1) backwards }
        .v4d-fade { animation: v4dFade .5s ease backwards }
        .v4d-float { animation: v4dFloat 5.5s ease-in-out infinite }
        .v4d-orb { position: absolute; border-radius: 999px; filter: blur(64px); pointer-events: none }
        .v4d-chip:hover:not(:disabled) { border-color: rgba(163,230,53,.45); transform: translateY(-1px); filter: drop-shadow(0 6px 10px rgba(163,230,53,.22)) }
        .v4d-sec:hover:not(:disabled) { border-color: rgba(163,230,53,.5); color: #E6EAF5; transform: translateY(-1px); box-shadow: 0 10px 24px -14px rgba(163,230,53,.35) }
        .v4d-card { transition: transform .35s cubic-bezier(.22,1,.36,1), box-shadow .35s ease }
        .v4d-card:hover { box-shadow: inset 0 0 0 1px rgba(163,230,53,.34), 0 30px 70px -36px rgba(163,230,53,.3), 0 26px 60px -30px rgba(0,0,0,.7) !important }
        .v4d-lift:hover { transform: translateY(-3px) }
        .v4d-primary { position: relative; overflow: hidden; transition: all .25s }
        .v4d-primary:hover:not(:disabled) { transform: translateY(-2px); filter: saturate(1.12) brightness(1.06) }
        .v4d-primary::after { content:""; position:absolute; top:-30%; bottom:-30%; left:-55%; width:38%; background:linear-gradient(105deg, transparent, rgba(255,255,255,.65), transparent); transform:skewX(-20deg); opacity:0; pointer-events:none }
        .v4d-primary:hover:not(:disabled)::after { animation: v4dSweep .85s ease }
        .v4d-swatch { transition: all .25s cubic-bezier(.22,1,.36,1) }
        .v4d-swatch:hover { transform: scale(1.16) rotate(-4deg); filter: drop-shadow(0 5px 9px rgba(163,230,53,.3)) }
        .v4d-peg { transition: all .3s cubic-bezier(.22,1,.36,1) }
        .v4d-peg:hover { transform: translateY(-4px) rotate(0deg) !important; filter: drop-shadow(0 10px 14px rgba(163,230,53,.22)) }
        .v4d-row { transition: border-color .25s, background .25s, transform .25s }
        .v4d-row:hover { border-color: rgba(163,230,53,.3) !important; background: rgba(163,230,53,.05) !important; transform: translateX(3px) }
        .v4d-render { transition: transform .4s cubic-bezier(.22,1,.36,1) }
        .v4d-render:hover { transform: scale(1.015) }
        .v4d-root ::-webkit-scrollbar { width: 6px; height: 6px }
        .v4d-root ::-webkit-scrollbar-track { background: transparent }
        .v4d-root ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.13); border-radius: 999px }
        .v4d-root ::-webkit-scrollbar-thumb:hover { background: rgba(163,230,53,.55) }
        .v4d-root ::selection { background: rgba(163,230,53,.85); color: #0A0F1E }
        @media (prefers-reduced-motion: reduce) {
          .v4d-root *, .v4d-root::before, .v4d-root::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important }
          .v4d-card:hover, .v4d-lift:hover, .v4d-primary:hover:not(:disabled), .v4d-chip:hover:not(:disabled), .v4d-sec:hover:not(:disabled), .v4d-swatch:hover, .v4d-peg:hover, .v4d-row:hover { transform: none !important }
        }
        @media (max-width: 1080px) {
          .v4d-grid { grid-template-columns: 1fr !important; }
          .v4d-rail { height: auto !important; }
        }
        @media (max-width: 700px) {
          .v4d-root { padding: 14px 12px !important }
        }
      `}</style>

      <div aria-hidden style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <div className="v4d-orb" style={{
          top: '-4%', left: '4%', width: 340, height: 340,
          background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`,
          animation: 'v4dOrbA 24s ease-in-out infinite',
        }} />
        <div className="v4d-orb" style={{
          bottom: '-8%', right: '6%', width: 420, height: 420,
          background: `radial-gradient(circle, ${ACCENT}26, transparent 70%)`,
          animation: 'v4dOrbB 30s ease-in-out infinite',
        }} />
      </div>

      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
          zIndex: 60, pointerEvents: 'none',
          padding: '8px 18px', borderRadius: 999,
          background: ACCENT, color: '#0A0F1E',
          fontFamily: MONO, fontSize: 11, fontWeight: 700,
          letterSpacing: '.2em', textTransform: 'uppercase',
          boxShadow: `0 6px 24px ${ACCENT}66`,
        }}>
          Déposer l'image · base de tracé
        </div>
      )}

      <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void D.loadImageToCanvas(f)
          e.currentTarget.value = ''
        }} />

      <header className="v4d-rise" style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14, flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
        <div className="v4d-float" style={{ position: 'relative', display: 'grid', placeItems: 'center' }}>
          <span aria-hidden style={{
            position: 'absolute', width: 76, height: 76, borderRadius: 999,
            background: `radial-gradient(circle, ${ACCENT}38, transparent 70%)`,
            filter: 'blur(8px)',
            animation: D.rendering ? 'v4dBreath 1.6s ease-in-out infinite' : 'v4dBreath 4.5s ease-in-out infinite',
          }} />
          <AuroraMascot module="drawing" size={46} state={D.rendering ? 'working' : 'idle'} />
        </div>
        <div style={{ flex: 1, minWidth: 180 }}>
          <h1 style={{
            margin: 0, fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', fontFamily: SANS,
            background: `linear-gradient(115deg, #ffffff 40%, ${ACCENT})`,
            WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>Dessin</h1>
          <Tech style={{ marginTop: 4 }}>Atelier Sumi · croquis pression → vision → FLUX local</Tech>
          <div aria-hidden style={{
            marginTop: 7, height: 2, width: 180, borderRadius: 999,
            background: `linear-gradient(90deg, ${ACCENT}, #F4FDE2 35%, ${ACCENT}44 65%, ${ACCENT})`,
            backgroundSize: '220% 100%',
            boxShadow: `0 0 12px ${ACCENT}55`,
            animation: 'v4dBand 6s ease-in-out infinite',
          }} />
        </div>
        {D.line.length > 0 && (
          <div title={`${D.line.length} feuille(s) sur la corde à séchage`} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontSize: 11, padding: '5px 11px', borderRadius: 999,
            border: '1px solid rgba(255,255,255,.12)', background: 'rgba(255,255,255,.03)',
            color: '#8B93A7', fontFamily: MONO, letterSpacing: '.08em',
          }}>
            <Ico name="sheet" size={11} /> <GradNum>{D.line.length}</GradNum>
          </div>
        )}
        {D.history.length > 0 && (
          <div title={`${D.history.length} invocation(s) dans l'historique`} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontSize: 11, padding: '5px 11px', borderRadius: 999,
            border: '1px solid rgba(255,255,255,.12)', background: 'rgba(255,255,255,.03)',
            color: '#8B93A7', fontFamily: MONO, letterSpacing: '.08em',
          }}>
            <Ico name="clock" size={11} /> <GradNum>{D.history.length}</GradNum>
          </div>
        )}
        {streak.current > 0 && (
          <div title={`Streak créativité : ${streak.current} jour(s) consécutif(s) — record ${streak.longest} jour(s)`}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 11, padding: '5px 11px', borderRadius: 999,
              border: `1px solid ${ACCENT}55`, color: streak.current >= 7 ? ACCENT : '#8B93A7',
              background: `${ACCENT}0D`,
              fontFamily: MONO, letterSpacing: '.08em',
            }}>
            <Ico name="flame" size={12} /> <GradNum>{streak.current}j</GradNum>{streak.longest > streak.current ? ` · record ${streak.longest}j` : ''}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <SecBtn onClick={D.undo} disabled={D.historyLen === 0} title="Annuler (Ctrl+Z)">
            <Ico name="undo" /> Annuler{D.historyLen > 0 ? ` · ${D.historyLen}` : ''}
          </SecBtn>
          <SecBtn onClick={D.redo} disabled={D.futureLen === 0} title="Rétablir (Ctrl+Y)">
            <Ico name="redo" /> Rétablir{D.futureLen > 0 ? ` · ${D.futureLen}` : ''}
          </SecBtn>
          <SecBtn onClick={D.clearCanvas} title="Nouvelle feuille vierge">
            <Ico name="sheet" /> Feuille
          </SecBtn>
          <SecBtn onClick={() => fileRef.current?.click()} disabled={D.rendering} title="Importer une image comme base de tracé">
            <Ico name="upload" /> Importer
          </SecBtn>
          <SecBtn onClick={D.downloadRender} disabled={!D.renderUrl} title="Télécharger le rendu PNG">
            <Ico name="download" /> PNG
          </SecBtn>
        </div>
      </header>

      <div aria-hidden style={{
        position: 'relative', zIndex: 1, height: 1, marginBottom: 16,
        background: `linear-gradient(90deg, ${ACCENT}4D, rgba(255,255,255,.08) 35%, transparent 92%)`,
      }} />

      <div className="v4d-grid" style={{ display: 'grid', gridTemplateColumns: '232px minmax(0,1fr) 300px', gap: 16, alignItems: 'stretch', position: 'relative', zIndex: 1 }}>
        <Glass className="v4d-rail v4d-card v4d-lift v4d-rise" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14, height: STAGE_H, overflowY: 'auto', animationDelay: '.05s' }}>
          <Tech>Pinceaux · B / E / S / X</Tech>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Chip active={D.brush === 'ink'} onClick={() => D.setBrush('ink')} title="Pinceau encre (B)">
              <Ico name="brush" size={12} /> Encre
            </Chip>
            <Chip active={D.brush === 'eraser'} onClick={() => D.setBrush('eraser')} title="Gomme (E)">
              <Ico name="eraser" size={12} /> Gomme
            </Chip>
            <Chip active={D.symmetry} onClick={() => D.setSymmetry(!D.symmetry)} title="Symétrie verticale (S)">
              <Ico name="mirror" size={12} /> Symétrie
            </Chip>
          </div>

          <div aria-hidden style={{ height: 1, background: 'linear-gradient(90deg, rgba(255,255,255,.1), transparent)' }} />

          <Tech>Encres</Tech>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {PALETTE.map((c, i) => (
              <button key={c} type="button" className="v4d-swatch v4d-fade"
                onClick={() => { D.setInkColor(c); D.setBrush('ink') }}
                title={c.toUpperCase()}
                style={{
                  width: 24, height: 24, borderRadius: 8, background: c,
                  border: D.inkColor === c ? `2px solid ${ACCENT}` : '1px solid rgba(255,255,255,.18)',
                  boxShadow: D.inkColor === c ? `0 0 12px ${ACCENT}55` : 'none',
                  cursor: 'pointer', padding: 0,
                  animationDelay: `${i * 22}ms`,
                }} />
            ))}
            <label className="v4d-swatch" title="Couleur personnalisée" style={{
              width: 24, height: 24, borderRadius: 8, cursor: 'pointer',
              border: `1px dashed rgba(255,255,255,.35)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#8B93A7',
            }}>
              <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round"><path d="M12 5v14 M5 12h14" /></svg>
              <input type="color" value={D.inkColor}
                onChange={(e) => { D.setInkColor(e.target.value); D.setBrush('ink') }}
                style={{ display: 'none' }} />
            </label>
          </div>

          {D.pinnedColors.length > 0 && (
            <>
              <Tech>Épinglées</Tech>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {D.pinnedColors.map((c, i) => (
                  <button key={`pin-${c}`} type="button" className="v4d-swatch v4d-fade"
                    onClick={(e) => {
                      if (e.shiftKey) { D.togglePinColor(c); return }
                      D.setInkColor(c); D.setBrush('ink')
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      D.togglePinColor(c)
                    }}
                    title={`Épinglée · ${c.toUpperCase()}\nShift+clic ou clic droit = désépingler`}
                    style={{
                      width: 20, height: 20, borderRadius: 7, background: c, padding: 0,
                      border: D.inkColor === c ? `2px solid ${ACCENT}` : `1px solid ${ACCENT}88`,
                      boxShadow: `0 0 8px ${ACCENT}33`,
                      cursor: 'pointer',
                      animationDelay: `${i * 25}ms`,
                    }} />
                ))}
              </div>
            </>
          )}

          {recents.length > 0 && (
            <>
              <Tech>Récentes</Tech>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {recents.map((c, i) => (
                  <button key={c} type="button" className="v4d-swatch v4d-fade"
                    onClick={(e) => {
                      if (e.shiftKey) { D.togglePinColor(c); return }
                      D.setInkColor(c); D.setBrush('ink')
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      D.removeColorFromHistory(c)
                    }}
                    title={`Récente · ${c.toUpperCase()}\nShift+clic = épingler · Clic droit = retirer`}
                    style={{
                      width: 18, height: 18, borderRadius: 6, background: c, padding: 0,
                      border: D.inkColor === c ? `2px solid ${ACCENT}` : '1px solid rgba(255,255,255,.18)',
                      cursor: 'pointer',
                      animationDelay: `${i * 25}ms`,
                    }} />
                ))}
              </div>
            </>
          )}

          <div aria-hidden style={{ height: 1, background: 'linear-gradient(90deg, rgba(255,255,255,.1), transparent)' }} />

          <Tech>Rendu IA</Tech>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Chip active={D.colorMode === 'auto'} onClick={() => D.setColorMode('auto')} title="Couleur décidée par le brief et le croquis">Auto</Chip>
            <Chip active={D.colorMode === 'color'} onClick={() => D.setColorMode('color')} title="Forcer un rendu couleur">Couleur</Chip>
            <Chip active={D.colorMode === 'monochrome'} onClick={() => D.setColorMode('monochrome')} title="Forcer le noir et blanc">N&B</Chip>
          </div>

          <Tech>Trait · <GradNum>{D.brushSize.toFixed(1)}px</GradNum> · touches 1-5</Tech>
          <input type="range" min={1} max={12} step={0.5} value={D.brushSize}
            onChange={(e) => D.setBrushSize(Number(e.target.value))}
            style={{ width: '100%', accentColor: ACCENT }} />
          <div style={{ display: 'flex', gap: 4 }}>
            {[1, 2, 4, 6, 12].map((sz) => {
              const active = Math.abs(D.brushSize - sz) < 0.25
              return (
                <button key={sz} type="button"
                  onClick={() => D.setBrushSize(sz)}
                  title={`Trait ${sz}px`}
                  style={{
                    flex: 1, padding: '4px 0', borderRadius: 8,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                    background: active ? ACCENT : 'rgba(255,255,255,.03)',
                    color: active ? '#0A0F1E' : '#8B93A7',
                    border: `1px solid ${active ? ACCENT : 'rgba(255,255,255,.1)'}`,
                    cursor: 'pointer',
                    fontFamily: MONO, fontSize: 10, fontWeight: active ? 700 : 500,
                    transition: 'all .25s',
                  }}>
                  <span style={{
                    width: Math.min(sz, 9), height: Math.min(sz, 9), borderRadius: '50%',
                    background: active ? '#0A0F1E' : '#8B93A7',
                  }} />
                  {sz}
                </button>
              )
            })}
          </div>

          <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{
              fontSize: 11, lineHeight: 1.5, color: '#5A6377',
              border: '1px solid rgba(255,255,255,.07)', borderRadius: 11, padding: '8px 10px',
              background: 'rgba(255,255,255,.015)',
            }}>
              {getDailyTip('drawing')}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: 0.55 }}>
              <img src={PORTRAITS[D.who]} alt={D.who} style={{ width: 34, height: 34, objectFit: 'cover', borderRadius: 10, border: `1px solid ${ACCENT}33` }} />
              <Tech style={{ fontSize: 9 }}>Compagnon · {D.who}</Tech>
            </div>
          </div>
        </Glass>

        <Glass className="v4d-card v4d-rise" style={{ padding: 10, height: STAGE_H, display: 'flex', position: 'relative', animationDelay: '.1s' }}>
          <div style={{
            position: 'relative', flex: 1, borderRadius: 12, overflow: 'hidden',
            background: PAPER,
            boxShadow: D.rendering
              ? `inset 0 0 0 2px ${ACCENT}66, inset 0 0 60px ${ACCENT}14, inset 0 0 40px rgba(10,15,30,.08)`
              : 'inset 0 0 40px rgba(10,15,30,.08)',
            transition: 'box-shadow .4s',
          }}>
            <canvas
              ref={D.canvasRef}
              {...D.canvasHandlers}
              style={{
                width: '100%', height: '100%', display: 'block',
                cursor: D.brush === 'eraser' ? 'cell' : 'crosshair',
                touchAction: 'none',
              }} />
            <div aria-hidden style={{
              position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.4,
              backgroundImage: 'radial-gradient(rgba(26,20,13,.06) 1px, transparent 1.2px)',
              backgroundSize: '22px 22px',
            }} />
            <span aria-hidden style={{ position: 'absolute', top: 7, left: 7, width: 13, height: 13, borderTop: '1.5px solid rgba(26,20,13,.35)', borderLeft: '1.5px solid rgba(26,20,13,.35)', pointerEvents: 'none' }} />
            <span aria-hidden style={{ position: 'absolute', top: 7, right: 7, width: 13, height: 13, borderTop: '1.5px solid rgba(26,20,13,.35)', borderRight: '1.5px solid rgba(26,20,13,.35)', pointerEvents: 'none' }} />
            <span aria-hidden style={{ position: 'absolute', bottom: 7, left: 7, width: 13, height: 13, borderBottom: '1.5px solid rgba(26,20,13,.35)', borderLeft: '1.5px solid rgba(26,20,13,.35)', pointerEvents: 'none' }} />
            <span aria-hidden style={{ position: 'absolute', bottom: 7, right: 7, width: 13, height: 13, borderBottom: '1.5px solid rgba(26,20,13,.35)', borderRight: '1.5px solid rgba(26,20,13,.35)', pointerEvents: 'none' }} />
            {D.rendering && (
              <div aria-hidden style={{
                position: 'absolute', left: 0, right: 0, height: '24%', top: '-28%',
                pointerEvents: 'none',
                background: `linear-gradient(180deg, transparent, ${ACCENT}26, transparent)`,
                animation: 'v4dBeam 2.4s linear infinite',
              }} />
            )}
            <div style={{
              position: 'absolute', top: 10, left: 28, pointerEvents: 'none',
              fontFamily: MONO, fontSize: 9, letterSpacing: '.2em', textTransform: 'uppercase',
              color: 'rgba(26,20,13,.4)',
            }}>
              Feuille · pression active · persistance auto
            </div>
            <div style={{
              position: 'absolute', bottom: 10, right: 28, pointerEvents: 'none',
              fontFamily: MONO, fontSize: 9, letterSpacing: '.18em', textTransform: 'uppercase',
              color: 'rgba(26,20,13,.45)',
              display: 'flex', alignItems: 'center', gap: 7,
            }}>
              {D.brush === 'eraser' ? 'Gomme' : 'Encre'} · {D.brushSize.toFixed(1)}px{D.symmetry ? ' · Miroir' : ''}
              <span style={{
                width: 9, height: 9, borderRadius: 999,
                background: D.brush === 'eraser' ? PAPER : D.inkColor,
                border: '1px solid rgba(26,20,13,.3)',
              }} />
            </div>
          </div>
        </Glass>

        <div className="v4d-rail" style={{ height: STAGE_H, display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
          <Glass className="v4d-card v4d-lift v4d-rise" style={{ flex: 1, padding: 14, display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0, animationDelay: '.15s' }}>
            <Tech style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 7, height: 7, borderRadius: 999,
                background: D.rendering ? ACCENT : D.renderUrl ? ACCENT : '#5A6377',
                boxShadow: D.rendering || D.renderUrl ? `0 0 10px ${ACCENT}` : 'none',
                animation: D.rendering ? 'v4dPulse 1.2s ease-in-out infinite' : 'none',
              }} />
              Rendu FLUX
              <span style={{
                marginLeft: 'auto', fontFamily: MONO, fontSize: 9, letterSpacing: '.14em',
                padding: '2px 8px', borderRadius: 999,
                border: `1px solid ${D.rendering || D.renderUrl ? `${ACCENT}55` : 'rgba(255,255,255,.1)'}`,
                background: D.rendering ? `${ACCENT}14` : 'transparent',
                color: D.rendering || D.renderUrl ? ACCENT : '#5A6377',
              }}>
                {D.rendering ? 'invocation' : D.renderUrl ? 'prêt' : 'veille'}
              </span>
            </Tech>
            <div style={{ flex: 1, minHeight: 0, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {D.renderUrl ? (
                <img src={D.renderUrl} alt="Rendu FLUX"
                  className="v4d-rise v4d-render"
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 12, boxShadow: `0 18px 50px -24px ${ACCENT}44` }} />
              ) : D.rendering ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, color: '#8B93A7' }}>
                  <span style={{
                    width: 10, height: 10, borderRadius: 999, background: ACCENT,
                    boxShadow: `0 0 14px ${ACCENT}`,
                    animation: 'v4dPulse 1.2s ease-in-out infinite',
                  }} />
                  <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '.12em', textAlign: 'center' }}>
                    {D.progress || 'Rendu en cours…'}
                  </span>
                  <span style={{ width: 148, height: 3, borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,.07)', display: 'block' }}>
                    <span style={{
                      display: 'block', width: '38%', height: '100%', borderRadius: 999,
                      background: `linear-gradient(90deg, transparent, ${ACCENT}, transparent)`,
                      animation: 'v4dScan 1.4s ease-in-out infinite',
                    }} />
                  </span>
                </div>
              ) : (
                <div className="v4d-fade" style={{
                  alignSelf: 'stretch', flex: 1, borderRadius: 14,
                  border: '1px dashed rgba(255,255,255,.12)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10,
                  color: '#5A6377', fontSize: 12, textAlign: 'center', padding: 14,
                }}>
                  <div className="v4d-float" style={{ position: 'relative', display: 'flex' }}>
                    <span aria-hidden style={{
                      position: 'absolute', inset: -18, borderRadius: 999, pointerEvents: 'none',
                      background: `radial-gradient(circle, ${ACCENT}26, transparent 70%)`,
                      filter: 'blur(6px)',
                    }} />
                    <AuroraMascot module="drawing" size={90} state="idle" />
                  </div>
                  <div style={{ color: '#8B93A7', fontSize: 12, lineHeight: 1.55, maxWidth: 230 }}>
                    Ta feuille est prête — trace quelques traits, je m'occupe de la magie.
                  </div>
                  <div style={{
                    fontFamily: MONO, fontSize: 9, letterSpacing: '.18em', textTransform: 'uppercase',
                    color: ACCENT, opacity: 0.85,
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                  }}>
                    <Ico name="spark" size={11} /> Ctrl+Entrée pour invoquer
                  </div>
                </div>
              )}
            </div>
            {D.renderUrl && !D.rendering && (
              <SecBtn onClick={D.downloadRender} title="Télécharger le rendu PNG">
                <Ico name="download" /> Télécharger le PNG
              </SecBtn>
            )}
          </Glass>

          <Glass className="v4d-card v4d-lift v4d-rise" style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8, animationDelay: '.2s' }}>
            <Tech>Corde à séchage · <GradNum>{D.line.length}</GradNum></Tech>
            {D.line.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#5A6377', lineHeight: 1.5 }}>
                <span style={{
                  width: 5, height: 5, borderRadius: 999, background: '#5A6377', flexShrink: 0,
                  animation: 'v4dPulse 2.6s ease-in-out infinite',
                }} />
                Les feuilles générées sécheront ici — lance une première invocation.
              </div>
            ) : (
              <div style={{ position: 'relative', paddingTop: 12 }}>
                <svg aria-hidden width="100%" height="14" viewBox="0 0 100 14" preserveAspectRatio="none"
                  style={{ position: 'absolute', top: 0, left: 0, display: 'block', pointerEvents: 'none' }}>
                  <path d="M0 3 Q 50 13 100 3" fill="none" stroke={`${ACCENT}59`} strokeWidth={1} vectorEffect="non-scaling-stroke" />
                </svg>
                <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 6 }}>
                  {D.line.map((sheet, i) => (
                    <button key={sheet.id} type="button" className="v4d-peg v4d-fade"
                      onClick={() => D.recallSheet(sheet)}
                      title={`${sheet.prompt}\nClic = rappeler feuille + rendu`}
                      style={{
                        position: 'relative', flexShrink: 0,
                        width: 64, padding: 0, background: 'transparent', border: 'none',
                        cursor: 'pointer',
                        transform: `rotate(${i % 2 === 0 ? -2 : 1.8}deg)`,
                        transformOrigin: 'top center',
                        animationDelay: `${Math.min(i, 10) * 55}ms`,
                      }}>
                      <span style={{
                        position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)',
                        width: 6, height: 6, borderRadius: 999, background: ACCENT,
                        boxShadow: `0 0 8px ${ACCENT}88`,
                      }} />
                      <img src={sheet.renderUrl ?? sheet.sketchUrl} alt={sheet.prompt}
                        style={{
                          width: '100%', aspectRatio: '1/1', objectFit: 'cover',
                          borderRadius: 8, border: '1px solid rgba(255,255,255,.14)',
                          display: 'block',
                        }} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Glass>
        </div>
      </div>

      <Glass className="v4d-card v4d-rise" style={{ marginTop: 16, padding: 16, display: 'flex', flexDirection: 'column', gap: 10, position: 'relative', zIndex: 1, animationDelay: '.25s' }}>
        <Tech style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          Invocation
          <span aria-hidden style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(255,255,255,.1), transparent)' }} />
          <Kbd>Ctrl</Kbd>
          <span style={{ color: '#5A6377' }}>+</span>
          <Kbd>Entrée</Kbd>
        </Tech>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <VoicePushToTalk
            onTranscript={(text) => D.setPrompt((D.prompt ? D.prompt + ' ' : '') + text)}
            label="Dicter l'intention de dessin"
            disabled={D.rendering}
            variant="ghost"
            size={34}
          />
          <textarea
            value={D.prompt}
            onChange={(e) => D.setPrompt(e.target.value)}
            onFocus={() => setPromptFocus(true)}
            onBlur={() => setPromptFocus(false)}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void D.invoke() } }}
            disabled={D.rendering}
            placeholder="Décris ton intention — Aurora lit ta feuille et invoque le rendu. Ctrl+Entrée pour lancer."
            rows={2}
            style={{
              flex: 1, padding: '10px 12px', fontSize: 13, lineHeight: 1.5,
              background: 'rgba(10,15,30,.6)', color: '#E6EAF5',
              border: `1px solid ${promptFocus ? ACCENT : 'rgba(255,255,255,.12)'}`,
              borderRadius: 11, outline: 'none', resize: 'none',
              fontFamily: SANS,
              boxShadow: promptFocus ? `0 0 16px ${ACCENT}40` : 'none',
              transition: 'all .25s',
            }} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {D.rendering ? (
              <button type="button" className="v4d-primary" onClick={D.stop}
                style={{
                  padding: '10px 16px', borderRadius: 12, border: 'none',
                  background: 'linear-gradient(120deg, #F43F5E, #ffffff33)',
                  color: '#0A0F1E', fontSize: 13, fontWeight: 750, fontFamily: SANS,
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7,
                  boxShadow: '0 6px 24px #F43F5E66',
                }}>
                <Ico name="stop" /> Stop
              </button>
            ) : (
              <button type="button" className="v4d-primary" onClick={() => void D.invoke()} disabled={!D.prompt.trim()}
                style={{
                  padding: '10px 18px', borderRadius: 12, border: 'none',
                  background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`,
                  color: '#0A0F1E', fontSize: 13, fontWeight: 750, fontFamily: SANS,
                  cursor: !D.prompt.trim() ? 'not-allowed' : 'pointer',
                  opacity: !D.prompt.trim() ? 0.5 : 1,
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  boxShadow: `0 8px 28px -6px ${ACCENT}99`,
                }}>
                <Ico name="spark" /> Générer le rendu
              </button>
            )}
            {!D.rendering && (
              <SecBtn
                onClick={() => {
                  D.randomDrawPreset()
                  window.setTimeout(() => { void latestD.current.invoke() }, 0)
                }}
                title="Encre + intention au hasard, puis rendu immédiat">
                <Ico name="shuffle" /> Surprise
              </SecBtn>
            )}
            <FavoriteButton
              prompt={D.prompt}
              module="drawing"
              tags={['drawing']}
              disabled={D.rendering}
            />
          </div>
        </div>

        {D.progress && (D.rendering || D.progress === 'Annulé') && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 6, height: 6, borderRadius: 999,
              background: D.rendering ? ACCENT : '#5A6377',
              boxShadow: D.rendering ? `0 0 8px ${ACCENT}` : 'none',
              animation: D.rendering ? 'v4dPulse 1.2s ease-in-out infinite' : 'none',
            }} />
            <span style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '.12em', color: '#8B93A7' }}>{D.progress}</span>
            {D.rendering && (
              <span style={{ width: 110, height: 2, borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,.07)', display: 'block' }}>
                <span style={{
                  display: 'block', width: '38%', height: '100%', borderRadius: 999,
                  background: `linear-gradient(90deg, transparent, ${ACCENT}, transparent)`,
                  animation: 'v4dScan 1.4s ease-in-out infinite',
                }} />
              </span>
            )}
          </div>
        )}

        {D.error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', borderRadius: 11,
            background: 'rgba(244,63,94,.1)', border: '1px solid rgba(244,63,94,.35)',
            color: '#FDA4AF', fontSize: 12,
          }}>
            <Ico name="alert" size={13} /> {D.error}
          </div>
        )}

        {D.history.length > 0 && (
          <div style={{ position: 'relative', paddingTop: 12 }}>
            <div aria-hidden style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 1,
              background: `linear-gradient(90deg, ${ACCENT}40, rgba(255,255,255,.08) 40%, transparent)`,
            }} />
            <Tech style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <Ico name="clock" size={11} /> Historique · <GradNum>{D.history.length}</GradNum>
            </Tech>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 130, overflowY: 'auto' }}>
              {D.history.map((h, i) => {
                const hasThumb = typeof h.meta?.renderBlobId === 'string'
                return (
                  <div key={h.prompt} className="v4d-row v4d-rise" style={{
                    display: 'grid',
                    gridTemplateColumns: hasThumb ? '40px 1fr 24px' : '1fr 24px',
                    gap: 8, alignItems: 'center',
                    padding: '4px 8px', borderRadius: 10, fontSize: 12,
                    background: 'rgba(255,255,255,.02)',
                    border: '1px solid rgba(255,255,255,.06)',
                    animationDelay: `${Math.min(i, 12) * 35}ms`,
                  }}>
                    {hasThumb && <HistoryThumb entry={h} onClick={() => D.recallPrompt(h)} />}
                    <button type="button" onClick={() => D.recallPrompt(h)} title={h.prompt}
                      style={{
                        background: 'transparent', border: 'none', padding: 0,
                        color: '#E6EAF5', cursor: 'pointer', textAlign: 'left',
                        fontFamily: SANS, fontSize: 12,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{h.prompt}</button>
                    <button type="button" onClick={() => D.removeHistory(h.prompt)}
                      title="Retirer de l'historique"
                      style={{
                        width: 24, height: 24, padding: 0,
                        background: 'rgba(255,255,255,.03)',
                        border: '1px solid rgba(255,255,255,.12)',
                        borderRadius: 8, cursor: 'pointer', color: '#8B93A7',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                      <Ico name="x" size={11} />
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </Glass>
    </div>
  )
}
