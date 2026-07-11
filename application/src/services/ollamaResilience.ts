import type { OllamaMessage } from '../types/app'
import {
  ollamaChat,
  ollamaChatStream,
  ollamaGenerate,
  ollamaListModels,
  checkServiceStatus,
  inspectHostResources,
  runtimeEnsureOllamaModelAvailable,
  runtimeEnsureService,
  runtimeReleaseService,
} from '../hooks/useTauri'
import {
  CODE_SINGLE_MODEL,
} from '../config/models'
import { useAppStore } from '../stores/appStore'
import { withTimeout } from './llmTimebox'

export type RecoveryEvent = {
  attempt: number
  maxAttempts: number
  action:
    | 'retry'
    | 'restart_service'
    | 'model_fallback'
    | 'health_check'
    | 'exhausted'
    | 'memory_guard'
    | 'release_models'
    | 'auto_install_fallback'
  model: string
  previousModel?: string
  error: string
  timestamp: number
}

export interface ResilienceOptions {
  onRecoveryAttempt?: (event: RecoveryEvent) => void
  signal?: AbortSignal
  timeoutMs?: number
  firstByteTimeoutMs?: number
  /**
   * v85c : when true, NEVER pre-skip this model for memory. The pre-skip
   * only exempts the literal CODE_SINGLE_MODEL constant, but the code
   * pipeline routes to gemma3:12b / qwen3:14b / qwen3-coder depending on the
   * project — those were getting memory_guard-skipped under transient RAM
   * pressure, producing ZERO files. The pipeline'd rather LET the model try
   * (and degrade num_ctx on a real OOM) than refuse to run at all — exactly
   * the intent already documented in shouldSkipModelForMemory.
   */
  neverMemorySkip?: boolean
}

type ModelCatalogEntry = {
  name: string
  sizeGiB: number
  family: string
}

type MemoryErrorSignal = {
  requiredGiB: number
  availableGiB: number
}

// SINGLE-MODEL: Backoff reduit — on ne change plus de modele, donc inutile de
// boucler 6 fois avec 25s de delay. 3 tentatives rapides suffisent.
// Si le modele echoue 3 fois, c'est un vrai probleme (OOM, service down).
const BACKOFF_DELAYS_MS = [800, 2_000, 4_000] as const
const MAX_ATTEMPTS = BACKOFF_DELAYS_MS.length
const MODEL_MEMORY_FLOORS_GIB = new Map<string, number>()

function normalizeModelName(model: string) {
  return model.trim().replace(/:latest$/i, '')
}

function emitRecovery(
  opts: ResilienceOptions | undefined,
  partial: Omit<RecoveryEvent, 'timestamp'>,
) {
  opts?.onRecoveryAttempt?.({ ...partial, timestamp: Date.now() })
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return String(err)
}

/**
 * Erreurs fatales qui ne se resolvent PAS en re-essayant.
 * Retry = perte de temps pure sur ces patterns.
 */
function isFatalNonRetryableError(errMsg: string): boolean {
  return /model .* not found/i.test(errMsg)
    || /invalid model/i.test(errMsg)
    || /pull model manifest/i.test(errMsg)
    || /unauthorized/i.test(errMsg)
    || /permission denied/i.test(errMsg)
    || /ECONNREFUSED.*11434/i.test(errMsg)
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }

    const timer = setTimeout(resolve, ms)

    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
}

function parseOllamaMemoryError(message: string): MemoryErrorSignal | null {
  const match = message.match(/requires more system memory \(([\d.]+)\s*GiB\) than is available \(([\d.]+)\s*GiB\)/i)
  if (!match) {
    return null
  }

  const requiredGiB = Number(match[1])
  const availableGiB = Number(match[2])
  if (!Number.isFinite(requiredGiB) || !Number.isFinite(availableGiB)) {
    return null
  }

  return { requiredGiB, availableGiB }
}

function buildCatalog(raw: unknown): Map<string, ModelCatalogEntry> {
  const entries = new Map<string, ModelCatalogEntry>()
  const models = Array.isArray((raw as { models?: unknown[] } | null | undefined)?.models)
    ? ((raw as { models: Array<Record<string, unknown>> }).models)
    : []

  for (const item of models) {
    const name = typeof item?.name === 'string' ? item.name : ''
    if (!name) continue

    const size = typeof item?.size === 'number' ? item.size : 0
    const sizeGiB = size > 0 ? size / 1024 / 1024 / 1024 : 0
    const details = typeof item?.details === 'object' && item.details
      ? item.details as Record<string, unknown>
      : {}
    const family = typeof details.family === 'string' ? details.family : ''

    entries.set(normalizeModelName(name), {
      name,
      sizeGiB,
      family: family.toLowerCase(),
    })
  }

  return entries
}

