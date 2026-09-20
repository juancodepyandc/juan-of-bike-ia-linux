/** Follow one ComfyUI job without treating queue time or an execution error as an empty image. */
export type ComfyImageOutput = { filename: string; subfolder: string }

export type ComfyHistoryReader = (promptId: string) => Promise<unknown>

type HistoryEntry = {
  status?: { completed?: boolean; status_str?: string; messages?: Array<[string, Record<string, unknown>]> }
  outputs?: Record<string, { images?: Array<{ filename?: string; type?: string; subfolder?: string }> }>
}

export function completedComfyImages(history: unknown, promptId: string): ComfyImageOutput[] | null {
  if (!history || typeof history !== 'object' || Array.isArray(history)) {
    throw new Error('ComfyUI : historique invalide.')
  }
  const entry = (history as Record<string, HistoryEntry>)[promptId]
  if (!entry) return null
  const failure = entry.status?.messages?.find(([type]) =>
    type === 'execution_error' || type === 'execution_interrupted')
  if (failure || entry.status?.status_str === 'error') {
    const detail = failure?.[1]?.exception_message
    throw new Error(`ComfyUI : ${typeof detail === 'string' ? detail : 'génération interrompue ou échouée'}`)
  }
  const names = Object.values(entry.outputs ?? {}).flatMap((output) =>
    (output.images ?? []).filter((image) => !image.type || image.type === 'output')
      .filter((image) => typeof image.filename === 'string' && image.filename.length > 0)
      .map((image) => ({ filename: image.filename!, subfolder: image.subfolder ?? '' })))
  if (names.length && (!entry.status || entry.status.completed === true || entry.status.status_str === 'success')) {
    return names
  }
  if (entry.status?.completed) throw new Error('ComfyUI : tâche terminée sans image de sortie.')
  return null
}

function abortable<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      signal.removeEventListener('abort', abort)
      reject(new DOMException('Annulé', 'AbortError'))
    }
    if (signal.aborted) { abort(); return }
    signal.addEventListener('abort', abort, { once: true })
    operation.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort))
  })
}

function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', abort)
      reject(new DOMException('Annulé', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, milliseconds)
    signal.addEventListener('abort', abort, { once: true })
    if (signal.aborted) abort()
  })
}

export async function waitForComfyImages(
  promptId: string,
  signal: AbortSignal,
  readHistory: ComfyHistoryReader,
  options: { timeoutMs?: number; pollMs?: number; maxConnectionFailures?: number } = {},
): Promise<ComfyImageOutput[]> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal.addEventListener('abort', abort, { once: true })
  if (signal.aborted) abort()
  let timedOut = false
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, options.timeoutMs ?? 30 * 60 * 1000)
  let failures = 0
  try {
    while (!controller.signal.aborted) {
      let history: unknown
      try {
        history = await abortable(readHistory(promptId), controller.signal)
        failures = 0
      } catch (error) {
        if (controller.signal.aborted) throw error
        failures += 1
        if (failures >= (options.maxConnectionFailures ?? 5)) {
          throw new Error(`ComfyUI : connexion perdue ; tâche ${promptId} conservée. ${String(error)}`)
        }
        await pause(options.pollMs ?? 1500, controller.signal)
        continue
      }
      const images = completedComfyImages(history, promptId)
      if (images) return images
      await pause(options.pollMs ?? 1500, controller.signal)
    }
    throw new DOMException('Annulé', 'AbortError')
  } catch (error) {
    if (timedOut) throw new Error(`ComfyUI : délai de suivi dépassé ; tâche ${promptId} conservée sur le serveur.`)
    throw error
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', abort)
  }
}
