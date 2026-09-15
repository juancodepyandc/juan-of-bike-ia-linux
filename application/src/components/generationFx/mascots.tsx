import { useId, type ReactElement } from 'react'
import type { FxModule } from './fxBus.ts'

export type { FxModule }

export const FX_AGENTS: Record<FxModule, { name: string; accent: string; hello: string }> = {
  conversation: { name: 'Lumo',   accent: '#8B5CF6', hello: 'Je structure tes idées.' },
  image:        { name: 'Prisma', accent: '#F472B6', hello: 'Je capture la lumière.' },
  code:         { name: 'Forge',  accent: '#22D3EE', hello: 'Du prompt au projet qui tourne.' },
  video:        { name: 'Klap',   accent: '#F59E0B', hello: 'Silence… on tourne.' },
  drawing:      { name: 'Sumi',   accent: '#A3E635', hello: 'Ton geste devient une œuvre.' },
  '3d':         { name: 'Poly',   accent: '#60A5FA', hello: 'Je sculpte vertex par vertex.' },
  learning:     { name: 'Sage',   accent: '#10B981', hello: 'Prêt à engranger de l\'XP ?' },
  cyber:        { name: 'Senti',  accent: '#F43F5E', hello: 'Périmètre sous contrôle.' },
  voice:        { name: 'Echo',   accent: '#2DD4BF', hello: 'Je t\'écoute déjà.' },
  cowork:       { name: 'Navi',   accent: '#6366F1', hello: 'Je navigue, tu supervises.' },
}

type MascotProps = {
  module: FxModule
  size?: number
  state?: 'idle' | 'working'
  className?: string
}

