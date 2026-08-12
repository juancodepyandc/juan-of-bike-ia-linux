// Contraintes de style EXPLICITES du brief.
//
// Mesure reelle (run 1021, brulerie artisanale lyonnaise): le juge visuel a
// refuse la livraison a 65/100 en exigeant « Transformations 3D (rotateY/X,
// perspective) » et « Animation pilotee par scroll ». Or la cliente ecrit,
// textuellement:
//
//   « Des animations discretes c est cool [...] mais je veux pas que ca fasse
//     gadget, faut que ca reste elegant. »
//
// Le juge reclamait donc exactement le gadget qu elle avait refuse. C est le
// meme motif que tous les defauts corriges jusqu ici: une porte qui juge selon
// un GABARIT INTERNE au lieu de juger selon ce qui a ete demande.
//
// Ce module lit la demande. Il ne rend PAS la porte plus permissive: il
// deplace la severite sur les criteres qui ont du sens quand la sobriete est
// demandee — finition typographique, coherence, densite editoriale,
// micro-interactions — et retire ceux qui contrediraient le brief.

export type StyleConstraints = {
  /** Le brief demande explicitement de la retenue. */
  restraint: boolean
  /** Les phrases exactes qui l ont etabli — une porte doit pouvoir se justifier. */
  evidence: string[]
}

// Formulations EXPLICITES de retenue. On exige une intention nette: « elegant »
// seul ne suffit pas — presque tous les briefs le disent, ce serait une porte
// de sortie universelle.
const RESTRAINT_PATTERNS: Array<{ id: string; re: RegExp }> = [
  { id: 'pas_gadget', re: /\b(?:pas|sans|aucun|rien\s+de)\s+(?:que\s+ca\s+fasse\s+)?(?:gadget|gadgets|tape[- ]a[-]l\W?oeil|clinquant|too\s?much|kitsch)\b/i },
  { id: 'pas_gadget_verbe', re: /\bje\s+veux\s+pas\s+que\s+(?:ca|cela)\s+fasse\s+gadget\b/i },
  { id: 'discret', re: /\b(?:discret|discrete|discretes|discrets|subtil|subtile|subtiles|sobre|sobres|sobriete)\b/i },
  { id: 'epure', re: /\b(?:epure|epuree|depouille|minimaliste|minimalist)\b/i },
  { id: 'sans_animation', re: /\b(?:pas|sans|aucune)\s+(?:d\W?)?(?:animation|animations|effet|effets)\s*(?:superflu\w*|inutile\w*|partout)?\b/i },
  { id: 'pas_3d', re: /\b(?:pas|sans|aucun)\s+(?:de\s+)?(?:3d|effet\s+3d|rotation|parallaxe|parallax)\b/i },
  { id: 'reste_simple', re: /\b(?:reste|rester|garde|garder)\s+(?:ca\s+)?(?:simple|sobre|classique|elegant)\b/i },
]

// Les criteres qui, sous contrainte de retenue, DEMANDERAIENT le gadget refuse.
export const GADGET_CHECK_IDS = [
  'has_3d_transforms',
  'has_scroll_driven',
  'has_layered_gradients',
  'has_depth',
] as const

// Ce sur quoi la porte devient PLUS exigeante quand la sobriete est demandee:
// sans effets pour impressionner, tout se joue sur la finition et le contenu.
export const RESTRAINT_REINFORCED_IDS = [
  'premium_fonts',
  'has_radius',
  'has_hover',
  'has_css_vars',
  'has_clamp',
  'min_sections',
  'rich_styling',
  'has_images',
  'no_flat_card_cluster',
] as const

/** Poids supplementaire applique aux criteres renforces. */
export const RESTRAINT_WEIGHT_BONUS = 6

export function resolveStyleConstraints(prompt: string): StyleConstraints {
  const text = String(prompt || '')
  if (!text.trim()) return { restraint: false, evidence: [] }

  const evidence: string[] = []
  for (const { id, re } of RESTRAINT_PATTERNS) {
    const match = re.exec(text)
    if (!match) continue
    const start = Math.max(0, match.index - 30)
    const excerpt = text.slice(start, match.index + match[0].length + 30).replace(/\s+/g, ' ').trim()
    evidence.push(`${id}: « …${excerpt}… »`)
  }

  return { restraint: evidence.length > 0, evidence }
}

/**
 * Explique la barre appliquee — une porte qui change de regle doit le DIRE,
 * sinon on retombe sur le defaut d origine: un verdict qu on ne peut pas
 * contester parce qu on ne sait pas sur quoi il porte.
 */
export function describeStyleConstraints(constraints: StyleConstraints): string {
  if (!constraints.restraint) return ''
  return [
    'Le brief demande explicitement de la RETENUE. Les criteres spectaculaires',
    '(3D, parallaxe, halos flous, degrades empiles) sont donc retires de la',
    'notation — les exiger contredirait la demande. En echange, la finition et',
    'la densite editoriale sont notees plus severement: sans effets pour',
    'impressionner, tout se joue sur la typographie, la coherence chromatique,',
    'les micro-interactions et le contenu.',
    '',
    ...constraints.evidence.map((line) => `- ${line}`),
  ].join('\n')
}
