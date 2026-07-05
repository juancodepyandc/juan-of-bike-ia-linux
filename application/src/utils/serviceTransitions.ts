/**
 * v82hi : log persistant des transitions des services backend
 * (Bridge / Ollama / ComfyUI). Ring buffer cap 30, stocké en
 * localStorage. Read-only depuis Settings, write depuis
 * ConnectionIndicator au moment de la détection up↔down.
 */

const KEY = 'aurora-service-transitions-v1'
const CAP = 30

export type ServiceId = 'bridge' | 'ollama' | 'comfy'

export type ServiceTransition = {
  ts: number
  service: ServiceId | 'all'
  // 'up' = passé OK, 'down' = passé KO/error
  kind: 'up' | 'down'
  // optionnel : services down lors d'une transition all (pour debug)
  downList?: ServiceId[]
}

export function readTransitions(): ServiceTransition[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr
      .filter((e): e is ServiceTransition =>
        e && typeof e.ts === 'number'
        && typeof e.service === 'string'
        && (e.kind === 'up' || e.kind === 'down'),
      )
      .slice(0, CAP)
  } catch { return [] }
}

export function pushTransition(entry: Omit<ServiceTransition, 'ts'>): ServiceTransition[] {
  if (typeof window === 'undefined') return []
  try {
    const cur = readTransitions()
    const next: ServiceTransition[] = [
      { ts: Date.now(), ...entry },
      ...cur,
    ].slice(0, CAP)
    window.localStorage.setItem(KEY, JSON.stringify(next))
    return next
  } catch { return readTransitions() }
}

export function clearTransitions(): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.removeItem(KEY) } catch { /* swallow */ }
}
