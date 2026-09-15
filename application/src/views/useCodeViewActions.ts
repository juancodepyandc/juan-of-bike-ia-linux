import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import type { SaveDialogData } from '../components/SaveDialog.tsx'
import type { CodeFile } from '../services/codeOrchestrator.ts'
import { stopDevServer } from '../services/codeDevServer.ts'
import { saveAndExportZip, saveToWorkspace } from '../services/saveSystem.ts'
import type { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore.ts'
import type { useModuleHistoryStore } from '../stores/moduleHistoryStore.ts'
import type { usePromptLibraryStore } from '../stores/promptLibraryStore.ts'
import type { WorkspaceSetters } from './useCodeViewWorkspacePersistence.ts'

export function useCodeViewActions({
  activeFileData,
  savedProjectData,
  addPrompt,
  clearHistory,
  resetWorkspaceSnapshot,
  setters,
  abortRef,
  resumeAfterReloadRef,
  isGeneratingRef,
  streamBufferRef,
  streamCharsTotalRef,
  streamTimerRef,
  setCopied,
  setIsGenerating,
  setStreamCharsTotal,
}: {
  activeFileData: CodeFile | null
  savedProjectData: SaveDialogData | null
  addPrompt: ReturnType<typeof usePromptLibraryStore.getState>['addPrompt']
  clearHistory: ReturnType<typeof useModuleHistoryStore.getState>['clearHistory']
  resetWorkspaceSnapshot: ReturnType<typeof useCodeWorkspaceStore.getState>['resetWorkspaceSnapshot']
  setters: WorkspaceSetters
  abortRef: MutableRefObject<AbortController | null>
  resumeAfterReloadRef: MutableRefObject<string | null>
  isGeneratingRef: MutableRefObject<boolean>
  streamBufferRef: MutableRefObject<string[]>
  streamCharsTotalRef: MutableRefObject<number>
  streamTimerRef: MutableRefObject<ReturnType<typeof setTimeout> | null>
  setCopied: Dispatch<SetStateAction<boolean>>
  setIsGenerating: Dispatch<SetStateAction<boolean>>
  setStreamCharsTotal: Dispatch<SetStateAction<number>>
}) {
  const copyCurrentFile = useCallback(() => {
    if (!activeFileData) return
    const pureCode = activeFileData.content
      .replace(/^```[\w-]*\n?/, '')
      .replace(/\n?```$/, '')
      .trim()
    void navigator.clipboard.writeText(pureCode)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }, [activeFileData, setCopied])

  const finalizeSavedResult = useCallback((savedPath: string, payload: SaveDialogData | null) => {
    if (!payload) return
    addPrompt({
      module: 'code',
      prompt: payload.prompt,
      fidelityScore: payload.fidelityScore,
      parameters: payload.parameters,
      tags: ['code'],
    })
    setters.setSavedProjectPath(savedPath)
    setters.setSaveFeedback(null)
    setters.setProgress(`Resultat sauvegarde: ${savedPath}`)
  }, [addPrompt, setters])

  const handlePersistentSave = useCallback(async (target: 'workspace' | 'zip') => {
    if (!savedProjectData) return
    setters.setSaveTarget(target)
    setters.setSaveFeedback(null)
    const result = target === 'workspace'
      ? await saveToWorkspace({ ...savedProjectData, codeFiles: savedProjectData.codeFiles })
      : await saveAndExportZip({ ...savedProjectData, codeFiles: savedProjectData.codeFiles })
    if (result.ok) {
      finalizeSavedResult(result.savedPath, savedProjectData)
    } else {
      setters.setSaveFeedback(result.error ?? 'Erreur inconnue pendant la sauvegarde.')
    }
    setters.setSaveTarget(null)
  }, [finalizeSavedResult, savedProjectData, setters])

  const clearConversation = useCallback(() => {
    clearHistory('code')
    resumeAfterReloadRef.current = null
    setters.setFiles([])
    setters.setActiveFile(0)
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
    setters.setSaveDialogData(null)
    setters.setSavedProjectData(null)
    setters.setSaveTarget(null)
    setters.setSaveFeedback(null)
    setters.setSavedProjectPath(null)
    setters.setPreflightReport(null)
    setters.setFollowUpAnalysis(null)
    setters.setPrompt('')
    setters.setRecoveryStatus(null)
    void stopDevServer()
    setters.setDevServerState({ running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null })
    resetWorkspaceSnapshot()
  }, [clearHistory, resetWorkspaceSnapshot, resumeAfterReloadRef, setters])

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    if (streamTimerRef.current !== null) {
      clearTimeout(streamTimerRef.current)
      streamTimerRef.current = null
    }
    streamBufferRef.current = []
    streamCharsTotalRef.current = 0
    setStreamCharsTotal(0)
    setters.setStreamPreview('')
    setters.setProgress('Generation arretee.')
    setIsGenerating(false)
    isGeneratingRef.current = false
  }, [abortRef, isGeneratingRef, setIsGenerating, setStreamCharsTotal, setters, streamBufferRef, streamCharsTotalRef, streamTimerRef])

  return { clearConversation, copyCurrentFile, finalizeSavedResult, handlePersistentSave, stopGeneration }
}
