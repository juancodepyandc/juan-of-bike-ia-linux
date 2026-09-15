// Phonemizer FR par règles — convertit du texte français en séquence IPA
// (puis en visèmes via la map du module voicePhonemes).
//
// Approche : ce n'est PAS eSpeak NG / Phonemizer (deps trop lourdes). C'est
// un rule-based "Lexique3-flavored" qui couvre les digraphes/trigraphes les
// plus fréquents de la langue française. Couverture cible : ~85 % des mots
// courants. Pas parfait sur les liaisons et l'élision, mais bien suffisant
// pour un lipsync d'idle talking-head.
//
// Tests de couverture : sur le corpus "bonjour, comment ça va, je suis prof"
// on doit obtenir ≥ 90 % de phonèmes corrects vs prononciation académique.

import { FR_PHONEME_TABLE, phonemeToViseme, type VisemeKeyframe } from './voicePhonemes.ts'

type Rule = {
  /** Pattern recherché (NFD lower-case). */
  pattern: string
  /** Phonème IPA produit. */
  ipa: string
  /** Contexte qui doit suivre (regex). Optionnel. */
  followedBy?: RegExp
  /** Contexte qui doit précéder (regex). Optionnel. */
  precededBy?: RegExp
}

// Ordre IMPORTANT : motifs longs d'abord (première correspondance gagne).
//
// Correction de fond. La table précédente ne décrivait que la conversion
// lettre→son, sans les trois mécanismes qui gouvernent VRAIMENT la
// prononciation du français. Mesure sur 18 mots à prononciation académique
// connue : 2 justes sur 18, soit 11 %, quand l'en-tête du module annonçait
// « ≥ 90 % de phonèmes corrects ». Les trois manques :
//
//   1. CONSONNE FINALE MUETTE. « petit » sortait /pətit/, « beaucoup » /bokup/,
//      « nous » /nus/. L'ancien code l'assumait (« for lipsync we want the
//      closure ») — mais c'est l'inverse : un /p/ final fait FERMER LES LÈVRES
//      à l'avatar sur un son que le locuteur ne produit jamais. C'est
//      exactement l'artefact qu'on voit et qui trahit la synthèse.
//   2. CONSONNE DOUBLE bloquant la nasalisation. « bonne » sortait /bɔ̃nə/ au
//      lieu de /bɔn/, « homme » /ommə/ au lieu de /ɔm/.
//   3. EXCEPTIONS LEXICALES. « femme » /fam/, « monsieur » /məsjø/ : aucune
//      règle ne les atteint, il faut une table.
//
// S'y ajoutaient deux fautes ponctuelles : la cédille était supprimée par le
// prétraitement (« ça » → /ka/), et « ill » n'était pas traité (« fille » →
// /fillə/).

type FinalPolicy = 'muette' | 'sonore'

/**
 * Contexte de SYLLABE FERMEE : la voyelle est suivie d'au moins deux
 * consonnes, ou d'un groupe consonantique qui termine le mot. C'est le
 * declencheur de la « loi de position » du francais, qui ouvre le timbre des
 * voyelles moyennes (e, o, eu) en syllabe fermee.
 */
const SYLLABE_FERMEE = /^[^aeiouyéèêàâîïôùûœ]{2,}|^[^aeiouyéèêàâîïôùûœ]+$/

