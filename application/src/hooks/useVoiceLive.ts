import { useCallback, useEffect, useRef, useState } from 'react'
import { fsWriteBinary, getWorkspacePath, runPythonScript } from './useTauri.ts'
import { isTauriRuntime, getBridgeUrl } from '../utils/runtime.ts'
import { safeParseJson } from '../utils/errors.ts'
import { phonemizeSentenceWithLiaisons, phonemizeWord } from '../services/voiceFrPhonemizer.ts'
import { FR_PHONEME_TABLE } from '../services/voicePhonemes.ts'

// ============================================================================
// 1. TYPES & INTERFACES AGI VOCALE, CLONAGE ZERO-SHOT & PRODUCTION MUSICALE
// ============================================================================

export type VoiceLivePhase = 'idle' | 'listening' | 'transcribing' | 'thinking' | 'speaking'

/** Cue Rhubarb — frame-accurate mouth shape. value = A..H | X */
export interface RhubarbCue { start: number; end: number; value: string }

/** Registre vocal estimé depuis la fréquence fondamentale F0 */
export type VocalRegister = 'bass' | 'baritone' | 'tenor' | 'alto' | 'mezzo' | 'soprano'

/**
 * Empreinte acoustique et prosodique extraite d'un échantillon vocal.
 * Sert au conditionnement de clonage vocal zero-shot et à l'adaptation TTS.
 */
export interface VoiceAcousticProfile {
  /** Fréquence fondamentale moyenne en Hz (trames voisées) */
  f0MeanHz: number
  /** Écart-type de F0 en Hz (mesure la modulation mélodique / expressivité) */
  f0StdHz: number
  /** Plage F0 min/max observée en Hz */
  f0MinHz: number
  f0MaxHz: number
  /** Registre vocal déduit de F0 */
  register: VocalRegister
  /** Formants vocaux moyens estimés (Hz) : F1 (ouverture), F2 (avancement), F3 (timbre) */
  formantsHz: { f1: number; f2: number; f3: number }
  /** Centroïde spectral moyen en Hz (brillance acoustique) */
  spectralCentroidHz: number
  /** Descripteurs timbraux normalisés [0..1] */
  timbre: {
    warmth: number
    brightness: number
    breathiness: number
    presence: number
  }
  /** Stabilité micro-prosodique : Jitter (%) et Shimmer (%) + HNR (dB) */
  jitterPct: number
  shimmerPct: number
  hnrDb: number
  /** Cadence syllabique estimée (syllabes / seconde) */
  syllablesPerSec: number
  /** Ratio temporel voisé / durée totale [0..1] */
  voicedRatio: number
  /** Plage dynamique en dB */
  dynamicRangeDb: number
  /** Durée utile analysée (secondes) */
  durationSec: number
  /** Signature compacte transmissible au moteur de clonage zero-shot */
  prosodySignature: string
}

/**
 * Plan prosodique et émotionnel calculé avant synthèse vocale.
 */
export interface ProsodyPlan {
  normalizedText: string
  emotion: 'neutral' | 'happy' | 'thinking' | 'surprised' | 'sad' | 'excited' | 'focused'
  rate: number
  pitch: number
  energy: number
  breathPauseMs: number
  intonationContour: 'declarative' | 'interrogative' | 'exclamative' | 'narrative'
  estimatedDurationSec: number
}

/**
 * Profil énergétique et spectral des 4 stems musicaux canoniques.
 */
export interface StemSeparationProfile {
  vocals: { energyRatio: number; rmsDb: number; centroidHz: number; dominance: number }
  bass: { energyRatio: number; rmsDb: number; subRatio: number; dominance: number }
  drums: { energyRatio: number; rmsDb: number; transientDensity: number; dominance: number }
  harmony: { energyRatio: number; rmsDb: number; stereoWidth: number; dominance: number }
  estimatedBpm: number
  estimatedKey: string
  integratedLufs: number
  crestFactorDb: number
}

export type MusicSectionKind = 'intro' | 'verse' | 'pre-chorus' | 'chorus' | 'bridge' | 'outro'

export interface MusicSectionPlan {
  kind: MusicSectionKind
  label: string
  startBar: number
  bars: number
  startSec: number
  endSec: number
  energyTarget: number
  lyricsLines: Array<{ text: string; syllables: number; stressPattern: string }>
  activeStems: Array<'vocals' | 'bass' | 'drums' | 'harmony'>
}

export interface MusicProductionStructure {
  bpm: number
  timeSignature: '4/4' | '3/4' | '6/8'
  keySignature: string
  totalDurationSec: number
  sections: MusicSectionPlan[]
}

// ============================================================================
// 2. MOTEUR DE NORMALISATION PROSODIQUE & PHONÉTIQUE FRANÇAISE
// ============================================================================

const ACRONYM_PHONETIC_FR: Readonly<Record<string, string>> = {
  AGI: 'A G I',
  IA: 'I A',
  API: 'A P I',
  GPU: 'G P U',
  CPU: 'C P U',
  VRAM: 'vé-ram',
  RAM: 'ram',
  TTS: 'T T S',
  STT: 'S T T',
  ASR: 'A S R',
  LLM: 'L L M',
  NLP: 'N L P',
  VAD: 'V A D',
  PBR: 'P B R',
  CAO: 'C A O',
  DAO: 'D A O',
  SQL: 'S Q L',
  JSON: 'jik-sonne',
  HTML: 'H T M L',
  CSS: 'C S S',
  URL: 'U R L',
  HTTPS: 'H T T P S',
  HTTP: 'H T T P',
  TCP: 'T C P',
  UDP: 'U D P',
  SSH: 'S S H',
  PDF: 'P D F',
  CSV: 'C S V',
  RVB: 'R V B',
  RGB: 'R G B',
  FPS: 'images par seconde',
  BPM: 'battements par minute',
  LUFS: 'L U F S',
}

const FRENCH_SMALL_NUMBERS: Readonly<Record<number, string>> = {
  0: 'zéro', 1: 'un', 2: 'deux', 3: 'trois', 4: 'quatre', 5: 'cinq',
  6: 'six', 7: 'sept', 8: 'huit', 9: 'neuf', 10: 'dix',
  11: 'onze', 12: 'douze', 13: 'treize', 14: 'quatorze', 15: 'quinze',
  16: 'seize', 20: 'vingt', 30: 'trente', 40: 'quarante', 50: 'cinquante',
  60: 'soixante', 100: 'cent', 1000: 'mille',
}

/**
 * Convertit un entier [0..9999] en toutes lettres françaises pour éviter
 * les erreurs de lecture de nombres par les moteurs TTS légers.
 */
