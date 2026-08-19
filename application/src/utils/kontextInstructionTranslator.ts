/**
 * kontextInstructionTranslator — l'edition FLUX.1 Kontext n'obeit bien qu'a
 * des instructions EN ANGLAIS (guide BFL). Le module image envoyait l'instruction
 * en francais brut : les mots courants a fort recouvrement (lunettes de soleil ->
 * sunglasses) passaient, mais les expressions idiomatiques etaient ignorees ou
 * traduites litteralement — "noeud papillon" (litt. "butterfly knot") ne produit
 * AUCUN noeud papillon, alors que "bow tie" fonctionne (verifie en live, meme seed).
 *
 * Strategie, calquee sur videoPromptComposer (deterministe d'abord, LLM en
 * complement) pour rester rapide et fonctionner hors-ligne :
 *   1. lexique FR->EN deterministe pour les pieges d'edition les plus courants
 *      (verbes, accessoires, parties du visage, couleurs, articles) — instantane,
 *      zero charge GPU, couvre la grande majorite des demandes ;
 *   2. polish LLM UNIQUEMENT s'il reste du francais de contenu non traduit
 *      (queue longue : "une echarpe a carreaux verts"), avec timeout court et
 *      repli sur le resultat du lexique.
 *
 * Le but n'est pas une traduction litterale parfaite mais de garantir que les
 * NOMS et l'ACTION arrivent en anglais a Kontext, qui s'ancre sur eux.
 */

export interface TranslateEditOptions {
  /** Fonction d'appel LLM (ollamaGenerate-like). Optionnelle : si absente, lexique seul. */
  generate?: (model: string, prompt: string) => Promise<{ response?: string } | null | undefined>
  /** Modele Ollama a utiliser pour le polish (ex: mainModel de l'app). */
  model?: string
  signal?: AbortSignal
  /** Timeout du polish LLM (defaut 12s). */
  timeoutMs?: number
}

/**
 * Pieges multi-mots (traites en PREMIER, du plus long au plus court, pour qu'une
 * expression composee gagne sur ses fragments).
 */
