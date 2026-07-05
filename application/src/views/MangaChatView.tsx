import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Mic, Paperclip, Send, StopCircle, Trash2, Volume2, VolumeX, Wand2, X, Cpu, Copy, RefreshCw, Radio } from 'lucide-react'
import { useChatStore } from '../stores/chatStore'
import { useAppStore } from '../stores/appStore'
import { runConversationTurn } from '../services/conversationOrchestrator'
import type { ChatMessage } from '../types/app'
import { getErrorMessage } from '../utils/errors'
import { speakify } from '../utils/speakify'
import MarkdownPro from '../components/MarkdownPro'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { pickRandomStarter } from '../utils/randomChatStarters'
import { getContextUsage } from '../utils/modelContext'
import { useNotificationStore } from '../stores/notificationStore'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))

type Attachment = {
  id: string
  name: string
  size: number
  type: string
  text?: string       // extracted text if available
  previewUrl?: string // data URL for images (prompt preview + vision)
  visionText?: string // Qwen3-VL description, injected into the LLM context
}

type Character = 'natsu' | 'lucy'

const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

const WELCOME: Record<Character, string> = {
  natsu: "Hé. Copilote local prêt. J'suis tout feu tout flamme — qu'est-ce qu'on brûle aujourd'hui ?",
  lucy:  "Ouvre-toi, Porte de l'Informatique ! Copilote prêt. Qu'est-ce que tu veux invoquer ?",
}

function readCharacter(): Character {
  try {
    const v = window.localStorage.getItem('ft-who')
    return v === 'lucy' ? 'lucy' : 'natsu'
  } catch {
    return 'natsu'
  }
}

function stripThink(raw: string): { visible: string; thinking: string | null } {
  let visible = raw
  const parts: string[] = []
  visible = visible.replace(/<think>([\s\S]*?)<\/think>/g, (_m, c) => { parts.push(c.trim()); return '' })
  const open = visible.lastIndexOf('<think>')
  let thinking = parts.length > 0 ? parts.join('\n') : null
  if (open !== -1) {
    thinking = (thinking ? thinking + '\n' : '') + visible.slice(open + 7).trim()
    visible = visible.slice(0, open)
  }
  return { visible: visible.trim(), thinking }
}

function SlashCommandMenu({ draft, onPick }: { draft: string; onPick: (cmd: string) => void }) {
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
    <div className="mc-slash-menu" role="listbox">
      {suggestions.map((s) => (
        <button
          key={s.name}
          type="button"
          className="mc-slash-item"
          onMouseDown={(e) => { e.preventDefault(); onPick(s.name) }}>
          <span className="mc-slash-name">/{s.name}</span>
          <span className="mc-slash-desc">{s.description}</span>
          <span className="mc-slash-example">{s.example}</span>
        </button>
      ))}
    </div>
  )
}

