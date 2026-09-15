import { useCallback, useEffect, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import type { SaveDialogData } from '../components/SaveDialog.tsx'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeIntent } from '../services/codeIntent.ts'
import { parseCodeFiles, type CodeFile, type FollowUpAnalysis } from '../services/codeOrchestrator.ts'
import type { CodePreflightReport } from '../services/codePreflight.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import { stopDevServer, type DevServerState } from '../services/codeDevServer.ts'
import type { ModuleHistoryMessage } from '../stores/moduleHistoryStore.ts'
import { useCodeWorkspaceStore, type PersistedCodeWorkspaceState } from '../stores/codeWorkspaceStore.ts'

type WorkspaceViewState = Pick<PersistedCodeWorkspaceState,
  | 'prompt' | 'progress' | 'notes' | 'files' | 'activeFile' | 'error'
  | 'validationResult' | 'correctionLog' | 'intent' | 'totalAttempts'
  | 'finalScore' | 'consoleOutput' | 'recoveryStatus' | 'preflightReport'
>

export type WorkspaceSetters = {
  setPrompt: Dispatch<SetStateAction<string>>
  setProgress: Dispatch<SetStateAction<string>>
  setNotes: Dispatch<SetStateAction<string>>
  setFiles: Dispatch<SetStateAction<CodeFile[]>>
  setActiveFile: Dispatch<SetStateAction<number>>
  setError: Dispatch<SetStateAction<string | null>>
  setValidationResult: Dispatch<SetStateAction<CodeSandboxResult | null>>
  setCorrectionLog: Dispatch<SetStateAction<CorrectionPass[]>>
  setIntent: Dispatch<SetStateAction<CodeIntent | null>>
  setTotalAttempts: Dispatch<SetStateAction<number>>
  setFinalScore: Dispatch<SetStateAction<number>>
  setConsoleOutput: Dispatch<SetStateAction<string>>
  setRecoveryStatus: Dispatch<SetStateAction<string | null>>
  setPreflightReport: Dispatch<SetStateAction<CodePreflightReport | null>>
  setFollowUpAnalysis: Dispatch<SetStateAction<FollowUpAnalysis | null>>
  setStreamPreview: Dispatch<SetStateAction<string>>
  setSaveDialogData: Dispatch<SetStateAction<SaveDialogData | null>>
  setSavedProjectData: Dispatch<SetStateAction<SaveDialogData | null>>
  setSaveTarget: Dispatch<SetStateAction<'workspace' | 'zip' | null>>
  setSaveFeedback: Dispatch<SetStateAction<string | null>>
  setSavedProjectPath: Dispatch<SetStateAction<string | null>>
  setDevServerState: Dispatch<SetStateAction<DevServerState>>
}