function numberToFrenchWords(n: number): string {
  if (!Number.isFinite(n) || n < 0 || n > 999999) return String(n)
  const intN = Math.round(n)
  if (FRENCH_SMALL_NUMBERS[intN]) return FRENCH_SMALL_NUMBERS[intN]
  if (intN < 20) return `dix-${FRENCH_SMALL_NUMBERS[intN - 10]}`
  if (intN < 70) {
    const tens = Math.floor(intN / 10) * 10
    const unit = intN % 10
    if (unit === 1) return `${FRENCH_SMALL_NUMBERS[tens]} et un`
    return `${FRENCH_SMALL_NUMBERS[tens]}-${FRENCH_SMALL_NUMBERS[unit]}`
  }
  if (intN < 80) {
    const rem = intN - 60
    if (rem === 11) return 'soixante et onze'
    return `soixante-${numberToFrenchWords(rem)}`
  }
  if (intN < 100) {
    if (intN === 80) return 'quatre-vingts'
    return `quatre-vingt-${numberToFrenchWords(intN - 80)}`
  }
  if (intN < 1000) {
    const hundreds = Math.floor(intN / 100)
    const rem = intN % 100
    const prefix = hundreds === 1 ? 'cent' : `${FRENCH_SMALL_NUMBERS[hundreds]} cent${rem === 0 ? 's' : ''}`
    return rem === 0 ? prefix : `${prefix} ${numberToFrenchWords(rem)}`
  }
  const thousands = Math.floor(intN / 1000)
  const rem = intN % 1000
  const prefix = thousands === 1 ? 'mille' : `${numberToFrenchWords(thousands)} mille`
  return rem === 0 ? prefix : `${prefix} ${numberToFrenchWords(rem)}`
}

/**
 * Normalise le texte pour une synthèse vocale française d'excellence :
 * - Nettoyage du Markdown, URLs et blocs de code
 * - Expansion des unités physiques, monétaires et mathématiques
 * - Diction des acronymes et nombres
 * - Désambiguïsation d'homophones et liaisons sensibles (neuf ans -> neuv ans, plus/plu)
 * - Insertion de ponctuation respiratoire sur les longues propositions
 */
export function normalizeFrenchProsodyAndPhonetics(rawText: string, lang = 'fr'): string {
  if (!rawText || !rawText.trim()) return ''

  let text = rawText
    // Blocs de code multi-lignes : ne pas épeler 50 lignes de code brut
    .replace(/```[\s\S]*?```/g, ' , bloc de code affiché à l’écran, ')
    // Code inline court : garder le contenu sans les backticks
    .replace(/`([^`\n]{1,48})`/g, '$1')
    .replace(/`[^`\n]+`/g, ' expression technique ')
    // Liens Markdown [label](url) -> label
    .replace(/\[([^\]]+)\]\((?:https?:\/\/|\/)[^)]+\)/g, '$1')
    // URLs nues
    .replace(/https?:\/\/[^\s)]+/g, 'lien web')
    // Titres Markdown et listes à puces -> pauses prosodiques
    .replace(/^#{1,6}\s+(.+)$/gm, '$1. ')
    .replace(/^\s*[-*•]\s+/gm, ', ')
    // Gras / italique Markdown
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')

  if (!lang.toLowerCase().startsWith('fr')) {
    return text.replace(/\s+/g, ' ').trim()
  }

  // Unités et symboles scientifiques / monétaires en français
  text = text
    .replace(/\b(\d+(?:[.,]\d+)?)\s*%/g, '$1 pour cent')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*€/g, '$1 euros')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*\$/g, '$1 dollars')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*°C\b/g, '$1 degrés Celsius')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*°F\b/g, '$1 degrés Fahrenheit')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*°\b/g, '$1 degrés')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*km\/h\b/gi, '$1 kilomètres par heure')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*m\/s\b/gi, '$1 mètres par seconde')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*kHz\b/gi, '$1 kilohertz')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*MHz\b/gi, '$1 mégahertz')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*GHz\b/gi, '$1 gigahertz')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*Hz\b/g, '$1 hertz')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*ms\b/g, '$1 millisecondes')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*dB\b/g, '$1 décibels')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*Go\b/g, '$1 gigaoctets')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*Mo\b/g, '$1 mégaoctets')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*Ko\b/g, '$1 kilooctets')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*GB\b/g, '$1 gigaoctets')
    .replace(/\b(\d+(?:[.,]\d+)?)\s*MB\b/g, '$1 mégaoctets')
    .replace(/\b3D\b/gi, 'trois D')
    .replace(/\b2D\b/gi, 'deux D')
    .replace(/\b4K\b/gi, 'quatre K')
    .replace(/\b8K\b/gi, 'huit K')
    .replace(/\b16K\b/gi, 'seize K')
    .replace(/≥|>=/g, ' supérieur ou égal à ')
    .replace(/≤|<=/g, ' inférieur ou égal à ')
    .replace(/!=|≠/g, ' différent de ')
    .replace(/->|→/g, ' vers ')

  // Nombres décimaux français (ex: 3.14 ou 3,14 -> 3 virgule 14)
  text = text.replace(/\b(\d+)[.,](\d+)\b/g, (_m, a, b) => `${a} virgule ${b}`)

  // Conversion des nombres entiers isolés [0..2000] pour garantir les liaisons justes
  text = text.replace(/\b(\d{1,4})\b/g, (match) => {
    const val = parseInt(match, 10)
    if (Number.isNaN(val) || val > 2500) return match
    return numberToFrenchWords(val)
  })

  // Liaisons phonétiques obligatoires critiques ("neuf ans" -> "neuv ans", "neuf heures" -> "neuv heures")
  text = text
    .replace(/\bneuf\s+(ans?|heures?)\b/gi, 'neuv $1')
    .replace(/\bdix-neuf\s+(ans?|heures?)\b/gi, 'dix-neuv $1')
    .replace(/\bvingt-neuf\s+(ans?|heures?)\b/gi, 'vingt-neuv $1')

  // Homophones contextuels : "en plus" -> "en plusse" en fin de proposition
  text = text.replace(/\ben plus(?=\s*[,.;:!?]|$)/gi, 'en plusse')

  // Acronymes techniques
  text = text.replace(/\b([A-Z]{2,6})\b/g, (acr) => ACRONYM_PHONETIC_FR[acr] ?? acr)

  // Insertion de ponctuation respiratoire dans les propositions trop longues (> 85 car. sans pause)
  const segments = text.split(/([,.;:!?…]+)/)
  const breathedSegments = segments.map((seg) => {
    if (seg.length <= 85 || /^[,.;:!?…]+$/.test(seg)) return seg
    return seg.replace(
      /\s+(cependant|toutefois|néanmoins|par conséquent|tandis que|alors que|parce que|puisque|afin de|afin que|notamment|ainsi que|c’est-à-dire|Autrement dit)\s+/gi,
      ', $1 ',
    )
  })

  return breathedSegments
    .join('')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/([,.;:!?])([^\s,.;:!?])/g, '$1 $2')
    .replace(/,{2,}/g, ',')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Calcule un plan prosodique complet (émotion, débit, hauteur, énergie, contour intonatif)
 * à partir du texte et d'un éventuel profil acoustique de référence (clonage).
 */
