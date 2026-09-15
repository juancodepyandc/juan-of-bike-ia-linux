import type { StoreApi } from 'zustand'
import { stopSpeaking, clearSpeakQueue } from '../services/auroraVoice.ts'
import { removeHistoryEntry, type PromptHistoryEntry } from '../utils/promptHistory.ts'
import { useModuleHistoryStore } from './moduleHistoryStore.ts'
import { captureSessionSnapshot, emptySessionSnapshot } from './codeStreamSessions.ts'
import { readNarrateVoice, writeNarrateVoice } from './codeStreamNarration.ts'
import type { CodeStreamStore } from './codeStreamTypes.ts'

type SetStore = StoreApi<CodeStreamStore>['setState']
type GetStore = StoreApi<CodeStreamStore>['getState']

type CoreActionNames =
  | 'dismissErrorDialog'
  | 'retryAfterError'
  | 'setNarrateVoice'
  | 'setDraft'
  | 'recallPrompt'
  | 'removeHistory'
  | 'setWorkMode'
  | 'setRepoPath'
  | 'clearRepoWriteResult'
  | 'activateSession'
  | 'newProject'
  | 'abort'
  | 'reset'

export function createCodeStreamCoreActions(
  set: SetStore,
  get: GetStore,
  abortCurrent: () => void,
): Pick<CodeStreamStore, CoreActionNames> {
  return {
    dismissErrorDialog() {
      set({ errorDialog: null })
    },
    async retryAfterError() {
      set({ errorDialog: null })
      await get().submit()
    },
    setNarrateVoice(on) {
      writeNarrateVoice(on)
      if (!on) {
        stopSpeaking()
        clearSpeakQueue()
      }
      set({ narrateVoice: on })
    },
    setDraft(draft) {
      set({ draft })
    },
    recallPrompt(entry: PromptHistoryEntry) {
      const sessionId = typeof entry.meta?.sessionId === 'string' ? entry.meta.sessionId : null
      const session = useModuleHistoryStore.getState().openPromptSession('code', entry.prompt, sessionId)
      get().activateSession(session.id)
      set({ draft: entry.prompt })
    },
    removeHistory(prompt) {
      set({ history: removeHistoryEntry('code', prompt) })
    },
    setWorkMode(workMode) {
      set({ workMode })
    },
    setRepoPath(repoPath) {
      set({ repoPath })
    },
    clearRepoWriteResult() {
      set({ repoWriteResult: null })
    },
    activateSession(sessionId) {
      const state = get()
      if (!sessionId || state.activeSessionId === sessionId) return
      if (state.streaming) {
        abortCurrent()
        stopSpeaking()
        clearSpeakQueue()
      }

      const snapshots = { ...state.sessionSnapshots }
      if (state.activeSessionId) snapshots[state.activeSessionId] = captureSessionSnapshot(state)
      const next = snapshots[sessionId] ?? emptySessionSnapshot()
      set({
        ...next,
        streaming: false,
        errorDialog: null,
        repoBusy: false,
        activeSessionId: sessionId,
        sessionSnapshots: snapshots,
      })
    },
    newProject() {
      abortCurrent()
      stopSpeaking()
      clearSpeakQueue()
      set({
        streaming: false, streamOutput: '', draft: '', error: null,
        files: [], notes: '', messages: [], followUpKind: null,
        finalScore: 0, totalAttempts: 0, phase: 'idle', phaseMessage: '',
        events: [], progressPct: 0, genStartedAt: null,
        etaSecondsRemaining: null, etaTotalSeconds: null, repoWriteResult: null,
        narration: '', narrationLog: [],
      })
    },
    abort() {
      abortCurrent()
      stopSpeaking()
      clearSpeakQueue()
      set({ streaming: false, phase: get().streamOutput ? 'done' : 'idle' })
    },
    reset() {
      abortCurrent()
      set({
        streaming: false, streamOutput: '', draft: '', error: null,
        phase: 'idle', phaseMessage: '', progressPct: 0, events: [],
        genStartedAt: null, etaSecondsRemaining: null, etaTotalSeconds: null,
      })
    },
  }
}

export { readNarrateVoice }