const PHRASE_LEXICON: Array<[RegExp, string]> = [
  [/\b(?:fais[-\s]moi\s+une\s+|fais\s+une\s+)?r[eé]plication\s+(?:fid[eè]le\s+)?(?:de\s+l['\u2019]?image|de\s+la\s+photo|de\s+cette\s+image|de\s+la\s+r[eé]f[eé]rence|de\s+ce\s+visuel)\b/giu, 'faithfully replicate the reference image'],
  [/\b(?:fais[-\s]moi\s+une\s+|fais\s+une\s+)?r[eé]plication\s+de\b/giu, 'replicate '],
  [/\br[eé]plication\s+fid[eè]le\b/giu, 'faithful replication'],
  [/\breproduction\s+fid[eè]le\b/giu, 'faithful reproduction'],
  [/\breprodui[st]?\s+fid[eè]lement\b/giu, 'faithfully reproduce'],
  [/\br[eé]pliqu[ez]?\s+fid[eè]lement\b/giu, 'faithfully replicate'],
  [/\bavec\s+(?:plusieurs|mes|les|ces|des)\s+r[eé]f[eé]rences\b/giu, 'using the visual references'],
  [/\ben\s+gardant\s+(?:exactement\s+)?(?:le\s+m[eê]me\s+|la\s+m[eê]me\s+)?style\b/giu, 'preserving the exact visual style'],
  [/\ben\s+gardant\s+(?:exactement\s+)?(?:le\s+m[eê]me\s+|la\s+m[eê]me\s+)?sujet\b/giu, 'preserving the main subject identity'],
  [/\ben\s+gardant\s+(?:exactement\s+)?(?:la\s+m[eê]me\s+)?pose\b/giu, 'preserving the exact pose'],
  [/\bsans\s+(?:changer|modifier)\s+(?:sa|la|les|son)\s+(?:tenue|v[eê]tements|habits)\s+ni\s+(?:son|sa|ses|le|la|les)\s+(?:visage|t[eê]te)\b/giu, 'without changing the clothes or face'],
  [/\bsans\s+(?:changer|modifier)\s+(?:sa|la|les|son)\s+(?:tenue|v[eê]tements|habits)\b/giu, 'without changing the clothes'],
  [/\bsans\s+(?:changer|modifier)\s+(?:son|le|sa|de)\s+(?:visage|t[eê]te)\b/giu, 'without changing the face or head'],
  [/\bsans\s+(?:changer|modifier)\s+(?:les|la|sa|son)\s+(?:cheveux|coiffure)\b/giu, 'without changing the hair'],
  [/\bni\s+(?:son|sa|ses|le|la|les)\s+(?:visage|t[eê]te)\b/giu, 'or face'],
  [/\bni\s+(?:son|sa|ses|le|la|les)\s+(?:tenue|v[eê]tements|habits)\b/giu, 'or clothes'],
  [/\bsuppression\s+(?:compl[e\u00e8]te?|complete|totale?|total|enti[e\u00e8]re?|entire|full)?\s*(?:de\s+l['\u2019]?|de\s+la\s+|des\s+|du\s+|de\s+)/giu, 'remove the '],
  [/\b(?:ajout|insertion|int[e\u00e9]gration)\s+(?:d['\u2019]un\s+|d['\u2019]une\s+|de\s+l['\u2019]?|de\s+la\s+|des\s+|du\s+|de\s+)/giu, 'add a '],
  [/\bhomme\s+m[e\u00e9]tis\b/giu, 'mixed-race man'],
  [/\bsur\s+(?:ses|les|son)\s+[e\u00e9]paules?\b/giu, 'on the shoulders'],
  [/\b[e\u00e9]paules?\s+droites?\s+(?:assis|assise)\b/giu, 'sitting on the right shoulder'],
  [/\b[e\u00e9]paules?\s+gauches?\s+(?:assis|assise)\b/giu, 'sitting on the left shoulder'],
  [/\b[e\u00e9]paules?\s+droites?\b/giu, 'right shoulder'],
  [/\b[e\u00e9]paules?\s+gauches?\b/giu, 'left shoulder'],
  [/\b(?:assis|assise)\s+sur\b/giu, 'sitting on'],
  [/\b(?:le\s+)?chat\s+(?:bleu\s+)?happy(?:\s+de\s+fairy\s+tail)?\b/giu, 'Happy, the cat from Fairy Tail'],
  [/\bchat\s+de\s+fairy\s+tail\s+(?:nomm[e\u00e9]e?s?|nommer|appel[e\u00e9]e?s?|named|called)\s+happy\b/giu, 'Happy, the cat from Fairy Tail'],
  [/\bcouleur\s+(?:de\s+la|des|de|du)\s+cheveux\b/giu, 'hair color'],
  [/\bcouleur\s+(?:de\s+la|des|de|du)\s+yeux\b/giu, 'eye color'],
  [/\bcapes?\s+(?:de\s+couleur\s+)?noirs?e?s?\b/giu, 'black cape'],
  [/\bcapes?\s+(?:de\s+couleur\s+)?bleus?e?s?\b/giu, 'blue cape'],
  [/\bcapes?\s+(?:de\s+couleur\s+)?rouges?e?s?\b/giu, 'red cape'],
  [/\bcapes?\s+(?:de\s+couleur\s+)?blan[cs]he?s?\b/giu, 'white cape'],
  [/\bcapes?\s+[aà]\s+capuche\b/giu, 'hooded cape'],
  [/\bcapes?\s+avec\s+capuche\b/giu, 'hooded cape'],
  [/\bflammes?\s+bleus?e?s?\s+en\s+plus\s+(?:des?\s+rouges?|des?\s+flammes?\s+rouges?)\b/giu, 'blue flames in addition to the red flames'],
  [/\bflammes?\s+bleus?e?s?\s+en\s+plus\b/giu, 'additional blue flames'],
  [/\bflammes?\s+bleus?e?s?\b/giu, 'blue flames'],
  [/\bflammes?\s+rouges?\b/giu, 'red flames'],
  [/\bflammes?\s+violettes?\b/giu, 'purple flames'],
  [/\bflammes?\s+(?:d['’]or|dor[eé]es?)\b/giu, 'golden flames'],
  [/\ben\s+plus\s+(?:de|des|du|d['’])\b/giu, 'along with '],
  [/\ben\s+plus\b/giu, 'in addition'],
  [/\ben\s+suppl[eé]ment\b/giu, 'additionally'],
  [/\bnuits?\s+[eé]toil[eé]es?\b/giu, 'starry night sky with glowing stars'],
  [/\bciels?\s+[eé]toil[eé]s?\b/giu, 'starry sky with stars'],
  [/\bciels?\s+de\s+nuit\s+[eé]toil[eé]s?\b/giu, 'starry night sky'],
  [/\ben\s+pleine\s+nuit\b/giu, 'at night'],
  [/\bciels?\s+nocturnes?\b/giu, 'night sky'],
  [/\baurores?\s+bor[eé]ales?\b/giu, 'aurora borealis northern lights'],
  [/\bclairs?\s+de\s+lune\b/giu, 'moonlight'],
  [/\bpleines?\s+lunes?\b/giu, 'full moon'],
  [/\bsous\s+la\s+pluie\b/giu, 'in the rain'],
  [/\bsous\s+la\s+neige\b/giu, 'in the snow'],
  [/\bn(?:œ|oe)uds?\s+papillons?\b/giu, 'bow tie'],
  [/\blunettes?\s+de\s+soleil\b/giu, 'sunglasses'],
  [/\bqueue\s+de\s+cheval\b/giu, 'ponytail'],
  [/\bboucles?\s+d['’]?\s*oreilles?\b/giu, 'earrings'],
  [/\bt[aâ]ches?\s+de\s+rousseur\b/giu, 'freckles'],
  [/\barri[eè]re[-\s]?plans?\b/giu, 'background'],
  [/\bcoucher\s+de\s+soleil\b/giu, 'sunset'],
  [/\bchemise\s+[aà]\s+carreaux\b/giu, 'plaid shirt'],
  [/\bbonnet\s+de\s+no[eë]l\b/giu, 'santa hat'],
  [/\bbouton(?:s)?\s+d['’]?\s*acn[eé]\b/giu, 'acne'],
]

/** Verbes d'edition. */
const VERB_LEXICON: Array<[RegExp, string]> = [
  [/\b(?:r[eé]pliqu[erz]?|r[eé]plique)\b/giu, 'replicate'],
  [/\b(?:reprodui[st]?|reproduire)\b/giu, 'reproduce'],
  [/\b(?:recr[eé]e[rz]?|recr[eé]er)\b/giu, 'recreate'],
  [/\b(?:dupliqu[erz]?|duplique)\b/giu, 'duplicate'],
  [/\b(?:copi[erz]?|copie)\b/giu, 'copy'],
  [/\b(?:imit[erz]?|imite)\b/giu, 'imitate'],
  [/\b(?:ajoute[rz]?|rajoute[rz]?)\b/giu, 'add'],
  [/\b(?:enl[eè]ve[rz]?|enlever|retire[rz]?|retirer|supprime[rz]?|supprimer|efface[rz]?|effacer|vire[rz]?)\b/giu, 'remove'],
  [/\b(?:remplace[rz]?|remplacer)\b/giu, 'replace'],
  [/\b(?:transforme[rz]?|transformer)\b/giu, 'turn'],
  [/\b(?:colorise[rz]?|coloriser|colore[rz]?|colorer)\b/giu, 'recolor'],
  [/\b(?:mets|met|mettre)\b/giu, 'put'],
  [/\b(?:place[rz]?|placer|pose[rz]?|poser)\b/giu, 'place'],
  [/\b(?:change[rz]?|changer)\b/giu, 'change'],
]

/**
 * Adjectifs de coiffure (longueur, texture, couleur) — sources SANS `\b` pour
 * l'alternance ; ordonnes du plus specifique au plus general (mi-long avant long).
 * "cheveux courts" etait traduit "hair courts" (court ignore par Kontext -> cheveux
 * longs par defaut) : c'est le bug que ce bloc corrige, avec l'ordre EN correct.
 */
const HAIR_ADJ: Array<[string, string]> = [
  ['mi[-\\s]?long(?:ue)?s?', 'medium-length'],
  ['long(?:ue)?s?', 'long'],
  ['court(?:e)?s?', 'short'],
  ['boucl[eé]e?s?', 'curly'],
  ['fris[eé]e?s?', 'curly'],
  ['ondul[eé]e?s?', 'wavy'],
  ['raides?', 'straight'],
  ['lisses?', 'straight'],
  ['cr[eê]pus?', 'afro-textured'],
  ['blond(?:e)?s?', 'blonde'],
  ['brun(?:e)?s?', 'brown'],
  ['ch[aâ]tains?', 'brown'],
  ['noir(?:e)?s?', 'black'],
  ['rousse?s?', 'red'],
  ['roux', 'red'],
  ['grise?s?', 'gray'],
  ['blan[cs]he?s?', 'white'],
  ['rouges?', 'red'],
  ['bleus?', 'blue'],
  ['verts?', 'green'],
  ['roses?', 'pink'],
  ['violet(?:te)?s?', 'purple'],
  ['dor[eé]e?s?', 'golden'],
]
const HAIR_ADJ_ALT = HAIR_ADJ.map(([p]) => p).join('|')
const HAIR_PHRASE_RE = new RegExp(`cheveux((?:\\s+(?:${HAIR_ADJ_ALT}))+)`, 'giu')

/** "cheveux longs blonds" -> "long blonde hair" (ordre EN, adjectifs traduits). */
function transformHair(text: string): string {
  return text.replace(HAIR_PHRASE_RE, (_m, group: string) => {
    const tokens = group.trim().split(/\s+/).filter(Boolean)
    const en = tokens.map((tok) => {
      for (const [p, val] of HAIR_ADJ) {
        if (new RegExp(`^(?:${p})$`, 'iu').test(tok)) return val
      }
      return tok
    })
    return `${en.join(' ')} hair`
  })
}

/** Noms simples (accessoires, vetements, visage, decor). */
const NOUN_LEXICON: Array<[RegExp, string]> = [
  [/\bpersonnages?\b/giu, 'character'],
  [/\bchats?\b/giu, 'cat'],
  [/\bhommes?\b/giu, 'man'],
  [/\bm[e\u00e9]tis(?:se)?s?\b/giu, 'mixed-race'],
  [/\b[e\u00e9]paules?\b/giu, 'shoulder'],
  [/\b(?:assis|assise)\b/giu, 'sitting'],
  [/\b(?:nomm[e\u00e9]e?s?|nommer|appel[e\u00e9]e?s?)\b/giu, 'named'],
  [/\bcapes?\b/giu, 'cape'],
  [/\bp[eè]lerines?\b/giu, 'cloak'],
  [/\bflammes?\b/giu, 'flames'],
  [/\bfeux?\b/giu, 'fire'],
  [/\bauras?\b/giu, 'aura'],
  [/\b[eé]clairs?\b/giu, 'lightning'],
  [/\bfoudres?\b/giu, 'lightning'],
  [/\b[eé]toiles?\b/giu, 'stars'],
  [/\bnuits?\b/giu, 'night'],
  [/\blunes?\b/giu, 'moon'],
  [/\bbanderoles?\b/giu, 'banner'],
  [/\bbanni[eè]res?\b/giu, 'banner'],
  [/\bvillages?\b/giu, 'village'],
  [/\bvilles?\b/giu, 'town'],
  [/\bb[aâ]timents?\b/giu, 'buildings'],
  [/\brues?\b/giu, 'streets'],
  [/\ball[eé]es?\b/giu, 'alleys'],
  [/\bfoules?\b/giu, 'crowd'],
  [/\bpassants?\b/giu, 'passersby'],
  [/\btenues?\b/giu, 'outfit'],
  [/\bv[eê]tements?\b/giu, 'clothes'],
  [/\bhabits?\b/giu, 'clothes'],
  [/\blunettes?\b/giu, 'glasses'],
  [/\bchapeaux?\b/giu, 'hat'],
  [/\bcasquettes?\b/giu, 'cap'],
  [/\bbonnets?\b/giu, 'beanie'],
  [/\b[eé]charpes?\b/giu, 'scarf'],
  [/\bcravates?\b/giu, 'necktie'],
  [/\bcolliers?\b/giu, 'necklace'],
  [/\bbarbe?\b/giu, 'beard'],
  [/\bmoustaches?\b/giu, 'moustache'],
  [/\bcheveux\b/giu, 'hair'],
  [/\bvisages?\b/giu, 'face'],
  [/\bt[eê]tes?\b/giu, 'head'],
  [/\byeux\b/giu, 'eyes'],
  [/\bbouche\b/giu, 'mouth'],
  [/\bsourires?\b/giu, 'smile'],
  [/\bcouronnes?\b/giu, 'crown'],
  [/\bfonds?\b/giu, 'background'],
  [/\bd[eé]cors?\b/giu, 'background'],
  [/\bciels?\b/giu, 'sky'],
  [/\bplages?\b/giu, 'beach'],
  [/\bfor[eê]ts?\b/giu, 'forest'],
  [/\bmontagnes?\b/giu, 'mountains'],
  [/\brobes?\b/giu, 'dress'],
  [/\bvestes?\b/giu, 'jacket'],
  [/\bmanteaux?\b/giu, 'coat'],
  [/\bchemises?\b/giu, 'shirt'],
  [/\bpulls?(?:[-\s]?overs?)?\b/giu, 'sweater'],
  [/\bt[-\s]?shirts?\b/giu, 't-shirt'],
  [/\bpantalons?\b/giu, 'pants'],
  [/\bjupes?\b/giu, 'skirt'],
  // NB: pas de regle "short" -> collision avec l'adjectif coiffure "short hair".
  [/\bgants?\b/giu, 'gloves'],
  [/\bcostumes?\b/giu, 'suit'],
  [/\bfleurs?\b/giu, 'flowers'],
  [/\bcouleurs?\b/giu, 'color'],
]

/** Couleurs (frequentes dans les editions de teinte). */
const COLOR_LEXICON: Array<[RegExp, string]> = [
  [/\brouges?\b/giu, 'red'],
  [/\bbleus?\b/giu, 'blue'],
  [/\bverts?\b/giu, 'green'],
  [/\bjaunes?\b/giu, 'yellow'],
  [/\bnoirs?e?\b/giu, 'black'],
  [/\bblan[cs]he?s?\b/giu, 'white'],
  [/\broses?\b/giu, 'pink'],
  [/\bviolets?te?s?\b/giu, 'purple'],
  [/\bmarrons?\b/giu, 'brown'],
  [/\bgrise?s?\b/giu, 'gray'],
  [/\bblonds?e?\b/giu, 'blonde'],
  [/\bbruns?e?\b/giu, 'brown'],
  [/\bdor[eé]e?s?\b/giu, 'golden'],
  [/\bargent[eé]e?s?\b/giu, 'silver'],
]

/** Articles / prepositions (traites en DERNIER, apres les noms composes). */
const GRAMMAR_LEXICON: Array<[RegExp, string]> = [
  [/\bavec\b/giu, 'with'],
  [/\bde\b/giu, 'from'],
  [/\bl['\u2019]\s*/giu, 'the '],
  [/\bl\s+(?=(?:man|mixed-race|shoulder|right|left|cat|character)\b)/giu, 'the '],
  [/\bcompl[e\u00e8]tement\b/giu, 'completely'],
  [/\bcompletement\b/giu, 'completely'],
  [/\bpar\b/giu, 'with'],
  [/\bet\b/giu, 'and'],
  [/\bou\b/giu, 'or'],
  [/\bsans\b/giu, 'without'],
  [/\bsur\b/giu, 'on'],
  [/\bdans\b/giu, 'in'],
  [/\bune?\b/giu, 'a'],
  [/\bles\b/giu, 'the'],
  [/\bla\b/giu, 'the'],
  [/\ble\b/giu, 'the'],
  [/\bdes\b/giu, ''],
  [/\bdu\b/giu, ''],
  [/\ben\b/giu, 'into'],
]

// transformHair tourne ENTRE les verbes et les noms (reorder "cheveux <adj>"
// avant que "cheveux" seul ne devienne "hair").
const LEXICONS_BEFORE_HAIR = [PHRASE_LEXICON, VERB_LEXICON]
const LEXICONS_AFTER_HAIR = [NOUN_LEXICON, COLOR_LEXICON, GRAMMAR_LEXICON]

/** Marqueurs de francais "de contenu" (hors articles que le lexique gere deja). */
const FRENCH_CONTENT_MARKERS = /[\u00e0-\u00ff]|\b(?:ajout|suppression|ajoute|enleve|retire|supprime|remplace|mets|mettre|change|transforme|avec|sans|cheveux|visage|t[eê]te|corps|homme|m[e\u00e9]tis|chat|personnage|nomm[e\u00e9]|assis|[e\u00e9]paule|fond|decor|arriere|cape|flamme|[eé]toile|nuit|lune|banderole|banni[eè]re|tenue|v[eê]tement|habits|village|ville)\b/i

/** Vrai si le texte d'origine contient du francais (sinon : ne pas toucher). */
export function looksFrench(text: string): boolean {
  return FRENCH_CONTENT_MARKERS.test(text)
}

/**
 * Recompile un motif `\b…\b` avec des frontieres de mot UNICODE.
 * `\b` est ASCII : il ne reconnait pas "é/à/ô…" comme lettres, donc un mot a
 * initiale accentuee ("ecouter" ok mais "écharpe", "étoile") echappe au lexique.
 * On remplace les `\b` de bord par des lookarounds `\p{L}` (lettre Unicode).
 */
function unicodeWordPattern(re: RegExp): RegExp {
  let src = re.source
  if (src.startsWith('\\b')) src = '(?<![\\p{L}\\p{N}_])' + src.slice(2)
  if (src.endsWith('\\b')) src = src.slice(0, -2) + '(?![\\p{L}\\p{N}_])'
  const flags = re.flags.includes('u') ? re.flags : `${re.flags}u`
  return new RegExp(src, flags)
}

/** Applique le lexique deterministe FR->EN. */
export function applyEditLexicon(text: string): string {
  let out = text
  for (const lexicon of LEXICONS_BEFORE_HAIR) {
    for (const [re, repl] of lexicon) {
      out = out.replace(unicodeWordPattern(re), repl)
    }
  }
  out = transformHair(out)
  for (const lexicon of LEXICONS_AFTER_HAIR) {
    for (const [re, repl] of lexicon) {
      out = out.replace(unicodeWordPattern(re), repl)
    }
  }
  return out.replace(/\s{2,}/g, ' ').replace(/\s+([,.;!?])/g, '$1').trim()
}

/** Vrai s'il reste du francais de contenu apres passage du lexique. */
function hasResidualFrench(text: string): boolean {
  // Apres lexique : on ignore les accents resolus, on cherche des marqueurs FR restants.
  return /[\u00e0-\u00ff]|\b(?:le|la|les|une?|des|du|avec|sans|dans|sur|pour|sous|entre|cheveux|visage|t[eê]te|corps|homme|m[e\u00e9]tis|chat|personnage|nomm[e\u00e9]|assis|[e\u00e9]paule|fond|cape|flamme|[eé]toile|nuit|tenue|v[eê]tement|village)\b/i.test(text)
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('translate timeout')), ms)
    p.then((v) => { clearTimeout(t); resolve(v) }, (e) => { clearTimeout(t); reject(e) })
  })
}

const LLM_TRANSLATE_PROMPT = (raw: string, hint: string) => `/no_think
You convert a user's IMAGE EDIT request into ONE short English instruction for an instruction-based image editor (FLUX Kontext).

Rules:
- Output ONLY the instruction. No quotes, no explanation, no preamble.
- Imperative and direct, maximum 30 words.
- Keep the SAME action (add / remove / replace / change / recolor) and the SAME target. Do NOT invent extra changes, styles or quality words.
- When adding wearable items (e.g. cape, cloak, jacket, hat, scarf), specify it is worn over the body without recoloring the existing clothes and without altering the head/face/hair.
- When adding magic energy or flames (e.g. blue flames), specify they appear around the character alongside existing elements without replacing them.
- When changing the background/sky (e.g. starry night, sunset, rain), specify to change only the background and keep the foreground subject identical with NO unrequested crowd or extra bystanders.
- Resolve French idioms to their REAL English meaning, never literally:
  "noeud papillon" = "bow tie" (NOT butterfly), "queue de cheval" = "ponytail",
  "lunettes de soleil" = "sunglasses", "tache de rousseur" = "freckle",
  "cape noire" = "black cape", "nuit étoilée" = "starry night sky",
  "flammes bleues en plus" = "blue flames in addition to the existing flames".
- If the request only changes color/lighting, say so without adding objects.

French request: ${raw}
Rough English draft (may be partial): ${hint}
English instruction:`

/**
 * Traduit une instruction d'edition FR -> EN. Deterministe d'abord, LLM ensuite
 * seulement si necessaire. Ne leve jamais : repli garanti sur le meilleur effort.
 */
export async function translateEditInstructionToEnglish(
  rawPrompt: string,
  options: TranslateEditOptions = {},
): Promise<string> {
  const raw = (rawPrompt || '').replace(/\s+/g, ' ').trim()
  if (!raw) return raw
  // Prompt deja anglais (ou neutre) : ne pas risquer de le corrompre.
  if (!looksFrench(raw)) return raw

  const lex = applyEditLexicon(raw)

  // Cas courant : le lexique a tout traduit -> pas d'appel LLM (zero charge GPU).
  if (!hasResidualFrench(lex)) return lex

  // Queue longue : francais residuel -> polish LLM si dispo.
  if (options.generate && options.model) {
    try {
      if (options.signal?.aborted) return lex
      const res = await withTimeout(
        Promise.resolve(options.generate(options.model, LLM_TRANSLATE_PROMPT(raw, lex))),
        options.timeoutMs ?? 12_000,
      )
      const text = (res?.response || '')
        .replace(/<think>[\s\S]*?<\/think>/g, '')
        .replace(/<think>[\s\S]*$/g, '')
        .replace(/^["'`\s]+|["'`\s]+$/g, '')
        .trim()
      // Garde-fou : on accepte le LLM seulement s'il rend de l'anglais plausible.
      if (text.length >= 3 && !looksFrench(text)) return text
    } catch {
      /* timeout / erreur LLM : on garde le resultat du lexique */
    }
  }

  return lex
}
