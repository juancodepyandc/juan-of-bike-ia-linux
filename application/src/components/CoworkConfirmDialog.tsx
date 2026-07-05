// ---------------------------------------------------------------------------
// CoworkConfirmDialog — modal shown when the action executor needs explicit
// user approval for a potentially-destructive step (write/edit/delete/shell
// outside allowlist or outside the workspace).
//
// Resolves through useCoworkStore.pendingConfirmation: approve / skip / abort.
// ---------------------------------------------------------------------------

import { AnimatePresence, motion } from 'framer-motion'
import { Check, ShieldAlert, SkipForward, X } from 'lucide-react'
import { useCoworkStore } from '../stores/coworkStore'
import type { CoworkAction, CoworkConfirmation } from '../services/coworkTypes'
import { useState } from 'react'

export default function CoworkConfirmDialog() {
  const pending = useCoworkStore((s) => s.pendingConfirmation)
  return (
    <AnimatePresence>
      {pending && <Dialog confirmation={pending} />}
    </AnimatePresence>
  )
}

function Dialog({ confirmation }: { confirmation: CoworkConfirmation }) {
  const { action, reason, destructive, approve, skip, abort } = confirmation
  const [ackChecked, setAckChecked] = useState(false)
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[260] flex items-center justify-center bg-black/70 backdrop-blur-sm"
    >
      <motion.div
        initial={{ y: 24, opacity: 0, scale: 0.97 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        exit={{ y: 12, opacity: 0, scale: 0.97 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#0b111b] p-6 text-white shadow-[0_30px_90px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start gap-3">
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${destructive ? 'bg-amber-500/15 text-amber-300' : 'bg-violet-500/15 text-violet-300'}`}>
            <ShieldAlert size={18} />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/40">Confirmation requise</p>
            <h3 className="mt-1 text-lg font-semibold tracking-tight">
              {destructive ? 'Action destructive' : 'Action a verifier'}
            </h3>
            <p className="mt-2 text-sm text-white/70">{reason}</p>
          </div>
        </div>

        <div className="mt-5 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/40">Action</p>
          <p className="mt-2 text-sm text-white/85">{describe(action)}</p>
          <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-black/40 p-3 text-[11px] leading-relaxed text-white/70">
            {safeStringify(action)}
          </pre>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
          {destructive && (
            <label className="flex items-center gap-2 mr-auto text-sm text-white/80">
              <input type="checkbox" checked={ackChecked} onChange={(e) => setAckChecked(e.target.checked)} className="h-4 w-4 rounded border-white/10 bg-black/20" />
              <span>Je comprends les risques et souhaite continuer</span>
            </label>
          )}
          <button
            type="button"
            onClick={abort}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-medium text-white/80 transition-colors hover:bg-white/[0.08]"
          >
            <X size={13} />
            Tout arreter
          </button>
          <button
            type="button"
            onClick={skip}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] font-medium text-white/80 transition-colors hover:bg-white/[0.08]"
          >
            <SkipForward size={13} />
            Sauter cette etape
          </button>
          <button
            type="button"
            onClick={approve}
            className={`inline-flex items-center gap-2 rounded-full px-5 py-2 text-[12px] font-semibold text-white transition-colors ${
              destructive
                ? 'bg-amber-500/90 hover:bg-amber-500'
                : 'bg-violet-500 hover:bg-violet-600'
            }`}
            disabled={destructive && !ackChecked}
          >
            <Check size={13} />
            Autoriser
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

function describe(action: CoworkAction): string {
  switch (action.kind) {
    case 'write_file':  return `Ecrire ${action.path} (${action.content.length} octets)`
    case 'edit_file':   return `Modifier ${action.path} (replace exact-match)`
    case 'delete_file': return `Supprimer ${action.path}`
    case 'shell':       return `Lancer "${action.command} ${(action.args ?? []).join(' ')}"`.trim()
    case 'web_search':  return `Recherche web : ${action.query}`
    case 'fetch':       return `Fetch ${action.method ?? 'GET'} ${action.url}`
    case 'read_file':   return `Lire ${action.path}`
    case 'list_dir':    return `Lister ${action.path}`
    case 'open_url':    return `Ouvrir ${action.url}`
    case 'reply':       return 'Repondre au user'
    case 'finish':      return action.summary
    case 'clipboard_read':  return 'Lire le presse-papiers'
    case 'clipboard_write': return 'Ecrire dans le presse-papiers'
    case 'voice_speak':     return `Lire a voix haute (${action.text.length} caracteres)`
    case 'dom_query':       return `Lire le DOM ${action.selector}${action.attribute ? `[${action.attribute}]` : ''}`
    case 'think':           return `Reflexion : ${action.topic}`
    case 'think_long':      return `Reflexion longue : ${action.topic} (LLM local)`
    case 'remember_fact':   return `Memoriser : ${action.fact.slice(0, 60)}`
    case 'forget_fact':     return `Oublier ${action.id ? `id=${action.id}` : `match="${action.matching}"`}`
    case 'vision_describe': return `Vision : analyse l image fournie`
    case 'screenshot_desktop': return `Capture ecran systeme (Print Screen)`
    case 'connector':       return `Connecteur ${action.connector}.${action.action}`
    case 'browser':         return `Navigateur : ${action.operation}`
  }
}

function safeStringify(action: CoworkAction): string {
  try { return JSON.stringify(action, null, 2) } catch { return String(action) }
}