function shade(hex: string, f: number): string {
  const n = parseInt(hex.slice(1), 16)
  const r = Math.round(Math.min(255, Math.max(0, ((n >> 16) & 255) * f)))
  const g = Math.round(Math.min(255, Math.max(0, ((n >> 8) & 255) * f)))
  const b = Math.round(Math.min(255, Math.max(0, (n & 255) * f)))
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`
}

type CharacterCfg = {
  skin: string
  hairBase: string
  hairShade: string
  hairLight: string
  outfit: string
  outfitLight: string
  eyeColor: string
  lashes: boolean
  hairBack?: string
  hairFront: string
  hairHighlight?: string
}

const CHARS: Record<FxModule, CharacterCfg> = {
  conversation: {
    skin: '#F6D7BE', hairBase: '#6D4BC4', hairShade: '#4C2F96', hairLight: '#A78BFA',
    outfit: '#2A2352', outfitLight: '#4C3F94', eyeColor: '#8B5CF6', lashes: false,
    hairBack: 'M27 44 C24 26 34 13 50 12 C66 13 76 26 73 44 C74 52 72 58 70 61 L66 47 L61 58 L56 45 L50 57 L44 45 L39 58 L34 47 L30 61 C28 58 26 52 27 44 Z',
    hairFront: 'M31 37 C31 22 39 15 50 15 C62 15 69 23 69 36 C64 29 60 33 56 26 C52 33 47 27 43 33 C39 27 34 31 31 37 Z',
    hairHighlight: 'M38 20 C43 16 50 15 55 17 C50 18 43 20 40 25 Z',
  },
  image: {
    skin: '#FBE0C8', hairBase: '#F26FA8', hairShade: '#C74B85', hairLight: '#FFB1D4',
    outfit: '#7A2E56', outfitLight: '#B0507F', eyeColor: '#F472B6', lashes: true,
    hairBack: 'M26 46 C24 25 35 12 50 12 C65 12 76 25 74 46 C74 55 71 61 68 64 C70 55 69 48 67 44 L64 62 C62 65 60 66 58 67 L58 48 L42 48 L42 67 C38 66 34 63 32 58 C30 52 28 49 26 46 Z',
    hairFront: 'M30 38 C29 22 38 14 50 14 C63 14 70 24 70 36 C66 31 63 34 58 28 C50 36 42 28 38 34 C35 30 32 33 30 38 Z',
    hairHighlight: 'M36 20 C42 15 52 14 58 18 C51 18 42 20 38 26 Z',
  },
  code: {
    skin: '#EFC9A8', hairBase: '#233043', hairShade: '#141C2A', hairLight: '#22D3EE',
    outfit: '#10202B', outfitLight: '#1E3A4A', eyeColor: '#22D3EE', lashes: false,
    hairBack: 'M28 43 C26 26 36 13 50 12 C64 13 74 26 72 43 L67 36 L68 48 L62 40 L62 52 L50 42 L38 52 L38 40 L32 48 L33 36 Z',
    hairFront: 'M30 36 C31 22 39 15 50 15 C61 15 69 22 70 36 C65 27 61 33 55 25 C50 32 45 26 41 32 C37 26 33 30 30 36 Z',
    hairHighlight: 'M55 16 C60 18 65 23 67 29 C63 24 58 20 53 18 Z',
  },
  video: {
    skin: '#FAD9BB', hairBase: '#E88A1F', hairShade: '#B5610C', hairLight: '#FFC15E',
    outfit: '#5A2E10', outfitLight: '#8A4B1D', eyeColor: '#F59E0B', lashes: true,
    hairBack: 'M25 47 C23 25 35 12 50 12 C65 12 77 25 75 47 C77 57 74 64 70 68 C72 60 71 53 68 48 C69 58 66 65 62 69 C64 61 63 53 60 48 L58 68 C54 70 46 70 42 68 L40 48 C37 53 36 61 38 69 C34 65 31 58 33 48 C30 53 29 60 31 68 C27 64 24 57 25 47 Z',
    hairFront: 'M29 39 C28 22 38 14 50 14 C62 14 71 23 71 38 C67 31 63 35 58 27 C52 35 46 28 41 34 C37 29 32 33 29 39 Z',
    hairHighlight: 'M37 19 C43 14 53 14 59 18 C52 17 43 19 39 24 Z',
  },
  drawing: {
    skin: '#F2CEA9', hairBase: '#1F2418', hairShade: '#11140C', hairLight: '#A3E635',
    outfit: '#26301C', outfitLight: '#3E4E2E', eyeColor: '#A3E635', lashes: false,
    hairBack: 'M29 42 C27 25 37 13 50 12 C63 13 73 25 71 42 C72 48 71 53 69 56 L66 44 L62 55 L58 44 L50 54 L42 44 L38 55 L34 44 L31 56 C29 53 28 48 29 42 Z',
    hairFront: 'M31 36 C32 22 40 15 50 15 C60 15 68 22 69 36 C64 29 59 32 54 26 C49 32 44 27 40 32 C36 28 33 31 31 36 Z',
    hairHighlight: 'M42 17 C47 15 54 15 58 17 C53 17 46 18 43 21 Z',
  },
  '3d': {
    skin: '#EFD3B6', hairBase: '#4F7FD9', hairShade: '#31599F', hairLight: '#9EC5FF',
    outfit: '#1D2B4A', outfitLight: '#33487A', eyeColor: '#60A5FA', lashes: false,
    hairBack: 'M28 44 L30 24 L40 14 L50 12 L60 14 L70 24 L72 44 L66 38 L66 50 L58 42 L58 54 L50 46 L42 54 L42 42 L34 50 L34 38 Z',
    hairFront: 'M31 37 L34 21 L44 15 L50 15 L56 15 L66 21 L69 37 L61 28 L56 33 L50 25 L44 33 L39 28 Z',
    hairHighlight: 'M44 16 L50 15 L56 16 L50 20 Z',
  },
  learning: {
    skin: '#F8DCC4', hairBase: '#1E8A66', hairShade: '#116247', hairLight: '#6EE7B7',
    outfit: '#123B2E', outfitLight: '#1F5C48', eyeColor: '#10B981', lashes: true,
    hairBack: 'M27 45 C25 25 36 12 50 12 C64 12 75 25 73 45 C74 56 71 63 67 67 L64 50 C65 59 63 65 59 69 L56 50 L44 50 L41 69 C37 65 35 59 36 50 L33 67 C29 63 26 56 27 45 Z',
    hairFront: 'M30 38 C29 22 39 14 50 14 C61 14 71 22 70 38 C66 30 62 34 57 27 C51 34 45 28 41 33 C37 29 33 32 30 38 Z',
    hairHighlight: 'M37 19 C43 15 52 14 57 17 C50 17 42 19 39 24 Z',
  },
  cyber: {
    skin: '#E8C4A6', hairBase: '#2A1220', hairShade: '#180A12', hairLight: '#F43F5E',
    outfit: '#1A0F1A', outfitLight: '#331B2E', eyeColor: '#F43F5E', lashes: false,
    hairFront: 'M33 38 C33 26 40 18 50 18 C60 18 67 26 67 38 C63 32 59 35 55 29 C50 35 45 30 41 34 C38 31 35 34 33 38 Z',
    hairHighlight: 'M44 20 C48 18 54 19 57 22 C52 21 47 21 45 24 Z',
  },
  voice: {
    skin: '#F9DDC2', hairBase: '#2AA79A', hairShade: '#1B7A70', hairLight: '#7DF0E2',
    outfit: '#0F3B38', outfitLight: '#1D5F5A', eyeColor: '#2DD4BF', lashes: true,
    hairBack: 'M26 46 C24 25 35 12 50 12 C65 12 76 25 74 46 C76 58 72 66 67 70 C69 62 68 55 65 50 C67 60 64 68 59 72 L57 52 L43 52 L41 72 C36 68 33 60 35 50 C32 55 31 62 33 70 C28 66 24 58 26 46 Z',
    hairFront: 'M30 38 C29 22 38 14 50 14 C62 14 71 23 70 38 C66 30 61 34 56 27 C50 34 44 28 40 33 C36 29 32 33 30 38 Z',
    hairHighlight: 'M36 19 C43 14 53 14 59 18 C51 17 42 19 38 24 Z',
  },
  cowork: {
    skin: '#F1CFAE', hairBase: '#3F3FA8', hairShade: '#2A2A78', hairLight: '#8E8EF0',
    outfit: '#1E1E46', outfitLight: '#39397A', eyeColor: '#6366F1', lashes: false,
    hairBack: 'M28 43 C26 26 36 13 50 12 C64 13 74 26 72 43 C73 49 72 53 70 56 L66 45 L61 55 L55 44 L50 55 L45 44 L39 55 L34 45 L30 56 C28 53 27 49 28 43 Z',
    hairFront: 'M31 36 C31 22 40 15 50 15 C60 15 69 22 69 36 C64 28 60 33 55 26 C50 32 45 27 41 32 C37 28 33 31 31 36 Z',
    hairHighlight: 'M40 18 C45 15 52 15 56 17 C51 17 44 18 42 22 Z',
  },
}

export default function AuroraMascot({ module, size = 46, state = 'idle', className }: MascotProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const agent = FX_AGENTS[module]
  const c = CHARS[module]
  const a = agent.accent
  const working = state === 'working'
  const auraId = `au${uid}`
  const irisId = `ir${uid}`
  const skinId = `sk${uid}`
  const outfitId = `of${uid}`
  const hairId = `hr${uid}`

  const blinkAnim = !working && (
    <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;0.44;0.5;0.56;1" dur="4.2s" repeatCount="indefinite" />
  )
  const gaze = (
    <animateTransform attributeName="transform" type="translate" values="0 0;1.1 -0.4;0 0;-1 0.3;0 0" keyTimes="0;0.25;0.5;0.75;1" dur="8s" repeatCount="indefinite" />
  )

  const eye = (cx: number) => (
    <g>
      <path
        d={`M${cx - 6} 45.5 Q${cx} ${working ? 42.5 : 40.5} ${cx + 6} 45.5 Q${cx} ${working ? 49.5 : 50.5} ${cx - 6} 45.5 Z`}
        fill="#FFFFFF"
      />
      <g>
        {gaze}
        <circle cx={cx} cy={45.5} r={working ? 3.1 : 3.6} fill={`url(#${irisId})`} />
        <circle cx={cx} cy={45.5} r={working ? 1.3 : 1.6} fill="#0A0F1E" />
        <circle cx={cx - 1.2} cy={44.2} r="1.1" fill="#FFFFFF" />
        <circle cx={cx + 1.4} cy={46.6} r="0.55" fill="#FFFFFF" opacity="0.8" />
      </g>
      <path
        d={`M${cx - 6.4} 45 Q${cx} ${working ? 41.5 : 39.5} ${cx + 6.4} 45`}
        stroke={c.hairShade}
        strokeWidth={c.lashes ? 2.1 : 1.5}
        fill="none"
        strokeLinecap="round"
      />
      {c.lashes && (
        <path d={`M${cx + 5.2} 42.4 L${cx + 7.4} 40.8 M${cx + 6} 43.8 L${cx + 8.4} 42.8`} stroke={c.hairShade} strokeWidth="1" strokeLinecap="round" />
      )}
      <ellipse cx={cx} cy={42.6} rx="6.4" ry="2.6" fill={c.skin} opacity="0">
        {blinkAnim}
      </ellipse>
    </g>
  )

  const brow = (cx: number, flip: boolean) => (
    <path
      d={working
        ? `M${cx - 5} ${flip ? 37.5 : 35.5} Q${cx} ${flip ? 34.5 : 36.5} ${cx + 5} ${flip ? 35.5 : 37.5}`
        : `M${cx - 5} 36.5 Q${cx} 34.2 ${cx + 5} 36.5`}
      stroke={c.hairShade}
      strokeWidth="1.7"
      fill="none"
      strokeLinecap="round"
    />
  )

  let accessory: ReactElement | null = null
  let auraFx: ReactElement | null = null
  switch (module) {
    case 'conversation':
      accessory = (
        <g>
          <path d="M20 64 Q34 58 50 62 Q66 58 80 64 L78 70 Q64 65 50 68 Q36 65 22 70 Z" fill={a} opacity="0.85" />
          <text x="30" y="68" fontSize="4.5" fill="#FFF" opacity="0.9" fontFamily="Georgia, serif">✦</text>
          <text x="66" y="68" fontSize="4.5" fill="#FFF" opacity="0.9" fontFamily="Georgia, serif">✦</text>
        </g>
      )
      auraFx = (
        <g fill={shade(a, 1.4)} fontFamily="Georgia, serif" opacity="0.8">
          <text x="16" y="34" fontSize="7">
            ✧<animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="3.2s" repeatCount="indefinite" />
          </text>
          <text x="79" y="42" fontSize="6">
            ✧<animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="2.6s" repeatCount="indefinite" />
          </text>
        </g>
      )
      break
    case 'image':
      accessory = (
        <g>
          <path d="M28 24 C30 14 44 10 56 13 C64 15 68 20 66 24 C60 19 48 17 40 20 C34 22 30 23 28 24 Z" fill={shade(a, 0.75)} />
          <ellipse cx="31" cy="24" rx="5" ry="3.4" fill={shade(a, 0.75)} transform="rotate(-18 31 24)" />
          <circle cx="26.5" cy="22" r="2.6" fill={shade(a, 1.15)} stroke="rgba(255,255,255,.5)" strokeWidth="0.6" />
          <g transform="rotate(24 72 40)">
            <rect x="70.6" y="30" width="2.8" height="16" rx="1.4" fill="#8A5A34" />
            <path d="M70.6 30 L73.4 30 L72 24.5 Z" fill={a}>
              {working && <animate attributeName="fill" values={`${a};#FDE047;#22D3EE;${a}`} dur="1.6s" repeatCount="indefinite" />}
            </path>
          </g>
        </g>
      )
      break
    case 'code':
      accessory = (
        <g>
          <path d="M31 30 L69 30 L67 24 L33 24 Z" fill="#101826" stroke={a} strokeWidth="1" />
          <rect x="36" y="25" width="12" height="4" rx="2" fill={a} opacity="0.85">
            {working && <animate attributeName="opacity" values="0.85;0.3;0.85" dur="0.9s" repeatCount="indefinite" />}
          </rect>
          <rect x="52" y="25" width="12" height="4" rx="2" fill={a} opacity="0.85">
            {working && <animate attributeName="opacity" values="0.3;0.85;0.3" dur="0.9s" repeatCount="indefinite" />}
          </rect>
        </g>
      )
      auraFx = working ? (
        <g fill={shade(a, 1.4)}>
          <rect x="18" y="52" width="2" height="2">
            <animate attributeName="y" values="52;40;52" dur="1.4s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;1;0" dur="1.4s" repeatCount="indefinite" />
          </rect>
          <rect x="80" y="58" width="2" height="2">
            <animate attributeName="y" values="58;44;58" dur="1.8s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;1;0" dur="1.8s" repeatCount="indefinite" />
          </rect>
        </g>
      ) : null
      break
    case 'video':
      accessory = (
        <g>
          <g transform="rotate(-14 30 22)">
            <rect x="22" y="18" width="17" height="4.5" rx="1.4" fill={shade(a, 1.15)} />
            <path d="M24 18 l2.6 4.5 M29 18 l2.6 4.5 M34 18 l2.6 4.5" stroke="#3A2408" strokeWidth="1.6" />
            <rect x="22" y="22.5" width="18" height="6" rx="1.4" fill="#241505" stroke={a} strokeWidth="1" />
            {working && (
              <animateTransform attributeName="transform" type="rotate" values="-14 30 22;-22 30 22;-14 30 22" dur="0.8s" repeatCount="indefinite" />
            )}
          </g>
          <path d="M40 33 C44 30 56 30 60 33" stroke={shade(a, 0.7)} strokeWidth="2.4" fill="none" strokeLinecap="round" />
        </g>
      )
      break
    case 'drawing':
      accessory = (
        <g>
          <circle cx="66" cy="22" r="5" fill={c.hairBase} />
          <g transform="rotate(38 66 22)">
            <rect x="64.9" y="8" width="2.2" height="18" rx="1.1" fill="#7A5230" />
            <path d="M64.9 8 L67.1 8 L66 3.5 Z" fill={a} />
          </g>
          <path d="M20 70 Q26 66 30 70" stroke={a} strokeWidth="1.6" fill="none" strokeLinecap="round" opacity="0.8">
            {working && <animate attributeName="opacity" values="0.8;0.2;0.8" dur="1.4s" repeatCount="indefinite" />}
          </path>
        </g>
      )
      break
    case '3d':
      auraFx = (
        <g stroke={shade(a, 1.25)} strokeWidth="1.1" fill={`${a}33`}>
          <path d="M17 38 l5 -3 5 3 0 6 -5 3 -5 -3 Z">
            <animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="3.4s" repeatCount="indefinite" />
          </path>
          <path d="M76 50 l4 -2.4 4 2.4 0 4.8 -4 2.4 -4 -2.4 Z">
            <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="2.7s" repeatCount="indefinite" />
          </path>
        </g>
      )
      break
    case 'learning':
      accessory = (
        <g>
          <circle cx="35" cy="45.5" r="8.2" fill="none" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <circle cx="61" cy="45.5" r="8.2" fill="none" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <path d="M43.2 45.5 L52.8 45.5" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <path d="M46 16 L50 12 L54 16 L50 20 Z" fill="#FDE047">
            <animate attributeName="opacity" values="1;0.5;1" dur="2.4s" repeatCount="indefinite" />
          </path>
        </g>
      )
      break
    case 'cyber':
      accessory = (
        <g>
          <path d="M24 46 C22 22 34 10 50 10 C66 10 78 22 76 46 C77 58 74 66 69 70 L66 52 C68 42 66 32 60 27 C66 34 66 44 64 50 L36 50 C34 44 34 34 40 27 C34 32 32 42 34 52 L31 70 C26 66 23 58 24 46 Z" fill="#151021" stroke={shade(a, 0.8)} strokeWidth="1" />
          <path d="M33 44 L67 44 L65 50 L35 50 Z" fill={`${a}44`} stroke={a} strokeWidth="0.9">
            <animate attributeName="opacity" values="1;0.55;1" dur="2s" repeatCount="indefinite" />
          </path>
          <rect x="38" y="46" width="8" height="1.6" fill={shade(a, 1.4)}>
            <animate attributeName="x" values="38;54;38" dur="2.2s" repeatCount="indefinite" />
          </rect>
        </g>
      )
      break
    case 'voice':
      accessory = (
        <g>
          <path d="M27 36 Q23 16 44 13 M73 36 Q77 16 56 13" stroke={shade(a, 0.85)} strokeWidth="3.6" fill="none" strokeLinecap="round" />
          <rect x="20.5" y="34" width="9" height="14" rx="4.5" fill={shade(a, 0.85)} stroke={shade(a, 1.3)} strokeWidth="0.8" />
          <rect x="70.5" y="34" width="9" height="14" rx="4.5" fill={shade(a, 0.85)} stroke={shade(a, 1.3)} strokeWidth="0.8" />
          <path d="M27 48 Q30 58 40 60" stroke={shade(a, 0.85)} strokeWidth="2" fill="none" />
          <circle cx="42" cy="60.5" r="2.6" fill="#101826" stroke={a} strokeWidth="1" />
          {working && (
            <g stroke={a} strokeWidth="1.3" strokeLinecap="round" fill="none">
              <path d="M12 38 v6 M15.5 35 v12 M84.5 35 v12 M88 38 v6">
                <animate attributeName="opacity" values="0.9;0.25;0.9" dur="0.8s" repeatCount="indefinite" />
              </path>
            </g>
          )}
        </g>
      )
      break
    case 'cowork':
      accessory = (
        <g>
          <circle cx="68" cy="45.5" r="8.6" fill="none" stroke="#C9A76B" strokeWidth="1.8" />
          <path d="M74.5 51.5 L80 58" stroke="#C9A76B" strokeWidth="2.2" strokeLinecap="round" />
          <path d="M50 66 L47 74 L50 72 L53 74 Z" fill={shade(a, 1.2)} />
        </g>
      )
      break
  }

  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={className} aria-hidden="true">
      <defs>
        <radialGradient id={auraId} cx="0.5" cy="0.45">
          <stop offset="0" stopColor={a} stopOpacity={working ? 0.5 : 0.32} />
          <stop offset="0.7" stopColor={a} stopOpacity={working ? 0.16 : 0.08} />
          <stop offset="1" stopColor={a} stopOpacity="0" />
        </radialGradient>
        <radialGradient id={irisId} cx="0.4" cy="0.32">
          <stop offset="0" stopColor={shade(c.eyeColor, 1.65)} />
          <stop offset="0.55" stopColor={c.eyeColor} />
          <stop offset="1" stopColor={shade(c.eyeColor, 0.4)} />
        </radialGradient>
        <linearGradient id={skinId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={shade(c.skin, 1.05)} />
          <stop offset="1" stopColor={shade(c.skin, 0.9)} />
        </linearGradient>
        <linearGradient id={outfitId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={c.outfitLight} />
          <stop offset="1" stopColor={c.outfit} />
        </linearGradient>
        <linearGradient id={hairId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={shade(c.hairBase, 1.12)} />
          <stop offset="1" stopColor={c.hairShade} />
        </linearGradient>
      </defs>

      <circle cx="50" cy="46" r="42" fill={`url(#${auraId})`}>
        <animate attributeName="r" values="42;44;42" dur={working ? '1.6s' : '3.4s'} repeatCount="indefinite" />
      </circle>
      <circle cx="50" cy="46" r="35" fill="none" stroke={a} strokeOpacity={working ? 0.45 : 0.22} strokeWidth="1" strokeDasharray="3 7">
        <animateTransform attributeName="transform" type="rotate" values="0 50 46;360 50 46" dur="24s" repeatCount="indefinite" />
      </circle>
      {auraFx}

      <ellipse cx="50" cy="93" rx="24" ry="4.5" fill="#000" opacity="0.3" />

      <g>
        <animateTransform attributeName="transform" type="translate" values="0 0;0 -1.8;0 0" dur="3.6s" repeatCount="indefinite" />

        <path d="M26 92 C27 78 36 71 50 71 C64 71 73 78 74 92 Z" fill={`url(#${outfitId})`} stroke="rgba(255,255,255,.14)" strokeWidth="0.8" />
        <path d="M42 72 L50 80 L58 72 L54 71 L50 75 L46 71 Z" fill={shade(c.outfit, 1.6)} />
        <path d="M27 90 C29 80 34 75 40 73 L38 92 L27 92 Z" fill="rgba(255,255,255,.05)" />

        <path d="M45 62 L55 62 L55 72 C52 74.5 48 74.5 45 72 Z" fill={`url(#${skinId})`} />
        <path d="M45 62 L55 62 L55 66 C52 68 48 68 45 66 Z" fill={shade(c.skin, 0.82)} />

        {c.hairBack && <path d={c.hairBack} fill={`url(#${hairId})`} />}

        <path d="M33.5 44 C33.5 30 40 21 50 21 C60 21 66.5 30 66.5 44 C66.5 55 60 63.5 50 63.5 C40 63.5 33.5 55 33.5 44 Z" fill={`url(#${skinId})`} />
        <path d="M33 46 C31 46 30 48.5 31 50.5 C31.7 52 33 52.6 34.4 52.3 Z" fill={shade(c.skin, 0.95)} />
        <path d="M67 46 C69 46 70 48.5 69 50.5 C68.3 52 67 52.6 65.6 52.3 Z" fill={shade(c.skin, 0.95)} />

        {brow(35, false)}
        {brow(61, true)}
        {eye(35)}
        {eye(61)}

        <path d="M49 51.5 Q50 52.8 51 51.5" stroke={shade(c.skin, 0.68)} strokeWidth="1.1" fill="none" strokeLinecap="round" />
        {working
          ? <path d="M45.5 58.5 Q48 57.2 52 58.2" stroke={shade(c.skin, 0.5)} strokeWidth="1.7" fill="none" strokeLinecap="round" />
          : <path d="M45 57.5 Q48 60.5 52.5 57.8" stroke={shade(c.skin, 0.5)} strokeWidth="1.7" fill="none" strokeLinecap="round" />}
        <ellipse cx="38" cy="53.5" rx="3.4" ry="1.8" fill={a} opacity="0.18" />
        <ellipse cx="62" cy="53.5" rx="3.4" ry="1.8" fill={a} opacity="0.18" />

        <path d={c.hairFront} fill={`url(#${hairId})`} />
        {c.hairHighlight && <path d={c.hairHighlight} fill={c.hairLight} opacity="0.55" />}

        {accessory}
      </g>

      {working && (
        <g fill={shade(a, 1.4)}>
          <circle cx="14" cy="40" r="1.5">
            <animate attributeName="cy" values="40;28;40" dur="2.1s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.9;0" dur="2.1s" repeatCount="indefinite" />
          </circle>
          <circle cx="87" cy="50" r="1.3">
            <animate attributeName="cy" values="50;36;50" dur="2.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.8;0" dur="2.6s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
    </svg>
  )
}
