// ---------------------------------------------------------------------------
// codeRenderedAestheticScore — juge ce que le NAVIGATEUR affiche, pas ce que le
// CSS declare.
//
// Pourquoi ce module existe. Une landing Mercedes-Benz produite par le pipeline
// complet a ete notee **87/100, « Rendu visuel acceptable »** par la porte
// source-statique. Capture reelle de la meme page dans Chromium:
//
//   - un vide blanc d environ 1 000 px en guise de hero;
//   - la plus GROSSE typo de la page en 1440 px de large: **18 px**;
//   - familles reellement resolues: Helvetica Neue et Georgia — soit
//     exactement les polices par defaut que le contrat design interdit;
//   - 0 image, 0 ombre, 4 elements interactifs;
//   - et la page est CASSEE au runtime: `Lenis is not defined`,
//     `SyntaxError: Unexpected identifier 'email'`.
//
// Une porte qui lit la SOURCE est structurellement trompable: le CSS peut
// declarer « Instrument Serif », des animations et une echelle typographique
// riche; si la police ne charge pas et que le titre sort en 18 px, le rendu est
// pauvre malgre une source flatteuse. Seul le rendu tranche.
//
// Ce module est volontairement PUR: il note des metriques deja mesurees sur le
// rendu (via getComputedStyle dans un vrai navigateur). Le navigateur vit dans
// `scripts/code_harness/aesthetic_capture.mjs`; la regle de notation vit ici,
// donc elle est testable sans navigateur.
// ---------------------------------------------------------------------------

/** Familles que le navigateur resout quand AUCUNE police premium n a charge. */
const FALLBACK_FAMILIES = [
  'helvetica', 'helvetica neue', 'arial', 'georgia', 'times', 'times new roman',
  'serif', 'sans-serif', 'monospace', 'system-ui', '-apple-system', 'roboto',
  'segoe ui', 'liberation serif', 'liberation sans', 'dejavu sans', 'ui-sans-serif',
]

export type RenderedViewportMetrics = {
  fontFamilies: string[]
  distinctTextColors: number
  distinctBackgrounds: number
  fontSizeScale: number[]
  distinctRadii: number
  distinctShadows: number
  animatedElements: number
  sections: number
  images: number
  canvases?: number
  interactive: number
  documentHeight: number
}

export type RenderedAestheticCheck = {
  id: string
  label: string
  weight: number
  passed: boolean
  evidence: string
  /**
   * Le critere a-t-il pu MESURER quelque chose ?
   *
   * Un critere non concluant ne compte ni dans le score ni dans les echecs: il
   * n a rien constate. Voir `scoreRenderedAesthetics` pour la mesure qui a
   * impose cette distinction.
   */
  conclusive?: boolean
}

export type RenderedAestheticVerdict = {
  score: number
  floor: number
  passed: boolean
  checks: RenderedAestheticCheck[]
  failedChecks: string[]
  critique: string
  /** Le style a-t-il pu etre mesure, ou la page n a-t-elle rien rendu ? */
  styleMeasured: boolean
}

function usesOnlyFallbackFonts(families: string[]): boolean {
  const real = families.map((f) => f.toLowerCase().trim()).filter(Boolean)
  if (real.length === 0) return true
  return real.every((f) => FALLBACK_FAMILIES.includes(f))
}

/**
 * Note le rendu d un projet visuel.
 *
 * Les seuils viennent d observations, pas d intuitions: chacun correspond a un
 * defaut constate sur une page reellement livree et pourtant notee 87/100.
 */
