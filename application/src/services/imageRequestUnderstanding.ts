/**
 * Compréhension d'une demande du module Image contre la session en cours.
 *
 * Le module décidait « nouvelle image » ou « retouche de l'image affichée » avec des expressions
 * régulières : un mot attendu déclenchait une action, une phrase tournée autrement partait dans le
 * mauvais sens (« je la veux de nuit » sans verbe de retouche, « fais un chat » après un chien…).
 * Ici le modèle de langage lit la phrase avec ce que l'utilisateur voit à l'écran et les derniers
 * échanges, et rend une décision structurée. Quand la demande est réellement ambiguë, on POSE la
 * question au lieu de deviner. Sans modèle joignable, la lecture le dit et la décision par
 * expressions reste celle qui s'applique : jamais une lecture inventée.
 */
import type { ImageEditMode, ParsedImageIntent } from '../utils/imagePromptParser.ts'
import { parseImageIntent, withEditMode } from '../utils/imagePromptParser.ts'

export type ImageIntention = 'creation' | 'retouche' | 'ambigu'

export type ImageRequestReading = {
  source: 'llm' | 'indisponible'
  intention: ImageIntention
  confiance: number
  sujet: string
  changements: string[]
  aConserver: string[]
  question?: string
  options?: string[]
  raison?: string
}

export type ImageSessionContext = {
  hasDisplayedImage: boolean
  hasAttachedImage: boolean
  /** demandes précédentes de la session, de la plus ancienne à la plus récente */
  previousRequests: string[]
}

const CONSIGNE = [
  "Tu lis une demande adressée à un générateur d'images, en tenant compte de ce que l'utilisateur voit déjà.",
  'Réponds UNIQUEMENT par un objet JSON de cette forme :',
  '{"intention":"creation|retouche|ambigu","confiance":0.0,"sujet":"...","changements":["..."],"a_conserver":["..."],"question":"...","options":["...","..."]}',
  "- creation : la demande décrit une NOUVELLE image (un autre sujet, ou une scène sans lien avec l'image affichée).",
  "- retouche : la demande modifie l'image affichée ou jointe (attribut, style, décor, lumière, ajout, retrait, cadrage…), même sans verbe de modification (« de nuit », « en hiver », « plus grand »).",
  "- Si la demande installe un SUJET PRINCIPAL ou une SCÈNE différents de ceux de l'image affichée (un autre animal, un autre objet, un autre lieu), c'est une creation, même si elle commence par « ajoute » ou « mets » ; si elle garde le sujet et la scène en y changeant ou ajoutant quelque chose, c'est une retouche.",
  "- ambigu : les deux lectures restent plausibles après cette règle ; écris alors une question courte en français et deux options claires.",
  '- confiance entre 0 et 1.',
  "- sujet : ce que l'image finale doit montrer. changements : ce qui doit changer. a_conserver : ce qui doit rester identique.",
  'Pas de texte hors du JSON.',
].join('\n')

function extraireJson(texte: string): Record<string, unknown> | null {
  const debut = texte.indexOf('{')
  const fin = texte.lastIndexOf('}')
  if (debut < 0 || fin <= debut) return null
  try {
    const valeur = JSON.parse(texte.slice(debut, fin + 1))
    return valeur && typeof valeur === 'object' && !Array.isArray(valeur) ? valeur as Record<string, unknown> : null
  } catch {
    return null
  }
}

const textes = (valeur: unknown): string[] =>
  Array.isArray(valeur) ? valeur.filter((v): v is string => typeof v === 'string' && v.trim().length > 0).map((v) => v.trim()).slice(0, 8) : []

export function indisponible(raison: string): ImageRequestReading {
  return { source: 'indisponible', intention: 'ambigu', confiance: 0, sujet: '', changements: [], aConserver: [], raison }
}

/** Valide la réponse du modèle contre le contrat ; une réponse hors contrat n'est pas une lecture. */
export function validerLecture(brut: unknown): ImageRequestReading {
  if (!brut || typeof brut !== 'object') return indisponible('réponse hors contrat')
  const r = brut as Record<string, unknown>
  const intention = r.intention
  if (intention !== 'creation' && intention !== 'retouche' && intention !== 'ambigu') return indisponible('intention hors contrat')
  const confiance = typeof r.confiance === 'number' && Number.isFinite(r.confiance) ? Math.min(1, Math.max(0, r.confiance)) : 0.5
  const question = typeof r.question === 'string' && r.question.trim() ? r.question.trim().slice(0, 240) : undefined
  const options = textes(r.options).slice(0, 4)
  return {
    source: 'llm',
    intention,
    confiance,
    sujet: typeof r.sujet === 'string' ? r.sujet.trim().slice(0, 400) : '',
    changements: textes(r.changements),
    aConserver: textes(r.a_conserver),
    question,
    options: options.length >= 2 ? options : undefined,
  }
}