function isVisionFamily(entry: ModelCatalogEntry | undefined) {
  if (!entry) return false
  return entry.family.includes('vl') || entry.name.toLowerCase().includes('-vl:')
}

function estimateModelNeedGiB(model: string, catalog: Map<string, ModelCatalogEntry>) {
  const normalized = normalizeModelName(model)
  const learnedFloor = MODEL_MEMORY_FLOORS_GIB.get(normalized)
  if (learnedFloor && Number.isFinite(learnedFloor)) {
    return learnedFloor
  }

  const entry = catalog.get(normalized)
  if (!entry?.sizeGiB) {
    return null
  }

  if (entry.sizeGiB >= 24) return entry.sizeGiB * 1.55
  if (entry.sizeGiB >= 16) return entry.sizeGiB * 1.85
  if (entry.sizeGiB >= 10) return entry.sizeGiB * 1.45
  return entry.sizeGiB * 1.2
}

async function fetchModelCatalog() {
  try {
    return buildCatalog(await ollamaListModels())
  } catch {
    return new Map<string, ModelCatalogEntry>()
  }
}

async function fetchHostMemorySnapshot() {
  try {
    return await inspectHostResources()
  } catch {
    const hardware = useAppStore.getState().hardware
    const fallbackRam = Number(hardware?.ram_gb ?? 0)
    return {
      total_ram_gb: fallbackRam,
      free_ram_gb: fallbackRam,
      memory_pressure: 'medium' as const,
    }
  }
}

/**
 * SINGLE-MODEL: La fallback list ne contient QUE le modele demande.
 * On ne swap JAMAIS vers un autre modele — c'est la source des
 * crashes (charger llama4:scout 67GB alors qu'on a 16GB VRAM).
 * Si le modele unique echoue, on retry avec LUI, pas avec un autre.
 */
function buildFallbackList(primaryModel: string, _catalog: Map<string, ModelCatalogEntry>): string[] {
  return [primaryModel]
}

function computeSafeMemoryBudget(snapshot: Awaited<ReturnType<typeof fetchHostMemorySnapshot>>) {
  const freeRamGiB = Number(snapshot.free_ram_gb)
  if (!Number.isFinite(freeRamGiB) || freeRamGiB <= 0) {
    return 0
  }

  const pressure = snapshot.memory_pressure
  const pressureFactor = pressure === 'high' ? 0.72 : pressure === 'medium' ? 0.82 : 0.9
  const reserveGiB = pressure === 'high' ? 4 : pressure === 'medium' ? 3 : 2
  return Math.max(0, freeRamGiB * pressureFactor - reserveGiB)
}

function shouldSkipModelForMemory(
  model: string,
  snapshot: Awaited<ReturnType<typeof fetchHostMemorySnapshot>>,
  catalog: Map<string, ModelCatalogEntry>,
) {
  // JAMAIS bloquer le CODE_SINGLE_MODEL — c est le seul modele du pipeline code.
  // Si la memoire est insuffisante, on le laisse essayer avec un num_ctx reduit.
  // Bloquer = pipeline mort. Essayer = chance de reussir.
  if (normalizeModelName(model) === normalizeModelName(CODE_SINGLE_MODEL)) return false

  const estimatedNeed = estimateModelNeedGiB(model, catalog)
  if (!estimatedNeed) return false

  // RAM check (existing)
  const safeBudgetGiB = computeSafeMemoryBudget(snapshot)
  if (safeBudgetGiB > 0 && estimatedNeed > safeBudgetGiB) return true

  // VRAM check — plus tolerant pour permettre l offload CPU partiel
  // Un 32B Q4 fait ~18-20 GiB, avec 16GB VRAM c est normal de deborder en RAM
  const vramGb = Number(useAppStore.getState().hardware?.vram_gb ?? 0)
  if (vramGb > 0 && estimatedNeed > vramGb * 2.0) return true

  return false
}

