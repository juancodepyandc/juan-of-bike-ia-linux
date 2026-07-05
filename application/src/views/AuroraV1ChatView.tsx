/**
 * AuroraV1ChatView — Editorial Computing port.
 *
 * Visual chrome from _design/aurora_design_screens_v1/chat.jsx, real
 * functionality from useChatViewLogic so every Manga feature stays alive:
 * attachments + vision, slash menu, bubble actions (copy/edit/regen/pin/
 * delete/narrate), <think> blocks, voice overlay, Aurora-Connect web read,
 * markdown + PDF export, conversation clear, stream stop. Same store, same
 * services, only the visual surface changes.
 */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Mic, Paperclip, Send, StopCircle, Trash2, Volume2, VolumeX,
  X, Cpu, Copy, RefreshCw, Radio, Globe,
} from 'lucide-react'
import MarkdownPro from '../components/MarkdownPro'
import AuroraSphereV1 from '../components/AuroraSphereV1'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { useChatViewLogic, stripThink, PORTRAITS, WELCOME, type Attachment } from '../hooks/useChatViewLogic'
import { useFileDrop } from '../hooks/useFileDrop'
import { suggestCommands, getRecentSlash, type SlashCommand } from '../utils/slashCommands'
import { pickRandomStarter } from '../utils/randomChatStarters'
import { getDailyTip } from '../utils/dailyTip'
import { getContextUsage } from '../utils/modelContext'
import { useNotificationStore } from '../stores/notificationStore'
// v82n5 : appStore + ModuleId imports dropped — swipe handler hoisted to
// App.tsx, ChatView no longer needs to switch modules itself.

// v82n5 : module-order constant superseded by window-level swipe handler
// in App.tsx (which works for ALL 8 modules, not just conversation).
// Kept here as a NO-OP marker so existing tests/grep on `SWIPE_MODULE_ORDER`
// still find the canonical list — App.tsx duplicates it intentionally.

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

function Eyebrow({ children, dot }: { children: React.ReactNode; dot?: string }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)', display: 'flex', alignItems: 'center', gap: 8,
    }}>
      {dot && <span style={{
        width: 8, height: 8, borderRadius: 99, background: dot,
        boxShadow: `0 0 12px ${dot}`,
      }} />}
      {children}
    </div>
  )
}

function Tag({ children, accent, style, title }: {
  children: React.ReactNode
  accent?: boolean
  style?: React.CSSProperties
  title?: string
}) {
  return (
    <span title={title} style={{
      fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 10,
      letterSpacing: '0.08em', textTransform: 'uppercase',
      color: accent ? 'var(--ember-500, #ff6a3d)' : 'var(--fg-dim, #aaa)',
      padding: '3px 9px',
      border: `1px solid var(--line-soft, rgba(255,255,255,0.08))`,
      borderRadius: 999,
      background: 'var(--bg-card, rgba(255,255,255,0.03))',
      ...style,
    }}>{children}</span>
  )
}

function Display({ size = 36, children, style }: {
  size?: number; children: React.ReactNode; style?: React.CSSProperties
}) {
  return (
    <div style={{
      fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontSize: size,
      fontStyle: 'italic', fontWeight: 400, lineHeight: 0.95,
      letterSpacing: '-0.02em', color: 'var(--fg, #f5f5f5)', ...style,
    }}>{children}</div>
  )
}

function Btn({ size = 'md', variant = 'ghost', children, onClick, disabled, title }: {
  size?: 'sm' | 'md'; variant?: 'primary' | 'ghost' | 'bare' | 'danger'
  children: React.ReactNode
  // v82n1 : accept the MouseEvent so callers that need `e.currentTarget`
  // (e.g. the copy-MD button at l. 595 with its transient ✓ feedback) typecheck.
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  disabled?: boolean; title?: string
}) {
  const fg = variant === 'primary' ? 'var(--ink-1000, #0a0a0a)'
    : variant === 'danger' ? 'var(--ember-500, #ff6a3d)' : 'var(--fg, #f5f5f5)'
  const bg = variant === 'primary' ? 'var(--ember-500, #ff6a3d)'
    : variant === 'bare' ? 'transparent' : 'var(--bg-card, rgba(255,255,255,0.04))'
  const border = variant === 'bare' ? 'none' : '1px solid var(--line, rgba(255,255,255,0.12))'
  return (
    <button
      type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontFamily: 'var(--font-sans, system-ui)',
        fontSize: size === 'sm' ? 12 : 13,
        padding: size === 'sm' ? '6px 12px' : '9px 16px',
        background: bg, color: fg, border,
        borderRadius: 'var(--r-md, 10px)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'background 120ms ease, opacity 120ms ease',
        display: 'inline-flex', alignItems: 'center', gap: 6,
      }}
    >{children}</button>
  )
}

// v82j : the previous CSS placeholder lost the centrepiece visual of the
// Editorial design. Now mounting the real WebGL2 noise sphere via
// AuroraSphereV1 (faithful port of `_design/aurora_design_lib/aurora-sphere.jsx`).

