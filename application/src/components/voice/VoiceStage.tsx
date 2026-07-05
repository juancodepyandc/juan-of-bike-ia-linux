/**
 * VoiceStage — scène voix complète : paysage + perso Lyra + bandeau
 * sous-titres + bouton push-to-talk en bas.
 *
 * Inspiré du flat-design Duolingo speaking practice : le paysage occupe
 * tout le viewport, le perso est centré, ce qu'il dit est affiché en
 * sous-titre, l'utilisateur appuie sur un gros bouton pour parler.
 *
 * S'utilise comme remplaçant complet de l'UI vocale "rond AuroraSphere"
 * — la version 3D reste dispo via prop showLegacyAvatar=true mais c'est
 * désactivé par défaut.
 */
import { useEffect, useState } from 'react'
import { Loader2, Mic, MicOff, X } from 'lucide-react'
import LyraCharacter, { type LyraEmotion, type LyraPhase, type LyraViseme } from './LyraCharacter'
import VoiceLandscape, { type LandscapeMode } from './VoiceLandscape'

interface Props {
  phase: LyraPhase
  /** Texte en cours de prononciation (sous-titre). */
  subtitle?: string
  /** Status humain (eg. "Je t'écoute…"). Petit chip au-dessus du sous-titre. */
  statusLabel?: string
  /** Couleur d'état (chip + halo). */
  statusColor?: string
  /** Amplitude vocale 0..1 — drive l'ouverture bouche + halo. */
  amplitude?: number
  /** Viseme courant. */
  viseme?: LyraViseme
  /** Émotion (changement de sourcils + blush). */
  emotion?: LyraEmotion
  /** Mode du paysage. */
  landscapeMode?: LandscapeMode
  /** Push-to-talk : ON pendant que micro actif. */
  micActive?: boolean
  /** Click bouton micro. */
  onTogglePtt?: () => void
  /** Fermer le mode voix. */
  onClose?: () => void
  /** Langue active (affichée comme chip cliquable). */
  lang?: 'fr' | 'en'
  /** Callback toggle langue. */
  onToggleLang?: () => void
  /** Liste des derniers échanges (user/lyra) pour drawer transcript. */
  transcript?: Array<{ role: 'user' | 'assistant'; text: string; image?: string; video?: string }>
  /** Callback "clear transcript". */
  onClearTranscript?: () => void
  /** Callback envoie texte (conversation libre, en plus du push-to-talk). */
  onSendText?: (text: string) => void
  /** True quand la caméra est active — Lyra pointe ce qu'elle analyse. */
  cameraActive?: boolean
  /** Texte de la dernière analyse de la cam pour montrer "Lyra voit X". */
  visualContext?: string
  /** Indicateur STT actif (eg. "whisper.cpp small · CUDA"). */
  sttInfo?: string
  /** Indicateur modèle LLM actif (eg. "qwen3-coder"). */
  modelInfo?: string
  /** Surimprimer un panneau enfant (avatar selector, transcript, etc.). */
  children?: React.ReactNode
}

