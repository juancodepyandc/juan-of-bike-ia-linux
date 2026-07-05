import { lazy, Suspense, useState, type CSSProperties, type ReactNode } from 'react'
import AuroraMascot from '../components/generationFx/mascots'
import FavoriteButton from '../components/FavoriteButton'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { useFileDrop } from '../hooks/useFileDrop'
import { useModuleStreak } from '../hooks/useModuleStreak'
import { useVideoViewLogic, type VideoAspect, type VideoLength } from '../hooks/useVideoViewLogic'
import { analyzeVideoPrompt } from '../services/videoPromptComposer'
import { getDailyTip } from '../utils/dailyTip'
import { RANDOM_VIDEO_STYLES } from '../utils/randomCreativePrompts'

const QuickClipView = lazy(() => import('./VideoView'))

const ACCENT = '#F59E0B'
const MONO = "'Cascadia Code',Consolas,monospace"
const FONT = "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif"

const ASPECTS: VideoAspect[] = ['16:9', '9:16', '1:1', '4:3']

const LENGTHS: { value: VideoLength; label: string }[] = [
  { value: 'short', label: 'Court · 15 s' },
  { value: 'medium', label: 'Standard · 30 s' },
  { value: 'long', label: 'Long · 60 s' },
]

const STATUS_FR: Record<string, string> = {
  queued: 'En file d’attente',
  running: 'Rendu en cours',
  done: 'Terminé',
  unknown: 'État inconnu',
}

const STATUS_DOT: Record<string, string> = {
  queued: '#8B93A7',
  running: ACCENT,
  done: '#34D399',
  unknown: '#F87171',
}

const GRADE_COLOR: Record<string, string> = {
  A: '#34D399',
  B: '#A3E635',
  C: '#FBBF24',
  D: '#F87171',
}

const GRADE_LABEL: Record<string, string> = {
  A: 'excellent, prêt à diffuser',
  B: 'correct, défauts mineurs',
  C: 'à retravailler, au moins un plan faible',
  D: 'inutilisable, régénère le storyboard',
}

const IC = {
  play: 'M7 4.8 19 12 7 19.2z',
  stop: 'M7.5 7.5h9v9h-9z',
  x: 'M6 6 18 18|M18 6 6 18',
  shuffle: 'M16 3h5v5|M4 20 21 3|M21 16v5h-5|M15 15l6 6|M4 4l5 5',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z|M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  pulse: 'M22 12h-4l-3 9L9 3l-3 9H2',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4|M7 10l5 5 5-5|M12 15V3',
  reset: 'M3 12a9 9 0 1 0 2.6-6.4L3 8|M3 3v5h5',
  warn: 'M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z|M12 9v4|M12 17h.01',
  clap: 'M3.2 10.4h17.6v8.4a2 2 0 0 1-2 2H5.2a2 2 0 0 1-2-2z|M3.2 10.4 2.4 7.2l17-4.4.8 3.2z|M7.4 9.3l1.3-3.9|M12.6 8 13.9 4.1',
  check: 'M20 6 9 17l-5-5',
  camera: 'M22.5 7.5 16 12l6.5 4.5z|M14 5.5H3.5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2H14a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2z',
  flask: 'M10 2v6.5L4.6 17.6a2 2 0 0 0 1.8 2.9h11.2a2 2 0 0 0 1.8-2.9L14 8.5V2|M8.5 2h7|M7 13.5h10',
  zap: 'M13 2 3 14h9l-1 8 10-12h-9z',
  film: 'M4.5 3h15a1.5 1.5 0 0 1 1.5 1.5v15a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19.5v-15A1.5 1.5 0 0 1 4.5 3z|M7.5 3v18|M16.5 3v18|M3 12h18|M3 7.5h4.5|M3 16.5h4.5|M16.5 7.5H21|M16.5 16.5H21',
}

