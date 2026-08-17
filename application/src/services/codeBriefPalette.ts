// ---------------------------------------------------------------------------
// codeBriefPalette — la palette nommee DANS le brief fait autorite.
//
// Run 1161. La cliente ecrit, textuellement:
//
//   « on n'est PAS un truc minimaliste blanc scandinave […] On veut plutot des
//     couleurs chaudes, terracotta, marron torrefie, un peu de vert olive
//     peut-etre, ca doit sentir l artisanal et le chaleureux »
//
// La design-spec lui a repondu, en `required: true`:
//
//   background  oklch(0.13 0.012 252)   (un noir bleute)
//   accent      #7c3aed                 (le violet d un editeur de code)
//
// Le fond etait code en dur pour TOUT projet web, quel que soit l archetype et
// quel que soit le brief; le violet venait de l archetype `ide_code_editor`,
// lui-meme obtenu parce que le mot « idee » contient « ide ». Le modele a
// produit, correctement, un site terracotta chaleureux — et la porte a signale
// « Ecart design-spec (palette) » a chaque passe.
//
// Une porte qui juge selon un gabarit interne au lieu de juger selon ce qui a
// ete demande: exactement le run 1021 (« le juge reclamait le gadget que la
// cliente avait refuse »), et le motif de toute la serie.
//
// Ici on lit les couleurs du brief. Et on n EXIGE jamais un fond que le brief
// contredit — un ecart mesure contre une valeur que personne n a demandee n est
// pas un ecart, c est un faux.
// ---------------------------------------------------------------------------

import { matchesHint, normalizeHintText } from './codePromptHints.ts'

export type BriefColor = {
  token: string
  hex: string
  /**
   * `hex` = le brief donne la valeur exacte, elle fait loi. `word` = le brief
   * nomme une FAMILLE (« terracotta »): on en propose une teinte, on ne peut pas
   * l exiger — mesurer un ecart contre un hex que personne n a ecrit serait
   * refaire la faute qu on corrige.
   */
  source: 'hex' | 'word'
}

export type BriefPalette = {
  /** Couleurs REELLEMENT demandees, dans l ordre du vocabulaire. */
  colors: BriefColor[]
  /** Le brief demande une ambiance claire/chaude — un fond quasi noir la trahit. */
  wantsLight: boolean
  /** Le brief demande explicitement du sombre. */
  wantsDark: boolean
  /** Les mots qui l ont etabli: une porte doit pouvoir se justifier. */
  evidence: string[]
}

/**
 * Vocabulaire chromatique FR/EN. Les locutions passent avant les mots simples
 * (« vert olive » avant « vert ») pour que la couleur retenue soit la plus
 * precise. Deduplique par teinte a la sortie.
 *
 * Limite assumee: un nom de couleur peut vivre dans une phrase qui ne parle pas
 * d habillage — le brief de la Brulerie decrit des notes de degustation
 * (« chocolat noir, agrumes »). L ordre par PRECISION fait que les vraies
 * couleurs de marque (« marron torrefie », « vert olive ») sortent en tete, et
 * les consommateurs ne prennent que les premieres. On ne pretend pas distinguer
 * un gout d une teinte: on classe, on ne devine pas.
 */
