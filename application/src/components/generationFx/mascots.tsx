import { useId, type ReactElement } from 'react'
import type { FxModule } from './fxBus.ts'

export type { FxModule }

/**
 * Personnages des modules — un personnage propre à chaque module.
 *
 * Les noms reprennent les personas du document maître (Lyra, Iris, Glyph,
 * Cinéma, Sumi, Atlas, Sage, Phantom, Sovereign). Voix et Cowork, qui n'en
 * avaient pas de distincts, reçoivent Écho et Navi. Chaque personnage a sa
 * silhouette, sa palette, son accessoire tenu en main et son geste de travail.
 * L'état affiché suit l'état réel du chargement (file, préparation, travail,
 * vérification, question, succès, erreur) ; il ne simule aucun avancement.
 */
export const FX_AGENTS: Record<FxModule, { name: string; role: string; accent: string; hello: string }> = {
  conversation: { name: 'Lyra', role: 'Confidente', accent: '#8B5CF6', hello: 'Je t’écoute avant de répondre.' },
  image: { name: 'Iris', role: 'Coloriste', accent: '#F472B6', hello: 'La couleur naît du contraste.' },
  code: { name: 'Glyph', role: 'Architecte', accent: '#22D3EE', hello: 'Lisible avant rapide.' },
  video: { name: 'Cinéma', role: 'Réalisateur', accent: '#FB7A3C', hello: 'Silence… on tourne.' },
  drawing: { name: 'Sumi', role: 'Calligraphe', accent: '#A3E635', hello: 'Un trait. Pas deux.' },
  '3d': { name: 'Atlas', role: 'Constructeur', accent: '#60A5FA', hello: 'Je bâtis ce que tu imagines.' },
  learning: { name: 'Sage', role: 'Mentor', accent: '#10B981', hello: 'On apprend en pratiquant.' },
  cyber: { name: 'Phantom', role: 'Sentinelle', accent: '#F43F5E', hello: 'Comprendre avant d’attaquer.' },
  business: { name: 'Sovereign', role: 'Stratège', accent: '#EAB308', hello: 'Survivre d’abord, composer ensuite.' },
  voice: { name: 'Écho', role: 'Voix', accent: '#2DD4BF', hello: 'Je t’écoute déjà.' },
  cowork: { name: 'Navi', role: 'Navigatrice', accent: '#6366F1', hello: 'Je navigue, tu supervises.' },
}

export type MascotState = 'idle' | 'thinking' | 'working' | 'checking' | 'waiting' | 'asking' | 'success' | 'error'

export const MASCOT_STATE_LABEL: Record<MascotState, string> = {
  idle: 'disponible',
  thinking: 'réfléchit',
  working: 'travaille',
  checking: 'vérifie',
  waiting: 'attend son tour',
  asking: 'attend ta réponse',
  success: 'a terminé',
  error: 'a rencontré un problème',
}

type MascotProps = {
  module: FxModule
  size?: number
  state?: MascotState
  className?: string
  title?: string
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
  /** forme des yeux : ronds (doux), amande (vifs), étroits (concentrés) */
  eyes: 'round' | 'almond' | 'narrow'
}