function SlashMenu({ draft, onPick }: { draft: string; onPick: (cmd: string) => void }) {
  const [suggestions, setSuggestions] = useState<Array<{ name: string; description: string; example: string }>>([])
  useEffect(() => {
    if (!draft.startsWith('/') || draft.includes('\n') || draft.includes(' ')) {
      setSuggestions([])
      return
    }
    void (async () => {
      try {
        const mod = await import('../utils/slashCommands')
        setSuggestions(mod.suggestCommands(draft).slice(0, 6))
      } catch { setSuggestions([]) }
    })()
  }, [draft])
  if (suggestions.length === 0) return null
  return (
    <div style={{
      marginBottom: 10, border: '1px solid var(--line, rgba(255,255,255,0.12))',
      background: 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 10,
      maxHeight: 220, overflowY: 'auto',
    }}>
      {suggestions.map((s) => (
        <button key={s.name} type="button"
          onMouseDown={(e) => { e.preventDefault(); onPick(s.name) }}
          style={{
            display: 'grid', gridTemplateColumns: '120px 1fr auto', gap: 12,
            width: '100%', textAlign: 'left', padding: '8px 12px',
            background: 'transparent', border: 'none',
            borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
            color: 'var(--fg, #f5f5f5)', fontFamily: 'var(--font-sans, system-ui)',
            fontSize: 12, cursor: 'pointer',
          }}>
          <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--ember-500, #ff6a3d)' }}>/{s.name}</span>
          <span style={{ color: 'var(--fg-dim, #aaa)' }}>{s.description}</span>
          <span style={{ color: 'var(--fg-mute, #777)', fontStyle: 'italic' }}>{s.example}</span>
        </button>
      ))}
    </div>
  )
}

function BubbleActions({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8,
      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
    }}>{children}</div>
  )
}

function ActionBtn({ onClick, active, title, children }: {
  onClick?: () => void; active?: boolean; title?: string; children: React.ReactNode
}) {
  return (
    <button type="button" onClick={onClick} title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '3px 8px', fontFamily: 'inherit', fontSize: 10,
        letterSpacing: '0.05em', textTransform: 'uppercase',
        background: active ? 'var(--ember-500, #ff6a3d)' : 'transparent',
        color: active ? 'var(--ink-1000, #0a0a0a)' : 'var(--fg-dim, #aaa)',
        border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
        borderRadius: 6, cursor: 'pointer',
      }}>{children}</button>
  )
}