export function extractProsodyPlan(
  rawText: string,
  lang = 'fr',
  referenceProfile?: VoiceAcousticProfile | null,
): ProsodyPlan {
  const normalizedText = normalizeFrenchProsodyAndPhonetics(rawText, lang)
  const lower = normalizedText.toLowerCase()

  const exclamations = (normalizedText.match(/!/g) || []).length
  const questions = (normalizedText.match(/\?/g) || []).length
  const ellipses = (normalizedText.match(/(\.\.\.|…)/g) || []).length

  let emotion: ProsodyPlan['emotion'] = 'neutral'
  if (/\b(bravo|super|excellent|parfait|génial|magnifique|félicitations|heureux|ravie?)\b/.test(lower)) {
    emotion = exclamations > 0 ? 'excited' : 'happy'
  } else if (/\b(attention|urgent|incroyable|impressionnant|extraordinaire)\b/.test(lower) || exclamations >= 2) {
    emotion = 'surprised'
  } else if (/\b(désolé|malheureusement|hélas|triste|erreur|échec|impossible)\b/.test(lower)) {
    emotion = 'sad'
  } else if (/\b(analysons|calculons|observons|considérons|hypothèse|étape|algorithme|architecture)\b/.test(lower)) {
    emotion = 'focused'
  } else if (ellipses > 0 || /\b(voyons|peut-être|réfléchissons|intéressant)\b/.test(lower)) {
    emotion = 'thinking'
  }

  let intonationContour: ProsodyPlan['intonationContour'] = 'declarative'
  if (questions > exclamations && questions > 0) intonationContour = 'interrogative'
  else if (exclamations > 0) intonationContour = 'exclamative'
  else if (normalizedText.length > 220) intonationContour = 'narrative'

  // Base prosodique modulée par l'émotion
  let rate = 0.98
  let pitch = 1.02
  let energy = 0.75
  let breathPauseMs = 180

  switch (emotion) {
    case 'excited':
      rate = 1.06; pitch = 1.08; energy = 0.95; breathPauseMs = 140
      break
    case 'happy':
      rate = 1.02; pitch = 1.05; energy = 0.85; breathPauseMs = 160
      break
    case 'surprised':
      rate = 1.04; pitch = 1.09; energy = 0.90; breathPauseMs = 150
      break
    case 'sad':
      rate = 0.91; pitch = 0.95; energy = 0.55; breathPauseMs = 260
      break
    case 'thinking':
      rate = 0.93; pitch = 0.99; energy = 0.65; breathPauseMs = 240
      break
    case 'focused':
      rate = 0.97; pitch = 1.00; energy = 0.80; breathPauseMs = 190
      break
    default:
      break
  }

  // Si un profil vocal de référence (clonage zero-shot) est actif, on adapte le débit et la hauteur
  if (referenceProfile && referenceProfile.durationSec >= 0.8) {
    // Normalisation autour d'une cadence française standard de 4.6 syllabes/s
    const cadenceFactor = Math.max(0.85, Math.min(1.18, referenceProfile.syllablesPerSec / 4.6))
    rate = Number((rate * 0.65 + cadenceFactor * 0.35).toFixed(3))
    // Adaptation douce de la hauteur relative selon le registre détecté
    const refF0Norm = Math.max(0.85, Math.min(1.18, referenceProfile.f0MeanHz / 185))
    pitch = Number((pitch * 0.6 + refF0Norm * 0.4).toFixed(3))
  }

  const wordCount = normalizedText.split(/\s+/).filter(Boolean).length
  const estimatedDurationSec = Math.max(0.6, (wordCount / (2.6 * rate)))

  return {
    normalizedText,
    emotion,
    rate,
    pitch,
    energy,
    breathPauseMs,
    intonationContour,
    estimatedDurationSec,
  }
}

// ============================================================================
// 3. ALIGNEMENT TEMPOREL PRÉCIS DES VISÈMES RHUBARB (A..H | X)
// ============================================================================

const FR_IPA_DURATION_MS = new Map<string, number>(
  FR_PHONEME_TABLE.map((p) => [p.ipa, p.defaultDurationMs]),
)

/**
 * Convertit un phonème IPA français vers la forme de bouche Rhubarb exacte (A..H | X) :
 * - A : voyelles grandes ouvertes (a, ɑ, ɑ̃, ɛ̃)
 * - B : consonnes bilabiales et occlusives labiales fermées (m, b, p)
 * - C : voyelles antérieures étirées / sourire (e, ɛ, i, j)
 * - D : consonnes alvéolaires / dentales (d, t, s, z, n, ɲ)
 * - E : voyelles moyennes arrondies (ø, œ, œ̃, ɔ, ə)
 * - F : voyelles fermées très arrondies / protrusion labiale (u, o, ɔ̃, y, w, ɥ)
 * - G : fricatives labiodentales (f, v)
 * - H : liquides et uvulaires (l, ʁ, k, ɡ, ʃ, ʒ)
 * - X : repos / silence respiratoire
 */
export function ipaToRhubarbViseme(ipa: string): string {
  switch (ipa) {
    case 'a':
    case 'ɑ':
    case 'ɑ̃':
    case 'ɛ̃':
      return 'A'
    case 'm':
    case 'b':
    case 'p':
      return 'B'
    case 'e':
    case 'ɛ':
    case 'i':
    case 'j':
      return 'C'
    case 'd':
    case 't':
    case 's':
    case 'z':
    case 'n':
    case 'ɲ':
    case 'ŋ':
      return 'D'
    case 'ø':
    case 'œ':
    case 'œ̃':
    case 'ɔ':
    case 'ə':
      return 'E'
    case 'u':
    case 'o':
    case 'ɔ̃':
    case 'y':
    case 'w':
    case 'ɥ':
      return 'F'
    case 'f':
    case 'v':
      return 'G'
    case 'l':
    case 'ʁ':
    case 'ʃ':
    case 'ʒ':
    case 'k':
    case 'ɡ':
      return 'H'
    default:
      return 'X'
  }
}

/**
 * Formants théoriques normalisés { low (F1 ouverture), mid (F2 étirement) } par visème Rhubarb.
 * Permet d'alimenter `formantsRef` à 60 FPS avec une fidélité articulatoire exacte même
 * lorsque l'élément audio ne peut pas être routé via MediaElementSource.
 */
function rhubarbVisemeToFormants(viseme: string, envelope: number): { low: number; mid: number } {
  const e = Math.max(0, Math.min(1, envelope))
  switch (viseme) {
    case 'A': return { low: 0.92 * e, mid: 0.55 * e }
    case 'B': return { low: 0.08 * e, mid: 0.18 * e }
    case 'C': return { low: 0.42 * e, mid: 0.90 * e }
    case 'D': return { low: 0.32 * e, mid: 0.72 * e }
    case 'E': return { low: 0.64 * e, mid: 0.52 * e }
    case 'F': return { low: 0.48 * e, mid: 0.25 * e }
    case 'G': return { low: 0.28 * e, mid: 0.45 * e }
    case 'H': return { low: 0.36 * e, mid: 0.60 * e }
    default:  return { low: 0.03 * e, mid: 0.03 * e }
  }
}

/**
 * Génère une timeline de cues Rhubarb (en secondes) à partir du texte français,
 * en intégrant les liaisons obligatoires, l'allongement vocalique de fin de groupe
 * rythmique et les pauses de ponctuation respiratoire.
 */
