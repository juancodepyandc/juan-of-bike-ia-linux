// ---------------------------------------------------------------------------
// CoworkOverlay (v2) — universal AI takeover surface.
//
// Activated via the Cowork button (formerly Focus). Surfaces:
//   - Prompt + voice input (left/top)
//   - Capabilities panel (left)
//   - Streaming events log + plan + audit drawer (right)
//
// Capabilities by runtime:
//   - tauri-desktop → full system rights (filesystem RW, command exec)
//   - web-desktop   → fetch / clipboard / dom (no filesystem)
//   - web-mobile    → read-only + voice dictation (no destructive actions)
//
// The orchestration logic lives in services/coworkPipeline.ts; this file is
// the UI shell. The CoworkConfirmDialog is rendered alongside so the user
// can approve / skip / abort destructive steps mid-run.
// ---------------------------------------------------------------------------

import { useEffect, useMemo, useRef, useState } from 'react'
import type { ModuleId } from '../types/app'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Brain,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Code2,
  Copy,
  Download,
  Eye,
  FileText,
  Globe,
  HardDrive,
  Image as ImageIcon,
  Maximize2,
  Minimize2,
  Mic,
  MicOff,
  Monitor,
  Paperclip,
  Pencil,
  RefreshCw,
  RotateCcw,
  Send,
  Settings as SettingsIcon,
  Smartphone,
  Sparkles,
  ShieldAlert,
  ShieldCheck,
  Square,
  Table as TableIcon,
  Terminal,
  Volume2,
  VolumeX,
  Wifi,
  X,
  Zap,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import LyraCharacter from './voice/LyraCharacter'
import remarkGfm from 'remark-gfm'
import { isTauriRuntime } from '../utils/runtime'
import {
  detectCoworkRuntime,
  getCoworkCapabilities,
  runCoworkPrompt,
} from '../services/coworkPipeline'
import type {
  CoworkActionEvent,
  CoworkCapability,
  CoworkRuntime,
} from '../services/coworkTypes'
import { useCoworkStore } from '../stores/coworkStore'
import { loadSettings, saveSettings } from '../services/coworkSettings'
import {
  coworkEventToAgentState,
  deriveEtaMs,
  useAgentRuntimeStore,
} from '../stores/agentRuntimeStore'
import { appendConnectorOptInClicked, clearAuditLog, readAuditLog, filterAuditEntriesForChip, summariseOptInClicksByHost, listExtractHostsFromAuditEntries, OPTIN_CLICKED_REASON_MARKER, type CoworkAuditEntry, type AuditChipMode } from '../services/coworkAudit'
import {
  pinConnector,
  isConnectorPinned,
  selectPromoteConnectorCandidate,
  connectorIdForHost,
  detectPinConflict,
  readPinnedConnectors,
  type PinConflictDescriptor,
  type PlannerConnectorRecommendation,
} from '../services/coworkConnectorPin'
import {
  fetchDualSignalEffective,
  postDualSignalReset,
  fetchTrendSignalStats,
  postTrendSignalReset,
  type CoworkDualSignalEffective,
} from '../services/coworkExtractionStats'
import {
  extractConnectorHintFromEventDetail,
  summariseConnectorHint,
  extractConnectorTargetFromHint,
} from '../services/coworkConnectorPill'
import CoworkConfirmDialog from './CoworkConfirmDialog'
import CoworkSettingsDialog from './CoworkSettingsDialog'
import CoworkExtractionStatsTile from './CoworkExtractionStatsTile'
import CodeBlock from './CodeBlock'
import {
  artifactLabel,
  clearCoworkProjectThread,
  diffCoworkProjectArtifacts,
  loadCoworkProjectThread,
  previewUrlForCoworkArtifact,
  saveCoworkProjectThread,
  updateCoworkProjectThreadFromEvents,
  type CoworkProjectArtifact,
  type CoworkProjectThread,
} from '../services/coworkProjectThread'

type CoworkOverlayProps = {
  open: boolean
  onClose: () => void
}

// ---------------------------------------------------------------------------
// Chat-mode conversation : pairs of user prompts + Aurora replies, each turn
// keeps a snapshot of its underlying technical events so the user can expand
// "voir les coulisses" if they want to inspect Plan #1, Plan #2, etc.
// ---------------------------------------------------------------------------
type ChatTurn = {
  id: string
  role: 'user' | 'aurora'
  content: string
  at: number
  technical?: CoworkActionEvent[]
  artifacts?: CoworkProjectArtifact[]
  // Marker = this Aurora turn is still streaming (replaced by the final reply
  // once the orchestrator emits a 'reply' event). When the run finishes
  // without a reply, content falls back to the run summary.
  pending?: boolean
}

const CHAT_STORAGE_KEY = 'cowork:chat-history'
const MAX_CHAT_TURNS = 100  // hard cap — evict oldest pairs if overflow

// v82l8 — ExtractDrawer persistence keys.
//   - intent : the textarea content (free-form description of what to extract)
//   - last items : the last successful extract result, rehydrated on mount so
//     the user doesn't lose the table after a reload. Capped at 50KB JSON
//     because some extracts produce 100+ items with rich values, and we
//     don't want to blow through the localStorage budget for one feature.
const EXTRACT_INTENT_KEY = 'aurora_cowork_extract_intent_v1'
const EXTRACT_LAST_ITEMS_KEY = 'aurora_cowork_extract_last_items_v1'
const EXTRACT_RESULT_MAX_BYTES = 50 * 1024  // 50KB cap for the persisted result

type PersistedExtractResult = {
  items: Array<Record<string, unknown>>
  schema: string
  notes: string
  model: string
  inputLength: number
  intent: string
}

// v82l9 — weak-extraction heuristic. We trigger the vision-suggestion banner
// when ANY of these signals fire on a NON-vision result :
//   - items.length === 0 after a 200 OK   (LLM returned an empty array)
//   - items.length === 1 AND that item has no keys (single empty placeholder
//     is just as useless as zero items — the LLM gave up but kept face)
//   - notes contains LLM "I gave up" markers (image-based, no structured data,
//     graphical content, no visible text, no extractable data, etc.)
//   - inputLength < 100 chars AND items.length === 0 (page barely had any
//     text AND the LLM produced nothing — vision will likely rescue this)
// The check is intentionally cheap and string-based ; we don't want to flag
// large successful extracts whose notes happen to mention "image" in passing,
// so we anchor on phrases that imply abandon.
//
// v82la — tuned. Previously inputLength<200 alone was enough to fire the
// banner, which produced false positives on minimalist but valid pages
// (e.g. a clean dashboard summary with 5 items but only 180 chars of raw
// text). We now require BOTH a tiny scrape AND zero items, and we lowered
// the char threshold to 100. We also added the "1-item-with-no-keys" case
// to catch the LLM polite-fail pattern `[{}]`.
function isWeakExtraction(r: {
  items: Array<Record<string, unknown>>
  notes: string
  inputLength: number
}): boolean {
  if (r.items.length === 0) return true
  // Single-item-with-no-keys : LLM emitted a placeholder it didn't fill.
  // Don't flag multi-item arrays — even one populated row is useful signal.
  if (r.items.length === 1) {
    const only = r.items[0] || {}
    const keyCount = Object.keys(only).length
    if (keyCount === 0) return true
  }
  const lc = (r.notes || '').toLowerCase()
  const surrenderPhrases = [
    'image-based',
    'image based',
    'no structured data',
    'no structured content',
    'graphical content',
    'no visible text',
    'no extractable data',
    'cannot extract',
    'unable to extract',
    'page is mostly visual',
    'mostly graphical',
  ]
  if (surrenderPhrases.some((p) => lc.includes(p))) return true
  // Tiny-scrape AND no useful items (the AND was added in v82la — a tiny
  // scrape with even ONE populated row is not weak, it's just terse). The
  // "no useful items" check covers both empty arrays and the single-empty-
  // placeholder pattern flagged just above.
  if (r.inputLength > 0 && r.inputLength < 100) {
    if (r.items.length === 0) return true
    if (r.items.length === 1 && Object.keys(r.items[0] || {}).length === 0) return true
  }
  return false
}

function loadPersistedExtractResult(): PersistedExtractResult | null {
  try {
    if (typeof localStorage === 'undefined') return null
    const raw = localStorage.getItem(EXTRACT_LAST_ITEMS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Defensive validation : items[] must exist and be an array of objects.
    if (
      parsed && typeof parsed === 'object'
      && Array.isArray(parsed.items)
      && typeof parsed.intent === 'string'
    ) {
      return {
        items: parsed.items,
        schema: typeof parsed.schema === 'string' ? parsed.schema : '',
        notes: typeof parsed.notes === 'string' ? parsed.notes : '',
        model: typeof parsed.model === 'string' ? parsed.model : '',
        inputLength: typeof parsed.inputLength === 'number' ? parsed.inputLength : 0,
        intent: parsed.intent,
      }
    }
    return null
  } catch { return null }
}

function loadChatHistory(): ChatTurn[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.slice(-MAX_CHAT_TURNS).map((turn) => ({
          ...turn,
          artifacts: Array.isArray(turn?.artifacts) ? turn.artifacts.slice(0, 6) : undefined,
        }))
      : []
  } catch { return [] }
}

function saveChatHistory(turns: ChatTurn[]): void {
  try {
    if (typeof localStorage === 'undefined') return
    // Strip the technical events before persisting — they bloat localStorage
    // (some runs emit 50+ events with detail strings), and the user only
    // really wants the conversation flow saved across reloads.
    const lite = turns.slice(-MAX_CHAT_TURNS).map((t) => ({
      id: t.id,
      role: t.role,
      content: t.content,
      at: t.at,
      artifacts: t.artifacts?.slice(0, 6).map(sanitizeChatArtifact),
    }))
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(lite))
  } catch { /* quota — ignore */ }
}

function sanitizeChatArtifact(artifact: CoworkProjectArtifact): CoworkProjectArtifact {
  const previewUrl = artifact.previewUrl && artifact.previewUrl.length < 120_000 ? artifact.previewUrl : undefined
  const isCodeLike = artifact.kind === 'code' || artifact.kind === 'game'
  const summaryLimit = isCodeLike ? 40_000 : 600
  return {
    ...artifact,
    previewUrl,
    summary: artifact.summary ? artifact.summary.slice(0, summaryLimit) : undefined,
    sourcePrompt: artifact.sourcePrompt ? artifact.sourcePrompt.slice(0, 600) : undefined,
  }
}

function extractAuroraReply(events: CoworkActionEvent[]): string {
  // The orchestrator emits the final user-facing reply with actionKind='reply'
  // and the actual text in `detail` on a success event. The preceding info
  // event contains raw action JSON for the technical log; never surface it as
  // chat content.
  const replies = events
    .filter((e) => e.kind === 'success' && e.actionKind === 'reply' && e.detail)
    .map((e) => e.detail!)
    .filter((detail) => !looksLikeCoworkReplyActionJson(detail))
  if (replies.length > 0) return replies.join('\n\n')
  // Fallback : use the run-completion summary (last 'success' or 'warn' event).
  const tail = events.slice().reverse().find((e) => /Termine|action.+reussie/i.test(e.message || ''))
  if (tail) return tail.detail || tail.message
  return '_(Aurora a termine sans message — ouvre la console technique pour voir le detail.)_'
}

