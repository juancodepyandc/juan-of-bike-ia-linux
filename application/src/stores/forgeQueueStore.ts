import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  emit as emitNotif,
  notifyError,
  notifyFinished,
  notifyQueueEnqueued,
  notifyQueueStarted,
  notifyStarted,
} from '../utils/notificationBus.ts'
import type { AvatarEntry } from '../types/app.ts'
import { runForgePipeline, type ForgeResult, type ForgeResume, type ForgeStepId } from '../services/characterForge.ts'
import { useAppStore } from './appStore.ts'
import { acquireProject } from '../utils/projectAdmission.ts'

export type QueueStatus = 'queued' | 'running' | 'done' | 'error'

export interface QueueJob {
  id: string
  requestId?: string
  prompt: string
  model: string
  status: QueueStatus
  stepDetail?: string
  progressPct?: number
  startedAt?: number
  endedAt?: number
  error?: string
  /** Set once the pipeline produced a ForgeResult; UI can click to save. */
  result?: ForgeResult
  /** True if the user already saved it into the gallery */
  saved?: boolean
  /** Growing set of intermediate artifacts — persisted after each step so a
   * page reload can pick up where the pipeline left off instead of starting
   * from scratch. */
  artifacts?: ForgeResume
}

interface ForgeQueueState {
  jobs: QueueJob[]
  enqueue: (prompt: string) => string
  cancel: (id: string) => void
  remove: (id: string) => void
  saveJob: (id: string, entry: AvatarEntry) => void
  _tick: () => Promise<void>
}

const isRunning = (jobs: QueueJob[]) => jobs.some((j) => j.status === 'running')
const nextQueued = (jobs: QueueJob[]) => jobs.find((j) => j.status === 'queued')

