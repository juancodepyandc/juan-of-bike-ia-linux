import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type LessonStepKind = 'course' | 'fiches' | 'quiz'

export type LessonProgress = {
  pathId: string
  nodeIndex: number
  courseRead: boolean
  fichesSeen: boolean
  quizPassed: boolean
  quizScore: number | null
  lastUpdatedAt: number
}

type LessonProgressState = {
  progress: Record<string, LessonProgress>
  getProgress: (pathId: string, nodeIndex: number) => LessonProgress
  markCourseRead: (pathId: string, nodeIndex: number) => void
  markFichesSeen: (pathId: string, nodeIndex: number) => void
  recordQuizScore: (pathId: string, nodeIndex: number, scorePct: number) => void
  resetNode: (pathId: string, nodeIndex: number) => void
  resetPath: (pathId: string) => void
  isNodeComplete: (pathId: string, nodeIndex: number) => boolean
  isNodeUnlocked: (pathId: string, nodeIndex: number) => boolean
}

const QUIZ_PASSING_SCORE = 60

function keyFor(pathId: string, nodeIndex: number): string {
  return `${pathId}::${nodeIndex}`
}

function emptyProgress(pathId: string, nodeIndex: number): LessonProgress {
  return {
    pathId,
    nodeIndex,
    courseRead: false,
    fichesSeen: false,
    quizPassed: false,
    quizScore: null,
    lastUpdatedAt: 0,
  }
}

export const useLessonProgressStore = create<LessonProgressState>()(
  persist(
    (set, get) => ({
      progress: {},

      getProgress: (pathId, nodeIndex) => {
        const key = keyFor(pathId, nodeIndex)
        return get().progress[key] ?? emptyProgress(pathId, nodeIndex)
      },

      markCourseRead: (pathId, nodeIndex) =>
        set((state) => {
          const key = keyFor(pathId, nodeIndex)
          const current = state.progress[key] ?? emptyProgress(pathId, nodeIndex)
          if (current.courseRead) return state
          return {
            progress: {
              ...state.progress,
              [key]: { ...current, courseRead: true, lastUpdatedAt: Date.now() },
            },
          }
        }),

      markFichesSeen: (pathId, nodeIndex) =>
        set((state) => {
          const key = keyFor(pathId, nodeIndex)
          const current = state.progress[key] ?? emptyProgress(pathId, nodeIndex)
          if (current.fichesSeen) return state
          return {
            progress: {
              ...state.progress,
              [key]: { ...current, fichesSeen: true, lastUpdatedAt: Date.now() },
            },
          }
        }),

      recordQuizScore: (pathId, nodeIndex, scorePct) =>
        set((state) => {
          const key = keyFor(pathId, nodeIndex)
          const current = state.progress[key] ?? emptyProgress(pathId, nodeIndex)
          const quizPassed = scorePct >= QUIZ_PASSING_SCORE
          const bestScore = current.quizScore === null ? scorePct : Math.max(current.quizScore, scorePct)
          return {
            progress: {
              ...state.progress,
              [key]: {
                ...current,
                quizScore: bestScore,
                quizPassed: current.quizPassed || quizPassed,
                lastUpdatedAt: Date.now(),
              },
            },
          }
        }),

      resetNode: (pathId, nodeIndex) =>
        set((state) => {
          const key = keyFor(pathId, nodeIndex)
          if (!state.progress[key]) return state
          const next = { ...state.progress }
          delete next[key]
          return { progress: next }
        }),

      resetPath: (pathId) =>
        set((state) => {
          const next: Record<string, LessonProgress> = {}
          for (const [key, value] of Object.entries(state.progress)) {
            if (!key.startsWith(`${pathId}::`)) next[key] = value
          }
          return { progress: next }
        }),

      isNodeComplete: (pathId, nodeIndex) => {
        const progress = get().progress[keyFor(pathId, nodeIndex)]
        if (!progress) return false
        return progress.courseRead && progress.fichesSeen && progress.quizPassed
      },

      isNodeUnlocked: (pathId, nodeIndex) => {
        if (nodeIndex <= 0) return true
        return get().isNodeComplete(pathId, nodeIndex - 1)
      },
    }),
    { name: 'juan-bike-lesson-progress', version: 1 },
  ),
)

export const LESSON_QUIZ_PASSING_SCORE = QUIZ_PASSING_SCORE
