/**
 * AuroraV3AcademyView — Ricochet "spiral notebook" entry for Academy.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-4.jsx
 * (AcademyV3): tan-paper margin with spiral binding rings on the left,
 * lined paper with red margin line, hand-written "le nombre d'or φ"
 * lesson with highlighted "def." and "ex." markers, post-it from
 * Aurora suggesting Fibonacci link, hand-drawn spiral SVG doodle,
 * Leitner boxes I·3 / II·7 / III·12 / IV·∞.
 *
 * Real wiring: MangaAcademyView (2242 LOC of SM-2 spaced repetition,
 * Leitner boxes, AI tutor chat, exo generation, past papers indexer,
 * gamification XP) lazy-mounts as soon as the user clicks anywhere on
 * the post-it or the "ouvrir le cahier" button.
 */
import { lazy, Suspense, useState } from 'react'

const MangaAcademyView = lazy(() => import('./MangaAcademyView'))

const TAN = '#c8b89a'
const PAPER = '#ffffff'
const RED = '#d04a4a'
const INK = '#1a2840'
const PURPLE = '#a050c8'
const YELLOW = '#fff8a0'
const GREEN = '#a0e8b8'
const POSTIT = '#fff088'
const GREY_BLUE = '#5a6a90'

export default function AuroraV3AcademyView() {
  // v82ap : skip the preview state. The v3 academy "spiral notebook"
  // preview shipped hardcoded "le nombre d'or φ" lesson content from
  // the design source mock — fictif. Boot direct on the real
  // MangaAcademyView (SM-2 spaced repetition, Leitner boxes, AI tutor
  // chat, exo generation, past papers, gamification XP). Same pattern
  // as v82an for V3 Code/Voice/Video/3D.
  const [live, setLive] = useState(true)
  void setLive

  if (live) {
    return (
      <Suspense fallback={
        <div style={{
          width: '100%', height: '100%',
          background: PAPER, color: INK,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Patrick Hand, Comic Sans MS, cursive', fontSize: 18,
        }}>✦ ouverture du cahier…</div>
      }>
        <MangaAcademyView />
      </Suspense>
    )
  }

  const today = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex',
      background: `linear-gradient(90deg, ${TAN} 0%, ${TAN} 80px, ${PAPER} 80px)`,
      fontFamily: 'Patrick Hand, Comic Sans MS, cursive', color: INK,
      position: 'relative', overflow: 'auto',
    }}>
      {/* Spiral binding rings */}
      <div style={{
        position: 'absolute', left: 30, top: 0, bottom: 0,
        width: 36,
        display: 'flex', flexDirection: 'column', justifyContent: 'space-around',
        padding: '12px 0', zIndex: 2,
      }}>
        {Array.from({ length: 24 }).map((_, i) => (
          <div key={i} style={{
            width: 28, height: 16,
            border: '3px solid #888', borderRadius: '50%',
            background: 'transparent',
            boxShadow: '0 1px 0 rgba(0,0,0,0.2)',
          }} />
        ))}
      </div>

      {/* Lined paper */}
      <div style={{
        flex: 1, marginLeft: 80, padding: '36px 36px 36px 80px',
        position: 'relative',
        backgroundImage: `repeating-linear-gradient(0deg, transparent 0 31px, #6c89c4 31px 32px)`,
        borderLeft: `2px solid ${RED}`,
        minHeight: '100%',
      }}>
        {/* Red margin line */}
        <div style={{
          position: 'absolute', left: 56, top: 0, bottom: 0,
          width: 1, background: RED,
        }} />

        <div style={{
          fontSize: 13, color: RED, position: 'absolute', top: 8, right: 24,
          transform: 'rotate(-1deg)', textTransform: 'lowercase',
        }}>
          {today} ✦
        </div>

        <h1 style={{
          fontSize: 44, margin: 0, lineHeight: 1,
          transform: 'rotate(-0.5deg)', color: INK,
        }}>
          le nombre d'or  <span style={{ background: YELLOW, padding: '0 8px' }}>φ</span>
        </h1>
        <div style={{ fontSize: 16, color: GREY_BLUE, marginTop: 4 }}>
          ↳ première · maths · leçon XII
        </div>

        <div style={{ marginTop: 24, fontSize: 18, lineHeight: '32px' }}>
          <p style={{ margin: 0 }}>
            <span style={{ background: GREEN, padding: '0 4px' }}>def.</span>{' '}
            le nombre d'or, noté <em style={{ color: PURPLE }}>φ</em>,
            est cette proportion{' '}
            <span style={{ textDecoration: `underline ${RED} wavy` }}>par laquelle</span> un
          </p>
          <p style={{ margin: 0 }}>segment se laisse diviser en deux parties dont</p>
          <p style={{ margin: 0 }}>le rapport <em>grande/petite</em> = rapport <em>tout/grande</em>.</p>
          <p style={{
            margin: '32px 0 0', fontSize: 26, color: PURPLE,
            textAlign: 'center', transform: 'rotate(-0.5deg)',
          }}>
            φ = (1 + √5) / 2  ≈  1,6180...
          </p>

          <div style={{ marginTop: 32 }}>
            <span style={{ background: YELLOW, padding: '0 6px' }}>ex.</span> on retrouve φ dans :
            <ul style={{ margin: '8px 0 0', paddingLeft: 32, fontSize: 18 }}>
              <li>les <span style={{ textDecoration: 'underline' }}>spirales de nautile</span> 🐚</li>
              <li>l'arrangement des fleurs de tournesol</li>
              <li>les façades du Parthénon</li>
            </ul>
          </div>
        </div>

        {/* Aurora post-it */}
        <button type="button" onClick={() => setLive(true)}
          style={{
            position: 'absolute', top: 200, right: 40,
            width: 200, minHeight: 180,
            background: POSTIT, padding: 14,
            transform: 'rotate(4deg)', transition: 'transform 200ms ease',
            boxShadow: '4px 6px 12px rgba(0,0,0,0.18)',
            fontSize: 16, lineHeight: 1.4, textAlign: 'left',
            border: 'none', cursor: 'pointer',
            fontFamily: 'inherit', color: INK,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.transform = 'rotate(2deg) scale(1.04)' }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = 'rotate(4deg)' }}>
          <strong style={{ color: '#a8231d' }}>aurora :</strong><br/>
          tu as déjà vu φ dans la suite de Fibonacci !<br/>
          1, 1, 2, 3, 5, 8, 13...<br/>
          <span style={{ color: GREY_BLUE, fontStyle: 'italic' }}>
            → je te fais une carte ?
          </span>
        </button>

        {/* Doodle spiral */}
        <svg width="160" height="120"
          style={{
            position: 'absolute', bottom: 120, right: 60,
            transform: 'rotate(8deg)', pointerEvents: 'none',
          }}
          viewBox="0 0 160 120">
          <path d="M 80 60 m -50 0 a 50 30 0 1 0 100 0 a 30 18 0 1 0 -60 0 a 18 11 0 1 0 36 0 a 11 7 0 1 0 -22 0"
            fill="none" stroke={PURPLE} strokeWidth="2" />
          <text x="80" y="115" textAnchor="middle"
            fontFamily="Patrick Hand, cursive" fontSize="14" fill={GREY_BLUE}>
            spirale d'or
          </text>
        </svg>

        {/* Leitner boxes */}
        <div style={{
          position: 'absolute', bottom: 30, left: 90,
          display: 'flex', gap: 12, transform: 'rotate(-1deg)',
        }}>
          {[
            { label: 'I·3', bg: YELLOW },
            { label: 'II·7', bg: PAPER },
            { label: 'III·12', bg: PAPER },
            { label: 'IV·∞', bg: GREEN },
          ].map((b, i) => (
            <button key={b.label} type="button" onClick={() => setLive(true)}
              style={{
                width: 56, height: 56, border: `2px solid ${INK}`,
                background: b.bg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, transform: `rotate(${(i - 1.5) * 1.5}deg)`,
                boxShadow: '2px 2px 0 rgba(0,0,0,0.15)',
                cursor: 'pointer', fontFamily: 'inherit', color: INK,
              }}>{b.label}</button>
          ))}
        </div>

        {/* Big enter button at the bottom-right */}
        <button type="button" onClick={() => setLive(true)}
          style={{
            position: 'absolute', bottom: 40, right: 60,
            background: INK, color: PAPER, border: 'none',
            padding: '10px 20px',
            fontFamily: 'Patrick Hand, cursive', fontSize: 18,
            transform: 'rotate(-2deg)', cursor: 'pointer',
            boxShadow: '3px 3px 0 rgba(0,0,0,0.25)',
          }}>
          ✦ ouvrir le cahier
        </button>
      </div>
    </div>
  )
}
