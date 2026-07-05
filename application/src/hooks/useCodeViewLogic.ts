/**
 * useCodeViewLogic — thin facade over codeStreamStore.
 *
 * v82n8 : refactored to a zustand store so in-flight generation survives
 * module navigation. v85 : extended to surface the project session
 * (files / conversation continuity), the real-time ETA, and the
 * online-vs-repo work mode. Public API is additive — existing consumers
 * keep working.
 */
import { useMemo } from 'react'
import {
  useCodeStreamStore,
  type CodeWorkMode,
  type RepoScanInfo,
} from '../stores/codeStreamStore'
import { selectCodeModelForHardware } from '../config/models'
import { useAppStore } from '../stores/appStore'
import { RANDOM_CODE_IDEAS, pickRandom as pickRandomCreative } from '../utils/randomCreativePrompts'
import type { PromptHistoryEntry } from '../utils/promptHistory'
import type { CodeFile, FollowUpKind } from '../services/codeOrchestrator'

export interface UseCodeViewLogic {
  draft: string
  setDraft: (s: string) => void
  streaming: boolean
  streamOutput: string
  error: string | null
  model: string
  submit: () => Promise<void>
  abort: () => void
  reset: () => void
  newProject: () => void
  hasOutput: boolean
  randomCodePreset: () => void
  history: PromptHistoryEntry[]
  recallPrompt: (entry: PromptHistoryEntry) => void
  removeHistory: (prompt: string) => void
  phase: 'idle' | 'research' | 'brand' | 'planning' | 'streaming' | 'validation' | 'done' | 'error'
  phaseMessage: string
  modelUsed: string | null
  brandPrimary: string | null

  // --- v85 : project session (continuity) ---
  files: CodeFile[]
  notes: string
  followUpKind: FollowUpKind | null
  finalScore: number
  totalAttempts: number
  /** True once at least one turn has produced a project (follow-up mode). */
  hasProject: boolean

  // --- v85 : real-time progress + ETA ---
  progressPct: number
  etaSecondsRemaining: number | null
  etaTotalSeconds: number | null
  /** Timestamp the current generation started (for a live elapsed timer). */
  genStartedAt: number | null

  // --- v85e : live narration + enunciate toggle ---
  narration: string
  narrationLog: string[]
  narrateVoice: boolean
  setNarrateVoice: (on: boolean) => void

  // --- v85 : online vs local repo ---
  workMode: CodeWorkMode
  setWorkMode: (mode: CodeWorkMode) => void
  repoPath: string | null
  setRepoPath: (path: string) => void
  repoLabel: string | null
  repoLoaded: boolean
  repoScan: RepoScanInfo | null
  repoBusy: boolean
  repoMessage: string | null
  repoWriteResult: { written: string[]; path: string; ts: number } | null
  pickRepo: () => Promise<void>
  scanRepo: (path?: string) => Promise<void>
  writeRepo: () => Promise<void>
  installRepoDeps: () => Promise<void>
  clearRepoWriteResult: () => void
  activateSession: (sessionId: string) => void
}

