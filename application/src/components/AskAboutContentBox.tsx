import { useState } from 'react'
import { HelpCircle, Loader2, Send } from 'lucide-react'
import { ollamaChat } from '../hooks/useTauri.ts'
import { getErrorMessage } from '../utils/errors.ts'

export type AskAboutContentBoxProps = {
  /** Title of the panel, shown in the header */
  label?: string
  /** Free-form context text (the course body, the fiche text, the parcours step…) */
  context: string
  /** Optional short subject label — shown to the LLM for grounding */
  subject?: string
  /** Optional academic level (e.g. "terminale", "prepa"), so the answer stays at that level */
  level?: string
  /** LLM model to use — same as the rest of the academie module */
  model: string
  /** Hint text displayed in the input placeholder */
  placeholder?: string
  /** Class overrides for the outer container */
  className?: string
}

type Exchange = {
  question: string
  answer: string
  error?: string
}

export default function AskAboutContentBox({
  label = 'Poser une question sur ce contenu',
  context,
  subject,
  level,
  model,
  placeholder = 'Je ne comprends pas cette partie...',
  className,
}: AskAboutContentBoxProps) {
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<Exchange[]>([])
  const [loading, setLoading] = useState(false)

  const ask = async () => {
    const question = input.trim()
    if (!question || loading) return
    setLoading(true)
    const pendingIndex = history.length
    setHistory((prev) => [...prev, { question, answer: '' }])
    setInput('')

    try {
      const response = await ollamaChat(model, [
        {
          role: 'system',
          content: [
            'Tu es le module Academie de Aurora IA. L utilisateur consulte un contenu pedagogique et te pose une question pour mieux comprendre.',
            level ? `NIVEAU ACADEMIQUE: ${level.toUpperCase()}. Reste strictement a ce niveau, ne descends pas pour "simplifier".` : '',
            subject ? `SUJET: ${subject}` : '',
            '',
            'REGLES:',
            '- Reponds UNIQUEMENT en francais, en 3 a 8 phrases maximum, claires et precises.',
            '- Appuie-toi d abord sur le CONTEXTE fourni; si un element manque, dis-le et complete avec des connaissances fiables.',
            '- Si la question est vague, demande une precision en une phrase au lieu d inventer.',
            '- Donne un exemple concret OU un petit raisonnement pas-a-pas quand c est pertinent.',
            '- Evite le remplissage, les emojis et les formules de politesse superflues.',
          ].filter(Boolean).join('\n'),
        },
        {
          role: 'user',
          content: [
            'CONTEXTE DU CONTENU COURANT:',
            '---',
            context.slice(0, 6000),
            '---',
            '',
            `QUESTION DE L UTILISATEUR: ${question}`,
          ].join('\n'),
        },
      ], 0.15)
      const answer = (response?.message?.content || '').trim()
        || 'Je n ai pas trouve de reponse claire. Reformule la question ou precise le point qui te bloque.'
      setHistory((prev) => prev.map((item, idx) => (idx === pendingIndex ? { ...item, answer } : item)))
    } catch (err) {
      const message = getErrorMessage(err, 'Echec de la reponse.')
      setHistory((prev) => prev.map((item, idx) => (idx === pendingIndex ? { ...item, error: message } : item)))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`rounded-2xl border border-aurora-border/40 bg-aurora-surface/55 p-4 ${className ?? ''}`}>
      <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">
        <HelpCircle size={13} />
        {label}
      </p>
      <p className="mt-1 text-xs text-aurora-text-dim">
        Demande une explication, un exemple supplementaire ou la reformulation d un passage qui t echappe. Le module repond sur la base du contenu affiche ci-dessus.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void ask()
            }
          }}
          placeholder={placeholder}
          className="flex-1 rounded-xl border border-aurora-border/40 bg-aurora-bg/50 px-3 py-2 text-sm text-aurora-text outline-none focus:border-aurora-accent/50"
        />
        <button
          onClick={() => void ask()}
          disabled={loading || !input.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-xl gradient-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          Demander
        </button>
      </div>
      {history.length > 0 && (
        <div className="mt-3 space-y-3">
          {history.map((exchange, idx) => (
            <div key={idx} className="rounded-xl border border-aurora-border/30 bg-aurora-surface-2/60 px-3 py-2">
              <p className="text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Q</p>
              <p className="mt-1 text-sm text-aurora-text">{exchange.question}</p>
              <p className="mt-3 text-[11px] uppercase tracking-[0.18em] text-aurora-text-dim">Reponse</p>
              {exchange.error ? (
                <p className="mt-1 text-sm text-aurora-red/80">{exchange.error}</p>
              ) : exchange.answer ? (
                <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-aurora-text">{exchange.answer}</p>
              ) : (
                <p className="mt-1 inline-flex items-center gap-2 text-xs text-aurora-text-dim">
                  <Loader2 size={12} className="animate-spin" />
                  Reflexion en cours...
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
