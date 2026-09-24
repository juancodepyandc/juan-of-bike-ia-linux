import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import AuroraMascot from '../components/generationFx/mascots.tsx'
import { useImageViewLogic, DIMENSIONS, type DimensionId, type GeneratedCard } from '../hooks/useImageViewLogic.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore.ts'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import FavoriteButton from '../components/FavoriteButton.tsx'
import { getDailyTip } from '../utils/dailyTip.ts'

const InpaintingPanel = lazy(() => import('../components/InpaintingPanel'))

const ACCENT = '#F472B6'

const glass: React.CSSProperties = {
  background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
  border: '1px solid rgba(255,255,255,.09)',
  borderRadius: 18,
  backdropFilter: 'blur(18px)',
  boxShadow: '0 18px 48px rgba(0,0,0,.3)',
}

const mono: React.CSSProperties = {
  fontFamily: "'Cascadia Code',Consolas,monospace",
  fontSize: 10,
  letterSpacing: '.2em',
  textTransform: 'uppercase',
  color: '#8B93A7',
}

const monoTag: React.CSSProperties = {
  ...mono,
  letterSpacing: '.12em',
  padding: '5px 10px',
  border: '1px solid rgba(255,255,255,.1)',
  borderRadius: 999,
  whiteSpace: 'nowrap',
}

const fieldStyle: React.CSSProperties = {
  background: 'rgba(10,15,30,.6)',
  border: '1px solid rgba(255,255,255,.12)',
  borderRadius: 11,
  color: '#E6EAF5',
  padding: '10px 12px',
  fontSize: 13,
  fontFamily: 'inherit',
  outline: 'none',
  width: '100%',
  transition: 'all .25s',
}

const ICONS = {
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  brush: 'M17 3.7a2.6 2.6 0 0 1 3.6 3.6L12 16l-4 1 1-4zM6.5 17.5c-1.5.3-2.4 1.3-2.9 2.9 1.7-.2 2.8-.7 3.5-1.6',
  expand: 'M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3',
  sparkle: 'M12 3l1.9 5.8 5.8 1.9-5.8 1.9L12 18.4l-1.9-5.8L4.3 10.7l5.8-1.9z',
  stop: 'M7 7h10v10H7z',
  close: 'M18 6 6 18M6 6l12 12',
  plus: 'M12 5v14M5 12h14',
  bolt: 'M13 2 3 14h9l-1 8 10-12h-9l1-8z',
  trash: 'M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6',
  redo: 'M3 12a9 9 0 1 0 2.6-6.4L3 8M3 3v5h5',
  target: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  chevron: 'm6 9 6 6 6-6',
  copy: 'M9 9h11v11H9zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1',
  image: 'M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM21 15l-5-5L5 21',
  pencil: 'M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z',
  check: 'M20 6 9 17l-5-5',
} as const

function Icon({ name, size = 13 }: { name: keyof typeof ICONS; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  )
}

function TechLabel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={{ ...mono, ...style }}>{children}</div>
}

function Divider() {
  return (
    <div aria-hidden="true" style={{
      height: 1,
      background: `linear-gradient(90deg, transparent, ${ACCENT}30, rgba(255,255,255,.1), transparent)`,
    }} />
  )
}

function Chip({ active, onClick, disabled, title, children }: {
  active?: boolean; onClick?: () => void; disabled?: boolean; title?: string; children: React.ReactNode
}) {
  return (
    <button type="button" className="av4img-chip" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontSize: 11,
        padding: '5px 11px',
        borderRadius: 999,
        border: `1px solid ${active ? 'transparent' : 'rgba(255,255,255,.1)'}`,
        background: active ? ACCENT : 'rgba(255,255,255,.03)',
        color: active ? '#0A0F1E' : '#8B93A7',
        fontWeight: active ? 700 : 500,
        boxShadow: active ? `0 4px 16px ${ACCENT}4D` : 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transition: 'all .25s',
        fontFamily: 'inherit',
      }}>{children}</button>
  )
}

function GhostBtn({ onClick, disabled, title, children, style }: {
  onClick?: () => void; disabled?: boolean; title?: string
  children: React.ReactNode; style?: React.CSSProperties
}) {
  return (
    <button type="button" className="av4img-ghost" onClick={onClick} disabled={disabled} title={title}
      style={{
        border: '1px solid rgba(255,255,255,.14)',
        background: 'rgba(255,255,255,.03)',
        color: '#8B93A7',
        borderRadius: 11,
        padding: '7px 12px',
        fontSize: 12,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        transition: 'all .25s',
        fontFamily: 'inherit',
      }}>{children}</button>
  )
}

function OverlayBtn({ onClick, disabled, title, children }: {
  onClick?: () => void; disabled?: boolean; title?: string; children: React.ReactNode
}) {
  return (
    <button type="button" className="av4img-ghost" onClick={onClick} disabled={disabled} title={title}
      style={{
        background: 'rgba(5,8,16,.74)',
        border: '1px solid rgba(255,255,255,.16)',
        color: '#E6EAF5',
        borderRadius: 9,
        padding: '5px 9px',
        fontSize: 11,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        backdropFilter: 'blur(6px)',
        transition: 'all .25s',
        fontFamily: 'inherit',
      }}>{children}</button>
  )
}

function MetaBadge({ children, color, title, onClick }: {
  children: React.ReactNode; color?: string; title?: string; onClick?: () => void
}) {
  return (
    <span title={title} onClick={onClick}
      style={{
        padding: '3px 8px',
        background: 'rgba(5,8,16,.74)',
        color: color ?? '#8B93A7',
        border: '1px solid rgba(255,255,255,.14)',
        borderRadius: 7,
        fontFamily: "'Cascadia Code',Consolas,monospace",
        fontSize: 10,
        letterSpacing: '.06em',
        backdropFilter: 'blur(4px)',
        cursor: onClick ? 'pointer' : 'default',
        whiteSpace: 'nowrap',
      }}>{children}</span>
  )
}

function IntentPill({ children, bg, fg, title }: {
  children: React.ReactNode; bg: string; fg: string; title?: string
}) {
  return (
    <span title={title} style={{
      padding: '2px 8px', borderRadius: 999, fontSize: 10,
      fontFamily: "'Cascadia Code',Consolas,monospace",
      background: bg, color: fg, whiteSpace: 'nowrap',
    }}>{children}</span>
  )
}

function compactMessage(text: string, max = 110) {
  const clean = text
    .replace(/\[image:[^\]]+\]/gi, '[image]')
    .replace(/\[id:[^\]]+\]/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
  return clean.length > max ? `${clean.slice(0, max - 1)}…` : clean
}

