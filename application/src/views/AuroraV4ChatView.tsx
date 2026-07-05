import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent,
  type KeyboardEvent as RKeyboardEvent,
  type ReactNode,
} from 'react'
import MarkdownPro from '../components/MarkdownPro'
import AuroraMascot from '../components/generationFx/mascots'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { useChatViewLogic, stripThink, WELCOME, type Attachment } from '../hooks/useChatViewLogic'
import { useChatStore } from '../stores/chatStore'
import { useFileDrop } from '../hooks/useFileDrop'
import { useNotificationStore } from '../stores/notificationStore'
import { suggestCommands, getRecentSlash } from '../utils/slashCommands'
import { pickRandomStarter } from '../utils/randomChatStarters'
import { getDailyTip } from '../utils/dailyTip'
import { getContextUsage } from '../utils/modelContext'
import type { ChatMessage } from '../types/app'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

const ACCENT = '#8B5CF6'
const MONO = "'Cascadia Code',Consolas,monospace"

const GLASS: CSSProperties = {
  background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
  border: '1px solid rgba(255,255,255,.09)',
  borderRadius: 18,
  backdropFilter: 'blur(18px)',
}

const LABEL: CSSProperties = {
  fontFamily: MONO,
  fontSize: 10,
  letterSpacing: '.2em',
  textTransform: 'uppercase',
  color: '#8B93A7',
}

const ICONS: Record<string, string> = {
  send: 'M22 2 11 13|M22 2 15 22 11 13 2 9z',
  stop: 'M7 7h10v10H7z',
  clip: 'M21.4 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48',
  globe: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z|M2 12h20|M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
  trash: 'M3 6h18|M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2|M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6|M10 11v6|M14 11v6',
  copy: 'M9 9h11v11H9z|M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1',
  check: 'M20 6 9 17l-5-5',
  regen: 'M23 4v6h-6|M1 20v-6h6|M3.5 9a9 9 0 0 1 14.9-3.4L23 10|M1 14l4.6 4.4A9 9 0 0 0 20.5 15',
  pin: 'M12 17v5|M9 3h6l-1 7 3 2v2H7v-2l3-2z',
  edit: 'M17 3a2.83 2.83 0 0 1 4 4L7.5 20.5 3 21l.5-4.5z',
  x: 'M18 6 6 18|M6 6l12 12',
  file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z|M14 2v6h6',
  vol: 'M11 5 6 9H2v6h4l5 4z|M15.5 8.5a5 5 0 0 1 0 7|M19 5a10 10 0 0 1 0 14',
  volx: 'M11 5 6 9H2v6h4l5 4z|M23 9l-6 6|M17 9l6 6',
  down: 'M12 5v14|M19 12l-7 7-7-7',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z|M21 21l-4.3-4.3',
  radio: 'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z|M7.8 7.8a6 6 0 0 0 0 8.4|M16.2 7.8a6 6 0 0 1 0 8.4|M4.9 4.9a10 10 0 0 0 0 14.2|M19.1 4.9a10 10 0 0 1 0 14.2',
  spark: 'M12 3v4|M12 17v4|M3 12h4|M17 12h4|M5.6 5.6l2.8 2.8|M15.6 15.6l2.8 2.8|M18.4 5.6l-2.8 2.8|M8.4 15.6l-2.8 2.8',
  slash: 'M16 4 8 20',
  user: 'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z|M4 21a8 8 0 0 1 16 0',
}

function Ic({ name, size = 13 }: { name: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      style={{ flexShrink: 0 }}
      stroke="currentColor"
      fill="none"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONS[name].split('|').map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  )
}

function Chip({ children, active, tone, title }: {
  children: ReactNode
  active?: boolean
  tone?: string
  title?: string
}) {
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        padding: '5px 11px',
        borderRadius: 999,
        fontFamily: MONO,
        border: `1px solid ${active ? ACCENT : tone ? `${tone}66` : 'rgba(255,255,255,.1)'}`,
        background: active ? ACCENT : tone ? `${tone}14` : 'rgba(255,255,255,.03)',
        color: active ? '#0A0F1E' : tone ?? '#8B93A7',
        fontWeight: active ? 700 : 500,
        whiteSpace: 'nowrap',
        transition: 'all .25s',
      }}
    >
      {children}
    </span>
  )
}

function GhostBtn({ onClick, title, disabled, active, danger, children }: {
  onClick?: () => void
  title?: string
  disabled?: boolean
  active?: boolean
  danger?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={`v4c-ghost${danger ? ' v4c-danger' : ''}${active ? ' v4c-on' : ''}`}
      onClick={onClick}
      title={title}
      disabled={disabled}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 12px',
        border: `1px solid ${active ? ACCENT : danger ? 'rgba(248,113,113,.35)' : 'rgba(255,255,255,.14)'}`,
        background: active ? `${ACCENT}26` : 'rgba(255,255,255,.03)',
        color: danger ? '#F87171' : active ? '#E6EAF5' : '#8B93A7',
        fontSize: 12,
        fontWeight: 600,
        borderRadius: 11,
        fontFamily: 'inherit',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'all .25s',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  )
}

