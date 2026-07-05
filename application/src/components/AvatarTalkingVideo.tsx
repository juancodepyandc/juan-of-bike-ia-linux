// Avatar talking video -- joue un MP4 genere par SadTalker (image FLUX + audio Kokoro).
// Le fichier MP4 contient deja tout: tete qui bouge, levres synchros, yeux, expressions.
// On le joue en boucle quand idle, et on synchronise playback avec la parole.
//
// Pre-requis: le MP4 est pre-genere par le backend (talking_head.py).
// Props:
//   videoSrc: URL du MP4 a jouer (peut changer a chaque nouvelle phrase)
//   phase: listening / speaking / idle
//   audioRef: optional -- pour synchro fine avec un audio element separe

import { useEffect, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'
import type { VoiceLivePhase } from '../hooks/useVoiceLive'

interface Props {
  phase: VoiceLivePhase
  /** URL du MP4 SadTalker (change a chaque nouvelle phrase) */
  videoSrc: string | null
  /** URL d une video "idle" loopee quand rien n est dit (ex: respiration simple) */
  idleVideoSrc?: string | null
  /** Audio externe a synchroniser (Kokoro WAV) -- si present, on mute la video et on sync sur audio.currentTime */
  audioRef?: MutableRefObject<HTMLAudioElement | null>
  size?: number
}

export default function AvatarTalkingVideo({
  phase,
  videoSrc,
  idleVideoSrc,
  audioRef,
  size = 240,
}: Props) {
  const videoEl = useRef<HTMLVideoElement | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const activeSrc = phase === 'speaking' && videoSrc ? videoSrc : (idleVideoSrc || videoSrc)

  useEffect(() => {
    if (!activeSrc) return
    setLoading(true)
    setError(null)
    const v = videoEl.current
    if (!v) return
    v.src = activeSrc
    v.load()
    const onCanPlay = () => {
      setLoading(false)
      v.play().catch((err) => {
        console.warn('[AvatarTalkingVideo] play rejected:', err)
      })
    }
    const onError = () => {
      setError('Video indisponible')
      setLoading(false)
    }
    v.addEventListener('canplay', onCanPlay)
    v.addEventListener('error', onError)
    return () => {
      v.removeEventListener('canplay', onCanPlay)
      v.removeEventListener('error', onError)
    }
  }, [activeSrc])

  // Synchro audio externe: si audioRef joue, on colle la video sur son currentTime.
  // Sinon on laisse la video jouer naturellement (avec son son inclus).
  useEffect(() => {
    if (!audioRef?.current || !videoEl.current) return
    const audio = audioRef.current
    const video = videoEl.current
    video.muted = true  // on prend le son de l audio externe, pas de la video

    let raf = 0
    const sync = () => {
      if (!video || !audio) return
      if (!audio.paused && Math.abs(video.currentTime - audio.currentTime) > 0.15) {
        try { video.currentTime = audio.currentTime } catch { /* ignore */ }
      }
      raf = requestAnimationFrame(sync)
    }
    raf = requestAnimationFrame(sync)
    return () => cancelAnimationFrame(raf)
  }, [audioRef, activeSrc])

  return (
    <div
      className="relative overflow-hidden rounded-2xl bg-[#1a1a24]"
      style={{ width: size, height: size }}
    >
      <video
        ref={videoEl}
        playsInline
        muted={!!audioRef}  // mute seulement si on synchronise sur un audio externe
        loop
        autoPlay
        className="block h-full w-full object-cover"
      />
      {loading && !error && activeSrc && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-white/40">
          Chargement video...
        </div>
      )}
      {!activeSrc && (
        <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-[11px] text-white/40">
          Genere une video d avatar pour activer le mode realiste
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-[11px] text-red-300">
          {error}
        </div>
      )}
    </div>
  )
}
