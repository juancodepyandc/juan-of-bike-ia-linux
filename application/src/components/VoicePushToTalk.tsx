import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Loader2 } from 'lucide-react'
import { auroraVoice, type ListenHandle, type VoicePhase } from '../services/auroraVoice.ts'

interface Props {
  /** Callback appelé avec le texte transcrit. */
  onTranscript: (text: string) => void
  /** Étiquette aria et titre. */
  label?: string
  /** Taille en pixels (carré). */
  size?: number
  /** Classe additionnelle pour le wrapper. */
  className?: string
  /** Si vrai, désactive le bouton (générations en cours…). */
  disabled?: boolean
  /** Langue ; par défaut on prend la préférence globale du service. */
  lang?: 'fr' | 'en'
  /** Variante visuelle. */
  variant?: 'solid' | 'ghost' | 'glass'
}

/**
 * Bouton micro réutilisable dans n'importe quel module : Chat, Academy, Code,
 * Image, Video, Drawing, 3D, Cyber, Cowork. Click = listen() ; click pendant
 * l'enregistrement = stop. Utilise le singleton auroraVoice pour partager
 * l'état (phase, volume) entre tous les modules.
 */
export default function VoicePushToTalk({
  onTranscript,
  label = 'Dicter au micro',
  size = 36,
  className = '',
  disabled = false,
  lang,
  variant = 'glass',
}: Props) {
  const [phase, setPhase] = useState<VoicePhase>(auroraVoice.getPhase())
  const [vol, setVol] = useState(0)
  const handleRef = useRef<ListenHandle | null>(null)

  useEffect(() => {
    const offPhase = auroraVoice.subscribe<VoicePhase>('phase', setPhase)
    const offVol = auroraVoice.subscribe<number>('volume', setVol)
    return () => { offPhase(); offVol() }
  }, [])

  const start = useCallback(async () => {
    if (disabled) return
    try {
      handleRef.current = await auroraVoice.listen(
        (text) => { onTranscript(text) },
        { lang },
      )
    } catch (e) {
      console.warn('[VoicePushToTalk] listen failed:', e)
    }
  }, [onTranscript, disabled, lang])

  const stop = useCallback(() => {
    handleRef.current?.stop()
    handleRef.current = null
  }, [])

  const active = phase === 'listening' || phase === 'transcribing'
  const transcribing = phase === 'transcribing'

  const style: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'transform 120ms ease, background 120ms ease, box-shadow 120ms ease',
    border: '1px solid rgba(180,140,255,0.35)',
    color: active ? '#fff' : '#b48cff',
    background:
      variant === 'solid'
        ? (active ? 'linear-gradient(135deg, #b48cff, #6d4dff)' : 'rgba(180,140,255,0.18)')
        : variant === 'ghost'
          ? 'transparent'
          : (active ? 'rgba(180,140,255,0.85)' : 'rgba(180,140,255,0.12)'),
    boxShadow: active ? `0 0 0 ${Math.round(4 + vol * 18)}px rgba(180,140,255,0.18)` : 'none',
    opacity: disabled ? 0.45 : 1,
  }

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={active ? stop : start}
      disabled={disabled}
      className={className}
      style={style}
    >
      {transcribing ? (
        <Loader2 size={Math.round(size * 0.5)} className="animate-spin" />
      ) : active ? (
        <MicOff size={Math.round(size * 0.5)} />
      ) : (
        <Mic size={Math.round(size * 0.5)} />
      )}
    </button>
  )
}