function PrimaryBtn({ onClick, title, disabled, children }: {
  onClick?: () => void
  title?: string
  disabled?: boolean
  children: ReactNode
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      type="button"
      className="v4c-primary"
      onClick={onClick}
      title={title}
      disabled={disabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: '9px 18px',
        background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`,
        color: '#0A0F1E',
        fontWeight: 750,
        fontSize: 12.5,
        border: 'none',
        borderRadius: 12,
        boxShadow: `0 6px 24px ${ACCENT}66`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transform: hov && !disabled ? 'translateY(-2px)' : 'none',
        transition: 'all .25s',
        fontFamily: 'inherit',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </button>
  )
}

function MsgBtn({ onClick, title, active, children }: {
  onClick?: () => void
  title?: string
  active?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={active ? 'v4c-msgbtn v4c-on' : 'v4c-msgbtn'}
      onClick={onClick}
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontFamily: MONO,
        fontSize: 10,
        letterSpacing: '.08em',
        textTransform: 'uppercase',
        padding: '4px 10px',
        borderRadius: 999,
        border: `1px solid ${active ? ACCENT : 'rgba(255,255,255,.1)'}`,
        background: active ? ACCENT : 'transparent',
        color: active ? '#0A0F1E' : '#8B93A7',
        fontWeight: active ? 700 : 500,
        cursor: 'pointer',
        transition: 'all .25s',
      }}
    >
      {children}
    </button>
  )
}

const STAGES = [
  { key: 'understand', label: 'Analyse' },
  { key: 'plan', label: 'Plan' },
  { key: 'draft', label: 'Rédaction' },
  { key: 'verify', label: 'Vérif' },
  { key: 'refine', label: 'Affinage' },
  { key: 'done', label: 'Fin' },
]

function PipelineStepper() {
  const run = useChatStore((s) => s.runState)
  const idx = STAGES.findIndex((s) => s.key === run.stage)
  const isError = run.stage === 'error'
  return (
    <div style={{ margin: '2px 0 10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', rowGap: 6 }}>
        {STAGES.map((st, i) => {
          const state = isError ? 'off' : i < idx ? 'done' : i === idx ? 'now' : 'off'
          return (
            <span key={st.key} style={{ display: 'inline-flex', alignItems: 'center' }}>
              {i > 0 && (
                <span style={{
                  width: 20,
                  height: 1,
                  margin: '0 7px',
                  background: state === 'off' ? 'rgba(255,255,255,.12)' : `${ACCENT}88`,
                }} />
              )}
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: state === 'off' ? 'transparent' : ACCENT,
                  border: `1px solid ${state === 'off' ? '#5A6377' : ACCENT}`,
                  boxShadow: state === 'now' ? `0 0 10px ${ACCENT}` : 'none',
                  animation: state === 'now' ? 'v4c-pulse 1.4s ease-in-out infinite' : 'none',
                }} />
                <span style={{
                  fontFamily: MONO,
                  fontSize: 9.5,
                  letterSpacing: '.14em',
                  textTransform: 'uppercase',
                  color: state === 'now' ? '#E6EAF5' : state === 'done' ? '#8B93A7' : '#5A6377',
                }}>
                  {st.label}
                </span>
              </span>
            </span>
          )
        })}
      </div>
      <div style={{ marginTop: 7, fontSize: 11, color: isError ? '#F87171' : '#8B93A7' }}>
        {run.label} — {run.detail}
      </div>
      {!isError && (
        <div aria-hidden="true" style={{
          marginTop: 8,
          height: 2,
          borderRadius: 2,
          overflow: 'hidden',
          background: 'rgba(255,255,255,.05)',
        }}>
          <div className="v4c-shimmer" style={{
            height: '100%',
            width: '38%',
            borderRadius: 2,
            background: `linear-gradient(90deg, transparent, ${ACCENT}cc, transparent)`,
          }} />
        </div>
      )}
    </div>
  )
}

function AttachmentRow({ attachments, onRemove }: {
  attachments: Attachment[]
  onRemove: (id: string) => void
}) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ ...LABEL, marginBottom: 7, display: 'flex', alignItems: 'center', gap: 6 }}>
        <Ic name="clip" size={11} />
        {attachments.length === 1
          ? '1 fichier joint au prochain message'
          : `${attachments.length} fichiers joints au prochain message`}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {attachments.map((a) => (
          <span
            key={a.id}
            title={a.previewUrl
              ? (a.visionText ? `Image — ${a.visionText.slice(0, 160)}…` : 'Image — analyse vision en cours…')
              : a.text ? `${a.name} — contenu lisible injecté` : `${a.name} — binaire (nom transmis uniquement)`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '5px 9px',
              borderRadius: 999,
              border: '1px solid rgba(255,255,255,.1)',
              background: 'rgba(255,255,255,.03)',
              fontSize: 11,
              color: '#E6EAF5',
            }}
          >
            {a.previewUrl
              ? <img src={a.previewUrl} alt={a.name} style={{ width: 22, height: 22, borderRadius: 6, objectFit: 'cover' }} />
              : <span style={{ color: '#8B93A7', display: 'inline-flex' }}><Ic name="file" size={12} /></span>}
            <span style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</span>
            {a.previewUrl && !a.visionText && (
              <span style={{ color: ACCENT, fontFamily: MONO, fontSize: 9, animation: 'v4c-pulse 1.4s ease-in-out infinite' }}>
                vision…
              </span>
            )}
            <span style={{ color: '#5A6377', fontFamily: MONO, fontSize: 10 }}>
              {a.size > 1024 ? `${(a.size / 1024).toFixed(1)} ko` : `${a.size} o`}
            </span>
            <button
              type="button"
              onClick={() => onRemove(a.id)}
              title="Retirer"
              style={{ background: 'transparent', border: 'none', color: '#8B93A7', cursor: 'pointer', padding: 2, display: 'inline-flex' }}
            >
              <Ic name="x" size={11} />
            </button>
          </span>
        ))}
      </div>
    </div>
  )
}

export default function AuroraV4ConversationView() {
  const L = useChatViewLogic()
  const transcriptRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const msgEls = useRef<(HTMLDivElement | null)[]>([])

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')
  const [bubbleCopiedId, setBubbleCopiedId] = useState<string | null>(null)
  const [copiedAll, setCopiedAll] = useState<'ok' | 'err' | null>(null)
  const [composerFocus, setComposerFocus] = useState(false)
  const [slashIdx, setSlashIdx] = useState(0)
  useEffect(() => { setSlashIdx(0) }, [L.draft])

  const [scrolledUp, setScrolledUp] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  useEffect(() => {
    const el = transcriptRef.current
    if (!el) return
    const onScroll = () => {
      const dist = el.scrollHeight - el.clientHeight - el.scrollTop
      const up = dist > 120
      setScrolledUp(up)
      if (!up) setUnreadCount(0)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  const [threadSearchOpen, setThreadSearchOpen] = useState(false)
  const [threadSearchQuery, setThreadSearchQuery] = useState('')
  const threadSearchInputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f' && !e.shiftKey) {
        const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        e.preventDefault()
        setThreadSearchOpen(true)
        window.setTimeout(() => threadSearchInputRef.current?.focus(), 50)
      } else if (e.key === 'Escape' && threadSearchOpen) {
        setThreadSearchOpen(false)
        setThreadSearchQuery('')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [threadSearchOpen])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i' && !e.shiftKey && !e.altKey) {
        const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        e.preventDefault()
        textareaRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return
      const isNav = e.key === 'End' || e.key === 'Home' || e.key === 'PageDown' || e.key === 'PageUp'
      if (!isNav) return
      const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const el = transcriptRef.current
      if (!el) return
      e.preventDefault()
      const page = el.clientHeight * 0.85
      const top = e.key === 'End' ? el.scrollHeight
        : e.key === 'Home' ? 0
        : e.key === 'PageDown' ? Math.min(el.scrollHeight, el.scrollTop + page)
        : Math.max(0, el.scrollTop - page)
      el.scrollTo({ top, behavior: 'smooth' })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const threadSearchQ = threadSearchQuery.trim().toLowerCase()
  const threadMatchIndices = threadSearchQ
    ? L.messages
        .map((m, i) => (m.content || '').toLowerCase().includes(threadSearchQ) ? i : -1)
        .filter((i) => i !== -1)
    : []
  const threadMatchCount = threadMatchIndices.length
  const [threadMatchCursor, setThreadMatchCursor] = useState(0)
  useEffect(() => { setThreadMatchCursor(0) }, [threadSearchQuery])
  const scrollToMatch = (cursor: number) => {
    if (threadMatchIndices.length === 0) return
    const safe = ((cursor % threadMatchIndices.length) + threadMatchIndices.length) % threadMatchIndices.length
    msgEls.current[threadMatchIndices[safe]]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const lastSeenLen = useRef(L.messages.length)
  useEffect(() => {
    const len = L.messages.length
    if (len > lastSeenLen.current) {
      const newest = L.messages[len - 1]
      if (newest?.role === 'user') {
        setUnreadCount(0)
        setScrolledUp(false)
        const el = transcriptRef.current
        if (el) el.scrollTop = el.scrollHeight
      } else if (scrolledUp) {
        setUnreadCount((n) => n + (len - lastSeenLen.current))
      }
    }
    lastSeenLen.current = len
  }, [L.messages.length, scrolledUp, L.messages])

  const lastLevelRef = useRef<'safe' | 'warn' | 'danger'>('safe')
  useEffect(() => {
    if (L.messages.length === 0) {
      lastLevelRef.current = 'safe'
      return
    }
    const total = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
    const usage = getContextUsage(L.mainModel, total)
    const ranks: Record<'safe' | 'warn' | 'danger', number> = { safe: 0, warn: 1, danger: 2 }
    if (ranks[usage.level] > ranks[lastLevelRef.current]) {
      const push = useNotificationStore.getState().push
      if (usage.level === 'warn') {
        push({
          level: 'warning',
          message: 'Contexte modèle 75% atteint',
          detail: `~${usage.tokens} / ${usage.limit} tokens. Pense à résumer ou ouvrir un nouveau fil bientôt.`,
          duration: 6000,
        })
      } else if (usage.level === 'danger') {
        push({
          level: 'error',
          message: 'Contexte modèle 95% — troncature imminente',
          detail: `~${usage.tokens} / ${usage.limit} tokens. Le modèle va perdre les anciens messages.`,
          duration: 9000,
        })
      }
    }
    lastLevelRef.current = usage.level
  }, [L.messages.length, L.mainModel, L.messages])

  const drop = useFileDrop({
    onFiles: (files) => void L.addFiles(files),
    accept: ['txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'html', 'css', 'sh', 'tex', 'xml', 'yaml', 'pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/json', 'image/'],
  })

  useEffect(() => {
    const el = transcriptRef.current
    if (el && !scrolledUp) el.scrollTop = el.scrollHeight
  }, [L.messages.length, L.streamContent, scrolledUp])

  useEffect(() => {
    const t = textareaRef.current
    if (!t) return
    t.style.height = 'auto'
    t.style.height = Math.min(180, t.scrollHeight) + 'px'
  }, [L.draft])

  const trimmedDraft = L.draft.trim()
  const slashActive = trimmedDraft.startsWith('/') && !trimmedDraft.includes(' ') && !trimmedDraft.includes('\n')
  const slashSuggestions = slashActive ? suggestCommands(trimmedDraft) : []
  const recentSlash = new Set(getRecentSlash())

  const onComposerKeyDown = (e: RKeyboardEvent<HTMLTextAreaElement>) => {
    if (slashActive && slashSuggestions.length > 0) {
      if (e.key === 'Escape') {
        e.preventDefault()
        L.setDraft('')
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashIdx((i) => Math.min(slashSuggestions.length - 1, i + 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashIdx((i) => Math.max(0, i - 1))
        return
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.metaKey && !e.ctrlKey)) {
        e.preventDefault()
        const cmd = slashSuggestions[Math.min(slashIdx, slashSuggestions.length - 1)]
        if (cmd) {
          L.setDraft(`/${cmd.name} `)
          textareaRef.current?.focus()
        }
        return
      }
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      void L.onSend()
    }
  }

  const onFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    await L.addFiles(files)
    e.target.value = ''
  }

  const startEdit = (m: ChatMessage) => {
    if (!m.id) return
    setEditingId(m.id)
    setEditDraft(stripThink(m.content).visible || m.content)
  }
  const saveEdit = () => {
    if (!editingId) return
    L.updateMessage(editingId, editDraft.trim())
    setEditingId(null)
  }

  const personaName = L.who === 'natsu' ? 'Natsu' : 'Lucy'
  const shortModel = L.mainModel.split('/').pop() || L.mainModel
  const totalChars = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
  const usage = L.messages.length > 0 ? getContextUsage(L.mainModel, totalChars) : null
  const usageTone = usage?.level === 'danger' ? '#F87171' : usage?.level === 'warn' ? '#FBBF24' : undefined
  const tip = getDailyTip('chat')

  return (
    <div
      {...drop.bind}
      className="v4c-root"
      style={{
        padding: '22px 26px',
        minHeight: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        color: '#E6EAF5',
        fontFamily: "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif",
        position: 'relative',
        isolation: 'isolate',
        overflow: 'hidden',
        outline: drop.isDraggingOver ? `2px dashed ${ACCENT}` : 'none',
        outlineOffset: -6,
        transition: 'outline .25s',
      }}
    >
      <style>{`
        @keyframes v4c-in { from { opacity: 0; transform: translateY(10px) } to { opacity: 1; transform: none } }
        @keyframes v4c-pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }
        @keyframes v4c-blink { 50% { opacity: 0 } }
        @keyframes v4c-sheen { from { transform: translateX(-160%) skewX(-18deg) } to { transform: translateX(260%) skewX(-18deg) } }
        @keyframes v4c-halo { 0%,100% { opacity: .5; transform: scale(1) } 50% { opacity: 1; transform: scale(1.08) } }
        @keyframes v4c-spin { to { transform: rotate(360deg) } }
        @keyframes v4c-drift { from { transform: translate3d(-1.5%, -1%, 0) scale(1) } to { transform: translate3d(1.5%, 1.5%, 0) scale(1.05) } }
        @keyframes v4c-float { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-5px) } }
        @keyframes v4c-gradshift { 0%,100% { background-position: 0% 50% } 50% { background-position: 100% 50% } }
        @keyframes v4c-scan { from { transform: translateX(-110%) } to { transform: translateX(380%) } }
        @keyframes v4c-glow { 0%,100% { box-shadow: 0 0 16px ${ACCENT}40 } 50% { box-shadow: 0 0 30px ${ACCENT}59, 0 0 62px ${ACCENT}21 } }
        @keyframes v4c-ring { 0% { box-shadow: 0 6px 24px ${ACCENT}66, 0 0 0 0 ${ACCENT}66 } 75% { box-shadow: 0 6px 24px ${ACCENT}66, 0 0 0 13px transparent } 100% { box-shadow: 0 6px 24px ${ACCENT}66, 0 0 0 0 transparent } }
        .v4c-root::before {
          content: ''; position: absolute; inset: -10%; z-index: -1; pointer-events: none;
          background:
            radial-gradient(620px 420px at 14% 2%, ${ACCENT}17, transparent 62%),
            radial-gradient(540px 460px at 88% 20%, ${ACCENT}0e, transparent 65%),
            radial-gradient(760px 520px at 58% 104%, ${ACCENT}0b, transparent 60%);
          animation: v4c-drift 26s ease-in-out infinite alternate;
        }
        .v4c-root::after {
          content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
          background-image:
            radial-gradient(circle, rgba(230,234,245,.05) 1px, transparent 1.3px),
            radial-gradient(circle, rgba(139,92,246,.055) 1px, transparent 1.4px);
          background-size: 32px 32px, 86px 86px;
          background-position: 0 0, 16px 22px;
          -webkit-mask-image: radial-gradient(ellipse 95% 78% at 50% 0%, #000 28%, transparent 100%);
          mask-image: radial-gradient(ellipse 95% 78% at 50% 0%, #000 28%, transparent 100%);
        }
        .v4c-root ::selection { background: rgba(139,92,246,.45); color: #fff }
        .v4c-root textarea::placeholder, .v4c-root input::placeholder { color: #5A6377 }
        .v4c-glass { position: relative }
        .v4c-glass::before {
          content: ''; position: absolute; top: 0; left: 13%; right: 13%; height: 1px; z-index: 2; pointer-events: none;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,.2) 28%, ${ACCENT}8c 50%, rgba(255,255,255,.2) 72%, transparent);
        }
        .v4c-gradtext { background-size: 220% 100%; animation: v4c-gradshift 7s ease-in-out infinite }
        .v4c-float { animation: v4c-float 5.5s ease-in-out infinite }
        .v4c-shimmer { animation: v4c-scan 1.5s ease-in-out infinite }
        .v4c-focusglow { animation: v4c-glow 2.6s ease-in-out infinite }
        .v4c-unread { animation: v4c-ring 1.8s cubic-bezier(0,0,.2,1) infinite }
        .v4c-scroll { scrollbar-width: thin; scrollbar-color: rgba(139,92,246,.35) transparent }
        .v4c-scroll::-webkit-scrollbar { width: 7px; height: 7px }
        .v4c-scroll::-webkit-scrollbar-track { background: transparent }
        .v4c-scroll::-webkit-scrollbar-thumb { background: rgba(139,92,246,.28); border-radius: 99px }
        .v4c-scroll::-webkit-scrollbar-thumb:hover { background: rgba(139,92,246,.6) }
        .v4c-msg { position: relative }
        .v4c-msg + .v4c-msg::before { content: ''; position: absolute; top: 0; left: 12px; right: 12px; height: 1px; background: linear-gradient(90deg, transparent, rgba(255,255,255,.08) 20%, rgba(139,92,246,.2) 50%, rgba(255,255,255,.08) 80%, transparent) }
        .v4c-msg:hover { transform: translateY(-2px) !important; background: rgba(139,92,246,.05) !important; box-shadow: inset 2px 0 0 rgba(139,92,246,.75), 0 18px 38px -22px rgba(0,0,0,.85) !important }
        .v4c-primary { position: relative; overflow: hidden }
        .v4c-primary::after { content: ''; position: absolute; top: -30%; bottom: -30%; left: 0; width: 46%; background: linear-gradient(105deg, transparent, rgba(255,255,255,.65), transparent); transform: translateX(-160%) skewX(-18deg); pointer-events: none }
        .v4c-primary:hover:not(:disabled)::after { animation: v4c-sheen .9s ease }
        .v4c-ghost:hover:not(:disabled) { transform: translateY(-1px) }
        .v4c-ghost:active:not(:disabled) { transform: translateY(0) }
        .v4c-ghost:not(.v4c-danger):not(.v4c-on):hover:not(:disabled) { color: #E6EAF5 !important; border-color: rgba(139,92,246,.5) !important; background: rgba(139,92,246,.08) !important; box-shadow: 0 8px 22px -12px rgba(139,92,246,.55) }
        .v4c-danger:hover:not(:disabled) { border-color: rgba(248,113,113,.65) !important; background: rgba(248,113,113,.12) !important }
        .v4c-msgbtn:not(.v4c-on):hover { color: #E6EAF5 !important; border-color: rgba(139,92,246,.55) !important; background: rgba(139,92,246,.12) !important }
        @media (prefers-reduced-motion: reduce) {
          .v4c-root *, .v4c-root *::before, .v4c-root *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important }
        }
      `}</style>

      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute',
          top: 12,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 100,
          pointerEvents: 'none',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 16px',
          borderRadius: 999,
          background: ACCENT,
          color: '#0A0F1E',
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '.14em',
          textTransform: 'uppercase',
          boxShadow: `0 8px 28px ${ACCENT}66`,
        }}>
          <Ic name="clip" size={12} />
          Déposer · txt / pdf / docx / image
        </div>
      )}

      <header style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        flexWrap: 'wrap',
        paddingBottom: 13,
        borderBottom: '1px solid transparent',
        borderImage: `linear-gradient(90deg, ${ACCENT}d9, ${ACCENT}40 38%, ${ACCENT}0d 72%, transparent) 1`,
        animation: 'v4c-in .5s cubic-bezier(.22,1,.36,1) both',
      }}>
        <span className="v4c-float" style={{ position: 'relative', display: 'flex', filter: `drop-shadow(0 0 14px ${ACCENT}55)` }}>
          <span style={{
            position: 'absolute',
            inset: -12,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${ACCENT}38, transparent 70%)`,
            animation: 'v4c-halo 3.4s ease-in-out infinite',
            pointerEvents: 'none',
          }} />
          <AuroraMascot module="conversation" size={46} state={L.isStreaming ? 'working' : 'idle'} />
        </span>
        <div style={{ minWidth: 0 }}>
          <h1 className="v4c-gradtext" style={{
            margin: 0,
            fontSize: 24,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
            background: 'linear-gradient(92deg, #FFFFFF 15%, #CDB9FF 55%, #9F7DFF 78%, #FFFFFF)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            Conversation
          </h1>
          <div aria-hidden="true" style={{
            height: 2,
            width: 148,
            margin: '5px 0 4px',
            borderRadius: 2,
            background: `linear-gradient(90deg, ${ACCENT}, ${ACCENT}59 55%, transparent)`,
            boxShadow: `0 0 12px ${ACCENT}59`,
          }} />
          <div style={LABEL}>
            agent lumo · persona {personaName} · {shortModel}
          </div>
        </div>
        <span style={{ flex: 1 }} />
        <Chip active={L.isStreaming} title={L.isStreaming ? 'Génération en cours' : 'Copilote prêt'}>
          <span style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: L.isStreaming ? '#0A0F1E' : '#4ADE80',
            boxShadow: L.isStreaming ? 'none' : '0 0 8px #4ADE80',
            animation: 'v4c-pulse 1.2s ease-in-out infinite',
          }} />
          {L.isStreaming ? 'live' : 'prêt'}
        </Chip>
        <Chip title="Nombre de tours dans le fil">{L.messages.length} tours</Chip>
        {usage && (
          <Chip
            tone={usageTone}
            title={`${totalChars} caractères · ~${usage.tokens} tokens / ~${usage.limit} (${(usage.ratio * 100).toFixed(0)}%) · modèle ${shortModel}`}
          >
            ~{usage.tokens}t · {(usage.ratio * 100).toFixed(0)}%
          </Chip>
        )}
        <GhostBtn
          active={threadSearchOpen}
          title="Chercher dans la conversation (Ctrl+F)"
          onClick={() => {
            const next = !threadSearchOpen
            setThreadSearchOpen(next)
            if (next) window.setTimeout(() => threadSearchInputRef.current?.focus(), 50)
            else setThreadSearchQuery('')
          }}
        >
          <Ic name="search" />
        </GhostBtn>
        <GhostBtn
          title="Copier la conversation en Markdown au presse-papier"
          onClick={() => {
            void L.copyConversation().then((ok) => {
              setCopiedAll(ok ? 'ok' : 'err')
              window.setTimeout(() => setCopiedAll(null), 1400)
            })
          }}
        >
          <Ic name={copiedAll === 'ok' ? 'check' : 'copy'} />
          {copiedAll === 'ok' ? 'Copié' : copiedAll === 'err' ? 'Échec' : 'Copier'}
        </GhostBtn>
        <GhostBtn title="Exporter en Markdown" onClick={() => void L.exportConversation('markdown')}>
          <Ic name="file" /> MD
        </GhostBtn>
        <GhostBtn title="Exporter en PDF" onClick={() => void L.exportConversation('pdf')}>
          <Ic name="file" /> PDF
        </GhostBtn>
        <GhostBtn title="Lire la page active du navigateur (Aurora-Connect)" onClick={() => void L.readActiveTab()}>
          <Ic name="globe" /> Onglet
        </GhostBtn>
        <GhostBtn danger title="Effacer toute la conversation" onClick={L.clearAll}>
          <Ic name="trash" />
        </GhostBtn>
      </header>

      <section className="v4c-glass" style={{
        ...GLASS,
        flex: 1,
        minHeight: 0,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        boxShadow: '0 24px 60px -32px rgba(0,0,0,.65)',
        animation: 'v4c-in .5s cubic-bezier(.22,1,.36,1) .06s both',
      }}>
        {threadSearchOpen && (
          <div style={{
            position: 'absolute',
            top: 12,
            right: 14,
            zIndex: 30,
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            padding: '7px 10px',
            ...GLASS,
            borderRadius: 13,
            background: 'rgba(8,12,24,.94)',
            boxShadow: '0 10px 30px rgba(0,0,0,.5)',
          }}>
            <span style={{ color: '#8B93A7', display: 'inline-flex' }}><Ic name="search" size={12} /></span>
            <input
              ref={threadSearchInputRef}
              type="text"
              value={threadSearchQuery}
              onChange={(e) => setThreadSearchQuery(e.target.value)}
              onKeyDown={(e: RKeyboardEvent<HTMLInputElement>) => {
                if (e.key === 'Enter' && threadMatchCount > 0) {
                  e.preventDefault()
                  const next = e.shiftKey ? threadMatchCursor - 1 : threadMatchCursor + 1
                  setThreadMatchCursor(next)
                  scrollToMatch(next)
                }
              }}
              placeholder="Chercher… (Entrée suivant · Maj+Entrée précédent)"
              onFocus={(e) => {
                e.currentTarget.style.borderColor = ACCENT
                e.currentTarget.style.boxShadow = `0 0 16px ${ACCENT}40`
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,.12)'
                e.currentTarget.style.boxShadow = 'none'
              }}
              style={{
                width: 230,
                padding: '6px 10px',
                background: 'rgba(10,15,30,.6)',
                border: '1px solid rgba(255,255,255,.12)',
                borderRadius: 11,
                color: '#E6EAF5',
                fontSize: 12,
                outline: 'none',
                fontFamily: 'inherit',
                transition: 'all .25s',
              }}
            />
            <span style={{ fontFamily: MONO, fontSize: 10, color: '#8B93A7', minWidth: 52, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {threadSearchQ
                ? `${threadMatchCount > 0 ? (((threadMatchCursor % threadMatchCount) + threadMatchCount) % threadMatchCount + 1) : 0} / ${threadMatchCount}`
                : `${L.messages.length}`}
            </span>
            <button
              type="button"
              onClick={() => { setThreadSearchOpen(false); setThreadSearchQuery('') }}
              title="Fermer (Échap)"
              style={{ background: 'transparent', border: 'none', color: '#8B93A7', cursor: 'pointer', padding: 3, display: 'inline-flex' }}
            >
              <Ic name="x" size={12} />
            </button>
          </div>
        )}

        <div ref={transcriptRef} className="v4c-scroll" style={{ flex: 1, overflowY: 'auto', padding: '18px 22px 24px' }}>
          {L.messages.length === 0 && !L.isStreaming && (
            <div style={{ textAlign: 'center', padding: '56px 20px 42px', maxWidth: 600, margin: '0 auto' }}>
              <div style={{ position: 'relative', display: 'inline-flex', marginBottom: 28, animation: 'v4c-in .6s cubic-bezier(.22,1,.36,1) both' }}>
                <span style={{
                  position: 'absolute',
                  inset: -28,
                  borderRadius: '50%',
                  background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`,
                  animation: 'v4c-halo 3.6s ease-in-out infinite',
                  pointerEvents: 'none',
                }} />
                <span style={{
                  position: 'absolute',
                  inset: -16,
                  borderRadius: '50%',
                  border: `1px dashed ${ACCENT}4d`,
                  animation: 'v4c-spin 26s linear infinite',
                  pointerEvents: 'none',
                }} />
                <span style={{
                  position: 'absolute',
                  inset: -30,
                  borderRadius: '50%',
                  border: `1px solid ${ACCENT}1f`,
                  animation: 'v4c-spin 44s linear infinite reverse',
                  pointerEvents: 'none',
                }} />
                <span aria-hidden="true" style={{
                  position: 'absolute',
                  top: -8,
                  right: -24,
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: ACCENT,
                  opacity: 0.75,
                  boxShadow: `0 0 10px ${ACCENT}`,
                  animation: 'v4c-float 4.2s ease-in-out infinite .2s',
                  pointerEvents: 'none',
                }} />
                <span aria-hidden="true" style={{
                  position: 'absolute',
                  top: 34,
                  left: -32,
                  width: 4,
                  height: 4,
                  borderRadius: '50%',
                  background: '#CDB9FF',
                  opacity: 0.5,
                  boxShadow: `0 0 8px ${ACCENT}`,
                  animation: 'v4c-float 5.1s ease-in-out infinite .9s',
                  pointerEvents: 'none',
                }} />
                <span aria-hidden="true" style={{
                  position: 'absolute',
                  bottom: -10,
                  right: -6,
                  width: 3,
                  height: 3,
                  borderRadius: '50%',
                  background: ACCENT,
                  opacity: 0.6,
                  boxShadow: `0 0 7px ${ACCENT}`,
                  animation: 'v4c-float 4.7s ease-in-out infinite 1.6s',
                  pointerEvents: 'none',
                }} />
                <span className="v4c-float" style={{ filter: `drop-shadow(0 0 24px ${ACCENT}66)`, display: 'flex' }}>
                  <AuroraMascot module="conversation" size={90} />
                </span>
              </div>
              <div style={{ ...LABEL, marginBottom: 10, animation: 'v4c-in .55s cubic-bezier(.22,1,.36,1) .08s both' }}>
                module conversation · agent lumo · prêt
              </div>
              <div style={{
                fontSize: 19,
                fontWeight: 800,
                letterSpacing: '-0.02em',
                marginBottom: 8,
                lineHeight: 1.4,
                background: 'linear-gradient(92deg, #FFFFFF 20%, #CDB9FF 58%, #9F7DFF 80%, #FFFFFF)',
                backgroundSize: '220% 100%',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                animation: 'v4c-in .55s cubic-bezier(.22,1,.36,1) .14s both, v4c-gradshift 7s ease-in-out .7s infinite',
              }}>
                {WELCOME[L.who]}
              </div>
              <div style={{ fontSize: 12.5, color: '#8B93A7', animation: 'v4c-in .55s cubic-bezier(.22,1,.36,1) .2s both' }}>
                Écris à Aurora ci-dessous — Ctrl+Entrée pour envoyer, / pour les commandes.
              </div>
              {tip && (
                <div style={{
                  marginTop: 26,
                  display: 'inline-block',
                  padding: '9px 14px',
                  fontSize: 11,
                  fontFamily: MONO,
                  color: '#8B93A7',
                  background: `${ACCENT}0d`,
                  border: `1px solid ${ACCENT}38`,
                  borderRadius: 11,
                  maxWidth: 520,
                  lineHeight: 1.55,
                  animation: 'v4c-in .55s cubic-bezier(.22,1,.36,1) .26s both',
                }}>
                  {tip}
                </div>
              )}
              <div style={{ marginTop: 22, display: 'flex', justifyContent: 'center', animation: 'v4c-in .55s cubic-bezier(.22,1,.36,1) .32s both' }}>
                <PrimaryBtn title="Lancer un sujet de conversation au hasard" onClick={() => void L.onSend(false, pickRandomStarter())}>
                  <Ic name="spark" /> Surprends-moi
                </PrimaryBtn>
              </div>
            </div>
          )}

          {L.messages.map((m, i) => {
            const id = String(m.id ?? m.timestamp ?? i)
            const isAsst = m.role === 'assistant'
            const { visible, thinking } = stripThink(m.content)
            const isEditing = editingId === m.id
            const isLast = i === L.messages.length - 1
            const matchesSearch = !threadSearchQ || (m.content || '').toLowerCase().includes(threadSearchQ)
            return (
              <div
                key={m.id || i}
                ref={(el) => { msgEls.current[i] = el }}
                className="v4c-msg"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '40px 1fr',
                  gap: 13,
                  padding: '14px 10px',
                  borderRadius: 12,
                  opacity: !matchesSearch ? 0.22 : 1,
                  background: m.pinned ? `${ACCENT}0f` : 'transparent',
                  boxShadow: m.pinned ? `inset 2px 0 0 ${ACCENT}` : 'none',
                  animation: `v4c-in .45s cubic-bezier(.22,1,.36,1) ${Math.min(i * 40, 240)}ms both`,
                  transition: 'opacity .25s, transform .25s, background .25s, box-shadow .25s',
                }}
              >
                {isAsst ? (
                  <span style={{ filter: `drop-shadow(0 0 8px ${ACCENT}44)`, display: 'flex', alignItems: 'flex-start' }}>
                    <AuroraMascot module="conversation" size={34} />
                  </span>
                ) : (
                  <span style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    border: '1px solid rgba(255,255,255,.14)',
                    background: 'rgba(255,255,255,.04)',
                    color: '#8B93A7',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    <Ic name="user" size={15} />
                  </span>
                )}
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 4, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 700, fontSize: 13, letterSpacing: '-0.01em' }}>
                      {isAsst ? `Aurora · ${personaName}` : 'Toi'}
                    </span>
                    {m.timestamp && (
                      <span
                        title={new Date(m.timestamp).toLocaleString('fr-FR')}
                        style={{ fontSize: 10, color: '#5A6377', fontFamily: MONO, fontVariantNumeric: 'tabular-nums' }}
                      >
                        {new Date(m.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                    {(visible || m.content).length > 80 && (
                      <span
                        title={`${(visible || m.content).length} caractères · ~${Math.ceil((visible || m.content).length / 4)} tokens (estimation)`}
                        style={{ fontSize: 10, color: '#5A6377', fontFamily: MONO, fontVariantNumeric: 'tabular-nums' }}
                      >
                        ~{Math.ceil((visible || m.content).length / 4)}t
                      </span>
                    )}
                    {m.pinned && (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 9.5,
                        fontFamily: MONO,
                        letterSpacing: '.1em',
                        textTransform: 'uppercase',
                        color: ACCENT,
                      }}>
                        <Ic name="pin" size={10} /> épinglé
                      </span>
                    )}
                    {m.edited && <span style={{ fontSize: 10, color: '#5A6377' }}>(modifié)</span>}
                  </div>
                  {thinking && (
                    <details style={{
                      marginBottom: 6,
                      fontSize: 12,
                      color: '#8B93A7',
                      borderLeft: `2px solid ${ACCENT}55`,
                      paddingLeft: 10,
                    }}>
                      <summary style={{ cursor: 'pointer', ...LABEL, fontSize: 9.5 }}>raisonnement</summary>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 6, color: '#5A6377' }}>{thinking}</div>
                    </details>
                  )}
                  {isEditing ? (
                    <div>
                      <textarea
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        rows={Math.min(10, editDraft.split('\n').length + 1)}
                        autoFocus
                        onKeyDown={(e: RKeyboardEvent<HTMLTextAreaElement>) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); saveEdit() }
                          else if (e.key === 'Escape') { e.preventDefault(); setEditingId(null) }
                        }}
                        style={{
                          width: '100%',
                          resize: 'vertical',
                          background: 'rgba(10,15,30,.6)',
                          border: `1px solid ${ACCENT}`,
                          boxShadow: `0 0 16px ${ACCENT}40`,
                          borderRadius: 11,
                          color: '#E6EAF5',
                          fontFamily: 'inherit',
                          fontSize: 13.5,
                          lineHeight: 1.55,
                          padding: 10,
                          outline: 'none',
                        }}
                      />
                      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                        <MsgBtn active onClick={saveEdit} title="Enregistrer (Ctrl+Entrée)">
                          <Ic name="check" size={10} /> enregistrer
                        </MsgBtn>
                        <MsgBtn onClick={() => setEditingId(null)} title="Annuler (Échap)">
                          <Ic name="x" size={10} /> annuler
                        </MsgBtn>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 14, lineHeight: 1.6 }}>
                      {isAsst
                        ? <MarkdownPro content={visible || m.content} idPrefix={`v4-bubble-${id}`} />
                        : <span style={{ whiteSpace: 'pre-wrap' }}>{visible || m.content}</span>}
                    </div>
                  )}
                  {!isEditing && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 9 }}>
                      {isAsst && (
                        <MsgBtn
                          active={L.narrating === id}
                          title={L.narrating === id ? 'Stopper la lecture' : 'Lire à voix haute'}
                          onClick={() => L.narrating === id
                            ? L.stopNarration()
                            : L.narrate(visible || m.content, id)}
                        >
                          <Ic name={L.narrating === id ? 'volx' : 'vol'} size={10} />
                          {L.narrating === id ? 'stop' : 'lire'}
                        </MsgBtn>
                      )}
                      <MsgBtn
                        title="Copier le texte brut au presse-papier"
                        onClick={() => {
                          void navigator.clipboard.writeText(visible || m.content).then(() => {
                            setBubbleCopiedId(m.id ?? null)
                            window.setTimeout(() => setBubbleCopiedId(null), 1200)
                          })
                        }}
                      >
                        <Ic name={bubbleCopiedId === m.id ? 'check' : 'copy'} size={10} />
                        {bubbleCopiedId === m.id ? 'copié' : 'copier'}
                      </MsgBtn>
                      {m.id && (
                        <MsgBtn title="Éditer le message" onClick={() => startEdit(m)}>
                          <Ic name="edit" size={10} /> éditer
                        </MsgBtn>
                      )}
                      {isAsst && isLast && !L.isStreaming && (
                        <MsgBtn title="Régénérer la réponse" onClick={L.onRegenerate}>
                          <Ic name="regen" size={10} /> régén
                        </MsgBtn>
                      )}
                      {m.id && (
                        <MsgBtn
                          active={m.pinned}
                          title={m.pinned ? 'Détacher' : 'Épingler'}
                          onClick={() => L.togglePinned(m.id!)}
                        >
                          <Ic name="pin" size={10} /> {m.pinned ? 'ôter' : 'épingler'}
                        </MsgBtn>
                      )}
                      {m.id && (
                        <MsgBtn
                          title="Supprimer le message"
                          onClick={() => {
                            if (window.confirm('Supprimer ce message ?')) L.removeMessage(m.id!, !isAsst)
                          }}
                        >
                          <Ic name="trash" size={10} /> suppr
                        </MsgBtn>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {L.isStreaming && (
            <div className="v4c-msg" style={{
              display: 'grid',
              gridTemplateColumns: '40px 1fr',
              gap: 13,
              padding: '14px 10px',
              borderRadius: 12,
              animation: 'v4c-in .45s cubic-bezier(.22,1,.36,1) both',
            }}>
              <span style={{ filter: `drop-shadow(0 0 10px ${ACCENT}66)`, display: 'flex', alignItems: 'flex-start' }}>
                <AuroraMascot module="conversation" size={34} state="working" />
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 13 }}>Aurora · {personaName}</span>
                  <Chip active>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#0A0F1E', animation: 'v4c-pulse 1s ease-in-out infinite' }} />
                    streaming
                  </Chip>
                </div>
                <PipelineStepper />
                <div style={{ fontSize: 14, lineHeight: 1.6 }}>
                  {L.streamingVisible
                    ? <MarkdownPro content={L.streamingVisible} idPrefix="v4-stream" />
                    : (
                      <span style={{ display: 'inline-flex', gap: 5 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT, animation: 'v4c-pulse 1s ease-in-out infinite' }} />
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT, animation: 'v4c-pulse 1s ease-in-out infinite .15s' }} />
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT, animation: 'v4c-pulse 1s ease-in-out infinite .3s' }} />
                      </span>
                    )}
                  {L.streamingVisible && (
                    <span style={{
                      display: 'inline-block',
                      width: 7,
                      height: 15,
                      marginLeft: 4,
                      verticalAlign: 'text-bottom',
                      background: ACCENT,
                      animation: 'v4c-blink .9s steps(2) infinite',
                    }} />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {scrolledUp && (
          <button
            type="button"
            className={unreadCount > 0 ? 'v4c-primary v4c-unread' : 'v4c-primary'}
            onClick={() => {
              const el = transcriptRef.current
              if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
              setUnreadCount(0)
            }}
            title={unreadCount > 0
              ? `${unreadCount} nouveau(x) message(s) — descendre`
              : 'Aller en bas de la conversation'}
            style={{
              position: 'absolute',
              right: 18,
              bottom: 16,
              zIndex: 25,
              minWidth: 38,
              height: 38,
              padding: unreadCount > 0 ? '0 14px' : 0,
              borderRadius: 999,
              background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`,
              color: '#0A0F1E',
              border: 'none',
              boxShadow: `0 6px 24px ${ACCENT}66`,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              fontWeight: 750,
              fontFamily: MONO,
              fontSize: 12,
              transition: 'all .25s',
            }}
          >
            <Ic name="down" size={14} />
            {unreadCount > 0 && <span>{unreadCount}</span>}
          </button>
        )}
      </section>

      <section className="v4c-glass" style={{
        ...GLASS,
        padding: 14,
        boxShadow: '0 18px 44px -28px rgba(0,0,0,.6)',
        animation: 'v4c-in .5s cubic-bezier(.22,1,.36,1) .12s both',
      }}>
        {L.attachments.length > 0 && <AttachmentRow attachments={L.attachments} onRemove={L.removeAttachment} />}
        <div style={{ position: 'relative' }}>
          {slashSuggestions.length > 0 && (
            <div className="v4c-scroll" style={{
              position: 'absolute',
              bottom: 'calc(100% + 8px)',
              left: 0,
              right: 0,
              zIndex: 40,
              ...GLASS,
              background: 'rgba(8,12,24,.96)',
              padding: 6,
              maxHeight: 250,
              overflowY: 'auto',
              boxShadow: '0 14px 40px rgba(0,0,0,.55)',
              animation: 'v4c-in .3s cubic-bezier(.22,1,.36,1) both',
            }}>
              <div style={{ ...LABEL, fontSize: 9, padding: '4px 8px', color: ACCENT }}>
                {slashSuggestions.length} commande(s) · flèches puis Tab ou Entrée · clic
                {recentSlash.size > 0 && (
                  <span style={{ color: '#5A6377', letterSpacing: 0, textTransform: 'none', marginLeft: 6 }}>
                    · point = récente
                  </span>
                )}
              </div>
              {slashSuggestions.map((cmd, ix) => (
                <button
                  key={cmd.name}
                  type="button"
                  onClick={() => {
                    L.setDraft(`/${cmd.name} `)
                    textareaRef.current?.focus()
                  }}
                  onMouseEnter={() => setSlashIdx(ix)}
                  title={cmd.example}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '7px 10px',
                    background: ix === slashIdx ? `${ACCENT}1f` : 'transparent',
                    border: 'none',
                    borderLeft: `3px solid ${ix === slashIdx ? ACCENT : 'transparent'}`,
                    borderRadius: 8,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    color: '#E6EAF5',
                    transition: 'all .25s',
                    animation: `v4c-in .3s cubic-bezier(.22,1,.36,1) ${Math.min(ix * 25, 150)}ms both`,
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {recentSlash.has(cmd.name) && (
                      <span
                        title="Récemment utilisée"
                        style={{ width: 5, height: 5, borderRadius: '50%', background: ACCENT, boxShadow: `0 0 6px ${ACCENT}`, flexShrink: 0 }}
                      />
                    )}
                    <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700, color: ACCENT }}>/{cmd.name}</span>
                    {cmd.aliases.length > 1 && (
                      <span style={{ fontSize: 10, color: '#5A6377' }}>
                        alias : {cmd.aliases.filter((a) => a !== cmd.name).join(', ')}
                      </span>
                    )}
                  </span>
                  <span style={{ display: 'block', fontSize: 11, color: '#8B93A7', marginTop: 2 }}>{cmd.description}</span>
                  <span style={{ display: 'block', fontSize: 10, color: '#5A6377', marginTop: 1, fontFamily: MONO }}>{cmd.example}</span>
                </button>
              ))}
            </div>
          )}
          <div className={composerFocus ? 'v4c-focusglow' : undefined} style={{
            background: 'rgba(10,15,30,.6)',
            border: `1px solid ${composerFocus ? ACCENT : 'rgba(255,255,255,.12)'}`,
            borderRadius: 11,
            boxShadow: composerFocus ? `0 0 16px ${ACCENT}40` : 'none',
            padding: '10px 12px',
            transition: 'all .25s',
          }}>
            <textarea
              ref={textareaRef}
              value={L.draft}
              onChange={(e) => L.setDraft(e.target.value)}
              onKeyDown={onComposerKeyDown}
              onFocus={() => setComposerFocus(true)}
              onBlur={() => setComposerFocus(false)}
              placeholder={L.who === 'natsu'
                ? "Balance ton défi — / pour les commandes, Ctrl+Entrée pour envoyer…"
                : "Dis-moi ce que tu veux invoquer — / pour les commandes, Ctrl+Entrée pour envoyer…"}
              rows={2}
              disabled={L.isStreaming}
              style={{
                width: '100%',
                resize: 'none',
                border: 'none',
                background: 'transparent',
                color: '#E6EAF5',
                fontFamily: 'inherit',
                fontSize: 13.5,
                lineHeight: 1.55,
                outline: 'none',
                minHeight: 40,
              }}
            />
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".txt,.md,.markdown,.json,.csv,.log,.py,.js,.ts,.html,.css,.sh,.tex,.xml,.yaml,.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"
              onChange={(e) => void onFileChange(e)}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              <GhostBtn title="Joindre un fichier (texte, pdf, docx, image)" onClick={() => fileInputRef.current?.click()}>
                <Ic name="clip" /> Joindre
              </GhostBtn>
              <VoicePushToTalk
                onTranscript={(text) => L.setDraft(L.draft.trim() ? `${L.draft} ${text}` : text)}
                label="Dicter dans le message"
                size={30}
                variant="glass"
              />
              <GhostBtn active={L.voiceOpen} title="Copilote vocal plein écran" onClick={L.openVoice}>
                <Ic name="radio" /> Voix live
              </GhostBtn>
              <GhostBtn title="Ouvrir les commandes slash" onClick={() => { L.setDraft('/'); textareaRef.current?.focus() }}>
                <Ic name="slash" /> Commande
              </GhostBtn>
              <GhostBtn
                active={L.narrationOn}
                title={L.narrationOn ? 'Narration automatique activée' : 'Lire chaque réponse à voix haute'}
                onClick={() => L.setNarrationOn(!L.narrationOn)}
              >
                <Ic name={L.narrationOn ? 'vol' : 'volx'} /> Narration
              </GhostBtn>
              <span style={{ flex: 1 }} />
              <span aria-hidden="true" style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontFamily: MONO,
                fontSize: 9,
                letterSpacing: '.12em',
                textTransform: 'uppercase',
                color: '#5A6377',
              }}>
                <span style={{
                  padding: '2px 6px',
                  borderRadius: 5,
                  border: '1px solid rgba(255,255,255,.12)',
                  background: 'rgba(255,255,255,.03)',
                  boxShadow: 'inset 0 -1px 0 rgba(255,255,255,.06)',
                }}>ctrl</span>
                +
                <span style={{
                  padding: '2px 6px',
                  borderRadius: 5,
                  border: '1px solid rgba(255,255,255,.12)',
                  background: 'rgba(255,255,255,.03)',
                  boxShadow: 'inset 0 -1px 0 rgba(255,255,255,.06)',
                }}>entrée</span>
              </span>
              {L.narrating && (
                <GhostBtn danger title="Couper la lecture vocale" onClick={L.stopNarration}>
                  <Ic name="volx" /> Couper la voix
                </GhostBtn>
              )}
              {!L.isStreaming && L.messages.length > 0 && (
                <GhostBtn title="Lancer un sujet de conversation au hasard" onClick={() => void L.onSend(false, pickRandomStarter())}>
                  <Ic name="spark" /> Surprise
                </GhostBtn>
              )}
              {L.isStreaming ? (
                <GhostBtn danger title="Arrêter la génération" onClick={L.onStop}>
                  <Ic name="stop" /> Stop
                </GhostBtn>
              ) : (
                <PrimaryBtn
                  title="Envoyer (Ctrl+Entrée)"
                  disabled={!L.draft.trim() && L.attachments.length === 0}
                  onClick={() => void L.onSend()}
                >
                  <Ic name="send" /> Envoyer
                </PrimaryBtn>
              )}
            </div>
          </div>
        </div>
      </section>

      {L.voiceOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          zIndex: 1000,
          background: 'rgba(5,7,13,.97)',
          backdropFilter: 'blur(20px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          animation: 'v4c-in .3s cubic-bezier(.22,1,.36,1)',
        }}>
          <div style={{ position: 'absolute', top: 16, right: 16 }}>
            <GhostBtn title="Fermer le mode vocal" onClick={L.closeVoice}>
              <Ic name="x" /> Fermer
            </GhostBtn>
          </div>
          <Suspense fallback={<div style={{ color: '#8B93A7', fontSize: 13, fontFamily: MONO }}>chargement du copilote vocal…</div>}>
            <VoiceCopilotView />
          </Suspense>
        </div>
      )}
    </div>
  )
}
