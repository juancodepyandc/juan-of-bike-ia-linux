import { startTransition, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import type { CorrectionPass } from '../services/codeAutoCorrection.ts'
import type { CodeFile, FollowUpAnalysis } from '../services/codeOrchestrator.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'
import type { RecoveryEvent } from '../services/ollamaResilience.ts'

type CallbackDeps = {
  setPhase: (detail: string, progress: number) => void
  setProgress: Dispatch<SetStateAction<string>>
  setActiveFile: Dispatch<SetStateAction<number>>
  setConsoleOutput: Dispatch<SetStateAction<string>>
  setCorrectionLog: Dispatch<SetStateAction<CorrectionPass[]>>
  setFiles: Dispatch<SetStateAction<CodeFile[]>>
  setFinalScore: Dispatch<SetStateAction<number>>
  setFollowUpAnalysis: Dispatch<SetStateAction<FollowUpAnalysis | null>>
  setNotes: Dispatch<SetStateAction<string>>
  setRecoveryStatus: Dispatch<SetStateAction<string | null>>
  setStreamCharsTotal: Dispatch<SetStateAction<number>>
  setStreamPreview: Dispatch<SetStateAction<string>>
  setTotalAttempts: Dispatch<SetStateAction<number>>
  setValidationResult: Dispatch<SetStateAction<CodeSandboxResult | null>>
  streamBufferRef: MutableRefObject<string[]>
  streamCharsTotalRef: MutableRefObject<number>
  streamTimerRef: MutableRefObject<ReturnType<typeof setTimeout> | null>
}

export function createCodeViewGenerationCallbacks(deps: CallbackDeps) {
  return {
    setPhase(detail: string, progress: number) {
      deps.setProgress(detail)
      deps.setPhase(detail, progress)
    },
    onToken(token: string) {
      deps.streamBufferRef.current.push(token)
      deps.streamCharsTotalRef.current += token.length
      if (deps.streamTimerRef.current !== null) return
      deps.streamTimerRef.current = setTimeout(() => {
        deps.streamTimerRef.current = null
        const toFlush = deps.streamBufferRef.current.join('')
        deps.streamBufferRef.current = []
        if (!toFlush) return
        deps.setStreamPreview((previous) => {
          const merged = previous + toFlush
          return merged.length > 10_000 ? merged.slice(-7_000) : merged
        })
        deps.setStreamCharsTotal(deps.streamCharsTotalRef.current)
      }, 250)
    },
    onFilesUpdate(newFiles: CodeFile[], newNotes: string) {
      startTransition(() => {
        deps.setFiles(newFiles)
        deps.setActiveFile(0)
        deps.setNotes(newNotes)
      })
    },
    onValidationUpdate(sandboxResult: CodeSandboxResult) {
      startTransition(() => {
        deps.setValidationResult(sandboxResult)
        const output = sandboxResult.steps
          .map((step) => {
            const stepOutput = step.output.length > 4_000
              ? `${step.output.slice(0, 2_500)}\n...[step tronque: ${step.output.length} chars]...\n${step.output.slice(-1_000)}`
              : step.output
            return `$ ${step.command}\n${stepOutput}`
          })
          .join('\n\n')
        deps.setConsoleOutput(
          output.length > 30_000
            ? `${output.slice(0, 12_000)}\n...[tronque]...\n${output.slice(-12_000)}`
            : output,
        )
      })
    },
    onCorrectionLogUpdate(log: CorrectionPass[], attempt: number, score: number) {
      startTransition(() => {
        deps.setCorrectionLog(log.length > 8 ? log.slice(-8) : log)
        deps.setTotalAttempts(attempt)
        deps.setFinalScore(score)
      })
    },
    onFollowUpAnalysis(analysis: FollowUpAnalysis) {
      deps.setFollowUpAnalysis(analysis)
    },
    onRecoveryEvent(event: RecoveryEvent) {
      const labels: Record<RecoveryEvent['action'], string> = {
        retry: 'Reconnexion Ollama...',
        restart_service: 'Redemarrage du service Ollama...',
        model_fallback: `Bascule vers ${event.model}...`,
        health_check: 'Verification sante Ollama...',
        memory_guard: event.error.startsWith('RAM insuffisante')
          ? `Memoire protegee: ${event.error}`
          : 'Protection memoire active...',
        release_models: 'Dechargement memoire Ollama...',
        auto_install_fallback: `Installation du fallback ${event.model}...`,
        exhausted: `Toutes les tentatives echouees: ${event.error}`,
      }
      deps.setRecoveryStatus(labels[event.action] || event.action)
      if (event.action === 'exhausted') {
        setTimeout(() => deps.setRecoveryStatus(null), 5000)
      }
    },
  }
}
