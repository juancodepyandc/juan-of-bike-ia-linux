/**
 * iter37 — Bubble assistant IA pour le parcours BAC.
 *
 * Comme un widget Intercom/Crisp : flotte en bas-droite, auto-ouvre après
 * génération avec un message de bienvenue, quick prompts pré-définis, et
 * un input pour faire développer n'importe quel point du parcours en
 * envoyant un prompt libre. Streaming gemma3:12b via le bridge proxy.
 *
 * Le contexte (synthèse + fiches + cartes + matière) est injecté en system
 * prompt pour que les réponses soient ANCRÉES sur le parcours actuel —
 * pas des généralités.
 */
import React, { useEffect, useRef, useState, useMemo } from 'react'
import { MessageCircle, X, Send, Sparkles, Loader2 } from 'lucide-react'
import type { AcademyParcoursPayload } from '../../hooks/useAcademyViewLogic'
import { getBridgeUrl } from '../../utils/runtime'

const GOLD = 'oklch(0.86 0.18 75)'
const VIOLET = 'oklch(0.62 0.22 295)'
const TEAL = 'oklch(0.72 0.13 195)'

type Msg = { role: 'user' | 'assistant'; content: string; streaming?: boolean }

interface Props {
  payload: AcademyParcoursPayload
  subjectLabel: string
  /** Step en cours pour calibrer le contexte de la suggestion. */
  currentStep?: 'synthese' | 'fiches' | 'menu' | 'exos' | 'exam'
  /** v83h : mode jeu/enquête → la bulle se présente en « coéquipier de mission ». */
  gameMode?: boolean
}

/**
 * Quick prompts pré-définis — l'élève clique au lieu de taper, pour réduire
 * la friction. Adaptés selon le step en cours (et le ton jeu si actif).
 */
function quickPromptsFor(step: Props['currentStep'], payload: AcademyParcoursPayload, gameMode?: boolean): string[] {
  const titre = payload.synthese_20_20?.titre ?? 'le sujet'
  const firstFiche = payload.fiches?.[0]?.titre ?? ''
  if (gameMode) {
    switch (step) {
      case 'synthese': return [
        `Explique-moi le briefing « ${titre} » simplement, avec un exemple marquant`,
        `Quels pièges vont me coûter des clés sur ce sujet ?`,
        `Donne-moi un moyen mnémo fun pour retenir l'essentiel`,
      ]
      case 'fiches': return [
        firstFiche ? `Développe l'entrée « ${firstFiche} » du carnet avec un cas concret` : `Développe la première entrée du carnet avec un cas concret`,
        `Donne-moi des exemples vivants (pas scolaires) pour chaque entrée`,
        `Quelle entrée du carnet est la plus décisive pour le Boss ?`,
      ]
      case 'menu':
      case 'exos': return [
        `Je bute sur ce défi — file-moi un indice sans donner la réponse`,
        `Pourquoi cette réponse est la bonne ? Explique le raisonnement`,
        `Refais-moi un défi du même style dans un autre contexte`,
      ]
      case 'exam': return [
        `Donne-moi le plan parfait pour le Boss final sur ce sujet`,
        `Quels dates / chiffres / citations je DOIS placer pour le vaincre ?`,
        `Quels pièges éviter dans ma copie du Boss ?`,
      ]
      default: return [
        `Explique « ${titre} » simplement, sans jargon`,
        `Donne 3 exemples concrets à placer dans ma copie`,
        `Comment je gagne 2 points de plus sur ce sujet ?`,
      ]
    }
  }
  switch (step) {
    case 'synthese':
      return [
        `Explique-moi "${titre}" comme si j'avais 12 ans, avec un exemple drôle`,
        `Quelles sont les 3 erreurs classiques que les élèves font sur ce sujet ?`,
        `Donne-moi un moyen mnémotechnique fun pour retenir l'essentiel`,
      ]
    case 'fiches':
      return [
        firstFiche ? `Développe la fiche "${firstFiche}" avec un cas concret BAC` : `Développe la première fiche avec un cas concret`,
        `Donne-moi des exemples vivants (pas scolaires) pour chaque fiche`,
        `Quelle fiche est la plus importante pour cartonner ?`,
      ]
    case 'menu':
    case 'exos':
      return [
        `Je galère sur cet exo — donne-moi un coup de pouce sans me donner la réponse`,
        `Aide-moi à comprendre POURQUOI cette réponse est correcte`,
        `Refais-moi un exo similaire mais dans un autre contexte`,
      ]
    case 'exam':
      return [
        `Donne-moi le plan parfait pour une dissertation sur ce sujet`,
        `Quelles citations / dates / chiffres je DOIS placer pour cartonner ?`,
        `Quels pièges éviter dans ma copie ?`,
      ]
    default:
      return [
        `Explique "${titre}" simplement, sans jargon`,
        `Donne 3 exemples concrets que je peux placer dans ma copie`,
        `Comment je peux gagner 2 points de plus sur ce sujet ?`,
      ]
  }
}

