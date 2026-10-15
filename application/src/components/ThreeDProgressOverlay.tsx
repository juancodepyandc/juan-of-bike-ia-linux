/**
 * v77zag — 3D generation live progress overlay (tunnel + Tauri parity).
 *
 * Reads from the existing setProgress / setPhase machinery in ModelView
 * (which already aggregates onPythonProgress events from the bridge or
 * the Tauri event bus). Adds the missing visual feedback layer:
 *
 *   - sticky panel at the bottom-right of the 3D view
 *   - circular percent meter from phase.progress
 *   - current stage label (large, white)
 *   - last detail message (smaller, grey, fades)
 *   - elapsed time SINCE LAST UPDATE — turns red after 30s without
 *     activity to flag genuine stalls vs natural long jobs
 *   - heartbeat dot pulsing while a job is active so the user knows
 *     the polling loop is live even when no event has fired in a while
 *
 * Why: Hunyuan3D shape generation can run 40-90s producing one or two
 * PROGRESS: events; Blender Rigify another 30-60s; texture bake yet
 * another 30s. Without this overlay the UI looks frozen even when
 * everything is working — exactly the symptom the user reported.
 *
 * Pure presentational — no fetches of its own, no state-machine
 * coupling. The parent passes active flag + progress + phase and gets
 * rerendered when those change.
 */
import { useEffect, useRef, useState } from 'react'
import { emitGenerationFx } from './generationFx/fxBus.ts'
import {
  computeLiveMissionTiming,
  readPersistedThreeDMission,
} from '../services/threeDSubAgentsOrchestrator.ts'

export type ThreeDProgressProps = {
  active: boolean
  progress: string         // last detail line — passed to setProgress in ModelView
  phaseLabel: string       // current stage label — passed to setPhase
  phasePercent: number     // 0..100 — passed to setPhase
  sceneStep?: { current: number; total: number } // For compositional scene generation (e.g., 1/3)
}