export function scoreRenderedAesthetics(args: {
  desktop: RenderedViewportMetrics
  mobile?: RenderedViewportMetrics | null
  consoleErrors?: string[]
  floor?: number
}): RenderedAestheticVerdict {
  const d = args.desktop
  const errors = args.consoleErrors ?? []
  const maxFont = d.fontSizeScale.length > 0 ? Math.max(...d.fontSizeScale) : 0
  const distinctSizes = new Set(d.fontSizeScale).size

  const checks: RenderedAestheticCheck[] = [
    {
      id: 'runtime_clean',
      label: 'La page ne casse pas au chargement',
      weight: 22,
      passed: errors.length === 0,
      evidence: errors.length === 0 ? 'aucune erreur runtime' : `${errors.length} erreur(s): ${errors.slice(0, 2).join(' | ')}`,
    },
    {
      id: 'display_typography',
      label: 'Une vraie typographie d affichage existe (>= 40 px en desktop)',
      weight: 18,
      passed: maxFont >= 40,
      evidence: `plus grande taille rendue: ${maxFont}px`,
    },
    {
      id: 'type_scale',
      label: 'Echelle typographique riche (>= 4 tailles distinctes)',
      weight: 10,
      passed: distinctSizes >= 4,
      evidence: `${distinctSizes} taille(s): ${d.fontSizeScale.join('/')}`,
    },
    {
      id: 'real_typeface',
      label: 'Une police choisie a reellement charge (pas seulement les fallbacks)',
      weight: 12,
      passed: !usesOnlyFallbackFonts(d.fontFamilies),
      evidence: `familles resolues: ${d.fontFamilies.join(', ') || 'aucune'}`,
    },
    {
      id: 'visual_content',
      label: 'La page montre quelque chose (image, svg ou canvas)',
      weight: 12,
      passed: (d.images + (d.canvases ?? 0)) > 0,
      evidence: `${d.images} image(s)/svg, ${d.canvases ?? 0} canvas`,
    },
    {
      id: 'depth',
      label: 'Le rendu n est pas totalement plat (ombres ou rayons)',
      weight: 8,
      passed: d.distinctShadows > 0 || d.distinctRadii > 1,
      evidence: `${d.distinctShadows} ombre(s), ${d.distinctRadii} rayon(s)`,
    },
    {
      id: 'content_density',
      label: 'La page n est pas un grand vide (contenu proportionne a sa hauteur)',
      weight: 10,
      // Une page BLANCHE passait ce critere: `documentHeight <= 900` est vrai
      // quand il n y a rien du tout. Un critere qui dit « ce n est pas un grand
      // vide » ne peut pas etre satisfait PAR le vide.
      passed: (d.sections + d.interactive + d.images) > 0
        && (d.documentHeight <= 900 || (d.sections + d.interactive + d.images) >= Math.floor(d.documentHeight / 350)),
      evidence: `${d.documentHeight}px de haut pour ${d.sections} section(s), ${d.interactive} controle(s), ${d.images} image(s)`,
    },
    {
      id: 'interactivity',
      label: 'La page offre de vrais controles (>= 5)',
      weight: 8,
      passed: d.interactive >= 5,
      evidence: `${d.interactive} element(s) interactif(s)`,
    },
  ]

  // MESURE (corpus des 33 runs archives, verdicts de rendu):
  //
  //   runtime_clean EN ECHEC :  4 runs, score moyen 22/100
  //   runtime_clean OK       : 10 runs, score moyen 78/100
  //
  // Les trois runs a 10/100 (v93, v110, v120) echouent EXACTEMENT les memes
  // sept criteres — tous. Ce n est pas une page laide: c est une page qui n a
  // pas rendu. Le DOM etant vide, `maxFont` vaut 0, aucune police ne charge,
  // aucune image n existe — donc six criteres de STYLE se declarent en echec
  // alors qu ils n ont rien mesure, et retirent 68 points a un livrable dont
  // personne n a vu le style.
  //
  // C est le motif recurrent de ce module applique a la note de rendu: une
  // porte qui condamne ce qu elle n a jamais mesure. Le cout est double —
  // le score raconte « laid » quand il fallait lire « cassé », et la passe
  // ciblee part corriger la typographie au lieu de l erreur d execution.
  //
  // Un critere non concluant sort donc du numerateur ET du denominateur.
  const nothingRendered = d.fontSizeScale.length === 0
    && d.fontFamilies.length === 0
    && d.images === 0
    && (d.canvases ?? 0) === 0
    && d.interactive === 0
    && d.sections === 0
  const STYLE_CHECKS = new Set([
    'display_typography', 'type_scale', 'real_typeface',
    'visual_content', 'depth', 'content_density', 'interactivity',
  ])
  for (const check of checks) {
    check.conclusive = !(nothingRendered && STYLE_CHECKS.has(check.id))
  }

  const conclusive = checks.filter((c) => c.conclusive !== false)
  const total = conclusive.reduce((sum, c) => sum + c.weight, 0)
  const gained = conclusive.filter((c) => c.passed).reduce((sum, c) => sum + c.weight, 0)
  const score = total > 0 ? Math.round((gained / total) * 100) : 0
  const floor = args.floor ?? 70
  const failed = conclusive.filter((c) => !c.passed)

  return {
    score,
    floor,
    // Une page cassee au runtime ne peut jamais passer, quel que soit le score.
    passed: score >= floor && errors.length === 0,
    checks,
    failedChecks: failed.map((c) => c.id),
    critique: buildRenderedAestheticCritique(failed, score, floor),
    styleMeasured: !nothingRendered,
  }
}

/** Critique actionnable, formulee comme une consigne au modele. */
export function buildRenderedAestheticCritique(
  failed: RenderedAestheticCheck[],
  score: number,
  floor: number,
): string {
  if (failed.length === 0) return ''
  const fixes: Record<string, string> = {
    runtime_clean: 'Corrige les erreurs JavaScript au chargement: toute librairie externe utilisee doit etre reellement importee (ou retiree), et le script ne doit pas contenir d erreur de syntaxe.',
    display_typography: 'Le titre principal doit etre une VRAIE typo d affichage: clamp(48px, 7vw, 96px) en desktop. Un hero dont le plus gros texte fait 18px est un echec.',
    type_scale: 'Utilise une echelle modulaire complete (12/14/16/20/28/40/56/72/96), pas deux ou trois tailles proches.',
    real_typeface: 'Charge reellement la police choisie (balise <link> Google Fonts ou @font-face) — un font-family declare sans chargement retombe sur Georgia/Helvetica, ce qui est exactement le rendu par defaut interdit.',
    visual_content: 'Ajoute un vrai contenu visuel: image du sujet, SVG, degrade mesh ou canvas. Une page de texte seul n est pas une landing premium.',
    depth: 'Ajoute de la profondeur: ombres composites, rayons, superpositions. Un aplat integral fait scolaire.',
    content_density: 'Le hero occupe un vide enorme sans contenu. Reduis la hauteur morte ou remplis-la (visuel, accroche, indicateurs, CTA).',
    interactivity: 'Ajoute de vrais controles (navigation, CTA, onglets, filtres), pas seulement un formulaire nu.',
  }
  return [
    `## RENDU REEL INSUFFISANT (${score}/100, seuil ${floor})`,
    'La page a ete OUVERTE dans un navigateur et mesuree. Les points suivants sont constates a l ecran, pas dans le code:',
    ...failed.map((c) => `- ${c.label} — constate: ${c.evidence}. ${fixes[c.id] ?? ''}`.trim()),
  ].join('\n')
}
