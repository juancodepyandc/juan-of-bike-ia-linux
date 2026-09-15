import { useState, useRef, useEffect, useCallback, useMemo, lazy, Suspense } from 'react'
import { analyseTone } from '../services/conversationToneMatcher.ts'
import { EXPERT } from '../services/auroraExpertPrompts.ts'
import LyraCharacter from '../components/voice/LyraCharacter.tsx'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot,
  Box,
  Code2,
  Copy,
  Cpu,
  Download,
  Gauge,
  GraduationCap,
  Image as ImageIcon,
  ListChecks,
  Loader2,
  MessageCircle,
  Mic,
  MicOff,
  Monitor,
  Paintbrush,
  Radio,
  Send,
  ShieldCheck,
  Sparkles,
  StopCircle,
  Trash2,
  Video,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react'
import ContextFilesField from '../components/ContextFilesField.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import { auroraVoice } from '../services/auroraVoice.ts'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard.tsx'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel.tsx'
import RecoveryBanner from '../components/RecoveryBanner.tsx'
import SessionSwitcher from '../components/SessionSwitcher.tsx'
import { buildConversationModuleAssets } from '../config/moduleAssetPacks.ts'

const VoiceCopilotView = lazy(() => import('./VoiceCopilotView'))
import { useChatStore } from '../stores/chatStore.ts'
import { useAppStore } from '../stores/appStore.ts'
import { useGenerationTrackerStore } from '../stores/generationTrackerStore.ts'
import { useGenerationRecovery } from '../hooks/useGenerationRecovery.ts'
import { useManagedRuntime } from '../hooks/useManagedRuntime.ts'
import { useModuleAssetPack } from '../hooks/useModuleAssetPack.ts'
import { runConversationTurn } from '../services/conversationOrchestrator.ts'
import { prepareTaskIntelligence } from '../services/taskIntelligence.ts'
import type { AssistantRunState, ChatMessage, ModuleId } from '../types/app.ts'
import { getErrorMessage } from '../utils/errors.ts'
import { getRuntimeLabel } from '../utils/runtime.ts'
import { prepareContextFiles } from '../utils/multimodalContext.ts'
import { fsMkdir, fsReadBinary, fsWriteBinary, getWorkspacePath, runPythonScript } from '../hooks/useTauri.ts'

function processThinkTags(raw: string): { visible: string; thinking: string | null } {
  let visible = raw
  let thinking: string | null = null

  const thinkRegex = /<think>([\s\S]*?)<\/think>/g
  const thinkParts: string[] = []
  visible = raw.replace(thinkRegex, (_match, content) => {
    thinkParts.push(content.trim())
    return ''
  })

  if (thinkParts.length > 0) {
    thinking = thinkParts.join('\n')
  }

  const lastOpen = visible.lastIndexOf('<think>')
  if (lastOpen !== -1) {
    const afterTag = visible.slice(lastOpen + 7)
    if (!afterTag.includes('</think>')) {
      thinking = (thinking ? `${thinking}\n` : '') + afterTag.trim()
      visible = visible.slice(0, lastOpen)
    }
  }

  return { visible: visible.trim(), thinking }
}

