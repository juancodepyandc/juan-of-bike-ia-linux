/**
 * useChatViewLogic — chat state machine extracted from MangaChatView so that
 * skin ports (Aurora V1 Editorial, Aurora V3 Ricochet) can render their own
 * chrome over the *same* feature set without duplicating logic.
 *
 * The Manga view used to own everything. Now Manga / V1 / V3 each consume
 * this hook and only render their visual surface, guaranteeing zero feature
 * regression when the user flips uiSkin in Settings.
 *
 * Exposes:
 *   • messages / streamContent / isStreaming / streamingVisible
 *   • draft + setDraft
 *   • attachments + addFiles + removeAttachment
 *   • narrationOn / setNarrationOn / narrating + narrate / stopNarration
 *   • voiceOpen + openVoice / closeVoice
 *   • onSend / onStop / onRegenerate
 *   • exportConversation (markdown / pdf)
 *   • readPageViaWebExtension (Aurora-Connect)
 *   • clearAll + per-message actions (updateMessage, removeMessage, togglePinned)
 *   • who (Character) + setWho persistence
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useGenerationFxEmitter } from '../components/generationFx/fxBus'
import { useChatStore } from '../stores/chatStore'
import { useAppStore } from '../stores/appStore'
import { runConversationTurn } from '../services/conversationOrchestrator'
import type { ChatMessage } from '../types/app'
import { getErrorMessage } from '../utils/errors'
import { speakify } from '../utils/speakify'

export type Attachment = {
  id: string
  name: string
  size: number
  type: string
  text?: string
  previewUrl?: string
  visionText?: string
}

export type Character = 'natsu' | 'lucy'

export const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

export const WELCOME: Record<Character, string> = {
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

export function stripThink(raw: string): { visible: string; thinking: string | null } {
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

const TEXT_LIKE = /\.(txt|md|markdown|json|csv|tsv|log|xml|yaml|yml|ini|conf|py|js|ts|tsx|jsx|html|css|scss|sh|bash|zsh|c|h|cpp|hpp|java|go|rs|rb|php|sql|toml)$/i
const IMAGE_LIKE = /^image\/(png|jpe?g|webp|gif|bmp|avif)$/i

export function useChatViewLogic() {
  const [who, setWhoState] = useState<Character>(readCharacter)
  useEffect(() => {
    const h = () => setWhoState(readCharacter())
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
  useGenerationFxEmitter('conversation', isStreaming)

  const [draft, setDraft] = useState('')
  const [narrationOn, setNarrationOn] = useState(false)
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const onSend = async (voiceMode: boolean = false, overrideText?: string) => {
    const rawText = (overrideText ?? draft).trim()
    if ((!rawText && attachments.length === 0) || isStreaming) return
    if (overrideText === undefined) setDraft('')
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    let text = rawText
    if (rawText.startsWith('/')) {
      try {
        const mod = await import('../utils/slashCommands')
        text = mod.applySlashCommand(rawText)
      } catch { /* fallback to raw text */ }
    }

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

  const [narrating, setNarrating] = useState<string | null>(null)
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

  const addFiles = async (files: File[]) => {
    if (files.length === 0) return
    const next: Attachment[] = []
    for (const f of files) {
      const isImage = IMAGE_LIKE.test(f.type) || /\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(f.name)
      const canRead = f.type.startsWith('text/') || TEXT_LIKE.test(f.name) || f.type === 'application/json'
      // v82fl : extend chat ingestion to PDF + DOCX via readTextFile
      const isPdfOrDocx = /\.(pdf|docx)$/i.test(f.name)
        || f.type === 'application/pdf'
        || f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      let text: string | undefined
      let previewUrl: string | undefined
      if (canRead) {
        try {
          text = await f.text()
          if (text.length > 200000) text = text.slice(0, 200000) + '\n\n[... fichier tronqué ...]'
        } catch { /* ignore */ }
      } else if (isPdfOrDocx) {
        try {
          const { readTextFile } = await import('../utils/textFileExtract')
          text = await readTextFile(f)
          if (text.length > 200000) text = text.slice(0, 200000) + '\n\n[... fichier tronqué ...]'
        } catch { /* ignore — keep attachment visible without text */ }
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
      next.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name,
        size: f.size,
        type: f.type || 'application/octet-stream',
        text,
        previewUrl,
      })
    }
    setAttachments((prev) => [...prev, ...next])
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
          } catch { /* vision offline → attachment still visible */ }
        })()
      }
    }
  }
  const removeAttachment = (id: string) =>
    setAttachments((prev) => prev.filter((a) => a.id !== id))

  const openVoice = () => setVoiceOpen(true)
  const closeVoice = () => setVoiceOpen(false)

  // v82h6 : helper interne pour générer le markdown de la conversation —
  //   réutilisé par exportConversation('markdown') ET copyConversation().
  const buildConversationMarkdown = (): string => {
    const character = readCharacter()
    const ts = new Date().toISOString().slice(0, 10)
    const header = `# Conversation · ${character} · ${ts}\n\n`
    const body = messages.map((m) => {
      const visible = stripThink(m.content).visible || m.content
      const label = m.role === 'user' ? '👤 **Toi**' : `✦ **${character === 'natsu' ? 'Natsu' : 'Lucy'}**`
      return `${label}\n\n${visible}\n`
    }).join('\n---\n\n')
    return header + body
  }

  // v82h6 : copy la conversation entière en markdown au presse-papier.
  //   Utile pour partager un échange dans un autre LLM/Slack/email
  //   sans passer par un fichier téléchargé.
  const copyConversation = async (): Promise<boolean> => {
    if (messages.length === 0) return false
    if (typeof navigator === 'undefined' || !navigator.clipboard) return false
    try {
      const md = buildConversationMarkdown()
      await navigator.clipboard.writeText(md)
      return true
    } catch { return false }
  }

  const exportConversation = async (format: 'markdown' | 'pdf') => {
    if (messages.length === 0) return
    const character = readCharacter()
    const ts = new Date().toISOString().slice(0, 10)
    const md = buildConversationMarkdown()
    if (format === 'markdown') {
      const blob = new Blob([md], { type: 'text/markdown; charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `conversation_${character}_${ts}.md`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 2000)
      return
    }
    const container = document.createElement('div')
    container.innerHTML = `<h1>Conversation · ${character} · ${ts}</h1>` + messages.map((m) => {
      const visible = stripThink(m.content).visible || m.content
      const html = visible.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')
      return `<div style="margin:10px 0;padding:10px 12px;border:2px solid #1a0f05;background:${m.role === 'user' ? '#b5241e' : '#fff'};color:${m.role === 'user' ? '#fff' : '#1a0f05'};border-radius:8px">
        <b>${m.role === 'user' ? '👤 Toi' : `✦ ${character === 'natsu' ? 'Natsu' : 'Lucy'}`}</b><br>${html}
      </div>`
    }).join('')
    const mod = await import('../utils/exportPdf')
    mod.printElement(container, {
      title: `Conversation · ${character}`,
      subtitle: ts,
      footer: `juan of bike IA · ${messages.length} messages`,
    })
  }

  const readActiveTab = async () => {
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
  }

  const clearAll = () => {
    if (window.confirm('Effacer toute la conversation ?')) clearMessages()
  }

  const streamingVisible = useMemo(() => stripThink(streamContent).visible, [streamContent])

  return {
    // identity
    who,
    // state
    messages, isStreaming, streamContent, streamingVisible,
    draft, setDraft,
    attachments, addFiles, removeAttachment,
    narrationOn, setNarrationOn,
    narrating, narrate, stopNarration,
    voiceOpen, openVoice, closeVoice,
    // model + send
    mainModel,
    onSend, onStop, onRegenerate,
    // export + util
    exportConversation, copyConversation, readActiveTab, clearAll,
    // per-message
    updateMessage, removeMessage, togglePinned,
  }
}
