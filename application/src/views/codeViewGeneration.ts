import { startTransition, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import type { ClarificationRequest } from '../components/ClarificationDialog'
import type { SaveDialogData } from '../components/SaveDialog'
import { orchestrateCodeGeneration, classifyClarificationSeverity, buildAutonomousAssumption, serializeCodeFiles, type CodeFile, type CodeOrchestrationResult, type FollowUpAnalysis } from '../services/codeOrchestrator'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodePreflightReport } from '../services/codePreflight'
import { classifyCodeIntent, type CodeIntent } from '../services/codeIntent'
import type { CodeSandboxResult } from '../services/codeSandbox'
import { startDevServer, stopDevServer, type DevServerState } from '../services/codeDevServer'
import { runCodeVisualRenderAudit } from '../services/codeVisualAuditClient'
import { generateSessionTitle } from '../services/sessionAutoNaming'
import { prepareTaskIntelligence } from '../services/taskIntelligence'
import { useCodeWorkspaceStore } from '../stores/codeWorkspaceStore'
import { getErrorMessage } from '../utils/errors'
import { prepareContextFiles } from '../utils/multimodalContext'

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
  preparePack: AnyFn
  prompt: string
  pushMessage: AnyFn
  renameSession: AnyFn
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
    preparePack,
    prompt,
    pushMessage,
    renameSession,
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
