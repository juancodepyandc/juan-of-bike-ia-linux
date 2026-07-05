import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModuleId } from '../types/app'
import { auroraVoice } from '../services/auroraVoice'
import { cleanFilenameForTTS } from '../utils/voiceSummary'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GenerationType = 'comfyui' | 'python_script' | 'ollama_stream'
export type GenerationStatus = 'pending' | 'completed' | 'failed' | 'interrupted'

export interface TrackedGeneration {
  id: string
  module: ModuleId
  type: GenerationType
  status: GenerationStatus
  prompt: string
  startedAt: number
  finishedAt: number | null

  // ComfyUI — permet de re-checker /history/{promptId} apres refresh
  comfyPromptId?: string

  // Python scripts — permet de scanner le repertoire pour les fichiers generes
  expectedOutputDir?: string
  expectedOutputPattern?: string // regex pattern pour matcher les fichiers

  // Resultat recupere
  resultPath?: string
  resultFilename?: string
  resultSubfolder?: string

  // Erreur
  error?: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_ENTRIES = 20
const MAX_AGE_MS = 24 * 60 * 60 * 1000 // 24h

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface GenerationTrackerState {
  generations: TrackedGeneration[]

  /** Demarre le tracking d'une generation. Retourne l'ID. */
  trackGeneration: (entry: Omit<TrackedGeneration, 'id' | 'status' | 'finishedAt'>) => string

  /** Marque une generation comme terminee avec succes. */
  completeGeneration: (id: string, result?: { resultPath?: string; resultFilename?: string; resultSubfolder?: string }) => void

  /** Marque une generation comme echouee. */
  failGeneration: (id: string, error: string) => void

  /** Marque une generation comme interrompue (refresh mid-stream). */
  markInterrupted: (id: string) => void

  /** Supprime une entree (dismiss par l'utilisateur). */
  dismissGeneration: (id: string) => void

  /** Retourne les generations pending/interrupted pour un module donne. */
  getPendingGenerations: (module?: ModuleId) => TrackedGeneration[]

  /** Nettoie les entrees trop vieilles ou trop nombreuses. */
  prune: () => void
}

function generateId(module: ModuleId): string {
  return `gen-${module}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function pruneEntries(entries: TrackedGeneration[]): TrackedGeneration[] {
  const now = Date.now()
  return entries
    .filter(e => now - e.startedAt < MAX_AGE_MS)
    .slice(0, MAX_ENTRIES)
}

export const useGenerationTrackerStore = create<GenerationTrackerState>()(
  persist(
    (set, get) => ({
      generations: [],

      trackGeneration: (entry) => {
        const id = generateId(entry.module)
        const tracked: TrackedGeneration = {
          ...entry,
          id,
          status: 'pending',
          finishedAt: null,
        }

        set(state => ({
          generations: pruneEntries([tracked, ...state.generations]),
        }))

        return id
      },

      completeGeneration: (id, result) => {
        const prev = get().generations.find(g => g.id === id)
        set(state => ({
          generations: state.generations.map(g =>
            g.id === id
              ? { ...g, status: 'completed' as const, finishedAt: Date.now(), ...result }
              : g
          ),
        }))
        if (prev && prev.status !== 'completed') {
          // Annonce vocale non bloquante (no-op si muted ou announceOnComplete=false).
          // Le filename est nettoyé pour la TTS (hash → …, extension retirée).
          const summary = result?.resultFilename ? cleanFilenameForTTS(result.resultFilename) : undefined
          try { auroraVoice.announce({ module: prev.module, kind: 'completed', summary }) } catch { /* ignore */ }
        }
      },

      failGeneration: (id, error) => {
        const prev = get().generations.find(g => g.id === id)
        set(state => ({
          generations: state.generations.map(g =>
            g.id === id
              ? { ...g, status: 'failed' as const, finishedAt: Date.now(), error }
              : g
          ),
        }))
        if (prev && prev.status !== 'failed') {
          // Tronque l'erreur pour ne pas saturer l'utterance.
          const summary = error ? error.slice(0, 80) : undefined
          try { auroraVoice.announce({ module: prev.module, kind: 'failed', summary }) } catch { /* ignore */ }
        }
      },

      markInterrupted: (id) => {
        set(state => ({
          generations: state.generations.map(g =>
            g.id === id
              ? { ...g, status: 'interrupted' as const, finishedAt: Date.now() }
              : g
          ),
        }))
      },

      dismissGeneration: (id) => {
        set(state => ({
          generations: state.generations.filter(g => g.id !== id),
        }))
      },

      getPendingGenerations: (module?) => {
        const all = get().generations
        const pending = all.filter(g =>
          (g.status === 'pending' || g.status === 'interrupted')
          && (!module || g.module === module)
        )
        return pending
      },

      prune: () => {
        set(state => ({ generations: pruneEntries(state.generations) }))
      },
    }),
    {
      name: 'aurora-generation-tracker',
      version: 1,
      // Ne PAS marquer les pending comme cancelled (contrairement a appStore) —
      // c'est tout l'interet : on veut retrouver les generations en cours au retour
    },
  ),
)