export async function lireDemandeImage(
  demande: string,
  contexte: ImageSessionContext,
  generer: (prompt: string) => Promise<string>,
): Promise<ImageRequestReading> {
  const situation = [
    contexte.hasAttachedImage ? "L'utilisateur a joint une image." : '',
    contexte.hasDisplayedImage ? "Une image générée précédemment est affichée à l'écran." : "Aucune image n'est affichée.",
    contexte.previousRequests.length ? `Demandes précédentes de la session :\n${contexte.previousRequests.slice(-4).map((d) => `- ${d}`).join('\n')}` : '',
  ].filter(Boolean).join('\n')
  try {
    const reponse = await generer(`${CONSIGNE}\n\n${situation}\n\nDemande : ${demande}`)
    return validerLecture(extraireJson(reponse))
  } catch (erreur) {
    return indisponible(erreur instanceof Error ? erreur.message : String(erreur))
  }
}

/** Seuil sous lequel une lecture n'est pas assez sûre pour contredire l'action déduite des mots. */
export const CONFIANCE_MIN = 0.6

export type ImageIntentDecision = {
  intent: ParsedImageIntent
  /** qui a tranché : la lecture du modèle, les expressions, ou la réponse de l'utilisateur */
  decidePar: 'comprehension' | 'expressions' | 'utilisateur'
  lecture: ImageRequestReading
  questionPosee?: string
}

const MODE_DE_RETOUCHE_PAR_DEFAUT: ImageEditMode = 'preserve_refine'

function versRetouche(texte: string, intent: ParsedImageIntent): ParsedImageIntent {
  if (intent.isEditIntent) return intent
  // relire la même phrase en considérant l'image comme désignée : le mode de retouche détaillé
  // (fond, style, ajout…) vient alors des mêmes règles que pour une demande explicite
  const relu = parseImageIntent(texte, { hasReference: true, hasExplicitReference: true })
  return relu.isEditIntent ? relu : withEditMode(relu, MODE_DE_RETOUCHE_PAR_DEFAUT)
}

function versCreation(intent: ParsedImageIntent): ParsedImageIntent {
  return intent.isEditIntent ? withEditMode(intent, 'create') : intent
}

/**
 * Décision finale : la compréhension tranche quand elle est sûre, l'utilisateur tranche quand la
 * demande est ambiguë, les expressions restent la règle quand le modèle n'a pas pu lire.
 */
export async function deciderIntentImage({
  texte,
  intentExpressions,
  contexte,
  generer,
  demander,
}: {
  texte: string
  intentExpressions: ParsedImageIntent
  contexte: ImageSessionContext
  generer: ((prompt: string) => Promise<string>) | null
  /** pose la question à l'utilisateur ; null quand aucune surface ne peut la poser */
  demander: ((question: string, options: [string, string]) => Promise<'creation' | 'retouche' | null>) | null
}): Promise<ImageIntentDecision> {
  // Sans image affichée ni jointe, il n'y a rien à retoucher : pas d'ambiguïté à lever.
  if (!contexte.hasDisplayedImage && !contexte.hasAttachedImage) {
    return { intent: intentExpressions, decidePar: 'expressions', lecture: indisponible('aucune image à retoucher') }
  }
  if (!generer) {
    return { intent: intentExpressions, decidePar: 'expressions', lecture: indisponible('aucun modèle de texte') }
  }
  const lecture = await lireDemandeImage(texte, contexte, generer)
  if (lecture.source !== 'llm') return { intent: intentExpressions, decidePar: 'expressions', lecture }

  const sure = lecture.intention !== 'ambigu' && lecture.confiance >= CONFIANCE_MIN
  if (sure) {
    const intent = lecture.intention === 'creation' ? versCreation(intentExpressions) : versRetouche(texte, intentExpressions)
    return { intent, decidePar: 'comprehension', lecture }
  }
  if (demander) {
    const question = lecture.question
      || "Je ne suis pas sûr : veux-tu modifier l'image affichée ou créer une nouvelle image ?"
    const reponse = await demander(question, ["Modifier l'image affichée", 'Créer une nouvelle image'])
    if (reponse) {
      const intent = reponse === 'creation' ? versCreation(intentExpressions) : versRetouche(texte, intentExpressions)
      return { intent, decidePar: 'utilisateur', lecture, questionPosee: question }
    }
  }
  return { intent: intentExpressions, decidePar: 'expressions', lecture }
}
