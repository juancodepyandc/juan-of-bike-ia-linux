import { create } from 'zustand'
import { persist } from 'zustand/middleware'
// Re-export pure utilities from dedicated module so existing imports continue to work
export { detectSubjectKind, SUBJECT_HINTS } from '../utils/subjectDetection.ts'
export type { SubjectKind } from '../utils/subjectDetection.ts'
import type { SubjectKind } from '../utils/subjectDetection.ts'

export type LeitnerBox = 1 | 2 | 3 | 4 | 5

export type KeyPoint = { label: string; detail?: string }
export type DateEvent = { year: string; event: string }

export type FlashcardKind = 'revision' | 'qa'

export type FlashcardVerificationStatus = 'verified' | 'general' | 'uncertain' | 'contradicted'

export type FlashcardVerification = {
  status: FlashcardVerificationStatus
  citedSources: number[]
  reasoning: string
  contradiction?: string
}

export type Flashcard = {
  id: string
  deckId: string
  kind: FlashcardKind
  front: string
  back: string
  /** Structured revision content (kind === 'revision'). */
  summary?: string
  /** Deep dive — 1-2 paragraphs that truly explain the concept. */
  deepDive?: string
  /** Why this concept matters (context / stakes / usage). */
  whyItMatters?: string
  keyPoints?: KeyPoint[]
  highlights?: string[]
  mnemonic?: string
  example?: string
  formula?: string
  quote?: string
  quoteAuthor?: string
  dates?: DateEvent[]
  /** Legacy flashcard Q/A helper. */
  hint?: string
  tags: string[]
  box: LeitnerBox
  streak: number
  dueAt: number
  lastReviewedAt?: number
  timesCorrect: number
  timesWrong: number
  createdAt: number
  /** Fact-check report from the second-pass verification pipeline. */
  verification?: FlashcardVerification
}

export type FlashcardDeck = {
  id: string
  subject: string
  theme: string
  description?: string
  level: 'debutant' | 'intermediaire' | 'avance'
  subjectKind?: SubjectKind
  accentHue?: number
  createdAt: number
  updatedAt: number
  cardCount: number
  masteredCount: number
}

type FlashcardsState = {
  decks: FlashcardDeck[]
  cards: Flashcard[]
  addDeckWithCards: (
    deck: Omit<FlashcardDeck, 'cardCount' | 'masteredCount' | 'createdAt' | 'updatedAt'>,
    cards: Array<
      Partial<Flashcard> &
        Pick<Flashcard, 'front' | 'back'> & {
          kind?: FlashcardKind
        }
    >,
  ) => FlashcardDeck
  removeDeck: (deckId: string) => void
  removeCard: (cardId: string) => void
  answerCard: (cardId: string, correct: boolean) => void
  resetDeckProgress: (deckId: string) => void
  cardsForDeck: (deckId: string) => Flashcard[]
  dueCardsForDeck: (deckId: string) => Flashcard[]
}

/** Leitner spacing (ms). Box 1 = jour meme, 5 = au delà d'une semaine. */
const LEITNER_DELAYS_MS: Record<LeitnerBox, number> = {
  1: 10 * 60 * 1000,
  2: 24 * 60 * 60 * 1000,
  3: 3 * 24 * 60 * 60 * 1000,
  4: 7 * 24 * 60 * 60 * 1000,
  5: 21 * 24 * 60 * 60 * 1000,
}

function nextBox(current: LeitnerBox, correct: boolean): LeitnerBox {
  if (!correct) return 1
  const next = (current + 1) as LeitnerBox
  return next > 5 ? 5 : next
}

function computeMastered(cards: Flashcard[]): number {
  return cards.filter((card) => card.box >= 4).length
}

function generateId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

// SUBJECT_HINTS, detectSubjectKind, SubjectKind are re-exported from utils/subjectDetection above

