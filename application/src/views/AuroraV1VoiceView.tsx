/**
 * AuroraV1VoiceView — Editorial sphere entry for the Voice module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (VoiceScreen): big AuroraSphere with "voice" pulse, italic display
 * caption, two waveform side-panels (you in / aurora out), bottom bar
 * with caméra / mute / settings / latency stats / Terminer.
 *
 * Real wiring: when the user enters the live session we mount the full
 * VoiceCopilotView underneath (1480 LOC) so EVERY feature stays alive —
 * whisper.cpp STT, vision frames, web search grounding, avatar gen,
 * transcript export, language detection, etc. The skin only re-styles
 * the *entry* and is replaced by the live session once active.
 */
import { lazy, Suspense, useState, useEffect } from 'react'
import { Camera, MicOff, Settings, Sparkles, X } from 'lucide-react'
import AuroraSphereV1 from '../components/AuroraSphereV1'
import LyraCharacter from '../components/voice/LyraCharacter'
import VoiceLandscape from '../components/voice/VoiceLandscape'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

interface AuroraV1VoiceViewProps {
  // v82ay : when mounted as a fullscreen overlay (App.tsx voiceOverlayOpen),
  // this is the outer-close handler. The entry-mode "X" button calls it
  // directly ; the live-session VoiceCopilotView's internal close also
  // calls it so the overlay disappears in one click instead of returning
  // to the editorial entry only to need a second click.
  onClose?: () => void
}

const PINK = 'oklch(0.72 0.14 350)'

function Eyebrow({ children, dot, style }: { children: React.ReactNode; dot?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)', display: 'flex', alignItems: 'center', gap: 8,
      ...style,
    }}>
      {dot && <span style={{ width: 8, height: 8, borderRadius: 99, background: dot, boxShadow: `0 0 12px ${dot}` }} />}
      {children}
    </div>
  )
}

function Btn({ size = 'md', variant = 'ghost', children, onClick, disabled, style }: {
  size?: 'sm' | 'md' | 'lg'; variant?: 'primary' | 'ghost' | 'danger'
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; style?: React.CSSProperties
}) {
  const fg = variant === 'primary' ? 'var(--ink-1000, #0a0a0a)' : variant === 'danger' ? '#ff6a3d' : 'var(--fg, #f5f5f5)'
  const bg = variant === 'primary' ? PINK : 'var(--bg-card, rgba(255,255,255,0.04))'
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      style={{
        fontFamily: 'var(--font-sans, system-ui)',
        fontSize: size === 'sm' ? 12 : size === 'lg' ? 14 : 13,
        padding: size === 'sm' ? '6px 12px' : size === 'lg' ? '12px 24px' : '9px 16px',
        background: bg, color: fg,
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 'var(--r-md, 10px)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 6, ...style,
      }}>{children}</button>
  )
}

function VoiceSphere({ pulse }: { pulse: number }) {
  return (
    <div style={{
      width: '100%', aspectRatio: '1 / 1', maxWidth: 480, margin: '0 auto',
      transform: `scale(${1 + pulse * 0.04})`,
      transition: 'transform 200ms ease, filter 200ms ease',
      filter: `drop-shadow(0 0 ${100 + pulse * 40}px ${PINK}55)`,
    }}>
      <AuroraSphereV1 tint={PINK} state="voice" radius={0.42} glow={1.4} />
    </div>
  )
}

export default function AuroraV1VoiceView({ onClose }: AuroraV1VoiceViewProps = {}) {
  const [live, setLive] = useState(false)
  const [pulse, setPulse] = useState(0)
  useEffect(() => {
    if (live) return
    let raf = 0
    const loop = () => {
      setPulse(Math.abs(Math.sin(performance.now() / 800)))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [live])

  if (live) {
    return (
      <div className="aurora-v1-live-fade">
        <Suspense fallback={
          <div style={{
            width: '100%', height: '100%',
            background: 'var(--bg, #0c0a09)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--fg-dim, #aaa)',
            fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 24,
          }}>Aurora s'éveille…</div>
        }>
          <VoiceCopilotView onClose={onClose ?? (() => setLive(false))} />
        </Suspense>
      </div>
    )
  }

  return (
    <div style={{
      height: '100%', position: 'relative',
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
    }}>
      <div style={{ flex: 1, position: 'relative' }}>
        {/* v82ay : close button (overlay mode only) — top-right, editorial */}
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Fermer Voice"
            style={{
              position: 'absolute', top: 20, right: 20, zIndex: 5,
              width: 36, height: 36, borderRadius: 'var(--r-md, 10px)',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              color: 'var(--fg-dim, #aaa)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'all 200ms var(--ease-out, ease)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--fg, #f5f5f5)'
              e.currentTarget.style.borderColor = 'var(--fg-mute, #888)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--fg-dim, #aaa)'
              e.currentTarget.style.borderColor = 'var(--line, rgba(255,255,255,0.12))'
            }}>
            <X size={16} />
          </button>
        )}

        {/* v83h — paysage Aurora plein écran (mascotte style) */}
        <VoiceLandscape mode="auto" animated />

        {/* Lyra centrée (perso iconique) */}
        <div style={{
          position: 'absolute', left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)', zIndex: 2, pointerEvents: 'none',
        }}>
          <LyraCharacter phase="idle" emotion="happy" accent="#b48cff" size={360} />
        </div>

        {/* Caption sous-titré (bandeau) */}
        <div style={{
          position: 'absolute', bottom: '14%', left: '50%',
          transform: 'translateX(-50%)', maxWidth: 720, width: '90%',
          textAlign: 'center', padding: '0 20px', zIndex: 3,
        }}>
          <Eyebrow dot={PINK} style={{ marginBottom: 14, justifyContent: 'center', color: 'rgba(255,255,255,0.75)' }}>
            Voice live · whisper.cpp · Lyra
          </Eyebrow>
          <div style={{
            display: 'inline-block', padding: '14px 22px',
            background: 'rgba(0,0,0,0.55)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 16,
            backdropFilter: 'blur(6px)',
            boxShadow: '0 12px 36px rgba(0,0,0,0.45)',
          }}>
            <p style={{
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontStyle: 'italic', fontSize: 26, lineHeight: 1.3,
              letterSpacing: '-0.015em', color: '#fff', margin: 0,
            }}>
              « Lance la session, je t'<span style={{ color: '#ffc680' }}>écoute</span> et te réponds en direct. »
            </p>
          </div>
        </div>

      </div>

      {/* Bottom bar */}
      <div style={{
        padding: '20px 40px',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(8,10,22,0.72)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        position: 'relative', zIndex: 4,
      }}>
        <Btn variant="ghost" disabled><Camera size={13} /> Caméra</Btn>
        <Btn variant="ghost" disabled><MicOff size={13} /> Mute</Btn>
        <Btn variant="ghost" disabled><Settings size={13} /> Voice</Btn>
        <span style={{ flex: 1 }} />
        <span style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          color: 'var(--fg-dim, #aaa)',
        }}>
          whisper.cpp · qwen3-coder · ollama TTS · prêt
        </span>
        <Btn variant="primary" size="lg" onClick={() => setLive(true)}>
          <Sparkles size={14} /> Démarrer session
        </Btn>
      </div>
    </div>
  )
}
