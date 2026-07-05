/**
 * Simple event bus used across the app to publish real notifications:
 *   generation.started / generation.finished / generation.error
 *   model.load / model.unload
 *   queue.enqueued / queue.started
 *
 * UI surfaces (MobileGrimoire's ink scrolls, desktop toasts, and the optional
 * service-worker Notification API) subscribe to the bus and render what they
 * care about.
 *
 * No timers, no fake cycles — every line the user sees corresponds to a real
 * event emitted by a service or a store.
 */
export type NotifKind =
  | 'generation.started'
  | 'generation.progress'
  | 'generation.finished'
  | 'generation.error'
  | 'queue.enqueued'
  | 'queue.started'
  | 'model.load'
  | 'model.unload'
  | 'info'
  | 'warn'
  | 'error'

export interface NotifEvent {
  id: number
  kind: NotifKind
  /** Which module emitted it (conversation, forge, image, video...). */
  source?: string
  /** Short human title. */
  title: string
  /** Optional longer body for off-app push. */
  body?: string
  /** If the event relates to a long-running job, its id. */
  jobId?: string
  at: number
  /** Should this also pop a system notification (PWA)? */
  push?: boolean
  /** Ink-scroll visual tone. */
  tone?: 'ok' | 'err' | 'info'
  /** Ink-scroll seal character. */
  seal?: string
}

type Handler = (ev: NotifEvent) => void

const handlers = new Set<Handler>()
let lastId = 0

export function subscribe(fn: Handler): () => void {
  handlers.add(fn)
  return () => handlers.delete(fn)
}

export function emit(partial: Omit<NotifEvent, 'id' | 'at'>): NotifEvent {
  const ev: NotifEvent = {
    ...partial,
    id: ++lastId,
    at: Date.now(),
  }
  for (const h of Array.from(handlers)) {
    try { h(ev) } catch { /* subscriber error — ignore to keep the bus alive */ }
  }
  // Fire-and-forget system push if requested and allowed
  if (ev.push) {
    void pushSystem(ev)
  }
  return ev
}

// ---------------------------------------------------------------------------
// System notifications (Notification API + service worker registration).
// Works when the PWA is installed or the tab stays open. Free, unlimited.
// ---------------------------------------------------------------------------

let swReg: ServiceWorkerRegistration | null = null

/**
 * Current notification permission (also handles the Safari/old-API detection).
 * `unsupported` = browser has no Notification API at all; caller should hide
 * any related UI instead of offering a broken button.
 */
export function pushPermissionState(): NotificationPermission | 'unsupported' {
  if (typeof window === 'undefined') return 'unsupported'
  if (typeof Notification === 'undefined') return 'unsupported'
  return Notification.permission
}

/**
 * Requests notification permission. Must be called synchronously from a user
 * gesture — Chrome, Brave, Edge, Safari macOS all require it. Safari iOS
 * additionally requires the PWA to be installed first.
 *
 * The legacy Notification.requestPermission signature (callback) is handled
 * for older Safari.
 */
export async function ensurePushPermission(): Promise<NotificationPermission | 'unsupported'> {
  if (typeof Notification === 'undefined') return 'unsupported'
  if (Notification.permission !== 'default') return Notification.permission
  try {
    // Newer browsers return a Promise; older Safari only supports a callback.
    const maybePromise = Notification.requestPermission((p) => p)
    if (maybePromise && typeof (maybePromise as Promise<NotificationPermission>).then === 'function') {
      return await (maybePromise as Promise<NotificationPermission>)
    }
    return Notification.permission
  } catch {
    return 'denied'
  }
}

export async function registerNotificationWorker(path = '/sw.js'): Promise<void> {
  if (typeof navigator === 'undefined') return
  if (!('serviceWorker' in navigator)) return
  try {
    swReg = await navigator.serviceWorker.register(path, { scope: '/' })
  } catch {
    swReg = null
  }
}

async function pushSystem(ev: NotifEvent): Promise<void> {
  if (typeof Notification === 'undefined') return
  if (Notification.permission !== 'granted') return
  const options: NotificationOptions = {
    body: ev.body,
    icon: '/fairy/natsu.png',
    badge: '/juan-bike-icon.svg',
    tag: ev.kind + ':' + (ev.jobId || ev.id),
    data: ev,
  }
  try {
    if (swReg?.showNotification) {
      await swReg.showNotification(ev.title, options)
    } else {
      new Notification(ev.title, options)
    }
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Convenience helpers used by the forge queue and other services
// ---------------------------------------------------------------------------

export function notifyStarted(source: string, label: string, jobId?: string) {
  return emit({
    kind: 'generation.started',
    source, title: `${label} lancé`, jobId,
    tone: 'info', seal: '⚡',
  })
}
export function notifyFinished(source: string, label: string, jobId?: string) {
  return emit({
    kind: 'generation.finished',
    source, title: `${label} terminé`, jobId,
    tone: 'ok', seal: '✦', push: true,
  })
}
export function notifyError(source: string, label: string, detail: string, jobId?: string) {
  return emit({
    kind: 'generation.error',
    source, title: `${label} échec`, body: detail, jobId,
    tone: 'err', seal: '✖', push: true,
  })
}
export function notifyQueueEnqueued(label: string, position: number) {
  return emit({
    kind: 'queue.enqueued',
    title: `${label} en file`, body: `Position ${position}`,
    tone: 'info', seal: '›',
  })
}
export function notifyQueueStarted(label: string) {
  return emit({
    kind: 'queue.started',
    title: `Lancement : ${label}`,
    tone: 'info', seal: '▶',
  })
}
export function notifyModelLoad(name: string) {
  return emit({ kind: 'model.load', title: `Chargement modèle`, body: name, tone: 'info', seal: '♢' })
}
export function notifyModelUnload(name: string) {
  return emit({ kind: 'model.unload', title: `Déchargé`, body: name, tone: 'info', seal: '◇' })
}
