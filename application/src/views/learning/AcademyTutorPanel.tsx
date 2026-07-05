/**
 * AcademyTutorPanel (v83f) — l'« endroit dédié » pour parler à l'IA prof.
 *
 * Demande TOUT ce que tu veux sur un cours / un exo / un concept : l'IA
 * (modèle local, streaming via le bridge) répond comme un prof particulier
 * BAC STI2D. Quand une vidéo aiderait à comprendre, elle propose une
 * recherche vidéo en un clic. Et à la fin d'un échange, elle peut proposer
 * de générer un parcours d'entraînement sur le sujet discuté (classique ou
 * mode jeu) — l'utilisateur n'a plus qu'à cliquer.
 *
 * Marqueurs que l'IA peut émettre en fin de message (parsés puis retirés
 * du texte affiché) :
 *   [VIDÉO: <2-5 mots>]   → bouton « ▶ Regarder une vidéo » (recherche YT)
 *   [PARCOURS: <sujet>]   → bouton « ✨ Créer un parcours d'entraînement »
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { GraduationCap, Send, Loader2, Sparkles, Video, X, RotateCcw, ImagePlus } from 'lucide-react'
import { ollamaChatStream } from '../../hooks/useTauri'
import LyraCharacter from '../../components/voice/LyraCharacter'
import VoiceLandscape from '../../components/voice/VoiceLandscape'
import VoicePushToTalk from '../../components/VoicePushToTalk'
import { buildBacInspirationBlock } from '../../services/learning/bacInspirationDb'

/** Lit un File image → base64 brut (sans le préfixe data:). */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const s = String(r.result || '')
      const comma = s.indexOf(',')
      resolve(comma >= 0 ? s.slice(comma + 1) : s)
    }
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

const GOLD = 'oklch(0.86 0.18 75)'
const TEAL = 'oklch(0.72 0.13 195)'
const gold = (a: number) => `oklch(0.86 0.18 75 / ${a})`
const teal = (a: number) => `oklch(0.72 0.13 195 / ${a})`
const GAME = 'oklch(0.78 0.18 85)'

type Msg = {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  video?: string | null
  parcours?: string | null
}

interface Props {
  subjectLabel: string
  model: string
  /** L'utilisateur clique « créer un parcours » → le parent injecte le sujet,
   *  passe en mode parcours-bac, (option) active le format jeu, et génère. */
  onCreateParcours: (topic: string, gameMode: boolean) => void
}

function parseMarkers(raw: string): { text: string; video: string | null; parcours: string | null } {
  let video: string | null = null
  let parcours: string | null = null
  let text = raw
  text = text.replace(/\[VID[ÉE]O\s*:\s*([^\]]+)\]/gi, (_m, q) => { video = String(q).trim(); return '' })
  text = text.replace(/\[PARCOURS\s*:\s*([^\]]+)\]/gi, (_m, q) => { parcours = String(q).trim(); return '' })
  return { text: text.trim(), video, parcours }
}