const CSS = `
@keyframes v4vIn{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes v4vSpin{to{transform:rotate(360deg)}}
@keyframes v4vPulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.8)}}
@keyframes v4vSheen{0%{left:-70%;opacity:0}12%{opacity:1}100%{left:140%;opacity:0}}
@keyframes v4vFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes v4vHalo{0%,100%{opacity:.5;transform:scale(1)}50%{opacity:.95;transform:scale(1.12)}}
@keyframes v4vBar{from{background-position:0 0}to{background-position:200% 0}}
@keyframes v4vBand{from{background-position:0 0}to{background-position:-200% 0}}
.v4v-root{isolation:isolate}
.v4v-root ::selection{background:${ACCENT};color:#0A0F1E}
.v4v-root ::-webkit-scrollbar{width:7px;height:7px}
.v4v-root ::-webkit-scrollbar-track{background:transparent}
.v4v-root ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.13);border-radius:999px}
.v4v-root ::-webkit-scrollbar-thumb:hover{background:${ACCENT}66}
.v4v-card{position:relative;border:1px solid rgba(255,255,255,.09);box-shadow:0 18px 44px -26px rgba(0,0,0,.6);animation:v4vIn .55s cubic-bezier(.22,1,.36,1) backwards;transition:transform .35s cubic-bezier(.22,1,.36,1),border-color .35s,box-shadow .35s}
.v4v-card::before{content:'';position:absolute;top:-1px;left:14%;right:14%;height:1px;border-radius:999px;background:linear-gradient(90deg,transparent,${ACCENT}73 35%,rgba(255,255,255,.55) 50%,${ACCENT}73 65%,transparent);opacity:.35;transition:opacity .35s;pointer-events:none}
.v4v-card:hover{transform:translateY(-3px);border-color:${ACCENT}3D;box-shadow:inset 0 0 0 1px ${ACCENT}26,0 32px 70px -30px rgba(0,0,0,.7),0 0 44px -12px ${ACCENT}4D}
.v4v-card:hover::before{opacity:.95}
.v4v-item{animation:v4vIn .4s cubic-bezier(.22,1,.36,1) backwards}
.v4v-mini{border:1px solid rgba(255,255,255,.07);transition:transform .25s cubic-bezier(.22,1,.36,1),border-color .25s,box-shadow .25s}
.v4v-mini:hover{transform:translateY(-3px);border-color:${ACCENT}55;box-shadow:0 18px 38px -18px rgba(0,0,0,.65),0 0 24px -10px ${ACCENT}66}
.v4v-film{position:relative;overflow:hidden}
.v4v-film::before,.v4v-film::after{content:'';position:absolute;left:12px;right:12px;height:4px;border-radius:2px;background-image:repeating-linear-gradient(90deg,rgba(230,234,245,.4) 0 6px,transparent 6px 14px);opacity:.16;pointer-events:none;transition:opacity .25s}
.v4v-film::before{top:5px}
.v4v-film::after{bottom:5px}
.v4v-film:hover::before,.v4v-film:hover::after{opacity:.45}
.v4v-spin{animation:v4vSpin .9s linear infinite}
.v4v-dot{animation:v4vPulse 1.6s ease-in-out infinite}
.v4v-halo{animation:v4vHalo 4.6s ease-in-out infinite}
.v4v-float{animation:v4vFloat 5.6s ease-in-out infinite}
.v4v-bar{background-size:200% 100%!important;animation:v4vBar 2.4s linear infinite}
.v4v-bandlight{background-size:200% 100%!important;animation:v4vBand 5.5s linear infinite}
.v4v-kfimg{display:block;transition:transform .5s cubic-bezier(.22,1,.36,1)}
.v4v-mini:hover .v4v-kfimg{transform:scale(1.06)}
.v4v-pri{position:relative;overflow:hidden;transition:transform .25s,box-shadow .25s,filter .25s}
.v4v-pri::after{content:'';position:absolute;top:-40%;bottom:-40%;left:-70%;width:42%;background:linear-gradient(105deg,transparent,rgba(255,255,255,.55),transparent);transform:skewX(-18deg);opacity:0;pointer-events:none}
.v4v-pri:hover:not(:disabled){transform:translateY(-2px);filter:saturate(1.1) brightness(1.05);box-shadow:0 12px 36px ${ACCENT}66}
.v4v-pri:hover:not(:disabled)::after{animation:v4vSheen .8s ease}
.v4v-pri:disabled{opacity:.45;cursor:not-allowed}
.v4v-gho{transition:all .25s}
.v4v-gho:hover:not(:disabled){border-color:${ACCENT}59;color:#E6EAF5;transform:translateY(-1px);box-shadow:0 8px 22px -12px ${ACCENT}59}
.v4v-gho:disabled{opacity:.45;cursor:not-allowed}
.v4v-chip{transition:all .25s}
.v4v-chip:hover:not(:disabled){transform:translateY(-1px)}
.v4v-in:focus{border-color:${ACCENT}!important;box-shadow:0 0 0 3px ${ACCENT}26,0 0 24px ${ACCENT}33;outline:none}
.v4v-in::placeholder{color:#5A6377}
.v4v-hist{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.06);transition:all .25s}
.v4v-hist:hover{background:rgba(255,255,255,.05);border-color:${ACCENT}3D;transform:translateY(-1px);box-shadow:inset 3px 0 0 -1px ${ACCENT}99}
@media (max-width:1100px){.v4v-grid{grid-template-columns:1fr!important}}
@media (max-width:700px){.v4v-page{padding:16px 14px!important}}
@media (prefers-reduced-motion:reduce){.v4v-card,.v4v-item,.v4v-dot,.v4v-halo,.v4v-float,.v4v-bar,.v4v-bandlight{animation:none!important}.v4v-card,.v4v-mini,.v4v-pri,.v4v-gho,.v4v-chip,.v4v-hist,.v4v-kfimg{transition:none!important}.v4v-card:hover,.v4v-mini:hover,.v4v-pri:hover:not(:disabled),.v4v-gho:hover:not(:disabled),.v4v-chip:hover:not(:disabled),.v4v-hist:hover{transform:none}.v4v-pri:hover:not(:disabled)::after{animation:none}.v4v-mini:hover .v4v-kfimg{transform:none}}
`

const priBtn: CSSProperties = {
  background: `linear-gradient(120deg, #FDE68A, ${ACCENT} 48%, #D97706)`,
  color: '#0A0F1E',
  fontWeight: 750,
  borderRadius: 12,
  boxShadow: `0 6px 24px ${ACCENT}66`,
  border: 'none',
  padding: '11px 18px',
  fontSize: 13,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  fontFamily: 'inherit',
}

const ghoBtn: CSSProperties = {
  border: '1px solid rgba(255,255,255,.14)',
  background: 'rgba(255,255,255,.03)',
  color: '#8B93A7',
  borderRadius: 11,
  padding: '10px 16px',
  fontSize: 12.5,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  fontFamily: 'inherit',
}

const gradText: CSSProperties = {
  background: `linear-gradient(100deg, #FFFFFF, #FDE68A 45%, ${ACCENT})`,
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  color: 'transparent',
}

const sepLine: CSSProperties = {
  height: 1,
  marginBottom: 12,
  background: `linear-gradient(90deg, transparent, ${ACCENT}4D 14%, rgba(255,255,255,.09) 55%, transparent)`,
}

function Ic({ d, size = 15 }: { d: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {d.split('|').map((p, i) => <path key={i} d={p} />)}
    </svg>
  )
}

function Spin({ size = 15 }: { size?: number }) {
  return (
    <svg className="v4v-spin" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-9-9" />
    </svg>
  )
}

function Glass({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div className="v4v-card" style={{
      background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
      borderRadius: 18,
      backdropFilter: 'blur(18px)',
      ...style,
    }}>{children}</div>
  )
}

function TechLabel({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      fontFamily: MONO,
      fontSize: 10,
      letterSpacing: '.2em',
      textTransform: 'uppercase',
      color: '#8B93A7',
      ...style,
    }}>{children}</div>
  )
}

function Chip({ active, onClick, disabled, children }: { active: boolean; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button type="button" className="v4v-chip" onClick={onClick} disabled={disabled} style={{
      fontSize: 11,
      padding: '5px 11px',
      borderRadius: 999,
      border: `1px solid ${active ? ACCENT : 'rgba(255,255,255,.1)'}`,
      background: active ? ACCENT : 'rgba(255,255,255,.03)',
      color: active ? '#0A0F1E' : '#8B93A7',
      fontWeight: active ? 700 : 500,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      fontFamily: 'inherit',
      transition: 'all .25s',
    }}>{children}</button>
  )
}

function Tag({ children, color }: { children: ReactNode; color?: string }) {
  return (
    <span style={{
      fontSize: 11,
      padding: '5px 11px',
      borderRadius: 999,
      border: `1px solid ${color ? `${color}55` : 'rgba(255,255,255,.1)'}`,
      color: color ?? '#8B93A7',
      fontFamily: MONO,
    }}>{children}</span>
  )
}

function keyframeUrl(raw: string): string {
  if (raw.startsWith('http')) return raw
  if (raw.startsWith('/files')) return raw
  return `/files?path=${encodeURIComponent(raw)}`
}

function fmtSec(s: number): string {
  if (!Number.isFinite(s) || s <= 0) return '0 s'
  const m = Math.floor(s / 60)
  const r = Math.round(s % 60)
  return m > 0 ? `${m} min ${String(r).padStart(2, '0')} s` : `${r} s`
}

