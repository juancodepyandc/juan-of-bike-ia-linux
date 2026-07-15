import type { PromptHistoryEntry } from '../utils/promptHistory.ts'
import type { CodeFile, FollowUpKind } from '../services/codeOrchestrator.ts'
import type { OllamaMessage } from '../types/app.ts'

export type CodeWorkMode = 'online' | 'repo'

export interface RepoScanInfo {
  files: number
  bytes: number
  branch: string | null
  truncated: boolean
}

export interface CodeStreamState {
  draft: string
  streaming: boolean
  streamOutput: string
  error: string | null
  history: PromptHistoryEntry[]
  lastCompletedAt: number | null
  runId: number
  // Coarse phase used by the View for banner colours. The detailed,
  // human-readable status lives in `phaseMessage`, and the numeric 0..100
  // pipeline progress in `progressPct`.
  phase: 'idle' | 'research' | 'brand' | 'planning' | 'streaming' | 'validation' | 'done' | 'error'
  phaseMessage: string
  errorDialog: {
    title: string
    message: string
    suggestion?: string
  } | null
  modelUsed: string | null
  brandPrimary: string | null

  // --- v85 : project session (conversation continuity) ---
  /** Current project files — passed as existingFiles so follow-ups iterate. */
  files: CodeFile[]
  notes: string
  /** Running conversation. Drives the follow-up analyzer. */
  messages: OllamaMessage[]
  /** What the follow-up analyzer decided for the latest turn. */
  followUpKind: FollowUpKind | null
  finalScore: number
  totalAttempts: number

  // --- v85 : real-time progress + ETA ---
  progressPct: number
  genStartedAt: number | null
  etaSecondsRemaining: number | null
  etaTotalSeconds: number | null

  // --- v85e : live first-person narration of the current task ---
  /** Current "je fais X…" sentence (French, first person). */
  narration: string
  /** History of narration lines for this run (capped). */
  narrationLog: string[]
  /** When true, the narration is spoken aloud (TTS). OFF by default. */
  narrateVoice: boolean

  // --- v85 : online vs local repo work mode ---
  workMode: CodeWorkMode
  repoPath: string | null
  repoLabel: string | null
  repoLoaded: boolean
  repoScan: RepoScanInfo | null
  repoBusy: boolean
  repoMessage: string | null
  repoWriteResult: { written: string[]; path: string; ts: number } | null

  // --- v86 : conversation-scoped code workspaces ---
  activeSessionId: string | null
  sessionSnapshots: Record<string, CodeSessionSnapshot>
}

export interface CodeStreamActions {
  setDraft: (s: string) => void
  submit: (modelOverride?: string) => Promise<void>
  abort: () => void
  /** Soft reset of the live stream (keeps the project + conversation). */
  reset: () => void
  /** Hard reset — start a brand new project (clears files + conversation). */
  newProject: () => void
  recallPrompt: (entry: PromptHistoryEntry) => void
  removeHistory: (prompt: string) => void
  dismissErrorDialog: () => void
  retryAfterError: () => Promise<void>
  /** Toggle spoken narration (TTS). Persisted; OFF by default. */
  setNarrateVoice: (on: boolean) => void

  // --- v85 : work mode + repo ---
  setWorkMode: (mode: CodeWorkMode) => void
  setRepoPath: (path: string) => void
  pickRepo: () => Promise<void>
  scanRepo: (path?: string) => Promise<void>
  writeRepo: () => Promise<void>
  /** v85f : detect + install the project's deps (detached) so it runs on the PC. */
  installRepoDeps: () => Promise<void>
  clearRepoWriteResult: () => void
  activateSession: (sessionId: string) => void
}

export type CodeStreamStore = CodeStreamState & CodeStreamActions

export type CodeSessionSnapshot = {
  draft: string
  streamOutput: string
  error: string | null
  lastCompletedAt: number | null
  phase: CodeStreamState['phase']
  phaseMessage: string
  modelUsed: string | null
  brandPrimary: string | null
  files: CodeFile[]
  notes: string
  messages: OllamaMessage[]
  followUpKind: FollowUpKind | null
  finalScore: number
  totalAttempts: number
  progressPct: number
  genStartedAt: number | null
  etaSecondsRemaining: number | null
  etaTotalSeconds: number | null
  narration: string
  narrationLog: string[]
  workMode: CodeWorkMode
  repoPath: string | null
  repoLabel: string | null
  repoLoaded: boolean
  repoScan: RepoScanInfo | null
  repoMessage: string | null
  repoWriteResult: { written: string[]; path: string; ts: number } | null
}
