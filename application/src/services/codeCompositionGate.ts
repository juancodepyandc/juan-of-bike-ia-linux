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
//
// CORRECTION (run 1161) — le juge de VIDE, lui, mesurait faux. Il sommait
// l aire des elements du DOM sans enfant element, ce qui jetait tout titre
// contenant un `<br>` ou un `<span>`. Rejoue et photographie, le cas qui avait
// calibre son seuil (audit_v94, « FAQ 658 px remplie a 12 % ») est une FAQ
// COMPLETE a cinq cartes. Cette porte n a jamais attrape un vrai positif: elle
// en fabriquait. Voir `computeSectionFill` et `EMPTY_SECTION_FILL`.
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
  /**
   * Part de la hauteur reellement occupee par du contenu, 0..1.
   *
   * Heritage: cette valeur venait d une SOMME d aires de feuilles du DOM, et
   * elle etait fausse (cf. `computeSectionFill`). Elle n est plus qu un repli
   * pour les appelants qui ne fournissent pas de bandes.
   */
  fill?: number
  /**
   * Intervalles verticaux [haut, bas], en px relatifs au haut de la section, ou
   * du contenu est REELLEMENT peint: texte (mesure au Range, donc independant
   * de l imbrication DOM), medias, et fonds image.
   */
  bands?: Array<[number, number]>
  /** Selecteur CSS de la section — la nommer sans ambiguite. */
  selector?: string
  /** Fichier source qui porte cette section, quand il a pu etre attribue. */
  sourceFile?: string
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
  /**
   * Fichiers DESIGNES par la mesure comme portant un defaut. Une passe ciblee
   * qui ignore cette liste doit deviner: au run 1161 elle a reecrit cinq pages
   * sans jamais ouvrir celle qui portait la section incriminee.
   */
  evidencePaths: string[]
}

/**
 * Sous ce taux d occupation VERTICALE, une section haute est un vide a l ecran.
 *
 * Correction d honnetete (run 1161). Le commentaire precedent disait: « le cas
 * reel mesure 12 % sur 658 px ». Ce cas a ete rejoue et photographie
 * (output/code/audit_v117/v94_faq.png): c est une FAQ COMPLETE — titre,
 * sous-titre, cinq cartes en accordeon. Elle n a jamais ete vide. Le seuil avait
 * donc ete cale sur un artefact de mesure, pas sur un defaut. Rejouee avec la
 * mesure d occupation reelle, la meme section sort a 85,4 %.
 *
 * Aucun vrai positif historique n existe pour calibrer ce seuil: 0,15 est donc
 * volontairement CONSERVATEUR — une section de 900 px dont le contenu tient sur
 * 110 px est signalee, le doute profite au livrable.
 */
export const EMPTY_SECTION_FILL = 0.15
/** Une section courte peut legitimement respirer: on ne juge que le grand vide. */
export const EMPTY_SECTION_MIN_HEIGHT = 400
/**
 * Un blanc de respiration entre deux blocs n est pas un vide. En dessous de
 * cette part de la hauteur de section, l intervalle est recolle: c est du
 * `padding`, pas un trou.
 */
export const SECTION_GAP_TOLERANCE = 0.12

/**
 * Part de la hauteur d une section reellement occupee par du contenu.
 *
 * Ce que faisait la mesure precedente, et pourquoi elle etait fausse (run 1161,
 * mesure element par element sur le livrable reel): elle SOMMAIT l aire des
 * elements du DOM n ayant AUCUN enfant element. Un titre contenant un `<br>`
 * — donc un enfant — etait integralement jete. Sur le hero de la Brulerie:
 *
 *     h1.hero-title  1440x298 px   JETE (contient un <br>)
 *     div.hero-content 1440x704    JETE (conteneur)
 *     compte: p 700x37 + img 330x289 + a 128x17   ->  fill = 9 %
 *
 * Le hero occupait 704 px sur 944, et la porte l a declare « quasi vide a 9 % ».
 * Pire, la mesure n avait aucune dynamique: une grille de quatre produits
 * entierement remplie sortait a 18,7 %, pour un seuil a 15 %. La porte
 * condamnait une chose qu elle n avait jamais mesuree.
 *
 * On mesure donc l OCCUPATION VERTICALE reelle: l union des bandes ou du
 * contenu est peint, les respirations courtes recollees. Un hero plein sort
 * au-dessus de 60 %, une section de 658 px qui ne porte que deux lignes reste
 * a 12 % — le cas d origine qui a calibre le seuil est preserve.
 */
