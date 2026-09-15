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

export type QueueStatus = 'queued' | 'running' | 'done' | 'error'

export interface QueueJob {
  id: string
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
          id, prompt, model, status: 'queued',
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
        // Move to running
        set((s) => ({
          jobs: s.jobs.map((j) =>
            j.id === job.id ? { ...j, status: 'running', startedAt: Date.now() } : j,
          ),
        }))
        notifyStarted('forge', `Forge "${job.prompt.slice(0, 28)}"`, job.id)
        // If this is the 2nd+ job (one just finished), announce start
        if (jobs.filter((j) => j.status === 'done').length > 0) {
          notifyQueueStarted(`Forge "${job.prompt.slice(0, 28)}"`)
        }
        try {
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
          // Small delay so the UI can paint the final state before the next job starts
          await new Promise((r) => setTimeout(r, 400))
          // Chain the next queued job
          void get()._tick()
        }
      },
    }),
    {
      name: 'forge-queue-v2',
      // Persist EVERY intermediate artifact (meta/traits/rig/portraitUrl/
      // layers/baseLayer…). The final `result` is rebuilt from them when the
      // pipeline resumes after a reload, so we don't need to store it.
      partialize: (state) => ({
        jobs: state.jobs.map((j) => ({
          ...j,
          result: undefined,
          // running jobs become queued on reload (bootstrap handles it)
          status: j.status === 'running' ? 'queued' as QueueStatus : j.status,
        })),
      }),
    },
  ),
)

/** Bootstrap called at app start (after persist rehydrate):
 *   - any job stuck in 'running' across a reload is reverted to 'queued'
 *     and restarted so the user's work resumes automatically.
 *   - surfaces a notif for pending "done but not saved" jobs.
 */
export function attachForgeQueueBootstrap() {
  const state = useForgeQueueStore.getState()
  const runningBefore = state.jobs.filter((j) => j.status === 'running')
  const resurrected = state.jobs.map((j) =>
    j.status === 'running' ? { ...j, status: 'queued' as QueueStatus } : j,
  )
  if (runningBefore.length > 0) {
    useForgeQueueStore.setState({ jobs: resurrected })
    // Tell the user what is actually happening so they understand nothing
    // was lost — and specify how much of the pipeline is already persisted.
    for (const j of runningBefore) {
      const steps: string[] = []
      if (j.artifacts?.meta)        steps.push('intent')
      if (j.artifacts?.traits)      steps.push('traits')
      if (j.artifacts?.rig)         steps.push('rig')
      if (j.artifacts?.portraitUrl) steps.push('portrait')
      if (j.artifacts?.features !== undefined) steps.push('features')
      if (j.artifacts?.layerFiles?.length) steps.push('layers')
      const skipping = steps.length > 0
        ? `Déjà fait : ${steps.join(', ')}`
        : 'Rien de déjà fait, on reprend du début'
      emitNotif({
        kind: 'queue.started',
        title: `Reprise : ${j.prompt.slice(0, 28)}`,
        body: skipping,
        tone: 'info', seal: '↻',
      })
    }
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
  // Kick the tick to drain any queued jobs (including the resurrected ones)
  void useForgeQueueStore.getState()._tick()
}