const COLOR_VOCABULARY: Array<{ token: string; hex: string; warm: boolean }> = [
  { token: 'terre cuite', hex: '#b4552f', warm: true },
  { token: 'marron torrefie', hex: '#5b3a26', warm: true },
  { token: 'vert olive', hex: '#6b7a3a', warm: false },
  { token: 'bleu marine', hex: '#1e3a5f', warm: false },
  { token: 'terracotta', hex: '#b4552f', warm: true },
  { token: 'chocolat', hex: '#4a2c17', warm: true },
  { token: 'bordeaux', hex: '#6d2130', warm: true },
  { token: 'moutarde', hex: '#c9a227', warm: true },
  { token: 'rouille', hex: '#a8522c', warm: true },
  { token: 'corail', hex: '#e1725c', warm: true },
  { token: 'marron', hex: '#6b4423', warm: true },
  { token: 'brun', hex: '#6b4423', warm: true },
  { token: 'beige', hex: '#d9c7a7', warm: true },
  { token: 'creme', hex: '#f3ece1', warm: true },
  { token: 'sable', hex: '#dcc9a6', warm: true },
  { token: 'ivoire', hex: '#f5f0e6', warm: true },
  { token: 'taupe', hex: '#8b7d6b', warm: true },
  { token: 'ocre', hex: '#c8863c', warm: true },
  { token: 'ambre', hex: '#b06c1f', warm: true },
  { token: 'olive', hex: '#6b7a3a', warm: false },
  { token: 'kaki', hex: '#6b7a3a', warm: false },
  { token: 'turquoise', hex: '#2ca6a4', warm: false },
  { token: 'lavande', hex: '#8b7fc7', warm: false },
  { token: 'anthracite', hex: '#2f3437', warm: false },
  { token: 'orange', hex: '#d97706', warm: true },
  { token: 'jaune', hex: '#d4a017', warm: true },
  { token: 'dore', hex: '#c9a227', warm: true },
  { token: 'rouge', hex: '#b91c1c', warm: true },
  { token: 'rose', hex: '#db7093', warm: true },
  { token: 'violet', hex: '#7c3aed', warm: false },
  { token: 'vert', hex: '#4a7c59', warm: false },
  { token: 'bleu', hex: '#2f5d8c', warm: false },
  { token: 'gris', hex: '#6b7280', warm: false },
  { token: 'noir', hex: '#111827', warm: false },
  { token: 'blanc', hex: '#ffffff', warm: false },
]

/** Ambiance claire demandee en toutes lettres, hors nom de couleur. */
const LIGHT_HINTS = [
  'couleurs chaudes', 'couleur chaude', 'tons chauds', 'ton chaud', 'chaleureux',
  'lumineux', 'clair', 'claire', 'light mode', 'theme clair', 'fond clair',
  'solaire', 'ensoleille', 'pastel',
]

const DARK_HINTS = [
  'sombre', 'dark', 'dark mode', 'theme sombre', 'fond sombre', 'fond noir',
  'nocturne', 'nuit', 'obscur', 'ambiance sombre',
]

/** Fond clair chaud, quand le brief demande la chaleur sans nommer de fond. */
export const WARM_LIGHT_BACKGROUND = '#faf6f0'

function isWarm(hex: string): boolean {
  return COLOR_VOCABULARY.some((entry) => entry.hex === hex && entry.warm)
}

/** Codes hexadecimaux ecrits tels quels dans le brief — la demande la plus explicite. */
function explicitHexes(prompt: string): string[] {
  const found = new Set<string>()
  for (const match of String(prompt || '').matchAll(/#([0-9a-f]{6}|[0-9a-f]{3})\b/gi)) {
    const raw = match[1].toLowerCase()
    const full = raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw
    found.add(`#${full}`)
  }
  return [...found]
}

export function resolveBriefPalette(prompt: string): BriefPalette {
  const text = normalizeHintText(prompt)
  const evidence: string[] = []
  const byHex = new Map<string, BriefColor>()

  for (const hex of explicitHexes(prompt)) {
    byHex.set(hex, { token: hex, hex, source: 'hex' })
    evidence.push(`hex explicite: ${hex}`)
  }
  for (const entry of COLOR_VOCABULARY) {
    if (!matchesHint(text, entry.token)) continue
    if (!byHex.has(entry.hex)) byHex.set(entry.hex, { token: entry.token, hex: entry.hex, source: 'word' })
    evidence.push(`couleur nommee: ${entry.token}`)
  }

  const colors = [...byHex.values()]
  const wantsDark = LIGHT_OR_DARK(text, DARK_HINTS)
  const namedLight = LIGHT_OR_DARK(text, LIGHT_HINTS)
  const warmNamed = colors.some((color) => isWarm(color.hex))
  if (namedLight) evidence.push('ambiance claire demandee')
  if (wantsDark) evidence.push('ambiance sombre demandee')

  return {
    colors,
    wantsLight: !wantsDark && (namedLight || warmNamed),
    wantsDark,
    evidence,
  }
}

function LIGHT_OR_DARK(normalized: string, hints: string[]): boolean {
  return hints.some((hint) => matchesHint(normalized, hint))
}

/**
 * Le fond quasi noir par defaut est-il CONTREDIT par le brief ? Si oui, il ne
 * peut pas etre exige: on ne mesure pas un ecart contre une valeur que personne
 * n a demandee.
 */
export function briefContradictsDarkBackground(palette: BriefPalette): boolean {
  return palette.wantsLight
}