function looksLikeCoworkReplyActionJson(detail: string): boolean {
  const trimmed = detail.trim()
  if (!trimmed.startsWith('{')) return false
  try {
    const parsed = JSON.parse(trimmed) as { kind?: unknown; message?: unknown }
    return parsed?.kind === 'reply' && typeof parsed.message === 'string'
  } catch {
    return /^\{\s*"kind"\s*:\s*"reply"/.test(trimmed)
  }
}

function renderInteractiveMarkdown(content: string): string {
  return content.replace(/\[\[([^[\]\n]{2,80})\]\]/g, (match, label: string) => {
    const clean = label.trim()
    if (!clean) return match
    return `[${clean}](cowork://explain/${encodeURIComponent(clean)})`
  })
}

function safeDecodeURIComponent(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function buildExplainNotionPrompt(notion: string): string {
  return `Explique-moi la notion "${notion}" dans le contexte de cette conversation, avec un exemple simple, les pieges a eviter, et ce que je dois retenir.`
}

function formatRunClock(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) return '--:--:--'
  return new Date(ts).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatRunDuration(ms: number): string {
  const safeMs = Math.max(0, Math.round(ms))
  if (safeMs < 1000) return `${safeMs} ms`
  const totalSeconds = Math.round(safeMs / 1000)
  if (totalSeconds < 60) return `${totalSeconds} s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds > 0 ? `${minutes} min ${seconds} s` : `${minutes} min`
}

function getCoworkRunMeta(turn: ChatTurn) {
  const events = turn.technical ?? []
  const startedAt = events[0]?.at ?? turn.at
  const lastAt = events[events.length - 1]?.at ?? (turn.pending ? Date.now() : startedAt)
  return {
    startedAt,
    startedLabel: formatRunClock(startedAt),
    durationLabel: formatRunDuration(lastAt - startedAt),
    steps: events.length,
  }
}

export default function CoworkOverlay({ open, onClose }: CoworkOverlayProps) {
  const [prompt, setPrompt] = useState('')
  const [recording, setRecording] = useState(false)
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<CoworkActionEvent[]>([])
  const [permissionsGranted, setPermissionsGranted] = useState(false)
  const [showAudit, setShowAudit] = useState(false)
  const [auditEntries, setAuditEntries] = useState<CoworkAuditEntry[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [sessionsList, setSessionsList] = useState<Array<{ id: string; title: string }>>([])
  // Risk warning : shown once at startup if fullyUnlocked = false. User can
  // dismiss or unlock. State is per-session (not persisted).
  const [showRiskWarning, setShowRiskWarning] = useState(true)

  // v82l7 — free-form structured-extraction panel. Bypasses the planner LLM
  // for the simple "I just want to extract X from this page" use case :
  //   1. user types an intent in plain language
  //   2. we ask the active extension to scrape the active tab + call
  //      /api/cowork/extract-structured (Ollama JSON-mode) directly
  //   3. items[] is rendered in a table with columns auto-derived from the
  //      first item's keys.
  // The full planner -> plan -> execute pipeline remains available via the
  // chat composer ; this panel is a shortcut for "give me data NOW".
  //
  // v82l8 — persistence : the textarea content + the last result (items[])
  // survive reloads via localStorage. The intent rehydrates lazily on mount,
  // saved on every change with a 300ms debounce. The last result is kept
  // under a separate key with a 50KB JSON cap (silent drop if oversize).
  // Explicit "Reset" button clears both.
  const [showExtract, setShowExtract] = useState(false)
  const [extractIntent, setExtractIntent] = useState<string>(() => {
    try {
      if (typeof localStorage === 'undefined') return ''
      return localStorage.getItem(EXTRACT_INTENT_KEY) || ''
    } catch { return '' }
  })
  const [extractRunning, setExtractRunning] = useState(false)
  const [extractResult, setExtractResult] = useState<{
    items: Array<Record<string, unknown>>
    schema: string
    notes: string
    model: string
    inputLength: number
    intent: string
  } | null>(() => loadPersistedExtractResult())
  const [extractError, setExtractError] = useState<string | null>(null)
  // v82l8 — vision : triggered per-call via the dedicated button (runExtract
  // gets `withVision:true`), not a persistent mode. Each click is an explicit
  // user choice — no sticky checkbox state to surprise them on the next run.
  //
  // v82l9 — auto-suggest vision banner. After a TEXT-only extract that comes
  // back weak (empty items, "image-based" notes, raw < 100 chars + empty,
  // single-empty-placeholder ; cf isWeakExtraction), we surface a non-
  // intrusive banner inside the drawer offering a one-click retry with vision.
  //
  // v82la — dismiss scope is INTENTIONALLY in-memory (React useState), NOT
  // localStorage and NOT sessionStorage. Rationale :
  //   - localStorage would be too sticky : if the user clicks "Ignorer" on
  //     page A today, they would not see the banner on unrelated page B
  //     three days later — wrong, the dismiss should be scoped to the
  //     current weak result, not durable.
  //   - sessionStorage is correct in spirit (per-tab) but redundant here :
  //     the banner is reset to suggestVision=false on every new run AND
  //     visionSuggestionDismissed is also reset on every new run (see
  //     runExtract above). So in-memory React state already gives us
  //     exactly the right scope : "dismissed for THIS result only".
  // Do not migrate this to storage. The current behaviour is the design.
  const [suggestVision, setSuggestVision] = useState(false)
  const [visionSuggestionDismissed, setVisionSuggestionDismissed] = useState(false)

  // Debounced persistence for extractIntent (300ms after last change).
  useEffect(() => {
    if (typeof localStorage === 'undefined') return
    const t = setTimeout(() => {
      try { localStorage.setItem(EXTRACT_INTENT_KEY, extractIntent) } catch { /* quota */ }
    }, 300)
    return () => clearTimeout(t)
  }, [extractIntent])

  // Persist last result (silent drop if >50KB JSON to respect localStorage budget).
  useEffect(() => {
    if (typeof localStorage === 'undefined') return
    if (!extractResult) {
      try { localStorage.removeItem(EXTRACT_LAST_ITEMS_KEY) } catch { /* ignore */ }
      return
    }
    try {
      const json = JSON.stringify(extractResult)
      if (json.length <= EXTRACT_RESULT_MAX_BYTES) {
        localStorage.setItem(EXTRACT_LAST_ITEMS_KEY, json)
      } else {
        // Too big — drop. Keep previous if any (don't pollute with truncated junk).
        localStorage.removeItem(EXTRACT_LAST_ITEMS_KEY)
      }
    } catch { /* quota — ignore */ }
  }, [extractResult])

  const resetExtract = () => {
    setExtractIntent('')
    setExtractResult(null)
    setExtractError(null)
    // v82l9 — clear vision-suggestion state alongside the result.
    setSuggestVision(false)
    setVisionSuggestionDismissed(false)
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(EXTRACT_INTENT_KEY)
        localStorage.removeItem(EXTRACT_LAST_ITEMS_KEY)
      }
    } catch { /* ignore */ }
  }

  // v115 — vue unifiee (plus de toggle Chat/Technique). chatMode reste
  // dans le code pour ne pas casser les refs internes mais est verrouille
  // sur true ; le mode "technique" est expose via le drawer "Details
  // techniques" qui montre les events live + capacites.
  // v19 — chat mode (conversation Q/A) : default UI is now a chat thread
  // instead of the raw events log. The technical console remains accessible
  // via a toggle in the header for users who want to see what Aurora does
  // step-by-step.
  const [chatMode] = useState(true)
  const [showConsole, setShowConsole] = useState(false)
  // v28 — voice mode : when ON, Aurora chains a voice_speak (TTS Kokoro)
  // before each finish so replies are read aloud. Combined with the existing
  // dictation button, this delivers a fully hands-free Cowork experience.
  // Persisted in localStorage so the user's preference survives reloads.
  const [voiceMode, setVoiceMode] = useState<boolean>(() => {
    try {
      if (typeof localStorage === 'undefined') return false
      return localStorage.getItem('cowork:voice-mode') === '1'
    } catch { return false }
  })
  useEffect(() => {
    try { localStorage.setItem('cowork:voice-mode', voiceMode ? '1' : '0') } catch { /* quota */ }
  }, [voiceMode])

  // v29 — attached images : drag-drop / paste / file-picker. Each entry holds
  // the raw dataUrl (for vision pre-run) + a thumb-sized base64 for preview.
  // Capped at 3 images per submit to avoid context bloat.
  const [attachedImages, setAttachedImages] = useState<Array<{ id: string; dataUrl: string }>>([])
  // v33 — attached text files : .txt .md .json .py .ts .js etc. Read as text,
  // injected as fenced code blocks in the user prompt for context. Cap 3 files,
  // 100 KB each (~25 KB after fence overhead in prompt context).
  const [attachedTextFiles, setAttachedTextFiles] = useState<Array<{ id: string; name: string; content: string; size: number }>>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const TEXT_FILE_MAX_BYTES = 100 * 1024

  const handleAttachFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const remainingImages = Math.max(0, 3 - attachedImages.length)
    const remainingTexts = Math.max(0, 3 - attachedTextFiles.length)
    for (const file of Array.from(files)) {
      if (file.type.startsWith('image/')) {
        if (remainingImages === 0) continue
        const reader = new FileReader()
        reader.onload = () => {
          const dataUrl = String(reader.result || '')
          if (dataUrl.startsWith('data:image/')) {
            setAttachedImages((prev) => [
              ...prev,
              { id: `img-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, dataUrl },
            ].slice(0, 3))
          }
        }
        reader.readAsDataURL(file)
      } else {
        // v33 — text/code file. Accept by extension since browsers often
        // report empty type for .ts / .py / .md / .yaml etc.
        const lc = file.name.toLowerCase()
        const looksTextual = file.type.startsWith('text/')
          || file.type === 'application/json'
          || file.type === 'application/xml'
          || /\.(txt|md|json|jsonc|yaml|yml|toml|ini|cfg|conf|env|sh|bash|zsh|fish|ps1|bat|py|pyi|ts|tsx|js|jsx|mjs|cjs|java|kt|swift|c|h|cpp|cc|hpp|rs|go|rb|php|lua|pl|sql|html|css|scss|less|xml|svg|csv|log|gitignore|dockerfile|makefile|cmake)$/i.test(lc)
        if (!looksTextual) continue
        if (remainingTexts === 0) continue
        if (file.size > TEXT_FILE_MAX_BYTES * 4) continue  // hard cap raw, before content trim
        const reader = new FileReader()
        reader.onload = () => {
          let content = String(reader.result || '')
          if (content.length > TEXT_FILE_MAX_BYTES) {
            content = content.slice(0, TEXT_FILE_MAX_BYTES) + `\n\n…[tronque a ${TEXT_FILE_MAX_BYTES} octets — fichier original ${(file.size / 1024).toFixed(0)} KB]`
          }
          setAttachedTextFiles((prev) => [
            ...prev,
            { id: `txt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, name: file.name, content, size: file.size },
          ].slice(0, 3))
        }
        reader.readAsText(file)
      }
    }
  }

  const [messages, setMessages] = useState<ChatTurn[]>(() => loadChatHistory())
  // Persist chat history across reloads (lite version, no events).
  useEffect(() => { saveChatHistory(messages) }, [messages])
  const [projectThread, setProjectThread] = useState<CoworkProjectThread>(() => loadCoworkProjectThread())
  const projectThreadRef = useRef<CoworkProjectThread>(projectThread)
  useEffect(() => {
    projectThreadRef.current = projectThread
    saveCoworkProjectThread(projectThread)
  }, [projectThread])

  // v24 — prompt history : up/down arrow recall the last 20 user prompts.
  // Stored in localStorage so it survives reloads. Capped at 20 to keep the
  // recall menu navigable.
  const [promptHistory, setPromptHistory] = useState<string[]>(() => {
    try {
      if (typeof localStorage === 'undefined') return []
      const raw = localStorage.getItem('cowork:prompt-history')
      const parsed = raw ? JSON.parse(raw) : []
      return Array.isArray(parsed) ? parsed.slice(-20) : []
    } catch { return [] }
  })
  const [historyIndex, setHistoryIndex] = useState<number>(-1)
  const draftBeforeHistoryRef = useRef<string>('')

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const recRef = useRef<MediaRecorder | null>(null)
  const recStreamRef = useRef<MediaStream | null>(null)
  const recChunksRef = useRef<Blob[]>([])

  const setAbortController = useCoworkStore((s) => s.setAbortController)
  const abortRun = useCoworkStore((s) => s.abortRun)
  const launchModule = useCoworkStore((s) => s.launchModule)
  const openSettings = useCoworkStore((s) => s.openSettings)

  const runtime: CoworkRuntime = useMemo(() => detectCoworkRuntime(), [])
  const capabilities: CoworkCapability[] = useMemo(() => getCoworkCapabilities(runtime), [runtime])

  // ESC closes (only when not running, no pending confirmation, and the
  // settings dialog isn't open — Settings handles its own ESC first so the
  // user can navigate Settings <-> Cowork independently).
  useEffect(() => {
    if (!open) return
    // Hide risk warning if user has already unlocked.
    const s = loadSettings()
    if (s.fullyUnlocked) setShowRiskWarning(false)
  }, [open])

  // ESC closes (only when not running, no pending confirmation, and the
  // settings dialog isn't open — Settings handles its own ESC first so the
  // user can navigate Settings <-> Cowork independently).
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || running) return
      const state = useCoworkStore.getState()
      if (state.settingsOpen) {
        state.closeSettings()
        return
      }
      if (state.pendingConfirmation) return
      onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, running, onClose])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 60)
  }, [open])

  // Refresh audit when the panel opens or after a run
  useEffect(() => {
    if (showAudit) setAuditEntries(readAuditLog())
  }, [showAudit, running])

  // Load sessions when overlay opens
  useEffect(() => {
    if (!open) return
    void (async () => {
      try {
        const mod = await import('../services/coworkSessionStore')
        const resp = await mod.remoteListSessions()
        if (resp?.ok && Array.isArray(resp.sessions)) {
          setSessionsList(resp.sessions.map((s: any) => ({ id: s.id, title: s.title })))
          if (resp.sessions.length > 0 && !selectedSessionId) setSelectedSessionId(resp.sessions[0].id)
        }
      } catch { /* ignore */ }
    })()
  }, [open])

  const requestPermissions = async () => {
    try {
      if (runtime === 'tauri-desktop') {
        setPermissionsGranted(true)
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        stream.getTracks().forEach((t) => t.stop())
      } catch { /* ignore */ }
      setPermissionsGranted(true)
    } catch {
      setPermissionsGranted(true)
    }
  }

  // v82l7 — direct extraction (bypass planner). Sends a single browser.
  // extract_structured-style command through the extension dispatch endpoint
  // and renders the items[] in a table. The bridge endpoint
  // /api/cowork/extract-structured does the LLM JSON shaping ; the extension
  // background.js picks it up via the 'extract_structured' command kind and
  // forwards the active tab text + intent.
  const runExtract = async (opts?: { withVision?: boolean }) => {
    const intent = extractIntent.trim()
    if (!intent || extractRunning) return
    // v82l8 — vision : extension captures a viewport screenshot and the
    // bridge routes to qwen3-vl. Useful for graphical pages (cards,
    // dashboards, schemas) where the textual scrape misses semantics.
    // The full plumbing (`includeImage`, `imageDataUrl`, qwen3-vl model
    // switch) already exists in extension/background.js + bridge_server.py.
    const withVision = Boolean(opts?.withVision)
    setExtractRunning(true)
    setExtractError(null)
    setExtractResult(null)
    // Reset suggestion state on every new run — the banner is per-result.
    // Dismissed flag is also reset so a fresh weak result re-offers vision.
    setSuggestVision(false)
    setVisionSuggestionDismissed(false)
    try {
      const { getBridgeUrl } = await import('../utils/runtime')
      const root = getBridgeUrl()
      // 1. find an active extension
      const listResp = await fetch(`${root}/api/cowork/extension/list`, {
        signal: AbortSignal.timeout(4000),
      })
      if (!listResp.ok) throw new Error(`bridge ${listResp.status} sur extension/list`)
      const listData = await listResp.json() as { ok?: boolean; extensions?: Array<{ extId: string }> }
      const extId = listData.extensions?.[0]?.extId
      if (!extId) {
        throw new Error('Aucune extension Aurora-Connect active. Installe-la depuis Parametres -> Aurora-Connect.')
      }
      // 2. dispatch the extract_structured command. With vision, we set
      //    includeImage:true — extension captures viewport via captureVisibleTab,
      //    forwards imageDataUrl to the bridge, which switches model to
      //    qwen3-vl:8b automatically (default_model branch in bridge_server.py).
      const dispatchResp = await fetch(`${root}/api/cowork/extension/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extId,
          kind: 'extract_structured',
          payload: withVision ? { intent, includeImage: true } : { intent },
        }),
      })
      const dispatchData = await dispatchResp.json() as { ok: boolean; commandId?: string; error?: string }
      if (!dispatchData.ok || !dispatchData.commandId) {
        throw new Error(dispatchData.error || 'dispatch echoue')
      }
      // 3. wait for the result. The extension scrapes the page (via
      //    content-scrape.js, which already has smart-retry + iframe sweep)
      //    and forwards the text to /api/cowork/extract-structured ; Ollama
      //    can take up to 120s on the bridge side, so we wait 90s on the
      //    extension await endpoint.
      const awaitResp = await fetch(
        `${root}/api/cowork/extension/await-result?commandId=${dispatchData.commandId}&wait=90000`,
        { signal: AbortSignal.timeout(95_000) },
      )
      if (!awaitResp.ok) throw new Error(`bridge ${awaitResp.status} sur await-result`)
      const awaitData = await awaitResp.json() as {
        ok: boolean
        result?: { ok: boolean; data?: unknown; error?: string }
      }
      if (!awaitData.ok || !awaitData.result) {
        throw new Error('extension n a pas repondu (timeout)')
      }
      if (!awaitData.result.ok) {
        throw new Error(awaitData.result.error || 'extension command failed')
      }
      // 4. payload returned by background.js extract_structured branch :
      //    { intent, items[], schema, notes, model, inputLength, hadVision }
      const data = awaitData.result.data as {
        items?: Array<Record<string, unknown>>
        schema?: string
        notes?: string
        model?: string
        inputLength?: number
        intent?: string
      } | null
      if (!data || !Array.isArray(data.items)) {
        throw new Error('reponse malformee (items[] manquant)')
      }
      const finalResult = {
        items: data.items,
        schema: data.schema || '',
        notes: data.notes || '',
        model: data.model || '',
        inputLength: data.inputLength || 0,
        intent: data.intent || intent,
      }
      setExtractResult(finalResult)
      // v82l9 — if this was a TEXT-only run and the result looks weak, surface
      // the auto-suggest banner. We only suggest when the user hasn't already
      // tried vision (withVision=false) — otherwise we'd loop offering the same
      // tool that already underperformed.
      if (!withVision && isWeakExtraction(finalResult)) {
        setSuggestVision(true)
      }
    } catch (err) {
      setExtractError(err instanceof Error ? err.message : String(err))
    } finally {
      setExtractRunning(false)
    }
  }

  // v24 — handle slash commands locally (no LLM call). Returns true if
  // the prompt was consumed as a slash command, false otherwise.
  const handleSlashCommand = (text: string): boolean => {
    const t = text.trim().toLowerCase()
    if (t === '/clear') {
      setMessages([])
      setProjectThread(clearCoworkProjectThread())
      return true
    }
    if (t === '/redo' || t === '/repeat') {
      // v40 — re-soumet le dernier user prompt. Pour qu il y ait un point
      // de comparaison/replay, on garde la paire precedente intacte (l user
      // verra deux paires user/aurora pour la meme question).
      const lastUser = [...messages].reverse().find((m) => m.role === 'user' && m.content)
      if (!lastUser) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: 'Aucune question precedente a rejouer. Pose-en une d abord.',
          at: Date.now(),
        }])
        return true
      }
      setPrompt('')
      // Defer to next tick so submit() (defined after handleSlashCommand)
      // is bound and stable. setTimeout(0) is sufficient.
      setTimeout(() => { void submit(lastUser.content) }, 0)
      return true
    }
    if (t === '/clear last') {
      // v38 — efface uniquement la derniere paire user/aurora.
      // Utile pour annuler un faux pas sans perdre toute la conversation.
      setMessages((prev) => {
        if (prev.length === 0) return prev
        // Trouve la derniere bulle aurora (probablement en fin de tableau).
        const lastAuroraIdx = prev.map((m) => m.role).lastIndexOf('aurora')
        // Trouve la bulle user qui la precede.
        let dropFrom = -1
        if (lastAuroraIdx >= 0) {
          for (let i = lastAuroraIdx - 1; i >= 0; i--) {
            if (prev[i].role === 'user') { dropFrom = i; break }
          }
        }
        // Si on n a trouve qu une bulle aurora orpheline (slash command par
        // exemple), on l efface elle seule.
        if (dropFrom < 0 && lastAuroraIdx >= 0) return prev.slice(0, lastAuroraIdx)
        if (dropFrom < 0) return prev  // rien a effacer
        return prev.slice(0, dropFrom)
      })
      return true
    }
    if (t === '/stop') {
      abortRun()
      return true
    }
    if (t === '/export') {
      const md = messages.map((m) => {
        const who = m.role === 'user' ? '## Toi' : '## Aurora'
        return `${who}\n\n${m.content}\n`
      }).join('\n---\n\n')
      navigator.clipboard?.writeText(md).catch(() => {})
      // Surface confirmation as a synthetic Aurora bubble so the user sees the action.
      setMessages((prev) => [...prev, {
        id: `slash-${Date.now()}`,
        role: 'aurora',
        content: `Conversation copiee dans le presse-papiers (${md.length} caracteres, ${messages.length} messages).`,
        at: Date.now(),
      }])
      return true
    }
    if (t === '/memory' || t === '/memory list') {
      void (async () => {
        const { loadSettings } = await import('../services/coworkSettings')
        const settings = loadSettings()
        const list = settings.userMemory.length === 0
          ? '_(Aucun fait memorise pour le moment.)_'
          : settings.userMemory.map((e) => `- **${e.fact}**${e.tags?.length ? ` _[${e.tags.join('|')}]_` : ''}`).join('\n')
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `## Memoire utilisateur (${settings.userMemory.length}/50)\n\n${list}`,
          at: Date.now(),
        }])
      })()
      return true
    }
    if (t === '/memory clear') {
      void (async () => {
        const { loadSettings, saveSettings } = await import('../services/coworkSettings')
        const settings = loadSettings()
        const before = settings.userMemory.length
        saveSettings({ ...settings, userMemory: [] })
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Memoire effacee : ${before} fait(s) supprime(s).`,
          at: Date.now(),
        }])
      })()
      return true
    }
    if (t === '/help' || t === '/?') {
      // v42 — /help refondu par categories pour lisibilite
      setMessages((prev) => [...prev, {
        id: `slash-${Date.now()}`,
        role: 'aurora',
        content: [
          '## Slash commands',
          '',
          '### 💬 Conversation',
          '- `/clear` — efface toute la conversation',
          '- `/clear last` — efface uniquement la derniere paire user/aurora',
          '- `/redo` ou `/repeat` — rejoue le dernier prompt utilisateur',
          '- `/stop` — arrete le run en cours',
          '- `/export` — copie tout le chat en markdown',
          '',
          '### 🎛️ Modes',
          '- `/voice [on|off]` — toggle mode vocal (TTS Kokoro)',
          '- `/console [on|off]` — toggle console technique a droite',
          '',
          '### 🧠 Memoire user',
          '- `/memory` — liste les faits memorises',
          '- `/memory clear` — efface tous les faits memorises',
          '',
          '### 💾 Templates de conversation',
          '- `/save <nom>` — sauvegarde la conversation comme template',
          '- `/load <nom>` — recharge un template (vide la conv courante)',
          '- `/templates` — liste les templates sauvegardes',
          '- `/template-delete <nom>` — efface un template',
          '',
          '### 🔍 Debug & info',
          '- `/diag` — healthcheck bridge / extension / ollama / connecteurs',
          '- `/connectors` — liste detaillee des connecteurs (actifs / quota / non configures)',
          '- `/about` — info systeme (runtime, modeles, totaux)',
          '',
          '### ❓ Aide',
          '- `/help` — cette aide',
          '',
          '---',
          '',
          '_Astuces clavier :_',
          '- _↑ / ↓ dans le composer rappellent tes 20 derniers prompts_',
          '- _drag-drop image OU fichier code/texte (.ts .py .json .md ...) dans le composer_',
          '- _Cmd+V pour coller une image directement_',
          '- _hover sur une bulle user pour Editer/Copier, sur une bulle Aurora pour Refaire/Copier_',
        ].join('\n'),
        at: Date.now(),
      }])
      return true
    }
    // v34 — templates : save/load/list/delete conversations as named templates.
    // Stored in localStorage under 'cowork:template:<name>' (lite version
    // without technical events, like loadChatHistory).
    if (t.startsWith('/save ')) {
      const name = text.trim().slice('/save '.length).trim()
      if (!name || /[/\\]/.test(name)) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: 'Usage : `/save <nom>` (sans `/` ni `\\`). Exemple : `/save audit-page`.',
          at: Date.now(),
        }])
        return true
      }
      try {
        const lite = messages.filter((m) => !m.pending).map((m) => ({
          id: m.id, role: m.role, content: m.content, at: m.at,
        }))
        localStorage.setItem(`cowork:template:${name}`, JSON.stringify(lite))
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Template **${name}** sauvegardé (${lite.length} message${lite.length > 1 ? 's' : ''}). Recharge avec \`/load ${name}\`.`,
          at: Date.now(),
        }])
      } catch (err) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Echec sauvegarde : ${err instanceof Error ? err.message : String(err)} (probablement quota localStorage).`,
          at: Date.now(),
        }])
      }
      return true
    }
    if (t.startsWith('/load ')) {
      const name = text.trim().slice('/load '.length).trim()
      if (!name) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: 'Usage : `/load <nom>`. Liste les templates avec `/templates`.',
          at: Date.now(),
        }])
        return true
      }
      try {
        const raw = localStorage.getItem(`cowork:template:${name}`)
        if (!raw) {
          setMessages((prev) => [...prev, {
            id: `slash-${Date.now()}`,
            role: 'aurora',
            content: `Template **${name}** introuvable. Liste : \`/templates\`.`,
            at: Date.now(),
          }])
          return true
        }
        const parsed = JSON.parse(raw)
        if (Array.isArray(parsed)) {
          setMessages(parsed as ChatTurn[])
        }
      } catch (err) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Echec chargement : ${err instanceof Error ? err.message : String(err)}.`,
          at: Date.now(),
        }])
      }
      return true
    }
    if (t === '/templates' || t === '/load') {
      try {
        const keys: string[] = []
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i)
          if (k && k.startsWith('cowork:template:')) keys.push(k.replace('cowork:template:', ''))
        }
        keys.sort()
        const list = keys.length === 0
          ? '_(Aucun template sauvegarde. Cree-en un avec `/save <nom>`.)_'
          : keys.map((k) => `- \`${k}\``).join('\n')
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `## Templates sauvegardes (${keys.length})\n\n${list}\n\nRecharge : \`/load <nom>\` · Efface : \`/template-delete <nom>\``,
          at: Date.now(),
        }])
      } catch (err) {
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Echec listing : ${err instanceof Error ? err.message : String(err)}.`,
          at: Date.now(),
        }])
      }
      return true
    }
    if (t.startsWith('/template-delete ')) {
      const name = text.trim().slice('/template-delete '.length).trim()
      if (!name) return false
      try {
        localStorage.removeItem(`cowork:template:${name}`)
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: `Template **${name}** supprime.`,
          at: Date.now(),
        }])
      } catch { /* ignore */ }
      return true
    }
    // v37 — clavier-first toggles : /voice et /console
    if (t === '/voice' || t === '/voice on' || t === '/voice off') {
      const next = t === '/voice off' ? false : t === '/voice on' ? true : !voiceMode
      setVoiceMode(next)
      setMessages((prev) => [...prev, {
        id: `slash-${Date.now()}`,
        role: 'aurora',
        content: next
          ? 'Mode vocal **active** 🔊 — Aurora lira ses reponses a voix haute (TTS Kokoro).'
          : 'Mode vocal **desactive** 🔇 — reponses texte uniquement.',
        at: Date.now(),
      }])
      return true
    }
    if (t === '/console' || t === '/console on' || t === '/console off') {
      const next = t === '/console off' ? false : t === '/console on' ? true : !showConsole
      setShowConsole(next)
      setMessages((prev) => [...prev, {
        id: `slash-${Date.now()}`,
        role: 'aurora',
        content: next
          ? 'Console technique **ouverte** — affiche les events live a droite du chat.'
          : 'Console technique **fermee** — l affichage reste cache jusqu au prochain toggle.',
        at: Date.now(),
      }])
      return true
    }
    if (t === '/about') {
      // v39 — info statique sur le systeme Cowork (complete /diag healthcheck
      // et /connectors detail). Utile pour rapport bug ou comprendre ce qui
      // tourne sans aller dans Settings.
      void (async () => {
        const { CONNECTORS } = await import('../services/coworkConnectors')
        const { loadSettings } = await import('../services/coworkSettings')
        const settings = loadSettings()
        const enabled = Object.entries(settings.connectors).filter(([_, c]) => c.enabled && c.apiKey).length
        let mainModel = 'inconnu'
        let visionModel = 'inconnu'
        try {
          const { useAppStore } = await import('../stores/appStore')
          const state = useAppStore.getState() as { mainModel?: string; visionModel?: string }
          mainModel = state.mainModel ?? 'inconnu'
          visionModel = state.visionModel ?? 'qwen3-vl:30b'
        } catch { /* noop */ }
        const lines = [
          '## Aurora Cowork',
          '',
          `- **Runtime detecte** : ${runtime}`,
          `- **Module actif** : ${launchModule}`,
          `- **Mode chat** : ${chatMode ? 'ON' : 'OFF (mode Technique)'}`,
          `- **Voix** : ${voiceMode ? 'ON 🔊' : 'OFF'}`,
          `- **Console** : ${showConsole ? 'visible' : 'cachee'}`,
          '',
          `- **Modele LLM principal** : \`${mainModel}\``,
          `- **Modele vision** : \`${visionModel}\``,
          '',
          `- **Connecteurs disponibles** : ${Object.keys(CONNECTORS).length}`,
          `- **Connecteurs configures (cle OK)** : ${enabled}`,
          `- **Faits memorises** : ${settings.userMemory.length}/50`,
          `- **Messages dans la conversation** : ${messages.filter((t) => !t.pending).length}`,
          '',
          '_Pour debugger : \`/diag\` (healthcheck), \`/connectors\` (liste detaillee)._',
        ]
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: lines.join('\n'),
          at: Date.now(),
        }])
      })()
      return true
    }
    if (t === '/connectors') {
      // v36 — liste detaillee des connecteurs avec leur etat
      void (async () => {
        const { loadSettings } = await import('../services/coworkSettings')
        const { CONNECTORS } = await import('../services/coworkConnectors')
        const settings = loadSettings()
        const all = Object.keys(CONNECTORS).sort()
        const lines: string[] = [`## Connecteurs (${all.length} disponibles)`, '']
        const enabled: string[] = []
        const exhausted: string[] = []
        const disabled: string[] = []
        for (const id of all) {
          const cfg = settings.connectors[id as keyof typeof settings.connectors]
          if (!cfg) { disabled.push(id); continue }
          const isQuotaExhausted = cfg.lastCheck && /quota|exhausted|429|402|limit/i.test(cfg.lastCheck.message || '')
          if (cfg.enabled && cfg.apiKey && !isQuotaExhausted) enabled.push(id)
          else if (cfg.enabled && isQuotaExhausted) exhausted.push(id)
          else disabled.push(id)
        }
        if (enabled.length > 0) {
          lines.push(`### ✅ Actifs (${enabled.length})`)
          for (const id of enabled) {
            const meta = CONNECTORS[id as keyof typeof CONNECTORS]
            lines.push(`- **${id}** — ${meta?.label ?? ''}`)
          }
          lines.push('')
        }
        if (exhausted.length > 0) {
          lines.push(`### ⚠️ Quota epuise (${exhausted.length})`)
          for (const id of exhausted) lines.push(`- **${id}** (clear auto au prochain run reussi)`)
          lines.push('')
        }
        const sample = disabled.slice(0, 12)
        lines.push(`### ⚙️ Non configures (${disabled.length})`)
        lines.push(sample.map((id) => `\`${id}\``).join(' · ') + (disabled.length > sample.length ? ` · _+${disabled.length - sample.length} autres_` : ''))
        lines.push('')
        lines.push('_Configure une cle dans Settings -> Cowork -> Connecteurs._')
        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: lines.join('\n'),
          at: Date.now(),
        }])
      })()
      return true
    }
    if (t === '/diag') {
      // v31 — diagnostic instantane des composants Cowork. Affiche bridge,
      // extension, Ollama, connecteurs configures dans une bulle Aurora.
      void (async () => {
        const { getBridgeUrl } = await import('../utils/runtime')
        const { loadSettings } = await import('../services/coworkSettings')
        const base = getBridgeUrl()
        const lines: string[] = ['## Diagnostic Cowork', '']

        // Bridge
        try {
          const r = await fetch(`${base}/api/_dev/status`, { signal: AbortSignal.timeout(3000) })
          if (r.ok) {
            const d = await r.json() as { bootedAt?: number; needsReload?: boolean }
            const uptime = d.bootedAt ? Math.round((Date.now() / 1000 - d.bootedAt) / 60) : '?'
            lines.push(`- ✅ **Bridge** \`${base || 'http://127.0.0.1:3001'}\` — uptime ${uptime}m${d.needsReload ? ' ⚠️ reload pending' : ''}`)
          } else {
            lines.push(`- ❌ **Bridge** \`${base || 'http://127.0.0.1:3001'}\` — HTTP ${r.status}`)
          }
        } catch (err) {
          lines.push(`- ❌ **Bridge** injoignable : ${err instanceof Error ? err.message : String(err)}`)
        }

        // Extension Aurora-Connect
        try {
          const r = await fetch(`${base}/api/cowork/extension/list`, { signal: AbortSignal.timeout(3000) })
          if (r.ok) {
            const d = await r.json() as { extensions?: Array<{ extId: string; lastSeenAgoMs: number }> }
            const exts = d.extensions ?? []
            if (exts.length === 0) {
              lines.push('- ⚠️ **Extension** Aurora-Connect non detectee (verifie chrome://extensions, recharge si besoin)')
            } else {
              const fresh = exts.map((e) => `${(e.lastSeenAgoMs / 1000).toFixed(0)}s`).join(', ')
              lines.push(`- ✅ **Extension** ${exts.length} active(s) — poll il y a ${fresh}`)
            }
          } else {
            lines.push(`- ❌ **Extension list** HTTP ${r.status}`)
          }
        } catch {
          lines.push('- ❌ **Extension** injoignable (bridge probablement HS)')
        }

        // Ollama (via runtime/inspect)
        try {
          const r = await fetch(`${base}/api/runtime/inspect`, { signal: AbortSignal.timeout(5000) })
          if (r.ok) {
            const d = await r.json() as { ollama?: { available?: boolean; models?: string[] } }
            if (d.ollama?.available) {
              const models = (d.ollama.models ?? []).slice(0, 3).join(', ')
              lines.push(`- ✅ **Ollama** disponible — modeles : ${models || '(aucun chargé)'}`)
            } else {
              lines.push('- ⚠️ **Ollama** non disponible — lance `ollama serve` ou redemarre start-aurora.bat')
            }
          } else {
            lines.push(`- ❌ **Ollama** HTTP ${r.status}`)
          }
        } catch {
          lines.push('- ⚠️ **Ollama** non testable depuis le bridge (endpoint runtime/inspect absent)')
        }

        // Connecteurs configures
        try {
          const settings = loadSettings()
          const enabled = Object.entries(settings.connectors)
            .filter(([_, c]) => c.enabled && c.apiKey)
            .map(([id]) => id)
          const exhausted = Object.entries(settings.connectors)
            .filter(([_, c]) => c.lastCheck && /quota|exhausted|429|402|limit/i.test(c.lastCheck.message || ''))
            .map(([id]) => id)
          lines.push(`- ${enabled.length > 0 ? '✅' : 'ℹ️'} **Connecteurs configures** : ${enabled.length}${enabled.length > 0 ? ` (${enabled.slice(0, 6).join(', ')}${enabled.length > 6 ? '…' : ''})` : ''}`)
          if (exhausted.length > 0) {
            lines.push(`- ⚠️ **Quota epuise** sur : ${exhausted.join(', ')} (clear auto au prochain run reussi)`)
          }
          // Memoire user
          lines.push(`- ℹ️ **Memoire Aurora** : ${settings.userMemory.length}/50 faits memorises`)
        } catch (err) {
          lines.push(`- ❌ **Settings** illisibles : ${err instanceof Error ? err.message : String(err)}`)
        }

        // Mode chat
        lines.push('')
        lines.push(`_Mode actuel : Voix ${voiceMode ? 'ON 🔊' : 'OFF'} · Console ${showConsole ? 'visible' : 'cachee'} · ${messages.filter((t) => !t.pending).length} messages en historique._`)

        setMessages((prev) => [...prev, {
          id: `slash-${Date.now()}`,
          role: 'aurora',
          content: lines.join('\n'),
          at: Date.now(),
        }])
      })()
      return true
    }
    return false
  }

  // v33 — derive language hint from file extension for fenced code block
  const guessFenceLang = (name: string): string => {
    const m = name.toLowerCase().match(/\.([a-z0-9]+)$/)
    if (!m) return ''
    const ext = m[1]
    const map: Record<string, string> = {
      ts: 'ts', tsx: 'tsx', js: 'js', jsx: 'jsx', mjs: 'js', cjs: 'js',
      py: 'python', pyi: 'python', rb: 'ruby', go: 'go', rs: 'rust',
      java: 'java', kt: 'kotlin', swift: 'swift', c: 'c', h: 'c',
      cpp: 'cpp', cc: 'cpp', hpp: 'cpp', php: 'php', lua: 'lua',
      sh: 'bash', bash: 'bash', zsh: 'bash', ps1: 'powershell', bat: 'batch',
      sql: 'sql', html: 'html', css: 'css', scss: 'scss', less: 'less',
      xml: 'xml', svg: 'xml', md: 'markdown', json: 'json', jsonc: 'json',
      yaml: 'yaml', yml: 'yaml', toml: 'toml', ini: 'ini', csv: 'csv',
      env: 'bash', dockerfile: 'dockerfile', makefile: 'makefile',
    }
    return map[ext] ?? ''
  }

  const submit = async (text: string) => {
    const finalPrompt = text.trim()
    if (!finalPrompt) return
    // v24 — slash commands are intercepted locally, before any LLM call.
    // v47 — they also bypass the `running` guard so that /stop, /voice, /console,
    // /export, /memory, /diag, /about, /help can all be used mid-turn. /clear
    // and /redo stay deliberately permissive too — the user knows what they want.
    if (finalPrompt.startsWith('/')) {
      const consumed = handleSlashCommand(finalPrompt)
      if (consumed) {
        setPrompt('')
        return
      }
      // v46 — unknown slash command : show a helpful error rather than letting
      // the typo /exprt reach the LLM. Heuristic : first whitespace-token must
      // be /<word> with no further slashes, so /etc/hosts (a path) or queries
      // like "/ help" still fall through as natural language.
      const firstTok = finalPrompt.split(/\s+/)[0]
      if (/^\/[a-z][a-z0-9-]*$/i.test(firstTok)) {
        setMessages((prev) => [...prev, {
          id: `slash-unknown-${Date.now()}`,
          role: 'aurora',
          content: `Commande inconnue : \`${firstTok}\`. Tape \`/help\` pour voir la liste des commandes.`,
          at: Date.now(),
        }])
        setPrompt('')
        return
      }
    }
    // Natural-language prompts must wait for the current turn.
    if (running) return
    // v24 — record this prompt in history (LRU 20).
    setPromptHistory((prev) => {
      const next = [...prev.filter((p) => p !== finalPrompt), finalPrompt].slice(-20)
      try { localStorage.setItem('cowork:prompt-history', JSON.stringify(next)) } catch { /* quota */ }
      return next
    })
    setHistoryIndex(-1)
    draftBeforeHistoryRef.current = ''
    setRunning(true)
    // Reset the live events for this new turn AND push the user msg + a
    // pending Aurora msg into the chat thread. Events accumulate as the
    // run progresses and are attached to the Aurora msg on completion.
    // v33 — if text files are attached, prepend their content as fenced code
    // blocks at the top of the prompt that gets shipped to the planner. The
    // user-displayed bubble keeps just the typed question for cleanliness.
    const textFilesAtSubmit = attachedTextFiles.slice()
    let promptForLLM = finalPrompt
    if (textFilesAtSubmit.length > 0) {
      const filesBlock = textFilesAtSubmit.map((f) => {
        const lang = guessFenceLang(f.name)
        return `### ${f.name}\n\`\`\`${lang}\n${f.content}\n\`\`\``
      }).join('\n\n')
      promptForLLM = `## Fichiers joints par l user :\n\n${filesBlock}\n\n## Question :\n${finalPrompt}`
    }
    const turnId = `t-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    // Display bubble shows just the user's typed text + a footer listing
    // attached files (if any), so the chat thread stays readable.
    const userBubbleContent = textFilesAtSubmit.length > 0
      ? `${finalPrompt}\n\n_${textFilesAtSubmit.length} fichier${textFilesAtSubmit.length > 1 ? 's' : ''} joint${textFilesAtSubmit.length > 1 ? 's' : ''} : ${textFilesAtSubmit.map((f) => f.name).join(', ')}_`
      : finalPrompt
    const userTurn: ChatTurn = { id: `${turnId}-u`, role: 'user', content: userBubbleContent, at: Date.now() }
    const auroraTurn: ChatTurn = { id: `${turnId}-a`, role: 'aurora', content: '', at: Date.now(), pending: true, technical: [] }
    setMessages((prev) => [...prev, userTurn, auroraTurn].slice(-MAX_CHAT_TURNS))
    setEvents([])
    setPrompt('')
    const localEvents: CoworkActionEvent[] = []
    const ctrl = new AbortController()
    setAbortController(ctrl)
    const coworkStartedAt = Date.now()
    useAgentRuntimeStore.getState().setAgentRuntime('manager', {
      state: 'planning',
      startedAt: coworkStartedAt,
      progress: 6,
      etaMs: deriveEtaMs(coworkStartedAt, 6),
      activeTool: 'cowork',
      detail: 'Mission Cowork recue.',
      collaborators: [launchModule],
    })
    useAgentRuntimeStore.getState().setModuleRuntime(launchModule, {
      state: 'handoff',
      startedAt: coworkStartedAt,
      progress: 10,
      etaMs: deriveEtaMs(coworkStartedAt, 10),
      activeTool: 'cowork',
      detail: 'Maia transmet la mission au module actif.',
      collaborators: ['manager'],
    })
    useAgentRuntimeStore.getState().recordHandoff('manager', launchModule, finalPrompt.slice(0, 140))
    useAgentRuntimeStore.getState().setVoiceActive(voiceMode)
    // v21 — pass the previous conversation turns (excluding the brand-new
    // user/aurora pair we just appended) to the planner so it can resolve
    // implicit references in follow-up questions.
    const conversationHistory = messages
      .filter((t) => !t.pending && t.content)
      .slice(-10)
      .map((t) => ({ role: t.role, content: t.content }))

    // v29 — pre-run vision_describe on each attached image so Aurora has the
    // visual context as plain text before planning. We do this on the bridge
    // via the executor (Tauri) or fail gracefully if vision is unavailable.
    let attachedImageDescriptions: string[] = []
    const imagesAtSubmit = attachedImages.slice()
    if (imagesAtSubmit.length > 0) {
      try {
        const { runAction } = await import('../services/coworkExecutor')
        for (const img of imagesAtSubmit) {
          const r = await runAction(
            { kind: 'vision_describe', imageDataUrl: img.dataUrl, question: 'Decris precisement le contenu : texte visible, layout, couleurs, sections, chiffres, erreurs eventuelles, contexte general.' },
            runtime,
            '',
            ctrl.signal,
          )
          if (r.ok && (r.output || (r.data && (r.data as { description?: string }).description))) {
            const desc = r.output || (r.data as { description?: string }).description || ''
            attachedImageDescriptions.push(desc)
          } else {
            attachedImageDescriptions.push(`(vision a echoue : ${r.error || 'unknown'})`)
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        attachedImageDescriptions.push(`(vision indisponible : ${msg})`)
      }
      // Clear the attached images NOW — they've been processed, the user
      // can attach a new set for the next prompt.
      setAttachedImages([])
    }
    // v33 — clear text files now too (their content was already captured in
    // promptForLLM and userBubbleContent earlier in the function).
    if (textFilesAtSubmit.length > 0) setAttachedTextFiles([])
    try {
      await runCoworkPrompt(
        promptForLLM,
        runtime,
        (ev) => {
          localEvents.push(ev)
          const agentState = coworkEventToAgentState(ev)
          const progress = ev.actionKind === 'finish'
            ? 100
            : Math.min(96, Math.max(18, 18 + localEvents.length * 6))
          useAgentRuntimeStore.getState().setAgentRuntime('manager', {
            state: agentState,
            startedAt: coworkStartedAt,
            progress,
            etaMs: deriveEtaMs(coworkStartedAt, progress),
            activeTool: 'cowork',
            detail: ev.message,
            collaborators: [launchModule],
          })
          useAgentRuntimeStore.getState().setModuleRuntime(launchModule, {
            state: agentState === 'planning' ? 'working' : agentState,
            startedAt: coworkStartedAt,
            progress,
            etaMs: deriveEtaMs(coworkStartedAt, progress),
            activeTool: 'cowork',
            detail: ev.detail || ev.message,
            collaborators: ['manager'],
          })
          if (ev.kind === 'warn' || ev.actionKind === 'think' || ev.actionKind === 'think_long') {
            useAgentRuntimeStore.getState().recordHandoff('manager', launchModule, ev.message)
          }
          setEvents((prev) => [...prev, ev])
          // Stream technical events into the pending Aurora turn so the
          // console drawer can show them live.
          setMessages((prev) => prev.map((t) => t.id === auroraTurn.id
            ? { ...t, technical: [...localEvents] }
            : t))
        },
        ctrl.signal,
        {
          module: launchModule,
          conversationHistory,
          voiceMode,
          attachedImageDescriptions,
          projectThread: projectThreadRef.current,
        },
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      const errEv: CoworkActionEvent = { kind: 'error', message: msg, at: Date.now() }
      localEvents.push(errEv)
      useAgentRuntimeStore.getState().setAgentRuntime('manager', {
        state: 'error',
        startedAt: coworkStartedAt,
        progress: 100,
        etaMs: 0,
        activeTool: 'cowork',
        detail: msg,
        collaborators: [launchModule],
      })
      useAgentRuntimeStore.getState().setModuleRuntime(launchModule, {
        state: 'error',
        startedAt: coworkStartedAt,
        progress: 100,
        etaMs: 0,
        activeTool: 'cowork',
        detail: msg,
        collaborators: ['manager'],
      })
      setEvents((prev) => [...prev, errEv])
    } finally {
      // Finalize : extract the final reply from events and stamp the
      // Aurora turn (pending=false). Also keep the technical snapshot.
      const finalReply = extractAuroraReply(localEvents)
      const previousProjectThread = projectThreadRef.current
      const nextProjectThread = updateCoworkProjectThreadFromEvents(previousProjectThread, {
        userPrompt: finalPrompt,
        assistantReply: finalReply,
        events: localEvents,
        attachedImageDescriptions,
      })
      const newArtifacts = diffCoworkProjectArtifacts(previousProjectThread, nextProjectThread)
        .map(sanitizeChatArtifact)
      projectThreadRef.current = nextProjectThread
      setProjectThread(nextProjectThread)
      setMessages((prev) => prev.map((t) => t.id === auroraTurn.id
        ? {
            ...t,
            pending: false,
            content: finalReply,
            technical: [...localEvents],
            artifacts: newArtifacts.length > 0 ? newArtifacts : t.artifacts,
          }
        : t))
      if (localEvents[localEvents.length - 1]?.kind !== 'error') {
        useAgentRuntimeStore.getState().setAgentRuntime('manager', {
          state: 'done',
          startedAt: coworkStartedAt,
          progress: 100,
          etaMs: 0,
          activeTool: 'cowork',
          detail: 'Mission Cowork terminee.',
          collaborators: [launchModule],
        })
        useAgentRuntimeStore.getState().setModuleRuntime(launchModule, {
          state: 'done',
          startedAt: coworkStartedAt,
          progress: 100,
          etaMs: 0,
          activeTool: 'cowork',
          detail: 'Mission Cowork terminee.',
          collaborators: ['manager'],
        })
      }
      useAgentRuntimeStore.getState().setVoiceActive(false)
      setRunning(false)
      setAbortController(null)
      setAuditEntries(readAuditLog())
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      recStreamRef.current = stream
      recChunksRef.current = []
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mr.ondataavailable = (e) => { if (e.data.size > 0) recChunksRef.current.push(e.data) }
      mr.onstop = async () => {
        const blob = new Blob(recChunksRef.current, { type: 'audio/webm' })
        try {
          const transcribed = await transcribeAudio(blob)
          if (transcribed) {
            setPrompt(transcribed)
            await submit(transcribed)
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err)
          setEvents((prev) => [...prev, { kind: 'error', message: `Transcription: ${msg}`, at: Date.now() }])
        }
      }
      mr.start()
      recRef.current = mr
      setRecording(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setEvents((prev) => [...prev, { kind: 'error', message: `Micro indisponible: ${msg}`, at: Date.now() }])
    }
  }

  const stopRecording = () => {
    if (recRef.current && recRef.current.state !== 'inactive') {
      recRef.current.stop()
    }
    if (recStreamRef.current) {
      recStreamRef.current.getTracks().forEach((t) => t.stop())
      recStreamRef.current = null
    }
    recRef.current = null
    setRecording(false)
  }

  return (
    <>
      <AnimatePresence>
        {open && showRiskWarning && (
          <RiskWarningModal
            onAcceptAndUnlock={() => {
              const s = loadSettings()
              saveSettings({ ...s, fullyUnlocked: false, trustMode: false, dangerMode: true, safetyProfileVersion: 2 })
              setShowRiskWarning(false)
            }}
            onDismiss={() => setShowRiskWarning(false)}
          />
        )}
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-stretch justify-stretch"
            style={{ background: 'rgba(6,6,10,.92)', backdropFilter: 'blur(24px) saturate(160%)' }}
          >
            <div className="relative w-full h-full flex flex-col">
              <div className="pointer-events-none absolute inset-0 overflow-hidden">
                <div style={{ position: 'absolute', top: '-15%', left: '-10%', width: 540, height: 540, borderRadius: '50%', background: 'radial-gradient(circle,#7c3aed,transparent 65%)', filter: 'blur(160px)', opacity: .35 }} />
                <div style={{ position: 'absolute', bottom: '-15%', right: '-10%', width: 480, height: 480, borderRadius: '50%', background: 'radial-gradient(circle,#22d3ee,transparent 65%)', filter: 'blur(160px)', opacity: .28 }} />
              </div>

              {/* Header */}
              <div className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div style={{ width: 48, height: 60, flexShrink: 0 }}>
                    <LyraCharacter
                      phase={running ? 'thinking' : 'idle'}
                      emotion={running ? 'focus' : 'happy'}
                      accent="#7c3aed"
                      size={48}
                    />
                  </div>
                  <Sparkles size={18} className="text-violet-300" />
                  <div>
                    <h2 className="text-lg font-semibold text-white tracking-tight">Cowork — Aurora prend la main</h2>
                    <p className="text-[11px] text-white/50">{labelForRuntime(runtime)} · {capabilities.filter((c) => c.enabled).length}/{capabilities.length} capacites actives</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Session selector: pick or create a temp session for files/artifacts */}
                  <div className="flex items-center gap-2 mr-2">
                    <select
                      value={selectedSessionId ?? ''}
                      onChange={(e) => setSelectedSessionId(e.target.value || null)}
                      className="rounded-full bg-white/[0.04] py-1 px-3 text-sm text-white/80 border border-white/8"
                    >
                      <option value="">-- Session --</option>
                      {sessionsList.map((s) => (
                        <option key={s.id} value={s.id}>{s.title}</option>
                      ))}
                    </select>
                    <button
                      onClick={async () => {
                        const title = `Session ${sessionsList.length + 1}`
                        try {
                          const mod = await import('../services/coworkSessionStore')
                          const resp = await mod.remoteCreateSession(title)
                          if (resp?.ok && resp.session) {
                            setSessionsList((prev) => [...prev, { id: resp.session!.id, title: resp.session!.title }])
                            setSelectedSessionId(resp.session!.id)
                          }
                          if (resp?.warnings && resp.warnings.length > 0) {
                            setEvents((prev) => [...prev, ...resp.warnings.map((w: string) => ({ kind: 'warn' as const, message: w, at: Date.now() }))])
                            setShowAudit(true)
                          }
                        } catch (err) { setEvents((prev) => [...prev, { kind: 'error', message: String(err instanceof Error ? err.message : err), at: Date.now() }]) }
                      }}
                      className="px-3 py-1 rounded-full text-[11px] font-semibold bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08]"
                      title="Creer une session temporaire"
                    >
                      +
                    </button>
                    <button
                      onClick={async () => {
                        if (!selectedSessionId) return
                        const { requestConfirmation, clearConfirmation } = useCoworkStore.getState()
                        const idToRemove = selectedSessionId
                        requestConfirmation({
                          id: `confirm-remove-session-${Date.now()}`,
                          action: { kind: 'delete_file', path: `session:${idToRemove}` },
                          reason: 'Supprimer cette session et ses fichiers temporaires ?',
                          destructive: true,
                          approve: async () => {
                            try {
                              const mod = await import('../services/coworkSessionStore')
                              const resp = await mod.remoteRemoveSession(idToRemove)
                              if (resp?.ok) {
                                setSessionsList((prev) => prev.filter((s) => s.id !== idToRemove))
                                if (selectedSessionId === idToRemove) setSelectedSessionId(null)
                              }
                              if (resp?.warnings && resp.warnings.length > 0) {
                                setEvents((prev) => [...prev, ...resp.warnings.map((w: string) => ({ kind: 'warn' as const, message: w, at: Date.now() }))])
                                setShowAudit(true)
                              }
                            } catch (err) { setEvents((prev) => [...prev, { kind: 'error', message: String(err instanceof Error ? err.message : err), at: Date.now() }]) }
                            clearConfirmation()
                          },
                          skip: () => { clearConfirmation() },
                          abort: () => { clearConfirmation() },
                        })
                      }}
                      className="px-3 py-1 rounded-full text-[11px] font-semibold bg-white/[0.04] text-red-300 border border-white/10 hover:bg-white/[0.06]"
                      title="Supprimer la session selectionnee"
                    >
                      Suppr
                    </button>
                  </div>
                  {!permissionsGranted && runtime !== 'tauri-desktop' && (
                    <button
                      onClick={requestPermissions}
                      className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-amber-400/20 text-amber-200 border border-amber-400/30 hover:bg-amber-400/30 transition-colors"
                    >
                      Autoriser le micro
                    </button>
                  )}
                  {/* v115 — toggle Chat/Technique supprime : une seule vue
                      unifiee. Le bouton "Details" ci-dessous ouvre le drawer
                      console technique a la demande, sans forcer un changement
                      de paradigme UI. */}
                  <button
                    onClick={() => setShowConsole((v) => !v)}
                    className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-colors flex items-center gap-1.5 ${
                      showConsole
                        ? 'bg-violet-500/20 text-violet-200 border-violet-500/30'
                        : 'bg-white/[0.04] text-white/70 border-white/10 hover:bg-white/[0.08]'
                    }`}
                    title="Affiche les details techniques (events live, capacites detectees) dans un drawer a droite"
                  >
                    <Terminal size={11} />
                    {showConsole ? 'Masquer details' : 'Details techniques'}
                  </button>
                  {/* v28 — voice mode toggle : Aurora reads its replies aloud */}
                  <button
                    onClick={() => setVoiceMode((v) => !v)}
                    className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-colors flex items-center gap-1.5 ${
                      voiceMode
                        ? 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30'
                        : 'bg-white/[0.04] text-white/70 border-white/10 hover:bg-white/[0.08]'
                    }`}
                    title={voiceMode
                      ? 'Mode vocal ON — Aurora lit ses reponses a voix haute (TTS Kokoro)'
                      : 'Mode vocal OFF — clique pour activer la lecture vocale des reponses'}
                  >
                    {voiceMode ? <Volume2 size={11} /> : <VolumeX size={11} />}
                    {voiceMode ? 'Voix ON' : 'Voix'}
                  </button>
                  {/* v82l7 — direct extraction toggle. Bypass planner,
                      one-shot extract_structured against the active tab. */}
                  <button
                    onClick={() => {
                      setShowExtract((v) => !v)
                      // Hide audit if turning extract on (panel is exclusive)
                      if (!showExtract) setShowAudit(false)
                    }}
                    className={`px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-colors flex items-center gap-1.5 ${
                      showExtract
                        ? 'bg-violet-500/20 text-violet-200 border-violet-500/30'
                        : 'bg-white/[0.04] text-white/70 border-white/10 hover:bg-white/[0.08]'
                    }`}
                    title="Extraction directe (bypass planner) — decris ce que tu veux extraire de la page active"
                  >
                    <Brain size={11} />
                    {showExtract ? 'Masquer extraction' : 'Extraire'}
                  </button>
                  <button
                    onClick={() => {
                      setShowAudit((v) => !v)
                      if (!showAudit) setShowExtract(false)
                    }}
                    className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08] transition-colors flex items-center gap-1.5"
                    title="Audit log local — historique des actions"
                  >
                    <ClipboardList size={11} />
                    {showAudit ? 'Masquer l audit' : 'Audit log'}
                  </button>
                  <button
                    onClick={() => openSettings()}
                    className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08] transition-colors flex items-center gap-1.5"
                    title="Parametres Cowork (prompts + permissions + connecteurs)"
                  >
                    <SettingsIcon size={11} />
                    Parametres
                  </button>
                  {running && (
                    <button
                      onClick={() => abortRun()}
                      className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-red-500/15 text-red-200 border border-red-500/30 hover:bg-red-500/25 transition-colors flex items-center gap-1.5"
                    >
                      <Square size={11} />
                      Arreter
                    </button>
                  )}
                  <button
                    onClick={onClose}
                    className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/60 hover:bg-white/10 hover:text-white transition-colors"
                    title="Fermer (Esc)"
                    disabled={running}
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>

              {/* Body */}
              {chatMode ? (
                <div className="relative z-10 flex-1 grid grid-cols-1 gap-4 px-4 py-4 overflow-hidden min-h-0"
                     style={{ gridTemplateColumns: showConsole ? 'minmax(0,1fr) 380px' : 'minmax(0,1fr)' }}>
                  {/* CHAT THREAD */}
                  <div className="flex flex-col gap-3 min-h-0">
                    {showExtract ? (
                      <ExtractDrawer
                        intent={extractIntent}
                        onIntentChange={setExtractIntent}
                        onRun={() => void runExtract()}
                        onRunWithVision={() => void runExtract({ withVision: true })}
                        onReset={resetExtract}
                        onClose={() => setShowExtract(false)}
                        running={extractRunning}
                        result={extractResult}
                        error={extractError}
                        suggestVision={suggestVision && !visionSuggestionDismissed}
                        onDismissVisionSuggestion={() => setVisionSuggestionDismissed(true)}
                      />
                    ) : showAudit ? (
                      <div className="flex-1 overflow-y-auto min-h-0 space-y-3">
                        {/* v82m2 — extraction-quality tile lives at the top of
                            the audit drawer so the user sees both "what Aurora
                            did" (audit) and "how well extraction is going"
                            (yield/under-extraction) on the same panel. */}
                        <CoworkExtractionStatsTile />
                        <AuditDrawer
                          entries={auditEntries}
                          onClear={() => { clearAuditLog(); setAuditEntries([]) }}
                          onRefresh={() => setAuditEntries(readAuditLog())}
                        />
                      </div>
                    ) : (
                      <ConversationThread
                        messages={messages}
                        running={running}
                        onClear={() => {
                          setMessages([])
                          setProjectThread(clearCoworkProjectThread())
                        }}
                        onRegenerate={(prompt) => void submit(prompt)}
                        projectThread={projectThread}
                        module={launchModule}
                        onEditUserTurn={(userTurnId) => {
                          // v32 — find the user turn + its following aurora turn,
                          // pre-fill the composer with the user content, and drop
                          // the pair so when the user resubmits the new prompt it
                          // becomes the new latest exchange.
                          setMessages((prev) => {
                            const idx = prev.findIndex((t) => t.id === userTurnId)
                            if (idx === -1) return prev
                            const userTurn = prev[idx]
                            setPrompt(userTurn.content)
                            setTimeout(() => inputRef.current?.focus(), 50)
                            // Drop the user turn and its immediately-following aurora turn.
                            const next = [...prev]
                            const dropEnd = idx + 1 < next.length && next[idx + 1].role === 'aurora' ? idx + 2 : idx + 1
                            next.splice(idx, dropEnd - idx)
                            return next
                          })
                        }}
                        onQuickPrompt={(p) => {
                          // Chips ending with ': ' are pre-fill (user appends
                          // their target/topic), the others submit directly.
                          if (p.endsWith(': ')) {
                            setPrompt(p)
                            inputRef.current?.focus()
                          } else {
                            void submit(p)
                          }
                        }}
                      />
                    )}

                    {/* Composer (always visible at the bottom in chat mode)
                        v29 — drag-drop / paste support : drop zone overlay
                        on the composer container, paste handler on textarea,
                        thumbnail strip above textarea when images attached.
                        v115 — border violet + label "MISSION" pour rendre la
                        zone d action evidente des l ouverture. */}
                    <div
                      className="rounded-2xl border border-violet-500/30 bg-violet-500/[0.04] backdrop-blur-md p-3 flex-shrink-0 relative shadow-[0_0_24px_-12px_rgba(124,58,237,0.4)]"
                      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }}
                      onDrop={(e) => {
                        e.preventDefault()
                        if (e.dataTransfer.files.length > 0) handleAttachFiles(e.dataTransfer.files)
                      }}
                    >
                      {/* v115 — petit label "MISSION" pour clarifier que c est
                          la zone d action principale (pas un simple chat). */}
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[9px] uppercase tracking-[0.22em] font-semibold text-violet-300/80">Mission</span>
                        <div className="h-px flex-1 bg-violet-400/15" />
                        <span className="text-[9px] text-white/35">⌘+Enter pour lancer</span>
                      </div>
                      {/* Hidden file input for the "Joindre" button —
                          accepts both images (image/*) and text/code files
                          (text/*, .json, .md, .py, .ts, .js, .yaml, ...). */}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*,text/*,application/json,application/xml,.md,.json,.jsonc,.yaml,.yml,.toml,.ini,.cfg,.conf,.env,.sh,.bash,.zsh,.fish,.ps1,.bat,.py,.pyi,.ts,.tsx,.js,.jsx,.mjs,.cjs,.java,.kt,.swift,.c,.h,.cpp,.cc,.hpp,.rs,.go,.rb,.php,.lua,.pl,.sql,.html,.css,.scss,.less,.xml,.svg,.csv,.log,.gitignore,.dockerfile,.makefile,.cmake"
                        multiple
                        className="hidden"
                        onChange={(e) => { handleAttachFiles(e.target.files); if (fileInputRef.current) fileInputRef.current.value = '' }}
                      />
                      {/* Thumbnail strip (only when images attached) */}
                      {attachedImages.length > 0 && (
                        <div className="flex gap-2 mb-2 flex-wrap">
                          {attachedImages.map((img) => (
                            <div key={img.id} className="relative group">
                              <img src={img.dataUrl} alt="attached" className="h-16 w-16 rounded-lg object-cover border border-white/10" />
                              <button
                                type="button"
                                onClick={() => setAttachedImages((prev) => prev.filter((p) => p.id !== img.id))}
                                className="absolute -top-1.5 -right-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500/90 text-white text-[10px] hover:bg-red-500 transition-colors"
                                title="Retirer cette image"
                              >
                                <X size={10} />
                              </button>
                            </div>
                          ))}
                          {attachedImages.length < 3 && (
                            <button
                              type="button"
                              onClick={() => fileInputRef.current?.click()}
                              className="h-16 w-16 rounded-lg border border-dashed border-white/15 bg-white/[0.02] text-white/40 hover:bg-white/[0.05] hover:border-white/30 transition-colors flex items-center justify-center"
                              title="Ajouter une image"
                            >
                              <ImageIcon size={18} />
                            </button>
                          )}
                        </div>
                      )}
                      {/* v33 — Text/code file chips */}
                      {attachedTextFiles.length > 0 && (
                        <div className="flex gap-1.5 mb-2 flex-wrap">
                          {attachedTextFiles.map((f) => (
                            <div key={f.id} className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-white/10 bg-white/[0.03] text-[11px] text-white/75">
                              <FileText size={12} className="text-violet-300/80" />
                              <span className="font-mono">{f.name}</span>
                              <span className="text-white/40">{(f.size / 1024).toFixed(1)} KB</span>
                              <button
                                type="button"
                                onClick={() => setAttachedTextFiles((prev) => prev.filter((p) => p.id !== f.id))}
                                className="ml-1 text-white/40 hover:text-red-300 transition-colors"
                                title="Retirer ce fichier"
                              >
                                <X size={11} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                      <textarea
                        ref={inputRef}
                        rows={2}
                        placeholder={runtime === 'web-mobile'
                          ? 'Decris la mission a executer — Aurora planifie + execute (dictee dispo).'
                          : 'Decris la mission a executer — Aurora planifie + execute en autonomie.  (⌘+Enter lancer · ↑↓ historique · /help · drop image/fichier OK)'}
                        value={prompt}
                        onPaste={(e) => {
                          // v29 — paste image directly into composer
                          const items = e.clipboardData?.items
                          if (!items) return
                          for (const item of Array.from(items)) {
                            if (item.kind === 'file' && item.type.startsWith('image/')) {
                              const file = item.getAsFile()
                              if (file) {
                                e.preventDefault()
                                const dt = new DataTransfer()
                                dt.items.add(file)
                                handleAttachFiles(dt.files)
                                return
                              }
                            }
                          }
                        }}
                        onChange={(e) => { setPrompt(e.target.value); setHistoryIndex(-1) }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                            e.preventDefault(); void submit(prompt)
                            return
                          }
                          if (e.key === 'ArrowUp' && promptHistory.length > 0) {
                            // Only intercept if cursor is at start (line 1) — let
                            // arrow up navigate inside multi-line text otherwise.
                            const ta = e.currentTarget
                            const onFirstLine = ta.value.slice(0, ta.selectionStart).indexOf('\n') === -1
                            if (!onFirstLine) return
                            e.preventDefault()
                            if (historyIndex === -1) draftBeforeHistoryRef.current = prompt
                            const nextIdx = historyIndex === -1
                              ? promptHistory.length - 1
                              : Math.max(0, historyIndex - 1)
                            setHistoryIndex(nextIdx)
                            setPrompt(promptHistory[nextIdx] ?? '')
                            return
                          }
                          if (e.key === 'ArrowDown' && historyIndex !== -1) {
                            const ta = e.currentTarget
                            const onLastLine = ta.value.slice(ta.selectionStart).indexOf('\n') === -1
                            if (!onLastLine) return
                            e.preventDefault()
                            if (historyIndex >= promptHistory.length - 1) {
                              setHistoryIndex(-1)
                              setPrompt(draftBeforeHistoryRef.current)
                            } else {
                              const nextIdx = historyIndex + 1
                              setHistoryIndex(nextIdx)
                              setPrompt(promptHistory[nextIdx] ?? '')
                            }
                            return
                          }
                        }}
                        disabled={running}
                        className="w-full resize-none bg-transparent text-white text-sm outline-none placeholder:text-white/35"
                      />
                      <div className="flex items-center gap-2 mt-1">
                        <button
                          onClick={() => recording ? stopRecording() : void startRecording()}
                          disabled={running}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-colors ${
                            recording
                              ? 'border-red-500/40 bg-red-500/15 text-red-200'
                              : 'border-white/10 bg-white/[0.04] text-white/70 hover:bg-white/[0.08]'
                          }`}
                        >
                          {recording ? <MicOff size={12} /> : <Mic size={12} />}
                          {recording ? 'Arreter dictee' : 'Dicter'}
                        </button>
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          disabled={running || (attachedImages.length >= 3 && attachedTextFiles.length >= 3)}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold border border-white/10 bg-white/[0.04] text-white/70 hover:bg-white/[0.08] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                          title="Joindre image OU fichier code/texte (drag-drop / paste / picker). Max 3 images + 3 fichiers."
                        >
                          <Paperclip size={12} />
                          Joindre{(attachedImages.length + attachedTextFiles.length) > 0 ? ` (${attachedImages.length + attachedTextFiles.length})` : ''}
                        </button>
                        <div className="flex-1" />
                        {/* v114 — bouton toujours cliquable : focus le textarea si vide,
                            sinon lance la mission. Permet de comprendre pourquoi rien
                            ne part sans avoir à deviner que le bouton est gris.
                            v115 — bouton agrandi (text-[13px], px-5, py-2) + glow
                            violet pour être le call-to-action evident. */}
                        <button
                          onClick={() => {
                            if (running) return
                            if (!prompt.trim()) { inputRef.current?.focus(); return }
                            void submit(prompt)
                          }}
                          disabled={running}
                          className="flex items-center gap-2 px-5 py-2 rounded-full text-[13px] font-semibold bg-violet-500 text-white hover:bg-violet-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-[0_0_20px_-6px_rgba(124,58,237,0.7)]"
                          title={running ? 'Mission en cours…' : (!prompt.trim() ? 'Saisis une mission puis clique pour lancer' : 'Lancer la mission (⌘+Enter)')}
                        >
                          <Send size={13} />
                          {running ? 'En cours…' : 'Lancer la mission'}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Console drawer (collapsible) */}
                  {showConsole && (
                    <aside className="flex flex-col min-h-0">
                      <ConsoleDrawer events={events} running={running}
                        onClose={() => setShowConsole(false)} />
                    </aside>
                  )}
                </div>
              ) : (
                <div className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-6 px-6 py-6 overflow-hidden min-h-0">
                  {/* CAPABILITIES (technical mode only) */}
                  <aside className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 overflow-y-auto">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-3">Capacites detectees</p>
                    <ul className="space-y-2">
                      {capabilities.map((cap) => {
                        const Icon = capabilityIcon(cap.id)
                        return (
                          <li
                            key={cap.id}
                            className={`flex items-start gap-3 px-3 py-2.5 rounded-xl border ${
                              cap.enabled
                                ? 'border-emerald-500/25 bg-emerald-500/8'
                                : 'border-white/5 bg-white/[0.02] opacity-60'
                            }`}
                          >
                            <Icon size={14} className={cap.enabled ? 'text-emerald-300 mt-0.5' : 'text-white/40 mt-0.5'} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-[12px] font-medium text-white">{cap.label}</span>
                                {cap.destructive && cap.enabled && <ShieldAlert size={11} className="text-amber-400" />}
                                {cap.destructive && !cap.enabled && <ShieldCheck size={11} className="text-emerald-400" />}
                              </div>
                              <p className="text-[10px] text-white/50 mt-0.5 leading-snug">{cap.description}</p>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                    <div className="mt-5 pt-4 border-t border-white/5">
                      <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">Runtime</p>
                      <p className="text-[11px] text-white/65 leading-relaxed">{describeRuntime(runtime)}</p>
                    </div>
                  </aside>

                  {/* PROMPT + EVENTS / AUDIT (technical mode) */}
                  <div className="flex flex-col gap-4 min-h-0">
                    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 flex-shrink-0">
                      <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-2">Demande a Aurora</p>
                      <textarea
                        ref={inputRef}
                        rows={3}
                        placeholder={runtime === 'web-mobile'
                          ? 'Mode mobile : dictee + lecture autorisees, modifications systeme bloquees.'
                          : runtime === 'tauri-desktop'
                            ? 'Ex : ouvre application/src/services/codeOrchestrator.ts et resume-moi le pipeline'
                            : 'Ex : recupere le contenu de la page et fais-moi un resume'}
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void submit(prompt) }
                        }}
                        disabled={running}
                        className="w-full resize-none bg-transparent text-white text-sm outline-none placeholder:text-white/35"
                      />
                      <div className="flex items-center gap-2 mt-2">
                        <button
                          onClick={() => recording ? stopRecording() : void startRecording()}
                          disabled={running}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold border transition-colors ${
                            recording
                              ? 'border-red-500/40 bg-red-500/15 text-red-200'
                              : 'border-white/10 bg-white/[0.04] text-white/70 hover:bg-white/[0.08]'
                          }`}
                        >
                          {recording ? <MicOff size={12} /> : <Mic size={12} />}
                          {recording ? 'Arreter' : 'Dicter'}
                        </button>
                        <div className="flex-1" />
                        <span className="text-[10px] text-white/40">⌘+Enter pour envoyer</span>
                        <button
                          onClick={() => {
                            if (running) return
                            if (!prompt.trim()) { inputRef.current?.focus(); return }
                            void submit(prompt)
                          }}
                          disabled={running}
                          className="flex items-center gap-2 px-4 py-1.5 rounded-full text-[11px] font-semibold bg-violet-500 text-white hover:bg-violet-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                          title={running ? 'Mission en cours…' : (!prompt.trim() ? 'Saisis une mission puis clique pour lancer' : 'Lancer la mission (⌘+Enter)')}
                        >
                          <Send size={12} />
                          {running ? 'En cours…' : 'Lancer'}
                        </button>
                      </div>
                    </div>

                    {showAudit ? (
                      <div className="flex-1 overflow-y-auto min-h-0 space-y-3">
                        {/* v82m2 — extraction-quality tile pairs with the
                            audit drawer in the non-chat mount too, so the
                            classic Cowork view also shows under-extraction
                            + yield trends without an extra toggle. */}
                        <CoworkExtractionStatsTile />
                        <AuditDrawer
                          entries={auditEntries}
                          onClear={() => { clearAuditLog(); setAuditEntries([]) }}
                          onRefresh={() => setAuditEntries(readAuditLog())}
                        />
                      </div>
                    ) : (
                      <EventsLog events={events} running={running} />
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirmation dialog is rendered outside AnimatePresence so it can
          appear over the overlay regardless of whether the overlay is open. */}
      <CoworkConfirmDialog />
      <CoworkSettingsDialog />
    </>
  )
}

// ---------------------------------------------------------------------------
// Risk Warning Modal — shown at startup if fullyUnlocked = false
// ---------------------------------------------------------------------------

function RiskWarningModal({ onAcceptAndUnlock, onDismiss }: { onAcceptAndUnlock: () => void; onDismiss: () => void }) {
  const [riskAccepted, setRiskAccepted] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[250] flex items-center justify-center bg-black/80 backdrop-blur-md"
    >
      <motion.div
        initial={{ scale: 0.9, y: 20, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.9, y: 20, opacity: 0 }}
        className="w-full max-w-2xl max-h-[80vh] rounded-3xl border border-red-500/30 bg-[#0b111b] text-white shadow-[0_30px_90px_rgba(220,38,38,0.3)] flex flex-col overflow-hidden"
      >
        <div className="px-6 py-4 border-b border-red-500/20 flex items-center gap-3">
          <ShieldAlert size={20} className="text-red-400" />
          <h2 className="text-xl font-semibold">Attention — Risques majeurs</h2>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          <p className="text-[13px] text-white/90 leading-relaxed">
            <strong>Aurora peut agir sur ta machine.</strong> En mode preventif, elle travaille librement dans le workspace mais demande confirmation avant les actions hors perimetre, sensibles ou destructrices.
          </p>

          <ul className="space-y-2.5 text-[12px] text-white/80 leading-relaxed list-disc list-inside">
            <li><strong>Commandes système destructives :</strong> sudo, format, dd, mkfs, rm -rf, shutdown</li>
            <li><strong>Lectures indiscrètes :</strong> fichiers confidentiels, emails, mots de passe, clés SSH/API</li>
            <li><strong>Infections persistantes :</strong> malware, backdoors, cron jobs malveillants, comptes cachés</li>
            <li><strong>Modifications en chaîne :</strong> code source, configurations, bases de données</li>
            <li><strong>Attaques externes :</strong> depuis ta machine vers tes serveurs, clients, ou le réseau interne</li>
            <li><strong>Exfiltration de données :</strong> copie/compression/envoi vers des serveurs distants</li>
            <li><strong>Escalade de privilèges :</strong> kernel exploits, permission elevation vers root/admin</li>
          </ul>

          <p className="text-[12px] text-amber-200 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 leading-relaxed">
            <strong>Scénario prevenu :</strong> tu demandes « analyse mon bureau », l'IA propose une commande risquee au lieu de lister. Aurora te montre l'action et attend ton accord avant execution.
          </p>

          <p className="text-[13px] text-white/90 leading-relaxed">
            <strong>Pourquoi ce mode preventif?</strong> Aurora doit pouvoir faire le travail sans s'arreter sur une tache banale, tout en te montrant les actions qui peuvent avoir un impact reel.
          </p>

          <ul className="space-y-2 text-[12px] text-white/80 leading-relaxed list-disc list-inside">
            <li><strong>Relisant les plans</strong> que Cowork affiche avant d'exécuter (voir chaque action proposée)</li>
            <li><strong>Utilisant des comptes utilisateur non-root</strong> (mitigation forte : tu ne peux pas formater un disque en tant qu'utilisateur normal)</li>
            <li><strong>Maintenant tes backups à jour</strong> (résilience : tu peux restaurer en cas de désastre)</li>
            <li><strong>Comprenant les risques</strong> (toi qui lis ceci = tu en es responsable)</li>
          </ul>

          <p className="text-[11px] text-white/60 italic leading-relaxed">
            Ce message n'est pas fait pour bloquer Cowork : il fixe le contrat. Aurora agit, mais les gestes a impact reel passent par une validation explicite.
          </p>
        </div>

        <div className="px-6 py-4 border-t border-red-500/20 flex items-center gap-3 bg-red-500/5">
          <input
            type="checkbox"
            id="accept-risks"
            className="w-4 h-4 rounded border-red-500/40"
            checked={riskAccepted}
            onChange={(e) => setRiskAccepted(e.target.checked)}
          />
          <label htmlFor="accept-risks" className="text-[12px] text-white/80 flex-1">
            J'ai lu et je comprends les risques. Je suis responsable des données que j'ai sur cette machine.
          </label>
          <button
            onClick={onAcceptAndUnlock}
            disabled={!riskAccepted}
            className="px-4 py-1.5 rounded-lg text-[12px] font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Continuer en mode preventif
          </button>
          <button
            onClick={onDismiss}
            className="px-4 py-1.5 rounded-lg text-[12px] font-semibold bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08] transition-colors"
          >
            Fermer
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Conversation thread (chat mode) — pairs of user / Aurora bubbles, auto-
// scrolling, with each Aurora bubble offering an inline "voir les coulisses"
// expansion that surfaces that turn's technical events.
// ---------------------------------------------------------------------------
// v22 — quick-action chips for the chat empty state. One-click starters
// for the most common Cowork prompts so the user doesn't have to think
// about what to type the first time.
//
// v25 — chips are now contextual : different starter prompts per
// launchModule. The cyber chips materialise the "real-pro mode" enabled
// by the v23 system prompt enrichment ; the code chips target dev
// workflows ; the conversation chips remain the general-purpose set.
type QuickPrompt = { label: string; prompt: string; emoji: string }
type QuickPromptModule = ModuleId

const QUICK_PROMPTS_DEFAULT: QuickPrompt[] = [
  { emoji: '🔍', label: 'Analyse cette page',  prompt: 'analyse la page web actuellement ouverte et fais un rapport structure (titre, sections, points cles).' },
  { emoji: '🧠', label: 'Resume mon code',     prompt: 'lis le fichier ouvert dans l editeur et fais-moi un resume structure de ce qu il fait, les dependances et les points de risque.' },
  { emoji: '📅', label: 'Planning de la semaine', prompt: 'fais-moi un recap de ce qui est sur mon planning cette semaine (Linear / Trello / Jira / GCal selon les connecteurs actifs).' },
  { emoji: '📊', label: 'Recap fitness',       prompt: 'recap mes activites Strava de la semaine et propose un objectif pour la semaine prochaine.' },
  { emoji: '⚡', label: 'Etat infra',          prompt: 'verifie l etat de mes services (CI runs, deploys recents, alerts Grafana en cours, sites principaux up/down).' },
  { emoji: '💡', label: 'Brainstorming',       prompt: 'reflechis a fond sur le sujet suivant et propose 3 options avec pros/cons : ' },
]

const QUICK_PROMPTS_CYBER: QuickPrompt[] = [
  { emoji: '🛡️', label: 'Confess scope',        prompt: 'remember_fact : je confirme etre proprietaire de la cible suivante et autorise pen-test actif full : ' },
  { emoji: '🔍', label: 'Recon mon Pi',         prompt: 'recon active sur mon Raspberry Pi (192.168.X.X — adapte selon le scope confirme) : nmap -sV -sC --script=vuln, fingerprint OS, services exposes, default creds connus, kernel level vs CVE recents. Format pen-test PRO.' },
  { emoji: '🌐', label: 'OSINT target',         prompt: 'OSINT passif sur la cible suivante (recon non-intrusif via theharvester, sherlock, crt.sh, GitHub dorks, brave_search, perplexity) : ' },
  { emoji: '⬆️', label: 'Privesc local',        prompt: 'check privesc complet sur cette machine : sudo -l, suid binaries (find / -perm -4000), capabilities (getcap -r /), cron, env passwords, NFS, Docker socket, GTFOBins lookup. Linpeas-equivalent.' },
  { emoji: '🛜', label: 'Network sweep',        prompt: 'sweep complet du subnet local (avec scope confirme) : arp-scan -l + nmap -sn 192.168.0.0/16, identification IoT (Tuya/Wyze/Bambu/Pi sur ports MQTT/UPnP/telnet/HTTP), services exposes par device. Tableau resultat.' },
  { emoji: '🔓', label: 'Audit web app',        prompt: 'audit web app pen-test (URL = scope confirme) : nikto + wpscan + ffuf wordlists + sqlmap si formulaire login + headers security. Rapport CVE/CWE/CVSS.' },
  { emoji: '🔐', label: 'Audit defensif',       prompt: 'mode blue team : audit defensif de cette machine. Verifie fail2ban, ufw/iptables, selinux/apparmor, sysctl hardening, ssh config, dependances vulnerables (npm audit/pip-audit/trivy), CIS benchmark coverage. Genere les fixes Ansible-ready.' },
  { emoji: '🔥', label: 'Check breaches',       prompt: 'verifie via HIBP si mes emails sont dans des breaches connues, et croise avec abuseipdb pour les IPs suspectes recentes. Liste-moi les actions a prendre.' },
]

const QUICK_PROMPTS_CODE: QuickPrompt[] = [
  { emoji: '🧠', label: 'Resume ce fichier',    prompt: 'lis le fichier actuellement ouvert dans l editeur et fais-moi un resume structure : ce qu il fait, dependances importees, fonctions exposees, points de risque, pattern arch utilise.' },
  { emoji: '🐛', label: 'Cherche les bugs',     prompt: 'lis le fichier actuel et identifie les bugs potentiels, race conditions, edge cases non gerees, leaks de ressources, validation manquante. Cite les lignes precises.' },
  { emoji: '✨', label: 'Refactor suggestions', prompt: 'lis le fichier actuel et propose un refactor concret : duplications a extraire, fonctions trop longues a decouper, types a renforcer, imports a nettoyer. Avec diff propose.' },
  { emoji: '🧪', label: 'Tests manquants',     prompt: 'lis le fichier actuel et identifie les tests manquants. Genere les cas tests prioritaires (happy path + edge cases + erreurs). Format Jest/Vitest/node:test selon le projet.' },
  { emoji: '📦', label: 'Audit deps',          prompt: 'audit des dependances : versions a jour ? CVE ouverts ? Packages inutilises ? Bundle size ? Lance npm audit / pip-audit / trivy selon le stack et synthetise.' },
  { emoji: '⚡', label: 'Optimisation perf',   prompt: 'analyse le fichier actuel pour identifier les goulots de perf : O(n^2) cachees, calls reseau redondants, re-renders React inutiles, queries DB N+1. Avec benchmarks proposes.' },
]

function getQuickPrompts(module: QuickPromptModule): QuickPrompt[] {
  switch (module) {
    case 'cyber': return QUICK_PROMPTS_CYBER
    case 'code':  return QUICK_PROMPTS_CODE
    default:      return QUICK_PROMPTS_DEFAULT
  }
}

function ConversationThread({
  messages, running, onClear, onRegenerate, onQuickPrompt, onEditUserTurn, module, projectThread,
}: {
  messages: ChatTurn[]
  running: boolean
  onClear: () => void
  onRegenerate: (userPrompt: string) => void
  onQuickPrompt: (prompt: string) => void
  onEditUserTurn: (userTurnId: string) => void
  module: QuickPromptModule
  projectThread: CoworkProjectThread
}) {
  const QUICK_PROMPTS = getQuickPrompts(module)
  const containerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, running])

  return (
    <div ref={containerRef} className="rounded-2xl border border-white/8 bg-white/[0.02] flex-1 overflow-y-auto min-h-0">
      <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-2 border-b border-white/5 bg-[#0b111b]/80 backdrop-blur-md">
        <p className="text-[10px] uppercase tracking-[0.18em] text-white/40">
          Mission Aurora · {messages.length} message{messages.length > 1 ? 's' : ''}
        </p>
        {messages.length > 0 && (
          <button
            onClick={onClear}
            className="px-2 py-0.5 rounded-full text-[10px] bg-white/[0.04] text-white/60 border border-white/10 hover:bg-red-500/15 hover:text-red-200 hover:border-red-500/30 transition-colors"
            title="Effacer l historique de chat (gardes les memoires Aurora)"
          >
            Effacer
          </button>
        )}
      </div>
      {messages.length === 0 && !running && (
        <div className="flex flex-col items-center justify-center py-12 text-center px-8">
          <Sparkles size={32} className="text-violet-300/40 mb-4" />
          <p className="text-[14px] font-semibold text-white max-w-md mb-2">
            Decris la mission, Aurora la planifie et l execute.
          </p>
          <p className="text-[11px] text-white/45 max-w-md mb-6 leading-relaxed">
            Tape ta mission dans la zone en bas puis clique <span className="font-mono px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-200">Lancer</span> (ou Ctrl+Enter). Pour voir les events techniques live, ouvre <span className="font-mono px-1.5 py-0.5 rounded bg-white/10">Details techniques</span> en haut. Aurora agit avec des garde-fous preventifs : elle avance en autonomie, mais demande confirmation pour les secrets, les actions destructrices ou les operations externes sensibles.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-xl w-full">
            {QUICK_PROMPTS.map((q) => (
              <button
                key={q.label}
                onClick={() => onQuickPrompt(q.prompt)}
                className="group flex items-center gap-2 px-3 py-2 rounded-xl border border-white/8 bg-white/[0.03] hover:bg-violet-500/15 hover:border-violet-500/30 transition-colors text-left"
                title={q.prompt}
              >
                <span className="text-[16px]">{q.emoji}</span>
                <span className="text-[11px] font-medium text-white/75 group-hover:text-white truncate">{q.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="px-4 py-3 space-y-3">
        <CoworkProjectMemoryPanel thread={projectThread} />
        {messages.map((m, i) => {
          // For Aurora bubbles, find the immediately preceding user prompt
          // so the "Refaire" button can re-submit the same query.
          const prevUser = m.role === 'aurora'
            ? [...messages.slice(0, i)].reverse().find((t) => t.role === 'user')?.content
            : undefined
          return <ChatBubble
            key={m.id}
            turn={m}
            onRegenerate={prevUser ? () => onRegenerate(prevUser) : undefined}
            onQuickPrompt={onQuickPrompt}
            onEdit={m.role === 'user' ? () => onEditUserTurn(m.id) : undefined}
          />
        })}
        {running && messages[messages.length - 1]?.pending && (
          <CoworkLiveActivity events={messages[messages.length - 1]?.technical ?? []} compact />
        )}
      </div>
    </div>
  )
}

function CoworkProjectMemoryPanel({ thread }: { thread: CoworkProjectThread }) {
  const artifacts = thread.artifacts.filter((artifact) => artifact.status === 'ready')
  if (artifacts.length === 0) return null
  const active = thread.activeArtifactId
    ? artifacts.find((artifact) => artifact.id === thread.activeArtifactId)
    : artifacts[artifacts.length - 1]
  const recent = artifacts.slice(-5).reverse()

  return (
    <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.05] px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[9px] uppercase tracking-[0.18em] text-violet-200/70">Projet actif</div>
          <div className="mt-0.5 truncate text-[12px] text-white/78">
            {active ? `${artifactLabel(active.kind)} v${active.version} - ${active.label.replace(/^.*? - /, '')}` : thread.brief || 'Aucun artefact actif'}
          </div>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto max-w-[58%]">
          {recent.map((artifact) => (
            <CoworkArtifactMini key={artifact.id} artifact={artifact} active={artifact.id === active?.id} />
          ))}
        </div>
      </div>
    </div>
  )
}

function CoworkArtifactMini({ artifact, active }: { artifact: CoworkProjectArtifact; active?: boolean }) {
  const src = artifact.kind === 'image' ? previewUrlForCoworkArtifact(artifact) : ''
  return (
    <div
      className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[10px] whitespace-nowrap ${
        active
          ? 'border-violet-400/45 bg-violet-500/18 text-violet-100'
          : 'border-white/10 bg-white/[0.04] text-white/58'
      }`}
      title={[artifact.label, artifact.path || artifact.url || ''].filter(Boolean).join('\n')}
    >
      {src ? (
        <img
          src={src}
          alt=""
          className="h-7 w-7 rounded-md object-cover border border-white/10"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
      ) : (
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.06]">
          {artifact.kind === 'model3d' ? '3D' : artifact.kind === 'game' ? 'JS' : artifact.kind === 'video' ? 'MP4' : 'F'}
        </span>
      )}
      <span>{artifactLabel(artifact.kind)} v{artifact.version}</span>
    </div>
  )
}