export const useFlashcardsStore = create<FlashcardsState>()(
  persist(
    (set, get) => ({
      decks: [],
      cards: [],

      addDeckWithCards: (deck, cardsInput) => {
        const now = Date.now()
        const newDeck: FlashcardDeck = {
          ...deck,
          createdAt: now,
          updatedAt: now,
          cardCount: cardsInput.length,
          masteredCount: 0,
        }
        const newCards: Flashcard[] = cardsInput.map((card) => ({
          id: generateId('card'),
          deckId: newDeck.id,
          kind: card.kind ?? 'revision',
          front: card.front,
          back: card.back,
          summary: card.summary,
          keyPoints: card.keyPoints,
          highlights: card.highlights,
          mnemonic: card.mnemonic,
          example: card.example,
          formula: card.formula,
          quote: card.quote,
          quoteAuthor: card.quoteAuthor,
          dates: card.dates,
          hint: card.hint,
          tags: card.tags ?? [],
          box: 1 as LeitnerBox,
          streak: 0,
          dueAt: now,
          timesCorrect: 0,
          timesWrong: 0,
          createdAt: now,
          verification: card.verification,
        }))
        set((state) => ({
          decks: [newDeck, ...state.decks],
          cards: [...newCards, ...state.cards],
        }))
        return newDeck
      },

      removeDeck: (deckId) =>
        set((state) => ({
          decks: state.decks.filter((deck) => deck.id !== deckId),
          cards: state.cards.filter((card) => card.deckId !== deckId),
        })),

      removeCard: (cardId) =>
        set((state) => {
          const card = state.cards.find((entry) => entry.id === cardId)
          if (!card) return state
          const updatedCards = state.cards.filter((entry) => entry.id !== cardId)
          const now = Date.now()
          const updatedDecks = state.decks.map((deck) => {
            if (deck.id !== card.deckId) return deck
            const deckCards = updatedCards.filter((entry) => entry.deckId === deck.id)
            return {
              ...deck,
              cardCount: deckCards.length,
              masteredCount: computeMastered(deckCards),
              updatedAt: now,
            }
          })
          return { cards: updatedCards, decks: updatedDecks }
        }),

      answerCard: (cardId, correct) =>
        set((state) => {
          const now = Date.now()
          const updatedCards = state.cards.map((card) => {
            if (card.id !== cardId) return card
            const box = nextBox(card.box, correct)
            return {
              ...card,
              box,
              streak: correct ? card.streak + 1 : 0,
              dueAt: now + LEITNER_DELAYS_MS[box],
              lastReviewedAt: now,
              timesCorrect: card.timesCorrect + (correct ? 1 : 0),
              timesWrong: card.timesWrong + (correct ? 0 : 1),
            }
          })

          const touchedCard = updatedCards.find((card) => card.id === cardId)
          const deckId = touchedCard?.deckId
          const updatedDecks = state.decks.map((deck) => {
            if (!deckId || deck.id !== deckId) return deck
            const deckCards = updatedCards.filter((card) => card.deckId === deck.id)
            return { ...deck, masteredCount: computeMastered(deckCards), updatedAt: now }
          })

          return { cards: updatedCards, decks: updatedDecks }
        }),

      resetDeckProgress: (deckId) =>
        set((state) => {
          const now = Date.now()
          const updatedCards = state.cards.map((card) =>
            card.deckId === deckId
              ? { ...card, box: 1 as LeitnerBox, streak: 0, dueAt: now, timesCorrect: 0, timesWrong: 0 }
              : card,
          )
          const updatedDecks = state.decks.map((deck) =>
            deck.id === deckId ? { ...deck, masteredCount: 0, updatedAt: now } : deck,
          )
          return { cards: updatedCards, decks: updatedDecks }
        }),

      cardsForDeck: (deckId) => get().cards.filter((card) => card.deckId === deckId),

      dueCardsForDeck: (deckId) => {
        const now = Date.now()
        return get()
          .cards.filter((card) => card.deckId === deckId)
          .sort((a, b) => a.dueAt - b.dueAt)
          .filter((card) => card.dueAt <= now || card.box <= 2)
      },
    }),
    {
      name: 'juan-bike-flashcards',
      version: 1,
      onRehydrateStorage: () => (state) => {
        if (!state) return
        state.cards = state.cards.map((card) => ({
          ...card,
          kind: card.kind ?? 'qa',
          tags: Array.isArray(card.tags) ? card.tags : [],
        }))
      },
    },
  ),
)
