import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { LearningSource } from '../services/learningResearch'
import type { QuizQuestion, LearningPathNode } from '../views/learning/types'
import type { AcademyParcoursPayload } from '../hooks/useAcademyViewLogic'

// ---------------------------------------------------------------------------
// Types per panel
// ---------------------------------------------------------------------------

export type QuizSession = {
  topic: string
  mode: 'classic' | 'kahoot' | 'duolingo'
  questions: QuizQuestion[]
  sources: LearningSource[]
  currentIndex: number
  score: number
  quizDone: boolean
  status: string
}

export type CoursesSession = {
  topic: string
  level: string
  courseContent: string
  courseSummary: string
  sources: LearningSource[]
}

export type FichesSession = {
  subject: string
  theme: string
  level: 'debutant' | 'intermediaire' | 'avance'
  activeDeckId: string | null
}

/**
 * v82nu : profil utilisateur que le module Académie demande AVANT de générer
 * un parcours. Sert ensuite à proposer "même format la prochaine fois ?".
 * Tous les champs sont optionnels — si l'utilisateur saute la question, on
 * retombe sur des défauts raisonnables côté UI.
 */
export type LearnerProfile = {
  /** Mode de travail préféré : audio / visuel / lecture / pratique / mixte. */
  workStyle?: 'audio' | 'visuel' | 'lecture' | 'pratique' | 'mixte'
  /**
   * Format de l'évaluation / du parcours.
   * v83a : ajout de `jeu` — parcours ludique (enquête, escape game, défis
   * narratifs à étapes) plutôt qu'un simple QCM. Le générateur de parcours
   * reçoit alors des consignes spécifiques (voir ParcoursPanel).
   */
  examFormat?: 'qcm' | 'dissertation' | 'oral' | 'mixte' | 'jeu'
  /** Durée prévue de l'évaluation en minutes (30/60/120/180/240). */
  examDurationMinutes?: number
  /** Date de l'évaluation (ISO 8601 yyyy-mm-dd). */
  examDate?: string
  /** Concepts précis à maîtriser (free text, séparés par virgules ou \n). */
  focusConcepts?: string
  /** Niveau scolaire libre (ex: "Terminale Techno"). */
  schoolLevel?: string
}

/**
 * v82nu : résultat synthétique d'un parcours achevé. Sert à dire à
 * l'utilisateur "tu as eu 12/20 sur ce parcours, on régénère ciblé sur tes
 * faiblesses ?" et à proposer un raccourci "rejouer même format".
 */
export type ParcoursOutcome = {
  finishedAt: number
  finalScorePct?: number
  weakConcepts?: string[]
  strongConcepts?: string[]
}

export type ParcoursSession = {
  goal: string
  parcours: LearningPathNode[]
  activePathId: string | null
  sources: LearningSource[]
  /** v82nu : profil persisté entre les sessions (réutilisé pour "même format"). */
  profile?: LearnerProfile
  /** v82nu : dernier verdict pour proposer la régénération adaptive. */
  lastOutcome?: ParcoursOutcome
}

/**
 * iter35.D : entrée persistée dans la banque de générations académiques.
 * Permet de retrouver tous les parcours générés, triés par matière, comme
 * les autres modules (image / video / 3d) ont leur historique.
 */
