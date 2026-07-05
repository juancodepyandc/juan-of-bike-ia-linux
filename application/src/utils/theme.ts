/**
 * theme — sets a `data-theme` attribute on <html> so CSS can opt into
 * variants. "sobre" softens splashes for serious work ; "dark" flips
 * the paper background to near-black ; "light" is paper. The legacy
 * "manga" id remains in the type for backward-compat with old
 * localStorage values, but it is no longer the default and is no
 * longer offered in the Settings picker (v82bb — user direction
 * "ne plus dépendre du design manga").
 *
 * Persisted to localStorage so the choice sticks across sessions.
 */
export type ThemeId = 'manga' | 'sobre' | 'dark' | 'light'

const STORAGE_KEY = 'aurora-theme'
const THEMES: ThemeId[] = ['manga', 'sobre', 'dark', 'light']
const DEFAULT_THEME: ThemeId = 'dark'

export function readTheme(): ThemeId {
  if (typeof window === 'undefined') return DEFAULT_THEME
  try {
    const v = window.localStorage.getItem(STORAGE_KEY)
    // v82bb : auto-migrate stored 'manga' → 'dark' so users coming back
    // after theme purge land on a non-manga theme without having to
    // touch Settings. Other valid values pass through.
    if (v === 'manga') {
      try { window.localStorage.setItem(STORAGE_KEY, DEFAULT_THEME) } catch { /* ignore */ }
      return DEFAULT_THEME
    }
    if (v && (THEMES as string[]).includes(v)) return v as ThemeId
  } catch { /* ignore */ }
  return DEFAULT_THEME
}

export function applyTheme(theme: ThemeId): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', theme)
  try { window.localStorage.setItem(STORAGE_KEY, theme) } catch { /* ignore */ }
}

export function installTheme(): void {
  applyTheme(readTheme())
}
