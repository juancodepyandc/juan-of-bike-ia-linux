export const IMAGE_GENERATION_LOCK_KEY = 'aurora.imageGenerationLock.v1'
export const IMAGE_GENERATION_LOCK_TTL_MS = 15 * 60 * 1000

export type ImageGenerationLockStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function readLock(storage: ImageGenerationLockStorage): { token?: string; startedAt?: number } | null {
  const raw = storage.getItem(IMAGE_GENERATION_LOCK_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as { token?: string; startedAt?: number } | null
  } catch {
    return null
  }
}

export function claimImageGenerationLock(
  prompt: string,
  options: {
    storage?: ImageGenerationLockStorage
    now?: number
    token?: string
    ttlMs?: number
  } = {},
): string | null {
  const now = options.now ?? Date.now()
  const ttlMs = options.ttlMs ?? IMAGE_GENERATION_LOCK_TTL_MS
  const token = options.token ?? `${now}-${Math.random().toString(36).slice(2)}`

  try {
    const storage = options.storage ?? globalThis.localStorage
    const existing = readLock(storage)
    if (existing?.token && typeof existing.startedAt === 'number'
      && Number.isFinite(existing.startedAt) && now - existing.startedAt < ttlMs) {
      return null
    }
    storage.setItem(IMAGE_GENERATION_LOCK_KEY, JSON.stringify({ token, prompt, startedAt: now }))
    return readLock(storage)?.token === token ? token : null
  } catch {
    return token
  }
}

export function releaseImageGenerationLock(
  token: string,
  storage?: ImageGenerationLockStorage,
): void {
  try {
    const lockStorage = storage ?? globalThis.localStorage
    if (readLock(lockStorage)?.token === token) lockStorage.removeItem(IMAGE_GENERATION_LOCK_KEY)
  } catch {
  }
}
