import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodeIntent } from '../services/codeIntent'
import type { CodeFile } from '../services/codeOrchestrator'
import type { CodePreflightReport } from '../services/codePreflight'
import type { CodeSandboxResult } from '../services/codeSandbox'

type PersistedCodeWorkspaceState = {
  sessionId: string | null
  prompt: string
  progress: string
  notes: string
  files: CodeFile[]
  activeFile: number
  error: string | null
  validationResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  intent: CodeIntent | null
  totalAttempts: number
  finalScore: number
  consoleOutput: string
  recoveryStatus: string | null
  preflightReport: CodePreflightReport | null
  pendingResume: boolean
  /** Nombre de fois que le resume automatique a ete tente sans succes */
  resumeFailCount: number
  /** Timestamp du dernier resume tente */
  lastResumeAttempt: number | null
  lastUpdatedAt: number | null
}

interface CodeWorkspaceState extends PersistedCodeWorkspaceState {
  setWorkspaceSnapshot: (patch: Partial<PersistedCodeWorkspaceState>) => void
  resetWorkspaceSnapshot: () => void
}

const INITIAL_STATE: PersistedCodeWorkspaceState = {
  sessionId: null,
  prompt: '',
  progress: '',
  notes: '',
  files: [],
  activeFile: 0,
  error: null,
  validationResult: null,
  correctionLog: [],
  intent: null,
  totalAttempts: 0,
  finalScore: 0,
  consoleOutput: '',
  recoveryStatus: null,
  preflightReport: null,
  pendingResume: false,
  resumeFailCount: 0,
  lastResumeAttempt: null,
  lastUpdatedAt: null,
}

const MAX_PERSISTED_FILES = 40
const MAX_TOTAL_FILE_CHARS = 1_200_000

function trimText(value: string, maxLength: number) {
  return value.length <= maxLength ? value : value.slice(-maxLength)
}

function trimFiles(files: CodeFile[]) {
  let remaining = MAX_TOTAL_FILE_CHARS
  const trimmed: CodeFile[] = []

  for (const file of files.slice(0, MAX_PERSISTED_FILES)) {
    if (remaining <= 0) break
    const limit = Math.max(0, Math.min(file.content.length, remaining))
    trimmed.push({
      ...file,
      content: file.content.slice(0, limit),
    })
    remaining -= limit
  }

  return trimmed
}

function sanitizePersistedState(state: PersistedCodeWorkspaceState) {
  return {
    ...state,
    prompt: trimText(state.prompt, 8_000),
    progress: trimText(state.progress, 2_000),
    notes: trimText(state.notes, 30_000),
    error: null,
    consoleOutput: trimText(state.consoleOutput, 80_000),
    recoveryStatus: null,
    files: trimFiles(state.files),
    correctionLog: state.correctionLog.slice(-12),
    validationResult: state.validationResult
      ? {
          ...state.validationResult,
          summary: trimText(state.validationResult.summary, 8_000),
          question: state.validationResult.question ? trimText(state.validationResult.question, 2_000) : null,
          steps: state.validationResult.steps.slice(-12).map((step) => ({
            ...step,
            output: trimText(step.output, 12_000),
          })),
        }
      : null,
  }
}

export const useCodeWorkspaceStore = create<CodeWorkspaceState>()(
  persist(
    (set) => ({
      ...INITIAL_STATE,
      setWorkspaceSnapshot: (patch) =>
        set((state) => ({
          ...state,
          ...patch,
          lastUpdatedAt: Date.now(),
        })),
      resetWorkspaceSnapshot: () => set({ ...INITIAL_STATE, lastUpdatedAt: Date.now() }),
    }),
    {
      name: 'aurora-code-workspace',
      version: 1,
      partialize: (state) => sanitizePersistedState({
        sessionId: state.sessionId,
        prompt: state.prompt,
        progress: state.progress,
        notes: state.notes,
        files: state.files,
        activeFile: state.activeFile,
        error: state.error,
        validationResult: state.validationResult,
        correctionLog: state.correctionLog,
        intent: state.intent,
        totalAttempts: state.totalAttempts,
        finalScore: state.finalScore,
        consoleOutput: state.consoleOutput,
        recoveryStatus: state.recoveryStatus,
        preflightReport: state.preflightReport,
        pendingResume: state.pendingResume,
        resumeFailCount: state.resumeFailCount,
        lastResumeAttempt: state.lastResumeAttempt,
        lastUpdatedAt: state.lastUpdatedAt,
      }),
    },
  ),
)