export function generateRhubarbCuesFromText(text: string, targetDurationSec?: number): RhubarbCue[] {
  if (!text || !text.trim()) return [{ start: 0, end: 0.2, value: 'X' }]

  // Découpage en groupes rythmiques par ponctuation pour préserver les pauses respiratoires
  const clauses = text
    .split(/([,.;:!?…]+)/)
    .map((s) => s.trim())
    .filter(Boolean)

  const rawCues: RhubarbCue[] = []
  let cursorSec = 0.02

  // Silence d'attaque initial
  rawCues.push({ start: 0, end: cursorSec, value: 'X' })

  for (const clause of clauses) {
    if (/^[,.;:!?…]+$/.test(clause)) {
      const pauseSec = /[.;!?…]/.test(clause) ? 0.22 : 0.11
      const last = rawCues[rawCues.length - 1]
      if (last && last.value === 'X') {
        last.end = Number((last.end + pauseSec).toFixed(4))
      } else {
        rawCues.push({ start: Number(cursorSec.toFixed(4)), end: Number((cursorSec + pauseSec).toFixed(4)), value: 'X' })
      }
      cursorSec += pauseSec
      continue
    }

    const phones = phonemizeSentenceWithLiaisons(clause)
    for (let i = 0; i < phones.length; i++) {
      const ph = phones[i]
      const viseme = ipaToRhubarbViseme(ph)
      const baseMs = FR_IPA_DURATION_MS.get(ph) ?? 75
      // Allongement prosodique de la dernière voyelle du groupe rythmique (+30 %)
      const isLastVowel = i >= phones.length - 2 && ['A', 'C', 'E', 'F'].includes(viseme)
      const durSec = (baseMs * (isLastVowel ? 1.3 : 1.0)) / 1000

      // Coarticulation bilabiale : si on passe à 'B' après un silence, anticipons de 18 ms
      const start = Number(cursorSec.toFixed(4))
      const end = Number((cursorSec + durSec).toFixed(4))
      const prev = rawCues[rawCues.length - 1]
      if (prev && prev.value === viseme) {
        prev.end = end
      } else {
        rawCues.push({ start, end, value: viseme })
      }
      cursorSec += durSec
    }
  }

  // Fermeture labiale finale au repos
  rawCues.push({
    start: Number(cursorSec.toFixed(4)),
    end: Number((cursorSec + 0.12).toFixed(4)),
    value: 'X',
  })

  if (targetDurationSec && Number.isFinite(targetDurationSec) && targetDurationSec > 0.15) {
    return recalibrateRhubarbCues(rawCues, targetDurationSec)
  }
  return rawCues
}

/**
 * Recalibre homothétiquement et lisse une liste de cues Rhubarb sur la durée exacte
 * du fichier audio (`actualDurationSec`), en fusionnant les micro-artefacts < 22 ms.
 */
export function recalibrateRhubarbCues(cues: RhubarbCue[], actualDurationSec: number): RhubarbCue[] {
  if (!cues.length || !Number.isFinite(actualDurationSec) || actualDurationSec <= 0.05) return cues
  const currentTotal = cues[cues.length - 1].end
  if (currentTotal <= 0.01) return cues

  const scale = actualDurationSec / currentTotal
  const scaled: RhubarbCue[] = []

  for (const c of cues) {
    const start = Number((c.start * scale).toFixed(4))
    const end = Number((c.end * scale).toFixed(4))
    const dur = end - start
    // Fusionner les micro-états non-bilabiaux trop brefs (< 22 ms) avec le voisin précédent
    if (dur < 0.022 && c.value !== 'B' && scaled.length > 0) {
      scaled[scaled.length - 1].end = end
      continue
    }
    if (scaled.length > 0 && scaled[scaled.length - 1].value === c.value) {
      scaled[scaled.length - 1].end = end
    } else {
      scaled.push({ start, end, value: c.value })
    }
  }

  return scaled
}

// ============================================================================
// 4. DSP AUDIO, PROFILAGE CLONAGE ZERO-SHOT & STRUCTURATION MUSICALE / STEMS
// ============================================================================

/**
 * Applique un prétraitement DSP professionnel sur les échantillons mono :
 * 1. Suppression du DC-offset (centrage zéro exact)
 * 2. Filtre passe-haut Butterworth 1er ordre à 75 Hz (élimine le rumble micro)
 * 3. Rognage des silences extrêmes de début/fin avec pre-roll/post-roll de 120 ms
 * 4. Normalisation de crête à -1 dBFS (0.891) avec limiteur doux tanh (zéro saturation)
 */
function preprocessVoiceSamplesDSP(rawSamples: Float32Array, sampleRate: number): Float32Array {
  const n = rawSamples.length
  if (n === 0) return rawSamples

  // 1. Suppression du DC-offset
  let dcSum = 0
  for (let i = 0; i < n; i++) dcSum += rawSamples[i]
  const dcOffset = dcSum / n

  // 2. Filtre passe-haut à fc = 75 Hz : y[i] = alpha * (y[i-1] + x[i] - x[i-1])
  const rc = 1 / (2 * Math.PI * 75)
  const dt = 1 / Math.max(8000, sampleRate)
  const alpha = rc / (rc + dt)

  const filtered = new Float32Array(n)
  let prevX = rawSamples[0] - dcOffset
  let prevY = 0
  let peak = 0

  for (let i = 0; i < n; i++) {
    const x = rawSamples[i] - dcOffset
    const y = alpha * (prevY + x - prevX)
    prevX = x
    prevY = y
    filtered[i] = y
    const absY = Math.abs(y)
    if (absY > peak) peak = absY
  }

  // 3. Rognage intelligent des silences de tête/queue avec garde de 120 ms
  const winSize = Math.max(64, Math.floor(sampleRate * 0.02)) // 20 ms
  const energyThreshold = Math.max(0.004, peak * 0.035)
  let firstActive = 0
  let lastActive = n - 1

  for (let i = 0; i + winSize < n; i += winSize) {
    let sumSq = 0
    for (let j = 0; j < winSize; j++) sumSq += filtered[i + j] * filtered[i + j]
    if (Math.sqrt(sumSq / winSize) >= energyThreshold) {
      firstActive = i
      break
    }
  }
  for (let i = n - winSize; i >= firstActive; i -= winSize) {
    let sumSq = 0
    for (let j = 0; j < winSize; j++) sumSq += filtered[i + j] * filtered[i + j]
    if (Math.sqrt(sumSq / winSize) >= energyThreshold) {
      lastActive = i + winSize
      break
    }
  }

  const padSamples = Math.floor(sampleRate * 0.12) // 120 ms pre/post-roll
  const startIdx = Math.max(0, firstActive - padSamples)
  const endIdx = Math.min(n, lastActive + padSamples)
  const trimmed = endIdx - startIdx >= Math.floor(sampleRate * 0.25)
    ? filtered.subarray(startIdx, endIdx)
    : filtered

  // 4. Normalisation de crête à -1 dBFS (0.891) avec soft-clipper tanh
  const targetPeak = 0.891
  const gain = peak > 0.005 ? Math.min(6.0, targetPeak / peak) : 1.0
  const out = new Float32Array(trimmed.length)
  for (let i = 0; i < trimmed.length; i++) {
    const v = trimmed[i] * gain
    // Soft-knee tanh au-delà de 0.85 pour garantir zéro saturation spectrale
    out[i] = Math.abs(v) > 0.85 ? Math.tanh(v) : v
  }
  return out
}

/**
 * Extrait le profil acoustique et prosodique complet (`VoiceAcousticProfile`)
 * depuis un signal PCM mono pour le clonage vocal zero-shot.
 */
