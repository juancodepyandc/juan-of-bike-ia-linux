/**
 * selfInformedReference — « s'informer avant d'ajouter/modifier ».
 *
 * Problème de fond (signalé en live) : demander « ajoute le personnage Jax » ou
 * « mets le décor du cirque de TADC » à un éditeur d'image sans lui DONNER
 * l'apparence réelle revient à le laisser inventer (Jax sortait en lapin violet
 * générique). Un glossaire en dur est un cache-misère : faux dès qu'il sort de
 * sa liste, et faux tout court s'il est imprécis.
 *
 * Évolution : pour TOUT ajout/modif d'un sujet SPÉCIFIQUE (personnage nommé,
 * objet nommé, environnement/lieu nommé), Aurora s'informe elle-même :
 *   1. elle construit des requêtes de recherche ciblées,
 *   2. elle récupère une VRAIE image de référence (vérifiée par le modèle vision
 *      comme étant le bon sujet, pas un substitut),
 *   3. elle en tire une description d'apparence PRÉCISE (analyse vision),
 *   4. et surtout elle peut réutiliser cette image trouvée comme SECONDE
 *      référence Kontext (stitch) → fidélité visuelle réelle, pas une description
 *      vague.
 * Repli LLM (description, si confiant) puis avis utilisateur si rien.
 *
 * Module PUR : toutes les capacités runtime (recherche web, vision, LLM) sont
 * injectées. L'UI (hooks Tauri) et la CLI (HTTP/python en Node) fournissent
 * leurs propres implémentations → MÊME logique, MÊME type de résultat des deux
 * côtés. Aucun import runtime de services Tauri ici (les `import type` sont
 * effacés par --experimental-strip-types, donc la CLI Node peut l'importer).
 */
import { detectNamedAddTarget } from '../utils/namedEntityEnrichment.ts'
import type { ParsedImageIntent } from '../utils/imagePromptParser.ts'

export type ReferenceKind = 'character' | 'object' | 'environment' | 'place'
/** add_subject : injecter le sujet dans l'image. become_scene : la scène devient ce lieu. */
export type ResearchRole = 'add_subject' | 'primary_subject' | 'become_scene'

export interface SubjectToResearch {
  /** Libellé propre du sujet à rechercher, ex: "Jax", "le cirque de The Amazing Digital Circus". */
  subject: string
  /** Disambiguated label for search, e.g. "Jax TADC" while subject stays "Jax". */
  searchLabel?: string
  kind: ReferenceKind
  role: ResearchRole
}

/** Profil de recherche (sous-ensemble structurellement compatible avec ReferenceSearchProfile). */
export interface ResearchProfile {
  subjectLabel: string
  identityTerms: string[]
  strictIdentity: boolean
  preferIsolatedSubject: boolean
  allowAdditionalSubjects: boolean
  requiredElements: string[]
  forbiddenElements: string[]
  requiredPageTerms?: string[]
  forbiddenPageTerms?: string[]
  preferredDomains?: string[]
  blockedDomains?: string[]
  minimumScore: number
}

export interface ResearchedImage {
  /** Nom du fichier déjà déposé dans l'input ComfyUI (prêt à servir de 2e référence). */
  comfyFilename?: string | null
  /** Blob de l'image trouvée (pour analyse vision si comfyFilename absent). */
  blob?: Blob | null
  sourceUrl?: string
  score?: number
}

export interface SelfInformDeps {
  /** Search and verify several references. The best one can become the Kontext source; the rest validate the description. */
  fetchReferenceImages?: (
    queries: string[],
    profile: ResearchProfile,
    signal?: AbortSignal,
  ) => Promise<ResearchedImage[]>
  /** Cherche + vérifie (vision) + dépose dans ComfyUI la meilleure référence du sujet. null si rien. */
  fetchReferenceImage?: (
    queries: string[],
    profile: ResearchProfile,
    signal?: AbortSignal,
  ) => Promise<ResearchedImage | null>
  /** Décrit précisément (vision) une référence trouvée → apparence anglaise dense. */
  describeReferenceImage?: (
    ref: ResearchedImage,
    target: SubjectToResearch,
    signal?: AbortSignal,
  ) => Promise<string>
  /** LLM texte (repli description quand aucune image fiable). */
  generate?: (model: string, prompt: string) => Promise<{ response?: string } | null | undefined>
  textModel?: string
  signal?: AbortSignal
  /** Hook de progression UI/CLI (facultatif). */
  onProgress?: (message: string) => void
}

export interface ResolvedSubjectReference {
  subject: string
  kind: ReferenceKind
  role: ResearchRole
  /** Description d'apparence à injecter dans l'instruction ('' si aucune). */
  appearanceDescription: string
  /** Si une image a été trouvée et déposée : son nom de fichier ComfyUI (2e référence Kontext). */
  referenceComfyFilename: string | null
  /** Number of verified visual references used for the decision. */
  referenceCount: number
  provenance: 'researched-image' | 'llm-description' | 'none'
  /** Avis utilisateur non bloquant quand rien n'a été trouvé. */
  advisory: string | null
}

