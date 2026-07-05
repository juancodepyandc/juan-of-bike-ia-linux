import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModuleId } from '../types/app'
import { inferTitle } from '../utils/titleInference.ts'

export interface ModuleHistoryMessage {
  role: 'user' | 'assistant'
  content: string
  images?: string[]
  timestamp: number
}

export interface ConversationSession {
  id: string
  module: ModuleId
  title: string
  messages: ModuleHistoryMessage[]
  createdAt: number
  updatedAt: number
}

interface ModuleHistoryState {
  // Anciennes donnees backwards-compatible
  histories: Record<string, ModuleHistoryMessage[]>

  // Nouveau: sessions de conversation par module
  sessions: ConversationSession[]
  activeSessionId: Record<string, string> // module → sessionId

  /** Cree une nouvelle session pour un module et la rend active. */
  createSession: (module: ModuleId, title?: string) => string

  /** Supprime une session. Si c'etait l'active, switch vers la precedente ou en cree une nouvelle. */
  deleteSession: (sessionId: string) => void

  /** Change la session active pour un module. */
  switchSession: (module: ModuleId, sessionId: string) => void

  /** Ouvre un prompt d'historique comme conversation isolee. */
  openPromptSession: (module: ModuleId, prompt: string, sessionId?: string | null) => ConversationSession

  /** Renomme une session. */
  renameSession: (sessionId: string, title: string) => void

  /** Retourne la session active du module (en cree une si aucune). */
  getActiveSession: (module: ModuleId) => ConversationSession

  /** Retourne toutes les sessions d'un module. */
  getModuleSessions: (module: ModuleId) => ConversationSession[]

  /** Ajoute un message a la session active du module. */
  pushMessage: (module: ModuleId, message: Omit<ModuleHistoryMessage, 'timestamp'>) => void

  /** Retourne les N derniers echanges de la session active. */
  getRecentMessages: (module: ModuleId, maxTurns?: number) => ModuleHistoryMessage[]

  /** Efface l'historique de la session active d'un module. */
  clearHistory: (module: ModuleId) => void

  /** Efface tout. */
  clearAll: () => void
}

const MAX_MESSAGES_PER_SESSION = 60
const MAX_SESSIONS_PER_MODULE = 20

function generateSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `session-${crypto.randomUUID()}`
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

// inferTitle is imported from utils/titleInference

