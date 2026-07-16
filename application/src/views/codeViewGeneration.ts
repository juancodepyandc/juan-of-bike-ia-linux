import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { orchestrateCodeGeneration, serializeCodeFiles, type CodeFile, type CodeOrchestrationResult, type FollowUpAnalysis } from '../services/codeOrchestrator'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodePreflightReport } from '../services/codePreflight'
import type { CodeIntent } from '../services/codeIntent'
import type { CodeSandboxResult } from '../services/codeSandbox'
import { startDevServer, stopDevServer, type DevServerState } from '../services/codeDevServer'
import { runCodeVisualRenderAudit } from '../services/codeVisualAuditClient'
import { generateSessionTitle } from '../services/sessionAutoNaming'
import { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore'
import { getErrorMessage } from '../utils/errors'
import { prepareCodeViewTaskContext } from './codeViewGenerationContext'
import { createCodeViewGenerationCallbacks } from './codeViewGenerationCallbacks'

export type CodeViewGenerateOptions = { resumeMode?: 'after_reload'; overridePrompt?: string }

type AnyFn = (...args: any[]) => any
type DesignReport = { score: number; missing: string[]; penalties: string[] }

type CodeViewGenerationDeps = {
  abortRef: MutableRefObject<AbortController | null>
  activeModel: string
  activeSessionId: string
  contextFiles: File[]
  diagnosticsBlockingReason: string | null
  executeWithRuntime: AnyFn
  files: CodeFile[]
  getActiveSession: AnyFn
  getRecentMessages: AnyFn
  isGenerating: boolean
  isGeneratingRef: MutableRefObject<boolean>
  preparePack: AnyFn
  prompt: string
  pushMessage: AnyFn
  renameSession: AnyFn
  resumeAfterReloadRef: MutableRefObject<string | null>
  setActiveFile: Dispatch<SetStateAction<number>>
  setClarification: Dispatch<SetStateAction<ClarificationRequest | null>>
  setConsoleOutput: Dispatch<SetStateAction<string>>
  setCorrectionLog: Dispatch<SetStateAction<CorrectionPass[]>>
  setDesignReport: Dispatch<SetStateAction<DesignReport | null>>
  setDevServerState: Dispatch<SetStateAction<DevServerState>>
  setError: Dispatch<SetStateAction<string | null>>
  setFiles: Dispatch<SetStateAction<CodeFile[]>>
  setFinalScore: Dispatch<SetStateAction<number>>
  setFollowUpAnalysis: Dispatch<SetStateAction<FollowUpAnalysis | null>>
  setIntent: Dispatch<SetStateAction<CodeIntent | null>>
  setIsGenerating: Dispatch<SetStateAction<boolean>>
  setNotes: Dispatch<SetStateAction<string>>
  setPreflightReport: Dispatch<SetStateAction<CodePreflightReport | null>>
  setProgress: Dispatch<SetStateAction<string>>
  setRecoveryStatus: Dispatch<SetStateAction<string | null>>
  setSaveDialogData: Dispatch<SetStateAction<SaveDialogData | null>>
  setSaveFeedback: Dispatch<SetStateAction<string | null>>
  setSavedProjectData: Dispatch<SetStateAction<SaveDialogData | null>>
  setSavedProjectPath: Dispatch<SetStateAction<string | null>>
  setSaveTarget: Dispatch<SetStateAction<'workspace' | 'zip' | null>>
  setStreamCharsTotal: Dispatch<SetStateAction<number>>
  setStreamPreview: Dispatch<SetStateAction<string>>
  setTotalAttempts: Dispatch<SetStateAction<number>>
  setValidationResult: Dispatch<SetStateAction<CodeSandboxResult | null>>
  setWorkspaceSnapshot: AnyFn
  streamBufferRef: MutableRefObject<string[]>
  streamCharsTotalRef: MutableRefObject<number>
  streamTimerRef: MutableRefObject<ReturnType<typeof setTimeout> | null>
  visionModel: string
}

export async function runCodeViewGeneration(deps: CodeViewGenerationDeps, options?: CodeViewGenerateOptions) {
  const {
    abortRef,
    activeModel,
    activeSessionId,
    contextFiles,
    diagnosticsBlockingReason,
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
  } = deps
      const activePrompt = (options?.overridePrompt ?? prompt).trim()
      const isResumeRun = options?.resumeMode === 'after_reload'

      if (!activePrompt || isGenerating) return
      if (diagnosticsBlockingReason) {
        setError(diagnosticsBlockingReason)
        setWorkspaceSnapshot({
          sessionId: activeSessionId,
          prompt: activePrompt,
          error: diagnosticsBlockingReason,
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
        sessionId: activeSessionId,
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
          prepare: async ({ setPhase }: { setPhase: (detail: string, progress: number) => void }) => {
            await preparePack(setPhase)
          },
          ollamaModel: activeModel,
          job: async ({ setPhase }: { setPhase: (detail: string, progress: number) => void }) => {
            const { preparedContext, taskContext, userFileDataUrls } = await prepareCodeViewTaskContext({
              activePrompt,
              activeModel,
              visionModel,
              contextFiles,
              setPhase,
              setProgress,
              setClarification,
            })

            const lastUserMessage = [...getRecentMessages('code', 4)].reverse().find((msg) => msg.role === 'user')
            if (!lastUserMessage || lastUserMessage.content !== taskContext.enrichedPrompt) {
              pushMessage('code', { role: 'user', content: taskContext.enrichedPrompt })
            }
            conversationHistory = getRecentMessages('code', 6)

            const controller = new AbortController()
            abortRef.current = controller

            setProgress('Classification du projet et demarrage du pipeline...')
            setPhase('Classification et pipeline expert code...', 15)
            const callbacks = createCodeViewGenerationCallbacks({
              setPhase,
              setProgress,
              setActiveFile,
              setConsoleOutput,
              setCorrectionLog,
              setFiles,
              setFinalScore,
              setFollowUpAnalysis,
              setNotes,
              setRecoveryStatus,
              setStreamCharsTotal,
              setStreamPreview,
              setTotalAttempts,
              setValidationResult,
              streamBufferRef,
              streamCharsTotalRef,
              streamTimerRef,
            })

            // Full orchestration pipeline
            const result: CodeOrchestrationResult = await orchestrateCodeGeneration({
              prompt: activePrompt,
              enrichedPrompt: taskContext.enrichedPrompt,
              conversationHistory: conversationHistory.map((msg: { role: string; content: string }) => ({
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
              ...callbacks,
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
            let visualAuditSummary: string | null = null
            if (result.intent.needsDevServer && result.sandboxResult?.rootPath) {
              setProgress('Demarrage du serveur de dev pour preview...')
              setPhase('Demarrage du dev server...', 95)
              const url = await startDevServer(
                result.sandboxResult.rootPath,
                result.intent,
                setDevServerState,
              )
              if (url) {
                setProgress(`Dev server pret: ${url}. Audit visuel rendu reel...`)
                try {
                  const visualAudit = await runCodeVisualRenderAudit({
                    url,
                    includeVision: Boolean(visionModel),
                    visionModel,
                    waitMs: 2500,
                    signal: controller.signal,
                  })
                  visualAuditSummary = visualAudit.report.summary
                  setDesignReport({
                    score: visualAudit.report.score,
                    missing: visualAudit.report.failedChecks,
                    penalties: visualAudit.report.checks
                      .filter((check) => !check.passed)
                      .map((check) => check.label),
                  })
                } catch (auditError) {
                  visualAuditSummary = `Audit visuel rendu indisponible: ${getErrorMessage(auditError, 'erreur inconnue')}`
                }
              } else {
                setProgress('Preview live indisponible. Les fichiers restent livres pour inspection manuelle.')
              }
            }

            // Set progress message
            const deliverySummary = result.sandboxResult?.ok
              ? `Livraison validee (${result.totalAttempts} passe${result.totalAttempts > 1 ? 's' : ''}, score ${result.finalScore}%).`
              : `Livraison structuree (${result.totalAttempts} passe${result.totalAttempts > 1 ? 's' : ''}, score ${result.finalScore}%). Ameliorations manuelles recommandees.`
            setProgress(visualAuditSummary ? `${deliverySummary} ${visualAuditSummary}` : deliverySummary)
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
          sessionId: activeSessionId,
          prompt: activePrompt,
          pendingResume: false,
          resumeFailCount: 0,
          lastResumeAttempt: null,
        })
      }
}