const CHARACTER_CUE = /\b(?:personnages?|perso|mascottes?|mascot|character|figure|h[ée]ros|h[ée]ro[ïi]ne|villain|m[ée]chant)\b/iu
/** Mots d'environnement/scène introduisant un lieu nommé. */
const SCENE_WORD = '(?:cirque|univers|monde|d[ée]cor|environnement|sc[èe]ne|lieu|endroit|royaume|world|universe|realm|land|scene|setting|place)'
const SCENE_NAMED_RE = new RegExp(
  `\\b${SCENE_WORD}\\s+(?:de\\s+la\\s+|de\\s+l['’]|des\\s+|du\\s+|de\\s+|of\\s+the\\s+|of\\s+|from\\s+the\\s+|from\\s+|the\\s+|d['’])([^,.;!?\\n]+)`,
  'iu',
)
/** "transforme/mets le décor/fond en <X>" (X spécifique). */
const SCENE_INTO_RE = new RegExp(
  `\\b(?:${SCENE_WORD}|fond|arri[èe]re[-\\s]?plan|background)\\b[^,.;!?\\n]*?\\b(?:en|into|to|comme|like|:)\\s+([^,.;!?\\n]+)`,
  'iu',
)

function clean(s: string): string {
  return s.replace(/\s+/g, ' ').trim()
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Coupe un libellé de lieu sur les connecteurs de relation/intention. */
function trimSceneName(raw: string): string {
  const stop = raw.search(/\s+(?:de\s+fa[cç]on|afin\b|pour\b|qui\b|avec\b|sans\b|en\s+gardant|tout\s+en|while\b|keeping\b)/iu)
  const cut = stop > 0 ? raw.slice(0, stop) : raw
  return clean(cut).split(/\s+/).slice(0, 8).join(' ').replace(/[,.;:!?]+$/u, '').trim()
}

function trimRelationContext(raw: string): string {
  const stop = raw.search(/\s+(?:de\s+fa[cç]on|afin\b|pour\b|qui\b|avec\b|sans\b|sur\b|dans\b|sous\b|épaule\b|epaule\b|posant\b|tenant\b|assis\b|debout\b|a\s+c[oô]t[ée]\b|en\s+posture\b|en\s+train\b|mangeant\b|combattant\b|faisant\b|marchant\b|portant\b|en\s+gardant|tout\s+en|while\b|keeping\b|posing\b|holding\b|on\b|in\b|shoulder\b|next\s+to\b|with\b)/iu)
  const cut = stop > 0 ? raw.slice(0, stop) : raw
  return clean(cut).split(/\s+/).slice(0, 8).join(' ').replace(/[,.;:!?]+$/u, '').trim()
}

function splitNamedSubject(named: string): { subject: string; context: string } {
  const value = clean(named)
  const match = value.match(/^(.+?)\s+(?:de|du|des|dans|in|of|from)\s+(.+)$/iu)
  if (!match?.[1] || !match?.[2]) return { subject: value, context: '' }

  const subject = clean(match[1]).replace(/[,.;:!?]+$/u, '')
  const context = clean(match[2]).replace(/[,.;:!?]+$/u, '')
  const contextLooksLikeFranchise =
    /\b[A-Z0-9]{2,}\b/.test(context)
    || /^the\b/i.test(context)
    || context.split(/\s+/).length >= 2

  return contextLooksLikeFranchise ? { subject, context } : { subject: value, context: '' }
}

function extractFranchiseContext(prompt: string, subject: string): string {
  const cleanSubject = clean(subject)
  if (!cleanSubject) return ''
  const subjectPattern = escapeRegExp(cleanSubject)
  const re = new RegExp(`${subjectPattern}\\s+(?:de\\s+la\\s+|de\\s+l['’]?|des\\s+|du\\s+|de\\s+|dans\\s+la\\s+|dans\\s+l['’]?|dans\\s+le\\s+|dans\\s+les\\s+|dans\\s+|d['’]|in\\s+the\\s+|in\\s+|of\\s+the\\s+|of\\s+|from\\s+the\\s+|from\\s+)([^,.;!?\\n]+)`, 'iu')
  const match = prompt.match(re)
  if (!match?.[1]) return ''
  return trimRelationContext(match[1])
}

function buildSearchLabel(subject: string, context: string): string | undefined {
  const cleanSubject = clean(subject)
  const cleanContext = clean(context)
  if (!cleanSubject || !cleanContext || cleanSubject.toLowerCase() === cleanContext.toLowerCase()) return undefined
  return clean(`${cleanSubject} ${cleanContext}`)
}

/** Vrai si le libellé désigne un sujet SPÉCIFIQUE (nommé), pas un nom commun générique. */
function looksSpecific(label: string): boolean {
  const l = clean(label)
  if (l.length < 3) return false
  if (/^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)$/i.test(l)) return false
  // un nom propre (majuscule interne/acronyme) ou un multi-mot un peu long = spécifique
  if (/[A-Z]/.test(l.replace(/^./, ''))) return true
  if (/\b[A-Z]{2,}\b/.test(l)) return true
  if (l.split(/\s+/).length >= 2 && l.length >= 7) return true
  return false
}

