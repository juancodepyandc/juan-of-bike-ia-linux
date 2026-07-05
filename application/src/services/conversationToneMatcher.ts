// Détecte le registre de langage du user et adapte la réponse Aurora pour
// matcher : si Juan tutoie + verlan, on répond pareil ; s'il est en mode
// formel ("Pourriez-vous, s'il vous plaît…"), on répond en vouvoiement
// professionnel.
//
// Pure compute FR. Lexique manuel.

export type ToneRegister = {
  /** formal/casual/familiar score [0..1]. */
  formality: number
  /** Tutoiement (>0.5) vs vouvoiement. */
  tutoiement: number
  /** Présence de marqueurs verlan/argot. */
  argot: number
  /** Niveau d'émotion détecté (cf. sentiment, ici amplifié par !!! ???). */
  emotionalLoad: number
  /** Hint pour Aurora : verbe à utiliser. */
  recommendedAddress: 'tu' | 'vous' | 'on'
  /** Style global suggéré. */
  recommendedStyle: 'professional' | 'conversational' | 'casual' | 'enthusiastic'
}

const TUTOIEMENT_MARKERS = new Set([
  'tu', 'te', 'toi', 'ton', 'ta', 'tes', "t'as", "t'es", 'tutoie',
])

const VOUVOIEMENT_MARKERS = new Set([
  'vous', 'votre', 'vos', 'vouvoyer', "qu'avez-vous", 'pourriez-vous',
  'auriez-vous', 'monsieur', 'madame', "s'il vous plaît", 'cordialement',
])

const FORMAL_LEXICON = new Set([
  'pourriez', 'voudriez', 'auriez', 'seriez', 'aimerais', 'souhaiterais',
  'sollicite', 'requiers', 'demande', 'concernant', 'relatif', 'objet',
  'préalable', 'effectuer', 'procéder', 'considérer', 'cordialement',
  'sincèrement', 'salutations', 'respectueusement', 'monsieur', 'madame',
  'mademoiselle', 'professeur', 'directeur',
])

const CASUAL_LEXICON = new Set([
  'salut', 'coucou', 'hey', 'yo', 'ouais', 'wesh', 'bah', 'ben',
  'truc', 'machin', 'genre', 'grave', 'trop', 'mdr', 'lol', 'ptdr',
  'cool', 'sympa', 'chouette',
])

const ARGOT_LEXICON = new Set([
  'meuf', 'mec', 'reuf', 'reum', 'frérot', 'frere', 'gros', 'pote',
  'kiffer', 'kiffe', 'chelou', 'relou', 'ouf', 'zoner', 'taffer',
  'cramer', 'capter', 'crever', 'bouffer', 'crécher', 'décrocher',
])

