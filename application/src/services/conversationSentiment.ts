// Analyseur de sentiment FR léger + détecteur de digression.
//
// Pas de modèle ML. Lexique manuel + règles de pondération + détection de
// négations. Suffisant pour : "Aurora détecte que Juan est frustré",
// "le sujet a changé entre les 2 dernières questions".

const POSITIVE_LEX_FR: Record<string, number> = {
  bien: 1, super: 2, génial: 2.5, top: 1.5, parfait: 2,
  excellent: 2.5, magnifique: 2.5, beau: 1.5, belle: 1.5, joli: 1,
  agréable: 1.5, fun: 1, amusant: 1.5, intéressant: 1.5, passionnant: 2,
  cool: 1.5, sympa: 1.5, plaisir: 2, content: 2, heureux: 2.5, ravi: 2.5,
  merci: 1.5, bravo: 2, félicitations: 2.5, "j'adore": 2.5, "j'aime": 1.5,
  réussi: 2, victoire: 2, gagné: 1.5, brillant: 2, formidable: 2.5,
  fantastique: 2.5, incroyable: 2,
}

const NEGATIVE_LEX_FR: Record<string, number> = {
  mauvais: -1.5, nul: -2, horrible: -2.5, terrible: -2.5, affreux: -2.5,
  triste: -2, déçu: -2, frustré: -2, fâché: -2, énervé: -2, agacé: -1.5,
  chiant: -2, pénible: -1.5, ennuyeux: -1.5, ennui: -1, lourd: -1,
  raté: -2, échec: -2, échoué: -2, perdu: -1.5, cassé: -1.5, bug: -1.5,
  problème: -1, erreur: -1, plante: -1.5,
  difficile: -1, impossible: -1.5, compliqué: -1, dur: -1,
  "je déteste": -2.5, déteste: -2, hais: -2.5, beurk: -2,
  bof: -1.5, faux: -1,
}

const NEGATION_TOKENS = new Set(['pas', 'plus', 'jamais', 'non', 'aucun', 'sans', 'ni'])

export type SentimentScore = {
  /** Score signé [-2.5..+2.5] approximatif. */
  score: number
  /** Catégorisation. */
  polarity: 'positive' | 'negative' | 'neutral' | 'mixed'
  /** Intensité [0..1]. */
  intensity: number
  /** Tokens qui ont contribué. */
  positiveTokens: Array<{ token: string; weight: number }>
  negativeTokens: Array<{ token: string; weight: number }>
  /** Négations qui ont inversé un score. */
  negations: string[]
  /** Nombre de marques d'emphase (!, MAJ, ?). */
  emphasis: number
}

