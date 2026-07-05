import type { ComponentType } from 'react'

export type LabId =
  | 'physics'
  | 'chemistry'
  | 'astronomy'
  | 'electronics'
  | 'math'
  | 'modeling'
  | 'modelism'
  | 'courses'

export type TutorialDifficulty = 'debutant' | 'intermediaire' | 'avance'

export type QuizChoice = {
  id: string
  label: string
  correct: boolean
  explanation?: string
}

export type TutorialQuiz = {
  question: string
  choices: QuizChoice[]
  hint?: string
}

export type TutorialStepMedia =
  | { kind: 'formula'; tex: string; caption?: string }
  | { kind: 'image'; src: string; alt: string }
  | { kind: 'table'; rows: Array<Array<string>>; headers?: string[] }
  | { kind: 'quote'; text: string; author?: string }

export type TutorialStep = {
  id: string
  title: string
  body: string
  media?: TutorialStepMedia[]
  simulationId?: SimulationId
  quiz?: TutorialQuiz
  objective?: string
}

export type Tutorial = {
  id: string
  lab: LabId
  title: string
  summary: string
  difficulty: TutorialDifficulty
  durationMin: number
  xpReward: number
  tags: string[]
  prerequisites?: string[]
  steps: TutorialStep[]
}

export type SimulationId =
  | 'molecule3d'
  | 'atom-shell'
  | 'vector-playground'
  | 'unit-circle'
  | 'scale-calculator'
  | 'ohm-calculator'
  | 'phase-diagram'

export type SimulationComponent = ComponentType<{
  params?: Record<string, number | string | boolean>
}>

const SIMULATION_REGISTRY = new Map<SimulationId, () => Promise<SimulationComponent>>()

export function registerSimulation(
  id: SimulationId,
  loader: () => Promise<SimulationComponent>,
): void {
  SIMULATION_REGISTRY.set(id, loader)
}

export function getSimulationLoader(
  id: SimulationId,
): (() => Promise<SimulationComponent>) | undefined {
  return SIMULATION_REGISTRY.get(id)
}

const TUTORIAL_REGISTRY: Tutorial[] = []

export function registerTutorials(tutorials: Tutorial[]): void {
  const existingIds = new Set(TUTORIAL_REGISTRY.map((t) => t.id))
  for (const t of tutorials) {
    if (existingIds.has(t.id)) continue
    TUTORIAL_REGISTRY.push(t)
    existingIds.add(t.id)
  }
}

export function listTutorials(lab?: LabId): Tutorial[] {
  if (!lab) return [...TUTORIAL_REGISTRY]
  return TUTORIAL_REGISTRY.filter((t) => t.lab === lab)
}

export function getTutorial(id: string): Tutorial | undefined {
  return TUTORIAL_REGISTRY.find((t) => t.id === id)
}

export function computeXpReward(tutorial: Tutorial, correctRatio: number): number {
  const base = tutorial.xpReward
  const bonusMax = Math.round(base * 0.5)
  const bonus = Math.round(bonusMax * Math.max(0, Math.min(1, correctRatio)))
  return base + bonus
}

export function isStepComplete(step: TutorialStep, answer?: string): boolean {
  if (!step.quiz) return true
  if (!answer) return false
  const choice = step.quiz.choices.find((c) => c.id === answer)
  return Boolean(choice?.correct)
}

export function scoreTutorial(
  tutorial: Tutorial,
  answers: Record<string, string>,
): { correct: number; total: number; ratio: number } {
  let correct = 0
  let total = 0
  for (const step of tutorial.steps) {
    if (!step.quiz) continue
    total += 1
    const answer = answers[step.id]
    if (answer && isStepComplete(step, answer)) correct += 1
  }
  return {
    correct,
    total,
    ratio: total === 0 ? 1 : correct / total,
  }
}

// --- Spaced-repetition bridge ----------------------------------------------
// Map a quiz score ratio to an FSRS rating without coupling tutorialEngine
// directly to the scheduler (keeps cyclic imports out and tutorials testable
// without instantiating cards).
//
//   ratio < 0.25 → Again (1)
//   ratio < 0.6  → Hard (2)
//   ratio < 0.95 → Good (3)
//   ratio ≥ 0.95 → Easy (4)
export function ratioToFsrsRating(ratio: number): 1 | 2 | 3 | 4 {
  if (!Number.isFinite(ratio) || ratio <= 0.25) return 1
  if (ratio < 0.6) return 2
  if (ratio < 0.95) return 3
  return 4
}
