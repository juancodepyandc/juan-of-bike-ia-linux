import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ClarificationDialog from '../components/ClarificationDialog.tsx'
import type { ClarificationRequest } from '../components/ClarificationDialog.tsx'
import PromptLibraryPanel from '../components/PromptLibraryPanel.tsx'
import SaveDialog from '../components/SaveDialog.tsx'
import type { SaveDialogData } from '../components/SaveDialog.tsx'
import { selectCodeModelForHardware } from '../config/models.ts'
import { buildCodeModuleAssets } from '../config/moduleAssetPacks.ts'
import { useManagedRuntime } from '../hooks/useManagedRuntime.ts'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack.ts'
import { useStudioDiagnostics } from '../hooks/useStudioDiagnostics.ts'
import {
  type CodeFile,
  type FollowUpAnalysis,
} from '../services/codeOrchestrator.ts'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodePreflightReport } from '../services/codePreflight.ts'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import { stopDevServer, type DevServerState } from '../services/codeDevServer.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore.ts'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore.ts'
import { usePromptLibraryStore } from '../stores/promptLibraryStore.ts'
import { CodeViewDeliveryPanel } from './codeViewDeliveryPanel.tsx'
import { CodeViewControlPanel } from './codeViewControlPanel.tsx'
import { CodeViewChrome } from './codeViewChrome.tsx'
import { runCodeViewGeneration, type CodeViewGenerateOptions } from './codeViewGeneration.ts'
import {
  CODE_VIEW_PROMPT_GUIDE,
  buildCodePipelineLabel,
  codeContextNeedsVision,
  formatProjectType,
} from './codeViewShellHelpers.ts'
import { useCodeViewWorkspacePersistence } from './useCodeViewWorkspacePersistence.ts'
import { useCodeViewActions } from './useCodeViewActions.ts'
import {
  PHYSICAL_SPRING_PRESETS,
  analyzePromptExcellence,
  auditCodeExcellence,
  buildExcellenceEnrichedPrompt,
  computeSpotlightLighting,
  computeStaggerChoreography,
  solveDampedSpring,
  stepFrameIndependentLerp,
} from '../services/codeExcellenceEngine.ts'

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
  const workspaceViewState = useMemo(() => ({
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
  }), [
    activeFile, consoleOutput, correctionLog, error, files, finalScore, intent,
    notes, preflightReport, progress, prompt, recoveryStatus, totalAttempts, validationResult,
  ])
  const workspaceSetters = useMemo(() => ({
    setPrompt,
    setProgress,
    setNotes,
    setFiles,
    setActiveFile,
    setError,
    setValidationResult,
    setCorrectionLog,
    setIntent,
    setTotalAttempts,
    setFinalScore,
    setConsoleOutput,
    setRecoveryStatus,
    setPreflightReport,
    setFollowUpAnalysis,
    setStreamPreview,
    setSaveDialogData,
    setSavedProjectData,
    setSaveTarget,
    setSaveFeedback,
    setSavedProjectPath,
    setDevServerState,
  }), [])
  const { handleSessionChange, workspacePersistenceReady } = useCodeViewWorkspacePersistence({
    activeSessionId: activeSession.id,
    getRecentMessages,
    isGeneratingRef,
    resumeAfterReloadRef,
    state: workspaceViewState,
    setters: workspaceSetters,
    setWorkspaceSnapshot,
  })

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

  // Aurora Code Excellence Engine: Explicit/Implicit AGI Synthesis, Physical Spring & Static AST Audit
  const [springPresetKey, setSpringPresetKey] = useState<'critically_damped' | 'snappy_ui' | 'spatial_reveal'>('critically_damped')
  const [showExcellenceDetails, setShowExcellenceDetails] = useState(false)
  const promptSynthesis = useMemo(() => analyzePromptExcellence(prompt, intent), [prompt, intent])
  const excellenceReport = useMemo(() => auditCodeExcellence(files, prompt, intent), [files, prompt, intent])
  const activeSpring = useMemo(() => solveDampedSpring(PHYSICAL_SPRING_PRESETS[springPresetKey]), [springPresetKey])
  const staggerTimings = useMemo(
    () => computeStaggerChoreography(promptSynthesis.implicitFeatures.length, 3),
    [promptSynthesis.implicitFeatures.length],
  )
  const effectiveDesignReport = useMemo(() => {
    if (designReport) return designReport
    if (files.length === 0) return null
    return {
      score: excellenceReport.overallScore,
      missing: excellenceReport.implicitFeatures
        .filter((f) => !f.detectedInCode)
        .map((f) => f.title),
      penalties: excellenceReport.priorityRecommendations,
    }
  }, [designReport, excellenceReport, files.length])

  // Physical rAF Lerp Spotlight (60/120fps frame-rate independent, zero React re-render on pointermove)
  const rootContainerRef = useRef<HTMLDivElement | null>(null)
  const spotlightOverlayRef = useRef<HTMLDivElement | null>(null)
  const pointerTargetRef = useRef({ x: 480, y: 220, w: 1280, h: 800, active: false })
  const pointerCurrentRef = useRef({ x: 480, y: 220 })
  const rafIdRef = useRef<number | null>(null)
  const lastFrameTimeRef = useRef<number>(0)

  const stepSpotlightPhysics = useCallback((timestamp: number) => {
    const dt = lastFrameTimeRef.current > 0 ? timestamp - lastFrameTimeRef.current : 16.67
    lastFrameTimeRef.current = timestamp
    const target = pointerTargetRef.current
    const current = pointerCurrentRef.current

    current.x = stepFrameIndependentLerp(current.x, target.x, dt, 18)
    current.y = stepFrameIndependentLerp(current.y, target.y, dt, 18)

    if (spotlightOverlayRef.current && rootContainerRef.current) {
      const light = computeSpotlightLighting(current.x, current.y, target.w, target.h)
      spotlightOverlayRef.current.style.background = light.backgroundGradient
      rootContainerRef.current.style.setProperty('--spotlight-x', light.cssVariables['--spotlight-x'])
      rootContainerRef.current.style.setProperty('--spotlight-y', light.cssVariables['--spotlight-y'])
      rootContainerRef.current.style.setProperty('--spotlight-intensity', light.cssVariables['--spotlight-intensity'])
    }

    const dist = Math.hypot(target.x - current.x, target.y - current.y)
    if (dist > 0.5) {
      rafIdRef.current = window.requestAnimationFrame(stepSpotlightPhysics)
    } else {
      rafIdRef.current = null
      lastFrameTimeRef.current = 0
    }
  }, [])

  const handleContainerPointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const el = rootContainerRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      pointerTargetRef.current = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        w: rect.width || 1280,
        h: rect.height || 800,
        active: true,
      }
      if (rafIdRef.current === null && typeof window !== 'undefined') {
        rafIdRef.current = window.requestAnimationFrame(stepSpotlightPhysics)
      }
    },
    [stepSpotlightPhysics],
  )

  // Cleanup dev server & rAF on unmount
  useEffect(() => {
    return () => {
      void stopDevServer()
      if (streamTimerRef.current !== null) {
        clearTimeout(streamTimerRef.current)
        streamTimerRef.current = null
      }
      if (rafIdRef.current !== null && typeof window !== 'undefined') {
        window.cancelAnimationFrame(rafIdRef.current)
        rafIdRef.current = null
      }
      streamBufferRef.current = []
    }
  }, [])

  useEffect(() => {
    if (!error) return
    if (diagnostics.blockingReason) return
    if (!/^(Ollama|ComfyUI|Shell natif):/i.test(error)) return
    setError(null)
  }, [diagnostics.blockingReason, error])

  const {
    clearConversation,
    copyCurrentFile,
    finalizeSavedResult,
    handlePersistentSave,
    stopGeneration,
  } = useCodeViewActions({
    activeFileData,
    savedProjectData,
    addPrompt,
    clearHistory,
    resetWorkspaceSnapshot,
    setters: workspaceSetters,
    abortRef,
    resumeAfterReloadRef,
    isGeneratingRef,
    streamBufferRef,
    streamCharsTotalRef,
    streamTimerRef,
    setCopied,
    setIsGenerating,
    setStreamCharsTotal,
  })

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

  const handleEnrichPromptWithExcellence = useCallback(() => {
    if (!prompt.trim()) return
    setPrompt((prev) => buildExcellenceEnrichedPrompt(prev, intent))
  }, [intent, prompt])

  const handleTriggerExcellenceOptimization = useCallback(() => {
    if (isGenerating || excellenceReport.priorityRecommendations.length === 0) return
    const optimizationBrief = [
      prompt.trim() || 'Optimiser le projet existant',
      '',
      '=== OPTIMISATION CHIRURGICALE D’EXCELLENCE (MOTION PHYSIQUE & ALGORITHMIQUE O(N)) ===',
      ...excellenceReport.priorityRecommendations.map((rec, idx) => `${idx + 1}. ${rec}`),
      `Courbe ressort amortie cible : ${activeSpring.cssEasing} (${activeSpring.settlingDurationMs}ms, ζ=${activeSpring.dampingRatio}).`,
    ].join('\n')
    void generate({ overridePrompt: optimizationBrief })
  }, [activeSpring, excellenceReport.priorityRecommendations, generate, isGenerating, prompt])

  return (
    <div
      ref={rootContainerRef}
      onPointerMove={handleContainerPointerMove}
      data-code-view="true"
      className="relative min-h-full flex flex-col overflow-hidden"
    >
      {/* Dynamic Physical rAF Lerp Spotlight Overlay */}
      <div
        ref={spotlightOverlayRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 transition-opacity duration-300"
      />
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

      {/* Aurora Code Excellence HUD: Explicit/Implicit AGI Synthesis, Physical Spring & Static AST Audit */}
      <section
        data-code-excellence-hud="true"
        aria-label="Moteur d'Excellence Code : Précision AGI, Motion Design Physique et Audit Algorithmique"
        className="relative z-10 mx-2 mt-2 rounded-[1.35rem] px-3.5 py-2.5 backdrop-blur-xl sm:mx-6 sm:px-5 sm:py-3"
        style={{
          border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 15%, transparent))',
          background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 78%, transparent))',
          transition: `transform ${activeSpring.settlingDurationMs}ms ${activeSpring.cssEasing}, box-shadow ${activeSpring.settlingDurationMs}ms ${activeSpring.cssEasing}`,
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-aurora-accent/15 px-2.5 py-1 text-[11px] font-semibold text-aurora-accent">
              <span>Excellence AGI</span>
              {files.length > 0 && <span>{excellenceReport.overallScore}/100</span>}
            </span>
            <span
              className="rounded-full border border-aurora-border/35 bg-aurora-surface/65 px-2.5 py-1 text-[11px] text-aurora-text"
              title="Contraintes explicites extraites et piliers implicites synthétisés"
            >
              Précision : {promptSynthesis.explicitConstraints.length} explicite(s) · {promptSynthesis.implicitFeatures.length} piliers AGI
            </span>
            <span
              className="rounded-full border border-aurora-border/35 bg-aurora-surface/65 px-2.5 py-1 text-[11px] text-aurora-text"
              title={`Équation ressort amorti : ζ=${activeSpring.dampingRatio}, ω₀=${activeSpring.naturalFrequency} rad/s, ${activeSpring.cssEasing}`}
            >
              Motion : {activeSpring.regime === 'critically_damped' ? ' critique' : ' sous-amorti'} ({activeSpring.settlingDurationMs}ms · ζ={activeSpring.dampingRatio})
            </span>
            <span
              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                excellenceReport.algorithmicAudit.quadraticCount === 0 && excellenceReport.zeroPlaceholderPassed
                  ? 'border-emerald-500/35 bg-emerald-500/10 text-emerald-400'
                  : 'border-amber-500/40 bg-amber-500/10 text-amber-300'
              }`}
              title="Complexité algorithmique dominante et vérification Zéro Placeholder/TODO"
            >
              Algo : {excellenceReport.algorithmicAudit.dominantComplexity} ·{' '}
              {excellenceReport.zeroPlaceholderPassed ? 'Zéro Placeholder' : `${excellenceReport.algorithmicAudit.placeholderCount} stub(s)`}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Profil physique de ressort Motion Design"
              value={springPresetKey}
              onChange={(e) => setSpringPresetKey(e.target.value as 'critically_damped' | 'snappy_ui' | 'spatial_reveal')}
              className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-2.5 py-1 text-[11px] text-aurora-text outline-none focus-visible:ring-2 focus-visible:ring-aurora-accent"
            >
              <option value="critically_damped">Ressort Critique (ζ=1.0)</option>
              <option value="snappy_ui">Micro-Interaction Vive</option>
              <option value="spatial_reveal">Révélation Spatiale Douce</option>
            </select>

            {prompt.trim().length > 0 && !prompt.includes('CONTRAT D’EXCELLENCE AURORA CODE') && (
              <button
                type="button"
                onClick={handleEnrichPromptWithExcellence}
                className="rounded-xl border border-aurora-accent/40 bg-aurora-accent/15 px-2.5 py-1 text-[11px] font-medium text-aurora-accent hover:bg-aurora-accent/25 focus-visible:ring-2 focus-visible:ring-aurora-accent"
                title="Ajouter explicitement au brief la synthèse AGI implicite (Persistance, Erreurs, WCAG AA, États vides, Recherche O(N), Raccourcis) et le contrat Motion/Algo"
              >
                + Synthèse AGI au brief
              </button>
            )}

            {files.length > 0 && excellenceReport.priorityRecommendations.length > 0 && !isGenerating && (
              <button
                type="button"
                onClick={handleTriggerExcellenceOptimization}
                className="rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/25 focus-visible:ring-2 focus-visible:ring-emerald-400"
                title="Lancer une passe d'optimisation chirurgicale sur la complexité algorithmique et le Motion Design"
              >
                Optimiser ({excellenceReport.priorityRecommendations.length})
              </button>
            )}

            <button
              type="button"
              onClick={() => setShowExcellenceDetails((prev) => !prev)}
              aria-expanded={showExcellenceDetails}
              className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-2.5 py-1 text-[11px] text-aurora-text-dim hover:text-aurora-text focus-visible:ring-2 focus-visible:ring-aurora-accent"
            >
              {showExcellenceDetails ? 'Masquer audit' : 'Détails AGI & AST'}
            </button>
          </div>
        </div>

        {showExcellenceDetails && (
          <div className="mt-3 grid gap-3 border-t border-aurora-border/25 pt-3 text-xs lg:grid-cols-3">
            {/* Column 1: Implicit AGI Pillars with Stagger Choreography */}
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-aurora-text-dim">
                Synthèse AGI Implicite & Contraintes ({excellenceReport.fidelityScore}/100)
              </p>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {excellenceReport.implicitFeatures.map((feat, idx) => {
                  const timing = staggerTimings[idx]
                  return (
                    <div
                      key={feat.pillar}
                      style={{
                        transitionDelay: `${timing?.delayMs ?? 0}ms`,
                        transitionDuration: `${activeSpring.settlingDurationMs}ms`,
                        transitionTimingFunction: activeSpring.cssEasing,
                      }}
                      className="rounded-xl border border-aurora-border/30 bg-aurora-surface/60 px-2.5 py-1.5 transition-all"
                      title={feat.implementationDirective}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-medium text-aurora-text">{feat.title}</span>
                        {files.length > 0 && (
                          <span className={feat.detectedInCode ? 'text-emerald-400' : 'text-amber-400'}>
                            {feat.detectedInCode ? '✓' : '○'}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Column 2: Physical Motion Design Solver */}
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-aurora-text-dim">
                Solveur Motion Design Physique ({excellenceReport.motionScore}/100)
              </p>
              <div className="rounded-xl border border-aurora-border/30 bg-aurora-surface/60 p-2.5 space-y-1">
                <p className="text-[11px] text-aurora-text">
                  Courbe : <code className="text-aurora-accent">{activeSpring.cssEasing}</code>
                </p>
                <p className="text-[11px] text-aurora-text-dim">
                  Stabilisation : {activeSpring.settlingDurationMs}ms · Dépassement : {activeSpring.overshootPercent}% · rAF Lerp 60fps actif
                </p>
                {excellenceReport.motionAudit.warnings.length > 0 ? (
                  <ul className="mt-1 space-y-0.5 text-[11px] text-amber-300">
                    {excellenceReport.motionAudit.warnings.slice(0, 2).map((w) => (
                      <li key={w}>• {w}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11px] text-emerald-400">
                    ✓ Transitions GPU (transform/opacity) & courbes physiques validées.
                  </p>
                )}
              </div>
            </div>

            {/* Column 3: Static AST Algorithmic & N+1 Audit */}
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-aurora-text-dim">
                Audit Algorithmique & Backend ({excellenceReport.algorithmicScore}/100)
              </p>
              <div className="rounded-xl border border-aurora-border/30 bg-aurora-surface/60 p-2.5 space-y-1">
                <p className="text-[11px] text-aurora-text">
                  Complexité : <strong>{excellenceReport.algorithmicAudit.dominantComplexity}</strong> · Boucles O(N²) : {excellenceReport.algorithmicAudit.quadraticCount} · N+1 I/O : {excellenceReport.algorithmicAudit.nPlusOneCount} · Fuites : {excellenceReport.algorithmicAudit.leakCount}
                </p>
                {excellenceReport.algorithmicAudit.findings.length > 0 ? (
                  <div className="max-h-24 overflow-y-auto space-y-1 pt-1">
                    {excellenceReport.algorithmicAudit.findings.slice(0, 4).map((finding) => {
                      const targetFileIdx = files.findIndex((f) => f.name === finding.file)
                      return (
                        <button
                          key={finding.id}
                          type="button"
                          onClick={() => {
                            if (targetFileIdx >= 0) {
                              setActiveFile(targetFileIdx)
                              setBigViewMode('code')
                            }
                          }}
                          className="block w-full text-left rounded-lg bg-aurora-surface-2/80 px-2 py-1 text-[11px] text-amber-300 hover:bg-aurora-surface-2"
                          title={finding.recommendation}
                        >
                          <span className="font-mono text-aurora-accent">{finding.file}:L{finding.line}</span> — {finding.explanation}
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-[11px] text-emerald-400">
                    ✓ Zéro boucle quadratique évitable, zéro requête N+1, zéro fuite de listener et zéro TODO.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      <div className="relative z-10 grid gap-3 px-2 pb-6 pt-3 sm:gap-4 sm:px-6 sm:pb-8 sm:pt-4 lg:grid-cols-[20rem_minmax(0,1fr)] xl:grid-cols-[23rem_minmax(0,1fr)]">
        <CodeViewControlPanel
          assetPack={assetPack}
          canGenerate={canGenerate}
          clearConversation={clearConversation}
          contextFiles={contextFiles}
          conversationTurns={conversationTurns}
          correctionLog={correctionLog}
          designReport={effectiveDesignReport}
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
