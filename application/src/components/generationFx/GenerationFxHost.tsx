import { bridgeFetch as fetch } from '../../utils/bridgeAuth.ts'
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../../stores/appStore.ts'
import { useCodeStreamStore } from '../../stores/codeStreamStore.ts'
import type { GenerationJobState, ModuleId } from '../../types/app.ts'
import { FX_EVENT, FX_PREF_EVENT, generationFxEnabled, type FxAsk, type FxCounters, type FxModule, type FxPatch, type FxRef, fxAnswer, markFxHostMounted } from './fxBus.ts'
import { watchComfyProgress } from './comfyProgress.ts'
import AuroraMascot, { FX_AGENTS, MASCOT_STATE_LABEL, type MascotState } from './mascots.tsx'
import { FX_SCENES, type SceneDraw, type SceneSync } from './scenes.ts'
import { animationProgress, codePhaseIndex, mascotStateFor, resolvePhaseIndex, stageForJob, type FxStage } from './fxPhases.ts'
import type { HologramStatus } from './HologramStage.tsx'
import {
  EtaCountdown,
  RunTimeline,
  accuracyLabel,
  calibrateEstimate,
  comparableRuns,
  estimateRemaining,
  etaAccuracy,
  etaHeadline,
  etaInterval,
  formatClock,
  formatWait,
  recordCompletedRun,
  recordEtaOutcome,
  type ComparableRuns,
  type EtaAccuracy,
  type EtaEstimate,
  type EtaSnapshot,
  type QueueInfo,
} from '../../services/generationTiming.ts'

// WebGL uniquement quand un écran 3D s'affiche : les autres modules ne chargent pas three.js.
const HologramStage = lazy(() => import('./HologramStage.tsx'))

const REVEAL_MS = 2600
/** une opération plus courte ne déclenche pas d'écran (pas de flash) */
const SHOW_DELAY_MS = 600
const RECENT_SESSION_MS = 180_000
/**
 * Modules dont le pourcentage reçu n'est qu'un jalon grossier (la 3D passe à
 * 82–95 % dès le démarrage du pipeline Python) : l'écran affiche l'étape réelle
 * plutôt qu'un pourcentage trompeur.
 */
const COARSE_PERCENT = new Set<FxModule>(['3d'])
const measuredFor = (module: FxModule, tl: RunTimeline, now: number): number | null =>
  tl.measured && !COARSE_PERCENT.has(module) ? tl.progressAt(now) : null

type FxEntry = {
  phase?: string
  phaseIdx: number
  progress?: number
  startedAt: number
  reveal?: { url: string; kind: 'image' | 'video' | 'mesh'; at: number }
  refs?: FxRef[]
  logLines?: string[]
  counters?: FxCounters
  meshUrl?: string
  meshInfo?: string
  ask?: FxAsk | null
}

type Session = {
  module: FxModule
  tl: RunTimeline
  explicitPhase: boolean
  revealContent: boolean
  autoMinimized: boolean
  endedAt: number | null
  success: boolean
  /** prédictions notées pendant le run, comparées au temps réel à la fin */
  snapshots: EtaSnapshot[]
  lastSnapshotAt: number
}

const SNAPSHOT_EVERY_MS = 10_000

let historyVersion = 0
const historyCache = new Map<string, { v: number; at: number; value: ComparableRuns }>()
function historyFor(module: string, model: string | null | undefined): ComparableRuns {
  const key = `${module}|${model ?? ''}`
  const hit = historyCache.get(key)
  if (hit && hit.v === historyVersion && Date.now() - hit.at < 5000) return hit.value
  const value = comparableRuns(module, model)
  historyCache.set(key, { v: historyVersion, at: Date.now(), value })
  return value
}

const countdowns = new Map<FxModule, EtaCountdown>()
const accuracyCache = new Map<string, { v: number; at: number; value: EtaAccuracy | null }>()
function accuracyFor(module: string): EtaAccuracy | null {
  const hit = accuracyCache.get(module)
  if (hit && hit.v === historyVersion && Date.now() - hit.at < 5000) return hit.value
  const value = etaAccuracy(module)
  accuracyCache.set(module, { v: historyVersion, at: Date.now(), value })
  return value
}

type TimingView = {
  est: EtaEstimate
  headline: string
  interval: string | null
  elapsedMs: number
  queue: QueueInfo | null
  /** précision mesurée sur les vraies générations précédentes du module */
  accuracy: string | null
}

function computeTiming(module: FxModule, s: Session, job: GenerationJobState | null, now: number, done: boolean): TimingView {
  const sched = job?.scheduling ?? null
  const queued = job?.status === 'queued'
  const queue: QueueInfo | null = queued
    ? { position: sched?.queue_position || 1, aheadCount: sched?.ahead_count ?? 0, waitSec: sched?.wait_seconds ?? null }
    : null
  const runStartedAt = queued ? null : job?.startedAt ?? s.tl.startedAt
  const { runs, basis } = historyFor(module, job?.model)
  const acc = accuracyFor(module)
  const rawEst = estimateRemaining({
    now,
    runStartedAt,
    phaseIdx: s.tl.phaseIdx,
    phaseCount: s.tl.phaseCount,
    phaseStartedAt: runStartedAt != null ? Math.max(s.tl.phaseStartedAt, runStartedAt) : null,
    overall: s.tl.overall,
    phase: s.tl.phase,
    runs,
    historyBasis: basis,
    server: sched
      ? { medianTotalSec: sched.estimated_duration_seconds, remainingSec: sched.remaining_seconds, sampleCount: sched.estimate_sample_count }
      : null,
    queue,
    done,
  })
  const est = calibrateEstimate(rawEst, acc)
  // prédiction notée toutes les 10 s : comparée au temps qui restait vraiment à la fin du run
  if (
    !done && runStartedAt != null && est.remainingMs != null &&
    ['history', 'blended', 'live', 'partial'].includes(est.state) && now - s.lastSnapshotAt >= SNAPSHOT_EVERY_MS
  ) {
    s.lastSnapshotAt = now
    s.snapshots.push({ elapsedMs: now - runStartedAt, remainingMs: est.remainingMs, lowMs: est.lowMs, highMs: est.highMs })
    if (s.snapshots.length > 60) s.snapshots.splice(0, s.snapshots.length - 60)
  }
  let cd = countdowns.get(module)
  if (!cd) {
    cd = new EtaCountdown()
    countdowns.set(module, cd)
  }
  const shown = cd.update(est, now)
  return {
    est,
    headline: etaHeadline(est, shown, queue),
    interval: etaInterval(est),
    elapsedMs: runStartedAt != null ? Math.max(0, now - runStartedAt) : 0,
    queue,
    accuracy: accuracyLabel(acc),
  }
}

function updateCounters(prev: FxCounters | undefined, line: string): FxCounters | undefined {
  const l = line.toLowerCase()
  const c: FxCounters = { ...(prev ?? {}) }
  let touched = false
  if (/photo .*(validee|valide)\b/.test(l)) { c.photosValidees = (c.photosValidees ?? 0) + 1; touched = true }
  if (/photo .*(rejetee|ignoree|ecartee)/.test(l)) { c.photosRejetees = (c.photosRejetees ?? 0) + 1; touched = true }
  const tent = l.match(/tentative[^0-9]*(\d+)/)
  if (tent) { c.meshTentatives = Math.max(c.meshTentatives ?? 0, parseInt(tent[1], 10)); touched = true }
  if (/nouvelle passe|regeneration|_r\d\b/.test(l)) { c.meshTentatives = (c.meshTentatives ?? 1) + 1; touched = true }
  if (/trellis|hunyuan|geometrie/.test(l) && (c.meshTentatives ?? 0) === 0) { c.meshTentatives = 1; touched = true }
  return touched ? c : prev
}

