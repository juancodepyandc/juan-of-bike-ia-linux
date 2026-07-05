/**
 * LyraCharacter — flat-design cartoon avatar pour le module Voice.
 *
 * Style : ours Duolingo / mascotte iconique. SVG pur, animé via state,
 * léger (<10kB). Lit la `phase` du moteur voix pour déclencher :
 *
 *   - mouth viseme : phoneme/rhubarb cue → forme bouche (closed / o / a / e / m)
 *   - eyes : blink toutes les 3-5s + regard qui suit doucement le curseur
 *   - head sway : bascule légère (±2°) à 4s/cycle quand idle
 *   - body breath : scale ±1% inhale/exhale (3s)
 *   - arms gesture : hand wave à l'arrivée, idle subtle
 *
 * Sans dépendance externe (pas de three.js, pas de Lottie).
 */
import { useEffect, useMemo, useRef, useState } from 'react'

export type LyraPhase = 'idle' | 'listening' | 'thinking' | 'speaking'
export type LyraViseme = 'closed' | 'A' | 'E' | 'I' | 'O' | 'U' | 'M' | 'F'
export type LyraEmotion = 'neutral' | 'happy' | 'curious' | 'focus' | 'sad' | 'surprised'

interface Props {
  phase: LyraPhase
  /** 0..1 — amplitude vocale temps réel, drive l'ouverture bouche. */
  amplitude?: number
  /** Viseme courant (depuis rhubarbToMorph ou phonemizer). 'closed' au repos. */
  viseme?: LyraViseme
  /** Émotion globale (eyes + sourcils + bouche au repos). */
  emotion?: LyraEmotion
  /** Couleur principale (overrideable). */
  accent?: string
  /** Taille en px (carré). */
  size?: number
  /** Lyra pointe avec son bras gauche (haut/gauche par défaut) — utilisé quand
      la caméra est active pour montrer ce qu'elle analyse. */
  pointingDirection?: 'left' | 'right' | 'up' | null
  /** Clé qui change déclenche une micro-réaction (sourcils levés brièvement)
      — par exemple à la réception d'un nouveau message user. */
  reactKey?: string | number
  /** Si défini, déclenche une animation "wave goodbye" (bras gauche levé +
      oscillation latérale rapide). */
  wavingBye?: boolean
}

// Mouth path par viseme : flat-design simple, expressivité claire.
// Viseme paths centrés à (100, 154) pour matcher la nouvelle position
// de la bouche sous le nez (y=142, écart ~12).
const MOUTH_PATHS: Record<LyraViseme, string> = {
  closed: 'M 93 154 Q 100 158 107 154',
  A:      'M 86 150 Q 100 172 114 150 Q 100 160 86 150 Z',
  E:      'M 84 154 Q 100 164 116 154 L 112 158 L 88 158 Z',
  I:      'M 90 154 L 110 154 L 108 158 L 92 158 Z',
  O:      'M 90 152 Q 100 168 110 152 Q 100 160 90 152 Z',
  U:      'M 92 152 Q 100 165 108 152 Q 100 158 92 152 Z',
  M:      'M 90 156 Q 100 158 110 156',
  F:      'M 88 154 Q 100 162 112 154',
}

const EMOTION_BROWS: Record<LyraEmotion, { l: string; r: string }> = {
  neutral:   { l: 'M 74 108 Q 84 102 94 107', r: 'M 106 107 Q 116 102 126 108' },
  happy:     { l: 'M 74 106 Q 84 98 94 104',  r: 'M 106 104 Q 116 98 126 106' },
  curious:   { l: 'M 74 110 Q 84 96 94 102',  r: 'M 106 108 Q 116 106 126 110' },
  focus:     { l: 'M 74 110 Q 84 114 94 112', r: 'M 106 112 Q 116 114 126 110' },
  sad:       { l: 'M 74 105 Q 84 113 94 110', r: 'M 106 110 Q 116 113 126 105' },
  surprised: { l: 'M 74 102 Q 84 94 94 102',  r: 'M 106 102 Q 116 94 126 102' },
}

