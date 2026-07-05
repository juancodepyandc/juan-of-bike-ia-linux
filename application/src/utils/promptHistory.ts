/**
 * v82gp : prompt history persistant par module.
 * Stocké en localStorage clé aurora-prompt-history-{module}-v1.
 * Cap à 12 entrées, déduplique sur prompt brut, ordre LRU (récent en tête).
 */

const KEY_PREFIX = 'aurora-prompt-history-'
const KEY_SUFFIX = '-v1'
const CAP = 12

export type PromptHistoryEntry = {
  prompt: string
  ts: number
  meta?: Record<string, string | number>
}

function key(module: string): string {
  return `${KEY_PREFIX}${module}${KEY_SUFFIX}`
}

export function readHistory(module: string): PromptHistoryEntry[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(key(module))
    if (!raw) return []
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr
      .filter((e): e is PromptHistoryEntry =>
        e && typeof e.prompt === 'string' && typeof e.ts === 'number',
      )
      .slice(0, CAP)
  } catch { return [] }
}

export function pushHistory(
  module: string,
  prompt: string,
  meta?: Record<string, string | number>,
): PromptHistoryEntry[] {
  if (typeof window === 'undefined') return []
  const trimmed = prompt.trim()
  if (!trimmed) return readHistory(module)
  try {
    const cur = readHistory(module).filter((e) => e.prompt !== trimmed)
    const next: PromptHistoryEntry[] = [
      { prompt: trimmed, ts: Date.now(), meta },
      ...cur,
    ].slice(0, CAP)
    window.localStorage.setItem(key(module), JSON.stringify(next))
    return next
  } catch { return readHistory(module) }
}

export function clearHistory(module: string): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.removeItem(key(module)) } catch { /* swallow */ }
}

export function removeHistoryEntry(module: string, prompt: string): PromptHistoryEntry[] {
  if (typeof window === 'undefined') return []
  try {
    const next = readHistory(module).filter((e) => e.prompt !== prompt)
    window.localStorage.setItem(key(module), JSON.stringify(next))
    return next
  } catch { return readHistory(module) }
}
