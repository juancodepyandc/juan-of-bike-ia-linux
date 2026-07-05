// Prosodie FR : intonation, pauses, accent tonique.
//
// Règles déterministes :
//   1. Phrase interrogative → courbe montante en fin (last 30 % +2 demi-tons).
//   2. Phrase exclamative → courbe + amplitude (energy boost 1.4× sur les mots
//      portant l'emphase).
//   3. Virgule → pause 200 ms ; point → 500 ms ; ; ! ? → 600 ms.
//   4. Liaison phonétique (cf. voiceFrPhonemizer) → 0 pause entre mots.
//   5. Mot précédé d'un déterminant emphatique ("très", "incroyable") → boost.
//   6. Accent tonique FR = sur la dernière syllabe non-muette d'un groupe
//      rythmique (3-7 syllabes).

export type ProsodicSegment = {
  /** Texte du segment (mot, ponctuation, ou bloc). */
  text: string
  /** Type. */
  kind: 'word' | 'punctuation' | 'pause'
  /** Durée estimée (ms). */
  durationMs: number
  /** Variation de pitch en demi-tons (relatif à la base). */
  pitchShiftSemitones: number
  /** Multiplicateur d'énergie (1 = normal). */
  energyGain: number
  /** True si la dernière syllabe porte l'accent rythmique. */
  hasStress: boolean
}

export type ProsodicAnalysis = {
  segments: ProsodicSegment[]
  /** Type global de phrase. */
  sentenceKind: 'statement' | 'question' | 'exclamation' | 'mixed'
  /** Durée totale (ms). */
  totalDurationMs: number
}

const EMPHATIC_INTENSIFIERS = new Set([
  'très', 'tres', 'super', 'extrêmement', 'extremement', 'totalement',
  'absolument', 'vraiment', 'incroyablement', 'tellement', 'completement',
  'complètement', 'fortement', 'énormément', 'enormement',
])

const PAUSE_DURATIONS: Record<string, number> = {
  ',': 200,
  ';': 350,
  ':': 350,
  '.': 500,
  '?': 600,
  '!': 600,
  '…': 700,
  '...': 700,
}

const WORD_DURATION_MS = (word: string) => {
  // ~150-200 ms par syllabe FR moyenne. Heuristique : 1 voyelle = 1 syllabe.
  const syllables = Math.max(1, (word.match(/[aeiouyàâäéèêëïîôùûüœ]+/gi) ?? []).length)
  return syllables * 170
}

/**
 * Tokenise un texte FR en respectant la ponctuation.
 * Préserve l'ordre, ne touche pas à la casse.
 */
function tokeniseWithPunct(text: string): Array<{ token: string; isPunct: boolean }> {
  // Inclut chiffres (point décimal optionnel) + lettres FR + apostrophes + tirets.
  const re = /([.,;:!?…]+|\d+(?:[.,]\d+)?|[a-zA-Zàâäéèêëïîôùûüçœæ]+(?:[''-][a-zA-Zàâäéèêëïîôùûüçœæ]+)*)/g
  const out: Array<{ token: string; isPunct: boolean }> = []
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) != null) {
    const tok = m[1]
    const isPunct = /^[.,;:!?…]+$/.test(tok)
    out.push({ token: tok, isPunct })
  }
  return out
}

/**
 * Analyse la prosodie d'une phrase FR.
 */