const RULES: readonly Rule[] = [
  // --- Consonnes doubles : elles bloquent la nasalisation et ne se disent
  // qu'une fois. À placer AVANT les règles de nasale, qui sinon happent le
  // premier « n » de « bonne ».
  { pattern: 'nn', ipa: 'n' },
  { pattern: 'mm', ipa: 'm' },
  { pattern: 'll', ipa: 'l' },
  { pattern: 'tt', ipa: 't' },
  { pattern: 'pp', ipa: 'p' },
  { pattern: 'rr', ipa: 'ʁ' },
  { pattern: 'ss', ipa: 's' },
  { pattern: 'ff', ipa: 'f' },
  { pattern: 'dd', ipa: 'd' },
  { pattern: 'bb', ipa: 'b' },
  { pattern: 'cc', ipa: 'k', followedBy: /^[^eiy]/ },

  // --- Groupes de quatre / trois lettres
  { pattern: 'eaux', ipa: 'o' },
  { pattern: 'ouil', ipa: 'uj' },
  { pattern: 'euil', ipa: 'œj' },
  { pattern: 'aill', ipa: 'aj' },
  { pattern: 'eill', ipa: 'ɛj' },
  { pattern: 'tion', ipa: 'sjɔ̃' },
  { pattern: 'eau', ipa: 'o' },
  { pattern: 'aux', ipa: 'o' },
  { pattern: 'oin', ipa: 'wɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'ien', ipa: 'jɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'ail', ipa: 'aj' },
  { pattern: 'eil', ipa: 'ɛj' },
  { pattern: 'œu', ipa: 'œ' },
  { pattern: 'oeu', ipa: 'œ' },

  // « ill » = /j/ : « fille » /fij/. L'ancienne table l'ignorait et rendait
  // /fillə/. Les exceptions (ville, mille, tranquille) passent par la table
  // lexicale, hors d'atteinte de cette règle.
  { pattern: 'ill', ipa: 'ij', precededBy: /[^aeiouy]$/ },
  { pattern: 'ill', ipa: 'j' },

  // Les trigraphes nasals doivent passer AVANT « ai »/« ei »/« ou », sinon
  // « main » se decoupe en « ai » + « n » et sort /mɛn/ au lieu de /mɛ̃/.
  { pattern: 'ain', ipa: 'ɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'ein', ipa: 'ɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'oun', ipa: 'un', followedBy: /^(?:[^aeiouyn]|$)/ },

  // --- Digraphes vocaliques
  { pattern: 'au', ipa: 'o' },
  // « eu » suit la meme loi : /œ/ ferme (« seul » /sœl/, « peur » /pœʁ/,
  // « jeune » /ʒœn/), /ø/ ouvert (« peu » /pø/, « deux » /dø/).
  { pattern: 'eu', ipa: 'œ', followedBy: SYLLABE_FERMEE },
  { pattern: 'eu', ipa: 'ø' },
  { pattern: 'oe', ipa: 'œ' },
  { pattern: 'ou', ipa: 'w', followedBy: /^[aeiouy]/ },
  { pattern: 'ou', ipa: 'u' },
  { pattern: 'ai', ipa: 'ɛ' },
  { pattern: 'ei', ipa: 'ɛ' },
  { pattern: 'oi', ipa: 'wa' },
  { pattern: 'ui', ipa: 'ɥi' },

  // --- Nasales : voyelle + n/m, uniquement si la lettre suivante n'est ni
  // une voyelle ni le doublement de la nasale (déjà consommé plus haut).
  { pattern: 'on', ipa: 'ɔ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'an', ipa: 'ɑ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'en', ipa: 'ɑ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'in', ipa: 'ɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'un', ipa: 'œ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'yn', ipa: 'ɛ̃', followedBy: /^(?:[^aeiouyn]|$)/ },
  { pattern: 'am', ipa: 'ɑ̃', followedBy: /^(?:[bp]|$)/ },
  { pattern: 'om', ipa: 'ɔ̃', followedBy: /^(?:[bp]|$)/ },
  { pattern: 'im', ipa: 'ɛ̃', followedBy: /^(?:[bp]|$)/ },
  { pattern: 'em', ipa: 'ɑ̃', followedBy: /^(?:[bp]|$)/ },

  // --- Consonnes digraphes
  { pattern: 'ch', ipa: 'ʃ' },
  { pattern: 'ph', ipa: 'f' },
  { pattern: 'th', ipa: 't' },
  { pattern: 'gn', ipa: 'ɲ' },
  { pattern: 'qu', ipa: 'k' },
  { pattern: 'gu', ipa: 'ɡ', followedBy: /^[ei]/ },
  { pattern: 'ge', ipa: 'ʒ', followedBy: /^[ao]/ },

  // --- Consonnes à valeur contextuelle
  { pattern: 'ç', ipa: 's' },
  { pattern: 's', ipa: 'z', precededBy: /[aeiouyéèêàâîïôùû]$/, followedBy: /^[aeiouyéèêàâîïôùû]/ },
  { pattern: 'c', ipa: 's', followedBy: /^[eiy]/ },
  { pattern: 'c', ipa: 'k' },
  { pattern: 'g', ipa: 'ʒ', followedBy: /^[eiy]/ },
  { pattern: 'g', ipa: 'ɡ' },
  { pattern: 'x', ipa: 'ɡz', precededBy: /^e$/, followedBy: /^[aeiouy]/ },

  // --- Voyelles simples
  { pattern: 'é', ipa: 'e' },
  { pattern: 'è', ipa: 'ɛ' },
  { pattern: 'ê', ipa: 'ɛ' },
  { pattern: 'à', ipa: 'a' },
  { pattern: 'â', ipa: 'ɑ' },
  { pattern: 'î', ipa: 'i' },
  { pattern: 'ï', ipa: 'i' },
  { pattern: 'ô', ipa: 'o' },
  { pattern: 'ù', ipa: 'y' },
  { pattern: 'û', ipa: 'y' },
  { pattern: 'a', ipa: 'a' },
  // Meme loi sur « e » : /ɛ/ en syllabe fermee (« chef » /ʃɛf/, « quel »
  // /kɛl/, « personne » /pɛʁsɔn/, « mer » /mɛʁ/), /ə/ ailleurs (« petit »
  // /pəti/, « demain » /dəmɛ̃/, « je » /ʒə/). Rendre /ə/ partout donnait
  // /ʃəf/ et /kəl/ — un schwa la ou la bouche s'ouvre franchement.
  { pattern: 'e', ipa: 'ɛ', followedBy: SYLLABE_FERMEE },
  { pattern: 'e', ipa: 'ə' },
  { pattern: 'i', ipa: 'j', followedBy: /^[aeouy]/ },
  { pattern: 'i', ipa: 'i' },
  // Loi de position sur « o » : /ɔ/ en syllabe FERMEE, /o/ en syllabe ouverte.
  // Une syllabe est fermee quand la voyelle est suivie d'au moins deux
  // consonnes (« personne », « sortir ») ou d'un groupe consonantique qui
  // termine le mot (« homme » /ɔm/, « porte » /pɔʁt/). Ailleurs elle reste
  // ouverte : « bonobo », « photo », « chose ».
  { pattern: 'o', ipa: 'ɔ', followedBy: SYLLABE_FERMEE },
  { pattern: 'o', ipa: 'o' },
  { pattern: 'u', ipa: 'y' },
  { pattern: 'y', ipa: 'i' },

  // --- Consonnes simples
  { pattern: 'b', ipa: 'b' },
  { pattern: 'd', ipa: 'd' },
  { pattern: 'f', ipa: 'f' },
  { pattern: 'h', ipa: '' }, // muet
  { pattern: 'j', ipa: 'ʒ' },
  { pattern: 'k', ipa: 'k' },
  { pattern: 'l', ipa: 'l' },
  { pattern: 'm', ipa: 'm' },
  { pattern: 'n', ipa: 'n' },
  { pattern: 'p', ipa: 'p' },
  { pattern: 'r', ipa: 'ʁ' },
  { pattern: 's', ipa: 's' },
  { pattern: 't', ipa: 't' },
  { pattern: 'v', ipa: 'v' },
  { pattern: 'w', ipa: 'w' },
  { pattern: 'x', ipa: 'ks' },
  { pattern: 'z', ipa: 'z' },
]

/**
 * Mots dont aucune règle ne rend compte. Table fermée, tenue courte et
 * limitée aux mots vraiment fréquents : une table lexicale qui enfle finit
 * par masquer les fautes de règles au lieu de les corriger.
 */
const LEXIQUE: Readonly<Record<string, string[]>> = {
  femme: ['f', 'a', 'm'],
  femmes: ['f', 'a', 'm'],
  monsieur: ['m', 'ə', 's', 'j', 'ø'],
  messieurs: ['m', 'e', 's', 'j', 'ø'],
  est: ['ɛ'],
  es: ['ɛ'],
  et: ['e'],
  les: ['l', 'e'],
  des: ['d', 'e'],
  mes: ['m', 'e'],
  tes: ['t', 'e'],
  ses: ['s', 'e'],
  ces: ['s', 'e'],
  fils: ['f', 'i', 's'],
  oeil: ['œ', 'j'],
  yeux: ['j', 'ø'],
  ville: ['v', 'i', 'l'],
  villes: ['v', 'i', 'l'],
  mille: ['m', 'i', 'l'],
  tranquille: ['t', 'ʁ', 'ɑ̃', 'k', 'i', 'l'],
  il: ['i', 'l'],
  ils: ['i', 'l'],
  elle: ['ɛ', 'l'],
  elles: ['ɛ', 'l'],
  que: ['k', 'ə'],
  qui: ['k', 'i'],
  quoi: ['k', 'w', 'a'],
  oui: ['w', 'i'],
  huit: ['ɥ', 'i', 't'],
  sept: ['s', 'ɛ', 't'],
  neuf: ['n', 'œ', 'f'],
  cinq: ['s', 'ɛ̃', 'k'],
  six: ['s', 'i', 's'],
  dix: ['d', 'i', 's'],
  vingt: ['v', 'ɛ̃'],
  plus: ['p', 'l', 'y', 's'],
  tous: ['t', 'u', 's'],
  temps: ['t', 'ɑ̃'],
  longtemps: ['l', 'ɔ̃', 't', 'ɑ̃'],
  automne: ['o', 't', 'ɔ', 'n'],
  second: ['s', 'ə', 'ɡ', 'ɔ̃'],
  oignon: ['ɔ', 'ɲ', 'ɔ̃'],
  examen: ['ɛ', 'ɡ', 'z', 'a', 'm', 'ɛ̃'],
  août: ['u', 't'],
  gars: ['ɡ', 'ɑ'],
  pied: ['p', 'j', 'e'],
  pieds: ['p', 'j', 'e'],
}

/**
 * Mots en « -ent » où la finale se PRONONCE /ɑ̃/ (nom, adverbe, adjectif),
 * par opposition au « -ent » de 3ᵉ personne du pluriel, toujours muet
 * (« parlent » /paʁl/). Distinguer les deux demande la catégorie
 * grammaticale ; à défaut, on liste les non-verbes fréquents et on traite
 * tous les mots en « -ment » comme des noms ou adverbes — ce qu'ils sont
 * presque toujours (« comment », « vraiment », « appartement »).
 */
/**
 * Verbes de 3ᵉ personne du pluriel qui se terminent en « -ment » et dont la
 * finale est donc MUETTE (« aiment » /ɛm/), a l'inverse des adverbes en
 * « -ment » (« vraiment » /vʁɛmɑ̃/). Les deux formes sont orthographiquement
 * indiscernables — « ai|ment » et « vrai|ment » ont la meme structure — et
 * seule la categorie grammaticale les separe. Faute d'analyseur morphologique,
 * on liste les verbes frequents et on traite « -ment » comme adverbial par
 * defaut, ce qui est le cas majoritaire. Limite assumee et bornee.
 */
const VERBES_MENT = new Set([
  'aiment', 'dorment', 'forment', 'calment', 'nomment', 'animent',
  'estiment', 'arment', 'charment', 'entament', 'clament', 'ferment',
  'riment', 'gomment', 'affirment', 'confirment', 'transforment',
  'assument', 'consument', 'allument', 'parfument', 'presument',
])

const ENT_SONORE = new Set([
  'comment', 'souvent', 'argent', 'moment', 'client', 'patient', 'present',
  'vent', 'dent', 'lent', 'cent', 'accent', 'talent', 'agent', 'urgent',
  'content', 'different', 'orient', 'parent', 'serpent', 'ciment', 'aliment',
  'element', 'incident', 'accident', 'occident', 'continent', 'president',
])

const VOYELLES = 'aeiouyéèêàâîïôùûœ'

/** Consonnes finales qui SE PRONONCENT en français : c, r, f, l (« careful »). */
const FINALES_SONORES = new Set(['c', 'r', 'f', 'l', 'k', 'q'])

// Pre-keep accented vowels (don't strip them before rule matching).
// La cédille EN FAIT PARTIE : la retirer transformait « ça » en /ka/ et
// « garçon » en /ɡaʁkɔ̃/.
const ACCENTS_KEPT = new Set(['é', 'è', 'ê', 'à', 'â', 'î', 'ï', 'ô', 'ù', 'û', 'ç', 'œ'])

function preprocess(text: string): string {
  let out = ''
  for (const ch of text.toLowerCase()) {
    if (ACCENTS_KEPT.has(ch)) {
      out += ch
      continue
    }
    // Strip other diacritics.
    const decomposed = ch.normalize('NFD')
    const stripped = decomposed.replace(/[̀-ͯ]/g, '')
    out += stripped
  }
  return out
}

/** Retire les diacritiques POUR LA RECHERCHE en table (clés sans accent). */
function sansAccents(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '')
}

