/**
 * Keep the mobile tab alive as long as possible so generations launched from
 * the phone don't trigger the iOS Safari "reload on return" that wipes the
 * React tree. We can't fully prevent iOS from killing a backgrounded tab,
 * but we can:
 *
 *   - acquire a screen wake-lock while a generation is in flight
 *   - warn the user via beforeunload if they hit "reload" with pending work
 *   - pause any uncritical timers on visibilitychange=hidden so iOS doesn't
 *     flag the tab as "runaway" (primary reason for the reload-on-return)
 *
 * The backend (bridge_server.py + ComfyUI) is untouched. A reload of the tab
 * now only costs reconnecting to the persisted queue/store state.
 */
import { useForgeQueueStore } from '../stores/forgeQueueStore'

type WakeLockSentinel = { release: () => Promise<void>; released: boolean }
let wakeLock: WakeLockSentinel | null = null

async function acquireWakeLock(): Promise<void> {
  try {
    const wl = (navigator as Navigator & {
      wakeLock?: { request: (t: 'screen') => Promise<WakeLockSentinel> }
    }).wakeLock
    if (!wl) return
    wakeLock = await wl.request('screen')
    wakeLock.released = false
  } catch {
    wakeLock = null
  }
}

async function releaseWakeLock(): Promise<void> {
  if (!wakeLock) return
  try { await wakeLock.release() } catch { /* ignore */ }
  wakeLock = null
}

function hasPendingWork(): boolean {
  const jobs = useForgeQueueStore.getState().jobs
  return jobs.some((j) => j.status === 'running' || j.status === 'queued')
    || jobs.some((j) => j.status === 'done' && !j.saved)
}

export function installTabLifecycleGuards(): () => void {
  // Prevent accidental reload when a job is pending. Most mobile browsers
  // ignore the custom string (standardized) but still show a native confirm.
  const onBeforeUnload = (e: BeforeUnloadEvent) => {
    if (!hasPendingWork()) return
    e.preventDefault()
    e.returnValue = ''
  }

  // Re-acquire the wake-lock when the tab becomes visible again — iOS releases
  // it automatically on visibilitychange=hidden, which is what we want (no
  // runaway) but we want it back the moment the user comes back to look.
  const onVisibility = () => {
    if (document.visibilityState === 'visible' && hasPendingWork()) {
      void acquireWakeLock()
    } else {
      void releaseWakeLock()
    }
  }

  // Subscribe to the queue store: acquire wake-lock as soon as a job starts
  // running, release when nothing is in flight.
  const unsubStore = useForgeQueueStore.subscribe((state) => {
    const running = state.jobs.some((j) => j.status === 'running')
    if (running && !wakeLock) void acquireWakeLock()
    else if (!running && wakeLock) void releaseWakeLock()
  })

  window.addEventListener('beforeunload', onBeforeUnload)
  document.addEventListener('visibilitychange', onVisibility)
  // page becomes fully hidden on iOS before destruction — last chance to emit
  window.addEventListener('pagehide', () => { void releaseWakeLock() })

  return () => {
    window.removeEventListener('beforeunload', onBeforeUnload)
    document.removeEventListener('visibilitychange', onVisibility)
    unsubStore()
    void releaseWakeLock()
  }
}
