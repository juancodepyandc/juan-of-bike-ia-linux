import type { ModuleId } from '../types/app.ts'

let pending: number | undefined

export function cancelModulePreload() {
  if (pending !== undefined) window.clearTimeout(pending)
  pending = undefined
}

export function requestModulePreload(id: ModuleId | 'cowork' | 'voice') {
  if (typeof window === 'undefined') return
  cancelModulePreload()
  const connection = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string }
  }).connection
  if (connection?.saveData || /^(slow-)?2g$/.test(connection?.effectiveType ?? '')) return

  // Brief dwell avoids fetching each module while quickly crossing the dock.
  pending = window.setTimeout(() => {
    pending = undefined
    window.dispatchEvent(new CustomEvent('aurora:preload-module', { detail: id }))
  }, 110)
}
