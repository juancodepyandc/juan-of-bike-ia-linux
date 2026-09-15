import { useCallback, useEffect, useRef, useState } from 'react'
import { fsWriteBinary, getWorkspacePath, runPythonScript } from './useTauri.ts'
import { isTauriRuntime, getBridgeUrl, isCloudRuntime } from '../utils/runtime.ts'
import { safeParseJson } from '../utils/errors.ts'

/**
 * Décode n'importe quel format audio (WebM, Ogg…) et ré-encode en WAV PCM 16-bit mono.
 * Évite la dépendance à ffmpeg côté Python pour la transcription.
 */
async function encodeAsWav(blob: Blob): Promise<Blob> {
  const tmpCtx = new AudioContext()
  try {
    const arrayBuffer = await blob.arrayBuffer()
    const audioBuffer = await tmpCtx.decodeAudioData(arrayBuffer)
    const sampleRate = audioBuffer.sampleRate

    let samples: Float32Array
    if (audioBuffer.numberOfChannels > 1) {
      const ch0 = audioBuffer.getChannelData(0)
      const ch1 = audioBuffer.getChannelData(1)
      samples = new Float32Array(ch0.length)
      for (let i = 0; i < ch0.length; i++) samples[i] = (ch0[i] + ch1[i]) * 0.5
    } else {
      samples = audioBuffer.getChannelData(0)
    }

    const numSamples = samples.length
    const wavBuffer = new ArrayBuffer(44 + numSamples * 2)
    const view = new DataView(wavBuffer)
    const w4 = (o: number, s: string) => { for (let i = 0; i < 4; i++) view.setUint8(o + i, s.charCodeAt(i)) }

    w4(0, 'RIFF'); view.setUint32(4, 36 + numSamples * 2, true); w4(8, 'WAVE')
    w4(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    w4(36, 'data'); view.setUint32(40, numSamples * 2, true)

    for (let i = 0; i < numSamples; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }

    return new Blob([wavBuffer], { type: 'audio/wav' })
  } finally {
    await tmpCtx.close()
  }
}

export type VoiceLivePhase = 'idle' | 'listening' | 'transcribing' | 'thinking' | 'speaking'

/** Cue Rhubarb — frame-accurate mouth shape. value = A..H | X */
export interface RhubarbCue { start: number; end: number; value: string }

interface Opts {
  onTranscript: (text: string) => void | Promise<void>
  autoStart?: boolean
  language?: string
  stopOnSilence?: boolean
  maxRecordingMs?: number
  /** Chemin vers l image avatar. Si fourni et SadTalker installe, le TTS declenche
   *  la generation d un MP4 talking-head synchronise, dispo dans talkingVideoUrlRef. */
  avatarImage?: string | null
  /** Callback appele quand un nouveau MP4 talking-video est pret a jouer. */
  onTalkingVideo?: (videoUrl: string) => void
  /** Persona vocal Aurora (lyra-soft, iris-bright, ...). Si fourni, le bridge TTS
   *  selectionne la voix Edge-TTS mappee pour donner une identite distincte par agent. */
  voicePersona?: string | null
  /** Duree de silence (ms) avant de cloturer un tour. Defaut 2800. En examen on
   *  monte ce seuil pour laisser l eleve respirer/reflechir sans etre coupe. */
  silenceMs?: number
}

const NOISE = 0.015
const NOISE_LOW = 0.009
const SILENCE_MS = 2800
const MIN_SPEECH = 400
const MAX_REC = 60000
const ECHO_GUARD_MS = 5000
const NOISE_ECHO = 0.08

const SILENT_WAV = (() => {
  const sr = 44100, n = Math.floor(sr * 0.05)
  const b = new ArrayBuffer(44 + n * 2), v = new DataView(b)
  const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
  w(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); w(8, 'WAVE')
  w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true)
  w(36, 'data'); v.setUint32(40, n * 2, true)
  return URL.createObjectURL(new Blob([b], { type: 'audio/wav' }))
})()

