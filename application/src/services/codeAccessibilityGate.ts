// Accessibilite mesuree au RENDU, pas devinee a la source.
//
// Un critic source existe deja (`codeStaticAccessibility`): 4 regles par regex
// — alt manquant, bouton icone sans aria-label, `<a>` sans href, input sans
// label. Utile, mais aveugle a tout ce qui n existe qu APRES mise en page: le
// contraste reellement calcule, l ordre des titres, la langue du document, le
// nom accessible d un bouton dont le libelle vient d une variable.
//
// C est la meme lecon que la porte de composition: certaines verites ne se
// lisent qu a l ecran. Ce module note ce que le navigateur a mesure; il ne
// mesure rien lui-meme, ce qui le rend testable sans navigateur.

export type AccessibilityMetrics = {
  /** `lang` du document, vide si absent. */
  documentLang: string
  /** Images porteuses de sens sans nom accessible. */
  imagesWithoutName: string[]
  /** Controles interactifs sans nom accessible (bouton icone, lien vide...). */
  controlsWithoutName: string[]
  /** Champs de formulaire sans etiquette associee. */
  fieldsWithoutLabel: string[]
  /** Niveaux de titres rencontres, dans l ordre du document. */
  headingLevels: number[]
  /** Textes dont le contraste calcule est sous 4.5:1 (AA). */
  lowContrastSamples: Array<{ text: string; ratio: number }>
  /** Elements interactifs inatteignables au clavier. */
  unreachableByKeyboard: string[]
}

export type AccessibilityCheck = {
  id: string
  label: string
  passed: boolean
  weight: number
  evidence?: string
  /**
   * Le critere avait-il quelque chose a MESURER ?
   *
   * MESURE: une page entierement vide obtenait 76/100 en accessibilite et
   * 62/100 en performance. Ces criteres comptent une ABSENCE DE VIOLATION
   * comme une PRESENCE DE QUALITE — sans image, aucune image ne manque
   * d alternative; sans controle, aucun n est inatteignable. Un critere sans
   * matiere n a pas mesure: il sort du score.
   */
  conclusive?: boolean
}

export type AccessibilityVerdict = {
  score: number
  ok: boolean
  floor: number
  checks: AccessibilityCheck[]
  failedChecks: string[]
  critique: string
}

/** Seuil AA du contraste texte normal. */
export const CONTRAST_AA = 4.5

const FLOOR = 80

function sample(values: readonly string[], max = 3): string {
  return values.slice(0, max).join(', ')
}

/**
 * Titres: un `h1` doit exister et les niveaux ne doivent pas sauter de marche
 * (h2 -> h4). C est la colonne vertebrale d une page pour un lecteur d ecran.
 */
export function findHeadingOrderIssues(levels: readonly number[]): string[] {
  const issues: string[] = []
  if (levels.length === 0) return ['aucun titre dans la page']
  if (!levels.includes(1)) issues.push('aucun <h1>')
  let previous = levels[0]
  for (const level of levels.slice(1)) {
    if (level > previous + 1) issues.push(`saut de <h${previous}> a <h${level}>`)
    previous = level
  }
  return issues
}