export default function VoiceStage({
  phase,
  subtitle,
  statusLabel,
  statusColor = '#a78bfa',
  amplitude = 0,
  viseme = 'closed',
  emotion = 'neutral',
  landscapeMode = 'auto',
  micActive = false,
  onTogglePtt,
  onClose,
  lang,
  onToggleLang,
  transcript,
  onClearTranscript,
  onSendText,
  cameraActive = false,
  visualContext,
  sttInfo,
  modelInfo,
  children,
}: Props) {
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const [textInput, setTextInput] = useState('')
  const [chatOpen, setChatOpen] = useState(true) // par défaut ouvert pour l'interface conversation libre

  // Dernier message Lyra avec un media embed à montrer dans la zone subtitle.
  const lastAssistantWithMedia = transcript
    ? [...transcript].reverse().find((m) => m.role === 'assistant' && (m.image || m.video))
    : undefined
  // Compteur user messages — sert de reactKey à Lyra (réagit visuellement).
  const userMsgCount = transcript ? transcript.filter((t) => t.role === 'user').length : 0
  // Caractère grandi en fonction du viewport (responsive).
  const [size, setSize] = useState(360)
  useEffect(() => {
    const update = () => {
      const h = window.innerHeight
      const s = Math.max(260, Math.min(480, h * 0.5))
      setSize(s)
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      minHeight: 0, overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'var(--font-sans, system-ui)',
      color: '#fff',
    }}>
      {/* Backdrop — paysage Aurora */}
      <VoiceLandscape mode={landscapeMode} animated />

      {/* Bouton fermer */}
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer la voix"
          style={{
            position: 'absolute', top: 18, left: 18, zIndex: 5,
            width: 38, height: 38, borderRadius: 19,
            background: 'rgba(0,0,0,0.45)',
            border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <X size={16} />
        </button>
      )}

      {/* Quick action chips — traduction, calcul, recherche */}
      {onSendText && (
        <div style={{
          position: 'absolute', top: 18, right: 88, zIndex: 5,
          display: 'flex', gap: 6,
        }}>
          {[
            { icon: '🌐', prompt: 'Traduis en anglais : ', label: 'translate' },
            { icon: '🔎', prompt: 'Cherche sur le web : ', label: 'search' },
            { icon: '📐', prompt: 'Calcule pour moi : ', label: 'calc' },
          ].map((q) => (
            <button
              key={q.label}
              type="button"
              onClick={() => {
                const text = window.prompt(q.prompt)
                if (text && text.trim()) onSendText(q.prompt + text.trim())
              }}
              title={q.prompt + '…'}
              style={{
                width: 36, height: 36, borderRadius: 18,
                background: 'rgba(0,0,0,0.45)',
                border: '1px solid rgba(255,255,255,0.18)',
                color: '#fff', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14,
              }}
            >{q.icon}</button>
          ))}
        </div>
      )}

      {/* Toggle langue FR/EN */}
      {lang && onToggleLang && (
        <button
          type="button"
          onClick={onToggleLang}
          aria-label={`Langue : ${lang === 'fr' ? 'français' : 'anglais'} — cliquer pour changer`}
          title={`Lyra parle ${lang === 'fr' ? 'français' : 'english'} · clique pour switcher`}
          style={{
            position: 'absolute', top: 18, left: 66, zIndex: 5,
            height: 38, padding: '0 14px', borderRadius: 19,
            background: 'rgba(0,0,0,0.45)',
            border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 8,
            fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 12,
            letterSpacing: '0.06em',
          }}
        >
          <span style={{ fontSize: 16 }}>{lang === 'fr' ? '🇫🇷' : '🇬🇧'}</span>
          <span>{lang.toUpperCase()}</span>
        </button>
      )}

      {/* Status chip — en haut au centre */}
      {statusLabel && (
        <div style={{
          position: 'absolute', top: 22, left: '50%', transform: 'translateX(-50%)',
          zIndex: 5,
          padding: '6px 14px', borderRadius: 99,
          background: 'rgba(0,0,0,0.55)',
          border: `1px solid ${statusColor}55`,
          color: '#fff', fontSize: 12, letterSpacing: '0.04em',
          fontFamily: 'var(--font-mono, ui-monospace)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span
            style={{
              width: 8, height: 8, borderRadius: 4, background: statusColor,
              boxShadow: `0 0 10px ${statusColor}`,
              animation: phase !== 'idle' ? 'pulse 1.4s ease-in-out infinite' : 'none',
            }}
          />
          <span>{statusLabel}</span>
          <style>{`
            @keyframes pulse {
              0%, 100% { transform: scale(1); opacity: 0.95 }
              50% { transform: scale(1.4); opacity: 0.55 }
            }
          `}</style>
        </div>
      )}

      {/* Phase chip flottant à côté de Lyra */}
      <div style={{
        position: 'absolute', left: '50%', top: '20%',
        transform: 'translate(-50%, 0)', zIndex: 4,
        pointerEvents: 'none',
      }}>
        <PhaseChip phase={phase} statusColor={statusColor} />
      </div>

      {/* Lyra — perso centré (cliquable pour easter egg) */}
      <div style={{
        position: 'absolute', left: '50%', top: '52%',
        transform: 'translate(-50%, -50%)',
        zIndex: 3, pointerEvents: 'auto',
      }}>
        <LyraCharacter
          phase={phase}
          amplitude={amplitude}
          viseme={viseme}
          emotion={emotion}
          accent="#b48cff"
          size={size}
          pointingDirection={cameraActive ? 'right' : null}
          reactKey={userMsgCount}
        />
      </div>

      {/* Speech bubble — quand Lyra parle, sa phrase apparaît dans une bulle BD */}
      {phase === 'speaking' && subtitle && (
        <div style={{
          position: 'absolute', left: '52%', top: '24%',
          transform: 'translateX(-50%)',
          zIndex: 4, pointerEvents: 'none',
          maxWidth: 360,
        }}>
          <div style={{
            position: 'relative',
            padding: '12px 18px',
            background: 'rgba(255,255,255,0.96)',
            color: '#1a1410',
            border: '2px solid rgba(180,140,255,0.8)',
            borderRadius: 18,
            fontSize: 14, lineHeight: 1.45,
            fontFamily: 'var(--font-sans, system-ui)',
            boxShadow: '0 8px 24px rgba(0,0,0,0.45)',
            textAlign: 'center',
          }}>
            {subtitle.length > 220 ? subtitle.slice(0, 217) + '…' : subtitle}
            {/* Queue de la bulle pointant vers Lyra */}
            <svg
              viewBox="0 0 30 22"
              width="30" height="22"
              style={{
                position: 'absolute', bottom: -16, left: '50%',
                transform: 'translateX(-50%)',
              }}
            >
              <path d="M 0 0 L 30 0 L 15 22 Z" fill="rgba(255,255,255,0.96)" />
              <path d="M 1 1 L 15 22 L 29 1" stroke="rgba(180,140,255,0.8)" strokeWidth="2" fill="none" />
            </svg>
          </div>
        </div>
      )}

      {/* Waveform amplitude — petit bandeau sous Lyra */}
      {(phase === 'speaking' || phase === 'listening') && (
        <div style={{
          position: 'absolute', left: '50%', top: '78%',
          transform: 'translateX(-50%)', zIndex: 3,
          pointerEvents: 'none',
        }}>
          <AmplitudeBars amplitude={amplitude} color={statusColor} />
        </div>
      )}

      {/* SOUS-TITRE — bandeau bas avec embed media si présent */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 196, zIndex: 4,
        display: 'flex', justifyContent: 'center',
        padding: '0 20px', pointerEvents: 'none',
      }}>
        {(subtitle || lastAssistantWithMedia) && (
          <div style={{
            maxWidth: 760, padding: '12px 20px',
            background: 'rgba(0,0,0,0.66)',
            border: '1px solid rgba(255,255,255,0.10)',
            borderRadius: 14,
            color: '#fff', fontSize: 17, lineHeight: 1.45,
            textAlign: 'center',
            backdropFilter: 'blur(6px)',
            boxShadow: '0 8px 30px rgba(0,0,0,0.45)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
          }}>
            {subtitle && <div>{subtitle}</div>}
            {lastAssistantWithMedia?.image && (
              <img
                src={lastAssistantWithMedia.image}
                alt="média partagé par Lyra"
                style={{
                  maxWidth: '100%', maxHeight: 280,
                  borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)',
                  boxShadow: '0 6px 18px rgba(0,0,0,0.45)',
                }}
              />
            )}
            {lastAssistantWithMedia?.video && (
              <video
                src={lastAssistantWithMedia.video}
                controls
                style={{
                  maxWidth: '100%', maxHeight: 280,
                  borderRadius: 10, border: '1px solid rgba(255,255,255,0.18)',
                }}
              />
            )}
          </div>
        )}
      </div>

      {/* Chat input bar — conversation libre par texte (en plus du PTT) */}
      {onSendText && chatOpen && (
        <div style={{
          position: 'absolute', left: '50%', transform: 'translateX(-50%)',
          bottom: 112, zIndex: 5,
          width: 'min(720px, calc(100% - 280px))',
          display: 'flex', gap: 8, alignItems: 'center',
        }}>
          <input
            id="voice-stage-input"
            name="voiceStageInput"
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && textInput.trim()) {
                e.preventDefault()
                onSendText(textInput.trim())
                setTextInput('')
              }
            }}
            placeholder="Écris à Lyra (ou appuie sur Parle)…"
            style={{
              flex: 1, height: 44, padding: '0 16px',
              background: 'rgba(0,0,0,0.65)',
              border: '1px solid rgba(255,255,255,0.18)',
              borderRadius: 22, color: '#fff', fontSize: 14,
              fontFamily: 'var(--font-sans, system-ui)',
              outline: 'none',
              backdropFilter: 'blur(6px)',
            }}
          />
          <button
            type="button"
            onClick={() => {
              if (textInput.trim()) {
                onSendText(textInput.trim())
                setTextInput('')
              }
            }}
            disabled={!textInput.trim()}
            aria-label="Envoyer"
            style={{
              height: 44, padding: '0 18px',
              borderRadius: 22,
              background: textInput.trim()
                ? 'linear-gradient(135deg, #b48cff, #67d2ff)'
                : 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.18)',
              color: '#fff', cursor: textInput.trim() ? 'pointer' : 'not-allowed',
              fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 12,
              letterSpacing: '0.08em',
            }}
          >envoyer ↵</button>
          <button
            type="button"
            onClick={() => setChatOpen(false)}
            title="Masquer le chat"
            style={{
              width: 36, height: 36, borderRadius: 18,
              background: 'rgba(0,0,0,0.45)',
              border: '1px solid rgba(255,255,255,0.18)',
              color: '#fff', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}
          >−</button>
        </div>
      )}
      {onSendText && !chatOpen && (
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          title="Ouvrir le chat"
          style={{
            position: 'absolute', left: '50%', transform: 'translateX(-50%)',
            bottom: 112, zIndex: 5,
            padding: '8px 18px', borderRadius: 99,
            background: 'rgba(0,0,0,0.55)',
            border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', cursor: 'pointer',
            fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
            letterSpacing: '0.1em',
          }}
        >✎ écrire à lyra</button>
      )}

      {/* Banner "Lyra voit" quand caméra active */}
      {cameraActive && visualContext && (
        <div style={{
          position: 'absolute', top: 70, left: 24, right: 24, zIndex: 4,
          display: 'flex', justifyContent: 'center', pointerEvents: 'none',
        }}>
          <div style={{
            maxWidth: 560, padding: '8px 16px',
            background: 'rgba(16,80,40,0.7)',
            border: '1px solid rgba(100,255,160,0.4)',
            borderRadius: 99,
            color: 'rgba(180,255,200,0.95)',
            fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
            letterSpacing: '0.04em',
            display: 'flex', alignItems: 'center', gap: 8,
            backdropFilter: 'blur(6px)',
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: 4,
              background: 'rgba(100,255,160,1)',
              animation: 'pulse 1.6s ease-in-out infinite',
            }} />
            <span>Lyra voit · </span>
            <span style={{ color: '#fff' }}>{visualContext.slice(0, 110)}{visualContext.length > 110 ? '…' : ''}</span>
          </div>
        </div>
      )}

      {/* Bouton transcript drawer (à gauche du PTT) */}
      {transcript && transcript.length > 0 && (
        <button
          type="button"
          onClick={() => setTranscriptOpen((v) => !v)}
          aria-pressed={transcriptOpen}
          title="Afficher le transcript"
          style={{
            position: 'absolute', left: 24, bottom: 38, zIndex: 5,
            height: 44, padding: '0 16px', borderRadius: 22,
            background: transcriptOpen ? 'rgba(180,140,255,0.25)' : 'rgba(0,0,0,0.45)',
            border: '1px solid rgba(255,255,255,0.18)',
            color: '#fff', cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
            letterSpacing: '0.06em',
          }}
        >
          📝 {transcript.length}
        </button>
      )}

      {/* Drawer transcript */}
      {transcriptOpen && transcript && transcript.length > 0 && (
        <div style={{
          position: 'absolute', left: 24, bottom: 92, zIndex: 5,
          width: 360, maxHeight: 320, overflowY: 'auto',
          background: 'rgba(0,0,0,0.78)',
          border: '1px solid rgba(255,255,255,0.18)',
          borderRadius: 14,
          padding: 12,
          color: '#fff',
          backdropFilter: 'blur(8px)',
          boxShadow: '0 12px 36px rgba(0,0,0,0.45)',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', marginBottom: 8,
          }}>
            <span style={{
              fontFamily: 'var(--font-mono, ui-monospace)',
              fontSize: 10, letterSpacing: '0.18em',
              textTransform: 'uppercase', opacity: 0.65,
            }}>Transcript récent</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {onClearTranscript && (
                <button
                  onClick={onClearTranscript}
                  title="Effacer transcript"
                  style={{
                    padding: '2px 8px', fontSize: 10,
                    fontFamily: 'var(--font-mono, ui-monospace)',
                    background: 'rgba(255,80,80,0.15)',
                    border: '1px solid rgba(255,80,80,0.3)',
                    borderRadius: 4, color: '#ffb0b0', cursor: 'pointer',
                  }}
                >clear</button>
              )}
              <button
                onClick={() => setTranscriptOpen(false)}
                style={{ background: 'transparent', color: '#fff', border: 'none', cursor: 'pointer' }}
                aria-label="Fermer"
              >×</button>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {transcript.slice(-12).map((m, i) => (
              <div key={i} style={{
                padding: '6px 10px', borderRadius: 8, fontSize: 12, lineHeight: 1.45,
                background: m.role === 'user' ? 'rgba(120,160,255,0.18)' : 'rgba(180,140,255,0.16)',
                border: `1px solid ${m.role === 'user' ? 'rgba(120,160,255,0.35)' : 'rgba(180,140,255,0.35)'}`,
              }}>
                <div style={{
                  fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 9,
                  letterSpacing: '0.14em', textTransform: 'uppercase',
                  opacity: 0.7, marginBottom: 3,
                }}>{m.role === 'user' ? 'toi' : 'lyra'}</div>
                <div>{m.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Suggested follow-ups — chips visibles quand Lyra a fini de parler */}
      {phase === 'idle' && onSendText && transcript && transcript.length > 0 && transcript[transcript.length - 1].role === 'assistant' && (
        <div style={{
          position: 'absolute', left: '50%', transform: 'translateX(-50%)',
          bottom: 168, zIndex: 4,
          display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center',
          maxWidth: 'min(720px, calc(100% - 280px))',
        }}>
          {['💬 Donne un exemple concret', '🔍 Explique plus en détail', '🎯 Et l\'essentiel à retenir ?'].map((label) => {
            const text = label.replace(/^[^\s]+\s/, '')
            return (
              <button
                key={label}
                onClick={() => onSendText(text)}
                style={{
                  padding: '6px 12px', borderRadius: 99,
                  background: 'rgba(180,140,255,0.18)',
                  border: '1px solid rgba(180,140,255,0.45)',
                  color: 'rgba(255,255,255,0.92)',
                  cursor: 'pointer',
                  fontSize: 12, fontFamily: 'var(--font-sans, system-ui)',
                  backdropFilter: 'blur(4px)',
                }}
              >{label}</button>
            )
          })}
        </div>
      )}

      {/* PUSH-TO-TALK — gros bouton bas */}
      {onTogglePtt && (
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 32, zIndex: 5,
          display: 'flex', justifyContent: 'center',
        }}>
          <button
            type="button"
            onClick={onTogglePtt}
            aria-pressed={micActive}
            aria-label={micActive ? 'Couper le micro' : 'Activer le micro'}
            style={{
              minWidth: 220, height: 64,
              padding: '0 28px',
              borderRadius: 32,
              fontFamily: 'var(--font-mono, ui-monospace)',
              fontSize: 14, letterSpacing: '0.14em',
              textTransform: 'uppercase',
              background: micActive
                ? 'linear-gradient(135deg, #ff6b3d, #ff3d6b)'
                : 'linear-gradient(135deg, #67d2ff, #8a8cff)',
              border: '2px solid rgba(255,255,255,0.35)',
              color: '#fff', cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              boxShadow: micActive
                ? '0 12px 36px rgba(255,80,80,0.45)'
                : '0 12px 36px rgba(120,140,255,0.4)',
              transition: 'background 200ms ease, transform 80ms ease',
            }}
          >
            {phase === 'thinking' ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Aurora réfléchit
              </>
            ) : micActive ? (
              <>
                <MicOff size={18} />
                Stop
              </>
            ) : (
              <>
                <Mic size={18} />
                Parle
              </>
            )}
          </button>
        </div>
      )}

      {/* Chip discret en bas-droite : modèle STT + LLM */}
      {(sttInfo || modelInfo) && (
        <div style={{
          position: 'absolute', right: 18, bottom: 18, zIndex: 5,
          padding: '4px 10px', borderRadius: 99,
          background: 'rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.10)',
          color: 'rgba(255,255,255,0.65)',
          fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 10,
          letterSpacing: '0.06em',
          display: 'flex', gap: 8,
          pointerEvents: 'none',
        }}>
          {sttInfo && <span>STT · {sttInfo}</span>}
          {sttInfo && modelInfo && <span style={{ opacity: 0.4 }}>·</span>}
          {modelInfo && <span>LLM · {modelInfo}</span>}
        </div>
      )}

      {children}
    </div>
  )
}

