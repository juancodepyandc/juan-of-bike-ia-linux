import { useEffect, useState } from 'react'
import { Volume2, VolumeX, Bell, BellOff, Globe, Play, Mic } from 'lucide-react'
import { auroraVoice } from '../services/auroraVoice.ts'

/**
 * Petit toggle flottant pour piloter la voix Aurora :
 *  - Mute / unmute global (TTS)
 *  - On/off des annonces de fin de génération
 *  - Bascule de langue fr ↔ en
 *
 * Monté une seule fois dans App.tsx à côté de ConnectionIndicator.
 * Stocke les préférences via auroraVoice (qui les persiste en localStorage).
 */
export default function VoiceQuickToggle() {
  const initial = auroraVoice.getPreferences()
  const [muted, setMuted] = useState(initial.muted)
  const [annonces, setAnnonces] = useState(initial.announceOnComplete)
  const [lang, setLang] = useState<'fr' | 'en'>(initial.language)
  const [open, setOpen] = useState(false)
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    const off = auroraVoice.subscribe<typeof initial>('prefs', (p) => {
      setMuted(p.muted); setAnnonces(p.announceOnComplete); setLang(p.language)
    })
    // Pulse visuel quand une annonce est lue — utile si l'utilisateur a muté
    // et veut quand même voir qu'une génération s'est terminée.
    let pulseTimer: ReturnType<typeof setTimeout> | null = null
    const offAnnounce = auroraVoice.subscribe<unknown>('announce', () => {
      setPulse(true)
      if (pulseTimer) clearTimeout(pulseTimer)
      pulseTimer = setTimeout(() => setPulse(false), 1500)
    })
    return () => {
      off()
      offAnnounce()
      if (pulseTimer) clearTimeout(pulseTimer)
    }
  }, [])

  // Raccourci global Ctrl+Shift+M : toggle mute. N'interfère pas avec les inputs
  // (skip si la cible est un champ texte).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey && e.shiftKey && (e.key === 'M' || e.key === 'm'))) return
      const t = e.target as HTMLElement | null
      const tag = t?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || t?.isContentEditable) return
      e.preventDefault()
      auroraVoice.setMuted(!auroraVoice.isMuted())
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const toggleMute = () => { auroraVoice.setMuted(!muted) }
  const toggleAnnounce = () => { auroraVoice.setAnnouncePolicy({ announceOnComplete: !annonces, announceOnFail: !annonces }) }
  const toggleLang = () => { auroraVoice.setLanguage(lang === 'fr' ? 'en' : 'fr') }
  const testVoice = () => {
    // Force unmute le temps du test si nécessaire pour que l'utilisateur entende.
    const wasMuted = auroraVoice.isMuted()
    if (wasMuted) auroraVoice.setMuted(false)
    const text = lang === 'fr'
      ? "Bonjour, je suis Aurora. La synthèse vocale fonctionne correctement."
      : "Hello, I'm Aurora. Speech synthesis is working correctly."
    void auroraVoice.speak(text, { detail: 'short' }).then(() => {
      if (wasMuted) auroraVoice.setMuted(true)
    })
  }

  const btn: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    width: 32, height: 32, borderRadius: 8,
    border: '1px solid rgba(180,140,255,0.30)',
    background: 'rgba(180,140,255,0.10)',
    color: '#b48cff', cursor: 'pointer',
    transition: 'background 120ms ease, color 120ms ease, border-color 120ms ease',
  }

  return (
    <div
      style={{
        position: 'fixed', right: 12, bottom: 12, zIndex: 9999,
        display: 'flex', gap: 6, alignItems: 'center',
        padding: open ? 8 : 0,
        borderRadius: 12,
        background: open ? 'rgba(20,18,30,0.85)' : 'transparent',
        border: open ? '1px solid rgba(180,140,255,0.25)' : 'none',
        backdropFilter: open ? 'blur(8px)' : 'none',
      }}
    >
      {open && (
        <>
          <button
            type="button"
            aria-label={muted ? 'Réactiver la voix' : 'Couper la voix'}
            title={muted ? 'Réactiver la voix Aurora (TTS)' : 'Couper la voix Aurora (TTS)'}
            onClick={toggleMute}
            style={{ ...btn, background: muted ? 'rgba(255,80,80,0.18)' : btn.background, color: muted ? '#ff6b6b' : btn.color }}
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
          <button
            type="button"
            aria-label={annonces ? 'Désactiver les annonces' : 'Activer les annonces'}
            title={annonces ? 'Désactiver les annonces de fin de génération' : 'Activer les annonces de fin de génération'}
            onClick={toggleAnnounce}
            style={{ ...btn, background: !annonces ? 'rgba(120,120,120,0.18)' : btn.background, color: !annonces ? '#bbb' : btn.color }}
          >
            {annonces ? <Bell size={16} /> : <BellOff size={16} />}
          </button>
          <button
            type="button"
            aria-label="Basculer la langue de la voix"
            title={`Langue voix : ${lang === 'fr' ? 'Français → cliquer pour passer en anglais' : 'English → click to switch to French'}`}
            onClick={toggleLang}
            style={{ ...btn, width: 'auto', padding: '0 8px', gap: 4 }}
          >
            <Globe size={14} />
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>{lang}</span>
          </button>
          <button
            type="button"
            aria-label="Tester la voix"
            title="Tester la voix Aurora (force unmute le temps du test)"
            onClick={testVoice}
            style={btn}
          >
            <Play size={14} />
          </button>
          <button
            type="button"
            aria-label="Ouvrir le copilote vocal"
            title="Ouvrir le copilote vocal full-screen (Lyra/Iris/Cinéma/Glyph/Sumi/Atlas/Sage/Phantom)"
            onClick={() => window.dispatchEvent(new CustomEvent('aurora:open-voice-overlay'))}
            style={btn}
          >
            <Mic size={14} />
          </button>
        </>
      )}
      <button
        type="button"
        aria-label={open ? 'Fermer le menu voix' : 'Ouvrir le menu voix'}
        title="Réglages voix Aurora (Ctrl+Shift+M pour mute rapide)"
        onClick={() => setOpen((v) => !v)}
        style={{
          ...btn,
          background: open ? 'rgba(180,140,255,0.25)' : btn.background,
          boxShadow: pulse ? '0 0 0 6px rgba(180,140,255,0.35)' : 'none',
          transform: pulse ? 'scale(1.08)' : 'scale(1)',
        }}
      >
        {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
      </button>
    </div>
  )
}