function MessageBubble({ msg, onNarrate }: { msg: ChatMessage; onNarrate?: (text: string) => void }) {
  const isUser = msg.role === 'user'
  const { visible } = processThinkTags(msg.content)
  // v84f — pour les messages user, montre un mini badge tone détecté.
  const tone = useMemo(() => isUser ? analyseTone(msg.content) : null, [isUser, msg.content])

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`max-w-[92%] lg:max-w-[82%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div
          className={`cut-panel-soft border px-4 py-4 text-sm leading-relaxed whitespace-pre-wrap shadow-[0_16px_34px_rgba(0,0,0,0.18)] ${
            isUser
              ? 'border-white/18 bg-[linear-gradient(135deg,rgba(116,232,255,0.16),rgba(255,107,61,0.22))] text-white'
              : 'border-white/10 bg-white/[0.04] text-aurora-text'
          }`}
        >
          {visible}
          {msg.images && msg.images.length > 0 && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {msg.images.slice(0, 4).map((image, index) => (
                <img
                  key={`${msg.id}-image-${index}`}
                  src={`data:image/png;base64,${image}`}
                  alt="Piece jointe"
                  className="max-h-40 w-full rounded-xl object-cover"
                />
              ))}
            </div>
          )}
        </div>
        {tone && (
          <div className={`mt-1 flex flex-wrap items-center gap-1 ${isUser ? 'justify-end' : 'justify-start'}`}>
            <span className="rounded bg-cyan-500/15 border border-cyan-500/30 px-1.5 py-0.5 text-[9px] font-mono text-cyan-200">
              {tone.formality > 0.65 ? 'formel' : tone.formality < 0.4 ? 'casual' : 'neutre'}
            </span>
            <span className="rounded bg-violet-500/15 border border-violet-500/30 px-1.5 py-0.5 text-[9px] font-mono text-violet-200">
              {tone.recommendedAddress === 'vous' ? 'vouv.' : 'tut.'}
            </span>
            {tone.argot > 0.3 && (
              <span className="rounded bg-fuchsia-500/15 border border-fuchsia-500/30 px-1.5 py-0.5 text-[9px] font-mono text-fuchsia-200">
                argot {Math.round(tone.argot * 100)}%
              </span>
            )}
            {tone.emotionalLoad > 0.5 && (
              <span className="rounded bg-rose-500/15 border border-rose-500/30 px-1.5 py-0.5 text-[9px] font-mono text-rose-200">
                émotion
              </span>
            )}
          </div>
        )}
        <div className={`mt-1.5 flex items-center gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
          <span className="text-[10px] text-aurora-text-dim">
            {new Date(msg.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && onNarrate && visible && (
            <button
              onClick={() => onNarrate(visible)}
              title="Lire à voix haute"
              className="flex h-5 w-5 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-white/40 transition-colors hover:border-aurora-accent/30 hover:bg-aurora-accent/10 hover:text-aurora-accent"
            >
              <Volume2 size={9} />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function StreamingBubble({ content, label }: { content: string; label: string }) {
  const { visible } = processThinkTags(content)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-start"
    >
      <div className="max-w-[92%] lg:max-w-[82%]">
        <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-[11px] text-aurora-text-dim">
          <Loader2 size={12} className="animate-spin text-aurora-accent" />
          <span>{label}</span>
        </div>
        <div className="cut-panel-soft border border-white/10 bg-white/[0.04] px-4 py-4 text-sm leading-relaxed whitespace-pre-wrap text-aurora-text shadow-[0_16px_34px_rgba(0,0,0,0.18)]">
          {visible}
          <span className="ml-1 inline-block h-4 w-1.5 animate-aurora-pulse rounded-sm bg-aurora-accent" />
        </div>
      </div>
    </motion.div>
  )
}

function SmallCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ShieldCheck
  label: string
  value: string
}) {
  return (
    <div className="cut-panel-soft border border-white/10 bg-white/[0.04] px-4 py-4">
      <div className="flex items-center gap-2 text-[11px] text-aurora-text-dim">
        <Icon size={13} />
        <span>{label}</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-aurora-text">{value}</p>
    </div>
  )
}

function TurnStatusPanel({
  runState,
  model,
  ollamaReady,
}: {
  runState: AssistantRunState
  model: string
  ollamaReady: boolean
}) {
  return (
    <div className="cut-panel border border-white/10 bg-white/[0.04] px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-aurora-text">Copilote</span>
            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${ollamaReady ? 'border-aurora-green/20 bg-aurora-green/10 text-aurora-text' : 'border-aurora-red/20 bg-aurora-red/10 text-aurora-text'}`}>
              {ollamaReady ? 'Ollama actif' : 'Ollama hors ligne'}
            </span>
          </div>
          <p className="mt-2 text-xs text-aurora-text-dim">{model}</p>
        </div>

        <div className="w-full max-w-xs">
          <div className="flex items-center justify-between text-[11px] text-aurora-text-dim">
            <span>{runState.label}</span>
            <span>{runState.progress}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/[0.08]">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${runState.progress}%` }}
              className="h-full rounded-full bg-[linear-gradient(90deg,#74e8ff,#ff6b3d)]"
            />
          </div>
          <p className="mt-2 text-[11px] text-aurora-text-dim">{runState.detail}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-3">
        <SmallCard
          icon={ListChecks}
          label="Objectif"
          value={runState.analysis?.objective || 'En attente'}
        />
        <SmallCard
          icon={Gauge}
          label="Precision"
          value={!runState.verification
            ? 'Non lancee'
            // Une verification qui n'a pas eu lieu n'a pas de note. Afficher
            // « 94/100 » sur un jugement absent trompait l'utilisateur.
            : runState.verification.verified === false
              ? 'Non verifiee'
              : `${runState.verification.score}/100`}
        />
        <SmallCard
          icon={ShieldCheck}
          label="Verification"
          value={runState.verification?.summary || 'En attente'}
        />
      </div>
    </div>
  )
}

function ModuleShortcut({
  moduleId,
  label,
  icon: Icon,
}: {
  moduleId: ModuleId
  label: string
  icon: typeof MessageCircle
}) {
  const { setActiveModule } = useAppStore()

  return (
    <button
      onClick={() => setActiveModule(moduleId)}
      className="cut-panel-soft border border-white/10 bg-white/[0.04] px-4 py-3 text-left transition-colors hover:border-white/18"
    >
      <span className="inline-flex items-center gap-3">
        <span className="status-orb flex h-9 w-9 items-center justify-center text-white">
          <Icon size={14} />
        </span>
        <span className="text-sm text-aurora-text">{label}</span>
      </span>
    </button>
  )
}