async function waitForMemoryRecovery(
  minimumBudgetGiB: number,
  signal?: AbortSignal,
) {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    const snapshot = await fetchHostMemorySnapshot()
    if (computeSafeMemoryBudget(snapshot) >= minimumBudgetGiB) {
      return
    }
    await sleep(1_500, signal)
  }
}

async function aggressivelyReleaseOllama(
  model: string,
  opts: ResilienceOptions | undefined,
  attempt: number,
  errMsg: string,
) {
  emitRecovery(opts, {
    attempt,
    maxAttempts: MAX_ATTEMPTS,
    action: 'release_models',
    model,
    error: errMsg,
  })

  try {
    await runtimeReleaseService('ollama', model)
  } catch {
    // Ignore cleanup failure, a restart path can still recover.
  }

  await sleep(1_500, opts?.signal)
}

async function ensureCompactFallbackInstalled(
  models: string[],
  catalog: Map<string, ModelCatalogEntry>,
  opts: ResilienceOptions | undefined,
  attempt: number,
  errMsg: string,
) {
  // SINGLE-MODEL: Le seul fallback est le modele unique 32B
  for (const candidate of [CODE_SINGLE_MODEL]) {
    const normalized = normalizeModelName(candidate)
    if (catalog.has(normalized) || models.some((entry) => normalizeModelName(entry) === normalized)) {
      return candidate
    }

    emitRecovery(opts, {
      attempt,
      maxAttempts: MAX_ATTEMPTS,
      action: 'auto_install_fallback',
      model: candidate,
      error: errMsg,
    })

    try {
      await runtimeEnsureService('ollama')
      await runtimeEnsureOllamaModelAvailable(candidate)
      return candidate
    } catch {
      // Try the next compact candidate.
    }
  }

  return null
}

export async function isOllamaAlive(): Promise<boolean> {
  try {
    const status = await checkServiceStatus()
    return status.ollama
  } catch {
    return false
  }
}

export async function restartOllamaService(): Promise<void> {
  try {
    await runtimeReleaseService('ollama')
  } catch {
    // Service may already be down.
  }

  await runtimeEnsureService('ollama')

  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    if (await isOllamaAlive()) return
    await sleep(500)
  }

  throw new Error('Ollama n a pas redemarre dans le delai imparti (10 s)')
}