export default function AuroraV1ChatView() {
  const L = useChatViewLogic()
  const transcriptRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // v82n5 : swipe handler hoisted to App.tsx (window-level) so it works on
  // EVERY V1 module, not just chat. Local handler removed to avoid
  // double-fire on conversation. setActiveModule is no longer needed here.
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')
  // v82h8 : feedback transitoire ✓ par message après copy.
  const [bubbleCopiedId, setBubbleCopiedId] = useState<string | null>(null)
  // v82eg : selected idx pour keyboard nav dans le slash dropdown
  const [slashIdx, setSlashIdx] = useState(0)
  // Reset à 0 quand draft change (sinon idx hors-bornes après filtrage)
  useEffect(() => { setSlashIdx(0) }, [L.draft])
  // v82fi : scroll-to-bottom indicator quand l'user a scrollé au-dessus
  // de bottom (long thread, peut rater le streaming en cours).
  // v82gm : compteur "nouveaux" quand des messages arrivent pendant
  // que l'user est remonté → pill "↓ N" au lieu de ↓ simple.
  const [scrolledUp, setScrolledUp] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  useEffect(() => {
    const el = transcriptRef.current
    if (!el) return
    const onScroll = () => {
      const dist = el.scrollHeight - el.clientHeight - el.scrollTop
      const up = dist > 120
      setScrolledUp(up)
      if (!up) setUnreadCount(0) // au bottom → reset compteur
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])
  // v82hr : search-in-thread (Ctrl+F dans la conversation).
  const [threadSearchOpen, setThreadSearchOpen] = useState(false)
  const [threadSearchQuery, setThreadSearchQuery] = useState('')
  const threadSearchInputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f' && !e.shiftKey) {
        // Skip si le focus est dans un input/textarea (le browser gère)
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
  // v82ii : Cmd+I / Ctrl+I = focus composer textarea sans souris.
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
  // v82hr : compute filtered indices pour highlight conditionnel.
  const threadSearchQ = threadSearchQuery.trim().toLowerCase()
  const threadMatchIndices = threadSearchQ
    ? L.messages
        .map((m, i) => (m.content || '').toLowerCase().includes(threadSearchQ) ? i : -1)
        .filter((i) => i !== -1)
    : []
  const threadMatchCount = threadMatchIndices.length
  // v82ht : current cursor pour Enter / Shift+Enter navigation.
  const [threadMatchCursor, setThreadMatchCursor] = useState(0)
  // Reset cursor à 0 quand query change.
  useEffect(() => { setThreadMatchCursor(0) }, [threadSearchQuery])
  // v82ht : scroll vers le match courant.
  const scrollToMatchIndex = (cursor: number) => {
    if (threadMatchIndices.length === 0) return
    const safeCursor = ((cursor % threadMatchIndices.length) + threadMatchIndices.length) % threadMatchIndices.length
    const msgIdx = threadMatchIndices[safeCursor]
    const transcript = transcriptRef.current
    if (!transcript) return
    // chaque bubble est un grid direct child — sélectionne le n+1ème.
    const bubble = transcript.children[msgIdx + 1] as HTMLElement | undefined
    if (bubble) bubble.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // v82gm : track new message arrivals tant que scrolledUp.
  // v82go : si la nouvelle message vient de l'user, reset unread + scroll
  //   bottom inconditionnel (l'user veut voir sa réponse).
  const lastSeenLen = useRef(L.messages.length)
  useEffect(() => {
    const len = L.messages.length
    if (len > lastSeenLen.current) {
      const newest = L.messages[len - 1]
      const isUserMsg = newest?.role === 'user'
      if (isUserMsg) {
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
  // v82fk + v82fl + v82fm : keyboard "End"/"Home"/"PageUp"/"PageDown".
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
  // v82hq : toast notification quand thread passe safe → warn → danger.
  const lastLevelRef = useRef<'safe' | 'warn' | 'danger'>('safe')
  useEffect(() => {
    if (L.messages.length === 0) {
      lastLevelRef.current = 'safe'
      return
    }
    const total = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
    const usage = getContextUsage(L.mainModel, total)
    const prev = lastLevelRef.current
    const ranks: Record<'safe'|'warn'|'danger', number> = { safe: 0, warn: 1, danger: 2 }
    if (ranks[usage.level] > ranks[prev]) {
      const push = useNotificationStore.getState().push
      if (usage.level === 'warn') {
        push({
          level: 'warning',
          message: 'Contexte modèle 75% atteint',
          detail: `~${usage.tokens} / ${usage.limit} tokens. Pense à résumer ou nouveau thread bientôt.`,
          duration: 6000,
        })
      } else if (usage.level === 'danger') {
        push({
          level: 'error',
          message: 'Contexte modèle 95% — truncation imminente',
          detail: `~${usage.tokens} / ${usage.limit} tokens. Le LLM va perdre les vieux messages.`,
          duration: 9000,
        })
      }
    }
    lastLevelRef.current = usage.level
  }, [L.messages.length, L.mainModel, L.messages])
  // v82fl : drag-and-drop fichiers sur la vue chat (texte/images/pdf/docx)
  const drop = useFileDrop({
    onFiles: (files) => void L.addFiles(files),
    accept: ['txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'html', 'css', 'sh', 'tex', 'xml', 'yaml', 'pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/json', 'image/'],
  })

  useEffect(() => {
    const el = transcriptRef.current
    // v82gm : ne pas yank l'user vers bottom s'il lit du contexte ancien.
    if (el && !scrolledUp) el.scrollTop = el.scrollHeight
  }, [L.messages.length, L.streamContent, scrolledUp])

  useEffect(() => {
    const t = textareaRef.current
    if (!t) return
    t.style.height = 'auto'
    t.style.height = Math.min(180, t.scrollHeight) + 'px'
  }, [L.draft])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // v82eg : keyboard nav dans le slash dropdown si visible.
    const trimmed = L.draft.trim()
    const slashActive = trimmed.startsWith('/') && !trimmed.includes(' ')
    if (slashActive) {
      const suggestions = suggestCommands(trimmed)
      if (suggestions.length > 0) {
        if (e.key === 'Escape') {
          e.preventDefault()
          L.setDraft('') // v82ei : Esc annule l'entrée slash
          return
        }
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          setSlashIdx((i) => Math.min(suggestions.length - 1, i + 1))
          return
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          setSlashIdx((i) => Math.max(0, i - 1))
          return
        }
        if (e.key === 'Tab' || (e.key === 'Enter' && !e.metaKey && !e.ctrlKey)) {
          e.preventDefault()
          const cmd = suggestions[Math.min(slashIdx, suggestions.length - 1)]
          if (cmd) {
            L.setDraft(`/${cmd.name} `)
            textareaRef.current?.focus()
          }
          return
        }
      }
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      void L.onSend()
    }
  }

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    await L.addFiles(files)
    e.target.value = ''
  }

  const startEdit = (m: { id?: string; content: string }) => {
    if (!m.id) return
    setEditingId(m.id)
    setEditDraft(stripThink(m.content).visible || m.content)
  }
  const saveEdit = () => {
    if (!editingId) return
    L.updateMessage(editingId, editDraft.trim())
    setEditingId(null)
  }

  return (
    <div className="grain aurora-v1-cols" {...drop.bind}
      style={{
        display: 'grid', gridTemplateColumns: '420px 1fr', height: '100%',
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
        position: 'relative',
        outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
        outlineOffset: drop.isDraggingOver ? '-6px' : '0',
        transition: 'outline 120ms ease',
      }}>
      {/* v82fl : hint visuel pendant drag-over */}
      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
          zIndex: 100, pointerEvents: 'none',
          padding: '8px 16px', borderRadius: 99,
          background: 'oklch(0.74 0.13 60 / 0.95)',
          color: 'var(--bg, #0c0a09)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          boxShadow: '0 6px 24px rgba(0,0,0,0.4)',
        }}>
          📎 Déposer · txt / pdf / docx / image
        </div>
      )}
      {/* Left rail — masquée sur mobile (sphère décorative + boutons
          Voice/Joindre/Web qui sont déjà dans la barre d'envoi à droite). */}
      <div className="aurora-v1-chat-rail" style={{
        position: 'relative', borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '20px 24px 0', display: 'flex', justifyContent: 'space-between' }}>
          <Eyebrow dot="oklch(0.72 0.12 200)">Conversation · {L.who === 'natsu' ? 'Natsu' : 'Lucy'}</Eyebrow>
          <Tag accent={L.isStreaming}>{L.isStreaming ? 'live' : 'idle'}</Tag>
        </div>
        <div style={{ flex: 1, position: 'relative', padding: '32px 28px 0' }}>
          <div style={{ width: '100%', aspectRatio: '1 / 1', maxWidth: 320, margin: '0 auto' }}>
            <AuroraSphereV1
              tint="oklch(0.72 0.120 200)"
              state={L.voiceOpen ? 'voice' : L.isStreaming ? 'streaming' : 'idle'}
              radius={0.42}
              glow={1.2}
            />
          </div>
          <div style={{ position: 'absolute', bottom: 24, left: 24, right: 24 }}>
            <Display size={48} style={{ marginBottom: 12 }}>
              {L.voiceOpen ? "J'écoute…" : L.isStreaming ? 'Aurora pense' : 'Aurora attend'}
            </Display>
            <div style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              letterSpacing: '0.04em', color: 'var(--fg-dim, #aaa)', marginBottom: 14,
            }}>
              {L.voiceOpen ? 'voice live · whisper.cpp'
                : L.isStreaming ? 'streaming · ctx local'
                : `prêt · ${L.mainModel.split('/').pop() || L.mainModel}`}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Btn size="sm" variant={L.voiceOpen ? 'primary' : 'ghost'} onClick={L.openVoice}>
                <Radio size={12} /> Voice live
              </Btn>
              <Btn size="sm" variant="ghost" onClick={() => fileInputRef.current?.click()}>
                <Paperclip size={12} /> Joindre
              </Btn>
              <Btn size="sm" variant="ghost" onClick={() => void L.readActiveTab()}>
                <Globe size={12} /> Web
              </Btn>
              <Btn size="sm" variant={L.narrationOn ? 'primary' : 'ghost'} onClick={() => L.setNarrationOn(!L.narrationOn)}>
                <Volume2 size={12} /> {L.narrationOn ? 'Voix on' : 'Voix off'}
              </Btn>
            </div>
          </div>
        </div>
      </div>

      {/* Right column */}
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
        <div style={{
          padding: '18px 32px', borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          display: 'flex', alignItems: 'baseline', gap: 16,
        }}>
          <Display size={36}>Conversation locale</Display>
          <span style={{ flex: 1 }} />
          <Tag>{L.messages.length} tours</Tag>
          {/* v82hm + v82hn : tokens cumulés + warning si proche limite */}
          {L.messages.length > 0 && (() => {
            const total = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
            const usage = getContextUsage(L.mainModel, total)
            const color = usage.level === 'danger'
              ? 'oklch(0.62 0.20 25)'
              : usage.level === 'warn'
              ? 'oklch(0.78 0.16 80)'
              : undefined
            const pct = (usage.ratio * 100).toFixed(0)
            return <Tag
              title={`${total} caractères · ~${usage.tokens} tokens / ~${usage.limit} (${pct}%) · modèle ${L.mainModel.split('/').pop()}`}
              style={color ? { color, borderColor: `${color}80`, background: `${color}14` } : undefined}>
              ~{usage.tokens}t · {pct}%
            </Tag>
          })()}
          <Tag><Cpu size={10} style={{ marginRight: 4, verticalAlign: 'middle' }} />
            {L.mainModel.split('/').pop() || L.mainModel}</Tag>
          {/* v82h6 : copy MD au clipboard avec feedback ✓ */}
          <Btn size="sm" variant="ghost"
            onClick={async (e: React.MouseEvent<HTMLButtonElement>) => {
              const ok = await L.copyConversation()
              const btn = e.currentTarget
              if (!btn) return
              const orig = btn.textContent ?? '⎘'
              btn.textContent = ok ? '✓' : '✗'
              window.setTimeout(() => { if (btn) btn.textContent = orig }, 1200)
            }}
            title="Copier la conversation en Markdown au presse-papier">
            ⎘
          </Btn>
          <Btn size="sm" variant="ghost" onClick={() => void L.exportConversation('markdown')} title="Export Markdown">
            <FileText size={12} /> MD
          </Btn>
          <Btn size="sm" variant="ghost" onClick={() => void L.exportConversation('pdf')} title="Export PDF">
            PDF
          </Btn>
          <Btn size="sm" variant="ghost" onClick={L.clearAll} title="Effacer">
            <Trash2 size={12} />
          </Btn>
        </div>

        {/* v82hr : floating search bar Ctrl+F */}
        {threadSearchOpen && (
          <div style={{
            position: 'absolute', top: 80, right: 24, zIndex: 50,
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 10px',
            background: 'var(--bg-raised, oklch(0.13 0.013 250))',
            border: '1px solid var(--line, rgba(255,255,255,0.18))',
            borderRadius: 6, boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          }}>
            <span style={{ color: 'var(--fg-mute, #888)' }}>🔎</span>
            <input
              ref={threadSearchInputRef}
              type="text"
              value={threadSearchQuery}
              onChange={(e) => setThreadSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && threadMatchCount > 0) {
                  e.preventDefault()
                  const next = e.shiftKey
                    ? threadMatchCursor - 1
                    : threadMatchCursor + 1
                  setThreadMatchCursor(next)
                  scrollToMatchIndex(next)
                }
              }}
              placeholder="Chercher dans la conversation… (↵ next · ⇧↵ prev)"
              style={{
                width: 240, padding: '4px 8px',
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 3, outline: 'none',
                fontFamily: 'inherit', fontSize: 'inherit',
              }} />
            <span style={{
              color: 'var(--fg-mute, #888)', fontSize: 10,
              fontVariantNumeric: 'tabular-nums', minWidth: 60, textAlign: 'right',
            }}>{threadSearchQ
              ? `${threadMatchCount > 0 ? (((threadMatchCursor % threadMatchCount) + threadMatchCount) % threadMatchCount + 1) : 0} / ${threadMatchCount}`
              : `${L.messages.length}`}</span>
            <button type="button"
              onClick={() => { setThreadSearchOpen(false); setThreadSearchQuery('') }}
              title="Fermer (Esc)"
              style={{
                width: 20, height: 20, padding: 0,
                background: 'transparent', cursor: 'pointer',
                border: '1px solid var(--line, rgba(255,255,255,0.18))',
                color: 'var(--fg-mute, #888)', borderRadius: 3,
                fontSize: 11,
              }}>×</button>
          </div>
        )}
        <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', padding: '4px 32px 32px', position: 'relative' }}>
          {L.messages.length === 0 && (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--fg-mute, #777)' }}>
              <Display size={28} style={{ marginBottom: 12, color: 'var(--fg-dim, #aaa)' }}>
                {WELCOME[L.who]}
              </Display>
              <div style={{ fontSize: 13 }}>
                Écris à Aurora ci-dessous. ⌘↵ ou Ctrl↵ pour envoyer.
              </div>
              {/* v82fs + v82ft : tip rotatif via util mutualisé */}
              <div style={{
                marginTop: 28, padding: '8px 14px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                color: 'var(--fg-dim, #aaa)',
                background: 'oklch(0.74 0.13 60 / 0.06)',
                border: '1px solid oklch(0.74 0.13 60 / 0.22)',
                borderRadius: 8, display: 'inline-block',
                maxWidth: 520, lineHeight: 1.55,
              }}>
                {getDailyTip('chat')}
              </div>
            </div>
          )}
          {L.messages.map((m, i) => {
            const id = String(m.id ?? m.timestamp ?? i)
            const isAsst = m.role === 'assistant'
            const { visible, thinking } = stripThink(m.content)
            const isEditing = editingId === m.id
            const isLast = i === L.messages.length - 1
            // v82hr : visibility filter selon search query.
            const isMatchSearch = !threadSearchQ
              || (m.content || '').toLowerCase().includes(threadSearchQ)
            return (
              <div key={m.id || i} style={{
                display: 'grid', gridTemplateColumns: '40px 1fr', gap: 14,
                padding: '14px 0',
                borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                opacity: !isMatchSearch ? 0.25 : (m.pinned ? 1 : 0.98),
                background: m.pinned ? 'rgba(255,106,61,0.04)' : 'transparent',
                animation: 'aurora-fadein .6s var(--ease-out, cubic-bezier(0.16,1,0.3,1)) both',
                transition: 'opacity .18s ease',
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 99,
                  background: isAsst
                    ? 'radial-gradient(circle at 30% 30%, var(--ember-200, #ffb195), var(--ember-700, #c5421d))'
                    : 'var(--ink-800, #1a1a1a)',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  overflow: 'hidden',
                }}>
                  {isAsst
                    ? <img src={PORTRAITS[L.who]} alt={L.who} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    : <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, fontWeight: 600 }}>J</span>}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>
                      {isAsst ? `Aurora · ${L.who === 'natsu' ? 'Natsu' : 'Lucy'}` : 'Toi'}
                    </span>
                    {/* v82hk : timestamp + token estimate (utile pour
                        suivre vitesse stream + évaluer contexte). */}
                    {m.timestamp && (
                      <span title={new Date(m.timestamp).toLocaleString('fr-FR')}
                        style={{
                          fontSize: 10, color: 'var(--fg-mute, #777)',
                          fontFamily: 'var(--font-mono, monospace)',
                          fontVariantNumeric: 'tabular-nums',
                        }}>
                        {new Date(m.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                    {(visible || m.content).length > 80 && (
                      <span title={`${(visible || m.content).length} caractères · ~${Math.ceil((visible || m.content).length / 4)} tokens (estimation)`}
                        style={{
                          fontSize: 10, color: 'var(--fg-mute, #777)',
                          fontFamily: 'var(--font-mono, monospace)',
                          fontVariantNumeric: 'tabular-nums',
                        }}>
                        ~{Math.ceil((visible || m.content).length / 4)}t
                      </span>
                    )}
                    {m.pinned && <Tag accent>📌 épinglé</Tag>}
                    {m.edited && <span style={{ fontSize: 10, color: 'var(--fg-mute, #777)' }}>(modifié)</span>}
                  </div>
                  {thinking && (
                    <details style={{
                      marginBottom: 6, fontSize: 12, color: 'var(--fg-mute, #777)',
                      borderLeft: '2px solid var(--line, rgba(255,255,255,0.12))', paddingLeft: 10,
                    }}>
                      <summary style={{ cursor: 'pointer', fontFamily: 'var(--font-mono, monospace)', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase' }}>thinking</summary>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 6, fontStyle: 'italic' }}>{thinking}</div>
                    </details>
                  )}
                  {isEditing ? (
                    <div>
                      <textarea
                        value={editDraft} onChange={(e) => setEditDraft(e.target.value)}
                        rows={Math.min(10, editDraft.split('\n').length + 1)} autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); saveEdit() }
                          else if (e.key === 'Escape') { e.preventDefault(); setEditingId(null) }
                        }}
                        style={{
                          width: '100%', resize: 'vertical', border: '1px solid var(--line, rgba(255,255,255,0.12))',
                          background: 'var(--bg-card, rgba(255,255,255,0.04))', color: 'var(--fg, #f5f5f5)',
                          fontFamily: 'var(--font-sans, system-ui)', fontSize: 14, padding: 10, borderRadius: 8,
                        }}
                      />
                      <BubbleActions>
                        <ActionBtn onClick={saveEdit}>✓ enregistrer</ActionBtn>
                        <ActionBtn onClick={() => setEditingId(null)}>× annuler</ActionBtn>
                      </BubbleActions>
                    </div>
                  ) : (
                    <div style={{ fontSize: 14.5, lineHeight: 1.6, color: 'var(--fg, #f5f5f5)' }}>
                      {isAsst
                        ? <MarkdownPro content={visible || m.content} idPrefix={`v1-bubble-${id}`} />
                        : (visible || m.content)}
                    </div>
                  )}
                  {!isEditing && (
                    <BubbleActions>
                      {isAsst && (
                        <ActionBtn
                          active={L.narrating === id}
                          title={L.narrating === id ? 'Stopper la lecture' : 'Lire à voix haute'}
                          onClick={() => L.narrating === id
                            ? L.stopNarration()
                            : L.narrate(visible || m.content, id)}>
                          {L.narrating === id ? <><VolumeX size={10} /> stop</> : <><Volume2 size={10} /> lire</>}
                        </ActionBtn>
                      )}
                      <ActionBtn title="Copier le texte brut au presse-papier" onClick={() => {
                        void navigator.clipboard.writeText(visible || m.content).then(() => {
                          setBubbleCopiedId(m.id ?? null)
                          window.setTimeout(() => setBubbleCopiedId(null), 1200)
                        })
                      }}>{bubbleCopiedId === m.id
                        ? <>✓ copié</>
                        : <><Copy size={10} /> copier</>}</ActionBtn>
                      {m.id && <ActionBtn title="Éditer" onClick={() => startEdit(m)}>✎ éditer</ActionBtn>}
                      {isAsst && isLast && (
                        <ActionBtn title="Régénérer" onClick={L.onRegenerate}>
                          <RefreshCw size={10} /> régén
                        </ActionBtn>
                      )}
                      {m.id && (
                        <ActionBtn active={m.pinned} title={m.pinned ? 'Détacher' : 'Épingler'}
                          onClick={() => L.togglePinned(m.id!)}>
                          📌 {m.pinned ? 'ôter' : 'pin'}
                        </ActionBtn>
                      )}
                      {m.id && (
                        <ActionBtn title="Supprimer" onClick={() => {
                          if (window.confirm('Supprimer ce message ?')) L.removeMessage(m.id!, !isAsst)
                        }}>🗑 suppr</ActionBtn>
                      )}
                    </BubbleActions>
                  )}
                </div>
              </div>
            )
          })}
          {L.isStreaming && (
            <div style={{
              display: 'grid', gridTemplateColumns: '40px 1fr', gap: 14,
              padding: '14px 0', borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
              animation: 'aurora-fadein .6s var(--ease-out, cubic-bezier(0.16,1,0.3,1)) both',
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 99,
                background: 'radial-gradient(circle at 30% 30%, var(--ember-200, #ffb195), var(--ember-700, #c5421d))',
                overflow: 'hidden', border: '1px solid var(--line, rgba(255,255,255,0.12))',
              }}>
                <img src={PORTRAITS[L.who]} alt={L.who} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>Aurora</span>
                  <Tag accent>● streaming</Tag>
                </div>
                <div style={{ fontSize: 14.5, lineHeight: 1.6 }}>
                  {L.streamingVisible
                    ? <MarkdownPro content={L.streamingVisible} />
                    : <span style={{ display: 'inline-flex', gap: 4 }}>
                        <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ember-500, #ff6a3d)', animation: 'aurora-blink 1s ease-in-out infinite' }} />
                        <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ember-500, #ff6a3d)', animation: 'aurora-blink 1s ease-in-out infinite .15s' }} />
                        <span style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--ember-500, #ff6a3d)', animation: 'aurora-blink 1s ease-in-out infinite .3s' }} />
                      </span>}
                  {L.streamingVisible && <span style={{
                    display: 'inline-block', width: 7, height: 16, marginLeft: 4,
                    verticalAlign: 'text-bottom', background: 'var(--ember-500, #ff6a3d)',
                    animation: 'aurora-blink .9s steps(2) infinite',
                  }} />}
                </div>
              </div>
              <style>{`
                @keyframes aurora-blink { 50% { opacity: 0 } }
                @keyframes aurora-fadein {
                  from { opacity: 0; transform: translateY(4px) }
                  to   { opacity: 1; transform: translateY(0) }
                }
              `}</style>
            </div>
          )}
        </div>

        {/* v82fi : floating "scroll to bottom" button quand l'user
            est remonté dans la conversation. Useful sur long thread
            pour suivre le streaming sans manuel scroll. */}
        {scrolledUp && (
          <button type="button"
            onClick={() => {
              const el = transcriptRef.current
              if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
              setUnreadCount(0)
            }}
            title={unreadCount > 0
              ? `${unreadCount} nouveau(x) message(s) — descendre`
              : 'Aller en bas de la conversation'}
            style={{
              position: 'absolute', right: 18, bottom: 220, zIndex: 50,
              minWidth: 36, height: 36,
              padding: unreadCount > 0 ? '0 14px' : 0,
              borderRadius: 18,
              background: 'oklch(0.74 0.13 60 / 0.85)',
              color: 'var(--bg, #0c0a09)',
              border: '1px solid oklch(0.74 0.13 60)',
              boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono, monospace)',
              transition: 'padding .18s ease, min-width .18s ease',
            }}>
            ↓{unreadCount > 0 && <span style={{ fontSize: 12 }}>{unreadCount}</span>}
          </button>
        )}
        {/* Composer */}
        <div style={{ padding: 18, borderTop: '1px solid var(--line, rgba(255,255,255,0.12))', background: 'var(--bg-raised, rgba(255,255,255,0.02))' }}>
          {L.attachments.length > 0 && <AttachmentChips attachments={L.attachments} onRemove={L.removeAttachment} />}
          <SlashMenu draft={L.draft} onPick={(cmd) => L.setDraft(`/${cmd} `)} />
          <div style={{
            border: '1px solid var(--line-strong, rgba(255,255,255,0.18))', borderRadius: 14, padding: 14,
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            boxShadow: '0 0 0 4px var(--accent-soft, rgba(255,106,61,0.08))',
            position: 'relative',
          }}>
            {/* v82ef : slash command suggestions overlay */}
            {(() => {
              const trimmed = L.draft.trim()
              if (!trimmed.startsWith('/')) return null
              if (trimmed.includes(' ') && trimmed.indexOf(' ') < trimmed.length) return null
              const suggestions = suggestCommands(trimmed)
              if (suggestions.length === 0) return null
              const recentSet = new Set(getRecentSlash())
              return (
                <div style={{
                  position: 'absolute', bottom: 'calc(100% + 6px)', left: 0, right: 0,
                  background: 'var(--bg, #0c0a09)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                  borderRadius: 10,
                  boxShadow: '0 8px 28px rgba(0,0,0,0.45)',
                  padding: 6, maxHeight: 240, overflowY: 'auto',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                  zIndex: 10,
                }}>
                  <div style={{
                    padding: '4px 8px', fontSize: 9, color: 'oklch(0.74 0.13 60)',
                    letterSpacing: '0.14em', textTransform: 'uppercase',
                  }}>
                    {suggestions.length} commande(s) · ↑↓ Tab/Entrée · clic
                    {recentSet.size > 0 && (
                      <span style={{ color: 'var(--fg-mute, #777)', letterSpacing: 0, textTransform: 'none', marginLeft: 6 }}>
                        · ★ = récent
                      </span>
                    )}
                  </div>
                  {suggestions.map((cmd: SlashCommand, ix: number) => (
                    <button key={cmd.name}
                      type="button"
                      onClick={() => {
                        L.setDraft(`/${cmd.name} `)
                        textareaRef.current?.focus()
                      }}
                      onMouseEnter={() => setSlashIdx(ix)}
                      title={cmd.example}
                      style={{
                        display: 'flex', flexDirection: 'column', gap: 2,
                        width: '100%', padding: '6px 10px', textAlign: 'left',
                        background: ix === slashIdx ? 'oklch(0.74 0.13 60 / 0.12)' : 'transparent',
                        borderLeft: `3px solid ${ix === slashIdx ? 'oklch(0.74 0.13 60)' : 'transparent'}`,
                        color: 'var(--fg, #f5f5f5)',
                        borderTop: 'none', borderRight: 'none', borderBottom: 'none',
                        borderRadius: 6, cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {recentSet.has(cmd.name) && (
                          <span title="Récemment utilisée"
                            style={{ color: 'oklch(0.72 0.14 25)', fontSize: 10 }}>★</span>
                        )}
                        <span style={{
                          color: 'oklch(0.74 0.13 60)', fontWeight: 700,
                        }}>/{cmd.name}</span>
                        {cmd.aliases.length > 1 && (
                          <span style={{ fontSize: 9, color: 'var(--fg-mute, #777)' }}>
                            alias: {cmd.aliases.filter((a) => a !== cmd.name).join(', ')}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--fg-dim, #aaa)' }}>
                        {cmd.description}
                      </div>
                      <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', fontStyle: 'italic' }}>
                        {cmd.example}
                      </div>
                    </button>
                  ))}
                </div>
              )
            })()}
            <textarea
              ref={textareaRef}
              value={L.draft} onChange={(e) => L.setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={L.who === 'natsu'
                ? "Balance ton défi, j'suis tout feu tout flamme…"
                : "Dis-moi ce que tu veux invoquer…"}
              rows={2} disabled={L.isStreaming}
              style={{
                width: '100%', resize: 'none', border: 'none',
                background: 'transparent', color: 'var(--fg, #f5f5f5)',
                fontFamily: 'var(--font-sans, system-ui)', fontSize: 14,
                lineHeight: 1.5, outline: 'none', minHeight: 40,
              }}
            />
            <input ref={fileInputRef} type="file" multiple hidden
              accept=".txt,.md,.markdown,.json,.csv,.log,.py,.js,.ts,.html,.css,.sh,.tex,.xml,.yaml,.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"
              onChange={onFileChange} />
            <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
              <Btn size="sm" variant="bare" onClick={() => fileInputRef.current?.click()} title="Joindre fichier">
                <Paperclip size={12} /> Fichier
              </Btn>
              <Btn size="sm" variant="bare" onClick={L.openVoice} title="Mode vocal full-screen">
                <Mic size={12} /> Voix
              </Btn>
              <VoicePushToTalk
                onTranscript={(text) => L.setDraft(L.draft.trim() ? `${L.draft} ${text}` : text)}
                label="Dicter dans le message"
                size={28}
                variant="ghost"
              />
              <Btn size="sm" variant="bare" onClick={() => L.setDraft('/')} title="Slash command">
                / Commande
              </Btn>
              <span style={{ flex: 1 }} />
              {L.narrating && (
                <Btn size="sm" variant="danger" onClick={L.stopNarration} title="Stop narration">
                  <VolumeX size={12} /> stop voix
                </Btn>
              )}
              {L.isStreaming ? (
                <Btn size="sm" variant="danger" onClick={L.onStop} title="Arrêter">
                  <StopCircle size={12} /> Stop
                </Btn>
              ) : (
                <Btn size="sm" variant="primary"
                  onClick={() => void L.onSend()}
                  disabled={!L.draft.trim() && L.attachments.length === 0}>
                  <Send size={12} /> {L.who === 'natsu' ? 'Brûler' : 'Invoquer'} ↵
                </Btn>
              )}
              {/* v82fc + v82fe : conversation starter aléatoire + auto-send (pool mutualisé) */}
              {!L.isStreaming && (
                <button type="button"
                  onClick={() => { void L.onSend(false, pickRandomStarter()) }}
                  title="Lance une conversation au hasard"
                  style={{
                    padding: '6px 10px', fontSize: 10,
                    background: 'oklch(0.74 0.13 60 / 0.10)',
                    color: 'oklch(0.74 0.13 60)',
                    border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                    borderRadius: 6, cursor: 'pointer',
                    fontFamily: 'var(--font-mono, monospace)', fontWeight: 700,
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                  }}>⚡ surprise · go</button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Voice overlay */}
      <AnimatePresence>
        {L.voiceOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 1000,
              background: 'var(--bg, #0c0a09)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            <button type="button" onClick={L.closeVoice} title="Fermer"
              style={{
                position: 'absolute', top: 16, right: 16,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 8, padding: 8, cursor: 'pointer',
                color: 'var(--fg, #f5f5f5)',
              }}>
              <X size={16} />
            </button>
            <Suspense fallback={<div style={{ color: 'var(--fg-dim, #aaa)' }}>Invocation du copilote vocal…</div>}>
              <VoiceCopilotView />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function AttachmentChips({ attachments, onRemove }: {
  attachments: Attachment[]; onRemove: (id: string) => void
}) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
        letterSpacing: '0.08em', textTransform: 'uppercase',
        color: 'var(--fg-dim, #aaa)', marginBottom: 6,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <Paperclip size={11} />
        {attachments.length === 1
          ? '1 fichier joint au prochain message'
          : `${attachments.length} fichiers joints au prochain message`}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {attachments.map((a) => (
          <div key={a.id}
            title={a.previewUrl ? (a.visionText ? `Image — ${a.visionText.slice(0, 160)}…` : 'Image — analyse vision en cours…')
              : a.text ? `${a.name} — contenu lisible injecté` : `${a.name} — binaire (nom transmis uniquement)`}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 8px',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
              borderRadius: 8, fontSize: 11, color: 'var(--fg, #f5f5f5)',
            }}>
            {a.previewUrl
              ? <img src={a.previewUrl} alt={a.name} style={{ width: 24, height: 24, borderRadius: 4, objectFit: 'cover' }} />
              : <FileText size={11} />}
            <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</span>
            {a.previewUrl && !a.visionText && <span style={{ color: 'var(--fg-mute, #777)' }} title="Vision en cours…">👁 …</span>}
            <span style={{ color: 'var(--fg-mute, #777)' }}>
              {a.size > 1024 ? `${(a.size / 1024).toFixed(1)} ko` : `${a.size} o`}
            </span>
            <button type="button" onClick={() => onRemove(a.id)} title="Retirer"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: 'var(--fg-mute, #777)', padding: 2,
              }}>
              <X size={11} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
