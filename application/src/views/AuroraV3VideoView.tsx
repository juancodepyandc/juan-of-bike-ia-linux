/**
 * AuroraV3VideoView — Ricochet "STEENBECK FLATBED EDITOR" entry.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-3.jsx
 * (VideoV3): brushed-steel diagonal hatched background, brand plate
 * STEENBECK + italic "Aurora Cinematica", red REC + timecode
 * 00:04/00:08 + 24fps, viewer with sepia-tinted moonlit landscape
 * SVG, film perforations on each side, vectorscope + RGB waveform,
 * 16-frame film strip timeline with selected shot, transport
 * controls (⏮ ◀◀ ◀ ■ ▶ ▶▶ ⏭) + SHUTTLE/JOG knobs.
 *
 * Real wiring: MangaVideoView (972 LOC) is lazy-mounted as soon as the
 * user clicks ▶ — every Manga feature stays alive (cinema API,
 * storyboard, voice library, batch render, MP4 export).
 */
import { lazy, Suspense, useEffect, useState } from 'react'

const MangaVideoView = lazy(() => import('./MangaVideoView'))

const STEEL_BG = 'linear-gradient(135deg, #6a6a6a 0%, #4a4a4a 50%, #5a5a5a 100%)'
const STEEL_HATCH = 'repeating-linear-gradient(135deg, transparent 0 2px, rgba(0,0,0,0.04) 2px 3px)'
const RED = '#a8231d'
const CREAM = '#f5f0d8'
const INK = '#1a1a1a'
const GREEN = '#7df9c4'
const RGB_R = '#ff6b6b'
const RGB_G = '#7df9c4'
const RGB_B = '#6b9eff'

