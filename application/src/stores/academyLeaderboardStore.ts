/**
 * academyLeaderboardStore — leaderboard local des sessions Academy
 * timed (mode épreuve). Persiste les runs avec subject + mode +
 * score + temps + flashcards confidence si applicable.
 *
 * v82by — parity avec cyberLeaderboardStore.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AcademyRun {
  id: string                   // unique key
  subject: string              // matière (Physique, Maths, …)
  mode: string                 // mode pédagogique (eval-type, …)
  topic: string                // focus / sujet de la session
  startedAt: number
  endedAt: number
  durationMs: number
  durationLimitSec: number
  score: number                // 0-1500 typique
  timeoutHit: boolean
  flashcardsConfidence?: number // % cartes "su" si mode flashcards
  // v82de : style d'apprentissage tracking
  usedVision?: boolean         // true si la session a utilisé qwen3-vl
  imagesCount?: number         // # d'images jointes (≥1 si usedVision)
}

interface State {
  runs: AcademyRun[]
  addRun: (run: AcademyRun) => void
  bestScoreFor: (subject?: string, mode?: string) => AcademyRun | null
  runsFor: (subject?: string, mode?: string) => AcademyRun[]
  clearAll: () => void
}

export const useAcademyLeaderboardStore = create<State>()(
  persist(
    (set, get) => ({
      runs: [],
      addRun: (run) => set((s) => ({ runs: [run, ...s.runs].slice(0, 200) })),
      bestScoreFor: (subject, mode) => {
        const rel = get().runs.filter((r) =>
          (subject === undefined || r.subject === subject)
          && (mode === undefined || r.mode === mode),
        )
        if (rel.length === 0) return null
        return rel.reduce((a, b) => (a.score >= b.score ? a : b))
      },
      runsFor: (subject, mode) => get().runs.filter((r) =>
        (subject === undefined || r.subject === subject)
        && (mode === undefined || r.mode === mode),
      ),
      clearAll: () => set({ runs: [] }),
    }),
    { name: 'aurora-academy-leaderboard-v1' },
  ),
)

export function formatAcademyDuration(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
