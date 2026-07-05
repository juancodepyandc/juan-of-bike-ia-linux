import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface CTFChallenge {
  id: string
  title: string
  category: 'crypto' | 'stego' | 'web' | 'forensics' | 'network' | 'misc'
  difficulty: 1 | 2 | 3 | 4 | 5
  description: string
  xpReward: number
  hints: string[]
  flagHash: string // SHA-256 du flag
  solutionMarkdown: string
}

interface ChallengeProgress {
  solved: boolean
  hintsUsed: number
  solvedAt: number | null
  attempts: number
}

interface CTFState {
  progress: Record<string, ChallengeProgress>
  totalXp: number
  markSolved: (id: string, xpGain: number) => void
  recordAttempt: (id: string) => void
  useHint: (id: string) => void
  reset: (id: string) => void
  resetAll: () => void
}

export const useCTFStore = create<CTFState>()(
  persist(
    (set) => ({
      progress: {},
      totalXp: 0,
      markSolved: (id, xpGain) => set((state) => {
        if (state.progress[id]?.solved) return state
        const prev = state.progress[id] || { solved: false, hintsUsed: 0, solvedAt: null, attempts: 0 }
        return {
          progress: { ...state.progress, [id]: { ...prev, solved: true, solvedAt: Date.now() } },
          totalXp: state.totalXp + xpGain,
        }
      }),
      recordAttempt: (id) => set((state) => ({
        progress: {
          ...state.progress,
          [id]: {
            solved: state.progress[id]?.solved || false,
            hintsUsed: state.progress[id]?.hintsUsed || 0,
            solvedAt: state.progress[id]?.solvedAt || null,
            attempts: (state.progress[id]?.attempts || 0) + 1,
          },
        },
      })),
      useHint: (id) => set((state) => ({
        progress: {
          ...state.progress,
          [id]: {
            solved: state.progress[id]?.solved || false,
            hintsUsed: (state.progress[id]?.hintsUsed || 0) + 1,
            solvedAt: state.progress[id]?.solvedAt || null,
            attempts: state.progress[id]?.attempts || 0,
          },
        },
      })),
      reset: (id) => set((state) => {
        const next = { ...state.progress }
        delete next[id]
        return { progress: next }
      }),
      resetAll: () => set({ progress: {}, totalXp: 0 }),
    }),
    { name: 'aurora-ctf-progress' },
  ),
)