export default function AuroraV3VideoView() {
  // v82an : skip preview, boot direct sur MangaVideoView.
  const [live, setLive] = useState(true)
  void setLive
  const [t, setT] = useState(0)
  useEffect(() => {
    if (live) return
    let raf = 0
    const loop = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [live])

  if (live) {
    return (
      <Suspense fallback={
        <div style={{
          width: '100%', height: '100%',
          background: '#1a1a1a', color: CREAM,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Helvetica Neue, sans-serif',
          letterSpacing: '0.4em', fontSize: 14,
        }}>STEENBECK · ENGAGING REELS…</div>
      }>
        <MangaVideoView />
      </Suspense>
    )
  }

  return (
    <div style={{
      width: '100%', height: '100%',
      background: STEEL_BG, backgroundImage: STEEL_HATCH,
      padding: 20,
      display: 'grid',
      gridTemplateRows: '40px 1fr auto auto', gap: 16,
      fontFamily: 'Helvetica Neue, sans-serif', color: INK, overflow: 'hidden',
    }}>
      {/* Brand plate header */}
      <header style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: '2px solid #2a2a2a', paddingBottom: 6,
      }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'baseline' }}>
          <span style={{
            background: INK, color: CREAM, padding: '3px 10px',
            fontSize: 11, letterSpacing: '0.3em', fontWeight: 700,
          }}>STEENBECK</span>
          <span style={{
            fontFamily: 'Georgia, serif', fontStyle: 'italic', fontSize: 22,
          }}>Aurora Cinematica</span>
        </div>
        <div style={{ display: 'flex', gap: 8, fontSize: 11 }}>
          <span style={{ background: RED, color: '#fff', padding: '3px 8px' }}>● REC</span>
          <span style={{ background: INK, color: CREAM, padding: '3px 8px' }}>00:04 / 00:08</span>
          <span style={{ background: INK, color: CREAM, padding: '3px 8px' }}>24fps</span>
        </div>
      </header>

      {/* Viewer + scopes */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16, minHeight: 0 }}>
        {/* Viewer */}
        <div style={{
          background: '#0a0a0a', border: '8px solid #2a2a2a', borderRadius: 4,
          boxShadow: 'inset 0 0 30px rgba(0,0,0,0.8), 0 6px 20px rgba(0,0,0,0.5)',
          position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer',
        }}
          onClick={() => setLive(true)}>
          <svg viewBox="0 0 400 220" width="100%" height="100%" style={{ filter: 'sepia(0.3) contrast(1.1)' }}>
            <defs>
              <radialGradient id="moon" cx="70%" cy="30%">
                <stop offset="0%" stopColor="#f8e4a0" />
                <stop offset="100%" stopColor="#1a1410" />
              </radialGradient>
            </defs>
            <rect width="400" height="220" fill="url(#moon)" />
            <path d="M 0 180 Q 100 140 200 170 T 400 165 L 400 220 L 0 220 Z" fill="#0a0806" />
            <path d="M 80 200 L 110 100 L 140 200 Z" fill="#1a1410" />
            <path d="M 200 195 L 240 110 L 280 195 Z" fill="#1a1410" />
          </svg>
          <div style={{
            position: 'absolute', top: 8, left: 12,
            color: RED, fontFamily: 'Courier New, monospace', fontSize: 11, letterSpacing: '0.2em',
          }}>● REC · A001_C012</div>
          <div style={{
            position: 'absolute', bottom: 8, right: 12,
            color: CREAM, fontFamily: 'Courier New, monospace', fontSize: 11,
          }}>TC 01:00:0{Math.floor(t) % 10}:{String(Math.floor(t * 24) % 24).padStart(2, '0')}</div>
          <div style={{
            position: 'absolute', left: -22, top: 8, bottom: 8, width: 14,
            background: 'repeating-linear-gradient(0deg, #2a2a2a 0 12px, #4a4a4a 12px 18px)',
          }} />
          <div style={{
            position: 'absolute', right: -22, top: 8, bottom: 8, width: 14,
            background: 'repeating-linear-gradient(0deg, #2a2a2a 0 12px, #4a4a4a 12px 18px)',
          }} />
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: 0.4 + Math.abs(Math.sin(t * 2)) * 0.4,
          }}>
            <div style={{
              background: RED, color: CREAM, padding: '12px 24px',
              fontSize: 13, letterSpacing: '0.4em', fontFamily: 'inherit',
              boxShadow: '0 4px 12px rgba(0,0,0,0.6)',
            }}>▶ JOUER LA BOBINE</div>
          </div>
        </div>

        {/* Scopes */}
        <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 12, minHeight: 0 }}>
          <div style={{ background: '#0a0a0a', border: '4px solid #2a2a2a', padding: 12 }}>
            <div style={{ color: GREEN, fontFamily: 'Courier New, monospace', fontSize: 10, letterSpacing: '0.2em' }}>VECTORSCOPE</div>
            <svg viewBox="-50 -50 100 100" width="100%" height="80%">
              <circle r="40" fill="none" stroke="#2a4a3a" strokeWidth="0.5" />
              <circle r="25" fill="none" stroke="#2a4a3a" strokeWidth="0.5" />
              {Array.from({ length: 200 }).map((_, i) => {
                const a = (i / 200) * Math.PI * 2 + t * 0.2
                const r = 8 + (i % 30) + Math.abs(Math.sin(t * 0.4 + i)) * 12
                return <circle key={i}
                  cx={Math.cos(a) * r} cy={Math.sin(a) * r}
                  r="0.4" fill={GREEN} opacity="0.6" />
              })}
            </svg>
          </div>
          <div style={{ background: '#0a0a0a', border: '4px solid #2a2a2a', padding: 12 }}>
            <div style={{ color: GREEN, fontFamily: 'Courier New, monospace', fontSize: 10, letterSpacing: '0.2em' }}>WAVEFORM RGB</div>
            <svg viewBox="0 0 200 60" width="100%" height="80%">
              {[RGB_R, RGB_G, RGB_B].map((c, j) => (
                <g key={c} opacity="0.7">
                  {Array.from({ length: 80 }).map((_, i) => {
                    const h = 8 + Math.abs(Math.sin(i * 0.3 + j + t * 1.5)) * 30
                    return <rect key={i} x={i * 2.5} y={50 - h} width="1" height={h} fill={c} />
                  })}
                </g>
              ))}
            </svg>
          </div>
        </div>
      </div>

      {/* Film strip timeline */}
      <div style={{ background: '#1a1a1a', border: '4px solid #2a2a2a', padding: '14px 18px' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          color: CREAM, fontSize: 10, letterSpacing: '0.2em', marginBottom: 8,
        }}>
          <span>FILM · 35mm · ROLL #04</span>
          <span>16 PRISES · 1 SÉLECTIONNÉE</span>
        </div>
        <div style={{ display: 'flex', gap: 0, position: 'relative', overflow: 'hidden' }}>
          {Array.from({ length: 16 }).map((_, i) => (
            <div key={i} style={{
              flex: 1, aspectRatio: '4/3',
              background: i === 4 ? '#3a2a1a' : '#0a0a0a',
              border: i === 4 ? '2px solid #f5d040' : 'none',
              backgroundImage: `radial-gradient(circle at ${30 + i * 4}% 50%, rgba(248,228,160,0.3), transparent 50%)`,
              position: 'relative',
              cursor: 'pointer',
            }} onClick={() => setLive(true)}>
              <div style={{
                position: 'absolute', left: 0, right: 0, top: 0, height: 6,
                background: 'repeating-linear-gradient(90deg, #2a2a2a 0 5px, transparent 5px 8px)',
              }} />
              <div style={{
                position: 'absolute', left: 0, right: 0, bottom: 0, height: 6,
                background: 'repeating-linear-gradient(90deg, #2a2a2a 0 5px, transparent 5px 8px)',
              }} />
              <div style={{
                position: 'absolute', bottom: 8, left: 4,
                fontSize: 8, color: CREAM, fontFamily: 'Courier New, monospace',
              }}>{String(i + 1).padStart(2, '0')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Transport controls */}
      <div style={{
        background: '#3a3a3a', border: '1px solid #1a1a1a', padding: 12,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)',
      }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['⏮', '◀◀', '◀', '■', '▶', '▶▶', '⏭'].map((c, i) => (
            <button key={i} type="button"
              onClick={i === 4 ? () => setLive(true) : undefined}
              style={{
                width: 50, height: 36,
                background: i === 4 ? RED : INK,
                color: CREAM, border: '1px solid #5a5a5a',
                fontSize: 14, cursor: 'pointer',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)',
                fontFamily: 'inherit',
              }}>{c}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
          {['SHUTTLE', 'JOG'].map((l) => (
            <div key={l} style={{ textAlign: 'center' }}>
              <div style={{
                width: 56, height: 56, borderRadius: '50%',
                background: 'radial-gradient(circle at 30% 30%, #6a6a6a, #2a2a2a 70%, #0a0a0a)',
                border: '2px solid #1a1a1a', position: 'relative',
              }}>
                <div style={{
                  position: 'absolute', top: 6, left: '50%',
                  width: 4, height: 14, background: '#f5d040',
                  transform: `translateX(-50%) rotate(${l === 'SHUTTLE' ? Math.sin(t) * 30 : Math.cos(t * 0.7) * 25}deg)`,
                  transformOrigin: '50% 22px',
                }} />
              </div>
              <div style={{
                fontSize: 9, color: CREAM, letterSpacing: '0.2em', marginTop: 4,
              }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
