/**
 * auroraVoice — singleton vocal manager utilisable depuis n'importe quel module.
 *
 * Capacités:
 *  - `speak(text, opts?)` : TTS via bridge (Kokoro), fallback Web Speech API.
 *  - `listen(callback, opts?)` : STT one-shot (micro + VAD basique).
 *  - `announce(module, kind, summary?)` : annonce contextuelle de fin de génération.
 *  - `subscribe(event, cb)` : flux d'événements (transcript, phase).
 *  - `setMuted`, `setLanguage`, `setRate`, `isMuted` : préférences globales persistées.
 *
 * Indépendant de React : peut être appelé depuis un store, un service ou un hook.
 * Les vues exposent un bouton micro via `<VoicePushToTalk />` qui appelle `listen()`.
 */
import { getBridgeUrl } from '../utils/runtime'
import { safeParseJson } from '../utils/errors'
import { tryHandleVoiceCommand } from '../utils/voiceCommands'
import { CoalesceTracker } from '../utils/coalesceTracker'
import { buildAnnounceText } from '../utils/announceText'
import { getAgent } from './auroraAgents'
import type { ModuleId } from '../types/app'

// ───────────────────────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────────────────────

export type VoicePhase = 'idle' | 'listening' | 'transcribing' | 'thinking' | 'speaking'

export interface SpeakOptions {
  /** 'short' = phrase courte, 'rich' = lecture longue avec prosodie */
  detail?: 'short' | 'rich'
  /** Annule toute parole en cours avant de parler */
  interrupt?: boolean
  /** Force le moteur (sinon: kokoro puis web-speech) */
  engine?: 'auto' | 'web-speech'
  lang?: 'fr' | 'en'
  /** Hint persona vocal de l'agent (lyra-soft, iris-bright, etc.). Transmis au bridge. */
  voicePersona?: string
  /** Module : si fourni et voicePersona absent, on prend l'agent de ce module. */
  module?: ModuleId
}

export interface ListenOptions {
  /** Timeout total en ms (par défaut 12 000) */
  maxMs?: number
  /** Durée de silence avant arrêt auto (par défaut 1 800 ms) */
  silenceMs?: number
  lang?: 'fr' | 'en'
}

export type AnnounceKind = 'started' | 'completed' | 'failed' | 'cancelled'

export interface AnnouncePayload {
  module: ModuleId
  kind: AnnounceKind
  /** Petit résumé contextuel (titre du contenu, durée, …) */
  summary?: string
}

interface Prefs {
  muted: boolean
  language: 'fr' | 'en'
  rate: number
  announceOnComplete: boolean
  announceOnFail: boolean
}

type Listener<T = unknown> = (payload: T) => void

// ───────────────────────────────────────────────────────────────────────────
// État singleton
// ───────────────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'aurora-voice-prefs-v1'

function loadPrefs(): Prefs {
  if (typeof localStorage === 'undefined') {
    return { muted: false, language: 'fr', rate: 1, announceOnComplete: true, announceOnFail: true }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { muted: false, language: 'fr', rate: 1, announceOnComplete: true, announceOnFail: true, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return { muted: false, language: 'fr', rate: 1, announceOnComplete: true, announceOnFail: true }
}

let prefs: Prefs = loadPrefs()
let phase: VoicePhase = 'idle'
let currentAudio: HTMLAudioElement | null = null
let currentUtterance: SpeechSynthesisUtterance | null = null
let speakSeq = 0

const listeners = new Map<string, Set<Listener>>()

function persistPrefs() {
  try { localStorage?.setItem(STORAGE_KEY, JSON.stringify(prefs)) } catch { /* ignore */ }
}

function emit<T>(event: string, payload: T) {
  const set = listeners.get(event)
  if (!set) return
  set.forEach(cb => { try { (cb as Listener<T>)(payload) } catch (e) { console.warn('[voice] listener error:', e) } })
}

function setPhase(next: VoicePhase) {
  if (phase === next) return
  phase = next
  emit('phase', next)
}

// ───────────────────────────────────────────────────────────────────────────
// TTS
// ───────────────────────────────────────────────────────────────────────────

async function speakViaBridge(text: string, lang: 'fr' | 'en', voicePersona?: string): Promise<boolean> {
  try {
    const bridgeUrl = getBridgeUrl()
    const endpoint = bridgeUrl ? `${bridgeUrl}/api/voice/tts` : '/api/voice/tts'
    const payload: Record<string, unknown> = { text: text.slice(0, 2000), lang }
    if (voicePersona) payload.voice = voicePersona
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(8000),
    })
    if (!resp.ok) return false
    const data = await safeParseJson<{ ok?: boolean; audio_url?: string }>(resp, 'auroraVoice TTS')
    if (!data.ok || !data.audio_url) return false
    const audioUrl = bridgeUrl ? `${bridgeUrl}${data.audio_url}` : data.audio_url

    return await new Promise<boolean>((resolve) => {
      const audio = new Audio()
      currentAudio = audio
      audio.preload = 'auto'
      audio.src = audioUrl
      audio.volume = 1
      let done = false
      const settle = (ok: boolean) => { if (done) return; done = true; resolve(ok) }
      audio.onended = () => settle(true)
      audio.onerror = () => settle(false)
      audio.oncanplay = () => { audio.play().catch(() => settle(false)) }
      // watchdog 1.5 s : si pas de lecture réelle, on échoue
      setTimeout(() => {
        if (!done && (audio.currentTime <= 0.05 || audio.paused)) settle(false)
      }, 1500)
    })
  } catch {
    return false
  }
}

