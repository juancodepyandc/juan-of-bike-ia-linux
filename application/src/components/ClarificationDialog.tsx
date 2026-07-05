import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { HelpCircle, Send, X } from 'lucide-react'

export interface ClarificationRequest {
  question: string
  /**
   * v77zh: when the upstream knows a finite set of plausible answers (e.g.
   * the 3D module's targeted clarification categories — character anatomy,
   * mechanism motion, vehicle motion, material ambiguous, person reproduction
   * views) it can pass them here. The dialog renders them as one-click
   * buttons above the free-text textarea so the user does not have to type
   * the answer the system already knew was likely.
   */
  options?: string[]
  /** Optional category hint (kept generic so non-3D callers can use it). */
  categoryLabel?: string
  /** Callback with user response — null if dismissed */
  onRespond: (response: string | null) => void
}

interface Props {
  request: ClarificationRequest | null
}

export default function ClarificationDialog({ request }: Props) {
  const [response, setResponse] = useState('')

  function handleSubmit() {
    if (!request || !response.trim()) return
    const answer = response.trim()
    setResponse('')
    request.onRespond(answer)
  }

  function handleDismiss() {
    if (!request) return
    setResponse('')
    request.onRespond(null)
  }

  function handleOption(option: string) {
    if (!request) return
    setResponse('')
    request.onRespond(option)
  }

  const options = request?.options ?? []

  return (
    <AnimatePresence>
      {request && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) handleDismiss() }}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0, y: 12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0, y: 12 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="relative w-full max-w-lg mx-4 rounded-2xl border border-aurora-accent/20 bg-[#0e0e10] p-6 shadow-2xl"
          >
            <button
              onClick={handleDismiss}
              className="absolute top-4 right-4 text-white/40 hover:text-white/70 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-start gap-3 mb-5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-aurora-accent/15">
                <HelpCircle size={20} className="text-aurora-accent" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-aurora-accent-light mb-2">
                  {request.categoryLabel ? `Clarification — ${request.categoryLabel}` : 'Clarification requise'}
                </p>
                <p className="text-sm leading-relaxed text-white/85">
                  {request.question}
                </p>
              </div>
            </div>

            {options.length > 0 && (
              <div className="mb-4 flex flex-col gap-2">
                {options.map((option) => (
                  <button
                    key={option}
                    onClick={() => handleOption(option)}
                    className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2/60 px-3 py-2.5 text-left text-sm text-aurora-text/90 transition-colors hover:border-aurora-accent/40 hover:bg-aurora-accent/10 hover:text-aurora-text focus:border-aurora-accent/60 focus:outline-none"
                  >
                    {option}
                  </button>
                ))}
                <p className="mt-1 text-[11px] text-white/40">
                  Choisis une option ou tape une reponse libre ci-dessous.
                </p>
              </div>
            )}

            <div className="flex gap-2">
              <textarea
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmit()
                  }
                }}
                placeholder={options.length > 0 ? 'Reponse libre (sinon clique une option)' : 'Ta reponse...'}
                rows={2}
                className="flex-1 resize-none rounded-xl border border-aurora-border bg-aurora-bg/60 px-3 py-2.5 text-sm text-aurora-text outline-none transition-colors focus:border-aurora-accent/45"
                autoFocus={options.length === 0}
              />
              <button
                onClick={handleSubmit}
                disabled={!response.trim()}
                className={`self-end flex h-10 w-10 items-center justify-center rounded-xl transition-all ${
                  response.trim()
                    ? 'gradient-accent text-white'
                    : 'bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
                }`}
              >
                <Send size={16} />
              </button>
            </div>

            <button
              onClick={handleDismiss}
              className="mt-3 w-full px-4 py-2 rounded-xl text-xs text-white/30 hover:text-white/50 transition-colors"
            >
              Ignorer et continuer sans reponse
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
