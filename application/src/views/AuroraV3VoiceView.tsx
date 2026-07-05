/**
 * AuroraV3VoiceView — Ricochet "Studio MK III · VOX" entry for Voice.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-2.jsx
 * (VoiceV3): brushed-metal studio aesthetic, brand plate "Aurora STUDIO
 * MK III · VOX", spinning tape reels SOURCE/TAKE-UP, VU meter with
 * animated needle, dual waveforms (input + Aurora output), 8-knob row
 * (GAIN/HI/MID/LO/REVERB/SPEED/PITCH/VOL).
 *
 * Like V1, the live session delegates to the full VoiceCopilotView so
 * every Manga feature is preserved verbatim — this skin only re-styles
 * the *entry/control room* before the session begins.
 */
import { lazy, Suspense, useEffect, useState } from 'react'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

const CREAM = '#e8d8a8'
const TAN = '#5a4a2a'
const RED = '#a8231d'
const STEEL = '#161616'

interface AuroraV3VoiceViewProps {
  // v82ay : same overlay-close pattern as AuroraV1VoiceView. When
  // mounted via the App-level voiceOverlayOpen, onClose closes the
  // overlay outright instead of returning to the (skipped) preview.
  onClose?: () => void
}

export default function AuroraV3VoiceView({ onClose }: AuroraV3VoiceViewProps = {}) {
  // v82an : skip preview, boot direct sur VoiceCopilotView. setLive
  // gardé en scope pour que le JSX preview en dessous type-check ;
  // jamais atteint au runtime car early-return live=true.
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
          background: '#1a1a1a',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: CREAM, fontFamily: 'Helvetica Neue, sans-serif',
          letterSpacing: '0.4em', fontSize: 14,
        }}>STUDIO MK III · MIKE OUVERT…</div>
      }>
        <VoiceCopilotView onClose={onClose ?? (() => setLive(false))} />
      </Suspense>
    )
  }

  const needle = -45 + Math.sin(t * 4) * 20 + 30

  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(180deg, #1a1a1a 0%, #0d0d0d 100%)',
      color: CREAM, fontFamily: 'Helvetica Neue, Arial, sans-serif',
      padding: 24,
      display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto 1fr auto',
      gap: 18, overflow: 'hidden',
    }}>
      {/* Brand plate */}
      <div style={{
        gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        borderBottom: `2px solid ${TAN}`, paddingBottom: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <span style={{
            fontFamily: 'Georgia, serif', fontStyle: 'italic',
            fontSize: 32, color: CREAM,
          }}>Aurora</span>
          <span style={{ fontSize: 11, letterSpacing: '0.4em', color: '#8a7a4a' }}>
            STUDIO · MK III · VOX
          </span>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          {[
            { l: 'REC', primary: true, click: () => setLive(true) },
            { l: 'PLAY', primary: false, click: () => setLive(true) },
            { l: 'PAUSE', primary: false, click: () => {} },
            { l: 'STOP', primary: false, click: () => {} },
          ].map((b) => (
            <button key={b.l} type="button" onClick={b.click}
              style={{
                width: 60, height: 32,
                background: b.primary ? RED : '#2a2a2a',
                border: '1px solid #444', color: '#fff',
                fontSize: 10, letterSpacing: '0.2em', cursor: 'pointer',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1), 0 2px 4px rgba(0,0,0,0.5)',
                fontFamily: 'inherit',
              }}>{b.l}</button>
          ))}
        </div>
      </div>

      {/* Tape reels */}
      <div style={{
        background: STEEL, border: '1px solid #2a2a2a', padding: 24,
        display: 'flex', justifyContent: 'space-around', alignItems: 'center', position: 'relative',
      }}>
        {[0, 1].map((i) => (
          <div key={i} style={{ position: 'relative' }}>
            <div style={{
              width: 140, height: 140, borderRadius: '50%',
              background: 'radial-gradient(circle, #2a2418 0%, #1a1611 60%, #0a0808 100%)',
              border: `2px solid ${TAN}`,
              transform: `rotate(${t * 80 * (i ? -1 : 1)}deg)`,
              boxShadow: 'inset 0 0 20px rgba(0,0,0,0.8), 0 4px 16px rgba(0,0,0,0.6)',
            }}>
              {[0, 60, 120].map((a) => (
                <div key={a} style={{
                  position: 'absolute', top: '50%', left: '50%',
                  width: 60, height: 4, background: TAN,
                  transform: `translate(-50%, -50%) rotate(${a}deg)`,
                  borderRadius: 2,
                }} />
              ))}
              <div style={{
                position: 'absolute', top: '50%', left: '50%',
                transform: 'translate(-50%,-50%)',
                width: 28, height: 28, borderRadius: '50%',
                background: '#0a0808', border: `1px solid ${TAN}`,
              }} />
            </div>
            <div style={{
              textAlign: 'center', marginTop: 8,
              fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a',
            }}>
              {i === 0 ? 'SOURCE' : 'TAKE-UP'}
            </div>
          </div>
        ))}
        <div style={{
          position: 'absolute', left: '20%', right: '20%', top: '52%',
          height: 3, background: '#3a2f1a', boxShadow: '0 1px 0 #1a1611',
        }} />
      </div>

      {/* VU meter + waveforms */}
      <div style={{
        background: STEEL, border: '1px solid #2a2a2a', padding: 16,
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        <div style={{
          background: '#f0d890', border: '4px solid #1a1a1a', borderRadius: 6,
          padding: 10, position: 'relative', height: 100,
        }}>
          <svg viewBox="-100 -20 200 110" width="100%" height="100%">
            <path d="M -80 80 A 80 80 0 0 1 80 80" fill="none" stroke="#1c1410" strokeWidth="0.6" />
            {Array.from({ length: 11 }).map((_, i) => {
              const a = -90 + i * 18
              const r = a * Math.PI / 180
              const x1 = Math.sin(r) * 70, y1 = 80 - Math.cos(r) * 70
              const x2 = Math.sin(r) * 80, y2 = 80 - Math.cos(r) * 80
              return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={i > 7 ? RED : '#1c1410'} strokeWidth={i % 5 === 0 ? 1.5 : 0.7} />
            })}
            {[-20, -10, -5, 0, '+3'].map((v, i) => {
              const a = -90 + i * 24 + 12
              const r = a * Math.PI / 180
              return <text key={String(v)} x={Math.sin(r) * 56} y={80 - Math.cos(r) * 56 + 3}
                fontSize="6" fill={i > 3 ? RED : '#1c1410'} textAnchor="middle">{v}</text>
            })}
            <text x="0" y="14" textAnchor="middle" fontSize="7" fill="#1c1410"
              fontFamily="Georgia, serif" fontStyle="italic">VU</text>
            <line x1="0" y1="80"
              x2={Math.sin(needle * Math.PI / 180) * 72}
              y2={80 - Math.cos(needle * Math.PI / 180) * 72}
              stroke={RED} strokeWidth="1.5" />
            <circle cx="0" cy="80" r="3" fill="#1c1410" />
          </svg>
        </div>

        <div style={{ fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a' }}>WAVEFORM · INPUT</div>
        <svg width="100%" height="40" viewBox="0 0 400 40">
          {Array.from({ length: 100 }).map((_, i) => {
            const h = 4 + Math.abs(Math.sin(i * 0.5 + t * 3)) * 16
            return <rect key={i} x={i * 4} y={20 - h / 2} width="2" height={h} fill={CREAM} opacity={0.85} />
          })}
        </svg>

        <div style={{ fontSize: 10, letterSpacing: '0.3em', color: '#8a7a4a' }}>WAVEFORM · AURORA OUTPUT</div>
        <svg width="100%" height="40" viewBox="0 0 400 40">
          {Array.from({ length: 100 }).map((_, i) => {
            const h = 2 + Math.abs(Math.cos(i * 0.4 + t * 2)) * 12
            return <rect key={i} x={i * 4} y={20 - h / 2} width="2" height={h} fill={RED} opacity={0.7} />
          })}
        </svg>
      </div>

      {/* Knobs row */}
      <div style={{
        gridColumn: '1 / -1', background: STEEL, border: '1px solid #2a2a2a', padding: 18,
        display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 8, alignItems: 'center',
      }}>
        {[
          ['GAIN', 64, CREAM], ['HI', 40, CREAM], ['MID', 50, CREAM], ['LO', 70, CREAM],
          ['REVERB', 25, CREAM], ['SPEED', 50, CREAM], ['PITCH', 50, CREAM], ['VOL', 80, RED],
        ].map(([label, val, color]) => {
          const angle = -135 + ((val as number) / 100) * 270
          return (
            <div key={String(label)} style={{ textAlign: 'center' }}>
              <div style={{
                width: 52, height: 52, margin: '0 auto', borderRadius: '50%',
                background: 'radial-gradient(circle at 30% 30%, #4a4a4a, #1a1a1a 60%, #0a0a0a)',
                border: `1px solid ${TAN}`, position: 'relative',
                boxShadow: 'inset 0 2px 4px rgba(255,255,255,0.05), 0 2px 6px rgba(0,0,0,0.6)',
              }}>
                <div style={{
                  position: 'absolute', left: '50%', top: '50%',
                  width: 2, height: 18, background: color as string,
                  transformOrigin: '50% 100%',
                  transform: `translate(-50%, -100%) rotate(${angle}deg)`,
                }} />
              </div>
              <div style={{
                fontSize: 9, letterSpacing: '0.25em', color: '#8a7a4a', marginTop: 6,
              }}>{label}</div>
              <div style={{ fontSize: 10, color: CREAM, fontFamily: 'Georgia, serif' }}>{val}</div>
            </div>
          )
        })}

        {/* Big enter button overlay */}
        <button type="button" onClick={() => setLive(true)}
          style={{
            gridColumn: '1 / -1', marginTop: 12,
            background: RED, color: '#fff', border: 'none',
            padding: '14px 24px', fontSize: 13,
            letterSpacing: '0.3em', fontWeight: 700,
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(0,0,0,0.6)',
            fontFamily: 'inherit',
          }}>
          ● OUVRIR LE MICRO · ENREGISTRER LA SESSION
        </button>
      </div>
    </div>
  )
}