const ytSearchUrl = (q: string) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`

const QUICK_PROMPTS = [
  'Explique-moi un chapitre que je dois réviser',
  'Je bloque sur un exercice — aide-moi à le comprendre',
  "C'est quoi la différence entre deux notions que je confonds ?",
  "Donne-moi un exemple concret (pas scolaire) d'un concept",
  'Fais-moi un mini quiz oral de 3 questions',
]

// v84n — questions ciblées BAC (méthodologie + types réels)
const BAC_TARGETED_PROMPTS = [
  { label: 'Méthodologie épreuve', q: 'Quelle est la méthodologie attendue à l\'épreuve écrite BAC pour cette matière ? Donne-moi les étapes phase par phase + les pièges à éviter.' },
  { label: 'Type de raisonnement', q: 'Quel raisonnement le correcteur attend-il sur ce chapitre ? Donne 2 exemples vus aux annales récentes (2022-2024) avec leur démarche type.' },
  { label: 'Annales récentes', q: 'Cite 3 sujets BAC officiels récents qui ont porté sur ce chapitre. Pour chacun, résume la question principale et la trame attendue.' },
  { label: 'Plan dissertation', q: 'Fais-moi un plan dialectique (thèse/antithèse/dépassement) sur le sujet de mon choix avec 3 références d\'auteurs ou de chercheurs ancrées dans le programme officiel.' },
  { label: 'Barème + critères', q: 'Quel est le barème typique d\'un exo de ce type et quels sont les critères de notation (idée juste, démarche, rigueur, communication) ?' },
  { label: 'Erreurs classiques', q: 'Quelles sont les 5 erreurs les plus fréquentes des candidats sur ce chapitre, observées par les jurys ? Comment les éviter ?' },
]

export default function AcademyTutorPanel({ subjectLabel, model, onCreateParcours }: Props) {
  const [open, setOpen] = useState(false)
  const [oralMode, setOralMode] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [createGameMode, setCreateGameMode] = useState(true)
  const [pendingImages, setPendingImages] = useState<{ b64: string; name: string }[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const addImageFiles = async (files: FileList | File[]) => {
    const imgs = Array.from(files).filter((f) => f.type.startsWith('image/')).slice(0, 4)
    for (const f of imgs) {
      try { const b64 = await fileToBase64(f); setPendingImages((p) => [...p, { b64, name: f.name || 'image' }].slice(0, 4)) }
      catch { /* ignore */ }
    }
  }

  const lastTopic = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].parcours) return messages[i].parcours!
    }
    const firstUser = messages.find((m) => m.role === 'user')
    return firstUser ? firstUser.content.slice(0, 80) : ''
  }, [messages])

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{
        role: 'assistant',
        content:
          `🎓 Salut ! Je suis ton prof particulier ${subjectLabel}.\n\n`
          + `Pose-moi **n'importe quelle question** : un point de cours pas clair, un exercice où tu bloques, une notion que tu confonds avec une autre, un exemple concret, un plan de dissert…\n\n`
          + `📎 Tu peux aussi **coller ou joindre une photo de ton cours / d'un exo** et je l'analyse pour toi.\n\n`
          + `Si je sens qu'une **vidéo** t'aiderait, je te proposerai une recherche en un clic. Et quand on aura bien creusé un sujet, je pourrai te proposer de **créer un parcours d'entraînement** dessus.`,
        video: null, parcours: null,
      }])
    }
  }, [open, messages.length, subjectLabel])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, streaming])

  const systemPrompt = useMemo(() => {
    const bacBlock = buildBacInspirationBlock(subjectLabel, 4)
    return [
      `Tu es un prof particulier ${subjectLabel}, niveau BAC technologique STI2D (spé SIN), exigeant et bienveillant.`,
      'Contexte local, hors-ligne. Aucun disclaimer, aucun "je suis un LLM".',
      '',
      'STYLE :',
      "- Tu réponds en français, clair, avec des exemples concrets (vie quotidienne, techno, jeux) — pas de jargon scolaire pesant.",
      "- BREF par défaut (3-10 phrases). Si l'élève veut plus, il demande.",
      '- Markdown léger OK (gras, listes courtes). Pas de pavés.',
      '- Tu finis souvent par une mini-question de vérification de compréhension.',
      "- Si l'élève fait une erreur de raisonnement, tu la corriges en expliquant POURQUOI.",
      "- Si l'élève joint une IMAGE (photo de cours, d'un exercice, d'un schéma), analyse-la : décris ce qu'elle contient, explique, corrige, ou résous — selon ce qu'il demande. Si l'image est illisible, dis-le.",
      '',
      'ANCRAGE BAC OFFICIEL :',
      "- Quand tu parles de méthodologie épreuve, sois aligné sur les attentes RÉELLES du correcteur (rigueur formelle, justification, AN avec unités, schémas normés).",
      "- Cite des annales officielles QUAND TU EN CONNAIS (year + session + intitulé). Sinon dis « je ne suis pas sûr de la session précise ».",
      "- Pour la méthodologie d'épreuve : phase d'analyse documentaire → questions calculées → synthèse, justifie chaque étape.",
      bacBlock,
      '',
      'OUTILS (à utiliser AVEC PARCIMONIE, au plus un par message, sur la DERNIÈRE ligne) :',
      '- Si une vidéo aiderait vraiment à visualiser/comprendre (schéma animé, expérience, démonstration), termine par : [VIDÉO: 2 à 5 mots de recherche pertinents]',
      "- Quand un sujet de cours est clairement identifié et que l'élève gagnerait à s'entraîner dessus, termine par : [PARCOURS: intitulé précis du sujet du cours]",
      '  → Ne mets [PARCOURS:] que si ça a du sens (après avoir expliqué quelque chose), pas à chaque message.',
      '',
      "Tu n'inventes pas de faits : si tu n'es pas sûr, dis-le et propose une vidéo ou une piste de vérification.",
    ].filter(Boolean).join('\n')
  }, [subjectLabel])

  const send = async (text: string) => {
    const trimmed = text.trim()
    const imgs = pendingImages.map((p) => p.b64)
    if ((!trimmed && imgs.length === 0) || streaming) return
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    const displayText = trimmed || (imgs.length > 0 ? `(analyse ${imgs.length === 1 ? 'cette image' : 'ces images'})` : '')
    const userMsg: Msg = { role: 'user', content: displayText + (imgs.length ? ` 🖼×${imgs.length}` : '') }
    setMessages((m) => [...m, userMsg, { role: 'assistant', content: '', streaming: true, video: null, parcours: null }])
    setInput('')
    const sentImages = imgs
    setPendingImages([])
    setStreaming(true)
    let acc = ''
    try {
      const history: { role: 'user' | 'assistant'; content: string; images?: string[] }[] =
        [...messages, { role: 'user' as const, content: trimmed || 'Analyse l\'image jointe et explique-moi ce qu\'il y a dessus (cours / exo), en restant pédagogue.' }]
          .slice(-8)
          .map(({ role, content }) => ({ role, content }))
      if (sentImages.length > 0 && history.length > 0) {
        history[history.length - 1] = { ...history[history.length - 1], images: sentImages }
      }
      await ollamaChatStream(
        model,
        [{ role: 'system', content: systemPrompt }, ...history],
        (tok) => {
          acc += tok
          const parsed = parseMarkers(acc)
          setMessages((m) => {
            const copy = [...m]
            copy[copy.length - 1] = { role: 'assistant', content: parsed.text || acc, streaming: true, video: parsed.video, parcours: parsed.parcours }
            return copy
          })
        },
        () => undefined,
        { temperature: 0.5, num_ctx: 8192, firstByteTimeoutMs: 120_000, signal: abortRef.current.signal },
      )
      const fin = parseMarkers(acc)
      setMessages((m) => {
        const copy = [...m]
        copy[copy.length - 1] = { role: 'assistant', content: fin.text || '(réponse vide — réessaie)', streaming: false, video: fin.video, parcours: fin.parcours }
        return copy
      })
    } catch (e) {
      const aborted = abortRef.current?.signal.aborted
      setMessages((m) => {
        const c = [...m]
        c[c.length - 1] = {
          role: 'assistant',
          content: aborted ? '_(interrompu)_' : `⚠ Le prof IA n'a pas répondu (${e instanceof Error ? e.message : String(e)}). Réessaie.`,
          streaming: false, video: null, parcours: null,
        }
        return c
      })
    } finally {
      setStreaming(false)
    }
  }

  const reset = () => {
    abortRef.current?.abort()
    setStreaming(false)
    setInput('')
    setMessages([]) // le message d'accueil revient via l'effet (open && length===0)
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        title="Pose n'importe quelle question sur un cours — l'IA prof t'explique, te propose des vidéos, et peut générer un parcours d'entraînement."
        style={{
          display: 'flex', alignItems: 'center', gap: 10, width: '100%',
          padding: '12px 14px', borderRadius: 10, cursor: 'pointer',
          background: `linear-gradient(135deg, ${gold(0.14)}, ${teal(0.14)})`,
          border: `1px solid ${gold(0.45)}`,
          color: 'var(--fg, #f5f5f5)', textAlign: 'left',
          fontFamily: 'var(--font-sans, system-ui)',
        }}>
        <GraduationCap size={20} style={{ color: GOLD }} />
        <span style={{ flex: 1 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>🎓 Demande au prof</span><br />
          <span style={{ fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>
            Une question sur un cours ? Demande tout — explications, vidéos, et il peut créer un parcours.
          </span>
        </span>
      </button>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      border: `1px solid ${gold(0.45)}`, borderRadius: 12,
      background: 'var(--bg-raised, rgba(255,255,255,0.03))', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.1))',
        background: `linear-gradient(135deg, ${gold(0.10)}, transparent)`,
      }}>
        <div style={{ width: 36, height: 44, marginLeft: -4 }}>
          <LyraCharacter
            phase={streaming ? 'speaking' : 'idle'}
            emotion={streaming ? 'happy' : 'curious'}
            accent="#d4a64a"
            size={36}
          />
        </div>
        <span style={{ fontWeight: 700, fontSize: 13, flex: 1 }}>🎓 Lyra · prof particulier · {subjectLabel}</span>
        <button
          type="button"
          onClick={() => setOralMode((v) => !v)}
          title={oralMode ? 'Mode oral activé · Lyra parle les réponses' : 'Activer le mode oral (Lyra parle ses réponses)'}
          style={{
            padding: '3px 9px', borderRadius: 99,
            background: oralMode ? gold(0.25) : 'transparent',
            border: `1px solid ${oralMode ? gold(0.6) : 'var(--line, rgba(255,255,255,0.14))'}`,
            color: oralMode ? GOLD : 'var(--fg-mute, #888)',
            cursor: 'pointer', fontSize: 10,
            fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.08em',
            textTransform: 'uppercase',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}
        >🎙 oral</button>
        <button type="button" onClick={reset} title="Nouvelle conversation"
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-mute, #888)', padding: 3, lineHeight: 0 }}>
          <RotateCcw size={13} />
        </button>
        <button type="button" onClick={() => setOpen(false)} title="Replier"
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-mute, #888)', padding: 3, lineHeight: 0 }}>
          <X size={14} />
        </button>
      </div>

      {/* v84i — Stage Lyra plein quand mode oral activé : landscape + perso XL */}
      {oralMode && (
        <AcademyOralStage
          subjectLabel={subjectLabel}
          streaming={streaming}
          lastAssistantText={messages.filter((m) => m.role === 'assistant' && !m.streaming).slice(-1)[0]?.content || ''}
          onClose={() => setOralMode(false)}
        />
      )}

      <div ref={scrollRef} style={{
        maxHeight: 320, overflowY: 'auto', padding: 12,
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '92%', padding: '8px 11px', borderRadius: 10,
            background: m.role === 'user' ? gold(0.14) : 'var(--bg-card, rgba(255,255,255,0.05))',
            border: `1px solid ${m.role === 'user' ? gold(0.35) : 'var(--line-soft, rgba(255,255,255,0.08))'}`,
            fontSize: 12.5, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            color: 'var(--fg, #f5f5f5)',
          }}>
            {m.content || (m.streaming ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : '…')}
            {!m.streaming && m.video && (
              <a href={ytSearchUrl(m.video)} target="_blank" rel="noopener noreferrer"
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8,
                  padding: '5px 10px', borderRadius: 99, textDecoration: 'none',
                  background: teal(0.16), color: TEAL, border: `1px solid ${teal(0.5)}`,
                  fontSize: 11, fontWeight: 600,
                }}>
                <Video size={12} /> Regarder une vidéo : « {m.video} »
              </a>
            )}
            {!m.streaming && m.parcours && (
              <button type="button" onClick={() => onCreateParcours(m.parcours!, createGameMode)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 8,
                  padding: '6px 12px', borderRadius: 99, cursor: 'pointer',
                  background: createGameMode ? GAME : GOLD, color: '#0a0a0a',
                  border: 'none', fontSize: 11.5, fontWeight: 700, fontFamily: 'var(--font-sans, system-ui)',
                }}>
                <Sparkles size={12} /> Créer un parcours {createGameMode ? '🎮 jeu ' : ''}sur « {m.parcours} »
              </button>
            )}
          </div>
        ))}
      </div>

      {messages.length <= 2 && !streaming && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '0 12px 8px' }}>
            {QUICK_PROMPTS.map((q) => (
              <button key={q} type="button" onClick={() => void send(q)}
                style={{
                  padding: '4px 9px', borderRadius: 99, cursor: 'pointer',
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  color: 'var(--fg-dim, #aaa)', fontSize: 11, fontFamily: 'var(--font-sans, system-ui)',
                }}>{q}</button>
            ))}
          </div>
          <div style={{ padding: '0 12px 10px' }}>
            <div style={{ fontSize: 10, color: 'var(--fg-mute, #888)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
              🎯 Questions ciblées BAC
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {BAC_TARGETED_PROMPTS.map((p) => (
                <button key={p.label} type="button" onClick={() => void send(p.q)}
                  title={p.q}
                  style={{
                    padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                    background: gold(0.10),
                    border: `1px solid ${gold(0.4)}`,
                    color: GOLD, fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                    fontWeight: 600,
                  }}>{p.label}</button>
              ))}
            </div>
          </div>
        </>
      )}

      <div style={{ borderTop: '1px solid var(--line, rgba(255,255,255,0.1))', padding: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* v83g — vignettes des images en attente d'analyse */}
        {pendingImages.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {pendingImages.map((p, i) => (
              <span key={i} title={p.name} style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                padding: '3px 8px 3px 6px', borderRadius: 99,
                background: teal(0.14), border: `1px solid ${teal(0.45)}`,
                fontSize: 10.5, color: TEAL, fontFamily: 'var(--font-mono, monospace)',
              }}>
                <img src={`data:image/*;base64,${p.b64}`} alt="" style={{ width: 18, height: 18, objectFit: 'cover', borderRadius: 3 }} />
                {p.name.slice(0, 16)}{p.name.length > 16 ? '…' : ''}
                <button type="button" onClick={() => setPendingImages((arr) => arr.filter((_, j) => j !== i))}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: TEAL, padding: 0, lineHeight: 0 }}>
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 6 }}>
          <input ref={fileRef} type="file" accept="image/*" multiple style={{ display: 'none' }}
            onChange={(e) => { if (e.target.files) void addImageFiles(e.target.files); e.target.value = '' }} />
          <button type="button" onClick={() => fileRef.current?.click()} disabled={streaming}
            title="Joindre une photo de ton cours / d'un exercice — je l'analyse."
            style={{
              padding: '7px 9px', borderRadius: 8, cursor: streaming ? 'not-allowed' : 'pointer',
              background: 'var(--bg-card, rgba(255,255,255,0.04))', color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.14))', opacity: streaming ? 0.5 : 1,
              display: 'inline-flex', alignItems: 'center',
            }}>
            <ImagePlus size={14} />
          </button>
          <input type="text" value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(input) } }}
            onPaste={(e) => {
              const items = Array.from(e.clipboardData?.items || []).filter((it) => it.type.startsWith('image/'))
              if (items.length > 0) {
                e.preventDefault()
                const files = items.map((it) => it.getAsFile()).filter((f): f is File => !!f)
                if (files.length) void addImageFiles(files)
              }
            }}
            disabled={streaming}
            placeholder={pendingImages.length > 0 ? 'Pose ta question sur l\'image (ou laisse vide)…' : 'Demande ce que tu veux — ou colle/joins une photo de ton cours…'}
            style={{
              flex: 1, padding: '7px 10px', fontSize: 12,
              background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.14))', borderRadius: 8,
              fontFamily: 'var(--font-sans, system-ui)',
            }} />
          <VoicePushToTalk
            onTranscript={(t) => setInput((prev) => (prev?.trim() ? `${prev} ${t}` : t))}
            label="Dicter ta question au tuteur"
            size={30}
            variant="ghost"
          />
          <button type="button" onClick={() => streaming ? abortRef.current?.abort() : void send(input)}
            disabled={!streaming && !input.trim() && pendingImages.length === 0}
            style={{
              padding: '7px 12px', borderRadius: 8, cursor: (!streaming && !input.trim() && pendingImages.length === 0) ? 'not-allowed' : 'pointer',
              background: streaming ? 'oklch(0.55 0.18 25)' : GOLD, color: '#0a0a0a',
              border: 'none', opacity: (!streaming && !input.trim() && pendingImages.length === 0) ? 0.5 : 1,
              display: 'inline-flex', alignItems: 'center',
            }}>
            {streaming ? <X size={14} /> : <Send size={14} />}
          </button>
        </div>
        {messages.some((m) => m.role === 'user') && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <button type="button"
              onClick={() => onCreateParcours(lastTopic || subjectLabel, createGameMode)}
              disabled={!lastTopic}
              title="Génère un parcours d'entraînement complet (synthèse → fiches → exos → contrôle) sur le sujet discuté."
              style={{
                flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, cursor: lastTopic ? 'pointer' : 'not-allowed',
                background: lastTopic ? (createGameMode ? GAME : GOLD) : 'transparent',
                color: lastTopic ? '#0a0a0a' : 'var(--fg-mute, #777)',
                border: `1px solid ${lastTopic ? (createGameMode ? GAME : GOLD) : 'var(--line, rgba(255,255,255,0.14))'}`,
                fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-sans, system-ui)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                opacity: lastTopic ? 1 : 0.6,
              }}>
              <Sparkles size={13} /> Créer un parcours {createGameMode ? '🎮 jeu ' : ''}sur ce sujet
            </button>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--fg-dim, #aaa)', cursor: 'pointer', fontFamily: 'var(--font-mono, monospace)' }}>
              <input type="checkbox" checked={createGameMode} onChange={(e) => setCreateGameMode(e.target.checked)} />
              mode jeu 🎮
            </label>
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