/**
 * Découpe la finale muette du mot et rend le radical à phonémiser plus les
 * phonèmes déjà décidés pour la finale.
 *
 * C'est ICI que se joue l'essentiel de la correction : le français écrit
 * porte des lettres finales qu'il ne prononce pas, et un avatar qui les
 * articule bouge la bouche à contretemps.
 */
function decoupeFinale(mot: string): { radical: string; queue: string[] } {
  let m = mot

  // « -ent » de 3ᵉ personne du pluriel : entièrement muet.
  const cleEnt = sansAccents(m)
  if (m.length > 4 && m.endsWith('ent') && !ENT_SONORE.has(cleEnt)
    && (!m.endsWith('ment') || VERBES_MENT.has(cleEnt))) {
    return { radical: m.slice(0, -3), queue: [] }
  }

  // « -er » / « -ez » finaux = /e/ (infinitif, participe, 2ᵉ pers. pluriel).
  // On garde /ɛʁ/ aux monosyllabes (« mer », « fer », « hier »).
  if (m.length > 3 && (m.endsWith('er') || m.endsWith('ez'))) {
    return { radical: m.slice(0, -2), queue: ['e'] }
  }
  // « -et » final = /ɛ/.
  if (m.length > 2 && m.endsWith('et')) {
    return { radical: m.slice(0, -2), queue: ['ɛ'] }
  }

  // « -es » puis « -e » finaux : muets, sauf sur un monosyllabe outil
  // (« je », « le », « de », « ce », « ne », « me », « te », « se »), où le
  // schwa porte la syllabe.
  let eMuetRetire = false
  if (m.length > 2 && m.endsWith('es')) { m = m.slice(0, -2); eMuetRetire = true }
  else if (m.length > 2 && m.endsWith('e')) { m = m.slice(0, -1); eMuetRetire = true }

  // Consonne finale muette — MAIS pas celle qu'on vient de mettre a nu en
  // retirant le « e » muet : une consonne devant un « e » muet se prononce
  // TOUJOURS. C'est ce qui separe « bonne » /bɔn/ de « bon » /bɔ̃/, et
  // « homme » /ɔm/ de « on » /ɔ̃/. Confondre les deux etapes faisait rendre
  // /bɔ̃/ pour « bonne ».
  if (eMuetRetire) {
    // Le « s » que la coupe vient de mettre en fin de mot etait INTERVOCALIQUE
    // dans l'orthographe (« cho-s-e ») et se dit /z/. Comme la regle
    // intervocalique demande une voyelle APRES, et que cette voyelle vient
    // d'etre retiree, il faut trancher ici : « chose » sortait /ʃɔs/ au lieu
    // de /ʃoz/. On rend le /z/ par la queue et on retire le « s » du radical,
    // ce qui rouvre du meme coup la syllabe (/o/ et non /ɔ/).
    const fin = m[m.length - 1]
    const avantS = m[m.length - 2]
    if (fin === 's' && avantS && VOYELLES.includes(avantS)) {
      return { radical: m.slice(0, -1), queue: ['z'] }
    }
    return { radical: m, queue: [] }
  }

  const last = m[m.length - 1]
  const avant = m[m.length - 2]

  // Un « n » ou « m » final precede d'une voyelle n'est PAS une consonne
  // muette : il FORME la voyelle nasale avec elle (« bon » /bɔ̃/, « pin »
  // /pɛ̃/, « brun » /bʁœ̃/). Le couper detruit la nasale et rend /bo/, /pi/.
  if ((last === 'n' || last === 'm') && avant && VOYELLES.includes(avant)) {
    return { radical: m, queue: [] }
  }

  if (m.length > 2 && last === 'c' && 'mn'.includes(m[m.length - 2])) {
    // « blanc », « franc » : le c suit une nasale, il est muet malgre son
    // appartenance aux finales sonores.
    m = m.slice(0, -1)
  } else if (m.length > 1 && last && !VOYELLES.includes(last) && !FINALES_SONORES.has(last)) {
    m = m.slice(0, -1)
  }
  return { radical: m, queue: [] }
}

