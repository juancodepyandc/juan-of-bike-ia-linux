import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Code2 } from 'lucide-react'
import ClarificationDialog from '../components/ClarificationDialog'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import PromptLibraryPanel from '../components/PromptLibraryPanel'
import SaveDialog from '../components/SaveDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { selectCodeModelForHardware } from '../config/models'
import { buildCodeModuleAssets } from '../config/moduleAssetPacks'
import { StudioHero } from '../components/StudioHero'
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
import { CodeViewDeliveryPanel } from './codeViewDeliveryPanel'
import { CodeViewControlPanel } from './codeViewControlPanel'

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
          promptGuide={promptGuide}
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