async function withResilience<T>(
  primaryModel: string,
  opts: ResilienceOptions | undefined,
  execute: (model: string) => Promise<T>,
): Promise<T> {
  let catalog = await fetchModelCatalog()
  const models = buildFallbackList(primaryModel, catalog)
  const testedModels: string[] = []
  const skippedModels: string[] = []
  let currentModelIndex = 0
  let executionAttempt = 0
  let lastError: unknown

  while (executionAttempt < MAX_ATTEMPTS) {
    if (opts?.signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }

    if (currentModelIndex >= models.length) {
      const installedCompact = await ensureCompactFallbackInstalled(
        models,
        catalog,
        opts,
        Math.max(executionAttempt, 1),
        errorMessage(lastError || 'Fallback compact requis'),
      )
      if (!installedCompact) {
        break
      }
      models.push(installedCompact)
      catalog = await fetchModelCatalog()
      continue
    }

    const model = models[currentModelIndex]
    const memorySnapshot = await fetchHostMemorySnapshot()
    if (!opts?.neverMemorySkip && shouldSkipModelForMemory(model, memorySnapshot, catalog)) {
      skippedModels.push(model)
      const estimatedNeed = estimateModelNeedGiB(model, catalog)
      const safeBudgetGiB = computeSafeMemoryBudget(memorySnapshot)
      emitRecovery(opts, {
        attempt: Math.max(executionAttempt, 1),
        maxAttempts: MAX_ATTEMPTS,
        action: 'memory_guard',
        model,
        error: estimatedNeed
          ? `Modele ecarte avant execution: besoin estime ${estimatedNeed.toFixed(1)} GiB pour un budget memoire securise de ${safeBudgetGiB.toFixed(1)} GiB`
          : `Modele ecarte avant execution: budget memoire securise insuffisant (${safeBudgetGiB.toFixed(1)} GiB)`,
      })
      currentModelIndex += 1
      continue
    }

    try {
      testedModels.push(model)
      const execution = execute(model)
      return opts?.timeoutMs
        ? await withTimeout(execution, {
            label: `Ollama ${model}`,
            timeoutMs: opts.timeoutMs,
          })
        : await execution
    } catch (err) {
      lastError = err

      if (err instanceof DOMException && err.name === 'AbortError') {
        throw err
      }

      executionAttempt += 1
      const errMsg = errorMessage(err)

      // EARLY EXIT: erreurs fatales qui ne se resolvent pas en re-essayant
      if (isFatalNonRetryableError(errMsg)) {
        emitRecovery(opts, {
          attempt: executionAttempt,
          maxAttempts: MAX_ATTEMPTS,
          action: 'exhausted',
          model,
          error: `Erreur fatale (pas de retry): ${errMsg}`,
        })
        throw new Error(`Ollama: erreur fatale — ${errMsg}`)
      }

      const memoryError = parseOllamaMemoryError(errMsg)

      if (memoryError) {
        MODEL_MEMORY_FLOORS_GIB.set(
          normalizeModelName(model),
          Math.max(memoryError.requiredGiB, memoryError.availableGiB + 1),
        )

        emitRecovery(opts, {
          attempt: executionAttempt,
          maxAttempts: MAX_ATTEMPTS,
          action: 'memory_guard',
          model,
          error: `RAM insuffisante pour ${model}: ${memoryError.requiredGiB.toFixed(1)} GiB requis pour ${memoryError.availableGiB.toFixed(1)} GiB libres`,
        })

        await aggressivelyReleaseOllama(model, opts, executionAttempt, errMsg)
        await waitForMemoryRecovery(Math.max(4, memoryError.availableGiB * 0.65), opts?.signal)

        if (currentModelIndex >= models.length - 1) {
          const installedCompact = await ensureCompactFallbackInstalled(
            models,
            catalog,
            opts,
            executionAttempt,
            errMsg,
          )
          if (installedCompact) {
            models.push(installedCompact)
            catalog = await fetchModelCatalog()
          }
        }

        const previousModel = model
        if (currentModelIndex < models.length - 1) {
          currentModelIndex += 1
          emitRecovery(opts, {
            attempt: executionAttempt,
            maxAttempts: MAX_ATTEMPTS,
            action: 'model_fallback',
            model: models[currentModelIndex],
            previousModel,
            error: errMsg,
          })
        }

        emitRecovery(opts, {
          attempt: executionAttempt,
          maxAttempts: MAX_ATTEMPTS,
          action: 'retry',
          model: models[Math.min(currentModelIndex, models.length - 1)] || model,
          error: errMsg,
        })

        await sleep(BACKOFF_DELAYS_MS[Math.min(executionAttempt - 1, BACKOFF_DELAYS_MS.length - 1)], opts?.signal)
        continue
      }

      emitRecovery(opts, {
        attempt: executionAttempt,
        maxAttempts: MAX_ATTEMPTS,
        action: 'health_check',
        model,
        error: errMsg,
      })

      const alive = await isOllamaAlive()
      if (!alive) {
        emitRecovery(opts, {
          attempt: executionAttempt,
          maxAttempts: MAX_ATTEMPTS,
          action: 'restart_service',
          model,
          error: errMsg,
        })

        try {
          await restartOllamaService()
        } catch (restartErr) {
          emitRecovery(opts, {
            attempt: executionAttempt,
            maxAttempts: MAX_ATTEMPTS,
            action: 'restart_service',
            model,
            error: `Restart echoue: ${errorMessage(restartErr)}`,
          })
        }
      } else {
        await aggressivelyReleaseOllama(model, opts, executionAttempt, errMsg)
        await waitForMemoryRecovery(4, opts?.signal)
      }

      if (currentModelIndex >= models.length - 1) {
        const installedCompact = await ensureCompactFallbackInstalled(
          models,
          catalog,
          opts,
          executionAttempt,
          errMsg,
        )
        if (installedCompact) {
          models.push(installedCompact)
          catalog = await fetchModelCatalog()
        }
      }

      const previousModel = model
      if (currentModelIndex < models.length - 1) {
        currentModelIndex += 1
        emitRecovery(opts, {
          attempt: executionAttempt,
          maxAttempts: MAX_ATTEMPTS,
          action: 'model_fallback',
          model: models[currentModelIndex],
          previousModel,
          error: errMsg,
        })
      }

      emitRecovery(opts, {
        attempt: executionAttempt,
        maxAttempts: MAX_ATTEMPTS,
        action: 'retry',
        model: models[Math.min(currentModelIndex, models.length - 1)] || model,
        error: errMsg,
      })

      await sleep(BACKOFF_DELAYS_MS[Math.min(executionAttempt - 1, BACKOFF_DELAYS_MS.length - 1)], opts?.signal)
    }
  }

  const finalMsg = errorMessage(lastError)
  const finalModel = models[Math.min(currentModelIndex, Math.max(0, models.length - 1))] || primaryModel

  emitRecovery(opts, {
    attempt: Math.max(executionAttempt, 1),
    maxAttempts: MAX_ATTEMPTS,
    action: 'exhausted',
    model: finalModel,
    error: finalMsg,
  })

  const testedSummary = testedModels.length > 0 ? testedModels.join(', ') : primaryModel
  const skippedSummary = skippedModels.length > 0
    ? ` Modeles bloques preventivement: ${skippedModels.join(', ')}.`
    : ''

  throw new Error(
    `Ollama: toutes les tentatives epuisees (${Math.max(executionAttempt, 1)}). ` +
    `Modeles testes: ${testedSummary}.` +
    skippedSummary +
    ` Derniere erreur: ${finalMsg}`,
  )
}

