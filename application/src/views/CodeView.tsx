import { lazy, startTransition, Suspense, useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

const CodeBlock = lazy(() => import('../components/CodeBlock'))
import {
  AlertTriangle,
  Archive,
  BookOpen,
  Bot,
  Check,
  Clipboard,
  Code2,
  Eye,
  Download,
  FileCode2,
  FolderOpen,
  Globe,
  Loader2,
  Monitor,
  Smartphone,
  Tablet,
  MessageSquare,
  Play,
  ScanSearch,
  Search,
  Sparkles,
  StopCircle,
  Terminal,
  Workflow,
} from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import CodeCorrectionLog from '../components/CodeCorrectionLog'
import CodeFileTree from '../components/CodeFileTree'
import CodeProjectPreview, { parsePartialStreamFiles, buildLivePreviewHtml, webProjectFromFiles } from '../components/CodeProjectPreview'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent'
import ContextFilesField from '../components/ContextFilesField'
import VoicePushToTalk from '../components/VoicePushToTalk'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import SessionSwitcher from '../components/SessionSwitcher'
import { selectCodeModelForHardware } from '../config/models'
import { buildCodeModuleAssets } from '../config/moduleAssetPacks'
import { StudioDiagnosticsPanel, StudioHero } from '../components/StudioHero'
import { useManagedRuntime } from '../hooks/useManagedRuntime'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics'
import {
  orchestrateCodeGeneration,
  classifyClarificationSeverity,
  buildAutonomousAssumption,
  serializeCodeFiles,
  parseCodeFiles,
  type CodeFile,
  type CodeOrchestrationResult,
  type FollowUpAnalysis,
} from '../services/codeOrchestrator'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodePreflightReport } from '../services/codePreflight'
import { classifyCodeIntent, type CodeIntent } from '../services/codeIntent'
import { analyzeCyclomaticComplexity, computeHalstead } from '../services/codeStructuralAnalysis'
import LyraCharacter from '../components/voice/LyraCharacter'
import AuroraMascot from '../components/generationFx/mascots'
import type { CodeSandboxResult } from '../services/codeSandbox'
import { startDevServer, stopDevServer, type DevServerState } from '../services/codeDevServer'
import { generateSessionTitle } from '../services/sessionAutoNaming'
import { saveAndExportZip, saveToWorkspace } from '../services/saveSystem'
import { prepareTaskIntelligence } from '../services/taskIntelligence'
import { useAppStore } from '../stores/appStore'
import { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'
import { usePromptLibraryStore } from '../stores/promptLibraryStore'
import { getErrorMessage } from '../utils/errors'
import { prepareContextFiles } from '../utils/multimodalContext'
import type { CodeProjectType } from '../services/codeIntent'

const PROJECT_TYPE_LABELS: Record<CodeProjectType, string> = {
  static_web: 'Page web statique',
  spa_react: 'App React (SPA)',
  spa_vue: 'App Vue (SPA)',
  spa_angular: 'App Angular (SPA)',
  spa_svelte: 'App Svelte (SPA)',
  ssr_nextjs: 'Next.js (SSR)',
  ssr_nuxt: 'Nuxt.js (SSR)',
  ssr_remix: 'Remix (SSR)',
  api_express: 'API Express (Node)',
  api_fastapi: 'API FastAPI (Python)',
  api_django: 'API Django (Python)',
  api_flask: 'API Flask (Python)',
  api_spring: 'API Spring Boot (Java)',
  api_gin: 'API Gin (Go)',
  api_actix: 'API Actix (Rust)',
  api_dotnet: 'API ASP.NET',
  fullstack_mern: 'Fullstack MERN',
  fullstack_nextjs: 'Fullstack Next.js',
  fullstack_django: 'Fullstack Django',
  fullstack_rails: 'Fullstack Rails',
  cli_node: 'CLI Node.js',
  cli_python: 'Script Python',
  cli_rust: 'CLI Rust',
  cli_go: 'CLI Go',
  cli_cpp: 'CLI C++',
  desktop_electron: 'App desktop Electron',
  desktop_tauri: 'App desktop Tauri',
  mobile_rn: 'App mobile React Native',
  mobile_flutter: 'App mobile Flutter',
  library_npm: 'Librairie npm',
  library_pypi: 'Package PyPI',
  library_crate: 'Crate Rust',
  game_web: 'Jeu / App 3D (canvas / WebGL)',
  game_unity: 'Jeu Unity (C#)',
  system_c: 'Système C',
  system_cpp: 'Système C++',
  system_rust: 'Système Rust',
  data_python: 'Data / ML (Python)',
  devops_docker: 'DevOps / Docker',
  script: 'Script',
  unknown: 'Type inconnu',
}

function formatProjectType(type: CodeProjectType): string {
  return PROJECT_TYPE_LABELS[type] ?? type.replace(/_/g, ' ')
}

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
  const contextNeedsVision = useMemo(
    () => contextFiles.some((file) => {
      const filename = file.name.toLowerCase()
      const mime = file.type.toLowerCase()
      return mime.startsWith('image/')
        || mime.includes('pdf')
        || /\.(png|jpe?g|webp|gif|bmp|pdf|xlsx?|xlsm|csv|tsv)$/i.test(filename)
    }),
    [contextFiles],
  )
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

  const promptGuide = useMemo(
    () => [
      'But concret et stack attendue (React, FastAPI, Rust CLI...)',
      'Fonctions obligatoires et comportement attendu',
      'Multi-page: routing, navigation, layout partage',
      'Architecture: API REST, GraphQL, fullstack, microservices',
    ],
    [],
  )

  // Pipeline label for UI
  const pipelineLabel = useMemo(() => {
    if (!intent) return 'Intent, preflight local, planning, generation, sandbox, correction, preview.'
    const parts: string[] = []
    parts.push('Preflight local')
    if (intent.needsArchitecturePlanning) parts.push('Planning archi')
    parts.push('Generation modele expert')
    parts.push('Sandbox isole')
    parts.push('Boucle auto-correction')
    if (intent.needsDevServer) parts.push('Dev server')
    if (intent.previewType !== 'none') parts.push('Preview')
    return parts.join(' → ')
  }, [intent])

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

  const generate = useCallback(async (options?: { resumeMode?: 'after_reload'; overridePrompt?: string }) => {
    const activePrompt = (options?.overridePrompt ?? prompt).trim()
    const isResumeRun = options?.resumeMode === 'after_reload'

    if (!activePrompt || isGenerating) return
    if (diagnostics.blockingReason) {
      setError(diagnostics.blockingReason)
      setWorkspaceSnapshot({
        sessionId: activeSession.id,
        prompt: activePrompt,
        error: diagnostics.blockingReason,
        pendingResume: false,
      })
      return
    }

    let conversationHistory = getRecentMessages('code', 6)

    setIsGenerating(true)
    isGeneratingRef.current = true
    setError(null)
    setProgress(isResumeRun ? 'Reprise de la mission code apres redemarrage...' : 'Preparation de la mission code...')
    setStreamPreview('')
    streamCharsTotalRef.current = 0
    setStreamCharsTotal(0)
    setSaveDialogData(null)
    setSavedProjectData(null)
    setSaveTarget(null)
    setSaveFeedback(null)
    setSavedProjectPath(null)
    const currentSnapshot = useCodeWorkspaceStore.getState()
    setWorkspaceSnapshot({
      sessionId: activeSession.id,
      prompt: activePrompt,
      progress: isResumeRun ? 'Reprise automatique de la mission code...' : 'Preparation de la mission code...',
      error: null,
      pendingResume: true,
      resumeFailCount: isResumeRun ? (currentSnapshot.resumeFailCount ?? 0) + 1 : 0,
      lastResumeAttempt: isResumeRun ? Date.now() : null,
    })

    if (isResumeRun) {
      setRecoveryStatus('Reprise automatique apres redemarrage...')
    } else {
      setNotes('')
      setFiles([])
      setActiveFile(0)
      setValidationResult(null)
      setCorrectionLog([])
      setIntent(null)
      setTotalAttempts(0)
      setFinalScore(0)
      setConsoleOutput('')
      setRecoveryStatus(null)
      setPreflightReport(null)
      void stopDevServer()
      setDevServerState({ running: false, port: null, url: null, process: 'stopped', error: null, rootPath: null })
    }

    try {
      await executeWithRuntime({
        module: 'code',
        title: isResumeRun ? 'Reprise generation code' : 'Generation code',
        services: ['ollama'],
        skipRelease: true,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
          setProgress('Analyse de la demande...')
          const taskContext = await prepareTaskIntelligence({
            module: 'code',
            prompt: activePrompt,
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 2,
            phaseSpan: 8,
          })

          // Smart clarification: only block the user for CRITICAL, stack-forking
          // decisions. Everything else auto-proceeds with a documented assumption
          // so the user never has to answer a vague "could you clarify?" dialog.
          if (taskContext.clarificationQuestion) {
            const earlyIntent = classifyCodeIntent(activePrompt)
            const severity = classifyClarificationSeverity(
              taskContext.clarificationQuestion,
              earlyIntent,
              activePrompt,
            )

            if (severity === 'critical') {
              setPhase('Clarification critique requise.', 12)
              const userAnswer = await new Promise<string | null>((resolve) => {
                setClarification({ question: taskContext.clarificationQuestion!, onRespond: resolve })
              })
              setClarification(null)
              if (userAnswer) {
                taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nPrecision utilisateur: ${userAnswer}`
                taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nUser clarification: ${userAnswer}`
              } else {
                const assumption = buildAutonomousAssumption(activePrompt, earlyIntent)
                taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nHypotheses autonomes (utilisateur a passe la clarification):\n${assumption}`
              }
            } else if (severity === 'optional') {
              // Optional: auto-proceed but document the assumption so the user
              // understands what the module decided.
              const assumption = buildAutonomousAssumption(activePrompt, earlyIntent)
              taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\nHypotheses autonomes du module (choix par defaut documente):\n${assumption}`
              taskContext.generationPrompt = `${taskContext.generationPrompt}\n\nAutonomous assumptions:\n${assumption}`
            }
            // severity === 'skip' → silently ignore the vague question.
          }

          // Enrich the prompt with a dedicated "## FICHIERS FOURNIS PAR L UTILISATEUR" block
          // so the Codeur knows the role of every attached file and how to integrate it:
          //   - images  → listed with a placeholder data URL the Codeur can reuse in <img src=...>
          //   - css     → merge into the project stylesheet so the user theme is preserved
          //   - json    → treat as data source (hero, products, testimonials, …)
          //   - text/md → treat as editorial copy to feed the page content
          // Build an id → data URL map for the placeholders injected in the prompt.
          const userFileDataUrls: Record<string, string> = {}
          if (preparedContext.length > 0) {
            preparedContext.forEach((file, idx) => {
              if (file.imageBase64) {
                userFileDataUrls[`USER_FILE_${idx}`] = `data:image/jpeg;base64,${file.imageBase64}`
              }
            })
          }
          if (preparedContext.length > 0) {
            const userFilesLines: string[] = [
              '## FICHIERS FOURNIS PAR L UTILISATEUR (a integrer fidelement)',
              '- Ces fichiers sont joints au prompt. Tu DOIS comprendre leur role et les incorporer.',
              '- Images → utilise-les comme <img src="USER_FILE_<id>"> (placeholder) — elles seront injectees au build en data URL.',
              '- CSS → fusionne leurs regles dans ta feuille de styles (conserve la palette/typographie qui y figure).',
              '- JSON → utilise leurs donnees pour remplir la page (products, faqs, testimonials, features, etc.).',
              '- Texte / Markdown → traite leur contenu comme le copywriting attendu dans la page.',
              '',
            ]
            preparedContext.forEach((file, idx) => {
              const id = `USER_FILE_${idx}`
              if (file.kind === 'image') {
                userFilesLines.push(`### ${file.name} — IMAGE (${file.kind})`)
                userFilesLines.push(`  Reference prompt: ${id}`)
                userFilesLines.push(`  Consigne: remplace les visuels adaptes par <img src="${id}" alt="...">.`)
              } else if (file.kind === 'text' || file.kind === 'pdf' || file.kind === 'spreadsheet' || file.kind === 'other') {
                const ext = file.name.split('.').pop()?.toLowerCase() || ''
                const role = ext === 'css' || ext === 'scss' ? 'FEUILLE DE STYLE A FUSIONNER'
                  : ext === 'json' ? 'DONNEES JSON A UTILISER DANS LA PAGE'
                  : ext === 'md' || ext === 'markdown' ? 'COPY EDITORIAL'
                  : ext === 'html' || ext === 'htm' ? 'FRAGMENT HTML A INTEGRER'
                  : 'CONTEXTE TEXTE'
                userFilesLines.push(`### ${file.name} — ${role}`)
                const excerpt = (file.extractedText || '').slice(0, 2500)
                if (excerpt) {
                  userFilesLines.push('```')
                  userFilesLines.push(excerpt)
                  userFilesLines.push('```')
                }
              }
            })
            taskContext.enrichedPrompt = `${taskContext.enrichedPrompt}\n\n${userFilesLines.join('\n')}`
          }

          const lastUserMessage = [...getRecentMessages('code', 4)].reverse().find((msg) => msg.role === 'user')
          if (!lastUserMessage || lastUserMessage.content !== taskContext.enrichedPrompt) {
            pushMessage('code', { role: 'user', content: taskContext.enrichedPrompt })
          }
          conversationHistory = getRecentMessages('code', 6)

          const controller = new AbortController()
          abortRef.current = controller

          setProgress('Classification du projet et demarrage du pipeline...')
          setPhase('Classification et pipeline expert code...', 15)

          // Full orchestration pipeline
          const result: CodeOrchestrationResult = await orchestrateCodeGeneration({
            prompt: activePrompt,
            enrichedPrompt: taskContext.enrichedPrompt,
            conversationHistory: conversationHistory.map((msg) => ({
              role: msg.role as 'user' | 'assistant',
              content: msg.content,
            })),
            // Pass the existing project files whenever we already have some,
            // not just during a resume. This turns every new prompt into a
            // follow-up conversation (modify / add / remove) instead of
            // a scratch-restart — exactly what the user expects when they
            // type "change the color to blue" after a first generation.
            existingFiles: files,
            contextImages: preparedContext.flatMap((file) => file.imageBase64 ? [file.imageBase64] : []),
            userFileDataUrls,
            configuredCodeModel: activeModel,
            visionModel,
            setPhase: (detail, prog) => {
              setProgress(detail)
              setPhase(detail, prog)
            },
            onToken: (token) => {
              // Coalesce via rAF + memory cap. A fast Ollama stream emits hundreds
              // of tokens per second; re-rendering CodeView per token is what made
              // the UI freeze on long generations. We accumulate into a ref and
              // schedule ONE state flush per animation frame.
              streamBufferRef.current.push(token)
              streamCharsTotalRef.current += token.length
              if (streamTimerRef.current !== null) return
              streamTimerRef.current = setTimeout(() => {
                streamTimerRef.current = null
                const toFlush = streamBufferRef.current.join('')
                streamBufferRef.current = []
                if (!toFlush) return
                setStreamPreview((prev) => {
                  const merged = prev + toFlush
                  // v77m: cap reduit de 20K a 10K et fenetre 7K. Pour les projets
                  // WebGL/Three.js (shader Fresnel + particles + textures) la
                  // sortie depasse facilement 30K chars; le <pre> qui re-render
                  // a chaque flush etait un gros contributeur a l OOM Chrome.
                  // L user voit toujours le stream complet via l onglet Code
                  // qui lit `files` (post-parse, pas `prev`).
                  if (merged.length > 10_000) return merged.slice(-7_000)
                  return merged
                })
                // v77n: refresh le counter visible (a basse frequence — chaque
                // flush, pas chaque token).
                setStreamCharsTotal(streamCharsTotalRef.current)
              }, 250)
            },
            onFilesUpdate: (newFiles, newNotes) => {
              // v77o: marquer ces setState comme NON-URGENT via startTransition.
              // Sans ca, setFiles avec 7+ fichiers de 5K chars chacun (35K
              // total) re-rendre tous les enfants de CodeView en sync (panel
              // Files, panel Code, panel Notes), bloquant le main thread JS
              // et pouvant declencher 'Page ne repond pas' Chrome. Avec
              // startTransition, React peut interrompre ce re-render si une
              // interaction urgente arrive (ex: clic Stop button) — la
              // reactivite est preservee.
              startTransition(() => {
                setFiles(newFiles)
                setActiveFile(0)
                setNotes(newNotes)
              })
            },
            onValidationUpdate: (sandboxRes) => {
              // v77o: idem startTransition — le validationResult panel
              // re-render avec les sandbox steps, qui peuvent contenir
              // plusieurs KB chacun.
              startTransition(() => {
                setValidationResult(sandboxRes)

                // MEMORY-SAFE: Cap encore plus agressif pour gros projets.
                // Chaque step peut avoir plusieurs KB — on cap chaque step
                // AVANT le join, puis le total a 30K au lieu de 50K.
                const perStepCap = 4_000
                const output = sandboxRes.steps
                  .map((s) => {
                    const outStr = s.output.length > perStepCap
                      ? `${s.output.slice(0, 2_500)}\n...[step tronque: ${s.output.length} chars]...\n${s.output.slice(-1_000)}`
                      : s.output
                    return `$ ${s.command}\n${outStr}`
                  })
                  .join('\n\n')
                setConsoleOutput(
                  output.length > 30_000
                    ? `${output.slice(0, 12_000)}\n...[tronque]...\n${output.slice(-12_000)}`
                    : output,
                )
              })
            },
            onCorrectionLogUpdate: (log, attempt, score) => {
              // MEMORY-SAFE: on stocke au max 8 dernieres passes en state React
              // (le reste est deja archive cote orchestrateur). Evite un gros
              // re-render de la colonne quand on a 10+ passes.
              // v77o: startTransition pour ne pas bloquer le clic Stop button
              // si l user veut interrompre pendant qu une passe se termine.
              startTransition(() => {
                setCorrectionLog(log.length > 8 ? log.slice(-8) : log)
                setTotalAttempts(attempt)
                setFinalScore(score)
              })
            },
            onFollowUpAnalysis: (analysis) => {
              setFollowUpAnalysis(analysis)
            },
            onRecoveryEvent: (ev) => {
              const labels: Record<string, string> = {
                retry: 'Reconnexion Ollama...',
                restart_service: 'Redemarrage du service Ollama...',
                model_fallback: `Bascule vers ${ev.model}...`,
                health_check: 'Verification sante Ollama...',
                memory_guard: ev.error.startsWith('RAM insuffisante')
                  ? `Memoire protegee: ${ev.error}`
                  : 'Protection memoire active...',
                release_models: 'Dechargement memoire Ollama...',
                auto_install_fallback: `Installation du fallback ${ev.model}...`,
                exhausted: `Toutes les tentatives echouees: ${ev.error}`,
              }
              setRecoveryStatus(labels[ev.action] || ev.action)
              if (ev.action === 'exhausted') {
                setTimeout(() => setRecoveryStatus(null), 5000)
              }
            },
            signal: controller.signal,
          })

          abortRef.current = null

          // Update final state
          setFiles(result.files)
          setNotes(result.notes)
          setValidationResult(result.sandboxResult)
          setCorrectionLog(result.correctionLog)
          setIntent(result.intent)
          setTotalAttempts(result.totalAttempts)
          setFinalScore(result.finalScore)
          setPreflightReport(result.preflightReport)
          setDesignReport(result.designReport ?? null)

          if (result.files.length === 0) {
            const emptyDeliveryReason = result.notes.trim() || 'Aucun fichier exploitable n a ete livre par le module code.'
            setError(emptyDeliveryReason)
            setProgress('Aucune livraison exploitable. Le pipeline a ete stoppe avec diagnostic.')
            setRecoveryStatus(null)
            return
          }

          // Save conversation
          if (result.files.length > 0) {
            pushMessage('code', {
              role: 'assistant',
              content: serializeCodeFiles(result.files),
            })

            // AI auto-naming: rename session with a smart title (fire-and-forget)
            const session = getActiveSession('code')
            if (session.title === 'Nouvelle conversation' || session.messages.length <= 2) {
              void generateSessionTitle(
                activePrompt,
                result.intent.projectType,
                result.intent.frameworks,
              ).then((title) => {
                renameSession(session.id, title)
              })
            }
          }

          setRecoveryStatus(null)

          // Start dev server if needed
          if (result.intent.needsDevServer && result.sandboxResult?.rootPath) {
            setProgress('Demarrage du serveur de dev pour preview...')
            setPhase('Demarrage du dev server...', 95)
            const url = await startDevServer(
              result.sandboxResult.rootPath,
              result.intent,
              setDevServerState,
            )
            if (url) {
              setProgress(`Dev server pret: ${url}`)
            } else {
              setProgress('Preview live indisponible. Les fichiers restent livres pour inspection manuelle.')
            }
          }

          // Set progress message
          setProgress(
            result.sandboxResult?.ok
              ? `Livraison validee (${result.totalAttempts} passe${result.totalAttempts > 1 ? 's' : ''}, score ${result.finalScore}%).`
              : `Livraison structuree (${result.totalAttempts} passe${result.totalAttempts > 1 ? 's' : ''}, score ${result.finalScore}%). Ameliorations manuelles recommandees.`,
          )
          setPhase('Livraison terminee.', 98)

          // Propose save
          if (result.files.length > 0) {
            const fidelity = result.finalScore
            const savePayload: SaveDialogData = {
              module: 'code',
              sourcePath: result.sandboxResult?.rootPath ?? '',
              prompt: activePrompt,
              fidelityScore: fidelity,
              parameters: {
                filesCount: result.files.length,
                language: result.files[0]?.language ?? 'unknown',
                sandboxPassed: result.sandboxResult?.ok ?? false,
                projectType: result.intent.projectType,
                complexity: result.intent.complexity,
                correctionPasses: result.totalAttempts,
                devCommand: result.intent.devCommand,
                buildCommand: result.intent.buildCommand,
              },
              codeFiles: result.files.map((f) => ({ name: f.name, content: f.content })),
            }
            setSaveDialogData(savePayload)
            setSavedProjectData(savePayload)
          }
        },
      })
    } catch (generationError) {
      if (generationError instanceof Error && generationError.name === 'AbortError') {
        setProgress('Generation interrompue.')
      } else {
        setError(getErrorMessage(generationError, 'Le module code a echoue sans detail exploitable.'))
        setProgress('')
      }
    } finally {
      abortRef.current = null
      setIsGenerating(false)
      isGeneratingRef.current = false
      // CRITICAL: clear any resume reference that handleSessionChange may have
      // set during the generation (re-renders race). Without this, the
      // useEffect below would fire `generate({resumeMode:'after_reload'})`
      // right after the normal completion — which is exactly what the user
      // saw as "la page s'est relancée alors que la generation etait finie".
      resumeAfterReloadRef.current = null
      setWorkspaceSnapshot({
        sessionId: activeSession.id,
        prompt: activePrompt,
        pendingResume: false,
        resumeFailCount: 0,
        lastResumeAttempt: null,
      })
    }
  }, [activeModel, activeSession.id, contextFiles, diagnostics.blockingReason, executeWithRuntime, files, getActiveSession, getRecentMessages, isGenerating, preparePack, prompt, pushMessage, renameSession, setWorkspaceSnapshot, visionModel])

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
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden opacity-70">
        <div
          className="absolute -top-40 -left-40 h-[40rem] w-[40rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent, #e63412)) 35%, transparent) 0%, transparent 65%)', filter: 'blur(80px)' }}
        />
        <div
          className="absolute -bottom-32 right-[-10%] h-[34rem] w-[34rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--accent, var(--ft-accent-2, #f78324)) 30%, transparent) 0%, transparent 65%)', filter: 'blur(90px)' }}
        />
        <div
          className="absolute top-1/3 right-[20%] h-[22rem] w-[22rem] rounded-full"
          style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent-3, #ffd24a)) 28%, transparent) 0%, transparent 70%)', filter: 'blur(70px)' }}
        />
      </div>

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
      <StudioHero
        icon={Code2}
        eyebrow="Atelier code"
        title="Pipeline code expert, auto-correction controlee, preview live."
        description="Classification projet → planning architecture → generation modele expert → sandbox isole → gates qualite → boucle auto-correction avec recherche web → dev server preview responsive."
        diagnostics={diagnostics}
        stats={[
          { label: 'Modele', value: activeModel, tone: runtimeServices.ollama.available ? 'good' : 'warn' },
          { label: 'Ollama', value: ollamaLabel, tone: runtimeServices.ollama.running ? 'good' : runtimeServices.ollama.available ? 'default' : 'warn' },
          { label: 'Fichiers', value: `${files.length}` },
          ...(intent ? [{ label: 'Projet', value: formatProjectType(intent.projectType) }] : []),
        ]}
      />

      <div className="grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 xl:grid-cols-[23rem_minmax(0,1fr)]">
        {/* LEFT PANEL */}
        <div
          className="xl:sticky xl:top-4 self-start overflow-y-auto overscroll-contain scroll-shell max-h-[60vh] sm:max-h-[calc(100vh-12rem)] rounded-[1.4rem] sm:rounded-[1.9rem] p-3 sm:p-4 space-y-3 sm:space-y-4 backdrop-blur-2xl"
          style={{
            border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
            background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 78%, transparent))',
            boxShadow: 'var(--v4code-card-shadow, 0 8px 40px -12px color-mix(in srgb, var(--ft-ink, #1a140d) 35%, transparent))',
          }}
        >
          {/* Session switcher */}
          <SessionSwitcher module="code" onSessionChange={handleSessionChange} />

          {/* Mission */}
          <div
            className="group relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-all duration-300"
            style={{
              border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 14%, transparent))',
              background: 'var(--v4code-card-bg, linear-gradient(135deg, color-mix(in srgb, var(--ft-paper, #f3ead4) 92%, transparent) 0%, color-mix(in srgb, var(--ft-paper-3, #faf3de) 60%, transparent) 100%))',
              boxShadow: 'var(--v4code-card-inset, inset 0 1px 0 color-mix(in srgb, var(--ft-paper-3, #faf3de) 60%, transparent))',
            }}
          >
            <div
              className="pointer-events-none absolute -top-8 -right-8 h-32 w-32 rounded-full blur-2xl opacity-60 group-hover:opacity-90 transition-opacity duration-500"
              style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent-2, #f78324)) 50%, transparent) 0%, transparent 70%)' }}
            />
            <div className="relative flex items-start justify-between gap-3">
              <div>
                <p
                  className="text-[10px] uppercase tracking-[0.28em] font-semibold"
                  style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
                >
                  Mission
                </p>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: 'var(--fg, color-mix(in srgb, var(--ft-ink, #1a140d) 95%, transparent))' }}
                >
                  Donne le livrable, la stack, les contraintes et le niveau de finition attendu.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPromptLibraryOpen(true)}
                  title="Bibliotheque de prompts"
                  className="flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 20%, transparent))',
                    background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper-3, #faf3de) 70%, transparent))',
                    color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 60%, transparent))',
                  }}
                >
                  <BookOpen size={14} />
                </button>
                <div
                  className="relative flex h-11 w-11 items-center justify-center rounded-2xl text-white shadow-lg transition-transform duration-300 group-hover:scale-105"
                  style={{
                    background: 'var(--v4code-accent-grad, linear-gradient(135deg, var(--ft-accent, #e63412) 0%, var(--ft-accent-2, #f78324) 60%, var(--ft-accent-3, #ffd24a) 100%))',
                    boxShadow: 'var(--v4code-accent-shadow, 0 8px 22px -6px color-mix(in srgb, var(--ft-accent, #e63412) 65%, transparent))',
                  }}
                >
                  <Sparkles size={18} className="relative" />
                </div>
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ex: Dashboard React multi-page avec auth JWT, CRUD utilisateurs, graphiques recharts, dark mode, responsive. Ou: API FastAPI complete avec PostgreSQL, JWT, Docker."
              rows={7}
              className="relative mt-4 w-full resize-none rounded-2xl px-3.5 py-3 text-sm outline-none transition-all duration-200"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                background: 'var(--bg-input, color-mix(in srgb, var(--ft-paper, #f3ead4) 70%, transparent))',
                color: 'var(--fg, var(--ft-ink, #1a140d))',
              }}
            />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}\n${text}` : text))}
                label="Dicter le brief du projet"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Dicte ton brief — la transcription s'ajoute à la fin.</span>
            </div>
          </div>

          {/* Brief guide */}
          <div
            className="rounded-[1.5rem] p-4 backdrop-blur-xl"
            style={{
              border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
              background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
            }}
          >
            <div
              className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
              style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
            >
              <ScanSearch size={13} />
              <span>Guide de brief</span>
            </div>
            <div className="mt-3 space-y-2">
              {promptGuide.map((item) => (
                <div
                  key={item}
                  className="rounded-2xl px-3 py-3 text-xs leading-relaxed transition-colors"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 10%, transparent))',
                    background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 65%, transparent))',
                    color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 80%, transparent))',
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute captures d ecran, PDF, textes ou tableurs pour guider la generation."
          />

          <ModuleAssetPackCard pack={assetPack} />

          {/* Runtime + Pipeline info */}
          <div className="grid grid-cols-2 gap-3">
            <div
              className="group/card relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
                background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
              }}
            >
              <div
                className="absolute -top-6 -right-6 h-20 w-20 rounded-full blur-2xl opacity-60 transition-opacity duration-500 group-hover/card:opacity-90"
                style={{
                  background: runtimeServices.ollama.running
                    ? 'color-mix(in srgb, var(--aura-code, var(--ft-accent-3, #ffd24a)) 50%, transparent)'
                    : 'color-mix(in srgb, var(--accent, var(--ft-accent-2, #f78324)) 40%, transparent)',
                }}
              />
              <div
                className="relative flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
                style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
              >
                <Bot size={13} />
                <span>Runtime</span>
              </div>
              <p className="relative mt-2 text-sm" style={{ color: 'var(--fg, var(--ft-ink, #1a140d))' }}>
                {runtimeServices.ollama.running
                  ? 'Serveur et modele actifs.'
                  : 'Demarrage automatique a la demande.'}
              </p>
            </div>

            <div
              className="group/card relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
                background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
              }}
            >
              <div
                className="absolute -top-6 -right-6 h-20 w-20 rounded-full blur-2xl opacity-60 transition-opacity duration-500 group-hover/card:opacity-90"
                style={{ background: 'color-mix(in srgb, var(--accent, var(--ft-accent, #e63412)) 35%, transparent)' }}
              />
              <div
                className="relative flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
                style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
              >
                <Workflow size={13} />
                <span>Pipeline</span>
              </div>
              <p className="relative mt-2 text-[11px] leading-relaxed" style={{ color: 'var(--fg, var(--ft-ink, #1a140d))' }}>{pipelineLabel}</p>
            </div>
          </div>

          {/* Intent panel (shows after classification) */}
          {intent && (
            <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">
                <Code2 size={13} />
                <span>Projet detecte</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-aurora-text-dim">Type: </span>
                  <span className="text-aurora-text">{formatProjectType(intent.projectType)}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">Complexite: </span>
                  <span className="text-aurora-text">{intent.complexity}</span>
                </div>
                {intent.frameworks.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Frameworks: </span>
                    <span className="text-aurora-text">{intent.frameworks.join(', ')}</span>
                  </div>
                )}
                {intent.gameKind && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Mode jeu: </span>
                    <span className="text-aurora-text">
                      {intent.gameKind === 'clone' && intent.knownGame
                        ? `Clone de ${intent.knownGame.canonical}`
                        : intent.gameKind === 'creative'
                          ? '✦ Création originale'
                          : 'Jeu générique'}
                    </span>
                  </div>
                )}
                {intent.features.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Features: </span>
                    <span className="text-aurora-text">{intent.features.join(', ')}</span>
                  </div>
                )}
                <div>
                  <span className="text-aurora-text-dim">Preview: </span>
                  <span className="text-aurora-text">{intent.previewType.replace(/_/g, ' ')}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">~Fichiers: </span>
                  <span className="text-aurora-text">{intent.estimatedFileCount}</span>
                </div>
              </div>
              {intent.needsDevServer && (
                <div className="flex items-center gap-1.5 text-[11px] text-aurora-accent-light">
                  <Globe size={11} />
                  <span>Dev server: {intent.devCommand}</span>
                </div>
              )}
            </div>
          )}

          {preflightReport && (
            <div className="rounded-[1.5rem] border border-sky-400/20 bg-sky-400/10 px-4 py-3 space-y-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-sky-300">
                <ScanSearch size={13} />
                <span>Preflight local</span>
              </div>
              <p className="text-xs leading-relaxed text-aurora-text">{preflightReport.summary}</p>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-aurora-text-dim">Stack: </span>
                  <span className="text-aurora-text">{preflightReport.chosenStack}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">PM: </span>
                  <span className="text-aurora-text">{preflightReport.packageManager || 'aucun'}</span>
                </div>
              </div>
              {preflightReport.mustInspectFirst.length > 0 && (
                <p className="text-[11px] leading-relaxed text-aurora-text-muted">
                  A inspecter d abord: {preflightReport.mustInspectFirst.slice(0, 4).join(', ')}
                </p>
              )}
              {preflightReport.localConstraints.length > 0 && (
                <p className="text-[11px] leading-relaxed text-aurora-text-muted">
                  Contraintes locales: {preflightReport.localConstraints.slice(0, 2).join(' | ')}
                </p>
              )}
            </div>
          )}

          {/* Dev server status */}
          {devServerState.running && devServerState.url && (
            <div className="rounded-[1.5rem] border border-green-500/25 bg-green-500/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] text-green-400">
                <Globe size={13} />
                <span>Dev server actif: {devServerState.url}</span>
              </div>
            </div>
          )}

          {/* Correction log */}
          <CodeCorrectionLog
            correctionLog={correctionLog}
            intent={intent}
            totalAttempts={totalAttempts}
            finalScore={finalScore}
            isRunning={isGenerating}
          />

          {/* v73: design polish badge — only for visual projects, gives the
              user a one-glance signal of whether the LLM produced premium
              CSS or just a stub. Click to expand the missing-checks list. */}
          {designReport && (
            <details className="rounded-[1.5rem] border border-purple-500/25 bg-gradient-to-br from-purple-500/8 to-pink-500/5 px-4 py-3">
              <summary className="cursor-pointer flex items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="text-purple-300">{designReport.score >= 80 ? '✨' : designReport.score >= 60 ? '🎨' : '⚠'}</span>
                  <span className="text-aurora-text">Design polish</span>
                  <span className={`font-semibold ${designReport.score >= 80 ? 'text-emerald-300' : designReport.score >= 60 ? 'text-amber-300' : 'text-rose-300'}`}>
                    {designReport.score}/100
                  </span>
                </div>
                <span className="text-[10px] text-aurora-text-muted">
                  {designReport.score >= 80 ? 'premium' : designReport.score >= 60 ? 'correct' : 'a refaire'}
                </span>
              </summary>
              {(designReport.missing.length > 0 || designReport.penalties.length > 0) && (
                <div className="mt-3 space-y-2 text-[10.5px] text-aurora-text-muted">
                  {designReport.missing.length > 0 && (
                    <div>
                      <div className="text-amber-300 font-semibold mb-1">Manquant ({designReport.missing.length})</div>
                      <ul className="space-y-0.5 pl-3 list-disc">
                        {designReport.missing.slice(0, 6).map((m, i) => <li key={i}>{m}</li>)}
                      </ul>
                    </div>
                  )}
                  {designReport.penalties.length > 0 && (
                    <div>
                      <div className="text-rose-300 font-semibold mb-1">Penalites ({designReport.penalties.length})</div>
                      <ul className="space-y-0.5 pl-3 list-disc">
                        {designReport.penalties.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </details>
          )}

          {/* Conversation context — enriched with mode + last 2 turns */}
          {hasConversation && (
            <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[11px] text-aurora-accent-light">
                  <MessageSquare size={13} />
                  <span>Discussion active ({conversationTurns} tour{recentMessages.length > 2 ? 's' : ''})</span>
                </div>
                <button
                  onClick={clearConversation}
                  className="text-[10px] uppercase tracking-wider text-aurora-text-muted hover:text-aurora-text transition-colors"
                  title="Effacer la discussion et repartir a zero"
                >
                  Reset
                </button>
              </div>
              {followUpAnalysis && (
                <div className={`rounded-xl px-2.5 py-1.5 text-[11px] ${
                  followUpAnalysis.kind === 'pivot_platform' ? 'border border-amber-400/30 bg-amber-400/10 text-amber-200'
                  : followUpAnalysis.kind === 'fresh_start' ? 'border border-sky-400/30 bg-sky-400/10 text-sky-200'
                  : followUpAnalysis.kind === 'pivot_feature' ? 'border border-violet-400/30 bg-violet-400/10 text-violet-200'
                  : 'border border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                }`}>
                  <span className="font-semibold">
                    {followUpAnalysis.kind === 'pivot_platform' ? 'Mode: Pivot plateforme'
                    : followUpAnalysis.kind === 'pivot_feature' ? 'Mode: Pivot fonctionnel'
                    : followUpAnalysis.kind === 'fresh_start' ? 'Mode: Nouveau projet'
                    : followUpAnalysis.kind === 'clarify_only' ? 'Mode: Clarification'
                    : 'Mode: Patch incremental'}
                  </span>
                  {followUpAnalysis.pivotReason && (
                    <span className="ml-1 opacity-80">— {followUpAnalysis.pivotReason.slice(0, 80)}</span>
                  )}
                </div>
              )}
              {recentMessages.length > 0 && (
                <div className="space-y-1">
                  {recentMessages.slice(-4).map((msg, idx) => {
                    const preview = (msg.content || '').replace(/\s+/g, ' ').slice(0, 110)
                    const isUser = msg.role === 'user'
                    return (
                      <div key={idx} className="text-[10px] leading-snug">
                        <span className={isUser ? 'text-aurora-cyan' : 'text-aurora-accent-light'}>
                          {isUser ? 'Toi:' : 'IA:'}
                        </span>{' '}
                        <span className="text-aurora-text-muted">{preview}{preview.length >= 110 ? '...' : ''}</span>
                      </div>
                    )
                  })}
                </div>
              )}
              <p className="text-[10px] text-aurora-text-muted">
                Tape une suite (&laquo;ajoute un bouton&raquo;, &laquo;la m&ecirc;me chose en Python&raquo;...). Le prompt se conserve apr&egrave;s g&eacute;n&eacute;ration.
              </p>
            </div>
          )}

          {/* Recovery status */}
          {recoveryStatus && (
            <div className="rounded-[1.5rem] border border-aurora-yellow/25 bg-aurora-yellow/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] text-aurora-yellow">
                <Loader2 size={13} className="animate-spin" />
                <span>Auto-reparation: {recoveryStatus}</span>
              </div>
            </div>
          )}

          {savedProjectData && (
            <div className="rounded-[1.5rem] border border-aurora-accent/25 bg-aurora-accent/8 p-4 space-y-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">
                <Archive size={13} />
                <span>Export persistant</span>
              </div>
              <p className="text-xs leading-relaxed text-aurora-text-muted">
                Les boutons restent disponibles meme si tu as ferme la popup finale. Le projet exporte inclut aussi `lancement.bat` quand un demarrage automatique est possible.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => void handlePersistentSave('workspace')}
                  disabled={saveTarget !== null}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border/35 bg-aurora-surface/70 px-3 py-3 text-sm text-aurora-text transition-colors hover:border-aurora-accent/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saveTarget === 'workspace' ? <Loader2 size={15} className="animate-spin" /> : <FolderOpen size={15} />}
                  <span>Workspace</span>
                </button>
                <button
                  onClick={() => void handlePersistentSave('zip')}
                  disabled={saveTarget !== null}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border/35 bg-aurora-surface/70 px-3 py-3 text-sm text-aurora-text transition-colors hover:border-aurora-accent/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saveTarget === 'zip' ? <Loader2 size={15} className="animate-spin" /> : <Archive size={15} />}
                  <span>ZIP</span>
                </button>
              </div>
              {savedProjectPath && (
                <p className="text-[11px] leading-relaxed text-aurora-text-dim break-all">
                  Derniere sauvegarde: {savedProjectPath}
                </p>
              )}
              {saveFeedback && (
                <p className="text-[11px] leading-relaxed text-aurora-red break-all">
                  {saveFeedback}
                </p>
              )}
            </div>
          )}

          {/* Generate / Stop buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => void generate()}
              disabled={!canGenerate}
              className={`group/btn relative flex-1 inline-flex items-center justify-center gap-2 overflow-hidden rounded-[1.4rem] px-4 py-3.5 text-sm font-bold tracking-wide transition-all duration-300 ${
                canGenerate
                  ? 'text-white hover:scale-[1.015] active:scale-[0.99]'
                  : 'opacity-60 cursor-not-allowed'
              }`}
              style={canGenerate ? {
                background: 'var(--v4code-accent-grad, linear-gradient(135deg, var(--ft-accent, #e63412) 0%, var(--ft-accent-2, #f78324) 55%, var(--ft-accent-3, #ffd24a) 100%))',
                boxShadow: 'var(--v4code-accent-shadow-lg, 0 8px 32px -8px color-mix(in srgb, var(--ft-accent, #e63412) 55%, transparent), 0 1px 0 color-mix(in srgb, var(--ft-accent-3, #ffd24a) 40%, transparent) inset)',
                fontFamily: 'var(--font-display, "Bangers", Impact, sans-serif)',
                letterSpacing: '0.08em',
                fontSize: '0.95rem',
              } : {
                background: 'color-mix(in srgb, var(--fg, var(--ft-ink, #1a140d)) 6%, transparent)',
                color: 'var(--fg-mute, color-mix(in srgb, var(--ft-ink, #1a140d) 35%, transparent))',
              }}
            >
              {canGenerate && (
                <span
                  className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover/btn:translate-x-full"
                  aria-hidden
                />
              )}
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="relative animate-spin" />
                  <span className="relative">
                    {progress || 'Generation...'}
                    {streamCharsTotal > 0 && (
                      <span className="ml-2 text-xs opacity-70">
                        · {(streamCharsTotal / 1000).toFixed(1)}k chars
                      </span>
                    )}
                  </span>
                </>
              ) : (
                <>
                  <Play size={18} className="relative" />
                  <span className="relative">{hasConversation ? 'Continuer' : 'Generer'}</span>
                </>
              )}
            </button>

            <button
              onClick={stopGeneration}
              disabled={!isGenerating}
              className={`inline-flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-colors ${
                isGenerating
                  ? 'border border-aurora-red/30 bg-aurora-red/12 text-aurora-red'
                  : 'border border-aurora-border/35 bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
              }`}
            >
              <StopCircle size={18} />
              <span>Stop</span>
            </button>
          </div>

          {/* "Inspecter design" — v69: affiche le score + missing + penalties
              sans regenerer. Pratique pour comprendre POURQUOI le design
              n est pas pousse avant de cliquer "Refaire". */}
          {files.length > 0 && !isGenerating && (
            <button
              onClick={async () => {
                const { computeDesignPolishReportPublic } = await import('../services/codeOrchestrator')
                const report = computeDesignPolishReportPublic(files)
                const status = report.score >= 80 ? '✅ Premium' : report.score >= 70 ? '🟢 Bon' : report.score >= 50 ? '🟠 Moyen' : '🔴 Scolaire'
                const summary = [
                  `${status} — ${report.score}/100 (seuil premium 70)`,
                  '',
                  ...(report.missing.length > 0 ? ['Patterns MANQUANTS:', ...report.missing.map((m) => `  ✗ ${m}`)] : ['Tous les patterns essentiels detectes ✓']),
                  ...(report.penalties.length > 0 ? ['', 'Defauts trouves:', ...report.penalties.map((p) => `  ⚠ ${p}`)] : []),
                ].join('\n')
                window.alert(summary)
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[1.4rem] border px-4 py-2.5 text-xs font-medium transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper-3, #faf3de) 65%, transparent))',
                color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 75%, transparent))',
              }}
              title="Audit le design des fichiers generes (score 0-100, missing patterns, penalties) sans regenerer."
            >
              🔍 Inspecter design
            </button>
          )}

          {/* "Refaire en plus pousse" — v69: maintenant intelligent. Au lieu
              d un texte boost generique, calcule le DesignPolishReport sur
              les fichiers existants et envoie au LLM la liste exacte des
              patterns manquants + penalties detectees. Le LLM regenere avec
              une cible precise au lieu d un vague "fais plus pousse". */}
          {files.length > 0 && !isGenerating && (
            <button
              onClick={async () => {
                // Lazy-import pour eviter d alourdir le bundle initial
                const { computeDesignPolishReportPublic } = await import('../services/codeOrchestrator')
                const report = computeDesignPolishReportPublic(files)
                const lines: string[] = [
                  `Refais le projet en CORRIGEANT EXACTEMENT ces points (audit design ${report.score}/100 — seuil 70):`,
                ]
                if (report.missing.length > 0) {
                  lines.push('', 'Patterns MANQUANTS a ajouter imperativement:')
                  for (const m of report.missing) lines.push(`  ✗ ${m}`)
                }
                if (report.penalties.length > 0) {
                  lines.push('', 'Defauts a corriger:')
                  for (const p of report.penalties) lines.push(`  ⚠ ${p}`)
                }
                lines.push(
                  '',
                  'Refais le projet COMPLET en respectant maintenant TOUS ces points.',
                  '',
                  `Demande originale:\n${prompt || (files[0]?.content?.slice(0, 200) ?? 'meme projet')}`
                )
                setPrompt(lines.join('\n'))
                void generate()
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[1.4rem] border px-4 py-3 text-sm font-medium transition-colors"
              style={{
                border: '1px solid color-mix(in srgb, var(--aura-code, var(--ft-accent, #e63412)) 35%, transparent)',
                background: 'var(--v4code-accent-soft-grad, linear-gradient(135deg, color-mix(in srgb, var(--ft-accent-2, #f78324) 14%, transparent), color-mix(in srgb, var(--ft-accent-3, #ffd24a) 8%, transparent)))',
                color: 'var(--fg, var(--ft-ink, #1a140d))',
              }}
              title="Audit le design genere et regenere avec correction ciblee des patterns manquants (score, missing, penalties)."
            >
              ✨ Refaire en plus poussé (audit design)
            </button>
          )}

          {/* Status / Error */}
          {(progress || error) && (
            <div className="space-y-3">
              {progress && (
                <div className="rounded-[1.5rem] border border-aurora-border/40 bg-aurora-surface/70 px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Etat courant</p>
                  <p className="mt-2 text-sm text-aurora-text">{progress}</p>
                </div>
              )}
              {error && (
                <div className="flex items-start gap-2 rounded-[1.5rem] border border-aurora-red/25 bg-aurora-red/10 px-3 py-3">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-aurora-red" />
                  <p className="text-xs leading-relaxed text-aurora-red">{error}</p>
                </div>
              )}
            </div>
          )}

          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight code" />
          <ConnectorRecommendationsPanel module="code" compact />
        </div>

        {/* RIGHT PANEL — Code output */}
        <div
          className="min-w-0 overflow-hidden rounded-[1.9rem] backdrop-blur-2xl"
          style={{
            border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 16%, transparent))',
            background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 75%, transparent))',
            boxShadow: 'var(--v4code-card-shadow, 0 12px 50px -15px color-mix(in srgb, var(--ft-ink, #1a140d) 45%, transparent), inset 0 1px 0 color-mix(in srgb, var(--ft-paper, #f3ead4) 70%, transparent))',
          }}
        >
          <div className="border-b border-aurora-border/30 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Livraison</p>
                <h2 className="mt-1 text-lg font-semibold text-aurora-text">Scene code</h2>
              </div>

              {activeFileData && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={copyCurrentFile}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Copier le fichier dans le presse-papiers"
                  >
                    {copied ? <Check size={14} className="text-aurora-green" /> : <Clipboard size={14} />}
                    <span>{copied ? 'Copie' : 'Copier'}</span>
                  </button>
                  <button
                    onClick={() => {
                      if (!activeFileData) return
                      const blob = new Blob([activeFileData.content], { type: 'text/plain;charset=utf-8' })
                      const url = URL.createObjectURL(blob)
                      const anchor = document.createElement('a')
                      anchor.href = url
                      anchor.download = activeFileData.name.split('/').pop() || 'file.txt'
                      anchor.click()
                      setTimeout(() => URL.revokeObjectURL(url), 1000)
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Telecharger ce fichier"
                  >
                    <Download size={14} />
                    <span>Download</span>
                  </button>
                  <button
                    onClick={() => setShowLineNumbers((v) => !v)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-colors ${
                      showLineNumbers ? 'border-aurora-accent/40 bg-aurora-accent/10 text-aurora-accent' : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                    }`}
                    title="Afficher/masquer les numeros de ligne"
                  >
                    # Lignes
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="grid min-h-[34rem] gap-4 p-5 xl:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
            {/* File tree + Preview */}
            <div className="min-h-0 flex flex-col gap-4">
              <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3">
                <div className="flex items-center gap-2 px-2 pb-3 text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
                  <FileCode2 size={13} />
                  <span>Fichiers ({files.length})</span>
                </div>

                <CodeFileTree
                  files={files}
                  activeFile={activeFile}
                  onSelectFile={setActiveFile}
                />
              </div>

              {activeFileData && (
                <>
                  <CodeLanguageChip
                    fileName={activeFileData.name}
                    declaredLang={activeFileData.language}
                    content={activeFileData.content}
                  />
                  <CodeCritiquePanel content={activeFileData.content} language={activeFileData.language ?? activeFileData.name} />
                  <CodeLyraCommentator
                    content={activeFileData.content}
                    language={activeFileData.language ?? activeFileData.name}
                    isGenerating={isGenerating}
                  />
                </>
              )}

              <CodeConsolePanel
                consoleOutput={consoleOutput}
                streamContent={streamPreview}
                isGenerating={isGenerating}
                recoveryStatus={recoveryStatus}
                progress={progress}
                errorMessage={error}
                sandboxOk={validationResult?.ok ?? null}
              />

              {intent?.previewType === 'dev_server' && devServerState?.running && devServerState.url && (
                <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px] text-aurora-text-dim">
                  <div className="flex items-center gap-2 uppercase tracking-[0.2em]">
                    <Globe size={13} />
                    <span>Dev server actif</span>
                  </div>
                  <a
                    href={devServerState.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 block truncate text-aurora-accent-light hover:underline"
                  >
                    {devServerState.url}
                  </a>
                </div>
              )}
            </div>

            {/* Code viewer */}
            <div className="min-h-0 overflow-hidden rounded-[1.6rem] border border-aurora-border/35 bg-[#091116]">
              <div className="border-b border-aurora-border/25 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
                      {bigViewMode === 'preview' ? '🎬 Simulateur live' : '📝 Code source'}
                    </p>
                    <p className="mt-1 text-sm text-aurora-text">
                      {bigViewMode === 'preview'
                        ? (isGenerating ? 'La page se construit a mesure que le code arrive' : files.length > 0 ? 'Apercu interactif de l app — clique-toi dedans' : 'Lance une generation pour voir l apercu se construire en direct')
                        : (activeFileData?.name || (isGenerating ? 'Streaming en direct' : 'En attente de generation'))}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center rounded-lg border border-aurora-border/35 bg-aurora-surface-2/60 p-0.5">
                      <button
                        onClick={() => setBigViewMode('code')}
                        title="Voir le code en cours d ecriture"
                        className={`flex h-7 items-center gap-1 rounded-md px-2.5 text-[11px] transition-colors ${
                          bigViewMode === 'code'
                            ? 'bg-aurora-accent/20 text-aurora-accent-light'
                            : 'text-aurora-text-dim hover:text-aurora-text'
                        }`}
                      >
                        <Code2 size={12} />
                        <span>Code</span>
                      </button>
                      <button
                        onClick={() => setBigViewMode('preview')}
                        title="Simulateur live — apercu interactif de l app/web en cours de generation"
                        className={`flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium transition-colors ${
                          bigViewMode === 'preview'
                            ? 'bg-aurora-accent/20 text-aurora-accent-light shadow-[inset_0_0_0_1px_rgba(251,146,60,0.35)]'
                            : 'text-aurora-text-dim hover:text-aurora-text'
                        }`}
                      >
                        <Eye size={12} />
                        <span>Simulateur</span>
                      </button>
                    </div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-aurora-border/35 bg-aurora-surface/60 px-3 py-1.5 text-[11px] text-aurora-text-dim">
                      <Sparkles size={12} />
                      <span>{files.length > 0 ? `${files.length} fichier(s)` : isGenerating ? 'Streaming...' : 'Aucun fichier livre'}</span>
                      {isGenerating && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-aurora-accent/15 px-1.5 text-[9px] text-aurora-accent-light">
                          <span className="h-1.5 w-1.5 rounded-full bg-aurora-accent animate-pulse" />
                          Live
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {bigViewMode === 'code' && activeFileData && (
                <div className="flex items-center gap-2 border-b border-aurora-border/25 bg-aurora-surface/30 px-4 py-2">
                  <Search size={12} className="text-aurora-text-dim" />
                  <input
                    value={fileSearch}
                    onChange={(event) => setFileSearch(event.target.value)}
                    placeholder="Chercher dans ce fichier (case insensitive)..."
                    className="min-w-0 flex-1 bg-transparent text-[11px] text-aurora-text outline-none placeholder:text-aurora-text-dim"
                  />
                  {fileSearch && (
                    <>
                      <span className="text-[10px] text-aurora-text-dim">
                        {(() => {
                          try {
                            const re = new RegExp(fileSearch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
                            const matches = activeFileData.content.match(re)
                            return `${matches?.length ?? 0} match(s)`
                          } catch {
                            return '0 match'
                          }
                        })()}
                      </span>
                      <button
                        onClick={() => setFileSearch('')}
                        className="text-[10px] text-aurora-text-dim hover:text-aurora-text"
                      >
                        Clear
                      </button>
                    </>
                  )}
                </div>
              )}

              <div className="min-h-[28rem] overflow-auto">
                {bigViewMode === 'preview' ? (
                  <BigLivePreviewFrame
                    files={files}
                    streamContent={streamPreview}
                    isGenerating={isGenerating}
                    iframeRef={bigPreviewIframeRef}
                    viewport={bigViewport}
                    onViewportChange={setBigViewport}
                  />
                ) : activeFileData ? (
                  <Suspense fallback={<pre className="px-5 py-5 text-[13px] text-aurora-text-dim">Chargement du highlighter...</pre>}>
                    <CodeBlock
                      code={activeFileData.content}
                      language={activeFileData.language ?? activeFileData.name}
                      showLineNumbers={showLineNumbers}
                      search={fileSearch}
                    />
                  </Suspense>
                ) : streamPreview ? (
                  <div className="px-5 py-5">
                    <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-aurora-accent/20 bg-aurora-accent/10 px-3 py-1.5 text-[11px] text-aurora-accent-light">
                      <Loader2 size={12} className="animate-spin" />
                      <span>Streaming du modele</span>
                    </div>
                    <pre className="text-[13px] leading-6 text-aurora-text whitespace-pre-wrap">
                      <code>{streamPreview}</code>
                    </pre>
                  </div>
                ) : (
                  <div className="grid h-full place-items-center p-6">
                    <div className="max-w-lg text-center">
                      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[1.8rem] border border-aurora-border/35 bg-aurora-surface-2">
                        <Code2 size={30} className="text-aurora-text-dim" />
                      </div>
                      <p className="mt-4 text-sm text-aurora-text">
                        Donne une mission code pour activer le pipeline expert avec auto-correction.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Validation result */}
          <AnimatePresence>
            {validationResult && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className="border-t border-aurora-border/30 px-5 py-4"
              >
                <div className={`rounded-[1.4rem] border px-4 py-4 ${
                  validationResult.ok
                    ? 'border-aurora-green/25 bg-aurora-green/10'
                    : 'border-aurora-red/25 bg-aurora-red/10'
                }`}>
                  <div className="flex items-center justify-between">
                    <p className={`text-[11px] uppercase tracking-[0.22em] ${
                      validationResult.ok ? 'text-aurora-green' : 'text-aurora-red'
                    }`}>Sandbox</p>
                    {validationResult.detectedLanguage && (
                      <span className="rounded-full border border-aurora-border/30 bg-aurora-surface-2/50 px-2 py-0.5 text-[10px] text-aurora-text-dim">
                        {validationResult.detectedLanguage}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-aurora-text">{validationResult.summary}</p>
                  <p className="mt-2 text-xs text-aurora-text-dim">{validationResult.rootPath}</p>

                  {validationResult.steps.length > 0 && (
                    <div className="mt-4 space-y-3">
                      {validationResult.steps.map((step) => (
                        <div key={`${step.label}-${step.command}`} className="rounded-2xl border border-aurora-border/30 bg-aurora-surface/50 px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm text-aurora-text">{step.label}</p>
                            <span className={`text-[11px] ${step.ok ? 'text-aurora-green' : 'text-aurora-red'}`}>
                              {step.ok ? 'OK' : 'ECHEC'}
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-aurora-text-dim">{step.command}</p>
                          {step.output && (
                            <pre className="mt-3 overflow-auto rounded-xl border border-aurora-border/25 bg-[#091116] px-3 py-3 text-[11px] leading-5 text-aurora-text-dim whitespace-pre-wrap max-h-32">
                              <code>{step.output}</code>
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {validationResult.question && (
                    <p className="mt-4 text-sm leading-relaxed text-aurora-text">{validationResult.question}</p>
                  )}
                </div>
              </motion.div>
            )}
            {notes && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className="border-t border-aurora-border/30 px-5 py-4"
              >
                <div className="rounded-[1.4rem] border border-aurora-yellow/25 bg-aurora-yellow/10 px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-yellow">Notes</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-aurora-text">{notes}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Code console panel — small left-side panel that replaces the old mini
// preview. Shows tokens-as-they-stream, sandbox output, errors, recovery and
// progress. The HTML render lives in the BIG viewer on the right.
// ---------------------------------------------------------------------------

type StepEntry = {
  ts: number
  message: string
  kind: 'info' | 'recover' | 'error' | 'success'
}

function CodeConsolePanel({
  consoleOutput,
  streamContent,
  isGenerating,
  recoveryStatus,
  progress,
  errorMessage,
  sandboxOk,
}: {
  consoleOutput: string
  streamContent: string
  isGenerating: boolean
  recoveryStatus: string | null
  progress: string
  errorMessage: string | null
  sandboxOk: boolean | null
}) {
  const [tab, setTab] = useState<'etapes' | 'sandbox' | 'erreurs'>('etapes')
  const [steps, setSteps] = useState<StepEntry[]>([])
  const logRef = useRef<HTMLPreElement>(null)
  const stepsRef = useRef<HTMLDivElement>(null)

  // Pipeline step journal — dedup consecutive duplicates, cap to last 60 entries.
  useEffect(() => {
    if (!progress) return
    setSteps((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.message === progress) return prev
      const kind: StepEntry['kind'] = 'info'
      const next = [...prev, { ts: Date.now(), message: progress, kind }]
      return next.slice(-60)
    })
  }, [progress])

  useEffect(() => {
    if (!recoveryStatus) return
    setSteps((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.message === recoveryStatus) return prev
      const entry: StepEntry = { ts: Date.now(), message: recoveryStatus, kind: 'recover' }
      return [...prev, entry].slice(-60)
    })
  }, [recoveryStatus])

  useEffect(() => {
    if (!errorMessage) return
    setSteps((prev) => {
      const entry: StepEntry = { ts: Date.now(), message: errorMessage, kind: 'error' }
      return [...prev, entry].slice(-60)
    })
    setTab('erreurs')
  }, [errorMessage])

  useEffect(() => {
    if (sandboxOk === true) {
      setSteps((prev) => {
        const entry: StepEntry = { ts: Date.now(), message: 'Sandbox: validation reussie.', kind: 'success' }
        return [...prev, entry].slice(-60)
      })
    }
  }, [sandboxOk])

  // Reset journal each time a new generation starts from an idle state.
  const prevGenerating = useRef(false)
  useEffect(() => {
    if (isGenerating && !prevGenerating.current) setSteps([])
    prevGenerating.current = isGenerating
  }, [isGenerating])

  useEffect(() => {
    if (tab === 'etapes' && stepsRef.current) stepsRef.current.scrollTop = stepsRef.current.scrollHeight
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [steps, consoleOutput, errorMessage, tab])

  const sandboxTail = consoleOutput.length > 40_000
    ? `${consoleOutput.slice(0, 10_000)}\n...[tronque]...\n${consoleOutput.slice(-20_000)}`
    : consoleOutput

  const pillColor = errorMessage
    ? 'bg-aurora-red/20 text-aurora-red'
    : sandboxOk === true
      ? 'bg-aurora-green/20 text-aurora-green'
      : isGenerating
        ? 'bg-aurora-accent/20 text-aurora-accent-light'
        : 'bg-aurora-surface-2/60 text-aurora-text-dim'

  const hasError = Boolean(errorMessage)
  // The big viewer already shows the token stream as it is written (mode Code),
  // so the console intentionally does NOT duplicate that firehose of characters.
  // It shows WHAT the orchestrator is doing, WHY it might be slow, and WHERE it failed.
  const tokenHint = streamContent.length > 0
    ? `${Math.round(streamContent.length / 100) / 10}k chars dans le stream — voir le code en direct dans l onglet Code du grand viewer.`
    : ''

  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-[#0d1117] overflow-hidden flex flex-col min-h-[18rem]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${isGenerating ? 'bg-aurora-accent animate-pulse' : hasError ? 'bg-aurora-red' : sandboxOk ? 'bg-aurora-green' : 'bg-aurora-text-dim'}`} />
          <span>Journal</span>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${pillColor}`}>
          {hasError ? 'ERR' : sandboxOk === true ? 'OK' : isGenerating ? 'LIVE' : 'IDLE'}
        </span>
      </div>

      <div className="flex items-center gap-1 border-b border-white/10 bg-[#0a0f14] px-2 py-1.5">
        {(['etapes', 'sandbox', 'erreurs'] as const).map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-2 py-1 text-[10px] uppercase tracking-wider transition-colors ${
              tab === key
                ? 'bg-aurora-accent/20 text-aurora-accent-light'
                : 'text-aurora-text-dim hover:text-aurora-text'
            }`}
          >
            {key === 'etapes' ? 'Etapes' : key === 'sandbox' ? 'Sandbox' : 'Erreurs'}
            {key === 'erreurs' && hasError && (
              <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-aurora-red" />
            )}
          </button>
        ))}
      </div>

      {tab === 'etapes' && (
        <div ref={stepsRef} className="flex-1 overflow-auto px-2 py-2 text-[10.5px] leading-[1.5] max-h-[26rem] space-y-1">
          {steps.length === 0 && (
            <div className="px-2 py-4 text-aurora-text-dim">
              {isGenerating ? 'Demarrage du pipeline...' : 'Lance une generation pour voir les etapes du pipeline ici.'}
            </div>
          )}
          {steps.map((entry, i) => {
            const color = entry.kind === 'error'
              ? 'border-aurora-red/30 bg-aurora-red/10 text-aurora-red'
              : entry.kind === 'recover'
                ? 'border-aurora-yellow/30 bg-aurora-yellow/10 text-aurora-yellow'
                : entry.kind === 'success'
                  ? 'border-aurora-green/30 bg-aurora-green/10 text-aurora-green'
                  : 'border-aurora-border/30 bg-aurora-surface-2/40 text-aurora-text'
            const time = new Date(entry.ts).toLocaleTimeString('fr-FR', { hour12: false })
            return (
              <div key={i} className={`rounded-lg border px-2 py-1 ${color}`}>
                <div className="flex items-start gap-2">
                  <span className="shrink-0 text-[9px] opacity-60 mt-0.5">{time}</span>
                  <span className="flex-1 break-words">{entry.message}</span>
                </div>
              </div>
            )
          })}
          {tokenHint && (
            <div className="px-2 pt-2 text-[9.5px] text-aurora-text-dim italic">{tokenHint}</div>
          )}
        </div>
      )}

      {tab === 'sandbox' && (
        <pre
          ref={logRef}
          className="flex-1 overflow-auto px-3 py-2 text-[10.5px] leading-[1.45] text-gray-200 whitespace-pre-wrap break-words font-mono max-h-[26rem]"
        >
          {sandboxTail || 'Aucune sortie sandbox pour le moment.'}
        </pre>
      )}

      {tab === 'erreurs' && (
        <pre
          ref={logRef}
          className="flex-1 overflow-auto px-3 py-2 text-[10.5px] leading-[1.45] text-aurora-red whitespace-pre-wrap break-words font-mono max-h-[26rem]"
        >
          {errorMessage || 'Aucune erreur pour le moment.'}
        </pre>
      )}

      {(progress || recoveryStatus) && (
        <div className="border-t border-white/10 px-3 py-1.5 text-[10px] text-aurora-text-dim truncate">
          {recoveryStatus ? `↺ ${recoveryStatus}` : progress}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Big live preview frame — dedicated to the large right panel. Watches the
// live stream from the orchestrator and refreshes the iframe as HTML/CSS/JS
// arrive, so the page visually evolves from blank → styled → interactive.
// ---------------------------------------------------------------------------

type BigViewport = 'desktop' | 'tablet' | 'mobile'

// Physical device proportions used to size the chrome realistically.
// Width × height are the OUTER frame size. Padding carves the inner "screen" area.
const BIG_VIEWPORT_SPEC: Record<BigViewport, {
  width: number   // outer frame width in px
  height: number  // outer frame height in px
  pad: number     // frame bezel thickness
  radius: number  // outer corner radius
  notch: boolean
  chrome: 'none' | 'browser'
}> = {
  desktop: { width: 1440, height: 900, pad: 0,  radius: 14, notch: false, chrome: 'browser' },
  tablet:  { width: 760,  height: 1024, pad: 20, radius: 36, notch: false, chrome: 'none' },
  mobile:  { width: 360,  height: 720,  pad: 12, radius: 40, notch: true,  chrome: 'none' },
}

// Detect heavy content that must NOT be hot-reloaded at every token:
// Three.js / WebGL / Canvas scenes reinitialize renderers + upload textures
// on every iframe reload, which exhausts GPU memory and crashes the page
// when the preview refreshes 60×/s during streaming.
function isHeavyWebGLProject(files: CodeFile[]): boolean {
  for (const f of files) {
    if (f.content.length > 80_000) return true
    const head = f.content.slice(0, 4000).toLowerCase()
    if (/three\.js|three\.module|import\s+\*\s+as\s+three|from\s+['"]three['"]/.test(head)) return true
    if (/webglrenderer|getcontext\(\s*['"]webgl/.test(head)) return true
    if (/requestanimationframe.*render|game\s*loop|scene\s*=\s*new/.test(head)) return true
  }
  return false
}

// Total bytes cap: beyond this, the preview recompute on every token is too
// expensive (split + regex + blob + iframe reload). We freeze the preview
// until generation finishes.
const LIVE_PREVIEW_TOTAL_CAP = 150_000

function BigLivePreviewFrame({
  files,
  streamContent,
  isGenerating,
  iframeRef,
  viewport,
  onViewportChange,
}: {
  files: CodeFile[]
  streamContent: string
  isGenerating: boolean
  iframeRef: RefObject<HTMLIFrameElement | null>
  viewport: BigViewport
  onViewportChange: (mode: BigViewport) => void
}) {
  // Debounce the stream content so we don't re-parse + re-build HTML on every
  // single token. 600ms gives a smooth "building" sensation while dividing the
  // CPU cost by ~40× during active streaming.
  const [debouncedStream, setDebouncedStream] = useState(streamContent)
  useEffect(() => {
    if (!isGenerating) {
      setDebouncedStream(streamContent)
      return
    }
    const timer = setTimeout(() => setDebouncedStream(streamContent), 600)
    return () => clearTimeout(timer)
  }, [streamContent, isGenerating])

  const streamFiles = useMemo(
    () => (debouncedStream ? parsePartialStreamFiles(debouncedStream) : []),
    [debouncedStream],
  )
  const rawEffectiveFiles = files.length > 0 ? files : streamFiles
  // v82nu : safety net — intelligentlyElevateFiles fixes broken <img>
  // (PLACEHOLDER_SUBJECT_IMG markers that survived hydration), wires
  // buttons, and patches CSS bg-images. Same hook as AuroraV1CodeView.
  // Only runs once streaming is finished to avoid burning CPU per token.
  const effectiveFiles = useMemo(() => {
    if (isGenerating || rawEffectiveFiles.length === 0) return rawEffectiveFiles
    try {
      const adapted = rawEffectiveFiles.map((f) => ({
        path: f.name,
        content: f.content,
        language: f.language,
      }))
      const { files: out } = intelligentlyElevateFiles(adapted, '', '')
      return out.map((f) => ({
        name: f.path,
        content: f.content,
        language: f.language,
      })) as CodeFile[]
    } catch {
      return rawEffectiveFiles
    }
  }, [rawEffectiveFiles, isGenerating])

  // Total byte budget: if the project is too big or WebGL-heavy, we freeze
  // the live preview during generation and only render the finished files.
  const totalBytes = useMemo(
    () => effectiveFiles.reduce((sum, f) => sum + f.content.length, 0),
    [effectiveFiles],
  )
  const isHeavy = useMemo(() => isHeavyWebGLProject(effectiveFiles), [effectiveFiles])
  // v77n FIX UI FREEZE: pendant TOUTE generation, skip la live preview iframe.
  // Avant: la preview iframe se reconstruisait toutes les 600ms (debouncedStream
  // change), avec parsePartialStreamFiles + buildLivePreviewHtml + iframe srcdoc
  // de 50K+ chars. Sur un projet brand_landing avec shader/particles, ces
  // operations bloquaient le main thread JS pendant >5s, ce qui declenchait le
  // dialog Chrome 'Page ne repond pas — Attendre / Quitter'. L user n a aucun
  // feedback que ca avance.
  // Apres: la preview est PAUSEE pendant toute la generation. L user voit le
  // code en direct via l onglet Code (qui reste leger — un <pre> avec stream
  // text capped a 10K). La preview iframe arrive d un coup a la fin, ce qui
  // est plus snappy et plus surement memory-safe. Les anciens checks heavy/
  // total_cap sont conserves comme fallback pour les rares cas ou l user a
  // active manuellement le mode temps-reel (futur toggle).
  const shouldSkipLivePreview = isGenerating

  const canRender = !shouldSkipLivePreview && webProjectFromFiles(effectiveFiles)
  const html = useMemo(
    () => (canRender ? buildLivePreviewHtml(effectiveFiles) : null),
    [effectiveFiles, canRender],
  )

  // Keep the last rendered HTML alive: once we have produced something,
  // we never go back to the "building..." placeholder just because the stream
  // is momentarily empty (regeneration, rescue pass, etc.).
  const lastGoodHtmlRef = useRef<string | null>(null)
  if (html) lastGoodHtmlRef.current = html

  useEffect(() => {
    if (!iframeRef.current) return
    const fallbackIdle = '<!DOCTYPE html><html><body style="margin:0;background:#0d1117;color:#8b949e;font-family:system-ui;display:grid;place-items:center;height:100vh"><div>Lance une generation pour voir la page se construire ici.</div></body></html>'
    const fallbackBuilding = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>body{margin:0;background:#0d1117;color:#8b949e;font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh}div{text-align:center;max-width:32rem;padding:2rem}h2{color:#e6edf3;margin:0 0 .5rem;font-weight:600;font-size:15px}p{margin:.35rem 0;font-size:12px;line-height:1.5}span.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#7cf0a5;margin-right:.4rem;animation:p 1s infinite}@keyframes p{0%,100%{opacity:1}50%{opacity:.3}}</style></head><body><div><h2><span class="dot"></span>La page se construit...</h2><p>Le rendu apparaitra au fur et a mesure que le modele ecrit index.html, style.css et script.js.</p><p>Bascule sur l onglet <b>Code</b> pour voir le texte brut en direct.</p></div></body></html>'
    const fallbackHeavy = '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><style>body{margin:0;background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh}div{text-align:center;max-width:32rem;padding:2rem}h2{color:#facc15;margin:0 0 .6rem;font-weight:600;font-size:15px}p{margin:.3rem 0;font-size:12px;line-height:1.5}</style></head><body><div><h2>Preview differee (projet lourd detecte)</h2><p>Ce projet utilise Three.js/WebGL ou depasse 150 KB cumules.</p><p>Le rendu live serait recalcule a chaque token et saturerait le GPU.</p><p>La preview s activera automatiquement des la fin de la generation.</p></div></body></html>'

    // Preference order:
    //  1. Fresh HTML just parsed from current files/stream.
    //  2. Last good HTML we ever managed to render (never regress to the placeholder).
    //  3. "heavy project" notice when live preview is paused.
    //  4. "building..." during generation.
    //  5. Idle message when no generation has been started.
    const payload = html
      ?? lastGoodHtmlRef.current
      ?? (shouldSkipLivePreview ? fallbackHeavy : isGenerating ? fallbackBuilding : fallbackIdle)

    // v77m fix bug critique OOM: switch de Blob URL -> srcdoc.
    // Avant: chaque update du payload creait une Blob + URL.createObjectURL,
    // revoquees uniquement dans le cleanup useEffect. Pendant un stream actif,
    // l effet se redeclenche au moins toutes les 600ms (debouncedStream change),
    // donc des dizaines de Blob URLs s accumulent avant que GC les libere.
    // Sur les projets Three.js/WebGL avec shader + textures, c est ce qui
    // saturait Chrome (OOM "Aïe aïe aïe" dans le tab tunnel).
    // srcdoc evite completement la creation de Blob — le HTML est inline dans
    // l attribut iframe, pas de URL a revoquer.
    iframeRef.current.srcdoc = payload
    iframeRef.current.removeAttribute('src')
  }, [html, isGenerating, iframeRef, shouldSkipLivePreview])

  const spec = BIG_VIEWPORT_SPEC[viewport]

  // Ensures every viewport (including desktop at 1440×900) auto-scales to fit
  // the visible area. The iframe still sees the real `spec.width × spec.height`
  // resolution so media queries trigger correctly.
  const frameWrapRef = useRef<HTMLDivElement>(null)
  const [frameScale, setFrameScale] = useState(1)

  useEffect(() => {
    const wrap = frameWrapRef.current
    if (!wrap) return
    const compute = () => {
      const availW = wrap.clientWidth - 32
      const availH = wrap.clientHeight - 32
      if (availW <= 0 || availH <= 0) return
      const s = Math.min(availW / spec.width, availH / spec.height, 1)
      setFrameScale(s < 0.2 ? 0.2 : s)
    }
    compute()
    const ro = new ResizeObserver(compute)
    ro.observe(wrap)
    window.addEventListener('resize', compute)
    return () => { ro.disconnect(); window.removeEventListener('resize', compute) }
  }, [viewport, spec.width, spec.height])

  return (
    <div className="flex flex-col h-full min-h-[32rem] bg-[#0d1117]">
      <div className="flex items-center justify-center gap-1 border-b border-black/5 bg-[#0a0f14] px-2 py-1.5">
        {(['desktop', 'tablet', 'mobile'] as const).map((mode) => {
          const Icon = mode === 'desktop' ? Monitor : mode === 'tablet' ? Tablet : Smartphone
          const label = mode === 'desktop' ? 'Desktop' : mode === 'tablet' ? 'Tablet' : 'Mobile'
          return (
            <button
              key={mode}
              onClick={() => onViewportChange(mode)}
              title={label}
              className={`flex h-6 items-center gap-1 rounded-md px-2 text-[10px] transition-colors ${
                viewport === mode
                  ? 'bg-aurora-accent/20 text-aurora-accent-light'
                  : 'text-aurora-text-dim hover:text-aurora-text'
              }`}
            >
              <Icon size={11} />
              <span>{label}</span>
            </button>
          )
        })}
      </div>
      <div
        ref={frameWrapRef}
        className="flex-1 flex items-center justify-center overflow-hidden min-h-[32rem]"
        style={{ background: 'var(--v4code-stage-bg, radial-gradient(circle at center, #1a1d22, #07080a))' }}
      >
        <div
          className="relative shrink-0 transition-[transform] duration-200 ease-out"
          style={{
            width: `${spec.width}px`,
            height: `${spec.height}px`,
            padding: `${spec.pad}px`,
            borderRadius: `${spec.radius}px`,
            background: spec.chrome === 'browser'
              ? 'linear-gradient(180deg,#2c2e33 0 44px,#fafafa 44px)'
              : 'linear-gradient(135deg,#1a1c22,#0a0b0e)',
            boxShadow: '0 30px 80px rgba(0,0,0,.55), inset 0 0 0 2px rgba(255,255,255,.05)',
            transform: `scale(${frameScale})`,
            transformOrigin: 'center center',
          }}
        >
          {spec.chrome === 'browser' && <BrowserChromeBar />}
          {spec.notch && (
            <div
              className="absolute left-1/2 -translate-x-1/2 z-10"
              style={{
                top: `${Math.round(spec.pad * 0.85)}px`,
                width: '110px',
                height: '26px',
                borderRadius: '18px',
                background: '#000',
                pointerEvents: 'none',
              }}
            />
          )}
          <iframe
            ref={iframeRef}
            title="Rendu live de la page"
            sandbox="allow-scripts allow-same-origin"
            className="block w-full h-full bg-white border-0"
            style={{
              borderRadius: spec.chrome === 'browser'
                ? '0 0 8px 8px'
                : `${Math.max(0, spec.radius - spec.pad * 0.5)}px`,
              marginTop: spec.chrome === 'browser' ? '44px' : 0,
              height: spec.chrome === 'browser' ? `calc(100% - 44px)` : '100%',
            }}
          />
        </div>
      </div>
    </div>
  )
}

function BrowserChromeBar() {
  return (
    <div
      className="absolute top-0 left-0 right-0 flex items-center gap-2 px-3"
      style={{
        height: '44px',
        borderRadius: '14px 14px 0 0',
        background: 'linear-gradient(180deg,#34363b,#26282d)',
        borderBottom: '1px solid rgba(0,0,0,.35)',
        pointerEvents: 'none',
      }}
    >
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
      <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
      <div
        className="ml-3 flex-1 flex items-center"
        style={{
          height: '26px',
          background: 'rgba(255,255,255,.08)',
          borderRadius: '999px',
          padding: '0 14px',
          fontSize: '11px',
          color: '#b6b8be',
          fontFamily: 'system-ui, sans-serif',
          letterSpacing: '.02em',
        }}
      >
        <span style={{ opacity: .55, marginRight: 6 }}>●</span>
        aurora-preview.local
      </div>
    </div>
  )
}

// v83i — Panneau de critique statique temps-réel sur le fichier actif.
// Affiche : complexité cyclomatique par fonction + Halstead + verdict global.
function CodeCritiquePanel({ content, language }: { content: string; language: string }) {
  const complexity = useMemo(() => analyzeCyclomaticComplexity(content, language), [content, language])
  const halstead = useMemo(() => computeHalstead(content, language), [content, language])
  const lines = content.split(/\r?\n/).length
  const worst = complexity.reduce((max, fn) => (fn.cyclomaticComplexity > max ? fn.cyclomaticComplexity : max), 0)
  const avg = complexity.length
    ? Math.round((complexity.reduce((s, fn) => s + fn.cyclomaticComplexity, 0) / complexity.length) * 10) / 10
    : 0
  const verdict =
    worst >= 20 ? { tone: 'rose', label: 'À refactorer', detail: 'Une fonction dépasse 20 (ingérable).' }
    : worst >= 11 ? { tone: 'amber', label: 'Complexe', detail: 'Au moins une fonction très complexe (>10).' }
    : worst >= 6 ? { tone: 'sky', label: 'Modéré', detail: 'Tout reste sous contrôle.' }
    : complexity.length === 0 ? { tone: 'slate', label: '—', detail: 'Aucune fonction détectée.' }
    : { tone: 'emerald', label: 'Propre', detail: 'Branches peu nombreuses, lisible.' }
  const toneCls: Record<string, string> = {
    rose: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    amber: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    sky: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
    slate: 'bg-white/5 text-aurora-text-dim border-white/10',
  }
  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-[0.2em] text-aurora-text-dim">Critique statique</span>
        <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono ${toneCls[verdict.tone]}`}>{verdict.label}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5 mb-2">
        <Mini label="Lignes" value={String(lines)} />
        <Mini label="Fonctions" value={String(complexity.length)} />
        <Mini label="Pire McCabe" value={worst > 0 ? String(worst) : '—'} />
        <Mini label="Moy McCabe" value={complexity.length > 0 ? String(avg) : '—'} />
        <Mini label="Halstead vol" value={Math.round(halstead.volume).toString()} />
        <Mini label="Bugs prédits" value={halstead.predictedBugs.toFixed(2)} />
      </div>
      <p className="text-[10px] text-aurora-text-dim italic">{verdict.detail}</p>
      {complexity.length > 0 && worst >= 6 && (
        <div className="mt-2 space-y-1 max-h-32 overflow-auto">
          {complexity
            .filter((fn) => fn.cyclomaticComplexity >= 6)
            .sort((a, b) => b.cyclomaticComplexity - a.cyclomaticComplexity)
            .slice(0, 5)
            .map((fn, i) => (
              <div key={i} className="flex items-center justify-between rounded-md bg-black/30 px-2 py-1 text-[10px] font-mono">
                <span className="text-aurora-text/85 truncate">{fn.name}</span>
                <span className={`shrink-0 ml-2 px-1.5 rounded ${fn.cyclomaticComplexity >= 20 ? 'bg-rose-500/30 text-rose-200' : fn.cyclomaticComplexity >= 11 ? 'bg-amber-500/30 text-amber-200' : 'bg-sky-500/30 text-sky-200'}`}>
                  {fn.cyclomaticComplexity}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-black/30 border border-white/5 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wider text-aurora-text-dim">{label}</div>
      <div className="text-[12px] font-mono text-aurora-text">{value}</div>
    </div>
  )
}

// v84k — Lyra commentator pour Code : réagit à la qualité du fichier actif.
function CodeLyraCommentator({
  content,
  language,
  isGenerating,
}: { content: string; language: string; isGenerating: boolean }) {
  const complexity = useMemo(() => analyzeCyclomaticComplexity(content, language), [content, language])
  const worst = complexity.reduce((m, fn) => (fn.cyclomaticComplexity > m ? fn.cyclomaticComplexity : m), 0)
  const emotion: 'focus' | 'happy' | 'sad' | 'curious' = isGenerating
    ? 'focus'
    : worst >= 15
      ? 'sad'
      : worst >= 6
        ? 'curious'
        : 'happy'
  const verdict =
    isGenerating ? 'je code…'
    : worst >= 20 ? 'à refactor sérieusement'
    : worst >= 11 ? 'ça commence à être touffu'
    : worst >= 6 ? 'lisible mais surveille'
    : complexity.length === 0 ? 'rien à analyser'
    : 'propre, bravo'
  return (
    <div className="flex items-center gap-3 rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3">
      <div style={{ width: 48, height: 60, flexShrink: 0 }}>
        <LyraCharacter
          phase={isGenerating ? 'thinking' : 'idle'}
          emotion={emotion}
          accent="#67d2ff"
          size={48}
        />
      </div>
      <div className="text-[11px] text-aurora-text-dim">
        <div className="font-mono uppercase tracking-wider text-aurora-text">{verdict}</div>
        {worst > 0 && <div className="mt-0.5">McCabe max : {worst}</div>}
      </div>
    </div>
  )
}

// v83t — Chip de détection de langage du fichier actif.
// Detection : extension fichier + heuristiques signatures (shebang, imports).
function CodeLanguageChip({
  fileName,
  declaredLang,
  content,
}: {
  fileName: string
  declaredLang?: string
  content: string
}) {
  const detected = useMemo(() => detectFileLanguage(fileName, content), [fileName, content])
  const lang = declaredLang || detected.lang
  const conf = declaredLang ? 1 : detected.confidence
  const TYPED_LANGS = new Set(['ts', 'tsx', 'typescript', 'rust', 'go', 'kotlin', 'swift', 'scala', 'c', 'cpp', 'csharp', 'java'])
  const isTyped = TYPED_LANGS.has(lang.toLowerCase())
  const sizeKb = (new Blob([content]).size / 1024)
  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-[0.2em] text-aurora-text-dim">Fichier</span>
        <span className="font-mono text-aurora-text-dim">{sizeKb.toFixed(1)} KB</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded-md border border-aurora-accent/40 bg-aurora-accent/15 px-2 py-0.5 text-[10px] font-mono text-aurora-accent-light">
          {lang}
        </span>
        <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim">
          {isTyped ? 'typé' : 'dynamique'}
        </span>
        <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim">
          {Math.round(conf * 100)}% conf
        </span>
        {detected.shebang && (
          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-mono text-emerald-200">
            shebang
          </span>
        )}
      </div>
    </div>
  )
}

// Heuristique langage du fichier — extension prioritaire, signature fallback.
function detectFileLanguage(name: string, content: string): { lang: string; confidence: number; shebang: boolean } {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  const EXT_MAP: Record<string, string> = {
    ts: 'ts', tsx: 'tsx', js: 'js', jsx: 'jsx', mjs: 'js', cjs: 'js',
    py: 'python', rs: 'rust', go: 'go', java: 'java', kt: 'kotlin',
    swift: 'swift', scala: 'scala', c: 'c', cc: 'cpp', cpp: 'cpp', cs: 'csharp', h: 'c',
    hpp: 'cpp', rb: 'ruby', php: 'php', lua: 'lua', sh: 'bash', bash: 'bash',
    zsh: 'bash', ps1: 'powershell', html: 'html', htm: 'html', css: 'css',
    scss: 'scss', sass: 'sass', less: 'less', json: 'json', yaml: 'yaml',
    yml: 'yaml', toml: 'toml', md: 'markdown', sql: 'sql',
  }
  const shebang = /^#!/.test(content)
  if (EXT_MAP[ext]) return { lang: EXT_MAP[ext], confidence: 0.98, shebang }
  // Fallback heuristiques.
  if (/^#!/.test(content)) {
    if (/python/.test(content.slice(0, 80))) return { lang: 'python', confidence: 0.85, shebang: true }
    if (/bash|sh/.test(content.slice(0, 80))) return { lang: 'bash', confidence: 0.85, shebang: true }
  }
  if (/^\s*import\s+\w+\s+from\s+['"]/.test(content) || /export\s+(default|const|function)/.test(content)) {
    return { lang: 'ts', confidence: 0.6, shebang: false }
  }
  if (/^\s*def\s+\w+\s*\(/.test(content) || /^\s*from\s+\w+\s+import/.test(content)) {
    return { lang: 'python', confidence: 0.6, shebang: false }
  }
  if (/^\s*fn\s+\w+\s*\(/.test(content)) {
    return { lang: 'rust', confidence: 0.6, shebang: false }
  }
  return { lang: ext || 'plaintext', confidence: 0.3, shebang }
}
