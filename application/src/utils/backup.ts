/**
 * backup — full-app export / import of every zustand-persisted store.
 *
 * We snapshot all keys under `aurora-*` / `forge-*` / `module-drafts-*` /
 * `ios_install_dismissed` / `aurora-theme` into a single JSON blob. Restoring
 * wipes the matching keys first, then writes the snapshot, then forces a
 * reload so every store rehydrates from the restored state.
 *
 * Scope: local-only. Nothing leaves the device.
 */

const SAFE_PREFIXES = [
  'aurora-',         // chat store, flashcards, gamification, calendar, drafts, cyber leaderboard, theme…
  'forge-',          // forge queue v2
  'module-drafts-',  // per-module drafts
  'ay-',             // Academy per-exo progress
]
const SAFE_KEYS = new Set([
  'ft-who',
  'ios_install_dismissed',
])

export interface BackupSnapshot {
  app: 'juan-of-bike-ia'
  version: number
  createdAt: string
  entries: Record<string, string>
}

function shouldCapture(key: string): boolean {
  if (SAFE_KEYS.has(key)) return true
  return SAFE_PREFIXES.some((p) => key.startsWith(p))
}

export function captureSnapshot(): BackupSnapshot {
  const entries: Record<string, string> = {}
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i)
    if (!k) continue
    if (!shouldCapture(k)) continue
    const v = localStorage.getItem(k)
    if (typeof v === 'string') entries[k] = v
  }
  return {
    app: 'juan-of-bike-ia',
    version: 1,
    createdAt: new Date().toISOString(),
    entries,
  }
}

export function downloadBackup(): void {
  const snap = captureSnapshot()
  const blob = new Blob([JSON.stringify(snap, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `aurora-backup-${new Date().toISOString().slice(0, 10)}.json`
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export async function restoreFromFile(file: File): Promise<{ restored: number; skipped: number; error?: string }> {
  const text = await file.text()
  let snap: BackupSnapshot
  try {
    snap = JSON.parse(text) as BackupSnapshot
  } catch (e) {
    return { restored: 0, skipped: 0, error: `JSON invalide : ${e instanceof Error ? e.message : String(e)}` }
  }
  if (!snap || snap.app !== 'juan-of-bike-ia' || typeof snap.entries !== 'object') {
    return { restored: 0, skipped: 0, error: 'Fichier non reconnu (champ app ou entries manquant)' }
  }
  // Wipe matching keys first so restored state is a clean copy.
  const toRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i)
    if (k && shouldCapture(k)) toRemove.push(k)
  }
  toRemove.forEach((k) => localStorage.removeItem(k))
  let restored = 0, skipped = 0
  for (const [k, v] of Object.entries(snap.entries)) {
    if (!shouldCapture(k)) { skipped++; continue }
    try {
      localStorage.setItem(k, v)
      restored++
    } catch { skipped++ }
  }
  return { restored, skipped }
}