export function useCodeViewLogic(): UseCodeViewLogic {
  const hardware = useAppStore((s) => s.hardware)
  const installedModels = useAppStore((s) => s.installedModels)
  const preferredCodeModel = useAppStore((s) => s.codeModel)

  const draft = useCodeStreamStore((s) => s.draft)
  const streaming = useCodeStreamStore((s) => s.streaming)
  const streamOutput = useCodeStreamStore((s) => s.streamOutput)
  const error = useCodeStreamStore((s) => s.error)
  const history = useCodeStreamStore((s) => s.history)
  const phase = useCodeStreamStore((s) => s.phase)
  const phaseMessage = useCodeStreamStore((s) => s.phaseMessage)
  const modelUsed = useCodeStreamStore((s) => s.modelUsed)
  const brandPrimary = useCodeStreamStore((s) => s.brandPrimary)
  const files = useCodeStreamStore((s) => s.files)
  const notes = useCodeStreamStore((s) => s.notes)
  const followUpKind = useCodeStreamStore((s) => s.followUpKind)
  const finalScore = useCodeStreamStore((s) => s.finalScore)
  const totalAttempts = useCodeStreamStore((s) => s.totalAttempts)
  const progressPct = useCodeStreamStore((s) => s.progressPct)
  const etaSecondsRemaining = useCodeStreamStore((s) => s.etaSecondsRemaining)
  const etaTotalSeconds = useCodeStreamStore((s) => s.etaTotalSeconds)
  const genStartedAt = useCodeStreamStore((s) => s.genStartedAt)
  const narration = useCodeStreamStore((s) => s.narration)
  const narrationLog = useCodeStreamStore((s) => s.narrationLog)
  const narrateVoice = useCodeStreamStore((s) => s.narrateVoice)
  const setNarrateVoice = useCodeStreamStore((s) => s.setNarrateVoice)
  const workMode = useCodeStreamStore((s) => s.workMode)
  const repoPath = useCodeStreamStore((s) => s.repoPath)
  const repoLabel = useCodeStreamStore((s) => s.repoLabel)
  const repoLoaded = useCodeStreamStore((s) => s.repoLoaded)
  const repoScan = useCodeStreamStore((s) => s.repoScan)
  const repoBusy = useCodeStreamStore((s) => s.repoBusy)
  const repoMessage = useCodeStreamStore((s) => s.repoMessage)
  const repoWriteResult = useCodeStreamStore((s) => s.repoWriteResult)

  const setDraft = useCodeStreamStore((s) => s.setDraft)
  const submit = useCodeStreamStore((s) => s.submit)
  const abort = useCodeStreamStore((s) => s.abort)
  const reset = useCodeStreamStore((s) => s.reset)
  const newProject = useCodeStreamStore((s) => s.newProject)
  const recallPrompt = useCodeStreamStore((s) => s.recallPrompt)
  const removeHistory = useCodeStreamStore((s) => s.removeHistory)
  const setWorkMode = useCodeStreamStore((s) => s.setWorkMode)
  const setRepoPath = useCodeStreamStore((s) => s.setRepoPath)
  const pickRepo = useCodeStreamStore((s) => s.pickRepo)
  const scanRepo = useCodeStreamStore((s) => s.scanRepo)
  const writeRepo = useCodeStreamStore((s) => s.writeRepo)
  const installRepoDeps = useCodeStreamStore((s) => s.installRepoDeps)
  const clearRepoWriteResult = useCodeStreamStore((s) => s.clearRepoWriteResult)
  const activateSession = useCodeStreamStore((s) => s.activateSession)

  const model = useMemo(
    () => selectCodeModelForHardware(hardware, installedModels ?? [], preferredCodeModel),
    [hardware, installedModels, preferredCodeModel],
  )

  return {
    draft,
    setDraft,
    streaming,
    streamOutput,
    error,
    model,
    submit: () => submit(),
    abort,
    reset,
    newProject,
    hasOutput: streamOutput.length > 0 || files.length > 0,
    randomCodePreset: () => setDraft(pickRandomCreative(RANDOM_CODE_IDEAS)),
    history,
    recallPrompt,
    removeHistory,
    phase,
    phaseMessage,
    modelUsed,
    brandPrimary,
    files,
    notes,
    followUpKind,
    finalScore,
    totalAttempts,
    hasProject: files.length > 0,
    progressPct,
    etaSecondsRemaining,
    etaTotalSeconds,
    genStartedAt,
    narration,
    narrationLog,
    narrateVoice,
    setNarrateVoice,
    workMode,
    setWorkMode,
    repoPath,
    setRepoPath,
    repoLabel,
    repoLoaded,
    repoScan,
    repoBusy,
    repoMessage,
    repoWriteResult,
    pickRepo,
    scanRepo,
    writeRepo,
    installRepoDeps,
    clearRepoWriteResult,
    activateSession,
  }
}