export function analyseProsody(text: string): ProsodicAnalysis {
  const tokens = tokeniseWithPunct(text)
  const segments: ProsodicSegment[] = []

  // Détecte le type de phrase d'après la ponctuation finale.
  const finalPunct = tokens[tokens.length - 1]?.isPunct ? tokens[tokens.length - 1].token : '.'
  const sentenceKind: ProsodicAnalysis['sentenceKind'] = finalPunct.includes('?')
    ? 'question'
    : finalPunct.includes('!') ? 'exclamation' : 'statement'

  // Compte les mots non-ponctuation pour calcul de l'index du group rhythmique.
  const wordIndices: number[] = []
  for (let i = 0; i < tokens.length; i += 1) {
    if (!tokens[i].isPunct) wordIndices.push(i)
  }
  const wordCount = wordIndices.length

  // Index du dernier mot (porte l'accent + variation pitch finale).
  const lastWordTokenIdx = wordIndices[wordIndices.length - 1] ?? -1

  for (let i = 0; i < tokens.length; i += 1) {
    const tok = tokens[i]
    if (tok.isPunct) {
      const pauseMs = PAUSE_DURATIONS[tok.token] ?? PAUSE_DURATIONS[tok.token[0]] ?? 200
      segments.push({
        text: tok.token,
        kind: 'pause',
        durationMs: pauseMs,
        pitchShiftSemitones: 0,
        energyGain: 1,
        hasStress: false,
      })
      continue
    }

    const wordPositionFromEnd = lastWordTokenIdx - i
    const isLastWord = i === lastWordTokenIdx
    // L'accent rythmique tombe sur la dernière syllabe accentuable du groupe.
    // Approximation : dernier mot de la phrase OU mot précédant une virgule.
    const nextTok = tokens[i + 1]
    const beforeComma = nextTok && nextTok.isPunct && /[,;:]/.test(nextTok.token)
    const hasStress = isLastWord || Boolean(beforeComma)

    // Pitch shift : question → courbe montante sur les 30% finaux.
    let pitchShift = 0
    if (sentenceKind === 'question' && wordPositionFromEnd >= 0 && wordPositionFromEnd < Math.ceil(wordCount * 0.3)) {
      pitchShift = 0.5 + (Math.ceil(wordCount * 0.3) - wordPositionFromEnd) * 0.5
    }
    if (sentenceKind === 'exclamation' && isLastWord) {
      pitchShift = -1 // descente finale "boum"
    }

    // Énergie : intensifier précédent → boost le suivant.
    let energyGain = 1
    if (i > 0 && !tokens[i - 1].isPunct && EMPHATIC_INTENSIFIERS.has(tokens[i - 1].token.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''))) {
      energyGain = 1.4
    }
    if (sentenceKind === 'exclamation') energyGain *= 1.2

    segments.push({
      text: tok.token,
      kind: 'word',
      durationMs: WORD_DURATION_MS(tok.token),
      pitchShiftSemitones: pitchShift,
      energyGain,
      hasStress,
    })
  }

  const totalDurationMs = segments.reduce((a, s) => a + s.durationMs, 0)
  return { segments, sentenceKind, totalDurationMs }
}

/**
 * Détecte les mots-clés à mettre en emphase pour qu'Aurora les prononce
 * avec accent tonique fort. Heuristique : mots > 5 lettres, hors stopwords,
 * ou précédés d'un intensifier.
 */
const VOICE_STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou',
  'que', 'qui', 'quoi', 'comme', 'aussi', 'pour', 'sur',
  'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
])

export type EmphasisHint = {
  word: string
  index: number
  reason: 'long-content-word' | 'after-intensifier' | 'capital-letter' | 'numeric'
}

export function detectEmphasisWords(text: string): EmphasisHint[] {
  const tokens = tokeniseWithPunct(text).filter((t) => !t.isPunct)
  const hints: EmphasisHint[] = []
  for (let i = 0; i < tokens.length; i += 1) {
    const w = tokens[i].token
    const wn = w.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    if (VOICE_STOPWORDS.has(wn)) continue
    if (/\d/.test(w)) {
      hints.push({ word: w, index: i, reason: 'numeric' })
      continue
    }
    if (/^[A-ZÉÈÀÂÊÎÔ]{2,}/.test(w)) {
      hints.push({ word: w, index: i, reason: 'capital-letter' })
      continue
    }
    if (i > 0 && EMPHATIC_INTENSIFIERS.has(tokens[i - 1].token.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''))) {
      hints.push({ word: w, index: i, reason: 'after-intensifier' })
      continue
    }
    if (w.length >= 6) {
      hints.push({ word: w, index: i, reason: 'long-content-word' })
    }
  }
  return hints
}

/**
 * Génère une chaîne SSML compatible Piper/eSpeak avec balises <prosody>
 * pour pitch + rate, et <break> pour pauses. Utile à passer directement
 * à un TTS qui supporte SSML.
 */
export function generateSsml(text: string, baseRate = 1.0): string {
  const analysis = analyseProsody(text)
  const parts: string[] = ['<speak>']
  for (const seg of analysis.segments) {
    if (seg.kind === 'pause') {
      parts.push(`<break time="${seg.durationMs}ms"/>`)
      continue
    }
    const pitch = seg.pitchShiftSemitones !== 0 ? ` pitch="${seg.pitchShiftSemitones > 0 ? '+' : ''}${seg.pitchShiftSemitones.toFixed(1)}st"` : ''
    const rate = baseRate !== 1.0 ? ` rate="${(baseRate * 100).toFixed(0)}%"` : ''
    const volume = seg.energyGain !== 1 ? ` volume="${seg.energyGain > 1 ? '+' : ''}${(Math.log2(seg.energyGain) * 6).toFixed(1)}dB"` : ''
    const open = pitch || rate || volume ? `<prosody${pitch}${rate}${volume}>` : ''
    const close = pitch || rate || volume ? '</prosody>' : ''
    parts.push(open + escapeSsml(seg.text) + close)
  }
  parts.push('</speak>')
  return parts.join('')
}

function escapeSsml(text: string): string {
  return text.replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[c]!))
}