export function extractVoiceAcousticProfile(samples: Float32Array, sampleRate: number): VoiceAcousticProfile {
  const durationSec = Number((samples.length / Math.max(1, sampleRate)).toFixed(3))
  const frameSize = Math.floor(sampleRate * 0.03) // Fenêtres de 30 ms
  const hopSize = Math.floor(sampleRate * 0.015)  // Pas de 15 ms

  const f0Values: number[] = []
  const periodSamplesList: number[] = []
  const framePeaks: number[] = []
  const frameRmsDb: number[] = []
  const hnrValues: number[] = []
  let zcrSum = 0
  let totalFrames = 0
  let voicedFrames = 0

  const minLag = Math.max(2, Math.floor(sampleRate / 450)) // 450 Hz max
  const maxLag = Math.min(frameSize - 2, Math.floor(sampleRate / 75)) // 75 Hz min

  for (let offset = 0; offset + frameSize <= samples.length; offset += hopSize) {
    totalFrames++
    let sumSq = 0
    let framePeak = 0
    let zc = 0
    for (let i = 0; i < frameSize; i++) {
      const s = samples[offset + i]
      sumSq += s * s
      const absS = Math.abs(s)
      if (absS > framePeak) framePeak = absS
      if (i > 0 && ((samples[offset + i - 1] >= 0 && s < 0) || (samples[offset + i - 1] < 0 && s >= 0))) {
        zc++
      }
    }
    const rms = Math.sqrt(sumSq / frameSize)
    const zcr = (zc / frameSize) * sampleRate
    zcrSum += zcr

    if (rms > 0.012) {
      frameRmsDb.push(20 * Math.log10(Math.max(1e-5, rms)))
    }

    // Détection de voisement et F0 par autocorrélation normalisée
    if (rms >= 0.018 && sumSq > 1e-6) {
      let bestLag = 0
      let bestCorr = 0
      for (let lag = minLag; lag <= maxLag; lag++) {
        let corr = 0
        let normA = 0
        let normB = 0
        const len = frameSize - lag
        for (let i = 0; i < len; i++) {
          const a = samples[offset + i]
          const b = samples[offset + i + lag]
          corr += a * b
          normA += a * a
          normB += b * b
        }
        const denom = Math.sqrt(normA * normB)
        const r = denom > 1e-8 ? corr / denom : 0
        if (r > bestCorr) {
          bestCorr = r
          bestLag = lag
        }
      }

      if (bestCorr >= 0.52 && bestLag > 0) {
        voicedFrames++
        const f0 = sampleRate / bestLag
        if (f0 >= 75 && f0 <= 450) {
          f0Values.push(f0)
          periodSamplesList.push(bestLag)
          framePeaks.push(framePeak)
          const hnr = 10 * Math.log10(Math.max(0.01, bestCorr) / Math.max(0.001, 1 - bestCorr))
          hnrValues.push(Math.max(0, Math.min(35, hnr)))
        }
      }
    }
  }

  const f0MeanHz = f0Values.length > 0
    ? Number((f0Values.reduce((a, b) => a + b, 0) / f0Values.length).toFixed(1))
    : 165
  const f0Variance = f0Values.length > 1
    ? f0Values.reduce((acc, v) => acc + (v - f0MeanHz) ** 2, 0) / f0Values.length
    : 18
  const f0StdHz = Number(Math.sqrt(f0Variance).toFixed(1))
  const f0MinHz = f0Values.length > 0 ? Number(Math.min(...f0Values).toFixed(1)) : 120
  const f0MaxHz = f0Values.length > 0 ? Number(Math.max(...f0Values).toFixed(1)) : 220

  // Registre vocal selon F0 moyenne
  let register: VocalRegister = 'baritone'
  if (f0MeanHz < 110) register = 'bass'
  else if (f0MeanHz < 145) register = 'baritone'
  else if (f0MeanHz < 185) register = 'tenor'
  else if (f0MeanHz < 220) register = 'alto'
  else if (f0MeanHz < 260) register = 'mezzo'
  else register = 'soprano'

  // Jitter (%) et Shimmer (%) sur les trames voisées consécutives
  let jitterSum = 0
  for (let i = 1; i < periodSamplesList.length; i++) {
    jitterSum += Math.abs(periodSamplesList[i] - periodSamplesList[i - 1])
  }
  const avgPeriod = periodSamplesList.length > 0
    ? periodSamplesList.reduce((a, b) => a + b, 0) / periodSamplesList.length
    : 1
  const jitterPct = periodSamplesList.length > 1
    ? Number(Math.min(8, ((jitterSum / (periodSamplesList.length - 1)) / avgPeriod) * 100).toFixed(2))
    : 0.65

  let shimmerSum = 0
  for (let i = 1; i < framePeaks.length; i++) {
    shimmerSum += Math.abs(framePeaks[i] - framePeaks[i - 1])
  }
  const avgPeak = framePeaks.length > 0
    ? framePeaks.reduce((a, b) => a + b, 0) / framePeaks.length
    : 1
  const shimmerPct = framePeaks.length > 1
    ? Number(Math.min(15, ((shimmerSum / (framePeaks.length - 1)) / Math.max(1e-4, avgPeak)) * 100).toFixed(2))
    : 2.4

  const hnrDb = hnrValues.length > 0
    ? Number((hnrValues.reduce((a, b) => a + b, 0) / hnrValues.length).toFixed(1))
    : 16.5

  const meanZcr = totalFrames > 0 ? zcrSum / totalFrames : 1200
  const spectralCentroidHz = Number(Math.max(450, Math.min(4200, meanZcr * 1.35)).toFixed(0))

  // Estimation allométrique des formants F1, F2, F3 selon la longueur du conduit vocal induite par F0
  const vocalTractScale = Math.max(0.82, Math.min(1.22, 1 + (f0MeanHz - 150) / 650))
  const formantsHz = {
    f1: Math.round(520 * vocalTractScale),
    f2: Math.round(1540 * vocalTractScale),
    f3: Math.round(2560 * vocalTractScale),
  }

  // Cadence syllabique par comptage des pics d'enveloppe d'énergie lissée (distants d'au moins 110 ms)
  let syllablePeaks = 0
  let lastPeakFrame = -10
  for (let i = 1; i + 1 < frameRmsDb.length; i++) {
    if (
      frameRmsDb[i] > frameRmsDb[i - 1] &&
      frameRmsDb[i] >= frameRmsDb[i + 1] &&
      frameRmsDb[i] > -32 &&
      i - lastPeakFrame >= 7
    ) {
      syllablePeaks++
      lastPeakFrame = i
    }
  }
  const activeSec = Math.max(0.4, (voicedFrames * hopSize) / Math.max(1, sampleRate))
  const syllablesPerSec = Number(Math.max(2.5, Math.min(7.2, syllablePeaks / activeSec || 4.4)).toFixed(2))
  const voicedRatio = totalFrames > 0 ? Number((voicedFrames / totalFrames).toFixed(2)) : 0

  const dynamicRangeDb = frameRmsDb.length > 2
    ? Number((Math.max(...frameRmsDb) - Math.min(...frameRmsDb)).toFixed(1))
    : 14.0

  const warmth = Number(Math.max(0.1, Math.min(1, 1 - (spectralCentroidHz - 600) / 3200)).toFixed(2))
  const brightness = Number(Math.max(0.1, Math.min(1, (spectralCentroidHz - 600) / 3000)).toFixed(2))
  const breathiness = Number(Math.max(0.05, Math.min(1, 1 - hnrDb / 28)).toFixed(2))
  const presence = Number(Math.max(0.2, Math.min(1, voicedRatio * 0.6 + brightness * 0.4)).toFixed(2))

  const prosodySignature = `${register}:f0=${f0MeanHz}Hz±${f0StdHz}:cad=${syllablesPerSec}syl/s:w=${warmth}:b=${brightness}`

  return {
    f0MeanHz,
    f0StdHz,
    f0MinHz,
    f0MaxHz,
    register,
    formantsHz,
    spectralCentroidHz,
    timbre: { warmth, brightness, breathiness, presence },
    jitterPct,
    shimmerPct,
    hnrDb,
    syllablesPerSec,
    voicedRatio,
    dynamicRangeDb,
    durationSec,
    prosodySignature,
  }
}

