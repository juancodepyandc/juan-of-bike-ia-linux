/**
 * LeitnerReviewPanel — session de révision basée sur la boîte Leitner.
 * Parcourt les cartes "due" (échéance dépassée) d'un deck et demande à
 * l'utilisateur Facile / Difficile / À revoir — l'ordre Leitner classique :
 *   correct  → box++, intervalle augmenté
 *   incorrect → box=1, due immédiatement
 *
 * Le store flashcardsStore gère déjà la mécanique via `answerCard(id, correct)`.
 */
import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFlashcardsStore, type Flashcard, type FlashcardDeck } from '../stores/flashcardsStore.ts'
import { useGamificationStore } from '../stores/gamificationStore.ts'
import MarkdownPro from './MarkdownPro.tsx'

interface Props {
  deck: FlashcardDeck
  onClose: () => void
}

function minutesUntil(dueAt: number): string {
  const delta = dueAt - Date.now()
  if (delta <= 0) return 'due'
  const m = Math.round(delta / 60000)
  if (m < 60) return `${m} min`
  const h = Math.round(m / 60)
  if (h < 48) return `${h} h`
  return `${Math.round(h / 24)} j`
}

export default function LeitnerReviewPanel({ deck, onClose }: Props) {
  const cardsForDeck = useFlashcardsStore((s) => s.cardsForDeck)
  const dueCards    = useFlashcardsStore((s) => s.dueCardsForDeck)
  const answerCard  = useFlashcardsStore((s) => s.answerCard)
  const addXp       = useGamificationStore((s) => s.addXp)

  const allCards = cardsForDeck(deck.id)
  const due = useMemo(() => dueCards(deck.id), [deck.id, dueCards])
  // Snapshot the review queue at mount so it doesn't shift as we answer.
  const [queue] = useState<Flashcard[]>(() => (due.length > 0 ? due : allCards.slice(0, 20)))
  const [idx, setIdx] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [report, setReport] = useState<{ right: number; wrong: number }>({ right: 0, wrong: 0 })

  const card = queue[idx]
  const done = idx >= queue.length

  const grade = (correct: boolean) => {
    if (!card) return
    answerCard(card.id, correct)
    if (correct) { addXp(4); setReport((r) => ({ ...r, right: r.right + 1 })) }
    else         { setReport((r) => ({ ...r, wrong: r.wrong + 1 })) }
    setRevealed(false)
    setIdx((i) => i + 1)
  }

  return createPortal(
    <div className="leitner-overlay" onClick={onClose}>
      <div className="leitner-panel" onClick={(e) => e.stopPropagation()}>
        <header className="leitner-head">
          <div>
            <div className="leitner-kicker">RÉVISION LEITNER</div>
            <div className="leitner-title">{deck.subject} — {deck.theme}</div>
          </div>
          <div className="leitner-prog">{Math.min(idx + 1, queue.length)}/{queue.length}</div>
          <button type="button" onClick={onClose} className="leitner-close">✕</button>
        </header>

        {queue.length === 0 ? (
          <div className="leitner-empty">
            <p>Aucune carte dans ce deck.</p>
            <button type="button" onClick={onClose}>Fermer</button>
          </div>
        ) : done ? (
          <div className="leitner-done">
            <div className="leitner-done-big">{report.right}/{report.right + report.wrong}</div>
            <p>Cartes bien répondues.</p>
            <div className="leitner-done-meta">
              +{report.right * 4} XP · {report.wrong > 0 ? `${report.wrong} à reprendre` : 'parfait'}
            </div>
            <button type="button" onClick={onClose}>Terminer</button>
          </div>
        ) : card ? (
          <div className="leitner-card">
            <div className="leitner-card-meta">
              Box {card.box} · {card.timesCorrect}✓ {card.timesWrong}✗ · prochaine échéance : {minutesUntil(card.dueAt)}
            </div>
            <div className="leitner-card-front">
              <MarkdownPro content={card.front} idPrefix={`lt-f-${card.id}`} />
            </div>
            {!revealed ? (
              <button type="button" className="leitner-reveal" onClick={() => setRevealed(true)}>
                Révéler la réponse
              </button>
            ) : (
              <>
                <div className="leitner-card-back">
                  <MarkdownPro content={card.back} idPrefix={`lt-b-${card.id}`} />
                  {card.example && <div className="leitner-card-extra"><b>Exemple :</b> {card.example}</div>}
                  {card.mnemonic && <div className="leitner-card-extra"><b>Mnémo :</b> {card.mnemonic}</div>}
                </div>
                <div className="leitner-actions">
                  <button type="button" className="leitner-btn is-wrong" onClick={() => grade(false)}>
                    ✗ À revoir
                  </button>
                  <button type="button" className="leitner-btn is-right" onClick={() => grade(true)}>
                    ✓ Acquis
                  </button>
                </div>
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  )
}
