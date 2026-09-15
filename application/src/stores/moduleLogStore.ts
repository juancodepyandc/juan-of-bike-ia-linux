import { create } from 'zustand'
import type { ModuleId } from '../types/app.ts'

export interface ModuleLogEntry {
  timestamp: number
  module: ModuleId
  level: 'info' | 'warn' | 'error' | 'retry' | 'repair'
  message: string
  detail?: string
}

interface ModuleLogState {
  logs: ModuleLogEntry[]

  /** Ajoute une entree de log pour un module. */
  log: (module: ModuleId, level: ModuleLogEntry['level'], message: string, detail?: string) => void

  /** Retourne les logs filtres par module. */
  getModuleLogs: (module: ModuleId, limit?: number) => ModuleLogEntry[]

  /** Efface tous les logs. */
  clearLogs: () => void
}

const MAX_LOGS = 200

export const useModuleLogStore = create<ModuleLogState>((set, get) => ({
  logs: [],

  log: (module, level, message, detail) =>
    set((state) => ({
      logs: [
        ...state.logs.slice(-(MAX_LOGS - 1)),
        { timestamp: Date.now(), module, level, message, detail },
      ],
    })),

  getModuleLogs: (module, limit = 50) => {
    return get()
      .logs.filter((entry) => entry.module === module)
      .slice(-limit)
  },

  clearLogs: () => set({ logs: [] }),
}))
