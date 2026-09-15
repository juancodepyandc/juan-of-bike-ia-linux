// ---------------------------------------------------------------------------
// AuroraCoworkView (v83) — the dedicated coworker workspace.
//
// This is THE cowork surface across desktop, web and tunnel. Runtime
// capabilities decide what the coworker can execute; the conversation,
// artifact cards and verification UI must remain visible everywhere.
//
// Why a new view : the old V1/V3 cowork "skins" were decorative HUDs (radar,
// static telemetry) that hid the real, fully-functional console behind a
// [CONSOLE] button — which made the coworker feel theatrical / theoretical.
// This view makes the real thing the default : a clean three-pane workspace
// built on the SAME proven pipeline (runCoworkPrompt) the console uses.
//
// Zero feature loss : the technical console is docked inside this same
// workspace, so logs and controls never hide the client conversation.
//
// The coworker is a real cooperator : it understands → asks a sharp question
// when (and only when) acting blind would build the wrong thing → executes
// real actions (filesystem, shell, web, remote SSH, cyber, LOCAL creation via
// the aurora_* connectors) → verifies → reports. Guardrails are PREVENTIVE,
// not restrictive (dangerMode default true : risky actions prompt, never hard-
// block ; the user stays in control).
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Activity,
  Boxes,
  Brain,
  ChevronRight,
  Clipboard,
  Code2,
  Cpu,
  Download,
  Eye,
  FileText,
  Globe,
  HardDrive,
  History,
  Image as ImageIcon,
  Maximize2,
  MessageSquarePlus,
  MessagesSquare,
  Mic,
  Minimize2,
  Monitor,
  Paperclip,
  Plus,
  Send,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Terminal,
  Trash2,
  Video,
  Volume2,
  VolumeX,
  Wrench,
  X,
} from 'lucide-react'
import CodeBlock from '../components/CodeBlock.tsx'
import {
  detectCoworkRuntime,
  getCoworkCapabilities,
  runCoworkPrompt,
} from '../services/coworkPipeline.ts'
import type { CoworkActionEvent, CoworkCapability, CoworkRuntime } from '../services/coworkTypes.ts'
import {
  artifactLabel,
  createEmptyCoworkProjectThread,
  loadCoworkProjectThread,
  normalizeCoworkProjectThread,
  previewUrlForCoworkArtifact,
  saveCoworkProjectThread,
  updateCoworkProjectThreadFromEvents,
  type CoworkProjectArtifact,
  type CoworkProjectThread,
} from '../services/coworkProjectThread.ts'
import { useCoworkStore } from '../stores/coworkStore.ts'
import { useAppStore } from '../stores/appStore.ts'
import { loadSettings, saveSettings, type CoworkSettings } from '../services/coworkSettings.ts'
import { CONNECTORS } from '../services/coworkConnectors.ts'
import CoworkConfirmDialog from '../components/CoworkConfirmDialog.tsx'

// Shared chat-history key so the current client thread keeps continuity.
const CHAT_STORAGE_KEY = 'cowork:chat-history'
const DISCUSSION_STORAGE_KEY = 'cowork:discussions-v1'
const VOICE_MODE_KEY = 'cowork:voice-mode'
const MAX_CHAT_TURNS = 100
const MAX_DISCUSSIONS = 24
const CONTENT_MAX = 1040

type ChatTurn = {
  id: string
  role: 'user' | 'aurora'
  content: string
  at: number
  pending?: boolean
  artifacts?: CoworkProjectArtifact[]
}

type CoworkDiscussion = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatTurn[]
  projectThread: CoworkProjectThread
}

// ---- palette (calm, dedicated — not a decorative HUD) ---------------------
const BG = '#0a0c12'
const PANEL = '#11141d'
const PANEL_2 = '#161a26'
const LINE = '#222838'
const TXT = '#e7e9f0'
const TXT_DIM = '#8b90a3'
const ACCENT = '#8b5cf6'
const ACCENT_2 = '#6366f1'
const OK = '#34d399'
const WARN = '#fbbf24'
const ERR = '#f87171'

// ---------------------------------------------------------------------------

function loadChatHistory(): ChatTurn[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? sanitizeChatTurns(parsed) : []
  } catch {
    return []
  }
}

function saveChatHistory(turns: ChatTurn[]): void {
  try {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(sanitizeChatTurns(turns)))
  } catch {
    /* quota — ignore */
  }
}

function sanitizeChatArtifact(artifact: CoworkProjectArtifact): CoworkProjectArtifact {
  const isCodeLike = artifact.kind === 'code' || artifact.kind === 'game'
  return {
    ...artifact,
    previewUrl: artifact.previewUrl && artifact.previewUrl.length < 120_000 ? artifact.previewUrl : undefined,
    summary: artifact.summary ? artifact.summary.slice(0, isCodeLike ? 40_000 : 600) : undefined,
    sourcePrompt: artifact.sourcePrompt ? artifact.sourcePrompt.slice(0, 600) : undefined,
  }
}

