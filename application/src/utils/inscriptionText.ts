/**
 * Texte à écrire DANS l'image (inscription, gravure, prénom, slogan…).
 *
 * Un mot placé après « inscription », « écrit », « gravé », « le prénom »…
 * est du texte à dessiner, jamais un sujet : « un vase avec l'inscription
 * Rayen » ne demande pas de personne nommée Rayen. Ce module est partagé par
 * le module Image (natif et web/tunnel) et le CLI `image_cli.mjs`, pour que la
 * recherche de références, le prompt et le prompt négatif lisent la même chose.
 */

const QUOTED_RE = /["“«‹]\s*([^"”»›\n]{1,60}?)\s*["”»›]/gu

// Mots-clés qui annoncent un texte à écrire. L'ordre compte : les formes
// longues d'abord pour que « inscriptions » ne soit pas lu « inscription » + « s ».
const CUE = String.raw`(?:inscriptions?|inscrite?s?|[eé]crit(?:e|es|s|ure)?|grav(?:[eé]e?s?|ure)|marqu[eé]e?s?|texte|mots?|noms?|pr[eé]noms?|lettres?|lettrage|message|slogan|devise|initiales?|signature|[eé]tiquette|label)`
// « l'inscription », « le prénom », « avec écrit », « où il est écrit », « portant le nom de »…
const CUE_RE = new RegExp(
  String.raw`(?:^|[\s,;(['’])${CUE}(?=\s*(?::\s*|\s+)(?:au\s+(?:nom|pr[eé]nom)\s+(?:de\s+|d['’]\s*)|(?:de|du|d['’])\s+|(?:le|la|les|l['’])\s*(?:(?:nom|pr[eé]nom|mot|texte)\s+)?)?(?:(?:nom|pr[eé]nom|mot|texte)\s+(?:de\s+|d['’]\s*)?)?([^\s,;:!?()]+(?:\s+[^\s,;:!?()]+){0,3}))`,
  'giu',
)

// Un texte s'arrête au premier mot qui reprend la description de l'objet.
const STOP_WORDS = new Set([
  'sur', 'dessus', 'dessous', 'dedans', 'devant', 'derriere', 'derrière', 'autour', 'au', 'aux', 'a', 'à',
  'en', 'avec', 'et', 'ou', 'dans', 'sous', 'pour', 'qui', 'que', 'de', 'des', 'du', 'd', 'le', 'la', 'les',
  'un', 'une', 'grave', 'gravé', 'gravee', 'gravée', 'graves', 'gravés', 'ecrit', 'écrit', 'ecrite', 'écrite',
  'peint', 'peinte', 'dore', 'doré', 'doree', 'dorée', 'dorees', 'dorées', 'blanc', 'blanche', 'noir', 'noire',
  'rouge', 'rose', 'bleu', 'bleue', 'vert', 'verte', 'or', 'argent', 'argente', 'argenté', 'en', 'style',
  'lettres', 'cursive', 'calligraphie', 'calligraphique', 'majuscules', 'minuscules', 'police', 'gros', 'grosses',
  'petites', 'petits', 'elegantes', 'élégantes', 'elegant', 'élégant', 'manuscrite', 'manuscrit', 'relief',
  'on', 'with', 'and', 'in', 'the', 'of', 'engraved', 'written', 'painted', 'golden', 'gold',
  'inscription', 'inscriptions', 'texte', 'nom', 'prenom', 'prénom', 'mot',
])

// Mots qui suivent un indice mais ne sont jamais le texte demandé.
const NOT_TEXT = /^(?:lisible|lisibles|clair|claire|net|nette|propre|aucun|aucune|pas|sans|personnalise|personnalisé|personnalisee|personnalisée|dessus|dessous|elegant|élégant|elegante|élégante|dore|doré|doree|dorée|grave|gravé|gravee|gravée|ecrit|écrit|ecrite|écrite|en|de|du|des|un|une|le|la|les|sur)$/iu

const NEGATED_TEXT_RE = /\b(?:sans|aucun(?:e)?|pas\s+de|no|without)\s+(?:texte|inscriptions?|[eé]criture|lettres?|text|lettering|writing)\b/iu

function cleanCandidate(raw: string): string {
  const words = raw.trim().split(/\s+/u)
  const kept: string[] = []
  for (const w of words) {
    const bare = w.replace(/^['’"“«]+|['’"”».]+$/gu, '')
    if (!bare) break
    if (STOP_WORDS.has(bare.toLowerCase())) break
    kept.push(bare)
  }
  return kept.join(' ').trim()
}

/** Textes à écrire dans l'image, dans l'ordre de la demande, sans doublon. */
export function extractInscriptionTexts(raw: string): string[] {
  const text = (raw || '').trim()
  if (!text || NEGATED_TEXT_RE.test(text)) return []
  const out: string[] = []
  const seen = new Set<string>()
  const push = (value: string) => {
    const v = value.replace(/\s+/g, ' ').trim()
    if (!v || v.length > 60 || NOT_TEXT.test(v)) return
    const key = v.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    out.push(v)
  }
  for (const m of text.matchAll(QUOTED_RE)) push(m[1] ?? '')
  // un texte entre guillemets est déjà exact : on n'ajoute pas sa version tronquée
  const quotedSpans = [...text.matchAll(QUOTED_RE)].map((m) => [m.index ?? 0, (m.index ?? 0) + m[0].length])
  for (const m of text.matchAll(CUE_RE)) {
    const at = (m.index ?? 0) + m[0].length
    if (quotedSpans.some(([a, b]) => at >= a && at < b)) continue
    if (/^["“«‹]/u.test(m[1] ?? '')) continue
    push(cleanCandidate(m[1] ?? ''))
  }
  return out
}

/**
 * Retire de la demande les textes à écrire (et leurs indices) pour que la
 * recherche de sujet ne prenne pas un prénom gravé pour un personnage.
 */
export function stripInscriptionSpans(raw: string): string {
  const texts = extractInscriptionTexts(raw)
  let out = raw || ''
  out = out.replace(QUOTED_RE, ' ')
  for (const t of texts) {
    const escaped = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    out = out.replace(new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}(?=$|[^\\p{L}\\p{N}])`, 'giu'), '$1 ')
  }
  return out.replace(/\s{2,}/g, ' ').trim()
}
