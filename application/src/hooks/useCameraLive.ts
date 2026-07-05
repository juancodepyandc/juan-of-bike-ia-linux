// Hook camera live -- capture de frames via getUserMedia pour le VoiceCopilote.
// Supporte:
// - Mode hybride (C): snapshot on-demand + background interval (10s par defaut)
// - Switch front/back (mobile)
// - Capture frame en dataUrl (pret pour qwen3-vl) ou blob (pour upload)
// - Cleanup automatique des MediaStream tracks a l unmount

import { useCallback, useEffect, useRef, useState } from 'react'

export type CameraFacing = 'user' | 'environment'

export interface CameraLiveOptions {
  // Interval en ms pour captures background automatiques (0 = desactive)
  backgroundIntervalMs?: number
  // Resolution cible ideale (navigateur peut l arrondir)
  idealWidth?: number
  idealHeight?: number
  // Callback invoque a chaque capture background (pour alimenter le contexte visuel)
  onBackgroundCapture?: (dataUrl: string) => void
  // Facing mode initial
  initialFacing?: CameraFacing
}

export interface CameraLiveState {
  enabled: boolean
  starting: boolean
  error: string | null
  facing: CameraFacing
  hasMultipleCameras: boolean
  lastCaptureAt: number | null
}

export interface CameraLiveApi extends CameraLiveState {
  // Element ref a attacher a <video ref={videoRef} playsInline muted />
  videoRef: React.RefObject<HTMLVideoElement>
  // Demarre/arrete la camera
  start: () => Promise<void>
  stop: () => void
  toggle: () => Promise<void>
  // Alterne front/back (mobile). Sans effet desktop avec 1 seule camera.
  switchCamera: () => Promise<void>
  // Capture une frame en dataUrl (JPEG base64). Retourne null si camera off.
  captureDataUrl: (maxSize?: number) => string | null
  // Capture en Blob JPEG (pour upload/download).
  captureBlob: (maxSize?: number, quality?: number) => Promise<Blob | null>
}

