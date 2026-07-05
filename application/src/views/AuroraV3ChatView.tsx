/**
 * AuroraV3ChatView — Ricochet "papier dactylographique" port.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-1.jsx (mock).
 * Real wiring goes through useChatViewLogic so every feature available in
 * Manga is preserved: attachments, vision, slash menu, bubble actions
 * (copy/edit/regen/pin/delete/narrate), <think> reveal, voice overlay,
 * Aurora-Connect web read, Markdown + PDF export, conversation clear,
 * stream stop. The aesthetic translates each affordance to typewriter
 * idioms (inverted-ink chips, carbon-paper attachments, RETOUR CHARIOT
 * separators, "VU PAR LE MAITRE" stamp).
 */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import MarkdownPro from '../components/MarkdownPro'
import { useChatViewLogic, stripThink, type Attachment } from '../hooks/useChatViewLogic'
import { useAppStore } from '../stores/appStore'
import { useFileDrop } from '../hooks/useFileDrop'
import { suggestCommands, getRecentSlash, type SlashCommand } from '../utils/slashCommands'
import { pickRandomStarter } from '../utils/randomChatStarters'
import { getDailyTip } from '../utils/dailyTip'
import { getContextUsage } from '../utils/modelContext'
import { useNotificationStore } from '../stores/notificationStore'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

const PAPER = '#f0e9d9'
const INK = '#1c1614'
const RED = '#c44'

function InkLabel({ children, color = INK }: { children: React.ReactNode; color?: string }) {
  return (
    <span style={{
      background: color, color: PAPER,
      padding: '0 6px', fontWeight: 700, fontSize: 11,
      letterSpacing: '0.05em',
    }}>{children}</span>
  )
}

function InkBtn({ onClick, active, danger, disabled, title, children }: {
  onClick?: () => void; active?: boolean; danger?: boolean; disabled?: boolean
  title?: string; children: React.ReactNode
}) {
  const bg = danger ? RED : active ? INK : 'transparent'
  const fg = danger || active ? PAPER : INK
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontFamily: 'Courier New, Courier, monospace',
        fontSize: 10, fontWeight: 700, letterSpacing: '0.15em',
        textTransform: 'uppercase',
        padding: '3px 8px',
        background: bg, color: fg,
        border: `1px solid ${INK}`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 4,
      }}>{children}</button>
  )
}

function PaperHoles() {
  return (
    <div style={{
      position: 'absolute', left: 14, top: 0, bottom: 0, width: 24,
      display: 'flex', flexDirection: 'column',
      justifyContent: 'space-around', padding: '40px 0',
      pointerEvents: 'none',
    }}>
      {Array.from({ length: 14 }).map((_, i) => (
        <div key={i} style={{
          width: 14, height: 14, borderRadius: '50%',
          background: '#d4cab8',
          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.3)',
        }} />
      ))}
    </div>
  )
}

function CarriageReturn() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      margin: '20px 0 12px', gap: 8,
      fontFamily: 'Courier New, Courier, monospace',
    }}>
      <span style={{ flex: 1, height: 0, borderTop: `1px dashed ${INK}` }} />
      <span style={{ fontSize: 10, letterSpacing: '0.3em' }}>RETOUR CHARIOT</span>
      <span style={{ flex: 1, height: 0, borderTop: `1px dashed ${INK}` }} />
    </div>
  )
}