/**
 * Analyse un AudioBuffer / tableau d'échantillons pour en extraire le profil des 4 stems
 * (`vocals`, `bass`, `drums`, `harmony`), le tempo BPM, la tonalité et la dynamique LUFS.
 */
export function analyzeAudioStemsFromSamples(samples: Float32Array, sampleRate: number): StemSeparationProfile {
  const n = samples.length
  if (n === 0) {
    return {
      vocals: { energyRatio: 0.35, rmsDb: -18, centroidHz: 1400, dominance: 0.5 },
      bass: { energyRatio: 0.25, rmsDb: -20, subRatio: 0.6, dominance: 0.4 },
      drums: { energyRatio: 0.20, rmsDb: -19, transientDensity: 2.5, dominance: 0.4 },
      harmony: { energyRatio: 0.20, rmsDb: -21, stereoWidth: 0.5, dominance: 0.4 },
      estimatedBpm: 120,
      estimatedKey: 'C major',
      integratedLufs: -16,
      crestFactorDb: 9.5,
    }
  }

  // Séparation multi-bandes temporelle par filtres IIR cascadés :
  // - Bass : passe-bas < 180 Hz
  // - Vocals/Mid : passe-bande [180 Hz .. 4200 Hz]
  // - High/Presence : > 4200 Hz
  const dt = 1 / Math.max(8000, sampleRate)
  const rcBass = 1 / (2 * Math.PI * 180)
  const alphaBass = dt / (rcBass + dt)
  const rcHigh = 1 / (2 * Math.PI * 4200)
  const alphaHigh = dt / (rcHigh + dt)

  let bassLP = 0
  let midLP = 0
  let sumBassSq = 0
  let sumVocSq = 0
  let sumDrumSq = 0
  let sumHarmSq = 0
  let sumTotalSq = 0
  let peakAbs = 0

  const winSize = Math.max(128, Math.floor(sampleRate * 0.02))
  const onsetEnv: number[] = []
  let prevWinEnergy = 0
  let transientCount = 0

  for (let i = 0; i < n; i++) {
    const x = samples[i]
    sumTotalSq += x * x
    const absX = Math.abs(x)
    if (absX > peakAbs) peakAbs = absX

    bassLP += alphaBass * (x - bassLP)
    midLP += alphaHigh * (x - midLP)
    const midBand = midLP - bassLP
    const highBand = x - midLP

    sumBassSq += bassLP * bassLP
    sumVocSq += midBand * midBand * 0.62
    sumHarmSq += (midBand * 0.38 + highBand * 0.5) ** 2
    sumDrumSq += highBand * highBand * 0.5

    if (i % winSize === winSize - 1) {
      const winRms = Math.sqrt((bassLP * bassLP + highBand * highBand) * 0.5)
      const flux = Math.max(0, winRms - prevWinEnergy)
      onsetEnv.push(flux)
      if (flux > 0.035) transientCount++
      prevWinEnergy = winRms
    }
  }

  const totalEnergy = Math.max(1e-9, sumBassSq + sumVocSq + sumDrumSq + sumHarmSq)
  const vocRatio = Number((sumVocSq / totalEnergy).toFixed(3))
  const bassRatio = Number((sumBassSq / totalEnergy).toFixed(3))
  const drumRatio = Number((sumDrumSq / totalEnergy).toFixed(3))
  const harmRatio = Number(Math.max(0, 1 - vocRatio - bassRatio - drumRatio).toFixed(3))

  const totalRms = Math.sqrt(sumTotalSq / n)
  const integratedLufs = Number((20 * Math.log10(Math.max(1e-5, totalRms)) - 0.691).toFixed(1))
  const crestFactorDb = Number((20 * Math.log10(Math.max(1e-5, peakAbs) / Math.max(1e-5, totalRms))).toFixed(1))

  // Estimation du BPM par autocorrélation de l'enveloppe d'onset (entre 72 et 165 BPM)
  const envRate = sampleRate / winSize // ~50 Hz
  const minBpmLag = Math.max(2, Math.floor((envRate * 60) / 165))
  const maxBpmLag = Math.min(onsetEnv.length - 2, Math.floor((envRate * 60) / 72))
  let bestBpmLag = Math.floor((envRate * 60) / 120)
  let bestBpmCorr = 0
  for (let lag = minBpmLag; lag <= maxBpmLag; lag++) {
    let corr = 0
    for (let i = 0; i + lag < onsetEnv.length; i++) {
      corr += onsetEnv[i] * onsetEnv[i + lag]
    }
    if (corr > bestBpmCorr) {
      bestBpmCorr = corr
      bestBpmLag = lag
    }
  }
  const estimatedBpm = Math.round(Math.max(72, Math.min(165, (envRate * 60) / Math.max(1, bestBpmLag))))

  // Estimation de tonalité par profil d'énergie sur les 12 demi-tons (A4 = 440 Hz)
  const KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  const profile = extractVoiceAcousticProfile(samples.subarray(0, Math.min(n, sampleRate * 8)), sampleRate)
  const midiNote = Math.round(69 + 12 * Math.log2(Math.max(65, profile.f0MeanHz) / 440))
  const pitchClass = ((midiNote % 12) + 12) % 12
  const mode = profile.timbre.warmth >= 0.55 ? 'minor' : 'major'
  const estimatedKey = `${KEY_NAMES[pitchClass]} ${mode}`

  const durationSec = Math.max(0.5, n / sampleRate)

  return {
    vocals: {
      energyRatio: vocRatio,
      rmsDb: Number((integratedLufs + 20 * Math.log10(Math.max(0.05, vocRatio))).toFixed(1)),
      centroidHz: profile.spectralCentroidHz,
      dominance: Number(Math.min(1, vocRatio * 1.8).toFixed(2)),
    },
    bass: {
      energyRatio: bassRatio,
      rmsDb: Number((integratedLufs + 20 * Math.log10(Math.max(0.05, bassRatio))).toFixed(1)),
      subRatio: Number(Math.min(1, bassRatio * 1.5).toFixed(2)),
      dominance: Number(Math.min(1, bassRatio * 1.7).toFixed(2)),
    },
    drums: {
      energyRatio: drumRatio,
      rmsDb: Number((integratedLufs + 20 * Math.log10(Math.max(0.05, drumRatio))).toFixed(1)),
      transientDensity: Number((transientCount / durationSec).toFixed(2)),
      dominance: Number(Math.min(1, drumRatio * 2.0).toFixed(2)),
    },
    harmony: {
      energyRatio: harmRatio,
      rmsDb: Number((integratedLufs + 20 * Math.log10(Math.max(0.05, harmRatio))).toFixed(1)),
      stereoWidth: 0.65,
      dominance: Number(Math.min(1, harmRatio * 1.6).toFixed(2)),
    },
    estimatedBpm,
    estimatedKey,
    integratedLufs,
    crestFactorDb,
  }
}