function scoreColor(s: number): string {
  return s >= 8 ? '#34D399' : s >= 6 ? '#FBBF24' : '#F87171'
}

export default function AuroraV4VideoView() {
  const v = useVideoViewLogic()
  const streak = useModuleStreak('video')
  const [clip, setClip] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const drop = useFileDrop({
    onFiles: async (files) => {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (const f of files) {
        try {
          const text = await readTextFile(f)
          const clamped = text.length > 8000
            ? `${text.slice(0, 8000)}\n[... tronqué à 8 Ko pour le storyboard ...]`
            : text
          sections.push(`--- ${f.name} ---\n${clamped.trim()}`)
        } catch {
          sections.push(`--- ${f.name} ---\n(lecture impossible)`)
        }
      }
      v.setPrompt(`${sections.join('\n\n')}\n\n${v.prompt}`)
    },
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: v.generating,
  })
  const eta = v.jobStatus?.eta
  const pct = eta && eta.total > 0 ? Math.round((eta.done / eta.total) * 100) : 0
  const result = v.jobStatus?.result
  const grade = result?.quality_grade
  const exportable = grade?.exportable !== false
  const renderCharQuality = result?.char_quality ?? null
  const shotQuality = result?.shot_quality ?? []
  const temporalQuality = result?.temporal_quality ?? []
  const audioQuality = result?.audio_quality ?? []
  const integrity = result?.integrity ?? null
  const styleOptions = RANDOM_VIDEO_STYLES.includes(v.style) ? RANDOM_VIDEO_STYLES : [...RANDOM_VIDEO_STYLES, v.style]
  const jobDot = v.jobStatus ? STATUS_DOT[v.jobStatus.status] ?? '#8B93A7' : '#8B93A7'
  const charQuality = v.previewResult?.char_quality ?? null
  const cine = analyzeVideoPrompt(v.prompt)
  const cineHits = [
    cine.shot,
    ...(cine.staticCamera ? ['static camera'] : cine.camera),
    ...cine.lighting,
    cine.style,
    cine.tempo,
  ].filter(Boolean) as string[]
  const dailyTip = getDailyTip('video')

  const runSample = async () => {
    if (!v.storyboard || busyAction) return
    setBusyAction('sample')
    setActionMsg(null)
    try {
      const { cinemaSampleRender } = await import('../services/cinemaApi')
      const r = await cinemaSampleRender(v.storyboard)
      setActionMsg(r.ok
        ? { ok: true, text: `Rendu d’essai lancé (1 plan, 720p) — job ${r.jobId ?? '?'}. Résultat dans 5 à 7 minutes.` }
        : { ok: false, text: `Rendu d’essai refusé : ${r.error ?? 'réponse invalide du bridge'}` })
    } catch (e) {
      setActionMsg({ ok: false, text: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusyAction(null)
    }
  }

  const regenShot = async (shotId: number) => {
    const jobId = v.jobStatus?.jobId
    if (!jobId || busyAction) return
    setBusyAction(`shot-${shotId}`)
    setActionMsg(null)
    try {
      const { cinemaRegenerateShot } = await import('../services/cinemaApi')
      const r = await cinemaRegenerateShot(jobId, shotId)
      setActionMsg(r.ok
        ? { ok: true, text: `Plan ${shotId} relancé avec une nouvelle graine (${r.seed ?? '?'}) — job ${r.jobId ?? '?'}.` }
        : { ok: false, text: `Reprise du plan ${shotId} refusée : ${r.error ?? 'réponse invalide du bridge'}` })
    } catch (e) {
      setActionMsg({ ok: false, text: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusyAction(null)
    }
  }

  if (clip) {
    return (
      <div className="v4v-root" style={{ minHeight: '100%', display: 'flex', flexDirection: 'column', color: '#E6EAF5', fontFamily: FONT, position: 'relative' }}>
        <style>{CSS}</style>
        <div aria-hidden style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: `radial-gradient(560px 320px at 8% -10%, ${ACCENT}10, transparent 62%), radial-gradient(640px 420px at 96% 0%, ${ACCENT}0A, transparent 65%)`,
        }} />
        <div style={{ padding: '14px 26px', display: 'flex', alignItems: 'center', gap: 12, position: 'relative' }}>
          <TechLabel style={{ color: ACCENT }}>Clip rapide · un prompt, un clip direct</TechLabel>
          <span style={{ flex: 1 }} />
          <button type="button" className="v4v-gho" style={ghoBtn} onClick={() => setClip(false)}>
            <Ic d={IC.x} size={13} /> Retour cinéma
          </button>
        </div>
        <div aria-hidden style={{ height: 1, position: 'relative', overflow: 'hidden', background: `linear-gradient(90deg, ${ACCENT}66, rgba(255,255,255,.08) 45%, transparent)` }}>
          <span className="v4v-bandlight" style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: '58%', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.5) 50%, transparent)' }} />
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <Suspense fallback={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, height: 220, color: '#8B93A7', fontSize: 12.5 }}>
              <Spin /> Chargement du studio clip…
            </div>
          }>
            <QuickClipView />
          </Suspense>
        </div>
      </div>
    )
  }

  return (
    <div {...drop.bind} className="v4v-root v4v-page" style={{
      padding: '22px 26px',
      minHeight: '100%',
      color: '#E6EAF5',
      fontFamily: FONT,
      position: 'relative',
      outline: drop.isDraggingOver ? `2px dashed ${ACCENT}` : 'none',
      outlineOffset: -6,
      transition: 'outline .15s ease',
    }}>
      <style>{CSS}</style>

      <div aria-hidden style={{
        position: 'absolute',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
        background: `conic-gradient(from 90deg at 8% -6%, transparent 8%, ${ACCENT}0D 14%, transparent 22%), radial-gradient(640px 420px at 10% -6%, ${ACCENT}12, transparent 62%), radial-gradient(760px 540px at 96% 8%, ${ACCENT}0D, transparent 65%), radial-gradient(600px 480px at 42% 112%, ${ACCENT}0A, transparent 62%)`,
      }}>
        <div style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: `radial-gradient(rgba(255,255,255,.05) 1px, transparent 1.4px), radial-gradient(${ACCENT}14 1px, transparent 1.6px)`,
          backgroundSize: '30px 30px, 74px 74px',
          backgroundPosition: '0 0, 17px 29px',
          maskImage: 'linear-gradient(180deg, rgba(0,0,0,.9), rgba(0,0,0,.25) 70%, transparent)',
          WebkitMaskImage: 'linear-gradient(180deg, rgba(0,0,0,.9), rgba(0,0,0,.25) 70%, transparent)',
        }} />
      </div>

      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute',
          top: 14,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 40,
          pointerEvents: 'none',
          padding: '8px 16px',
          borderRadius: 999,
          background: ACCENT,
          color: '#0A0F1E',
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '.14em',
          textTransform: 'uppercase',
          boxShadow: '0 6px 24px rgba(0,0,0,.4)',
        }}>
          Déposer brief ou scénario · txt / md / pdf / docx
        </div>
      )}

      <div style={{ position: 'relative', zIndex: 1 }}>

      <header style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <span style={{ position: 'relative', display: 'inline-flex' }}>
          <span aria-hidden className="v4v-halo" style={{ position: 'absolute', inset: -12, borderRadius: 999, background: `radial-gradient(circle, ${ACCENT}38, transparent 70%)`, filter: 'blur(8px)' }} />
          <span className="v4v-float" style={{ position: 'relative', display: 'inline-flex' }}>
            <AuroraMascot module="video" size={46} />
          </span>
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', background: `linear-gradient(115deg, #FFFFFF 55%, #FDE68A 82%, ${ACCENT})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>Vidéo</h1>
          <TechLabel style={{ marginTop: 4 }}>klap · storyboard wan2.2 i2v · rendu local plan par plan</TechLabel>
        </div>
        {streak.current > 0 && (
          <Tag color={ACCENT}>
            série {streak.current} j{streak.longest > streak.current ? ` · record ${streak.longest} j` : ''}
          </Tag>
        )}
        <button type="button" className="v4v-gho" style={ghoBtn} onClick={() => setClip(true)} title="Un prompt, un clip direct sans storyboard (Wan2.2 / LTX)">
          <Ic d={IC.zap} /> Clip rapide
        </button>
        <button type="button" className="v4v-gho" style={ghoBtn} onClick={() => void v.runSelftest()} disabled={v.selftesting}>
          {v.selftesting ? <Spin /> : <Ic d={IC.pulse} />}
          {v.selftesting ? 'Diagnostic en cours' : 'Self-test pipeline'}
        </button>
        <button type="button" className="v4v-gho" style={ghoBtn} onClick={v.reset}>
          <Ic d={IC.reset} /> Réinitialiser
        </button>
      </header>

      <div aria-hidden style={{ height: 2, borderRadius: 999, marginBottom: 18, position: 'relative', overflow: 'hidden', background: `linear-gradient(90deg, ${ACCENT}, ${ACCENT}55 24%, rgba(255,255,255,.07) 55%, transparent 82%)` }}>
        <span className="v4v-bandlight" style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: '58%', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.65) 50%, transparent)' }} />
      </div>

      {v.selftestResult && (
        <Glass style={{
          padding: 16,
          marginBottom: 18,
          border: `1px solid ${v.selftestResult.overall_ok ? 'rgba(52,211,153,.35)' : 'rgba(248,113,113,.35)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 700, color: v.selftestResult.overall_ok ? '#34D399' : '#F87171' }}>
            <Ic d={v.selftestResult.overall_ok ? IC.check : IC.warn} />
            {v.selftestResult.summary}
          </div>
          {Object.keys(v.selftestResult.stages).length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: 8, marginTop: 12 }}>
              {Object.entries(v.selftestResult.stages).map(([name, st], i) => (
                <div key={name} className="v4v-item" style={{
                  padding: '7px 10px',
                  borderRadius: 10,
                  border: `1px solid ${st.ok ? 'rgba(52,211,153,.3)' : 'rgba(248,113,113,.4)'}`,
                  background: 'rgba(10,15,30,.4)',
                  fontFamily: MONO,
                  fontSize: 10.5,
                  color: st.ok ? '#34D399' : '#F87171',
                  animationDelay: `${Math.min(i, 12) * 45}ms`,
                }}>
                  {name} · {st.ms} ms
                  {st.error && (
                    <div style={{ marginTop: 3, color: '#5A6377', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{st.error}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Glass>
      )}

      <div className="v4v-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 18, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>

          <Glass style={{ padding: 20, animationDelay: '40ms' }}>
            <TechLabel>Brief de scène</TechLabel>
            <textarea
              className="v4v-in"
              value={v.prompt}
              onChange={(e) => v.setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault()
                  void v.generateStoryboard()
                }
              }}
              placeholder="Décris ta scène : « Une grue cendrée traverse la baie au lever du soleil »"
              disabled={v.generating}
              rows={3}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                marginTop: 10,
                padding: '12px 14px',
                background: 'rgba(10,15,30,.6)',
                border: '1px solid rgba(255,255,255,.12)',
                borderRadius: 11,
                color: '#E6EAF5',
                fontSize: 13.5,
                lineHeight: 1.55,
                fontFamily: 'inherit',
                resize: 'vertical',
                minHeight: 84,
                transition: 'all .25s',
              }}
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <TechLabel style={{ minWidth: 82 }}>Format</TechLabel>
                {ASPECTS.map((a) => (
                  <Chip key={a} active={v.aspect === a} onClick={() => v.setAspect(a)} disabled={v.generating}>{a}</Chip>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <TechLabel style={{ minWidth: 82 }}>Durée</TechLabel>
                {LENGTHS.map((l) => (
                  <Chip key={l.value} active={v.length === l.value} onClick={() => v.setLength(l.value)} disabled={v.generating}>{l.label}</Chip>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <TechLabel style={{ minWidth: 82 }}>Style</TechLabel>
                {styleOptions.map((s) => (
                  <Chip key={s} active={v.style === s} onClick={() => v.setStyle(s)} disabled={v.generating}>{s}</Chip>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <TechLabel style={{ minWidth: 82 }}>Sous-titres</TechLabel>
                <button
                  type="button"
                  role="switch"
                  aria-checked={v.subtitlesEnabled}
                  onClick={() => v.setSubtitlesEnabled(!v.subtitlesEnabled)}
                  style={{
                    width: 38,
                    height: 20,
                    boxSizing: 'border-box',
                    borderRadius: 999,
                    border: `1px solid ${v.subtitlesEnabled ? ACCENT : 'rgba(255,255,255,.14)'}`,
                    background: v.subtitlesEnabled ? ACCENT : 'rgba(255,255,255,.06)',
                    position: 'relative',
                    cursor: 'pointer',
                    transition: 'all .25s',
                    padding: 0,
                  }}
                >
                  <span style={{
                    position: 'absolute',
                    top: 2,
                    left: v.subtitlesEnabled ? 20 : 2,
                    width: 14,
                    height: 14,
                    borderRadius: 999,
                    background: v.subtitlesEnabled ? '#0A0F1E' : '#8B93A7',
                    transition: 'all .25s',
                  }} />
                </button>
                <span style={{ fontSize: 11.5, color: '#5A6377' }}>Piste SRT incrustée dans le MP4 final</span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 18 }}>
              <button
                type="button"
                className="v4v-pri"
                style={priBtn}
                onClick={() => void v.generateStoryboard()}
                disabled={!v.prompt.trim() || v.generating}
              >
                {v.generating ? <Spin /> : <Ic d={IC.clap} />}
                {v.generating ? 'Écriture du storyboard…' : 'Générer le storyboard'}
              </button>
              <button type="button" className="v4v-gho" style={ghoBtn} onClick={v.randomVideoPreset} disabled={v.generating}>
                <Ic d={IC.shuffle} /> Idée surprise
              </button>
              <VoicePushToTalk
                onTranscript={(text) => v.setPrompt((v.prompt ? `${v.prompt} ` : '') + text)}
                label="Dicter la scène vidéo"
                disabled={v.generating}
                variant="ghost"
                size={34}
              />
              <FavoriteButton
                prompt={v.prompt}
                module="video"
                parameters={{ style: v.style, aspect: v.aspect, length: v.length }}
                tags={['video', v.style]}
                disabled={v.generating}
              />
              <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 10, letterSpacing: '.15em', color: '#5A6377', textTransform: 'uppercase' }}>
                Ctrl + Entrée · glisse un brief txt / md / pdf / docx
              </span>
            </div>

            {v.prompt.trim() && cineHits.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
                <TechLabel>Grammaire ciné détectée</TechLabel>
                {cineHits.map((h) => <Tag key={h} color={ACCENT}>{h}</Tag>)}
              </div>
            )}
          </Glass>

          {v.clarification && (
            <Glass style={{ padding: 18, border: `1px solid ${ACCENT}44`, animationDelay: '70ms' }}>
              <TechLabel style={{ color: ACCENT }}>Clarification demandée</TechLabel>
              <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.6, color: '#E6EAF5' }}>{v.clarification}</div>
              <div style={{ marginTop: 8, fontSize: 11.5, color: '#8B93A7' }}>Précise ton brief ci-dessus puis relance le storyboard.</div>
            </Glass>
          )}

          {v.error && (
            <Glass style={{ padding: 18, border: '1px solid rgba(248,113,113,.4)', animationDelay: '70ms' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#F87171', fontSize: 12.5, fontWeight: 700 }}>
                <Ic d={IC.warn} /> Erreur
              </div>
              <div style={{ marginTop: 8, fontSize: 12.5, lineHeight: 1.55, color: '#E6EAF5', wordBreak: 'break-word' }}>{v.error}</div>
            </Glass>
          )}

          {v.storyboard && (
            <Glass style={{ padding: 20, animationDelay: '100ms' }}>
              <TechLabel style={{ color: ACCENT }}>Storyboard</TechLabel>
              <h2 style={{ margin: '8px 0 0', fontSize: 20, fontWeight: 800, letterSpacing: '-0.02em' }}>{v.storyboard.title}</h2>
              <div style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.6, color: '#8B93A7' }}>{v.storyboard.summary}</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                <Tag color={ACCENT}>{v.storyboard.shots.length} plans</Tag>
                <Tag>{v.storyboard.aspect}</Tag>
                <Tag>{v.storyboard.resolution}</Tag>
                <Tag>{v.storyboard.style}</Tag>
                {v.storyboard.music?.enabled && <Tag>musique</Tag>}
                {v.storyboard.characters.map((c) => (
                  <Tag key={c.name}>{c.name} · {c.voice_lang}</Tag>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 16 }}>
                {v.rendering ? (
                  <button type="button" className="v4v-gho" style={{ ...ghoBtn, color: '#F87171', borderColor: 'rgba(248,113,113,.4)' }} onClick={v.cancelRender}>
                    <Ic d={IC.stop} /> Annuler le rendu
                  </button>
                ) : (
                  <>
                    <button type="button" className="v4v-pri" style={priBtn} onClick={() => void v.runRender()}>
                      <Ic d={IC.play} /> Lancer le rendu Wan2.2
                    </button>
                    <button type="button" className="v4v-gho" style={ghoBtn} onClick={() => void v.previewKeyframes()} disabled={v.previewing}>
                      {v.previewing ? <Spin /> : <Ic d={IC.eye} />}
                      {v.previewing ? 'Flux en cours…' : 'Aperçu keyframes Flux'}
                    </button>
                    <button type="button" className="v4v-gho" style={ghoBtn} onClick={() => void runSample()} disabled={busyAction !== null || v.previewing}>
                      {busyAction === 'sample' ? <Spin /> : <Ic d={IC.flask} />}
                      {busyAction === 'sample' ? 'Essai en cours…' : 'Rendu d’essai · 1 plan'}
                    </button>
                  </>
                )}
              </div>

              <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill,minmax(230px,1fr))', marginTop: 18 }}>
                {v.storyboard.shots.map((s, i) => (
                  <div key={s.id ?? i} className="v4v-mini v4v-item v4v-film" style={{
                    padding: '18px 14px',
                    borderRadius: 14,
                    background: 'rgba(10,15,30,.45)',
                    animationDelay: `${Math.min(i, 10) * 55}ms`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <TechLabel style={{ color: ACCENT }}>Plan {String(i + 1).padStart(2, '0')}</TechLabel>
                      <TechLabel style={{ color: '#5A6377' }}>{s.duration_s} s</TechLabel>
                    </div>
                    <div style={{ fontSize: 12.5, lineHeight: 1.55, marginTop: 8 }}>{s.scene}</div>
                    {s.dialogue && (
                      <div style={{ marginTop: 8, fontSize: 12, lineHeight: 1.5, color: '#8B93A7' }}>
                        {s.speaker && <span style={{ color: ACCENT, fontWeight: 700 }}>{s.speaker} — </span>}
                        « {s.dialogue} »
                      </div>
                    )}
                    {(s.camera || s.needs_lipsync) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontFamily: MONO, fontSize: 10, color: '#5A6377' }}>
                        <Ic d={IC.camera} size={12} />
                        {s.camera}{s.needs_lipsync ? ' · lipsync' : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Glass>
          )}

          {actionMsg && (
            <Glass style={{ padding: 14, border: `1px solid ${actionMsg.ok ? 'rgba(52,211,153,.35)' : 'rgba(248,113,113,.4)'}`, animationDelay: '70ms' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: actionMsg.ok ? '#34D399' : '#F87171' }}>
                <Ic d={actionMsg.ok ? IC.check : IC.warn} size={14} />
                <span style={{ flex: 1, minWidth: 0, wordBreak: 'break-word' }}>{actionMsg.text}</span>
                <button
                  type="button"
                  onClick={() => setActionMsg(null)}
                  title="Fermer"
                  style={{ background: 'transparent', border: 'none', color: '#5A6377', cursor: 'pointer', padding: 2, display: 'inline-flex' }}
                >
                  <Ic d={IC.x} size={12} />
                </button>
              </div>
            </Glass>
          )}

          {v.jobStatus && (
            <Glass style={{ padding: 18, animationDelay: '130ms' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span
                  className={v.jobStatus.status === 'running' ? 'v4v-dot' : undefined}
                  style={{ width: 9, height: 9, borderRadius: 999, background: jobDot, boxShadow: `0 0 10px ${jobDot}` }}
                />
                <TechLabel>Job {v.jobStatus.jobId.slice(0, 8)}</TechLabel>
                <span style={{ fontSize: 13, fontWeight: 700 }}>{STATUS_FR[v.jobStatus.status] ?? v.jobStatus.status}</span>
                {eta?.stage && <Tag>{eta.stage}</Tag>}
              </div>

              {eta && eta.total > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontFamily: MONO, fontSize: 10.5, color: '#8B93A7', marginBottom: 6 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8 }}>
                      <span style={{ ...gradText, fontSize: 16, fontWeight: 800 }}>{pct}%</span>
                      <span>{eta.done}/{eta.total} plans</span>
                    </span>
                    {eta.remaining_s > 0 && <span>reste ~{fmtSec(eta.remaining_s)}</span>}
                  </div>
                  <div style={{ position: 'relative' }}>
                    <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,.07)', overflow: 'hidden' }}>
                      <div className={v.jobStatus.status === 'running' ? 'v4v-bar' : undefined} style={{
                        width: `${pct}%`,
                        height: '100%',
                        borderRadius: 999,
                        background: `linear-gradient(90deg,${ACCENT},#FDE68A,${ACCENT})`,
                        boxShadow: `0 0 12px ${ACCENT}88`,
                        transition: 'width .4s ease',
                      }} />
                    </div>
                    {v.jobStatus.status === 'running' && pct > 0 && pct < 100 && (
                      <span aria-hidden style={{
                        position: 'absolute',
                        left: `calc(${pct}% - 5px)`,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        width: 10,
                        height: 10,
                        borderRadius: 999,
                        background: '#FDE68A',
                        boxShadow: `0 0 10px ${ACCENT}, 0 0 24px ${ACCENT}AA`,
                        transition: 'left .4s ease',
                        pointerEvents: 'none',
                      }} />
                    )}
                  </div>
                </div>
              )}

              {v.jobStatus.error && (
                <div style={{ marginTop: 10, fontSize: 12, color: '#F87171', wordBreak: 'break-word' }}>{v.jobStatus.error}</div>
              )}

              {v.jobStatus.outputPath && (
                <div style={{ marginTop: 10, fontFamily: MONO, fontSize: 10.5, color: '#5A6377', wordBreak: 'break-all' }}>{v.jobStatus.outputPath}</div>
              )}

              {v.jobStatus.output && (
                <details style={{ marginTop: 10 }}>
                  <summary style={{ fontFamily: MONO, fontSize: 10, letterSpacing: '.15em', textTransform: 'uppercase', color: '#5A6377', cursor: 'pointer' }}>Journal du moteur</summary>
                  <pre style={{
                    margin: '8px 0 0',
                    padding: 10,
                    borderRadius: 10,
                    background: 'rgba(10,15,30,.6)',
                    border: '1px solid rgba(255,255,255,.08)',
                    fontFamily: MONO,
                    fontSize: 10,
                    color: '#8B93A7',
                    maxHeight: 160,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}>{v.jobStatus.output.slice(-2000)}</pre>
                </details>
              )}

              {grade && (
                <div style={{
                  marginTop: 14,
                  display: 'flex',
                  gap: 14,
                  alignItems: 'center',
                  padding: 14,
                  borderRadius: 14,
                  border: `1px solid ${GRADE_COLOR[grade.grade]}55`,
                  background: `${GRADE_COLOR[grade.grade]}12`,
                }}>
                  <div style={{
                    width: 46,
                    height: 46,
                    borderRadius: 999,
                    background: `radial-gradient(circle at 32% 28%, #FFFFFF55, transparent 42%), ${GRADE_COLOR[grade.grade]}`,
                    color: '#0A0F1E',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 800,
                    fontSize: 22,
                    flexShrink: 0,
                    boxShadow: `0 0 0 5px ${GRADE_COLOR[grade.grade]}1F, 0 10px 30px -8px ${GRADE_COLOR[grade.grade]}66`,
                  }}>{grade.grade}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: GRADE_COLOR[grade.grade] }}>
                      Qualité {grade.overall_pct}% — {GRADE_LABEL[grade.grade]}
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 6, fontFamily: MONO, fontSize: 10.5, color: '#8B93A7' }}>
                      <span>plans {grade.breakdown.shot_pct}%</span>
                      <span>personnages {grade.breakdown.char_pct}%</span>
                      <span>audio {grade.breakdown.audio_pct}%</span>
                      <span>temporel {grade.breakdown.temporal_pct}%</span>
                      <span>intégrité {grade.breakdown.integrity_pct}%</span>
                    </div>
                    {grade.weak_shots.length > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                        <span style={{ fontSize: 11.5, color: '#F87171' }}>{grade.weak_shots.length} plan(s) faible(s) :</span>
                        {grade.weak_shots.map((w) => (
                          <button
                            key={w.shot_id}
                            type="button"
                            className="v4v-gho"
                            style={{ ...ghoBtn, padding: '4px 10px', fontSize: 10.5, gap: 5, color: '#F87171', borderColor: 'rgba(248,113,113,.4)' }}
                            onClick={() => void regenShot(w.shot_id)}
                            disabled={busyAction !== null}
                            title={`Reprendre le plan ${w.shot_id} avec une nouvelle graine`}
                          >
                            {busyAction === `shot-${w.shot_id}` ? <Spin size={11} /> : <Ic d={IC.reset} size={11} />}
                            plan {w.shot_id} · {w.avg_score}/10
                          </button>
                        ))}
                      </div>
                    )}
                    {!grade.exportable && (
                      <div style={{ marginTop: 6, fontSize: 11.5, fontWeight: 700, color: '#F87171' }}>
                        Export bloqué — reprends les plans faibles avant téléchargement
                      </div>
                    )}
                  </div>
                </div>
              )}

              {renderCharQuality && Object.keys(renderCharQuality).length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <div aria-hidden style={sepLine} />
                  <TechLabel>Fidélité personnages · vision</TechLabel>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                    {Object.entries(renderCharQuality).map(([name, q], i) => (
                      <div key={name} className="v4v-item" style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontSize: 12, animationDelay: `${Math.min(i, 12) * 40}ms` }}>
                        <span style={{ fontFamily: MONO, fontWeight: 700, minWidth: 44, color: scoreColor(q.score) }}>{q.score}/10</span>
                        <span style={{ fontWeight: 700 }}>{name}</span>
                        <span style={{ flex: 1, minWidth: 0, fontSize: 11.5, lineHeight: 1.45, color: '#8B93A7' }}>{q.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {shotQuality.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <TechLabel>Fidélité par plan · scène / physique / identité</TechLabel>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                    {shotQuality.map((q) => {
                      const weak = (q.score != null && q.score < 7)
                        || (q.physics_score != null && q.physics_score < 6)
                        || (q.identity_score != null && q.identity_score < 6)
                      return (
                        <div key={q.shot_id} style={{
                          padding: '8px 10px',
                          borderRadius: 10,
                          background: 'rgba(10,15,30,.4)',
                          border: '1px solid rgba(255,255,255,.06)',
                        }}>
                          <div style={{ display: 'flex', gap: 14, alignItems: 'baseline', flexWrap: 'wrap', fontFamily: MONO, fontSize: 11 }}>
                            <span style={{ minWidth: 56, color: '#5A6377' }}>plan {String(q.shot_id).padStart(2, '0')}</span>
                            <span title="Cohérence de la scène" style={{ fontWeight: 700, color: q.score == null ? '#5A6377' : scoreColor(q.score) }}>
                              scène {q.score == null ? '—' : `${q.score}/10`}
                            </span>
                            <span title="Cohérence physique (gravité, contacts, clipping)" style={{ fontWeight: 700, color: q.physics_score == null ? '#5A6377' : scoreColor(q.physics_score) }}>
                              physique {q.physics_score == null ? '—' : `${q.physics_score}/10`}
                            </span>
                            <span title="Identité personnage sur 3 frames" style={{ fontWeight: 700, color: q.identity_score == null ? '#5A6377' : scoreColor(q.identity_score) }}>
                              identité {q.identity_score == null ? '—' : `${q.identity_score}/10`}
                            </span>
                          </div>
                          {q.issues && q.issues.length > 0 && (
                            <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 11, lineHeight: 1.5, color: '#F87171' }}>
                              {q.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                            </ul>
                          )}
                          {weak && (
                            <button
                              type="button"
                              className="v4v-gho"
                              style={{ ...ghoBtn, marginTop: 8, padding: '5px 12px', fontSize: 11, gap: 6 }}
                              onClick={() => void regenShot(q.shot_id)}
                              disabled={busyAction !== null}
                            >
                              {busyAction === `shot-${q.shot_id}` ? <Spin size={12} /> : <Ic d={IC.reset} size={12} />}
                              Reprendre ce plan · nouvelle graine
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {temporalQuality.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <TechLabel>Cohérence temporelle · cuts internes</TechLabel>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 8 }}>
                    {temporalQuality.map((t) => {
                      const color = t.ok ? '#34D399' : t.cuts_count >= 3 ? '#F87171' : '#FBBF24'
                      return (
                        <div key={t.shot_id} style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontFamily: MONO, fontSize: 11 }}>
                          <span style={{ minWidth: 56, color: '#5A6377' }}>plan {String(t.shot_id).padStart(2, '0')}</span>
                          <span style={{ flex: 1, minWidth: 0, color }}>
                            {t.cuts_count === 0 ? 'continu, aucun cut'
                              : t.cuts_count === 1 ? '1 cut détecté (acceptable)'
                              : `${t.cuts_count} cuts internes — jump cut / téléportation`}
                            {t.cuts && t.cuts.length > 0 && (
                              <span style={{ marginLeft: 8, color: '#5A6377' }}>@ {t.cuts.map((c) => `${c.t}s`).join(', ')}</span>
                            )}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {audioQuality.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <TechLabel>Intégrité audio par plan</TechLabel>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 8 }}>
                    {audioQuality.map((a) => {
                      const ratio = a.silence_ratio ?? 0
                      const color = !a.ok ? '#F87171'
                        : !a.has_audio ? '#5A6377'
                        : ratio < 0.2 ? '#34D399'
                        : ratio < 0.4 ? '#FBBF24'
                        : '#F87171'
                      return (
                        <div key={a.shot_id} style={{ display: 'flex', gap: 10, alignItems: 'baseline', fontFamily: MONO, fontSize: 11 }}>
                          <span style={{ minWidth: 56, color: '#5A6377' }}>plan {String(a.shot_id).padStart(2, '0')}</span>
                          <span style={{ flex: 1, minWidth: 0, color }}>
                            {!a.has_audio
                              ? 'piste audio absente'
                              : `silence ${(ratio * 100).toFixed(0)}%${a.expected_dialogue ? ' · dialogue attendu' : ''}`}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {integrity && (
                <div style={{
                  marginTop: 14,
                  padding: 12,
                  borderRadius: 12,
                  border: `1px solid ${integrity.ok ? 'rgba(52,211,153,.3)' : 'rgba(248,113,113,.4)'}`,
                  background: integrity.ok ? 'rgba(52,211,153,.06)' : 'rgba(248,113,113,.06)',
                }}>
                  <TechLabel style={{ color: integrity.ok ? '#34D399' : '#F87171' }}>
                    {integrity.ok ? 'Intégrité validée · ffprobe' : 'Problèmes d’intégrité détectés · ffprobe'}
                  </TechLabel>
                  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8, fontFamily: MONO, fontSize: 11, color: '#E6EAF5' }}>
                    <span>durée {integrity.duration_s.toFixed(1)} s</span>
                    <span>vidéo {integrity.video_codec ?? 'absente'}</span>
                    <span>audio {integrity.has_audio ? integrity.audio_codec ?? '?' : 'absent'}</span>
                    <span>{(integrity.size_bytes / (1024 * 1024)).toFixed(1)} Mo</span>
                  </div>
                  {integrity.errors.length > 0 && (
                    <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 11, lineHeight: 1.5, color: '#F87171' }}>
                      {integrity.errors.map((err, i) => <li key={i}>{err}</li>)}
                    </ul>
                  )}
                </div>
              )}
            </Glass>
          )}

          {v.videoUrl && (
            <Glass style={{ padding: 18, animationDelay: '160ms' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <TechLabel style={{ color: ACCENT }}>Projection</TechLabel>
                <span style={{ flex: 1 }} />
                {exportable ? (
                  <a href={v.videoUrl} download className="v4v-pri" style={{ ...priBtn, padding: '9px 15px', fontSize: 12, textDecoration: 'none' }}>
                    <Ic d={IC.download} size={14} /> Télécharger le MP4
                  </a>
                ) : (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: '#F87171', fontWeight: 700 }}>
                    <Ic d={IC.warn} size={13} /> Export bloqué (grade {grade?.grade})
                  </span>
                )}
              </div>
              <video
                src={v.videoUrl}
                controls
                style={{
                  width: '100%',
                  maxHeight: '58vh',
                  marginTop: 12,
                  background: '#05070F',
                  borderRadius: 14,
                  border: `1px solid ${ACCENT}44`,
                  boxShadow: `0 30px 90px -30px ${ACCENT}4D, 0 0 60px ${ACCENT}22`,
                }}
              />
            </Glass>
          )}

          {v.previewResult && (
            <Glass style={{ padding: 18, animationDelay: '190ms' }}>
              <TechLabel style={{ color: ACCENT }}>Aperçu keyframes · fidélité personnages</TechLabel>
              {v.previewResult.error ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12.5, color: '#F87171' }}>
                  <Ic d={IC.warn} /> Aperçu échoué : {v.previewResult.error}
                </div>
              ) : charQuality && Object.keys(charQuality).length > 0 ? (
                <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', marginTop: 12 }}>
                  {Object.entries(charQuality).map(([name, q], i) => (
                    <div key={name} className="v4v-mini v4v-item" style={{
                      padding: 10,
                      borderRadius: 14,
                      background: 'rgba(10,15,30,.45)',
                      border: `1px solid ${scoreColor(q.score)}44`,
                      animationDelay: `${Math.min(i, 10) * 60}ms`,
                    }}>
                      <div style={{ overflow: 'hidden', borderRadius: 10, background: '#05070F' }}>
                        <img
                          className="v4v-kfimg"
                          src={keyframeUrl(q.keyframe_url)}
                          alt={name}
                          onError={(e) => { e.currentTarget.style.display = 'none' }}
                          style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover' }}
                        />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 8 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 700 }}>{name}</span>
                        <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700, color: scoreColor(q.score) }}>{q.score}/10</span>
                      </div>
                      <div style={{ marginTop: 4, fontSize: 11, lineHeight: 1.45, color: '#8B93A7' }}>{q.reason}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ marginTop: 10, fontSize: 12, color: '#8B93A7' }}>Aucun personnage détecté dans ce storyboard.</div>
              )}
            </Glass>
          )}

          {!v.hasResult && !v.jobStatus && !v.videoUrl && !v.previewResult && (
            <Glass style={{ padding: '34px 28px 30px', textAlign: 'center', animationDelay: '130ms' }}>
              <span style={{ position: 'relative', display: 'inline-flex' }}>
                <span aria-hidden className="v4v-halo" style={{ position: 'absolute', inset: -22, borderRadius: 999, background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`, filter: 'blur(10px)' }} />
                <span className="v4v-float" style={{ position: 'relative', display: 'inline-flex' }}>
                  <AuroraMascot module="video" size={90} />
                </span>
              </span>
              <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.01em', marginTop: 16, ...gradText }}>
                Le plateau est prêt, il ne manque que ta scène
              </div>
              <div style={{ maxWidth: 460, margin: '8px auto 0', fontSize: 12, lineHeight: 1.6, color: '#8B93A7' }}>
                Décris ta scène, choisis format, durée et style : j’écris le storyboard plan par plan,
                tu vérifies les keyframes Flux, puis on engage le rendu Wan2.2 complet.
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginTop: 16 }}>
                {['01 · storyboard', '02 · keyframes flux', '03 · rendu wan2.2', '04 · mp4 final'].map((step, i) => (
                  <span key={step} className="v4v-item" style={{
                    fontFamily: MONO,
                    fontSize: 10,
                    letterSpacing: '.12em',
                    textTransform: 'uppercase',
                    color: '#8B93A7',
                    padding: '5px 12px',
                    borderRadius: 999,
                    border: '1px solid rgba(255,255,255,.09)',
                    background: 'rgba(10,15,30,.4)',
                    animationDelay: `${180 + i * 70}ms`,
                  }}>{step}</span>
                ))}
              </div>
              {dailyTip && (
                <div style={{
                  maxWidth: 440,
                  margin: '14px auto 0',
                  padding: '8px 14px',
                  borderRadius: 10,
                  border: `1px solid ${ACCENT}33`,
                  background: `${ACCENT}0D`,
                  fontFamily: MONO,
                  fontSize: 10.5,
                  lineHeight: 1.55,
                  color: '#8B93A7',
                }}>
                  {dailyTip}
                </div>
              )}
            </Glass>
          )}
        </div>

        <Glass style={{ padding: 18, animationDelay: '210ms' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <TechLabel>Historique</TechLabel>
            <TechLabel style={{ color: '#5A6377' }}>{v.history.length}</TechLabel>
          </div>
          {v.history.length === 0 ? (
            <div style={{ marginTop: 16, textAlign: 'center', padding: '10px 6px 14px' }}>
              <span style={{ position: 'relative', display: 'inline-flex', color: '#5A6377' }}>
                <span aria-hidden style={{ position: 'absolute', inset: -14, borderRadius: 999, background: `radial-gradient(circle, ${ACCENT}1F, transparent 70%)`, filter: 'blur(6px)' }} />
                <Ic d={IC.film} size={26} />
              </span>
              <div style={{ marginTop: 10, fontSize: 12, lineHeight: 1.6, color: '#5A6377' }}>
                Aucun brief mémorisé. Chaque storyboard généré est archivé ici pour être rejoué.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12, maxHeight: '56vh', overflowY: 'auto' }}>
              {v.history.map((h) => (
                <div key={h.prompt} className="v4v-hist" style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0,1fr) 24px',
                  gap: 8,
                  alignItems: 'center',
                  padding: '8px 10px',
                  borderRadius: 11,
                  border: '1px solid rgba(255,255,255,.06)',
                  background: 'rgba(255,255,255,.02)',
                }}>
                  <button
                    type="button"
                    onClick={() => v.recallPrompt(h)}
                    title={h.prompt}
                    style={{ background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'pointer', color: '#E6EAF5', fontFamily: 'inherit', minWidth: 0 }}
                  >
                    <div style={{ fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.prompt}</div>
                    <div style={{ fontFamily: MONO, fontSize: 9.5, letterSpacing: '.08em', color: '#5A6377', marginTop: 3 }}>
                      {typeof h.meta?.style === 'string' ? `${h.meta.style} · ` : ''}{new Date(h.ts).toLocaleDateString('fr-FR')}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => v.removeHistory(h.prompt)}
                    title="Retirer de l’historique"
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 8,
                      border: '1px solid rgba(255,255,255,.1)',
                      background: 'transparent',
                      color: '#5A6377',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: 0,
                    }}
                  >
                    <Ic d={IC.x} size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Glass>
      </div>

      </div>
    </div>
  )
}
