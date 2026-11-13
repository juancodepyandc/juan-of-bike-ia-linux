/**
 * Verrou de fidélité du sujet pour FLUX.2 (module Image natif, web/tunnel et CLI).
 *
 * Constat (13 novembre 2026) : « un vase en forme de coeur avec inscriptions
 * rayen » donnait un flacon transparent avec une personne. Causes observées
 * dans le code : la traduction lexicale produisait « a vase into forme de coeur »
 * (FLUX.2 ne savait pas qu'il fallait un cœur) ; le prompt positif recevait des
 * consignes humaines (« plastic airbrushed skin, wax face, deformed anatomy,
 * extra fingers », « preserve the original person identity, face structure,
 * shoulders… ») que l'encodeur Mistral lit comme du contenu à dessiner ; et
 * « Rayen » était recherché sur le web comme personnage.
 *
 * Ce module dit, sans modèle de langage :
 *  - quel est l'objet demandé et sa catégorie exacte (un vase reste un vase) ;
 *  - sa forme, sa matière et le texte exact à écrire ;
 *  - si une personne / un animal est demandé (sinon : aucun, en négatif réel) ;
 * puis construit la phrase de tête du prompt positif, le complément du prompt
 * négatif (CFGGuider = vrai négatif) et un contrôle de l'expansion du LLM.
 */
import { extractInscriptionTexts, stripInscriptionSpans } from '../utils/inscriptionText.ts'

type NounEntry = {
  /** expression régulière sur le texte normalisé (minuscules, sans accents) */
  re: RegExp
  en: string
  /** précision de catégorie : ce qui distingue l'objet de ses voisins */
  guard?: string
  /** catégories voisines qu'il ne faut pas produire à la place */
  confusions?: string[]
  /** un objet à figure humaine (statue, poupée…) : la figure est voulue */
  figurative?: boolean
}

