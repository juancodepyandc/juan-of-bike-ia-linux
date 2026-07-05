/**
 * Per-module UI draft persistence. Every module that lets the user type a
 * prompt / select a style / upload a file / etc. stores its in-flight state
 * here so a reload never starts from zero.
 *
 * The backend (bridge + ComfyUI + Ollama) is untouched by a reload. This
 * store is purely the *visual* state the phone loses on tab-kill.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModuleId } from '../types/app'

export interface ModuleDraft {
  /** Raw user prompt (textarea contents). */
  prompt?: string
  /** Style tag / category selection (per-module vocabulary). */
  style?: string
  /** Motion / mood / variant / seed — free-form JSON keyed by the module. */
  options?: Record<string, unknown>
  /** Last time the draft was touched — used to prune stale entries. */
  updatedAt: number
  /** Module-specific arbitrary scratch-pad. */
  scratch?: Record<string, unknown>
}

interface ModuleDraftsState {
  drafts: Partial<Record<ModuleId, ModuleDraft>>
  setDraft: (id: ModuleId, patch: Partial<Omit<ModuleDraft, 'updatedAt'>>) => void
  clearDraft: (id: ModuleId) => void
  getDraft: (id: ModuleId) => ModuleDraft | undefined
}

export const useModuleDraftsStore = create<ModuleDraftsState>()(
  persist(
    (set, get) => ({
      drafts: {},
      setDraft: (id, patch) =>
        set((s) => {
          const prev = s.drafts[id] ?? { updatedAt: 0 }
          return {
            drafts: {
              ...s.drafts,
              [id]: {
                ...prev,
                ...patch,
                options: { ...(prev.options || {}), ...(patch.options || {}) },
                scratch: { ...(prev.scratch || {}), ...(patch.scratch || {}) },
                updatedAt: Date.now(),
              },
            },
          }
        }),
      clearDraft: (id) =>
        set((s) => {
          const next = { ...s.drafts }
          delete next[id]
          return { drafts: next }
        }),
      getDraft: (id) => get().drafts[id],
    }),
    {
      name: 'module-drafts-v1',
    },
  ),
)

/** React helper: bind a single field of a module draft. */
export function useModuleDraftField<T>(
  id: ModuleId,
  field: keyof ModuleDraft,
  defaultValue: T,
): [T, (v: T) => void] {
  const value = useModuleDraftsStore((s) => (s.drafts[id]?.[field] as T | undefined) ?? defaultValue)
  const setDraft = useModuleDraftsStore((s) => s.setDraft)
  const set = (v: T) => setDraft(id, { [field]: v } as Partial<ModuleDraft>)
  return [value, set]
}
