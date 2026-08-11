// ---------------------------------------------------------------------------
// codeCompositionGate — juge ce que la mesure de style ne voit pas: les
// elements qui se CHEVAUCHENT, les sections VIDES, et les icones en EMOJI.
//
// Le juge de rendu precedent notait 100/100 une page ou « Get Started » et
// « Scroll to explore » se superposaient dans le hero, ou le hero occupait un
// grand vide, et ou les six « icones » de fonctionnalites etaient des emoji.
// Il comptait les tailles de police, les fonds et les ombres — jamais la
// COMPOSITION. Trois defauts qu un directeur artistique voit en une seconde et
// qu aucune metrique de style ne capture.
//
// Les mesures viennent du navigateur (rectangles reels apres mise en page); la
// regle de notation vit ici, donc elle se teste sans navigateur.
// ---------------------------------------------------------------------------

export type OverlapPair = {
  a: string
  b: string
  /** Surface d intersection en pixels. */
  area: number
}

export type SectionFill = {
  label: string
  height: number
  /** Part de la hauteur reellement occupee par du contenu, 0..1. */
  fill: number
}

export type CompositionMetrics = {
  overlaps: OverlapPair[]
  sections: SectionFill[]
  /** Emoji employes en position d icone (source livree). */
  emojiIcons: string[]
  viewportWidth: number
}

export type CompositionCheck = {
  id: string
  label: string
  passed: boolean
  evidence: string
}

export type CompositionReport = {
  ok: boolean
  checks: CompositionCheck[]
  failedChecks: string[]
  critique: string
}

/** Sous ce taux, une section haute est un vide a l ecran. Le cas reel mesure
 * 12 % sur 658 px: le seuil doit donc etre au-dessus pour l attraper. */
export const EMPTY_SECTION_FILL = 0.15
/** Une section courte peut legitimement respirer: on ne juge que le grand vide. */
export const EMPTY_SECTION_MIN_HEIGHT = 400

export function findEmptySections(sections: SectionFill[]): SectionFill[] {
  return sections.filter((s) => s.height >= EMPTY_SECTION_MIN_HEIGHT && s.fill < EMPTY_SECTION_FILL)
}

/**
 * Note la composition. Chaque regle correspond a un defaut CONSTATE sur une
 * page reelle que le juge de style avait pourtant notee 100/100.
 */
export function checkComposition(metrics: CompositionMetrics): CompositionReport {
  const emptySections = findEmptySections(metrics.sections)
  const checks: CompositionCheck[] = [
    {
      id: 'no_overlap',
      label: 'Aucun element ne se chevauche',
      passed: metrics.overlaps.length === 0,
      evidence: metrics.overlaps.length === 0
        ? 'aucun chevauchement'
        : metrics.overlaps.slice(0, 3).map((o) => `"${o.a}" x "${o.b}" (${Math.round(o.area)}px2)`).join(' | '),
    },
    {
      id: 'no_empty_section',
      label: 'Aucune grande section quasi vide',
      passed: emptySections.length === 0,
      evidence: emptySections.length === 0
        ? 'toutes les sections sont remplies'
        : emptySections.slice(0, 3).map((s) => `${s.label}: ${Math.round(s.height)}px remplie a ${Math.round(s.fill * 100)}%`).join(' | '),
    },
    {
      id: 'real_iconography',
      label: 'Les icones ne sont pas des emoji',
      passed: metrics.emojiIcons.length === 0,
      evidence: metrics.emojiIcons.length === 0
        ? 'aucune icone emoji'
        : `${metrics.emojiIcons.length} emoji en position d icone: ${metrics.emojiIcons.slice(0, 8).join(' ')}`,
    },
  ]
  const failed = checks.filter((c) => !c.passed)
  return {
    ok: failed.length === 0,
    checks,
    failedChecks: failed.map((c) => c.id),
    critique: buildCompositionCritique(failed),
  }
}

/** Consigne de correction ciblee, nommant le defaut constate a l ecran. */
export function buildCompositionCritique(failed: CompositionCheck[]): string {
  if (failed.length === 0) return ''
  const fixes: Record<string, string> = {
    no_overlap: "Deux elements se superposent a l ecran. Donne au conteneur un `display:flex` avec `gap`, ou retire le positionnement absolu qui sort l element du flux. Un texte pose sur un bouton est illisible.",
    no_empty_section: "Une grande section est quasi vide. Soit tu la remplis (visuel, accroche, indicateurs, CTA), soit tu reduis sa hauteur. Un `min-height:100vh` sur une section qui ne contient que deux lignes produit un vide blanc.",
    real_iconography: "Remplace les emoji par une VRAIE iconographie: SVG inline coherents (meme grille, meme epaisseur de trait, meme style) ou un set d icones unique. Un emoji est la signature d un prototype, jamais d un produit fini.",
  }
  return [
    '## COMPOSITION INSUFFISANTE — CONSTATS A L ECRAN',
    'La page a ete rendue et mesuree. Ces defauts ne sont pas des questions de gout:',
    ...failed.map((c) => `- ${c.label} — constate: ${c.evidence}. ${fixes[c.id] ?? ''}`.trim()),
  ].join('\n')
}

// ---------------------------------------------------------------------------
// Detection d emoji en position d icone (analyse de la source livree)
// ---------------------------------------------------------------------------

/**
 * Plages Unicode des pictogrammes. On ignore volontairement les symboles
 * typographiques courants (fleches, puces) qui ne pretendent pas etre des
 * icones de produit.
 */
const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}]/gu

/** Le texte a-t-il un emoji ET rien d autre de substantiel ? */
function isIconLikeText(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return false
  const withoutEmoji = trimmed.replace(EMOJI_RE, '').trim()
  // Un emoji seul (ou presque) dans un element = il TIENT LIEU d icone.
  return withoutEmoji.length <= 2 && EMOJI_RE.test(trimmed)
}

/**
 * Repere les emoji employes comme icones dans le markup livre: un element dont
 * le contenu se reduit a un pictogramme.
 */
export function detectEmojiIcons(files: Array<{ name: string; content: string }>): string[] {
  const found = new Set<string>()
  for (const file of files) {
    if (!/\.(html?|vue|svelte|[jt]sx)$/i.test(file.name)) continue
    for (const m of file.content.matchAll(/>([^<>{}]{1,12})</g)) {
      if (isIconLikeText(m[1])) {
        for (const e of m[1].match(EMOJI_RE) ?? []) found.add(e)
      }
    }
  }
  return [...found]
}
