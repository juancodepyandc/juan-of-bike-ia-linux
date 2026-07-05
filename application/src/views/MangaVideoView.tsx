import { lazy, Suspense, type ComponentType, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { motion as fm, AnimatePresence } from 'framer-motion'
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp,
  Download, Film, Layers, Library, Loader2, Mic2, Play,
  RotateCcw, Sparkles, StopCircle, Trash2, Upload, X, ZoomIn, ZoomOut,
} from 'lucide-react'
const VideoKeyframeEditor = lazy(() => import('../components/VideoKeyframeEditor'))
import type { Keyframe } from '../components/VideoKeyframeEditor'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore'
import { useAppStore } from '../stores/appStore'
import { DEFAULT_MAIN_MODEL } from '../config/models'
import {
  cinemaGenerateRun,
  cinemaGenerateStoryboard,
  cinemaJobStatus,
  localFileToBridgeUrl,
  voiceExtractRun,
  voiceLibraryClear,
  voiceLibraryDelete,
  voiceLibraryList,
  voiceRegister,
  type CinemaEta,
  type CinemaShot,
  type Storyboard,
  type VoiceLibraryEntry,
} from '../services/cinemaApi'

type Character = 'natsu' | 'lucy'
const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

type IconProps = { size?: number; strokeWidth?: number }
type MotionDir = 'static' | 'pan-left' | 'pan-right' | 'pan-up' | 'pan-down' | 'zoom-in' | 'zoom-out' | 'orbit' | 'dolly'
const MOTION_DIRS: { id: MotionDir; label: string; angle: number; icon: ComponentType<IconProps> }[] = [
  { id: 'pan-up',     label: 'PAN HAUT',   angle: -90, icon: ArrowUp },
  { id: 'orbit',      label: 'ORBIT',      angle: -45, icon: RotateCcw },
  { id: 'pan-right',  label: 'PAN DROIT',  angle: 0,   icon: ArrowRight },
  { id: 'zoom-in',    label: 'ZOOM IN',    angle: 45,  icon: ZoomIn },
  { id: 'pan-down',   label: 'PAN BAS',    angle: 90,  icon: ArrowDown },
  { id: 'dolly',      label: 'DOLLY',      angle: 135, icon: Sparkles },
  { id: 'pan-left',   label: 'PAN GAUCHE', angle: 180, icon: ArrowLeft },
  { id: 'zoom-out',   label: 'ZOOM OUT',   angle: 225, icon: ZoomOut },
]

type Aspect = '16:9' | '9:16' | '1:1' | '4:3' | '21:9'
type Resolution = 'auto' | '720p' | '1080p' | '1440p'

type Clip = {
  id: string
  prompt: string
  motion: MotionDir
  frames: number
  ts: number
  videoUrl?: string
  videoPath?: string
  storyboard?: Storyboard
  durationS?: number
}

function readCharacter(): Character {
  try { return window.localStorage.getItem('ft-who') === 'lucy' ? 'lucy' : 'natsu' }
  catch { return 'natsu' }
}

function fmtSec(seconds: number | undefined | null): string {
  if (!seconds || seconds <= 0) return '–'
  const total = Math.round(seconds)
  const m = Math.floor(total / 60)
  const s = total % 60
  return m > 0 ? `${m}m ${s.toString().padStart(2, '0')}` : `${s}s`
}

// Pre-generation time table — cf. application/docs/VIDEO_GENERATION_TIMES.md
type StyleKey = 'cartoon_pixar' | 'anime' | 'realistic' | 'manga' | 'documentary' | 'noir' | 'watercolor'
const TIME_TABLE_5S_MIN: Record<StyleKey, Record<'720p' | '1080p' | '1440p', number>> = {
  cartoon_pixar: { '720p': 22, '1080p': 28, '1440p': 35 },
  anime:         { '720p': 18, '1080p': 24, '1440p': 30 },
  realistic:     { '720p': 28, '1080p': 36, '1440p': 45 },
  manga:         { '720p': 18, '1080p': 24, '1440p': 30 },
  documentary:   { '720p': 28, '1080p': 36, '1440p': 45 },
  noir:          { '720p': 25, '1080p': 32, '1440p': 40 },
  watercolor:    { '720p': 24, '1080p': 30, '1440p': 38 },
}

function estimateMinutes(shots: CinemaShot[], style: string, resolution: '720p' | '1080p' | '1440p'): number {
  const styleKey = (TIME_TABLE_5S_MIN[style as StyleKey] ? style : 'realistic') as StyleKey
  const per5s = TIME_TABLE_5S_MIN[styleKey][resolution]
  let total = 0
  for (const s of shots) total += per5s * (Math.max(s.duration_s, 4) / 5)
  return Math.round(total)
}