const CHARS: Record<FxModule, CharacterCfg> = {
  conversation: {
    skin: '#F6D7BE', hairBase: '#6D4BC4', hairShade: '#4C2F96', hairLight: '#A78BFA',
    outfit: '#2A2352', outfitLight: '#4C3F94', eyeColor: '#8B5CF6', lashes: true, eyes: 'round',
    hairBack: 'M27 44 C24 26 34 13 50 12 C66 13 76 26 73 44 C74 52 72 58 70 61 L66 47 L61 58 L56 45 L50 57 L44 45 L39 58 L34 47 L30 61 C28 58 26 52 27 44 Z',
    hairFront: 'M31 37 C31 22 39 15 50 15 C62 15 69 23 69 36 C64 29 60 33 56 26 C52 33 47 27 43 33 C39 27 34 31 31 37 Z',
    hairHighlight: 'M38 20 C43 16 50 15 55 17 C50 18 43 20 40 25 Z',
  },
  image: {
    skin: '#FBE0C8', hairBase: '#F26FA8', hairShade: '#C74B85', hairLight: '#FFB1D4',
    outfit: '#7A2E56', outfitLight: '#B0507F', eyeColor: '#F472B6', lashes: true, eyes: 'almond',
    hairBack: 'M26 46 C24 25 35 12 50 12 C65 12 76 25 74 46 C74 55 71 61 68 64 C70 55 69 48 67 44 L64 62 C62 65 60 66 58 67 L58 48 L42 48 L42 67 C38 66 34 63 32 58 C30 52 28 49 26 46 Z',
    hairFront: 'M30 38 C29 22 38 14 50 14 C63 14 70 24 70 36 C66 31 63 34 58 28 C50 36 42 28 38 34 C35 30 32 33 30 38 Z',
    hairHighlight: 'M36 20 C42 15 52 14 58 18 C51 18 42 20 38 26 Z',
  },
  code: {
    skin: '#EFC9A8', hairBase: '#233043', hairShade: '#141C2A', hairLight: '#22D3EE',
    outfit: '#10202B', outfitLight: '#1E3A4A', eyeColor: '#22D3EE', lashes: false, eyes: 'narrow',
    hairBack: 'M28 43 C26 26 36 13 50 12 C64 13 74 26 72 43 L67 36 L68 48 L62 40 L62 52 L50 42 L38 52 L38 40 L32 48 L33 36 Z',
    hairFront: 'M30 36 C31 22 39 15 50 15 C61 15 69 22 70 36 C65 27 61 33 55 25 C50 32 45 26 41 32 C37 26 33 30 30 36 Z',
    hairHighlight: 'M55 16 C60 18 65 23 67 29 C63 24 58 20 53 18 Z',
  },
  video: {
    skin: '#FAD9BB', hairBase: '#B4531F', hairShade: '#7E3510', hairLight: '#FFA35E',
    outfit: '#3B1D0E', outfitLight: '#6A3518', eyeColor: '#FB7A3C', lashes: false, eyes: 'almond',
    hairBack: 'M28 44 C26 26 36 13 50 12 C64 13 74 26 72 44 C73 50 72 55 70 58 L66 46 L60 54 L55 44 L45 44 L40 54 L34 46 L30 58 C28 55 27 50 28 44 Z',
    hairFront: 'M29 39 C28 22 38 14 50 14 C62 14 71 23 71 38 C67 31 63 35 58 27 C52 35 46 28 41 34 C37 29 32 33 29 39 Z',
    hairHighlight: 'M37 19 C43 14 53 14 59 18 C52 17 43 19 39 24 Z',
  },
  drawing: {
    skin: '#F2CEA9', hairBase: '#1F2418', hairShade: '#11140C', hairLight: '#A3E635',
    outfit: '#26301C', outfitLight: '#3E4E2E', eyeColor: '#A3E635', lashes: true, eyes: 'narrow',
    hairBack: 'M29 42 C27 25 37 13 50 12 C63 13 73 25 71 42 C72 48 71 53 69 56 L66 44 L62 55 L58 44 L50 54 L42 44 L38 55 L34 44 L31 56 C29 53 28 48 29 42 Z',
    hairFront: 'M31 36 C32 22 40 15 50 15 C60 15 68 22 69 36 C64 29 59 32 54 26 C49 32 44 27 40 32 C36 28 33 31 31 36 Z',
    hairHighlight: 'M42 17 C47 15 54 15 58 17 C53 17 46 18 43 21 Z',
  },
  '3d': {
    skin: '#EFD3B6', hairBase: '#4F7FD9', hairShade: '#31599F', hairLight: '#9EC5FF',
    outfit: '#1D2B4A', outfitLight: '#33487A', eyeColor: '#60A5FA', lashes: false, eyes: 'round',
    hairBack: 'M28 44 L30 24 L40 14 L50 12 L60 14 L70 24 L72 44 L66 38 L66 50 L58 42 L58 54 L50 46 L42 54 L42 42 L34 50 L34 38 Z',
    hairFront: 'M31 37 L34 21 L44 15 L50 15 L56 15 L66 21 L69 37 L61 28 L56 33 L50 25 L44 33 L39 28 Z',
    hairHighlight: 'M44 16 L50 15 L56 16 L50 20 Z',
  },
  learning: {
    skin: '#F8DCC4', hairBase: '#1E8A66', hairShade: '#116247', hairLight: '#6EE7B7',
    outfit: '#123B2E', outfitLight: '#1F5C48', eyeColor: '#10B981', lashes: true, eyes: 'round',
    hairBack: 'M27 45 C25 25 36 12 50 12 C64 12 75 25 73 45 C74 56 71 63 67 67 L64 50 C65 59 63 65 59 69 L56 50 L44 50 L41 69 C37 65 35 59 36 50 L33 67 C29 63 26 56 27 45 Z',
    hairFront: 'M30 38 C29 22 39 14 50 14 C61 14 71 22 70 38 C66 30 62 34 57 27 C51 34 45 28 41 33 C37 29 33 32 30 38 Z',
    hairHighlight: 'M37 19 C43 15 52 14 57 17 C50 17 42 19 39 24 Z',
  },
  cyber: {
    skin: '#E8C4A6', hairBase: '#2A1220', hairShade: '#180A12', hairLight: '#F43F5E',
    outfit: '#1A0F1A', outfitLight: '#331B2E', eyeColor: '#F43F5E', lashes: false, eyes: 'narrow',
    hairFront: 'M33 38 C33 26 40 18 50 18 C60 18 67 26 67 38 C63 32 59 35 55 29 C50 35 45 30 41 34 C38 31 35 34 33 38 Z',
    hairHighlight: 'M44 20 C48 18 54 19 57 22 C52 21 47 21 45 24 Z',
  },
  voice: {
    skin: '#F9DDC2', hairBase: '#2AA79A', hairShade: '#1B7A70', hairLight: '#7DF0E2',
    outfit: '#0F3B38', outfitLight: '#1D5F5A', eyeColor: '#2DD4BF', lashes: true, eyes: 'almond',
    hairBack: 'M26 46 C24 25 35 12 50 12 C65 12 76 25 74 46 C76 58 72 66 67 70 C69 62 68 55 65 50 C67 60 64 68 59 72 L57 52 L43 52 L41 72 C36 68 33 60 35 50 C32 55 31 62 33 70 C28 66 24 58 26 46 Z',
    hairFront: 'M30 38 C29 22 38 14 50 14 C62 14 71 23 70 38 C66 30 61 34 56 27 C50 34 44 28 40 33 C36 29 32 33 30 38 Z',
    hairHighlight: 'M36 19 C43 14 53 14 59 18 C51 17 42 19 38 24 Z',
  },
  cowork: {
    skin: '#F1CFAE', hairBase: '#3F3FA8', hairShade: '#2A2A78', hairLight: '#8E8EF0',
    outfit: '#1E1E46', outfitLight: '#39397A', eyeColor: '#6366F1', lashes: true, eyes: 'round',
    hairBack: 'M28 43 C26 26 36 13 50 12 C64 13 74 26 72 43 C73 49 72 53 70 56 L66 45 L61 55 L55 44 L50 55 L45 44 L39 55 L34 45 L30 56 C28 53 27 49 28 43 Z',
    hairFront: 'M31 36 C31 22 40 15 50 15 C60 15 69 22 69 36 C64 28 60 33 55 26 C50 32 45 27 41 32 C37 28 33 31 31 36 Z',
    hairHighlight: 'M40 18 C45 15 52 15 56 17 C51 17 44 18 42 22 Z',
  },
  business: {
    skin: '#F5D6BA', hairBase: '#1F2937', hairShade: '#111827', hairLight: '#9CA3AF',
    outfit: '#14213D', outfitLight: '#22345E', eyeColor: '#EAB308', lashes: false, eyes: 'almond',
    hairBack: 'M29 42 C27 25 37 13 50 12 C63 13 73 25 71 42 L68 48 L66 38 L34 38 L32 48 Z',
    hairFront: 'M31 35 C32 22 40 15 50 15 C60 15 68 22 69 35 C63 27 56 25 47 26 C41 27 36 30 31 35 Z',
    hairHighlight: 'M41 18 C46 15 54 15 58 17 C52 17 45 18 42 22 Z',
  },
}

