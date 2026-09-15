/**
 * PomodoroTimer — floating pomodoro widget for Academy.
 *
 * Cycles : 25 min work → 5 min pause × 4 then 20 min long break.
 * At the end of each work session, awards +15 XP + emits a bus notification
 * so the user sees "Session finie !" even when the tab is hidden (requires
 * PWA install on iOS, cf. existing notificationBus).
 */
import { useEffect, useRef, useState } from 'react'
import { useGamificationStore } from '../stores/gamificationStore.ts'
import { emit as emitNotif } from '../utils/notificationBus.ts'

type Phase = 'work' | 'short' | 'long' | 'idle'

const DURATIONS: Record<Exclude<Phase, 'idle'>, number> = {
  work: 25 * 60,
  short: 5 * 60,
  long: 20 * 60,
}

function formatClock(seconds: number): string {
  const m = Math.max(0, Math.floor(seconds / 60))
  const s = Math.max(0, seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

interface Props {
  /** Dock at bottom-right of the parent; default true. */
  floating?: boolean
}

export default function PomodoroTimer({ floating = true }: Props) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [left, setLeft] = useState(DURATIONS.work)
  const [cycle, setCycle] = useState(0)
  const addXp = useGamificationStore((s) => s.addXp)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [collapsed, setCollapsed] = useState(true)

  useEffect(() => {
    if (phase === 'idle') {
      if (tickRef.current) clearInterval(tickRef.current)
      return
    }
    tickRef.current = setInterval(() => {
      setLeft((l) => {
        if (l <= 1) {
          // Phase ends
          if (tickRef.current) clearInterval(tickRef.current)
          onPhaseEnd()
          return 0
        }
        return l - 1
      })
    }, 1000)
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

  const onPhaseEnd = () => {
    if (phase === 'work') {
      addXp(15)
      emitNotif({
        kind: 'generation.finished',
        source: 'academy',
        title: '🎯 Session pomodoro terminée',
        body: '+15 XP · Prends une pause',
        tone: 'ok', seal: '✦', push: true,
      })
      const nextCycle = cycle + 1
      setCycle(nextCycle)
      const isLong = nextCycle % 4 === 0
      setPhase(isLong ? 'long' : 'short')
      setLeft(isLong ? DURATIONS.long : DURATIONS.short)
    } else {
      emitNotif({
        kind: 'info',
        title: '⚡ Retour au travail',
        body: 'Nouvelle session de 25 min',
        tone: 'info', seal: '▶',
      })
      setPhase('work')
      setLeft(DURATIONS.work)
    }
  }
  const start = () => {
    setPhase('work')
    setLeft(DURATIONS.work)
    setCollapsed(false)
  }
  const pause = () => {
    if (tickRef.current) clearInterval(tickRef.current)
    setPhase('idle')
  }
  const reset = () => {
    if (tickRef.current) clearInterval(tickRef.current)
    setPhase('idle')
    setLeft(DURATIONS.work)
    setCycle(0)
  }
  const skip = () => {
    // End current phase immediately, trigger onPhaseEnd
    onPhaseEnd()
  }

  const totalSecs = phase !== 'idle' ? DURATIONS[phase] : DURATIONS.work
  const pct = totalSecs > 0 ? (1 - left / totalSecs) * 100 : 0

  return (
    <div className={`pomo ${floating ? 'is-floating' : ''} ${collapsed ? 'is-collapsed' : ''} phase-${phase}`}>
      {collapsed ? (
        <button type="button" className="pomo-collapsed" onClick={() => setCollapsed(false)} title="Pomodoro">
          <span className="pomo-icon">🍅</span>
          {phase !== 'idle' && <span className="pomo-mini-clock">{formatClock(left)}</span>}
        </button>
      ) : (
        <>
          <div className="pomo-head">
            <span className="pomo-phase">{
              phase === 'work' ? 'FOCUS'
              : phase === 'short' ? 'PAUSE COURTE'
              : phase === 'long' ? 'PAUSE LONGUE'
              : 'POMODORO'
            }</span>
            <button type="button" className="pomo-min" onClick={() => setCollapsed(true)}>–</button>
          </div>
          <div className="pomo-clock">{formatClock(left)}</div>
          <div className="pomo-bar"><span style={{ width: `${pct}%` }} /></div>
          <div className="pomo-cycle">cycle {cycle}/4</div>
          <div className="pomo-actions">
            {phase === 'idle' ? (
              <button type="button" className="pomo-btn is-primary" onClick={start}>▶ Démarrer</button>
            ) : (
              <>
                <button type="button" className="pomo-btn" onClick={pause}>⏸ Pause</button>
                <button type="button" className="pomo-btn" onClick={skip}>⏭ Skip</button>
              </>
            )}
            <button type="button" className="pomo-btn is-ghost" onClick={reset}>↻</button>
          </div>
        </>
      )}
    </div>
  )
}