export const useModuleHistoryStore = create<ModuleHistoryState>()(
  persist(
    (set, get) => ({
      histories: {},
      sessions: [],
      activeSessionId: {},

      createSession: (module, title) => {
        const id = generateSessionId()
        const session: ConversationSession = {
          id,
          module,
          title: title || 'Nouvelle conversation',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        set((state) => {
          // Limite le nombre de sessions par module
          const moduleSessions = state.sessions.filter((s) => s.module === module)
          const toRemove = moduleSessions.length >= MAX_SESSIONS_PER_MODULE
            ? moduleSessions.slice(0, moduleSessions.length - MAX_SESSIONS_PER_MODULE + 1).map((s) => s.id)
            : []
          return {
            sessions: [...state.sessions.filter((s) => !toRemove.includes(s.id)), session],
            activeSessionId: { ...state.activeSessionId, [module]: id },
          }
        })
        return id
      },

      deleteSession: (sessionId) => {
        set((state) => {
          const session = state.sessions.find((s) => s.id === sessionId)
          if (!session) return state

          const remaining = state.sessions.filter((s) => s.id !== sessionId)
          const moduleSessions = remaining
            .filter((s) => s.module === session.module)
            .sort((a, b) => b.updatedAt - a.updatedAt)
          const newActive = { ...state.activeSessionId }

          if (newActive[session.module] === sessionId) {
            if (moduleSessions.length > 0) {
              newActive[session.module] = moduleSessions[0].id
            } else {
              // Creer une nouvelle session vide
              const newId = generateSessionId()
              const newSession: ConversationSession = {
                id: newId,
                module: session.module,
                title: 'Nouvelle conversation',
                messages: [],
                createdAt: Date.now(),
                updatedAt: Date.now(),
              }
              remaining.push(newSession)
              newActive[session.module] = newId
            }
          }

          return { sessions: remaining, activeSessionId: newActive }
        })
      },

      switchSession: (module, sessionId) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId && s.module === module ? { ...s, updatedAt: Date.now() } : s,
          ),
          activeSessionId: { ...state.activeSessionId, [module]: sessionId },
        }))
      },

      openPromptSession: (module, prompt, sessionId) => {
        const trimmed = prompt.trim()
        if (!trimmed) return get().getActiveSession(module)

        let opened: ConversationSession | null = null
        set((state) => {
          const now = Date.now()
          const requested = sessionId
            ? state.sessions.find((s) => s.id === sessionId && s.module === module)
            : null
          const matching = requested || [...state.sessions]
            .filter((s) => s.module === module)
            .sort((a, b) => b.updatedAt - a.updatedAt)
            .find((s) => s.messages.some((m) => m.role === 'user' && m.content.trim() === trimmed))

          if (matching) {
            opened = { ...matching, updatedAt: now }
            return {
              sessions: state.sessions.map((s) =>
                s.id === matching.id ? { ...s, updatedAt: now } : s,
              ),
              activeSessionId: { ...state.activeSessionId, [module]: matching.id },
            }
          }

          const id = generateSessionId()
          const session: ConversationSession = {
            id,
            module,
            title: inferTitle(trimmed),
            messages: [{ role: 'user', content: trimmed, timestamp: now }],
            createdAt: now,
            updatedAt: now,
          }
          opened = session

          const moduleSessions = state.sessions.filter((s) => s.module === module)
          const toRemove = moduleSessions.length >= MAX_SESSIONS_PER_MODULE
            ? moduleSessions.slice(0, moduleSessions.length - MAX_SESSIONS_PER_MODULE + 1).map((s) => s.id)
            : []

          return {
            sessions: [...state.sessions.filter((s) => !toRemove.includes(s.id)), session],
            activeSessionId: { ...state.activeSessionId, [module]: id },
            histories: {
              ...state.histories,
              [module]: [...(state.histories[module] || []), session.messages[0]].slice(-MAX_MESSAGES_PER_SESSION),
            },
          }
        })

        return opened || get().getActiveSession(module)
      },

      renameSession: (sessionId, title) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s,
          ),
        }))
      },

      getActiveSession: (module) => {
        const state = get()
        const activeId = state.activeSessionId[module]
        const existing = activeId ? state.sessions.find((s) => s.id === activeId) : null

        if (existing) return existing

        // Creer automatiquement une session si aucune n'existe.
        // IMPORTANT: on defer le set() via queueMicrotask pour eviter
        // "Cannot update a component while rendering a different component"
        // quand getActiveSession est appele depuis un render React.
        const id = generateSessionId()
        const session: ConversationSession = {
          id,
          module,
          title: 'Nouvelle conversation',
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        }
        queueMicrotask(() => {
          // Verifie qu'une autre creation n'a pas eu lieu entre-temps
          const current = get()
          const alreadyCreated = current.sessions.some((s) => s.id === id)
          if (!alreadyCreated) {
            set((prev) => ({
              sessions: [...prev.sessions, session],
              activeSessionId: { ...prev.activeSessionId, [module]: id },
            }))
          }
        })
        return session
      },

      getModuleSessions: (module) => {
        return get().sessions
          .filter((s) => s.module === module)
          .sort((a, b) => b.updatedAt - a.updatedAt)
      },

      pushMessage: (module, message) => {
        const fullMessage = { ...message, timestamp: Date.now() }

        set((state) => {
          // Session active
          const activeId = state.activeSessionId[module]
          let sessions = state.sessions
          let needsNewSession = !activeId || !sessions.find((s) => s.id === activeId)

          if (needsNewSession) {
            const id = generateSessionId()
            const session: ConversationSession = {
              id,
              module,
              title: message.role === 'user' ? inferTitle(message.content) : 'Nouvelle conversation',
              messages: [fullMessage],
              createdAt: Date.now(),
              updatedAt: Date.now(),
            }
            return {
              sessions: [...sessions, session],
              activeSessionId: { ...state.activeSessionId, [module]: id },
              // Backward compat
              histories: {
                ...state.histories,
                [module]: [...(state.histories[module] || []), fullMessage].slice(-MAX_MESSAGES_PER_SESSION),
              },
            }
          }

          sessions = sessions.map((s) => {
            if (s.id !== activeId) return s
            const updated = [...s.messages, fullMessage].slice(-MAX_MESSAGES_PER_SESSION)
            const title = s.messages.length === 0 && message.role === 'user'
              ? inferTitle(message.content)
              : s.title
            return { ...s, messages: updated, title, updatedAt: Date.now() }
          })

          return {
            sessions,
            // Backward compat
            histories: {
              ...state.histories,
              [module]: [...(state.histories[module] || []), fullMessage].slice(-MAX_MESSAGES_PER_SESSION),
            },
          }
        })
      },

      getRecentMessages: (module, maxTurns = 8) => {
        const session = get().getActiveSession(module)
        return session.messages.slice(-(maxTurns * 2))
      },

      clearHistory: (module) => {
        set((state) => {
          const activeId = state.activeSessionId[module]
          return {
            sessions: state.sessions.map((s) =>
              s.id === activeId ? { ...s, messages: [], updatedAt: Date.now() } : s,
            ),
            histories: { ...state.histories, [module]: [] },
          }
        })
      },

      clearAll: () => set({ histories: {}, sessions: [], activeSessionId: {} }),
    }),
    {
      name: 'aurora-module-history',
      version: 2,
    },
  ),
)
