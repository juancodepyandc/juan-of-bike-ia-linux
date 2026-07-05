import { useCallback, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, MessageSquarePlus, Trash2, Pencil, Check, X } from 'lucide-react'
import { useModuleHistoryStore, type ConversationSession } from '../stores/moduleHistoryStore'
import type { ModuleId } from '../types/app'

interface SessionSwitcherProps {
  module: ModuleId
  /** Callback optionnel quand on change de session (pour reset d'UI locale). */
  onSessionChange?: (session: ConversationSession) => void
}

export default function SessionSwitcher({ module, onSessionChange }: SessionSwitcherProps) {
  const {
    getActiveSession,
    getModuleSessions,
    createSession,
    deleteSession,
    switchSession,
    renameSession,
  } = useModuleHistoryStore()

  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const activeSession = getActiveSession(module)
  const sessions = getModuleSessions(module)

  const handleCreate = useCallback(() => {
    const id = createSession(module)
    const session = useModuleHistoryStore.getState().sessions.find((s) => s.id === id)
    if (session) onSessionChange?.(session)
    setOpen(false)
  }, [createSession, module, onSessionChange])

  const handleSwitch = useCallback((sessionId: string) => {
    switchSession(module, sessionId)
    const session = useModuleHistoryStore.getState().sessions.find((s) => s.id === sessionId)
    if (session) onSessionChange?.(session)
    setOpen(false)
  }, [module, onSessionChange, switchSession])

  const handleDelete = useCallback((sessionId: string) => {
    deleteSession(sessionId)
    const newActive = useModuleHistoryStore.getState().getActiveSession(module)
    onSessionChange?.(newActive)
  }, [deleteSession, module, onSessionChange])

  const handleStartRename = useCallback((session: ConversationSession) => {
    setEditingId(session.id)
    setEditTitle(session.title)
  }, [])

  const handleConfirmRename = useCallback(() => {
    if (editingId && editTitle.trim()) {
      renameSession(editingId, editTitle.trim())
    }
    setEditingId(null)
  }, [editingId, editTitle, renameSession])

  const displayTitle = activeSession.title.length > 30
    ? `${activeSession.title.slice(0, 30)}...`
    : activeSession.title

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-xl border border-aurora-border/35 bg-aurora-surface/60 px-3 py-2 text-left text-xs transition-colors hover:border-aurora-border-light"
      >
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.18em] text-aurora-text-dim">Session</p>
          <p className="mt-0.5 truncate text-aurora-text">{displayTitle}</p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] text-aurora-text-dim">{sessions.length}</span>
          <ChevronDown size={12} className={`text-aurora-text-dim transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-y-auto rounded-xl border border-aurora-border/40 bg-aurora-surface/95 backdrop-blur-xl shadow-lg"
          >
            {/* Nouvelle session */}
            <button
              onClick={handleCreate}
              className="flex w-full items-center gap-2 border-b border-aurora-border/20 px-3 py-2.5 text-xs text-aurora-accent hover:bg-aurora-accent/8 transition-colors"
            >
              <MessageSquarePlus size={14} />
              <span>Nouvelle conversation</span>
            </button>

            {/* Liste des sessions */}
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`group flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
                  session.id === activeSession.id
                    ? 'bg-aurora-accent/10 text-aurora-accent-light'
                    : 'text-aurora-text-muted hover:bg-white/[0.04] hover:text-aurora-text'
                }`}
              >
                {editingId === session.id ? (
                  <div className="flex flex-1 items-center gap-1">
                    <input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleConfirmRename()}
                      className="flex-1 rounded bg-aurora-bg/60 px-1.5 py-0.5 text-xs text-aurora-text outline-none border border-aurora-accent/30"
                      autoFocus
                    />
                    <button onClick={handleConfirmRename} className="text-aurora-green hover:text-aurora-green/80">
                      <Check size={12} />
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-aurora-text-dim hover:text-aurora-red">
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      onClick={() => handleSwitch(session.id)}
                      className="flex-1 truncate text-left"
                    >
                      <span className="truncate">{session.title}</span>
                      <span className="ml-2 text-[10px] text-aurora-text-dim">
                        ({session.messages.length} msg)
                      </span>
                    </button>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleStartRename(session)}
                        className="text-aurora-text-dim hover:text-aurora-accent"
                        title="Renommer"
                      >
                        <Pencil size={11} />
                      </button>
                      {sessions.length > 1 && (
                        <button
                          onClick={() => handleDelete(session.id)}
                          className="text-aurora-text-dim hover:text-aurora-red"
                          title="Supprimer"
                        >
                          <Trash2 size={11} />
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}

            {sessions.length === 0 && (
              <p className="px-3 py-3 text-center text-[11px] text-aurora-text-dim">Aucune session.</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
