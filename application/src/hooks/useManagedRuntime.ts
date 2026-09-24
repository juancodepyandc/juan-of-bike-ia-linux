import { useCallback } from 'react'
import { useAppStore } from '../stores/appStore.ts'
import { useModuleLogStore } from '../stores/moduleLogStore.ts'
import type { ModuleId, RuntimeServiceId } from '../types/app.ts'
import {
  runtimeEnsureService,
  runtimeInspectServices,
  runtimePrepareOllamaModel,
  runtimeReleaseService,
} from './useTauri.ts'
import { getErrorMessage } from '../utils/errors.ts'
import {
  AUXILIARY_ANALYSIS_MODEL,
  DEFAULT_MAIN_MODEL,
  resolveConfiguredModel,
  selectAdaptiveReasoningModel,
  shouldAvoidHeavyReasoningModel,
} from '../config/models.ts'

let runtimeExecutionQueue: Promise<void> = Promise.resolve()
type ManagedRuntimePhase = 'prepare' | 'generate' | 'cleanup' | 'done' | 'error'
const RECOVERABLE_RUNTIME_ERROR_PATTERNS = [
  /event\.listen not allowed/i,
  /connection/i,
  /refused/i,
  /timeout/i,
  /temporarily unavailable/i,
  /temporarily unreachable/i,
  /service unavailable/i,
  /returned 50\d/i,
  /ollama .*ne repond/i,
  /comfyui .*ne repond/i,
  /a quitte pendant le demarrage/i,
]

function createGenerationJobId(module: ModuleId) {
  // crypto.randomUUID() is available in all modern browsers and Node 14.17+.
  // Falls back to the old pattern only if the API is somehow absent.
  const uid = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  return `job-${module}-${uid}`
}

function isRecoverableRuntimeError(error: unknown) {
  if (error instanceof Error && error.name === 'AbortError') {
    return false
  }

  const message = getErrorMessage(error, '')
  return RECOVERABLE_RUNTIME_ERROR_PATTERNS.some((pattern) => pattern.test(message))
}

type ManagedRuntimeJob<T> = {
  module: ModuleId
  title: string
  services: RuntimeServiceId[]
  ollamaModel?: string
  // Quand true, les services ne sont pas liberes apres le job (utile pour la conversation
  // afin d'eviter de dechager le modele LLM entre chaque tour).
  skipRelease?: boolean
  prepare?: (helpers: { setPhase: (detail: string, progress: number) => void }) => Promise<void>
  job: (helpers: { setPhase: (detail: string, progress: number) => void }) => Promise<T>
}