export function useCodeViewWorkspacePersistence({
  activeSessionId,
  getRecentMessages,
  isGeneratingRef,
  resumeAfterReloadRef,
  state,
  setters,
  setWorkspaceSnapshot,
}: {
  activeSessionId: string
  getRecentMessages: (module: 'code', maxTurns?: number) => ModuleHistoryMessage[]
  isGeneratingRef: MutableRefObject<boolean>
  resumeAfterReloadRef: MutableRefObject<string | null>
  state: WorkspaceViewState
  setters: WorkspaceSetters
  setWorkspaceSnapshot: ReturnType<typeof useCodeWorkspaceStore.getState>['setWorkspaceSnapshot']
}) {
  const hydrationTimerRef = useRef<number | null>(null)
  const [persistenceReady, setPersistenceReady] = useState(false)

  const armPersistence = useCallback(() => {
    if (hydrationTimerRef.current) window.clearTimeout(hydrationTimerRef.current)
    hydrationTimerRef.current = window.setTimeout(() => {
      setPersistenceReady(true)
      hydrationTimerRef.current = null
    }, 0)
  }, [])

  const applySnapshot = useCallback((snapshot: ReturnType<typeof useCodeWorkspaceStore.getState>) => {
    setters.setPrompt(snapshot.prompt)
    setters.setProgress(snapshot.progress)
    setters.setNotes(snapshot.notes)
    setters.setFiles(snapshot.files)
    setters.setActiveFile(snapshot.activeFile)
    setters.setError(null)
    setters.setValidationResult(snapshot.validationResult)
    setters.setCorrectionLog(snapshot.correctionLog)
    setters.setIntent(snapshot.intent)
    setters.setTotalAttempts(snapshot.totalAttempts)
    setters.setFinalScore(snapshot.finalScore)
    setters.setConsoleOutput(snapshot.consoleOutput)
    setters.setRecoveryStatus(null)
    setters.setPreflightReport(snapshot.preflightReport)
  }, [setters])

  const hydrateHistory = useCallback(() => {
    const messages = getRecentMessages('code', 20)
    const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')
    const restored = lastAssistant?.content ? parseCodeFiles(lastAssistant.content) : []
    setters.setFiles(restored)
  }, [getRecentMessages, setters])

  const handleSessionChange = useCallback(() => {
    if (isGeneratingRef.current) return
    setPersistenceReady(false)
    if (hydrationTimerRef.current) {
      window.clearTimeout(hydrationTimerRef.current)
      hydrationTimerRef.current = null
    }
    resetTransientView(setters)

    const snapshot = useCodeWorkspaceStore.getState()
    const hasSnapshot = snapshot.sessionId === activeSessionId
      && (snapshot.prompt.trim().length > 0 || snapshot.files.length > 0 || snapshot.pendingResume || Boolean(snapshot.progress))
    if (!hasSnapshot) {
      hydrateHistory()
      armPersistence()
      return
    }

    applySnapshot(snapshot)
    const resumeFailCount = snapshot.resumeFailCount ?? 0
    const timeSinceLastResume = Date.now() - (snapshot.lastResumeAttempt ?? 0)
    const canResume = snapshot.pendingResume
      && snapshot.prompt.trim()
      && resumeFailCount < 12
      && timeSinceLastResume > 2_500
    if (canResume) {
      setters.setProgress('Session restauree apres redemarrage. Reprise automatique programmee...')
      resumeAfterReloadRef.current = snapshot.prompt
    } else if (snapshot.pendingResume && snapshot.prompt.trim()) {
      useCodeWorkspaceStore.getState().setWorkspaceSnapshot({
        pendingResume: false,
        resumeFailCount: 0,
        lastResumeAttempt: null,
      })
      setters.setProgress('Reprise automatique suspendue apres une serie de redemarrages consecutifs. Relance manuelle disponible.')
    }
    armPersistence()
  }, [activeSessionId, applySnapshot, armPersistence, hydrateHistory, isGeneratingRef, resumeAfterReloadRef, setters])

  useEffect(() => () => {
    if (hydrationTimerRef.current) window.clearTimeout(hydrationTimerRef.current)
  }, [])

  useEffect(() => {
    handleSessionChange()
  }, [handleSessionChange])

  useEffect(() => {
    if (!persistenceReady) return
    setWorkspaceSnapshot({ sessionId: activeSessionId, ...state })
  }, [activeSessionId, persistenceReady, setWorkspaceSnapshot, state])

  return { handleSessionChange, workspacePersistenceReady: persistenceReady }
}

function resetTransientView(setters: WorkspaceSetters) {
  setters.setActiveFile(0)
  setters.setPrompt('')
  setters.setNotes('')
  setters.setStreamPreview('')
  setters.setValidationResult(null)
  setters.setCorrectionLog([])
  setters.setIntent(null)
  setters.setTotalAttempts(0)
  setters.setFinalScore(0)
  setters.setConsoleOutput('')
  setters.setError(null)
  setters.setProgress('')
  setters.setRecoveryStatus(null)
  setters.setPreflightReport(null)
  setters.setFollowUpAnalysis(null)
  setters.setSaveDialogData(null)
  setters.setSavedProjectData(null)
  setters.setSaveTarget(null)
  setters.setSaveFeedback(null)
  setters.setSavedProjectPath(null)
  void stopDevServer()
  setters.setDevServerState({ running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null })
}