export type ParcoursBankEntry = {
  id: string
  createdAt: number
  /** Matière BAC : "géographie" | "histoire" | "philo" | "anglais" | "ses" | etc. */
  subject: string
  /** Titre court du parcours (synthese.titre ou topic). */
  topic: string
  /** Date d'évaluation prévue ISO yyyy-mm-dd, optionnel. */
  examDate?: string
  /** Le payload complet pour pouvoir relancer la session. */
  payload: AcademyParcoursPayload
  /** Verdict final si la session a été terminée. */
  outcome?: ParcoursOutcome
  /** Texte de leçon original (pour contexte oral / vision). */
  lessonText?: string
  lessonName?: string | null
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

/**
 * iter31 : signal global "il y a une session de parcours BAC prête à être
 * ouverte en plein écran". Sert au cross-module auto-open : quand
 * useAcademyViewLogic finit la génération de parcours-bac alors que
 * l'utilisateur est sur un autre module, on lève ce flag, App.tsx (via
 * un hook global) bascule sur 'learning' et la vue Academy auto-ouvre
 * la page dédiée. Pas persisté volontairement : un reload plante de
 * toute façon le state in-memory du parcoursPayload.
 */
type ParcoursOverlaySignal = {
  /** True quand un parcours-bac vient d'être généré et n'est pas encore vu. */
  ready: boolean
  /** Signature stable du payload pour ne pas re-déclencher. */
  signature: string | null
}

type LearningSessionState = {
  quiz: QuizSession | null
  courses: CoursesSession | null
  fiches: FichesSession | null
  parcours: ParcoursSession | null
  /** iter31 : signal cross-module "ouvre la page parcours". */
  parcoursOverlay: ParcoursOverlaySignal
  /** iter35.D : banque persistée des parcours générés (tous matières). */
  parcoursBank: ParcoursBankEntry[]

  saveQuiz: (s: QuizSession) => void
  saveCourses: (s: CoursesSession) => void
  saveFiches: (s: FichesSession) => void
  saveParcours: (s: ParcoursSession) => void
  clearQuiz: () => void
  clearCourses: () => void
  /** iter31 : pousse le signal "parcours prêt" (appelé par useAcademyViewLogic). */
  signalParcoursReady: (signature: string) => void
  /** iter31 : marque le signal comme consommé (appelé après auto-switch). */
  consumeParcoursOverlay: () => void
  /** iter35.D : ajoute (ou remplace) un parcours dans la banque. */
  addToParcoursBank: (entry: ParcoursBankEntry) => void
  /** iter35.D : supprime un parcours de la banque. */
  removeFromParcoursBank: (id: string) => void
  /** iter35.D : met à jour le verdict d'un parcours terminé. */
  updateParcoursBankOutcome: (id: string, outcome: ParcoursOutcome) => void
}

export const useLearningSessionStore = create<LearningSessionState>()(
  persist(
    (set, get) => ({
      quiz: null,
      courses: null,
      fiches: null,
      parcours: null,
      parcoursOverlay: { ready: false, signature: null },
      parcoursBank: [],

      saveQuiz: (s) => set({ quiz: s }),
      saveCourses: (s) => set({ courses: s }),
      saveFiches: (s) => set({ fiches: s }),
      saveParcours: (s) => set({ parcours: s }),
      clearQuiz: () => set({ quiz: null }),
      clearCourses: () => set({ courses: null }),
      signalParcoursReady: (signature) => {
        const cur = get().parcoursOverlay
        if (cur.signature === signature && cur.ready) return
        set({ parcoursOverlay: { ready: true, signature } })
      },
      consumeParcoursOverlay: () => set((state) => ({
        parcoursOverlay: { ready: false, signature: state.parcoursOverlay.signature },
      })),
      addToParcoursBank: (entry) => set((state) => {
        const existing = state.parcoursBank.findIndex(e => e.id === entry.id)
        const next = [...state.parcoursBank]
        if (existing >= 0) next[existing] = entry
        else next.unshift(entry)
        // Cap raisonnable pour la persistence (50 parcours max).
        return { parcoursBank: next.slice(0, 50) }
      }),
      removeFromParcoursBank: (id) => set((state) => ({
        parcoursBank: state.parcoursBank.filter(e => e.id !== id),
      })),
      updateParcoursBankOutcome: (id, outcome) => set((state) => ({
        parcoursBank: state.parcoursBank.map(e =>
          e.id === id ? { ...e, outcome } : e,
        ),
      })),
    }),
    {
      name: 'aurora-learning-sessions',
      version: 1,
      // Le signal cross-module n'a pas de sens entre reloads — on
      // l'exclut de la persistance pour éviter de réveiller l'overlay
      // au boot suivant si l'utilisateur a quitté en plein examen.
      partialize: (state) => ({
        quiz: state.quiz,
        courses: state.courses,
        fiches: state.fiches,
        parcours: state.parcours,
        parcoursBank: state.parcoursBank,
      }),
    },
  ),
)