const css = `
@keyframes av4ImgRise { from { opacity: 0; transform: translateY(12px) } to { opacity: 1; transform: translateY(0) } }
@keyframes av4ImgPulse { 0%, 100% { opacity: 1 } 50% { opacity: .3 } }
@keyframes av4ImgHalo { 0%, 100% { opacity: .5; transform: scale(1) } 50% { opacity: 1; transform: scale(1.07) } }
@keyframes av4ImgFloat { 0%, 100% { transform: translateY(0) } 50% { transform: translateY(-7px) } }
@keyframes av4ImgSheen { from { transform: translateX(-170%) skewX(-20deg) } to { transform: translateX(330%) skewX(-20deg) } }
@keyframes av4ImgDrift { from { background-position: 0 0 } to { background-position: 44px -32px } }
@keyframes av4ImgOrbit { to { transform: rotate(360deg) } }
@keyframes av4ImgScan { from { left: -42% } to { left: 108% } }
@keyframes av4ImgBarGlint { 0%, 58% { left: -14%; opacity: 0 } 62% { opacity: 1 } 88%, 100% { left: 112%; opacity: 0 } }
@keyframes av4ImgReveal { from { opacity: 0; transform: scale(.976); filter: blur(12px) saturate(.6) } to { opacity: 1; transform: scale(1); filter: blur(0) saturate(1) } }
@keyframes av4ImgHeroShine { from { background-position: 165% 165% } to { background-position: -65% -65% } }
.av4img-root::before { content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none; background: radial-gradient(640px 460px at 8% 0%, ${ACCENT}17, transparent 64%), radial-gradient(700px 540px at 96% 22%, ${ACCENT}0E, transparent 62%), radial-gradient(580px 480px at 40% 108%, rgba(96,165,250,.08), transparent 66%), radial-gradient(520px 400px at 72% 80%, ${ACCENT}0A, transparent 65%); animation: av4ImgDrift 26s ease-in-out infinite alternate; }
.av4img-root::after { content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none; background-image: radial-gradient(rgba(230,234,245,.055) 1px, transparent 1.4px), radial-gradient(${ACCENT}26 1px, transparent 1.5px); background-size: 26px 26px, 340px 340px; background-position: 0 0, 120px 90px; -webkit-mask-image: radial-gradient(ellipse 92% 72% at 50% 0%, #000 28%, transparent 100%); mask-image: radial-gradient(ellipse 92% 72% at 50% 0%, #000 28%, transparent 100%); }
.av4img-root ::selection { background: ${ACCENT}; color: #0A0F1E; }
.av4img-root * { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,.16) transparent; }
.av4img-root ::-webkit-scrollbar { width: 7px; height: 7px; }
.av4img-root ::-webkit-scrollbar-track { background: transparent; }
.av4img-root ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.14); border-radius: 999px; }
.av4img-root ::-webkit-scrollbar-thumb:hover { background: ${ACCENT}99; }
.av4img-grad { background: linear-gradient(90deg, ${ACCENT}, #FFFFFF); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; }
.av4img-gradsoft { background: linear-gradient(115deg, #FFFFFF 35%, ${ACCENT}); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; }
.av4img-bar { position: relative; overflow: hidden; }
.av4img-bar::after { content: ""; position: absolute; top: 0; bottom: 0; left: -14%; width: 12%; border-radius: 999px; background: linear-gradient(90deg, transparent, rgba(255,255,255,.85), transparent); animation: av4ImgBarGlint 5.6s cubic-bezier(.4,0,.2,1) 1.4s infinite; }
.av4img-input:focus { border-color: ${ACCENT} !important; box-shadow: 0 0 16px ${ACCENT}40, inset 0 0 0 1px ${ACCENT}26; }
.av4img-primary { position: relative; overflow: hidden; }
.av4img-primary::after { content: ""; position: absolute; top: -30%; bottom: -30%; left: 0; width: 42%; background: linear-gradient(105deg, transparent, rgba(255,255,255,.5), transparent); transform: translateX(-170%) skewX(-20deg); opacity: 0; pointer-events: none; }
.av4img-primary:hover:not(:disabled) { transform: translateY(-2px); filter: saturate(1.12) brightness(1.06); }
.av4img-primary:hover:not(:disabled)::after { opacity: 1; animation: av4ImgSheen .85s cubic-bezier(.4,0,.2,1); }
.av4img-ghost:hover:not(:disabled) { color: #E6EAF5 !important; border-color: ${ACCENT}66 !important; transform: translateY(-1px); box-shadow: 0 6px 18px rgba(0,0,0,.35); }
.av4img-chip:hover:not(:disabled) { transform: translateY(-1px); border-color: ${ACCENT}59 !important; }
.av4img-panel { position: relative; transition: transform .35s cubic-bezier(.22,1,.36,1), border-color .35s, box-shadow .35s; }
.av4img-panel::before { content: ""; position: absolute; top: 0; left: 14%; right: 14%; height: 1px; border-radius: 999px; background: linear-gradient(90deg, transparent, rgba(255,255,255,.28), ${ACCENT}40, transparent); pointer-events: none; }
.av4img-panel:hover { transform: translateY(-2px); border-color: ${ACCENT}3D !important; box-shadow: inset 0 0 0 1px ${ACCENT}2E, 0 22px 48px -20px ${ACCENT}2E, 0 34px 68px -28px rgba(0,0,0,.7) !important; }
.av4img-live { border-color: ${ACCENT}4D !important; box-shadow: 0 18px 48px rgba(0,0,0,.3), 0 0 44px ${ACCENT}1C !important; }
.av4img-hero { animation: av4ImgReveal .7s cubic-bezier(.22,1,.36,1) both; }
.av4img-hero::after { content: ""; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(115deg, transparent 42%, rgba(255,255,255,.13) 50%, transparent 58%); background-size: 260% 260%; animation: av4ImgHeroShine 1.5s cubic-bezier(.4,0,.2,1) .3s both; }
.av4img-hero > img { transition: transform .9s cubic-bezier(.22,1,.36,1); }
.av4img-hero:hover > img { transform: scale(1.014); }
.av4img-row { transition: border-color .25s, background .25s, transform .25s; }
.av4img-row:hover { border-color: ${ACCENT}55 !important; transform: translateX(3px); }
.av4img-thumb:hover { transform: translateY(-3px); border-color: ${ACCENT}AA !important; box-shadow: 0 10px 24px rgba(0,0,0,.5), 0 0 16px ${ACCENT}33 !important; }
.av4img-thumb img { transition: transform .5s cubic-bezier(.22,1,.36,1); }
.av4img-thumb:hover img { transform: scale(1.12); }
.av4img-orbit { animation: av4ImgOrbit 9s linear infinite; }
.av4img-orbit-rev { animation: av4ImgOrbit 14s linear infinite reverse; }
.av4img-range { accent-color: ${ACCENT}; }
.av4img-menu-item:hover:not(:disabled) { background: ${ACCENT}14 !important; color: #E6EAF5 !important; }
@media (max-width: 1080px) { .av4img-grid { grid-template-columns: 1fr !important; } }
@media (max-width: 700px) { .av4img-root { padding: 14px 12px !important; } }
@media (prefers-reduced-motion: reduce) { .av4img-root *, .av4img-root::before, .av4img-root::after, .av4img-hero, .av4img-hero::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; } }
`