function ExpertPromptVisualizer() {
  const [open, setOpen] = useState(false)
  const spec = EXPERT.conversation
  return (
    <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/[0.04] p-3 text-[11px]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-cyan-200 hover:text-cyan-100 transition-colors w-full text-left"
        aria-expanded={open}
      >
        <span className="text-[10px] font-mono uppercase tracking-wider">{open ? '▾' : '▸'}</span>
        <span className="font-semibold">Expert system prompt actif</span>
        <span className="ml-auto rounded bg-cyan-500/15 border border-cyan-500/30 px-1.5 py-0.5 text-[9px] font-mono">
          conversation
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <Section title="Identity">
            <p className="text-aurora-text whitespace-pre-wrap">{spec.identity}</p>
          </Section>
          <Section title="Quality bar">
            <p className="text-aurora-text whitespace-pre-wrap">{spec.qualityBar}</p>
          </Section>
          <Section title="Negative">
            <p className="text-rose-200/85 whitespace-pre-wrap">{spec.negative}</p>
          </Section>
          {spec.outputFormat && (
            <Section title="Output format">
              <p className="text-aurora-text whitespace-pre-wrap font-mono text-[10px]">{spec.outputFormat}</p>
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-cyan-200/70 mb-1">{title}</div>
      <div className="rounded-md bg-black/30 border border-white/5 p-2 text-[10px] leading-relaxed">{children}</div>
    </div>
  )
}

function ConversationLiveTelemetry({
  input,
  messages,
  model,
}: {
  input: string
  messages: Array<{ role: string; content: string }>
  model: string
}) {
  // Tone détecté en temps réel sur le dernier message user (ou input courant).
  const baseText = input.trim() || (
    [...messages].reverse().find((m) => m.role === 'user')?.content || ''
  )
  const tone = useMemo(() => analyseTone(baseText), [baseText])
  // Estimation tokens (~4 chars/token).
  const totalChars = useMemo(() => messages.reduce((s, m) => s + (m.content?.length || 0), 0), [messages])
  const approxTokens = Math.round(totalChars / 4)
  const formalityLabel =
    tone.formality > 0.65 ? 'formel'
    : tone.formality < 0.4 ? 'casual'
    : 'neutre'
  const addressLabel = tone.recommendedAddress === 'vous' ? 'vouv.' : 'tut.'
  const styleLabel = tone.recommendedStyle
  const chips: Array<{ label: string; value: string; tone: string }> = []
  if (baseText.length > 0) {
    chips.push({ label: 'tone', value: `${formalityLabel} · ${addressLabel}`, tone: 'cyan' })
    chips.push({ label: 'style', value: styleLabel, tone: 'violet' })
    if (tone.argot > 0.3) chips.push({ label: 'argot', value: `${Math.round(tone.argot * 100)}%`, tone: 'fuchsia' })
    if (tone.emotionalLoad > 0.5) chips.push({ label: 'émotion', value: `${Math.round(tone.emotionalLoad * 100)}%`, tone: 'rose' })
  }
  chips.push({ label: 'modèle', value: model.split(':')[0], tone: 'slate' })
  chips.push({ label: '~tokens', value: approxTokens.toString(), tone: 'slate' })
  const toneCls: Record<string, string> = {
    cyan: 'bg-cyan-500/15 text-cyan-200 border-cyan-500/30',
    violet: 'bg-violet-500/15 text-violet-200 border-violet-500/30',
    fuchsia: 'bg-fuchsia-500/15 text-fuchsia-200 border-fuchsia-500/30',
    rose: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    slate: 'bg-white/5 text-aurora-text-dim border-white/10',
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {chips.map((c, i) => (
        <span key={i} className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-mono ${toneCls[c.tone] ?? toneCls.slate}`}>
          <span className="opacity-70 uppercase">{c.label}</span>
          <span>{c.value}</span>
        </span>
      ))}
    </div>
  )
}

export default function ConversationView() {
  const {
    messages,
    isStreaming,
    streamContent,
    runState,
    addMessage,
    setStreaming,
    setStreamContent,
    appendStreamContent,
    clearMessages,
    popLastAssistantTurn,
    startRun,
    setRunStage,
    setRunAnalysis,
    setRunVerification,
    finishRun,
    failRun,
    resetRun,
  } = useChatStore()
  const { hardware, mainModel, installedModels, setMainModel, runtimeServices, services, visionModel } = useAppStore()
  const { trackGeneration, completeGeneration, failGeneration } = useGenerationTrackerStore()
  const recovery = useGenerationRecovery('conversation')
  const { executeWithRuntime } = useManagedRuntime()
  const activeTrackerIdRef = useRef<string | null>(null)
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const { pack: assetPack, preparePack } = useModuleAssetPack({
    module: 'conversation',
    title: 'Pack modele conversation',
    assets: buildConversationModuleAssets(mainModel, visionModel, contextFiles.length > 0),
  })
  const [input, setInput] = useState('')
  const [suggestedRoute, setSuggestedRoute] = useState<{ moduleId: ModuleId; confidence: number; hint: string } | null>(null)
  const routeToModule = useAppStore((s) => s.setActiveModule)
  // v84h — Stream rate : tok/s observé pendant le streaming.
  const [streamRate, setStreamRate] = useState<number>(0)
  const streamStartRef = useRef<number>(0)
  useEffect(() => {
    if (isStreaming && streamStartRef.current === 0) {
      streamStartRef.current = performance.now()
    }
    if (isStreaming && streamContent.length > 0 && streamStartRef.current > 0) {
      const elapsedSec = (performance.now() - streamStartRef.current) / 1000
      if (elapsedSec > 0.1) {
        const approxTokens = streamContent.length / 4
        setStreamRate(Math.round(approxTokens / elapsedSec))
      }
    }
    if (!isStreaming) {
      streamStartRef.current = 0
      setStreamRate(0)
    }
  }, [isStreaming, streamContent])
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // --- Voice state ---
  const [voicePanelOpen, setVoicePanelOpen] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [narrationEnabled, setNarrationEnabled] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState<string | null>(null)
  const [sttModelUsed, setSttModelUsed] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const currentAudioRef = useRef<HTMLAudioElement | null>(null)
  const vadAnalyserRef = useRef<AnalyserNode | null>(null)
  const vadFrameRef = useRef<number>(0)
  const vadActiveRef = useRef(false)
  // true quand le dernier message a ete envoye via STT — active le mode vocal rapide
  const lastSendWasVoiceRef = useRef(false)
  // Ref pour que stopRecordingAndTranscribe accede a handleSend sans cycle
  const handleSendRef = useRef<((textOverride?: string, isVoice?: boolean) => Promise<void>) | null>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent, runState.timeline.length])

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 220)}px`
    }
  }, [input])

  const ollamaReady = services.ollama || runtimeServices.ollama.available
  const activeModel = contextFiles.length > 0 ? visionModel : mainModel

  // --- Voice helpers ---

  const startRecording = useCallback(async () => {
    let stream: MediaStream | null = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 },
      })
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm',
      })
      audioChunksRef.current = []
      vadActiveRef.current = true

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data)
      }

      // VAD via Web Audio API — arret auto apres 1.8s de silence
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.8
      source.connect(analyser)
      vadAnalyserRef.current = analyser

      const vadData = new Float32Array(analyser.fftSize)
      let silenceStart: number | null = null
      const SILENCE_THRESHOLD = 0.012
      const SILENCE_MS = 1800

      const checkVAD = () => {
        if (!vadActiveRef.current || !vadAnalyserRef.current) return
        vadAnalyserRef.current.getFloatTimeDomainData(vadData)
        let rms = 0
        for (let i = 0; i < vadData.length; i += 1) rms += vadData[i] * vadData[i]
        rms = Math.sqrt(rms / vadData.length)

        if (rms < SILENCE_THRESHOLD) {
          if (!silenceStart) silenceStart = Date.now()
          if (Date.now() - silenceStart > SILENCE_MS) {
            // Silence detecte — arret automatique
            vadActiveRef.current = false
            cancelAnimationFrame(vadFrameRef.current)
            setVoiceStatus('Fin detectee, transcription...')
            if (mediaRecorder.state !== 'inactive') mediaRecorder.stop()
            stream?.getTracks().forEach((t) => t.stop())
            return
          }
        } else {
          silenceStart = null
        }
        vadFrameRef.current = requestAnimationFrame(checkVAD)
      }
      vadFrameRef.current = requestAnimationFrame(checkVAD)

      mediaRecorder.start(100)
      mediaRecorderRef.current = mediaRecorder
      setIsRecording(true)
      setVoiceStatus('Parlez... (arret auto apres silence)')
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())
      setVoiceStatus(`Micro inaccessible: ${getErrorMessage(error, 'permission refusee')}`)
    }
  }, [])

  const setVoiceStatusWithAutoClear = useCallback((status: string | null, duration = 10000) => {
    setVoiceStatus(status)
    if (status) {
      const timer = window.setTimeout(() => {
        setVoiceStatus((current) => current === status ? null : current)
      }, duration)
      return () => window.clearTimeout(timer)
    }
  }, [])

  const stopRecordingAndTranscribe = useCallback(async () => {
    const recorder = mediaRecorderRef.current
    if (!recorder) return

    // Arreter le VAD
    vadActiveRef.current = false
    cancelAnimationFrame(vadFrameRef.current)
    vadAnalyserRef.current = null

    setIsRecording(false)
    setVoiceStatus('Arret de l\'enregistrement...')
    mediaRecorderRef.current = null

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve()
      if (recorder.state !== 'inactive') {
        recorder.stop()
      } else {
        resolve()
      }
    })
    recorder.stream.getTracks().forEach((track) => track.stop())

    const chunks = audioChunksRef.current
    audioChunksRef.current = []

    if (chunks.length === 0) {
      setVoiceStatus('Aucun audio capture. Reessayez.')
      return
    }

    setVoiceStatus('Transcription en cours...')

    try {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      if (blob.size < 100) {
        setVoiceStatus('Enregistrement trop court. Reessayez.')
        return
      }

      const arrayBuffer = await blob.arrayBuffer()
      const bytes = Array.from(new Uint8Array(arrayBuffer))

      const workspacePath = await getWorkspacePath()
      const tmpDir = `${workspacePath}/output/voice_tmp`
      await fsMkdir(tmpDir)
      const audioPath = `${tmpDir}/mic_${Date.now()}.webm`
      const scriptPath = `${workspacePath}/python-services/voice_service.py`

      await fsWriteBinary(audioPath, bytes)
      const output = await runPythonScript(scriptPath, ['--mode', 'stt', '--audio', audioPath])

      // Parse JSON from last line backwards — skip non-JSON PROGRESS lines
      const lines = output.split('\n').filter((l) => l.trim() && !l.startsWith('PROGRESS:'))
      let foundResult = false
      for (let index = lines.length - 1; index >= 0; index--) {
        try {
          const json = JSON.parse(lines[index]) as { ok?: boolean; text?: string; model_used?: string; error?: string }
          if (json.ok && json.text) {
            setSttModelUsed(json.model_used ?? null)
            setVoiceStatusWithAutoClear(`Transcrit (${json.model_used ?? 'stt'}): "${json.text.slice(0, 60)}${json.text.length > 60 ? '…' : ''}"`)
            void handleSendRef.current?.(json.text, true)
            foundResult = true
            break
          }
          if (json.ok === false) {
            setVoiceStatusWithAutoClear(`Transcription echouee: ${json.error ?? 'erreur inconnue'}`, 15000)
            foundResult = true
            break
          }
        } catch {
          // Not JSON, continue
        }
      }
      if (!foundResult) {
        setVoiceStatus('Aucun texte transcrit. Le moteur STT n\'a pas retourne de resultat.')
      }
    } catch (error) {
      setVoiceStatusWithAutoClear(`Erreur STT: ${getErrorMessage(error, 'pipeline vocal echoue')}`, 15000)
    }
  }, [setVoiceStatusWithAutoClear])

  const narrateText = useCallback(async (text: string, force = false) => {
    if (!force && !narrationEnabled) return
    if (!text.trim()) return
    // Respecte le mute global piloté par VoiceQuickToggle / auroraVoice.
    if (auroraVoice.isMuted()) return

    try {
      const workspacePath = await getWorkspacePath()
      const tmpDir = `${workspacePath}/output/voice_tmp`
      await fsMkdir(tmpDir)
      const outputPath = `${tmpDir}/tts_${Date.now()}.wav`
      const scriptPath = `${workspacePath}/python-services/voice_service.py`

      // Persona 'lyra-soft' : voix Microsoft Denise Neural douce, identité conversationnelle Aurora.
      const output = await runPythonScript(scriptPath, [
        '--mode', 'tts',
        '--text', text.slice(0, 4000),
        '--output', outputPath,
        '--lang', 'fr',
        '--voice', 'lyra-soft',
      ])

      const lines = output.split('\n').filter((l) => l.trim() && !l.startsWith('PROGRESS:'))
      for (let index = lines.length - 1; index >= 0; index--) {
        try {
          const json = JSON.parse(lines[index]) as { ok?: boolean; path?: string; error?: string }
          if (json.ok && json.path) {
            const bytes = await fsReadBinary(json.path)
            const blob = new Blob([new Uint8Array(bytes)], { type: 'audio/wav' })
            const url = URL.createObjectURL(blob)

            // Stop previous audio
            if (currentAudioRef.current) {
              currentAudioRef.current.pause()
              currentAudioRef.current = null
            }

            const audio = new Audio(url)
            currentAudioRef.current = audio
            audio.onended = () => {
              URL.revokeObjectURL(url)
              if (currentAudioRef.current === audio) currentAudioRef.current = null
            }
            audio.onerror = () => {
              URL.revokeObjectURL(url)
              if (currentAudioRef.current === audio) currentAudioRef.current = null
            }
            await audio.play()
            return
          }
          if (json.ok === false) {
            console.warn('[TTS] Echec:', json.error)
            return
          }
        } catch {
          // Not JSON
        }
      }
    } catch (error) {
      console.warn('[TTS] Pipeline echoue:', getErrorMessage(error, 'inconnu'))
    }
  }, [narrationEnabled])

  const handleSend = useCallback(async (textOverride?: string, isVoice = false) => {
    const text = (textOverride ?? input).trim()
    if (!text || isStreaming) return

    // Mode vocal : actif si le message vient du STT ou si la narration est activee
    const voiceMode = isVoice || narrationEnabled
    lastSendWasVoiceRef.current = voiceMode

    // Le runtime demarre Ollama automatiquement si absent ou eteint.
    // Aucun blocage ici: executeWithRuntime gere tout.

    const preparedContext = contextFiles.length > 0 ? await prepareContextFiles(contextFiles) : []
    const attachedImages = preparedContext.flatMap((file) => file.imageBase64 ? [file.imageBase64] : [])

    const pendingUserMessage: ChatMessage = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
      images: attachedImages.length > 0 ? attachedImages : undefined,
    }

    setInput('')
    setContextFiles([])
    addMessage({ role: 'user', content: text, images: pendingUserMessage.images })
    setStreaming(true)
    setStreamContent('')
    startRun()

    const controller = new AbortController()
    abortRef.current = controller

    activeTrackerIdRef.current = trackGeneration({
      module: 'conversation',
      type: 'ollama_stream',
      prompt: text,
      startedAt: Date.now(),
    })

    try {
      const result = await executeWithRuntime({
        module: 'conversation',
        title: 'Copilote global',
        services: ['ollama'],
        // Conserver le modele charge en VRAM entre les tours de conversation
        skipRelease: true,
        prepare: async ({ setPhase }) => {
          await preparePack(setPhase)
        },
        ollamaModel: activeModel,
        job: async ({ setPhase }) => {
          const taskContext = await prepareTaskIntelligence({
            module: 'conversation',
            prompt: text,
            model: preparedContext.some((file) => file.imageBase64) ? visionModel : activeModel,
            files: preparedContext,
            setPhase,
            phaseBase: 32,
            phaseSpan: 18,
          })

          return runConversationTurn({
            model: activeModel,
            messages: [...messages, pendingUserMessage],
            userInput: taskContext.effectivePrompt,
            voiceMode,
            signal: controller.signal,
            onToken: appendStreamContent,
            onEvent: (event) => {
              if (event.type === 'stage') {
                setRunStage(event.stage, event.label, event.detail, event.progress, event.timelineStatus)
                return
              }

              if (event.type === 'analysis') {
                setRunAnalysis(event.analysis)
                return
              }

              if (event.type === 'verification') {
                setRunVerification(event.verification)
                return
              }

              // 'intent' event — Aurora suggère un module ; on stocke pour
              // afficher un chip "→ ouvre module X" cliquable dans le header.
              if (event.type === 'intent' && event.confidence > 0.4) {
                setSuggestedRoute({
                  moduleId: event.moduleId as ModuleId,
                  confidence: event.confidence,
                  hint: event.hint,
                })
              }
            },
          })
        },
      })

      addMessage({ role: 'assistant', content: result.finalText })
      finishRun()
      if (activeTrackerIdRef.current) {
        completeGeneration(activeTrackerIdRef.current, {})
        activeTrackerIdRef.current = null
      }
      // Narration vocale de la reponse si activee (fire-and-forget)
      void narrateText(result.finalText)
    } catch (error: unknown) {
      const currentStream = useChatStore.getState().streamContent
      if (error instanceof Error && error.name === 'AbortError') {
        if (activeTrackerIdRef.current) {
          failGeneration(activeTrackerIdRef.current, 'Interrompu par l\'utilisateur')
          activeTrackerIdRef.current = null
        }
        if (currentStream.trim()) {
          addMessage({ role: 'assistant', content: `${currentStream}\n\n[Interrompu]` })
        }
        resetRun()
      } else {
        const rawMessage = getErrorMessage(error, 'Le pipeline conversation a echoue sans detail exploitable.')
        if (activeTrackerIdRef.current) {
          failGeneration(activeTrackerIdRef.current, rawMessage)
          activeTrackerIdRef.current = null
        }
        // Humaniser les erreurs courantes pour l'utilisateur
        let userMessage = rawMessage
        if (/ollama.*ne repond/i.test(rawMessage) || /connection.*refused/i.test(rawMessage) || /timeout/i.test(rawMessage)) {
          userMessage = 'Le service LLM local (Ollama) est en cours de demarrage. Aurora a tente 3 fois de se reconnecter. Reessaie dans quelques secondes — le modele est probablement en train de charger en memoire.'
        } else if (/comfyui.*ne repond/i.test(rawMessage)) {
          userMessage = 'Le service de generation visuelle (ComfyUI) n est pas encore pret. Reessaie dans quelques secondes.'
        } else if (/model.*not found/i.test(rawMessage) || /modele.*introuvable/i.test(rawMessage)) {
          userMessage = `Le modele demande n est pas installe localement. Verifie que le modele "${activeModel}" est bien telecharge dans Ollama.`
        }
        addMessage({ role: 'assistant', content: userMessage })
        failRun(rawMessage)
      }
    } finally {
      setStreaming(false)
      setStreamContent('')
    }
  }, [
    input,
    isStreaming,
    narrationEnabled,
    addMessage,
    appendStreamContent,
    executeWithRuntime,
    finishRun,
    activeModel,
    contextFiles,
    messages,
    resetRun,
    setRunAnalysis,
    setRunStage,
    setRunVerification,
    setStreaming,
    startRun,
    failRun,
    preparePack,
    visionModel,
    narrateText,
    trackGeneration,
    completeGeneration,
    failGeneration,
  ])

  // Synchroniser la ref a chaque render pour que stopRecordingAndTranscribe ait toujours la derniere version
  handleSendRef.current = handleSend

  const handleStop = () => {
    abortRef.current?.abort()
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const quickPrompts = [
    'Clarifie ma demande.',
    'Verifie mon idee.',
    'Produis une version finale.',
  ]

  const applyQuickPrompt = (prompt: string) => {
    setInput(prompt)
    requestAnimationFrame(() => {
      inputRef.current?.focus()
    })
  }

  const showStatusPanel = isStreaming || messages.length > 0 || runState.stage !== 'idle'
  const hardwareSummary = hardware
    ? `${hardware.cores} coeurs / ${Math.round(hardware.ram_gb)} Go`
    : 'Detection'

  return (
    <div className="relative grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 aurora-mesh opacity-40" />
        <div className="absolute -top-32 left-1/4 h-72 w-72 rounded-full bg-cyan-500/15 blur-3xl" />
      </div>
      <div className="relative flex min-h-0 flex-col gap-3 p-2 sm:gap-4 sm:p-4 lg:p-5">
        <div className="holo-card holo-card-cyan px-3 py-3 sm:px-5 sm:py-5">
          <div className="flex flex-wrap items-start justify-between gap-3 sm:gap-4">
            <div className="flex gap-3 items-start">
              <div style={{ width: 64, height: 80, flexShrink: 0 }}>
                <LyraCharacter
                  phase={isStreaming ? 'speaking' : runState.stage !== 'idle' ? 'thinking' : 'idle'}
                  emotion={isStreaming ? 'happy' : runState.stage !== 'idle' ? 'focus' : 'curious'}
                  accent="#67d2ff"
                  size={64}
                />
              </div>
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-500/10 px-2 py-0.5 text-[10px] text-cyan-100 sm:px-3 sm:py-1 sm:text-[11px]">
                  <MessageCircle size={12} className="text-cyan-300" />
                  <span className="mono-kicker text-[9px]">IA locale · Copilot · Lyra</span>
                </div>
                <h1 className="mt-2 text-2xl font-black tracking-tight sm:mt-4 sm:text-4xl lg:text-5xl">
                  <span className="gradient-text-ocean">Copilote global</span>
                </h1>
              <ConversationLiveTelemetry input={input} messages={messages} model={mainModel} />
              {/* v83q — Indicateur cache hit : si la dernière étape du run était
                  un "Cache", on l'affiche en chip. Permet à l'utilisateur de
                  comprendre pourquoi la réponse était instantanée. */}
              {runState.timeline.some((t) => t.label === 'Cache') && (
                <div className="mt-1 inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-mono text-emerald-200">
                  <span>⚡ cache HIT</span>
                  <span className="opacity-60">· servi sans appel modèle</span>
                </div>
              )}
              {isStreaming && streamRate > 0 && (
                <div className="mt-1 inline-flex items-center gap-1 rounded-md border border-cyan-500/30 bg-cyan-500/15 px-2 py-0.5 text-[10px] font-mono text-cyan-200">
                  <span className="animate-pulse">●</span>
                  <span>{streamRate} tok/s</span>
                </div>
              )}
              {suggestedRoute && suggestedRoute.moduleId !== 'conversation' && (
                <div className="mt-1 inline-flex items-center gap-2 rounded-md border border-violet-400/40 bg-violet-500/15 px-2 py-1 text-[11px] text-violet-100">
                  <span className="font-mono opacity-70">→</span>
                  <span>{suggestedRoute.hint}</span>
                  <button
                    onClick={() => { routeToModule(suggestedRoute.moduleId); setSuggestedRoute(null) }}
                    className="ml-1 rounded bg-violet-400/25 border border-violet-400/40 px-2 py-0.5 text-[10px] font-mono hover:bg-violet-400/40"
                  >ouvrir {suggestedRoute.moduleId}</button>
                  <button
                    onClick={() => setSuggestedRoute(null)}
                    aria-label="ignorer"
                    className="text-violet-200/60 hover:text-violet-100"
                  >×</button>
                </div>
              )}
              <div className="mt-3">
                <ExpertPromptVisualizer />
              </div>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-36 sm:w-52">
                <SessionSwitcher module="conversation" onSessionChange={() => clearMessages()} />
              </div>
              <button
                onClick={() => {
                  if (messages.length === 0) return
                  const md = [
                    `# Conversation Aurora IA`,
                    `_${new Date().toLocaleString('fr-FR')}_`,
                    '',
                    ...messages.map((msg) => `**${msg.role === 'user' ? 'Moi' : msg.role === 'assistant' ? 'Aurora' : msg.role}** :\n\n${msg.content}\n`),
                  ].join('\n')
                  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
                  const url = URL.createObjectURL(blob)
                  const anchor = document.createElement('a')
                  anchor.href = url
                  anchor.download = `aurora-conversation-${Date.now()}.md`
                  anchor.click()
                  setTimeout(() => URL.revokeObjectURL(url), 1000)
                }}
                disabled={messages.length === 0}
                className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-2 text-[11px] text-aurora-text transition-colors hover:border-aurora-accent active:bg-aurora-accent/10 disabled:opacity-40 disabled:cursor-not-allowed sm:px-3"
                title="Exporter la conversation en .md"
              >
                <span className="inline-flex items-center gap-1.5 sm:gap-2">
                  <Download size={14} />
                  <span className="hidden sm:inline">Export</span>
                </span>
              </button>
              <button
                onClick={() => {
                  if (messages.length === 0) return
                  const text = messages
                    .map((msg) => `${msg.role === 'user' ? 'Moi' : 'Aurora'} : ${msg.content}`)
                    .join('\n\n')
                  navigator.clipboard?.writeText(text).catch(() => undefined)
                }}
                disabled={messages.length === 0}
                className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-2 text-[11px] text-aurora-text transition-colors hover:border-aurora-accent active:bg-aurora-accent/10 disabled:opacity-40 disabled:cursor-not-allowed sm:px-3"
                title="Copier la conversation"
              >
                <span className="inline-flex items-center gap-1.5 sm:gap-2">
                  <Copy size={14} />
                </span>
              </button>
              <button
                onClick={() => {
                  if (isStreaming) return
                  const lastUser = popLastAssistantTurn()
                  if (!lastUser) return
                  setTimeout(() => { void handleSend(lastUser) }, 60)
                }}
                disabled={isStreaming || messages.length === 0}
                className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-2 text-[11px] text-aurora-text transition-colors hover:border-aurora-accent active:bg-aurora-accent/10 disabled:opacity-40 disabled:cursor-not-allowed sm:px-3"
                title="Regenerer la derniere reponse"
              >
                <span className="inline-flex items-center gap-1.5 sm:gap-2">
                  <Sparkles size={14} />
                  <span className="hidden sm:inline">Regen</span>
                </span>
              </button>
              <button
                onClick={() => {
                  if (messages.length === 0 || confirm('Effacer la conversation en cours ?')) {
                    clearMessages()
                  }
                }}
                className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-2 text-[11px] text-aurora-text transition-colors hover:border-aurora-red active:bg-aurora-red/10 sm:px-3"
                title="Effacer la conversation"
              >
                <span className="inline-flex items-center gap-1.5 sm:gap-2">
                  <Trash2 size={14} />
                  <span className="hidden sm:inline">Vider</span>
                </span>
              </button>
            </div>
          </div>

          <div className="mt-3 grid gap-3 sm:mt-5 sm:gap-4 xl:grid-cols-[minmax(0,1fr)_13rem]">
            <div>
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ecris ta demande ici."
                rows={3}
                className="min-h-[6rem] w-full resize-none border-none bg-transparent text-sm leading-relaxed text-aurora-text outline-none placeholder:text-aurora-text-dim sm:min-h-[13rem] sm:text-base"
                disabled={isStreaming}
              />

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <VoicePushToTalk
                  onTranscript={(text) => setInput((prev) => (prev.trim() ? `${prev} ${text}` : text))}
                  label="Dicter ton message"
                  size={36}
                />
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => applyQuickPrompt(prompt)}
                    className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-2 text-xs text-aurora-text transition-colors hover:border-white/18"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              <div className="mt-4">
                <ContextFilesField
                  files={contextFiles}
                  onFilesChange={setContextFiles}
                  accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
                  hint="Ajoute images, PDF, textes ou tableurs pour enrichir la conversation."
                />
              </div>
            </div>

            <div className="grid gap-3">
              <SmallCard icon={Monitor} label="Runtime" value={getRuntimeLabel()} />
              <SmallCard icon={Cpu} label="Machine" value={hardwareSummary} />
              <SmallCard icon={ShieldCheck} label="Modele" value={activeModel} />

              {isStreaming ? (
                <button
                  onClick={handleStop}
                  className="cut-panel-soft border border-aurora-red/20 bg-aurora-red/10 px-4 py-4 text-left text-sm font-medium text-aurora-text transition-colors hover:bg-aurora-red/14"
                >
                  <span className="inline-flex items-center gap-2">
                    <StopCircle size={16} className="text-aurora-red" />
                    <span>Arreter</span>
                  </span>
                </button>
              ) : (
                <button
                  onClick={() => void handleSend()}
                  disabled={!input.trim()}
                  className={`cut-panel-soft px-4 py-4 text-left text-sm font-medium transition-all ${
                    input.trim()
                      ? 'border border-white/18 bg-[linear-gradient(135deg,rgba(116,232,255,0.18),rgba(255,107,61,0.18))] text-white hover:opacity-92'
                      : 'border border-white/8 bg-white/[0.03] text-aurora-text-dim'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <Send size={16} />
                    <span>Lancer</span>
                  </span>
                </button>
              )}

              {/* Controles vocaux */}
              <button
                onClick={() => isRecording ? void stopRecordingAndTranscribe() : void startRecording()}
                disabled={isStreaming}
                title={isRecording ? 'Arreter l\'enregistrement' : 'Parler au copilote'}
                className={`cut-panel-soft px-4 py-3 text-left text-sm font-medium transition-all ${
                  isRecording
                    ? 'border border-aurora-accent/40 bg-aurora-accent/10 text-white'
                    : 'border border-white/10 bg-white/[0.04] text-aurora-text-dim hover:border-white/18'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  {isRecording ? (
                    <>
                      <motion.span
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 1, repeat: Infinity }}
                        className="h-2 w-2 rounded-full bg-aurora-accent"
                      />
                      <MicOff size={15} className="text-aurora-accent" />
                      <span>Arreter</span>
                    </>
                  ) : (
                    <>
                      <Mic size={15} />
                      <span>Parler</span>
                    </>
                  )}
                </span>
              </button>

              <button
                onClick={() => setNarrationEnabled((value) => !value)}
                title={narrationEnabled ? 'Desactiver la narration vocale' : 'Activer la narration vocale'}
                className={`cut-panel-soft px-4 py-3 text-left text-xs transition-all ${
                  narrationEnabled
                    ? 'border border-aurora-green/25 bg-aurora-green/8 text-aurora-text'
                    : 'border border-white/8 bg-white/[0.03] text-aurora-text-dim'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  {narrationEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
                  <span>{narrationEnabled ? 'Narration active' : 'Narration off'}</span>
                </span>
              </button>

              {/* Bouton Chat Vocal Live → ouvre l'overlay avec avatar */}
              <button
                onClick={() => setVoicePanelOpen(true)}
                className="cut-panel-soft border border-indigo-400/20 bg-indigo-500/[0.06] px-4 py-3 text-left text-sm font-medium transition-all hover:border-indigo-400/35 hover:bg-indigo-500/[0.10]"
              >
                <span className="inline-flex items-center gap-2 text-indigo-300/80">
                  <Radio size={15} />
                  <span>Chat Vocal Live</span>
                </span>
              </button>

              {voiceStatus && (
                <div className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-[11px] text-aurora-text-dim">
                  {voiceStatus}
                  {sttModelUsed && <span className="ml-1 text-aurora-accent">({sttModelUsed})</span>}
                </div>
              )}
            </div>
          </div>
        </div>

        {showStatusPanel && (
          <TurnStatusPanel runState={runState} model={activeModel} ollamaReady={ollamaReady} />
        )}

        <RecoveryBanner
          recovery={recovery}
          onRetry={(gen) => { setInput(gen.prompt) }}
        />

        <div ref={scrollRef} className="scroll-shell min-h-0 flex-1 overflow-y-auto pr-1">
          {messages.length === 0 && !isStreaming ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
              <div className="cut-panel border border-white/10 bg-white/[0.04] px-5 py-5">
                <div className="grid gap-3 sm:grid-cols-3">
                  <SmallCard icon={Monitor} label="Runtime" value={getRuntimeLabel()} />
                  <SmallCard icon={Cpu} label="Machine" value={hardwareSummary} />
                  <SmallCard icon={ShieldCheck} label="Modele" value={activeModel} />
                </div>
              </div>

              <div className="grid gap-3">
                <SmallCard icon={ListChecks} label="Mode" value="Clarifier" />
                <SmallCard icon={Gauge} label="Mode" value="Verifier" />
                <SmallCard icon={Sparkles} label="Mode" value="Produire" />
              </div>
            </div>
          ) : (
            <div className="space-y-5 pb-2">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} msg={msg} onNarrate={(text) => void narrateText(text, true)} />
              ))}

              {isStreaming && streamContent && (
                <StreamingBubble content={streamContent} label={runState.label || 'Preparation'} />
              )}

              {isStreaming && !streamContent && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-aurora-text-dim"
                >
                  <Loader2 size={16} className="animate-spin text-aurora-accent" />
                  <span>{runState.detail || 'Preparation en cours...'}</span>
                </motion.div>
              )}
            </div>
          )}
        </div>
      </div>

      <aside className="hidden min-h-0 xl:block">
        <div className="grid h-full gap-4 p-4 pl-0">
          <div className="cut-panel border border-white/10 bg-white/[0.04] px-4 py-4">
            <p className="mono-kicker text-[9px] text-aurora-text-dim">Local</p>
            <div className="mt-4 grid gap-3">
              <SmallCard icon={Bot} label="Ollama" value={ollamaReady ? 'pret ou auto-start' : 'demarrage auto a la demande'} />
              <SmallCard icon={Sparkles} label="ComfyUI" value={services.comfyui ? 'pret' : 'a la demande'} />
            </div>
            {installedModels.length > 1 && (
              <div className="mt-3">
                <label className="block text-[10px] text-aurora-text-dim mb-1">Modele LLM</label>
                <select
                  value={mainModel}
                  onChange={(e) => setMainModel(e.target.value)}
                  className="w-full rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1.5 text-xs text-aurora-text outline-none focus:border-aurora-accent"
                >
                  {installedModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <ModuleAssetPackCard pack={assetPack} />
          <ConnectorRecommendationsPanel module="conversation" compact />

          <div className="cut-panel border border-white/10 bg-white/[0.04] px-4 py-4">
            <p className="mono-kicker text-[9px] text-aurora-text-dim">Modules</p>
            <div className="mt-4 grid gap-3">
              <ModuleShortcut moduleId="image" label="Image" icon={ImageIcon} />
              <ModuleShortcut moduleId="code" label="Code" icon={Code2} />
              <ModuleShortcut moduleId="video" label="Video" icon={Video} />
              <ModuleShortcut moduleId="drawing" label="Dessin" icon={Paintbrush} />
              <ModuleShortcut moduleId="3d" label="3D" icon={Box} />
              <ModuleShortcut moduleId="learning" label="Academie" icon={GraduationCap} />
            </div>
          </div>
        </div>
      </aside>

      {/* ===== OVERLAY CHAT VOCAL LIVE ===== */}
      <AnimatePresence>
        {voicePanelOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/55 backdrop-blur-sm"
            onClick={() => setVoicePanelOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 16 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onClick={(e) => e.stopPropagation()}
              data-voice-panel="true"
              data-overlay="true"
              role="dialog"
              className="relative w-full max-w-[380px] overflow-hidden rounded-2xl border border-white/10 bg-[#0b0d1c] shadow-2xl"
              style={{ maxHeight: '88vh' }}
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full border border-indigo-400/30 bg-indigo-500/15">
                    <Radio size={10} className="text-indigo-300" />
                  </div>
                  <span className="text-[11px] font-medium text-white/60">Chat Vocal Live</span>
                </div>
                <button
                  onClick={() => setVoicePanelOpen(false)}
                  className="flex h-7 w-7 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-white/50 hover:bg-white/[0.12] hover:text-white/80"
                >
                  <X size={13} />
                </button>
              </div>

              <Suspense fallback={
                <div className="grid min-h-[300px] place-items-center">
                  <span className="text-[12px] text-white/30">Chargement...</span>
                </div>
              }>
                <VoiceCopilotView
                  onClose={() => setVoicePanelOpen(false)}
                  onMessage={(userText, assistantText) => {
                    addMessage({ role: 'user', content: userText })
                    addMessage({ role: 'assistant', content: assistantText })
                  }}
                />
              </Suspense>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