/** Accessoire tenu en main ; `act` = geste de travail en cours. */
function HeldProp({ module, a, act, uid }: { module: FxModule; a: string; act: boolean; uid: string }): ReactElement {
  const hi = shade(a, 1.35)
  switch (module) {
    case 'conversation':
      return (
        <g>
          <path d="M41 81 h18 a4 4 0 0 1 4 4 v6 a4 4 0 0 1 -4 4 h-10 l-5 4 v-4 h-3 a4 4 0 0 1 -4 -4 v-6 a4 4 0 0 1 4 -4 Z" fill="#14112B" stroke={a} strokeWidth="1.2" />
          {[45, 50, 55].map((x, i) => (
            <circle key={x} cx={x} cy="88" r="1.5" fill={hi}>
              {act && <animate attributeName="cy" values="88;85.5;88" dur="0.9s" begin={`${i * 0.15}s`} repeatCount="indefinite" />}
            </circle>
          ))}
        </g>
      )
    case 'image':
      return (
        <g>
          <path d="M37 89 C36 83 42 80 48 81 C54 82 56 86 53 88 C51 89 52 92 49 93 C43 95 38 93 37 89 Z" fill="#E8D8C8" stroke="#8A6A4A" strokeWidth="0.8" />
          <circle cx="42" cy="86" r="1.6" fill="#F43F5E" />
          <circle cx="46" cy="84.5" r="1.6" fill="#FDE047" />
          <circle cx="50" cy="85.5" r="1.6" fill="#22D3EE" />
          <circle cx="44" cy="90" r="1.6" fill={a} />
          <g>
            {act && <animateTransform attributeName="transform" type="rotate" values="-8 60 92;14 60 92;-8 60 92" dur="1.1s" repeatCount="indefinite" />}
            <rect x="58.8" y="76" width="2.4" height="16" rx="1.2" fill="#8A5A34" transform="rotate(18 60 92)" />
            <path d="M56.7 76.6 L59.6 75.7 L58.2 71.5 Z" fill={a} transform="rotate(18 60 92)">
              {act && <animate attributeName="fill" values={`${a};#FDE047;#22D3EE;${a}`} dur="1.6s" repeatCount="indefinite" />}
            </path>
          </g>
        </g>
      )
    case 'code':
      return (
        <g>
          <path d="M36 84 L64 84 L67 94 L33 94 Z" fill="#0B1620" stroke={a} strokeWidth="1" />
          {[0, 1, 2].map((row) => (
            <g key={row}>
              {[0, 1, 2, 3, 4, 5].map((k) => (
                <rect key={k} x={37.5 + k * 4.4 + row * 0.6} y={86 + row * 2.6} width="3.4" height="1.7" rx="0.5" fill={a} opacity="0.35">
                  {act && <animate attributeName="opacity" values="0.3;0.95;0.3" dur={`${0.5 + ((k * 7 + row * 3) % 5) * 0.12}s`} begin={`${((k + row) % 4) * 0.13}s`} repeatCount="indefinite" />}
                </rect>
              ))}
            </g>
          ))}
          {act && (
            <text x="50" y="80" textAnchor="middle" fontSize="6" fill={hi} fontFamily="Consolas, monospace">
              {'</>'}
              <animate attributeName="y" values="81;72;81" dur="1.6s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0;1;0" dur="1.6s" repeatCount="indefinite" />
            </text>
          )}
        </g>
      )
    case 'video':
      return (
        <g>
          <rect x="39" y="85" width="22" height="10" rx="1.5" fill="#1B1208" stroke={a} strokeWidth="1" />
          <path d="M42 85 l3 10 M48 85 l3 10 M54 85 l3 10" stroke="#3A2408" strokeWidth="1.2" />
          <g>
            {act && <animateTransform attributeName="transform" type="rotate" values="0 39 85;-22 39 85;0 39 85" keyTimes="0;0.25;0.35" dur="1.4s" repeatCount="indefinite" />}
            <rect x="39" y="81" width="22" height="4" rx="1" fill={shade(a, 1.1)} />
            <path d="M42 81 l2.6 4 M47.5 81 l2.6 4 M53 81 l2.6 4" stroke="#2B1A08" strokeWidth="1.6" />
          </g>
          {act && (
            <circle cx="64" cy="80" r="1.6" fill="#EF4444">
              <animate attributeName="opacity" values="1;0.15;1" dur="1s" repeatCount="indefinite" />
            </circle>
          )}
        </g>
      )
    case 'drawing':
      return (
        <g>
          <path d="M33 93 Q42 88 50 92 T67 90" stroke={a} strokeWidth="1.8" fill="none" strokeLinecap="round" strokeDasharray="40" strokeDashoffset={act ? undefined : 0}>
            {act && <animate attributeName="stroke-dashoffset" values="40;0;0;40" keyTimes="0;0.6;0.85;1" dur="2.2s" repeatCount="indefinite" />}
          </path>
          <g>
            {act && <animateTransform attributeName="transform" type="translate" values="-14 2;8 -1;-14 2" dur="2.2s" repeatCount="indefinite" />}
            <rect x="56.8" y="72" width="2.4" height="15" rx="1.2" fill="#7A5230" transform="rotate(24 58 86)" />
            <path d="M56.4 86.5 Q58 92 59.8 86.5 Z" fill="#11140C" transform="rotate(24 58 86)" />
          </g>
        </g>
      )
    case '3d':
      return (
        <g>
          <g>
            {act && <animateTransform attributeName="transform" type="rotate" values="0 50 86;360 50 86" dur="6s" repeatCount="indefinite" />}
            <path d="M50 78 L58 82.5 L58 91.5 L50 96 L42 91.5 L42 82.5 Z" fill={`${a}22`} stroke={a} strokeWidth="1.1" />
            <path d="M42 82.5 L50 87 L58 82.5 M50 87 L50 96" stroke={hi} strokeWidth="0.9" fill="none" />
          </g>
          <ellipse cx="50" cy="97" rx="10" ry="1.6" fill={a} opacity="0.35">
            {act && <animate attributeName="opacity" values="0.15;0.5;0.15" dur="1.4s" repeatCount="indefinite" />}
          </ellipse>
        </g>
      )
    case 'learning':
      return (
        <g>
          <path d="M50 84 C44 81 38 81 34 83 L34 94 C38 92 44 92 50 95 Z" fill="#F1F5F9" stroke="#475569" strokeWidth="0.8" />
          <path d="M50 84 C56 81 62 81 66 83 L66 94 C62 92 56 92 50 95 Z" fill="#E2E8F0" stroke="#475569" strokeWidth="0.8" />
          <path d="M37 86 h9 M37 88.5 h8 M54 86 h9 M54 88.5 h7" stroke="#94A3B8" strokeWidth="0.7" />
          {act && (
            <path d="M50 84 C56 81 62 81 66 83 L66 94 C62 92 56 92 50 95 Z" fill="#FFFFFF" stroke="#475569" strokeWidth="0.6" opacity="0.9">
              {/* translation puis symétrie : la page tourne autour de la reliure (x = 50) */}
              <animateTransform attributeName="transform" type="translate" values="0 0;100 0;100 0" keyTimes="0;0.5;1" dur="1.8s" additive="sum" repeatCount="indefinite" />
              <animateTransform attributeName="transform" type="scale" values="1 1;-1 1;-1 1" keyTimes="0;0.5;1" dur="1.8s" additive="sum" repeatCount="indefinite" />
            </path>
          )}
        </g>
      )
    case 'cyber':
      return (
        <g>
          <path d="M50 79 L60 83 C60 90 56 94.5 50 97 C44 94.5 40 90 40 83 Z" fill="#170C16" stroke={a} strokeWidth="1.2" />
          <path d="M46 87 h8 v5 h-8 Z M47.5 87 v-2 a2.5 2.5 0 0 1 5 0 v2" fill="none" stroke={hi} strokeWidth="1" />
          {act && (
            <rect x="41" y="80" width="18" height="1.2" fill={hi} opacity="0.8">
              <animate attributeName="y" values="80;94;80" dur="1.6s" repeatCount="indefinite" />
            </rect>
          )}
        </g>
      )
    case 'business':
      return (
        <g>
          <rect x="38" y="81" width="24" height="15" rx="2" fill="#0D1526" stroke={a} strokeWidth="1" />
          {[0, 1, 2, 3].map((k) => (
            <rect key={k} x={41 + k * 5} y={93 - (3 + k * 2.2)} width="3.2" height={3 + k * 2.2} fill={k === 3 ? a : '#34D399'} opacity="0.9">
              {act && <animate attributeName="height" values={`1;${3 + k * 2.2};${3 + k * 2.2}`} keyTimes="0;0.6;1" dur="1.8s" begin={`${k * 0.12}s`} repeatCount="indefinite" />}
              {act && <animate attributeName="y" values={`92;${93 - (3 + k * 2.2)};${93 - (3 + k * 2.2)}`} keyTimes="0;0.6;1" dur="1.8s" begin={`${k * 0.12}s`} repeatCount="indefinite" />}
            </rect>
          ))}
          <path d="M47 71.5 L50 83 L53 71.5 L50 70 Z" fill={a} />
        </g>
      )
    case 'voice':
      return (
        <g>
          <rect x="47" y="80" width="6" height="10" rx="3" fill="#0F2E2B" stroke={a} strokeWidth="1" />
          <path d="M45 87 a5 5 0 0 0 10 0 M50 92 v4" stroke={hi} strokeWidth="1" fill="none" />
          {act && (
            <g stroke={a} strokeWidth="1.2" fill="none" strokeLinecap="round">
              <path d="M41 82 a10 10 0 0 0 0 9 M59 82 a10 10 0 0 1 0 9">
                <animate attributeName="opacity" values="0.9;0.2;0.9" dur="0.8s" repeatCount="indefinite" />
              </path>
              <path d="M37 80 a14 14 0 0 0 0 13 M63 80 a14 14 0 0 1 0 13">
                <animate attributeName="opacity" values="0.2;0.9;0.2" dur="0.8s" repeatCount="indefinite" />
              </path>
            </g>
          )}
        </g>
      )
    case 'cowork':
    default:
      return (
        <g>
          <circle cx="50" cy="88" r="8" fill="#12122E" stroke="#C9A76B" strokeWidth="1.2" />
          <path d="M50 81.5 L51.2 88 L50 94.5 L48.8 88 Z" fill={a}>
            {act && <animateTransform attributeName="transform" type="rotate" values="0 50 88;40 50 88;-25 50 88;0 50 88" dur="2.4s" repeatCount="indefinite" />}
          </path>
          <circle cx="50" cy="88" r="1.1" fill="#C9A76B" />
          <defs>
            <radialGradient id={`cmp${uid}`}><stop offset="0" stopColor={a} stopOpacity="0.35" /><stop offset="1" stopColor={a} stopOpacity="0" /></radialGradient>
          </defs>
          <circle cx="50" cy="88" r="11" fill={`url(#cmp${uid})`} />
        </g>
      )
  }
}