export default function ParcoursAssistantBubble({ payload, subjectLabel, currentStep, gameMode }: Props) {
  const [open, setOpen] = useState(false)
  const [autoOpened, setAutoOpened] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [pulse, setPulse] = useState(true)

  // Auto-open ~1.2s après mount + welcome message tailored au parcours.
  // Le pulse stoppe au premier ouvert pour ne pas gener visuellement.
  useEffect(() => {
    if (autoOpened) return
    const t = window.setTimeout(() => {
      setOpen(true)
      setAutoOpened(true)
      setPulse(false)
      setMessages([{
        role: 'assistant',
        content: gameMode
          ? `🎲 Salut ! Je suis ton coéquipier de mission (${subjectLabel}).\n\nOn part sur « ${payload.synthese_20_20?.titre ?? 'ce sujet'} ». Si tu bloques sur une manche, qu'un truc est pas clair, ou que tu veux un indice — sonne-moi, je suis là discret en coin.\n\n_Tu peux aussi cliquer une question rapide ci-dessous._`
          : `🎓 Salut ! Je suis ton coach BAC ${subjectLabel}.\n\nJ'ai lu ton parcours sur "${payload.synthese_20_20?.titre ?? 'ton sujet'}". Si t'as un point pas clair, un truc à creuser, ou si tu veux un exemple plus concret — demande-moi et je développe.\n\n_Tu peux aussi cliquer une question rapide ci-dessous._`,
      }])
    }, 1200)
    return () => window.clearTimeout(t)
  }, [autoOpened, payload, subjectLabel])

  // Stoppe le pulse dès que l'utilisateur ouvre manuellement.
  useEffect(() => {
    if (open) setPulse(false)
  }, [open])

  // Scroll auto vers le dernier message.
  useEffect(() => {
    if (!scrollRef.current) return
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, streaming])

  const quickPrompts = useMemo(() => quickPromptsFor(currentStep, payload, gameMode), [currentStep, payload, gameMode])

  // Build le system prompt avec tout le contexte parcours.
  const systemPrompt = useMemo(() => {
    const lines: string[] = []
    lines.push(gameMode
      ? `Tu es le COÉQUIPIER DE MISSION d'un.e élève dans un parcours de révision ${subjectLabel} déguisé en aventure à manches (Préparation → Carnet → Choix → Défis → Boss final). Ton job : l'aider sans spoiler — indices progressifs, explications du POURQUOI, encouragements. Tu parles comme un pote dans la même équipe.`
      : `Tu es un coach BAC ${subjectLabel} fun, direct et pédagogue. Tu aides un.e élève à comprendre son parcours révision.`)
    lines.push('')
    lines.push('STYLE :')
    lines.push('- Tu parles comme un pote qui connait le BAC — décontracté mais précis.')
    lines.push('- Tu utilises des analogies concrètes, des exemples vivants (films, jeux, vie quotidienne).')
    lines.push('- Tu évites le jargon scolaire pesant. Si tu introduis un terme technique, tu le traduis.')
    lines.push('- Tu es BREF par défaut (3-8 phrases) sauf si l\'élève demande explicitement plus.')
    lines.push('- Markdown OK pour structurer (gras, listes courtes), mais pas de sections lourdes.')
    lines.push('- Tu finis souvent par une mini-question ou un check de compréhension.')
    lines.push("- Si une vidéo aiderait vraiment à visualiser (schéma animé, expérience, démo), termine ton message par : [VIDÉO: 2 à 5 mots de recherche]. À utiliser avec parcimonie, au plus une par message.")
    lines.push('')
    lines.push('CONTEXTE — voici son parcours :')
    lines.push(`Sujet : ${payload.synthese_20_20?.titre ?? 'inconnu'}`)
    if (payload.is_oral) lines.push(`Mode oral en ${payload.language ?? 'langue cible'}.`)
    if (payload.synthese_20_20?.ce_qu_il_faut_savoir?.length) {
      lines.push('')
      lines.push('À savoir :')
      for (const k of payload.synthese_20_20.ce_qu_il_faut_savoir.slice(0, 8)) {
        lines.push(`- ${k}`)
      }
    }
    if (payload.fiches?.length) {
      lines.push('')
      lines.push('Fiches :')
      for (const f of payload.fiches.slice(0, 6)) {
        lines.push(`- ${f.titre}: ${(f.definition || '').slice(0, 140)}`)
      }
    }
    if (payload.synthese_20_20?.vocabulaire_a_maitriser?.length) {
      lines.push('')
      lines.push('Vocab clé :')
      for (const v of payload.synthese_20_20.vocabulaire_a_maitriser.slice(0, 8)) {
        lines.push(`- ${v.terme} = ${(v.definition_exacte || '').slice(0, 100)}`)
      }
    }
    return lines.join('\n')
  }, [payload, subjectLabel])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || streaming) return
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    const userMsg: Msg = { role: 'user', content: trimmed }
    const placeholderAi: Msg = { role: 'assistant', content: '', streaming: true }
    setMessages((m) => [...m, userMsg, placeholderAi])
    setInput('')
    setStreaming(true)
    try {
      const url = `${getBridgeUrl()}/proxy/ollama/api/chat`
      // Prend les 6 derniers messages comme historique pour ne pas trop grossir.
      const history = [...messages, userMsg].slice(-6).map(({ role, content }) => ({ role, content }))
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          model: 'gemma3:12b',
          stream: true,
          messages: [
            { role: 'system', content: systemPrompt },
            ...history,
          ],
          options: { num_ctx: 8192, temperature: 0.55 },
        }),
      })
      if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`)
      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let acc = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const obj = JSON.parse(line)
            const tok = obj?.message?.content ?? ''
            if (tok) {
              acc += tok
              setMessages((m) => {
                const copy = [...m]
                const last = copy[copy.length - 1]
                if (last && last.streaming) copy[copy.length - 1] = { ...last, content: acc }
                return copy
              })
            }
          } catch {
            // chunk JSON cassé — ignore
          }
        }
      }
      // Final flush
      setMessages((m) => {
        const copy = [...m]
        const last = copy[copy.length - 1]
        if (last && last.streaming) copy[copy.length - 1] = { role: 'assistant', content: acc || '_(réponse vide)_' }
        return copy
      })
    } catch (e) {
      const errMsg = e instanceof Error && e.name === 'AbortError' ? '_(stoppé)_' : `⚠ Coach indisponible : ${String(e).slice(0, 120)}`
      setMessages((m) => {
        const copy = [...m]
        const last = copy[copy.length - 1]
        if (last && last.streaming) copy[copy.length - 1] = { role: 'assistant', content: errMsg }
        return copy
      })
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  const stopStream = () => {
    abortRef.current?.abort()
    setStreaming(false)
  }

  // Bubble fermée : juste l'icône qui pulse.
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        title={gameMode ? 'Coéquipier de mission — clique pour un indice / un coup de main' : 'Coach BAC — clique pour faire développer un point'}
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 70,
          width: 60, height: 60, borderRadius: '50%',
          background: `linear-gradient(135deg, ${VIOLET}, ${GOLD})`,
          border: `2px solid ${GOLD}88`,
          color: '#0a0a0a', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: pulse
            ? `0 0 0 0 ${GOLD}88, 0 6px 28px rgba(0,0,0,0.5)`
            : `0 6px 24px rgba(0,0,0,0.4)`,
          animation: pulse ? 'coachPulse 2.2s ease-out infinite' : undefined,
        }}>
        <Sparkles size={26} />
        <style>{`
          @keyframes coachPulse {
            0%   { box-shadow: 0 0 0 0 ${GOLD}88, 0 6px 28px rgba(0,0,0,0.5); }
            70%  { box-shadow: 0 0 0 18px ${GOLD}00, 0 6px 28px rgba(0,0,0,0.5); }
            100% { box-shadow: 0 0 0 0 ${GOLD}00, 0 6px 28px rgba(0,0,0,0.5); }
          }
        `}</style>
      </button>
    )
  }

  return (
    <aside className="parcoursBubble" style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 70,
      width: 'min(420px, 92vw)', height: 'min(560px, 80vh)',
      borderRadius: 16,
      background: 'oklch(0.16 0.018 70 / 0.97)',
      border: `1px solid ${GOLD}55`,
      boxShadow: '0 20px 80px rgba(0,0,0,0.6)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      backdropFilter: 'blur(8px)',
    }}>
      {/* iter38 : sur mobile la bubble prend tout l'écran (immersif) car
          un widget 420px serait trop tassé sur un écran 360px. */}
      <style>{`
        @media (max-width: 720px) {
          .parcoursBubble {
            bottom: 0 !important;
            right: 0 !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            height: 100dvh !important;
            border-radius: 0 !important;
            border-left: none !important;
            border-right: none !important;
          }
        }
      `}</style>
      {/* Header */}
      <header style={{
        padding: '12px 16px',
        background: `linear-gradient(135deg, ${VIOLET}30, ${GOLD}30)`,
        borderBottom: `1px solid ${GOLD}33`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: '50%',
            background: `linear-gradient(135deg, ${VIOLET}, ${GOLD})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#0a0a0a',
          }}>
            <Sparkles size={18} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>
              {gameMode ? '🎲 Coéquipier' : 'Coach BAC'} · {subjectLabel}
            </div>
            <div style={{ fontSize: 10, color: TEAL, fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.08em' }}>
              ● en ligne · gemma3
            </div>
          </div>
        </div>
        <button type="button" onClick={() => setOpen(false)} title="Fermer"
          style={{
            background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer', padding: 4,
          }}>
          <X size={18} />
        </button>
      </header>

      {/* Messages */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: 14,
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '88%',
            padding: '10px 14px', borderRadius: 14,
            fontSize: 13, lineHeight: 1.5,
            background: m.role === 'user'
              ? `linear-gradient(135deg, ${VIOLET}AA, ${VIOLET}77)`
              : 'rgba(255,255,255,0.05)',
            color: m.role === 'user' ? '#fff' : 'rgba(255,255,255,0.92)',
            border: m.role === 'user' ? 'none' : '1px solid rgba(255,255,255,0.08)',
            whiteSpace: 'pre-wrap',
          }}>
            {(() => {
              // v83f : extrait un éventuel marqueur [VIDÉO: …] → lien de
              // recherche cliquable, retiré du texte affiché.
              const vm = m.content.match(/\[VID[ÉE]O\s*:\s*([^\]]+)\]/i)
              const vid = vm ? vm[1].trim() : null
              const txt = vid ? m.content.replace(/\[VID[ÉE]O\s*:\s*[^\]]+\]/i, '').trim() : m.content
              return (
                <>
                  {txt || (m.streaming
                    ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, opacity: 0.7 }}><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> écrit…</span>
                    : '_(vide)_')}
                  {!m.streaming && vid && (
                    <a href={`https://www.youtube.com/results?search_query=${encodeURIComponent(vid)}`} target="_blank" rel="noopener noreferrer"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8,
                        padding: '4px 10px', borderRadius: 99, textDecoration: 'none',
                        background: `${TEAL}22`, color: TEAL, border: `1px solid ${TEAL}66`,
                        fontSize: 11, fontWeight: 600,
                      }}>
                      🎬 Voir une vidéo : « {vid} »
                    </a>
                  )}
                </>
              )
            })()}
          </div>
        ))}
      </div>

      {/* Quick prompts (uniquement si peu de messages OU à l'idle) */}
      {!streaming && messages.length <= 2 && (
        <div style={{
          padding: '8px 12px',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', flexWrap: 'wrap', gap: 6,
        }}>
          {quickPrompts.map((q, i) => (
            <button key={i} type="button" onClick={() => void send(q)}
              style={{
                padding: '6px 10px', borderRadius: 99,
                background: `${GOLD}18`, color: GOLD,
                border: `1px solid ${GOLD}55`,
                fontSize: 11, cursor: 'pointer',
                fontFamily: 'var(--font-mono, monospace)',
                lineHeight: 1.3,
              }}>
              {q.length > 60 ? q.slice(0, 58) + '…' : q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        padding: 12, borderTop: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', gap: 8, alignItems: 'flex-end',
      }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send(input)
            }
          }}
          rows={1}
          placeholder="Demande-moi de développer un point…"
          style={{
            flex: 1, minHeight: 36, maxHeight: 120,
            padding: '8px 12px', borderRadius: 10,
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.12)',
            color: '#fff', fontSize: 13, fontFamily: 'inherit',
            resize: 'none', outline: 'none',
          }}
        />
        {streaming ? (
          <button type="button" onClick={stopStream}
            title="Arrêter"
            style={{
              padding: '8px 12px', borderRadius: 10,
              background: 'rgba(231,76,60,0.18)', color: 'rgba(231,76,60,0.95)',
              border: '1px solid rgba(231,76,60,0.5)',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
            }}>
            ■
          </button>
        ) : (
          <button type="button" onClick={() => void send(input)}
            disabled={!input.trim()}
            style={{
              padding: '8px 12px', borderRadius: 10,
              background: input.trim() ? `linear-gradient(135deg, ${VIOLET}, ${GOLD})` : 'rgba(255,255,255,0.06)',
              color: input.trim() ? '#0a0a0a' : 'rgba(255,255,255,0.4)',
              border: 'none',
              cursor: input.trim() ? 'pointer' : 'not-allowed',
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: 13, fontWeight: 700,
            }}>
            <Send size={14} />
          </button>
        )}
      </div>
    </aside>
  )
}