export async function resilientOllamaChat(
  model: string,
  messages: OllamaMessage[],
  temperature?: number,
  opts?: ResilienceOptions & { num_ctx?: number },
) {
  const ctxLevels = [opts?.num_ctx, 4096, 2048].filter(
    (v): v is number | undefined => v === undefined || (typeof v === 'number' && v > 0),
  )
  const seen = new Set<number | undefined>()
  const uniqueCtxLevels = ctxLevels.filter((v) => { if (seen.has(v)) return false; seen.add(v); return true })

  for (let i = 0; i < uniqueCtxLevels.length; i++) {
    const ctx = uniqueCtxLevels[i]
    try {
      return await withResilience(model, opts, (selectedModel) =>
        ollamaChat(selectedModel, messages, temperature, {
          num_ctx: ctx,
          signal: opts?.signal,
          firstByteTimeoutMs: opts?.firstByteTimeoutMs,
        }),
      )
    } catch (err) {
      const msg = errorMessage(err)
      const isMemoryRelated = /memory|memoire|OOM|out of memory|CUDA|VRAM|insufficient/i.test(msg)
        || !!parseOllamaMemoryError(msg)
      if (!isMemoryRelated || i >= uniqueCtxLevels.length - 1) throw err
    }
  }

  return withResilience(model, opts, (selectedModel) =>
    ollamaChat(selectedModel, messages, temperature, {
      num_ctx: 2048,
      signal: opts?.signal,
      firstByteTimeoutMs: opts?.firstByteTimeoutMs,
    }),
  )
}