export function useManagedRuntime() {
  const {
    addGenerationJob,
    mergeRuntimeService,
    pruneGenerationJobs,
    setGenerationJob,
    setRuntimeServices,
    setRuntimeTask,
    setServices,
  } = useAppStore()

  const { log: moduleLog } = useModuleLogStore()

  const syncRuntime = useCallback(async () => {
    const services = await runtimeInspectServices()
    const mapped = services.reduce((accumulator, service) => {
      accumulator[service.id] = service
      return accumulator
    }, {} as Record<'ollama' | 'comfyui', (typeof services)[number]>)

    setRuntimeServices(mapped)
    setServices({
      ollama: mapped.ollama?.running || false,
      comfyui: mapped.comfyui?.running || false,
    })
  }, [setRuntimeServices, setServices])

  const executeWithRuntime = useCallback(async <T>({
    module,
    title,
    services,
    ollamaModel: rawOllamaModel,
    skipRelease = false,
    prepare,
    job,
  }: ManagedRuntimeJob<T>) => {
    // Auto-correction: intercepte les modeles legacy avant tout appel Rust
    const hardware = useAppStore.getState().hardware
    const adaptiveMainFallback = selectAdaptiveReasoningModel(hardware, DEFAULT_MAIN_MODEL, AUXILIARY_ANALYSIS_MODEL)
    const ollamaModel = rawOllamaModel
      ? resolveConfiguredModel(rawOllamaModel, adaptiveMainFallback)
      : rawOllamaModel
    const forceAggressiveCleanup = services.includes('ollama') && shouldAvoidHeavyReasoningModel(hardware)
    const effectiveSkipRelease = skipRelease && !forceAggressiveCleanup
    const jobId = createGenerationJobId(module)
    addGenerationJob({
      id: jobId,
      module,
      title,
      detail: 'En file d attente du runtime...',
      progress: 0,
      phase: 'idle',
      status: 'queued',
      services,
      model: ollamaModel || null,
      createdAt: Date.now(),
      startedAt: null,
      finishedAt: null,
      error: null,
      history: [],
    })

    const runQueuedJob = async () => {
      const startedAt = Date.now()

      setGenerationJob(jobId, {
        status: 'running',
        phase: 'prepare',
        detail: 'Preparation du runtime local...',
        progress: 4,
        startedAt,
        finishedAt: null,
        error: null,
      })
      setRuntimeTask({
        active: true,
        module,
        title,
        phase: 'prepare',
        detail: 'Preparation du runtime local...',
        progress: 4,
        startedAt,
        finishedAt: null,
        services,
        error: null,
      })

      const setPhase = (
        detail: string,
        progress: number,
        phase: ManagedRuntimePhase = 'prepare',
      ) => {
        setRuntimeTask({ phase, detail, progress })
        setGenerationJob(jobId, { phase, detail, progress })
      }

      try {
        // SINGLE-MODEL: 2 tentatives runtime suffisent — la couche resilience
        // gere deja ses propres retries en interne. 3 × 3 = 9 retries inutiles.
        const MAX_ATTEMPTS = 2
        for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
          try {
            if (attempt > 0) {
              const backoffMs = 2500 // 2.5s — laisse Ollama charger le modele
              moduleLog(module, 'retry', `Tentative ${attempt + 1}/${MAX_ATTEMPTS}`, `Backoff: ${backoffMs}ms`)
              setPhase(`Auto-reparation: attente ${backoffMs / 1000}s avant tentative ${attempt + 1}...`, 22, 'prepare')
              await new Promise((resolve) => setTimeout(resolve, backoffMs))
            }

            for (let index = 0; index < services.length; index += 1) {
              const service = services[index]
              setPhase(`Activation de ${service}...`, 12 + index * 16, 'prepare')

              mergeRuntimeService(service, {
                detail: 'Activation demandee par le module.',
                progress: 18 + index * 12,
              })

              const runtimeInfo = await runtimeEnsureService(service)
              mergeRuntimeService(service, runtimeInfo)
            }

            if (prepare) {
              setPhase('Verification du pack modele du module...', 30, 'prepare')
              await prepare({ setPhase })
            }

            if (ollamaModel) {
              setPhase(`Chargement du modele ${ollamaModel}...`, 34, 'prepare')
              await runtimePrepareOllamaModel(ollamaModel)
            }

            moduleLog(module, 'info', 'Generation lancee', `Modele: ${ollamaModel || 'aucun'}, Services: ${services.join(', ')}`)
            setPhase('Generation en cours.', 42, 'generate')
            const result = await job({ setPhase })

            moduleLog(module, 'info', 'Generation terminee avec succes')

            if (!effectiveSkipRelease) {
              setPhase(
                forceAggressiveCleanup
                  ? 'Nettoyage memoire renforce pour eviter toute surcharge machine...'
                  : 'Liberation des ressources locales...',
                92,
                'cleanup',
              )
              for (const service of services) {
                const runtimeInfo = await runtimeReleaseService(service, ollamaModel)
                mergeRuntimeService(service, runtimeInfo)
              }
              await syncRuntime()
            }

            setGenerationJob(jobId, {
              status: 'done',
              phase: 'done',
              detail: effectiveSkipRelease
                ? 'Session terminee. Runtime maintenu chaud, sans decharge automatique.'
                : 'Session terminee, ressources liberees.',
              progress: 100,
              finishedAt: Date.now(),
              error: null,
            })
            setRuntimeTask({
              phase: 'done',
              detail: effectiveSkipRelease
                ? 'Session terminee. Runtime maintenu chaud, sans decharge automatique.'
                : 'Session terminee, ressources liberees.',
              progress: 100,
              finishedAt: Date.now(),
              error: null,
            })

            return result
          } catch (error) {
            if (!effectiveSkipRelease) {
              for (const service of services) {
                try {
                  const runtimeInfo = await runtimeReleaseService(service, ollamaModel)
                  mergeRuntimeService(service, runtimeInfo)
                } catch {
                  // Ignore cleanup errors after a generation failure.
                }
              }
            }

            await syncRuntime().catch(() => undefined)

            const isAbort = error instanceof Error && error.name === 'AbortError'
            const message = getErrorMessage(error, 'Erreur runtime inconnue.')
            const shouldRetry = !isAbort && attempt < MAX_ATTEMPTS - 1 && isRecoverableRuntimeError(error)

            moduleLog(module, shouldRetry ? 'retry' : 'error', message, `Tentative ${attempt + 1}/${MAX_ATTEMPTS}, Recoverable: ${shouldRetry}`)

            if (shouldRetry) {
              const retryDetail = `Auto-reparation du runtime (tentative ${attempt + 2}/${MAX_ATTEMPTS}): ${message}`
              setRuntimeTask({
                active: true,
                phase: 'prepare',
                detail: retryDetail,
                progress: 28,
                finishedAt: null,
                error: null,
              })
              setGenerationJob(jobId, {
                status: 'running',
                phase: 'prepare',
                detail: `${retryDetail}. Nouvelle tentative en cours...`,
                progress: 28,
                finishedAt: null,
                error: null,
              })
              continue
            }

            setGenerationJob(jobId, {
              status: isAbort ? 'cancelled' : 'error',
              phase: isAbort ? 'done' : 'error',
              detail: isAbort ? 'Generation interrompue.' : message,
              progress: 100,
              finishedAt: Date.now(),
              error: isAbort ? null : message,
            })
            setRuntimeTask({
              active: true,
              phase: isAbort ? 'done' : 'error',
              detail: isAbort ? 'Generation interrompue.' : message,
              progress: 100,
              finishedAt: Date.now(),
              error: isAbort ? null : message,
            })

            throw error
          }
        }

        throw new Error('Le runtime n a pas pu terminer la generation apres 3 tentatives.')
      } finally {
        pruneGenerationJobs()
      }
    }

    const queuedRun = runtimeExecutionQueue.then(runQueuedJob).catch((err: unknown) => {
      // Absorb the error in the queue chain to prevent unhandled rejection,
      // but re-throw so the caller's await still receives the error.
      throw err
    })
    runtimeExecutionQueue = queuedRun.then(() => undefined).catch(() => undefined)
    // Return a NEW promise that mirrors queuedRun — this prevents the same
    // rejection from being "unhandled" on two separate promise branches.
    return new Promise<T>((resolve, reject) => {
      queuedRun.then(resolve as (value: T) => void, reject)
    })
  }, [
    addGenerationJob,
    mergeRuntimeService,
    moduleLog,
    pruneGenerationJobs,
    setGenerationJob,
    setRuntimeServices,
    setRuntimeTask,
    setServices,
    syncRuntime,
  ])

  return {
    executeWithRuntime,
    syncRuntime,
  }
}