function speakViaWebSpeech(text: string, lang: 'fr' | 'en', rate: number): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) { resolve(); return }
    try {
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        window.speechSynthesis.cancel()
      }
    } catch { /* ignore */ }
    const speak = () => {
      const utter = new SpeechSynthesisUtterance(text)
      utter.lang = lang === 'en' ? 'en-US' : 'fr-FR'
      utter.rate = Math.max(0.5, Math.min(2, rate * 0.95))
      utter.pitch = 1.05
      utter.volume = 1
      const voices = window.speechSynthesis.getVoices()
      const prefix = lang === 'en' ? 'en' : 'fr'
      const matched =
        voices.find(v => v.lang.startsWith(prefix) && v.localService)
        || voices.find(v => v.lang.startsWith(prefix))
        || voices[0]
      if (matched) utter.voice = matched
      currentUtterance = utter
      const guard = setTimeout(() => { resolve() }, Math.max(4000, text.length * 90))
      utter.onend = () => { clearTimeout(guard); resolve() }
      utter.onerror = () => { clearTimeout(guard); resolve() }
      window.speechSynthesis.speak(utter)
    }
    const voices = window.speechSynthesis.getVoices()
    if (voices.length) speak()
    else {
      const onChange = () => { window.speechSynthesis.removeEventListener('voiceschanged', onChange); speak() }
      window.speechSynthesis.addEventListener('voiceschanged', onChange)
      setTimeout(() => { window.speechSynthesis.removeEventListener('voiceschanged', onChange); speak() }, 1200)
    }
  })
}

// File d'attente pour les annonces non-interruptives. Sans queue, deux
// completions rapprochées (ex: image fini à T+0, code fini à T+0.5) jouaient
// simultanément leurs audios → cacophonie. Maintenant on enchaîne.
const speakQueue: Array<{ text: string; opts: SpeakOptions; resolve: () => void }> = []
let queueProcessing = false

async function processQueue() {
  if (queueProcessing) return
  queueProcessing = true
  try {
    while (speakQueue.length > 0) {
      const item = speakQueue.shift()!
      await speakNow(item.text, item.opts)
      item.resolve()
    }
  } finally {
    queueProcessing = false
  }
}

/** Exécution effective d'un speak — sans gestion de queue. */
async function speakNow(text: string, opts: SpeakOptions): Promise<void> {
  if (!text || !text.trim()) return
  if (prefs.muted) return
  const seq = ++speakSeq
  if (opts.interrupt !== false) stopSpeaking()
  setPhase('speaking')
  const lang = opts.lang || prefs.language
  // Résolution du persona vocal : explicite > module agent > rien
  let voicePersona = opts.voicePersona
  if (!voicePersona && opts.module) {
    try { voicePersona = getAgent(opts.module).voice } catch { /* ignore */ }
  }
  // tronquer pour le mode "short"
  const payload = opts.detail === 'short' && text.length > 200 ? text.slice(0, 200) : text.slice(0, 2000)
  let played = false
  if (opts.engine !== 'web-speech') {
    played = await speakViaBridge(payload, lang, voicePersona)
  }
  if (!played && speakSeq === seq) {
    await speakViaWebSpeech(payload, lang, prefs.rate)
  }
  if (speakSeq === seq) setPhase('idle')
}