export async function resilientOllamaChatStream(
  model: string,
  messages: OllamaMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
  opts?: ResilienceOptions & {
    temperature?: number
    // Sampling nucleus / top-k / penalites — indispensables pour appliquer le preset
    // officiel du modele (ex. Qwen3-Coder : temp 0.7, top_p 0.8, top_k 20, repeat 1.05).
    // Avant, ces valeurs etaient acceptees par l'appelant mais jamais transmises a
    // ollamaChatStream → sampling par defaut du modele.
    top_p?: number
    top_k?: number
    min_p?: number
    repeat_penalty?: number
    num_ctx?: number
    // v85b : forward the output budget + first-byte timeout. Without these the
    // code generation ran at Ollama's default context/length → truncated,
    // simplistic multi-file output. Both degrade gracefully with num_ctx.
    num_predict?: number
    firstByteTimeoutMs?: number
  },
) {
  const ctxLevels = [opts?.num_ctx, 4096, 2048].filter(
    (v): v is number | undefined => v === undefined || (typeof v === 'number' && v > 0),
  )
  const seen = new Set<number | undefined>()
  const uniqueCtxLevels = ctxLevels.filter((v) => { if (seen.has(v)) return false; seen.add(v); return true })

  // When the context is downgraded on OOM, the output budget must shrink with
  // it (num_predict can't exceed the window minus the prompt).
  const predictFor = (ctx: number | undefined) => {
    if (opts?.num_predict === undefined) return undefined
    if (ctx === undefined) return opts.num_predict
    return Math.min(opts.num_predict, Math.max(512, Math.floor(ctx * 0.6)))
  }

  for (let i = 0; i < uniqueCtxLevels.length; i++) {
    const ctx = uniqueCtxLevels[i]
    try {
      return await withResilience(model, opts, (selectedModel) =>
        ollamaChatStream(selectedModel, messages, onToken, onDone, {
          temperature: opts?.temperature,
          top_p: opts?.top_p,
          top_k: opts?.top_k,
          min_p: opts?.min_p,
          repeat_penalty: opts?.repeat_penalty,
          signal: opts?.signal,
          num_ctx: ctx,
          num_predict: predictFor(ctx),
          firstByteTimeoutMs: opts?.firstByteTimeoutMs,
        }),
      )
    } catch (err) {
      const msg = errorMessage(err)
      const isMemoryRelated = /memory|memoire|OOM|out of memory|CUDA|VRAM|insufficient/i.test(msg)
        || !!parseOllamaMemoryError(msg)
      if (!isMemoryRelated || i >= uniqueCtxLevels.length - 1) throw err
    }
  }

  return withResilience(model, opts, (selectedModel) =>
    ollamaChatStream(selectedModel, messages, onToken, onDone, {
      temperature: opts?.temperature,
      top_p: opts?.top_p,
      top_k: opts?.top_k,
      min_p: opts?.min_p,
      repeat_penalty: opts?.repeat_penalty,
      signal: opts?.signal,
      num_ctx: 2048,
      num_predict: predictFor(2048),
      firstByteTimeoutMs: opts?.firstByteTimeoutMs,
    }),
  )
}

/**
 * resilientOllamaGenerate avec REDUCTION DE CONTEXTE AUTOMATIQUE
 * Si le modele echoue pour memoire, on reduit num_ctx progressivement
 * au lieu de tout abandonner. Mieux vaut un contexte reduit qu un echec total.
 */
export async function resilientOllamaGenerate(
  model: string,
  prompt: string,
  opts?: ResilienceOptions & { num_ctx?: number },
) {
  // Niveaux de contexte a essayer en cas d echec memoire
  // undefined = defaut Ollama, puis reduction progressive
  const ctxLevels = [opts?.num_ctx, 4096, 2048].filter(
    (v): v is number | undefined => v === undefined || (typeof v === 'number' && v > 0),
  )
  // Deduplicate: si opts.num_ctx est deja 4096 ou 2048, ne pas re-essayer
  const seen = new Set<number | undefined>()
  const uniqueCtxLevels = ctxLevels.filter((v) => { if (seen.has(v)) return false; seen.add(v); return true })

  for (let i = 0; i < uniqueCtxLevels.length; i++) {
    const ctx = uniqueCtxLevels[i]
    try {
      return await withResilience(model, opts, (selectedModel) =>
        ollamaGenerate(selectedModel, prompt, {
          num_ctx: ctx,
          signal: opts?.signal,
          firstByteTimeoutMs: opts?.firstByteTimeoutMs,
        }),
      )
    } catch (err) {
      const msg = errorMessage(err)
      const isMemoryRelated = /memory|memoire|OOM|out of memory|CUDA|VRAM|insufficient/i.test(msg)
        || !!parseOllamaMemoryError(msg)

      // Si ce n est PAS une erreur memoire, on ne peut pas corriger avec num_ctx → throw
      if (!isMemoryRelated) throw err

      // Si c est la derniere tentative de ctx, throw
      if (i >= uniqueCtxLevels.length - 1) throw err

      // Sinon, on essaie avec un contexte plus petit
      emitRecovery(opts, {
        attempt: i + 1,
        maxAttempts: uniqueCtxLevels.length,
        action: 'retry',
        model,
        error: `Memoire insuffisante — reduction du contexte a num_ctx=${uniqueCtxLevels[i + 1] ?? 2048}`,
      })
    }
  }

  // Fallback ultime — ne devrait jamais arriver, mais pour la surete
  return withResilience(model, opts, (selectedModel) =>
    ollamaGenerate(selectedModel, prompt, {
      num_ctx: 2048,
      signal: opts?.signal,
      firstByteTimeoutMs: opts?.firstByteTimeoutMs,
    }),
  )
}