function Bubble({ msg, who, onNarrate, isNarrating, onCopy, copyFeedback, onRegen, onEdit, onDelete, onPin }: {
  msg: ChatMessage
  who: Character
  onNarrate?: () => void
  isNarrating?: boolean
  onCopy?: () => void
  copyFeedback?: string | null
  onRegen?: () => void
  onEdit?: (newContent: string) => void
  onDelete?: () => void
  onPin?: () => void
}) {
  const isUser = msg.role === 'user'
  const { visible, thinking } = stripThink(msg.content)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(visible || msg.content)

  const saveEdit = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== (visible || msg.content)) {
      onEdit?.(trimmed)
    }
    setEditing(false)
  }

  return (
    <div className={`mc-msg ${isUser ? 'is-user' : 'is-assistant'} ${msg.pinned ? 'is-pinned' : ''}`}>
      {!isUser && (
        <div className="mc-msg-avatar">
          <img src={PORTRAITS[who]} alt={who} />
        </div>
      )}
      <div className="mc-msg-content">
        {msg.pinned && <span className="mc-msg-pin-badge" title="Épinglé">📌</span>}
        {/* v82ho : timestamp + token estimate per-bubble (parité V1/V3) */}
        {(msg.timestamp || (visible || msg.content).length > 80) && (
          <div style={{
            display: 'flex', gap: 8, alignItems: 'baseline',
            fontFamily: 'var(--font-mono, ui-monospace, monospace)',
            fontSize: 9, color: 'rgba(0,0,0,0.45)',
            fontVariantNumeric: 'tabular-nums', marginBottom: 4,
            letterSpacing: '0.05em',
          }}>
            {msg.timestamp && (
              <span title={new Date(msg.timestamp).toLocaleString('fr-FR')}>
                {new Date(msg.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {(visible || msg.content).length > 80 && (
              <span title={`${(visible || msg.content).length} caractères · ~${Math.ceil((visible || msg.content).length / 4)} tokens (estimation)`}>
                ~{Math.ceil((visible || msg.content).length / 4)}t
              </span>
            )}
          </div>
        )}
        {thinking && (
          <details className="mc-msg-thinking">
            <summary>thinking</summary>
            <div className="mc-msg-thinking-body">{thinking}</div>
          </details>
        )}
        <div className="mc-msg-bubble">
          {editing ? (
            <div className="mc-msg-editor">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={Math.min(10, draft.split('\n').length + 1)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); saveEdit() }
                  else if (e.key === 'Escape') { e.preventDefault(); setEditing(false); setDraft(visible || msg.content) }
                }}
              />
              <div className="mc-msg-editor-actions">
                <button type="button" className="mc-msg-action" onClick={saveEdit}>✓ enregistrer</button>
                <button type="button" className="mc-msg-action" onClick={() => { setEditing(false); setDraft(visible || msg.content) }}>× annuler</button>
              </div>
            </div>
          ) : isUser ? (
            <>
              {visible || msg.content}
              {msg.edited && <span className="mc-msg-edited">(modifié)</span>}
            </>
          ) : (
            <MarkdownPro content={visible || msg.content} idPrefix={`bubble-${msg.id || msg.timestamp}`} />
          )}
        </div>
        {!editing && (
          <div className="mc-msg-actions">
            {!isUser && onNarrate && (
              <button
                type="button"
                className={`mc-msg-action ${isNarrating ? 'is-active' : ''}`}
                onClick={onNarrate}
                title={isNarrating ? 'Stopper la lecture' : 'Lire à voix haute'}
              >
                {isNarrating
                  ? <><VolumeX size={11} strokeWidth={2.2} /> stop</>
                  : <><Volume2 size={11} strokeWidth={2.2} /> lire</>}
              </button>
            )}
            {onCopy && (
              <button type="button" className="mc-msg-action" onClick={onCopy}
                title="Copier le texte brut au presse-papier">
                {copyFeedback
                  ? <>{copyFeedback} copié</>
                  : <><Copy size={11} strokeWidth={2.2} /> copier</>}
              </button>
            )}
            {onEdit && (
              <button type="button" className="mc-msg-action"
                onClick={() => { setDraft(visible || msg.content); setEditing(true) }}
                title="Éditer">
                ✎ éditer
              </button>
            )}
            {onRegen && (
              <button type="button" className="mc-msg-action" onClick={onRegen} title="Régénérer">
                <RefreshCw size={11} strokeWidth={2.2} /> régén
              </button>
            )}
            {onPin && (
              <button type="button" className={`mc-msg-action ${msg.pinned ? 'is-active' : ''}`} onClick={onPin}
                title={msg.pinned ? 'Détacher' : 'Épingler'}>
                📌 {msg.pinned ? 'ôter' : 'pin'}
              </button>
            )}
            {onDelete && (
              <button type="button" className="mc-msg-action"
                onClick={() => { if (window.confirm('Supprimer ce message ?')) onDelete() }}
                title="Supprimer">
                🗑 suppr
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function MangaChatView() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const h = () => setWho(readCharacter())
    window.addEventListener('storage', h)
    const t = window.setInterval(h, 800)
    return () => { window.removeEventListener('storage', h); window.clearInterval(t) }
  }, [])

  const {
    messages, isStreaming, streamContent,
    addMessage, setStreaming, setStreamContent, appendStreamContent,
    startRun, setRunStage, setRunAnalysis, setRunVerification, finishRun, failRun, clearMessages, popLastAssistantTurn,
    updateMessage, removeMessage, togglePinned,
  } = useChatStore()
  const mainModel = useAppStore((s) => s.mainModel)

  const [draft, setDraft] = useState('')
  const [narrationOn, setNarrationOn] = useState(false)
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // v82fj : scroll-to-bottom floating button (parité V1+V3)
  // v82gn : compteur "nouveaux" + respect scroll-up (parité v82gm).
  const [scrolledUp, setScrolledUp] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  // v82h7 : feedback transitoire bouton copy MD (✓/✗ 1.2s)
  const [mdCopyFeedback, setMdCopyFeedback] = useState<string | null>(null)
  // v82h9 : feedback per-bubble copy.
  const [bubbleCopiedId, setBubbleCopiedId] = useState<string | null>(null)
  useEffect(() => {
    const el = threadRef.current
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

  // Auto-scroll to bottom when stream progresses (sauf si user remonté)
  useEffect(() => {
    const el = threadRef.current
    if (!el) return
    if (!scrolledUp) el.scrollTop = el.scrollHeight
  }, [messages.length, streamContent, scrolledUp])

  // v82gn : track new message arrivals tant que scrolledUp.
  // v82go : si la nouvelle message vient de l'user, reset unread + scroll bottom.
  const lastSeenLen = useRef(messages.length)
  useEffect(() => {
    const len = messages.length
    if (len > lastSeenLen.current) {
      const newest = messages[len - 1]
      const isUserMsg = newest?.role === 'user'
      if (isUserMsg) {
        setUnreadCount(0)
        setScrolledUp(false)
        const el = threadRef.current
        if (el) el.scrollTop = el.scrollHeight
      } else if (scrolledUp) {
        setUnreadCount((n) => n + (len - lastSeenLen.current))
      }
    }
    lastSeenLen.current = len
  }, [messages.length, scrolledUp, messages])
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
  // v82hs : search-in-thread Ctrl+F (parité V1/V3 v82hr).
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
    ? messages.map((m, i) => (m.content || '').toLowerCase().includes(threadSearchQ) ? i : -1).filter((i) => i !== -1)
    : []
  const threadMatchCount = threadMatchIndices.length
  // v82hv : cursor + scroll navigation.
  const [threadMatchCursor, setThreadMatchCursor] = useState(0)
  useEffect(() => { setThreadMatchCursor(0) }, [threadSearchQuery])
  const scrollToMatchIndex = (cursor: number) => {
    if (threadMatchIndices.length === 0) return
    const safeCursor = ((cursor % threadMatchIndices.length) + threadMatchIndices.length) % threadMatchIndices.length
    const msgIdx = threadMatchIndices[safeCursor]
    const thread = threadRef.current
    if (!thread) return
    const bubble = thread.children[msgIdx] as HTMLElement | undefined
    if (bubble) bubble.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // v82hq : toast notification quand thread passe safe → warn → danger.
  const lastLevelRef = useRef<'safe' | 'warn' | 'danger'>('safe')
  useEffect(() => {
    if (messages.length === 0) { lastLevelRef.current = 'safe'; return }
    const total = messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
    const usage = getContextUsage(mainModel, total)
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
  }, [messages.length, mainModel, messages])
  // v82fk + v82fl + v82fm : keyboard "End"/"Home"/"PageUp"/"PageDown".
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return
      const isNav = e.key === 'End' || e.key === 'Home' || e.key === 'PageDown' || e.key === 'PageUp'
      if (!isNav) return
      const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const el = threadRef.current
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

  // Textarea auto-height
  useEffect(() => {
    const t = textareaRef.current
    if (!t) return
    t.style.height = 'auto'
    t.style.height = Math.min(180, t.scrollHeight) + 'px'
  }, [draft])

  const onSend = async (voiceMode: boolean = false, overrideText?: string) => {
    const rawText = (overrideText ?? draft).trim()
    if ((!rawText && attachments.length === 0) || isStreaming) return
    if (overrideText === undefined) setDraft('')
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    // Slash-commands rewrite the prompt before it hits the LLM. The user
    // still sees `/fiche Dérivées` in their history but the model receives
    // the full detailed instruction, so shortcuts don't dumb down responses.
    let text = rawText
    if (rawText.startsWith('/')) {
      try {
        const mod = await import('../utils/slashCommands')
        text = mod.applySlashCommand(rawText)
      } catch { /* fallback to raw text */ }
    }

    // Attach any file contents as a context block. Text files paste their
    // content; images paste the vision-model description produced by Qwen3-VL
    // so the text-only LLM can reason about them.
    let composed = text
    if (attachments.length > 0) {
      const parts: string[] = []
      for (const a of attachments) {
        if (a.text) {
          parts.push(`--- FICHIER JOINT : ${a.name} ---\n${a.text}\n--- FIN ${a.name} ---`)
        } else if (a.visionText) {
          parts.push(`--- IMAGE JOINTE : ${a.name} ---\n(description vision) ${a.visionText}\n--- FIN ${a.name} ---`)
        } else if (a.previewUrl) {
          parts.push(`--- IMAGE JOINTE : ${a.name} --- (vision indisponible, décris à l'utilisateur que tu peux voir le fichier mais sans le modèle vision)`)
        }
      }
      const attachBlocks = parts.join('\n\n')
      composed = attachBlocks ? (text ? `${text}\n\n${attachBlocks}` : attachBlocks) : text
      setAttachments([])
    }

    addMessage({ role: 'user', content: composed || text })
    setStreaming(true)
    setStreamContent('')
    startRun()

    const payload = composed || text
    const userMsg: ChatMessage = { id: 'u', role: 'user', content: payload, timestamp: Date.now() }
    const history: ChatMessage[] = [...messages, userMsg]

    try {
      const result = await runConversationTurn({
        model: mainModel,
        messages: history,
        userInput: payload,
        voiceMode,
        signal: abortRef.current.signal,
        onEvent: (ev) => {
          if (ev.type === 'stage') setRunStage(ev.stage, ev.label, ev.detail, ev.progress, ev.timelineStatus)
          else if (ev.type === 'analysis') setRunAnalysis(ev.analysis)
          else if (ev.type === 'verification') setRunVerification(ev.verification)
        },
        onToken: (tok) => appendStreamContent(tok),
      })
      addMessage({ role: 'assistant', content: result.finalText })
      finishRun()
      setStreamContent('')
      if (narrationOn) void narrate(result.finalText)
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        setStreamContent('')
      } else {
        const detail = getErrorMessage(err)
        failRun(detail)
        addMessage({ role: 'assistant', content: `⚠️ Erreur : ${detail}` })
      }
    } finally {
      setStreaming(false)
    }
  }

  const onStop = () => { abortRef.current?.abort() }

  const onRegenerate = () => {
    const lastText = popLastAssistantTurn()
    if (lastText) void onSend(false, lastText)
  }

  // Narration via Web Speech API, avec expansion des symboles scientifiques/littéraires
  const [narrating, setNarrating] = useState<string | null>(null)   // id du message en cours
  const frVoiceRef = useRef<SpeechSynthesisVoice | null>(null)
  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const pick = () => {
      const voices = window.speechSynthesis.getVoices()
      if (!voices.length) return
      const fr =
        voices.find((v) => /^fr-FR$/i.test(v.lang)) ||
        voices.find((v) => /^fr[-_]/i.test(v.lang)) ||
        voices.find((v) => /fr/i.test(v.lang))
      if (fr) frVoiceRef.current = fr
    }
    pick()
    window.speechSynthesis.addEventListener('voiceschanged', pick)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', pick)
  }, [])

  const narrate = (text: string, id?: string) => {
    try {
      if (!('speechSynthesis' in window)) return
      const prepared = speakify(text)
      if (!prepared.trim()) return
      window.speechSynthesis.cancel()

      // Chunk on paragraph boundaries so Chrome doesn't truncate long utterances
      const chunks = prepared
        .split(/\n{2,}|(?<=[.!?])\s+(?=[A-ZÀ-Ö])/g)
        .map((s) => s.trim())
        .filter(Boolean)

      if (chunks.length === 0) return
      const currentId = id ?? 'live'
      setNarrating(currentId)

      const speakNext = (i: number) => {
        if (i >= chunks.length) { setNarrating((cur) => (cur === currentId ? null : cur)); return }
        const u = new SpeechSynthesisUtterance(chunks[i])
        u.lang = 'fr-FR'
        u.rate = 0.98
        u.pitch = 1.0
        if (frVoiceRef.current) u.voice = frVoiceRef.current
        u.onend = () => speakNext(i + 1)
        u.onerror = () => setNarrating((cur) => (cur === currentId ? null : cur))
        window.speechSynthesis.speak(u)
      }
      speakNext(0)
    } catch {
      setNarrating(null)
    }
  }
  const stopNarration = () => {
    try { window.speechSynthesis.cancel() } catch { /* ignore */ }
    setNarrating(null)
  }
  useEffect(() => () => { try { window.speechSynthesis.cancel() } catch { /* ignore */ } }, [])

  const TEXT_LIKE = /\.(txt|md|markdown|json|csv|tsv|log|xml|yaml|yml|ini|conf|py|js|ts|tsx|jsx|html|css|scss|sh|bash|zsh|c|h|cpp|hpp|java|go|rs|rb|php|sql|toml)$/i
  const IMAGE_LIKE = /^image\/(png|jpe?g|webp|gif|bmp|avif)$/i
  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length === 0) return
    const next: Attachment[] = []
    for (const f of files) {
      const isImage = IMAGE_LIKE.test(f.type) || /\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(f.name)
      const canRead = f.type.startsWith('text/') || TEXT_LIKE.test(f.name) || f.type === 'application/json'
      let text: string | undefined
      let previewUrl: string | undefined
      if (canRead) {
        try {
          text = await f.text()
          if (text.length > 200000) text = text.slice(0, 200000) + '\n\n[... fichier tronqué ...]'
        } catch { /* ignore */ }
      } else if (isImage) {
        try {
          previewUrl = await new Promise<string>((resolve, reject) => {
            const r = new FileReader()
            r.onload = () => resolve(String(r.result))
            r.onerror = () => reject(r.error)
            r.readAsDataURL(f)
          })
        } catch { /* ignore */ }
      }
      const attachment: Attachment = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name,
        size: f.size,
        type: f.type || 'application/octet-stream',
        text,
        previewUrl,
      }
      next.push(attachment)
    }
    setAttachments((prev) => [...prev, ...next])
    e.target.value = ''
    // After render, kick off async vision description for every new image.
    // Results mutate state as they come back (non-blocking UX).
    for (const a of next) {
      if (a.previewUrl) {
        void (async () => {
          try {
            const mod = await import('../services/visionService')
            const description = await mod.analyzeLiveSnapshot(
              a.previewUrl!,
              `Décris précisément l'image jointe par l'utilisateur : ${a.name}`,
            )
            setAttachments((prev) => prev.map((x) =>
              x.id === a.id ? { ...x, visionText: description } : x,
            ))
          } catch { /* vision offline → attachment still visible as image */ }
        })()
      }
    }
  }
  const removeAttachment = (id: string) =>
    setAttachments((prev) => prev.filter((a) => a.id !== id))

  const openVoice = () => setVoiceOpen(true)
  const closeVoice = () => setVoiceOpen(false)

  // v82h7 : helper interne pour réutilisation export + copy.
  const buildConversationMarkdown = (): string => {
    const who = readCharacter()
    const ts = new Date().toISOString().slice(0, 10)
    const header = `# Conversation · ${who} · ${ts}\n\n`
    const body = messages.map((m) => {
      const visible = stripThink(m.content).visible || m.content
      const label = m.role === 'user' ? '👤 **Toi**' : `✦ **${who === 'natsu' ? 'Natsu' : 'Lucy'}**`
      return `${label}\n\n${visible}\n`
    }).join('\n---\n\n')
    return header + body
  }

  // v82h7 : copy conversation au presse-papier (parité V1).
  const copyConversation = async (): Promise<boolean> => {
    if (messages.length === 0) return false
    if (typeof navigator === 'undefined' || !navigator.clipboard) return false
    try {
      await navigator.clipboard.writeText(buildConversationMarkdown())
      return true
    } catch { return false }
  }

  const exportConversation = async (format: 'markdown' | 'pdf') => {
    if (messages.length === 0) return
    const who = readCharacter()
    const ts = new Date().toISOString().slice(0, 10)
    const md = buildConversationMarkdown()
    if (format === 'markdown') {
      const blob = new Blob([md], { type: 'text/markdown; charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `conversation_${who}_${ts}.md`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 2000)
      return
    }
    // PDF via printElement — build a tidy HTML
    const container = document.createElement('div')
    container.innerHTML = `<h1>Conversation · ${who} · ${ts}</h1>` + messages.map((m) => {
      const visible = stripThink(m.content).visible || m.content
      const html = visible.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
      return `<div style="margin:10px 0;padding:10px 12px;border:2px solid #1a0f05;background:${m.role === 'user' ? '#b5241e' : '#fff'};color:${m.role === 'user' ? '#fff' : '#1a0f05'};border-radius:8px">
        <b>${m.role === 'user' ? '👤 Toi' : `✦ ${who === 'natsu' ? 'Natsu' : 'Lucy'}`}</b><br>${html}
      </div>`
    }).join('')
    const mod = await import('../utils/exportPdf')
    mod.printElement(container, {
      title: `Conversation · ${who}`,
      subtitle: ts,
      footer: `juan of bike IA · ${messages.length} messages`,
    })
  }

  const streamingVisible = useMemo(() => stripThink(streamContent).visible, [streamContent])

  return (
    <div className="mc-root">
      {/* Header */}
      <header className="mc-header">
        <div className="mc-header-left">
          <div className="mc-header-avatar">
            <img src={PORTRAITS[who]} alt={who} />
          </div>
          <div className="mc-header-ident">
            <div className="mc-header-kicker">Copilote IA · {who === 'natsu' ? 'Natsu' : 'Lucy'}</div>
            <div className="mc-header-title">Chat</div>
          </div>
        </div>
        <div className="mc-header-right">
          {/* v82ho : tokens cumulés + warning limite contexte (parité V1/V3) */}
          {messages.length > 0 && (() => {
            const total = messages.reduce((s, m) => s + (m.content?.length ?? 0), 0)
            const usage = getContextUsage(mainModel, total)
            const color = usage.level === 'danger'
              ? 'oklch(0.62 0.20 25)'
              : usage.level === 'warn'
              ? 'oklch(0.78 0.16 80)'
              : undefined
            const pct = (usage.ratio * 100).toFixed(0)
            return <span className="mc-pill"
              title={`${total} caractères · ~${usage.tokens} tokens / ~${usage.limit} (${pct}%)`}
              style={color ? { color, borderColor: `${color}80` } : undefined}>
              ~{usage.tokens}t · {pct}%
            </span>
          })()}
          <span className="mc-pill"><Cpu size={11} strokeWidth={2.4} /> {mainModel.split('/').pop() || mainModel}</span>
          <button
            type="button"
            className="mc-icon-btn"
            onClick={async () => {
              try {
                const { extractActiveTabText } = await import('../services/auroraExtensionBridge')
                const result = await extractActiveTabText()
                if (result.ok) {
                  const snippet = `Page active: ${result.data.title}\nURL: ${result.data.url}\n\nExtrait:\n${result.data.text.slice(0, 4000)}\n\nResume cette page et reponds a mes questions sur son contenu.`
                  void onSend(false, snippet)
                } else {
                  window.alert(`Aurora-Connect non disponible: ${result.reason}`)
                }
              } catch (err) {
                window.alert(`Echec lecture page: ${err instanceof Error ? err.message : String(err)}`)
              }
            }}
            title="Lire la page web actuellement ouverte dans le navigateur (necessite l extension Aurora-Connect)"
          >
            <span style={{ fontSize: 10, fontFamily: 'Bangers, cursive', letterSpacing: 1 }}>WEB</span>
          </button>
          <button
            type="button"
            className={`mc-icon-btn ${narrationOn ? 'is-active' : ''}`}
            onClick={() => setNarrationOn((v) => !v)}
            title={narrationOn ? 'Narration active' : 'Activer narration'}
          >
            <Volume2 size={14} strokeWidth={2.2} />
          </button>
          {/* v82h7 : copy MD au clipboard avec feedback transitoire */}
          <button
            type="button"
            className="mc-icon-btn"
            onClick={() => {
              void copyConversation().then((ok) => {
                setMdCopyFeedback(ok ? '✓' : '✗')
                window.setTimeout(() => setMdCopyFeedback(null), 1200)
              })
            }}
            title="Copier la conversation en Markdown"
          >
            {mdCopyFeedback ? (
              <span style={{ fontSize: 12, fontWeight: 700 }}>{mdCopyFeedback}</span>
            ) : (
              <span style={{ fontSize: 11, fontFamily: 'Bangers, cursive', letterSpacing: 1 }}>⎘</span>
            )}
          </button>
          <button
            type="button"
            className="mc-icon-btn"
            onClick={() => exportConversation('markdown')}
            title="Exporter la conversation en Markdown"
          >
            <FileText size={14} strokeWidth={2.2} />
          </button>
          <button
            type="button"
            className="mc-icon-btn"
            onClick={() => exportConversation('pdf')}
            title="Exporter la conversation en PDF"
          >
            <span style={{ fontSize: 10, fontFamily: 'Bangers, cursive', letterSpacing: 1 }}>PDF</span>
          </button>
          <button
            type="button"
            className="mc-icon-btn"
            onClick={() => { if (window.confirm('Effacer toute la conversation ?')) clearMessages() }}
            title="Effacer la conversation"
          >
            <Trash2 size={14} strokeWidth={2.2} />
          </button>
        </div>
      </header>

      {/* Thread */}
      {/* v82hs : floating search bar Ctrl+F */}
      {threadSearchOpen && (
        <div style={{
          position: 'absolute', top: 80, right: 24, zIndex: 50,
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 10px',
          background: '#fff', color: '#1a0f05',
          border: '2px solid #1a0f05',
          borderRadius: 8, boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
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
            placeholder="Chercher… (↵ next · ⇧↵ prev)"
            style={{
              width: 240, padding: '4px 8px',
              background: '#fff', color: '#1a0f05',
              border: '1px solid #1a0f05',
              borderRadius: 4, outline: 'none',
              fontFamily: 'inherit', fontSize: 'inherit',
            }} />
          <span style={{
            fontSize: 10, fontVariantNumeric: 'tabular-nums',
            minWidth: 60, textAlign: 'right',
          }}>{threadSearchQ
            ? `${threadMatchCount > 0 ? (((threadMatchCursor % threadMatchCount) + threadMatchCount) % threadMatchCount + 1) : 0}/${threadMatchCount}`
            : `${messages.length}`}</span>
          <button type="button"
            onClick={() => { setThreadSearchOpen(false); setThreadSearchQuery('') }}
            title="Fermer (Esc)"
            style={{
              width: 22, height: 22, padding: 0,
              background: '#fff', color: '#1a0f05',
              border: '1px solid #1a0f05', borderRadius: 3,
              cursor: 'pointer', fontSize: 11,
            }}>×</button>
        </div>
      )}
      <div className="mc-thread" ref={threadRef}>
        <div className="mc-hero-watermark">
          <img src={PORTRAITS[who]} alt="" aria-hidden="true" />
        </div>
        {messages.length === 0 && (
          <div className="mc-msg is-assistant">
            <div className="mc-msg-avatar"><img src={PORTRAITS[who]} alt={who} /></div>
            <div className="mc-msg-content">
              <div className="mc-msg-bubble">{WELCOME[who]}</div>
            </div>
          </div>
        )}
        {messages.map((msg, i) => {
          const id = String(msg.id ?? msg.timestamp ?? i)
          const isAsst = msg.role === 'assistant'
          // v82hs : visibility filter par search.
          const isMatchSearch = !threadSearchQ
            || (msg.content || '').toLowerCase().includes(threadSearchQ)
          return (
            <div key={msg.id || i} style={{
              opacity: isMatchSearch ? 1 : 0.25,
              transition: 'opacity .18s ease',
            }}>
            <Bubble
              msg={msg}
              who={who}
              isNarrating={narrating === id}
              onNarrate={isAsst ? () => {
                if (narrating === id) { stopNarration(); return }
                narrate(stripThink(msg.content).visible || msg.content, id)
              } : undefined}
              onCopy={() => {
                void navigator.clipboard.writeText(stripThink(msg.content).visible || msg.content).then(() => {
                  setBubbleCopiedId(msg.id ?? null)
                  window.setTimeout(() => setBubbleCopiedId(null), 1200)
                })
              }}
              copyFeedback={bubbleCopiedId === msg.id ? '✓' : null}
              onRegen={isAsst && i === messages.length - 1 ? onRegenerate : undefined}
              onEdit={(newContent) => updateMessage(msg.id!, newContent)}
              onDelete={() => removeMessage(msg.id!, !isAsst)}
              onPin={() => togglePinned(msg.id!)}
            />
            </div>
          )
        })}
        {isStreaming && (
          <div className="mc-msg is-assistant">
            <div className="mc-msg-avatar"><img src={PORTRAITS[who]} alt={who} /></div>
            <div className="mc-msg-content">
              <div className="mc-msg-bubble">
                {streamingVisible ? streamingVisible : (
                  <span className="mc-streaming"><span /><span /><span /></span>
                )}
                {streamingVisible && <span className="mc-cursor">▍</span>}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* v82fj : floating ↓ bottom (parité V1+V3) · v82gn : compteur unread */}
      {scrolledUp && (
        <button type="button"
          onClick={() => {
            const el = threadRef.current
            if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
            setUnreadCount(0)
          }}
          title={unreadCount > 0
            ? `${unreadCount} nouveau(x) message(s) — descendre`
            : 'Aller en bas'}
          style={{
            position: 'absolute', right: 24, bottom: 240, zIndex: 50,
            minWidth: 36, height: 36,
            padding: unreadCount > 0 ? '0 14px' : 0,
            borderRadius: 18,
            background: 'oklch(0.74 0.13 60 / 0.85)',
            color: '#0a0a0a',
            border: '1px solid oklch(0.74 0.13 60)',
            boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 14, fontWeight: 700,
            transition: 'padding .18s ease, min-width .18s ease',
          }}>
          ↓{unreadCount > 0 && <span style={{ fontSize: 12 }}>{unreadCount}</span>}
        </button>
      )}
      {/* Composer */}
      <div className="mc-composer">
        <div className="mc-composer-tools">
          <button type="button" className="mc-tool" onClick={() => textareaRef.current?.focus()}>
            <Wand2 size={13} strokeWidth={2.2} /> prompt
          </button>
          <button
            type="button"
            className="mc-tool"
            onClick={() => fileInputRef.current?.click()}
            title="Joindre un fichier"
          >
            <Paperclip size={13} strokeWidth={2.2} /> joindre
          </button>
          <button
            type="button"
            className="mc-tool"
            onClick={openVoice}
            title="Mode copilote vocal (full screen)"
          >
            <Radio size={13} strokeWidth={2.2} /> vocal
          </button>
          <span className="flex-1" />
          <span className="mc-composer-hint">⌘⏎ envoyer · ⇧⏎ nouvelle ligne</span>
        </div>

        {attachments.length > 0 && (
          <div className="mc-attachments-wrap">
            <div className="mc-attachments-label">
              <Paperclip size={11} strokeWidth={2.4} />
              {attachments.length === 1
                ? '1 fichier joint au prochain message'
                : `${attachments.length} fichiers joints au prochain message`}
            </div>
            <div className="mc-attachments">
              {attachments.map((a) => (
                <div
                  key={a.id}
                  className={`mc-attachment-chip ${a.previewUrl ? 'is-image' : a.text ? 'has-text' : 'no-text'}`}
                  title={
                    a.previewUrl ? (a.visionText
                      ? `Image — ${a.visionText.slice(0, 160)}…`
                      : `Image — analyse vision en cours…`)
                      : a.text ? `${a.name} — contenu lisible injecté`
                      : `${a.name} — binaire (nom transmis uniquement)`
                  }
                >
                  {a.previewUrl
                    ? <img src={a.previewUrl} alt={a.name} className="mc-attachment-thumb" />
                    : <FileText size={12} strokeWidth={2.2} />}
                  <span className="mc-attachment-name">{a.name}</span>
                  {a.previewUrl && !a.visionText && <span className="mc-attachment-size" title="Vision en cours…">· 👁 …</span>}
                  <span className="mc-attachment-size">
                    {a.size > 1024 ? `${(a.size / 1024).toFixed(1)} ko` : `${a.size} o`}
                  </span>
                  <button
                    type="button"
                    className="mc-attachment-x"
                    onClick={() => removeAttachment(a.id)}
                    title="Retirer"
                  >
                    <X size={10} strokeWidth={2.6} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          accept=".txt,.md,.markdown,.json,.csv,.log,.py,.js,.ts,.html,.css,.sh,.tex,.xml,.yaml,image/*"
          onChange={onFileChange}
        />

        <SlashCommandMenu draft={draft} onPick={(cmd) => setDraft(`/${cmd} `)} />

        <div className="mc-composer-row">
          <button
            type="button"
            className="mc-mic"
            onClick={openVoice}
            title="Copilote vocal"
          >
            <Mic size={14} strokeWidth={2.4} />
          </button>
          <textarea
            ref={textareaRef}
            className="mc-input"
            rows={1}
            placeholder={who === 'natsu'
              ? "Balance ton défi, j'suis tout feu tout flamme…"
              : "Dis-moi ce que tu veux invoquer…"}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void onSend() }
            }}
            disabled={isStreaming}
          />
          <VoicePushToTalk
            onTranscript={(t) => setDraft(draft?.trim() ? `${draft} ${t}` : t)}
            label="Dicter ta question"
            size={28}
            variant="ghost"
          />
          {narrating && (
            <button
              type="button"
              className="mc-mic"
              onClick={stopNarration}
              title="Stopper la narration"
              style={{ color: '#ff6a3d' }}
            >
              <VolumeX size={14} strokeWidth={2.4} />
            </button>
          )}
          {isStreaming ? (
            <button type="button" className="mc-send is-stop" onClick={onStop} title="Arrêter">
              <StopCircle size={14} strokeWidth={2.4} /> Stop
            </button>
          ) : (
            <>
              <button
                type="button"
                className="mc-send"
                onClick={() => void onSend()}
                disabled={!draft.trim() && attachments.length === 0}
                title="Envoyer"
              >
                <Send size={14} strokeWidth={2.4} /> {who === 'natsu' ? 'Brûler' : 'Invoquer'}
              </button>
              {/* v82ff : conversation starter aléatoire + auto-send (parité V1+V3) */}
              <button
                type="button"
                onClick={() => { void onSend(false, pickRandomStarter()) }}
                title="Lance une conversation au hasard"
                style={{
                  padding: '6px 10px', fontSize: 11, marginLeft: 6,
                  background: 'oklch(0.74 0.13 60 / 0.10)',
                  color: 'oklch(0.74 0.13 60)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                  borderRadius: 6, cursor: 'pointer',
                  fontFamily: 'var(--font-mono, monospace)', fontWeight: 700,
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                }}>
                ⚡ surprise
              </button>
            </>
          )}
        </div>
      </div>

      {/* Voice copilot overlay */}
      <AnimatePresence>
        {voiceOpen && (
          <motion.div
            className="mc-voice-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <button
              type="button"
              className="mc-voice-close"
              onClick={closeVoice}
              title="Fermer"
            >
              <X size={16} strokeWidth={2.4} />
            </button>
            <Suspense
              fallback={
                <div className="mc-voice-loading">Invocation du copilote vocal…</div>
              }
            >
              <VoiceCopilotView />
            </Suspense>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