export const useForgeQueueStore = create<ForgeQueueState>()(
  persist(
    (set, get) => ({
      jobs: [],
      enqueue: (prompt: string) => {
        const id = `forge-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
        const model = useAppStore.getState().mainModel
        const job: QueueJob = {
          id, requestId: crypto.randomUUID(), prompt, model, status: 'queued',
        }
        set((s) => ({ jobs: [...s.jobs, job] }))
        const position = get().jobs.filter((j) => j.status !== 'done' && j.status !== 'error').length
        if (isRunning(get().jobs) || position > 1) {
          notifyQueueEnqueued(`Forge "${prompt.slice(0, 28)}"`, position)
        }
        void get()._tick()
        return id
      },
      cancel: (id) => set((s) => ({
        jobs: s.jobs.map((j) => (j.id === id && j.status === 'queued' ? { ...j, status: 'error', error: 'Annulé' } : j)),
      })),
      remove: (id) => set((s) => ({ jobs: s.jobs.filter((j) => j.id !== id) })),
      saveJob: (id, entry) => {
        set((s) => ({ jobs: s.jobs.map((j) => (j.id === id ? { ...j, saved: true } : j)) }))
        useAppStore.getState().addAvatar(entry)
        useAppStore.getState().setSelectedAvatar(entry.id)
      },
      _tick: async () => {
        const { jobs } = get()
        if (isRunning(jobs)) return
        const job = nextQueued(jobs)
        if (!job) return
        const requestId = job.requestId || crypto.randomUUID()
        // Reserve locally before awaiting admission, so another tick cannot start a copy.
        set((s) => ({
          jobs: s.jobs.map((j) =>
            j.id === job.id ? { ...j, requestId, status: 'running', stepDetail: 'En attente sur le PC' } : j,
          ),
        }))
        let finish: Awaited<ReturnType<typeof acquireProject>> | undefined
        let outcome: 'completed' | 'failed' = 'failed'
        try {
          finish = await acquireProject({ request_id: requestId, module: 'image', title: `Forge : ${job.prompt}`.slice(0, 500), model: job.model }, (detail) => {
            set((s) => ({ jobs: s.jobs.map((j) => j.id === job.id ? { ...j, stepDetail: detail } : j) }))
          })
          set((s) => ({ jobs: s.jobs.map((j) => j.id === job.id ? { ...j, startedAt: Date.now() } : j) }))
          notifyStarted('forge', `Forge "${job.prompt.slice(0, 28)}"`, job.id)
          if (jobs.some((j) => j.status === 'done')) notifyQueueStarted(`Forge "${job.prompt.slice(0, 28)}"`)
          const result = await runForgePipeline(job.prompt, job.model, {
            onStep: (stepId: ForgeStepId, patch) => {
              if (patch.detail) {
                set((s) => ({
                  jobs: s.jobs.map((j) =>
                    j.id === job.id ? { ...j, stepDetail: `${stepId}: ${patch.detail}` } : j,
                  ),
                }))
              }
            },
            onStatus: (msg, pct) => {
              if (typeof pct === 'number') {
                set((s) => ({
                  jobs: s.jobs.map((j) =>
                    j.id === job.id ? { ...j, progressPct: pct, stepDetail: msg } : j,
                  ),
                }))
              }
            },
            // Hand every major artifact back to the store so a reload can resume
            resume: job.artifacts,
            onArtifact: (partial) => {
              set((s) => ({
                jobs: s.jobs.map((j) =>
                  j.id === job.id
                    ? { ...j, artifacts: { ...(j.artifacts || {}), ...partial } }
                    : j,
                ),
              }))
            },
          })
          set((s) => ({
            jobs: s.jobs.map((j) =>
              j.id === job.id ? {
                ...j, status: 'done', endedAt: Date.now(),
                progressPct: 100, stepDetail: 'Prêt à enregistrer',
                result,
              } : j,
            ),
          }))
          outcome = 'completed'
          notifyFinished('forge', `Forge "${job.prompt.slice(0, 28)}"`, job.id)
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err)
          set((s) => ({
            jobs: s.jobs.map((j) =>
              j.id === job.id ? { ...j, status: 'error', endedAt: Date.now(), error: msg } : j,
            ),
          }))
          notifyError('forge', `Forge "${job.prompt.slice(0, 28)}"`, msg, job.id)
        } finally {
          if (finish) await finish(outcome)
          // Small delay so the UI can paint the final state before the next job starts
          await new Promise((r) => setTimeout(r, 400))
          // Chain the next queued job
          void get()._tick()
        }
      },
    }),
    {
      name: 'forge-queue-v2',
      // Keep results and the true execution state. A refresh must never
      // transform an unknown in-flight operation into a fresh generation.
      partialize: (state) => ({ jobs: state.jobs }),
    },
  ),
)

/** Restore saved outputs; an unknown interrupted execution requires inspection,
 * never an automatic replay of expensive model/tool operations. */
export function attachForgeQueueBootstrap() {
  const state = useForgeQueueStore.getState()
  const interrupted = state.jobs.filter((j) => j.status === 'running' || (j.status === 'queued' && j.startedAt))
  if (interrupted.length) {
    useForgeQueueStore.setState({ jobs: state.jobs.map((j) => interrupted.some((old) => old.id === j.id)
      ? { ...j, status: 'error' as QueueStatus, error: 'Connexion interrompue pendant ce projet. Résultats et étapes conservés ; vérifier le travail sur le PC avant reprise.' } : j) })
    emitNotif({ kind: 'info', title: 'Forge : travail à vérifier', body: 'Les étapes enregistrées sont conservées, sans relancer une génération dont le résultat est inconnu.', tone: 'info', seal: '↻' })
  }
  const unsaved = state.jobs.filter((j) => j.status === 'done' && !j.saved)
  if (unsaved.length > 0) {
    emitNotif({
      kind: 'info',
      title: `${unsaved.length} forge${unsaved.length > 1 ? 's' : ''} à enregistrer`,
      body: 'Ouvre la Galerie',
      tone: 'info', seal: '›',
    })
  }
  // Only jobs that never started may enter admission automatically.
  void useForgeQueueStore.getState()._tick()
}