export function ThreeDProgressOverlay({ active, progress, phaseLabel, phasePercent, sceneStep }: ThreeDProgressProps) {
  const [elapsedTotal, setElapsedTotal] = useState(0)
  const [remainingEta, setRemainingEta] = useState('~04m 00s')
  const [elapsedSinceUpdate, setElapsedSinceUpdate] = useState(0)
  const startedAtRef = useRef<number | null>(null)
  const lastUpdateRef = useRef<number>(Date.now())
  const lastProgressRef = useRef<string>(progress)
  const lastPhaseRef = useRef<string>(phaseLabel)
  const lastEmittedLineRef = useRef<string>('')
  const activeRef = useRef<boolean>(active)
  activeRef.current = active

  const persisted = readPersistedThreeDMission()
  const effectivePercent = Math.max(
    active ? 5 : 0,
    Math.min(
      100,
      Math.round(
        phasePercent > 0
          ? phasePercent
          : persisted?.active && persisted.phasePercent > 0
            ? persisted.phasePercent
            : active
              ? 8
              : 0,
      ),
    ),
  )

  useEffect(() => {
    if (progress !== lastProgressRef.current || phaseLabel !== lastPhaseRef.current) {
      lastUpdateRef.current = Date.now()
      lastProgressRef.current = progress
      lastPhaseRef.current = phaseLabel
      setElapsedSinceUpdate(0)
    }
  }, [progress, phaseLabel])

  useEffect(() => {
    const isNewLine = Boolean(progress) && progress !== lastEmittedLineRef.current
    if (isNewLine) lastEmittedLineRef.current = progress
    if (active) {
      emitGenerationFx('3d', {
        active: true,
        phase: phaseLabel || progress || persisted?.phaseLabel || 'Reconstruction 3D en cours…',
        progress: Math.max(0.05, Math.min(0.99, effectivePercent / 100)),
        logLine: isNewLine ? progress : undefined,
      })
    } else {
      emitGenerationFx('3d', { active: false })
    }
  }, [active, phaseLabel, progress, effectivePercent, persisted?.phaseLabel])

  useEffect(
    () => () => {
      // Ne couper l'indicateur global que si la génération est réellement terminée
      if (!activeRef.current && !readPersistedThreeDMission()?.active) {
        emitGenerationFx('3d', { active: false })
      }
    },
    [],
  )

  useEffect(() => {
    if (!active) {
      startedAtRef.current = null
      setElapsedTotal(0)
      setElapsedSinceUpdate(0)
      return
    }
    const storedMission = readPersistedThreeDMission()
    if (startedAtRef.current === null) {
      startedAtRef.current =
        storedMission?.active && storedMission.startedAtMs > 0
          ? storedMission.startedAtMs
          : Date.now()
      lastUpdateRef.current = Date.now()
    }
    const tick = () => {
      const now = Date.now()
      const currentMission = readPersistedThreeDMission()
      const anchor =
        currentMission?.active && currentMission.startedAtMs > 0
          ? currentMission.startedAtMs
          : startedAtRef.current ?? now
      startedAtRef.current = anchor
      setElapsedTotal(Math.max(0, Math.floor((now - anchor) / 1000)))
      setElapsedSinceUpdate(Math.max(0, Math.floor((now - lastUpdateRef.current) / 1000)))
      const liveTiming = computeLiveMissionTiming(currentMission, now)
      setRemainingEta(liveTiming.formattedRemaining)
    }
    tick()
    const interval = setInterval(tick, 500)
    return () => clearInterval(interval)
  }, [active])

  if (!active) return null

  const percent = effectivePercent
  const isQuietPhase = elapsedSinceUpdate > 30 && elapsedSinceUpdate <= 120
  const isLikelyStuck = elapsedSinceUpdate > 120
  const formattedElapsed = formatElapsed(elapsedTotal)
  const activeSubAgent =
    persisted?.subAgents?.find((a) => a.status === 'working') || persisted?.subAgents?.[0]

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 1000,
        minWidth: 340,
        maxWidth: 440,
        background: 'rgba(10, 15, 26, 0.95)',
        border: isLikelyStuck
          ? '1px solid rgba(239, 68, 68, 0.6)'
          : isQuietPhase
            ? '1px solid rgba(234, 179, 8, 0.5)'
            : '1px solid rgba(56, 189, 248, 0.45)',
        borderRadius: 14,
        padding: 14,
        color: '#e5e7eb',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
        fontSize: 12,
        boxShadow: '0 12px 36px rgba(0,0,0,0.55)',
        backdropFilter: 'blur(10px)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        {/* Heartbeat dot */}
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: isLikelyStuck ? '#ef4444' : isQuietPhase ? '#eab308' : '#22c55e',
            animation: 'aurora-progress-pulse 1.4s ease-in-out infinite',
          }}
        />
        <span style={{ fontWeight: 700, color: '#fff', flex: 1 }}>
          {sceneStep
            ? `Génération Objet ${sceneStep.current}/${sceneStep.total}`
            : activeSubAgent
              ? `Agent ${activeSubAgent.index}/5 · ${activeSubAgent.role}`
              : 'Génération 3D en cours'}
        </span>
        <span style={{ color: '#38bdf8', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
          {formattedElapsed} · ETA {remainingEta}
        </span>
      </div>

      {/* Percent bar */}
      <div
        style={{
          height: 6,
          background: 'rgba(255,255,255,0.08)',
          borderRadius: 3,
          overflow: 'hidden',
          marginBottom: 10,
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: '100%',
            background: isLikelyStuck
              ? 'linear-gradient(90deg, #ef4444 0%, #f87171 100%)'
              : isQuietPhase
                ? 'linear-gradient(90deg, #eab308 0%, #fbbf24 100%)'
                : 'linear-gradient(90deg, #38bdf8 0%, #6366f1 50%, #22c55e 100%)',
            transition: 'width 300ms ease',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <span style={{ color: '#fff', fontSize: 13, fontWeight: 500 }}>
          {phaseLabel || persisted?.phaseLabel || 'Initialisation des sous-agents...'}
        </span>
        <span style={{ color: '#34d399', fontVariantNumeric: 'tabular-nums', fontSize: 13, fontWeight: 700 }}>
          {percent}%
        </span>
      </div>

      {/* Last event detail */}
      {progress && (
        <div
          style={{
            color: '#9ca3af',
            lineHeight: 1.4,
            wordBreak: 'break-word',
            marginBottom: (isQuietPhase || isLikelyStuck) ? 8 : 0,
          }}
        >
          {progress.length > 220 ? progress.slice(0, 220) + '…' : progress}
        </div>
      )}

      {/* Quiet-phase note (orange, informative — NOT an error) */}
      {isQuietPhase && (
        <div style={{ color: '#fcd34d', fontSize: 11, marginTop: 4 }}>
          Phase silencieuse en cours ({elapsedSinceUpdate}s). C est normal: Hunyuan3D / rigify_generate / paint bake ne logguent pas pendant le compute lourd. Le job continue.
        </div>
      )}

      {/* Likely-stuck warning (red — > 2 min sans le moindre event) */}
      {isLikelyStuck && (
        <div style={{ color: '#fca5a5', fontSize: 11, marginTop: 4 }}>
          ⚠ Aucun event depuis {Math.round(elapsedSinceUpdate / 60)} min. Possibilites: bridge deconnecte, GPU crash, hang Blender. Verifie le terminal du PC (logs bridge_server.py + Hunyuan3D.log).
        </div>
      )}

      <style>{`
        @keyframes aurora-progress-pulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  )
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}
