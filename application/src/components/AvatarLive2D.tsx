// Avatar 2D anime depuis une image FLUX.
// Principe:
// - L image FLUX est affichee dans un canvas HTML.
// - Les coordonnees yeux/bouche sont detectees par qwen3-vl et stockees dans avatarPath JSON.
// - On anime en temps reel:
//   * blink yeux (paupieres): overlay rectangle couleur peau pulse quand timer blink
//   * lip-sync bouche: overlay plus ou moins ouvert selon speakingAmplitude / Rhubarb
//   * respiration: legere scale Y 0.99-1.01
//   * suivi regard: pupilles dessinees qui suivent la souris ou la camera
// Avantage vs 3D: l image FLUX est TOUJOURS de qualite, on obtient un vrai
// ressemblant (Natsu = vraiment Natsu, pas un blob de polygones).

import { useEffect, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'
import type { VoiceLivePhase, RhubarbCue } from '../hooks/useVoiceLive'

export interface FaceFeatures2D {
  eyeL: { x: number; y: number; w: number; h: number } | null
  eyeR: { x: number; y: number; w: number; h: number } | null
  mouth: { x: number; y: number; w: number; h: number } | null
  faceColor: string | null
  hairColor: string | null
  hasFace: boolean
}

/**
 * Mode d animation:
 * - humanoid: perso humain -> overlay bouche/yeux classiques
 * - stylized: perso non-standard (Caine TADC, mascotte, etc.) -> effets globaux seulement
 *             (scale/glow/distortion sur l image entiere, aucune overlay localisee)
 * - creature: bete avec gueule -> overlay bouche large
 * - robot: pas de bouche -> LED pulse
 * - abstract: entite sans features -> glow global
 *
 * Quand en doute: 'stylized' -- le rendu est plus honnete (on ne fake pas une
 * bouche humaine sur un perso qui n en a pas).
 */
export type AnimationMode = 'humanoid' | 'stylized' | 'creature' | 'robot' | 'abstract'

interface Props {
  phase: VoiceLivePhase
  volumeLevel: number
  speakingAmplitude: number
  imageSrc: string                  // URL de l image FLUX (PNG)
  features?: FaceFeatures2D | null  // coords yeux/bouche, null = defaults
  /**
   * Mode d animation selon le type de personnage:
   * - humanoid (defaut): yeux blinkent, bouche s ouvre legerement au centre visage
   * - creature: "gueule" plus large qui s ouvre verticalement, plus de mouvement
   * - robot: pas de bouche, "visor" horizontal + pulsation couleur selon audio
   * - abstract: glow global + deformation subtle sans overlay localise
   */
  animationMode?: AnimationMode
  spokenText?: string
  formantsRef?: MutableRefObject<{ low: number; mid: number }>
  audioRef?: MutableRefObject<HTMLAudioElement | null>
  phonemeCuesRef?: MutableRefObject<RhubarbCue[]>
  size?: number                     // taille du canvas (px), carre. Default 256.
}

const DEFAULT_FEATURES: FaceFeatures2D = {
  eyeL: { x: 0.38, y: 0.42, w: 0.08, h: 0.045 },
  eyeR: { x: 0.62, y: 0.42, w: 0.08, h: 0.045 },
  mouth: { x: 0.50, y: 0.60, w: 0.13, h: 0.04 },
  faceColor: '#f0c9a0',
  hairColor: '#3a2518',
  hasFace: true,
}

// Lookup Rhubarb viseme -> ouverture bouche [0..1]
function rhubarbToMouthOpen(v: string): { openY: number; openX: number } {
  switch (v) {
    case 'A': return { openY: 0.9, openX: 0.65 }  // ah wide
    case 'B': return { openY: 0.05, openX: 0.9 }  // closed m/b/p
    case 'C': return { openY: 0.35, openX: 1.05 } // smile e
    case 'D': return { openY: 0.3, openX: 0.95 }  // d/t/s
    case 'E': return { openY: 0.55, openX: 0.75 } // oh
    case 'F': return { openY: 0.65, openX: 0.45 } // oo round
    case 'G': return { openY: 0.35, openX: 0.7 }  // f/v
    case 'H': return { openY: 0.25, openX: 0.85 } // l
    default:  return { openY: 0.08, openX: 0.9 }  // X silence
  }
}

function getRhubarbViseme(cues: RhubarbCue[], t: number): string {
  if (!cues.length) return 'X'
  for (let i = cues.length - 1; i >= 0; i--) {
    if (t >= cues[i].start) return cues[i].value
  }
  return 'X'
}

// Timeline phonemique text-based (fallback Rhubarb).
// Retourne un viseme approximatif par caractere prononce.
function charToViseme(ch: string): string {
  const c = ch.toLowerCase()
  if ('aàâ'.includes(c)) return 'A'
  if ('mbp'.includes(c)) return 'B'
  if ('eéèê'.includes(c)) return 'C'
  if ('dtsznrlj'.includes(c)) return 'D'
  if ('oôó'.includes(c)) return 'E'
  if ('uùû'.includes(c)) return 'F'
  if ('fv'.includes(c)) return 'G'
  if ('iîïy'.includes(c)) return 'H'
  if (c === ' ') return 'X'
  return 'D'
}

export default function AvatarLive2D({
  phase, volumeLevel, speakingAmplitude,
  imageSrc, features, spokenText,
  audioRef, phonemeCuesRef,
  animationMode = 'humanoid',
  size = 288,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError] = useState<string | null>(null)

  const blinkRef = useRef({ next: 2 + Math.random() * 3, progress: 0 })
  const breathRef = useRef(0)
  const mouthRef = useRef({ openY: 0.1, openX: 0.9 })
  const textStartRef = useRef(0)
  const mousePosRef = useRef({ x: 0.5, y: 0.5 })

  const f: FaceFeatures2D = features?.hasFace ? features : DEFAULT_FEATURES

  // Charger l image
  useEffect(() => {
    setImgLoaded(false)
    setImgError(null)
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imgRef.current = img
      setImgLoaded(true)
    }
    img.onerror = () => {
      setImgError('Impossible de charger l image avatar.')
      imgRef.current = null
    }
    img.src = imageSrc
  }, [imageSrc])

  // Reset timeline quand le texte parle change
  useEffect(() => {
    if (spokenText && phase === 'speaking') {
      textStartRef.current = performance.now() / 1000
    }
  }, [spokenText, phase])

  // Tracking souris pour pupilles qui suivent (desktop)
  useEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      mousePosRef.current = {
        x: (e.clientX - rect.left) / rect.width,
        y: (e.clientY - rect.top) / rect.height,
      }
    }
    window.addEventListener('mousemove', onMove, { passive: true })
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  // Animation loop
  useEffect(() => {
    if (!imgLoaded || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let raf = 0
    let lastT = performance.now() / 1000

    const draw = () => {
      const img = imgRef.current
      if (!img) { raf = requestAnimationFrame(draw); return }
      const t = performance.now() / 1000
      const dt = Math.min(0.1, t - lastT)
      lastT = t

      // --- Audio state (doit etre calcule en premier pour breathScale + mouth)
      const audio = audioRef?.current
      const audioPlaying = !!(audio && !audio.paused && audio.currentTime > 0 && !audio.ended)

      // --- Respiration + vibration parole (scale)
      // Mode stylized: l image entiere pulse plus fort quand on parle, pour
      // simuler le caractere vivant du perso sans dessiner sur sa bouche.
      breathRef.current = Math.sin(t * 1.8) * 0.5 + 0.5
      const baseScale = 1 + (breathRef.current - 0.5) * 0.015
      const audioPulse = phase === 'speaking' && audioPlaying
        ? Math.sin(t * 18) * 0.5 + 0.5  // oscillation rapide 9Hz
        : 0
      const speakBoost = animationMode === 'stylized' && phase === 'speaking'
        ? audioPulse * speakingAmplitude * 0.035  // pulse plus fort sur stylized
        : phase === 'speaking' ? audioPulse * 0.005 : 0
      const breathScale = baseScale + speakBoost

      // --- Blink
      const blink = blinkRef.current
      blink.next -= dt
      if (blink.next <= 0) {
        blink.progress = 1
        blink.next = 2.5 + Math.random() * 3
      }
      // decay blink sur 150ms
      if (blink.progress > 0) {
        blink.progress = Math.max(0, blink.progress - dt / 0.15)
      }
      const blinkAmount = blink.progress

      // --- Mouth open target (audio + audioPlaying deja calcules plus haut)
      let targetMouth = { openY: 0.08, openX: 0.9 }
      if (phase === 'speaking' && audioPlaying) {
        // 1) Rhubarb cues si dispo (frame-accurate avec audio.currentTime)
        const cues = phonemeCuesRef?.current
        if (cues && cues.length) {
          const viseme = getRhubarbViseme(cues, audio!.currentTime)
          targetMouth = rhubarbToMouthOpen(viseme)
        } else if (spokenText) {
          // 2) Fallback text-based base sur audio.currentTime (pas performance.now)
          // pour rester synchro avec la lecture meme si elle bufferise.
          const charsPerSec = 12
          const idx = Math.floor(audio!.currentTime * charsPerSec) % Math.max(1, spokenText.length)
          const viseme = charToViseme(spokenText[idx] || ' ')
          targetMouth = rhubarbToMouthOpen(viseme)
        } else {
          // 3) Fallback amplitude (seulement si audio joue)
          const a = Math.min(1, speakingAmplitude * 1.4)
          targetMouth = { openY: 0.1 + a * 0.75, openX: 0.9 + a * 0.05 }
        }
      } else if (phase === 'listening') {
        // legere pulsation "ecoute active"
        const a = Math.min(1, volumeLevel * 1.8)
        targetMouth = { openY: 0.08 + a * 0.1, openX: 0.9 }
      }
      // Si phase === 'speaking' mais audio pas en train de jouer -> bouche fermee (0.08, 0.9)
      // -> l animation demarre EXACTEMENT quand le son commence
      // Smoothing
      mouthRef.current.openY += (targetMouth.openY - mouthRef.current.openY) * 0.35
      mouthRef.current.openX += (targetMouth.openX - mouthRef.current.openX) * 0.35

      // ==========================================
      // RENDER
      // ==========================================
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      // 1. Image de base (avec respiration)
      const scaledW = W * breathScale
      const scaledH = H * breathScale
      const dx = (W - scaledW) / 2
      const dy = (H - scaledH) / 2 - (phase === 'speaking' ? 2 : 0)
      ctx.drawImage(img, dx, dy, scaledW, scaledH)

      // 2. Overlay blink SEULEMENT pour humanoid (perso humain classique).
      // stylized/creature/robot/abstract: pas de blink dessine (l image d origine
      // fait deja foi -- on ne fake pas des paupieres sur un perso qui n en a pas).
      if (blinkAmount > 0.15 && animationMode === 'humanoid') {
        const drawEyeLid = (eye: typeof f.eyeL) => {
          if (!eye) return
          const ex = eye.x * W
          const ey = eye.y * H
          const ew = eye.w * W * 1.15
          const eh = eye.h * H * 1.5
          const lidH = eh * blinkAmount

          // Paupiere: gradient de la couleur peau vers un peu plus sombre (ombre cil)
          const skinCol = f.faceColor || '#f0c9a0'
          const grad = ctx.createLinearGradient(0, ey - eh / 2, 0, ey - eh / 2 + lidH)
          grad.addColorStop(0, skinCol)
          grad.addColorStop(0.85, skinCol)
          grad.addColorStop(1, 'rgba(60, 40, 35, 0.8)')  // ombre cil

          ctx.save()
          ctx.globalCompositeOperation = 'source-over'
          ctx.fillStyle = grad
          // ellipse douce au lieu d un rectangle net
          ctx.beginPath()
          ctx.ellipse(ex, ey - eh / 2 + lidH / 2, ew / 2, lidH / 2, 0, 0, Math.PI * 2)
          ctx.fill()
          ctx.restore()
        }
        drawEyeLid(f.eyeL)
        drawEyeLid(f.eyeR)
      }

      // 3. Les pupilles qui suivent la souris sont DESACTIVEES par defaut:
      //    le rendu 2D n arrive pas a faire un point subtle qui ne ressemble pas
      //    a un "bug d encre". Reserve pour v2 avec detection precise de l iris.

      // 4. Rendu parle adapte au mode d animation
      const opening = mouthRef.current.openY
      const speaking = phase === 'speaking' && opening > 0.15

      if (animationMode === 'humanoid' && f.mouth && speaking) {
        // HUMAIN: petite ellipse sombre sur la bouche (preserve le dessin FLUX)
        const mx = f.mouth.x * W
        const my = f.mouth.y * H
        const mw = f.mouth.w * W * mouthRef.current.openX * 0.85
        const mh = f.mouth.h * H * (opening * 2.2)

        const gradR = Math.max(mw, mh) / 2
        const grad = ctx.createRadialGradient(mx, my, 0, mx, my, gradR)
        grad.addColorStop(0, `rgba(25, 10, 15, ${0.45 + opening * 0.25})`)
        grad.addColorStop(0.55, `rgba(35, 15, 20, ${0.25 + opening * 0.15})`)
        grad.addColorStop(1, 'rgba(60, 25, 30, 0)')

        ctx.save()
        ctx.globalCompositeOperation = 'multiply'
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.ellipse(mx, my, mw / 2, mh / 2, 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()

        ctx.save()
        ctx.globalCompositeOperation = 'multiply'
        ctx.fillStyle = `rgba(110, 60, 65, ${0.35 + opening * 0.2})`
        ctx.beginPath()
        ctx.ellipse(mx, my - mh * 0.45, mw * 0.42, Math.max(1, mh * 0.08), 0, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()
      } else if (animationMode === 'creature' && f.mouth && speaking) {
        // CREATURE: gueule plus large, ouverture plus forte, ombre noire opaque
        // (les creatures ont un interieur de bouche sombre visible).
        const mx = f.mouth.x * W
        const my = f.mouth.y * H
        const mw = f.mouth.w * W * 1.6 * mouthRef.current.openX
        const mh = f.mouth.h * H * (opening * 4.0)  // x2 ouverture vs humanoid

        ctx.save()
        ctx.fillStyle = `rgba(10, 5, 8, ${0.75 + opening * 0.2})`
        ctx.beginPath()
        ctx.ellipse(mx, my + mh * 0.1, mw / 2, mh / 2, 0, 0, Math.PI * 2)
        ctx.fill()
        // Contour rouge-sombre pour simuler levre / interieur
        ctx.strokeStyle = `rgba(80, 20, 20, ${0.4 + opening * 0.3})`
        ctx.lineWidth = 2
        ctx.stroke()
        ctx.restore()
      } else if (animationMode === 'robot' && speaking) {
        // ROBOT: pas de bouche organique. On pulse une ligne/LED horizontale
        // au centre bas du visage (visor style) qui reagit a l audio.
        const cx = W / 2
        const cy = H * 0.62  // bas du visage
        const lineW = W * 0.35 * (0.5 + opening * 0.8)
        const lineH = Math.max(2, H * 0.01 * (1 + opening * 2))
        ctx.save()
        // Glow externe
        const glowR = lineW * 0.6
        const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowR)
        const gIntensity = 0.25 + opening * 0.5
        glow.addColorStop(0, `rgba(80, 200, 255, ${gIntensity})`)
        glow.addColorStop(1, 'rgba(80, 200, 255, 0)')
        ctx.fillStyle = glow
        ctx.fillRect(cx - glowR, cy - glowR / 2, glowR * 2, glowR)
        // Ligne LED centrale
        ctx.fillStyle = `rgba(120, 230, 255, ${0.6 + opening * 0.4})`
        ctx.fillRect(cx - lineW / 2, cy - lineH / 2, lineW, lineH)
        ctx.restore()
      } else if (animationMode === 'stylized' && phase === 'speaking') {
        // STYLIZED: perso complexe/non-standard (Caine TADC, mascotte, cartoon).
        // AUCUN overlay -- on laisse l image d origine entiere et on applique un
        // micro-warp + une legere pulsation de la couleur globale pour simuler
        // une vibration de parole sans fake une bouche humaine.
        // L image ELLE-MEME porte deja le "mouth shape" du perso, on la laisse parler.
        const amp = Math.min(1, speakingAmplitude * 1.3)
        if (amp > 0.05) {
          // Pulse de saturation/luminosite subtile: overlay blanc tres transparent
          ctx.save()
          ctx.globalCompositeOperation = 'soft-light'
          ctx.fillStyle = `rgba(255, 255, 240, ${amp * 0.08})`
          ctx.fillRect(0, 0, W, H)
          ctx.restore()

          // Vibration: micro-glow autour des coord mouth detectees si dispo
          // (NE DESSINE PAS une bouche -- juste une zone d attention lumineuse)
          if (f.mouth) {
            const mx = f.mouth.x * W
            const my = f.mouth.y * H
            const r = Math.max(W, H) * 0.18
            const grad = ctx.createRadialGradient(mx, my, 0, mx, my, r)
            grad.addColorStop(0, `rgba(255, 240, 200, ${amp * 0.18})`)
            grad.addColorStop(1, 'rgba(255, 240, 200, 0)')
            ctx.save()
            ctx.globalCompositeOperation = 'screen'
            ctx.fillStyle = grad
            ctx.fillRect(mx - r, my - r, r * 2, r * 2)
            ctx.restore()
          }
        }
      } else if (animationMode === 'abstract' && phase === 'speaking') {
        // ABSTRACT: pas d overlay localise. On ajoute un glow global pulsant sur
        // toute l image pour symboliser la parole sans element anatomique.
        const amp = Math.min(1, speakingAmplitude * 1.5)
        ctx.save()
        ctx.globalCompositeOperation = 'screen'
        const glow = ctx.createRadialGradient(W / 2, H / 2, W * 0.2, W / 2, H / 2, W * 0.6)
        glow.addColorStop(0, `rgba(150, 100, 255, ${amp * 0.22})`)
        glow.addColorStop(1, 'rgba(150, 100, 255, 0)')
        ctx.fillStyle = glow
        ctx.fillRect(0, 0, W, H)
        ctx.restore()
      }

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    return () => cancelAnimationFrame(raf)
  }, [imgLoaded, phase, volumeLevel, speakingAmplitude, spokenText, audioRef, phonemeCuesRef, f])

  return (
    <div
      className="relative overflow-hidden rounded-2xl"
      style={{ width: size, height: size, background: '#1a1a24' }}
    >
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        style={{ width: '100%', height: '100%', display: 'block' }}
      />
      {!imgLoaded && !imgError && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-white/40">
          Chargement avatar...
        </div>
      )}
      {imgError && (
        <div className="absolute inset-0 flex items-center justify-center p-3 text-center text-[11px] text-red-300">
          {imgError}
        </div>
      )}
    </div>
  )
}
