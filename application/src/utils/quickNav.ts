/**
 * Quick-nav hotkey: press `g` then a letter within 800ms to jump between
 * modules — `g c` = chat, `g i` = image, `g o` = code, etc.
 *
 * Inspired by Gmail/GitHub's "g + letter" leader key. Zero-install, just
 * attaches a single keydown listener at the document level.
 */
import { useAppStore } from '../stores/appStore'
import type { ModuleId } from '../types/app'

const SHORTCUT_MAP: Record<string, ModuleId> = {
  c: 'conversation',
  i: 'image',
  o: 'code',        // 'c' taken by chat, 'o' for cOde
  v: 'video',
  d: 'drawing',
  t: '3d',          // '3' not a letter — use 't' for Three-d
  a: 'learning',    // a = Academy
  s: 'voice',       // s = Speech/voice
  y: 'cyber',       // y = cYber
}

export function installQuickNav(): () => void {
  let leader = false
  let leaderTimer: number | null = null

  const resetLeader = () => {
    leader = false
    if (leaderTimer !== null) {
      window.clearTimeout(leaderTimer)
      leaderTimer = null
    }
  }

  const onKey = (e: KeyboardEvent) => {
    // Ignore when typing in any input/textarea/contenteditable.
    const target = e.target as HTMLElement | null
    const tag = target?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable) return
    if (e.metaKey || e.ctrlKey || e.altKey) return

    if (!leader) {
      if (e.key === 'g') {
        leader = true
        leaderTimer = window.setTimeout(resetLeader, 800)
      }
      return
    }

    // Second keystroke in leader sequence
    e.preventDefault()
    const letter = e.key.toLowerCase()
    const moduleId = SHORTCUT_MAP[letter]
    if (moduleId) {
      const store = useAppStore.getState()
      store.setActiveModule(moduleId)
      // Also enter focus mode so the user lands directly in the module UI
      // rather than just highlighting its card on the spatial canvas.
      store.setFocusMode(true)
    }
    resetLeader()
  }

  window.addEventListener('keydown', onKey)
  return () => {
    window.removeEventListener('keydown', onKey)
    resetLeader()
  }
}

export const QUICK_NAV_MAP = SHORTCUT_MAP