async function speakInternal(text: string, opts: SpeakOptions): Promise<void> {
  // interrupt=true (défaut explicite ou via speak() inline) → on saute la queue
  // et on parle tout de suite. Utile pour le TTS chat conversationnel.
  if (opts.interrupt === true) {
    return speakNow(text, opts)
  }
  // interrupt=false → on respecte la file pour éviter de superposer les annonces.
  return new Promise<void>((resolve) => {
    speakQueue.push({ text, opts, resolve })
    void processQueue()
  })
}

export function speak(text: string, opts: SpeakOptions = {}): Promise<void> {
  return speakInternal(text, opts)
}

/** Vide la file d'attente sans interrompre la lecture en cours. */
export function clearSpeakQueue(): void {
  while (speakQueue.length > 0) {
    const item = speakQueue.shift()
    item?.resolve()
  }
}

/**
 * Shortcut : parle avec la voix de l'agent du module spécifié.
 * Pratique pour les hooks de chaque vue qui veulent une narration locale
 * (ex. "voici les variantes Iris") sans avoir à passer par announce().
 */
export function speakAs(module: ModuleId, text: string, opts: Omit<SpeakOptions, 'module'> = {}): Promise<void> {
  return speakInternal(text, { ...opts, module })
}

export function stopSpeaking() {
  speakSeq++
  try { currentAudio?.pause(); if (currentAudio) currentAudio.src = ''; currentAudio = null } catch { /* ignore */ }
  try { window.speechSynthesis?.cancel() } catch { /* ignore */ }
  currentUtterance = null
  if (phase === 'speaking') setPhase('idle')
}

// ───────────────────────────────────────────────────────────────────────────
// STT one-shot
// ───────────────────────────────────────────────────────────────────────────

