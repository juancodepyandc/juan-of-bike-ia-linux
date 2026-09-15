import { useCallback, useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Mic, MicOff, Volume2, VolumeX, Loader2, Radio } from 'lucide-react'
import { useVoiceLive, type VoiceLivePhase } from '../hooks/useVoiceLive.ts'
import { cleanTextForVoice } from '../utils/textCleaner.ts'

interface VoiceLiveChatProps {
  onTranscript: (text: string) => void
  onSpeakResponse?: (text: string) => void
  disabled?: boolean
  lastAssistantText?: string
  autoSpeak?: boolean
}

const PHASE_LABELS: Record<VoiceLivePhase, string> = {
  idle: 'Appuie pour parler',
  listening: 'Ecoute en cours...',
  transcribing: 'Transcription...',
  thinking: 'Reflexion...',
  speaking: 'Reponse vocale...',
}

const PHASE_COLORS: Record<VoiceLivePhase, string> = {
  idle: 'border-white/10 bg-white/[0.04]',
  listening: 'border-aurora-accent/40 bg-aurora-accent/10',
  transcribing: 'border-aurora-yellow/30 bg-aurora-yellow/8',
  thinking: 'border-aurora-cyan/30 bg-aurora-cyan/8',
  speaking: 'border-aurora-green/30 bg-aurora-green/8',
}

export default function VoiceLiveChat({
  onTranscript,
  disabled = false,
  lastAssistantText,
  autoSpeak = false,
}: VoiceLiveChatProps) {
  const lastSpokenRef = useRef<string | null>(null)

  const {
    phase,
    error,
    volumeLevel,
    toggleListening,
    speakText,
    stopSpeaking,
    isActive,
    isContinuous,
  } = useVoiceLive({
    onTranscript,
  })

  // Auto-speak last assistant response when autoSpeak is on — texte nettoyé
  useEffect(() => {
    if (
      autoSpeak
      && lastAssistantText
      && lastAssistantText !== lastSpokenRef.current
      && phase === 'idle'
    ) {
      lastSpokenRef.current = lastAssistantText
      void speakText(cleanTextForVoice(lastAssistantText))
    }
  }, [autoSpeak, lastAssistantText, phase, speakText])

  const handleClick = useCallback(() => {
    if (disabled) return
    if (phase === 'speaking') {
      stopSpeaking()
    } else {
      toggleListening()
    }
  }, [disabled, phase, stopSpeaking, toggleListening])

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Main voice button */}
      <motion.button
        onClick={handleClick}
        disabled={disabled || phase === 'transcribing' || phase === 'thinking'}
        whileTap={{ scale: 0.95 }}
        className={`relative flex h-16 w-16 items-center justify-center rounded-full border-2 transition-all ${
          PHASE_COLORS[phase]
        } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:opacity-90'}`}
      >
        {/* Volume ring animation */}
        <AnimatePresence>
          {phase === 'listening' && (
            <motion.div
              initial={{ scale: 1, opacity: 0.6 }}
              animate={{
                scale: 1 + volumeLevel * 0.5,
                opacity: 0.2 + volumeLevel * 0.4,
              }}
              exit={{ scale: 1, opacity: 0 }}
              className="absolute inset-0 rounded-full border-2 border-aurora-accent/40"
            />
          )}
        </AnimatePresence>

        {/* Pulsing dot for listening */}
        {phase === 'listening' && (
          <motion.div
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 0.8, repeat: Infinity }}
            className="absolute -top-0.5 -right-0.5 h-3 w-3 rounded-full bg-aurora-accent"
          />
        )}

        {/* Icon */}
        {phase === 'listening' ? (
          <MicOff size={24} className="text-aurora-accent" />
        ) : phase === 'transcribing' || phase === 'thinking' ? (
          <Loader2 size={24} className="animate-spin text-aurora-cyan" />
        ) : phase === 'speaking' ? (
          <Volume2 size={24} className="text-aurora-green" />
        ) : (
          <Mic size={24} className="text-aurora-text-dim" />
        )}
      </motion.button>

      {/* Phase label */}
      <AnimatePresence mode="wait">
        <motion.p
          key={phase}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className="text-[11px] text-aurora-text-dim"
        >
          {isActive && (
            <Radio size={10} className="mr-1 inline-block text-aurora-accent animate-pulse" />
          )}
          {phase === 'idle' && isContinuous ? "Parle, je t'ecoute..." : PHASE_LABELS[phase]}
        </motion.p>
      </AnimatePresence>

      {/* Error display */}
      {error && (
        <p className="max-w-[16rem] text-center text-[10px] text-aurora-red">{error}</p>
      )}
    </div>
  )
}
