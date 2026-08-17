// ---------------------------------------------------------------------------
// codePromptHints — lire ce que le brief demande, pas ce qui y ressemble.
//
// Deux fautes mesurees sur le brief reel de la Brulerie Nomade (run 1161).
//
// 1. RECHERCHE PAR SOUS-CHAINE. `detectDesignArchetype` testait
//    `text.includes(hint)`. L indice `'ide'` est tombe dans le mot francais
//    « idee »:
//
//      « …trouve mieux si t'as une IDEe), et direct en dessous nos cafes… »
//
//    Une brulerie de cafe lyonnaise a donc ete classee `ide_code_editor`, et la
//    design-spec a exige d elle la palette violet sombre d un editeur de code.
//
// 2. AVEUGLEMENT A LA NEGATION. La cliente ecrit, textuellement:
//
//      « on n'est PAS un truc minimaliste blanc scandinave comme tout le monde
//        fait pour le cafe en ce moment, j'en ai marre de voir ca partout »
//
//    Le mot « minimaliste » y est present — comme REFUS. Une porte qui compte
//    les occurrences lit ce refus comme une commande. C est le motif du run 1021
//    (« le juge reclamait le gadget que la cliente avait refuse »), et le motif
//    de toute cette serie: decider sur une chose qu on n a jamais vraiment
//    mesuree.
//
// Ici un indice ne compte que s il apparait comme MOT ENTIER et qu il n est pas
// NIE dans sa propre proposition. La portee de la negation s arrete a la
// ponctuation: « pas de tableau de bord, juste un blog » demande bien un blog.
// ---------------------------------------------------------------------------

/** Frontiere de proposition: une negation ne franchit pas la ponctuation. */
const CLAUSE_BREAK = '§'

/** Fenetre de negation, en caracteres avant l indice. */
const NEGATION_WINDOW = 40

const NEGATION_MARKERS = [
  'pas', 'plus', 'sans', 'jamais', 'aucun', 'aucune', 'ni', 'non',
  'marre de', 'marre des', 'eviter', 'evite', 'evitez', 'fini les',
  'surtout pas', 'not', 'no', 'without', 'avoid', 'never',
]

/**
 * Texte normalise pour la recherche d indices: minuscules, diacritiques
 * retires, ponctuation reduite a une frontiere de proposition, tout le reste
 * aplati en espaces. Le resultat est encadre d espaces pour que la recherche de
 * mot entier soit une simple inclusion.
 */
export function normalizeHintText(text: string): string {
  const flat = String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[,.;:!?()[\]{}\n\r•—–]+/g, ` ${CLAUSE_BREAK} `)
    .replace(/[^a-z0-9§]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return ` ${flat} `
}

/** Indice normalise, encadre d espaces: la recherche devient exacte au mot. */
function normalizeHint(hint: string): string {
  const inner = normalizeHintText(hint).replace(new RegExp(CLAUSE_BREAK, 'g'), ' ').replace(/\s+/g, ' ').trim()
  return inner ? ` ${inner} ` : ''
}

/**
 * L indice est-il NIE a cette position ? On remonte jusqu a la frontiere de
 * proposition la plus proche, sans depasser `NEGATION_WINDOW` caracteres.
 */
export function isNegatedAt(normalizedText: string, index: number): boolean {
  const from = Math.max(0, index - NEGATION_WINDOW)
  let window = normalizedText.slice(from, index)
  const lastBreak = window.lastIndexOf(CLAUSE_BREAK)
  if (lastBreak >= 0) window = window.slice(lastBreak + 1)
  return NEGATION_MARKERS.some((marker) => window.includes(` ${marker} `))
}

/**
 * Variantes acceptees d un indice: le mot exact et ses pluriels. Un brief reel
 * ecrit « nos stores » ou « des dashboards ». Le suffixe ne porte que sur le
 * DERNIER mot, et il n ouvre aucune breche de sous-chaine: « idees » ne
 * contient toujours pas le mot « ide ».
 */
function hintVariants(hint: string): string[] {
  const needle = normalizeHint(hint)
  if (!needle) return []
  const core = needle.trim()
  const variants = [core, `${core}s`]
  // `es` rouvrirait le trou qu on vient de fermer sur les indices COURTS:
  // `ide` + `es` = `idees`, et le brief de la Brulerie ecrit « des idées ».
  // Mesure faite: le premier jet de ce module a re-classe la brulerie en IDE
  // par cette seule variante. Au-dela de 4 lettres, l accident n existe plus.
  const lastWord = core.split(' ').pop() ?? core
  if (lastWord.length >= 5) variants.push(`${core}es`)
  return [...new Set(variants)].map((v) => ` ${v} `)
}

function occurrencesOf(normalizedText: string, needle: string): number[] {
  const found: number[] = []
  let from = 0
  for (;;) {
    // Les espaces encadrants se chevauchent entre deux occurrences adjacentes:
    // on repart sur le dernier espace, jamais apres.
    const at = normalizedText.indexOf(needle, from)
    if (at < 0) break
    found.push(at + 1)
    from = at + needle.length - 1
  }
  return found
}

/**
 * Toutes les positions ou l indice apparait comme mot entier, negations
 * comprises — utile pour expliquer un verdict.
 */
export function hintOccurrences(normalizedText: string, hint: string): number[] {
  const found = new Set<number>()
  for (const variant of hintVariants(hint)) {
    for (const at of occurrencesOf(normalizedText, variant)) found.add(at)
  }
  return [...found].sort((a, b) => a - b)
}

/** L indice est-il REELLEMENT demande: mot entier, et au moins une occurrence non niee ? */
export function matchesHint(normalizedText: string, hint: string): boolean {
  return hintOccurrences(normalizedText, hint).some((at) => !isNegatedAt(normalizedText, at))
}

/** Un seul indice suffit — mais aucun indice nie ne suffit. */
export function matchesAnyHint(normalizedText: string, hints: string[]): boolean {
  return hints.some((hint) => matchesHint(normalizedText, hint))
}

/** Les indices reellement demandes, dans l ordre de la liste fournie. */
export function matchedHints(normalizedText: string, hints: string[]): string[] {
  return hints.filter((hint) => matchesHint(normalizedText, hint))
}