export function computeSectionFill(section: SectionFill): number {
  if (!Array.isArray(section.bands)) {
    // Rien de mesure: on ne prononce rien. Un defaut non mesure n est pas un
    // defaut constate — c est la regle de tout ce module.
    return typeof section.fill === 'number' ? section.fill : 1
  }
  const height = section.height
  if (!(height > 0)) return 1

  const spans = section.bands
    .map(([a, b]) => [Math.max(0, Math.min(a, b)), Math.min(height, Math.max(a, b))] as [number, number])
    .filter(([a, b]) => b > a)
    .sort((x, y) => x[0] - y[0])
  if (spans.length === 0) return 0

  const tolerance = height * SECTION_GAP_TOLERANCE
  const merged: Array<[number, number]> = [[spans[0][0], spans[0][1]]]
  for (const [a, b] of spans.slice(1)) {
    const last = merged[merged.length - 1]
    if (a - last[1] <= tolerance) last[1] = Math.max(last[1], b)
    else merged.push([a, b])
  }
  const covered = merged.reduce((sum, [a, b]) => sum + (b - a), 0)
  return Math.max(0, Math.min(1, covered / height))
}

export function findEmptySections(sections: SectionFill[]): SectionFill[] {
  return sections.filter((s) => s.height >= EMPTY_SECTION_MIN_HEIGHT && computeSectionFill(s) < EMPTY_SECTION_FILL)
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
        : emptySections.slice(0, 3).map(describeEmptySection).join(' | '),
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
    evidencePaths: [...new Set(emptySections.map((s) => s.sourceFile).filter((p): p is string => Boolean(p)))],
  }
}

/**
 * Nomme la section incriminee: son texte, son SELECTEUR et le FICHIER qui la
 * porte. Sans cela le correcteur recoit « section: 944px remplie a 9% » sur un
 * projet de 31 fichiers, et ne peut que deviner — au run 1161 il a reecrit cinq
 * pages sans jamais ouvrir `HeroSection.tsx`, qui portait la section visee.
 */
function describeEmptySection(s: SectionFill): string {
  const where = [s.selector, s.sourceFile].filter(Boolean).join(' dans ')
  const fill = Math.round(computeSectionFill(s) * 100)
  return `${where ? `${where} — ` : ''}"${s.label}": ${Math.round(s.height)}px occupee a ${fill}%`
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
/** Meme jeu de plages, SANS le drapeau global: `.test()` sur un regex global
 * avance `lastIndex` et rend le resultat dependant de l appel precedent. */
const EMOJI_ANYWHERE_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}]/u

/**
 * Le texte contient-il un pictogramme, OU QUE CE SOIT ?
 *
 * `detectEmojiIcons` ne voit que les emoji ecrits entre deux balises
 * (`<span>☕</span>`). Le juge, lui, mesure le DOM RENDU. Mesure sur le run 1061:
 * la porte `real_iconography` echouait sur des etoiles produites par
 * `{'★'.repeat(rating)}` — une expression JavaScript. Le navigateur les voyait,
 * l analyse de source non. Une reparation ciblee doit chercher les emoji la ou
 * ils VIVENT dans le code, pas seulement la ou ils sont ecrits litteralement.
 */
export function containsPictographicEmoji(text: string): boolean {
  return EMOJI_ANYWHERE_RE.test(text)
}

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
