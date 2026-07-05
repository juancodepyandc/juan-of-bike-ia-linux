import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type TutorialProgress = {
  tutorialId: string
  currentStepIndex: number
  answers: Record<string, string>
  startedAt: number
  completedAt?: number
  lastSeenAt: number
  correctCount: number
  totalQuizzes: number
}

type TutorialState = {
  progress: Record<string, TutorialProgress>
  completed: string[]
  activeTutorialId: string | null

  openTutorial: (id: string) => void
  closeTutorial: () => void
  setStepIndex: (tutorialId: string, index: number) => void
  recordAnswer: (tutorialId: string, stepId: string, answerId: string, correct: boolean) => void
  markCompleted: (tutorialId: string, totalQuizzes: number, correctCount: number) => void
  resetTutorial: (tutorialId: string) => void
  isCompleted: (tutorialId: string) => boolean
  getProgress: (tutorialId: string) => TutorialProgress | undefined
}

function freshProgress(tutorialId: string): TutorialProgress {
  const now = Date.now()
  return {
    tutorialId,
    currentStepIndex: 0,
    answers: {},
    startedAt: now,
    lastSeenAt: now,
    correctCount: 0,
    totalQuizzes: 0,
  }
}

export const useTutorialStore = create<TutorialState>()(
  persist(
    (set, get) => ({
      progress: {},
      completed: [],
      activeTutorialId: null,

      openTutorial: (id) =>
        set((state) => {
          const existing = state.progress[id]
          const now = Date.now()
          if (existing) {
            return {
              activeTutorialId: id,
              progress: {
                ...state.progress,
                [id]: { ...existing, lastSeenAt: now },
              },
            }
          }
          return {
            activeTutorialId: id,
            progress: { ...state.progress, [id]: freshProgress(id) },
          }
        }),

      closeTutorial: () => set({ activeTutorialId: null }),

      setStepIndex: (tutorialId, index) =>
        set((state) => {
          const current = state.progress[tutorialId] ?? freshProgress(tutorialId)
          return {
            progress: {
              ...state.progress,
              [tutorialId]: {
                ...current,
                currentStepIndex: Math.max(0, index),
                lastSeenAt: Date.now(),
              },
            },
          }
        }),

      recordAnswer: (tutorialId, stepId, answerId, correct) =>
        set((state) => {
          const current = state.progress[tutorialId] ?? freshProgress(tutorialId)
          const prevAnswer = current.answers[stepId]
          const hadCorrect = prevAnswer
            ? current.answers[stepId] === answerId && correct
            : false
          return {
            progress: {
              ...state.progress,
              [tutorialId]: {
                ...current,
                answers: { ...current.answers, [stepId]: answerId },
                correctCount:
                  hadCorrect
                    ? current.correctCount
                    : current.correctCount + (correct ? 1 : 0) - (prevAnswer && !correct ? 0 : 0),
                lastSeenAt: Date.now(),
              },
            },
          }
        }),

      markCompleted: (tutorialId, totalQuizzes, correctCount) =>
        set((state) => {
          const current = state.progress[tutorialId] ?? freshProgress(tutorialId)
          const now = Date.now()
          const alreadyCompleted = state.completed.includes(tutorialId)
          return {
            progress: {
              ...state.progress,
              [tutorialId]: {
                ...current,
                completedAt: now,
                totalQuizzes,
                correctCount,
                lastSeenAt: now,
              },
            },
            completed: alreadyCompleted ? state.completed : [...state.completed, tutorialId],
          }
        }),

      resetTutorial: (tutorialId) =>
        set((state) => ({
          progress: { ...state.progress, [tutorialId]: freshProgress(tutorialId) },
          completed: state.completed.filter((id) => id !== tutorialId),
        })),

      isCompleted: (tutorialId) => get().completed.includes(tutorialId),

      getProgress: (tutorialId) => get().progress[tutorialId],
    }),
    { name: 'aurora-tutorial-progress', version: 1 },
  ),
)
