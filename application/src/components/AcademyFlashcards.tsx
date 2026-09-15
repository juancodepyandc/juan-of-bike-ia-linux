/**
 * AcademyFlashcards — interactive flip-card viewer for a deck generated
 * by useAcademyViewLogic (mode 'flashcards'). v82bv :
 *   - flip front/back au click ou espace
 *   - next/prev
 *   - "got it / again" → réordonne le deck (revoir les "again" plus tôt)
 *   - progress bar + scoreboard simple (% confiance)
 *   - shuffle bouton
 *
 * Pas de persistance pour cette passe — la révision SM-2 long-terme
 * est queued (useFlashcardsStore + Leitner exists déjà côté manga).
 */
import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Shuffle, Check, RotateCw, Eye } from 'lucide-react'
import type { AcademyFlashcard } from '../hooks/useAcademyViewLogic.ts'

const GOLD = 'oklch(0.74 0.11 90)'
const RED = 'oklch(0.55 0.18 25)'
const GREEN = 'oklch(0.72 0.12 145)'

interface Props {
  cards: AcademyFlashcard[]
  /** v82cb : callback live à chaque progression — pour persistance
   *  externe (ex. injection dans le score d'épreuve Academy). */
  onConfidenceChange?: (pct: number) => void
}

interface ProgressEntry {
  index: number
  outcome: 'pending' | 'got' | 'again'
}

