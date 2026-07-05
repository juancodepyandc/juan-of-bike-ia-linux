// Map phonèmes français → visèmes pour le lipsync de l'idle Aurora.
//
// Demandé par le handoff :
//   "Lipsync: phoneme map FR → viseme (pas anglais par défaut)"
//
// La table source utilisée est IPA (International Phonetic Alphabet) →
// visème ARPABET subset adapté FR. Couvre les 36 phonèmes du français
// standard (16 voyelles + 17 consonnes + 3 semi-voyelles).
//
// Visèmes (positions de bouche neutres) :
//   - rest    : bouche fermée
//   - aa      : ouvert grand, mâchoire basse
//   - ee      : sourire, lèvres rétractées
//   - ih      : étalé léger
//   - oh      : arrondi moyen
//   - ou      : arrondi serré (kiss)
//   - eu      : neutre arrondi
//   - mm      : lèvres jointes
//   - ff      : dents sur lèvre inférieure
//   - th      : langue entre dents (rare en FR, mais utile pour mots empruntés)
//   - dd      : langue derrière dents
//   - kk      : arrière de la langue contre le palais
//   - ll      : langue contre le palais antérieur

export type Viseme =
  | 'rest'
  | 'aa'
  | 'ee'
  | 'ih'
  | 'oh'
  | 'ou'
  | 'eu'
  | 'mm'
  | 'ff'
  | 'th'
  | 'dd'
  | 'kk'
  | 'll'

export type PhonemeSample = {
  /** Phonème IPA. */
  ipa: string
  /** Visème cible. */
  viseme: Viseme
  /** Durée typique au débit normal (ms). */
  defaultDurationMs: number
}

/**
 * Table FR — sons standards. Étendue, mais pas exhaustive (les variantes
 * régionales ne sont pas distinguées : on rejoint le visème le plus proche).
 */
export const FR_PHONEME_TABLE: readonly PhonemeSample[] = [
  // Voyelles orales
  { ipa: 'i', viseme: 'ih', defaultDurationMs: 90 },   // "lit"
  { ipa: 'e', viseme: 'ee', defaultDurationMs: 90 },   // "thé"
  { ipa: 'ɛ', viseme: 'ee', defaultDurationMs: 110 },  // "fait"
  { ipa: 'a', viseme: 'aa', defaultDurationMs: 110 },  // "patte"
  { ipa: 'ɑ', viseme: 'aa', defaultDurationMs: 130 },  // "pâte"
  { ipa: 'ɔ', viseme: 'oh', defaultDurationMs: 110 },  // "sotte"
  { ipa: 'o', viseme: 'oh', defaultDurationMs: 90 },   // "sot"
  { ipa: 'u', viseme: 'ou', defaultDurationMs: 100 },  // "fou"
  { ipa: 'y', viseme: 'ou', defaultDurationMs: 100 },  // "tu"
  { ipa: 'ø', viseme: 'eu', defaultDurationMs: 90 },   // "feu"
  { ipa: 'œ', viseme: 'eu', defaultDurationMs: 110 },  // "fleur"
  { ipa: 'ə', viseme: 'eu', defaultDurationMs: 70 },   // "le"
  // Voyelles nasales
  { ipa: 'ɛ̃', viseme: 'aa', defaultDurationMs: 130 }, // "pain"
  { ipa: 'ɑ̃', viseme: 'aa', defaultDurationMs: 140 }, // "blanc"
  { ipa: 'ɔ̃', viseme: 'oh', defaultDurationMs: 130 }, // "bon"
  { ipa: 'œ̃', viseme: 'eu', defaultDurationMs: 120 }, // "brun" (rare)
  // Semi-voyelles
  { ipa: 'j', viseme: 'ih', defaultDurationMs: 60 },   // "yeux"
  { ipa: 'ɥ', viseme: 'ou', defaultDurationMs: 60 },   // "huit"
  { ipa: 'w', viseme: 'ou', defaultDurationMs: 60 },   // "oui"
  // Consonnes
  { ipa: 'p', viseme: 'mm', defaultDurationMs: 50 },
  { ipa: 'b', viseme: 'mm', defaultDurationMs: 50 },
  { ipa: 'm', viseme: 'mm', defaultDurationMs: 70 },
  { ipa: 't', viseme: 'dd', defaultDurationMs: 50 },
  { ipa: 'd', viseme: 'dd', defaultDurationMs: 50 },
  { ipa: 'n', viseme: 'dd', defaultDurationMs: 70 },
  { ipa: 'ɲ', viseme: 'dd', defaultDurationMs: 70 },  // "gn" (agneau)
  { ipa: 'k', viseme: 'kk', defaultDurationMs: 50 },
  { ipa: 'ɡ', viseme: 'kk', defaultDurationMs: 50 },
  { ipa: 'f', viseme: 'ff', defaultDurationMs: 70 },
  { ipa: 'v', viseme: 'ff', defaultDurationMs: 70 },
  { ipa: 's', viseme: 'dd', defaultDurationMs: 80 },
  { ipa: 'z', viseme: 'dd', defaultDurationMs: 80 },
  { ipa: 'ʃ', viseme: 'eu', defaultDurationMs: 80 },  // "ch"
  { ipa: 'ʒ', viseme: 'eu', defaultDurationMs: 80 },  // "j"
  { ipa: 'l', viseme: 'll', defaultDurationMs: 70 },
  { ipa: 'ʁ', viseme: 'aa', defaultDurationMs: 90 },  // "r" français uvulaire
  { ipa: 'ŋ', viseme: 'kk', defaultDurationMs: 70 },  // "ng" (parking)
  { ipa: 'θ', viseme: 'th', defaultDurationMs: 80 },  // "th" (mots empruntés)
]