function hexA(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a))})`
}

/** Couche commune à toutes les scènes : elle rend visibles les vrais événements. */
function drawSyncLayer(ctx: CanvasRenderingContext2D, W: number, H: number, accent: string, sync: SceneSync) {
  if (sync.phaseIdx > 0 && sync.phaseAge < 1400) {
    const t = sync.phaseAge / 1400
    ctx.save()
    ctx.globalCompositeOperation = 'lighter'
    ctx.strokeStyle = hexA(accent, 0.5 * (1 - t))
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(W / 2, H * 0.42, (0.06 + t * 0.62) * Math.max(W, H), 0, Math.PI * 2)
    ctx.stroke()
    const x = W * t
    const g = ctx.createLinearGradient(x - 90, 0, x + 90, 0)
    g.addColorStop(0, 'rgba(0,0,0,0)')
    g.addColorStop(0.5, hexA(accent, 0.16 * (1 - t)))
    g.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = g
    ctx.fillRect(x - 90, 0, 180, H)
    ctx.restore()
  }
  if (sync.pulseAge >= 0 && sync.pulseAge < 650) {
    const t = sync.pulseAge / 650
    ctx.save()
    ctx.strokeStyle = hexA(accent, 0.32 * (1 - t))
    ctx.lineWidth = 2 + 6 * (1 - t)
    ctx.strokeRect(1, 1, W - 2, H - 2)
    ctx.restore()
  }
  if (sync.stage === 'queued') {
    ctx.fillStyle = 'rgba(4,6,11,.48)'
    ctx.fillRect(0, 0, W, H)
  }
}

type FrameRead = { prog: number; sync: SceneSync }

function FxCanvas({ module, read, ambientOnly = false }: { module: FxModule; read: () => FrameRead; ambientOnly?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const readRef = useRef(read)
  readRef.current = read
  const ambientRef = useRef(ambientOnly)
  ambientRef.current = ambientOnly
  useEffect(() => {
    const cv = canvasRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const accent = FX_AGENTS[module].accent
    const draw: SceneDraw = FX_SCENES[module].create()
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let W = 0
    let H = 0
    const size = () => {
      W = cv.clientWidth
      H = cv.clientHeight
      cv.width = Math.max(1, W * dpr)
      cv.height = Math.max(1, H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    size()
    const ro = new ResizeObserver(size)
    ro.observe(cv)
    let alive = true
    let raf = 0
    let last = 0
    const stars: { x: number; y: number; r: number; p: number; s: number }[] = []
    for (let i = 0; i < 55; i++) stars.push({ x: Math.random(), y: Math.random(), r: Math.random() * 1.2 + 0.3, p: Math.random() * 6.28, s: 0.5 + Math.random() * 1.5 })
    const frame = (now: number) => {
      if (!alive || !cv.isConnected) { ro.disconnect(); return }
      raf = requestAnimationFrame(frame)
      // ≤ ~60 images/s : même vitesse d'animation sur écran 120/144 Hz, GPU laissé au moteur
      if (now - last < 15) return
      last = now
      const { prog, sync } = readRef.current()
      ctx.clearRect(0, 0, W, H)
      const g1 = ctx.createRadialGradient(W * 0.25, H * 0.2, 0, W * 0.25, H * 0.2, W * 0.6)
      g1.addColorStop(0, hexA(accent, 0.09))
      g1.addColorStop(1, hexA(accent, 0))
      ctx.fillStyle = g1
      ctx.fillRect(0, 0, W, H)
      const g2 = ctx.createRadialGradient(W * 0.8, H * 0.75, 0, W * 0.8, H * 0.75, W * 0.55)
      g2.addColorStop(0, hexA(accent, 0.055))
      g2.addColorStop(1, hexA(accent, 0))
      ctx.fillStyle = g2
      ctx.fillRect(0, 0, W, H)
      for (const st of stars) {
        ctx.globalAlpha = 0.22 + 0.5 * (0.5 + 0.5 * Math.sin(now * 0.001 * st.s + st.p))
        ctx.fillStyle = '#CFE3FF'
        ctx.beginPath()
        ctx.arc(st.x * W, st.y * H, st.r, 0, 6.2832)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      // derrière l'hologramme WebGL, seule l'ambiance est dessinée (GPU laissé au moteur)
      if (!ambientRef.current) {
        try { draw(ctx, W, H, now, prog, accent, sync) } catch { /* scène isolée */ }
      }
      drawSyncLayer(ctx, W, H, accent, sync)
      const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75)
      vg.addColorStop(0, 'rgba(0,0,0,0)')
      vg.addColorStop(1, 'rgba(0,0,0,.4)')
      ctx.fillStyle = vg
      ctx.fillRect(0, 0, W, H)
    }
    raf = requestAnimationFrame(frame)
    return () => { alive = false; cancelAnimationFrame(raf); ro.disconnect() }
  }, [module])
  return <canvas ref={canvasRef} aria-hidden="true" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
}

const ROLE_LABELS: Record<string, string> = {
  face: 'FACE', trois_quarts: '3/4', dos: 'DOS', gauche: 'GAUCHE', droite: 'DROITE',
  haut: 'HAUT', bas: 'BAS', extra: 'VUE +', inconnu: 'VUE',
}

function RefsPanel({ refs, accent, narrow }: { refs: FxRef[]; accent: string; narrow: boolean }) {
  if (narrow) {
    return (
      <div style={{ position: 'absolute', left: 12, right: 12, top: 66, display: 'flex', gap: 8, overflowX: 'auto', pointerEvents: 'none', zIndex: 1 }}>
        {refs.map((r, i) => (
          <img key={`${r.url}-${i}`} src={r.url} alt={r.role} style={{ height: 54, borderRadius: 8, border: `1px solid ${accent}55`, background: 'rgba(255,255,255,.03)' }} />
        ))}
      </div>
    )
  }
  return (
    <div style={{
      position: 'absolute', left: 48, top: 72, bottom: 190, width: 200,
      display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto',
      pointerEvents: 'none',
    }}>
      <span style={{ fontSize: 10, letterSpacing: '.28em', color: '#8B93A7', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
        RÉFÉRENCES{refs.length > 1 ? ` · MULTI-VUES (${refs.length})` : ''}
      </span>
      {refs.map((r, i) => (
        <div key={`${r.url}-${i}`} style={{ position: 'relative', borderRadius: 12, overflow: 'hidden', border: `1px solid ${accent}44`, background: 'rgba(255,255,255,.03)' }}>
          <img src={r.url} alt={r.role} style={{ width: '100%', display: 'block', objectFit: 'contain', maxHeight: 150 }} />
          <span style={{
            position: 'absolute', left: 8, top: 8, fontSize: 10, fontWeight: 700,
            padding: '3px 8px', borderRadius: 999, letterSpacing: '.14em',
            background: 'rgba(4,6,11,.8)', border: `1px solid ${accent}88`, color: '#fff',
            fontFamily: "'Cascadia Code',Consolas,monospace",
          }}>{ROLE_LABELS[r.role] ?? r.role.toUpperCase()}</span>
        </div>
      ))}
    </div>
  )
}

function CenterStage({ entry, accent, tl, done, narrow }: { entry: FxEntry; accent: string; tl: RunTimeline; done: boolean; narrow: boolean }) {
  const [status, setStatus] = useState<HologramStatus | null>(null)
  const c = entry.counters ?? {}
  const feed = (entry.logLines ?? []).slice(-6)
  const lastReject = [...(entry.logLines ?? [])].reverse().find((l) => /rejet|ecart|ignor/i.test(l))
  const quality: 'high' | 'low' = narrow || (typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches) ? 'low' : 'high'
  const label = done
    ? 'MODÈLE PRÊT — GÉOMÉTRIE RÉELLE VERROUILLÉE'
    : status?.source === 'mesh'
      ? 'HOLOGRAMME — MAILLAGE RÉEL EN MATÉRIALISATION'
      : status?.source === 'parts'
        ? 'HOLOGRAMME — PIÈCES STL MESURÉES'
        : status && status.source !== 'emitter'
          ? 'HOLOGRAMME — RECONSTRUIT DEPUIS LES VUES DE LA DEMANDE'
          : 'ÉMETTEUR HOLOGRAPHIQUE — EN ATTENTE DES VUES DE RÉFÉRENCE'
  const meshUrl = entry.meshUrl ?? (entry.reveal?.kind === 'mesh' ? entry.reveal.url : null)
  return (
    <div style={{
      position: 'absolute',
      left: narrow ? 12 : entry.refs?.length ? 280 : 48,
      right: narrow ? 12 : 232,
      top: narrow ? (entry.refs?.length ? 128 : 66) : 60,
      bottom: narrow ? 236 : 190,
      display: 'flex', flexDirection: 'column', pointerEvents: 'auto',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 10, letterSpacing: '.24em', color: '#8B93A7', fontFamily: "'Cascadia Code',Consolas,monospace" }}>{label}</span>
        <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            { lab: 'photos ✓', val: c.photosValidees ?? 0, col: '#4ADE80' },
            { lab: 'photos ✗', val: c.photosRejetees ?? 0, col: '#F87171' },
            { lab: 'essai mesh', val: c.meshTentatives ?? 0, col: accent },
            { lab: 'GLB', val: meshUrl ? 1 : 0, col: meshUrl ? '#4ADE80' : '#8B93A7' },
          ].map((k) => (
            <span key={k.lab} style={{
              fontSize: 10, padding: '4px 10px', borderRadius: 999,
              border: `1px solid ${k.col}55`, color: '#E6EAF5', background: 'rgba(4,6,11,.6)',
              fontFamily: "'Cascadia Code',Consolas,monospace",
            }}><b style={{ color: k.col, fontSize: 12 }}>{k.val}</b> {k.lab}</span>
          ))}
        </span>
      </div>
      <div style={{
        position: 'relative', flex: 1, minHeight: 160, borderRadius: 16, overflow: 'hidden',
        border: `1px solid ${accent}33`,
        background: `radial-gradient(ellipse at 50% 85%, ${hexA(accent, 0.12)}, rgba(3,5,10,.92) 62%)`,
      }}>
        <Suspense fallback={<div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#5A6377', fontSize: 11 }}>Initialisation de l’émetteur…</div>}>
          <HologramStage
            accent={accent}
            phaseIdx={done ? tl.phaseCount - 1 : tl.phaseIdx}
            phaseCount={tl.phaseCount}
            readProgress={() => (done ? 1 : tl.phaseIdx / tl.phaseCount)}
            readPulseAt={() => tl.lastEventAt}
            refs={entry.refs}
            meshUrl={meshUrl}
            done={done}
            quality={quality}
            interactive
            onStatus={setStatus}
          />
        </Suspense>
        {status?.note && (
          <div style={{
            position: 'absolute', left: 12, bottom: 10, right: 12, fontSize: 10.5, color: '#B7C0D4',
            fontFamily: "'Cascadia Code',Consolas,monospace", pointerEvents: 'none', textShadow: '0 1px 6px #000',
          }}>
            {status.note}{entry.meshInfo && status.source === 'mesh' ? ` · ${entry.meshInfo}` : ''}
          </div>
        )}
        {!done && (
          <div style={{ position: 'absolute', right: 12, top: 10, fontSize: 10, color: '#7C869C', pointerEvents: 'none' }}>
            glisser pour tourner
          </div>
        )}
        {done && (
          <div style={{
            position: 'absolute', left: '50%', top: 16, transform: 'translateX(-50%)', padding: '6px 14px', borderRadius: 999,
            fontSize: 12, letterSpacing: '.2em', color: '#4ADE80', border: '1px solid rgba(74,222,128,.5)', background: 'rgba(4,10,8,.75)',
            fontFamily: "'Cascadia Code',Consolas,monospace", animation: 'aurora-fx-reveal-bg .4s ease',
          }}>✓ MODÈLE PRÊT</div>
        )}
      </div>
      {lastReject && (
        <div style={{
          marginTop: 6, fontSize: 10, color: '#F87171', whiteSpace: 'nowrap', overflow: 'hidden',
          textOverflow: 'ellipsis', fontFamily: "'Cascadia Code',Consolas,monospace",
        }}>dernier rejet : {lastReject.replace(/^PROGRESS:[a-z_]*:?/i, '')}</div>
      )}
      {!narrow && (
        <div style={{
          marginTop: 6, height: 86, overflow: 'hidden', borderRadius: 10,
          border: '1px solid rgba(255,255,255,.07)', background: 'rgba(0,0,0,.32)',
          padding: '8px 12px', fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 10.5,
          lineHeight: 1.65, color: '#9AA5BC', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
        }}>
          {feed.length === 0 && <div style={{ color: '#5A6377' }}>le détail de chaque décision du pipeline s’affichera ici…</div>}
          {feed.map((l, i) => (
            <div key={i} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: i === feed.length - 1 ? '#E6EAF5' : undefined }}>
              <span style={{ color: accent }}>›</span> {l.replace(/^PROGRESS:[a-z_]*:?/i, '')}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const STATE_SAYS: Partial<Record<MascotState, string>> = {
  waiting: 'J’attends mon tour sur le PC, rien n’a commencé.',
  asking: 'J’ai besoin de ta réponse pour continuer.',
  success: 'C’est prêt !',
  error: 'Quelque chose a échoué — preuves conservées.',
}

function frameReader(s: Session, entry: FxEntry, stage: FxStage): () => FrameRead {
  return () => {
    const wall = Date.now()
    const tl = s.tl
    const measured = measuredFor(s.module, tl, wall)
    const prog = entry.reveal
      ? 1
      : animationProgress({
        measured,
        phaseIdx: tl.phaseIdx,
        phaseCount: tl.phaseCount,
        phaseAgeMs: wall - tl.phaseStartedAt,
        elapsedMs: wall - tl.startedAt,
        phaseReported: tl.lastPhaseChangeAt !== tl.startedAt || s.explicitPhase,
      })
    return {
      prog,
      sync: {
        phaseIdx: tl.phaseIdx,
        phaseCount: tl.phaseCount,
        phaseAge: wall - tl.phaseStartedAt,
        pulseAge: wall - tl.lastEventAt,
        events: tl.eventCount,
        measured: tl.measured,
        stage,
      },
    }
  }
}

function FullOverlay({ module, entry, session, job, onMinimize, onStopOverlay }: {
  module: FxModule
  entry: FxEntry
  session: Session
  job: GenerationJobState | null
  onMinimize?: () => void
  onStopOverlay?: () => void
}) {
  const scene = FX_SCENES[module]
  const agent = FX_AGENTS[module]
  const [, force] = useState(0)
  const [page, setPage] = useState<'scene' | 'construction'>(module === '3d' ? 'construction' : 'scene')
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < 760)
  useEffect(() => {
    const iv = window.setInterval(() => force((n) => n + 1), 250)
    const onResize = () => setNarrow(window.innerWidth < 760)
    window.addEventListener('resize', onResize)
    return () => { window.clearInterval(iv); window.removeEventListener('resize', onResize) }
  }, [])
  const now = Date.now()
  const tl = session.tl
  const done = Boolean(entry.reveal)
  const stage: FxStage = done ? 'done' : stageForJob(job)
  const idx = done ? scene.phases.length - 1 : tl.phaseIdx
  const phaseName = scene.phases[idx]
  const measured = measuredFor(module, tl, now)
  const timing = computeTiming(module, session, job, now, done)
  const mState = mascotStateFor({ ask: Boolean(entry.ask), reveal: done, stage, phaseIdx: idx, phaseName })
  const says = STATE_SAYS[mState]
    ?? (stage === 'preparing' ? 'Je prépare les modèles et services…' : scene.says[Math.min(scene.says.length - 1, Math.floor(((idx + 0.5) / scene.phases.length) * scene.says.length))])
  const read = frameReader(session, entry, stage)
  const pctLabel = done
    ? '100 %'
    : stage === 'queued'
      ? 'En file'
      : stage === 'preparing'
        ? 'Préparation'
        : measured != null
          ? `${Math.round(measured * 100)} %`
          : `Étape ${idx + 1}/${scene.phases.length}`
  const elapsedLabel = stage === 'queued'
    ? `en file depuis ${formatClock(job ? now - job.createdAt : now - tl.startedAt)}`
    : `écoulé ${formatClock(timing.elapsedMs)}`
  return (
    <div
      role="dialog"
      aria-label={`${agent.name} — génération ${module} en cours`}
      style={{
        position: 'fixed', inset: 0,
        width: '100%', height: '100%',
        zIndex: 99999, pointerEvents: 'auto',
        overflow: 'hidden',
        background: '#04060b',
        boxShadow: `inset 0 0 120px ${agent.accent}18`,
        animation: 'aurora-fx-in .45s cubic-bezier(.22,1,.36,1)',
      }}
    >
      <div style={{ position: 'absolute', top: 14, right: 16, zIndex: 5, display: 'flex', alignItems: 'center', gap: 8, pointerEvents: 'auto' }}>
        {onMinimize && (
          <button
            type="button"
            onClick={onMinimize}
            style={{
              minHeight: 44, cursor: 'pointer', padding: '7px 14px', borderRadius: 999,
              border: '1px solid rgba(56,189,248,.45)', background: 'rgba(15,23,42,.82)',
              color: '#bae6fd', fontSize: 12, fontWeight: 600, fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
            }}
          >
            ⎯ Réduire{narrow ? '' : ' (voir l’Atelier)'}
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            window.dispatchEvent(new CustomEvent('aurora-fx-stop', { detail: { module } }))
            onStopOverlay?.()
          }}
          style={{
            minHeight: 44, cursor: 'pointer', padding: '7px 14px', borderRadius: 999,
            border: '1px solid rgba(248,113,113,.5)', background: 'rgba(127,29,29,.35)',
            color: '#fecaca', fontSize: 12, fontWeight: 650, fontFamily: "'Inter','Segoe UI',system-ui,sans-serif",
          }}
        >
          ■ Arrêter{narrow ? '' : ' la génération'}
        </button>
      </div>
      <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('aurora:projects'))}
        style={{ position: 'absolute', top: 14, left: 16, zIndex: 5, minHeight: 44,
          maxWidth: 'calc(50% - 24px)', padding: '8px 14px', borderRadius: 16, border: '1px solid #a78bfa88',
          background: '#171228', color: '#e9ddff', cursor: 'pointer' }}>
        {narrow ? 'File' : 'Projets et file d’attente'}
      </button>
      <FxCanvas module={module} read={read} ambientOnly={module === '3d' && page === 'construction'} />
      {!done && entry.refs && entry.refs.length > 0 && <RefsPanel refs={entry.refs} accent={agent.accent} narrow={narrow} />}
      {module === '3d' && page === 'construction' && (
        <CenterStage entry={entry} accent={agent.accent} tl={tl} done={done} narrow={narrow} />
      )}
      {!done && module === '3d' && (
        <button
          type="button"
          onClick={() => setPage((p) => (p === 'scene' ? 'construction' : 'scene'))}
          title={page === 'scene' ? 'Voir l’hologramme de la fabrication réelle' : 'Revenir à la scène animée'}
          aria-label={page === 'scene' ? 'Voir l’hologramme' : 'Voir la scène animée'}
          style={{
            position: 'absolute', right: narrow ? 12 : 48, top: narrow ? 70 : '46%', zIndex: 2,
            width: 48, height: 48, borderRadius: '50%', cursor: 'pointer',
            border: `1px solid ${agent.accent}77`, background: 'rgba(8,12,22,.85)',
            color: agent.accent, fontSize: 20, fontWeight: 700,
            boxShadow: `0 0 24px ${agent.accent}33`, pointerEvents: 'auto',
          }}
        >{page === 'scene' ? '❯' : '❮'}</button>
      )}
      {!done && entry.ask && <FxAskPanel module={module} ask={entry.ask} accent={agent.accent} />}
      {done && entry.reveal && entry.reveal.kind !== 'mesh' && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(4,6,11,.55)', backdropFilter: 'blur(6px)', animation: 'aurora-fx-reveal-bg .4s ease',
        }}>
          {entry.reveal.kind === 'video' ? (
            <video src={entry.reveal.url} muted autoPlay playsInline style={{
              maxWidth: '78%', maxHeight: '78%', borderRadius: 14,
              border: `1px solid ${agent.accent}88`, boxShadow: `0 20px 70px rgba(0,0,0,.6), 0 0 40px ${agent.accent}44`,
              animation: 'aurora-fx-reveal 1.1s cubic-bezier(.22,1,.36,1)',
            }} />
          ) : (
            <img src={entry.reveal.url} alt="Résultat généré" style={{
              maxWidth: '78%', maxHeight: '78%', borderRadius: 14, objectFit: 'contain',
              border: `1px solid ${agent.accent}88`, boxShadow: `0 20px 70px rgba(0,0,0,.6), 0 0 40px ${agent.accent}44`,
              animation: 'aurora-fx-reveal 1.1s cubic-bezier(.22,1,.36,1)',
            }} />
          )}
          <span style={{ position: 'absolute', bottom: 84, fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 12, color: '#4ADE80', letterSpacing: '.2em' }}>✓ TERMINÉ</span>
        </div>
      )}
      <div style={{ position: 'absolute', left: narrow ? 12 : 48, right: narrow ? 12 : 48, bottom: narrow ? 14 : 24, fontFamily: "'Cascadia Code',Consolas,monospace", pointerEvents: 'none', zIndex: 2 }}>
        {/* le personnage est posé au-dessus du HUD, quelle que soit sa hauteur */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
          <div style={{
            display: 'flex', flexDirection: narrow ? 'row' : 'column', alignItems: 'center', gap: narrow ? 8 : 4,
            animation: mState === 'success' ? undefined : 'aurora-fx-float 3.6s ease-in-out infinite',
          }}>
            <span style={{
              fontSize: 11, color: '#E6EAF5', padding: '6px 11px', borderRadius: 12,
              background: 'rgba(8,12,22,.86)', border: `1px solid ${agent.accent}44`, maxWidth: narrow ? 200 : 168, textAlign: 'center',
              fontFamily: "'Inter','Segoe UI',system-ui,sans-serif", lineHeight: 1.35,
            }}>
              <b style={{ color: agent.accent }}>{agent.name}</b> · {says}
            </span>
            <AuroraMascot module={module} size={narrow ? 52 : 100} state={mState} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: 10, letterSpacing: '.24em', color: '#8B93A7', textTransform: 'uppercase' }}>
            {agent.name} {MASCOT_STATE_LABEL[mState]} · {module === '3d' ? '3D' : module}
          </span>
          <span
            title={measured != null ? 'Progression mesurée transmise par le pipeline' : 'Aucune progression chiffrée transmise : étape réelle affichée'}
            style={{ fontSize: narrow ? 16 : 22, fontWeight: 700, color: agent.accent, textShadow: `0 0 18px ${agent.accent}88`, whiteSpace: 'nowrap' }}
          >
            {pctLabel}
          </span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap',
          padding: '8px 12px', marginBottom: 10, borderRadius: 10,
          background: 'rgba(8, 12, 24, 0.86)', border: `1px solid ${agent.accent}55`, boxShadow: `0 0 18px ${agent.accent}22`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '1 1 260px' }}>
            <span style={{
              padding: '3px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
              background: `${agent.accent}28`, color: '#fff', border: `1px solid ${agent.accent}88`, whiteSpace: 'nowrap',
            }}>
              {stage === 'queued' ? 'EN FILE' : stage === 'preparing' ? 'PRÉPARATION' : `ÉTAPE ${idx + 1}/${scene.phases.length}`}
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#EEF2FF', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {stage === 'queued' || stage === 'preparing' ? (job?.detail || entry.phase || phaseName) : (entry.phase || phaseName)}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, minWidth: 0 }}>
            <span style={{ fontSize: 12, color: '#FDE68A', fontWeight: 700, whiteSpace: 'nowrap' }}>
              {done ? '✓ terminé' : `${elapsedLabel} · ${timing.headline}`}
            </span>
            {!done && (
              <span style={{ fontSize: 9.5, color: '#8B93A7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: narrow ? 280 : 520 }}>
                {timing.interval ? `intervalle ${timing.interval} · ` : ''}{timing.est.basis}{timing.accuracy ? ` · ${timing.accuracy}` : ''}
              </span>
            )}
          </div>
        </div>
        {narrow ? (
          <div style={{ display: 'flex', gap: 5, marginBottom: 10 }}>
            {scene.phases.map((p, i) => (
              <span key={p} title={p} style={{
                flex: 1, height: 4, borderRadius: 2,
                background: i < idx || done ? '#4ADE80' : i === idx ? agent.accent : 'rgba(255,255,255,.12)',
                boxShadow: i === idx && !done ? `0 0 8px ${agent.accent}` : 'none',
              }} />
            ))}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${scene.phases.length}, minmax(0, 1fr))`, gap: 6, marginBottom: 10 }}>
            {scene.phases.map((p, i) => {
              const isDone = done || i < idx
              const isCurrent = !done && i === idx
              return (
                <div key={p} style={{
                  display: 'flex', flexDirection: 'column', gap: 3, padding: '5px 8px', borderRadius: 8,
                  border: `1px solid ${isCurrent ? agent.accent : isDone ? 'rgba(74,222,128,.35)' : 'rgba(255,255,255,.08)'}`,
                  background: isCurrent ? `${agent.accent}18` : isDone ? 'rgba(74,222,128,.06)' : 'rgba(255,255,255,.02)',
                  boxShadow: isCurrent ? `0 0 16px ${agent.accent}44` : 'none', transition: 'all .3s ease',
                }}>
                  <span style={{
                    fontSize: 9.5, fontWeight: isCurrent ? 700 : 500,
                    color: isDone ? '#4ADE80' : isCurrent ? '#fff' : '#6B7280',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {isDone ? '✓ ' : `${i + 1}. `}{p}
                  </span>
                  <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,.08)', overflow: 'hidden', position: 'relative' }}>
                    {isDone && <div style={{ height: '100%', width: '100%', background: '#4ADE80' }} />}
                    {isCurrent && (
                      <div style={{
                        position: 'absolute', inset: 0,
                        background: `linear-gradient(90deg, transparent, ${agent.accent}, transparent)`,
                        backgroundSize: '50% 100%', backgroundRepeat: 'no-repeat',
                        animation: 'aurora-fx-shimmer 1.4s linear infinite',
                      }} />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {!narrow && Boolean(entry.logLines?.length) && !(module === '3d' && page === 'construction') && (
          <div role="log" aria-label={`Actions réelles de la génération ${module}`} style={{
            fontSize: 11, lineHeight: 1.5, marginTop: 6, marginBottom: 8, padding: '7px 11px', borderRadius: 9,
            background: 'rgba(4, 7, 15, 0.76)', border: '1px solid rgba(255,255,255,.08)', overflowWrap: 'anywhere', color: '#B7C0D4',
          }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.16em', color: '#8B93A7', marginBottom: 3, textTransform: 'uppercase' }}>
              Journal des étapes exécutées ({entry.logLines!.length})
            </div>
            {entry.logLines!.slice(-3).map((line, index, arr) => (
              <div key={index} style={{ color: index === arr.length - 1 ? '#EEF2FF' : '#8B93A7' }}>
                <span style={{ color: index === arr.length - 1 ? agent.accent : '#4ADE80' }}>{index === arr.length - 1 ? '▸ ' : '✓ '}</span>
                {line.slice(0, 600)}
              </div>
            ))}
          </div>
        )}
        <div style={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,.08)', overflow: 'hidden', position: 'relative' }}>
          {measured != null || done ? (
            <i style={{
              display: 'block', height: '100%', width: `${(done ? 1 : measured ?? 0) * 100}%`,
              background: `linear-gradient(90deg, ${agent.accent}, #fff8)`, boxShadow: `0 0 14px ${agent.accent}`,
              transition: 'width .3s linear',
            }} />
          ) : (
            <>
              <i style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(idx / scene.phases.length) * 100}%`, background: `${agent.accent}AA` }} />
              <i style={{
                position: 'absolute', top: 0, bottom: 0, left: `${(idx / scene.phases.length) * 100}%`, width: `${100 / scene.phases.length}%`,
                background: `linear-gradient(90deg, transparent, ${agent.accent}, transparent)`, backgroundSize: '60% 100%', backgroundRepeat: 'no-repeat',
                animation: 'aurora-fx-shimmer 1.2s linear infinite',
              }} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function MiniPill({ module, entry, session, job, onClick }: { module: FxModule; entry: FxEntry; session: Session; job: GenerationJobState | null; onClick: () => void }) {
  const agent = FX_AGENTS[module]
  const [, force] = useState(0)
  useEffect(() => {
    const iv = window.setInterval(() => force((n) => n + 1), 1000)
    return () => window.clearInterval(iv)
  }, [])
  const now = Date.now()
  const done = Boolean(entry.reveal)
  const stage: FxStage = done ? 'done' : stageForJob(job)
  const tl = session.tl
  const scene = FX_SCENES[module]
  const idx = done ? scene.phases.length - 1 : tl.phaseIdx
  const mState = mascotStateFor({ ask: Boolean(entry.ask), reveal: done, stage, phaseIdx: idx, phaseName: scene.phases[idx] })
  const timing = computeTiming(module, session, job, now, done)
  const measured = measuredFor(module, tl, now)
  const left = done
    ? '✓ terminé'
    : stage === 'queued'
      ? timing.headline
      : `${measured != null ? `${Math.round(measured * 100)} %` : `étape ${idx + 1}/${scene.phases.length}`} · ${
        timing.est.remainingMs != null && timing.est.state !== 'queued' ? `≈ ${formatWait(timing.est.remainingMs)}` : timing.est.state === 'overdue' ? 'plus long que d’habitude' : 'estimation en préparation'
      }`
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${agent.name} ${MASCOT_STATE_LABEL[mState]} (${module}) — ${timing.headline}. Cliquer pour revenir à l’écran.`}
      style={{
        display: 'flex', alignItems: 'center', gap: 9, padding: '6px 14px 6px 6px', borderRadius: 999,
        border: `1px solid ${agent.accent}66`, background: 'rgba(8,12,22,.94)', cursor: 'pointer',
        boxShadow: `0 10px 30px rgba(0,0,0,.5), 0 0 18px ${agent.accent}22`,
        color: '#E6EAF5', fontFamily: "'Inter','Segoe UI',system-ui,sans-serif", maxWidth: 'min(92vw, 420px)',
      }}
    >
      <AuroraMascot module={module} size={34} state={mState} />
      <span style={{ fontSize: 12, fontWeight: 650 }}>{agent.name}</span>
      {entry.ask ? (
        <span style={{ fontSize: 11, fontWeight: 700, color: '#ffb44d', animation: 'pulse 1.2s ease-in-out infinite' }}>
          QUESTION EN ATTENTE — cliquer
        </span>
      ) : (
        <span style={{ fontSize: 11, fontFamily: "'Cascadia Code',Consolas,monospace", color: agent.accent, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {left}
        </span>
      )}
    </button>
  )
}

// La question est une PARTIE de l'ecran de generation — pas une modale
// empilee par-dessus. Fond PLEIN (aucune transparence sous le texte),
// lisibilite d'abord; la generation reste visible autour, en pause implicite.
function FxAskPanel({ module, ask, accent }: { module: FxModule; ask: FxAsk; accent: string }) {
  const [text, setText] = useState('')
  const [choix, setChoix] = useState<number | null>(null)
  // 31/07 (demande Juan): sur un LOT, pouvoir trier IMAGE PAR IMAGE (garder /
  // jeter) au lieu du tout-ou-rien oui/non.
  const [jetees, setJetees] = useState<Set<number>>(new Set())
  const confirm = ask.kind === 'confirm_images'
  const pick = ask.kind === 'pick_image'
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 3, display: 'grid',
      placeItems: 'center', pointerEvents: 'auto',
      background: 'rgba(4,6,11,.95)',
    }}>
      <div style={{
        width: 'min(820px, 94vw)', maxHeight: '88vh', overflowY: 'auto',
        background: '#0B0F16', borderRadius: 20, padding: '26px 30px',
        border: `1px solid ${accent}66`,
        boxShadow: `0 30px 90px rgba(0,0,0,.65), 0 0 40px ${accent}22`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <AuroraMascot module={module} size={48} state="asking" />
          <div style={{
            fontSize: 11, letterSpacing: '.3em', color: accent, fontWeight: 700,
            fontFamily: "'Cascadia Code',Consolas,monospace",
          }}>
            {ask.categoryLabel?.toUpperCase() ?? (confirm ? 'VALIDATION — VOTRE AVIS EST ATTENDU' : 'QUESTION — LA GÉNÉRATION ATTEND VOTRE RÉPONSE')}
          </div>
        </div>
        <div style={{ fontSize: 20, lineHeight: 1.5, color: '#EEF2FB', fontWeight: 600 }}>
          {ask.question}
        </div>
        {(confirm || pick) && ask.images && ask.images.length > 0 && (
          <div style={{
            marginTop: 18, display: 'grid', gap: 12,
            gridTemplateColumns: ask.images.length > 1 ? 'repeat(auto-fit, minmax(180px, 1fr))' : '1fr',
          }}>
            {ask.images.map((u, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img src={u} alt={`Proposition ${i + 1}`}
                  onClick={pick ? () => setChoix(i)
                    : confirm && ask.allowPickEach && i > 0
                      ? () => setJetees((prev) => { const n = new Set(prev); if (n.has(i)) n.delete(i); else n.add(i); return n })
                      : undefined}
                  style={{
                    width: '100%', maxHeight: '38vh', objectFit: 'contain',
                    borderRadius: 12, background: '#091116',
                    cursor: pick || (confirm && ask.allowPickEach && i > 0) ? 'pointer' : 'default',
                    opacity: jetees.has(i) ? 0.35 : 1,
                    border: pick && choix === i
                      ? `3px solid ${accent}`
                      : jetees.has(i)
                        ? '3px solid rgba(248,113,113,.8)'
                        : '1px solid rgba(255,255,255,.08)',
                    boxShadow: pick && choix === i ? `0 0 24px ${accent}55` : 'none',
                  }} />
                {confirm && ask.allowPickEach && i > 0 && (
                  <span style={{ position: 'absolute', top: 6, left: 8, fontSize: 11, fontWeight: 700,
                                 color: jetees.has(i) ? '#FCA5A5' : '#86EFAC' }}>
                    {jetees.has(i) ? '✕ jetee — cliquer pour garder' : '✓ gardee — cliquer pour jeter'}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
        {!confirm && ask.options && ask.options.length > 0 && (
          <div style={{ marginTop: 18, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {ask.options.map((opt) => (
              <button key={opt} type="button"
                onClick={() => fxAnswer(module, ask.id, opt)}
                style={{
                  padding: '12px 18px', borderRadius: 12, cursor: 'pointer',
                  border: `1px solid ${accent}55`, background: `${accent}14`,
                  color: '#EDF2FC', fontSize: 15, fontWeight: 600,
                }}>{opt}</button>
            ))}
          </div>
        )}
        {confirm && ask.allowPhoto && (
          <label style={{
            marginTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 8, padding: '12px', borderRadius: 12, cursor: 'pointer',
            border: `1px dashed ${accent}66`, background: `${accent}0d`,
            color: '#BFDBFE', fontSize: 14, fontWeight: 600,
          }}>
            Joindre la 2e photo (vraie vue sous un autre angle)
            <input type="file" accept="image/*,.png,.jpg,.jpeg,.webp,.avif,.heic,.heif" style={{ display: 'none' }}
              onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f) return
                const fd = new FormData()
                fd.append('file', f, f.name)
                try {
                  const base = window.location.port === '1420' ? 'http://127.0.0.1:3001' : ''
                  const r = await fetch(`${base}/api/upload`, { method: 'POST', body: fd })
                  const d = await r.json()
                  if (d?.path) fxAnswer(module, ask.id, { accepted: true, verdict: 'photo', photo: d.path, reason: '' })
                } catch { /* l'utilisateur peut cliquer Accepter pour mono-vue */ }
                e.currentTarget.value = ''
              }} />
          </label>
        )}
        {(confirm || ask.allowText) && (
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            placeholder={confirm ? 'Optionnel (si vous refusez) : ce qui ne va pas' : 'Votre réponse...'}
            style={{
              marginTop: 16, width: '100%', borderRadius: 12, padding: 12,
              background: '#101623', color: '#EDF2FC', fontSize: 15,
              border: '1px solid rgba(255,255,255,.14)', resize: 'vertical',
            }} />
        )}
        <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
          {pick ? (
            <button type="button" disabled={choix === null}
              onClick={() => choix !== null && fxAnswer(module, ask.id, { choix })}
              style={{
                padding: '12px 26px', borderRadius: 12,
                cursor: choix === null ? 'not-allowed' : 'pointer',
                opacity: choix === null ? 0.45 : 1,
                border: `1px solid ${accent}88`, background: `${accent}22`,
                color: '#EDF2FC', fontSize: 15, fontWeight: 700,
              }}>Valider la proposition {choix !== null ? choix + 1 : ''}</button>
          ) : confirm ? (
            <>
              <button type="button"
                onClick={() => fxAnswer(module, ask.id, { accepted: false, reason: text.trim(), verdict: 'non' })}
                style={{
                  padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(248,113,113,.6)', background: 'rgba(248,113,113,.14)',
                  color: '#FCA5A5', fontSize: 15, fontWeight: 700,
                }}>✕ Non — supprimer</button>
              {ask.allowMaybe && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, { accepted: false, reason: text.trim(), verdict: 'peutetre' })}
                  style={{
                    padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                    border: '1px solid rgba(251,191,36,.55)', background: 'rgba(251,191,36,.12)',
                    color: '#FCD34D', fontSize: 15, fontWeight: 700,
                  }}>~ Peut-être — garder et proposer autre chose</button>
              )}
              {ask.allowPickEach && jetees.size > 0 && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, { accepted: true, reason: text.trim(), verdict: 'selection', jetees: Array.from(jetees) })}
                  style={{
                    padding: '12px 20px', borderRadius: 12, cursor: 'pointer',
                    border: '1px solid rgba(96,165,250,.6)', background: 'rgba(96,165,250,.14)',
                    color: '#93C5FD', fontSize: 15, fontWeight: 700,
                  }}>Garder ma selection ({(ask.images?.length || 1) - 1 - jetees.size} vue(s))</button>
              )}
              <button type="button"
                onClick={() => fxAnswer(module, ask.id, { accepted: true, reason: '', verdict: 'oui' })}
                style={{
                  padding: '12px 24px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(74,222,128,.6)', background: 'rgba(74,222,128,.16)',
                  color: '#86EFAC', fontSize: 15, fontWeight: 700,
                }}>✓ Accepter</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => fxAnswer(module, ask.id, null)}
                style={{
                  padding: '12px 18px', borderRadius: 12, cursor: 'pointer',
                  border: '1px solid rgba(255,255,255,.18)', background: 'transparent',
                  color: '#9AA3B8', fontSize: 14,
                }}>Passer</button>
              {ask.allowText && (
                <button type="button"
                  onClick={() => fxAnswer(module, ask.id, text.trim() || null)}
                  style={{
                    padding: '12px 24px', borderRadius: 12, cursor: 'pointer',
                    border: `1px solid ${accent}88`, background: `${accent}22`,
                    color: '#EDF2FC', fontSize: 15, fontWeight: 700,
                  }}>Envoyer</button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function GenerationFxHost() {
  const [entries, setEntries] = useState<Partial<Record<FxModule, FxEntry>>>({})
  const [minimizedModules, setMinimizedModules] = useState<Partial<Record<FxModule, boolean>>>({})
  const [, forceRender] = useState(0)
  const sessions = useRef(new Map<FxModule, Session>())
  const recentSessions = useRef<Session[]>([])
  const recordedJobs = useRef(new Set<string>())
  useEffect(() => {
    markFxHostMounted(true)
    return () => markFxHostMounted(false)
  }, [])
  const [enabled, setEnabled] = useState(generationFxEnabled)
  const activeModule = useAppStore((s) => s.activeModule)
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const generationJobs = useAppStore((s) => s.generationJobs)
  const jobsRef = useRef(generationJobs)
  jobsRef.current = generationJobs

  const retire = useCallback((module: FxModule) => {
    const s = sessions.current.get(module)
    if (!s) return
    sessions.current.delete(module)
    if (s.endedAt == null) s.endedAt = Date.now()
    const cutoff = Date.now() - RECENT_SESSION_MS
    recentSessions.current = [...recentSessions.current.filter((r) => (r.endedAt ?? 0) > cutoff), s].slice(-12)
    countdowns.delete(module)
    if (s.autoMinimized) setMinimizedModules((prev) => (prev[module] ? { ...prev, [module]: false } : prev))
  }, [])

  const apply = useCallback((module: FxModule, patch: FxPatch) => {
    const now = Date.now()
    const phases = FX_SCENES[module].phases
    let s = sessions.current.get(module)
    let idx = s?.tl.phaseIdx ?? 0
    let revealAt: number | null = null
    if (patch.active) {
      if (!s || s.endedAt != null) {
        if (s) retire(module)
        s = { module, tl: new RunTimeline(now, phases.length), explicitPhase: false, revealContent: false, autoMinimized: false, endedAt: null, success: false, snapshots: [], lastSnapshotAt: 0 }
        sessions.current.set(module, s)
      }
      if (patch.phase !== undefined || patch.phaseIndex !== undefined || patch.progress !== undefined) {
        idx = resolvePhaseIndex(module, phases, {
          text: patch.phase, index: patch.phaseIndex, progress: patch.progress, prev: s.tl.phaseIdx, explicit: s.explicitPhase,
        })
        if (typeof patch.phaseIndex === 'number') s.explicitPhase = true
      }
      const changed = s.tl.notePhase(idx, now)
      if (typeof patch.progress === 'number' && Number.isFinite(patch.progress)) s.tl.noteProgress(patch.progress, now, patch.progressKind === 'fine')
      if (typeof patch.phaseFraction === 'number') s.tl.notePhaseFraction(patch.phaseFraction, now)
      if (changed || patch.logLine || typeof patch.progress === 'number' || patch.refs || patch.meshUrl || patch.ask) s.tl.noteEvent(now)
      if (patch.revealContent && !s.revealContent) {
        // le contenu du module s'affiche déjà : l'écran s'efface pour le laisser lire
        s.revealContent = true
        s.autoMinimized = true
        setMinimizedModules((prev) => (prev[module] ? prev : { ...prev, [module]: true }))
      }
    } else {
      if (s && s.endedAt == null) {
        const ended = s
        ended.endedAt = now
        ended.success = Boolean(patch.resultUrl) || patch.outcome === 'success'
        ended.tl.noteEvent(now)
        if (ended.success) {
          // un module sans job géré enregistre ici sa durée ; les jobs gérés sont
          // enregistrés à leur fin réelle (avec les étapes observées)
          const managed = jobsRef.current.some((j) => (j.module as string) === module && j.createdAt >= ended.tl.startedAt - 20000)
          const fxId = `fx:${module}:${ended.tl.startedAt}`
          if (!managed && recordCompletedRun(module, null, { id: fxId, totalMs: now - ended.tl.startedAt, phaseMs: ended.tl.phaseDurations(now), at: now })) {
            recordEtaOutcome(module, fxId, ended.snapshots, now - ended.tl.startedAt)
            historyVersion++
          }
        }
        if (!patch.resultUrl) retire(module)
      }
      if (patch.resultUrl) revealAt = now
    }
    const sessionStart = s?.tl.startedAt ?? now
    setEntries((prev) => {
      const next = { ...prev }
      const cur = next[module]
      if (!patch.active) {
        if (!cur && !patch.resultUrl) return prev
        if (cur?.reveal && !patch.resultUrl) return prev
        if (patch.resultUrl) {
          const base: FxEntry = cur ?? { startedAt: now - SHOW_DELAY_MS, phaseIdx: phases.length - 1 }
          next[module] = {
            ...base,
            progress: 1,
            ask: null,
            phaseIdx: phases.length - 1,
            meshUrl: patch.resultKind === 'mesh' ? patch.resultUrl : base.meshUrl,
            reveal: { url: patch.resultUrl, kind: patch.resultKind ?? 'image', at: now },
          }
          return next
        }
        delete next[module]
        return next
      }
      const base = cur && !cur.reveal ? cur : undefined
      const logLines = patch.logLine ? [...(base?.logLines ?? []), patch.logLine].slice(-300) : base?.logLines
      next[module] = {
        startedAt: base?.startedAt ?? sessionStart,
        phaseIdx: idx,
        phase: patch.phase ?? base?.phase,
        progress: patch.progress ?? base?.progress,
        refs: patch.refs ?? base?.refs,
        logLines,
        counters: patch.logLine ? updateCounters(base?.counters, patch.logLine) : base?.counters,
        meshUrl: patch.meshUrl ?? base?.meshUrl,
        meshInfo: patch.meshInfo ?? base?.meshInfo,
        // undefined = inchange; null = question retiree (repondue)
        ask: patch.ask === undefined ? base?.ask : patch.ask,
      }
      return next
    })
    if (revealAt != null) {
      const at = revealAt
      window.setTimeout(() => {
        setEntries((p2) => {
          if (p2[module]?.reveal?.at !== at) return p2
          const n2 = { ...p2 }
          delete n2[module]
          return n2
        })
        const cur = sessions.current.get(module)
        if (cur && cur.endedAt != null) retire(module)
      }, REVEAL_MS)
    }
  }, [retire])

  useEffect(() => {
    const onFx = (ev: Event) => {
      const d = (ev as CustomEvent<{ module: FxModule } & FxPatch>).detail
      if (!d?.module || !FX_SCENES[d.module]) return
      apply(d.module, d)
    }
    const onPref = () => setEnabled(generationFxEnabled())
    window.addEventListener(FX_EVENT, onFx)
    window.addEventListener(FX_PREF_EVENT, onPref)
    return () => {
      window.removeEventListener(FX_EVENT, onFx)
      window.removeEventListener(FX_PREF_EVENT, onPref)
    }
  }, [apply])

  // Durées réelles : chaque job géré terminé avec succès alimente l'historique
  // (y compris ceux conservés d'une session précédente, dédoublonnés par id).
  useEffect(() => {
    for (const job of generationJobs) {
      if (job.status !== 'done' || !job.startedAt || !job.finishedAt || recordedJobs.current.has(job.id)) continue
      recordedJobs.current.add(job.id)
      const total = job.finishedAt - job.startedAt
      const fxModule = job.module as FxModule
      const candidates = [sessions.current.get(fxModule), ...recentSessions.current.filter((r) => r.module === fxModule).reverse()]
      const s = candidates.find((c) => c && c.tl.startedAt <= job.finishedAt! && c.tl.startedAt >= job.createdAt - 20000 && (c.endedAt ?? Date.now()) >= job.startedAt! - 5000)
      let phaseMs: number[] | undefined
      if (s) {
        const d = s.tl.phaseDurations(Math.min(job.finishedAt, s.endedAt ?? job.finishedAt))
        const excess = d.reduce((a, b) => a + b, 0) - total
        if (excess > 0) d[0] = Math.max(0, d[0] - excess) // attente en file avant admission
        phaseMs = d
      }
      if (recordCompletedRun(job.module, job.model, { id: job.id, totalMs: total, phaseMs, at: job.finishedAt })) {
        // écart réel des prédictions affichées pendant ce run (calibration sur vraie génération)
        if (s) recordEtaOutcome(job.module, job.id, s.snapshots, total)
        historyVersion++
      }
    }
  }, [generationJobs])

  const comfyActive = Boolean(entries.image && !entries.image.reveal) || Boolean(entries.drawing && !entries.drawing.reveal)
  useEffect(() => {
    if (!comfyActive) return
    return watchComfyProgress((frac, label, logLine, measure) => {
      for (const m of ['image', 'drawing'] as FxModule[]) {
        const s = sessions.current.get(m)
        if (!s || s.endedAt != null) continue
        const finished = Boolean(measure?.executedNode)
        apply(m, {
          active: true,
          phase: m === 'image' ? label : finished ? 'Révélation' : 'Rendu FLUX',
          phaseIndex: finished ? 4 : m === 'image' ? 2 : 3,
          progress: m === 'image' ? frac : undefined,
          phaseFraction: finished ? undefined : measure?.phaseFraction,
          logLine,
        })
      }
    })
  }, [comfyActive, apply])

  const codeStreaming = useCodeStreamStore((s) => s.streaming)
  const codePhase = useCodeStreamStore((s) => s.phase)
  const codeMessage = useCodeStreamStore((s) => s.phaseMessage)
  const codeProgress = useCodeStreamStore((s) => s.progressPct)
  const lastCodeLine = useRef('')
  useEffect(() => {
    const running = codeStreaming || (codePhase !== 'idle' && codePhase !== 'done' && codePhase !== 'error')
    if (running) {
      const line = codeMessage && codeMessage !== lastCodeLine.current ? codeMessage : undefined
      if (line) lastCodeLine.current = line
      apply('code', {
        active: true,
        phase: codeMessage || codePhase,
        phaseIndex: codePhaseIndex(codePhase),
        logLine: line,
        progress: typeof codeProgress === 'number' && codeProgress > 0 ? codeProgress / 100 : undefined,
      })
    } else {
      lastCodeLine.current = ''
      apply('code', { active: false, outcome: codePhase === 'done' ? 'success' : codePhase === 'error' ? 'error' : undefined })
    }
  }, [codeStreaming, codePhase, codeMessage, codeProgress, apply])

  // une opération courte n'affiche rien ; au-delà du délai, l'écran apparaît
  const pending = (Object.values(entries) as FxEntry[]).some((e) => !e.reveal && !e.ask && Date.now() - e.startedAt < SHOW_DELAY_MS)
  useEffect(() => {
    if (!pending) return
    const t = window.setTimeout(() => forceRender((n) => n + 1), SHOW_DELAY_MS + 40)
    return () => window.clearTimeout(t)
  }, [pending, entries])

  const activeFx = Object.entries(entries) as [FxModule, FxEntry][]
  if (!enabled || activeFx.length === 0) return null
  const nowR = Date.now()
  const shown = activeFx.filter(([, e]) => Boolean(e.reveal) || Boolean(e.ask) || nowR - e.startedAt >= SHOW_DELAY_MS)
  if (shown.length === 0) return null

  const sessionFor = (m: FxModule, e: FxEntry): Session => {
    const live = sessions.current.get(m)
    if (live) return live
    const recent = [...recentSessions.current].reverse().find((r) => r.module === m)
    if (recent) return recent
    const s: Session = { module: m, tl: new RunTimeline(e.startedAt, FX_SCENES[m].phases.length), explicitPhase: false, revealContent: false, autoMinimized: false, endedAt: nowR, success: true, snapshots: [], lastSnapshotAt: 0 }
    s.tl.notePhase(e.phaseIdx, e.startedAt)
    sessions.current.set(m, s)
    return s
  }
  const jobFor = (m: FxModule): GenerationJobState | null =>
    generationJobs.find((j) => (j.module as string) === m && (j.status === 'queued' || j.status === 'running')) ?? null

  const fxForCurrent = shown.find(([m]) => (m as string) === (activeModule as string) && !minimizedModules[m])
  const others = shown.filter(([m]) => (m as string) !== (activeModule as string) || Boolean(minimizedModules[m]))

  return (
    <>
      <style>{`
        @keyframes aurora-fx-in { from { opacity: 0; transform: scale(.985) } to { opacity: 1; transform: scale(1) } }
        @keyframes aurora-fx-float { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-7px) } }
        @keyframes aurora-fx-reveal { from { opacity: 0; clip-path: inset(0 100% 0 0); transform: scale(.96) } to { opacity: 1; clip-path: inset(0 0 0 0); transform: scale(1) } }
        @keyframes aurora-fx-reveal-bg { from { opacity: 0 } to { opacity: 1 } }
        @keyframes aurora-fx-shimmer { from { background-position: -60% 0 } to { background-position: 160% 0 } }
        @media (prefers-reduced-motion: reduce) {
          [style*="aurora-fx-float"], [style*="aurora-fx-shimmer"] { animation: none !important }
        }
      `}</style>
      {fxForCurrent && (
        <FullOverlay
          key={`${fxForCurrent[0]}-${sessionFor(fxForCurrent[0], fxForCurrent[1]).tl.startedAt}`}
          module={fxForCurrent[0]}
          entry={fxForCurrent[1]}
          session={sessionFor(fxForCurrent[0], fxForCurrent[1])}
          job={jobFor(fxForCurrent[0])}
          onMinimize={() => setMinimizedModules((prev) => ({ ...prev, [fxForCurrent[0]]: true }))}
          onStopOverlay={() => {
            const mod = fxForCurrent[0]
            const s = sessions.current.get(mod)
            if (s && s.endedAt == null) s.endedAt = Date.now()
            retire(mod)
            setEntries((prev) => {
              const next = { ...prev }
              delete next[mod]
              return next
            })
          }}
        />
      )}
      {others.length > 0 && (
        <div style={{ position: 'fixed', right: 18, bottom: 18, zIndex: 119, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
          {others.map(([m, e]) => (
            <MiniPill
              key={m}
              module={m}
              entry={e}
              session={sessionFor(m, e)}
              job={jobFor(m)}
              onClick={() => {
                const s = sessions.current.get(m)
                if (s) s.autoMinimized = false
                setMinimizedModules((prev) => ({ ...prev, [m]: false }))
                setActiveModule(m as ModuleId)
              }}
            />
          ))}
        </div>
      )}
    </>
  )
}
