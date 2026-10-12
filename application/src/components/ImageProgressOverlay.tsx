import { useEffect, useRef, useState } from 'react'

export type ImageProgressProps = {
  active: boolean
  progress: string
  phaseLabel: string
  phasePercent: number
}

export function ImageProgressOverlay({ active, progress, phaseLabel, phasePercent }: ImageProgressProps) {
  const [elapsedTotal, setElapsedTotal] = useState(0)
  const [elapsedSinceUpdate, setElapsedSinceUpdate] = useState(0)
  const startedAtRef = useRef<number | null>(null)
  const lastUpdateRef = useRef<number>(Date.now())
  const lastProgressRef = useRef<string>(progress)
  const lastPhaseRef = useRef<string>(phaseLabel)

  useEffect(() => {
    if (progress !== lastProgressRef.current || phaseLabel !== lastPhaseRef.current) {
      lastUpdateRef.current = Date.now()
      lastProgressRef.current = progress
      lastPhaseRef.current = phaseLabel
      setElapsedSinceUpdate(0)
    }
  }, [progress, phaseLabel])

  useEffect(() => {
    if (!active) {
      startedAtRef.current = null
      setElapsedTotal(0)
      setElapsedSinceUpdate(0)
      return
    }
    if (startedAtRef.current === null) {
      startedAtRef.current = Date.now()
      lastUpdateRef.current = Date.now()
    }
    const interval = setInterval(() => {
      const now = Date.now()
      setElapsedTotal(Math.floor((now - (startedAtRef.current ?? now)) / 1000))
      setElapsedSinceUpdate(Math.floor((now - lastUpdateRef.current) / 1000))
    }, 500)
    return () => clearInterval(interval)
  }, [active])

  if (!active) return null

  const percent = Math.max(0, Math.min(100, Math.round(phasePercent || 0)))
  const isQuietPhase = elapsedSinceUpdate > 30 && elapsedSinceUpdate <= 120
  const isLikelyStuck = elapsedSinceUpdate > 120
  const formattedElapsed = formatElapsed(elapsedTotal)

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 16,
        right: 16,
        zIndex: 1000,
        minWidth: 320,
        maxWidth: 420,
        background: 'rgba(28, 15, 24, 0.92)',
        border: isLikelyStuck
          ? '1px solid rgba(239, 68, 68, 0.6)'
          : isQuietPhase
            ? '1px solid rgba(234, 179, 8, 0.5)'
            : '1px solid rgba(236, 72, 153, 0.4)', // Rose/Magenta
        borderRadius: 12,
        padding: 14,
        color: '#e5e7eb',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
        fontSize: 12,
        boxShadow: '0 8px 32px rgba(236, 72, 153, 0.15)', // Glow magenta
        backdropFilter: 'blur(8px)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        {/* Heartbeat dot */}
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: isLikelyStuck ? '#ef4444' : isQuietPhase ? '#eab308' : '#ec4899',
            animation: 'aurora-image-pulse 1.4s ease-in-out infinite',
          }}
        />
        <span style={{ fontWeight: 600, color: '#fff', flex: 1 }}>
          Studio Image
        </span>
        <span style={{ color: '#a3a3a3', fontVariantNumeric: 'tabular-nums' }}>
          {formattedElapsed}
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
                : 'linear-gradient(90deg, #ec4899 0%, #d946ef 50%, #a855f7 100%)', // Gradient rose/purple
            transition: 'width 300ms ease',
          }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <span style={{ color: '#fff', fontSize: 13, fontWeight: 500 }}>
          {phaseLabel || 'Initialisation...'}
        </span>
        <span style={{ color: '#9ca3af', fontVariantNumeric: 'tabular-nums', fontSize: 13 }}>
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

      {isQuietPhase && (
        <div style={{ color: '#fcd34d', fontSize: 11, marginTop: 4 }}>
          Génération silencieuse ({elapsedSinceUpdate}s). ComfyUI / FLUX travaillent en arrière-plan.
        </div>
      )}

      {isLikelyStuck && (
        <div style={{ color: '#fca5a5', fontSize: 11, marginTop: 4 }}>
          ⚠ Aucun event depuis {Math.round(elapsedSinceUpdate / 60)} min. Possibilités : ComfyUI planté, OOM (Out of Memory) GPU. Vérifiez le terminal ComfyUI.
        </div>
      )}

      <style>{`
        @keyframes aurora-image-pulse {
          0%, 100% { opacity: 0.6; transform: scale(1); box-shadow: 0 0 0 rgba(236,72,153, 0); }
          50% { opacity: 1; transform: scale(1.2); box-shadow: 0 0 10px rgba(236,72,153, 0.6); }
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
