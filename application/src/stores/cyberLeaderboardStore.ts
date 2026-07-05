/**
 * cyberLeaderboardStore — local leaderboard of best runs per kata.
 * Persists {kataId, stage, time_ms, hints_taken, xp} tuples and surfaces
 * personal bests + medals.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface KataRun {
  kataId: string
  stage: number            // 1..4
  startedAt: number
  endedAt: number
  durationMs: number
  hintsTaken: number       // total deep hints used
  flagsFound: number
  objectivesDone: number
  totalObjectives: number
  xpEarned: number
  // v82bs : mode épreuve metadata. Champs optionnels pour
  // backward-compat avec les runs persistés avant cette version.
  mode?: 'libre' | 'epreuve'
  score?: number           // score time-based de l'épreuve (0 en libre)
  timeoutHit?: boolean     // true si la run s'est terminée sur timeout
  durationLimitSec?: number // durée prévue de l'épreuve
}

interface State {
  runs: KataRun[]
  addRun: (run: KataRun) => void
  bestFor: (kataId: string, stage?: number) => KataRun | null
  // v82bs : meilleur SCORE (épreuve only) au lieu du meilleur temps.
  bestScoreFor: (kataId: string, stage?: number) => KataRun | null
  runsFor: (kataId: string) => KataRun[]
  // v82bs : runs filtrés sur mode épreuve only — pour leaderboard
  // "course chrono" séparé du leaderboard "rapide en libre".
  epreuveRunsFor: (kataId: string) => KataRun[]
  totalTimeMs: () => number
  clearAll: () => void
}

export const useCyberLeaderboardStore = create<State>()(
  persist(
    (set, get) => ({
      runs: [],
      addRun: (run) => set((s) => ({ runs: [run, ...s.runs].slice(0, 200) })),
      bestFor: (kataId, stage) => {
        const relevant = get().runs.filter((r) => r.kataId === kataId && (stage === undefined || r.stage === stage))
        if (relevant.length === 0) return null
        return relevant.reduce((a, b) => (a.durationMs <= b.durationMs ? a : b))
      },
      // v82bs : meilleur run épreuve par SCORE (descendant). Filtre
      // sur mode === 'epreuve' uniquement, ignore les libres.
      bestScoreFor: (kataId, stage) => {
        const relevant = get().runs.filter((r) =>
          r.kataId === kataId
          && r.mode === 'epreuve'
          && (stage === undefined || r.stage === stage)
        )
        if (relevant.length === 0) return null
        return relevant.reduce((a, b) => ((a.score ?? 0) >= (b.score ?? 0) ? a : b))
      },
      runsFor: (kataId) => get().runs.filter((r) => r.kataId === kataId),
      epreuveRunsFor: (kataId) => get().runs.filter((r) => r.kataId === kataId && r.mode === 'epreuve'),
      totalTimeMs: () => get().runs.reduce((s, r) => s + r.durationMs, 0),
      clearAll: () => set({ runs: [] }),
    }),
    { name: 'aurora-cyber-leaderboard-v1' },
  ),
)

export function formatDuration(ms: number): string {
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h${String(m).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function medalFor(run: KataRun, best: KataRun | null): '🥇' | '🥈' | '🥉' | null {
  if (!best) return '🥇'
  if (run.durationMs <= best.durationMs) return '🥇'
  if (run.durationMs <= best.durationMs * 1.25) return '🥈'
  if (run.durationMs <= best.durationMs * 1.6) return '🥉'
  return null
}
