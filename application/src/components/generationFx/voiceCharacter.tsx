import { useId } from 'react'

export type V4Viseme = 'closed' | 'A' | 'E' | 'I' | 'O' | 'U' | 'M' | 'F'

type Props = {
  phase: string
  viseme: V4Viseme
  level: number
  size?: number
}

const TEAL = '#2DD4BF'
const TEAL_D = '#1B7A70'
const TEAL_L = '#7DF0E2'
const SKIN = '#F9DDC2'
const SKIN_D = '#E8C09A'
const HAIR = '#2AA79A'
const HAIR_D = '#17685F'
const HAIR_L = '#8FF5E7'
const OUTFIT = '#0F3B38'
const OUTFIT_L = '#1D5F5A'
const INK = '#0A0F1E'

function Mouth({ viseme, boost }: { viseme: V4Viseme; boost: number }) {
  const s = 1 + boost * 0.25
  switch (viseme) {
    case 'A':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <ellipse cx="0" cy="0" rx="11" ry="12" fill="#5A2430" />
          <path d="M-10 -4 Q0 -8 10 -4 L10 -1 Q0 -4.6 -10 -1 Z" fill="#FFFFFF" />
          <ellipse cx="0" cy="7.5" rx="6.5" ry="3.6" fill="#C2556B" />
        </g>
      )
    case 'E':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <ellipse cx="0" cy="0" rx="12.5" ry="6.5" fill="#5A2430" />
          <path d="M-11 -2.4 Q0 -5.4 11 -2.4 L11 0 Q0 -2.4 -11 0 Z" fill="#FFFFFF" />
        </g>
      )
    case 'I':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <ellipse cx="0" cy="0" rx="10" ry="3.4" fill="#5A2430" />
          <path d="M-8.6 -1 Q0 -2.8 8.6 -1 L8.6 0.4 Q0 -0.8 -8.6 0.4 Z" fill="#FFFFFF" />
        </g>
      )
    case 'O':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <ellipse cx="0" cy="0" rx="7" ry="9" fill="#5A2430" />
          <ellipse cx="0" cy="4.4" rx="4" ry="2.8" fill="#C2556B" />
        </g>
      )
    case 'U':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <ellipse cx="0" cy="0" rx="4.6" ry="5.6" fill="#5A2430" />
        </g>
      )
    case 'M':
      return (
        <g transform="translate(110 172)">
          <path d="M-9 0 Q0 2.4 9 0" stroke="#B06A6E" strokeWidth="2.6" fill="none" strokeLinecap="round" />
        </g>
      )
    case 'F':
      return (
        <g transform={`translate(110 172) scale(${s})`}>
          <path d="M-9 -1.5 Q0 -3.5 9 -1.5 L9 1 Q0 -0.6 -9 1 Z" fill="#FFFFFF" />
          <path d="M-9 1 Q0 4.6 9 1 Q0 7.2 -9 1 Z" fill="#C2556B" />
        </g>
      )
    default:
      return (
        <path d="M101 171 Q110 177.5 119 171" stroke="#B06A6E" strokeWidth="2.8" fill="none" strokeLinecap="round" />
      )
  }
}

