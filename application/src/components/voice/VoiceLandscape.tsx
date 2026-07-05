/**
 * VoiceLandscape — backdrop flat-design pour le module Voice.
 *
 * Style : pareil que la mascotte Duolingo (ciel dégradé + montagnes
 * superposées + silhouettes sapins + sol). Mais palette Aurora (violet /
 * teal / orange) avec un voile d'aurore stylisée la nuit, ciel doux le
 * jour. Le mode jour/nuit suit l'heure locale.
 *
 * Pur SVG, plein écran via preserveAspectRatio="xMidYMid slice".
 */
import { useMemo } from 'react'

export type LandscapeMode = 'aurora' | 'day' | 'sunset' | 'auto'

interface Props {
  mode?: LandscapeMode
  /** Animation des éléments (étoiles scintillent, aurore ondule). */
  animated?: boolean
}

function pickMode(mode: LandscapeMode): Exclude<LandscapeMode, 'auto'> {
  if (mode !== 'auto') return mode
  const h = new Date().getHours()
  if (h >= 6 && h < 17) return 'day'
  if (h >= 17 && h < 20) return 'sunset'
  return 'aurora'
}

export default function VoiceLandscape({ mode = 'auto', animated = true }: Props) {
  const m = useMemo(() => pickMode(mode), [mode])
  const sky =
    m === 'aurora'
      ? { top: '#0c1638', mid: '#3a1f5f', bot: '#562b5a' }
      : m === 'sunset'
        ? { top: '#3a1d4a', mid: '#a3457a', bot: '#f0a070' }
        : { top: '#9bd2f1', mid: '#c8e9f6', bot: '#f1f7f8' }

  const mtnFar =
    m === 'aurora' ? '#243154' : m === 'sunset' ? '#6c3f6e' : '#7b9bb8'
  const mtnMid =
    m === 'aurora' ? '#1a223d' : m === 'sunset' ? '#4b2a5d' : '#5a7c9c'
  const mtnNear =
    m === 'aurora' ? '#0d1226' : m === 'sunset' ? '#2f1c44' : '#3f5d7d'

  const tree = m === 'aurora' ? '#091022' : m === 'sunset' ? '#1f0e30' : '#2c4836'
  const ground = m === 'aurora' ? '#0a0d1c' : m === 'sunset' ? '#1c1226' : '#84a07a'

  return (
    <svg
      viewBox="0 0 1600 900"
      preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="vlSky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={sky.top} />
          <stop offset="55%" stopColor={sky.mid} />
          <stop offset="100%" stopColor={sky.bot} />
        </linearGradient>
        <linearGradient id="vlAurora" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(100,255,200,0)" />
          <stop offset="40%" stopColor="rgba(120,255,200,0.42)" />
          <stop offset="70%" stopColor="rgba(180,140,255,0.32)" />
          <stop offset="100%" stopColor="rgba(255,120,200,0.05)" />
        </linearGradient>
        <radialGradient id="vlSun" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={m === 'sunset' ? '#ffe7b0' : '#fff7c8'} stopOpacity="0.95" />
          <stop offset="60%" stopColor={m === 'sunset' ? '#ff9c6c' : '#fff2a8'} stopOpacity="0.4" />
          <stop offset="100%" stopColor={m === 'sunset' ? '#a3457a' : '#fff2a8'} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Ciel */}
      <rect width="1600" height="900" fill="url(#vlSky)" />

      {/* Soleil / lune */}
      {m === 'aurora' ? (
        <circle cx="1380" cy="180" r="56" fill="#f6f2e0" opacity="0.85" />
      ) : m === 'sunset' ? (
        <circle cx="320" cy="380" r="140" fill="url(#vlSun)" />
      ) : (
        <circle cx="1280" cy="200" r="80" fill="url(#vlSun)" />
      )}

      {/* AURORE — bandes ondulantes en mode nuit */}
      {m === 'aurora' && (
        <g style={{ mixBlendMode: 'screen', opacity: 0.9 }}>
          <path d="M 0 200 Q 400 80 800 220 T 1600 240 L 1600 520 Q 1200 380 800 540 T 0 480 Z" fill="url(#vlAurora)">
            {animated && (
              <animate attributeName="d"
                dur="14s" repeatCount="indefinite"
                values="
                  M 0 200 Q 400 80 800 220 T 1600 240 L 1600 520 Q 1200 380 800 540 T 0 480 Z;
                  M 0 220 Q 400 140 800 180 T 1600 260 L 1600 500 Q 1200 420 800 500 T 0 460 Z;
                  M 0 200 Q 400 80 800 220 T 1600 240 L 1600 520 Q 1200 380 800 540 T 0 480 Z" />
            )}
          </path>
          <path d="M 0 280 Q 500 180 1000 300 T 1600 320 L 1600 480 Q 1100 420 600 460 T 0 440 Z" fill="rgba(140,220,200,0.18)">
            {animated && (
              <animate attributeName="d"
                dur="17s" repeatCount="indefinite"
                values="
                  M 0 280 Q 500 180 1000 300 T 1600 320 L 1600 480 Q 1100 420 600 460 T 0 440 Z;
                  M 0 300 Q 500 240 1000 260 T 1600 340 L 1600 460 Q 1100 440 600 420 T 0 460 Z;
                  M 0 280 Q 500 180 1000 300 T 1600 320 L 1600 480 Q 1100 420 600 460 T 0 440 Z" />
            )}
          </path>
        </g>
      )}

      {/* Étoiles (uniquement la nuit) */}
      {m === 'aurora' && (
        <g fill="#fff">
          {Array.from({ length: 70 }).map((_, i) => {
            const x = (i * 197) % 1600
            const y = (i * 113) % 380
            const r = (i % 4 === 0) ? 1.6 : i % 3 === 0 ? 1.1 : 0.7
            const o = 0.4 + (i % 5) * 0.12
            return <circle key={i} cx={x} cy={y} r={r} opacity={o} />
          })}
        </g>
      )}

      {/* Montagnes loin */}
      <path
        d="M 0 520 L 180 380 L 320 460 L 460 360 L 620 480 L 780 360 L 920 460 L 1100 380 L 1260 480 L 1400 380 L 1600 460 L 1600 900 L 0 900 Z"
        fill={mtnFar}
        opacity="0.85"
      />
      {/* Montagnes mid */}
      <path
        d="M 0 620 L 200 460 L 360 580 L 540 440 L 720 600 L 880 460 L 1080 600 L 1240 480 L 1420 600 L 1600 480 L 1600 900 L 0 900 Z"
        fill={mtnMid}
      />
      {/* Montagnes near */}
      <path
        d="M 0 740 L 240 580 L 460 720 L 660 560 L 880 740 L 1080 600 L 1280 740 L 1480 600 L 1600 700 L 1600 900 L 0 900 Z"
        fill={mtnNear}
      />

      {/* SOL */}
      <rect x="0" y="760" width="1600" height="140" fill={ground} />

      {/* Sapins gauche */}
      <g fill={tree}>
        <polygon points="80,820 120,720 160,820" />
        <polygon points="80,800 120,700 160,800" />
        <polygon points="180,830 230,710 280,830" />
        <polygon points="180,810 230,690 280,810" />
        <polygon points="300,830 340,740 380,830" />
      </g>
      {/* Sapins droite */}
      <g fill={tree}>
        <polygon points="1240,830 1290,710 1340,830" />
        <polygon points="1240,810 1290,690 1340,810" />
        <polygon points="1380,820 1420,720 1460,820" />
        <polygon points="1380,800 1420,700 1460,800" />
        <polygon points="1500,830 1540,750 1580,830" />
      </g>

      {/* Lucioles / particules quand aurora */}
      {m === 'aurora' && animated && (
        <g fill="#bff5ff" opacity="0.7">
          {Array.from({ length: 18 }).map((_, i) => {
            const x = 80 + ((i * 89) % 1440)
            const y = 600 + ((i * 31) % 200)
            return (
              <circle key={i} cx={x} cy={y} r="1.4">
                <animate attributeName="cy" values={`${y};${y - 18};${y}`} dur={`${5 + (i % 4)}s`} repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.2;0.9;0.2" dur={`${4 + (i % 3)}s`} repeatCount="indefinite" />
              </circle>
            )
          })}
        </g>
      )}
    </svg>
  )
}
