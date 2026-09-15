import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModuleId } from '../types/app.ts'

export interface SavedPrompt {
  id: string
  module: ModuleId
  prompt: string
  fidelityScore: number
  parameters: Record<string, unknown>
  savedAt: number
  tags: string[]
  useCount: number
}

interface PromptLibraryState {
  prompts: SavedPrompt[]
  addPrompt: (prompt: Omit<SavedPrompt, 'id' | 'savedAt' | 'useCount'>) => SavedPrompt
  updatePrompt: (id: string, changes: Partial<SavedPrompt>) => void
  deletePrompt: (id: string) => void
  incrementUseCount: (id: string) => void
  getPromptsForModule: (module: ModuleId | 'all') => SavedPrompt[]
  searchPrompts: (query: string, module?: ModuleId | 'all') => SavedPrompt[]
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `prompt-${crypto.randomUUID()}`
  }
  return `prompt-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export const usePromptLibraryStore = create<PromptLibraryState>()(
  persist(
    (set, get) => ({
      prompts: [],

      addPrompt(entry) {
        const newPrompt: SavedPrompt = {
          ...entry,
          id: generateId(),
          savedAt: Date.now(),
          useCount: 0,
        }
        set((state) => ({ prompts: [newPrompt, ...state.prompts] }))
        return newPrompt
      },

      updatePrompt(id, changes) {
        set((state) => ({
          prompts: state.prompts.map((p) => (p.id === id ? { ...p, ...changes } : p)),
        }))
      },

      deletePrompt(id) {
        set((state) => ({ prompts: state.prompts.filter((p) => p.id !== id) }))
      },

      incrementUseCount(id) {
        set((state) => ({
          prompts: state.prompts.map((p) => (p.id === id ? { ...p, useCount: p.useCount + 1 } : p)),
        }))
      },

      getPromptsForModule(module) {
        const { prompts } = get()
        if (module === 'all') return [...prompts].sort((a, b) => b.savedAt - a.savedAt)
        return prompts.filter((p) => p.module === module).sort((a, b) => b.savedAt - a.savedAt)
      },

      searchPrompts(query, module) {
        const normalized = query.toLowerCase().trim()
        const { prompts } = get()
        return prompts
          .filter((p) => {
            if (module && module !== 'all' && p.module !== module) return false
            if (!normalized) return true
            return (
              p.prompt.toLowerCase().includes(normalized)
              || p.tags.some((tag) => tag.toLowerCase().includes(normalized))
            )
          })
          .sort((a, b) => b.fidelityScore - a.fidelityScore)
      },
    }),
    {
      name: 'aurora-prompt-library',
      version: 1,
    },
  ),
)
