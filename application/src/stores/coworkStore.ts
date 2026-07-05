// Store for the Cowork takeover overlay state. Anywhere in the app can call
// useCoworkStore.getState().open() to launch the Cowork UI; AppShell renders
// the overlay based on isOpen.
//
// In v2 the store also brokers user-facing confirmations: the executor
// pauses on a destructive action and pushes a CoworkConfirmation here; the
// CoworkOverlay UI renders the dialog and resolves the promise via approve /
// skip / abort.

import { create } from 'zustand'
import { useAppStore } from './appStore.ts'
import type { CoworkConfirmation } from '../services/coworkTypes.ts'
import type { ModuleId } from '../types/app.ts'

// Cowork must stay visible on desktop, web and tunnel surfaces: the runtime
// capability table decides which actions are allowed, while the UI still
// shows the real thread, artifacts, connector cards and verification state.
function coworkAvailable(): boolean {
  return typeof window !== 'undefined'
}

export { coworkAvailable }

export type CoworkLaunchModule = ModuleId

function getDefaultLaunchModule(): CoworkLaunchModule {
  return useAppStore.getState().activeModule
}

type CoworkState = {
  isOpen: boolean
  // Module that opened the overlay — wired to the planner system prompt to
  // give Aurora the right context (e.g. "Module Code actif").
  launchModule: CoworkLaunchModule
  open: (m?: CoworkLaunchModule) => void
  close: () => void
  toggle: (m?: CoworkLaunchModule) => void

  // Pending confirmation, if any. Only one at a time — the executor
  // serialises actions and waits for resolution before issuing the next.
  pendingConfirmation: CoworkConfirmation | null
  requestConfirmation: (c: CoworkConfirmation) => void
  clearConfirmation: () => void

  // Current run abort controller (set by the overlay when a run starts so
  // the user can stop a long-running plan without unmounting the overlay).
  abortController: AbortController | null
  setAbortController: (c: AbortController | null) => void
  abortRun: () => void

  // Settings panel visibility (overlay-internal, not the global app settings).
  settingsOpen: boolean
  // v82m1 — when set, CoworkSettingsDialog opens directly on the
  // 'connecteurs' tab and scrolls / highlights the row matching this id
  // (case-insensitive, suffix-matched against ConnectorId so 'reddit',
  // 'Reddit', 'github' all resolve). Cleared by closeSettings(). Pure
  // user-driven : only set when the user clicks a connector pill in the
  // events log AND confirms the opt-in dialog.
  settingsFocusConnector: string | null
  openSettings: (focusConnector?: string | null) => void
  closeSettings: () => void
}

export const useCoworkStore = create<CoworkState>((set, get) => ({
  isOpen: false,
  launchModule: 'conversation',
  open: (m) => {
    if (!coworkAvailable()) return
    set({ isOpen: true, launchModule: m ?? getDefaultLaunchModule() })
  },
  close: () => {
    get().abortRun()
    set({ isOpen: false, pendingConfirmation: null, settingsOpen: false, settingsFocusConnector: null })
  },
  toggle: (m) => set((s) => {
    if (s.isOpen) {
      return { isOpen: false, pendingConfirmation: null, settingsOpen: false, settingsFocusConnector: null }
    }
    if (!coworkAvailable()) return s
    return { isOpen: true, launchModule: m ?? getDefaultLaunchModule() }
  }),

  pendingConfirmation: null,
  requestConfirmation: (c) => set({ pendingConfirmation: c }),
  clearConfirmation: () => set({ pendingConfirmation: null }),

  abortController: null,
  setAbortController: (c) => set({ abortController: c }),
  abortRun: () => {
    const c = get().abortController
    if (c && !c.signal.aborted) {
      try { c.abort() } catch { /* noop */ }
    }
    set({ abortController: null })
  },

  settingsOpen: false,
  settingsFocusConnector: null,
  openSettings: (focusConnector?: string | null) => set({
    settingsOpen: true,
    settingsFocusConnector: focusConnector ?? null,
  }),
  closeSettings: () => set({ settingsOpen: false, settingsFocusConnector: null }),
}))