function normalise(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

function tokenise(text: string): string[] {
  return text.split(/\s+/).map((t) => t.replace(/[.,;:!?()«»"']/g, '')).filter(Boolean)
}

export function analyzeSentiment(text: string): SentimentScore {
  if (!text || text.trim().length === 0) {
    return { score: 0, polarity: 'neutral', intensity: 0, positiveTokens: [], negativeTokens: [], negations: [], emphasis: 0 }
  }

  // Lexiques normalisés (accents strippés pour matcher).
  const posIndex = new Map<string, number>()
  for (const [k, v] of Object.entries(POSITIVE_LEX_FR)) posIndex.set(normalise(k), v)
  const negIndex = new Map<string, number>()
  for (const [k, v] of Object.entries(NEGATIVE_LEX_FR)) negIndex.set(normalise(k), v)

  const normalised = normalise(text)
  const tokens = tokenise(normalised)
  let score = 0
  const positiveTokens: SentimentScore['positiveTokens'] = []
  const negativeTokens: SentimentScore['negativeTokens'] = []
  const negations: string[] = []

  for (let i = 0; i < tokens.length; i += 1) {
    const tok = tokens[i]
    let weight = posIndex.get(tok) ?? negIndex.get(tok) ?? 0
    if (weight === 0) continue

    // Vérifie une négation dans les 3 tokens précédents.
    let negated = false
    for (let j = Math.max(0, i - 3); j < i; j += 1) {
      if (NEGATION_TOKENS.has(tokens[j])) {
        negated = true
        negations.push(tokens[j])
        break
      }
    }
    if (negated) weight = -weight

    score += weight
    if (weight > 0) positiveTokens.push({ token: tok, weight })
    else negativeTokens.push({ token: tok, weight })
  }

  // Emphase : !, MAJ entières, ?
  const emphasis = (text.match(/[!?]+/g)?.length ?? 0) + (text.match(/\b[A-Z]{3,}\b/g)?.length ?? 0)
  // Amplification : chaque marque d'emphase amplifie le score absolu de 20%.
  const amplifier = 1 + emphasis * 0.2
  const amplified = score * amplifier

  const intensity = Math.min(1, Math.abs(amplified) / 5)
  let polarity: SentimentScore['polarity']
  if (positiveTokens.length > 0 && negativeTokens.length > 0) polarity = 'mixed'
  else if (amplified > 0.5) polarity = 'positive'
  else if (amplified < -0.5) polarity = 'negative'
  else polarity = 'neutral'

  return {
    score: amplified,
    polarity,
    intensity,
    positiveTokens,
    negativeTokens,
    negations,
    emphasis,
  }
}

// --- Détection de digression -----------------------------------------------
//
// Comparer 2 messages successifs : si leurs sets de tokens distinctifs (hors
// stopwords) ont une intersection vide ou très faible, le sujet a changé.

const STOPWORDS_FR_DIGRESS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'a', 'à',
  'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
  'que', 'qui', 'quoi', 'est', 'sont', 'ce', 'cette', 'ces', 'mais',
  'plus', 'moins', 'pas', 'donc', 'car', 'comme', 'aussi', 'pour',
  'sur', 'avec', 'dans', 'sans', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
  'son', 'sa', 'ses', 'votre', 'vos', 'leur', 'leurs', 'en',
])

function distinctiveTokens(text: string): Set<string> {
  return new Set(
    tokenise(normalise(text)).filter((t) => t.length >= 3 && !STOPWORDS_FR_DIGRESS.has(t)),
  )
}

export type DigressionDetection = {
  /** Score de similarité [0..1]. */
  similarity: number
  /** True si le sujet a changé. */
  digressed: boolean
  /** Tokens partagés. */
  sharedTokens: string[]
  /** Type de digression. */
  kind: 'continuation' | 'tangent' | 'topic-shift'
}

export function detectDigression(previousMessage: string, currentMessage: string): DigressionDetection {
  const setA = distinctiveTokens(previousMessage)
  const setB = distinctiveTokens(currentMessage)
  if (setA.size === 0 || setB.size === 0) {
    return { similarity: 0, digressed: false, sharedTokens: [], kind: 'continuation' }
  }
  let inter = 0
  const shared: string[] = []
  for (const t of setA) {
    if (setB.has(t)) {
      inter += 1
      shared.push(t)
    }
  }
  const union = new Set<string>()
  for (const t of setA) union.add(t)
  for (const t of setB) union.add(t)
  const similarity = inter / union.size

  // Aussi : si un token "marqueur" est partagé (mot-clé concept), on est
  // en continuation même si Jaccard global est faible — ce qui arrive
  // quand le user reformule avec beaucoup de variations.
  let kind: DigressionDetection['kind']
  if (similarity > 0.15 || (shared.length >= 1 && shared.some((t) => t.length >= 5))) kind = 'continuation'
  else if (similarity > 0.05 || shared.length >= 1) kind = 'tangent'
  else kind = 'topic-shift'

  return {
    similarity,
    digressed: kind === 'topic-shift',
    sharedTokens: shared,
    kind,
  }
}

/**
 * Compare une question à un contexte multi-messages plus large : utile pour
 * détecter si le user revient sur un sujet précédent (callback) ou démarre
 * complètement autre chose.
 */
export function checkContextRelevance(question: string, context: string[]): { topMatch: number; matchedTokens: string[] } {
  const qSet = distinctiveTokens(question)
  let topMatch = 0
  let topShared: string[] = []
  for (const ctx of context) {
    const cSet = distinctiveTokens(ctx)
    if (qSet.size === 0 || cSet.size === 0) continue
    let inter = 0
    const shared: string[] = []
    for (const t of qSet) if (cSet.has(t)) { inter += 1; shared.push(t) }
    const union = new Set<string>([...qSet, ...cSet])
    const sim = inter / union.size
    if (sim > topMatch) {
      topMatch = sim
      topShared = shared
    }
  }
  return { topMatch, matchedTokens: topShared }
}
