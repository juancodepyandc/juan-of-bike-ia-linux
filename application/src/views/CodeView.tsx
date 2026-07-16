import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { selectCodeModelForHardware } from '../config/models'
import { buildCodeModuleAssets } from '../config/moduleAssetPacks'
import { useManagedRuntime } from '../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics'
import {
  parseCodeFiles,
  type CodeFile,
  type FollowUpAnalysis,
} from '../services/codeOrchestrator'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodePreflightReport } from '../services/codePreflight'
import type { CodeIntent } from '../services/codeIntent'
import type { CodeSandboxResult } from '../services/codeSandbox'
import { stopDevServer, type DevServerState } from '../services/codeDevServer'
import { saveAndExportZip, saveToWorkspace } from '../services/saveSystem'
import { useAppStore } from '../stores/appStore'
import { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import { CodeViewDeliveryPanel } from './codeViewDeliveryPanel'
import { CodeViewControlPanel } from './codeViewControlPanel'
import { CodeViewChrome } from './codeViewChrome'
import { runCodeViewGeneration, type CodeViewGenerateOptions } from './codeViewGeneration'
import {
  CODE_VIEW_PROMPT_GUIDE,
  buildCodePipelineLabel,
  codeContextNeedsVision,
  formatProjectType,
} from './codeViewShellHelpers'

export default function CodeView() {
  const { codeModel, hardware, installedModels, mainModel, runtimeServices, visionModel } = useAppStore()
  const diagnostics = useStudioDiagnostics({ requiresOllama: true })
  const { executeWithRuntime } = useManagedRuntime()
  const { pushMessage, getRecentMessages, clearHistory, getActiveSession, renameSession } = useModuleHistoryStore()
  const { setWorkspaceSnapshot, resetWorkspaceSnapshot } = useCodeWorkspaceStore()
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const effectiveCodeModel = useMemo(
    () => selectCodeModelForHardware(hardware, installedModels, codeModel),
    [codeModel, hardware, installedModels],
  )
  const contextNeedsVision = useMemo(() => codeContextNeedsVision(contextFiles), [contextFiles])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'code',
    title: 'Pack modele code',
    assets: buildCodeModuleAssets(effectiveCodeModel, visionModel, mainModel, contextNeedsVision),
  })
  const [prompt, setPrompt] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState('')
  const [streamPreview, setStreamPreview] = useState('')
  // v77n: counter cumulatif de chars recus (non cappe) pour montrer
  // VISUELLEMENT que la generation avance — meme quand la live preview est
  // pausee. Sans ca, l user voit '...' fige sur le progress et a l impression
  // que la page freeze.
  const [streamCharsTotal, setStreamCharsTotal] = useState(0)
  const streamCharsTotalRef = useRef(0)
  // Coalesce streaming-token appends: without batching, a 50K-char generation
  // triggers thousands of React re-renders on the entire CodeView which freezes
  // the tunnel UI (setInterval 63ms violations, page unresponsive, forced
  // reload). We throttle at 250ms (4 flushes per second) instead of rAF
  // (60/s) — the UI still feels live but the main thread stays free.
  const streamBufferRef = useRef<string[]>([])
  const streamTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [fileSearch, setFileSearch] = useState('')
  const [showLineNumbers, setShowLineNumbers] = useState(true)
  // Default mode = 'preview' (simulator visible immediately) — l user explicitement
  // demande "j ai pas de simulateur pour voir a quoi ca ressemble". Le simulator
  // existait depuis longtemps via le toggle "Oeil" mais etait peu visible.
  // En mettant preview en defaut, l user voit l app/web qui se construit en
  // streaming des le premier token au lieu de devoir trouver le bouton.
  const [bigViewMode, setBigViewMode] = useState<'code' | 'preview'>('preview')
  const [bigViewport, setBigViewport] = useState<'desktop' | 'tablet' | 'mobile'>('desktop')
  const bigPreviewIframeRef = useRef<HTMLIFrameElement>(null)
  const [notes, setNotes] = useState('')
  const [files, setFiles] = useState<CodeFile[]>([])
  const [activeFile, setActiveFile] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [validationResult, setValidationResult] = useState<CodeSandboxResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [saveDialogData, setSaveDialogData] = useState<SaveDialogData | null>(null)
  const [savedProjectData, setSavedProjectData] = useState<SaveDialogData | null>(null)
  const [saveTarget, setSaveTarget] = useState<'workspace' | 'zip' | null>(null)
  const [saveFeedback, setSaveFeedback] = useState<string | null>(null)
  const [savedProjectPath, setSavedProjectPath] = useState<string | null>(null)
  const [promptLibraryOpen, setPromptLibraryOpen] = useState(false)
  const [clarification, setClarification] = useState<ClarificationRequest | null>(null)
  const { addPrompt } = usePromptLibraryStore()
  const abortRef = useRef<AbortController | null>(null)

  // New pipeline state
  const [correctionLog, setCorrectionLog] = useState<CorrectionPass[]>([])
  const [intent, setIntent] = useState<CodeIntent | null>(null)
  const [totalAttempts, setTotalAttempts] = useState(0)
  const [finalScore, setFinalScore] = useState(0)
  // v73: design polish report (visual projects only) — score / 100 with the
  // exact missing/penalties so the user can see why a generation got a low
  // mark instead of having to guess from the rendered preview.
  const [designReport, setDesignReport] = useState<{ score: number; missing: string[]; penalties: string[] } | null>(null)
  const [devServerState, setDevServerState] = useState<DevServerState>({
    running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null,
  })
  const [consoleOutput, setConsoleOutput] = useState('')
  const [recoveryStatus, setRecoveryStatus] = useState<string | null>(null)
  const [preflightReport, setPreflightReport] = useState<CodePreflightReport | null>(null)
  const [followUpAnalysis, setFollowUpAnalysis] = useState<FollowUpAnalysis | null>(null)
  const resumeAfterReloadRef = useRef<string | null>(null)
  const workspaceHydrationTimerRef = useRef<ReturnType<typeof window.setTimeout> | null>(null)
  const [workspacePersistenceReady, setWorkspacePersistenceReady] = useState(false)
  // Mirror `isGenerating` in a ref so callbacks that must NOT rebuild every
  // toggle (handleSessionChange) can still read the latest value without
  // listing `isGenerating` as a dependency (that would cause a re-render loop).
  const isGeneratingRef = useRef(false)

  // Pre-compute recent messages ONCE to avoid calling getRecentMessages (which
  // triggers getActiveSession → potential set()) multiple times during render.
  const recentMessages = getRecentMessages('code', 6)
  const activeSession = getActiveSession('code')
  const hasConversation = recentMessages.length > 0
  const conversationTurns = Math.ceil(recentMessages.length / 2)

  const armWorkspacePersistence = useCallback(() => {
    if (workspaceHydrationTimerRef.current) {
      window.clearTimeout(workspaceHydrationTimerRef.current)
    }

    workspaceHydrationTimerRef.current = window.setTimeout(() => {
      setWorkspacePersistenceReady(true)
      workspaceHydrationTimerRef.current = null
    }, 0)
  }, [])

  const applyPersistedWorkspaceSnapshot = useCallback((snapshot: ReturnType<typeof useCodeWorkspaceStore.getState>) => {
    setPrompt(snapshot.prompt)
    setProgress(snapshot.progress)
    setNotes(snapshot.notes)
    setFiles(snapshot.files)
    setActiveFile(snapshot.activeFile)
    setError(null)
    setValidationResult(snapshot.validationResult)
    setCorrectionLog(snapshot.correctionLog)
    setIntent(snapshot.intent)
    setTotalAttempts(snapshot.totalAttempts)
    setFinalScore(snapshot.finalScore)
    setConsoleOutput(snapshot.consoleOutput)
    setRecoveryStatus(null)
    setPreflightReport(snapshot.preflightReport)
  }, [])

  const hydrateFromSessionHistory = useCallback(() => {
    const sessionMessages = getRecentMessages('code', 20)
    const lastAssistantMsg = [...sessionMessages].reverse().find((m) => m.role === 'assistant')
    if (lastAssistantMsg?.content) {
      const restored = parseCodeFiles(lastAssistantMsg.content)
      setFiles(restored.length > 0 ? restored : [])
    } else {
      setFiles([])
    }
  }, [getRecentMessages])

  // Session change handler — resets UI state, then restores files from session history
  const handleSessionChange = useCallback(() => {
    // If a generation is currently running, DO NOT re-apply a snapshot
    // restoration that could re-arm a resume. The active generate() already
    // owns the workspace lifecycle; touching it here causes the "page se
    // relance apres generation finie" symptom. Using the ref keeps this
    // guard out of the useCallback dependency array.
    if (isGeneratingRef.current) {
      return
    }
    setWorkspacePersistenceReady(false)
    if (workspaceHydrationTimerRef.current) {
      window.clearTimeout(workspaceHydrationTimerRef.current)
      workspaceHydrationTimerRef.current = null
    }
    setActiveFile(0)
    setPrompt('')
    setNotes('')
    setStreamPreview('')
    setValidationResult(null)
    setCorrectionLog([])
    setIntent(null)
    setTotalAttempts(0)
    setFinalScore(0)
    setConsoleOutput('')
    setError(null)
    setProgress('')
    setRecoveryStatus(null)
    setPreflightReport(null)
    setFollowUpAnalysis(null)
    setSaveDialogData(null)
    setSavedProjectData(null)
    setSaveTarget(null)
    setSaveFeedback(null)
    setSavedProjectPath(null)
    void stopDevServer()
    setDevServerState({ running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null })

    const snapshot = useCodeWorkspaceStore.getState()
    const hasSnapshotForSession = snapshot.sessionId === activeSession.id
      && (
        snapshot.prompt.trim().length > 0
        || snapshot.files.length > 0
        || snapshot.pendingResume
        || Boolean(snapshot.progress)
      )

    if (hasSnapshotForSession) {
      applyPersistedWorkspaceSnapshot(snapshot)
      // Reprise agressive: on privilegie la continuite de la mission, avec un petit
      // delai pour eviter uniquement les boucles de crash ultra-serrees.
      const maxResumeAttempts = 12
      const minResumeIntervalMs = 2_500
      const resumeFailCount = snapshot.resumeFailCount ?? 0
      const lastResumeAttempt = snapshot.lastResumeAttempt ?? 0
      const timeSinceLastResume = Date.now() - lastResumeAttempt
      const canResume = snapshot.pendingResume
        && snapshot.prompt.trim()
        && resumeFailCount < maxResumeAttempts
        && timeSinceLastResume > minResumeIntervalMs

      if (canResume) {
        setProgress('Session restauree apres redemarrage. Reprise automatique programmee...')
        resumeAfterReloadRef.current = snapshot.prompt
      } else if (snapshot.pendingResume && snapshot.prompt.trim()) {
        // Trop de tentatives ou trop rapide — on clear le flag et on laisse l'user decider
        useCodeWorkspaceStore.getState().setWorkspaceSnapshot({
          pendingResume: false,
          resumeFailCount: 0,
          lastResumeAttempt: null,
        })
        setProgress('Reprise automatique suspendue apres une serie de redemarrages consecutifs. Relance manuelle disponible.')
      }
      armWorkspacePersistence()
      return
    }

    hydrateFromSessionHistory()
    armWorkspacePersistence()
  }, [activeSession.id, applyPersistedWorkspaceSnapshot, armWorkspacePersistence, hydrateFromSessionHistory])

  const activeFileData = files[activeFile] || null
  const ollamaLabel = runtimeServices.ollama.running
    ? 'Actif'
    : runtimeServices.ollama.available
      ? 'Auto-start'
      : 'Absent'
  const activeModel = contextNeedsVision ? visionModel : effectiveCodeModel
  const canGenerate = Boolean(prompt.trim()) && !isGenerating && !diagnostics.blockingReason

  // Pipeline label for UI
  const pipelineLabel = useMemo(() => buildCodePipelineLabel(intent), [intent])

  // Cleanup dev server on unmount
  useEffect(() => {
    return () => {
      void stopDevServer()
      if (streamTimerRef.current !== null) {
        clearTimeout(streamTimerRef.current)
        streamTimerRef.current = null
      }
      streamBufferRef.current = []
    }
  }, [])

  useEffect(() => {
    return () => {
      if (workspaceHydrationTimerRef.current) {
        window.clearTimeout(workspaceHydrationTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    handleSessionChange()
  }, [handleSessionChange])

  useEffect(() => {
    if (!workspacePersistenceReady) return

    setWorkspaceSnapshot({
      sessionId: activeSession.id,
      prompt,
      progress,
      notes,
      files,
      activeFile,
      error,
      validationResult,
      correctionLog,
      intent,
      totalAttempts,
      finalScore,
      consoleOutput,
      recoveryStatus,
      preflightReport,
    })
  }, [
    activeFile,
    activeSession.id,
    correctionLog,
    consoleOutput,
    error,
    files,
    finalScore,
    intent,
    notes,
    preflightReport,
    progress,
    prompt,
    recoveryStatus,
    setWorkspaceSnapshot,
    totalAttempts,
    validationResult,
    workspacePersistenceReady,
  ])

  useEffect(() => {
    if (!error) return
    if (diagnostics.blockingReason) return
    if (!/^(Ollama|ComfyUI|Shell natif):/i.test(error)) return
    setError(null)
  }, [diagnostics.blockingReason, error])

  const copyCurrentFile = useCallback(() => {
    if (!activeFileData) return
    const pureCode = activeFileData.content
      .replace(/^```[\w-]*\n?/, '')
      .replace(/\n?```$/, '')
      .trim()
    void navigator.clipboard.writeText(pureCode)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }, [activeFileData])

  const finalizeSavedResult = useCallback((savedPath: string, payload: SaveDialogData | null) => {
    if (!payload) return
    addPrompt({
      module: 'code',
      prompt: payload.prompt,
      fidelityScore: payload.fidelityScore,
      parameters: payload.parameters,
      tags: ['code'],
    })
    setSavedProjectPath(savedPath)
    setSaveFeedback(null)
    setProgress(`Resultat sauvegarde: ${savedPath}`)
  }, [addPrompt])

  const handlePersistentSave = useCallback(async (target: 'workspace' | 'zip') => {
    if (!savedProjectData) return
    setSaveTarget(target)
    setSaveFeedback(null)

    const result = target === 'workspace'
      ? await saveToWorkspace({ ...savedProjectData, codeFiles: savedProjectData.codeFiles })
      : await saveAndExportZip({ ...savedProjectData, codeFiles: savedProjectData.codeFiles })

    if (result.ok) {
      finalizeSavedResult(result.savedPath, savedProjectData)
    } else {
      setSaveFeedback(result.error ?? 'Erreur inconnue pendant la sauvegarde.')
    }

    setSaveTarget(null)
  }, [finalizeSavedResult, savedProjectData])

  const clearConversation = useCallback(() => {
    clearHistory('code')
    resumeAfterReloadRef.current = null
    setFiles([])
    setActiveFile(0)
    setNotes('')
    setStreamPreview('')
    setValidationResult(null)
    setCorrectionLog([])
    setIntent(null)
    setTotalAttempts(0)
    setFinalScore(0)
    setConsoleOutput('')
    setError(null)
    setProgress('')
    setSaveDialogData(null)
    setSavedProjectData(null)
    setSaveTarget(null)
    setSaveFeedback(null)
    setSavedProjectPath(null)
    setPreflightReport(null)
    setFollowUpAnalysis(null)
    setPrompt('')
    setRecoveryStatus(null)
    void stopDevServer()
    setDevServerState({ running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null })
    resetWorkspaceSnapshot()
  }, [clearHistory, resetWorkspaceSnapshot])

  const stopGeneration = useCallback(() => {
    // v77m fix bug critique OOM: stopper la generation doit
    // (1) abort le pipeline TS (signal.aborted),
    // (2) immediatement clear le state UI pour liberer la memoire ET
    //     debloquer le bouton Generate (avant ce fix, isGenerating
    //     restait true tant qu Ollama n avait pas reagi a l abort,
    //     et streamBufferRef continuait a accumuler).
    abortRef.current?.abort()
    abortRef.current = null
    // Clear streaming buffers immediately — sinon les chunks deja en transit
    // continuent a s accumuler en memoire jusqu a ce que setTimeout flush.
    if (streamTimerRef.current !== null) {
      clearTimeout(streamTimerRef.current)
      streamTimerRef.current = null
    }
    streamBufferRef.current = []
    streamCharsTotalRef.current = 0
    setStreamCharsTotal(0)
    setStreamPreview('')
    setProgress('Generation arretee.')
    setIsGenerating(false)
    isGeneratingRef.current = false
    // Le reste du state (files, notes, validationResult, correctionLog)
    // n est PAS clear : l user veut voir ce qui a ete genere jusque la.
  }, [])

  const generate = useCallback(
    (options?: CodeViewGenerateOptions) => runCodeViewGeneration({
      abortRef,
      activeModel,
      activeSessionId: activeSession.id,
      contextFiles,
      diagnosticsBlockingReason: diagnostics.blockingReason,
      executeWithRuntime,
      files,
      getActiveSession,
      getRecentMessages,
      isGenerating,
      isGeneratingRef,
      preparePack,
      prompt,
      pushMessage,
      renameSession,
      resumeAfterReloadRef,
      setActiveFile,
      setClarification,
      setConsoleOutput,
      setCorrectionLog,
      setDesignReport,
      setDevServerState,
      setError,
      setFiles,
      setFinalScore,
      setFollowUpAnalysis,
      setIntent,
      setIsGenerating,
      setNotes,
      setPreflightReport,
      setProgress,
      setRecoveryStatus,
      setSaveDialogData,
      setSaveFeedback,
      setSavedProjectData,
      setSavedProjectPath,
      setSaveTarget,
      setStreamCharsTotal,
      setStreamPreview,
      setTotalAttempts,
      setValidationResult,
      setWorkspaceSnapshot,
      streamBufferRef,
      streamCharsTotalRef,
      streamTimerRef,
      visionModel,
    }, options),
    [activeModel, activeSession.id, contextFiles, diagnostics.blockingReason, executeWithRuntime, files, getActiveSession, getRecentMessages, isGenerating, preparePack, prompt, pushMessage, renameSession, setWorkspaceSnapshot, visionModel],
  )

  useEffect(() => {
    if (!workspacePersistenceReady || isGenerating) return

    const promptToResume = resumeAfterReloadRef.current
    if (!promptToResume) return

    // Extra safety: if the current snapshot says there is no pendingResume,
    // we must NOT auto-fire a generate (the previous run finished cleanly).
    const snap = useCodeWorkspaceStore.getState()
    if (!snap.pendingResume) {
      resumeAfterReloadRef.current = null
      return
    }

    resumeAfterReloadRef.current = null
    void generate({ resumeMode: 'after_reload', overridePrompt: promptToResume })
  }, [generate, isGenerating, workspacePersistenceReady])

  return (
    <div data-code-view="true" className="relative min-h-full flex flex-col overflow-hidden">
      <ClarificationDialog request={clarification} />
      <SaveDialog
        data={saveDialogData}
        onClose={() => setSaveDialogData(null)}
        onSaved={(savedPath) => {
          finalizeSavedResult(savedPath, saveDialogData)
          setSaveDialogData(null)
        }}
      />
      <PromptLibraryPanel
        open={promptLibraryOpen}
        onClose={() => setPromptLibraryOpen(false)}
        currentModule="code"
        onUsePrompt={(p) => setPrompt(p)}
      />
      <CodeViewChrome
        activeModel={activeModel}
        diagnostics={diagnostics}
        filesCount={files.length}
        ollamaAvailable={runtimeServices.ollama.available}
        ollamaLabel={ollamaLabel}
        ollamaRunning={runtimeServices.ollama.running}
        projectLabel={intent ? formatProjectType(intent.projectType) : undefined}
      />

      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 xl:grid-cols-[23rem_minmax(0,1fr)]">
        <CodeViewControlPanel
          assetPack={assetPack}
          canGenerate={canGenerate}
          clearConversation={clearConversation}
          contextFiles={contextFiles}
          conversationTurns={conversationTurns}
          correctionLog={correctionLog}
          designReport={designReport}
          devServerState={devServerState}
          diagnostics={diagnostics}
          error={error}
          files={files}
          finalScore={finalScore}
          followUpAnalysis={followUpAnalysis}
          formatProjectType={formatProjectType}
          generate={generate}
          handlePersistentSave={handlePersistentSave}
          handleSessionChange={handleSessionChange}
          hasConversation={hasConversation}
          intent={intent}
          isGenerating={isGenerating}
          ollamaRunning={runtimeServices.ollama.running}
          pipelineLabel={pipelineLabel}
          preflightReport={preflightReport}
          progress={progress}
          prompt={prompt}
          promptGuide={CODE_VIEW_PROMPT_GUIDE}
          recentMessages={recentMessages}
          recoveryStatus={recoveryStatus}
          saveFeedback={saveFeedback}
          savedProjectData={savedProjectData}
          savedProjectPath={savedProjectPath}
          saveTarget={saveTarget}
          setContextFiles={setContextFiles}
          setPrompt={setPrompt}
          setPromptLibraryOpen={setPromptLibraryOpen}
          stopGeneration={stopGeneration}
          streamCharsTotal={streamCharsTotal}
          totalAttempts={totalAttempts}
        />
        <CodeViewDeliveryPanel
          activeFile={activeFile}
          activeFileData={activeFileData}
          bigPreviewIframeRef={bigPreviewIframeRef}
          bigViewport={bigViewport}
          bigViewMode={bigViewMode}
          consoleOutput={consoleOutput}
          copied={copied}
          copyCurrentFile={copyCurrentFile}
          devServerState={devServerState}
          error={error}
          fileSearch={fileSearch}
          files={files}
          intent={intent}
          isGenerating={isGenerating}
          notes={notes}
          progress={progress}
          recoveryStatus={recoveryStatus}
          setActiveFile={setActiveFile}
          setBigViewport={setBigViewport}
          setBigViewMode={setBigViewMode}
          setFileSearch={setFileSearch}
          setShowLineNumbers={setShowLineNumbers}
          showLineNumbers={showLineNumbers}
          streamPreview={streamPreview}
          validationResult={validationResult}
        />
      </div>
    </div>
  )
}