function normalizeChatTurn(input: unknown): ChatTurn | null {
  if (!input || typeof input !== 'object') return null
  const value = input as Partial<ChatTurn>
  if (value.role !== 'user' && value.role !== 'aurora') return null
  const content = typeof value.content === 'string' ? value.content : ''
  if (!content && !value.pending) return null
  return {
    id: typeof value.id === 'string' ? value.id : `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    role: value.role,
    content,
    at: typeof value.at === 'number' ? value.at : Date.now(),
    pending: Boolean(value.pending),
    artifacts: Array.isArray(value.artifacts)
      ? value.artifacts.slice(0, 6).map((artifact) => sanitizeChatArtifact(artifact as CoworkProjectArtifact))
      : undefined,
  }
}

function sanitizeChatTurns(turns: unknown[]): ChatTurn[] {
  return turns
    .map(normalizeChatTurn)
    .filter((turn): turn is ChatTurn => turn !== null && !turn.pending)
    .slice(-MAX_CHAT_TURNS)
}

function createDiscussionId(): string {
  return `discussion-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function makeDiscussionTitle(messages: ChatTurn[], thread: CoworkProjectThread): string {
  const fromUser = messages.find((message) => message.role === 'user' && message.content.trim())?.content
  const fromArtifact = thread.artifacts.slice().reverse().find((artifact) => artifact.label)?.label
  const raw = fromUser || thread.brief || fromArtifact || 'Nouvelle discussion'
  const title = raw.replace(/\s+/g, ' ').trim().slice(0, 72)
  return title || 'Nouvelle discussion'
}

function makeCoworkDiscussion(
  id: string,
  messages: ChatTurn[],
  projectThread: CoworkProjectThread,
  previous?: CoworkDiscussion,
): CoworkDiscussion {
  const cleanMessages = sanitizeChatTurns(messages)
  const cleanThread = normalizeCoworkProjectThread(projectThread)
  const now = Date.now()
  return {
    id,
    title: makeDiscussionTitle(cleanMessages, cleanThread),
    createdAt: previous?.createdAt || now,
    updatedAt: now,
    messages: cleanMessages,
    projectThread: cleanThread,
  }
}

function loadCoworkDiscussions(): CoworkDiscussion[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(DISCUSSION_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((entry): CoworkDiscussion | null => {
        if (!entry || typeof entry !== 'object') return null
        const value = entry as Partial<CoworkDiscussion>
        const projectThread = normalizeCoworkProjectThread(value.projectThread)
        const messages = Array.isArray(value.messages) ? sanitizeChatTurns(value.messages) : []
        return {
          id: typeof value.id === 'string' ? value.id : createDiscussionId(),
          title: typeof value.title === 'string' && value.title.trim()
            ? value.title.trim().slice(0, 72)
            : makeDiscussionTitle(messages, projectThread),
          createdAt: typeof value.createdAt === 'number' ? value.createdAt : Date.now(),
          updatedAt: typeof value.updatedAt === 'number' ? value.updatedAt : Date.now(),
          messages,
          projectThread,
        }
      })
      .filter((entry): entry is CoworkDiscussion => Boolean(entry))
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_DISCUSSIONS)
  } catch {
    return []
  }
}

function saveCoworkDiscussions(discussions: CoworkDiscussion[]): void {
  try {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(DISCUSSION_STORAGE_KEY, JSON.stringify(discussions.slice(0, MAX_DISCUSSIONS)))
  } catch {
    /* quota - keep the in-memory list */
  }
}

function buildConversationMarkdown(messages: ChatTurn[]): string {
  return sanitizeChatTurns(messages).map((m) => {
    const artifacts = m.artifacts?.length
      ? `\n\nArtefacts:\n${m.artifacts.map((a) => `- ${artifactLabel(a.kind)} v${a.version}: ${a.label}${a.path ? ` (${a.path})` : ''}`).join('\n')}`
      : ''
    return `## ${m.role === 'user' ? 'Client' : 'Aurora'}\n\n${m.content}${artifacts}\n`
  }).join('\n---\n\n')
}

// The orchestrator emits the final user-facing reply as a success event with
// actionKind='reply' and the text in `detail`. Fall back to the run summary.
function extractAuroraReply(events: CoworkActionEvent[]): string {
  const replies = events
    .filter((e) => e.kind === 'success' && e.actionKind === 'reply' && e.detail)
    .map((e) => e.detail!)
    .filter((d) => !looksLikeReplyJson(d))
  if (replies.length > 0) return replies.join('\n\n')
  const tail = events.slice().reverse().find((e) => /Termin|réussie|reussie/i.test(e.message || ''))
  if (tail) return tail.detail || tail.message
  return '_(Aurora a terminé sans message — ouvre la console technique pour voir le détail.)_'
}

function looksLikeReplyJson(detail: string): boolean {
  const t = detail.trim()
  if (!t.startsWith('{')) return false
  try {
    const p = JSON.parse(t) as { kind?: unknown; message?: unknown }
    return p?.kind === 'reply' && typeof p.message === 'string'
  } catch {
    return /^\{\s*"kind"\s*:\s*"reply"/.test(t)
  }
}

function eventColor(kind: CoworkActionEvent['kind']): string {
  if (kind === 'success') return OK
  if (kind === 'warn') return WARN
  if (kind === 'error') return ERR
  return TXT_DIM
}

// Safety posture derived from the three booleans. Preventive is the default
// and the recommended mode (warn + confirm risky, never hard-block).
type Posture = 'preventif' | 'confiance' | 'deverrouille'
function posture(s: CoworkSettings): Posture {
  if (s.fullyUnlocked) return 'deverrouille'
  if (s.trustMode) return 'confiance'
  return 'preventif'
}
function applyPosture(s: CoworkSettings, p: Posture): CoworkSettings {
  if (p === 'preventif') return { ...s, fullyUnlocked: false, trustMode: false, dangerMode: true }
  if (p === 'confiance') return { ...s, fullyUnlocked: false, trustMode: true, dangerMode: true }
  return { ...s, fullyUnlocked: true, trustMode: true, dangerMode: true }
}

// ---------------------------------------------------------------------------

export default function AuroraCoworkView({ open: openProp, onClose }: { open?: boolean; onClose?: () => void } = {}) {
  const isStoreOpen = useCoworkStore((s) => s.isOpen)
  const setAbortController = useCoworkStore((s) => s.setAbortController)
  const abortRun = useCoworkStore((s) => s.abortRun)
  const launchModule = useCoworkStore((s) => s.launchModule)
  const mainModel = useAppStore((s) => s.mainModel)

  const runtime: CoworkRuntime = useMemo(() => detectCoworkRuntime(), [])
  const capabilities: CoworkCapability[] = useMemo(() => getCoworkCapabilities(runtime), [runtime])

  const [messages, setMessages] = useState<ChatTurn[]>(() => loadChatHistory())
  const [projectThread, setProjectThread] = useState<CoworkProjectThread>(() => loadCoworkProjectThread())
  const [prompt, setPrompt] = useState('')
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<CoworkActionEvent[]>([])
  const [showConsole, setShowConsole] = useState(false)
  const [showDiscussions, setShowDiscussions] = useState(false)
  const [showActivity, setShowActivity] = useState(true)
  const [settings, setSettings] = useState<CoworkSettings>(() => loadSettings())
  const [voiceMode, setVoiceMode] = useState<boolean>(() => {
    try { return typeof localStorage !== 'undefined' && localStorage.getItem(VOICE_MODE_KEY) === '1' } catch { return false }
  })
  const [attachedTextFiles, setAttachedTextFiles] = useState<Array<{ id: string; name: string; content: string }>>([])
  const [discussions, setDiscussions] = useState<CoworkDiscussion[]>(() => {
    const stored = loadCoworkDiscussions()
    return stored.length > 0 ? stored : [makeCoworkDiscussion(createDiscussionId(), messages, projectThread)]
  })
  const [activeDiscussionId, setActiveDiscussionId] = useState<string>(() => discussions[0]?.id || createDiscussionId())

  const inputRef = useRef<HTMLTextAreaElement>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    saveChatHistory(messages)
    saveCoworkProjectThread(projectThread)
    setDiscussions((prev) => {
      const previous = prev.find((discussion) => discussion.id === activeDiscussionId)
      const hasContent = messages.some((message) => !message.pending && message.content.trim())
        || projectThread.artifacts.length > 0
        || projectThread.stages.length > 0
        || projectThread.notes.length > 0
      if (!hasContent && !previous) return prev
      const snapshot = makeCoworkDiscussion(activeDiscussionId, messages, projectThread, previous)
      const next = [snapshot, ...prev.filter((discussion) => discussion.id !== activeDiscussionId)].slice(0, MAX_DISCUSSIONS)
      saveCoworkDiscussions(next)
      return next
    })
  }, [messages, projectThread, activeDiscussionId])
  useEffect(() => {
    try { localStorage.setItem(VOICE_MODE_KEY, voiceMode ? '1' : '0') } catch { /* quota */ }
  }, [voiceMode])

  // Autoscroll the thread on new messages / events.
  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, events])

  useEffect(() => {
    if (openProp !== false) setTimeout(() => inputRef.current?.focus(), 80)
  }, [openProp])

  const enabledConnectors = useMemo(() => {
    let n = 0
    for (const id of Object.keys(CONNECTORS)) {
      const cfg = settings.connectors[id as keyof typeof settings.connectors]
      if (cfg?.enabled) n += 1
    }
    return n
  }, [settings])

  const handleClose = useCallback(() => {
    if (running) abortRun()
    onClose?.()
  }, [running, abortRun, onClose])

  // ESC closes when idle.
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !running && !useCoworkStore.getState().pendingConfirmation) handleClose()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [running, handleClose])

  const setPosture = (p: Posture) => {
    setSettings((prev) => {
      const next = applyPosture(prev, p)
      saveSettings(next)
      return next
    })
  }

  const openDiscussion = useCallback((discussion: CoworkDiscussion) => {
    const nextThread = normalizeCoworkProjectThread(discussion.projectThread)
    setActiveDiscussionId(discussion.id)
    setMessages(sanitizeChatTurns(discussion.messages))
    setProjectThread(nextThread)
    setEvents([])
    setPrompt('')
    saveChatHistory(discussion.messages)
    saveCoworkProjectThread(nextThread)
    setTimeout(() => inputRef.current?.focus(), 80)
  }, [])

  const startNewDiscussion = useCallback(() => {
    const id = createDiscussionId()
    const emptyThread = createEmptyCoworkProjectThread()
    const emptyDiscussion = makeCoworkDiscussion(id, [], emptyThread)
    setActiveDiscussionId(id)
    setMessages([])
    setProjectThread(emptyThread)
    setEvents([])
    setPrompt('')
    saveChatHistory([])
    saveCoworkProjectThread(emptyThread)
    setDiscussions((prev) => {
      const next = [emptyDiscussion, ...prev].slice(0, MAX_DISCUSSIONS)
      saveCoworkDiscussions(next)
      return next
    })
    setShowDiscussions(false)
    setTimeout(() => inputRef.current?.focus(), 80)
  }, [])

  const clearCurrentDiscussion = useCallback(() => {
    const emptyThread = createEmptyCoworkProjectThread()
    setMessages([])
    setProjectThread(emptyThread)
    setEvents([])
    saveChatHistory([])
    saveCoworkProjectThread(emptyThread)
    setDiscussions((prev) => {
      const previous = prev.find((discussion) => discussion.id === activeDiscussionId)
      const next = [
        makeCoworkDiscussion(activeDiscussionId, [], emptyThread, previous),
        ...prev.filter((discussion) => discussion.id !== activeDiscussionId),
      ].slice(0, MAX_DISCUSSIONS)
      saveCoworkDiscussions(next)
      return next
    })
  }, [activeDiscussionId])

  const deleteDiscussion = useCallback((id: string) => {
    const next = discussions.filter((discussion) => discussion.id !== id)
    if (next.length === 0) {
      const emptyThread = createEmptyCoworkProjectThread()
      const emptyDiscussion = makeCoworkDiscussion(createDiscussionId(), [], emptyThread)
      setActiveDiscussionId(emptyDiscussion.id)
      setMessages([])
      setProjectThread(emptyThread)
      setEvents([])
      setDiscussions([emptyDiscussion])
      saveChatHistory([])
      saveCoworkProjectThread(emptyThread)
      saveCoworkDiscussions([emptyDiscussion])
      return
    }
    setDiscussions(next)
    saveCoworkDiscussions(next)
    if (id === activeDiscussionId) openDiscussion(next[0])
  }, [activeDiscussionId, discussions, openDiscussion])

  const exportCurrentDiscussion = useCallback(() => {
    const md = buildConversationMarkdown(messages)
    navigator.clipboard?.writeText(md).catch(() => {})
    setMessages((p) => [...p, {
      id: `sys-${Date.now()}`,
      role: 'aurora',
      content: `Conversation copiée (${md.length} caractères).`,
      at: Date.now(),
    }])
  }, [messages])

  const handleSlash = (text: string): boolean => {
    const t = text.trim().toLowerCase()
    if (t === '/clear') { clearCurrentDiscussion(); return true }
    if (t === '/stop') { abortRun(); return true }
    if (t === '/console') { setShowConsole(true); setShowDiscussions(false); return true }
    if (t === '/export') { exportCurrentDiscussion(); return true }
    if (t === '/help' || t === '/?') {
      setMessages((p) => [...p, {
        id: `sys-${Date.now()}`, role: 'aurora', at: Date.now(),
        content: [
          '**Commandes rapides**',
          '- `/clear` — efface la conversation',
          '- `/stop` — stoppe le run en cours',
          '- `/console` — ouvre le dock technique sans quitter le fil',
          '- `/export` — copie la conversation et les livrables en markdown',
          '',
          '_Astuce : glisse un fichier texte/code dans le composer pour le donner en contexte._',
        ].join('\n'),
      }])
      return true
    }
    return false
  }

  const submit = useCallback(async (rawText?: string) => {
    const base = (rawText ?? prompt).trim()
    if (!base || running) return
    if (handleSlash(base)) { setPrompt(''); return }

    // Inject attached text files as fenced context.
    let composed = base
    if (attachedTextFiles.length > 0) {
      const blocks = attachedTextFiles
        .map((f) => `\n\n--- fichier joint : ${f.name} ---\n\`\`\`\n${f.content}\n\`\`\``)
        .join('')
      composed = `${base}${blocks}`
    }

    const userTurn: ChatTurn = { id: `u-${Date.now()}`, role: 'user', content: base, at: Date.now() }
    const pendingId = `a-${Date.now()}`
    setMessages((p) => [...p, userTurn, { id: pendingId, role: 'aurora', content: '', at: Date.now(), pending: true }])
    setPrompt('')
    setAttachedTextFiles([])
    setEvents([])
    setRunning(true)

    const controller = new AbortController()
    setAbortController(controller)
    const collected: CoworkActionEvent[] = []

    try {
      await runCoworkPrompt(
        composed,
        runtime,
        (ev) => {
          collected.push(ev)
          setEvents((prev) => [...prev, ev])
        },
        controller.signal,
        {
          module: launchModule,
          voiceMode,
          conversationHistory: messages
            .filter((m) => !m.pending && m.content)
            .slice(-8)
            .map((m) => ({ role: m.role, content: m.content })),
        },
      )
      const reply = extractAuroraReply(collected)
      const nextThread = updateCoworkProjectThreadFromEvents(projectThread, {
        userPrompt: base,
        assistantReply: reply,
        events: collected,
        attachedImageDescriptions: attachedTextFiles.map((f) => `${f.name}: ${f.content.slice(0, 220)}`),
      })
      saveCoworkProjectThread(nextThread)
      setProjectThread(nextThread)
      const newArtifacts = nextThread.artifacts
        .filter((artifact) => artifact.status === 'ready')
        .slice(-6)
        .map(sanitizeChatArtifact)
      setMessages((p) => p.map((m) => (m.id === pendingId
        ? { ...m, content: reply, pending: false, artifacts: newArtifacts.length > 0 ? newArtifacts : m.artifacts }
        : m)))
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      const aborted = controller.signal.aborted || /abort/i.test(msg)
      setMessages((p) => p.map((m) => (m.id === pendingId
        ? { ...m, content: aborted ? '_(Run interrompu.)_' : `⚠️ Erreur : ${msg}`, pending: false }
        : m)))
    } finally {
      setRunning(false)
      setAbortController(null)
    }
  }, [prompt, running, attachedTextFiles, runtime, launchModule, voiceMode, messages, projectThread, setAbortController])

  const onAttach = (files: FileList | null) => {
    if (!files) return
    for (const file of Array.from(files).slice(0, 3)) {
      const reader = new FileReader()
      reader.onload = () => {
        let content = String(reader.result || '')
        if (content.length > 100_000) content = content.slice(0, 100_000) + '\n…[tronqué]'
        setAttachedTextFiles((p) => [...p, { id: `f-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, name: file.name, content }].slice(0, 3))
      }
      reader.readAsText(file)
    }
  }

  if (openProp === false || (!isStoreOpen && openProp === undefined)) return null

  // Advanced console takeover (full feature set — zero feature loss).
  const cur = posture(settings)

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 95, background: BG, color: TXT,
      display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gridTemplateRows: '58px 1fr',
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <CoworkConfirmDialog />
      {showDiscussions && (
        <DiscussionDock
          discussions={discussions}
          activeDiscussionId={activeDiscussionId}
          onClose={() => setShowDiscussions(false)}
          onOpen={openDiscussion}
          onNew={startNewDiscussion}
          onDelete={deleteDiscussion}
          onClearCurrent={clearCurrentDiscussion}
          onExportCurrent={exportCurrentDiscussion}
        />
      )}
      {showConsole && (
        <TechnicalConsoleDock
          events={events}
          thread={projectThread}
          runtime={runtime}
          running={running}
          enabledConnectors={enabledConnectors}
          capabilities={capabilities}
          onClose={() => setShowConsole(false)}
        />
      )}

      {/* Header */}
      <header style={{
        gridColumn: '1 / -1', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 18px', borderBottom: `1px solid ${LINE}`, background: PANEL,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 9, display: 'grid', placeItems: 'center',
            background: `linear-gradient(135deg, ${ACCENT}, ${ACCENT_2})`,
          }}>
            <Sparkles size={17} color="#fff" />
          </div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontWeight: 700, fontSize: 14 }}>Aurora · Cowork</div>
            <div style={{ fontSize: 11, color: TXT_DIM }}>
              ton coopérateur — comprend · demande · exécute · vérifie
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <PostureChip cur={cur} onSet={setPosture} />
          <button onClick={() => setVoiceMode((v) => !v)} title="Lecture vocale des réponses (TTS)"
            style={iconBtn(voiceMode ? ACCENT : TXT_DIM)}>
            {voiceMode ? <Volume2 size={15} /> : <VolumeX size={15} />}
          </button>
          <button onClick={() => { setShowDiscussions(true); setShowConsole(false) }} title="Gerer les discussions et reprendre un fil projet"
            style={{ ...pillBtn(), borderColor: LINE, color: TXT }}>
            <MessagesSquare size={13} /> Discussions
          </button>
          <button onClick={() => { setShowConsole(true); setShowDiscussions(false) }} title="Console technique integree : journal, modules, etapes, verification"
            style={{ ...pillBtn(), borderColor: showConsole ? 'rgba(139,92,246,.55)' : LINE, color: showConsole ? '#ddd6fe' : TXT }}>
            <Terminal size={13} /> Console technique
          </button>
          {onClose && (
            <button onClick={handleClose} title="Fermer (Esc)" style={iconBtn(TXT_DIM)}>
              <X size={16} />
            </button>
          )}
        </div>
      </header>

      {/* Left rail — capabilities (kills the "theoretical" perception) */}
      <aside style={{ background: PANEL, borderRight: `1px solid ${LINE}`, padding: 16, overflowY: 'auto' }}>
        <RailTitle>Ce que je peux faire ici</RailTitle>
        <Capability icon={<HardDrive size={14} />} label="Fichiers & système" desc="lire, écrire, éditer, shell" on />
        <Capability icon={<Globe size={14} />} label="Web & recherche" desc="web_search, fetch, navigateur" on />
        <Capability icon={<Monitor size={14} />} label="Controle PC & UI" desc="captures, clics, tunnel, debug visuel" on />
        <Capability icon={<Server size={14} />} label="Connexion distante" desc="SSH : Pi, Linux, NAS, VPS" on />
        <Capability icon={<Shield size={14} />} label="Cyber (préventif)" desc="recon, audit, OSINT, exploit scoped" on />
        <Capability icon={<ImageIcon size={14} />} label="Créer une image" desc="aurora_image · FLUX local" on />
        <Capability icon={<Video size={14} />} label="Créer une vidéo" desc="aurora_video · Wan2.2" on />
        <Capability icon={<Boxes size={14} />} label="Créer un modèle 3D" desc="aurora_3d · Hunyuan3D" on />
        <Capability icon={<Cpu size={14} />} label="Générer du code" desc="aurora_code · qwen3-coder" on />
        <Capability icon={<Volume2 size={14} />} label="Voix" desc="aurora_voice · TTS Kokoro" on />

        <RailTitle style={{ marginTop: 18 }}>État</RailTitle>
        <div style={{ fontSize: 12, color: TXT_DIM, lineHeight: 1.9 }}>
          <div>Runtime : <b style={{ color: TXT }}>{runtime}</b></div>
          <div>Modèle : <b style={{ color: TXT }}>{mainModel}</b></div>
          <div>Connecteurs actifs : <b style={{ color: TXT }}>{enabledConnectors}</b> / {Object.keys(CONNECTORS).length}</div>
          <div>Capacités runtime : <b style={{ color: TXT }}>{capabilities.filter((c) => c.enabled).length}</b></div>
        </div>

        <div style={{
          marginTop: 18, padding: 11, borderRadius: 9, background: PANEL_2, border: `1px solid ${LINE}`,
          fontSize: 11.5, color: TXT_DIM, lineHeight: 1.6,
        }}>
          <b style={{ color: TXT }}>Garde-fous préventifs.</b> Les actions risquées (suppression,
          shell hors-liste, appel externe) sont annoncées et demandent ta confirmation — jamais bloquées
          d'office. Tu restes maître.
        </div>
      </aside>

      {/* Center — chat thread + composer */}
      <main style={{ display: 'flex', flexDirection: 'column', minHeight: 0, background: BG }}>
        {(projectThread.artifacts.some((artifact) => artifact.status === 'ready') || projectThread.stages.length > 0) && (
          <div style={{
            borderBottom: `1px solid ${LINE}`,
            background: 'rgba(10,12,18,.92)',
            padding: '12px 22px',
            boxShadow: '0 14px 40px rgba(0,0,0,.22)',
          }}>
            <div style={{ maxWidth: CONTENT_MAX, margin: '0 auto', display: 'grid', gap: 10 }}>
              <ProjectMemoryBand thread={projectThread} />
              <ProjectStageRail thread={projectThread} />
            </div>
          </div>
        )}
        <div ref={threadRef} style={{ flex: 1, overflowY: 'auto', padding: '22px 22px 8px', minHeight: 0 }}>
          {messages.length === 0 && <EmptyState onPick={(p) => submit(p)} />}
          <div style={{ maxWidth: CONTENT_MAX, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {messages.map((m) => (
              <Bubble key={m.id} turn={m} onNotion={(n) => submit(`Explique-moi la notion "${n}" dans le contexte de cette conversation.`)} />
            ))}
            {running && (
              <LiveActivity events={events} show={showActivity} onToggle={() => setShowActivity((s) => !s)} />
            )}
          </div>
        </div>

        {/* Composer */}
        <div style={{ borderTop: `1px solid ${LINE}`, background: PANEL, padding: '12px 22px 16px' }}>
          <div style={{ maxWidth: CONTENT_MAX, margin: '0 auto' }}>
            {attachedTextFiles.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                {attachedTextFiles.map((f) => (
                  <span key={f.id} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
                    background: PANEL_2, border: `1px solid ${LINE}`, borderRadius: 7, padding: '3px 8px', color: TXT_DIM,
                  }}>
                    <FileText size={12} /> {f.name}
                    <button onClick={() => setAttachedTextFiles((p) => p.filter((x) => x.id !== f.id))}
                      style={{ background: 'none', border: 'none', color: TXT_DIM, cursor: 'pointer', padding: 0, display: 'inline-flex' }}>
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: 8, background: PANEL_2,
              border: `1px solid ${LINE}`, borderRadius: 13, padding: 8,
            }}>
              <input ref={fileRef} type="file" multiple hidden
                accept=".txt,.md,.json,.csv,.log,.py,.ts,.tsx,.js,.jsx,.css,.html,.yml,.yaml,.toml,.ini,.sh,.rs,.go,.java,.c,.cpp,.sql"
                onChange={(e) => { onAttach(e.target.files); e.currentTarget.value = '' }} />
              <button onClick={() => fileRef.current?.click()} title="Joindre un fichier texte/code" style={iconBtn(TXT_DIM)}>
                <Paperclip size={17} />
              </button>
              <button onClick={() => { setShowConsole(true); setShowDiscussions(false) }} title="Ouvrir la console technique" style={iconBtn(TXT_DIM)}>
                <Mic size={17} />
              </button>
              <textarea
                ref={inputRef}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit() }
                }}
                placeholder="Demande n'importe quoi : analyser, créer (image/vidéo/3D/code), te connecter à distance, auditer…"
                rows={1}
                style={{
                  flex: 1, resize: 'none', maxHeight: 160, background: 'transparent', border: 'none',
                  outline: 'none', color: TXT, fontSize: 14, lineHeight: 1.5, fontFamily: 'inherit', padding: '6px 2px',
                }}
              />
              {running ? (
                <button onClick={abortRun} title="Stopper" style={{ ...sendBtn(), background: ERR }}>
                  <Square size={15} fill="#fff" />
                </button>
              ) : (
                <button onClick={() => void submit()} disabled={!prompt.trim()} title="Envoyer (Entrée)"
                  style={{ ...sendBtn(), opacity: prompt.trim() ? 1 : 0.4 }}>
                  <Send size={15} />
                </button>
              )}
            </div>
            <div style={{ fontSize: 10.5, color: TXT_DIM, marginTop: 6, textAlign: 'center' }}>
              Entrée pour envoyer · Maj+Entrée nouvelle ligne · <code>/help</code> pour les commandes
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PostureChip({ cur, onSet }: { cur: Posture; onSet: (p: Posture) => void }) {
  const [open, setOpen] = useState(false)
  const meta: Record<Posture, { label: string; icon: ReactNode; color: string }> = {
    preventif: { label: 'Préventif', icon: <ShieldCheck size={13} />, color: OK },
    confiance: { label: 'Confiance', icon: <Shield size={13} />, color: WARN },
    deverrouille: { label: 'Déverrouillé', icon: <ShieldAlert size={13} />, color: ERR },
  }
  const m = meta[cur]
  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen((o) => !o)} title="Niveau de garde-fous"
        style={{ ...pillBtn(), borderColor: m.color, color: m.color }}>
        {m.icon} {m.label}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 36, right: 0, zIndex: 10, background: PANEL_2,
          border: `1px solid ${LINE}`, borderRadius: 10, padding: 6, width: 250, boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
        }}>
          {(['preventif', 'confiance', 'deverrouille'] as Posture[]).map((p) => (
            <button key={p} onClick={() => { onSet(p); setOpen(false) }}
              style={{
                display: 'flex', gap: 9, alignItems: 'flex-start', width: '100%', textAlign: 'left',
                background: p === cur ? PANEL : 'transparent', border: 'none', borderRadius: 7,
                padding: '8px 9px', cursor: 'pointer', color: TXT,
              }}>
              <span style={{ color: meta[p].color, marginTop: 1 }}>{meta[p].icon}</span>
              <span style={{ lineHeight: 1.35 }}>
                <span style={{ fontSize: 12.5, fontWeight: 600 }}>{meta[p].label}</span>
                <span style={{ display: 'block', fontSize: 10.5, color: TXT_DIM }}>
                  {p === 'preventif' && 'Prévient + confirme les actions risquées (recommandé).'}
                  {p === 'confiance' && 'Auto-approuve les confirmations préventives, garde les blocages durs.'}
                  {p === 'deverrouille' && 'Zéro confirmation — tu assumes tous les risques.'}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function DiscussionDock({
  discussions,
  activeDiscussionId,
  onClose,
  onOpen,
  onNew,
  onDelete,
  onClearCurrent,
  onExportCurrent,
}: {
  discussions: CoworkDiscussion[]
  activeDiscussionId: string
  onClose: () => void
  onOpen: (discussion: CoworkDiscussion) => void
  onNew: () => void
  onDelete: (id: string) => void
  onClearCurrent: () => void
  onExportCurrent: () => void
}) {
  return (
    <aside style={dockShell()}>
      <div style={dockHeader()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={dockIcon()}><MessagesSquare size={16} /></span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 750 }}>Discussions client</div>
            <div style={{ color: TXT_DIM, fontSize: 11 }}>fil, historique, artefacts et contexte projet</div>
          </div>
        </div>
        <button onClick={onClose} title="Fermer" style={iconBtn(TXT_DIM)}><X size={16} /></button>
      </div>

      <div style={{ padding: 14, display: 'flex', gap: 8, borderBottom: `1px solid ${LINE}` }}>
        <button onClick={onNew} style={{ ...pillBtn(), color: TXT, background: 'rgba(139,92,246,.18)', borderColor: 'rgba(139,92,246,.38)' }}>
          <Plus size={13} /> Nouvelle
        </button>
        <button onClick={onExportCurrent} style={{ ...pillBtn(), color: TXT_DIM }}>
          <Clipboard size={13} /> Exporter
        </button>
        <button onClick={onClearCurrent} style={{ ...pillBtn(), color: WARN }}>
          <Trash2 size={13} /> Vider
        </button>
      </div>

      <div style={{ padding: 14, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {discussions.length === 0 ? (
          <div style={{ color: TXT_DIM, fontSize: 12 }}>Aucune discussion enregistrée.</div>
        ) : discussions.map((discussion) => {
          const active = discussion.id === activeDiscussionId
          const artifacts = discussion.projectThread.artifacts.filter((artifact) => artifact.status === 'ready').length
          const stages = discussion.projectThread.stages.length
          const turns = discussion.messages.filter((message) => message.role === 'user').length
          return (
            <button
              key={discussion.id}
              onClick={() => { onOpen(discussion); onClose() }}
              style={{
                textAlign: 'left',
                border: active ? '1px solid rgba(167,139,250,.65)' : `1px solid ${LINE}`,
                background: active ? 'rgba(139,92,246,.18)' : PANEL_2,
                color: TXT,
                borderRadius: 10,
                padding: 12,
                cursor: 'pointer',
                boxShadow: active ? '0 12px 34px rgba(91,33,182,.22)' : 'none',
              }}
            >
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{
                  width: 32,
                  height: 32,
                  borderRadius: 9,
                  display: 'grid',
                  placeItems: 'center',
                  color: active ? '#ede9fe' : TXT_DIM,
                  background: active ? 'rgba(139,92,246,.24)' : BG,
                  border: `1px solid ${active ? 'rgba(167,139,250,.35)' : LINE}`,
                  flexShrink: 0,
                }}>
                  <History size={14} />
                </span>
                <span style={{ minWidth: 0, flex: 1 }}>
                  <span style={{ display: 'block', fontSize: 12.5, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {discussion.title}
                  </span>
                  <span style={{ display: 'block', color: TXT_DIM, fontSize: 10.5, marginTop: 4 }}>
                    {turns} demande{turns > 1 ? 's' : ''} · {artifacts} livrable{artifacts > 1 ? 's' : ''} · {stages} étape{stages > 1 ? 's' : ''}
                  </span>
                  <span style={{ display: 'block', color: '#646b80', fontSize: 10.5, marginTop: 4 }}>{formatDateTime(discussion.updatedAt)}</span>
                </span>
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(event) => { event.stopPropagation(); onDelete(discussion.id) }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      event.stopPropagation()
                      onDelete(discussion.id)
                    }
                  }}
                  title="Supprimer cette discussion"
                  style={{ ...miniIconButton(), width: 28, height: 28, color: active ? WARN : TXT_DIM }}
                >
                  <Trash2 size={12} />
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </aside>
  )
}

function TechnicalConsoleDock({
  events,
  thread,
  runtime,
  running,
  enabledConnectors,
  capabilities,
  onClose,
}: {
  events: CoworkActionEvent[]
  thread: CoworkProjectThread
  runtime: CoworkRuntime
  running: boolean
  enabledConnectors: number
  capabilities: CoworkCapability[]
  onClose: () => void
}) {
  const recent = events.slice(-14).reverse()
  const stages = thread.stages.slice(-10).reverse()
  const copyLog = () => {
    const payload = events.map((event) => `[${event.kind}] ${event.actionKind || 'cowork'} - ${event.message}${event.detail ? `\n${event.detail}` : ''}`).join('\n\n')
    navigator.clipboard?.writeText(payload || 'Aucun evenement technique.').catch(() => {})
  }

  return (
    <aside style={dockShell()}>
      <div style={dockHeader()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={dockIcon()}><Terminal size={16} /></span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 750 }}>Console technique</div>
            <div style={{ color: TXT_DIM, fontSize: 11 }}>journal, modules, étapes et verification</div>
          </div>
        </div>
        <button onClick={onClose} title="Fermer" style={iconBtn(TXT_DIM)}><X size={16} /></button>
      </div>

      <div style={{ padding: 14, borderBottom: `1px solid ${LINE}`, display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 9 }}>
        <Metric label="Runtime" value={runtime} />
        <Metric label="Run" value={running ? 'en cours' : 'idle'} tone={running ? WARN : OK} />
        <Metric label="Connecteurs" value={`${enabledConnectors}`} />
        <Metric label="Capacités" value={`${capabilities.filter((capability) => capability.enabled).length}`} />
      </div>

      <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
        <section>
          <div style={dockSectionTitle()}>
            <Activity size={13} /> Evenements récents
            <button onClick={copyLog} style={{ ...miniModeBtn(false), marginLeft: 'auto' }}><Clipboard size={11} /> Copier</button>
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {recent.length === 0 ? (
              <div style={emptyDockState()}>Aucun run technique en cours.</div>
            ) : recent.map((event, index) => (
              <div key={`${event.message}-${index}`} style={{
                border: `1px solid ${LINE}`,
                background: PANEL_2,
                borderRadius: 9,
                padding: '8px 9px',
                fontSize: 11.5,
                color: TXT,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: eventColor(event.kind), boxShadow: `0 0 14px ${eventColor(event.kind)}66` }} />
                  <span style={{ color: eventColor(event.kind), textTransform: 'uppercase', fontSize: 9.5, letterSpacing: '.12em' }}>{event.kind}</span>
                  <span style={{ marginLeft: 'auto', color: TXT_DIM }}>{event.actionKind || 'cowork'}</span>
                </div>
                <div style={{ marginTop: 5, lineHeight: 1.45 }}>{event.message}</div>
                {event.detail && <div style={{ marginTop: 5, color: TXT_DIM, fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxHeight: 120, overflow: 'auto' }}>{event.detail}</div>}
              </div>
            ))}
          </div>
        </section>

        <section>
          <div style={dockSectionTitle()}><MessageSquarePlus size={13} /> Étapes projet mémorisées</div>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {stages.length === 0 ? (
              <div style={emptyDockState()}>Le prochain run créera ici les passes utiles : recherche, génération, verification, correction.</div>
            ) : stages.map((stage) => (
              <div key={stage.id} style={{ border: `1px solid ${LINE}`, background: PANEL_2, borderRadius: 9, padding: '8px 9px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: TXT, fontSize: 11.5, fontWeight: 650 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: stageStatusColor(stage.status) }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stage.label}</span>
                  <span style={{ marginLeft: 'auto', color: TXT_DIM, fontSize: 10.5 }}>{formatStageDuration(stage.durationMs)}</span>
                </div>
                {stage.detail && <div style={{ marginTop: 5, color: TXT_DIM, fontSize: 10.5, lineHeight: 1.4 }}>{stage.detail}</div>}
              </div>
            ))}
          </div>
        </section>
      </div>
    </aside>
  )
}

function Metric({ label, value, tone = TXT }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ border: `1px solid ${LINE}`, background: PANEL_2, borderRadius: 9, padding: '9px 10px' }}>
      <div style={{ color: TXT_DIM, fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em' }}>{label}</div>
      <div style={{ marginTop: 4, color: tone, fontSize: 13, fontWeight: 750, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</div>
    </div>
  )
}

function RailTitle({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      fontSize: 10.5, letterSpacing: '0.08em', textTransform: 'uppercase',
      color: TXT_DIM, marginBottom: 9, fontWeight: 600, ...style,
    }}>{children}</div>
  )
}

function Capability({ icon, label, desc, on }: { icon: ReactNode; label: string; desc: string; on?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '6px 0' }}>
      <span style={{ color: on ? ACCENT : TXT_DIM, marginTop: 1 }}>{icon}</span>
      <span style={{ lineHeight: 1.3 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600 }}>{label}</span>
        <span style={{ display: 'block', fontSize: 10.5, color: TXT_DIM }}>{desc}</span>
      </span>
    </div>
  )
}

function Bubble({ turn, onNotion }: { turn: ChatTurn; onNotion: (n: string) => void }) {
  const isUser = turn.role === 'user'
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{ maxWidth: isUser ? '78%' : '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{
          background: isUser ? `linear-gradient(135deg, ${ACCENT}, ${ACCENT_2})` : PANEL,
          color: isUser ? '#fff' : TXT,
          border: isUser ? 'none' : `1px solid ${LINE}`,
          borderRadius: 13, padding: isUser ? '10px 14px' : '12px 16px',
          fontSize: 13.5, lineHeight: 1.55,
        }}>
          {turn.pending && !turn.content ? (
            <span style={{ color: TXT_DIM }}><Thinking /></span>
          ) : isUser ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{turn.content}</span>
          ) : (
            <div className="cowork-md" onClick={(e) => {
              const a = (e.target as HTMLElement).closest('a')
              if (a && a.getAttribute('href')?.startsWith('cowork://')) {
                e.preventDefault()
                const n = decodeURIComponent(a.getAttribute('href')!.replace('cowork://explain/', ''))
                onNotion(n)
              }
            }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {turn.content.replace(/\[\[([^[\]\n]{2,80})\]\]/g, (_m, l: string) => `[${l.trim()}](cowork://explain/${encodeURIComponent(l.trim())})`)}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {!isUser && turn.artifacts && turn.artifacts.length > 0 && (
          <ArtifactCards artifacts={turn.artifacts} />
        )}
      </div>
    </div>
  )
}

function ProjectMemoryBand({ thread }: { thread: CoworkProjectThread }) {
  const artifacts = thread.artifacts.filter((artifact) => artifact.status === 'ready')
  if (artifacts.length === 0) return null
  const active = thread.activeArtifactId
    ? artifacts.find((artifact) => artifact.id === thread.activeArtifactId)
    : artifacts[artifacts.length - 1]
  return (
    <div style={{
      border: '1px solid rgba(139,92,246,.26)',
      background: 'rgba(139,92,246,.08)',
      borderRadius: 12,
      padding: '10px 12px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: '#c4b5fd' }}>Projet actif</div>
        <div style={{ marginTop: 2, fontSize: 12.5, color: TXT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {active ? `${artifactLabel(active.kind)} v${active.version} - ${active.label.replace(/^.*? - /, '')}` : thread.brief || 'Artefacts charges'}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', maxWidth: '52%' }}>
        {artifacts.slice(-5).reverse().map((artifact) => (
          <span key={artifact.id} title={artifact.path || artifact.url || artifact.label} style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            border: artifact.id === active?.id ? '1px solid rgba(167,139,250,.75)' : `1px solid ${LINE}`,
            background: artifact.id === active?.id ? 'rgba(139,92,246,.22)' : PANEL_2,
            color: artifact.id === active?.id ? '#ede9fe' : TXT_DIM,
            borderRadius: 8,
            padding: '5px 7px',
            whiteSpace: 'nowrap',
            fontSize: 10.5,
          }}>
            {artifact.kind === 'image' ? 'IMG' : artifact.kind === 'model3d' ? '3D' : artifact.kind === 'game' ? 'GAME' : artifact.kind === 'code' ? 'CODE' : artifact.kind.toUpperCase()}
            <span>v{artifact.version}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function ProjectStageRail({ thread }: { thread: CoworkProjectThread }) {
  const stages = thread.stages.slice(-7)
  if (stages.length === 0) return null
  return (
    <div style={{
      border: `1px solid ${LINE}`,
      background: PANEL,
      borderRadius: 12,
      padding: '10px 12px',
      overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 9 }}>
        <div style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: '#c4b5fd' }}>Etapes projet</div>
        <div style={{ color: TXT_DIM, fontSize: 10.5 }}>{stages.length} passe{stages.length > 1 ? 's' : ''}</div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))', gap: 7 }}>
        {stages.map((stage) => (
          <div key={stage.id} title={stage.detail || stage.label} style={{
            minHeight: 62,
            border: `1px solid ${LINE}`,
            borderRadius: 9,
            background: PANEL_2,
            padding: '8px 9px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: 7,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                width: 7,
                height: 7,
                borderRadius: 999,
                background: stageStatusColor(stage.status),
                boxShadow: `0 0 14px ${stageStatusColor(stage.status)}66`,
                flexShrink: 0,
              }} />
              <span style={{ color: TXT, fontSize: 11.5, fontWeight: 650, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {stage.label}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, fontSize: 10.5, color: TXT_DIM }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stage.module || stage.actionKind || 'cowork'}</span>
              <span>{formatStageDuration(stage.durationMs)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function ArtifactCards({ artifacts }: { artifacts: CoworkProjectArtifact[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 12 }}>
      {artifacts.slice(0, 6).map((artifact) => (
        <div
          key={artifact.id}
          style={{ gridColumn: artifact.kind === 'image' || artifact.kind === 'video' || artifact.kind === 'game' ? '1 / -1' : undefined }}
        >
          <ArtifactCard artifact={artifact} />
        </div>
      ))}
    </div>
  )
}

function ArtifactCard({ artifact }: { artifact: CoworkProjectArtifact }) {
  const href = previewUrlForCoworkArtifact(artifact)
  const { code, language } = useMemo(() => extractArtifactCode(artifact), [artifact])
  const hasCode = Boolean(code)
  const hasPreview = Boolean(href) || Boolean(artifact.summary)
  const hasEmulator = hasCode || Boolean(href)
  const [mode, setMode] = useState<'preview' | 'code' | 'emulator'>(() => {
    if (artifact.kind === 'game' && hasEmulator) return 'emulator'
    if (artifact.kind === 'image' || artifact.kind === 'video') return 'preview'
    return hasCode ? 'code' : 'preview'
  })
  const [fullscreen, setFullscreen] = useState(false)
  const downloadHref = buildArtifactDownloadHref(artifact, code, href)
  const downloadName = buildArtifactDownloadName(artifact, language)
  const canFrameHref = href
    && !/^data:/i.test(href)
    && (artifact.kind === 'game' || /\.(html?|svg)(?:[?#].*)?$/i.test(href))
  const shell: CSSProperties = fullscreen
    ? {
        position: 'fixed', inset: 16, zIndex: 130, display: 'flex', flexDirection: 'column',
        overflow: 'hidden', borderRadius: 16, border: '1px solid rgba(196,181,253,.36)',
        background: 'rgba(8,7,19,.98)', boxShadow: '0 24px 80px rgba(0,0,0,.75)',
      }
    : {
        overflow: 'hidden',
        borderRadius: 12,
        border: '1px solid rgba(167,139,250,.18)',
        background: 'linear-gradient(180deg, rgba(139,92,246,.08), rgba(17,20,29,.98) 34%)',
        boxShadow: '0 18px 50px rgba(0,0,0,.22)',
      }

  useEffect(() => {
    if (mode === 'code' && !hasCode) setMode('preview')
    if (mode === 'emulator' && !hasEmulator) setMode('preview')
  }, [hasCode, hasEmulator, mode])

  return (
    <div style={shell} title={artifact.path || artifact.url || artifact.summary || artifact.label}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        borderBottom: `1px solid ${LINE}`, padding: '10px 12px',
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: '#c4b5fd' }}>
              {artifactLabel(artifact.kind)} v{artifact.version}
            </span>
            {artifact.active && <span style={{ fontSize: 9.5, color: OK, background: 'rgba(52,211,153,.12)', borderRadius: 999, padding: '1px 6px' }}>actif</span>}
          </div>
          <div style={{ marginTop: 3, fontSize: 13, fontWeight: 700, color: TXT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{artifact.label}</div>
          {(artifact.connector || artifact.parentIds?.length || artifact.sourceAction) && (
            <div style={{ marginTop: 3, color: TXT_DIM, fontSize: 10.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {[artifact.connector || artifact.sourceAction, artifact.parentIds?.length ? `${artifact.parentIds.length} source${artifact.parentIds.length > 1 ? 's' : ''}` : ''].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          {(hasPreview || hasCode || hasEmulator) && (
            <div style={{ display: 'inline-flex', gap: 2, border: `1px solid ${LINE}`, background: BG, borderRadius: 8, padding: 2 }}>
              {hasPreview && (
                <button onClick={() => setMode('preview')} title="Voir l aperçu" style={miniModeBtn(mode === 'preview')}>
                  <Eye size={11} /> Aperçu
                </button>
              )}
              {hasCode && (
                <button onClick={() => setMode('code')} title="Voir le code colore" style={miniModeBtn(mode === 'code')}>
                  <Code2 size={11} /> Code
                </button>
              )}
              {hasEmulator && (
                <button onClick={() => setMode('emulator')} title="Voir dans l emulateur sandbox" style={miniModeBtn(mode === 'emulator')}>
                  <Monitor size={11} /> Emulateur
                </button>
              )}
            </div>
          )}
          {downloadHref && (
            <a href={downloadHref} download={downloadName} title={`Telecharger ${downloadName}`} style={miniIconLink()}>
              <Download size={13} />
            </a>
          )}
          {href && (
            <a href={href} target="_blank" rel="noopener noreferrer" title="Ouvrir l artefact" style={miniIconLink()}>
              <Eye size={13} />
            </a>
          )}
          <button onClick={() => setFullscreen((v) => !v)} title={fullscreen ? 'Quitter le plein ecran' : 'Plein ecran'} style={miniIconButton()}>
            {fullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>
      <div style={fullscreen ? { minHeight: 0, flex: 1, overflow: 'hidden' } : undefined}>
        {mode === 'code' && hasCode ? (
          <div style={{ maxHeight: fullscreen ? '100%' : 440, height: fullscreen ? '100%' : undefined, overflow: 'auto', background: '#090b12', fontFamily: 'monospace', fontSize: 12.5 }}>
            <CodeBlock code={code} language={language} showLineNumbers />
          </div>
        ) : mode === 'emulator' && hasEmulator ? (
          <iframe
            title={`${artifact.label} - emulateur`}
            src={canFrameHref ? href : undefined}
            srcDoc={canFrameHref ? undefined : buildArtifactEmulatorSrcDoc(artifact, code, language, href)}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            style={{ width: '100%', height: fullscreen ? '100%' : 420, border: 0, background: '#070812' }}
          />
        ) : artifact.kind === 'video' && href ? (
          <video src={href} controls style={{ width: '100%', height: fullscreen ? '100%' : 390, objectFit: 'contain', background: '#05060c' }} />
        ) : artifact.kind === 'image' && href ? (
          <div style={{ background: '#05060c', padding: fullscreen ? 0 : 10 }}>
            <img src={href} alt={artifact.label} style={{ width: '100%', height: fullscreen ? '100%' : 390, objectFit: 'contain', display: 'block' }} />
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', minHeight: 142, padding: 14, background: 'rgba(5,6,12,.45)' }}>
            <div style={{ width: 56, height: 56, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: 14, border: `1px solid ${LINE}`, color: '#ddd6fe', fontSize: 11, fontWeight: 800, background: PANEL_2 }}>
              {artifact.kind === 'model3d' ? '3D' : artifact.kind === 'game' ? 'GAME' : artifact.kind === 'code' ? 'CODE' : 'FILE'}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: TXT, fontSize: 12.5, fontWeight: 650 }}>{artifactLabel(artifact.kind)} prêt</div>
              <div style={{ color: TXT_DIM, fontSize: 12, marginTop: 5, lineHeight: 1.45 }}>{artifact.summary ? artifact.summary.slice(0, 260) : 'Artefact disponible dans le fil Cowork.'}</div>
              {(artifact.path || artifact.url) && <div style={{ marginTop: 8, color: '#646b80', fontSize: 10.5, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{artifact.path || artifact.url}</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Thinking() {
  return (
    <span style={{ display: 'inline-flex', gap: 9, alignItems: 'center' }}>
      <Brain size={14} />
      <span>Aurora orchestre les modules</span>
      <style>{`@keyframes cwk-flow{0%{transform:translateX(-100%)}100%{transform:translateX(220%)}}`}</style>
      <span style={{ width: 86, height: 5, borderRadius: 999, overflow: 'hidden', background: 'rgba(139,92,246,.18)', display: 'inline-block' }}>
        <span style={{ display: 'block', width: 34, height: '100%', borderRadius: 999, background: 'linear-gradient(90deg, transparent, #c4b5fd, transparent)', animation: 'cwk-flow 1.2s linear infinite' }} />
      </span>
    </span>
  )
}

function LiveActivity({ events, show, onToggle }: { events: CoworkActionEvent[]; show: boolean; onToggle: () => void }) {
  const recent = events.slice(-6)
  return (
    <div style={{ background: PANEL, border: `1px solid ${LINE}`, borderRadius: 11, padding: 10 }}>
      <button onClick={onToggle} style={{
        display: 'flex', alignItems: 'center', gap: 7, background: 'none', border: 'none',
        color: TXT_DIM, cursor: 'pointer', fontSize: 11.5, fontWeight: 600, padding: 0, width: '100%',
      }}>
        <Wrench size={13} />
        Activité {running_count(events)}
        <ChevronRight size={13} style={{ marginLeft: 'auto', transform: show ? 'rotate(90deg)' : 'none', transition: 'transform .15s' }} />
      </button>
      {show && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11.5, fontFamily: 'monospace' }}>
          {recent.map((e, i) => (
            <div key={i} style={{ color: eventColor(e.kind), display: 'flex', gap: 6 }}>
              <span style={{ opacity: 0.6 }}>›</span>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function running_count(events: CoworkActionEvent[]): string {
  const ok = events.filter((e) => e.kind === 'success').length
  return ok > 0 ? `· ${ok} étape(s) OK` : ''
}

function stageStatusColor(status: CoworkProjectThread['stages'][number]['status']): string {
  if (status === 'ok') return OK
  if (status === 'warn' || status === 'running') return WARN
  return ERR
}

function formatStageDuration(durationMs?: number): string {
  if (!durationMs || durationMs < 0) return 'en cours'
  if (durationMs < 1000) return `${durationMs} ms`
  if (durationMs < 60_000) return `${(durationMs / 1000).toFixed(durationMs < 10_000 ? 1 : 0)} s`
  const minutes = Math.floor(durationMs / 60_000)
  const seconds = Math.round((durationMs % 60_000) / 1000)
  return `${minutes} min ${seconds}s`
}

function EmptyState({ onPick }: { onPick: (p: string) => void }) {
  const ideas = [
    { icon: <ImageIcon size={15} />, t: 'Crée une image', p: 'Crée une image : un renard origami géométrique sur fond bleu nuit.' },
    { icon: <Boxes size={15} />, t: 'Génère un modèle 3D', p: 'Génère un modèle 3D d\'un petit robot mignon style Pixar.' },
    { icon: <Server size={15} />, t: 'Connecte-toi à distance', p: 'Connecte-toi à mon Raspberry Pi et fais-moi un état de santé (uptime, disque, services).' },
    { icon: <Shield size={15} />, t: 'Audit cyber (mon périmètre)', p: 'Audit défensif de ma machine locale : ports ouverts, services, mises à jour.' },
    { icon: <HardDrive size={15} />, t: 'Analyse mon bureau', p: 'Fais-moi une fiche récapitulative de mon bureau informatique (matériel, OS, apps actives).' },
    { icon: <Cpu size={15} />, t: 'Génère du code', p: 'Génère un script Python qui sauvegarde mes photos par date dans des dossiers.' },
  ]
  return (
    <div style={{ maxWidth: 720, margin: '6vh auto 0', textAlign: 'center' }}>
      <div style={{
        width: 54, height: 54, borderRadius: 16, margin: '0 auto 16px', display: 'grid', placeItems: 'center',
        background: `linear-gradient(135deg, ${ACCENT}, ${ACCENT_2})`,
      }}>
        <Sparkles size={28} color="#fff" />
      </div>
      <h2 style={{ margin: '0 0 6px', fontSize: 21, fontWeight: 700 }}>Ton coopérateur Aurora</h2>
      <p style={{ margin: '0 0 22px', color: TXT_DIM, fontSize: 13.5, lineHeight: 1.6 }}>
        Décris une tâche — même complexe. Je comprends, je te pose une question si c'est vraiment ambigu,
        puis j'exécute pour de vrai (fichiers, web, distant, cyber, création image/vidéo/3D/code) et je vérifie.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, textAlign: 'left' }}>
        {ideas.map((it) => (
          <button key={it.t} onClick={() => onPick(it.p)} style={{
            display: 'flex', alignItems: 'center', gap: 11, background: PANEL, border: `1px solid ${LINE}`,
            borderRadius: 11, padding: '13px 14px', cursor: 'pointer', color: TXT, textAlign: 'left',
          }}>
            <span style={{ color: ACCENT }}>{it.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 600 }}>{it.t}</span>
            <ChevronRight size={14} style={{ marginLeft: 'auto', color: TXT_DIM }} />
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// inline style helpers
// ---------------------------------------------------------------------------

function dockShell(): CSSProperties {
  return {
    position: 'fixed',
    top: 0,
    right: 0,
    bottom: 0,
    zIndex: 125,
    width: 430,
    maxWidth: 'calc(100vw - 24px)',
    display: 'flex',
    flexDirection: 'column',
    background: 'rgba(14,17,27,.98)',
    borderLeft: '1px solid rgba(167,139,250,.26)',
    boxShadow: '0 24px 80px rgba(0,0,0,.55)',
    backdropFilter: 'blur(18px)',
  }
}

function dockHeader(): CSSProperties {
  return {
    minHeight: 58,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    padding: '0 14px',
    borderBottom: `1px solid ${LINE}`,
    background: 'linear-gradient(180deg, rgba(139,92,246,.12), rgba(17,20,29,.92))',
  }
}

function dockIcon(): CSSProperties {
  return {
    width: 34,
    height: 34,
    borderRadius: 10,
    display: 'grid',
    placeItems: 'center',
    color: '#ede9fe',
    border: '1px solid rgba(167,139,250,.35)',
    background: 'rgba(139,92,246,.2)',
    flexShrink: 0,
  }
}

function dockSectionTitle(): CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    color: '#c4b5fd',
    fontSize: 10.5,
    fontWeight: 750,
    letterSpacing: '.12em',
    textTransform: 'uppercase',
  }
}

function emptyDockState(): CSSProperties {
  return {
    minHeight: 74,
    display: 'grid',
    placeItems: 'center',
    textAlign: 'center',
    border: `1px dashed ${LINE}`,
    borderRadius: 10,
    color: TXT_DIM,
    fontSize: 11.5,
    lineHeight: 1.45,
    padding: 12,
  }
}

function formatDateTime(value: number): string {
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return ''
  }
}

function iconBtn(color: string): CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32,
    background: 'transparent', border: 'none', borderRadius: 8, color, cursor: 'pointer',
  }
}
function pillBtn(): CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600,
    background: 'transparent', border: `1px solid ${LINE}`, borderRadius: 8, padding: '6px 11px', cursor: 'pointer',
  }
}
function sendBtn(): CSSProperties {
  return {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36,
    background: `linear-gradient(135deg, ${ACCENT}, ${ACCENT_2})`, color: '#fff', border: 'none',
    borderRadius: 10, cursor: 'pointer', flexShrink: 0,
  }
}

function miniModeBtn(active: boolean): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    border: 'none',
    borderRadius: 6,
    padding: '4px 7px',
    background: active ? 'rgba(139,92,246,.36)' : 'transparent',
    color: active ? TXT : TXT_DIM,
    cursor: 'pointer',
    fontSize: 10.5,
  }
}

function miniIconButton(): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 29,
    height: 29,
    borderRadius: 8,
    border: `1px solid ${LINE}`,
    background: PANEL_2,
    color: TXT_DIM,
    cursor: 'pointer',
  }
}

function miniIconLink(): CSSProperties {
  return {
    ...miniIconButton(),
    textDecoration: 'none',
  }
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
  if (code && /<!doctype html|<html[\s>]/i.test(code)) return injectEmulatorPrelude(code)
  if (code && (language === 'markup' || language === 'html')) {
    const html = code.includes('<body')
      ? code
      : `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title></head><body>${code}</body></html>`
    return injectEmulatorPrelude(html)
  }
  if (code && language === 'javascript') {
    return `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title><style>${emulatorCss()}</style><script>${emulatorSandboxPrelude()}<\/script></head><body><main><h1>${safeTitle}</h1><p>Sandbox JavaScript avec console capturee.</p><pre id="out"></pre></main><script>const out=document.getElementById('out');const print=(...a)=>{out.textContent+=a.map(x=>typeof x==='object'?JSON.stringify(x,null,2):String(x)).join(' ')+'\\n'};console.log=print;console.error=(...a)=>print('ERROR:',...a);try{${code.replace(/<\/script/gi, '<\\/script')}}catch(e){print('ERROR:',e&&e.stack||e)}<\/script></body></html>`
  }
  return `<!doctype html><html><head><meta charset="utf-8"><title>${safeTitle}</title><style>${emulatorCss()}</style><script>${emulatorSandboxPrelude()}<\/script></head><body><main><h1>${safeTitle}</h1><p>${href ? `Artefact lie: <a href="${escapeHtml(href)}" target="_blank">${escapeHtml(href)}</a>` : 'Emulation directe indisponible pour ce type, affichage technique ci-dessous.'}</p><pre>${escapeHtml(code || artifact.summary || artifact.path || artifact.url || 'Aucun contenu brut expose.')}</pre></main></body></html>`
}

function injectEmulatorPrelude(html: string): string {
  const prelude = `<script>${emulatorSandboxPrelude()}<\/script>`
  if (/<head[\s>]/i.test(html)) return html.replace(/<head([^>]*)>/i, `<head$1>${prelude}`)
  if (/<html[\s>]/i.test(html)) return html.replace(/<html([^>]*)>/i, `<html$1>${prelude}`)
  return `${prelude}${html}`
}

function emulatorSandboxPrelude(): string {
  return `(()=>{try{const make=()=>{const m=new Map();return{get length(){return m.size},key:i=>Array.from(m.keys())[i]??null,getItem:k=>m.has(String(k))?m.get(String(k)):null,setItem:(k,v)=>{m.set(String(k),String(v))},removeItem:k=>{m.delete(String(k))},clear:()=>{m.clear()}}};Object.defineProperty(window,'localStorage',{configurable:true,value:make()});Object.defineProperty(window,'sessionStorage',{configurable:true,value:make()});}catch(e){}})();`
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
