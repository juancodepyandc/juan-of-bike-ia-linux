import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Badge {
  id: string
  label: string
  icon: string
  unlockedAt?: string
}

const ALL_BADGES: Badge[] = [
  { id: 'first_quiz', label: 'Premier quiz', icon: '🎯' },
  { id: 'streak_3', label: '3 jours de suite', icon: '🔥' },
  { id: 'streak_7', label: 'Semaine parfaite', icon: '⚡' },
  { id: 'streak_30', label: 'Mois incroyable', icon: '🏆' },
  { id: 'perfect_quiz', label: 'Sans faute', icon: '💎' },
  { id: 'speed_demon', label: 'Reponse eclair', icon: '⚡' },
  { id: 'code_master', label: 'Code master', icon: '💻' },
  { id: 'image_artist', label: 'Artiste IA', icon: '🎨' },
  { id: 'video_creator', label: 'Videaste IA', icon: '🎬' },
  { id: '3d_sculptor', label: 'Sculpteur 3D', icon: '🗿' },
  { id: 'polyglot', label: 'Polyglotte', icon: '🌍' },
  { id: 'explorer', label: 'Explorateur', icon: '🧭' },
  { id: 'level_10', label: 'Niveau 10', icon: '⭐' },
  { id: 'level_25', label: 'Legende', icon: '👑' },
]

interface GamificationState {
  xp: number
  level: number
  streak: number
  lastActivityDate: string | null
  badges: Badge[]
  quizHistory: Array<{ date: string; score: number; total: number; topic: string }>
  learningPaths: Array<{ id: string; title: string; nodes: unknown[]; createdAt: string }>

  addXp: (amount: number) => void
  updateStreak: () => void
  unlockBadge: (id: string) => void
  addQuizResult: (score: number, total: number, topic: string) => void
  addLearningPath: (path: { id: string; title: string; nodes: unknown[] }) => void
}

function levelFromXp(xp: number): number {
  return Math.floor(Math.sqrt(xp / 100)) + 1
}

export const useGamificationStore = create<GamificationState>()(
  persist(
    (set) => ({
      xp: 0,
      level: 1,
      streak: 0,
      lastActivityDate: null,
      badges: [],
      quizHistory: [],
      learningPaths: [],

      addXp: (amount) =>
        set((state) => {
          const nextXp = state.xp + amount
          const nextLevel = levelFromXp(nextXp)
          return { xp: nextXp, level: nextLevel }
        }),

      updateStreak: () =>
        set((state) => {
          const today = new Date().toISOString().slice(0, 10)
          if (state.lastActivityDate === today) return state

          const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
          const nextStreak = state.lastActivityDate === yesterday ? state.streak + 1 : 1
          return { streak: nextStreak, lastActivityDate: today }
        }),

      unlockBadge: (id) =>
        set((state) => {
          if (state.badges.some((badge) => badge.id === id)) return state
          const badge = ALL_BADGES.find((entry) => entry.id === id)
          if (!badge) return state
          return {
            badges: [...state.badges, { ...badge, unlockedAt: new Date().toISOString() }],
          }
        }),

      addQuizResult: (score, total, topic) =>
        set((state) => ({
          quizHistory: [
            ...state.quizHistory.slice(-99),
            { date: new Date().toISOString(), score, total, topic },
          ],
        })),

      addLearningPath: (path) =>
        set((state) => ({
          learningPaths: [
            ...state.learningPaths,
            { ...path, createdAt: new Date().toISOString() },
          ],
        })),
    }),
    { name: 'juan-bike-gamification', version: 1 },
  ),
)

export { ALL_BADGES }
