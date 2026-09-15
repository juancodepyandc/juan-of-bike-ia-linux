/**
 * WeeklyChallenges — défis hebdomadaires Academy basés sur des
 * patterns de l'user. Compact panel qui propose 3-4 objectifs
 * actionnables pour la semaine en cours, avec progress live.
 *
 * v82dl : pas de personnalisation IA — juste des templates qui
 * adaptent le wording / target selon les runs récents.
 */
import { useMemo } from 'react'
import { useAcademyLeaderboardStore } from '../stores/academyLeaderboardStore.ts'

const GOLD = 'oklch(0.74 0.11 90)'
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

export default function WeeklyChallenges() {
  const allRuns = useAcademyLeaderboardStore((s) => s.runs)

  const challenges = useMemo<Challenge[]>(() => {
    const t0 = startOfWeek()
    const weekRuns = allRuns.filter((r) => r.startedAt >= t0)
    const weekCount = weekRuns.length
    const cleanCount = weekRuns.filter((r) => !r.timeoutHit).length
    const maxScore = Math.max(0, ...weekRuns.map((r) => r.score))
    // Subject le plus joué cette semaine
    const subjectCounts: Record<string, number> = {}
    for (const r of weekRuns) subjectCounts[r.subject] = (subjectCounts[r.subject] || 0) + 1
    const topSubject = Object.entries(subjectCounts)
      .sort((a, b) => b[1] - a[1])[0]?.[0] || null
    // Subjects all-time
    const allSubjects = new Set(allRuns.map((r) => r.subject))
    // Subjects cette semaine
    const weekSubjects = new Set(weekRuns.map((r) => r.subject))
    // Subjects que l'user a déjà touché mais pas cette semaine
    const dormantSubjects = Array.from(allSubjects).filter((s) => !weekSubjects.has(s))

    const out: Challenge[] = []

    // 1. Démarre la semaine (si 0 sessions)
    out.push({
      id: 'first-session',
      label: '🚀 Première session de la semaine',
      detail: weekCount === 0 ? 'Lance ta première session pour démarrer.' : 'Bien joué, tu as commencé la semaine !',
      current: Math.min(1, weekCount), target: 1,
      done: weekCount >= 1,
    })

    // 2. Régularité (3 sessions sans timeout)
    out.push({
      id: 'three-clean',
      label: '🎯 3 sessions sans timeout',
      detail: 'Termine 3 épreuves cette semaine sans manquer le temps.',
      current: cleanCount, target: 3,
      done: cleanCount >= 3,
    })

    // 3. Score top — adaptatif (1500 si déjà fait, sinon 1000)
    const scoreTarget = maxScore >= 1500 ? 2000 : maxScore >= 1000 ? 1500 : 1000
    out.push({
      id: 'top-score',
      label: `💯 Atteins ${scoreTarget} pts`,
      detail: `Maximum cette semaine : ${maxScore} pts. ${maxScore >= scoreTarget ? 'Battu !' : 'Allez !'}`,
      current: maxScore, target: scoreTarget,
      done: maxScore >= scoreTarget,
    })

    // 4. Diversifie (matière dormante OU plus joué)
    if (dormantSubjects.length > 0 && allSubjects.size > 1) {
      const target = dormantSubjects[0]
      out.push({
        id: 'diversify',
        label: `🔄 Reviens sur ${target}`,
        detail: 'Tu n\'as pas pratiqué cette matière cette semaine.',
        current: weekSubjects.has(target) ? 1 : 0, target: 1,
        done: weekSubjects.has(target),
      })
    } else if (topSubject) {
      out.push({
        id: 'master-subject',
        label: `📚 Approfondis ${topSubject}`,
        detail: `Tu as joué ${subjectCounts[topSubject]} session(s). Continue !`,
        current: subjectCounts[topSubject], target: Math.max(5, subjectCounts[topSubject] + 2),
        done: false,
      })
    }

    return out
  }, [allRuns])

  if (challenges.length === 0) return null

  return (
    <div style={{
      padding: 8, borderRadius: 6,
      background: 'oklch(0.74 0.11 90 / 0.05)',
      border: '1px solid oklch(0.74 0.11 90 / 0.25)',
      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
    }}>
      <div style={{ marginBottom: 6, color: GOLD, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
        🎯 Défis de la semaine
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
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: 9,
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