function SlashMenu({ draft, onPick, slashIdx, setSlashIdx }: {
  draft: string
  onPick: (cmd: string) => void
  slashIdx: number
  setSlashIdx: (n: number) => void
}) {
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
  const recentSet = new Set(getRecentSlash())
  return (
    <div style={{
      marginBottom: 8, border: `2px solid ${INK}`,
      background: PAPER, fontFamily: 'Courier New, monospace',
    }}>
      <div style={{
        background: INK, color: PAPER, padding: '2px 8px',
        fontSize: 10, fontWeight: 700, letterSpacing: '0.2em',
      }}>COMMANDES · ↑↓ TAB/ENTRÉE · CLIC{recentSet.size > 0 ? ' · ★ RÉCENT' : ''}</div>
      {suggestions.map((s, ix) => (
        <button key={s.name} type="button"
          onMouseDown={(e) => { e.preventDefault(); onPick(s.name) }}
          onMouseEnter={() => setSlashIdx(ix)}
          style={{
            display: 'grid', gridTemplateColumns: '110px 1fr',
            width: '100%', textAlign: 'left', padding: '4px 8px',
            background: ix === slashIdx ? INK : 'transparent',
            color: ix === slashIdx ? PAPER : INK,
            border: 'none',
            borderBottom: `1px dashed ${INK}`,
            fontFamily: 'inherit',
            fontSize: 11, textTransform: 'uppercase', cursor: 'pointer',
          }}>
          <span style={{ fontWeight: 700, color: RED, display: 'flex', alignItems: 'center', gap: 4 }}>
            {recentSet.has(s.name) && <span style={{ fontSize: 9 }}>★</span>}
            /{s.name}
          </span>
          <span style={{ color: ix === slashIdx ? PAPER : INK }}>{s.description}</span>
        </button>
      ))}
    </div>
  )
}