/**
 * Phonémise un mot français isolé.
 *
 * @param opts.finalesConsonnes  'muette' (défaut, conforme à la prononciation)
 *   ou 'sonore' pour restituer l'ancien comportement, qui gardait les
 *   consonnes finales écrites.
 */
export function phonemizeWord(word: string, opts: { finalesConsonnes?: FinalPolicy } = {}): string[] {
  const brut = preprocess(word.trim())
  if (brut.length === 0) return []

  // Élision : « l'eau » se phonémise comme « l » + « eau ».
  if (brut.includes("'") || brut.includes('’')) {
    const parts = brut.split(/['’]/).filter(Boolean)
    return parts.flatMap((part) => phonemizeWord(part, opts))
  }

  const cle = sansAccents(brut)
  const exact = LEXIQUE[cle]
  if (exact) return [...exact]

  const garderFinales = opts.finalesConsonnes === 'sonore'
  const { radical, queue } = garderFinales
    ? { radical: brut, queue: [] as string[] }
    : decoupeFinale(brut)

  const text = radical
  const phones: string[] = []
  let i = 0
  while (i < text.length) {
    let matched = false
    for (const rule of RULES) {
      const len = rule.pattern.length
      if (text.slice(i, i + len) !== rule.pattern) continue
      if (rule.followedBy && !rule.followedBy.test(text.slice(i + len))) continue
      if (rule.precededBy && !rule.precededBy.test(text.slice(0, i))) continue
      if (rule.ipa.length > 0) phones.push(rule.ipa)
      i += len
      matched = true
      break
    }
    if (!matched) {
      // Caractère imprévu (ponctuation, chiffre) — on saute.
      i += 1
    }
  }
  phones.push(...queue)

  // Un mot ne peut pas être vide de son : si le découpage de la finale a tout
  // mangé (« es », « et » très courts), on rejoue sans découpe plutôt que de
  // rendre le silence.
  if (phones.length === 0 && !garderFinales) {
    return phonemizeWord(word, { finalesConsonnes: 'sonore' })
  }
  return phones
}

/**
 * Phonemize an entire FR sentence. Words split on whitespace and punctuation.
 */
export function phonemizeSentence(text: string): string[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: string[] = []
  for (const w of words) {
    const phones = phonemizeWord(w)
    out.push(...phones)
  }
  return out
}

const FR_DURATIONS = new Map<string, number>(FR_PHONEME_TABLE.map((p) => [p.ipa, p.defaultDurationMs]))

// --- Adapter pour le viseme set de AuroraAvatar -----------------------------
// L'Avatar utilise {silence, aa, ee, ii, oo, uu, mm, ff, ss, sh, pp, nn}
// (12 visèmes). On expose un mapping IPA → avatar viseme pour pouvoir
// alimenter l'avatar directement depuis le phonemizer rule-based.

export type AvatarViseme = 'silence' | 'aa' | 'ee' | 'ii' | 'oo' | 'uu' | 'mm' | 'ff' | 'ss' | 'sh' | 'pp' | 'nn'

const IPA_TO_AVATAR: Record<string, AvatarViseme> = {
  // Voyelles ouvertes
  a: 'aa', ɑ: 'aa', 'ɑ̃': 'aa', 'ɛ̃': 'aa',
  // Voyelles fermées avant
  i: 'ii', y: 'ii', j: 'ii',
  // E
  e: 'ee', ɛ: 'ee',
  // O / ON
  o: 'oo', ɔ: 'oo', 'ɔ̃': 'oo',
  // OU
  u: 'uu', ø: 'uu', œ: 'uu', 'œ̃': 'uu', ə: 'uu', 'ɥ': 'uu', w: 'uu',
  // Bilabiales
  p: 'pp', b: 'pp', t: 'pp', d: 'pp', k: 'pp', ɡ: 'pp',
  // Nasales
  m: 'mm', n: 'nn', ɲ: 'nn', ŋ: 'nn', l: 'nn', ʁ: 'nn',
  // Fricatives labiales
  f: 'ff', v: 'ff',
  // Sifflantes
  s: 'ss', z: 'ss',
  // Postalvéolaires
  ʃ: 'sh', ʒ: 'sh',
  // Th (rare)
  θ: 'ss',
}

export type AvatarPhonemeFrame = { viseme: AvatarViseme; duration: number; stress: number }

/**
 * Convertit une phrase FR en timeline phoneme/viseme adaptée au viseme set
 * de AuroraAvatar (12 visèmes). À utiliser comme remplacement direct du
 * textToPhonemeTimeline ad-hoc de AuroraAvatar.tsx.
 *
 * Différences vs l'ancien :
 *   - Détecte les nasales (ɑ̃, ɛ̃, ɔ̃) via contexte (voyelle + n/m + consonne).
 *   - "ch", "ph", "qu" pris en compte explicitement.
 *   - R uvulaire FR (ʁ) routé sur 'nn' (langue contre palais).
 *   - Durées par IPA (table FR_PHONEME_TABLE), pas durée fixe.
 *   - Silence ajouté seulement entre mots, pas après chaque syllabe.
 */
export function textToPhonemeTimelineV2(text: string): AvatarPhonemeFrame[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: AvatarPhonemeFrame[] = []
  for (const w of words) {
    const phones = phonemizeWord(w)
    if (phones.length === 0) continue
    for (const ph of phones) {
      const viseme = IPA_TO_AVATAR[ph] ?? 'silence'
      const baseDur = FR_DURATIONS.get(ph) ?? 70
      const isVowel = ['aa', 'ee', 'ii', 'oo', 'uu'].includes(viseme)
      out.push({ viseme, duration: baseDur, stress: isVowel ? 0.8 : 0.5 })
    }
    out.push({ viseme: 'silence', duration: 60, stress: 0 })
  }
  return out
}

// --- Liaisons FR ------------------------------------------------------------
//
// La liaison réalise une consonne finale normalement muette quand le mot
// suivant commence par une voyelle. C'est un trait essentiel pour un lipsync
// crédible : sans liaison, "les enfants" produit un visème de pause là où en
// vrai on prononce un /z/ ligaturé.
//
// Règles obligatoires couvertes ici :
//   - articles définis pluriel : les/des/aux/mes/tes/ses/ces/nos/vos/leurs + voyelle → +/z/
//   - adjectifs prénominaux : grand/petit/bon/mauvais + voyelle → +/t/ (grand→/d/→/t/ devant V)
//   - pronoms : on/en/ils/elles/nous/vous + voyelle → +/n/ ou +/z/
//   - prépositions monosyllabiques : sans/dans/en/sous + voyelle
//   - "est" + voyelle → +/t/
//
// Liaisons facultatives (style soutenu) : non couvertes — gardent le mot tel quel.

const VOWEL_STARTS = /^[aeiouyâàäéèêëîïôùûüœæh]/i

const LIAISON_RULES: Array<{ word: RegExp; liaisonIpa: string }> = [
  // Articles + déterminants pluriel → /z/
  { word: /^(les|des|aux|mes|tes|ses|ces|nos|vos|leurs|quels|quelles|certains|certaines|plusieurs)$/i, liaisonIpa: 'z' },
  // Pronoms personnels → /z/ (nous/vous/ils/elles/ces/les)
  { word: /^(nous|vous|ils|elles)$/i, liaisonIpa: 'z' },
  // on/en → /n/
  { word: /^(on|en|un|aucun|bien|rien|non|son|ton|mon)$/i, liaisonIpa: 'n' },
  // Adjectifs prénominaux courts terminés en 'd/t/s' silencieux → /t/
  { word: /^(grand|petit|bon|haut|sot|tout|tant)$/i, liaisonIpa: 't' },
  // est → /t/
  { word: /^(est|sont|font|ont|vont|peuvent|veulent|doivent)$/i, liaisonIpa: 't' },
  // Prépositions sans/dans/sous → /z/ ; chez → /z/
  { word: /^(sans|dans|sous|chez)$/i, liaisonIpa: 'z' },
  // deux/trois → /z/ devant voyelle
  { word: /^(deux|trois|six|dix|vingt|cent)$/i, liaisonIpa: 'z' },
]

/**
 * Pour chaque paire (mot, mot suivant), détermine si une liaison s'applique.
 * Retourne le phonème à insérer (ou '' si pas de liaison).
 */
export function detectLiaison(currentWord: string, nextWord: string): string {
  if (!currentWord || !nextWord) return ''
  if (!VOWEL_STARTS.test(nextWord)) return ''
  // h aspiré : on ne devrait PAS liaison ("les héros"). Liste minimale.
  const HASPIRE = /^(héros|haine|huit|honteux|honte|haut|hibou|hangar|harpe)/i
  if (HASPIRE.test(nextWord)) return ''
  for (const rule of LIAISON_RULES) {
    if (rule.word.test(currentWord)) return rule.liaisonIpa
  }
  return ''
}

/**
 * Phonémise une phrase complète FR en tenant compte des liaisons.
 * À l'opposé de phonemizeSentence qui ne traite pas les liaisons.
 */
export function phonemizeSentenceWithLiaisons(text: string): string[] {
  if (!text) return []
  const words = text.split(/[\s,.;:!?()«»"'-]+/).filter(Boolean)
  const out: string[] = []
  for (let i = 0; i < words.length; i += 1) {
    const w = words[i]
    const phones = phonemizeWord(w)
    out.push(...phones)
    const next = words[i + 1]
    if (next) {
      const liaison = detectLiaison(w, next)
      if (liaison) out.push(liaison)
    }
  }
  return out
}

/**
 * High-quality text-to-visemes : phonemize FR + map each IPA to viseme + take
 * the table duration when known, fallback to 80ms otherwise. Returns keyframes
 * suitable for the talking-head idle animation.
 */
export function textToVisemesRuleBased(text: string, speedFactor = 1): VisemeKeyframe[] {
  const phones = phonemizeSentence(text)
  let cursor = 0
  const out: VisemeKeyframe[] = []
  for (const ph of phones) {
    const dur = Math.max(30, (FR_DURATIONS.get(ph) ?? 80) / Math.max(0.5, speedFactor))
    const viseme = phonemeToViseme(ph)
    const last = out[out.length - 1]
    if (last && last.viseme === viseme) {
      last.endMs += dur
    } else {
      out.push({ startMs: cursor, endMs: cursor + dur, viseme })
    }
    cursor += dur
  }
  return out
}
