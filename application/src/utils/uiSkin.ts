import { reloadFresh } from './buildRecovery.ts'

export type UiSkinId = 'manga' | 'aurora_v1' | 'aurora_v3' | 'aurora_v4'

const STORAGE_KEY = 'aurora-ui-skin'
const CHOICE_KEY = 'aurora-ui-skin-choice'
export const USER_PICKABLE_SKINS: UiSkinId[] = ['aurora_v4', 'aurora_v1', 'aurora_v3']
const DEFAULT_SKIN: UiSkinId = 'aurora_v4'

export const UI_SKIN_LABELS: Record<UiSkinId, { title: string; subtitle: string }> = {
  manga:     { title: 'Manga',     subtitle: '(legacy fallback interne, non sélectionnable)' },
  aurora_v1: { title: 'Editorial', subtitle: 'sphère 3D centrale · shell unifié · italic display' },
  aurora_v3: { title: 'Ricochet',  subtitle: '11 esthétiques radicales · une par module · zéro shell partagé' },
  aurora_v4: { title: 'Aurora OS', subtitle: 'dock orbital · aurores boréales · Team Aurora vivante' },
}

export function readUiSkin(): UiSkinId {
  if (typeof window === 'undefined') return DEFAULT_SKIN
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    const choice = window.localStorage.getItem(CHOICE_KEY)
    if (v && (USER_PICKABLE_SKINS as string[]).includes(v) && v === choice) {
      return v as UiSkinId
    }
    if (v !== DEFAULT_SKIN) {
      try { window.localStorage.setItem(STORAGE_KEY, DEFAULT_SKIN) } catch { /* ignore */ }
    }
  } catch { /* ignore */ }
  return DEFAULT_SKIN
}

export function applyUiSkin(skin: UiSkinId, opts?: { explicit?: boolean }): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-ui-skin', skin)
  try {
    window.localStorage.setItem(STORAGE_KEY, skin)
    if (opts?.explicit !== false) window.localStorage.setItem(CHOICE_KEY, skin)
  } catch { /* ignore */ }
  try { window.dispatchEvent(new CustomEvent('aurora:ui-skin-change', { detail: { skin } })) } catch { /* ignore */ }
}

export function installUiSkin(): void {
  applyUiSkin(readUiSkin(), { explicit: false })
  installSkinCycleHotkey()
  installCrossTabSync()
}

const SYNC_INSTALLED = Symbol.for('aurora.uiSkin.syncInstalled')
type SyncHost = Window & { [SYNC_INSTALLED]?: true }

function installCrossTabSync(): void {
  if (typeof window === 'undefined') return
  const host = window as SyncHost
  if (host[SYNC_INSTALLED]) return
  window.addEventListener('storage', (e: StorageEvent) => {
    if (e.key !== STORAGE_KEY || !e.newValue) return
    if (!(USER_PICKABLE_SKINS as string[]).includes(e.newValue)) return
    if (e.newValue === readUiSkin()) return
    document.documentElement.setAttribute('data-ui-skin', e.newValue)
    setTimeout(() => { try { reloadFresh() } catch { window.location.reload() } }, 200)
  })
  host[SYNC_INSTALLED] = true
}

const HOTKEY_INSTALLED = Symbol.for('aurora.uiSkin.hotkeyInstalled')
type HotkeyHost = Window & { [HOTKEY_INSTALLED]?: true }

function installSkinCycleHotkey(): void {
  if (typeof window === 'undefined') return
  const host = window as HotkeyHost
  if (host[HOTKEY_INSTALLED]) return
  const handler = (e: KeyboardEvent) => {
    if (!(e.metaKey || e.ctrlKey) || !e.shiftKey) return
    if (e.key.toLowerCase() !== 'u') return
    const target = e.target as HTMLElement | null
    const tag = target?.tagName?.toLowerCase()
    if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return
    e.preventDefault()
    const current = readUiSkin()
    const idx = USER_PICKABLE_SKINS.indexOf(current)
    const next = idx === -1
      ? USER_PICKABLE_SKINS[0]
      : USER_PICKABLE_SKINS[(idx + 1) % USER_PICKABLE_SKINS.length]
    applyUiSkin(next)
    setTimeout(() => { try { reloadFresh() } catch { window.location.reload() } }, 360)
  }
  window.addEventListener('keydown', handler)
  host[HOTKEY_INSTALLED] = true
}