function classifyAddKind(prompt: string): ReferenceKind {
  return CHARACTER_CUE.test(prompt) ? 'character' : 'object'
}

/** Verbe d'ajout (FR + EN) pour la détection de nom propre sans cue explicite. */
const ADD_VERB_LOOSE = /\b(?:ajout|insertion|integration|intégration|ajoute[rz]?|rajoute[rz]?|mets?|mettre|place[rz]?|pose[rz]?|incruste[rz]?|ins[eè]re[rz]?|int[èe]gre[rz]?|add|insert|put)\b/iu
/** Mots capitalisés à ignorer (articles/pronoms en tête de phrase). */
const COMMON_CAP_STOP = new Set([
  'Le', 'La', 'Les', 'Un', 'Une', 'Des', 'Du', 'De', 'The', 'A', 'An',
  'Mon', 'Ma', 'Mes', 'Ce', 'Cette', 'Ces', 'Il', 'Elle', 'Je', 'Tu', 'On',
  'Photo', 'Image', 'Illustration', 'Dessin', 'Portrait', 'Scene', 'Style',
  'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII',
])

const KNOWN_GAZETTEER_ICONS: Array<[RegExp, string]> = [
  [/\b(?:natsu\s+dragneel|natsu)\b/i, 'Natsu Dragneel'],
  [/\b(?:lucy\s+heartfilia|lucy)\b/i, 'Lucy Heartfilia'],
  [/\b(?:erza\s+scarlet|erza)\b/i, 'Erza Scarlet'],
  [/\b(?:gray\s+fullbuster|gray)\b/i, 'Gray Fullbuster'],
  [/\b(?:happy)\b/i, 'Happy'],
  [/\b(?:pikachu)\b/i, 'Pikachu'],
  [/\b(?:charizard|dracaufeu)\b/i, 'Charizard'],
  [/\b(?:homer\s+simpson|homer)\b/i, 'Homer Simpson'],
  [/\b(?:bart\s+simpson|bart)\b/i, 'Bart Simpson'],
  [/\b(?:marge\s+simpson|marge)\b/i, 'Marge Simpson'],
  [/\b(?:lisa\s+simpson|lisa)\b/i, 'Lisa Simpson'],
  [/\b(?:goldorak|grendizer|goldrake)\b/i, 'Goldorak'],
  [/\b(?:son\s+goku|sangoku|goku)\b/i, 'Goku'],
  [/\b(?:vegeta)\b/i, 'Vegeta'],
  [/\b(?:monkey\s+d\.?\s+luffy|luffy)\b/i, 'Luffy'],
  [/\b(?:naruto\s+uzumaki|naruto)\b/i, 'Naruto'],
  [/\b(?:sasuke\s+uchiha|sasuke)\b/i, 'Sasuke'],
  [/\b(?:mario)\b/i, 'Mario'],
  [/\b(?:luigi)\b/i, 'Luigi'],
  [/\b(?:sonic)\b/i, 'Sonic'],
  [/\b(?:batman)\b/i, 'Batman'],
  [/\b(?:superman)\b/i, 'Superman'],
  [/\b(?:spiderman|spider-man)\b/i, 'Spider-Man'],
  [/\b(?:ironman|iron\s+man)\b/i, 'Iron Man'],
]

function findGazetteerMatch(text: string): string | null {
  for (const [re, canonical] of KNOWN_GAZETTEER_ICONS) {
    if (re.test(text)) return canonical
  }
  return null
}

/**
 * Détecte un sujet NOMMÉ par nom propre, même SANS mot-clé « personnage »
 * (« ajoute Pikachu en colère » → "Pikachu", « mets Goku » → "Goku"). On exige
 * un verbe d'ajout puis un nom propre (Majuscule), en sautant un article. On
 * NE déclenche PAS sur un nom commun en minuscule (« ajoute un chapeau »).
 */