export default function AuroraV4ImageView() {
  const I = useImageViewLogic()
  const [sessionListOpen, setSessionListOpen] = useState(false)
  const [thumbMenu, setThumbMenu] = useState<{ id: string; x: number; y: number } | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  useEffect(() => {
    if (!thumbMenu) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (t && t.closest('[data-thumb-menu]')) return
      setThumbMenu(null)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setThumbMenu(null) }
    window.addEventListener('mousedown', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [thumbMenu])
  const allSessions = useModuleHistoryStore((s) => s.sessions)
  const imageSessions = useMemo(
    () => allSessions.filter((s) => s.module === 'image').slice().sort((a, b) => b.updatedAt - a.updatedAt),
    [allSessions],
  )
  const dim = DIMENSIONS[I.dimensions]
  const drop = useFileDrop({
    onFile: (file) => void I.uploadReferenceFile(file),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: I.generating || I.refUploading,
  })
  const sourceReady = Boolean(I.refPreview || I.current)

  const createNewSession = () => {
    const id = useModuleHistoryStore.getState().createSession('image')
    const sess = useModuleHistoryStore.getState().sessions.find((s) => s.id === id)
    if (sess) I.onImageSessionChange(sess)
    setSessionListOpen(false)
  }
  const switchToSession = (id: string) => {
    useModuleHistoryStore.getState().switchSession('image', id)
    const sess = useModuleHistoryStore.getState().sessions.find((s) => s.id === id)
    if (sess) I.onImageSessionChange(sess)
    setSessionListOpen(false)
  }
  const removeSession = (id: string) => {
    useModuleHistoryStore.getState().deleteSession(id)
    const active = useModuleHistoryStore.getState().getActiveSession('image')
    I.onImageSessionChange(active)
  }
  const startRename = (id: string, title: string) => {
    setRenamingId(id)
    setRenameDraft(title)
  }
  const confirmRename = () => {
    if (renamingId && renameDraft.trim()) {
      useModuleHistoryStore.getState().renameSession(renamingId, renameDraft.trim())
    }
    setRenamingId(null)
  }
  const imageAsReference = async (img: GeneratedCard) => {
    try {
      const res = await fetch(img.url)
      const blob = await res.blob()
      const file = new File([blob], `aurora-ref-${img.id}.png`, { type: blob.type || 'image/png' })
      await I.uploadReferenceFile(file)
    } catch {
    }
  }
  const copyText = async (text: string) => {
    try { await navigator.clipboard.writeText(text) } catch {
    }
  }
  const copyCurrentSeed = async () => {
    if (I.current?.seed === null || I.current?.seed === undefined) return
    await copyText(String(I.current.seed))
  }
  const downloadImage = async (img: GeneratedCard) => {
    const { downloadImageUniversal } = await import('../utils/imageDownload')
    await downloadImageUniversal(img)
  }
  const recallWithSeed = (img: GeneratedCard, offset: number) => {
    I.setPrompt(img.prompt)
    I.setStyle(img.style)
    if (img.seed !== null && img.seed !== undefined) {
      I.setSeed(String(img.seed + offset))
    }
  }
  const replaySeed = (offset: number) => {
    if (I.current) recallWithSeed(I.current, offset)
  }
  const onSourceDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const file = e.dataTransfer.files?.[0]
    if (file && sourceReady && !I.generating && !I.refUploading2) void I.uploadSourceFile(file)
  }
  const launchSurprise = () => {
    const preset = I.randomImagePreset()
    if (preset) void I.queuePrompt(preset)
  }

  return (
    <div {...drop.bind} className="av4img-root" style={{
      padding: '22px 26px',
      minHeight: '100%',
      color: '#E6EAF5',
      fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif",
      position: 'relative',
      isolation: 'isolate',
      outline: drop.isDraggingOver ? `2px dashed ${ACCENT}` : 'none',
      outlineOffset: -8,
      transition: 'outline .2s',
    }}>
      <style>{css}</style>

      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
          zIndex: 60, pointerEvents: 'none',
          padding: '7px 16px', borderRadius: 999,
          background: ACCENT, color: '#0A0F1E',
          fontSize: 11, fontWeight: 750, letterSpacing: '.08em',
          boxShadow: `0 6px 24px ${ACCENT}66`,
        }}>
          Déposer l'image : elle devient la référence d'édition
        </div>
      )}

      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginBottom: 10, animation: 'av4ImgRise .4s cubic-bezier(.22,1,.36,1) both' }}>
        <span style={{ position: 'relative', display: 'inline-flex', flexShrink: 0, animation: 'av4ImgFloat 5.5s ease-in-out infinite' }}>
          <span aria-hidden="true" style={{ position: 'absolute', inset: -12, borderRadius: '50%', background: `radial-gradient(circle, ${ACCENT}38, transparent 70%)`, filter: 'blur(7px)', animation: 'av4ImgHalo 3.4s ease-in-out infinite' }} />
          <span style={{ position: 'relative', display: 'inline-flex' }}>
            <AuroraMascot module="image" size={46} />
          </span>
        </span>
        <div>
          <h1 className="av4img-gradsoft" style={{ margin: 0, fontSize: 23, fontWeight: 800, letterSpacing: '-0.02em', filter: `drop-shadow(0 0 16px ${ACCENT}38)` }}>Image</h1>
          <TechLabel style={{ marginTop: 3 }}>flux · kontext · comfyui</TechLabel>
        </div>
        <span style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            ...monoTag,
            color: I.editEngine === 'kontext' ? '#6EE7B7' : '#FBBF24',
            borderColor: I.editEngine === 'kontext' ? 'rgba(110,231,183,.35)' : 'rgba(251,191,36,.3)',
          }}
            title={I.editEngine === 'kontext'
              ? 'Moteur d\'édition FLUX.1 Kontext détecté : les retouches modifient réellement l\'image'
              : 'UNET Kontext absent : l\'édition retombe sur img2img, approximatif'}>
            {I.editEngine === 'kontext' ? 'kontext · édition réelle' : 'img2img · approximatif'}
          </span>
          <span style={monoTag}>{dim.w}×{dim.h} · 28 étapes</span>
          <span style={monoTag}>seed {I.seed || 'aléatoire'}</span>
          {I.imageStreak.current > 0 && (
            <span style={{ ...monoTag, color: ACCENT, borderColor: `${ACCENT}55` }}
              title={`Série créative : ${I.imageStreak.current} jour${I.imageStreak.current > 1 ? 's' : ''} d'affilée · record ${I.imageStreak.longest} j`}>
              série {I.imageStreak.current}j
            </span>
          )}
          {I.generating && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, ...monoTag, color: ACCENT, borderColor: `${ACCENT}55` }}>
              <span style={{
                width: 7, height: 7, borderRadius: 999, background: ACCENT,
                boxShadow: `0 0 10px ${ACCENT}`, animation: 'av4ImgPulse 1.2s ease-in-out infinite',
              }} />
              rendu
            </span>
          )}
        </div>
      </div>

      <div aria-hidden="true" className="av4img-bar" style={{ position: 'relative', height: 2, borderRadius: 999, marginBottom: 16, background: `linear-gradient(90deg, ${ACCENT}D9, ${ACCENT}33 42%, rgba(255,255,255,.06) 72%, transparent)`, animation: 'av4ImgRise .45s cubic-bezier(.22,1,.36,1) both' }} />

      {I.resumeBanner && (
        <div style={{
          ...glass, position: 'relative', borderColor: 'rgba(251,191,36,.35)', padding: '12px 16px', marginBottom: 14,
          display: 'flex', alignItems: 'center', gap: 10, animation: 'av4ImgRise .4s cubic-bezier(.22,1,.36,1) both',
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 999, background: '#FBBF24', boxShadow: '0 0 12px #FBBF24', animation: 'av4ImgPulse 1.4s ease-in-out infinite', flexShrink: 0 }} />
          <div style={{ fontSize: 12, lineHeight: 1.5 }}>
            <span style={{ fontWeight: 700, color: '#FDE68A' }}>Reprise d'un rendu en cours.</span>{' '}
            <span style={{ color: '#8B93A7' }}>
              Le PC termine une image démarrée il y a {I.resumeBanner.minutes} min
              {I.resumeBanner.text ? ` (« ${I.resumeBanner.text.slice(0, 70)}${I.resumeBanner.text.length > 70 ? '…' : ''} »)` : ''}.
            </span>
          </div>
        </div>
      )}

      {I.error && (
        <div style={{
          ...glass, position: 'relative', borderColor: 'rgba(248,113,113,.4)', padding: '12px 16px', marginBottom: 14,
          display: 'flex', alignItems: 'flex-start', gap: 10, color: '#FCA5A5', fontSize: 12, lineHeight: 1.5,
        }}>
          <span style={{ flexShrink: 0, marginTop: 1 }}><Icon name="close" /></span>
          <span style={{ flex: 1 }}>{I.error}</span>
        </div>
      )}

      {I.notice && (
        <div style={{
          ...glass, position: 'relative', borderColor: `${ACCENT}44`, padding: '12px 16px', marginBottom: 14,
          display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 12, lineHeight: 1.5, color: '#E6EAF5',
        }}>
          <span style={{ color: ACCENT, flexShrink: 0, marginTop: 1 }}><Icon name="sparkle" /></span>
          <span style={{ flex: 1 }}>{I.notice}</span>
          <button type="button" onClick={() => I.setNotice(null)} title="Fermer le conseil"
            style={{ background: 'transparent', border: 'none', color: '#8B93A7', cursor: 'pointer', padding: 2 }}>
            <Icon name="close" size={12} />
          </button>
        </div>
      )}

      <div className="av4img-grid" style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'minmax(330px,400px) minmax(0,1fr)', gap: 18, alignItems: 'start' }}>

        <div className="av4img-panel" style={{ ...glass, padding: 18, display: 'flex', flexDirection: 'column', gap: 13, animation: 'av4ImgRise .45s cubic-bezier(.22,1,.36,1) backwards' }}>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <TechLabel>session</TechLabel>
              <div style={{ display: 'flex', gap: 6 }}>
                <GhostBtn onClick={createNewSession} title="Ouvrir une nouvelle conversation image" style={{ padding: '4px 9px', fontSize: 11 }}>
                  <Icon name="plus" size={11} /> Nouvelle
                </GhostBtn>
                <GhostBtn onClick={() => setSessionListOpen((v) => !v)} title="Reprendre une session passée" style={{ padding: '4px 9px', fontSize: 11 }}>
                  {imageSessions.length}
                  <span style={{ display: 'inline-flex', transform: sessionListOpen ? 'rotate(180deg)' : 'none', transition: 'transform .25s' }}>
                    <Icon name="chevron" size={11} />
                  </span>
                </GhostBtn>
              </div>
            </div>
            <div style={{ fontSize: 12, color: '#E6EAF5', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
              title={I.activeImageSession.title}>
              {I.activeImageSession.title}
              <span style={{ color: '#5A6377', marginLeft: 8, fontSize: 11 }}>{I.activeImageSession.messages.length} msg</span>
            </div>
            {sessionListOpen && (
              <div style={{
                marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4,
                maxHeight: 180, overflowY: 'auto', paddingRight: 2,
              }}>
                {imageSessions.map((s, sIdx) => (
                  <div key={s.id} className="av4img-row" style={{
                    display: 'grid',
                    gridTemplateColumns: renamingId === s.id ? '1fr 22px' : '1fr 22px 22px',
                    gap: 4, alignItems: 'center',
                    padding: '5px 8px', borderRadius: 10,
                    border: s.id === I.activeImageSession.id ? `1px solid ${ACCENT}66` : '1px solid rgba(255,255,255,.07)',
                    background: s.id === I.activeImageSession.id ? `${ACCENT}14` : 'rgba(255,255,255,.02)',
                    animation: 'av4ImgRise .3s cubic-bezier(.22,1,.36,1) backwards',
                    animationDelay: `${Math.min(sIdx, 10) * 30}ms`,
                  }}>
                    {renamingId === s.id ? (
                      <>
                        <input
                          className="av4img-input"
                          autoFocus
                          value={renameDraft}
                          onChange={(e) => setRenameDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') confirmRename()
                            if (e.key === 'Escape') setRenamingId(null)
                          }}
                          style={{ ...fieldStyle, padding: '3px 8px', fontSize: 11, borderRadius: 8 }}
                        />
                        <button type="button" onClick={confirmRename} title="Valider le nouveau titre"
                          style={{ background: 'transparent', border: 'none', color: '#6EE7B7', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                          <Icon name="check" size={12} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button type="button" onClick={() => switchToSession(s.id)}
                          title={`Reprendre « ${s.title} » — la galerie de cette session est restaurée`}
                          style={{
                            background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
                            textAlign: 'left', color: '#E6EAF5', fontSize: 11, fontFamily: 'inherit',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}>
                          {s.title}
                          <span style={{ color: '#5A6377', marginLeft: 6 }}>{new Date(s.updatedAt).toLocaleDateString('fr-FR')}</span>
                        </button>
                        <button type="button" onClick={() => startRename(s.id, s.title)} title="Renommer cette session"
                          style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                          <Icon name="pencil" size={12} />
                        </button>
                        <button type="button" onClick={() => removeSession(s.id)} title="Supprimer cette session"
                          style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                          <Icon name="trash" size={12} />
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
            {I.recentImageMessages.length > 0 && (
              <div style={{
                marginTop: 10, padding: '8px 10px', borderRadius: 12,
                border: '1px solid rgba(255,255,255,.07)', background: 'rgba(10,15,30,.4)',
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <TechLabel style={{ fontSize: 9 }}>continuité active</TechLabel>
                {I.recentImageMessages.slice(-4).map((m) => (
                  <div key={`${m.timestamp}-${m.role}`} style={{ display: 'grid', gridTemplateColumns: '46px 1fr', gap: 6, alignItems: 'baseline' }}>
                    <span style={{
                      fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10,
                      color: m.role === 'user' ? ACCENT : '#6EE7B7',
                    }}>{m.role === 'user' ? 'toi' : 'aurora'}</span>
                    <span style={{ fontSize: 11, color: '#8B93A7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {compactMessage(m.content)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Divider />

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <TechLabel>prompt</TechLabel>
              <VoicePushToTalk
                onTranscript={(text) => I.setPrompt((I.prompt ? I.prompt + ' ' : '') + text)}
                label="Dicter le prompt image"
                disabled={I.generating}
                variant="ghost"
                size={26}
              />
            </div>
            <textarea
              className="av4img-input"
              value={I.prompt}
              onChange={(e) => I.setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (!I.generating && (e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault()
                  void I.queuePrompt()
                }
              }}
              disabled={I.generating}
              placeholder={I.who === 'natsu'
                ? 'Ex : vélo gravel orange, atelier, étincelles, ciel orageux…'
                : 'Ex : portrait stellaire, nuit étoilée, porte dorée…'}
              rows={3}
              style={{ ...fieldStyle, resize: 'vertical', lineHeight: 1.55 }}
            />
            {(I.previewIntent.removals.length > 0 || I.previewIntent.isEditIntent || I.effectiveDenoise !== null || I.styleOverrideReason) && (
              <div style={{ marginTop: 7, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {I.previewIntent.removals.map((r, i) => (
                  <IntentPill key={`${r}-${i}`} bg="rgba(248,113,113,.14)" fg="#F87171" title="Élément détecté à retirer">− {r}</IntentPill>
                ))}
                {I.previewIntent.isEditIntent && (
                  <IntentPill bg={`${ACCENT}22`} fg={ACCENT}>{I.previewIntent.editContract.label}</IntentPill>
                )}
                {I.previewIntent.isEditIntent && (
                  <IntentPill
                    bg={I.editEngine === 'kontext' ? 'rgba(110,231,183,.14)' : 'rgba(251,191,36,.14)'}
                    fg={I.editEngine === 'kontext' ? '#6EE7B7' : '#FBBF24'}>
                    {I.editEngine === 'kontext' ? 'kontext · édition réelle' : 'img2img · approximatif'}
                  </IntentPill>
                )}
                {I.effectiveDenoise !== null && I.editEngine !== 'kontext' && (
                  <IntentPill bg="rgba(255,255,255,.06)" fg="#8B93A7">denoise {I.effectiveDenoise.toFixed(2)}</IntentPill>
                )}
                {I.styleOverrideReason && (
                  <IntentPill bg="rgba(96,165,250,.14)" fg="#60A5FA" title={I.styleOverrideReason}>style photo préservé</IntentPill>
                )}
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <Chip active={I.showNeg} onClick={() => I.setShowNeg(!I.showNeg)}
                title="Prompt négatif : ce que l'image ne doit PAS contenir">
                prompt négatif{I.negPrompt.trim() ? ' ·' : ''}
              </Chip>
            </div>
            {I.showNeg && (
              <textarea
                className="av4img-input"
                value={I.negPrompt}
                onChange={(e) => I.setNegPrompt(e.target.value)}
                disabled={I.generating}
                placeholder="Ex : blurry, low quality, watermark, extra fingers, text"
                rows={2}
                style={{ ...fieldStyle, marginTop: 8, fontSize: 12, resize: 'vertical', borderStyle: 'dashed', color: '#8B93A7' }}
              />
            )}
          </div>

          <Divider />

          <div>
            <TechLabel style={{ marginBottom: 8 }}>styles flux · <span className="av4img-grad" style={{ fontSize: 12, fontWeight: 800 }}>{I.styles.length}</span></TechLabel>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {I.styles.map((s) => (
                <Chip key={s.id} active={I.style === s.id} disabled={I.generating}
                  onClick={() => I.setStyle(s.id)} title={`Style FLUX : ${s.label}`}>
                  {s.label}
                </Chip>
              ))}
            </div>
          </div>

          <Divider />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <TechLabel>réglages</TechLabel>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ ...mono, width: 52, flexShrink: 0 }}>seed</span>
              <input
                className="av4img-input"
                type="text" inputMode="numeric" pattern="[0-9]*"
                value={I.seed}
                onChange={(e) => I.setSeed(e.target.value.replace(/[^0-9]/g, '').slice(0, 10))}
                placeholder="aléatoire"
                disabled={I.generating}
                style={{ ...fieldStyle, padding: '6px 10px', fontSize: 12, fontFamily: "'Cascadia Code',Consolas,monospace", letterSpacing: '.04em' }}
              />
              {I.seed && !I.generating && (
                <button type="button" onClick={() => I.setSeed('')} title="Repasser en seed aléatoire"
                  style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                  <Icon name="close" size={12} />
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ ...mono, width: 52, flexShrink: 0 }}>lot</span>
              <div style={{ display: 'flex', gap: 6, flex: 1 }}>
                {([1, 2, 3, 4] as const).map((n) => (
                  <Chip key={n} active={I.batch === n} disabled={I.generating}
                    onClick={() => I.setBatch(n)} title={`Générer ${n} image${n > 1 ? 's' : ''} d'affilée`}>
                    ×{n}
                  </Chip>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ ...mono, width: 52, flexShrink: 0 }}>format</span>
              <div style={{ display: 'flex', gap: 6, flex: 1 }}>
                {(['square', 'portrait', 'landscape'] as DimensionId[]).map((d) => (
                  <Chip key={d} active={I.dimensions === d} disabled={I.generating}
                    onClick={() => I.setDimensions(d)} title={`${DIMENSIONS[d].w}×${DIMENSIONS[d].h}`}>
                    {DIMENSIONS[d].label}
                  </Chip>
                ))}
              </div>
            </div>
          </div>

          <Divider />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <TechLabel>références</TechLabel>
            {I.refPreview ? (
              <div style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: 8,
                border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, background: 'rgba(10,15,30,.4)',
              }}>
                <img src={I.refPreview} alt="Référence d'édition" style={{ width: 42, height: 42, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ ...mono, fontSize: 9, letterSpacing: '.12em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                    title={I.refFilename ?? undefined}>
                    référence · denoise {I.refDenoise.toFixed(2)}
                  </div>
                  <input className="av4img-range" type="range" min={0.3} max={0.95} step={0.05}
                    value={I.refDenoise} onChange={(e) => I.setRefDenoise(Number(e.target.value))}
                    disabled={I.generating} style={{ width: '100%', marginTop: 4 }} />
                </div>
                <button type="button" onClick={I.clearReference} disabled={I.generating} title="Retirer la référence"
                  style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                  <Icon name="close" size={13} />
                </button>
              </div>
            ) : (
              <label style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '12px 10px', fontSize: 11, color: '#8B93A7',
                border: '1px dashed rgba(255,255,255,.14)', borderRadius: 12,
                background: 'rgba(255,255,255,.02)', cursor: I.refUploading ? 'wait' : 'pointer',
                transition: 'all .25s',
              }}>
                <input type="file" accept="image/*" onChange={I.onUploadReference}
                  disabled={I.generating || I.refUploading} style={{ display: 'none' }} />
                <Icon name="image" />
                {I.refUploading ? 'Envoi de la référence…' : 'Référence / édition — cliquer ou déposer'}
              </label>
            )}
            {I.refPreview2 ? (
              <div style={{
                display: 'flex', gap: 10, alignItems: 'center', padding: 8,
                border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, background: 'rgba(10,15,30,.4)',
              }}>
                <img src={I.refPreview2} alt="Source à injecter" style={{ width: 42, height: 42, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0, fontSize: 10, color: '#8B93A7', lineHeight: 1.45 }}
                  title={I.refFilename2 ?? undefined}>
                  Source d'extraction : l'élément demandé est extrait d'ici puis injecté dans la référence
                </div>
                <button type="button" onClick={I.clearSource} disabled={I.generating} title="Retirer la source"
                  style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                  <Icon name="close" size={13} />
                </button>
              </div>
            ) : (
              <label onDrop={onSourceDrop} onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
                title={sourceReady
                  ? 'Image source : un élément en sera extrait et injecté dans la référence'
                  : 'Ajoute d\'abord une référence ou génère une image de base'}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  padding: '10px 10px', fontSize: 11, color: '#8B93A7',
                  border: '1px dashed rgba(255,255,255,.12)', borderRadius: 12,
                  background: 'rgba(255,255,255,.015)',
                  cursor: sourceReady ? (I.refUploading2 ? 'wait' : 'pointer') : 'not-allowed',
                  opacity: sourceReady ? 1 : 0.45,
                  transition: 'all .25s',
                }}>
                <input type="file" accept="image/*" onChange={I.onUploadSource}
                  disabled={I.generating || I.refUploading2 || !sourceReady} style={{ display: 'none' }} />
                <Icon name="plus" size={12} />
                {I.refUploading2 ? 'Envoi de la source…' : 'Image source · extraire et injecter'}
              </label>
            )}
          </div>

          <Divider />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {I.generating ? (
              <button type="button" className="av4img-primary" onClick={I.onStop}
                style={{
                  width: '100%', padding: '11px 18px', borderRadius: 12, border: '1px solid rgba(248,113,113,.5)',
                  background: 'rgba(248,113,113,.14)', color: '#FCA5A5', fontWeight: 750, fontSize: 13,
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  transition: 'all .25s', fontFamily: 'inherit',
                }}>
                <Icon name="stop" /> Arrêter le rendu
              </button>
            ) : (
              <button type="button" className="av4img-primary" onClick={() => void I.queuePrompt()}
                disabled={!I.prompt.trim()}
                style={{
                  width: '100%', padding: '12px 18px', borderRadius: 12, border: 'none',
                  background: `linear-gradient(125deg, #FBCFE8, ${ACCENT} 55%, #EC4899)`,
                  color: '#0A0F1E', fontWeight: 750, fontSize: 13, letterSpacing: '.01em',
                  boxShadow: `0 8px 28px ${ACCENT}66, inset 0 1px 0 rgba(255,255,255,.4)`,
                  cursor: I.prompt.trim() ? 'pointer' : 'not-allowed',
                  opacity: I.prompt.trim() ? 1 : 0.55,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  transition: 'all .25s', fontFamily: 'inherit',
                }}>
                <Icon name="sparkle" /> Générer · Ctrl+Entrée
              </button>
            )}
            {!I.generating && (
              <GhostBtn onClick={launchSurprise}
                title="Pioche un style et un prompt au hasard puis lance le rendu immédiatement"
                style={{ width: '100%', justifyContent: 'center', color: ACCENT, borderColor: `${ACCENT}44` }}>
                <Icon name="bolt" size={12} /> Surprise · rendu immédiat
              </GhostBtn>
            )}
            <FavoriteButton
              prompt={I.prompt}
              module="image"
              parameters={{ style: I.style }}
              tags={['image', I.style]}
              disabled={I.generating}
            />
            {I.progress && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
                <span style={{
                  width: 7, height: 7, borderRadius: 999, background: ACCENT, flexShrink: 0,
                  boxShadow: `0 0 10px ${ACCENT}`,
                  animation: I.generating ? 'av4ImgPulse 1.2s ease-in-out infinite' : 'none',
                }} />
                <span style={{ fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 11, color: '#8B93A7' }}>
                  {I.progress}
                </span>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
          <div className={I.generating ? 'av4img-panel av4img-live' : 'av4img-panel'} style={{ ...glass, padding: 18, display: 'flex', flexDirection: 'column', gap: 12, animation: 'av4ImgRise .5s cubic-bezier(.22,1,.36,1) backwards', animationDelay: '60ms' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <TechLabel>galerie · <span className="av4img-grad" style={{ fontSize: 12, fontWeight: 800 }}>{I.images.length}</span>/24</TechLabel>
              <span style={{ fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10, color: '#5A6377' }}>
                {I.generating ? I.progress || 'rendu en cours' : `${dim.w}×${dim.h}`}
              </span>
            </div>
            {I.generating && (
              <div aria-hidden="true" style={{ position: 'relative', height: 2, borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,.06)' }}>
                <span style={{ position: 'absolute', top: 0, bottom: 0, width: '38%', borderRadius: 999, background: `linear-gradient(90deg, transparent, ${ACCENT}, #FFFFFF, ${ACCENT}, transparent)`, boxShadow: `0 0 12px ${ACCENT}`, animation: 'av4ImgScan 1.5s cubic-bezier(.4,0,.2,1) infinite' }} />
              </div>
            )}

            {I.current ? (
              <>
                <div key={I.current.id} className="av4img-hero" style={{
                  position: 'relative', borderRadius: 14, overflow: 'hidden',
                  border: '1px solid rgba(255,255,255,.08)', background: '#05070F',
                  boxShadow: `0 24px 56px -24px rgba(0,0,0,.75), 0 0 44px ${ACCENT}14`,
                }}>
                  <img src={I.current.url} alt={I.current.prompt}
                    style={{ width: '100%', maxHeight: 'min(58vh, 640px)', objectFit: 'contain', display: 'block' }} />
                  <div aria-hidden="true" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 88, background: 'linear-gradient(180deg, transparent, rgba(5,7,15,.58))', pointerEvents: 'none' }} />
                  <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {I.current.seed !== null && I.current.seed !== undefined && (
                      <MetaBadge color={ACCENT} onClick={() => void copyCurrentSeed()}
                        title="Cliquer pour copier le seed">
                        seed {I.current.seed}
                      </MetaBadge>
                    )}
                    <MetaBadge color="#6EE7B7"
                      title={I.current.requestedStyle
                        ? `Style demandé : ${I.current.requestedStyle} → appliqué : ${I.current.style}${I.current.styleOverrideReason ? ` (${I.current.styleOverrideReason})` : ''}`
                        : `Style FLUX : ${I.current.style}`}>
                      {I.current.style}{I.current.requestedStyle ? ' *' : ''}
                    </MetaBadge>
                    <MetaBadge title={new Date(I.current.timestamp).toLocaleString('fr-FR')}>
                      {new Date(I.current.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                    </MetaBadge>
                  </div>
                  {!I.generating && (
                    <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <OverlayBtn onClick={I.downloadCurrent} title="Télécharger en PNG">
                        <Icon name="download" size={12} /> PNG
                      </OverlayBtn>
                      <OverlayBtn onClick={() => I.setInpaintOpen(true)} title="Retouche par masque (inpainting)">
                        <Icon name="brush" size={12} /> Retouche
                      </OverlayBtn>
                      <OverlayBtn disabled={I.upscaling} onClick={() => void I.upscaleCurrent(2)} title="Agrandir 2×">
                        <Icon name="expand" size={12} /> 2×
                      </OverlayBtn>
                      <OverlayBtn disabled={I.upscaling} onClick={() => void I.upscaleCurrent(4)} title="Agrandir 4×">
                        4×
                      </OverlayBtn>
                      <OverlayBtn onClick={() => { if (I.current) void imageAsReference(I.current) }} title="Utiliser cette image comme référence d'édition">
                        <Icon name="target" size={12} /> Réf
                      </OverlayBtn>
                    </div>
                  )}
                  {I.upscaling && (
                    <div style={{
                      position: 'absolute', top: 10, left: 10,
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '4px 10px', borderRadius: 999,
                      background: 'rgba(5,8,16,.74)', border: `1px solid ${ACCENT}55`,
                      fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10, color: ACCENT,
                      backdropFilter: 'blur(4px)',
                    }}>
                      <span style={{ width: 6, height: 6, borderRadius: 999, background: ACCENT, animation: 'av4ImgPulse 1s ease-in-out infinite' }} />
                      agrandissement…
                    </div>
                  )}
                </div>

                <div style={{ fontSize: 11, color: '#5A6377', lineHeight: 1.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                  title={I.current.prompt}>
                  {I.current.prompt}
                </div>

                {!I.generating && (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <GhostBtn onClick={() => I.setPrompt(I.current ? I.current.prompt : '')} title="Recharger ce prompt dans le composeur">
                      <Icon name="redo" size={11} /> Reprendre le prompt
                    </GhostBtn>
                    <GhostBtn onClick={() => { if (I.current) void copyText(I.current.prompt) }} title="Copier le prompt dans le presse-papier">
                      <Icon name="copy" size={11} /> Copier
                    </GhostBtn>
                    {I.current.seed !== null && I.current.seed !== undefined && (
                      <>
                        <GhostBtn onClick={() => replaySeed(0)} title={`Recharge prompt + style + seed ${I.current.seed} pour reproduire à l'identique`}>
                          Seed exact {I.current.seed}
                        </GhostBtn>
                        <GhostBtn onClick={() => replaySeed(1)} title="Même prompt et style, seed +1 : variation proche">
                          Variation +1
                        </GhostBtn>
                      </>
                    )}
                  </div>
                )}

                {I.images.length > 1 && (
                  <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                    {I.images.map((img, tIdx) => (
                      <button key={img.id} type="button" className="av4img-thumb"
                        onClick={() => I.setCurrent(img)}
                        onContextMenu={(e) => {
                          e.preventDefault()
                          setThumbMenu({
                            id: img.id,
                            x: Math.min(e.clientX, window.innerWidth - 240),
                            y: Math.min(e.clientY, window.innerHeight - 320),
                          })
                        }}
                        title={`${img.prompt}${img.seed !== null && img.seed !== undefined ? `\nseed ${img.seed}` : ''}\nstyle ${img.style}\nClic droit : actions`}
                        style={{
                          position: 'relative',
                          flexShrink: 0, width: 62, height: 62, padding: 0, borderRadius: 12, overflow: 'hidden',
                          cursor: 'pointer', background: 'rgba(10,15,30,.6)',
                          border: img.id === I.current?.id ? `2px solid ${ACCENT}` : '1px solid rgba(255,255,255,.12)',
                          boxShadow: img.id === I.current?.id ? `0 0 14px ${ACCENT}44` : 'none',
                          transition: 'all .25s',
                          animation: 'av4ImgRise .35s cubic-bezier(.22,1,.36,1) backwards',
                          animationDelay: `${Math.min(tIdx, 12) * 30}ms`,
                        }}>
                        <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                        <span style={{
                          position: 'absolute', top: 3, left: 3, padding: '1px 5px',
                          borderRadius: 5, background: 'rgba(5,8,16,.78)', color: ACCENT,
                          fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 8,
                          letterSpacing: '.06em', backdropFilter: 'blur(2px)',
                        }}>
                          {img.style.slice(0, 3)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ padding: '46px 20px 52px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, animation: 'av4ImgRise .5s cubic-bezier(.22,1,.36,1) both' }}>
                <div style={{ position: 'relative', display: 'inline-flex', animation: 'av4ImgFloat 4.6s ease-in-out infinite' }}>
                  <span aria-hidden="true" style={{ position: 'absolute', inset: -22, borderRadius: '50%', background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`, filter: 'blur(10px)', animation: 'av4ImgHalo 3.6s ease-in-out infinite' }} />
                  <span aria-hidden="true" className="av4img-orbit" style={{ position: 'absolute', inset: -26 }}>
                    <span style={{ position: 'absolute', top: 0, left: '50%', width: 5, height: 5, marginLeft: -2, borderRadius: 999, background: ACCENT, boxShadow: `0 0 10px ${ACCENT}` }} />
                  </span>
                  <span aria-hidden="true" className="av4img-orbit-rev" style={{ position: 'absolute', inset: -12 }}>
                    <span style={{ position: 'absolute', bottom: 0, left: '50%', width: 3, height: 3, borderRadius: 999, background: '#FFFFFF', boxShadow: '0 0 7px rgba(255,255,255,.9)', opacity: .85 }} />
                  </span>
                  <span style={{ position: 'relative', display: 'inline-flex' }}>
                    <AuroraMascot module="image" size={90} />
                  </span>
                </div>
                <div className="av4img-gradsoft" style={{ fontSize: 19, fontWeight: 800, letterSpacing: '-0.02em' }}>
                  Décris ta scène, choisis un style, lance le rendu.
                </div>
                <div style={{ fontSize: 12, color: '#8B93A7', maxWidth: 420, lineHeight: 1.6 }}>
                  {I.generating
                    ? (I.progress || 'Rendu en cours…')
                    : 'La galerie de la session s\'affichera ici : sélection, retouche, agrandissement et téléchargement.'}
                </div>
                {!I.generating && (
                  <GhostBtn onClick={launchSurprise}
                    title="Pioche un style et un prompt au hasard puis lance le rendu immédiatement"
                    style={{ color: ACCENT, borderColor: `${ACCENT}55`, padding: '8px 16px' }}>
                    <Icon name="bolt" size={12} /> Surprends-moi, Aurora
                  </GhostBtn>
                )}
                <div style={{
                  padding: '7px 14px', borderRadius: 999, fontSize: 11, lineHeight: 1.55,
                  border: `1px solid ${ACCENT}33`, background: `${ACCENT}0F`, color: '#8B93A7', maxWidth: 460,
                }}>
                  {getDailyTip('image')}
                </div>
              </div>
            )}
          </div>

          {I.history.length > 0 && (
            <div className="av4img-panel" style={{ ...glass, padding: 16, animation: 'av4ImgRise .55s cubic-bezier(.22,1,.36,1) backwards', animationDelay: '120ms' }}>
              <TechLabel style={{ marginBottom: 8 }}>historique des prompts · <span className="av4img-grad" style={{ fontSize: 12, fontWeight: 800 }}>{I.history.length}</span></TechLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 190, overflowY: 'auto' }}>
                {I.history.map((h, hIdx) => (
                  <div key={h.prompt} className="av4img-row" style={{
                    display: 'grid', gridTemplateColumns: '1fr 26px', gap: 6, alignItems: 'center',
                    padding: '5px 9px', borderRadius: 10,
                    border: '1px solid rgba(255,255,255,.06)', background: 'rgba(255,255,255,.02)',
                    animation: 'av4ImgRise .3s cubic-bezier(.22,1,.36,1) backwards',
                    animationDelay: `${Math.min(hIdx, 12) * 25}ms`,
                  }}>
                    <button type="button" onClick={() => I.recallPrompt(h)}
                      title={`${h.prompt}${h.meta?.style ? ` · ${h.meta.style}` : ''}\nCliquer : rouvrir la conversation et reprendre ce prompt`}
                      style={{
                        background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
                        textAlign: 'left', color: '#E6EAF5', fontSize: 11, fontFamily: 'inherit',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                      {h.prompt}
                    </button>
                    <button type="button" onClick={() => I.removeHistory(h.prompt)} title="Retirer de l'historique"
                      style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}>
                      <Icon name="trash" size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {thumbMenu && (() => {
        const img = I.images.find((m) => m.id === thumbMenu.id)
        if (!img) return null
        const close = () => setThumbMenu(null)
        const item: React.CSSProperties = {
          background: 'transparent', border: 'none', color: '#C7CDDC', cursor: 'pointer',
          padding: '7px 10px', borderRadius: 9, textAlign: 'left', fontSize: 11,
          fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', transition: 'all .2s',
        }
        return (
          <div data-thumb-menu style={{
            ...glass,
            position: 'fixed', top: thumbMenu.y, left: thumbMenu.x, zIndex: 90,
            background: 'rgba(8,12,24,.94)', borderRadius: 13, padding: 5,
            boxShadow: `0 14px 44px rgba(0,0,0,.55), 0 0 24px ${ACCENT}14`,
            display: 'flex', flexDirection: 'column', gap: 1, minWidth: 216,
            animation: 'av4ImgRise .18s cubic-bezier(.22,1,.36,1) both',
          }}>
            <button type="button" className="av4img-menu-item" style={item}
              onClick={() => { I.setCurrent(img); close() }} title="Afficher cette image en grand">
              <Icon name="image" size={11} /> Voir en grand
            </button>
            <button type="button" className="av4img-menu-item" style={item}
              onClick={() => { I.setPrompt(img.prompt); close() }} title="Recharger ce prompt dans le composeur">
              <Icon name="redo" size={11} /> Reprendre le prompt
            </button>
            <button type="button" className="av4img-menu-item" style={item}
              onClick={() => { void copyText(img.prompt); close() }} title="Copier le prompt dans le presse-papier">
              <Icon name="copy" size={11} /> Copier le prompt
            </button>
            <button type="button" className="av4img-menu-item" style={item}
              onClick={() => { downloadImage(img); close() }} title="Télécharger cette image en PNG">
              <Icon name="download" size={11} /> Télécharger en PNG
            </button>
            <button type="button" className="av4img-menu-item"
              disabled={I.generating || I.refUploading}
              style={{ ...item, opacity: I.generating || I.refUploading ? 0.45 : 1 }}
              onClick={() => { void imageAsReference(img); close() }}
              title="Cette image devient la référence d'édition de la prochaine génération">
              <Icon name="target" size={11} /> Utiliser comme référence
            </button>
            {img.seed !== null && img.seed !== undefined && (
              <>
                <button type="button" className="av4img-menu-item" style={item}
                  onClick={() => { recallWithSeed(img, 0); close() }}
                  title={`Recharge prompt + style + seed ${img.seed} pour reproduire à l'identique`}>
                  <Icon name="sparkle" size={11} /> Seed exact {img.seed}
                </button>
                <button type="button" className="av4img-menu-item" style={item}
                  onClick={() => { recallWithSeed(img, 1); close() }}
                  title="Même prompt et style, seed +1 : variation proche">
                  <Icon name="bolt" size={11} /> Variation +1
                </button>
              </>
            )}
          </div>
        )
      })()}

      {I.inpaintOpen && I.current && (
        <Suspense fallback={null}>
          <InpaintingPanel
            imageSrc={I.current.url}
            onClose={() => I.setInpaintOpen(false)}
            onApply={(newUrl: string) => void I.applyInpaint(newUrl)}
          />
        </Suspense>
      )}
    </div>
  )
}
