/**
 * entSessionStore — état session ENT côté Aurora frontend.
 *
 * v82jg Pass 3/9 — Phase 2 P2.2.
 *
 * Track :
 *   - adapter actif détecté (Pronote/ÉcoleDirecte/...)
 *   - hostname courant (utile pour reconstruction URL)
 *   - dernier harvest par section (timestamp + count)
 *   - état "extension détectée" pour gating UI
 *
 * Persisté localStorage → reste visible même sans extension active.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { EntSection } from '../services/entAdapters'

export type EntHarvestSummary = {
  ts: number
  count: number
  hostname?: string
}

interface EntSessionState {
  /** Last detected ENT adapter id, e.g. "pronote". null si jamais connecté. */
  activeAdapter: string | null
  /** Last hostname auth'd. */
  activeHostname: string | null
  /** Per-section : dernier harvest persisté. Lookup table. */
  lastHarvests: Record<string, Record<string, EntHarvestSummary>>
  /** ✓ après le 1er harvest réussi pour gating UI académie. */
  hasAnyHarvest: boolean

  setActive: (adapter: string | null, hostname: string | null) => void
  recordHarvest: (adapter: string, section: EntSection, summary: EntHarvestSummary) => void
  clearAll: () => void
  getLastHarvest: (adapter: string, section: EntSection) => EntHarvestSummary | null
}

export const useEntSessionStore = create<EntSessionState>()(
  persist(
    (set, get) => ({
      activeAdapter: null,
      activeHostname: null,
      lastHarvests: {},
      hasAnyHarvest: false,
      setActive: (adapter, hostname) => set({ activeAdapter: adapter, activeHostname: hostname }),
      recordHarvest: (adapter, section, summary) => {
        set((state) => {
          const current = state.lastHarvests[adapter] ?? {}
          return {
            lastHarvests: {
              ...state.lastHarvests,
              [adapter]: { ...current, [section]: summary },
            },
            hasAnyHarvest: true,
          }
        })
      },
      clearAll: () => set({
        activeAdapter: null,
        activeHostname: null,
        lastHarvests: {},
        hasAnyHarvest: false,
      }),
      getLastHarvest: (adapter, section) => {
        const adapterHarvests = get().lastHarvests[adapter]
        return adapterHarvests?.[section] ?? null
      },
    }),
    {
      name: 'aurora-ent-session-v1',
      partialize: (state) => ({
        activeAdapter: state.activeAdapter,
        activeHostname: state.activeHostname,
        lastHarvests: state.lastHarvests,
        hasAnyHarvest: state.hasAnyHarvest,
      }),
    },
  ),
)
