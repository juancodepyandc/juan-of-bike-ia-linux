/**
 * entNotifScheduler — schedule des notifications X jours avant chaque
 * évaluation détectée. Utilise les Notifications Web (déjà autorisées
 * via SettingsPanel push permission).
 *
 * v82jk Pass 7/9 — Phase 2 P2.6.
 *
 * Fonctionnement :
 *   1. À chaque harvest devoirs OU au boot Aurora, on appelle
 *      `recomputeAllEvalNotifs()`.
 *   2. Pour chaque devoir détecté éval (via entEvalDetector) avec date
 *      future, on calcule la date de notif (date_eval - leadDays).
 *   3. Si date notif > now, on schedule via setTimeout.
 *   4. À fire, on ouvre `new Notification(title, body)` + log dans
 *      `aurora-ent-notifs-sent-v1` pour ne pas re-notifier 2× le même.
 *
 * Toggleable via Settings (entNotifEnabled + leadDays).
 */
import type { HarvestDevoirItem } from './entHarvestService'
import { fastClassify } from './entEvalDetector'

const PREF_KEY = 'aurora-ent-notif-prefs-v1'
const SENT_KEY = 'aurora-ent-notifs-sent-v1'

export type EntNotifPrefs = {
  enabled: boolean
  leadDays: number   // 1, 3, 7
}

const DEFAULT_PREFS: EntNotifPrefs = { enabled: false, leadDays: 3 }

export function readNotifPrefs(): EntNotifPrefs {
  if (typeof window === 'undefined') return DEFAULT_PREFS
  try {
    const raw = window.localStorage.getItem(PREF_KEY)
    if (!raw) return DEFAULT_PREFS
    const parsed = JSON.parse(raw)
    return {
      enabled: typeof parsed.enabled === 'boolean' ? parsed.enabled : false,
      leadDays: [1, 3, 7].includes(parsed.leadDays) ? parsed.leadDays : 3,
    }
  } catch { return DEFAULT_PREFS }
}

export function writeNotifPrefs(prefs: EntNotifPrefs): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(PREF_KEY, JSON.stringify(prefs)) } catch { /* ignore */ }
}

function readSent(): Record<string, number> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(SENT_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function writeSent(sent: Record<string, number>): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(SENT_KEY, JSON.stringify(sent)) } catch { /* ignore */ }
}

/** Build deterministic key from devoir for dedup. */
function notifKey(item: HarvestDevoirItem): string {
  return `${(item.subject || '').slice(0, 20)}::${(item.title || '').slice(0, 80)}::${item.date || ''}`
}

/** Cleanup expired sent records (>30 days old) pour pas saturer storage. */
function cleanSent(sent: Record<string, number>): Record<string, number> {
  const cutoff = Date.now() - 30 * 24 * 3600 * 1000
  const cleaned: Record<string, number> = {}
  for (const [k, ts] of Object.entries(sent)) {
    if (ts > cutoff) cleaned[k] = ts
  }
  return cleaned
}

/** Active timeouts pending pour pouvoir cancel sur re-compute. */
const activeTimeouts: Map<string, number> = new Map()

function clearAllTimeouts(): void {
  for (const t of activeTimeouts.values()) {
    window.clearTimeout(t)
  }
  activeTimeouts.clear()
}

/** Recompute toutes les notifs futures pour les devoirs donnés. */
export function recomputeEvalNotifs(devoirs: HarvestDevoirItem[]): {
  scheduled: number
  alreadySent: number
  pastDue: number
  notEval: number
} {
  const prefs = readNotifPrefs()
  if (!prefs.enabled) {
    clearAllTimeouts()
    return { scheduled: 0, alreadySent: 0, pastDue: 0, notEval: 0 }
  }
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') {
    return { scheduled: 0, alreadySent: 0, pastDue: 0, notEval: 0 }
  }
  clearAllTimeouts()
  let sent = cleanSent(readSent())
  let scheduled = 0, alreadySent = 0, pastDue = 0, notEval = 0
  const now = Date.now()
  for (const item of devoirs) {
    const det = fastClassify(item)
    if (!det.isEval) { notEval++; continue }
    const dueDate = item.date ? new Date(item.date).getTime() : NaN
    if (Number.isNaN(dueDate)) { notEval++; continue }
    if (dueDate < now) { pastDue++; continue }
    const notifAt = dueDate - prefs.leadDays * 24 * 3600 * 1000
    if (notifAt < now) { pastDue++; continue }
    const key = notifKey(item)
    if (sent[key]) { alreadySent++; continue }
    const delay = notifAt - now
    if (delay > 2_147_000_000) continue  // setTimeout max int32 ~24.8 days
    const t = window.setTimeout(() => {
      try {
        const notif = new Notification(`📚 Éval ${prefs.leadDays}j : ${item.subject || 'matière'}`, {
          body: item.title || 'Évaluation à venir',
          tag: `aurora-eval-${key}`,
          icon: '/icons/aurora-192.png',
        })
        notif.onclick = () => {
          window.focus()
          // Idéalement ouvre la vue Academy "Mon ENT" — wired in Pass 9.
          window.dispatchEvent(new CustomEvent('aurora-academy-focus-eval', { detail: { item } }))
        }
        sent[key] = Date.now()
        writeSent(sent)
        activeTimeouts.delete(key)
      } catch { /* swallow notif errors */ }
    }, delay)
    activeTimeouts.set(key, t)
    scheduled++
  }
  return { scheduled, alreadySent, pastDue, notEval }
}

/** Force-trigger une notif (pour test). */
export function triggerTestNotif(): boolean {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return false
  try {
    new Notification('📚 Aurora ENT — test', {
      body: 'Les notifs Pronote/ENT sont actives. Tu seras prévenu·e avant chaque éval.',
      tag: 'aurora-ent-test',
    })
    return true
  } catch { return false }
}

/** Stats actuelles pour UI. */
export function getNotifStats(): { activeTimeouts: number; sentTotal: number } {
  return {
    activeTimeouts: activeTimeouts.size,
    sentTotal: Object.keys(readSent()).length,
  }
}