function detectProperNounAddTarget(prompt: string): string | null {
  const verb = ADD_VERB_LOOSE.exec(prompt)
  if (!verb) return null
  const gaz = findGazetteerMatch(prompt.slice(verb.index))
  if (gaz) return gaz
  let rest = prompt.slice(verb.index + verb[0].length).replace(/^\s+/, '')
  rest = rest.replace(/^(?:un|une|le|la|les|des|du|de|d['’]|my|the|a|an)\s+/i, '')
  const m = rest.match(/^([A-ZÀ-Ÿ][\p{L}'’-]+(?:\s+[A-ZÀ-Ÿ][\p{L}'’-]+){0,2})/u)
  if (!m) return null
  const name = clean(m[1]).replace(/[,.;:!?]+$/u, '')
  const first = name.split(/\s+/)[0]
  if (!first || COMMON_CAP_STOP.has(first) || name.length < 2) return null
  return name
}

/** Premier nom propre rencontré N'IMPORTE OÙ dans un fragment (cible d'un
 * « remplace X par le chat bleu Happy de Fairy Tail » → "Happy"). */
function findProperNounIn(s: string): string | null {
  const gaz = findGazetteerMatch(s)
  if (gaz) return gaz
  const t = clean(s)
  const re = /(?<![\p{L}\p{N}])([A-ZÀ-Ÿ][\p{L}'’-]+(?:\s+[A-ZÀ-Ÿ][\p{L}'’-]+){0,2})/gu
  let m: RegExpExecArray | null
  while ((m = re.exec(t)) !== null) {
    const name = clean(m[1]).replace(/[,.;:!?]+$/u, '')
    const first = name.split(/\s+/)[0]
    if (!first || COMMON_CAP_STOP.has(first) || name.length < 2) continue
    return name
  }
  return null
}

const NAMED_PHRASE_RE = /\b(?:nomm[ée]e?s?|nommer|appel[ée]e?s?|named|called)\s+([^,.;!?\n]+)/iu

const REPLICATION_PREFIX_RE = /^\s*(?:(?:fais[-\s]moi\s+une\s+|fais\s+une\s+)(?:r[eé]plication|reproduction|copie)\s*(?:fid[eè]le\s+)?(?:de\s+|d['’]|of\s+)?|(?:r[eé]plication|reproduction|copie)\s+(?:fid[eè]le\s+)?(?:de\s+|d['’]|of\s+)|(?:r[eé]pliqu(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|reprodui(?:re|s|t|sez|sent|sant)|recr[eé](?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|dupliqu(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|copi(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|imit(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es))\s+(?:fid[eè]lement\s+)?(?:de\s+|d['’]|of\s+|le\s+|la\s+|les\s+|un\s+|une\s+)?)/iu
const CREATION_PREFIX_RE = /^\s*(?:(?:photo|image|illustration|dessin|render|rendu|portrait|scene|sc[eè]ne|visuel)\s+(?:photo(?:r[eé]aliste|realiste)|r[eé]aliste|realiste|anime|manga|cinematic|cin[eé]matique|style\s+\w+)?\s*(?:de\s+|d['’]|of\s+)?)?/iu
const CREATION_RELATION_STOP_RE = /\s+(?:devant|face\s+a|face\s+au|face\s+aux|a\s+cote|a\s+cot[eé]|pres\s+de|pr[eè]s\s+de|dans|sur|sous|avec|contre|inside|in\s+front\s+of|next\s+to|beside|near|with|on|under|style|au\s+style|en\s+style|,|;|\.|!|\?)/iu
const CREATION_OBJECT_CUE_RE = /\b(?:voiture|car|moto|motorcycle|telephone|phone|iphone|smartphone|ordinateur|computer|laptop|console|camera|cam[eé]ra|casque|headset|shoe|sneaker|chaussure|product|produit|objet|logo|marque|brand|model|modele|mod[eè]le|tesla|gpu|cpu|motherboard|carte\s+mere|carte\s+m[eè]re)\b/iu
const CREATION_PLACE_CUE_RE = /\b(?:tour|tower|ville|city|pays|country|mont|mount|mountain|parc|park|palais|palace|chateau|ch[aâ]teau|eglise|[eé]glise|cathedrale|cath[eé]drale|temple|plage|beach|foret|for[eê]t|rue|street)\b/iu

function properNameCandidateFromFragment(fragment: string): string | null {
  const gaz = findGazetteerMatch(fragment)
  if (gaz) return gaz
  const trimmed = clean(fragment)
  if (!trimmed) return null
  const stop = trimmed.search(CREATION_RELATION_STOP_RE)
  const head = clean((stop > 0 ? trimmed.slice(0, stop) : trimmed)
    .replace(/^(?:un|une|le|la|les|des|du|de|d['’]|the|a|an)\s+/iu, ''))
  const match = head.match(/^([A-ZÀ-Ÿ][\p{L}0-9'’.-]+(?:\s+[A-ZÀ-Ÿ0-9][\p{L}0-9'’.-]+){0,3})/u)
  if (!match?.[1]) return null
  const name = clean(match[1]).replace(/[,.;:!?]+$/u, '')
  const first = name.split(/\s+/)[0]
  if (!first || COMMON_CAP_STOP.has(first) || name.length < 2) return null
  return name
}

function detectPrimaryCreationSubject(prompt: string, intent: ParsedImageIntent | null | undefined): SubjectToResearch | null {
  if (intent?.isEditIntent && intent.editMode !== 'replicate') return null
  const text = clean(prompt)
  if (!text || (ADD_VERB_LOOSE.test(text) && intent?.editMode !== 'replicate')) return null

  const isExplicitPlaceCreation = /^\s*(?:(?:photo|image|illustration|dessin|render|rendu|visuel|creation|cr[eé]ation)\s+(?:photo(?:r[eé]aliste|realiste)|r[eé]aliste|realiste|anime|manga|cinematic|cin[eé]matique)?\s*(?:du|de\s+la|des|de|d['’]|of\s+)?)?(?:ville|village|royaume|paysage|d[eé]cor|environnement|quartier|monde|lieu)\s+(?:de\s+|d['’]|du\s+|of\s+)/iu.test(text)

  const withoutPrefix = text.replace(REPLICATION_PREFIX_RE, '').replace(CREATION_PREFIX_RE, '')
  const proper = properNameCandidateFromFragment(withoutPrefix) || findProperNounIn(withoutPrefix)
  if (!proper) return null

  const split = splitNamedSubject(proper)
  const subject = split.subject || proper
  const context = split.context || extractFranchiseContext(text, subject)
  const placeLike = isExplicitPlaceCreation
    || CREATION_PLACE_CUE_RE.test(subject)
    || /\b(?:ville|village|royaume|paysage|lieu|cite|cité|quartier|monde)\s+(?:de|du|d'|of)\s+/iu.test(subject)

  return {
    subject,
    searchLabel: buildSearchLabel(subject, context),
    kind: placeLike ? 'place' : CREATION_OBJECT_CUE_RE.test(subject) ? 'object' : 'character',
    role: placeLike ? 'become_scene' : 'primary_subject',
  }
}

function titleCaseLoose(value: string): string {
  const cleaned = clean(value)
  if (!cleaned) return ''
  if (/[A-ZÀ-Ÿ]/u.test(cleaned)) return cleaned
  return cleaned.replace(/\b([\p{L}])([\p{L}'’-]*)/gu, (_m, first: string, rest: string) => `${first.toUpperCase()}${rest.toLowerCase()}`)
}

function extractNamedPhraseContext(prefix: string): string {
  const match = prefix.match(/(?:de\s+la\s+|de\s+l['’]?|des\s+|du\s+|de\s+|of\s+the\s+|of\s+|from\s+the\s+|from\s+)([^,.;!?\n]+?)\s*$/iu)
  if (!match?.[1]) return ''
  const context = trimRelationContext(match[1])
  const withoutLeadingNoun = context
    .replace(/^(?:chat|cat|personnage|character|mascotte|mascot|creature|créature|animal)\s+/iu, '')
    .replace(/^(?:de|du|of|from)\s+/iu, '')
  return titleCaseLoose(withoutLeadingNoun)
}

function detectNamedPhraseAddTarget(prompt: string): { subject: string; context: string } | null {
  const verb = ADD_VERB_LOOSE.exec(prompt)
  if (!verb) return null
  const match = prompt.match(NAMED_PHRASE_RE)
  if (!match?.[1] || match.index === undefined || match.index < verb.index) return null
  const subject = titleCaseLoose(trimRelationContext(match[1]))
    .split(/\s+/)
    .slice(0, 4)
    .join(' ')
    .replace(/[,.;:!?]+$/u, '')
    .trim()
  if (!subject || subject.length < 2) return null
  const context = extractNamedPhraseContext(prompt.slice(verb.index + verb[0].length, match.index))
  return { subject, context }
}

/**
 * Détecte le sujet spécifique à rechercher pour une édition donnée, ou null si
 * la demande ne vise rien de nommé (ex : « ajoute un chapeau » → null, pas de
 * recherche). Couvre l'ajout de personnage/objet nommé ET le passage vers un
 * environnement/lieu nommé (« le cirque de The Amazing Digital Circus »).
 */
export function detectSubjectToResearch(
  prompt: string,
  intent: ParsedImageIntent | null | undefined,
): SubjectToResearch | null {
  const text = clean(prompt)
  if (!text) return null

  const primary = detectPrimaryCreationSubject(text, intent)
  if (primary) return primary

  // 1) Ajout d'un personnage / objet nommé.
  const named = detectNamedAddTarget(text)
  if (named) {
    const split = splitNamedSubject(named)
    const promptContext = extractFranchiseContext(text, split.subject)
    const context = split.context || promptContext
    const subject = split.subject || named
    if (!looksSpecific(named) && !/^[A-Z0-9]/.test(subject) && !context) return null
    return {
      subject,
      searchLabel: buildSearchLabel(subject, context),
      kind: classifyAddKind(text),
      role: 'add_subject',
    }
  }

  // 1b) Entite explicite par "nomme/called" avec contexte de franchise :
  // "mets le chat de Fairy Tail nomme Happy" -> subject Happy, search Happy Fairy Tail.
  const namedPhrase = detectNamedPhraseAddTarget(text)
  if (namedPhrase) {
    return {
      subject: namedPhrase.subject,
      searchLabel: buildSearchLabel(namedPhrase.subject, namedPhrase.context),
      kind: 'character',
      role: 'add_subject',
    }
  }

  // 1c) Nom propre ajouté SANS cue explicite (« ajoute Pikachu en colère »).
  const proper = detectProperNounAddTarget(text)
  if (proper) {
    const split = splitNamedSubject(proper)
    const subject = split.subject || proper
    const context = split.context || extractFranchiseContext(text, subject)
    return {
      subject,
      searchLabel: buildSearchLabel(subject, context),
      // un nom propre ajouté est presque toujours un personnage/créature.
      kind: 'character',
      role: 'add_subject',
    }
  }

  // 1d) Cible NOMMÉE d'un REMPLACEMENT (« remplace l'homme par Happy de Fairy
  // Tail ») : on s'informe sur le NOUVEAU sujet Y (celui à rendre), role add.
  if (intent?.editMode === 'replace_element' && intent.replacements?.length) {
    for (const r of intent.replacements) {
      const cand = findProperNounIn(r?.to || '')
      if (!cand) continue
      const split = splitNamedSubject(cand)
      const subject = split.subject || cand
      const context = split.context || extractFranchiseContext(text, subject)
      return {
        subject,
        searchLabel: buildSearchLabel(subject, context),
        kind: 'character',
        role: 'add_subject',
      }
    }
  }

  // 2) Scène / décor : devenir un environnement ou lieu nommé.
  // Garde-fou : un VRAI nom propre (« The Amazing Digital Circus », « Mario »,
  // un acronyme) — pas un simple multi-mot générique (« à sa place de façon
  // cohérente » ne doit PAS être pris pour un lieu nommé).
  const looksProperNamed = (name: string) => /[A-ZÀ-Ÿ]/.test(name) || /\b[A-Z]{2,}\b/.test(name)
  const mode = intent?.editMode
  const sceneEligible = mode === 'scene_transform' || mode === 'background_change' || /\b(d[ée]cor|fond|arri[èe]re[-\s]?plan|environnement|cirque|univers|monde|background|scene|world)\b/i.test(text)
  if (sceneEligible) {
    const m1 = text.match(SCENE_NAMED_RE)
    if (m1?.[1]) {
      const name = trimSceneName(m1[1])
      // on garde le mot de scène pour la requête ("cirque de X")
      const full = clean(`${m1[0].split(/\s+/)[0]} de ${name}`)
      if (looksSpecific(name) && looksProperNamed(name)) return { subject: full, kind: 'environment', role: 'become_scene' }
    }
    const m2 = text.match(SCENE_INTO_RE)
    if (m2?.[1]) {
      const name = trimSceneName(m2[1])
      if (looksSpecific(name) && looksProperNamed(name)) return { subject: name, kind: 'place', role: 'become_scene' }
    }
  }

  // 3) Entité / personnage connu présent n'importe où dans le prompt
  const gaz = findGazetteerMatch(text)
  if (gaz) {
    const split = splitNamedSubject(gaz)
    const subject = split.subject || gaz
    const context = split.context || extractFranchiseContext(text, subject)
    return {
      subject,
      searchLabel: buildSearchLabel(subject, context),
      kind: 'character',
      role: 'primary_subject',
    }
  }

  return null
}

/** Requêtes de recherche ciblées selon le type de sujet. */
export function buildResearchQueries(target: SubjectToResearch): string[] {
  const s = clean(target.searchLabel || target.subject)
  const subjectOnly = clean(target.subject)
  const base: string[] = []
  switch (target.kind) {
    case 'character':
      base.push(
        `${s} official character reference full body`,
        `${s} character design sheet`,
        `${s} official art transparent png`,
        subjectOnly.toLowerCase() !== s.toLowerCase() ? `${s} wiki appearance` : '',
        s,
      )
      break
    case 'object':
      base.push(`${s} official reference photo isolated`, `${s} product reference`, s)
      break
    case 'environment':
      base.push(`${s} environment background official`, `${s} location screenshot wide shot`, `${s} concept art background`, s)
      break
    case 'place':
      base.push(`${s} photograph`, `${s} wide establishing shot`, s)
      break
  }
  return Array.from(new Set(base.map(clean).filter(Boolean))).slice(0, 5)
}

/** Profil identité-stricte pour ne pas accepter un substitut générique. */
export function buildResearchProfile(target: SubjectToResearch): ResearchProfile {
  const tokens = clean(target.subject)
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length >= 3 && !['the', 'and', 'les', 'des', 'una', 'une', 'with'].includes(t))
  const contextTokens = clean(target.searchLabel || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length >= 3 && !['the', 'and', 'les', 'des', 'una', 'une', 'with'].includes(t))
    .filter((t) => !tokens.includes(t))
  const isSubject = target.role === 'add_subject' || target.role === 'primary_subject'
  const forbiddenPageTerms = target.kind === 'character'
    ? ['tissot', 'watch', 'watches', 'montre', 'clock', 'shirt', 'tshirt', 't-shirt', 'hoodie', 'poster', 'packaging']
    : undefined

  return {
    subjectLabel: target.searchLabel || target.subject,
    identityTerms: tokens,
    strictIdentity: true,
    preferIsolatedSubject: isSubject,
    allowAdditionalSubjects: !isSubject,
    requiredElements: [],
    forbiddenElements: isSubject ? ['watermark', 'meme caption', 'UI overlay'] : [],
    requiredPageTerms: contextTokens.length > 0 ? contextTokens : undefined,
    forbiddenPageTerms,
    // un cran sous le défaut strict (84) : les sujets de niche ont peu de réfs propres,
    // mais la vérif vision "bon sujet" reste le vrai garde-fou.
    minimumScore: 78,
  }
}

function cleanDescription(text: string): string {
  const t = clean(
    (text || '')
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<think>[\s\S]*$/g, '')
      .replace(/^["'`\s]+|["'`\s]+$/g, ''),
  )
  if (!t || /^none\b/i.test(t) || t.length < 8) return ''
  return t.length > 320 ? `${t.slice(0, 319)}…` : t
}

function mergeReferenceDescriptions(descriptions: string[]): string {
  const cleaned = descriptions.map(cleanDescription).filter(Boolean)
  if (cleaned.length === 0) return ''
  // Use the top consensus-ranked description directly.
  // We avoid meta-prefixes like "Primary reference:" or "Cross-check 1:" because diffusion models
  // misinterpret them as instructions to render multiple tiled panes/mosaics.
  return cleaned[0]
}

function descriptionTokens(description: string): Set<string> {
  return new Set(clean(description)
    .toLowerCase()
    .replace(/\bno\s+[^.;,]+/g, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length >= 4)
    .filter((token) => ![
      'with', 'wears', 'wearing', 'body', 'face', 'head', 'eyes',
      'character', 'humanoid', 'cartoon', 'large', 'small', 'long',
      'short', 'color', 'colors', 'reference', 'primary', 'cross',
      'light', 'dark', 'shirt', 'shirts', 'accessory', 'accessories',
      'human', 'person', 'distinctive', 'marks', 'beyond', 'attire',
      'yellow', 'purple', 'pink', 'blue', 'green', 'black', 'white',
      'brown', 'orange', 'gray', 'grey', 'silver', 'gold', 'golden',
    ].includes(token)))
}

function tokenOverlap(left: Set<string>, right: Set<string>): number {
  let count = 0
  for (const token of left) {
    if (right.has(token)) count += 1
  }
  return count
}

function consensusRankDescriptions<T extends { description: string; ref: ResearchedImage }>(items: T[]): T[] {
  const tokenSets = items.map((item) => descriptionTokens(item.description))
  const ranked = items
    .map((item, index) => {
      const consensus = tokenSets.reduce((sum, tokens, otherIndex) => (
        otherIndex === index ? sum : sum + tokenOverlap(tokenSets[index], tokens)
      ), 0)
      return { item, index, consensus }
    })
    .sort((left, right) => {
      if (right.consensus !== left.consensus) return right.consensus - left.consensus
      return Number(right.item.ref.score || 0) - Number(left.item.ref.score || 0)
    })

  if (ranked.length <= 1) return ranked.map((entry) => entry.item)
  const primaryTokens = descriptionTokens(ranked[0].item.description)
  const minimumOverlap = Math.max(2, Math.min(4, Math.ceil(primaryTokens.size * 0.12)))
  return ranked
    .filter((entry, index) => (
      index === 0
      || tokenOverlap(descriptionTokens(entry.item.description), primaryTokens) >= minimumOverlap
    ))
    .map((entry) => entry.item)
}

const LLM_DESC_PROMPT = (target: SubjectToResearch) => `/no_think
Describe the precise VISUAL appearance of "${target.searchLabel || target.subject}" so an image editor can render it FAITHFULLY.
Rules:
- Output ONE dense English line, max 45 words.
- Be specific: ${target.role === 'become_scene'
  ? 'layout, dominant colors, ground/sky, signature structures, distinctive props of this exact place/environment.'
  : 'species/body type, exact colors, face/eyes, outfit, accessories, distinctive marks of this exact subject.'}
- Describe appearance ONLY. No franchise name, no preamble, no quotes.
- If you are NOT reasonably sure what it looks like, output exactly: NONE
Appearance:`

/**
 * Avis utilisateur quand aucune référence fiable n'a pu être obtenue.
 */
export function buildResearchAdvisory(target: SubjectToResearch): string {
  return `Aurora n'a pas trouvé de référence fiable pour « ${clean(target.subject)} ». Pour une fidélité maximale, joins toi-même une image de référence (📎) — sinon le rendu reste une approximation.`
}

/**
 * Résout la meilleure référence disponible pour le sujet : image trouvée
 * (idéale, réutilisable comme 2e référence Kontext) + description précise,
 * sinon description LLM confiante, sinon avis. Ne lève jamais.
 */
export async function resolveSubjectReference(
  target: SubjectToResearch,
  deps: SelfInformDeps,
): Promise<ResolvedSubjectReference> {
  const out: ResolvedSubjectReference = {
    subject: target.subject,
    kind: target.kind,
    role: target.role,
    appearanceDescription: '',
    referenceComfyFilename: null,
    referenceCount: 0,
    provenance: 'none',
    advisory: null,
  }
  if (deps.signal?.aborted) return out

  const queries = buildResearchQueries(target)
  const profile = buildResearchProfile(target)

  // 1) Recherche d'une vraie image de référence (vérifiée bon sujet par vision).
  if (deps.fetchReferenceImages) {
    deps.onProgress?.(`Recherche de references pour ${clean(target.searchLabel || target.subject)}...`)
    try {
      const found = ((await deps.fetchReferenceImages(queries, profile, deps.signal)) ?? [])
        .filter((ref): ref is ResearchedImage => Boolean(ref && (ref.comfyFilename || ref.blob)))
        .sort((left, right) => Number(right.score || 0) - Number(left.score || 0))
        .slice(0, 3)

      if (found.length > 0) {
        out.referenceCount = found.length
        out.referenceComfyFilename = found.find((ref) => ref.comfyFilename)?.comfyFilename ?? null
        out.provenance = 'researched-image'

        if (deps.describeReferenceImage) {
          deps.onProgress?.(`Analyse des references pour ${clean(target.searchLabel || target.subject)}...`)
          const described: Array<{ ref: ResearchedImage; description: string }> = []
          for (const ref of found) {
            if (deps.signal?.aborted) return out
            try {
              const description = cleanDescription(await deps.describeReferenceImage(ref, target, deps.signal))
              if (description) described.push({ ref, description })
            } catch {
              /* description best-effort */
            }
          }
          const ranked = consensusRankDescriptions(described)
          if (ranked.length > 0) {
            out.referenceComfyFilename = ranked.find((item) => item.ref.comfyFilename)?.ref.comfyFilename ?? out.referenceComfyFilename
            out.appearanceDescription = mergeReferenceDescriptions(ranked.map((item) => item.description))
          }
        }
      }
    } catch {
      /* recherche best-effort : on retombe sur le LLM */
    }
  }

  if (!out.referenceCount && deps.fetchReferenceImage) {
    deps.onProgress?.(`Recherche d'une référence de « ${clean(target.subject)} »…`)
    try {
      const found = await deps.fetchReferenceImage(queries, profile, deps.signal)
      if (found && (found.comfyFilename || found.blob)) {
        out.referenceComfyFilename = found.comfyFilename ?? null
        out.referenceCount = 1
        out.provenance = 'researched-image'
        // 2) Description précise à partir de l'image trouvée.
        if (deps.describeReferenceImage) {
          deps.onProgress?.(`Analyse de la référence de « ${clean(target.subject)} »…`)
          try {
            out.appearanceDescription = cleanDescription(
              await deps.describeReferenceImage(found, target, deps.signal),
            )
          } catch {
            /* description best-effort */
          }
        }
      }
    } catch {
      /* recherche best-effort : on retombe sur le LLM */
    }
  }

  // 3) Repli : description LLM (confiante uniquement).
  const requiresGroundedContext = Boolean(target.searchLabel && clean(target.searchLabel).toLowerCase() !== clean(target.subject).toLowerCase())
  if (!out.appearanceDescription && deps.generate && deps.textModel && !requiresGroundedContext) {
    if (deps.signal?.aborted) return out
    deps.onProgress?.(`Description de « ${clean(target.subject)} »…`)
    try {
      const res = await deps.generate(deps.textModel, LLM_DESC_PROMPT(target))
      const desc = cleanDescription(res?.response || '')
      if (desc) {
        out.appearanceDescription = desc
        if (out.provenance === 'none') out.provenance = 'llm-description'
      }
    } catch {
      /* repli best-effort */
    }
  }

  if (out.provenance === 'none' && !out.appearanceDescription) {
    out.advisory = buildResearchAdvisory(target)
  }
  return out
}

/**
 * Clause d'apparence à injecter dans l'instruction Kontext, adaptée au rôle.
 * Partagée UI + CLI (parité).
 */
export function buildAppearanceClause(target: SubjectToResearch, description: string): string {
  const desc = clean(description)
  if (!desc) return ''
  if (target.role === 'become_scene' || target.kind === 'environment' || target.kind === 'place') {
    return `The environment and background (${clean(target.subject)}) must match this exact visual appearance: ${desc}. Accurate linear perspective and spatial depth, with clean architectural scenery, no deformed humanoid blobs or messy unrecognizable characters on banners, and no giant out-of-scale background figures.`
  }
  if (target.role === 'primary_subject') {
    const noun = target.kind === 'character' ? 'main character' : 'main subject'
    return `The ${noun} (${clean(target.subject)}) must match this exact reference appearance: ${desc}`
  }
  const noun = target.kind === 'character' ? 'character' : 'element'
  return `The added ${noun} (${clean(target.subject)}) must look exactly like this: ${desc}`
}

export const __test__ = {
  looksSpecific,
  trimSceneName,
  splitNamedSubject,
  extractFranchiseContext,
  buildSearchLabel,
  mergeReferenceDescriptions,
  SCENE_NAMED_RE,
  SCENE_INTO_RE,
}