type CoworkActivitySummary = {
  label: string
  detail: string
  scope: string
  state: 'running' | 'ok' | 'warn' | 'error'
  icon: 'brain' | 'terminal' | 'globe' | 'file' | 'pencil' | 'eye' | 'remote' | 'shield'
}

function CoworkLiveActivity({ events, compact = false }: { events: CoworkActionEvent[]; compact?: boolean }) {
  const activities = buildCoworkLiveActivities(events)
  const latest = pickLatestCoworkActivity(activities, compact)
  const shown = activities.slice(-4)

  if (!latest) {
    return (
      <div className="flex items-center gap-2 px-3 text-[12px] text-violet-300">
        <span className="inline-block h-2 w-2 rounded-full bg-violet-400 animate-pulse" />
        <span>Planifie la mission</span>
        <span className="text-white/35">(Cowork local)</span>
      </div>
    )
  }

  return (
    <div className={`${compact ? 'px-3' : ''} space-y-1.5`}>
      <div className="flex items-center gap-2 text-[12px] text-violet-200">
        <ActivityIcon id={latest.icon} className="h-3.5 w-3.5 text-violet-300" />
        <span className="inline-block h-2 w-2 rounded-full bg-violet-400 animate-pulse" />
        <span className="font-medium">{latest.label}</span>
        <span className="text-white/40">({latest.scope})</span>
      </div>
      {shouldShowActivityDetail(latest, compact) ? (
        <div className="truncate pl-7 text-[11px] text-white/45">{latest.detail}</div>
      ) : null}
      {isCreativeRunningActivity(latest) && (
        <CoworkCreationPulse activity={latest} compact={compact} />
      )}
      {!compact && (
        <div className="space-y-1">
          {shown.map((activity, index) => (
            <div key={`${activity.label}-${activity.detail}-${index}`} className="flex items-start gap-2 text-[11px] text-white/55">
              <ActivityStateDot state={activity.state} />
              <span className="min-w-0">
                <span className="text-white/70">{activity.label}</span>
                <span className="text-white/35"> ({activity.scope})</span>
                {activity.detail ? <span className="text-white/45"> - {activity.detail}</span> : null}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CoworkCreationPulse({ activity, compact }: { activity: CoworkActivitySummary; compact: boolean }) {
  const rails = compact ? 4 : 6
  return (
    <div className={`${compact ? 'ml-7' : 'ml-6'} overflow-hidden rounded-xl border border-violet-400/15 bg-black/20 px-3 py-2`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.18em] text-violet-200/60">atelier actif</div>
          <div className="mt-0.5 truncate text-[11px] text-white/68">{activity.label} - {activity.scope}</div>
        </div>
        <div className="flex shrink-0 items-end gap-1">
          {Array.from({ length: rails }).map((_, index) => (
            <motion.span
              key={index}
              className="block w-1.5 rounded-full bg-violet-300/70"
              initial={{ height: 8, opacity: 0.35 }}
              animate={{ height: [8, 18, 10], opacity: [0.35, 0.95, 0.45] }}
              transition={{ duration: 1.1, repeat: Infinity, delay: index * 0.11, ease: 'easeInOut' }}
            />
          ))}
        </div>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="h-full w-1/3 rounded-full bg-gradient-to-r from-violet-400 via-sky-300 to-emerald-300"
          animate={{ x: ['-120%', '320%'] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>
    </div>
  )
}

function isCreativeRunningActivity(activity: CoworkActivitySummary): boolean {
  return activity.state === 'running' && [
    'Genere une image',
    'Modifie une image',
    'Prepare le modele 3D',
    'Construit le jeu',
    'Genere du code',
    'Compose une video',
  ].includes(activity.label)
}

function pickLatestCoworkActivity(activities: CoworkActivitySummary[], compact: boolean): CoworkActivitySummary | undefined {
  if (!compact) return activities[activities.length - 1]
  const reversed = activities.slice().reverse()
  return reversed.find((activity) => activity.state === 'running' && activity.label !== 'Corrige la strategie')
    ?? reversed.find((activity) => activity.state !== 'warn' && activity.label !== 'Corrige la strategie')
    ?? activities[activities.length - 1]
}

function shouldShowActivityDetail(activity: CoworkActivitySummary, compact: boolean): boolean {
  if (!compact || !activity.detail || activity.state !== 'running') return false
  return [
    'Recherche web',
    'Lit une ressource web',
    'Utilise commande shell',
    'Lit un fichier',
    'Scanne un dossier',
    'Cree un fichier',
    'Code et modifie',
    'Controle le navigateur',
    'Utilise un connecteur',
    'Verifie visuellement',
    'Genere une image',
    'Modifie une image',
    'Prepare le modele 3D',
    'Construit le jeu',
    'Genere du code',
    'Compose une video',
  ].includes(activity.label)
}

function ActivityStateDot({ state }: { state: CoworkActivitySummary['state'] }) {
  const tone =
    state === 'error' ? 'bg-red-400'
    : state === 'warn' ? 'bg-amber-300'
    : state === 'ok' ? 'bg-emerald-300'
    : 'bg-violet-400 animate-pulse'
  return <span className={`mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full ${tone}`} />
}

function ActivityIcon({ id, className }: { id: CoworkActivitySummary['icon']; className?: string }) {
  const sizeClass = className ?? 'h-3.5 w-3.5'
  switch (id) {
    case 'terminal': return <Terminal className={sizeClass} />
    case 'globe': return <Globe className={sizeClass} />
    case 'file': return <FileText className={sizeClass} />
    case 'pencil': return <Pencil className={sizeClass} />
    case 'eye': return <Eye className={sizeClass} />
    case 'remote': return <Wifi className={sizeClass} />
    case 'shield': return <ShieldCheck className={sizeClass} />
    case 'brain':
    default: return <Brain className={sizeClass} />
  }
}

function buildCoworkLiveActivities(events: CoworkActionEvent[]): CoworkActivitySummary[] {
  const summaries: CoworkActivitySummary[] = []
  for (const ev of events) {
    const summary = summarizeCoworkActivityEvent(ev)
    if (!summary) continue
    const previous = summaries[summaries.length - 1]
    if (
      previous
      && previous.label === summary.label
      && previous.detail === summary.detail
      && previous.scope === summary.scope
    ) {
      summaries[summaries.length - 1] = {
        ...previous,
        state: mergeActivityState(previous.state, summary.state),
      }
      continue
    }
    summaries.push(summary)
  }
  return summaries
}

function mergeActivityState(
  previous: CoworkActivitySummary['state'],
  next: CoworkActivitySummary['state'],
): CoworkActivitySummary['state'] {
  if (next === 'error' || previous === 'error') return 'error'
  if (next === 'warn' || previous === 'warn') return 'warn'
  if (next === 'ok') return 'ok'
  return previous
}

function summarizeCoworkActivityEvent(ev: CoworkActionEvent): CoworkActivitySummary | null {
  const state: CoworkActivitySummary['state'] =
    ev.kind === 'error' ? 'error'
    : ev.kind === 'warn' ? 'warn'
    : ev.kind === 'success' ? 'ok'
    : 'running'

  const action = parseEventAction(ev.detail)
  if (action) return summarizeActionActivity(action, state, ev)

  if (/^Plan #/i.test(ev.message) || /^Estimation/i.test(ev.message)) {
    return {
      label: 'Reflechit et planifie',
      detail: ev.message.replace(/\s+/g, ' ').slice(0, 120),
      scope: 'LLM Cowork local',
      state,
      icon: 'brain',
    }
  }
  if (/replannifie|strategie|alternative|anti-boucle|echec detecte/i.test(ev.message)) {
    return {
      label: 'Corrige la strategie',
      detail: ev.message.replace(/\s+/g, ' ').slice(0, 120),
      scope: 'LLM Cowork local',
      state,
      icon: 'shield',
    }
  }
  if (ev.actionKind) {
    return {
      label: labelForActionKind(ev.actionKind),
      detail: ev.message.replace(/\s+/g, ' ').slice(0, 120),
      scope: scopeForActionKind(ev.actionKind),
      state,
      icon: iconForActionKind(ev.actionKind),
    }
  }
  return null
}

function parseEventAction(detail?: string): Record<string, unknown> | null {
  if (!detail || !detail.trim().startsWith('{')) return null
  try {
    const parsed = JSON.parse(detail) as unknown
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : null
  } catch {
    return null
  }
}

function summarizeActionActivity(
  action: Record<string, unknown>,
  state: CoworkActivitySummary['state'],
  ev: CoworkActionEvent,
): CoworkActivitySummary {
  const kind = typeof action.kind === 'string' ? action.kind : ev.actionKind ?? 'unknown'
  const detail = summarizePayload(action, ev.message)
  return {
    label: kind === 'connector' ? labelForConnectorActivity(action) : labelForActionKind(kind),
    detail,
    scope: scopeForAction(action),
    state,
    icon: iconForActionKind(kind),
  }
}

function labelForConnectorActivity(action: Record<string, unknown>): string {
  const connector = String(action.connector || '')
  const connectorAction = String(action.action || '')
  if (connector === 'aurora_image') return connectorAction === 'img2img' ? 'Modifie une image' : 'Genere une image'
  if (connector === 'aurora_3d') return 'Prepare le modele 3D'
  if (connector === 'aurora_code') {
    const params = action.params && typeof action.params === 'object' ? action.params as Record<string, unknown> : {}
    const prompt = String(params.prompt || '').toLowerCase()
    return /\b(jeu|game|gameplay|personnage)\b/.test(prompt) ? 'Construit le jeu' : 'Genere du code'
  }
  if (connector === 'aurora_video') return 'Compose une video'
  if (connector === 'aurora_voice') return 'Genere la voix'
  return 'Utilise un connecteur'
}

function scopeForAction(action: Record<string, unknown>): string {
  const kind = typeof action.kind === 'string' ? action.kind : ''
  if (kind === 'shell') return inferShellScope(action)
  if (kind === 'web_search') return 'internet - moteur de recherche'
  if (kind === 'fetch' || kind === 'open_url') return internetScope(String(action.url || ''))
  if (kind === 'browser') return browserScope(action)
  if (kind === 'connector') return connectorScope(action)
  if (kind === 'read_file' || kind === 'list_dir' || kind === 'write_file' || kind === 'edit_file' || kind === 'delete_file') {
    return localPathScope(String(action.path || ''))
  }
  if (kind === 'screenshot_desktop') return 'bureau local - ecran'
  if (kind === 'dom_query') return 'application web locale'
  if (kind === 'think' || kind === 'think_long' || kind === 'reply' || kind === 'finish') return 'LLM Cowork local'
  return 'Cowork local'
}

function scopeForActionKind(kind: string): string {
  if (kind === 'web_search') return 'internet - moteur de recherche'
  if (kind === 'fetch' || kind === 'open_url') return 'internet'
  if (kind === 'browser') return 'bureau distant - navigateur'
  if (kind === 'connector') return 'service distant'
  if (kind === 'shell' || kind === 'screenshot_desktop') return 'bureau local'
  if (kind === 'think' || kind === 'think_long' || kind === 'reply' || kind === 'finish') return 'LLM Cowork local'
  return 'bureau local'
}

function inferShellScope(action: Record<string, unknown>): string {
  const cwd = typeof action.cwd === 'string' ? action.cwd : ''
  const command = typeof action.command === 'string' ? action.command : ''
  const args = Array.isArray(action.args) ? action.args.map(String).join(' ') : ''
  const text = `${command} ${args} ${cwd}`.toLowerCase()
  if (/(ssh|scp|winrs|psexec|evil-winrm|mstsc|rdp|nmap|hydra|metasploit|msfconsole|net use|\\\\)/.test(text)) {
    return 'bureau distant - machine cible'
  }
  if (/https?:\/\//.test(text) || /\b(curl|wget|Invoke-WebRequest|iwr)\b/i.test(`${command} ${args}`)) {
    return 'internet - ligne de commande'
  }
  return localPathScope(cwd || '')
}

function internetScope(url: string): string {
  try {
    const host = new URL(url).hostname
    return host ? `internet - ${host}` : 'internet'
  } catch {
    return 'internet'
  }
}

function browserScope(action: Record<string, unknown>): string {
  const payload = action.payload && typeof action.payload === 'object' ? action.payload as Record<string, unknown> : {}
  const url = typeof payload.url === 'string' ? payload.url : ''
  if (url) return internetScope(url)
  const op = typeof action.operation === 'string' ? action.operation : 'onglet'
  return `bureau distant - navigateur (${op})`
}

function connectorScope(action: Record<string, unknown>): string {
  const connector = connectorLabel(action)
  return connector ? `service distant - ${connector}` : 'service distant'
}

function connectorLabel(action: Record<string, unknown>): string {
  const raw = typeof action.connector === 'string' ? action.connector : ''
  return raw ? raw.replace(/[-_]+/g, ' ') : ''
}

function localPathScope(path: string): string {
  const clean = path.replace(/\\/g, '/').toLowerCase()
  if (!clean) return 'bureau local'
  if (clean.includes('/users/juan/desktop')) return 'bureau local - Bureau'
  if (clean.includes('/desktop/')) return 'bureau local - Bureau'
  if (clean.includes('/auroraia-v2/')) return 'bureau local - projet AuroraIA-v2'
  return 'bureau local - fichiers'
}

function summarizePayload(action: Record<string, unknown>, fallback: string): string {
  const kind = typeof action.kind === 'string' ? action.kind : ''
  if (kind === 'shell') {
    const command = typeof action.command === 'string' ? action.command : ''
    const args = Array.isArray(action.args) ? action.args.map(String).join(' ') : ''
    return `Je lance : ${`${command} ${args}`.trim()}`.slice(0, 140)
  }
  if (kind === 'web_search') return `Je recherche : ${String(action.query || '')}`.slice(0, 140)
  if (kind === 'fetch' || kind === 'open_url') return `Je lis : ${summarizeUrlForActivity(String(action.url || ''))}`.slice(0, 140)
  if (kind === 'browser') {
    const op = String(action.operation || 'operation')
    const payload = action.payload && typeof action.payload === 'object' ? action.payload as Record<string, unknown> : {}
    const target = String(payload.url || payload.selector || '')
    return `Je controle : ${op}${target ? ` - ${target}` : ''}`.slice(0, 140)
  }
  if (kind === 'connector') return `J utilise : ${String(action.connector || '')}.${String(action.action || '')}`.slice(0, 140)
  if (kind === 'write_file') return `Je cree : ${summarizePathForActivity(String(action.path || ''))}`.slice(0, 140)
  if (kind === 'edit_file') return `Je modifie : ${summarizePathForActivity(String(action.path || ''))}`.slice(0, 140)
  if (kind === 'read_file') return `Je lis : ${summarizePathForActivity(String(action.path || ''))}`.slice(0, 140)
  if (kind === 'list_dir') return `Je scanne : ${summarizePathForActivity(String(action.path || ''))}`.slice(0, 140)
  if ('path' in action) return summarizePathForActivity(String(action.path || '')).slice(0, 140)
  if (kind === 'think' || kind === 'think_long') return String(action.topic || '').slice(0, 140)
  if (kind === 'reply') return 'redaction de la reponse'
  if (kind === 'finish') return 'verification et cloture'
  return fallback.replace(/\s+/g, ' ').slice(0, 140)
}

function summarizeUrlForActivity(url: string): string {
  try {
    const parsed = new URL(url)
    const path = parsed.pathname && parsed.pathname !== '/' ? parsed.pathname.split('/').filter(Boolean).slice(-2).join('/') : ''
    return `${parsed.hostname}${path ? `/${path}` : ''}`
  } catch {
    return url
  }
}

function summarizePathForActivity(path: string): string {
  return path.replace(/\\/g, '/').split('/').filter(Boolean).slice(-3).join('/')
}

function labelForActionKind(kind: string): string {
  switch (kind) {
    case 'think':
    case 'think_long': return 'Reflechit'
    case 'web_search': return 'Recherche web'
    case 'fetch':
    case 'open_url': return 'Lit une ressource web'
    case 'shell': return 'Utilise commande shell'
    case 'read_file': return 'Lit un fichier'
    case 'list_dir': return 'Scanne un dossier'
    case 'write_file': return 'Cree un fichier'
    case 'edit_file': return 'Code et modifie'
    case 'delete_file': return 'Supprime un fichier'
    case 'browser': return 'Controle le navigateur'
    case 'connector': return 'Utilise un connecteur'
    case 'screenshot_desktop':
    case 'vision_describe': return 'Verifie visuellement'
    case 'reply': return 'Redige la reponse'
    case 'finish': return 'Finalise'
    default: return 'Travaille'
  }
}

function iconForActionKind(kind: string): CoworkActivitySummary['icon'] {
  switch (kind) {
    case 'shell': return 'terminal'
    case 'web_search':
    case 'fetch':
    case 'open_url': return 'globe'
    case 'read_file':
    case 'list_dir':
    case 'write_file': return 'file'
    case 'edit_file':
    case 'delete_file': return 'pencil'
    case 'browser':
    case 'connector': return 'remote'
    case 'screenshot_desktop':
    case 'vision_describe':
    case 'dom_query': return 'eye'
    case 'finish': return 'shield'
    case 'think':
    case 'think_long':
    case 'reply':
    default: return 'brain'
  }
}

function CoworkArtifactPreviewRow({ artifacts }: { artifacts: CoworkProjectArtifact[] }) {
  const shown = artifacts.slice(0, 6)
  return (
    <div className="grid grid-cols-1 gap-2">
      {shown.map((artifact) => (
        <CoworkArtifactWorkspaceCard key={artifact.id} artifact={artifact} />
      ))}
    </div>
  )
}

function CoworkArtifactWorkspaceCard({ artifact }: { artifact: CoworkProjectArtifact }) {
  const href = previewUrlForCoworkArtifact(artifact)
  const codePayload = useMemo(() => extractArtifactCode(artifact), [artifact])
  const hasCode = Boolean(codePayload.code)
  const hasEmulator = hasCode || Boolean(href)
  const [mode, setMode] = useState<'preview' | 'code' | 'emulator'>(() => hasCode ? 'code' : 'preview')
  const [fullscreen, setFullscreen] = useState(false)
  const [hidden, setHidden] = useState(false)
  const downloadHref = useMemo(() => buildArtifactDownloadHref(artifact, codePayload.code, href), [artifact, codePayload.code, href])
  const downloadName = buildArtifactDownloadName(artifact, codePayload.language)
  const isImage = artifact.kind === 'image' && href
  const shell = fullscreen
    ? 'fixed inset-4 z-[80] flex flex-col overflow-hidden rounded-2xl border border-violet-300/30 bg-[#080713]/96 shadow-2xl shadow-black/70 backdrop-blur-xl'
    : 'overflow-hidden rounded-xl border border-white/8 bg-white/[0.04]'

  useEffect(() => {
    if (mode === 'code' && !hasCode) setMode('preview')
    if (mode === 'emulator' && !hasEmulator) setMode('preview')
  }, [hasCode, hasEmulator, mode])

  if (hidden) return null

  return (
    <div className={shell} title={artifact.path || artifact.url || artifact.summary || artifact.label}>
      <div className="flex items-center justify-between gap-2 border-b border-white/8 px-3 py-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.16em] text-violet-200/70">
              {artifactLabel(artifact.kind)} v{artifact.version}
            </span>
            {artifact.active && <span className="rounded-full bg-emerald-400/12 px-1.5 py-0.5 text-[9px] text-emerald-200/85">actif</span>}
          </div>
          <div className="mt-0.5 truncate text-[12px] text-white/82">{artifact.label}</div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {(hasCode || hasEmulator) && (
            <div className="mr-1 inline-flex rounded-lg border border-white/10 bg-black/20 p-0.5">
              {hasCode && (
                <button
                  type="button"
                  onClick={() => setMode('code')}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] ${mode === 'code' ? 'bg-violet-500/35 text-white' : 'text-white/55 hover:text-white/82'}`}
                  title="Voir le code colore"
                >
                  <Code2 size={11} /> Code
                </button>
              )}
              {hasEmulator && (
                <button
                  type="button"
                  onClick={() => setMode('emulator')}
                  className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] ${mode === 'emulator' ? 'bg-violet-500/35 text-white' : 'text-white/55 hover:text-white/82'}`}
                  title="Voir dans l emulateur sandbox"
                >
                  <Monitor size={11} /> Emulateur
                </button>
              )}
            </div>
          )}
          {downloadHref && (
            <a
              href={downloadHref}
              download={downloadName}
              className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/62 hover:bg-white/[0.08] hover:text-white"
              title={`Telecharger ${downloadName}`}
            >
              <Download size={13} />
            </a>
          )}
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/62 hover:bg-white/[0.08] hover:text-white"
              title="Ouvrir l artefact"
            >
              <Eye size={13} />
            </a>
          )}
          <button
            type="button"
            onClick={() => setFullscreen((value) => !value)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/62 hover:bg-white/[0.08] hover:text-white"
            title={fullscreen ? 'Quitter le plein ecran' : 'Plein ecran'}
          >
            {fullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button
            type="button"
            onClick={() => setHidden(true)}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-white/50 hover:bg-red-500/12 hover:text-red-100"
            title="Masquer cette carte"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      <div className={fullscreen ? 'min-h-0 flex-1 overflow-hidden' : ''}>
        {mode === 'code' && hasCode ? (
          <div className={`${fullscreen ? 'h-full overflow-auto' : 'max-h-80 overflow-auto'} bg-[#090b12] font-mono text-[12px]`}>
            <CodeBlock code={codePayload.code} language={codePayload.language} showLineNumbers />
          </div>
        ) : mode === 'emulator' && hasEmulator ? (
          <CoworkArtifactEmulator artifact={artifact} href={href} code={codePayload.code} language={codePayload.language} fullscreen={fullscreen} />
        ) : (
          <div>
            {isImage ? (
              <img
                src={href}
                alt={artifact.label}
                className={`${fullscreen ? 'h-full max-h-[calc(100vh-8rem)]' : 'h-44'} w-full object-contain bg-black/35`}
                onError={(e) => { e.currentTarget.style.display = 'none' }}
              />
            ) : (
              <div className="flex min-h-28 items-center gap-3 px-3 py-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.05] text-[12px] font-semibold text-violet-100">
                  {artifact.kind === 'model3d' ? '3D' : artifact.kind === 'game' ? 'GAME' : artifact.kind === 'video' ? 'MP4' : artifact.kind === 'code' ? 'CODE' : 'FILE'}
                </div>
                <div className="min-w-0">
                  <div className="text-[12px] text-white/72">{artifact.summary ? artifact.summary.slice(0, 180) : 'Artefact disponible dans le fil Cowork.'}</div>
                  {(artifact.path || artifact.url) && (
                    <div className="mt-2 truncate font-mono text-[10px] text-white/38">
                      {artifact.path || artifact.url}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CoworkArtifactEmulator({
  artifact,
  href,
  code,
  language,
  fullscreen,
}: {
  artifact: CoworkProjectArtifact
  href: string
  code: string
  language: string
  fullscreen: boolean
}) {
  const canFrameHref = href && (artifact.kind === 'game' || /\.(html?|svg)(?:[?#].*)?$/i.test(href))
  const srcDoc = canFrameHref ? undefined : buildArtifactEmulatorSrcDoc(artifact, code, language, href)
  return (
    <iframe
      title={`${artifact.label} - emulateur`}
      src={canFrameHref ? href : undefined}
      srcDoc={srcDoc}
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
      className={`${fullscreen ? 'h-full min-h-[60vh]' : 'h-72'} w-full bg-[#070812]`}
    />
  )
}

function extractArtifactCode(artifact: CoworkProjectArtifact): { code: string; language: string } {
  const raw = artifact.summary || ''
  if (!raw && artifact.kind !== 'code' && artifact.kind !== 'game') return { code: '', language: 'text' }
  const fence = raw.match(/```([a-zA-Z0-9_+-]*)\s*\n([\s\S]*?)```/)
  const language = normalizeArtifactLanguage(fence?.[1] || inferArtifactLanguage(artifact))
  const code = fence?.[2]?.trim() || (artifact.kind === 'code' || artifact.kind === 'game' ? raw.trim() : '')
  return { code, language }
}

function inferArtifactLanguage(artifact: CoworkProjectArtifact): string {
  const ref = `${artifact.path || artifact.url || ''} ${artifact.sourcePrompt || ''}`.toLowerCase()
  if (/\btypescript|\.tsx?|react\b/.test(ref)) return 'typescript'
  if (/\bjavascript|\.jsx?|canvas\b/.test(ref)) return 'javascript'
  if (/\.html?|site|page web/.test(ref)) return 'html'
  if (/\.css/.test(ref)) return 'css'
  if (/\.py|python/.test(ref)) return 'python'
  if (/\.json/.test(ref)) return 'json'
  return artifact.kind === 'game' ? 'html' : 'text'
}

function normalizeArtifactLanguage(value: string): string {
  const lower = value.toLowerCase().trim()
  if (lower === 'ts' || lower === 'tsx') return 'typescript'
  if (lower === 'js' || lower === 'jsx' || lower === 'mjs') return 'javascript'
  if (lower === 'html') return 'markup'
  return lower || 'text'
}

function buildArtifactDownloadHref(artifact: CoworkProjectArtifact, code: string, href: string): string {
  if (href) return href
  if (code) return `data:text/plain;charset=utf-8,${encodeURIComponent(code)}`
  if (artifact.summary) return `data:text/plain;charset=utf-8,${encodeURIComponent(artifact.summary)}`
  return ''
}

function buildArtifactDownloadName(artifact: CoworkProjectArtifact, language: string): string {
  const ref = artifact.path || artifact.url || ''
  const name = ref.replace(/\\/g, '/').split('/').filter(Boolean).pop()
  if (name) return name.replace(/[?#].*$/, '')
  const ext =
    artifact.kind === 'image' ? 'png'
    : artifact.kind === 'model3d' ? 'glb'
    : artifact.kind === 'video' ? 'mp4'
    : language === 'typescript' ? 'ts'
    : language === 'javascript' ? 'js'
    : language === 'markup' || language === 'html' ? 'html'
    : language === 'python' ? 'py'
    : 'txt'
  return `cowork-${artifact.kind}-v${artifact.version}.${ext}`
}

function buildArtifactEmulatorSrcDoc(artifact: CoworkProjectArtifact, code: string, language: string, href: string): string {
  const safeTitle = escapeHtml(artifact.label)
  if (code && /<!doctype html|<html[\s>]/i.test(code)) return code
  if (code && (language === 'markup' || language === 'html')) {
    return code.includes('<body') ? code : `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title></head><body>${code}</body></html>`
  }
  if (code && language === 'javascript') {
    return `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title><style>${emulatorCss()}</style></head><body><main><h1>${safeTitle}</h1><p>Sandbox JavaScript avec console capturee.</p><pre id="out"></pre></main><script>const out=document.getElementById('out');const print=(...a)=>{out.textContent+=a.map(x=>typeof x==='object'?JSON.stringify(x,null,2):String(x)).join(' ')+'\\n'};console.log=print;console.error=(...a)=>print('ERROR:',...a);try{${code.replace(/<\/script/gi, '<\\/script')}}catch(e){print('ERROR:',e&&e.stack||e)}<\/script></body></html>`
  }
  return `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title><style>${emulatorCss()}</style></head><body><main><h1>${safeTitle}</h1><p>${href ? `Artefact lie: <a href="${escapeHtml(href)}" target="_blank">${escapeHtml(href)}</a>` : 'Emulation directe indisponible pour ce type, affichage technique ci-dessous.'}</p><pre>${escapeHtml(code || artifact.summary || artifact.path || artifact.url || 'Aucun contenu brut expose.')}</pre></main></body></html>`
}

function emulatorCss(): string {
  return 'html,body{margin:0;height:100%;background:#070812;color:#e5e7eb;font:14px/1.5 Inter,Segoe UI,system-ui,sans-serif}main{padding:22px}h1{font-size:18px;margin:0 0 8px;color:#c4b5fd}p{color:#a1a1aa}pre{white-space:pre-wrap;background:#0f1220;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:14px;overflow:auto}a{color:#c4b5fd}'
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function ChatBubble({ turn, onRegenerate, onEdit, onQuickPrompt }: {
  turn: ChatTurn
  onRegenerate?: () => void
  onEdit?: () => void
  onQuickPrompt?: (prompt: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const isUser = turn.role === 'user'
  const techCount = turn.technical?.length ?? 0
  const runMeta = !isUser && techCount > 0 ? getCoworkRunMeta(turn) : null

  // v22 — typewriter reveal : when an Aurora bubble's content lands fresh,
  // animate revealing it progressively so the page feels alive instead of
  // a single BAM-here-is-everything paint. Caps at ~600ms total regardless
  // of content length so long markdown rapports don't take forever.
  // Already-rendered turns (loaded from localStorage on mount) are revealed
  // instantly — we only animate turns that just transitioned out of pending.
  const [displayedLength, setDisplayedLength] = useState<number>(() =>
    isUser || turn.pending ? 0 : (turn.content?.length ?? 0))
  const animatedRef = useRef(false)
  useEffect(() => {
    if (isUser) {
      setDisplayedLength(turn.content?.length ?? 0)
      return
    }
    if (turn.pending) {
      setDisplayedLength(0)
      return
    }
    const total = turn.content?.length ?? 0
    if (total === 0) {
      setDisplayedLength(0)
      return
    }
    if (animatedRef.current) {
      // Already animated this bubble in this session — keep fully revealed.
      setDisplayedLength(total)
      return
    }
    animatedRef.current = true
    setDisplayedLength(0)
    const TOTAL_MS = Math.min(800, Math.max(180, total * 1.2))
    const STEPS = 24
    const stepMs = TOTAL_MS / STEPS
    let cur = 0
    const id = setInterval(() => {
      cur += 1
      const next = Math.min(total, Math.round((total * cur) / STEPS))
      setDisplayedLength(next)
      if (cur >= STEPS) clearInterval(id)
    }, stepMs)
    return () => clearInterval(id)
  }, [isUser, turn.pending, turn.content])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(turn.content || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* clipboard unavailable */ }
  }
  const visibleMarkdown = useMemo(
    () => renderInteractiveMarkdown(turn.content.slice(0, displayedLength)),
    [turn.content, displayedLength],
  )

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} group`}>
      <div className={`max-w-[88%] flex flex-col gap-1.5`}>
        <div className={`px-4 py-2.5 rounded-2xl text-[13px] leading-relaxed break-words ${
          isUser
            ? 'bg-violet-500 text-white rounded-br-md whitespace-pre-wrap'
            : 'bg-white/[0.05] text-white/90 border border-white/8 rounded-bl-md cowork-md'
        }`}>
          {isUser ? (
            turn.content
          ) : turn.pending && !turn.content ? (
            <CoworkLiveActivity events={turn.technical ?? []} />
          ) : turn.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const isInline = !className
                  return isInline
                    ? <code className="px-1 py-0.5 rounded bg-black/40 text-violet-200 text-[12px]" {...props}>{children}</code>
                    : <code className={className} {...props}>{children}</code>
                },
                a({ children, href, ...props }) {
                  if (href?.startsWith('cowork://explain/')) {
                    const notion = safeDecodeURIComponent(href.slice('cowork://explain/'.length))
                    return (
                      <button
                        type="button"
                        className="inline-flex items-center rounded-full border border-violet-400/25 bg-violet-500/10 px-2 py-0.5 text-[12px] font-medium text-violet-200 hover:bg-violet-500/20 hover:text-violet-100"
                        onClick={() => onQuickPrompt?.(buildExplainNotionPrompt(notion))}
                        title={`Expliquer: ${notion}`}
                      >
                        {children}
                      </button>
                    )
                  }
                  return <a target="_blank" rel="noopener noreferrer" className="text-violet-300 hover:underline" href={href} {...props}>{children}</a>
                },
              }}
            >{visibleMarkdown}</ReactMarkdown>
          ) : (
            <span className="text-white/40 italic">(reponse vide)</span>
          )}
          {/* Typewriter caret while still revealing */}
          {!isUser && !turn.pending && turn.content && displayedLength < turn.content.length && (
            <span className="inline-block w-1.5 h-[14px] -mb-0.5 bg-violet-300/80 ml-0.5 animate-pulse" />
          )}
        </div>
        {!isUser && turn.artifacts && turn.artifacts.length > 0 && (
          <CoworkArtifactPreviewRow artifacts={turn.artifacts} />
        )}
        {/* Action toolbar (Aurora bubbles only, hidden until hover for cleanliness) */}
        {!isUser && !turn.pending && turn.content && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/[0.04] text-white/55 border border-white/8 hover:bg-white/[0.08] hover:text-white/80 transition-colors"
              title="Copier la reponse"
            >
              <Copy size={10} />
              {copied ? 'Copie !' : 'Copier'}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/[0.04] text-white/55 border border-white/8 hover:bg-white/[0.08] hover:text-white/80 transition-colors"
                title="Refaire avec la meme question"
              >
                <RefreshCw size={10} />
                Refaire
              </button>
            )}
          </div>
        )}
        {/* v32 — User bubble toolbar : Edit button (hover-revealed). Click
            preloads the prompt in the composer + drops the user/aurora pair
            so the user can reformulate cleanly. Right-aligned for symmetry
            with the user bubble (which is right-justified). */}
        {isUser && onEdit && turn.content && (
          <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/[0.04] text-white/55 border border-white/8 hover:bg-white/[0.08] hover:text-white/80 transition-colors"
              title="Copier ma question"
            >
              <Copy size={10} />
              {copied ? 'Copie !' : 'Copier'}
            </button>
            <button
              onClick={onEdit}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/[0.04] text-white/55 border border-white/8 hover:bg-white/[0.08] hover:text-white/80 transition-colors"
              title="Modifier cette question (la paire suivante sera supprimee)"
            >
              <Pencil size={10} />
              Editer
            </button>
          </div>
        )}
        {!isUser && techCount > 0 && runMeta && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] text-white/35">
              Lance a {runMeta.startedLabel} - duree {runMeta.durationLabel} - {runMeta.steps} etape{runMeta.steps > 1 ? 's' : ''}
            </span>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="self-start flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-medium bg-white/[0.04] text-white/55 border border-white/8 hover:bg-white/[0.08] hover:text-white/80 transition-colors"
            >
              {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
              {expanded ? 'Masquer les coulisses' : `Voir toutes les etapes (${techCount})`}
            </button>
          </div>
        )}
        {!isUser && expanded && turn.technical && (
          <div className="rounded-xl border border-white/8 bg-black/40 p-3 max-h-[260px] overflow-y-auto">
            <ul className="space-y-1.5">
              {turn.technical.map((ev, i) => <CoworkEventRow key={i} event={ev} />)}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Console drawer (chat mode side panel) — same content as EventsLog but
// docked to the right with a close button. Streams the current turn's
// events live as Aurora works.
// ---------------------------------------------------------------------------
function ConsoleDrawer({
  events, running, onClose,
}: {
  events: CoworkActionEvent[]
  running: boolean
  onClose: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, running])

  return (
    <div className="rounded-2xl border border-white/8 bg-black/40 flex flex-col min-h-0 flex-1">
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/5 flex-shrink-0">
        <p className="text-[10px] uppercase tracking-[0.18em] text-white/45 flex items-center gap-1.5">
          <Terminal size={10} />
          Console technique · {events.length} evt
        </p>
        <button
          onClick={onClose}
          className="text-white/40 hover:text-white transition-colors p-1 rounded hover:bg-white/[0.06]"
          title="Fermer la console"
        >
          <X size={12} />
        </button>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto p-3 min-h-0">
        {events.length === 0 && !running && (
          <p className="text-[11px] text-white/40 text-center py-8">
            La console s anime quand Aurora travaille.
          </p>
        )}
        <ul className="space-y-1.5">
          {events.map((ev, i) => <CoworkEventRow key={i} event={ev} />)}
          {running && (
            <li className="flex items-center gap-2 text-[11px] text-violet-300">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              en cours…
            </li>
          )}
        </ul>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Events log
// ---------------------------------------------------------------------------

function EventsLog({ events, running }: { events: CoworkActionEvent[]; running: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the bottom whenever a new event arrives, so the user
  // always sees the latest action without manually scrolling.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, running])

  return (
    <div ref={containerRef} className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 flex-1 overflow-y-auto min-h-0">
      <p className="text-[10px] uppercase tracking-[0.18em] text-white/40 mb-3">
        {running ? 'En cours…' : events.length > 0 ? `Resultat · ${events.length} etape(s)` : 'Pret'}
      </p>
      {events.length === 0 && !running && (
        <div className="flex flex-col items-center justify-center h-full text-center py-12">
          <Zap size={28} className="text-white/20 mb-3" />
          <p className="text-[12px] text-white/45 max-w-md">
            Tape ou dicte une consigne. Aurora analysera l intent, planifiera des actions et te demandera confirmation
            avant tout effet destructif.
          </p>
        </div>
      )}
      <ul className="space-y-2">
        {events.map((ev, i) => (
          <CoworkEventRow key={i} event={ev} />
        ))}
        {running && (
          <li className="flex items-center gap-2 text-[12px] text-violet-300">
            <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
            Aurora travaille…
          </li>
        )}
      </ul>
    </div>
  )
}

function CoworkEventRow({ event }: { event: CoworkActionEvent }) {
  const tone =
    event.kind === 'error' ? 'text-red-300 bg-red-500/8 border-red-500/20'
    : event.kind === 'warn' ? 'text-amber-200 bg-amber-500/8 border-amber-500/20'
    : event.kind === 'success' ? 'text-emerald-200 bg-emerald-500/8 border-emerald-500/20'
    : 'text-white/80 bg-white/[0.02] border-white/8'

  // v82m0 — connector pill : when the event detail JSON describes a
  // browser.extract_structured(card_iteration) action whose payload carries
  // a connector_hint string, render a small pill so the user sees the
  // connector recommendation surfaced from the planner. Pure read of the
  // event.detail JSON — no executor change.
  const connectorHint = extractConnectorHintFromEventDetail(event)
  // v82m1 — extract the connector id+label from the hint. When non-null,
  // the pill becomes clickable (cursor:pointer, opens opt-in dialog).
  // When null (generic / extension-only host), pill stays a passive label.
  const connectorTarget = connectorHint ? extractConnectorTargetFromHint(connectorHint) : null
  const [optInOpen, setOptInOpen] = useState(false)
  const openSettings = useCoworkStore((s) => s.openSettings)

  const onPillClick = () => {
    if (!connectorTarget) return
    setOptInOpen(true)
  }
  const onConfirmOptIn = () => {
    if (!connectorTarget) return
    setOptInOpen(false)
    // v82m2 — write a connector_optin_clicked audit entry BEFORE navigating
    // to settings so the audit drawer surfaces which sites prompted the
    // user most often. We extract the host from the connector hint label
    // (e.g. "LinkedIn") fallback to the connector id when no label is
    // available. Pure observability — never blocks the navigation.
    try {
      const host = (connectorHint && /on ([\w.+-]+\.[a-z]{2,})/i.exec(connectorHint)?.[1])
        || (connectorTarget.label ? connectorTarget.label.toLowerCase() : connectorTarget.id)
      appendConnectorOptInClicked(connectorTarget.id, host)
    } catch { /* noop — audit must never break the user flow */ }
    openSettings(connectorTarget.id)
  }
  const onCancelOptIn = () => setOptInOpen(false)

  return (
    <li className={`text-[12px] px-3 py-2 rounded-lg border ${tone} leading-relaxed`}>
      <div className="flex items-start gap-2">
        <span className="text-[10px] uppercase tracking-wider opacity-60 shrink-0 mt-0.5">{event.kind}</span>
        <span className="text-[10px] font-mono opacity-45 shrink-0 mt-0.5">{formatRunClock(event.at)}</span>
        <div className="flex-1 min-w-0 break-words">
          {event.message}
          {connectorHint && (
            connectorTarget ? (
              <button
                type="button"
                data-testid="cowork-connector-pill"
                data-connector-id={connectorTarget.id}
                data-clickable="true"
                onClick={onPillClick}
                className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/12 text-violet-200 border border-violet-400/30 align-middle cursor-pointer hover:bg-violet-500/25 hover:text-violet-100 hover:border-violet-300/50 transition-colors"
                title={`${connectorHint} — click to configure ${connectorTarget.label}`}
              >
                <span aria-hidden>🔌</span>
                <span>{summariseConnectorHint(connectorHint)}</span>
              </button>
            ) : (
              <span
                data-testid="cowork-connector-pill"
                data-clickable="false"
                className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/12 text-violet-200 border border-violet-400/30 align-middle cursor-default"
                title={connectorHint}
              >
                <span aria-hidden>🔌</span>
                <span>{summariseConnectorHint(connectorHint)}</span>
              </span>
            )
          )}
          {event.detail && (
            <pre className="mt-1 whitespace-pre-wrap text-[10px] opacity-70 max-h-40 overflow-auto">
              {event.detail}
            </pre>
          )}
        </div>
      </div>
      {/* v82m1 — opt-in dialog : only mounted when the user clicks a clickable
          pill. Tiny modal-style confirm that gates the settings navigation
          behind an explicit user choice. ZERO auto-action ; the only way to
          land in Settings → Connecteurs (focused) is via this dialog. */}
      <AnimatePresence>
        {optInOpen && connectorTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[260] flex items-center justify-center bg-black/70 backdrop-blur-sm"
            data-testid="cowork-pill-optin"
          >
            <motion.div
              initial={{ y: 16, opacity: 0, scale: 0.97 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: 8, opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="w-full max-w-sm rounded-2xl border border-white/10 bg-[#0b111b] text-white shadow-[0_24px_72px_rgba(0,0,0,0.55)]"
            >
              <div className="px-5 py-4 border-b border-white/8">
                <p className="text-[10px] uppercase tracking-[0.2em] text-violet-300/80 mb-1">Connecteur detecte</p>
                <h3 className="text-[14px] font-semibold tracking-tight">Configurer le connecteur {connectorTarget.label} ?</h3>
                <p className="mt-2 text-[11px] text-white/60 leading-relaxed">
                  Aurora a detecte que la page actuelle est servie par {connectorTarget.label}. Configurer ce connecteur permet une extraction plus riche que le scrape topologique generique.
                </p>
              </div>
              <div className="flex items-center justify-end gap-2 px-5 py-3 bg-white/[0.02]">
                <button
                  type="button"
                  data-testid="cowork-pill-optin-cancel"
                  onClick={onCancelOptIn}
                  className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-white/70 hover:bg-white/8 hover:text-white transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  data-testid="cowork-pill-optin-confirm"
                  onClick={onConfirmOptIn}
                  className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-violet-500/80 hover:bg-violet-500 text-white transition-colors"
                >
                  Configurer
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  )
}

// ---------------------------------------------------------------------------
// Audit drawer
// ---------------------------------------------------------------------------

function AuditDrawer({
  entries,
  onClear,
  onRefresh,
}: {
  entries: CoworkAuditEntry[]
  onClear: () => void
  onRefresh: () => void
}) {
  // v82m3 — chip toggle "Tous" / "Opt-in clicks". Default 'all' means
  // legacy behavior (full list). When 'optin' is active, the list narrows
  // to entries flagged with OPTIN_CLICKED_REASON_MARKER so the user sees
  // "I clicked Configurer N times on these sites" without grepping.
  // Pure local state — no new endpoint, no new audit field. The filter
  // helper is exported for unit tests.
  const [chipMode, setChipMode] = useState<AuditChipMode>('all')
  const visibleEntries = filterAuditEntriesForChip(entries, chipMode)
  // Count of opt-in entries shown in the chip label so the user sees the
  // total at a glance (matches the pattern of the main "(N)" counter).
  const optInCount = entries.reduce(
    (n, e) => (e.reason === OPTIN_CLICKED_REASON_MARKER ? n + 1 : n),
    0,
  )
  // v82m5 — promote-connector CTA. Local state, NOT persisted : when the
  // user clicks Plus tard, the banner is hidden for THIS session only
  // (refreshing the drawer surfaces it again so the nudge is gentle, not
  // sticky-dismissed). When the user clicks Confirmer, the connector is
  // pinned via `pinConnector` (localStorage-backed) and we mark the CTA
  // confirmed so it stops re-rendering. We compute the candidate from the
  // FULL entries list (not the chip-filtered visible one) so the signal
  // is independent of the user's filter choice.
  const [promoteCtaState, setPromoteCtaState] = useState<'pending' | 'confirmed' | 'dismissed'>('pending')
  const promoteCandidate = (() => {
    if (promoteCtaState !== 'pending') return null
    const summary = summariseOptInClicksByHost(entries)
    const candidate = selectPromoteConnectorCandidate(summary)
    if (!candidate) return null
    // Skip CTA when the connector is already pinned — don't keep nagging.
    const connectorId = connectorIdForHost(candidate.host) || candidate.host
    if (isConnectorPinned(connectorId)) return null
    return { ...candidate, connectorId }
  })()
  const onConfirmPromote = () => {
    if (!promoteCandidate) return
    pinConnector(promoteCandidate.connectorId, promoteCandidate.host)
    setPromoteCtaState('confirmed')
  }
  const onDismissPromote = () => setPromoteCtaState('dismissed')

  // v82m7 — DUAL_SIGNAL_INEFFECTIVE chip + reset path.
  //
  // Discover hosts on which Aurora has recently issued an extract action,
  // probe each one against /api/cowork/dual-signal-effective. Hosts where
  // effective:false get a small red chip with a "Reset signals" button that
  // clears the bridge's per-host slice (POST /api/cowork/dual-signal-reset).
  // Lets the user manually break the cool-down after a strategy change
  // (e.g. logged in to the site, opened a different tab) without restarting
  // the bridge.
  //
  // Probe runs on mount + whenever the entries list changes (the user
  // refreshes the audit log). Single-flight per host : we keep an in-flight
  // controller so a fast re-render doesn't fan out duplicate probes.
  const [ineffectiveHosts, setIneffectiveHosts] = useState<CoworkDualSignalEffective[]>([])
  // v82m9 — tier-2 trend ineffective hosts (derived from /trend-signal-stats
  // with threshold emitted >= 3, accepted == 0). Stored as a Set for O(1)
  // intersection with `ineffectiveHosts` to detect TIER_3 (both flagged).
  const [trendIneffectiveHosts, setTrendIneffectiveHosts] = useState<Set<string>>(new Set())
  const [resetToast, setResetToast] = useState<string | null>(null)
  const ineffectiveProbeAbortRef = useRef<AbortController | null>(null)
  useEffect(() => {
    // Cancel any prior in-flight probe so we never race two effects.
    if (ineffectiveProbeAbortRef.current) {
      try { ineffectiveProbeAbortRef.current.abort() } catch { /* noop */ }
    }
    const ctrl = new AbortController()
    ineffectiveProbeAbortRef.current = ctrl
    const candidateHosts = listExtractHostsFromAuditEntries(entries)
    if (candidateHosts.length === 0) {
      setIneffectiveHosts([])
      setTrendIneffectiveHosts(new Set())
      return
    }
    void (async () => {
      const found: CoworkDualSignalEffective[] = []
      for (const host of candidateHosts) {
        const env = await fetchDualSignalEffective(host, { signal: ctrl.signal })
        if (ctrl.signal.aborted) return
        if (env && env.effective === false) found.push(env)
      }
      // v82m9 — pull trend-signal-stats once (global aggregate) and derive
      // the per-host tier-2 ineffective set. Threshold matches the planner
      // ctx enricher : emitted >= 3 AND accepted == 0.
      const trendStats = await fetchTrendSignalStats({ signal: ctrl.signal })
      if (ctrl.signal.aborted) return
      const trendSet = new Set<string>()
      if (trendStats) {
        for (const row of trendStats.by_host_top5) {
          if (!row || typeof row.host !== 'string' || !row.host) continue
          if (row.emitted >= 3 && row.accepted === 0) trendSet.add(row.host)
        }
      }
      if (!ctrl.signal.aborted) {
        setIneffectiveHosts(found)
        setTrendIneffectiveHosts(trendSet)
      }
    })()
    return () => {
      try { ctrl.abort() } catch { /* noop */ }
    }
    // entries identity changes on refresh ; that's the trigger we want.
  }, [entries])
  const onResetSignals = async (host: string) => {
    const result = await postDualSignalReset(host)
    if (!result) {
      setResetToast(`Echec reset ${host}`)
      setTimeout(() => setResetToast(null), 2400)
      return
    }
    // Drop the chip locally so the UI updates instantly.
    setIneffectiveHosts((prev) => prev.filter((h) => h.host !== host))
    setResetToast(`Signals reset for ${host} — cleared ${result.cleared_emitted} emitted, ${result.cleared_accepted} accepted`)
    setTimeout(() => setResetToast(null), 2400)
  }

  // v82m9 — TIER_3 cluster reset : fires BOTH /dual-signal-reset AND
  // /trend-signal-reset in parallel for the given host. Surfaces a single
  // success toast on full success, a fallback toast on partial / total
  // failure. Drops the host from BOTH local sets so the UI updates
  // instantly without a re-fetch.
  const onResetAllSignalsForHost = async (host: string) => {
    const [tier1, tier2] = await Promise.all([
      postDualSignalReset(host),
      postTrendSignalReset(host),
    ])
    if (!tier1 && !tier2) {
      setResetToast(`Echec reset ${host}`)
      setTimeout(() => setResetToast(null), 2400)
      return
    }
    // Optimistic local clear regardless of partial success — the user
    // wanted both gone, and we'll re-derive on next refresh anyway.
    setIneffectiveHosts((prev) => prev.filter((h) => h.host !== host))
    setTrendIneffectiveHosts((prev) => {
      const next = new Set(prev)
      next.delete(host)
      return next
    })
    const totalCleared =
      (tier1 ? tier1.cleared_emitted + tier1.cleared_accepted : 0) +
      (tier2 ? tier2.cleared_emitted + tier2.cleared_accepted : 0)
    setResetToast(`Signals reset for ${host} — ${totalCleared} entries cleared (tier-1 + tier-2)`)
    setTimeout(() => setResetToast(null), 2400)
  }
  // v82m9 — derive the list of hosts in TIER_3 terminal state (BOTH tier-1
  // and tier-2 ineffective). Empty when nothing intersects.
  const tier3Hosts = ineffectiveHosts
    .filter((h) => trendIneffectiveHosts.has(h.host))
    .map((h) => h.host)

  // v82m9 — pin promotion conflict detector. For each host that surfaced
  // an extract action recently, build a synthetic planner-recommendation
  // from `connectorIdForHost` and feed both into `detectPinConflict`.
  // When the user has pinned a different id than the catalog heuristic
  // proposes, surface a small chip with a confirm/switch dialog. Pure
  // derivation — no fetch, no DOM mutation outside the chip itself.
  const pinConflicts = (() => {
    const candidateHosts = listExtractHostsFromAuditEntries(entries)
    if (candidateHosts.length === 0) return [] as PinConflictDescriptor[]
    const pinned = readPinnedConnectors()
    if (pinned.length === 0) return [] as PinConflictDescriptor[]
    const out: PinConflictDescriptor[] = []
    const seen = new Set<string>()
    for (const host of candidateHosts) {
      if (seen.has(host)) continue
      seen.add(host)
      const recoId = connectorIdForHost(host)
      if (!recoId) continue
      const recos: PlannerConnectorRecommendation[] = [{ host, connectorId: recoId }]
      const conflict = detectPinConflict(pinned, recos, host)
      if (conflict) out.push(conflict)
    }
    return out
  })()
  const [pinConflictDialog, setPinConflictDialog] = useState<PinConflictDescriptor | null>(null)
  const onConfirmKeepPin = () => {
    setPinConflictDialog(null)
  }
  const onSwitchToSuggested = () => {
    if (!pinConflictDialog) return
    pinConnector(pinConflictDialog.suggestedId, pinConflictDialog.host)
    setPinConflictDialog(null)
  }

  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 flex-1 overflow-y-auto min-h-0">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] uppercase tracking-[0.18em] text-white/40">
          Audit log ({visibleEntries.length}{chipMode === 'optin' ? ` / ${entries.length}` : ''})
        </p>
        <div className="flex gap-2">
          <button
            onClick={onRefresh}
            className="px-2 py-1 rounded-full text-[10px] bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08] transition-colors"
          >
            Rafraichir
          </button>
          <button
            onClick={onClear}
            className="px-2 py-1 rounded-full text-[10px] bg-red-500/10 text-red-200 border border-red-500/30 hover:bg-red-500/20 transition-colors"
          >
            Vider
          </button>
        </div>
      </div>
      {/* v82m5 — promote-connector CTA banner. One-shot nudge fired when a
          single host accumulates >= 3 opt-in clicks and the matching
          connector hasn't been pinned yet. Confirm pins the connector at
          the top of the pin store ; Plus tard hides the banner for THIS
          session only (no persistent dismissal — we re-prompt on next
          drawer mount so the user can change their mind). Audit-driven,
          zero auto-action. */}
      {promoteCandidate && (
        <div
          data-testid="cowork-audit-promote-cta"
          data-host={promoteCandidate.host}
          data-count={promoteCandidate.count}
          data-connector={promoteCandidate.connectorId}
          className="flex flex-col gap-2 mb-3 p-3 rounded-lg border border-violet-400/30 bg-violet-500/10"
        >
          <p className="text-[12px] text-violet-100 leading-snug">
            <span aria-hidden className="mr-1">★</span>
            Promouvoir <strong>{promoteCandidate.host}</strong> comme connecteur principal ?
            <span className="ml-1 text-[10px] text-violet-200/70 font-mono">
              ({promoteCandidate.count} clic(s) sur Configurer)
            </span>
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="cowork-audit-promote-cta-confirm"
              onClick={onConfirmPromote}
              className="px-3 py-1 rounded-full text-[10px] bg-violet-500/30 text-violet-50 border border-violet-400/50 hover:bg-violet-500/50 transition-colors"
            >
              Confirmer
            </button>
            <button
              type="button"
              data-testid="cowork-audit-promote-cta-dismiss"
              onClick={onDismissPromote}
              className="px-3 py-1 rounded-full text-[10px] bg-white/[0.04] text-white/70 border border-white/10 hover:bg-white/[0.08] transition-colors"
            >
              Plus tard
            </button>
          </div>
        </div>
      )}
      {/* v82m9 — TIER_3 cluster reset button. Surfaced ONLY when a host is
          in terminal state (BOTH tier-1 dual-signal AND tier-2 trend-signal
          flagged ineffective). Click fires both /dual-signal-reset AND
          /trend-signal-reset in parallel, giving the user a one-click
          recovery path after manual review (logged in, switched tab, etc.).
          Closes the loop opened by the TIER_3 nudge. */}
      {tier3Hosts.length > 0 && (
        <div
          className="flex flex-col gap-1.5 mb-3"
          data-testid="cowork-audit-tier3-cluster-list"
        >
          {tier3Hosts.map((host) => (
            <div
              key={host}
              data-testid="cowork-audit-tier3-cluster"
              data-host={host}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-orange-500/40 bg-orange-500/10 text-orange-100"
            >
              <span aria-hidden className="text-[12px]">🛑</span>
              <span className="text-[11px] flex-1">
                TIER_3 sur <strong className="font-mono">{host}</strong> — escalations tier-1 + tier-2 ineffectives
              </span>
              <button
                type="button"
                data-testid="cowork-audit-tier3-cluster-reset"
                onClick={() => { void onResetAllSignalsForHost(host) }}
                className="px-2 py-1 rounded-full text-[10px] bg-orange-500/30 text-orange-50 border border-orange-400/50 hover:bg-orange-500/50 transition-colors"
                title={`Reset BOTH tier-1 + tier-2 signal counters for ${host}`}
              >
                🔄 Reset all signals for {host}
              </button>
            </div>
          ))}
        </div>
      )}
      {/* v82m9 — pin promotion conflict chip. Surfaced when the user has
          pinned a connector for a host but the catalog heuristic
          (`connectorIdForHost`) proposes a different id. Click opens a
          tiny confirm/switch dialog. Stays silent when no conflict. */}
      {pinConflicts.length > 0 && (
        <div
          className="flex flex-col gap-1.5 mb-3"
          data-testid="cowork-audit-pin-conflict-list"
        >
          {pinConflicts.map((c) => (
            <button
              key={c.host}
              type="button"
              data-testid="cowork-audit-pin-conflict-chip"
              data-host={c.host}
              data-pinned-id={c.pinnedId}
              data-suggested-id={c.suggestedId}
              onClick={() => setPinConflictDialog(c)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/8 text-amber-200 hover:bg-amber-500/15 transition-colors text-left"
              title={c.message}
            >
              <span aria-hidden className="text-[12px]">⚠️</span>
              <span className="text-[11px] flex-1">
                Conflit pin/reco sur <strong className="font-mono">{c.host}</strong>
                <span className="ml-1 text-[10px] text-amber-300/70 font-mono">
                  (pin={c.pinnedId} ≠ reco={c.suggestedId})
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
      {pinConflictDialog && (
        <div
          data-testid="cowork-audit-pin-conflict-dialog"
          data-host={pinConflictDialog.host}
          className="flex flex-col gap-2 mb-3 p-3 rounded-lg border border-amber-400/40 bg-amber-500/10"
          role="dialog"
          aria-label="Resolution conflit pin"
        >
          <p className="text-[12px] text-amber-100 leading-snug">
            {pinConflictDialog.message}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="cowork-audit-pin-conflict-keep"
              onClick={onConfirmKeepPin}
              className="px-3 py-1 rounded-full text-[10px] bg-amber-500/30 text-amber-50 border border-amber-400/50 hover:bg-amber-500/50 transition-colors"
            >
              Garder {pinConflictDialog.pinnedId}
            </button>
            <button
              type="button"
              data-testid="cowork-audit-pin-conflict-switch"
              onClick={onSwitchToSuggested}
              className="px-3 py-1 rounded-full text-[10px] bg-violet-500/30 text-violet-50 border border-violet-400/50 hover:bg-violet-500/50 transition-colors"
            >
              Switch vers {pinConflictDialog.suggestedId}
            </button>
          </div>
        </div>
      )}
      {/* v82m7 — DUAL_SIGNAL_INEFFECTIVE chips per host. Visible only when
          the bridge reports effective:false on hosts present in audit
          history. Each chip surfaces "INEFFECTIVE on <host>" + a "Reset
          signals" button that clears the bridge's per-host slice so the
          planner can re-evaluate after a manual strategy change. Audit-
          driven, zero auto-action. v82m9 — when a host is ALSO in TIER_3,
          we hide the tier-1-only chip (the cluster button supersedes it).
          */}
      {ineffectiveHosts.filter((r) => !trendIneffectiveHosts.has(r.host)).length > 0 && (
        <div
          className="flex flex-col gap-1.5 mb-3"
          data-testid="cowork-audit-ineffective-chip-list"
        >
          {ineffectiveHosts.filter((r) => !trendIneffectiveHosts.has(r.host)).map((row) => (
            <div
              key={row.host}
              data-testid="cowork-audit-ineffective-chip"
              data-host={row.host}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/30 bg-red-500/8 text-red-200"
            >
              <span aria-hidden className="text-[12px]">⚠️</span>
              <span className="text-[11px] flex-1">
                INEFFECTIVE on <strong className="font-mono">{row.host}</strong> — try a connector
                <span className="ml-1 text-[10px] text-red-300/70 font-mono">
                  ({row.emitted} emitted, {row.accepted} accepted)
                </span>
              </span>
              <button
                type="button"
                data-testid="cowork-audit-ineffective-chip-reset"
                onClick={() => { void onResetSignals(row.host) }}
                className="px-2 py-1 rounded-full text-[10px] bg-red-500/20 text-red-100 border border-red-400/40 hover:bg-red-500/40 transition-colors"
                title={`Clear bridge signal counters for ${row.host}`}
              >
                Reset signals
              </button>
            </div>
          ))}
        </div>
      )}
      {resetToast && (
        <div
          data-testid="cowork-audit-reset-toast"
          className="mb-3 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-[11px]"
          role="status"
        >
          {resetToast}
        </div>
      )}
      {/* v82m3 — filter chip (radio-style). Shows opt-in count in label so
          the user sees frequency at a glance. */}
      <div className="flex gap-1.5 mb-3" role="radiogroup" aria-label="Filtrer audit log">
        <button
          role="radio"
          aria-checked={chipMode === 'all'}
          onClick={() => setChipMode('all')}
          className={`px-2.5 py-1 rounded-full text-[10px] border transition-colors ${
            chipMode === 'all'
              ? 'bg-violet-500/20 text-violet-100 border-violet-400/40'
              : 'bg-white/[0.04] text-white/60 border-white/10 hover:bg-white/[0.08]'
          }`}
        >
          Tous
        </button>
        <button
          role="radio"
          aria-checked={chipMode === 'optin'}
          onClick={() => setChipMode('optin')}
          className={`px-2.5 py-1 rounded-full text-[10px] border transition-colors ${
            chipMode === 'optin'
              ? 'bg-violet-500/20 text-violet-100 border-violet-400/40'
              : 'bg-white/[0.04] text-white/60 border-white/10 hover:bg-white/[0.08]'
          }`}
          title={`${optInCount} clic(s) sur Configurer enregistre(s)`}
        >
          Opt-in clicks{optInCount > 0 ? ` (${optInCount})` : ''}
        </button>
      </div>
      {/* v82m4 — per-host opt-in summary chips. Visible only when the
          chip filter is active AND there is at least one opt-in entry.
          Pure aggregation of `params.host` from connector.optin_clicked
          entries, sorted by frequency. Lets the user see at a glance
          "I keep being prompted to connect reddit" without scanning the
          full list. Pre-empts a future "promote reddit connector"
          suggestion (next pass). */}
      {chipMode === 'optin' && visibleEntries.length > 0 && (() => {
        const summary = summariseOptInClicksByHost(entries)
        if (summary.length === 0) return null
        return (
          <div
            className="flex flex-wrap gap-1.5 mb-3 pb-2 border-b border-white/6"
            data-testid="cowork-audit-optin-host-summary"
          >
            <span className="text-[9px] uppercase tracking-[0.16em] text-white/35 self-center mr-1">
              par host
            </span>
            {summary.map((row) => (
              <span
                key={row.host}
                data-testid="cowork-audit-optin-host-summary-chip"
                data-host={row.host}
                data-count={row.count}
                className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-violet-500/10 text-violet-200/90 border border-violet-400/20"
                title={`${row.count} clic(s) sur Configurer pour ${row.host}`}
              >
                {row.host} × {row.count}
              </span>
            ))}
          </div>
        )
      })()}
      {visibleEntries.length === 0 && (
        <p className="text-[12px] text-white/45 py-4 text-center">
          {chipMode === 'optin'
            ? 'Aucun clic sur Configurer enregistre pour le moment.'
            : 'Aucune action enregistree pour le moment.'}
        </p>
      )}
      <ul className="space-y-1.5">
        {[...visibleEntries].reverse().map((entry) => (
          <li
            key={entry.id}
            className={`text-[11px] px-3 py-2 rounded-lg border ${
              entry.decision === 'block' || entry.decision === 'aborted'
                ? 'border-red-500/20 bg-red-500/8 text-red-200'
                : entry.decision === 'skipped'
                  ? 'border-amber-500/20 bg-amber-500/8 text-amber-200'
                  : entry.result?.ok
                    ? 'border-emerald-500/20 bg-emerald-500/8 text-emerald-200'
                    : 'border-white/8 bg-white/[0.02] text-white/70'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono">{new Date(entry.at).toLocaleTimeString()}</span>
              <span className="uppercase tracking-wider opacity-70 text-[9px]">{entry.decision}</span>
            </div>
            <div className="mt-1 break-words">
              <strong>{entry.action.kind}</strong>
              {' '}
              {summariseEntry(entry)}
            </div>
            {entry.result?.error && (
              <div className="mt-1 text-[10px] opacity-80">erreur: {entry.result.error}</div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function summariseEntry(entry: CoworkAuditEntry): string {
  const a = entry.action
  switch (a.kind) {
    case 'read_file':       return a.path
    case 'list_dir':        return a.path
    case 'write_file':      return `${a.path} (${a.content.length} octets)`
    case 'edit_file':       return a.path
    case 'delete_file':     return a.path
    case 'shell':           return `${a.command} ${(a.args ?? []).slice(0, 3).join(' ')}`
    case 'web_search':      return a.query
    case 'fetch':           return `${a.method ?? 'GET'} ${a.url}`
    case 'open_url':        return a.url
    case 'reply':           return (a.message || '').slice(0, 80)
    case 'finish':          return (a.summary || '').slice(0, 80)
    case 'clipboard_read':  return ''
    case 'clipboard_write': return (a.text || '').slice(0, 60)
    case 'voice_speak':     return `${a.text.slice(0, 60)}${a.text.length > 60 ? '…' : ''}`
    case 'dom_query':       return `${a.selector}${a.attribute ? `[${a.attribute}]` : ''}`
    case 'think':           return `${a.topic} — ${a.thought.slice(0, 60)}`
    case 'think_long':      return `${a.topic} — ${a.prompt.slice(0, 60)} (long)`
    case 'remember_fact':   return a.fact.slice(0, 80)
    case 'forget_fact':     return a.id ? `id=${a.id}` : `match="${a.matching}"`
    case 'vision_describe': return `image ${(a.imageDataUrl.length / 1024).toFixed(0)} KB ${a.question ? '· ' + a.question.slice(0, 40) : ''}`
    case 'screenshot_desktop': return `desktop ${a.quality ?? 'fast'}`
    case 'connector':       return `${a.connector}.${a.action}`
    case 'browser':         return `${a.operation}${a.payload?.selector ? ' ' + String(a.payload.selector).slice(0, 40) : ''}`
  }
}

// ---------------------------------------------------------------------------
// v82l7 — ExtractDrawer : free-form structured extraction UI.
//
// The user describes in plain language what they want from the active tab
// ("liste des cours du jour avec heure et salle", "tous les prix produits
// avec devise"), we send it through the extension dispatch as one
// `extract_structured` command. The bridge calls Ollama with a system prompt
// that forces JSON output adapted to the intent ; items[] comes back with
// keys decided by the LLM.
//
// Why bypass the planner ?
// For "I just want this data" the full plan->execute->replan cycle is
// overkill : 3-5x the latency, several LLM calls, and the user has to read
// reasoning bubbles instead of getting a table. Direct path = single dispatch
// + single Ollama call + render.
// ---------------------------------------------------------------------------

function ExtractDrawer({
  intent,
  onIntentChange,
  onRun,
  onRunWithVision,
  onReset,
  onClose,
  running,
  result,
  error,
  suggestVision,
  onDismissVisionSuggestion,
}: {
  intent: string
  onIntentChange: (v: string) => void
  onRun: () => void
  onRunWithVision: () => void
  onReset: () => void
  onClose: () => void
  running: boolean
  result: {
    items: Array<Record<string, unknown>>
    schema: string
    notes: string
    model: string
    inputLength: number
    intent: string
  } | null
  error: string | null
  // v82l9 — auto-suggest vision banner. Parent computes whether the last
  // result looks weak (empty items / surrender notes / tiny scrape) and sets
  // suggestVision=true. Banner shows a "Reessayer avec vision" CTA + an
  // "Ignorer" dismiss. Both buttons coexist with the existing manual "Avec
  // vision" pill — the banner is just a contextual nudge.
  suggestVision: boolean
  onDismissVisionSuggestion: () => void
}) {
  // Auto-derive table columns from the FIRST item's keys. If items have
  // heterogeneous shapes, we union all keys (capped at 12) so the user
  // doesn't lose data — but the natural common case is homogeneous items
  // (the LLM is instructed to keep the schema stable per call).
  const columns = useMemo<string[]>(() => {
    if (!result || result.items.length === 0) return []
    const keys = new Set<string>()
    for (const it of result.items.slice(0, 50)) {
      if (it && typeof it === 'object' && !Array.isArray(it)) {
        for (const k of Object.keys(it)) keys.add(k)
        if (keys.size >= 12) break
      }
    }
    return Array.from(keys).slice(0, 12)
  }, [result])

  const renderCell = (v: unknown): string => {
    if (v == null) return ''
    if (typeof v === 'string') return v
    if (typeof v === 'number' || typeof v === 'boolean') return String(v)
    try { return JSON.stringify(v) } catch { return String(v) }
  }

  const copyJSON = async () => {
    if (!result) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(result.items, null, 2))
    } catch { /* clipboard unavailable */ }
  }

  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4 flex-1 overflow-y-auto min-h-0 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-violet-300" />
          <p className="text-[10px] uppercase tracking-[0.18em] text-white/40">
            Extraction directe — bypass planner
          </p>
        </div>
        <button
          onClick={onClose}
          className="px-2 py-0.5 rounded-full text-[10px] bg-white/[0.04] text-white/60 border border-white/10 hover:bg-white/[0.08] transition-colors"
        >
          Fermer
        </button>
      </div>

      <textarea
        rows={3}
        placeholder="Que veux-tu extraire de cette page ? Exemple : liste des cours du jour avec heure de debut, heure de fin, matiere, salle, prof"
        value={intent}
        onChange={(e) => onIntentChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault()
            if (intent.trim() && !running) onRun()
          }
        }}
        disabled={running}
        className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-[13px] text-white outline-none placeholder:text-white/35 focus:border-violet-500/40"
      />
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={onRun}
          disabled={!intent.trim() || running}
          className="flex items-center gap-2 px-4 py-1.5 rounded-full text-[12px] font-semibold bg-violet-500 text-white hover:bg-violet-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Brain size={12} />
          {running ? 'Extraction…' : 'Extraire'}
        </button>
        {/* v82l8 — vision-mode extraction. Captures the visible viewport via
            captureVisibleTab and routes through qwen3-vl:8b. Useful when the
            page relies on graphical layout (cards, dashboards, schemas) that
            text scraping flattens. Same quotas apply (intent required, items
            cap, 90s timeout). */}
        <button
          onClick={onRunWithVision}
          disabled={!intent.trim() || running}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-medium bg-white/[0.04] text-violet-200 border border-violet-500/30 hover:bg-violet-500/15 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="Capture la page + utilise qwen3-vl pour les pages graphiques (cartes, dashboards, schemas)"
        >
          <Eye size={12} />
          {running ? '…' : 'Avec vision'}
        </button>
        <button
          onClick={onReset}
          disabled={running || (!intent && !result && !error)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] bg-white/[0.03] text-white/55 border border-white/10 hover:bg-white/[0.07] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Vide l intent et le dernier resultat (efface la persistance localStorage)"
        >
          <RotateCcw size={11} />
          Reset
        </button>
        <span className="text-[10px] text-white/40">
          ⌘+Enter envoyer · vision = qwen3-vl pour pages graphiques
        </span>
      </div>

      {running && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-violet-500/8 border border-violet-500/20 text-violet-200 text-[12px]">
          <span className="inline-block w-2 h-2 rounded-full bg-violet-400 animate-pulse" />
          Lecture de la page + extraction Ollama (peut prendre jusqu a 90s sur grosses pages)…
        </div>
      )}

      {error && !running && (
        <div className="px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-[12px]">
          <strong>Erreur : </strong>{error}
        </div>
      )}

      {/* v82l9 — auto-suggest vision banner. Triggered when the last text-only
          extract looks weak (items empty, "image-based" notes, scrape <200c).
          Style is consistent with the rest of the drawer (rounded violet pill
          card, icon + text + 2 buttons), non-intrusive — it sits above the
          result body and disappears on click of either CTA. */}
      {suggestVision && result && !running && (
        <div className="px-3 py-2 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-100 text-[12px] flex items-center gap-3 flex-wrap">
          <Eye size={14} className="text-violet-300 shrink-0" />
          <span className="flex-1 min-w-[180px]">
            Cette page semble graphique — l extraction texte est faible. Reessayer avec vision ?
          </span>
          <button
            onClick={() => { onDismissVisionSuggestion(); onRunWithVision() }}
            className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-violet-500 text-white hover:bg-violet-600 transition-colors"
          >
            <Eye size={11} />
            Vision
          </button>
          <button
            onClick={onDismissVisionSuggestion}
            className="px-3 py-1 rounded-full text-[11px] bg-white/[0.04] text-white/60 border border-white/10 hover:bg-white/[0.08] transition-colors"
          >
            Ignorer
          </button>
        </div>
      )}

      {result && !running && (
        <div className="flex-1 flex flex-col gap-2 min-h-0">
          {/* Meta strip — model, item count, schema description */}
          <div className="flex items-center gap-3 flex-wrap text-[10px] text-white/55">
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-200 border border-emerald-500/30 font-mono">
              {result.items.length} item{result.items.length > 1 ? 's' : ''}
            </span>
            {result.model && (
              <span className="px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 font-mono">
                {result.model}
              </span>
            )}
            {result.inputLength > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 font-mono">
                {(result.inputLength / 1024).toFixed(1)} KB scrape
              </span>
            )}
            <button
              onClick={() => void copyJSON()}
              className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 hover:bg-white/[0.08] text-white/65 transition-colors"
              title="Copier items[] en JSON"
              disabled={result.items.length === 0}
            >
              <Copy size={10} />
              Copier JSON
            </button>
          </div>

          {result.schema && (
            <p className="text-[11px] text-white/65 italic">
              <strong className="not-italic text-white/80">Schema :</strong> {result.schema}
            </p>
          )}
          {result.notes && (
            <p className="text-[11px] text-amber-200/80">
              <strong className="text-amber-200">Notes :</strong> {result.notes}
            </p>
          )}

          {result.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center text-white/55">
              <TableIcon size={28} className="text-white/20 mb-3" />
              <p className="text-[12px]">Aucun item extrait. Reformule l intent ou regarde les notes ci-dessus.</p>
            </div>
          ) : (
            <div className="flex-1 overflow-auto rounded-xl border border-white/10 bg-black/20">
              <table className="w-full text-[11px] text-left">
                <thead className="sticky top-0 bg-[#0b111b]/95 backdrop-blur">
                  <tr>
                    {columns.map((c) => (
                      <th
                        key={c}
                        className="px-3 py-2 font-semibold text-violet-200 border-b border-white/10 whitespace-nowrap"
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((it, i) => (
                    <tr key={i} className="border-b border-white/5 hover:bg-white/[0.03]">
                      {columns.map((c) => (
                        <td
                          key={c}
                          className="px-3 py-1.5 text-white/85 align-top max-w-xs"
                          title={renderCell(it[c])}
                        >
                          <div className="line-clamp-3 break-words">{renderCell(it[c])}</div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!result && !running && !error && (
        <div className="flex flex-col items-center justify-center py-8 text-center text-white/55">
          <Sparkles size={28} className="text-violet-300/40 mb-3" />
          <p className="text-[12px] max-w-md">
            Decris en langage naturel ce que tu veux extraire. Aurora lit la page active,
            identifie le schema le plus pertinent et te rend un tableau.
          </p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function capabilityIcon(id: CoworkCapability['id']) {
  switch (id) {
    case 'filesystem': return HardDrive
    case 'shell': return Terminal
    case 'fetch': return Globe
    case 'clipboard': return Wifi
    case 'voice': return Mic
    case 'dom': return Globe
    case 'mobile-bridge': return Smartphone
    default: return ShieldCheck
  }
}

function labelForRuntime(rt: CoworkRuntime): string {
  switch (rt) {
    case 'tauri-desktop': return 'PC (Tauri · droits complets)'
    case 'web-desktop': return 'Navigateur desktop'
    case 'web-mobile': return 'Navigateur mobile (lecture seule)'
  }
}

function describeRuntime(rt: CoworkRuntime): string {
  switch (rt) {
    case 'tauri-desktop':
      return 'Application Tauri locale. Aurora peut lire et modifier les fichiers du workspace, lancer des commandes shell, et automatiser via les commandes Tauri declarees. Toute action destructive (write/edit/delete/shell hors allowlist) demande confirmation.'
    case 'web-desktop':
      return 'Navigateur desktop. Aurora peut faire des fetch, manipuler le DOM, lire/ecrire le presse-papiers (avec permission), mais ne peut pas toucher au filesystem local. Pour les actions systeme, utilise l app Tauri.'
    case 'web-mobile':
      return 'Navigateur mobile. Mode lecture/dictee uniquement. Toutes les actions destructives sont bloquees. Pour les actions systeme, installe l extension Aurora-Connect ou ouvre Aurora sur PC.'
  }
}

async function transcribeAudio(blob: Blob): Promise<string> {
  if (isTauriRuntime()) {
    try {
      const { runPythonScript, getWorkspacePath, fsWriteBinary } = await import('../hooks/useTauri')
      const wp = await getWorkspacePath()
      const tmpPath = `${wp}/output/cowork_input_${Date.now()}.webm`
      const buf = await blob.arrayBuffer()
      await fsWriteBinary(tmpPath, Array.from(new Uint8Array(buf)))
      const out = await runPythonScript(`${wp}/python-services/voice_service.py`, ['--mode', 'stt', '--input', tmpPath])
      const last = out.split('\n').filter((l) => l.trim()).pop() || ''
      try {
        const json = JSON.parse(last) as { ok?: boolean; text?: string }
        return json.text || ''
      } catch {
        return last
      }
    } catch {
      return ''
    }
  } else {
    try {
      const { getBridgeUrl } = await import('../utils/runtime')
      const form = new FormData()
      form.append('audio', blob, 'cowork.webm')
      const resp = await fetch(`${getBridgeUrl()}/api/voice/transcribe`, { method: 'POST', body: form, signal: AbortSignal.timeout(60_000) })
      if (resp.ok) {
        const data = await resp.json() as { ok?: boolean; text?: string }
        return data.text || ''
      }
    } catch { /* ignore */ }
    return ''
  }
}