async function encodeAsWav(blob: Blob): Promise<Blob> {
  const ctx = new AudioContext()
  try {
    const arr = await blob.arrayBuffer()
    const audioBuffer = await ctx.decodeAudioData(arr)
    const sr = audioBuffer.sampleRate
    let samples: Float32Array
    if (audioBuffer.numberOfChannels > 1) {
      const a = audioBuffer.getChannelData(0)
      const b = audioBuffer.getChannelData(1)
      samples = new Float32Array(a.length)
      for (let i = 0; i < a.length; i++) samples[i] = (a[i] + b[i]) * 0.5
    } else {
      samples = audioBuffer.getChannelData(0)
    }
    const n = samples.length
    const buf = new ArrayBuffer(44 + n * 2)
    const view = new DataView(buf)
    const w = (o: number, s: string) => { for (let i = 0; i < 4; i++) view.setUint8(o + i, s.charCodeAt(i)) }
    w(0, 'RIFF'); view.setUint32(4, 36 + n * 2, true); w(8, 'WAVE')
    w(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
    view.setUint16(22, 1, true); view.setUint32(24, sr, true); view.setUint32(28, sr * 2, true)
    view.setUint16(32, 2, true); view.setUint16(34, 16, true)
    w(36, 'data'); view.setUint32(40, n * 2, true)
    for (let i = 0; i < n; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return new Blob([buf], { type: 'audio/wav' })
  } finally {
    await ctx.close()
  }
}

async function transcribe(blob: Blob, lang: 'fr' | 'en'): Promise<string> {
  let audioBlob = blob
  try { audioBlob = await encodeAsWav(blob) } catch { /* ignore */ }
  const bridgeUrl = getBridgeUrl()
  const endpoint = bridgeUrl ? `${bridgeUrl}/api/voice/stt` : '/api/voice/stt'
  const fd = new FormData()
  fd.append('audio', audioBlob, 'voice.wav')
  fd.append('language', lang)
  const r = await fetch(endpoint, { method: 'POST', body: fd })
  const result = await safeParseJson<{ ok?: boolean; text?: string }>(r, 'auroraVoice STT')
  if (result.text && result.text !== '(silence detecte)') return result.text
  return ''
}

let activeRecording: { stop: () => void; cancel: () => void } | null = null

export interface ListenHandle {
  /** Termine l'enregistrement et déclenche la transcription */
  stop: () => void
  /** Avorte sans transcrire */
  cancel: () => void
}

export function isListening(): boolean {
  return phase === 'listening' || phase === 'transcribing'
}

export async function listen(
  onTranscript: (text: string) => void,
  opts: ListenOptions = {},
): Promise<ListenHandle> {
  if (activeRecording) {
    // Si on relance, on annule l'enregistrement courant pour éviter d'avoir 2 micros actifs.
    activeRecording.cancel()
  }
  const lang = opts.lang || prefs.language
  const maxMs = opts.maxMs ?? 12000
  const silenceMs = opts.silenceMs ?? 1800

  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
  } catch (e) {
    setPhase('idle')
    emit('error', { stage: 'mic', error: e instanceof Error ? e.message : String(e) })
    throw e
  }

  setPhase('listening')
  emit('listen-start', { lang })

  const ctx = new AudioContext()
  const src = ctx.createMediaStreamSource(stream)
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 1024
  src.connect(analyser)
  const buffer = new Float32Array(analyser.fftSize)

  const candidateMimes = [
    'audio/webm;codecs=opus', 'audio/webm',
    'audio/mp4;codecs=mp4a.40.2', 'audio/mp4',
    'audio/ogg;codecs=opus', '',
  ]
  let rec: MediaRecorder | null = null
  for (const mime of candidateMimes) {
    if (mime && typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported && !MediaRecorder.isTypeSupported(mime)) continue
    try {
      rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      try { rec.start(250) } catch { try { rec.start() } catch { /* ignore */ } }
      if ((rec.state as string) === 'recording') break
      rec = null
    } catch { rec = null }
  }
  if (!rec) {
    stream.getTracks().forEach(t => t.stop())
    await ctx.close()
    setPhase('idle')
    throw new Error('MediaRecorder non supporté')
  }

  const chunks: Blob[] = []
  rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data) }
  const mime = rec.mimeType || 'audio/webm'

  let cancelled = false
  let raf = 0
  let maxTimer: ReturnType<typeof setTimeout> | null = null
  let spokeAt = 0
  let silenceAt = 0
  const NOISE = 0.012
  const MIN_SPEECH = 350

  const cleanup = () => {
    if (raf) cancelAnimationFrame(raf)
    if (maxTimer) clearTimeout(maxTimer)
    try { stream.getTracks().forEach(t => t.stop()) } catch { /* ignore */ }
    try { ctx.close() } catch { /* ignore */ }
    activeRecording = null
  }

  const finish = async () => {
    if (rec && rec.state === 'recording') {
      await new Promise<void>(res => { rec!.onstop = () => res(); try { rec!.stop() } catch { res() } })
    }
    if (cancelled) { cleanup(); setPhase('idle'); return }
    const blob = new Blob(chunks, { type: mime })
    cleanup()
    if (blob.size < 4000) { setPhase('idle'); return }
    setPhase('transcribing')
    try {
      const text = await transcribe(blob, lang)
      if (text) {
        emit('transcript', { text })
        // Commandes vocales globales : "ouvre le code", "passe en cyber"…
        // Si la phrase est interceptée comme commande, on speak la réponse
        // ET on saute le callback du module pour éviter d'injecter "ouvre le code" dans le prompt.
        const cmd = tryHandleVoiceCommand(text)
        if (cmd.handled) {
          speak(cmd.reply, { detail: 'short' })
        } else {
          onTranscript(text)
        }
      }
    } catch (e) {
      emit('error', { stage: 'stt', error: e instanceof Error ? e.message : String(e) })
    } finally {
      setPhase('idle')
    }
  }

  const vad = () => {
    if (!rec || rec.state !== 'recording') return
    analyser.getFloatTimeDomainData(buffer)
    let sum = 0
    for (let i = 0; i < buffer.length; i++) sum += buffer[i] * buffer[i]
    const rms = Math.sqrt(sum / buffer.length)
    emit('volume', rms)
    const now = Date.now()
    if (rms >= NOISE) {
      if (!spokeAt) spokeAt = now
      silenceAt = 0
    } else if (spokeAt) {
      if (!silenceAt) silenceAt = now
      if ((silenceAt - spokeAt) >= MIN_SPEECH && (now - silenceAt) >= silenceMs) {
        finish()
        return
      }
    }
    raf = requestAnimationFrame(vad)
  }
  raf = requestAnimationFrame(vad)
  maxTimer = setTimeout(() => { finish() }, maxMs)

  const handle: ListenHandle = {
    stop: () => { finish() },
    cancel: () => { cancelled = true; if (rec?.state === 'recording') try { rec.stop() } catch { /* ignore */ } else { cleanup(); setPhase('idle') } },
  }
  activeRecording = handle
  return handle
}