export default function AcademyFlashcards({ cards, onConfidenceChange }: Props) {
  const [order, setOrder] = useState<number[]>(() => cards.map((_, i) => i))
  const [cursor, setCursor] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const [progress, setProgress] = useState<ProgressEntry[]>(() =>
    cards.map((_, i) => ({ index: i, outcome: 'pending' })),
  )

  // Reset on deck change
  useEffect(() => {
    setOrder(cards.map((_, i) => i))
    setCursor(0)
    setFlipped(false)
    setShowHint(false)
    setProgress(cards.map((_, i) => ({ index: i, outcome: 'pending' })))
  }, [cards])

  const card = cards[order[cursor]] ?? cards[0]
  const total = cards.length
  const seen = progress.filter((p) => p.outcome !== 'pending').length
  const got = progress.filter((p) => p.outcome === 'got').length
  const confidence = total > 0 ? Math.round((got / total) * 100) : 0

  // v82cb : push live le confidence vers le hook parent pour
  // persistance dans le leaderboard épreuve.
  useEffect(() => {
    onConfidenceChange?.(confidence)
  }, [confidence, onConfidenceChange])

  const goto = (delta: number) => {
    if (total === 0) return
    setCursor((c) => Math.max(0, Math.min(total - 1, c + delta)))
    setFlipped(false)
    setShowHint(false)
  }

  const mark = (outcome: 'got' | 'again') => {
    const realIdx = order[cursor]
    setProgress((prev) =>
      prev.map((p) => (p.index === realIdx ? { ...p, outcome } : p)),
    )
    if (outcome === 'again') {
      // re-pousse 3 cartes plus loin pour qu'elle revienne
      setOrder((prev) => {
        const next = [...prev]
        const removed = next.splice(cursor, 1)[0]
        const insertAt = Math.min(next.length, cursor + 3)
        next.splice(insertAt, 0, removed)
        return next
      })
      setFlipped(false)
      setShowHint(false)
      // cursor pointe maintenant sur la carte suivante qui a glissé
    } else {
      goto(1)
    }
  }

  const shuffle = () => {
    setOrder((prev) => {
      const arr = [...prev]
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]]
      }
      return arr
    })
    setCursor(0)
    setFlipped(false)
    setShowHint(false)
  }

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.code === 'Space' || e.key === 'Enter') { e.preventDefault(); setFlipped((v) => !v) }
      else if (e.key === 'ArrowRight') { e.preventDefault(); goto(1) }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); goto(-1) }
      else if (e.key === '1' || e.key.toLowerCase() === 'a') { e.preventDefault(); mark('again') }
      else if (e.key === '2' || e.key.toLowerCase() === 'g') { e.preventDefault(); mark('got') }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cursor, order, total])  // eslint-disable-line react-hooks/exhaustive-deps

  if (!card || total === 0) {
    return (
      <div style={{
        padding: 16, fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
        color: 'var(--fg-mute, #777)',
      }}>Aucune carte parsée — relance la génération.</div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Header progress */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, fontSize: 11,
        fontFamily: 'var(--font-mono, monospace)', color: 'var(--fg-dim, #aaa)',
      }}>
        <span style={{ color: GOLD, fontWeight: 700 }}>{cursor + 1}/{total}</span>
        <span>·</span>
        <span>{seen} vues</span>
        <span>·</span>
        <span style={{ color: GREEN }}>{got} sues</span>
        <span style={{ flex: 1 }} />
        <span>{confidence}% confiance</span>
        <button type="button" onClick={shuffle} title="Mélanger"
          style={{
            padding: 4, background: 'transparent', color: 'var(--fg-dim, #aaa)',
            border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 4,
            cursor: 'pointer', display: 'inline-flex',
          }}><Shuffle size={11} /></button>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, borderRadius: 99, background: 'var(--ink-800, rgba(255,255,255,0.06))', overflow: 'hidden' }}>
        <div style={{
          width: `${(seen / total) * 100}%`, height: '100%',
          background: `linear-gradient(90deg, ${GREEN}, ${GOLD})`,
          transition: 'width 200ms ease',
        }} />
      </div>

      {/* Card */}
      <div
        onClick={() => setFlipped((v) => !v)}
        style={{
          minHeight: 180, padding: 20,
          background: flipped ? 'var(--bg-card, rgba(255,255,255,0.05))' : 'var(--bg-raised, rgba(255,255,255,0.03))',
          border: `1px solid ${flipped ? GOLD : 'var(--line, rgba(255,255,255,0.12))'}`,
          borderRadius: 10, cursor: 'pointer',
          display: 'flex', flexDirection: 'column', gap: 10,
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          transition: 'border 200ms ease, background 200ms ease',
        }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          color: 'var(--fg-mute, #777)', letterSpacing: '0.14em',
          textTransform: 'uppercase',
        }}>
          {flipped ? '◆ verso · réponse' : '◇ recto · question'}
          {card.tag && <span style={{ color: GOLD }}>· {card.tag}</span>}
          <span style={{ flex: 1 }} />
          <span>espace pour flip</span>
        </div>
        <div style={{
          flex: 1, fontStyle: flipped ? 'normal' : 'italic',
          fontSize: flipped ? 16 : 22, letterSpacing: '-0.01em',
          color: 'var(--fg, #f5f5f5)', lineHeight: 1.4,
          fontFamily: flipped ? 'var(--font-mono, monospace)' : undefined,
          whiteSpace: 'pre-wrap',
        }}>
          {flipped ? card.back : card.front}
        </div>
        {!flipped && card.hint && (
          <div style={{ marginTop: 'auto' }}>
            {showHint ? (
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                color: 'var(--fg-dim, #aaa)', fontStyle: 'italic',
              }}>💡 {card.hint}</div>
            ) : (
              <button type="button"
                onClick={(e) => { e.stopPropagation(); setShowHint(true) }}
                style={{
                  padding: '3px 8px', fontSize: 10,
                  background: 'transparent', color: 'var(--fg-dim, #aaa)',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  borderRadius: 4, cursor: 'pointer',
                  fontFamily: 'var(--font-mono, monospace)',
                }}><Eye size={9} style={{ marginRight: 4 }} /> indice</button>
            )}
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <button type="button" onClick={() => goto(-1)} disabled={cursor === 0}
          style={{
            padding: '6px 8px', background: 'transparent',
            color: cursor === 0 ? 'var(--fg-mute, #555)' : 'var(--fg-dim, #aaa)',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            borderRadius: 6, cursor: cursor === 0 ? 'not-allowed' : 'pointer',
            display: 'inline-flex', alignItems: 'center',
          }}><ChevronLeft size={12} /></button>
        <button type="button" onClick={() => mark('again')}
          style={{
            flex: 1, padding: '6px 10px',
            background: 'transparent', color: RED,
            border: `1px solid ${RED}`,
            borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600,
            fontFamily: 'var(--font-sans, system-ui)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4,
          }}><RotateCw size={11} /> Encore (1/A)</button>
        <button type="button" onClick={() => mark('got')}
          style={{
            flex: 1, padding: '6px 10px',
            background: GREEN, color: '#0a0a0a',
            border: 'none', borderRadius: 6, cursor: 'pointer',
            fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-sans, system-ui)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4,
          }}><Check size={11} /> Su (2/G)</button>
        <button type="button" onClick={() => goto(1)} disabled={cursor === total - 1}
          style={{
            padding: '6px 8px', background: 'transparent',
            color: cursor === total - 1 ? 'var(--fg-mute, #555)' : 'var(--fg-dim, #aaa)',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            borderRadius: 6, cursor: cursor === total - 1 ? 'not-allowed' : 'pointer',
            display: 'inline-flex', alignItems: 'center',
          }}><ChevronRight size={12} /></button>
      </div>
    </div>
  )
}