/**
 * Compte les syllabes phonétiques françaises d'un vers et génère son patron rythmique.
 */
function analyzeFrenchLyricLine(line: string): { text: string; syllables: number; stressPattern: string } {
  const words = line.trim().split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const vowelIpas = new Set(['a', 'ɑ', 'ɑ̃', 'e', 'ɛ', 'ɛ̃', 'ə', 'i', 'o', 'ɔ', 'ɔ̃', 'ø', 'œ', 'œ̃', 'u', 'y'])
  let syllables = 0
  const stresses: string[] = []

  for (let wIdx = 0; wIdx < words.length; wIdx++) {
    const phones = phonemizeWord(words[wIdx])
    const wordVowels = phones.filter((p) => vowelIpas.has(p))
    const count = Math.max(1, wordVowels.length)
    syllables += count
    for (let s = 0; s < count; s++) {
      // En français, l'accent tonique tombe sur la dernière syllabe du mot/groupe
      stresses.push(s === count - 1 ? '1' : '0')
    }
  }
  return {
    text: line.trim(),
    syllables: Math.max(1, syllables),
    stressPattern: stresses.join(''),
  }
}

/**
 * Structure un texte lyrique ou un brief musical en plan de production multi-stems complet
 * (`MusicProductionStructure`) avec découpage en mesures, sections et métrique syllabique.
 */
export function buildMusicProductionPlan(
  lyricsOrPrompt: string,
  opts?: { bpm?: number; keySignature?: string; timeSignature?: '4/4' | '3/4' | '6/8' },
): MusicProductionStructure {
  const bpm = Math.max(60, Math.min(200, opts?.bpm ?? 118))
  const timeSignature = opts?.timeSignature ?? '4/4'
  const keySignature = opts?.keySignature ?? 'A minor'
  const beatsPerBar = timeSignature === '3/4' ? 3 : 4
  const barDurationSec = (60 / bpm) * beatsPerBar

  const rawLines = (lyricsOrPrompt || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)

  const blueprint: Array<{
    kind: MusicSectionKind
    label: string
    bars: number
    energyTarget: number
    activeStems: Array<'vocals' | 'bass' | 'drums' | 'harmony'>
  }> = [
    { kind: 'intro', label: 'Intro Atmosphérique', bars: 4, energyTarget: 0.35, activeStems: ['harmony', 'bass'] },
    { kind: 'verse', label: 'Couplet 1', bars: 8, energyTarget: 0.60, activeStems: ['vocals', 'bass', 'harmony'] },
    { kind: 'pre-chorus', label: 'Pré-Refrain (Montée)', bars: 4, energyTarget: 0.78, activeStems: ['vocals', 'bass', 'drums', 'harmony'] },
    { kind: 'chorus', label: 'Refrain Principal', bars: 8, energyTarget: 0.96, activeStems: ['vocals', 'bass', 'drums', 'harmony'] },
    { kind: 'bridge', label: 'Pont Harmonique', bars: 4, energyTarget: 0.68, activeStems: ['vocals', 'harmony'] },
    { kind: 'outro', label: 'Outro & Fade', bars: 4, energyTarget: 0.30, activeStems: ['harmony', 'bass'] },
  ]

  let currentBar = 1
  let currentSec = 0
  let lineCursor = 0

  const sections: MusicSectionPlan[] = blueprint.map((sec) => {
    const secDuration = sec.bars * barDurationSec
    const linesForSec: Array<{ text: string; syllables: number; stressPattern: string }> = []
    if (sec.activeStems.includes('vocals') && rawLines.length > 0) {
      const targetLineCount = sec.bars >= 8 ? 4 : 2
      for (let i = 0; i < targetLineCount; i++) {
        const l = rawLines[lineCursor % rawLines.length]
        lineCursor++
        linesForSec.push(analyzeFrenchLyricLine(l))
      }
    }
    const plan: MusicSectionPlan = {
      kind: sec.kind,
      label: sec.label,
      startBar: currentBar,
      bars: sec.bars,
      startSec: Number(currentSec.toFixed(2)),
      endSec: Number((currentSec + secDuration).toFixed(2)),
      energyTarget: sec.energyTarget,
      lyricsLines: linesForSec,
      activeStems: sec.activeStems,
    }
    currentBar += sec.bars
    currentSec += secDuration
    return plan
  })

  return {
    bpm,
    timeSignature,
    keySignature,
    totalDurationSec: Number(currentSec.toFixed(2)),
    sections,
  }
}

/**
 * Décode n'importe quel format audio (WebM, Ogg…) et ré-encode en WAV PCM 16-bit mono
 * après passage dans le pipeline DSP (suppression DC-offset, filtre passe-haut 75 Hz,
 * rognage intelligent des silences et normalisation -1 dBFS sans saturation).
 * Retourne également le profil acoustique extrait pour le clonage vocal zero-shot.
 */