const FR_TABLE_INDEX: ReadonlyMap<string, PhonemeSample> = new Map(FR_PHONEME_TABLE.map((p) => [p.ipa, p]))

/** Map a single phoneme to its viseme. Falls back to 'rest' when unknown. */
export function phonemeToViseme(ipa: string): Viseme {
  return FR_TABLE_INDEX.get(ipa)?.viseme ?? 'rest'
}

// --- Conversion texte → suite visèmes (très grossier) ----------------------
//
// Pour Aurora, on n'a pas besoin de précision linguistique. On veut juste un
// keyframe stream visème-temps "plausible". Une vraie pipeline ferait passer
// le texte par eSpeak NG ou Phonemizer ; ici on offre un fallback léger basé
// sur les digraphes/lettres FR (très approximatif, ~70% de plausibilité).

const FALLBACK_LETTER_TO_VISEME: Record<string, Viseme> = {
  a: 'aa', à: 'aa', â: 'aa', ä: 'aa',
  e: 'eu', é: 'ee', è: 'ee', ê: 'ee', ë: 'ee',
  i: 'ih', î: 'ih', ï: 'ih', y: 'ih',
  o: 'oh', ô: 'oh', ö: 'oh',
  u: 'ou', û: 'ou', ü: 'ou',
  m: 'mm', p: 'mm', b: 'mm',
  f: 'ff', v: 'ff',
  t: 'dd', d: 'dd', n: 'dd', s: 'dd', z: 'dd',
  k: 'kk', c: 'kk', q: 'kk', g: 'kk',
  l: 'll',
  r: 'aa',
  j: 'eu',
  w: 'ou', h: 'rest', ' ': 'rest', "'": 'rest', '-': 'rest',
}

export type VisemeKeyframe = {
  startMs: number
  endMs: number
  viseme: Viseme
}

/**
 * Convert plain FR text to a viseme keyframe stream. Designed for the idle
 * talking-head — not for serious lipsync. Caller passes wordsPerMinute to
 * scale timing.
 */
export function textToVisemes(text: string, wordsPerMinute = 160): VisemeKeyframe[] {
  if (!text) return []
  const totalChars = text.length
  // Average 5 chars/word + 1 space → wpm × 6 → chars/min → chars/ms
  const charsPerMs = (wordsPerMinute * 6) / 60_000
  let cursor = 0
  const out: VisemeKeyframe[] = []
  for (const ch of text.toLowerCase()) {
    const viseme = FALLBACK_LETTER_TO_VISEME[ch] ?? 'rest'
    const duration = Math.max(40, Math.round(1 / charsPerMs))
    out.push({ startMs: cursor, endMs: cursor + duration, viseme })
    cursor += duration
  }
  return mergeAdjacent(out)
}

function mergeAdjacent(frames: VisemeKeyframe[]): VisemeKeyframe[] {
  const out: VisemeKeyframe[] = []
  for (const frame of frames) {
    const last = out[out.length - 1]
    if (last && last.viseme === frame.viseme) {
      last.endMs = frame.endMs
    } else {
      out.push({ ...frame })
    }
  }
  return out
}