const OBJECTS: NounEntry[] = [
  { re: /\bvases?\b/, en: 'vase', guard: 'a decorative vase: an open-topped vessel with a wide opening at the top', confusions: ['bottle', 'perfume bottle', 'flask', 'flacon', 'decanter', 'jar with lid', 'stopper', 'cork'] },
  { re: /\bflacons?\b/, en: 'flacon', guard: 'a small glass flacon (bottle) with a stopper', confusions: ['vase'] },
  { re: /\bbouteilles?\b/, en: 'bottle', guard: 'a bottle with a narrow neck', confusions: ['vase'] },
  { re: /\bcarafes?\b/, en: 'carafe', guard: 'a carafe for pouring water or wine' },
  { re: /\bpots?\s+de\s+fleurs?\b|\bcache[- ]?pots?\b/, en: 'flower pot', guard: 'a flower pot for a plant', confusions: ['vase'] },
  { re: /\bbocal|\bbocaux\b/, en: 'jar', guard: 'a glass jar' },
  { re: /\btasses?\b/, en: 'cup', guard: 'a cup with a handle', confusions: ['mug'] },
  { re: /\bmugs?\b/, en: 'mug', guard: 'a ceramic mug with a handle' },
  { re: /\bbols?\b/, en: 'bowl', guard: 'an open bowl' },
  { re: /\bassiettes?\b/, en: 'plate', guard: 'a flat plate' },
  { re: /\btheieres?\b/, en: 'teapot', guard: 'a teapot with spout, handle and lid' },
  { re: /\bverres?\s+a\s+vin\b|\bcoupes?\s+de\s+champagne\b/, en: 'wine glass', guard: 'a stemmed glass' },
  { re: /\bbougies?\b/, en: 'candle', guard: 'a candle with a wick' },
  { re: /\bbougeoirs?\b/, en: 'candle holder' },
  { re: /\blampes?\b/, en: 'lamp' },
  { re: /\bboites?\b|\bcoffrets?\b/, en: 'box', guard: 'a lidded box' },
  { re: /\bbagues?\b|\banneaux?\b/, en: 'ring', guard: 'a finger ring (jewelry)' },
  { re: /\bcolliers?\b/, en: 'necklace' },
  { re: /\bpendentifs?\b|\bmedaillons?\b/, en: 'pendant' },
  { re: /\bbracelets?\b/, en: 'bracelet' },
  { re: /\bboucles?\s+d['’ ]?oreilles?\b/, en: 'earrings' },
  { re: /\bmontres?\b/, en: 'wristwatch' },
  { re: /\bhorloges?\b|\bpendules?\b/, en: 'clock' },
  { re: /\bcadres?\s+photo\b|\bcadres?\b/, en: 'picture frame' },
  { re: /\bcoussins?\b/, en: 'cushion' },
  { re: /\bsacs?\s+a\s+main\b|\bsacs?\b/, en: 'bag' },
  { re: /\bchaussures?\b|\bbaskets?\b|\bsneakers?\b/, en: 'shoe' },
  { re: /\bgateaux?\b/, en: 'cake' },
  { re: /\bplaques?\b/, en: 'plaque', guard: 'a flat engraved plaque' },
  { re: /\btrophees?\b|\bcoupes?\b/, en: 'trophy' },
  { re: /\bmedailles?\b/, en: 'medal' },
  { re: /\bporte[- ]?cles?\b/, en: 'keychain' },
  { re: /\bt[- ]?shirts?\b|\btee[- ]?shirts?\b/, en: 't-shirt', guard: 'a t-shirt laid flat or on a hanger', confusions: ['person wearing the t-shirt'] },
  { re: /\bcasquettes?\b/, en: 'cap' },
  { re: /\bchaises?\b|\bfauteuils?\b/, en: 'chair' },
  { re: /\btables?\b/, en: 'table' },
  { re: /\bepees?\b|\bsabres?\b/, en: 'sword' },
  { re: /\bcasques?\b/, en: 'helmet', guard: 'an empty helmet, nobody wearing it' },
  { re: /\bcouteaux?\b/, en: 'knife' },
  { re: /\bstylos?\b/, en: 'pen' },
  { re: /\blivres?\b/, en: 'book' },
  { re: /\bcarnets?\b/, en: 'notebook' },
  { re: /\bpeluches?\b/, en: 'plush toy', figurative: true },
  { re: /\bstatuettes?\b|\bstatues?\b|\bfigurines?\b|\bbustes?\b/, en: 'statue', figurative: true },
  { re: /\bpoupees?\b/, en: 'doll', figurative: true },
  { re: /\bsculptures?\b/, en: 'sculpture' },
  { re: /\bvoitures?\b/, en: 'car' },
  { re: /\bmotos?\b/, en: 'motorcycle' },
  { re: /\bvelos?\b/, en: 'bicycle' },
  { re: /\bmaisons?\b/, en: 'house' },
  { re: /\bbouquets?\b/, en: 'bouquet of flowers' },
  { re: /\blogos?\b/, en: 'logo' },
]

const SHAPES: Array<[RegExp, string]> = [
  [/coeurs?|cœurs?/, 'heart'], [/etoiles?/, 'star'], [/lunes?|croissants?\s+de\s+lune/, 'crescent moon'],
  [/cercles?|ronds?|boules?|spheres?/, 'round'], [/carres?/, 'square'], [/cubes?/, 'cube'],
  [/gouttes?(?:\s+d['’ ]?eau)?/, 'teardrop'], [/fleurs?/, 'flower'], [/roses?/, 'rose'], [/papillons?/, 'butterfly'],
  [/diamants?/, 'diamond'], [/spirales?/, 'spiral'], [/triangles?/, 'triangle'], [/ovales?|oeufs?/, 'oval'],
  [/chats?/, 'cat'], [/hiboux?|chouettes?/, 'owl'], [/coquillages?/, 'seashell'], [/feuilles?/, 'leaf'],
  [/nuages?/, 'cloud'], [/arbres?/, 'tree'], [/pommes?/, 'apple'], [/hexagones?/, 'hexagon'], [/vagues?/, 'wave'],
  [/cranes?/, 'skull'], [/main/, 'hand'], [/visage/, 'face'],
]

const MATERIALS: Array<[RegExp, string]> = [
  [/\b(?:en\s+)?verre\s+souffle\b/, 'hand-blown glass'],
  [/\b(?:en\s+)?verre\b|\bvitre\b/, 'glass'], [/\bcristal\b/, 'crystal'],
  [/\b(?:en\s+)?ceramique\b/, 'ceramic'], [/\b(?:en\s+)?porcelaine\b/, 'porcelain'], [/\b(?:en\s+)?gres\b/, 'stoneware'],
  [/\bterre\s+cuite\b/, 'terracotta'], [/\b(?:en\s+)?bois\b/, 'wooden'], [/\b(?:en\s+)?marbre\b/, 'marble'],
  [/\b(?:en\s+)?pierre\b/, 'stone'], [/\b(?:en\s+)?metal\b/, 'metal'], [/\ben\s+or\b|\bdore(?:e)?\b/, 'gold'],
  [/\ben\s+argent\b|\bargente(?:e)?\b/, 'silver'], [/\b(?:en\s+)?cuivre\b/, 'copper'], [/\b(?:en\s+)?bronze\b/, 'bronze'],
  [/\b(?:en\s+)?laiton\b/, 'brass'], [/\b(?:en\s+)?acier\b/, 'steel'], [/\b(?:en\s+)?plastique\b/, 'plastic'],
  [/\b(?:en\s+)?cuir\b/, 'leather'], [/\b(?:en\s+)?tissu\b/, 'fabric'], [/\b(?:en\s+)?resine\b/, 'resin'],
]

const FINISHES: Array<[RegExp, string]> = [
  [/\btransparent(?:e)?s?\b/, 'transparent'], [/\bopaque\b/, 'opaque'], [/\bmat(?:e)?\b/, 'matte'],
  [/\bbrillant(?:e)?s?\b|\bvernis(?:se)?\b|\bemaille(?:e)?\b/, 'glossy glazed'],
]

const COLORS: Array<[RegExp, string]> = [
  [/\brouge(?:s)?\b/, 'red'], [/\brose(?:s)?\b(?!\s+(?:des|de))/, 'pink'], [/\bbleu(?:e|s|es)?\b/, 'blue'],
  [/\bvert(?:e|s|es)?\b/, 'green'], [/\bjaune(?:s)?\b/, 'yellow'], [/\borange(?:s)?\b/, 'orange'],
  [/\bviolet(?:te|s|tes)?\b/, 'purple'], [/\bnoir(?:e|s|es)?\b/, 'black'], [/\bblanc(?:he|s|hes)?\b/, 'white'],
  [/\bgris(?:e|es)?\b/, 'grey'], [/\bmarron\b|\bbrun(?:e)?\b/, 'brown'], [/\bturquoise\b/, 'turquoise'],
  [/\bbeige\b/, 'beige'], [/\bbordeaux\b/, 'burgundy'],
]

/** Une personne est réellement demandée (sujet humain, partie du corps, personnage). */
const HUMAN_REQUEST_RE = /\b(?:personnes?|gens|homme|hommes|femme|femmes|enfants?|bebes?|fille|filles|garcon|garcons|ado|adolescent(?:e)?|vieil(?:le|lard)|dame|monsieur|portrait|selfie|visage|personnage|perso|heros|heroine|guerrier(?:e)?|chevalier|mage|sorcier(?:e)?|ninja|samourai|pirate|princesse?|roi|reine|mannequin|modele\s+humain|tenu(?:e)?\s+(?:par|dans)|dans\s+(?:la|les|sa|ses)\s+mains?|main(?:s)?\s+qui|people|person|man|woman|girl|boy|child|human|character|someone|astronaute|cycliste|danseu(?:r|se)|famille|couple|bride|mariee?)\b/
const ANIMAL_REQUEST_RE = /\b(?:chats?|chatons?|chiens?|chiots?|oiseaux?|oiseau|chevaux|cheval|lapins?|renards?|loups?|lions?|tigres?|ours|poissons?|dragons?|papillons?|hiboux?|chouettes?|souris|elephants?|dauphins?|animal|animaux|creatures?|pokemon|cat|dog|bird|horse|animal|creature)\b/

/** mots anglais qui signalent une personne inventée par l'expansion */
const EN_HUMAN_RE = /\b(?:person|persons|people|woman|women|man|men|girl|girls|boy|boys|child|children|kid|lady|gentleman|someone|somebody|model|portrait|her|his|she|he|they are holding|holding it|in (?:her|his|their) hands?|hands? (?:holding|cradling|gripping)|fingers?|figure of a|human)\b/i
const EN_ANIMAL_RE = /\b(?:cat|kitten|dog|puppy|bird|horse|rabbit|fox|wolf|animal|creature|butterfly)\b/i

export type SubjectFidelity = {
  request: string
  /** texte exact à écrire dans l'image */
  inscriptions: string[]
  nounEn: string | null
  guard: string | null
  confusions: string[]
  shapeEn: string | null
  /** forme demandée sans traduction connue : transmise telle quelle */
  shapeFr: string | null
  materialEn: string | null
  finishEn: string | null
  colorEn: string | null
  wantsHuman: boolean
  wantsAnimal: boolean
  /** objet seul : aucune personne, main ni animal ne doit apparaître */
  objectOnly: boolean
  figurative: boolean
}

function norm(text: string): string {
  return (text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/œ/g, 'oe')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

function firstMatch<T>(table: Array<[RegExp, T]>, text: string): T | null {
  for (const [re, v] of table) if (re.test(text)) return v
  return null
}

export function analyzeSubjectFidelity(request: string): SubjectFidelity {
  const inscriptions = extractInscriptionTexts(request)
  // le texte à écrire ne décrit pas le sujet (« inscription Rose » n'est pas une couleur)
  const body = norm(stripInscriptionSpans(request))
  // l'objet principal est le premier nom d'objet de la demande
  let noun: NounEntry | null = null
  let nounAt = Infinity
  for (const entry of OBJECTS) {
    const m = entry.re.exec(body)
    if (m && m.index < nounAt) { noun = entry; nounAt = m.index }
  }
  const shapeMatch = body.match(/\ben\s+forme\s+(?:de\s+|d['’ ]\s*)(?:petit(?:e)?\s+|grand(?:e)?\s+)?([a-z'’ -]{2,30}?)(?=$|[\s,.;!?](?:avec|et|en|sur|dans|qui|de\s+couleur|aux?|a)\b|[,.;!?])/)
  const shapeEn = shapeMatch ? (firstMatch(SHAPES.map(([re, en]) => [new RegExp(`^(?:${re.source})$`), en] as [RegExp, string]), shapeMatch[1].trim()) ?? null) : null
  const shapeFr = shapeMatch?.[1]?.trim() ?? ''
  // « en forme de cœur » ne doit pas être lu comme une demande de visage, de main ou de chat
  const bodyNoShape = shapeMatch ? body.replace(shapeMatch[0], ' ') : body
  const wantsHuman = HUMAN_REQUEST_RE.test(bodyNoShape)
  const wantsAnimal = ANIMAL_REQUEST_RE.test(bodyNoShape)
  const figurative = Boolean(noun?.figurative)
  return {
    request: request.trim(),
    inscriptions,
    nounEn: noun?.en ?? null,
    guard: noun?.guard ?? null,
    confusions: noun?.confusions ?? [],
    shapeEn,
    shapeFr: shapeEn ? null : (shapeFr || null),
    materialEn: firstMatch(MATERIALS, bodyNoShape),
    finishEn: firstMatch(FINISHES, bodyNoShape),
    colorEn: firstMatch(COLORS, bodyNoShape),
    wantsHuman,
    wantsAnimal,
    objectOnly: Boolean(noun) && !wantsHuman && !wantsAnimal && !figurative,
    figurative,
  }
}

function article(word: string): string {
  return /^[aeiou]/i.test(word) ? 'an' : 'a'
}

/**
 * Phrase de tête du prompt positif : l'objet, sa catégorie, sa forme, sa
 * matière et le texte exact. Vide quand aucun objet n'est reconnu (le prompt
 * existant reste alors seul maître).
 */
export function buildSubjectLockLine(f: SubjectFidelity): string {
  if (!f.nounEn) return ''
  const descriptors = [f.colorEn, f.finishEn, f.shapeEn ? `${f.shapeEn}-shaped` : null, f.materialEn].filter(Boolean) as string[]
  const core = `${descriptors.join(' ')} ${f.nounEn}`.trim()
  // avec une personne demandée, l'objet est un élément exact de la scène, pas le seul sujet
  const parts = [f.wantsHuman || f.wantsAnimal ? `Requested object: ${article(core)} ${core}` : `Main subject: ${article(core)} single ${core}`]
  if (f.guard) parts.push(`it is ${f.guard}`)
  if (f.shapeEn) parts.push(`its whole silhouette and body are clearly shaped like a ${f.shapeEn}`)
  else if (f.shapeFr) parts.push(`its whole silhouette is shaped like « ${f.shapeFr} » (French)`)
  if (f.inscriptions.length) {
    parts.push(`with the inscription ${f.inscriptions.map((t) => `"${t}"`).join(' and ')} clearly lettered on its surface, spelled exactly as written`)
  }
  let line = `${parts.join(', ')}.`
  if (f.objectOnly) {
    line += ` Still life: the ${f.nounEn} is the only subject, standing on its own, unattended, nobody in the frame.`
  }
  return line
}

/** Ligne du texte exact quand il n'y a pas d'objet reconnu (tableau, affiche…). */
export function buildInscriptionLine(f: SubjectFidelity): string {
  if (!f.inscriptions.length) return ''
  return `Exact lettering required: ${f.inscriptions.map((t) => `"${t}"`).join(', ')} — written once, spelled exactly letter for letter, no other words or letters.`
}

/** Demande d'origine, lue telle quelle par l'encodeur Mistral de FLUX.2 (multilingue). */
export function buildVerbatimRequestLine(request: string): string {
  const clean = request.replace(/\s+/g, ' ').trim()
  return clean ? `Original user request (authoritative, French): « ${clean} ».` : ''
}

/** Termes du vrai prompt négatif (CFGGuider) propres à la demande. */
export function fidelityNegativeTerms(f: SubjectFidelity): string[] {
  const out: string[] = []
  // objet seul : personne, main ni animal ; un paysage ou une scène garde sa liberté de figurants
  if (f.objectOnly) {
    out.push('person', 'people', 'woman', 'man', 'child', 'human face', 'portrait', 'hands', 'fingers', 'human body', 'mannequin', 'animal')
    out.push('blurry', 'low detail', 'watermark', 'extra objects', 'duplicate object')
  }
  out.push(...f.confusions)
  if (f.inscriptions.length) out.push('misspelled lettering', 'extra words', 'random letters')
  return out
}

export type ExpansionCheck = { ok: boolean; reasons: string[] }

/**
 * Contrôle de l'expansion écrite par le LLM : refusée si elle invente une
 * personne ou un animal, perd l'objet demandé, ou le remplace par une
 * catégorie voisine (vase → flacon).
 */
export function checkExpansionFidelity(expanded: string, f: SubjectFidelity): ExpansionCheck {
  const text = expanded || ''
  const reasons: string[] = []
  if (!f.wantsHuman && !f.figurative && EN_HUMAN_RE.test(text)) reasons.push('personne inventée')
  if (!f.wantsAnimal && !f.figurative && EN_ANIMAL_RE.test(text) && !(f.shapeEn && EN_ANIMAL_RE.test(f.shapeEn))) reasons.push('animal inventé')
  if (f.nounEn && !new RegExp(`\\b${f.nounEn.replace(/[-\s]+/g, '[-\\s]?')}s?\\b`, 'i').test(text)) reasons.push(`objet « ${f.nounEn} » absent`)
  for (const c of f.confusions) {
    if (new RegExp(`\\b${c.replace(/\s+/g, '\\s+')}s?\\b`, 'i').test(text)) { reasons.push(`catégorie voisine « ${c} »`); break }
  }
  for (const t of f.inscriptions) {
    if (!text.toLowerCase().includes(t.toLowerCase())) { reasons.push(`texte « ${t} » absent`); break }
  }
  return { ok: reasons.length === 0, reasons }
}

/** Retire d'un texte anglais les phrases qui ajoutent une personne non demandée. */
export function stripUnrequestedHumans(text: string, f: SubjectFidelity): string {
  if (f.wantsHuman || f.figurative) return text
  return text
    .split(/(?<=[.!?])\s+/)
    .filter((sentence) => !EN_HUMAN_RE.test(sentence) && !/\b(?:skin|pores?|anatomy|facial|identity)\b/i.test(sentence))
    .join(' ')
    .trim()
}