export default function AuroraV3ChatView() {
  const L = useChatViewLogic()
  const profile = useAppStore((s) => s.profile)
  // v82eb : drag-drop parity V3 — fichier(s) → addFiles
  const drop = useFileDrop({
    onFiles: (files) => void L.addFiles(files),
    accept: ['txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'html', 'css', 'pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/json', 'image/'],
  })
  // v82am : "LE MAITRE" hardcodé du design source mock retiré.
  // Fallback sur le nom de profil utilisateur si défini, sinon "VOUS".
  const userLabel = (profile?.name && profile.name !== 'Utilisateur')
    ? profile.name.toUpperCase()
    : 'VOUS'
  const transcriptRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState('')
  // v82h7 : feedback transitoire pour le bouton COPY (✓/✗ 1.2s)
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null)
  // v82h9 : feedback per-bubble copy (parité v82h8)
  const [bubbleCopiedId, setBubbleCopiedId] = useState<string | null>(null)
  // v82eh : slash dropdown idx (parité V1)
  const [slashIdx, setSlashIdx] = useState(0)
  useEffect(() => { setSlashIdx(0) }, [L.draft])
  // v82fj : floating ↓ bottom button parité V1 v82fi.
  // v82gn : compteur "nouveaux" + respect scroll-up (parité v82gm).
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
  // v82gn : track new message arrivals tant que scrolledUp.
  // v82go : si la nouvelle message vient de l'user, reset unread + scroll bottom.
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

  // v82ij : Cmd+I focus composer (parité V1 v82ii).
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
  // v82hs : search-in-thread Ctrl+F (parité V1 v82hr).
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
  const threadSearchQ = threadSearchQuery.trim().toLowerCase()
  const threadMatchIndices = threadSearchQ
    ? L.messages.map((m, i) => (m.content || '').toLowerCase().includes(threadSearchQ) ? i : -1).filter((i) => i !== -1)
    : []
  const threadMatchCount = threadMatchIndices.length
  // v82hv : cursor pour Enter/Shift+Enter navigation.
  const [threadMatchCursor, setThreadMatchCursor] = useState(0)
  useEffect(() => { setThreadMatchCursor(0) }, [threadSearchQuery])
  const scrollToMatchIndex = (cursor: number) => {
    if (threadMatchIndices.length === 0) return
    const safeCursor = ((cursor % threadMatchIndices.length) + threadMatchIndices.length) % threadMatchIndices.length
    const msgIdx = threadMatchIndices[safeCursor]
    const transcript = transcriptRef.current
    if (!transcript) return
    const bubble = transcript.children[msgIdx + 1] as HTMLElement | undefined
    if (bubble) bubble.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // v82hq : toast notification quand thread passe safe → warn → danger.
  const lastLevelRef = useRef<'safe' | 'warn' | 'danger'>('safe')
  useEffect(() => {
    if (L.messages.length === 0) { lastLevelRef.current = 'safe'; return }
    const total = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
    const usage = getContextUsage(L.mainModel, total)
    const ranks = { safe: 0, warn: 1, danger: 2 } as const
    if (ranks[usage.level] > ranks[lastLevelRef.current]) {
      const push = useNotificationStore.getState().push
      if (usage.level === 'warn') {
        push({ level: 'warning', message: 'Contexte modèle 75% atteint',
          detail: `~${usage.tokens} / ${usage.limit} tokens.`, duration: 6000 })
      } else if (usage.level === 'danger') {
        push({ level: 'error', message: 'Contexte modèle 95% — truncation imminente',
          detail: `~${usage.tokens} / ${usage.limit} tokens.`, duration: 9000 })
      }
    }
    lastLevelRef.current = usage.level
  }, [L.messages.length, L.mainModel, L.messages])

  useEffect(() => {
    const el = transcriptRef.current
    // v82gn : ne yank pas si l'user lit du contexte ancien.
    if (el && !scrolledUp) el.scrollTop = el.scrollHeight
  }, [L.messages.length, L.streamContent, scrolledUp])

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // v82eh : keyboard nav slash dropdown
    const trimmed = L.draft.trim()
    const slashActive = trimmed.startsWith('/') && !trimmed.includes(' ')
    if (slashActive) {
      const sg = suggestCommands(trimmed)
      if (sg.length > 0) {
        if (e.key === 'Escape') {
          e.preventDefault()
          L.setDraft('') // v82ei : Esc annule l'entrée slash
          return
        }
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          setSlashIdx((i) => Math.min(sg.length - 1, i + 1))
          return
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          setSlashIdx((i) => Math.max(0, i - 1))
          return
        }
        if (e.key === 'Tab' || (e.key === 'Enter' && !e.metaKey && !e.ctrlKey)) {
          e.preventDefault()
          const cmd = sg[Math.min(slashIdx, sg.length - 1)]
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

  const fileNo = String(L.messages.length).padStart(3, '0')
  const now = new Date().toTimeString().slice(0, 8)

  return (
    <div {...drop.bind} style={{
      width: '100%', height: '100%',
      background: PAPER,
      fontFamily: 'Courier New, Courier, monospace',
      color: INK,
      padding: 28,
      position: 'relative',
      outline: drop.isDraggingOver ? `2px dashed ${RED}` : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      display: 'flex', flexDirection: 'column',
      backgroundImage: 'repeating-linear-gradient(0deg, transparent 0, transparent 27px, rgba(28,30,80,0.08) 27px, rgba(28,30,80,0.08) 28px)',
    }}>
      <PaperHoles />

      <div style={{
        position: 'absolute', left: 80, top: 0, bottom: 0,
        width: 1, background: RED, pointerEvents: 'none',
      }} />

      <div style={{ marginLeft: 70, flex: 1, display: 'flex',
                    flexDirection: 'column', minHeight: 0 }}>
        {/* Letterhead */}
        <div style={{
          borderBottom: `2px solid ${INK}`, paddingBottom: 8, marginBottom: 16,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          gap: 8, flexWrap: 'wrap',
        }}>
          <span style={{ fontWeight: 700, letterSpacing: '0.3em', fontSize: 14 }}>
            AURORA — DICTAPHONE
          </span>
          <span style={{ flex: 1 }} />
          <InkBtn onClick={() => void L.readActiveTab()} title="Lire la page web active">WEB</InkBtn>
          <InkBtn active={L.narrationOn} onClick={() => L.setNarrationOn(!L.narrationOn)} title="Narration auto">
            VOIX {L.narrationOn ? 'ON' : 'OFF'}
          </InkBtn>
          {/* v82h7 : parité copy MD au clipboard */}
          <InkBtn
            onClick={() => {
              void L.copyConversation().then((ok) => {
                setCopyFeedback(ok ? '✓' : '✗')
                window.setTimeout(() => setCopyFeedback(null), 1200)
              })
            }}
            title="Copier la conversation en Markdown au presse-papier">
            {copyFeedback ?? 'COPY'}
          </InkBtn>
          <InkBtn onClick={() => void L.exportConversation('markdown')} title="Export MD">MD</InkBtn>
          <InkBtn onClick={() => void L.exportConversation('pdf')} title="Export PDF">PDF</InkBtn>
          <InkBtn danger onClick={L.clearAll} title="Effacer">EFFACER</InkBtn>
          {/* v82hm + v82hn : total tokens + warning si proche limite */}
          {L.messages.length > 0 && (() => {
            const total = L.messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
            const usage = getContextUsage(L.mainModel, total)
            const color = usage.level === 'danger' ? RED
              : usage.level === 'warn' ? 'oklch(0.65 0.16 60)'
              : INK
            const pct = (usage.ratio * 100).toFixed(0)
            return <span
              title={`${total} caractères · ~${usage.tokens} tokens / ~${usage.limit} (${pct}%) · modèle ${L.mainModel.split('/').pop()}`}
              style={{
                fontSize: 11, fontFamily: 'Courier New, monospace',
                letterSpacing: '0.1em', color,
                fontWeight: usage.level === 'danger' ? 700 : 400,
              }}>
              ~{usage.tokens}T · {pct}%
            </span>
          })()}
          <span style={{ fontSize: 11 }}>
            FILE No. {fileNo} · {L.isStreaming ? 'LIVE' : 'CARBON COPY'}
          </span>
        </div>

        {/* Transcript */}
        {/* v82hs : floating search bar Ctrl+F */}
        {threadSearchOpen && (
          <div style={{
            position: 'absolute', top: 80, right: 24, zIndex: 50,
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 10px',
            background: PAPER, color: INK,
            border: `2px solid ${INK}`,
            boxShadow: `4px 4px 0 ${INK}`,
            fontFamily: 'Courier New, Courier, monospace', fontSize: 11,
          }}>
            <span>🔎</span>
            <input
              ref={threadSearchInputRef}
              type="text"
              value={threadSearchQuery}
              onChange={(e) => setThreadSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && threadMatchCount > 0) {
                  e.preventDefault()
                  const next = e.shiftKey ? threadMatchCursor - 1 : threadMatchCursor + 1
                  setThreadMatchCursor(next)
                  scrollToMatchIndex(next)
                }
              }}
              placeholder="CHERCHER… ↵ NEXT ⇧↵ PREV"
              style={{
                width: 240, padding: '4px 8px',
                background: PAPER, color: INK,
                border: `1px solid ${INK}`,
                outline: 'none',
                fontFamily: 'inherit', fontSize: 'inherit',
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }} />
            <span style={{
              fontSize: 10, fontVariantNumeric: 'tabular-nums',
              minWidth: 60, textAlign: 'right', letterSpacing: '0.1em',
            }}>{threadSearchQ
              ? `${threadMatchCount > 0 ? (((threadMatchCursor % threadMatchCount) + threadMatchCount) % threadMatchCount + 1) : 0}/${threadMatchCount}`
              : `${L.messages.length}`}</span>
            <button type="button"
              onClick={() => { setThreadSearchOpen(false); setThreadSearchQuery('') }}
              title="Fermer (Esc)"
              style={{
                width: 22, height: 22, padding: 0,
                background: PAPER, color: INK,
                border: `1px solid ${INK}`, cursor: 'pointer',
                fontSize: 11, fontFamily: 'inherit',
              }}>×</button>
          </div>
        )}
        <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', minHeight: 0,
                                          paddingRight: 12 }}>
          {L.messages.length === 0 && (
            <div style={{
              padding: '40px 0', maxWidth: '70ch',
              fontSize: 14, lineHeight: '28px',
            }}>
              <InkLabel>READY</InkLabel>{' '}DICTEZ VOTRE PREMIERE LIGNE
              CI-DESSOUS — CTRL+ENTER POUR ENVOYER.
              {/* v82fw : daily tip stencil-style Ricochet */}
              <div style={{
                marginTop: 24, padding: '8px 12px',
                fontSize: 11, fontFamily: 'Courier New, monospace',
                color: INK,
                background: PAPER,
                border: `1px solid ${INK}`,
                borderRadius: 0, lineHeight: 1.5,
                display: 'inline-block',
              }}>
                {getDailyTip('chat')}
              </div>
            </div>
          )}
          {L.messages.map((m, i) => {
            const id = String(m.id ?? m.timestamp ?? i)
            const isAsst = m.role === 'assistant'
            const accent = isAsst ? RED : INK
            const fromText = isAsst ? `AURORA · ${L.who.toUpperCase()}` : userLabel
            const { visible, thinking } = stripThink(m.content)
            const isEditing = editingId === m.id
            const isLast = i === L.messages.length - 1
            // v82hs : visibility filter selon search query.
            const isMatchSearch = !threadSearchQ
              || (m.content || '').toLowerCase().includes(threadSearchQ)
            return (
              <div key={m.id || i} style={{
                opacity: isMatchSearch ? 1 : 0.25,
                transition: 'opacity .18s ease',
              }}>
                <div style={{ marginBottom: 16, fontFamily: 'Courier New, Courier, monospace' }}>
                  <div style={{ marginBottom: 8, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                    <InkLabel color={accent}>FROM</InkLabel>
                    <span style={{ color: accent, fontWeight: 700 }}>{fromText}</span>
                    <span>·</span>
                    <InkLabel color={accent}>TIME</InkLabel>
                    <span>{m.timestamp ? new Date(m.timestamp).toTimeString().slice(0, 8) : now}</span>
                    {isAsst && <>
                      <span>·</span>
                      <InkLabel color={accent}>MOD</InkLabel>
                      <span>{(L.mainModel.split('/').pop() || L.mainModel).toUpperCase()}</span>
                    </>}
                    {/* v82hl : token count par bubble (parité V1 v82hk) */}
                    {(visible || m.content).length > 80 && <>
                      <span>·</span>
                      <InkLabel color={accent}>TOK</InkLabel>
                      <span title={`${(visible || m.content).length} caractères · estimation 4ch/token`}>
                        ~{Math.ceil((visible || m.content).length / 4)}
                      </span>
                    </>}
                    {m.pinned && <InkLabel color={RED}>VU PAR LE MAITRE</InkLabel>}
                    {m.edited && <span style={{ fontSize: 10, fontStyle: 'italic' }}>(corrigé)</span>}
                  </div>
                  {thinking && (
                    <details style={{
                      margin: '4px 0 8px 12px', fontSize: 12,
                      borderLeft: `2px dashed ${INK}`, paddingLeft: 10,
                    }}>
                      <summary style={{ cursor: 'pointer', fontSize: 10, letterSpacing: '0.2em' }}>
                        PENSEE BRUTE
                      </summary>
                      <div style={{
                        whiteSpace: 'pre-wrap', textTransform: 'uppercase',
                        marginTop: 4, opacity: 0.7,
                      }}>{thinking}</div>
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
                          width: '100%', maxWidth: '70ch',
                          fontFamily: 'Courier New, monospace', fontSize: 14, lineHeight: '24px',
                          background: 'transparent', color: INK,
                          border: `1px dashed ${INK}`, padding: 8, resize: 'vertical',
                          textTransform: 'uppercase',
                        }}
                      />
                      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                        <InkBtn onClick={saveEdit}>✓ ENREGISTRER</InkBtn>
                        <InkBtn onClick={() => setEditingId(null)}>× ANNULER</InkBtn>
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      fontSize: 14, lineHeight: '28px', color: INK,
                      textTransform: isAsst ? 'none' : 'uppercase',
                      maxWidth: '70ch',
                      whiteSpace: isAsst ? undefined : 'pre-wrap',
                      wordBreak: 'break-word',
                      ...(m.pinned ? { background: 'rgba(196,68,68,0.05)', padding: 4 } : {}),
                    }}>
                      {isAsst
                        ? <MarkdownPro content={visible || m.content} idPrefix={`v3-bubble-${id}`} />
                        : (visible || m.content)}
                    </div>
                  )}
                  {!isEditing && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                      {isAsst && (
                        <InkBtn active={L.narrating === id}
                          onClick={() => L.narrating === id
                            ? L.stopNarration()
                            : L.narrate(visible || m.content, id)}
                          title="Lire">
                          {L.narrating === id ? '◼ STOP' : '▶ LIRE'}
                        </InkBtn>
                      )}
                      <InkBtn onClick={() => {
                        void navigator.clipboard.writeText(visible || m.content).then(() => {
                          setBubbleCopiedId(m.id ?? null)
                          window.setTimeout(() => setBubbleCopiedId(null), 1200)
                        })
                      }} title="Copier le texte brut au presse-papier">{bubbleCopiedId === m.id ? '✓ COPIÉ' : '⎘ COPIER'}</InkBtn>
                      {m.id && <InkBtn onClick={() => startEdit(m)} title="Éditer">✎ CORRIGER</InkBtn>}
                      {isAsst && isLast && (
                        <InkBtn onClick={L.onRegenerate} title="Régénérer">↻ RECTAPER</InkBtn>
                      )}
                      {m.id && (
                        <InkBtn active={m.pinned}
                          onClick={() => L.togglePinned(m.id!)}
                          title={m.pinned ? 'Détacher' : 'Épingler'}>
                          ★ {m.pinned ? 'OTER' : 'PIN'}
                        </InkBtn>
                      )}
                      {m.id && (
                        <InkBtn danger onClick={() => {
                          if (window.confirm('Supprimer ce message ?')) L.removeMessage(m.id!, !isAsst)
                        }} title="Supprimer">🗑 BIFFER</InkBtn>
                      )}
                    </div>
                  )}
                </div>
                {i < L.messages.length - 1 && <CarriageReturn />}
              </div>
            )
          })}
          {L.isStreaming && (
            <>
              {L.messages.length > 0 && <CarriageReturn />}
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>
                  <InkLabel color={RED}>FROM</InkLabel>{' '}
                  <span style={{ color: RED, fontWeight: 700 }}>AURORA</span>
                  {' · '}<InkLabel color={RED}>TIME</InkLabel>{' '}{now}
                  {' · '}<InkLabel color={RED}>MOD</InkLabel>{' '}{(L.mainModel.split('/').pop() || L.mainModel).toUpperCase()}
                </div>
                <div style={{ fontSize: 14, lineHeight: '28px', maxWidth: '70ch' }}>
                  {L.streamingVisible
                    ? <MarkdownPro content={L.streamingVisible} />
                    : <span style={{ letterSpacing: '0.3em' }}>… … …</span>}
                  {L.streamingVisible && <span style={{
                    display: 'inline-block', width: 10, height: 14, marginLeft: 4,
                    verticalAlign: 'text-bottom', background: INK,
                    animation: 'caret 1s steps(2) infinite',
                  }} />}
                </div>
              </div>
            </>
          )}
        </div>

        {/* v82fj : floating ↓ bottom (parité V1) · v82gn : compteur unread */}
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
              position: 'absolute', right: 28, bottom: 220, zIndex: 50,
              minWidth: 36, height: 36,
              padding: unreadCount > 0 ? '0 14px' : 0,
              borderRadius: 18,
              background: INK, color: PAPER,
              border: `2px solid ${INK}`,
              boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              fontSize: 14, fontWeight: 700,
              fontFamily: 'Permanent Marker, Marker Felt, cursive',
              transition: 'padding .18s ease, min-width .18s ease',
            }}>
            ↓{unreadCount > 0 && <span style={{ fontSize: 14 }}>{unreadCount}</span>}
          </button>
        )}
        {/* Composer */}
        <div style={{ borderTop: `2px solid ${INK}`, paddingTop: 12, marginTop: 12 }}>
          {L.attachments.length > 0 && <V3AttachmentChips attachments={L.attachments} onRemove={L.removeAttachment} />}
          <SlashMenu
            draft={L.draft}
            onPick={(cmd) => { L.setDraft(`/${cmd} `); textareaRef.current?.focus() }}
            slashIdx={slashIdx}
            setSlashIdx={setSlashIdx}
          />
          <input ref={fileInputRef} type="file" multiple hidden
            accept=".txt,.md,.markdown,.json,.csv,.log,.py,.js,.ts,.html,.css,.sh,.tex,.xml,.yaml,image/*"
            onChange={onFileChange} />
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap',
          }}>
            <InkLabel>TYPE&gt;</InkLabel>
            <textarea
              ref={textareaRef}
              value={L.draft}
              onChange={(e) => L.setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder=""
              rows={1}
              disabled={L.isStreaming}
              style={{
                flex: 1, minWidth: 200,
                fontSize: 14, lineHeight: '20px',
                fontFamily: 'Courier New, Courier, monospace',
                color: INK, background: 'transparent',
                border: 'none', borderBottom: `1px solid ${INK}`,
                outline: 'none', resize: 'none',
                textTransform: 'uppercase',
              }}
            />
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              <InkBtn onClick={() => fileInputRef.current?.click()} title="Joindre">📎 JOINDRE</InkBtn>
              <InkBtn onClick={L.openVoice} title="Voix">🎙 VOIX</InkBtn>
              {L.narrating && <InkBtn danger onClick={L.stopNarration}>◼ STOP VOIX</InkBtn>}
              {L.isStreaming ? (
                <InkBtn danger onClick={L.onStop}>◼ STOP</InkBtn>
              ) : (
                <>
                  <InkBtn
                    onClick={() => void L.onSend()}
                    disabled={!L.draft.trim() && L.attachments.length === 0}
                    title="Envoyer">
                    {L.isStreaming ? '…' : '▶ ENVOYER ↵'}
                  </InkBtn>
                  {/* v82fd + v82fe : conversation starter aléatoire + auto-send (pool mutualisé V1+V3) */}
                  <InkBtn
                    onClick={() => { void L.onSend(false, pickRandomStarter()) }}
                    title="Lance une conversation au hasard">
                    ⚡ SURPRISE
                  </InkBtn>
                </>
              )}
            </div>
            <span style={{ fontSize: 10, letterSpacing: '0.2em' }}>CTRL+ENTER</span>
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
              background: PAPER,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
            <button type="button" onClick={L.closeVoice} title="Fermer"
              style={{
                position: 'absolute', top: 16, right: 16,
                background: INK, color: PAPER, border: 'none', padding: '6px 12px',
                fontFamily: 'Courier New, monospace', fontWeight: 700,
                letterSpacing: '0.2em', cursor: 'pointer',
              }}>× FERMER</button>
            <Suspense fallback={<div style={{ color: INK, fontFamily: 'Courier New, monospace' }}>INVOCATION DU COPILOTE VOCAL…</div>}>
              <VoiceCopilotView />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`@keyframes caret { 50% { opacity: 0 } }`}</style>
    </div>
  )
}

