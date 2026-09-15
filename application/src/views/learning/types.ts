// Shared type definitions for the Learning module
import type { LearningSource } from '../../services/learningResearch.ts'

export type Tab =
  | 'dashboard'
  | 'daily'
  | 'quiz'
  | 'courses'
  | 'library'
  | 'fiches'
  | 'parcours'
  | 'video'
  | 'physics'
  | 'chemistry'
  | 'electronics'
  | 'math'
  | 'astronomy'
  | 'modeling'
  | 'modelism'
export type QuizMode = 'classic' | 'kahoot' | 'duolingo'
export type ExerciseMode = 'words' | 'pairs' | 'fillblank'
export type QuizFormatPref = 'mcq' | 'open' | 'mix'

export type GameTerm = {
  word: string
  definition: string
  hints: string[]
}

export type GamePayload = {
  terms: GameTerm[]
  passage?: string
  blanks?: Array<{ word: string; options: string[]; sentence: string }>
}

export type QuizQuestion = {
  question: string
  options: string[]
  correctIndex: number
  explanation: string
  sourceHint?: string
  concept?: string
  /**
   * Question format. 'mcq' = classic 4-option multiple choice (default).
   * 'open' = essay/development question where the learner drafts an answer and
   * the explanation holds the full model answer + barème + grading checklist.
   */
  kind?: 'mcq' | 'open'
  /** For open questions: structured expected-answer plan the learner should cover. */
  answerOutline?: string[]
  /** For open questions: grading criteria with points per criterion. */
  gradingCriteria?: Array<{ label: string; points: number }>
  /** For open questions: total barème (sum of points). */
  totalPoints?: number
}

export type QuizPayload = {
  questions: QuizQuestion[]
  sources: LearningSource[]
}

export type LessonRef = { pathId: string; nodeIndex: number }

export type FlashcardDraft = {
  front?: string
  back?: string
  title?: string
  summary?: string
  deepDive?: string
  whyItMatters?: string
  keyPoints?: Array<string | { label: string; detail?: string }>
  highlights?: string[]
  mnemonic?: string
  example?: string
  formula?: string
  quote?: string
  quoteAuthor?: string
  dates?: Array<{ year?: string | number; event?: string }>
  hint?: string
  tags?: string[]
}

export type LearningPathNode = {
  title: string
  status: 'todo' | 'active' | 'done'
  objective?: string
  deliverable?: string
  estimatedMinutes?: number
  resources?: string[]
  /** Nœud final "Examen blanc" en conditions réelles — timer + corrigé complet. */
  isExamFinal?: boolean
  /** Durée de l'examen en minutes (60/120/180/240) si isExamFinal. */
  examDurationMinutes?: number
}


export type TocEntry = { id: string; level: 2 | 3; label: string }

export type SavedCourse = {
  id: string
  topic: string
  level: string
  summary: string
  content: string
  date: number
}