export default function AuroraMascot({ module, size = 46, state = 'idle', className, title }: MascotProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const agent = FX_AGENTS[module] ?? FX_AGENTS.conversation
  const c = CHARS[module] ?? CHARS.conversation
  const a = state === 'error' ? '#F87171' : agent.accent
  const busy = state === 'working' || state === 'checking'
  const auraId = `au${uid}`
  const irisId = `ir${uid}`
  const skinId = `sk${uid}`
  const outfitId = `of${uid}`
  const hairId = `hr${uid}`

  // regard : idle balaye doucement, thinking regarde en haut, checking scanne
  const gaze =
    state === 'thinking' ? (
      <animateTransform attributeName="transform" type="translate" values="1.2 -1.2;1.6 -1.4;1.2 -1.2" dur="2.4s" repeatCount="indefinite" />
    ) : state === 'checking' ? (
      <animateTransform attributeName="transform" type="translate" values="-1.6 0;1.6 0;-1.6 0" dur="1.6s" repeatCount="indefinite" />
    ) : state === 'idle' || state === 'waiting' ? (
      <animateTransform attributeName="transform" type="translate" values="0 0;1.1 -0.4;0 0;-1 0.3;0 0" keyTimes="0;0.25;0.5;0.75;1" dur="8s" repeatCount="indefinite" />
    ) : null
  const blink = state !== 'success' && (
    <animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;0.44;0.5;0.56;1" dur={state === 'waiting' ? '3s' : '4.4s'} repeatCount="indefinite" />
  )

  const eyeOpen = c.eyes === 'narrow' || busy ? 3.2 : c.eyes === 'almond' ? 4 : 4.8
  const eye = (cx: number) => {
    if (state === 'success') {
      return <path d={`M${cx - 5} 46.5 Q${cx} 41.5 ${cx + 5} 46.5`} stroke={c.hairShade} strokeWidth="1.9" fill="none" strokeLinecap="round" />
    }
    const top = 45.5 - eyeOpen
    const bot = 45.5 + eyeOpen * (c.eyes === 'almond' ? 0.8 : 1)
    return (
      <g>
        <path d={`M${cx - 6} 45.5 Q${cx} ${top} ${cx + 6} 45.5 Q${cx} ${bot} ${cx - 6} 45.5 Z`} fill="#FFFFFF" />
        <g>
          {gaze}
          <circle cx={cx} cy={45.5} r={busy ? 3 : 3.5} fill={`url(#${irisId})`} />
          <circle cx={cx} cy={45.5} r={busy ? 1.3 : 1.6} fill="#0A0F1E" />
          <circle cx={cx - 1.2} cy={44.2} r="1.05" fill="#FFFFFF" />
          <circle cx={cx + 1.4} cy={46.6} r="0.5" fill="#FFFFFF" opacity="0.8" />
        </g>
        <path d={`M${cx - 6.4} 45 Q${cx} ${top - 0.6} ${cx + 6.4} 45`} stroke={c.hairShade} strokeWidth={c.lashes ? 2.1 : 1.5} fill="none" strokeLinecap="round" />
        {c.lashes && <path d={`M${cx + 5.2} 42.4 L${cx + 7.4} 40.8 M${cx + 6} 43.8 L${cx + 8.4} 42.8`} stroke={c.hairShade} strokeWidth="1" strokeLinecap="round" />}
        {state === 'waiting' && <path d={`M${cx - 6.4} 44.6 Q${cx} ${top + 1.6} ${cx + 6.4} 44.6 L${cx + 6.4} 43 L${cx - 6.4} 43 Z`} fill={c.skin} />}
        <ellipse cx={cx} cy={42.6} rx="6.5" ry="2.8" fill={c.skin} opacity="0">{blink}</ellipse>
      </g>
    )
  }

  const brow = (cx: number, right: boolean) => {
    let d = `M${cx - 5} 36.5 Q${cx} 34.2 ${cx + 5} 36.5`
    if (busy) d = right ? `M${cx - 5} 37.4 Q${cx} 35 ${cx + 5} 35.6` : `M${cx - 5} 35.6 Q${cx} 35 ${cx + 5} 37.4`
    if (state === 'thinking' || (state === 'asking' && right)) d = `M${cx - 5} 35 Q${cx} 31.8 ${cx + 5} 34.6`
    if (state === 'error') d = right ? `M${cx - 5} 35.2 Q${cx} 35.8 ${cx + 5} 37.6` : `M${cx - 5} 37.6 Q${cx} 35.8 ${cx + 5} 35.2`
    return <path d={d} stroke={c.hairShade} strokeWidth="1.7" fill="none" strokeLinecap="round" />
  }

  const mouth = (() => {
    const lip = shade(c.skin, 0.5)
    switch (state) {
      case 'success':
        return <path d="M44.5 56.6 Q48.5 62.4 53 56.8 Z" fill="#7A2E2E" stroke={lip} strokeWidth="1" />
      case 'error':
        return <path d="M45 59 Q47 57.2 48.8 58.6 Q50.6 60 52.6 58.2" stroke={lip} strokeWidth="1.5" fill="none" strokeLinecap="round" />
      case 'thinking':
      case 'asking':
        return <path d="M46.5 58.4 Q49 57.4 51.5 58.4" stroke={lip} strokeWidth="1.6" fill="none" strokeLinecap="round" />
      case 'working':
      case 'checking':
        return <path d="M45.5 58.5 Q48 57.2 52 58.2" stroke={lip} strokeWidth="1.7" fill="none" strokeLinecap="round" />
      case 'waiting':
        return <path d="M46 58 Q48.5 59.4 51.5 58" stroke={lip} strokeWidth="1.5" fill="none" strokeLinecap="round" />
      default:
        return <path d="M45 57.5 Q48 60.5 52.5 57.8" stroke={lip} strokeWidth="1.7" fill="none" strokeLinecap="round" />
    }
  })()

  // couvre-chefs et attributs de tête propres à chaque personnage
  let headwear: ReactElement | null = null
  switch (module) {
    case 'conversation':
      headwear = (
        <g>
          <path d="M60 22 l2.4 -4.6 2.4 4.6 -2.4 1.6 Z" fill={shade(a, 1.3)} />
          <circle cx="62.4" cy="21.4" r="1" fill="#FFF" opacity="0.9" />
        </g>
      )
      break
    case 'image':
      headwear = (
        <g>
          <path d="M28 24 C30 14 44 10 56 13 C64 15 68 20 66 24 C60 19 48 17 40 20 C34 22 30 23 28 24 Z" fill={shade(a, 0.75)} />
          <ellipse cx="31" cy="24" rx="5" ry="3.4" fill={shade(a, 0.75)} transform="rotate(-18 31 24)" />
          <circle cx="26.5" cy="22" r="2.6" fill={shade(a, 1.15)} stroke="rgba(255,255,255,.5)" strokeWidth="0.6" />
        </g>
      )
      break
    case 'code':
      headwear = (
        <g>
          <path d="M31 30 L69 30 L67 24 L33 24 Z" fill="#101826" stroke={a} strokeWidth="1" />
          <rect x="36" y="25" width="12" height="4" rx="2" fill={a} opacity="0.85">
            {busy && <animate attributeName="opacity" values="0.85;0.3;0.85" dur="0.9s" repeatCount="indefinite" />}
          </rect>
          <rect x="52" y="25" width="12" height="4" rx="2" fill={a} opacity="0.85">
            {busy && <animate attributeName="opacity" values="0.3;0.85;0.3" dur="0.9s" repeatCount="indefinite" />}
          </rect>
        </g>
      )
      break
    case 'video':
      headwear = (
        <g>
          <path d="M30 26 C32 16 42 12 52 13 C62 14 69 19 70 26 Z" fill="#2A1A10" />
          <path d="M66 26 C72 26 77 27 79 29 C74 30 69 29 66 28 Z" fill="#2A1A10" />
          <rect x="44" y="18" width="10" height="3" rx="1" fill={a} />
        </g>
      )
      break
    case 'drawing':
      headwear = (
        <g>
          <circle cx="66" cy="20" r="5.2" fill={c.hairBase} />
          <rect x="64.8" y="6" width="2.2" height="18" rx="1.1" fill="#7A5230" transform="rotate(38 66 20)" />
          <path d="M64.8 6 L67 6 L66 1.5 Z" fill={a} transform="rotate(38 66 20)" />
        </g>
      )
      break
    case '3d':
      headwear = (
        <g>
          <path d="M33 31 L67 31" stroke={shade(a, 1.1)} strokeWidth="2.2" strokeLinecap="round" />
          <rect x="45" y="27.5" width="10" height="5.5" rx="1.4" fill="#0E1A30" stroke={a} strokeWidth="0.9" />
          <circle cx="50" cy="30.2" r="1.5" fill={shade(a, 1.4)}>
            {busy && <animate attributeName="opacity" values="1;0.35;1" dur="1.2s" repeatCount="indefinite" />}
          </circle>
        </g>
      )
      break
    case 'learning':
      headwear = (
        <g>
          <circle cx="35" cy="45.5" r="8.2" fill="none" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <circle cx="61" cy="45.5" r="8.2" fill="none" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <path d="M43.2 45.5 L52.8 45.5" stroke={shade(a, 1.2)} strokeWidth="1.4" opacity="0.9" />
          <path d="M33 41 L37 39.5" stroke="#FFF" strokeWidth="1" opacity="0.7">
            {busy && <animate attributeName="opacity" values="0;0.9;0" dur="2.2s" repeatCount="indefinite" />}
          </path>
        </g>
      )
      break
    case 'cyber':
      headwear = (
        <g>
          <path d="M24 46 C22 22 34 10 50 10 C66 10 78 22 76 46 C77 58 74 66 69 70 L66 52 C68 42 66 32 60 27 C66 34 66 44 64 50 L36 50 C34 44 34 34 40 27 C34 32 32 42 34 52 L31 70 C26 66 23 58 24 46 Z" fill="#151021" stroke={shade(a, 0.8)} strokeWidth="1" />
          <path d="M33 44 L67 44 L65 50 L35 50 Z" fill={`${a}44`} stroke={a} strokeWidth="0.9">
            <animate attributeName="opacity" values="1;0.55;1" dur="2s" repeatCount="indefinite" />
          </path>
          <rect x="38" y="46" width="8" height="1.6" fill={shade(a, 1.4)}>
            <animate attributeName="x" values="38;54;38" dur={busy ? '1.1s' : '2.2s'} repeatCount="indefinite" />
          </rect>
        </g>
      )
      break
    case 'voice':
      headwear = (
        <g>
          <path d="M27 36 Q23 16 44 13 M73 36 Q77 16 56 13" stroke={shade(a, 0.85)} strokeWidth="3.6" fill="none" strokeLinecap="round" />
          <rect x="20.5" y="34" width="9" height="14" rx="4.5" fill={shade(a, 0.85)} stroke={shade(a, 1.3)} strokeWidth="0.8" />
          <rect x="70.5" y="34" width="9" height="14" rx="4.5" fill={shade(a, 0.85)} stroke={shade(a, 1.3)} strokeWidth="0.8" />
        </g>
      )
      break
    case 'cowork':
      headwear = (
        <g>
          <circle cx="61" cy="45.5" r="8.4" fill="none" stroke="#C9A76B" strokeWidth="1.7" />
          <path d="M67.5 51.5 L71 55" stroke="#C9A76B" strokeWidth="1.6" strokeLinecap="round" />
        </g>
      )
      break
    case 'business':
      headwear = (
        <g>
          <path d="M38 66 C42 70 58 70 62 66" stroke="#E5E7EB" strokeWidth="1.2" fill="none" opacity="0.7" />
        </g>
      )
      break
  }

  // effets d'état : bulle de pensée, sablier, question, étincelles, goutte
  let stateFx: ReactElement | null = null
  switch (state) {
    case 'thinking':
      stateFx = (
        <g>
          <circle cx="76" cy="26" r="1.4" fill="#E2E8F0" opacity="0.8" />
          <circle cx="80" cy="20" r="2" fill="#E2E8F0" opacity="0.85" />
          <ellipse cx="86" cy="11" rx="9" ry="6.5" fill="#E2E8F0" opacity="0.92" />
          {[82, 86, 90].map((x, i) => (
            <circle key={x} cx={x} cy="11" r="1.2" fill={shade(a, 0.7)}>
              <animate attributeName="opacity" values="0.2;1;0.2" dur="1.2s" begin={`${i * 0.2}s`} repeatCount="indefinite" />
            </circle>
          ))}
        </g>
      )
      break
    case 'waiting':
      stateFx = (
        <g>
          <g>
            <animateTransform attributeName="transform" type="rotate" values="0 85 16;0 85 16;180 85 16;180 85 16" keyTimes="0;0.8;0.9;1" dur="3s" repeatCount="indefinite" />
            <path d="M80 9 h10 M80 23 h10 M81 9 C81 14 89 14 89 16 C89 18 81 18 81 23 M89 9 C89 14 81 14 81 16 C81 18 89 18 89 23" stroke="#CBD5E1" strokeWidth="1.1" fill="none" />
            <path d="M83 20.5 L87 20.5 L85 18 Z" fill={a} />
          </g>
        </g>
      )
      break
    case 'asking':
      stateFx = (
        <g>
          <circle cx="84" cy="16" r="9" fill={a} opacity="0.95">
            <animate attributeName="r" values="8.4;9.4;8.4" dur="1.2s" repeatCount="indefinite" />
          </circle>
          <text x="84" y="20.4" textAnchor="middle" fontSize="12" fontWeight="800" fill="#FFF" fontFamily="system-ui, sans-serif">?</text>
        </g>
      )
      break
    case 'checking':
      stateFx = (
        <g>
          <circle cx="84" cy="18" r="7.5" fill="none" stroke="#4ADE80" strokeWidth="1.3" opacity="0.85" />
          <path d="M80.5 18.5 L83 21 L88 15.5" stroke="#4ADE80" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeDasharray="12">
            <animate attributeName="stroke-dashoffset" values="12;0;0;12" keyTimes="0;0.5;0.85;1" dur="1.8s" repeatCount="indefinite" />
          </path>
        </g>
      )
      break
    case 'success':
      stateFx = (
        <g fill="#FDE68A">
          {[[16, 24, 0], [84, 20, 0.2], [12, 58, 0.4], [88, 56, 0.6]].map(([x, y, d]) => (
            <path key={`${x}-${y}`} d={`M${x} ${y - 4} L${x + 1.2} ${y - 1.2} L${x + 4} ${y} L${x + 1.2} ${y + 1.2} L${x} ${y + 4} L${x - 1.2} ${y + 1.2} L${x - 4} ${y} L${x - 1.2} ${y - 1.2} Z`}>
              <animateTransform attributeName="transform" type="scale" values="0.4;1.15;0.4" dur="1.2s" begin={`${d}s`} additive="sum" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.3;1;0.3" dur="1.2s" begin={`${d}s`} repeatCount="indefinite" />
            </path>
          ))}
        </g>
      )
      break
    case 'error':
      stateFx = (
        <path d="M70 30 C70 30 66.5 35 66.5 37 a3.5 3.5 0 0 0 7 0 C73.5 35 70 30 70 30 Z" fill="#93C5FD" opacity="0.9">
          <animateTransform attributeName="transform" type="translate" values="0 0;0 4;0 0" dur="1.8s" repeatCount="indefinite" />
        </path>
      )
      break
  }

  const bob =
    state === 'success' ? (
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0;0 -2.5;0 0" keyTimes="0;0.2;0.4;0.55;1" dur="1.4s" repeatCount="indefinite" />
    ) : busy ? (
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -1.1;0 0" dur="1.3s" repeatCount="indefinite" />
    ) : (
      <animateTransform attributeName="transform" type="translate" values="0 0;0 -1.8;0 0" dur={state === 'waiting' ? '4.6s' : '3.6s'} repeatCount="indefinite" />
    )
  const tilt = state === 'asking' ? 'rotate(-6 50 48)' : state === 'thinking' ? 'rotate(4 50 48)' : undefined
  const orbitDur = busy ? '7s' : state === 'waiting' ? '40s' : '24s'

  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={className} role="img" aria-label={title ?? `${agent.name}, ${agent.role} — ${MASCOT_STATE_LABEL[state]}`}>
      <defs>
        <radialGradient id={auraId} cx="0.5" cy="0.45">
          <stop offset="0" stopColor={a} stopOpacity={busy || state === 'success' ? 0.5 : 0.3} />
          <stop offset="0.7" stopColor={a} stopOpacity={busy ? 0.16 : 0.08} />
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

      <circle cx="50" cy="48" r="44" fill={`url(#${auraId})`}>
        <animate attributeName="r" values="42;45;42" dur={busy ? '1.6s' : '3.4s'} repeatCount="indefinite" />
      </circle>
      <circle cx="50" cy="48" r="38" fill="none" stroke={a} strokeOpacity={busy ? 0.45 : 0.22} strokeWidth="1" strokeDasharray="3 7">
        <animateTransform attributeName="transform" type="rotate" values="0 50 48;360 50 48" dur={orbitDur} repeatCount="indefinite" />
      </circle>
      {module === '3d' && (
        <g stroke={shade(a, 1.25)} strokeWidth="1.1" fill={`${a}33`}>
          <path d="M14 38 l5 -3 5 3 0 6 -5 3 -5 -3 Z">
            <animateTransform attributeName="transform" type="translate" values="0 0;0 -5;0 0" dur="3.4s" repeatCount="indefinite" />
          </path>
          <path d="M80 54 l4 -2.4 4 2.4 0 4.8 -4 2.4 -4 -2.4 Z">
            <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="2.7s" repeatCount="indefinite" />
          </path>
        </g>
      )}

      <g>
        {bob}
        {/* buste et bras */}
        <path d="M24 100 C24 82 34 72 50 72 C66 72 76 82 76 100 Z" fill={`url(#${outfitId})`} stroke="rgba(255,255,255,.14)" strokeWidth="0.8" />
        <path d="M42 73 L50 81 L58 73 L54 72 L50 76 L46 72 Z" fill={shade(c.outfit, 1.6)} />
        <path d="M30 84 C31 90 35 92 40 91" stroke={shade(c.outfitLight, 1.1)} strokeWidth="5.5" fill="none" strokeLinecap="round" />
        <path d="M70 84 C69 90 65 92 60 91" stroke={shade(c.outfitLight, 1.1)} strokeWidth="5.5" fill="none" strokeLinecap="round" />
        <HeldProp module={module} a={agent.accent} act={busy} uid={uid} />
        <circle cx="40.5" cy="90.5" r="2.7" fill={`url(#${skinId})`} />
        <circle cx="59.5" cy="90.5" r="2.7" fill={`url(#${skinId})`} />

        <g transform={tilt}>
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
          {mouth}
          <ellipse cx="38" cy="53.5" rx="3.4" ry="1.8" fill={a} opacity={state === 'success' ? 0.32 : 0.18} />
          <ellipse cx="62" cy="53.5" rx="3.4" ry="1.8" fill={a} opacity={state === 'success' ? 0.32 : 0.18} />
          <path d={c.hairFront} fill={`url(#${hairId})`} />
          {c.hairHighlight && <path d={c.hairHighlight} fill={c.hairLight} opacity="0.55" />}
          {headwear}
        </g>
      </g>

      {stateFx}
      {busy && (
        <g fill={shade(a, 1.4)}>
          <circle cx="12" cy="44" r="1.5">
            <animate attributeName="cy" values="44;30;44" dur="2.1s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.9;0" dur="2.1s" repeatCount="indefinite" />
          </circle>
          <circle cx="89" cy="52" r="1.3">
            <animate attributeName="cy" values="52;38;52" dur="2.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0;0.8;0" dur="2.6s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
    </svg>
  )
}