function detectMobile(): boolean {
  if (typeof window === 'undefined') return false
  return /android|iphone|ipad|mobile/i.test(navigator.userAgent) || window.innerWidth < 720
}

function defaultResolution(): Resolution {
  return detectMobile() ? '720p' : 'auto'
}

export default function MangaVideoView() {
  const [who, setWho] = useState<Character>(readCharacter)
  const mainModel = useAppStore((s) => s.mainModel) || DEFAULT_MAIN_MODEL
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  const videoDraft = useModuleDraftsStore((s) => s.drafts.video)
  const setVideoDraft = useModuleDraftsStore((s) => s.setDraft)
  const [scene, setScene] = useState<string>(() => videoDraft?.prompt ?? '')
  const [motionDir, setMotionDir] = useState<MotionDir>(() => (videoDraft?.options?.motion as MotionDir) ?? 'static')
  const [keyframeOpen, setKeyframeOpen] = useState(false)
  const [keyframes, setKeyframes] = useState<Keyframe[]>([])
  const [videoDuration, setVideoDuration] = useState<number>(8)
  const [aspect, setAspect] = useState<Aspect>(
    () => (videoDraft?.options?.aspect as Aspect) ?? '16:9',
  )
  const [resolution, setResolution] = useState<Resolution>(() => defaultResolution())
  const [qualityMode, setQualityMode] = useState<'auto' | 'balanced' | 'premium'>('auto')

  useEffect(() => {
    const id = window.setTimeout(() =>
      setVideoDraft('video', { prompt: scene, options: { motion: motionDir, aspect } }),
    200)
    return () => window.clearTimeout(id)
  }, [scene, motionDir, aspect, setVideoDraft])

  const ASPECT_PRESETS: Array<{ id: Aspect; label: string; w: number; h: number; hint: string }> = [
    { id: '16:9', label: '16:9', w: 1280, h: 720, hint: 'YouTube · cinema' },
    { id: '9:16', label: '9:16', w: 720,  h: 1280, hint: 'Reels · TikTok' },
    { id: '1:1',  label: '1:1',  w: 1024, h: 1024, hint: 'Instagram · carre' },
    { id: '4:3',  label: '4:3',  w: 1024, h: 768,  hint: 'TV classique' },
    { id: '21:9', label: '21:9', w: 1536, h: 640,  hint: 'Ultra-wide' },
  ]
  const RES_PRESETS: Array<{ id: Resolution; label: string; hint: string }> = [
    { id: 'auto',   label: 'Auto',   hint: 'Mobile -> 720p, sinon 1080p' },
    { id: '720p',   label: '720p',   hint: 'Le plus rapide' },
    { id: '1080p',  label: '1080p',  hint: 'Equilibre' },
    { id: '1440p',  label: '1440p',  hint: 'Maximum qualite' },
  ]
  const activeAspect = ASPECT_PRESETS.find((a) => a.id === aspect) ?? ASPECT_PRESETS[0]

  // Phases: idle | storyboarding | review | generating | clip
  type Phase = 'idle' | 'storyboarding' | 'review' | 'generating' | 'cleared'
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null)
  const [clarification, setClarification] = useState<string | null>(null)
  const [eta, setEta] = useState<CinemaEta | null>(null)
  const [progressLabel, setProgressLabel] = useState<string>('')
  const [reel, setReel] = useState<Clip[]>([])
  const [activeClipId, setActiveClipId] = useState<string | null>(null)
  const cancelRef = useRef<{ cancelled: boolean }>({ cancelled: false })

  // Voice library state
  const [voiceLibOpen, setVoiceLibOpen] = useState(false)
  const [voiceList, setVoiceList] = useState<VoiceLibraryEntry[]>([])
  const [voiceLoading, setVoiceLoading] = useState(false)

  const activeClip = useMemo(() => reel.find((c) => c.id === activeClipId) ?? null, [reel, activeClipId])

  // -------------------------------------------------------------------------
  // First-mount cleanup: the user explicitly asked that old artifacts from the
  // previous Video module are wiped when the new Cinema module boots.
  // -------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      try {
        // Best-effort: ask the bridge to clear the old video temp dir. We do
        // NOT touch /generated/videos (user files) — only /temp/cinema scratch.
        await fetch('/api/fs/remove-dir', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: 'application/temp/video_legacy' }),
        }).catch(() => null)
      } catch {
        // Ignored — cleanup is best-effort.
      }
      if (!cancelled) setPhase((p) => (p === 'idle' ? 'cleared' : p))
    }
    void run()
    return () => { cancelled = true }
  }, [])

  // Coerce `cleared` back to `idle` once the visual sweep is over so the screen
  // shows the projector portrait again.
  useEffect(() => {
    if (phase === 'cleared') {
      const id = window.setTimeout(() => setPhase('idle'), 600)
      return () => window.clearTimeout(id)
    }
    return undefined
  }, [phase])

  // -------------------------------------------------------------------------
  // Voice library — open/refresh
  // -------------------------------------------------------------------------
  const refreshVoices = useCallback(async () => {
    setVoiceLoading(true)
    try {
      const list = await voiceLibraryList()
      setVoiceList(list)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setVoiceLoading(false)
    }
  }, [])

  useEffect(() => {
    if (voiceLibOpen) void refreshVoices()
  }, [voiceLibOpen, refreshVoices])

  const handleDeleteVoice = useCallback(async (slug: string) => {
    try {
      await voiceLibraryDelete(slug)
      await refreshVoices()
    } catch (e) {
      setError((e as Error).message)
    }
  }, [refreshVoices])

  const handleClearVoices = useCallback(async () => {
    try {
      await voiceLibraryClear()
      await refreshVoices()
    } catch (e) {
      setError((e as Error).message)
    }
  }, [refreshVoices])

  const handleImportVoice = useCallback(async (file: File, character: string, lang: string) => {
    if (!character.trim()) {
      setError('Donne un nom de personnage avant d importer.')
      return
    }
    try {
      const buf = new Uint8Array(await file.arrayBuffer())
      let bin = ''
      for (let i = 0; i < buf.byteLength; i++) bin += String.fromCharCode(buf[i])
      const wavBase64 = btoa(bin)
      await voiceRegister({ character, lang, source: `import:${file.name}`, wavBase64 })
      await refreshVoices()
    } catch (e) {
      setError(`Import voix echoue: ${(e as Error).message}`)
    }
  }, [refreshVoices])

  const handleExtractVoice = useCallback(async (character: string, query: string, lang: string) => {
    if (!character.trim() || !query.trim()) {
      setError('Donne un nom de personnage ET une requete YouTube.')
      return
    }
    try {
      const spawn = await voiceExtractRun({ character, query, lang })
      // Poll job — keeps light, no bridge UI here, just show status when done
      const startedAt = Date.now()
      const poll = async () => {
        const r = await fetch(`/api/python/job/${spawn.jobId}`).catch(() => null)
        if (!r || !r.ok) return false
        const data = await r.json() as { status: string; output?: string; error?: string }
        if (data.status === 'done') {
          await refreshVoices()
          if (data.error && data.error.length > 4) {
            setError(`Extraction voix: ${data.error.slice(0, 240)}`)
          }
          return true
        }
        if (Date.now() - startedAt > 15 * 60 * 1000) {
          setError('Extraction voix: timeout 15 min.')
          return true
        }
        return false
      }
      const tick = window.setInterval(async () => {
        const done = await poll()
        if (done) window.clearInterval(tick)
      }, 4000)
    } catch (e) {
      setError(`Extraction voix echoue: ${(e as Error).message}`)
    }
  }, [refreshVoices])

  // -------------------------------------------------------------------------
  // Storyboard generation
  // -------------------------------------------------------------------------

  const buildHints = (): Record<string, string> => {
    const hints: Record<string, string> = {}
    if (motionDir !== 'static') hints.motion = motionDir
    if (aspect) hints.aspect = aspect
    if (resolution !== 'auto') hints.resolution = resolution
    return hints
  }

  const handleStoryboard = useCallback(async () => {
    if (!scene.trim()) return
    setError(null)
    setClarification(null)
    setStoryboard(null)
    setPhase('storyboarding')
    try {
      // Anchor the storyboard with reference URLs from Aurora-Connect when
      // online: feed the LLM real images of the subject so each shot keeps
      // the visual identity (helmet color, face, clothing). Best-effort.
      let augmentedScene = scene
      try {
        const { searchReferenceImages } = await import('../services/auroraExtensionBridge')
        const refResult = await searchReferenceImages(scene.slice(0, 200), { limit: 3 })
        if (refResult.ok && refResult.data.length > 0) {
          const lines = ['', 'REFERENCES VISUELLES (Aurora-Connect):']
          for (const ref of refResult.data) {
            lines.push(`- ${ref.title || 'reference'}: ${ref.url}`)
          }
          lines.push('Garde l identite visuelle du sujet coherent avec ces references dans chaque shot.')
          augmentedScene = `${scene}\n${lines.join('\n')}`
        }
      } catch { /* extension grounding best-effort */ }

      const resp = await cinemaGenerateStoryboard(augmentedScene, buildHints(), mainModel)
      if (!resp.ok) {
        setError(resp.error || 'Storyboard refuse par le LLM.')
        setPhase('idle')
        return
      }
      if (resp.clarification) {
        setClarification(resp.clarification)
        setPhase('idle')
        return
      }
      if (!resp.storyboard) {
        setError('Le LLM n a renvoye ni storyboard ni clarification.')
        setPhase('idle')
        return
      }
      const sb = resp.storyboard
      // Apply user overrides on top of LLM-detected values
      if (resolution !== 'auto') sb.resolution = resolution
      if (aspect) sb.aspect = aspect
      sb.quality_mode = qualityMode
      setStoryboard(sb)
      setPhase('review')
    } catch (e) {
      setError((e as Error).message)
      setPhase('idle')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, motionDir, aspect, resolution, qualityMode])

  // -------------------------------------------------------------------------
  // Cinema pipeline launch + ETA polling
  // -------------------------------------------------------------------------

  const handleAction = useCallback(async () => {
    if (!storyboard) return
    setError(null)
    setEta(null)
    setProgressLabel('Demarrage du moteur...')
    setPhase('generating')
    cancelRef.current = { cancelled: false }
    try {
      const spawn = await cinemaGenerateRun(storyboard)
      const jobId = spawn.jobId
      const startedAt = Date.now()
      while (!cancelRef.current.cancelled) {
        await new Promise((r) => setTimeout(r, 2500))
        try {
          const status = await cinemaJobStatus(jobId)
          if (status.eta) setEta(status.eta)
          if (status.eta?.stage) setProgressLabel(status.eta.stage)
          if (status.status === 'done') {
            const r = status.result
            if (!r || r.ok === false) {
              setError(r?.error || status.error || 'Pipeline cinema echoue.')
              setPhase('idle')
              return
            }
            const path = r.video || status.outputPath || spawn.outputPath
            const clip: Clip = {
              id: `clip-${Date.now()}`,
              prompt: storyboard.title || scene,
              motion: motionDir,
              frames: storyboard.shots.reduce((acc, s) => acc + Math.round(s.duration_s * 24), 0),
              ts: Date.now(),
              videoUrl: localFileToBridgeUrl(path),
              videoPath: path,
              storyboard,
              durationS: r.actual_time_s,
            }
            setReel((prev) => [clip, ...prev].slice(0, 24))
            setActiveClipId(clip.id)
            setProgressLabel('')
            setEta(null)
            setPhase('idle')
            setStoryboard(null)
            return
          }
        } catch (e) {
          // transient; keep polling unless we've been at it for 2h
          if (Date.now() - startedAt > 2 * 60 * 60 * 1000) {
            throw e
          }
        }
      }
    } catch (e) {
      setError((e as Error).message)
      setPhase('idle')
    }
  }, [storyboard, scene, motionDir])

  const cut = () => {
    cancelRef.current.cancelled = true
    setPhase('idle')
    setEta(null)
    setProgressLabel('')
  }

  const SELECTED_DIR = MOTION_DIRS.find((d) => d.id === motionDir)
  const isRunning = phase === 'generating' || phase === 'storyboarding'

  // For the on-screen estimate row
  const estimateRes: '720p' | '1080p' | '1440p' = (() => {
    const r = (storyboard?.resolution || resolution || 'auto')
    if (r === '720p' || r === '1080p' || r === '1440p') return r
    return detectMobile() ? '720p' : '1080p'
  })()
  const estimateMin = storyboard ? estimateMinutes(storyboard.shots, storyboard.style, estimateRes) : 0

  return (
    <div className="mv-root">
      {/* Projector head */}
      <div className="mv-projector">
        <div className="mv-reels">
          <div className="mv-reel-wheel spin-left" aria-hidden="true" />
          <div className="mv-reel-wheel spin-right" aria-hidden="true" />
        </div>
        <div className="mv-brand">
          <Film size={14} strokeWidth={2.4} />
          <span>SALLE DE PROJECTION CINEMA · {who === 'natsu' ? 'NATSU' : 'LUCY'}</span>
        </div>
        <button
          type="button"
          className="mv-aspect-btn"
          style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}
          onClick={() => setVoiceLibOpen(true)}
          title="Bibliotheque de voix"
        >
          <Mic2 size={12} strokeWidth={2.4} /> VOIX
        </button>
      </div>

      {/* Main stage: screen + motion dial */}
      <div className="mv-stage">
        {/* Cinema screen */}
        <div className="mv-screen">
          <div className="mv-curtain mv-curtain-l" />
          <div className="mv-curtain mv-curtain-r" />
          <div className="mv-screen-frame">
            <AnimatePresence mode="wait">
              {phase === 'storyboarding' ? (
                <fm.div
                  key="storyboarding"
                  className="mv-screen-running"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                >
                  <div className="mv-slate">
                    <span className="mv-slate-title">STORYBOARD EN COURS…</span>
                    <span className="mv-slate-bar"><span className="mv-slate-bar-fill" style={{ width: '40%' }} /></span>
                    <div className="mv-slate-meta">
                      <span>LLM compose le plan</span>
                    </div>
                  </div>
                </fm.div>
              ) : phase === 'generating' ? (
                <fm.div
                  key="generating"
                  className="mv-screen-running"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                >
                  <div className="mv-slate">
                    <span className="mv-slate-title">PRISE EN COURS</span>
                    <span className="mv-slate-bar">
                      <span className="mv-slate-bar-fill" style={{ width: `${eta && eta.total > 0 ? Math.min(100, (eta.done / eta.total) * 100) : 5}%` }} />
                    </span>
                    <div className="mv-slate-meta">
                      <span>{progressLabel || 'rendu Wan2.2 + voix + lipsync'}</span>
                      <span>{eta ? `plan ${eta.done}/${eta.total}` : 'init'}</span>
                      <span>ETA {fmtSec(eta?.remaining_s)}</span>
                    </div>
                  </div>
                </fm.div>
              ) : phase === 'review' && storyboard ? (
                <fm.div
                  key="review"
                  className="mv-screen-clip"
                  initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  style={{ overflow: 'auto', alignItems: 'flex-start', textAlign: 'left', padding: '14px 16px' }}
                >
                  <StoryboardReview
                    storyboard={storyboard}
                    estimateMinutes={estimateMin}
                    estimateRes={estimateRes}
                    onChange={(sb) => setStoryboard(sb)}
                  />
                </fm.div>
              ) : activeClip && activeClip.videoUrl ? (
                <fm.div
                  key={activeClip.id}
                  className="mv-screen-clip"
                  initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                  style={{ padding: 0 }}
                >
                  <video
                    src={activeClip.videoUrl}
                    controls
                    playsInline
                    style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
                  />
                  <div className="mv-screen-meta" style={{ position: 'absolute', bottom: 12, left: 12 }}>
                    <span className="mv-screen-chip">{activeClip.storyboard?.style ?? activeClip.motion}</span>
                    <span className="mv-screen-chip">{activeClip.storyboard?.resolution ?? estimateRes}</span>
                    {activeClip.videoPath ? (
                      <a
                        href={activeClip.videoUrl}
                        download={`cinema-${activeClip.id}.mp4`}
                        className="mv-screen-chip"
                        style={{ textDecoration: 'none' }}
                        title="Telecharger"
                      >
                        <Download size={11} strokeWidth={2.4} /> MP4
                      </a>
                    ) : null}
                  </div>
                </fm.div>
              ) : (
                <fm.div
                  key="idle"
                  className="mv-screen-idle"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                >
                  <img src={PORTRAITS[who]} alt={who} className="mv-screen-portrait" />
                  <div className="mv-screen-banner">
                    {who === 'natsu' ? 'MOTEUR ! ÇA VA CHAUFFER' : 'LUMIERE STELLAIRE ! MOTEUR'}
                  </div>
                </fm.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Motion dial (kept visual, contributes a hint to storyboard) */}
        <div className="mv-dial">
          <div className="mv-dial-head">
            <span className="mv-dial-title">MOTION</span>
            <span className="mv-dial-value">{SELECTED_DIR?.label ?? motionDir.toUpperCase()}</span>
          </div>
          <div className="mv-dial-ring">
            <button
              type="button"
              className={`mv-dial-center ${motionDir === 'static' ? 'is-active' : ''}`}
              onClick={() => setMotionDir('static')}
              title="Plan fixe"
              disabled={isRunning}
            >
              <span className="mv-dial-center-label">STATIC</span>
              <span className="mv-dial-center-sub">plan fixe</span>
            </button>
            {MOTION_DIRS.map((d) => {
              const Icon = d.icon
              const r = 96
              const angle = (d.angle * Math.PI) / 180
              const x = Math.cos(angle) * r
              const y = Math.sin(angle) * r
              return (
                <button
                  key={d.id}
                  type="button"
                  className={`mv-dial-btn ${motionDir === d.id ? 'is-active' : ''}`}
                  onClick={() => setMotionDir(d.id)}
                  style={{ left: `calc(50% + ${x}px)`, top: `calc(50% + ${y}px)` }}
                  title={d.label}
                  disabled={isRunning}
                >
                  <Icon size={14} strokeWidth={2.4} />
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Sparkles input (bottom action bar) */}
      <div className="mv-clap">
        <div className="mv-clap-slate">
          <div className="mv-clap-slate-stripes" />
          <div className="mv-clap-info">
            <div className="mv-clap-kicker">SCENE #{reel.length + 1}</div>
            <div className="mv-clap-meta">
              <span>TAKE {reel.length + 1}</span>
              <span>·</span>
              <span>{SELECTED_DIR?.label ?? 'STATIC'}</span>
              <span>·</span>
              <span title={activeAspect.hint}>{activeAspect.label} {activeAspect.w}×{activeAspect.h}</span>
              <span>·</span>
              <span>{resolution.toUpperCase()}</span>
              {storyboard ? (
                <>
                  <span>·</span>
                  <span title={`${storyboard.shots.length} plans, style ${storyboard.style}`}>
                    {storyboard.shots.length} plan(s) · ~{estimateMin}m
                  </span>
                </>
              ) : null}
            </div>
            <div className="mv-aspect-row" role="radiogroup" aria-label="Aspect ratio">
              {ASPECT_PRESETS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  role="radio"
                  aria-checked={aspect === a.id}
                  className={`mv-aspect-btn ${aspect === a.id ? 'is-on' : ''}`}
                  onClick={() => setAspect(a.id)}
                  title={`${a.label} · ${a.hint}`}
                  disabled={isRunning}
                >
                  {a.label}
                </button>
              ))}
              <span style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.18)', margin: '0 4px' }} />
              {RES_PRESETS.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={`mv-aspect-btn ${resolution === r.id ? 'is-on' : ''}`}
                  onClick={() => setResolution(r.id)}
                  title={`${r.label} · ${r.hint}`}
                  disabled={isRunning}
                >
                  {r.label}
                </button>
              ))}
              <span style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.18)', margin: '0 4px' }} />
              {(['auto', 'balanced', 'premium'] as const).map((q) => (
                <button
                  key={q}
                  type="button"
                  className={`mv-aspect-btn ${qualityMode === q ? 'is-on' : ''}`}
                  onClick={() => setQualityMode(q)}
                  title={q === 'premium' ? 'Q6_K + offload' : q === 'balanced' ? 'Q4_K_M rapide' : 'Selectionne par hardware'}
                  disabled={isRunning}
                >
                  {q.toUpperCase()}
                </button>
              ))}
            </div>
            {error ? (
              <div style={{ marginTop: 6, color: '#fca5a5', fontSize: 11, lineHeight: 1.4 }}>
                {error}
              </div>
            ) : null}
            {clarification ? (
              <div style={{ marginTop: 6, color: '#fcd34d', fontSize: 11, lineHeight: 1.4 }}>
                Clarification demandee : {clarification}
              </div>
            ) : null}
          </div>
        </div>
        <textarea
          className="mv-clap-input"
          rows={2}
          placeholder={who === 'natsu'
            ? 'Decris ta scene Pixar/anime/realiste : sujet, action, dialogue, ambiance.'
            : 'Decris ta scene : decor, personnages, action, dialogue (le LLM detecte le style).'}
          value={scene}
          onChange={(e) => setScene(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void handleStoryboard() }
          }}
          disabled={isRunning}
        />
        <div className="mt-2 flex items-center gap-2">
          <VoicePushToTalk
            onTranscript={(t) => setScene((prev) => (prev?.trim() ? `${prev}, ${t}` : t))}
            label="Dicter la scène vidéo"
            size={30}
            variant="ghost"
          />
          <span style={{ fontSize: 11, opacity: 0.55 }}>Dicte ta scène.</span>
        </div>
        <div className="mv-clap-side">
          {phase === 'review' && storyboard ? (
            <button type="button" className="mv-action" onClick={handleAction}>
              <Sparkles size={16} strokeWidth={2.4} /> {who === 'natsu' ? 'MOTEUR !' : 'ACTION !'}
            </button>
          ) : isRunning ? (
            <button type="button" className="mv-action is-stop" onClick={cut}>
              <StopCircle size={16} strokeWidth={2.4} /> CUT !
            </button>
          ) : (
            <button type="button" className="mv-action" onClick={() => void handleStoryboard()} disabled={!scene.trim()}>
              <Sparkles size={16} strokeWidth={2.4} /> STORYBOARD
            </button>
          )}
          <button type="button" className="mv-keyframe-toggle"
            onClick={() => setVoiceLibOpen(true)}
            title="Bibliotheque de voix">
            <Library size={13} strokeWidth={2.4} /> Voix ({voiceList.length})
          </button>
          <button type="button" className="mv-keyframe-toggle"
            onClick={() => setKeyframeOpen((v) => !v)}
            title="Editer les keyframes (timeline multi-shot)">
            <Layers size={13} strokeWidth={2.4} /> {keyframeOpen ? 'Fermer' : 'Keyframes'}{keyframes.length > 0 ? ` (${keyframes.length})` : ''}
          </button>
        </div>

        {keyframeOpen && (
          <Suspense fallback={null}>
            <VideoKeyframeEditor
              value={keyframes}
              onChange={setKeyframes}
              duration={videoDuration}
              onDurationChange={setVideoDuration}
            />
          </Suspense>
        )}
      </div>

      {/* Film reel strip (bottom collection) */}
      <div className="mv-film">
        <div className="mv-film-head">
          <Film size={13} strokeWidth={2.4} />
          <span>BOBINE · {reel.length}</span>
        </div>
        {reel.length === 0 ? (
          <div className="mv-film-empty">— bobine vierge —</div>
        ) : (
          <div className="mv-film-strip">
            {reel.map((c, i) => (
              <button
                key={c.id}
                type="button"
                className={`mv-film-cell ${activeClipId === c.id ? 'is-active' : ''}`}
                onClick={() => setActiveClipId(c.id)}
                title={c.prompt}
              >
                <div className="mv-film-cell-num">#{String(i + 1).padStart(2, '0')}</div>
                <div className="mv-film-cell-dir">{c.storyboard?.style ?? c.motion}</div>
                <div className="mv-film-cell-prompt">{c.prompt}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {voiceLibOpen ? (
        <VoiceLibraryDrawer
          voices={voiceList}
          loading={voiceLoading}
          onClose={() => setVoiceLibOpen(false)}
          onRefresh={() => void refreshVoices()}
          onDelete={(slug) => void handleDeleteVoice(slug)}
          onClearAll={() => void handleClearVoices()}
          onImport={(file, character, lang) => void handleImportVoice(file, character, lang)}
          onExtract={(character, query, lang) => void handleExtractVoice(character, query, lang)}
        />
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Storyboard review — shown on the cinema screen between "Storyboard" and
// "Action !". The user can tweak duration / dialogue inline before validating.
// ---------------------------------------------------------------------------

function StoryboardReview({
  storyboard, estimateMinutes, estimateRes, onChange,
}: {
  storyboard: Storyboard
  estimateMinutes: number
  estimateRes: string
  onChange: (sb: Storyboard) => void
}) {
  const updateShot = (idx: number, patch: Partial<CinemaShot>) => {
    const next = { ...storyboard, shots: storyboard.shots.map((s, i) => i === idx ? { ...s, ...patch } : s) }
    onChange(next)
  }
  return (
    <div style={{ width: '100%', color: '#f5f5f4', fontFamily: 'inherit' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, letterSpacing: '0.04em' }}>{storyboard.title || 'Sans titre'}</h3>
        <span style={{ opacity: 0.7, fontSize: 11 }}>
          {storyboard.style} · {storyboard.aspect} · {estimateRes} · ~{estimateMinutes}m
        </span>
      </div>
      <p style={{ margin: '0 0 10px', opacity: 0.85, fontSize: 12, lineHeight: 1.5 }}>{storyboard.summary}</p>
      {storyboard.characters.length ? (
        <div style={{ marginBottom: 8, fontSize: 11, opacity: 0.85 }}>
          <strong>Personnages : </strong>
          {storyboard.characters.map((c) => `${c.name} (${c.voice_lang})`).join(' · ')}
        </div>
      ) : null}
      <div style={{ display: 'grid', gap: 6 }}>
        {storyboard.shots.map((shot, idx) => (
          <div key={shot.id} style={{
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 8,
            padding: '6px 8px',
            background: 'rgba(255,255,255,0.04)',
            fontSize: 11,
            display: 'grid',
            gap: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontWeight: 700 }}>#{shot.id}</span>
              <span style={{ opacity: 0.6 }}>{shot.camera}</span>
              <input
                type="number"
                min={3}
                max={8}
                step={1}
                value={shot.duration_s}
                onChange={(e) => updateShot(idx, { duration_s: Number(e.target.value) })}
                style={{ width: 56, marginLeft: 'auto', background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit' }}
              />
              <span style={{ opacity: 0.6 }}>s</span>
            </div>
            <div style={{ opacity: 0.9 }}>{shot.scene}</div>
            {shot.dialogue ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                <span style={{ opacity: 0.6, minWidth: 70 }}>{shot.speaker || '—'}</span>
                <input
                  type="text"
                  value={shot.dialogue}
                  onChange={(e) => updateShot(idx, { dialogue: e.target.value })}
                  style={{ flex: 1, background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit' }}
                />
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Voice library drawer
// ---------------------------------------------------------------------------

function VoiceLibraryDrawer({
  voices, loading, onClose, onRefresh, onDelete, onClearAll, onImport, onExtract,
}: {
  voices: VoiceLibraryEntry[]
  loading: boolean
  onClose: () => void
  onRefresh: () => void
  onDelete: (slug: string) => void
  onClearAll: () => void
  onImport: (file: File, character: string, lang: string) => void
  onExtract: (character: string, query: string, lang: string) => void
}) {
  const [importChar, setImportChar] = useState('')
  const [importLang, setImportLang] = useState<'fr' | 'en'>('fr')
  const [extractChar, setExtractChar] = useState('')
  const [extractQuery, setExtractQuery] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onImport(file, importChar, importLang)
    e.target.value = ''
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 60,
      background: 'rgba(8, 6, 14, 0.78)',
      display: 'flex', justifyContent: 'flex-end',
      backdropFilter: 'blur(4px)',
    }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        width: 'min(420px, 100vw)', height: '100vh',
        background: '#0d0a18', color: '#f5f5f4',
        padding: 16, overflowY: 'auto',
        borderLeft: '1px solid rgba(255,255,255,0.1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h3 style={{ margin: 0, fontSize: 14, letterSpacing: '0.06em' }}>BIBLIOTHEQUE DE VOIX</h3>
          <button type="button" onClick={onClose} style={{ background: 'transparent', color: '#f5f5f4', border: 'none', cursor: 'pointer', padding: 4 }} aria-label="Fermer">
            <X size={16} />
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, fontSize: 11 }}>
          <button type="button" onClick={onRefresh} className="mv-aspect-btn">{loading ? '…' : 'Rafraichir'}</button>
          <button type="button" onClick={onClearAll} className="mv-aspect-btn" title="Vider tout le cache de voix">
            <Trash2 size={12} strokeWidth={2.4} /> Vider cache
          </button>
        </div>

        <div style={{ display: 'grid', gap: 6, marginBottom: 14 }}>
          {voices.length === 0 ? (
            <div style={{ opacity: 0.6, fontSize: 11 }}>Aucune voix enregistree.</div>
          ) : voices.map((v) => (
            <div key={v.slug} style={{
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 6, padding: '6px 8px',
              display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
            }}>
              <span style={{ flex: 1, fontWeight: 600 }}>{v.character}</span>
              <span style={{ opacity: 0.6 }}>{v.lang}</span>
              <span style={{ opacity: 0.6 }}>{v.duration_s ? `${Math.round(v.duration_s)}s` : '—'}</span>
              <button type="button" onClick={() => onDelete(v.slug)} className="mv-aspect-btn" aria-label={`Supprimer ${v.character}`}>
                <Trash2 size={11} strokeWidth={2.4} />
              </button>
            </div>
          ))}
        </div>

        <h4 style={{ margin: '14px 0 6px', fontSize: 12, letterSpacing: '0.04em', opacity: 0.85 }}>IMPORTER UN WAV</h4>
        <p style={{ margin: '0 0 6px', fontSize: 11, opacity: 0.7, lineHeight: 1.4 }}>
          Recommande : 15–30s, mono ou stereo, 16 kHz ou plus. Formats : .wav, .mp3, .m4a, .flac.
        </p>
        <div style={{ display: 'grid', gap: 6, marginBottom: 14 }}>
          <input
            type="text"
            placeholder="Nom du personnage (ex: Mecano)"
            value={importChar}
            onChange={(e) => setImportChar(e.target.value)}
            style={{ background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, padding: '4px 8px', fontFamily: 'inherit', fontSize: 12 }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            {(['fr', 'en'] as const).map((l) => (
              <button key={l} className={`mv-aspect-btn ${importLang === l ? 'is-on' : ''}`} onClick={() => setImportLang(l)}>{l.toUpperCase()}</button>
            ))}
          </div>
          <input ref={fileRef} type="file" accept="audio/*,.wav,.mp3,.m4a,.flac" onChange={onFile} style={{ display: 'none' }} />
          <button type="button" className="mv-action" onClick={() => fileRef.current?.click()} style={{ width: '100%' }}>
            <Upload size={12} strokeWidth={2.4} /> Importer un fichier audio
          </button>
        </div>

        <h4 style={{ margin: '6px 0 6px', fontSize: 12, letterSpacing: '0.04em', opacity: 0.85 }}>OU EXTRAIRE DEPUIS YOUTUBE</h4>
        <div style={{ display: 'grid', gap: 6 }}>
          <input
            type="text"
            placeholder="Nom du personnage (ex: Natsu)"
            value={extractChar}
            onChange={(e) => setExtractChar(e.target.value)}
            style={{ background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, padding: '4px 8px', fontFamily: 'inherit', fontSize: 12 }}
          />
          <input
            type="text"
            placeholder="Recherche YouTube (ex: Natsu Fairy Tail VF)"
            value={extractQuery}
            onChange={(e) => setExtractQuery(e.target.value)}
            style={{ background: 'rgba(0,0,0,0.3)', color: '#fff', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, padding: '4px 8px', fontFamily: 'inherit', fontSize: 12 }}
          />
          <button
            type="button" className="mv-action"
            onClick={() => onExtract(extractChar, extractQuery, importLang)}
            disabled={!extractChar.trim() || !extractQuery.trim()}
            style={{ width: '100%' }}
          >
            <Loader2 size={12} strokeWidth={2.4} /> Lancer l extraction
          </button>
        </div>
      </div>
    </div>
  )
}