export default function V4VoiceCharacter({ phase, viseme, level, size = 300 }: Props) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const irisId = `vi${uid}`
  const skinId = `vs${uid}`
  const hairId = `vh${uid}`
  const outfitId = `vo${uid}`
  const glowId = `vg${uid}`
  const listening = phase === 'listening'
  const thinking = phase === 'thinking' || phase === 'preparing' || phase === 'transcribing' || phase === 'searching' || phase === 'observing'
  const speaking = phase === 'speaking'
  const boost = Math.max(0, Math.min(1, level))
  const headTilt = listening ? -5 : thinking ? 4 : 0
  const pupilDx = thinking ? 2.4 : listening ? -1.6 : 0
  const pupilDy = thinking ? -3 : 0

  return (
    <svg viewBox="0 0 220 300" width={size} height={size * (300 / 220)} aria-hidden="true" style={{ overflow: 'visible' }}>
      <defs>
        <radialGradient id={irisId} cx="0.38" cy="0.3">
          <stop offset="0" stopColor={TEAL_L} />
          <stop offset="0.55" stopColor={TEAL} />
          <stop offset="1" stopColor="#0C4A44" />
        </radialGradient>
        <linearGradient id={skinId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FDE8D2" />
          <stop offset="1" stopColor={SKIN_D} />
        </linearGradient>
        <linearGradient id={hairId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3FC3B3" />
          <stop offset="1" stopColor={HAIR_D} />
        </linearGradient>
        <linearGradient id={outfitId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={OUTFIT_L} />
          <stop offset="1" stopColor={OUTFIT} />
        </linearGradient>
        <radialGradient id={glowId}>
          <stop offset="0" stopColor={TEAL} stopOpacity="0.4" />
          <stop offset="1" stopColor={TEAL} stopOpacity="0" />
        </radialGradient>
      </defs>

      <ellipse cx="110" cy="288" rx="64" ry="10" fill={`url(#${glowId})`} />
      <ellipse cx="110" cy="286" rx="46" ry="6.5" fill="#000" opacity="0.35" />

      <g>
        <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur={speaking ? '2.2s' : '3.8s'} repeatCount="indefinite" />

        <path d="M52 148 C40 190 40 236 52 268 C60 276 74 280 84 280 L80 200 Z" fill={`url(#${hairId})`} opacity="0.95">
          <animateTransform attributeName="transform" type="rotate" values="0 60 150;2.2 60 150;0 60 150" dur="4.6s" repeatCount="indefinite" />
        </path>
        <path d="M168 148 C180 190 180 236 168 268 C160 276 146 280 136 280 L140 200 Z" fill={`url(#${hairId})`} opacity="0.95">
          <animateTransform attributeName="transform" type="rotate" values="0 160 150;-2.2 160 150;0 160 150" dur="5.2s" repeatCount="indefinite" />
        </path>
        <path d="M60 160 C55 200 56 240 64 266 L74 262 C68 236 68 200 72 168 Z" fill={HAIR_L} opacity="0.28" />

        <path d="M60 286 C62 244 80 224 110 224 C140 224 158 244 160 286 Z" fill={`url(#${outfitId})`} stroke="rgba(255,255,255,.14)" strokeWidth="1.2" />
        <path d="M92 226 L110 246 L128 226 L120 224 L110 234 L100 224 Z" fill={TEAL_D} />
        <path d="M104 250 L116 250 L114 262 L106 262 Z" fill={TEAL} opacity="0.85">
          {speaking && <animate attributeName="opacity" values="0.85;0.4;0.85" dur="0.9s" repeatCount="indefinite" />}
        </path>
        <path d="M63 282 C66 254 76 238 90 230 L86 286 Z" fill="rgba(255,255,255,.06)" />

        <g opacity={listening ? 1 : 0} style={{ transition: 'opacity .35s' }}>
          <path d="M158 246 C172 238 178 220 172 202 C168 190 160 182 152 178" stroke={`url(#${outfitId})`} strokeWidth="17" fill="none" strokeLinecap="round" />
          <ellipse cx="150" cy="172" rx="10" ry="8.5" fill={`url(#${skinId})`} transform="rotate(-24 150 172)" />
        </g>
        <g opacity={thinking ? 1 : 0} style={{ transition: 'opacity .35s' }}>
          <path d="M64 246 C52 234 48 216 56 198 C60 189 68 184 78 182" stroke={`url(#${outfitId})`} strokeWidth="17" fill="none" strokeLinecap="round" />
          <ellipse cx="84" cy="184" rx="9.5" ry="8" fill={`url(#${skinId})`} transform="rotate(30 84 184)" />
        </g>
        <g opacity={!listening && !thinking ? 1 : 0} style={{ transition: 'opacity .35s' }}>
          <path d="M66 244 C58 256 56 268 58 280" stroke={`url(#${outfitId})`} strokeWidth="16" fill="none" strokeLinecap="round" />
          <path d="M154 244 C162 256 164 268 162 280" stroke={`url(#${outfitId})`} strokeWidth="16" fill="none" strokeLinecap="round" />
        </g>

        <path d="M99 208 L121 208 L121 228 C114 233 106 233 99 228 Z" fill={`url(#${skinId})`} />
        <path d="M99 208 L121 208 L121 216 C114 220 106 220 99 216 Z" fill={SKIN_D} />

        <g transform={`rotate(${headTilt} 110 150)`}>
          <path d="M48 118 C44 62 72 30 110 30 C148 30 176 62 172 118 C174 138 170 152 164 160 C168 138 166 122 160 112 C164 134 160 152 152 162 L148 118 L72 118 L68 162 C60 152 56 134 60 112 C54 122 52 138 56 160 C50 152 46 138 48 118 Z" fill={`url(#${hairId})`} />

          <path d="M69 118 C69 82 85 60 110 60 C135 60 151 82 151 118 C151 146 135 168 110 168 C85 168 69 146 69 118 Z" fill={`url(#${skinId})`} />
          <path d="M67 122 C62 122 59 128 61 134 C63 139 67 141 71 140 Z" fill={`url(#${skinId})`} />
          <path d="M153 122 C158 122 161 128 159 134 C157 139 153 141 149 140 Z" fill={`url(#${skinId})`} />

          <g transform={`translate(${pupilDx} ${pupilDy})`}>
            <g>
              <path d="M78 132 Q89 122 100 132 Q89 146 78 132 Z" fill="#FFFFFF" />
              <circle cx="89" cy="132.5" r={thinking ? 6.2 : 7.3} fill={`url(#${irisId})`} />
              <circle cx="89" cy="132.5" r="2.8" fill={INK} />
              <circle cx="86.6" cy="129.8" r="2" fill="#FFF" />
              <circle cx="91.6" cy="135" r="1" fill="#FFF" opacity="0.8" />
            </g>
            <g>
              <path d="M120 132 Q131 122 142 132 Q131 146 120 132 Z" fill="#FFFFFF" />
              <circle cx="131" cy="132.5" r={thinking ? 6.2 : 7.3} fill={`url(#${irisId})`} />
              <circle cx="131" cy="132.5" r="2.8" fill={INK} />
              <circle cx="128.6" cy="129.8" r="2" fill="#FFF" />
              <circle cx="133.6" cy="135" r="1" fill="#FFF" opacity="0.8" />
            </g>
          </g>
          {thinking && (
            <g fill={SKIN}>
              <path d="M77 128 Q89 121 101 128 L101 132 Q89 125 77 132 Z" />
              <path d="M119 128 Q131 121 143 128 L143 132 Q131 125 119 132 Z" />
            </g>
          )}
          <path d="M77 130.5 Q89 120.5 101 130.5" stroke={HAIR_D} strokeWidth="2.6" fill="none" strokeLinecap="round" />
          <path d="M119 130.5 Q131 120.5 143 130.5" stroke={HAIR_D} strokeWidth="2.6" fill="none" strokeLinecap="round" />
          <path d="M99 127 L104 123.4 M100.6 129.6 L106 127" stroke={HAIR_D} strokeWidth="1.4" strokeLinecap="round" />
          <path d="M141 127 L146 123.4 M142.6 129.6 L148 127" stroke={HAIR_D} strokeWidth="1.4" strokeLinecap="round" />
          {!thinking && (
            <g fill={SKIN}>
              <ellipse cx="89" cy="126.4" rx="11.5" ry="4.2" opacity="0">
                <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;0.46;0.5;0.54;1" dur="4.4s" repeatCount="indefinite" />
              </ellipse>
              <ellipse cx="131" cy="126.4" rx="11.5" ry="4.2" opacity="0">
                <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;0.46;0.5;0.54;1" dur="4.4s" repeatCount="indefinite" />
              </ellipse>
            </g>
          )}

          <path d={listening ? 'M84 114 Q89 110 95 113' : thinking ? 'M83 116 Q89 112 95 114' : 'M83 115 Q89 112 95 114.6'} stroke={HAIR_D} strokeWidth="2.4" fill="none" strokeLinecap="round" />
          <path d={listening ? 'M125 113 Q131 110 136 114' : thinking ? 'M125 114 Q131 111 137 116' : 'M125 114.6 Q131 112 137 115'} stroke={HAIR_D} strokeWidth="2.4" fill="none" strokeLinecap="round" />

          <path d="M108 148 Q110 152 112.5 148.4" stroke={SKIN_D} strokeWidth="1.8" fill="none" strokeLinecap="round" />
          <ellipse cx="82" cy="152" rx="7.5" ry="4" fill={TEAL} opacity="0.16" />
          <ellipse cx="138" cy="152" rx="7.5" ry="4" fill={TEAL} opacity="0.16" />

          <Mouth viseme={speaking ? viseme : thinking ? 'M' : 'closed'} boost={boost} />

          <path d="M62 104 C60 58 84 42 110 42 C136 42 160 58 158 104 C152 114 147 106 143 94 C139 112 130 114 124 99 C118 113 106 114 101 99 C96 113 87 113 81 99 C77 110 68 114 62 104 Z" fill={`url(#${hairId})`} />
          <path d="M74 58 C86 48 104 44 116 48 C102 48 88 52 80 62 Z" fill={HAIR_L} opacity="0.5" />
          <path d="M96 52 C104 48 116 48 124 54 C116 52 106 53 100 58 Z" fill={HAIR_L} opacity="0.35" />
          <path d="M63 100 C61 118 63 134 68 146 L61 142 C57 128 58 112 63 100 Z" fill={`url(#${hairId})`}>
            <animateTransform attributeName="transform" type="rotate" values="0 64 100;3 64 100;0 64 100" dur="3.8s" repeatCount="indefinite" />
          </path>
          <path d="M157 100 C159 118 157 134 152 146 L159 142 C163 128 162 112 157 100 Z" fill={`url(#${hairId})`}>
            <animateTransform attributeName="transform" type="rotate" values="0 156 100;-3 156 100;0 156 100" dur="4.4s" repeatCount="indefinite" />
          </path>

          <path d="M58 108 Q52 64 96 44 M162 108 Q168 64 124 44" stroke={TEAL_D} strokeWidth="7" fill="none" strokeLinecap="round" />
          <rect x="47" y="104" width="17" height="30" rx="8" fill={TEAL_D} stroke={TEAL} strokeWidth="1.4" />
          <rect x="156" y="104" width="17" height="30" rx="8" fill={TEAL_D} stroke={TEAL} strokeWidth="1.4" />
          <rect x="50" y="109" width="4" height="20" rx="2" fill={TEAL_L} opacity={speaking || listening ? 0.9 : 0.4}>
            {(speaking || listening) && <animate attributeName="opacity" values="0.9;0.35;0.9" dur="0.7s" repeatCount="indefinite" />}
          </rect>
          <rect x="166" y="109" width="4" height="20" rx="2" fill={TEAL_L} opacity={speaking || listening ? 0.9 : 0.4}>
            {(speaking || listening) && <animate attributeName="opacity" values="0.9;0.35;0.9" dur="0.7s" repeatCount="indefinite" />}
          </rect>
          <path d="M62 132 Q64 156 84 168" stroke={TEAL_D} strokeWidth="3.4" fill="none" />
          <ellipse cx="87" cy="169.5" rx="5" ry="4" fill={INK} stroke={TEAL} strokeWidth="1.4">
            {speaking && <animate attributeName="stroke-width" values="1.4;2.6;1.4" dur="0.6s" repeatCount="indefinite" />}
          </ellipse>
        </g>
      </g>

      {speaking && (
        <g fill={TEAL_L} fontFamily="Georgia, serif" fontSize="15">
          <text x="176" y="120">
            ♪
            <animateTransform attributeName="transform" type="translate" values="0 0;8 -26;14 -50" dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;1;0" dur="2s" repeatCount="indefinite" />
          </text>
          <text x="30" y="140" fontSize="12">
            ♫
            <animateTransform attributeName="transform" type="translate" values="0 0;-8 -22;-12 -46" dur="2.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;1;0" dur="2.6s" repeatCount="indefinite" />
          </text>
        </g>
      )}
      {thinking && (
        <g fill={TEAL_L} opacity="0.9">
          <circle cx="170" cy="70" r="3">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="1.6s" repeatCount="indefinite" />
          </circle>
          <circle cx="181" cy="56" r="4.2">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="1.6s" begin="0.4s" repeatCount="indefinite" />
          </circle>
          <circle cx="194" cy="40" r="5.4">
            <animate attributeName="opacity" values="0.2;1;0.2" dur="1.6s" begin="0.8s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
      {listening && (
        <g stroke={TEAL} strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.85">
          <path d="M186 140 Q192 150 186 160">
            <animate attributeName="opacity" values="0.85;0.2;0.85" dur="1.1s" repeatCount="indefinite" />
          </path>
          <path d="M194 132 Q204 150 194 168">
            <animate attributeName="opacity" values="0.2;0.85;0.2" dur="1.1s" repeatCount="indefinite" />
          </path>
        </g>
      )}
    </svg>
  )
}