function normaliseToken(t: string): string {
  return t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

// Normalise les sets pour matcher les tokens sans accents.
const TUTOIEMENT_NORM = new Set(Array.from(TUTOIEMENT_MARKERS).map(normaliseToken))
const VOUVOIEMENT_NORM = new Set(Array.from(VOUVOIEMENT_MARKERS).map(normaliseToken))
const FORMAL_NORM = new Set(Array.from(FORMAL_LEXICON).map(normaliseToken))
const CASUAL_NORM = new Set(Array.from(CASUAL_LEXICON).map(normaliseToken))
const ARGOT_NORM = new Set(Array.from(ARGOT_LEXICON).map(normaliseToken))

function tokenize(text: string): string[] {
  // Split sur ponctuation + tirets + apostrophes pour traiter "pourriez-vous"
  // comme 2 tokens "pourriez" + "vous".
  return text.split(/[\s,.;:!?()«»"'’-]+/).filter(Boolean).map(normaliseToken)
}

/**
 * Détermine le registre de langage d'un message.
 */
export function analyseTone(text: string): ToneRegister {
  if (!text || text.trim().length === 0) {
    return {
      formality: 0.5,
      tutoiement: 0.5,
      argot: 0,
      emotionalLoad: 0,
      recommendedAddress: 'tu',
      recommendedStyle: 'conversational',
    }
  }

  const tokens = tokenize(text)
  let tuCount = 0
  let vousCount = 0
  let formalCount = 0
  let casualCount = 0
  let argotCount = 0

  for (const t of tokens) {
    if (TUTOIEMENT_NORM.has(t)) tuCount += 1
    if (VOUVOIEMENT_NORM.has(t)) vousCount += 1
    if (FORMAL_NORM.has(t)) formalCount += 1
    if (CASUAL_NORM.has(t)) casualCount += 1
    if (ARGOT_NORM.has(t)) argotCount += 1
  }

  const totalAddress = tuCount + vousCount
  const tutoiement = totalAddress === 0 ? 0.5 : tuCount / totalAddress

  const totalRegister = formalCount + casualCount + argotCount
  let formality = 0.5
  if (totalRegister > 0) {
    formality = (formalCount + 0.3 * vousCount) / (totalRegister + tuCount + vousCount + 0.001)
    formality = Math.min(1, Math.max(0, formality))
  } else if (totalAddress > 0) {
    formality = vousCount / totalAddress
  }

  // Emotional load : ! et ? répétés, MAJ
  const exclam = (text.match(/[!]+/g) || []).reduce((s, x) => s + x.length, 0)
  const interrog = (text.match(/[?]+/g) || []).reduce((s, x) => s + x.length, 0)
  const caps = (text.match(/\b[A-ZÉÈÀÂÊÎÔ]{3,}\b/g) || []).length
  const emotionalLoad = Math.min(1, (exclam + interrog * 0.5 + caps * 2) / 10)

  const argot = totalRegister === 0 ? 0 : argotCount / totalRegister

  // Choix de l'adresse.
  let recommendedAddress: 'tu' | 'vous' | 'on' = 'tu'
  if (vousCount > tuCount && formality > 0.5) recommendedAddress = 'vous'
  else if (tutoiement > 0.5) recommendedAddress = 'tu'
  else recommendedAddress = 'tu' // par défaut pour Juan

  // Style global. Seuil 0.55 pour "professional" — une phrase typique
  // formelle avec "Monsieur" + "pourriez-vous" + "cordialement" ne dépasse
  // pas naturellement 0.7 à cause de la dilution par tokens vide.
  let recommendedStyle: ToneRegister['recommendedStyle']
  if (formality > 0.55 && (recommendedAddress === 'vous' || formalCount >= 2)) recommendedStyle = 'professional'
  else if (emotionalLoad > 0.4 || casualCount > 1) recommendedStyle = 'enthusiastic'
  else if (argot > 0.3) recommendedStyle = 'casual'
  else recommendedStyle = 'conversational'

  return {
    formality,
    tutoiement,
    argot,
    emotionalLoad,
    recommendedAddress,
    recommendedStyle,
  }
}

/**
 * Génère un prefix de système-prompt qui guide Aurora pour matcher le tone
 * détecté. À injecter au début du message system.
 */
export function generateSystemHint(tone: ToneRegister): string {
  const parts: string[] = []
  if (tone.recommendedAddress === 'vous') {
    parts.push('Tu vouvoies l\'utilisateur, ton registre est professionnel.')
  } else {
    parts.push('Tu tutoies l\'utilisateur.')
  }
  switch (tone.recommendedStyle) {
    case 'professional':
      parts.push('Style soigné, phrases bien construites, pas d\'abréviations.')
      break
    case 'conversational':
      parts.push('Style naturel, conversationnel, comme à un ami curieux.')
      break
    case 'casual':
      parts.push('Style décontracté, tu peux utiliser de l\'argot léger si pertinent.')
      break
    case 'enthusiastic':
      parts.push('Style énergique, expressif, marque l\'enthousiasme si le sujet le mérite.')
      break
  }
  if (tone.emotionalLoad > 0.5) {
    parts.push('L\'utilisateur est expressif/émotionnel — accuse réception du ressenti avant la réponse factuelle.')
  }
  return parts.join(' ')
}

/**
 * Compare 2 textes et dit lequel est plus formel. Utile pour repérer
 * un swap de registre intra-conversation.
 */
export function compareFormality(textA: string, textB: string): { aMoreFormal: boolean; delta: number } {
  const toneA = analyseTone(textA)
  const toneB = analyseTone(textB)
  return {
    aMoreFormal: toneA.formality > toneB.formality,
    delta: Math.abs(toneA.formality - toneB.formality),
  }
}
