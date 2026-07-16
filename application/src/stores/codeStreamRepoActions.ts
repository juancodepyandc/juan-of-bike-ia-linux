import type { StoreApi } from 'zustand'
import type { CodeFile } from '../services/codeOrchestrator'
import { getBridgeUrl } from '../utils/runtime'
import type { CodeStreamStore } from './codeStreamTypes.ts'

type SetStore = StoreApi<CodeStreamStore>['setState']
type GetStore = StoreApi<CodeStreamStore>['getState']
type RepoActionNames = 'pickRepo' | 'scanRepo' | 'writeRepo' | 'installRepoDeps'

export function createCodeStreamRepoActions(
  set: SetStore,
  get: GetStore,
): Pick<CodeStreamStore, RepoActionNames> {
  return {
    async pickRepo() {
      set({ repoBusy: true, repoMessage: 'Sélection du dossier…' })
      try {
        const response = await fetch(`${getBridgeUrl()}/api/code/repo/pick`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
          signal: AbortSignal.timeout(120_000),
        })
        const result = await response.json() as { ok?: boolean; path?: string; error?: string }
        if (result.ok && result.path) {
          set({ repoPath: result.path })
          await get().scanRepo(result.path)
        } else {
          set({ repoBusy: false, repoMessage: result.error || 'Aucun dossier sélectionné.' })
        }
      } catch (error) {
        set({ repoBusy: false, repoMessage: `Sélecteur indisponible : ${messageOf(error)}. Colle le chemin manuellement.` })
      }
    },
    async scanRepo(path) {
      const target = (path ?? get().repoPath ?? '').trim()
      if (!target) {
        set({ repoMessage: 'Chemin du repo vide.' })
        return
      }
      set({ repoBusy: true, repoMessage: 'Lecture du dépôt en cours…' })
      try {
        const response = await fetch(`${getBridgeUrl()}/api/code/repo/scan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: target, max_files: 120, max_bytes: 1_400_000 }),
          signal: AbortSignal.timeout(60_000),
        })
        const result = await response.json() as {
          ok?: boolean
          error?: string
          path?: string
          label?: string
          branch?: string | null
          truncated?: boolean
          total_files?: number
          total_bytes?: number
          files?: Array<{ path: string; content: string; language?: string }>
        }
        if (!result.ok || !Array.isArray(result.files)) {
          set({ repoBusy: false, repoLoaded: false, repoMessage: result.error || 'Lecture du dépôt échouée.' })
          return
        }
        const files: CodeFile[] = result.files.map((file) => ({
          name: file.path,
          language: file.language || 'text',
          content: file.content,
        }))
        set({
          repoPath: result.path || target,
          repoLabel: result.label || target.split(/[\\/]/).filter(Boolean).pop() || target,
          repoLoaded: true,
          repoBusy: false,
          repoScan: {
            files: result.total_files ?? files.length,
            bytes: result.total_bytes ?? 0,
            branch: result.branch ?? null,
            truncated: Boolean(result.truncated),
          },
          repoMessage: `${files.length} fichier(s) chargé(s) comme contexte${result.branch ? ` · branche ${result.branch}` : ''}.`,
          files,
          messages: [],
          followUpKind: null,
          streamOutput: '',
          notes: '',
        })
      } catch (error) {
        set({ repoBusy: false, repoLoaded: false, repoMessage: `Lecture échouée : ${messageOf(error)}` })
      }
    },
    async writeRepo() {
      const path = (get().repoPath ?? '').trim()
      const files = get().files
      if (!path) {
        set({ repoMessage: 'Aucun repo sélectionné.' })
        return
      }
      if (files.length === 0) {
        set({ repoMessage: 'Aucun fichier à écrire.' })
        return
      }
      set({ repoBusy: true, repoMessage: 'Écriture des changements dans le dépôt…' })
      try {
        const response = await fetch(`${getBridgeUrl()}/api/code/repo/write`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, files: files.map((file) => ({ path: file.name, content: file.content })), backup: true }),
          signal: AbortSignal.timeout(30_000),
        })
        const result = await response.json() as { ok?: boolean; written?: string[]; error?: string }
        if (result.ok) {
          set({
            repoBusy: false,
            repoWriteResult: { written: result.written ?? [], path, ts: Date.now() },
            repoMessage: `${(result.written ?? []).length} fichier(s) écrit(s) dans ${path}.`,
          })
        } else {
          set({ repoBusy: false, repoMessage: result.error || 'Écriture échouée.' })
        }
      } catch (error) {
        set({ repoBusy: false, repoMessage: `Écriture échouée : ${messageOf(error)}` })
      }
    },
    async installRepoDeps() {
      const path = (get().repoPath ?? '').trim()
      if (!path) {
        set({ repoMessage: 'Aucun repo sélectionné.' })
        return
      }
      set({ repoBusy: true, repoMessage: 'Détection + installation des dépendances…' })
      try {
        const response = await fetch(`${getBridgeUrl()}/api/code/repo/install`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path }),
          signal: AbortSignal.timeout(15_000),
        })
        const result = await response.json() as { ok?: boolean; command?: string; error?: string }
        set({
          repoBusy: false,
          repoMessage: result.ok
            ? `Installation lancée : ${result.command} (suis la progression dans la console qui s'est ouverte).`
            : result.error || 'Installation échouée.',
        })
      } catch (error) {
        set({ repoBusy: false, repoMessage: `Installation échouée : ${messageOf(error)}` })
      }
    },
  }
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