// --- Voice profiles (personas) ---------------------------------------------
//
// Demandé par le handoff :
//   - "TTS: choix automatique de voix par contexte (cours = pédagogique,
//      conversation = naturelle, hype = énergique)"
//   - "Persistence: voix favorites par contexte"

export type VoicePersonaId = 'aurora-prof' | 'aurora-pote' | 'aurora-hype' | 'aurora-narrateur' | 'aurora-zen'

export type VoiceProfile = {
  id: VoicePersonaId
  label: string
  /** Modèle Piper / Sherpa-ONNX. */
  ttsModel: string
  /** Pitch shift en demi-tons. */
  pitchSemitones: number
  /** Speed factor (1 = normal). */
  speed: number
  /** Style prompt utile pour les modèles "neural prompts". */
  stylePrompt: string
  /** Contextes typiques où on active ce profil par défaut. */
  defaultFor: Array<'cours' | 'discussion' | 'hype' | 'narration' | 'meditation'>
}

export const VOICE_PROFILES: readonly VoiceProfile[] = [
  {
    id: 'aurora-prof',
    label: 'Aurora prof',
    ttsModel: 'fr_FR-tom-medium',
    pitchSemitones: -1,
    speed: 0.95,
    stylePrompt: 'pédagogue, posée, articule, exemples concrets',
    defaultFor: ['cours'],
  },
  {
    id: 'aurora-pote',
    label: 'Aurora pote',
    ttsModel: 'fr_FR-siwis-medium',
    pitchSemitones: 0,
    speed: 1.0,
    stylePrompt: 'naturelle, chaleureuse, ton conversationnel, tutoiement',
    defaultFor: ['discussion'],
  },
  {
    id: 'aurora-hype',
    label: 'Aurora hype',
    ttsModel: 'fr_FR-siwis-medium',
    pitchSemitones: 2,
    speed: 1.1,
    stylePrompt: 'énergique, motivante, débit rapide, exclamations',
    defaultFor: ['hype'],
  },
  {
    id: 'aurora-narrateur',
    label: 'Aurora narrateur',
    ttsModel: 'fr_FR-tom-medium',
    pitchSemitones: -2,
    speed: 0.92,
    stylePrompt: 'grave, narrateur de documentaire, descriptions atmosphériques',
    defaultFor: ['narration'],
  },
  {
    id: 'aurora-zen',
    label: 'Aurora zen',
    ttsModel: 'fr_FR-siwis-medium',
    pitchSemitones: -1,
    speed: 0.85,
    stylePrompt: 'calme, douce, respiration ample, méditation guidée',
    defaultFor: ['meditation'],
  },
]

/** Pick a profile for a context, falling back to "aurora-pote". */
export function pickProfileForContext(context: VoiceProfile['defaultFor'][number]): VoiceProfile {
  return VOICE_PROFILES.find((p) => p.defaultFor.includes(context)) ?? VOICE_PROFILES[1]
}

// --- Interruption state machine --------------------------------------------
//
// "Cancel/interrupt : si user parle pendant que TTS joue, fade out + écoute."
// Cette machine d'état pure permet de simuler/tester ce comportement.

export type VoiceMode = 'idle' | 'speaking' | 'fading' | 'listening' | 'processing'

export type VoiceTransition =
  | { kind: 'start_speak' }
  | { kind: 'finish_speak' }
  | { kind: 'user_voice_detected'; rms: number }
  | { kind: 'user_voice_lost'; sinceMs: number }
  | { kind: 'speech_recognised' }
  | { kind: 'reset' }

export const VAD_RMS_THRESHOLD = 0.04
export const VAD_LOST_DEBOUNCE_MS = 600

export function transition(mode: VoiceMode, ev: VoiceTransition): VoiceMode {
  switch (ev.kind) {
    case 'reset': return 'idle'
    case 'start_speak': return mode === 'idle' || mode === 'listening' ? 'speaking' : mode
    case 'finish_speak': return mode === 'speaking' || mode === 'fading' ? 'idle' : mode
    case 'user_voice_detected':
      if (mode === 'speaking' && ev.rms >= VAD_RMS_THRESHOLD) return 'fading'
      if (mode === 'fading') return 'listening'
      if (mode === 'idle') return 'listening'
      return mode
    case 'user_voice_lost':
      if (mode === 'listening' && ev.sinceMs >= VAD_LOST_DEBOUNCE_MS) return 'processing'
      return mode
    case 'speech_recognised':
      if (mode === 'processing' || mode === 'listening') return 'idle'
      return mode
  }
}