function V3AttachmentChips({ attachments, onRemove }: {
  attachments: Attachment[]; onRemove: (id: string) => void
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{
        fontSize: 10, letterSpacing: '0.2em', marginBottom: 4,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <InkLabel>ANNEXE</InkLabel>
        <span>
          {attachments.length === 1
            ? '1 PIECE JOINTE AU PROCHAIN MESSAGE'
            : `${attachments.length} PIECES JOINTES AU PROCHAIN MESSAGE`}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {attachments.map((a) => (
          <div key={a.id}
            title={a.previewUrl ? (a.visionText ? `Image — ${a.visionText.slice(0, 160)}…` : 'Image — analyse vision en cours…')
              : a.text ? `${a.name} — contenu lisible injecté` : `${a.name} — binaire (nom transmis uniquement)`}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 6px',
              background: PAPER, border: `1px solid ${INK}`,
              fontSize: 11, color: INK,
              fontFamily: 'Courier New, monospace',
            }}>
            {a.previewUrl
              ? <img src={a.previewUrl} alt={a.name} style={{ width: 22, height: 22, objectFit: 'cover', filter: 'sepia(0.4)' }} />
              : <span style={{ fontSize: 12 }}>📄</span>}
            <span style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textTransform: 'uppercase' }}>{a.name}</span>
            {a.previewUrl && !a.visionText && <span style={{ fontStyle: 'italic' }}>👁…</span>}
            <span style={{ fontSize: 10 }}>
              {a.size > 1024 ? `${(a.size / 1024).toFixed(1)}KO` : `${a.size}O`}
            </span>
            <button type="button" onClick={() => onRemove(a.id)} title="Retirer"
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: INK, padding: 0, fontSize: 12, fontWeight: 700,
              }}>×</button>
          </div>
        ))}
      </div>
    </div>
  )
}