// ───────────────────────────────────────────────────────────────────────────
// Annonces contextuelles
// ───────────────────────────────────────────────────────────────────────────

// Pools + buildAnnouncement extraits vers utils/announceText.ts (testable).
// Anti-spam : si le même module+kind fire deux fois en moins de 2500ms,
// on ignore la seconde. Évite que 3 succès image en 2s déclenchent 3 annonces.
const announceCoalescer = new CoalesceTracker(2500)

// Compteur d'index pour casser la monotonie des phrases (RNG initial pour
// que deux sessions consécutives ne tirent pas la même phrase en première).
let _announceIndex = Math.floor(Math.random() * 1000)

export function announce(payload: AnnouncePayload, opts: SpeakOptions = {}): Promise<void> {
  if (payload.kind === 'completed' && !prefs.announceOnComplete) return Promise.resolve()
  if (payload.kind === 'failed' && !prefs.announceOnFail) return Promise.resolve()
  const key = `${payload.module}:${payload.kind}`
  if (!announceCoalescer.shouldAllow(key)) {
    // L'événement reste émis (pulse visuel, log) mais l'utterance est coalescée.
    emit('announce', { ...payload, coalesced: true })
    return Promise.resolve()
  }
  const text = buildAnnounceText(payload, opts.lang || prefs.language, _announceIndex++)
  emit('announce', payload)
  return speak(text, { detail: 'short', interrupt: false, module: payload.module, ...opts })
}

// ───────────────────────────────────────────────────────────────────────────
// Préférences
// ───────────────────────────────────────────────────────────────────────────

export function getPreferences(): Readonly<Prefs> { return prefs }
export function setMuted(muted: boolean) {
  prefs = { ...prefs, muted }
  persistPrefs()
  if (muted) {
    stopSpeaking()
    clearSpeakQueue()
  }
  emit('prefs', prefs)
}
export function isMuted(): boolean { return prefs.muted }
export function setLanguage(language: 'fr' | 'en') { prefs = { ...prefs, language }; persistPrefs(); emit('prefs', prefs) }
export function setRate(rate: number) { prefs = { ...prefs, rate: Math.max(0.5, Math.min(2, rate)) }; persistPrefs(); emit('prefs', prefs) }
export function setAnnouncePolicy(p: Partial<Pick<Prefs, 'announceOnComplete' | 'announceOnFail'>>) {
  prefs = { ...prefs, ...p }; persistPrefs(); emit('prefs', prefs)
}

// ───────────────────────────────────────────────────────────────────────────
// Pub/sub
// ───────────────────────────────────────────────────────────────────────────

export function subscribe<T = unknown>(event: 'phase' | 'volume' | 'transcript' | 'error' | 'announce' | 'prefs' | 'listen-start', cb: Listener<T>): () => void {
  const set = listeners.get(event) || new Set<Listener>()
  set.add(cb as Listener)
  listeners.set(event, set)
  return () => { set.delete(cb as Listener) }
}

export function getPhase(): VoicePhase { return phase }

// ───────────────────────────────────────────────────────────────────────────
// Util: dispatch d'événement DOM pour découplage cross-module
// ───────────────────────────────────────────────────────────────────────────

if (typeof window !== 'undefined') {
  window.addEventListener('aurora:voice-announce', ((ev: Event) => {
    const detail = (ev as CustomEvent<AnnouncePayload>).detail
    if (detail) announce(detail)
  }) as EventListener)
  window.addEventListener('aurora:voice-speak', ((ev: Event) => {
    const detail = (ev as CustomEvent<{ text: string; opts?: SpeakOptions }>).detail
    if (detail?.text) speak(detail.text, detail.opts || {})
  }) as EventListener)
  window.addEventListener('aurora:voice-stop', (() => stopSpeaking()) as EventListener)
}

export const auroraVoice = {
  speak,
  speakAs,
  stopSpeaking,
  clearSpeakQueue,
  listen,
  isListening,
  announce,
  subscribe,
  getPhase,
  getPreferences,
  setMuted,
  isMuted,
  setLanguage,
  setRate,
  setAnnouncePolicy,
}

export default auroraVoice