export default function LyraCharacter({
  phase = 'idle',
  amplitude = 0,
  viseme = 'closed',
  emotion = 'neutral',
  accent = '#b48cff',
  size = 320,
  pointingDirection = null,
  reactKey,
  wavingBye = false,
}: Props) {
  const [blink, setBlink] = useState(false)
  const [gaze, setGaze] = useState({ x: 0, y: 0 })
  const [jumpUntil, setJumpUntil] = useState(0)
  const [forcedEmotion, setForcedEmotion] = useState<LyraEmotion | null>(null)
  // React on reactKey change : raise eyebrows briefly + tiny head bump.
  useEffect(() => {
    if (reactKey === undefined) return
    setForcedEmotion('surprised')
    setJumpUntil(performance.now() + 280)
    const t = window.setTimeout(() => setForcedEmotion(null), 480)
    return () => clearTimeout(t)
  }, [reactKey])
  const breathRef = useRef(0)
  const swayRef = useRef(0)
  const [, force] = useState(0)

  // Blink loop : 250ms close every 3-5s (random). Skip pour size < 60px.
  useEffect(() => {
    if (size < 60) return
    let cancelled = false
    const loop = () => {
      if (cancelled) return
      const next = 3000 + Math.random() * 2500
      window.setTimeout(() => {
        if (cancelled) return
        setBlink(true)
        window.setTimeout(() => {
          if (cancelled) return
          setBlink(false)
          loop()
        }, 180)
      }, next)
    }
    loop()
    return () => { cancelled = true }
  }, [size])

  // Idle breath + sway anim — throttled à 100ms (10 FPS) pour ne pas saturer
  // le CPU quand plusieurs Lyra rendent en parallèle (9+ instances dans
  // l'app). Visuellement quasi identique au 60 FPS pour ce type d'anim.
  // Skip TOTAL si size < 96px (icon-mode, anim invisible de toute façon).
  useEffect(() => {
    if (size < 96) return
    let start = performance.now()
    const tick = () => {
      const dt = (performance.now() - start) / 1000
      breathRef.current = Math.sin(dt * (2 * Math.PI) / 3) * 0.01
      swayRef.current = Math.sin(dt * (2 * Math.PI) / 4) * 2.2
      force((n) => (n + 1) % 1024)
    }
    const id = window.setInterval(tick, 100)
    return () => window.clearInterval(id)
  }, [size])

  // Gaze : suit le curseur global (legèrement). Skip pour les petites
  // instances (icon mode) — le gaze n'est pas visible et ça évite N event
  // listeners qui se déclenchent à chaque mousemove.
  useEffect(() => {
    if (size < 120) return
    let raf = 0
    let pending: { x: number; y: number } | null = null
    const handler = (e: MouseEvent) => {
      const cx = window.innerWidth / 2
      const cy = window.innerHeight / 2
      const dx = (e.clientX - cx) / window.innerWidth
      const dy = (e.clientY - cy) / window.innerHeight
      pending = { x: Math.max(-1, Math.min(1, dx * 2)) * 2, y: Math.max(-1, Math.min(1, dy * 2)) * 1.5 }
      if (raf) return
      raf = requestAnimationFrame(() => {
        if (pending) setGaze(pending)
        pending = null
        raf = 0
      })
    }
    window.addEventListener('mousemove', handler, { passive: true })
    return () => {
      window.removeEventListener('mousemove', handler)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [size])

  // Effective viseme : si phase==='speaking' on prend `viseme` reçu, sinon closed.
  // amplitude (0..1) module l'ouverture (legère scaling au runtime via transform).
  const effectiveViseme: LyraViseme = phase === 'speaking' ? viseme : 'closed'
  const mouthScale = phase === 'speaking' ? (1 + amplitude * 0.6) : 1
  const mouthPath = MOUTH_PATHS[effectiveViseme]
  const effectiveEmotion: LyraEmotion = forcedEmotion ?? emotion
  const brows = EMOTION_BROWS[effectiveEmotion]
  // Easter egg : saut court (350ms) déclenché par clic.
  const jumpProgress = Math.max(0, Math.min(1, (jumpUntil - performance.now()) / 350))
  const jumpY = jumpProgress > 0
    ? -Math.sin(jumpProgress * Math.PI) * 22
    : 0
  const handleSelfClick = () => {
    setJumpUntil(performance.now() + 350)
    setForcedEmotion('surprised')
    setBlink(true)
    window.setTimeout(() => setBlink(false), 120)
    window.setTimeout(() => setForcedEmotion(null), 700)
  }

  // Geste bras par phase. En speaking, l'amplitude vocale ajoute du dynamisme.
  // En thinking, le bras DROIT remonte vers le menton (main pensive).
  // Quand pointingDirection est défini, le bras GAUCHE remonte pour pointer.
  const tNow = performance.now() / 1000
  const armSwingSpeaking = phase === 'speaking'
    ? Math.sin(tNow * Math.PI * 2 * 0.9) * (5 + amplitude * 10)
    : 0
  // Pointing direction surcharge le swing : rotation forte pour bras tendu.
  let armRotL = phase === 'speaking' ? armSwingSpeaking : 0
  let armDxL = 0
  let armDyL = 0
  if (wavingBye) {
    // Bras gauche levé qui oscille latéralement façon "coucou".
    armRotL = -75 + Math.sin(tNow * Math.PI * 2 * 2.5) * 18
    armDxL = 5; armDyL = -48
  } else if (pointingDirection === 'left') {
    armRotL = 55 + Math.sin(tNow * Math.PI * 2 * 0.5) * 2.5
    armDxL = 18; armDyL = -38
  } else if (pointingDirection === 'right') {
    armRotL = -65 + Math.sin(tNow * Math.PI * 2 * 0.5) * 2.5
    armDxL = -10; armDyL = -42
  } else if (pointingDirection === 'up') {
    armRotL = -90 + Math.sin(tNow * Math.PI * 2 * 0.5) * 3
    armDxL = 0; armDyL = -52
  }
  // En thinking : bras droit (regardant) levé : rotation -55° pour pointer vers le menton.
  const armRotR = phase === 'thinking'
    ? -55 + Math.sin(tNow * Math.PI * 2 * 0.4) * 2.5
    : phase === 'speaking' ? -armSwingSpeaking : 0
  // Position translation pour la main thinking : la main remonte vers menton.
  const armDxR = phase === 'thinking' ? -22 : 0
  const armDyR = phase === 'thinking' ? -40 : 0

  // Tilt par phase.
  const listenTilt = phase === 'listening' ? -6 : 0
  const thinkTilt = phase === 'thinking' ? 4 : 0
  const speakNod = phase === 'speaking' ? Math.sin(tNow * Math.PI * 2 * 1.6) * (1 + amplitude * 1.5) : 0

  const headTilt = swayRef.current + listenTilt + thinkTilt + speakNod
  const breathScale = 1 + breathRef.current

  // Pupil offset (px dans viewBox).
  const pupilDx = gaze.x * 1.8
  const pupilDy = gaze.y * 1.2 - (phase === 'thinking' ? 1.2 : 0)

  const accentLight = useMemo(() => lighten(accent, 0.4), [accent])
  const accentDark = useMemo(() => darken(accent, 0.25), [accent])

  // Update emotion blush + effective emotion through effectiveEmotion later.
  // (used in eyes/blush conditions below).
  const emotionForVisual = effectiveEmotion

  return (
    <svg
      viewBox="0 0 200 240"
      width={size}
      height={size * 1.2}
      onClick={handleSelfClick}
      style={{
        display: 'block',
        filter: phase === 'listening' ? 'drop-shadow(0 0 24px rgba(255,180,90,0.25))' : 'none',
        transition: 'filter 220ms ease',
        cursor: 'pointer',
        pointerEvents: 'auto',
        transform: `translateY(${jumpY}px)`,
      }}
      aria-label="Lyra, avatar Aurora vocale (clique pour la saluer)"
    >
      {/* SHADOW ELLIPSE (au sol) */}
      <ellipse cx="100" cy="232" rx="56" ry="4.5" fill="rgba(0,0,0,0.28)" />

      {/* BODY — cape qui descend bien sous la tête, épaules larges */}
      <g style={{ transform: `translateY(${-breathRef.current * 4}px) scale(${breathScale})`, transformOrigin: '100px 200px', transition: 'transform 60ms linear' }}>
        {/* Cape extérieure : épaules arrondies, base évasée */}
        <path
          d="M 44 230 Q 38 174 62 158 Q 76 152 100 152 Q 124 152 138 158 Q 162 174 156 230 Z"
          fill={accent}
        />
        {/* Buste : panneau frontal clair façon "tablier" cousu */}
        <path
          d="M 76 168 Q 100 178 124 168 L 124 218 Q 100 226 76 218 Z"
          fill="#f7f2e4"
        />
        {/* Couture cape (ligne décorative qui souligne les bords) */}
        <path
          d="M 76 168 Q 100 178 124 168"
          fill="none" stroke={accentDark} strokeWidth="1.6" opacity="0.6"
        />
        {/* Étoile centrale du buste */}
        <g transform="translate(100 194)">
          <path d="M 0 -9 L 2.7 -2.7 L 9 0 L 2.7 2.7 L 0 9 L -2.7 2.7 L -9 0 L -2.7 -2.7 Z" fill={accentDark} opacity="0.72" />
        </g>
        {/* Bras gauche — manche + main, posé devant le corps (peut pointer) */}
        <g style={{
          transform: `translate(${armDxL}px, ${armDyL}px) rotate(${armRotL}deg)`,
          transformOrigin: '60px 175px',
          transition: 'transform 320ms cubic-bezier(0.22, 1, 0.36, 1)',
        }}>
          <path d="M 48 168 Q 42 188 50 212 L 70 212 Q 76 188 70 168 Z" fill={accent} />
          <circle cx="60" cy="216" r="10" fill="#f1d3a8" stroke={accentDark} strokeWidth="1.2" opacity="0.95" />
          {/* Quand pointing, ajouter un index pointé sortant de la main */}
          {pointingDirection && (
            <path
              d="M 56 220 L 52 232 L 54 232 L 50 240 L 60 230 L 57 230 L 60 222 Z"
              fill="#f1d3a8" stroke={accentDark} strokeWidth="0.8"
            />
          )}
        </g>
        {/* Bras droit — en thinking : remonte vers le menton (main pensive) */}
        <g style={{
          transform: `translate(${armDxR}px, ${armDyR}px) rotate(${armRotR}deg)`,
          transformOrigin: '140px 175px',
          transition: 'transform 320ms cubic-bezier(0.22, 1, 0.36, 1)',
        }}>
          <path d="M 130 168 Q 124 188 130 212 L 152 212 Q 158 188 152 168 Z" fill={accent} />
          <circle cx="140" cy="216" r="10" fill="#f1d3a8" stroke={accentDark} strokeWidth="1.2" opacity="0.95" />
        </g>
      </g>

      {/* HEAD + face — sous-groupe qui tilt indépendamment */}
      <g style={{ transform: `rotate(${headTilt}deg)`, transformOrigin: '100px 110px', transition: 'transform 60ms linear' }}>
        {/* ANTENNES — petites pointes étoilées qui dépassent du hood,
            wiggle quand phase='listening' pour signaler l'écoute */}
        <g style={{
          transform: `rotate(${phase === 'listening' ? Math.sin(tNow * Math.PI * 2 * 1.6) * 6 : 0}deg)`,
          transformOrigin: '70px 30px',
          transition: 'transform 80ms linear',
        }}>
          <line x1="70" y1="30" x2="60" y2="14" stroke={accentDark} strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="58" cy="12" r="3.5" fill={accentLight} stroke={accentDark} strokeWidth="1" />
        </g>
        <g style={{
          transform: `rotate(${phase === 'listening' ? -Math.sin(tNow * Math.PI * 2 * 1.6 + 0.6) * 6 : 0}deg)`,
          transformOrigin: '130px 30px',
          transition: 'transform 80ms linear',
        }}>
          <line x1="130" y1="30" x2="140" y2="14" stroke={accentDark} strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="142" cy="12" r="3.5" fill={accentLight} stroke={accentDark} strokeWidth="1" />
        </g>
        {/* Capuche extérieure — englobe correctement le visage, descend en U */}
        <path
          d="M 36 110 Q 36 32 100 32 Q 164 32 164 110 Q 164 156 156 156 L 158 158 Q 130 160 100 160 Q 70 160 42 158 L 44 156 Q 36 156 36 110 Z"
          fill={accent}
        />
        {/* Étoiles sur la capuche */}
        <g fill={accentLight} opacity="0.85">
          <circle cx="56" cy="58" r="1.6" />
          <circle cx="72" cy="42" r="1.2" />
          <circle cx="128" cy="44" r="1.4" />
          <circle cx="146" cy="60" r="1.8" />
          <circle cx="82" cy="36" r="1" />
          <circle cx="118" cy="38" r="1" />
          <circle cx="50" cy="86" r="1.2" />
          <circle cx="150" cy="86" r="1" />
        </g>
        {/* Ombre intérieure de la capuche au-dessus du front */}
        <path d="M 56 92 Q 100 70 144 92 Q 100 80 56 92 Z" fill={accentDark} opacity="0.42" />

        {/* Visage (peau) — ovale légèrement plus large que haut */}
        <ellipse cx="100" cy="116" rx="44" ry="42" fill="#f7e5c8" />
        {/* Joues (subtil pour donner du volume) */}
        <ellipse cx="74" cy="140" rx="6" ry="3.4" fill="#f0c8a8" opacity="0.55" />
        <ellipse cx="126" cy="140" rx="6" ry="3.4" fill="#f0c8a8" opacity="0.55" />

        {/* Mèche frontale */}
        <path d="M 60 92 Q 80 78 100 82 Q 122 78 140 94 Q 122 86 100 88 Q 78 86 60 92 Z" fill={accentDark} />

        {/* SOURCILS — plus haut, au-dessus des yeux */}
        <path d={brows.l} stroke="#3b2a1a" strokeWidth="3.6" strokeLinecap="round" fill="none" />
        <path d={brows.r} stroke="#3b2a1a" strokeWidth="3.6" strokeLinecap="round" fill="none" />

        {/* YEUX — gros, expressifs, façon Duolingo. Taille modulée par emotion. */}
        <g>
          {(() => {
            const eyeScale = emotionForVisual === 'surprised' ? 1.18 : emotionForVisual === 'sad' ? 0.92 : 1
            const ryBase = (blink ? 0.8 : 11.5) * eyeScale
            const rxBase = 11 * eyeScale
            const pupilR = 5 * eyeScale
            return (
              <>
                <ellipse cx="84" cy="124" rx={rxBase} ry={ryBase} fill="#fff" stroke="#1a1410" strokeWidth="1.6" />
                {!blink && (
                  <>
                    <ellipse cx={84 + pupilDx} cy={124 + pupilDy} rx={pupilR} ry={pupilR * 1.12} fill="#1a1410" />
                    <circle cx={86 + pupilDx} cy={121 + pupilDy} r="1.8" fill="#fff" />
                    <circle cx={82 + pupilDx} cy={126 + pupilDy} r="0.8" fill="#fff" opacity="0.7" />
                  </>
                )}
                <ellipse cx="116" cy="124" rx={rxBase} ry={ryBase} fill="#fff" stroke="#1a1410" strokeWidth="1.6" />
                {!blink && (
                  <>
                    <ellipse cx={116 + pupilDx} cy={124 + pupilDy} rx={pupilR} ry={pupilR * 1.12} fill="#1a1410" />
                    <circle cx={118 + pupilDx} cy={121 + pupilDy} r="1.8" fill="#fff" />
                    <circle cx={114 + pupilDx} cy={126 + pupilDy} r="0.8" fill="#fff" opacity="0.7" />
                  </>
                )}
              </>
            )
          })()}
          {/* Larme quand sad */}
          {emotionForVisual === 'sad' && !blink && (
            <path d={`M ${84 + pupilDx - 1} ${134} Q ${84 + pupilDx - 1.5} ${140} ${84 + pupilDx} ${142} Q ${84 + pupilDx + 1.5} ${140} ${84 + pupilDx - 1} ${134} Z`} fill="rgba(140,200,255,0.85)" />
          )}
        </g>

        {/* Blush quand happy/listening — par-dessus les joues */}
        {(emotionForVisual === 'happy' || emotionForVisual === 'surprised' || phase === 'listening') && (
          <>
            <ellipse cx="74" cy="142" rx="5.5" ry="2.4" fill="#f6a6a6" opacity="0.65" />
            <ellipse cx="126" cy="142" rx="5.5" ry="2.4" fill="#f6a6a6" opacity="0.65" />
          </>
        )}

        {/* NEZ — petit point arrondi */}
        <ellipse cx="100" cy="142" rx="2" ry="2.4" fill="#3b2a1a" />

        {/* BOUCHE — sous le nez, visème animé */}
        <g style={{ transform: `scale(${mouthScale})`, transformOrigin: '100px 154px', transition: 'transform 50ms linear' }}>
          <path
            d={mouthPath}
            stroke="#2a1d10" strokeWidth="2.4" strokeLinecap="round"
            fill={effectiveViseme === 'A' || effectiveViseme === 'O' || effectiveViseme === 'U' ? '#5a2a2a' : 'none'}
          />
        </g>
      </g>

      {/* AURA / ÉTAT ANIMÉ (sous le character quand thinking) */}
      {phase === 'thinking' && (
        <g>
          <circle cx="100" cy="200" r="8" fill="none" stroke={accent} strokeWidth="1.8" opacity="0.5">
            <animate attributeName="r" from="6" to="40" dur="1.5s" repeatCount="indefinite" />
            <animate attributeName="opacity" from="0.5" to="0" dur="1.5s" repeatCount="indefinite" />
          </circle>
          {/* éclair flash près de la main thinking — calculating viseme */}
          <g transform={`translate(80 158)`}>
            <path d="M 0 0 L 4 -4 L 2 -4 L 6 -10 L 0 -3 L 3 -3 Z" fill={accentLight} opacity="0.9">
              <animate attributeName="opacity" values="0;1;0" dur="0.8s" repeatCount="indefinite" />
            </path>
          </g>
        </g>
      )}

      {/* Particules d'étoiles autour quand speaking — feedback magique */}
      {phase === 'speaking' && (
        <g fill={accentLight}>
          {Array.from({ length: 6 }).map((_, i) => {
            const offsets = [
              { x: 30, y: 60, d: 1.8 },
              { x: 170, y: 70, d: 2.2 },
              { x: 20, y: 130, d: 1.6 },
              { x: 180, y: 140, d: 2.4 },
              { x: 60, y: 180, d: 1.9 },
              { x: 140, y: 180, d: 2.1 },
            ][i]
            return (
              <g key={i} opacity={0.85}>
                <circle cx={offsets.x} cy={offsets.y} r="1.6">
                  <animate attributeName="opacity" values="0.2;1;0.2" dur={`${offsets.d}s`} repeatCount="indefinite" begin={`${i * 0.15}s`} />
                  <animate attributeName="r" values="1;2.4;1" dur={`${offsets.d}s`} repeatCount="indefinite" begin={`${i * 0.15}s`} />
                  <animateTransform
                    attributeName="transform"
                    type="translate"
                    values={`0 0; ${(i % 2 === 0 ? 4 : -4)} -12; 0 0`}
                    dur={`${offsets.d * 1.4}s`}
                    repeatCount="indefinite"
                    begin={`${i * 0.15}s`}
                  />
                </circle>
              </g>
            )
          })}
        </g>
      )}
    </svg>
  )
}

// ----------------------------------------------------------------------
// HELPERS COULEURS
// ----------------------------------------------------------------------

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  if (h.length !== 6) return [180, 140, 255]
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function rgbToHex(r: number, g: number, b: number): string {
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')
  return `#${c(r)}${c(g)}${c(b)}`
}

function lighten(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  return rgbToHex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount)
}

function darken(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex)
  return rgbToHex(r * (1 - amount), g * (1 - amount), b * (1 - amount))
}
