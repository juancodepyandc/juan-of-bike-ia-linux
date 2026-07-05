/**
 * CyberWeeklyChallenges — défis hebdomadaires Cyber, parity de
 * WeeklyChallenges Academy mais adapté aux KataRun :
 *   - Premier kata de la semaine
 *   - Épreuve no-hint full success
 *   - Score épreuve adaptatif
 *   - Diversifier disciplines
 *
 * v82dp.
 */
import { useMemo } from 'react'
import { useCyberLeaderboardStore } from '../stores/cyberLeaderboardStore'

const GOLD = 'oklch(0.74 0.13 60)'
const GREEN = 'oklch(0.72 0.12 145)'

interface Challenge {
  id: string
  label: string
  detail: string
  current: number
  target: number
  done: boolean
}

function startOfWeek(): number {
  const now = new Date()
  const day = now.getDay() === 0 ? 6 : now.getDay() - 1
  const m = new Date(now)
  m.setHours(0, 0, 0, 0)
  m.setDate(m.getDate() - day)
  return m.getTime()
}

export default function CyberWeeklyChallenges() {
  const allRuns = useCyberLeaderboardStore((s) => s.runs)

  const challenges = useMemo<Challenge[]>(() => {
    const t0 = startOfWeek()
    const wkRuns = allRuns.filter((r) => r.startedAt >= t0)
    const wkCount = wkRuns.length
    const wkEpreuve = wkRuns.filter((r) => r.mode === 'epreuve')
    const noHintFull = wkEpreuve.filter((r) =>
      r.hintsTaken === 0 && r.objectivesDone === r.totalObjectives && r.totalObjectives > 0,
    ).length
    const wkMaxScore = Math.max(0, ...wkEpreuve.map((r) => r.score ?? 0))
    const wkDisciplines = new Set(wkRuns.map((r) => r.kataId.split('-')[0]))
    const out: Challenge[] = []

    out.push({
      id: 'first-kata-week', label: '🥋 Premier kata de la semaine',
      detail: wkCount === 0 ? 'Lance ton premier kata.' : 'Bien joué !',
      current: Math.min(1, wkCount), target: 1, done: wkCount >= 1,
    })

    out.push({
      id: 'no-hint-week', label: '💎 1 épreuve no-hint full success',
      detail: 'Termine sans aucun indice avec tous les objectifs.',
      current: Math.min(1, noHintFull), target: 1, done: noHintFull >= 1,
    })

    const scoreTarget = wkMaxScore >= 1000 ? 1500 : wkMaxScore >= 500 ? 1000 : 500
    out.push({
      id: 'cyber-score-week', label: `💯 Score ≥ ${scoreTarget} en épreuve`,
      detail: `Max épreuve cette semaine : ${wkMaxScore} pts.`,
      current: wkMaxScore, target: scoreTarget,
      done: wkMaxScore >= scoreTarget,
    })

    out.push({
      id: 'three-disciplines', label: '🎯 3 disciplines différentes',
      detail: 'Pratique au moins 3 catégories Cyber cette semaine.',
      current: wkDisciplines.size, target: 3, done: wkDisciplines.size >= 3,
    })

    return out
  }, [allRuns])

  return (
    <div style={{
      padding: 8, borderRadius: 6,
      background: 'oklch(0.74 0.13 60 / 0.05)',
      border: '1px solid oklch(0.74 0.13 60 / 0.25)',
      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
    }}>
      <div style={{ marginBottom: 6, color: GOLD, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
        🎯 Défis Cyber de la semaine
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {challenges.map((c) => {
          const pct = c.target > 0 ? Math.min(100, (c.current / c.target) * 100) : 0
          return (
            <div key={c.id} style={{
              padding: '4px 6px', borderRadius: 3,
              background: c.done ? 'oklch(0.72 0.12 145 / 0.08)' : 'rgba(255,255,255,0.02)',
              border: `1px ${c.done ? 'solid' : 'dashed'} ${c.done ? GREEN : 'var(--line-soft, rgba(255,255,255,0.06))'}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{
                  color: c.done ? GREEN : 'var(--fg, #f5f5f5)',
                  fontWeight: c.done ? 700 : 400,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{c.done ? '✓' : '○'} {c.label}</span>
                <span style={{ flex: 1 }} />
                <span style={{
                  color: c.done ? GREEN : 'var(--fg-mute, #777)',
                  fontVariantNumeric: 'tabular-nums', fontSize: 9,
                }}>{c.current}/{c.target}</span>
              </div>
              {!c.done && (
                <div style={{
                  marginTop: 2, height: 2, borderRadius: 99,
                  background: 'var(--ink-800, rgba(255,255,255,0.06))',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', width: `${pct}%`,
                    background: GOLD, transition: 'width 200ms ease',
                  }} />
                </div>
              )}
              <div style={{ color: 'var(--fg-mute, #777)', fontSize: 9, marginTop: 1 }}>
                {c.detail}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
