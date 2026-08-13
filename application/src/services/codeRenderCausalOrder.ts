// ---------------------------------------------------------------------------
// codeRenderCausalOrder — separer LA cause de ses symptomes.
//
// Run 1101. L application crashe au montage:
//
//   TypeError: Cannot read properties of undefined (reading 'map')
//
// La porte de rendu a alors declare SEPT echecs:
//
//   runtime_clean, display_typography, type_scale, real_typeface,
//   visual_content, depth, interactivity
//
// et la passe ciblee a corrige HUIT fichiers de style (App.css, Header.css,
// animations.css, variables.css...). Resultat: 10/100 avant, 10/100 apres.
//
// Les six derniers n etaient pas des defauts: quand la page ne monte pas, il n y
// a ni typographie, ni profondeur, ni interactivite A MESURER. On a note
// l absence d un rendu comme si c etait un defaut de gout, puis on a envoye le
// modele repeindre une page qui ne s affiche pas.
//
// C est la regle constante de ce module, poussee d un cran: un juge qui ne peut
// pas mesurer ne condamne pas — et un juge dont la page n a jamais monte n a
// rien mesure DU TOUT. Tant que le crash n est pas repare, les criteres en aval
// ne sont pas « echoues », ils sont NON CONCLUANTS.
// ---------------------------------------------------------------------------

/** L echec qui empeche toute mesure en aval: la page n a pas tenu. */
export const RENDER_ROOT_FAILURE = 'runtime_clean'

/**
 * Criteres qui n ont de sens que sur une page REELLEMENT montee. Tous les
 * criteres de style, de composition, d accessibilite et de performance en font
 * partie: ils se mesurent sur des rectangles, des couleurs et des noeuds qui
 * n existent pas quand le montage echoue.
 */
export function dependsOnMountedPage(checkId: string): boolean {
  return checkId !== RENDER_ROOT_FAILURE
}

export type CausalSplit = {
  /** Ce qu il faut reparer, et rien d autre. */
  causes: string[]
  /** Mesures rendues non concluantes par la cause. */
  symptoms: string[]
}

/**
 * Reduit une liste d echecs a sa ou ses causes. Sans crash, tout echec est une
 * cause: on ne masque jamais un vrai defaut de style.
 */
export function splitRenderFailures(failedChecks: readonly string[]): CausalSplit {
  const unique = [...new Set(failedChecks.filter((id) => typeof id === 'string' && id.length > 0))]
  if (!unique.includes(RENDER_ROOT_FAILURE)) {
    return { causes: unique, symptoms: [] }
  }
  return {
    causes: [RENDER_ROOT_FAILURE],
    symptoms: unique.filter(dependsOnMountedPage),
  }
}

/**
 * Chemins SOURCE nommes par les traces resolues. C est la portee naturelle de la
 * reparation: le crash designe lui-meme les fichiers a corriger, il n y a plus a
 * deviner. Les positions de bundle non resolues sont ignorees — elles ne
 * designent aucun fichier reparable.
 */
export function extractSourcePathsFromErrors(errors: readonly string[]): string[] {
  const found = new Set<string>()
  for (const error of errors) {
    if (typeof error !== 'string') continue
    for (const match of error.matchAll(/(?:^|[\s(])((?:src|app|lib|pages|components)\/[\w./@-]+\.(?:[jt]sx?|vue|svelte)):(\d+)/g)) {
      found.add(match[1])
    }
  }
  return [...found]
}

/**
 * Consigne de correction quand la page ne monte pas. Elle dit deux choses, et
 * seulement deux: repare CE crash, et ne touche a rien d autre.
 */
export function buildRenderRootCauseCritique(args: {
  consoleErrors: readonly string[]
  symptoms: readonly string[]
}): string {
  const errors = args.consoleErrors.filter((e) => typeof e === 'string' && e.trim().length > 0)
  return [
    '## LA PAGE NE MONTE PAS — CORRIGE CE CRASH, ET RIEN D AUTRE',
    'La page a ete ouverte dans un navigateur. Elle a leve une erreur au chargement,',
    'donc AUCUN pixel n a ete rendu et aucune autre mesure n a de valeur.',
    '',
    '### Erreur exacte, resolue en position source',
    ...(errors.length > 0
      ? errors.slice(0, 3).map((e) => `\`\`\`\n${e.slice(0, 1200)}\n\`\`\``)
      : ['(aucune trace capturee — cherche un acces a une valeur absente au montage)']),
    '',
    '### Ce que tu dois faire',
    '- Corrige UNIQUEMENT la cause de cette erreur, dans le ou les fichiers qu elle nomme.',
    '- Un `.map()`, un `.length` ou une destructuration sur une valeur `undefined` se repare',
    '  a la SOURCE de la donnee (import, export par defaut, valeur initiale du state,',
    '  props manquante), pas par un `?.` pose au hasard sur le symptome.',
    '- Ne retouche AUCUN fichier de style: une page qui ne s affiche pas n a pas de',
    '  probleme de typographie, de profondeur ni d interactivite.',
    args.symptoms.length > 0
      ? `- Les criteres suivants sont NON CONCLUANTS tant que la page ne monte pas, ils ne sont pas des defauts: ${args.symptoms.join(', ')}.`
      : '',
  ].filter(Boolean).join('\n')
}