// v84b — Waveform 12 barres pulsantes selon amplitude.
function AmplitudeBars({ amplitude, color }: { amplitude: number; color: string }) {
  const N = 12
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', gap: 3,
      height: 28, padding: '0 6px',
    }}>
      {Array.from({ length: N }).map((_, i) => {
        // Variation pseudo-aleatoire stable selon l'index : la vague n'est pas uniforme.
        const offset = ((i * 37) % 100) / 100
        const wave = 0.4 + Math.sin(performance.now() / 220 + i * 0.7) * 0.3
        const h = 4 + amplitude * 22 * (0.6 + offset * 0.6) * wave
        return (
          <div
            key={i}
            style={{
              width: 3, height: Math.max(3, h),
              background: color,
              borderRadius: 2,
              opacity: 0.6 + amplitude * 0.4,
              boxShadow: amplitude > 0.4 ? `0 0 6px ${color}88` : 'none',
              transition: 'height 60ms linear, box-shadow 120ms ease',
            }}
          />
        )
      })}
    </div>
  )
}

// v84a — Phase chip flottant : icône + label rapidement lisible.
function PhaseChip({ phase, statusColor }: { phase: LyraPhase; statusColor: string }) {
  const map: Record<LyraPhase, { icon: string; label: string }> = {
    idle:      { icon: '◌', label: 'En attente' },
    listening: { icon: '◉', label: "J'écoute" },
    thinking:  { icon: '◐', label: 'Je réfléchis' },
    speaking:  { icon: '●', label: 'Je parle' },
  }
  const m = map[phase]
  if (phase === 'idle') return null
  return (
    <div style={{
      padding: '4px 12px', borderRadius: 99,
      background: 'rgba(0,0,0,0.65)',
      border: `1px solid ${statusColor}55`,
      color: '#fff', fontFamily: 'var(--font-mono, ui-monospace)',
      fontSize: 11, letterSpacing: '0.06em',
      display: 'inline-flex', alignItems: 'center', gap: 6,
      boxShadow: `0 0 14px ${statusColor}33`,
    }}>
      <span style={{ color: statusColor }}>{m.icon}</span>
      <span>{m.label}</span>
    </div>
  )
}