async function encodeAsWavWithProfile(blob: Blob): Promise<{ wavBlob: Blob; profile: VoiceAcousticProfile }> {
  const tmpCtx = new AudioContext()
  try {
    const arrayBuffer = await blob.arrayBuffer()
    const audioBuffer = await tmpCtx.decodeAudioData(arrayBuffer)
    const sampleRate = audioBuffer.sampleRate

    let rawSamples: Float32Array
    if (audioBuffer.numberOfChannels > 1) {
      const ch0 = audioBuffer.getChannelData(0)
      const ch1 = audioBuffer.getChannelData(1)
      rawSamples = new Float32Array(ch0.length)
      for (let i = 0; i < ch0.length; i++) rawSamples[i] = (ch0[i] + ch1[i]) * 0.5
    } else {
      rawSamples = audioBuffer.getChannelData(0)
    }

    const samples = preprocessVoiceSamplesDSP(rawSamples, sampleRate)
    const profile = extractVoiceAcousticProfile(samples, sampleRate)

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

    return {
      wavBlob: new Blob([wavBuffer], { type: 'audio/wav' }),
      profile,
    }
  } finally {
    await tmpCtx.close()
  }
}

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
  const [acousticProfile, setAcousticProfile] = useState<VoiceAcousticProfile | null>(null)
  const [lastProsodyPlan, setLastProsodyPlan] = useState<ProsodyPlan | null>(null)

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
  const noiseFloorRef = useRef(0.006)
  const acousticProfileRef = useRef<VoiceAcousticProfile | null>(null)
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

  // Web Audio API — analyse spectrale TTS temps réel
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
    s = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    })
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

  /**
   * Analyse un échantillon audio de référence (clonage vocal zero-shot)
   * et met à jour l'empreinte acoustique active du hook.
   */
  const analyzeVoiceReference = useCallback(async (referenceBlob: Blob): Promise<VoiceAcousticProfile> => {
    const { profile } = await encodeAsWavWithProfile(referenceBlob)
    acousticProfileRef.current = profile
    if (mountedRef.current) setAcousticProfile(profile)
    return profile
  }, [])

  /**
   * Analyse un fichier/blob musical ou vocal en 4 stems + BPM + tonalité + LUFS.
   */
  const analyzeAudioStems = useCallback(async (audioBlob: Blob): Promise<StemSeparationProfile> => {
    const tmpCtx = new AudioContext()
    try {
      const arrayBuffer = await audioBlob.arrayBuffer()
      const audioBuffer = await tmpCtx.decodeAudioData(arrayBuffer)
      const ch0 = audioBuffer.getChannelData(0)
      return analyzeAudioStemsFromSamples(ch0, audioBuffer.sampleRate)
    } finally {
      await tmpCtx.close()
    }
  }, [])

  const doTranscribe = useCallback(async (blob: Blob) => {
    if (!mountedRef.current) return
    setP('transcribing')
    try {
      let audioBlob = blob
      try {
        const { wavBlob, profile } = await encodeAsWavWithProfile(blob)
        audioBlob = wavBlob
        if (profile.voicedRatio >= 0.12 && profile.durationSec >= 0.4) {
          acousticProfileRef.current = profile
          if (mountedRef.current) setAcousticProfile(profile)
        }
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
        if (acousticProfileRef.current) {
          fd.append('voice_profile', JSON.stringify(acousticProfileRef.current))
        }
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
        let zc = 0
        for (let i = 0; i < buf.length; i++) {
          const s = buf[i]
          sum += s * s
          if (i > 0 && ((buf[i - 1] >= 0 && s < 0) || (buf[i - 1] < 0 && s >= 0))) zc++
        }
        const rms = Math.sqrt(sum / buf.length)
        const zcrRatio = zc / buf.length

        // Adaptation continue du plancher de bruit ambiant hors parole
        if (!spokeRef.current && rms < NOISE * 1.4) {
          noiseFloorRef.current = noiseFloorRef.current * 0.96 + rms * 0.04
        }

        setVolumeLevel(Math.min(1, rms * 8))
        const now = Date.now()
        const echoActive = now < echoGuardRef.current
        const adaptiveHigh = Math.max(NOISE, noiseFloorRef.current * 2.4)
        const adaptiveLow = Math.max(NOISE_LOW, noiseFloorRef.current * 1.6)
        const th = echoActive ? NOISE_ECHO : (spokeRef.current ? adaptiveLow : adaptiveHigh)
        // Rejet des transitoires purement haute fréquence non-vocaux (ZCR > 0.45)
        const isPlausibleVoice = zcrRatio < 0.45 || rms > th * 1.8

        if (rms >= th && isPlausibleVoice) {
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

    // 1. Calcul du plan prosodique et normalisation phonétique française
    const prosodyPlan = extractProsodyPlan(text, languageRef.current, acousticProfileRef.current)
    const normalizedText = prosodyPlan.normalizedText || text.trim()
    setLastProsodyPlan(prosodyPlan)

    // 2. Pré-génération immédiate des cues Rhubarb par règles phonétiques + liaisons
    //    (sera remplacé ou recalibré dès que Kokoro renvoie ses phonèmes ou sa durée audio)
    phonemeCuesRef.current = generateRhubarbCuesFromText(
      normalizedText,
      prosodyPlan.estimatedDurationSec,
    )

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

    // Animation amplitude & formants F1/F2 synchronisée aux cues Rhubarb et au temps audio réel
    const startAmplitudeAnimation = () => {
      const startWallSec = performance.now() / 1000
      const tick = () => {
        if (spkIdRef.current !== id) {
          setSpeakingAmplitude(0); formantsRef.current = { low: 0, mid: 0 }; rafRef.current = 0; return
        }
        const audioEl = audioRef.current
        const currentSec = (audioEl && !audioEl.paused && audioEl.currentTime > 0)
          ? audioEl.currentTime
          : (performance.now() / 1000) - startWallSec

        // Recherche de la cue Rhubarb active à l'instant currentSec
        const cues = phonemeCuesRef.current
        let activeCue: RhubarbCue | null = null
        for (let i = cues.length - 1; i >= 0; i--) {
          if (currentSec >= cues[i].start) {
            activeCue = cues[i]
            break
          }
        }

        const viseme = activeCue?.value ?? 'A'
        if (viseme === 'X') {
          setSpeakingAmplitude(0.03)
          formantsRef.current = { low: 0.02, mid: 0.02 }
        } else {
          // Enveloppe syllabique naturelle (attaque franche, maintien doux, relâchement)
          const cueDur = Math.max(0.04, (activeCue?.end ?? currentSec + 0.08) - (activeCue?.start ?? currentSec))
          const relPos = Math.max(0, Math.min(1, (currentSec - (activeCue?.start ?? currentSec)) / cueDur))
          const syllableEnv = Math.sin(relPos * Math.PI) * 0.35 + 0.65
          const formants = rhubarbVisemeToFormants(viseme, syllableEnv * prosodyPlan.energy)
          const amp = Math.max(0.12, Math.min(1, (formants.low * 0.65 + formants.mid * 0.45)))
          setSpeakingAmplitude(amp)
          formantsRef.current = formants
        }
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
      const ttsPayload: Record<string, unknown> = {
        text: normalizedText.slice(0, 2000),
        raw_text: text.slice(0, 2000),
        lang: languageRef.current,
        speed: prosodyPlan.rate,
        pitch: prosodyPlan.pitch,
        emotion: prosodyPlan.emotion,
      }
      // Si un avatar image est configure, on demande au bridge de generer aussi le MP4 talking-head
      if (avatarImageRef.current) {
        ttsPayload.avatar = avatarImageRef.current
      }
      // Persona vocal Aurora — bridge mappe lyra-soft -> Denise, iris-bright -> Brigitte, etc.
      if (voicePersonaRef.current) {
        ttsPayload.voice = voicePersonaRef.current
      }
      // Conditionnement acoustique zero-shot si une empreinte vocale de référence est disponible
      if (acousticProfileRef.current) {
        ttsPayload.voice_profile = {
          f0_mean_hz: acousticProfileRef.current.f0MeanHz,
          register: acousticProfileRef.current.register,
          syllables_per_sec: acousticProfileRef.current.syllablesPerSec,
          prosody_signature: acousticProfileRef.current.prosodySignature,
        }
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
          if (data.phonemes?.length) {
            phonemeCuesRef.current = data.phonemes
          }
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

            // Recalibrage frame-accurate des visèmes Rhubarb dès que la durée réelle du WAV est connue
            audio.onloadedmetadata = () => {
              if (audio && Number.isFinite(audio.duration) && audio.duration > 0.1) {
                phonemeCuesRef.current = recalibrateRhubarbCues(phonemeCuesRef.current, audio.duration)
              }
            }

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
              audio!.onloadedmetadata = null
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
              if (audio && Number.isFinite(audio.duration) && audio.duration > 0.1) {
                phonemeCuesRef.current = recalibrateRhubarbCues(phonemeCuesRef.current, audio.duration)
              }
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
            const maxMs = Math.max(8000, normalizedText.length * 120)
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
    console.log('[TTS] Web Speech API fallback engaged, text:', normalizedText.slice(0, 60))
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
        const utter = new SpeechSynthesisUtterance(normalizedText)
        const langCode = languageRef.current === 'en' ? 'en-US' : 'fr-FR'
        utter.lang = langCode
        utter.rate = prosodyPlan.rate
        utter.pitch = prosodyPlan.pitch
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

        const maxMs = Math.max(6000, normalizedText.length * 90)
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
    // Phase 3 — Profilage acoustique zero-shot, prosodie FR & structuration musicale
    acousticProfile,
    acousticProfileRef,
    lastProsodyPlan,
    analyzeVoiceReference,
    analyzeAudioStems,
    buildMusicProductionPlan,
    normalizeFrenchProsodyAndPhonetics,
  }
}