export function scoreAccessibility(metrics: AccessibilityMetrics): AccessibilityVerdict {
  // Y a-t-il eu une page a auditer ? Sans aucun titre, image, controle, champ
  // ni echantillon de texte, l audit ne mesure rien — il constate un vide.
  const hasContent = metrics.headingLevels.length > 0
    || metrics.imagesWithoutName.length > 0
    || metrics.controlsWithoutName.length > 0
    || metrics.fieldsWithoutLabel.length > 0
    || metrics.lowContrastSamples.length > 0
    || metrics.unreachableByKeyboard.length > 0
    || Boolean(metrics.documentLang)
  const headingIssues = findHeadingOrderIssues(metrics.headingLevels)
  const worstContrast = metrics.lowContrastSamples
    .slice()
    .sort((a, b) => a.ratio - b.ratio)[0]

  const checks: AccessibilityCheck[] = [
    {
      id: 'document_lang',
      label: 'Langue du document declaree (<html lang>)',
      passed: metrics.documentLang.trim().length >= 2,
      weight: 10,
      evidence: metrics.documentLang ? undefined : 'attribut lang absent',
    },
    {
      id: 'images_have_name',
      conclusive: metrics.imagesWithoutName.length > 0 || hasContent,
      label: `Images avec texte alternatif (${metrics.imagesWithoutName.length} sans)`,
      passed: metrics.imagesWithoutName.length === 0,
      weight: 18,
      evidence: metrics.imagesWithoutName.length ? sample(metrics.imagesWithoutName) : undefined,
    },
    {
      id: 'controls_have_name',
      conclusive: metrics.controlsWithoutName.length > 0 || hasContent,
      label: `Controles avec nom accessible (${metrics.controlsWithoutName.length} sans)`,
      passed: metrics.controlsWithoutName.length === 0,
      weight: 20,
      evidence: metrics.controlsWithoutName.length ? sample(metrics.controlsWithoutName) : undefined,
    },
    {
      id: 'fields_have_label',
      conclusive: metrics.fieldsWithoutLabel.length > 0 || hasContent,
      label: `Champs avec etiquette (${metrics.fieldsWithoutLabel.length} sans)`,
      passed: metrics.fieldsWithoutLabel.length === 0,
      weight: 16,
      evidence: metrics.fieldsWithoutLabel.length ? sample(metrics.fieldsWithoutLabel) : undefined,
    },
    {
      id: 'heading_order',
      conclusive: metrics.headingLevels.length > 0,
      label: 'Hierarchie de titres coherente',
      passed: headingIssues.length === 0,
      weight: 14,
      evidence: headingIssues.length ? sample(headingIssues) : undefined,
    },
    {
      id: 'text_contrast',
      conclusive: metrics.lowContrastSamples.length > 0 || hasContent,
      label: `Contraste du texte >= ${CONTRAST_AA}:1 (${metrics.lowContrastSamples.length} sous le seuil)`,
      passed: metrics.lowContrastSamples.length === 0,
      weight: 14,
      evidence: worstContrast ? `« ${worstContrast.text.slice(0, 40)} » a ${worstContrast.ratio.toFixed(2)}:1` : undefined,
    },
    {
      id: 'keyboard_reachable',
      conclusive: metrics.unreachableByKeyboard.length > 0 || hasContent,
      label: `Interactifs atteignables au clavier (${metrics.unreachableByKeyboard.length} hors parcours)`,
      passed: metrics.unreachableByKeyboard.length === 0,
      weight: 8,
      evidence: metrics.unreachableByKeyboard.length ? sample(metrics.unreachableByKeyboard) : undefined,
    },
  ]

  // Un critere non concluant sort du numerateur ET du denominateur: il n a rien
  // constate, il ne peut donc ni recompenser ni condamner.
  const conclusive = checks.filter((check) => check.conclusive !== false)
  const total = conclusive.reduce((sum, check) => sum + check.weight, 0)
  const earned = conclusive.filter((check) => check.passed).reduce((sum, check) => sum + check.weight, 0)
  const score = total > 0 ? Math.round((earned / total) * 100) : 0
  const failedChecks = conclusive.filter((check) => !check.passed).map((check) => check.id)

  const critique = failedChecks.length === 0
    ? `Accessibilite mesuree au rendu: ${score}/100, rien a signaler.`
    : [
      `## ACCESSIBILITE (${score}/100, seuil ${FLOOR}) — mesuree sur la page RENDUE`,
      '',
      ...checks.filter((check) => !check.passed).map((check) => (
        `- ${check.label}${check.evidence ? ` — ${check.evidence}` : ''}`
      )),
      '',
      'Ces defauts se corrigent sans rien changer au design: un `alt` decrit l image,',
      'un `aria-label` nomme un bouton icone, un `<label for>` relie un champ, et un',
      'texte gris clair sur fond blanc se fonce jusqu a 4.5:1.',
    ].join('\n')

  return { score, ok: score >= FLOOR, floor: FLOOR, checks, failedChecks, critique }
}