// v84i — Stage Lyra plein écran pour le mode oral : exos/examens/cours parlés.
// Landscape Aurora + Lyra XL + speech bubble avec dernière phrase prof.
// L'overlay reste dans l'AcademyTutorPanel mais prend tout le viewport quand oralMode = ON.
function AcademyOralStage({
  subjectLabel,
  streaming,
  lastAssistantText,
  onClose,
}: {
  subjectLabel: string
  streaming: boolean
  lastAssistantText: string
  onClose: () => void
}) {
  // Auto-narrate la dernière réponse via Web Speech API (fallback léger ;
  // un vrai TTS Kokoro serait préférable mais nécessite plus de wiring).
  useEffect(() => {
    if (!lastAssistantText || streaming) return
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    // Strip markers vidéo/parcours du texte avant narration.
    const clean = lastAssistantText
      .replace(/\[VID[ÉE]O\s*:[^\]]+\]/gi, '')
      .replace(/\[PARCOURS\s*:[^\]]+\]/gi, '')
      .replace(/[*_`#]/g, '')
      .trim()
    if (!clean) return
    const utter = new SpeechSynthesisUtterance(clean.slice(0, 600))
    utter.lang = 'fr-FR'
    utter.rate = 0.95
    utter.pitch = 1.1
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utter)
    return () => { window.speechSynthesis.cancel() }
  }, [lastAssistantText, streaming])

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      background: 'rgba(0,0,0,0.92)',
      display: 'flex', flexDirection: 'column',
    }}>
      <VoiceStageEmbed
        subjectLabel={subjectLabel}
        streaming={streaming}
        lastAssistantText={lastAssistantText}
        onClose={onClose}
      />
    </div>
  )
}

function VoiceStageEmbed({
  subjectLabel,
  streaming,
  lastAssistantText,
  onClose,
}: {
  subjectLabel: string
  streaming: boolean
  lastAssistantText: string
  onClose: () => void
}) {
  return (
    <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
      <VoiceLandscapeEmbed />
      <button
        type="button"
        onClick={onClose}
        aria-label="Quitter mode oral"
        style={{
          position: 'absolute', top: 18, right: 18, zIndex: 5,
          padding: '8px 16px', borderRadius: 99,
          background: 'rgba(0,0,0,0.55)',
          border: '1px solid rgba(255,255,255,0.18)',
          color: '#fff', cursor: 'pointer',
          fontFamily: 'var(--font-mono, ui-monospace)', fontSize: 11,
          letterSpacing: '0.08em',
        }}
      >× quitter oral</button>
      <div style={{
        position: 'absolute', top: 18, left: 18, zIndex: 5,
        padding: '6px 14px', borderRadius: 99,
        background: 'rgba(0,0,0,0.55)',
        border: `1px solid ${GOLD}55`,
        color: GOLD, fontSize: 11,
        fontFamily: 'var(--font-mono, ui-monospace)',
        letterSpacing: '0.08em',
      }}>🎓 oral · {subjectLabel}</div>
      <div style={{
        position: 'absolute', left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)', zIndex: 3,
      }}>
        <LyraCharacter
          phase={streaming ? 'speaking' : 'idle'}
          emotion={streaming ? 'happy' : 'curious'}
          accent="#d4a64a"
          size={Math.min(480, window.innerHeight * 0.55)}
        />
      </div>
      {lastAssistantText && !streaming && (
        <div style={{
          position: 'absolute', left: '50%', bottom: '12%',
          transform: 'translateX(-50%)', zIndex: 4,
          maxWidth: 720, padding: '14px 22px',
          background: 'rgba(0,0,0,0.68)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 14,
          color: '#fff', fontSize: 16, lineHeight: 1.5,
          textAlign: 'center',
          backdropFilter: 'blur(6px)',
        }}>{lastAssistantText.slice(0, 360)}</div>
      )}
    </div>
  )
}

function VoiceLandscapeEmbed() {
  return <VoiceLandscape mode="auto" animated />
}