export function useCameraLive(options: CameraLiveOptions = {}): CameraLiveApi {
  const {
    backgroundIntervalMs = 0,
    idealWidth = 1280,
    idealHeight = 720,
    onBackgroundCapture,
    initialFacing = 'user',
  } = options

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const bgIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const mountedRef = useRef(true)
  // Guard contre les appels paralleles a startInternal (double-click, re-render React).
  // Sans ce guard, un double-start acquiert 2 streams puis l un des 2 est arrete,
  // ce qui cause "l apercu apparait une fraction de seconde puis disparait".
  const isStartingRef = useRef(false)

  const [enabled, setEnabled] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [facing, setFacing] = useState<CameraFacing>(initialFacing)
  const [hasMultipleCameras, setHasMultipleCameras] = useState(false)
  const [lastCaptureAt, setLastCaptureAt] = useState<number | null>(null)

  // Callback ref pour que les intervals utilisent toujours la derniere version
  const onBgRef = useRef(onBackgroundCapture)
  onBgRef.current = onBackgroundCapture

  // Detecter le nombre de cameras disponibles
  useEffect(() => {
    mountedRef.current = true
    if (navigator.mediaDevices?.enumerateDevices) {
      navigator.mediaDevices
        .enumerateDevices()
        .then((devices) => {
          if (!mountedRef.current) return
          const cams = devices.filter((d) => d.kind === 'videoinput')
          setHasMultipleCameras(cams.length > 1)
        })
        .catch(() => {
          // Permission non accordee -> on saura apres le start()
        })
    }
    return () => {
      mountedRef.current = false
    }
  }, [])

  // ---------------------------------------------------------------
  // Capture helpers
  // ---------------------------------------------------------------

  const ensureCanvas = (): HTMLCanvasElement => {
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas')
    }
    return canvasRef.current
  }

  const captureToCanvas = (maxSize: number): HTMLCanvasElement | null => {
    const video = videoRef.current
    if (!video || !video.videoWidth || !video.videoHeight) return null

    const srcW = video.videoWidth
    const srcH = video.videoHeight
    const largest = Math.max(srcW, srcH)
    const scale = largest > maxSize ? maxSize / largest : 1
    const targetW = Math.round(srcW * scale)
    const targetH = Math.round(srcH * scale)

    const canvas = ensureCanvas()
    canvas.width = targetW
    canvas.height = targetH
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, 0, 0, targetW, targetH)
    return canvas
  }

  const captureDataUrl = useCallback((maxSize = 1024): string | null => {
    const canvas = captureToCanvas(maxSize)
    if (!canvas) return null
    try {
      const url = canvas.toDataURL('image/jpeg', 0.85)
      setLastCaptureAt(Date.now())
      return url
    } catch {
      return null
    }
  }, [])

  const captureBlob = useCallback(async (maxSize = 1024, quality = 0.85): Promise<Blob | null> => {
    const canvas = captureToCanvas(maxSize)
    if (!canvas) return null
    return new Promise<Blob | null>((resolve) => {
      canvas.toBlob((blob) => {
        if (blob) setLastCaptureAt(Date.now())
        resolve(blob)
      }, 'image/jpeg', quality)
    })
  }, [])

  // ---------------------------------------------------------------
  // Start / stop
  // ---------------------------------------------------------------

  const stopInternal = useCallback(() => {
    if (bgIntervalRef.current) {
      clearInterval(bgIntervalRef.current)
      bgIntervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => {
        try { t.stop() } catch { /* ignore */ }
      })
      streamRef.current = null
    }
    if (videoRef.current) {
      try { videoRef.current.srcObject = null } catch { /* ignore */ }
    }
    if (mountedRef.current) {
      setEnabled(false)
      setStarting(false)
    }
  }, [])

  const startInternal = useCallback(async (targetFacing: CameraFacing) => {
    // Guard double-call: empeche l apercu de clignoter si l utilisateur clique
    // plusieurs fois rapidement ou si React re-declenche le handler.
    if (isStartingRef.current) {
      console.warn('[useCameraLive] startInternal already in progress, ignoring duplicate call')
      return
    }
    if (streamRef.current && streamRef.current.getTracks().some((t) => t.readyState === 'live')) {
      console.warn('[useCameraLive] stream deja actif, skip double-start')
      return
    }
    isStartingRef.current = true

    // Diagnostic: contexte securise requis (sauf localhost/Tauri)
    const isSecure = typeof window !== 'undefined'
      && (window.isSecureContext
          || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname)
          || window.location.protocol === 'tauri:')

    if (!navigator.mediaDevices?.getUserMedia) {
      isStartingRef.current = false
      const msg = !isSecure
        ? `Camera indisponible : le navigateur exige un contexte securise (HTTPS ou localhost). Adresse actuelle : ${window.location.protocol}//${window.location.host}. Pour le mobile, utilise un tunnel HTTPS (Cloudflared, ngrok) ou installe le certificat local.`
        : 'Camera non supportee par ce navigateur (mediaDevices.getUserMedia absent).'
      console.error('[useCameraLive] getUserMedia absent:', { isSecure, host: window.location.host, protocol: window.location.protocol })
      setError(msg)
      return
    }

    if (!isSecure) {
      isStartingRef.current = false
      const msg = `Camera bloquee : contexte non securise. Tu es sur ${window.location.protocol}//${window.location.host}. Sur mobile, il faut HTTPS (ex: Cloudflared tunnel) ou que le site soit servi via localhost.`
      console.error('[useCameraLive] Non-secure context:', window.location)
      setError(msg)
      return
    }

    // iOS Safari CRITIQUE: getUserMedia DOIT etre appele AVANT setStarting/setError
    // (tout setState React consomme le user gesture et iOS rejette silencieusement).
    // On prepare les constraints puis on appelle directement.
    const constraints: MediaStreamConstraints = {
      video: {
        facingMode: { ideal: targetFacing },
        width: { ideal: idealWidth },
        height: { ideal: idealHeight },
      },
      audio: false,
    }

    let stream: MediaStream
    try {
      console.log('[useCameraLive] getUserMedia with facingMode:', targetFacing)
      stream = await navigator.mediaDevices.getUserMedia(constraints)
    } catch (primaryErr) {
      console.warn('[useCameraLive] facingMode failed, fallback to video:true', primaryErr)
      // Fallback: certains PC desktop refusent facingMode -> essayer sans
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      } catch (fallbackErr) {
        console.error('[useCameraLive] fallback also failed:', fallbackErr)
        // Permet au catch externe de produire un message friendly
        const err = fallbackErr instanceof Error ? fallbackErr : new Error(String(fallbackErr))
        const name = err.name || ''
        const msg = err.message || ''
        let friendly = msg
        if (name === 'NotAllowedError' || /permission|denied|notallow/i.test(msg)) {
          friendly = 'Permission camera refusee. Clique sur l icone camera de la barre d adresse et autorise l acces, puis retente. Sur iPhone: reglages Safari > camera > autoriser.'
        } else if (name === 'NotFoundError' || /not ?found|no ?device/i.test(msg)) {
          friendly = 'Aucune camera detectee.'
        } else if (name === 'NotReadableError') {
          friendly = 'Camera utilisee par une autre app (Skype/Teams/OBS). Ferme-la et reessaye.'
        } else if (name === 'SecurityError') {
          friendly = 'Camera bloquee par politique de securite (HTTPS requis sur mobile).'
        } else if (!msg) {
          friendly = 'Camera indisponible (erreur silencieuse iOS). Sur iPhone, verifie Reglages > Safari > Camera = Autoriser.'
        }
        setError(friendly)
        isStartingRef.current = false
        return
      }
    }

    // On a le stream -> maintenant on peut faire les setState React
    setStarting(true)
    setError(null)

    try {

      if (!mountedRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }

      // Arreter l ancien stream avant d attacher le nouveau
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => {
          try { t.stop() } catch { /* ignore */ }
        })
      }

      streamRef.current = stream

      // Note: on n attache PAS le stream au videoRef ici car React n a pas encore
      // monte le <video> element (enabled=false pendant ce render).
      // Un useEffect [enabled] plus bas s en charge apres le mount.
      setEnabled(true)
      setFacing(targetFacing)

      // Demarrer le polling background si configure
      if (backgroundIntervalMs > 0) {
        if (bgIntervalRef.current) clearInterval(bgIntervalRef.current)
        bgIntervalRef.current = setInterval(() => {
          if (!mountedRef.current) return
          const dataUrl = captureDataUrl(1024)
          if (dataUrl && onBgRef.current) {
            try { onBgRef.current(dataUrl) } catch (cbErr) {
              console.warn('[useCameraLive] background callback error:', cbErr)
            }
          }
        }, backgroundIntervalMs)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      const name = err instanceof Error ? err.name : ''
      console.error('[useCameraLive] getUserMedia error:', { name, msg, err })

      let friendly = msg
      if (name === 'NotAllowedError' || /permission|denied|notallow/i.test(msg)) {
        friendly = `Permission camera refusee. Clique sur l icone de camera dans la barre d adresse du navigateur et autorise l acces, puis reessaye. (${msg})`
      } else if (name === 'NotFoundError' || /not ?found|no ?device/i.test(msg)) {
        friendly = 'Aucune camera detectee sur ce systeme. Branche une webcam ou active la camera integree.'
      } else if (name === 'NotReadableError' || /in ?use|busy|readable/i.test(msg)) {
        friendly = 'Camera deja utilisee par une autre application (Skype, Teams, OBS, Zoom...). Ferme l autre app et reessaye.'
      } else if (name === 'OverconstrainedError') {
        friendly = 'Camera ne supporte pas la resolution demandee. Essaie de rafraichir la page.'
      } else if (name === 'SecurityError') {
        friendly = 'Camera bloquee par la politique de securite. Verifie que tu es bien en HTTPS ou sur localhost.'
      } else if (!msg) {
        friendly = 'Camera indisponible (erreur inconnue). Ouvre la console du navigateur (F12) pour voir le detail.'
      }
      setError(friendly)
      stopInternal()
    } finally {
      if (mountedRef.current) setStarting(false)
      isStartingRef.current = false
    }
  }, [backgroundIntervalMs, idealHeight, idealWidth, captureDataUrl, stopInternal])

  const start = useCallback(() => startInternal(facing), [facing, startInternal])
  const stop = useCallback(() => stopInternal(), [stopInternal])

  const toggle = useCallback(async () => {
    if (enabled) stopInternal()
    else await startInternal(facing)
  }, [enabled, facing, startInternal, stopInternal])

  const switchCamera = useCallback(async () => {
    const next: CameraFacing = facing === 'user' ? 'environment' : 'user'
    console.log('[useCameraLive] switchCamera:', facing, '->', next)
    if (enabled) {
      // Arreter l ancien stream AVANT de redemarrer avec le nouveau facing.
      // Sinon le guard dans startInternal (streamRef.current live) nous bloque.
      stopInternal()
      // Petit delai pour laisser le browser liberer la camera (important sur mobile)
      await new Promise((r) => setTimeout(r, 150))
      await startInternal(next)
    } else {
      setFacing(next)
    }
  }, [enabled, facing, startInternal, stopInternal])

  // CRITICAL: attache le stream au videoRef APRES que React ait monte le <video>.
  // Sans cet effect, le videoRef est null au moment du getUserMedia (le <video> est
  // monte en conditional seulement apres setEnabled(true)) et la preview reste noire.
  // Verifie srcObject !== stream pour eviter de re-attacher si deja fait (evite
  // l AbortError "play() interrupted by new load request").
  useEffect(() => {
    if (!enabled) return
    const video = videoRef.current
    const stream = streamRef.current
    if (!video || !stream) {
      console.warn('[useCameraLive] mount effect: missing video or stream', { hasVideo: !!video, hasStream: !!stream })
      return
    }
    if (video.srcObject === stream) {
      console.log('[useCameraLive] stream already attached, skipping')
      return
    }
    console.log('[useCameraLive] attaching stream to video element')
    try {
      video.srcObject = stream
    } catch (err) {
      console.error('[useCameraLive] srcObject assign failed:', err)
      return
    }
    // play() peut rejeter (autoplay policy). On ne re-play que si pause effective.
    const playPromise = video.play()
    if (playPromise && typeof playPromise.then === 'function') {
      playPromise.catch((err) => {
        // AbortError est souvent benin (remplace par le prochain play implicite)
        if (err && err.name === 'AbortError') {
          console.log('[useCameraLive] play() aborted (benign, next play will take over)')
        } else {
          console.warn('[useCameraLive] video.play() rejected:', err)
        }
      })
    }
  }, [enabled])

  // Cleanup a l unmount
  useEffect(() => {
    return () => {
      stopInternal()
    }
  }, [stopInternal])

  return {
    videoRef: videoRef as React.RefObject<HTMLVideoElement>,
    enabled,
    starting,
    error,
    facing,
    hasMultipleCameras,
    lastCaptureAt,
    start,
    stop,
    toggle,
    switchCamera,
    captureDataUrl,
    captureBlob,
  }
}
