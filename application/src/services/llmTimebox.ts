export class LlmTimeboxError extends Error {
  readonly label: string
  readonly timeoutMs: number

  constructor(label: string, timeoutMs: number) {
    super(`${label} timed out after ${timeoutMs}ms`)
    this.name = 'LlmTimeboxError'
    this.label = label
    this.timeoutMs = timeoutMs
  }
}

export function isLlmTimeboxError(error: unknown): error is LlmTimeboxError {
  return error instanceof LlmTimeboxError
}

export async function withTimeout<T>(
  promise: Promise<T>,
  {
    label,
    timeoutMs,
  }: {
    label: string
    timeoutMs: number
  },
): Promise<T> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return promise
  }

  let timer: ReturnType<typeof globalThis.setTimeout> | null = null

  try {
    return await Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        timer = globalThis.setTimeout(() => {
          reject(new LlmTimeboxError(label, timeoutMs))
        }, timeoutMs)
      }),
    ])
  } finally {
    if (timer) {
      globalThis.clearTimeout(timer)
    }
  }
}