export function useVoiceLive({ onTranscript, autoStart = false, language = 'fr', stopOnSilence = true, maxRecordingMs = MAX_REC, avatarImage = null, onTalkingVideo, voicePersona = null, silenceMs = SILENCE_MS }: Opts) {
  const [phase, setPhase] = useState<VoiceLivePhase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [volumeLevel, setVolumeLevel] = useState(0)
  const [speakingAmplitude, setSpeakingAmplitude] = useState(0)

  const phaseRef = useRef<VoiceLivePhase>('idle')
  const setP = (p: VoiceLivePhase) => { phaseRef.current = p; setPhase(p) }

  const streamRef = useRef<MediaStream | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const recRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const vadRef = useRef(0)
  const maxRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const spkIdRef = useRef(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const ampRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const rafRef = useRef<number>(0)
  const spokeRef = useRef(false)
  const spokeAtRef = useRef(0)
  const silAtRef = useRef(0)
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript
  const languageRef = useRef(language)
  languageRef.current = language
  const stopOnSilenceRef = useRef(stopOnSilence)
  stopOnSilenceRef.current = stopOnSilence
  const maxRecordingMsRef = useRef(maxRecordingMs)
  maxRecordingMsRef.current = maxRecordingMs
  const silenceMsRef = useRef(silenceMs)
  silenceMsRef.current = silenceMs
  const echoGuardRef = useRef(0)

  // Web Audio API — lecture TTS via BufferSource (pas de audio.src = URL)
  const ttsCtxRef = useRef<AudioContext | null>(null)
  const ttsAnalyserRef = useRef<AnalyserNode | null>(null)
  const ttsSourceRef = useRef<HTMLAudioElement | null>(null)

  // Formants TTS — mis à jour dans la boucle RAF, pas de re-render React
  const formantsRef = useRef<{ low: number; mid: number }>({ low: 0, mid: 0 })

  // Cues Rhubarb — mis à jour à chaque TTS, stables entre les cues
  const phonemeCuesRef = useRef<RhubarbCue[]>([])

  const continuousRef = useRef(false)
  const avatarImageRef = useRef<string | null>(avatarImage)
  avatarImageRef.current = avatarImage
  const onTalkingVideoRef = useRef(onTalkingVideo)
  onTalkingVideoRef.current = onTalkingVideo
  const voicePersonaRef = useRef<string | null>(voicePersona)
  voicePersonaRef.current = voicePersona
  const wantListenRef = useRef(false)
  // Guard contre les appels paralleles de startListenInternal (double-click, re-render).
  // Sans ce guard, on peut creer 2 MediaRecorder sur le meme stream -> "state is 'recording'" sur Edge.
  const isStartingRef = useRef(false)
  const [continuous, setContinuous] = useState(false)

  useEffect(() => {
    mountedRef.current = true
    if (!audioRef.current) { audioRef.current = new Audio(); audioRef.current.preload = 'auto' }
    return () => {
      mountedRef.current = false
      // Stop VAD loop (separate RAF from amplitude animation)
      if (vadRef.current) { cancelAnimationFrame(vadRef.current); vadRef.current = 0 }
      if (maxRef.current) { clearTimeout(maxRef.current); maxRef.current = null }
      if (recRef.current?.state === 'recording') { try { recRef.current.stop() } catch {} }
      if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = '' }
      if (ampRef.current) clearInterval(ampRef.current)
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = 0 }
      if (ttsSourceRef.current) { ttsSourceRef.current.pause(); ttsSourceRef.current.src = ''; ttsSourceRef.current = null }
      if (ttsCtxRef.current && ttsCtxRef.current.state !== 'closed') {
        ttsCtxRef.current.close().catch(() => {})
      }
      window.speechSynthesis?.cancel()
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
    }
  }, [])

  useEffect(() => {
    if (phase === 'idle' && wantListenRef.current && mountedRef.current) {
      wantListenRef.current = false
      const id = setTimeout(() => {
        if (mountedRef.current && phaseRef.current === 'idle' && continuousRef.current) {
          startListenInternal()
        }
      }, 600)
      return () => clearTimeout(id)
    }
  }, [phase])

  const getStream = useCallback(async () => {
    let s = streamRef.current
    if (s && s.getTracks().some(t => t.readyState === 'live')) return s
    s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    streamRef.current = s
    if (ctxRef.current) try { ctxRef.current.close() } catch {}
    ctxRef.current = new AudioContext()
    const src = ctxRef.current.createMediaStreamSource(s)
    const an = ctxRef.current.createAnalyser()
    an.fftSize = 1024; an.smoothingTimeConstant = 0.5
    src.connect(an)
    analyserRef.current = an
    return s
  }, [])

  const doTranscribe = useCallback(async (blob: Blob) => {
    if (!mountedRef.current) return
    setP('transcribing')
    try {
      let audioBlob = blob
      try {
        audioBlob = await encodeAsWav(blob)
      } catch (encErr) {
        console.warn('[V] WAV encode failed, using raw blob:', encErr)
      }

      let text = ''
      if (isTauriRuntime()) {
        const wp = await getWorkspacePath()
        const ap = `${wp}/temp/voice_live.wav`
        await fsWriteBinary(ap, Array.from(new Uint8Array(await audioBlob.arrayBuffer())))
        const out = await runPythonScript(`${wp}/python-services/voice_service.py`, ['--mode', 'stt', '--audio', ap, '--lang', languageRef.current])
        const lines = out.split('\n').filter(l => l.trim())
        const result = JSON.parse(lines[lines.length - 1])
        if (result.ok && result.text && result.text !== '(silence detecte)') {
          text = result.text
        } else if (!result.ok) {
          console.warn('[V] STT Python error:', result.error)
        }
      } else {
        const fd = new FormData()
        fd.append('audio', audioBlob, 'voice.wav')
        fd.append('language', languageRef.current)
        const r = await fetch(`${getBridgeUrl()}/api/voice/stt`, { method: 'POST', body: fd })
        const result = await safeParseJson<{ ok?: boolean; text?: string; error?: string }>(r, 'Voice STT')
        if (result.text && result.text !== '(silence detecte)') {
          text = result.text
        }
      }
      if (text) {
        await onTranscriptRef.current(text)
      }
    } catch (e) {
      console.error('[V] STT error:', e)
      setError('Erreur STT')
    } finally {
      if (mountedRef.current && phaseRef.current === 'transcribing') {
        setP('idle')
        if (continuousRef.current) {
          wantListenRef.current = true
        }
      }
    }
  }, [])

  const startListenInternal = useCallback(async () => {
    if (phaseRef.current !== 'idle') return
    // Guard double-call (double-click, re-render, auto-continuation).
    if (isStartingRef.current) {
      console.warn('[useVoiceLive] startListen already in progress, ignoring duplicate call')
      return
    }
    isStartingRef.current = true

    // iOS Safari CRITIQUE: getUserMedia DOIT etre appele AVANT tout setState
    // ou await audio.play(). Sinon le user gesture est perdu et Safari rejette
    // silencieusement la demande de permission.
    let stream: MediaStream
    try {
      stream = await getStream()
    } catch (e) {
      isStartingRef.current = false
      if (!mountedRef.current) return
      const err = e instanceof Error ? e : new Error(String(e))
      const name = err.name || ''
      const isSecure = typeof window !== 'undefined'
        && (window.isSecureContext
            || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname)
            || window.location.protocol === 'tauri:')
      let friendly = err.message || 'Erreur micro inconnue'
      if (!isSecure) {
        friendly = `Micro bloque: contexte non securise (${window.location.protocol}//${window.location.host}). HTTPS requis sur mobile. Utilise un tunnel HTTPS (Cloudflared/ngrok) ou ouvre le site sur localhost.`
      } else if (name === 'NotAllowedError' || /permission|denied|notallow/i.test(err.message)) {
        friendly = 'Permission micro refusee. Clique sur l icone de la barre d adresse (ou parametres du site) et autorise le micro, puis retente.'
      } else if (name === 'NotFoundError') {
        friendly = 'Aucun micro detecte sur cet appareil.'
      } else if (name === 'NotReadableError') {
        friendly = 'Micro utilise par une autre app. Ferme Skype/Zoom/Teams et reessaye.'
      } else if (name === 'SecurityError') {
        friendly = 'Micro bloque par politique de securite. Verifie HTTPS et les permissions du site.'
      }
      console.error('[useVoiceLive] getStream failed:', { name, message: err.message, friendly, href: window.location.href })
      setError(friendly)
      setP('idle')
      return
    }

    // Stream obtenu -> on peut faire les setState et autres awaits en toute securite
    setError(null)
    setP('listening')
    chunksRef.current = []
    spokeRef.current = false; silAtRef.current = 0; spokeAtRef.current = 0

    if (audioRef.current) { audioRef.current.src = SILENT_WAV; try { await audioRef.current.play() } catch {} }

    // CRITIQUE mobile: unlock Web Speech Synthesis AU SEIN du user gesture.
    // On speak une utterance quasi-silencieuse pour activer le pipeline TTS.
    // NE PAS appeler cancel() juste apres: ca casse le buffer pour les prochains speak().
    // Pre-chargement des voix aussi (getVoices peut renvoyer [] avant le premier call).
    try {
      if (window.speechSynthesis) {
        // Force le chargement des voix
        window.speechSynthesis.getVoices()
        // Utterance " " (espace) tres courte pour activer le pipeline sans faire trop de bruit
        const primer = new SpeechSynthesisUtterance(' ')
        primer.volume = 0.01
        primer.rate = 10  // tres vite -> dure quelques ms
        window.speechSynthesis.speak(primer)
        console.log('[useVoiceLive] speechSynthesis primed (voices:', window.speechSynthesis.getVoices().length, ')')
      }
    } catch (primerErr) {
      console.warn('[useVoiceLive] speechSynthesis prime failed:', primerErr)
    }

    try {
      if (ctxRef.current?.state === 'suspended') await ctxRef.current.resume()
      const an = analyserRef.current!
      const buf = new Float32Array(an.fftSize)

      // isTypeSupported() ment sur Edge/Chromium (retourne true pour audio/webm;codecs=opus
      // mais le MediaRecorder throw NotSupportedError au start). On teste donc a l usage reel:
      // pour chaque MIME candidat on cree un recorder et appelle start(), si ca marche
      // on le garde, sinon on passe au suivant.
      const candidateMimes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4;codecs=mp4a.40.2',
        'audio/mp4',
        'audio/ogg;codecs=opus',
        'audio/aac',
        '',  // default du navigateur
      ]

      const createWorkingRecorder = (mime: string): MediaRecorder | null => {
        let candidate: MediaRecorder
        try {
          candidate = mime
            ? new MediaRecorder(stream, { mimeType: mime })
            : new MediaRecorder(stream)
        } catch (ctorErr) {
          console.warn(`[useVoiceLive] constructor("${mime || 'default'}") failed:`, ctorErr instanceof Error ? ctorErr.message : ctorErr)
          return null
        }

        // Edge throw souvent NotSupportedError au start() MALGRE le fait que le
        // state devient 'recording' (recorder fonctionnel). On essaie avec puis
        // sans timeslice. A la fin, si state='recording', on l accepte.
        const tryStart = (withTimeslice: boolean) => {
          try {
            if (withTimeslice) candidate.start(250)
            else candidate.start()
            return true
          } catch (err) {
            const stillRecording = (candidate.state as string) === 'recording'
            console.warn(
              `[useVoiceLive] start(${withTimeslice ? '250' : ''}) with MIME "${mime || 'default'}" threw:`,
              err instanceof Error ? err.message : err,
              '| state after:', candidate.state,
              stillRecording ? '(OK, state=recording)' : '(FAIL)',
            )
            return stillRecording
          }
        }

        if (tryStart(true)) return candidate
        // state pourrait etre 'inactive' apres un start rate -> retry sans timeslice
        if ((candidate.state as string) !== 'recording') {
          if (tryStart(false)) return candidate
        }
        // Ultime tentative: peut-etre que state=recording juste apres un throw
        if ((candidate.state as string) === 'recording') return candidate

        try { candidate.stop() } catch { /* ignore */ }
        return null
      }

      let rec: MediaRecorder | null = null
      let usedMime = ''
      for (const mime of candidateMimes) {
        if (mime && typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported) {
          if (!MediaRecorder.isTypeSupported(mime)) continue
        }
        rec = createWorkingRecorder(mime)
        if (rec) {
          usedMime = mime || '(default)'
          break
        }
      }

      // Fallback ultime: cloner le stream (isoler de l AnalyserNode) et retester.
      // Certains browsers/drivers rejettent un MediaRecorder quand le stream est
      // deja connecte a un autre noeud Web Audio.
      if (!rec) {
        console.warn('[useVoiceLive] All MIME failed on shared stream, trying cloned stream')
        const clonedTracks = stream.getTracks().map(t => t.clone())
        const clonedStream = new MediaStream(clonedTracks)
        const createClonedRecorder = (mime: string): MediaRecorder | null => {
          try {
            const c = mime ? new MediaRecorder(clonedStream, { mimeType: mime }) : new MediaRecorder(clonedStream)
            try { c.start() } catch {
              if ((c.state as string) !== 'recording') return null
            }
            return (c.state as string) === 'recording' ? c : null
          } catch { return null }
        }
        for (const mime of ['', 'audio/webm', 'audio/mp4', 'audio/webm;codecs=opus']) {
          rec = createClonedRecorder(mime)
          if (rec) { usedMime = `${mime || 'default'} (cloned stream)`; break }
        }
      }

      if (!rec) {
        throw new Error(
          'Aucun format audio supporte par MediaRecorder sur ce navigateur. '
          + `User-Agent: ${navigator.userAgent.slice(0, 80)}. `
          + 'Solutions: installe Chrome/Firefox recent, OU utilise le mode Tauri desktop (application native).',
        )
      }

      console.log('[useVoiceLive] MediaRecorder WORKING with MIME:', usedMime, 'state:', rec.state)

      const blobMime = rec.mimeType || usedMime || 'audio/webm'
      rec.ondataavailable = e => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
          console.log('[useVoiceLive] chunk received, size:', e.data.size)
        }
      }
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: blobMime })
        console.log('[useVoiceLive] rec stopped, blob size:', blob.size, 'type:', blobMime)
        if (blob.size > 4000) {
          doTranscribe(blob)
        } else {
          console.warn('[useVoiceLive] blob too small to transcribe:', blob.size)
          if (mountedRef.current) setP('idle')
          if (continuousRef.current) {
            wantListenRef.current = true
          }
        }
      }
      recRef.current = rec

      const vad = () => {
        if (rec.state !== 'recording') return
        an.getFloatTimeDomainData(buf)
        let sum = 0
        for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
        const rms = Math.sqrt(sum / buf.length)
        setVolumeLevel(Math.min(1, rms * 8))
        const now = Date.now()
        const echoActive = now < echoGuardRef.current
        const th = echoActive ? NOISE_ECHO : (spokeRef.current ? NOISE_LOW : NOISE)
        if (rms >= th) {
          if (!spokeRef.current) { spokeRef.current = true; spokeAtRef.current = now }
          silAtRef.current = 0
        } else if (spokeRef.current) {
          if (!silAtRef.current) silAtRef.current = now
          if (stopOnSilenceRef.current && (silAtRef.current - spokeAtRef.current) >= MIN_SPEECH && (now - silAtRef.current) >= silenceMsRef.current) {
            rec.stop(); setVolumeLevel(0); return
          }
        }
        vadRef.current = requestAnimationFrame(vad)
      }
      vadRef.current = requestAnimationFrame(vad)
      maxRef.current = setTimeout(() => { if (rec.state === 'recording') rec.stop(); setVolumeLevel(0) }, Math.max(1000, maxRecordingMsRef.current || MAX_REC))
      // Demarrage reussi -> on relache le guard
      isStartingRef.current = false
    } catch (e) {
      isStartingRef.current = false
      const err = e instanceof Error ? e : new Error(String(e))
      console.error('[V] mic error:', err.name, err.message, err)
      let friendly = 'Micro inaccessible'
      if (err.name === 'NotSupportedError' || /mediarecorder/i.test(err.message)) {
        friendly = `Enregistrement audio non supporte par ce navigateur. ${err.message}. Essaie Chrome/Safari recent, ou passe en mode Tauri desktop.`
      } else if (err.name === 'NotAllowedError') {
        friendly = 'Permission micro refusee. Autorise dans les parametres.'
      }
      setError(friendly); setP('idle')
    }
  }, [getStream, doTranscribe])

  const stopRec = useCallback(() => {
    if (vadRef.current) cancelAnimationFrame(vadRef.current)
    if (maxRef.current) clearTimeout(maxRef.current)
    if (recRef.current?.state === 'recording') recRef.current.stop()
    setVolumeLevel(0)
  }, [])

  const autoStartDone = useRef(false)
  useEffect(() => {
    if (!autoStart || autoStartDone.current) return
    autoStartDone.current = true
    const id = setTimeout(() => {
      if (mountedRef.current && phaseRef.current === 'idle') {
        continuousRef.current = true
        setContinuous(true)
        startListenInternal()
      }
    }, 500)
    return () => clearTimeout(id)
  }, [autoStart, startListenInternal])

  const speakText = useCallback(async (text: string): Promise<void> => {
    if (!text.trim()) return

    const id = ++spkIdRef.current
    if (!mountedRef.current) return

    setP('speaking')

    const done = () => {
      if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = 0 }
      setSpeakingAmplitude(0)
      formantsRef.current = { low: 0, mid: 0 }
      if (mountedRef.current && spkIdRef.current === id) {
        echoGuardRef.current = Date.now() + ECHO_GUARD_MS
        setP('idle')
        if (continuousRef.current) wantListenRef.current = true
      }
    }

    // Animation amplitude pendant la parole audio
    const startAmplitudeAnimation = () => {
      const tick = () => {
        if (spkIdRef.current !== id) {
          setSpeakingAmplitude(0); formantsRef.current = { low: 0, mid: 0 }; rafRef.current = 0; return
        }
        const t = Date.now() / 1000
        const amp = Math.max(0.15, Math.min(1, 0.5 + Math.sin(t * 12) * 0.2 + Math.sin(t * 30) * 0.12))
        setSpeakingAmplitude(amp)
        formantsRef.current = { low: amp * 0.6, mid: amp * 0.4 }
        rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    // Kokoro est utilise sur tous les appareils (desktop + mobile).
    // Sur mobile via tunnel HTTPS, on laisse un watchdog plus long (5s) pour tolerer
    // la latence reseau, et Web Speech API reste le fallback fiable.
    const isMobile = /iPhone|iPad|iPod|Android|Mobile/i.test(navigator.userAgent)
    const kokoroWatchdogMs = isMobile ? 5000 : 1500
    console.log('[TTS] isMobile:', isMobile, 'watchdog:', kokoroWatchdogMs, 'ms')

    {  // bloc conservant l indentation d origine sans if/else externe

    // --- Tentative Kokoro TTS via bridge ---
    try {
      const bridgeUrl = getBridgeUrl()
      const ttsEndpoint = bridgeUrl ? `${bridgeUrl}/api/voice/tts` : '/api/voice/tts'
      const ttsPayload: Record<string, unknown> = { text: text.slice(0, 2000), lang: languageRef.current }
      // Si un avatar image est configure, on demande au bridge de generer aussi le MP4 talking-head
      if (avatarImageRef.current) {
        ttsPayload.avatar = avatarImageRef.current
      }
      // Persona vocal Aurora — bridge mappe lyra-soft -> Denise, iris-bright -> Brigitte, etc.
      if (voicePersonaRef.current) {
        ttsPayload.voice = voicePersonaRef.current
      }
      const resp = await fetch(ttsEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ttsPayload),
        // Timeout adaptatif: plus long si talking-video demande (SadTalker ~10-30s)
        signal: AbortSignal.timeout(avatarImageRef.current ? 45000 : 12000),
      })

      if (resp.ok) {
        const data = await safeParseJson<{
          ok?: boolean
          audio_url?: string
          video_url?: string
          video_cached?: boolean
          phonemes?: RhubarbCue[]
        }>(resp, 'TTS')
        console.log('[TTS] Kokoro response:', {
          ok: data.ok,
          hasAudio: !!data.audio_url,
          hasVideo: !!data.video_url,
          videoCached: data.video_cached,
          phonemes: data.phonemes?.length || 0,
        })
        if (data.ok && data.audio_url) {
          if (data.phonemes?.length) phonemeCuesRef.current = data.phonemes
          const audioUrl = bridgeUrl ? `${bridgeUrl}${data.audio_url}` : data.audio_url
          // Relayer le MP4 talking-video au callback si present
          if (data.video_url && onTalkingVideoRef.current) {
            const videoUrl = bridgeUrl ? `${bridgeUrl}${data.video_url}` : data.video_url
            try {
              console.log('[TTS] talking-video received:', videoUrl, 'cached:', data.video_cached)
              onTalkingVideoRef.current(videoUrl)
            } catch (cbErr) {
              console.warn('[TTS] onTalkingVideo callback error:', cbErr)
            }
          }
          console.log('[TTS] Playing audio:', audioUrl)

          // Strategie robuste: on essaye Kokoro. Si l audio ne progresse pas
          // reellement (currentTime reste a 0 apres play()), on tombe sur Web Speech.
          const kokoroResult = await new Promise<'played' | 'failed'>((resolveKokoro) => {
            let audio = audioRef.current
            if (!audio) {
              audio = new Audio()
              audioRef.current = audio
            }
            try { audio.pause() } catch { /* ignore */ }
            audio.src = audioUrl
            audio.currentTime = 0
            audio.preload = 'auto'
            audio.volume = 1
            audio.muted = false
            ttsSourceRef.current = audio

            console.log('[TTS] Audio setup:', {
              src: audioUrl,
              volume: audio.volume,
              muted: audio.muted,
              readyState: audio.readyState,
            })

            let resolved = false
            const settle = (outcome: 'played' | 'failed') => {
              if (resolved) return
              resolved = true
              audio!.onended = null
              audio!.onerror = null
              audio!.oncanplay = null
              audio!.onplaying = null
              resolveKokoro(outcome)
            }

            audio.onended = () => {
              console.log('[TTS] Kokoro audio ended OK')
              settle('played')
              done()
            }
            audio.onerror = () => {
              const mediaErr = audio!.error
              console.error('[TTS] Kokoro audio error:', {
                code: mediaErr?.code,
                message: mediaErr?.message,
                src: audio!.src,
              })
              settle('failed')
            }

            audio.onplaying = () => {
              console.log('[TTS] Kokoro onplaying fired, currentTime:', audio!.currentTime)
              startAmplitudeAnimation()
              // On marque "played" ici et on resolve cette promise QUAND onended arrivera.
              // En attendant on ne settle pas pour laisser le lecteur finir.
            }

            const attemptPlay = () => {
              const p = audio!.play()
              if (p && typeof p.then === 'function') {
                p.then(() => {
                  console.log('[TTS] Kokoro play() promise resolved')
                }).catch((err) => {
                  console.error('[TTS] Kokoro play() rejected:', err?.name, err?.message)
                  settle('failed')
                })
              }
            }

            if (audio.readyState >= 3) attemptPlay()
            else audio.oncanplay = () => attemptPlay()

            // Watchdog adaptatif: 1.5s desktop, 5s mobile (tunnel lent).
            // Si l audio n a pas progresse d au moins 50ms -> fallback Web Speech.
            setTimeout(() => {
              if (resolved) return
              const progressing = audio!.currentTime > 0.05 && !audio!.paused
              console.log(`[TTS] ${kokoroWatchdogMs}ms watchdog:`, {
                currentTime: audio!.currentTime,
                paused: audio!.paused,
                progressing,
                duration: audio!.duration,
                readyState: audio!.readyState,
              })
              if (!progressing) {
                console.warn('[TTS] Kokoro audio not progressing -> fallback to Web Speech')
                try { audio!.pause() } catch { /* ignore */ }
                settle('failed')
              }
            }, kokoroWatchdogMs)

            // Limite dure: au bout de maxMs on stoppe tout
            const maxMs = Math.max(8000, text.length * 120)
            setTimeout(() => {
              if (!resolved) {
                console.warn('[TTS] Kokoro final timeout', maxMs, 'ms')
                try { audio!.pause() } catch { /* ignore */ }
                settle('failed')
              }
            }, maxMs)
          })

          if (kokoroResult === 'played') {
            // onended a deja appele done() et resolve() -> on ne repasse pas par la
            return
          }
          // Sinon: Kokoro a echoue, on tombe sur Web Speech plus bas
          console.log('[TTS] falling back to Web Speech API')
        }
      } else {
        console.warn('[TTS] fetch response not ok:', resp.status)
      }
    } catch (err) {
      console.warn('[TTS] Kokoro TTS failed, falling back to Web Speech:', err)
    }

    }  // fin du `else` (desktop-only Kokoro block)

    // --- Fallback / Mobile par defaut: Web Speech API (native browser TTS) ---
    console.log('[TTS] Web Speech API fallback engaged, text:', text.slice(0, 60))
    return new Promise<void>((resolve) => {
      if (!window.speechSynthesis) {
        console.error('[TTS] window.speechSynthesis not available -- no TTS possible')
        done(); resolve(); return
      }

      // On annule UNIQUEMENT si quelque chose est deja en train de parler ou en attente,
      // pour eviter de polluer le pipeline si on vient juste d amorcer avec le primer.
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        console.log('[TTS] Web Speech: canceling previous utterance')
        try { window.speechSynthesis.cancel() } catch { /* ignore */ }
      }

      const speak = () => {
        const utter = new SpeechSynthesisUtterance(text)
        const langCode = languageRef.current === 'en' ? 'en-US' : 'fr-FR'
        utter.lang = langCode
        utter.rate = 0.95
        utter.pitch = 1.05
        utter.volume = 1

        const voices = window.speechSynthesis.getVoices()
        const langPrefix = languageRef.current === 'en' ? 'en' : 'fr'
        const matchedVoice = voices.find(v => v.lang.startsWith(langPrefix) && v.localService)
          || voices.find(v => v.lang.startsWith(langPrefix))
          || voices[0]
        if (matchedVoice) {
          utter.voice = matchedVoice
          console.log('[TTS] Web Speech voice:', matchedVoice.name, matchedVoice.lang)
        } else {
          console.warn('[TTS] Web Speech: no voices available')
        }

        const maxMs = Math.max(6000, text.length * 90)
        const timeoutId = setTimeout(() => {
          console.warn('[TTS] Web Speech timeout')
          done(); resolve()
        }, maxMs)

        utter.onstart = () => {
          console.log('[TTS] Web Speech onstart -- starting mimiques')
          startAmplitudeAnimation()
        }
        utter.onend = () => { console.log('[TTS] Web Speech ended OK'); clearTimeout(timeoutId); done(); resolve() }
        utter.onerror = (e) => { console.error('[TTS] Web Speech error:', e); clearTimeout(timeoutId); done(); resolve() }

        window.speechSynthesis.speak(utter)
      }

      // WebView2 / Chromium: voices may not be loaded synchronously on first call
      const voices = window.speechSynthesis.getVoices()
      if (voices.length > 0) {
        speak()
      } else {
        // Wait for voices to load, then speak
        const onVoicesChanged = () => {
          window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged)
          speak()
        }
        window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged)
        // Safety timeout in case voiceschanged never fires
        setTimeout(() => {
          window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged)
          speak()
        }, 1500)
      }
    })
  }, [])

  const stopSpeak = useCallback(() => {
    spkIdRef.current++
    if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = 0 }
    if (ampRef.current) { clearInterval(ampRef.current); ampRef.current = null }
    if (ttsSourceRef.current) { ttsSourceRef.current.pause(); ttsSourceRef.current.src = ''; ttsSourceRef.current = null }
    if (ttsCtxRef.current && ttsCtxRef.current.state !== 'closed') {
      ttsCtxRef.current.close().catch(() => {})
      ttsCtxRef.current = null
    }
    ttsAnalyserRef.current = null
    formantsRef.current = { low: 0, mid: 0 }
    window.speechSynthesis?.cancel()
    setSpeakingAmplitude(0); setP('idle')
  }, [])

  const toggle = useCallback(() => {
    const p = phaseRef.current
    if (p === 'listening') {
      continuousRef.current = false
      setContinuous(false)
      wantListenRef.current = false
      stopRec()
    } else if (p === 'idle') {
      continuousRef.current = true
      setContinuous(true)
      startListenInternal()
    } else if (p === 'speaking') {
      stopSpeak()
      if (continuousRef.current) {
        wantListenRef.current = true
      }
    }
  }, [startListenInternal, stopRec, stopSpeak])

  const stopAll = useCallback(() => {
    continuousRef.current = false
    setContinuous(false)
    wantListenRef.current = false
    stopSpeak()
    stopRec()
    // Stop stream tracks so the OS mic indicator disappears
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    if (phaseRef.current !== 'idle') setP('idle')
  }, [stopSpeak, stopRec])

  return {
    phase, error, volumeLevel, speakingAmplitude,
    toggleListening: toggle,
    speakText,
    stopSpeaking: stopSpeak,
    stopAll,
    isActive: phase !== 'idle',
    isContinuous: continuous,
    // Phase 1 — analyse audio temps réel
    formantsRef,    // { low, mid } mis à jour 60fps — lire depuis useFrame sans re-render
    audioRef,       // HTMLAudioElement — pour audio.currentTime dans useFrame
    // Phase 2 — Rhubarb Lip Sync
    phonemeCuesRef, // RhubarbCue[] — stable entre changements de texte
  }
}
