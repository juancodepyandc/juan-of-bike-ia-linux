// ---------------------------------------------------------------------------
// codeNpmDiagnostics — separer ce qui ECHOUE de ce qui PARLE.
//
// Effet de bord mesure du correctif « stderr fusionne » (run 1191): npm ecrit
// sur stderr ses AVERTISSEMENTS autant que ses erreurs. Une fois stderr rendu
// au pipeline, les avertissements sont arrives dans le texte remis au
// correcteur, et le modele a passe les passes 5, 6 et 7 a diagnostiquer:
//
//   « L erreur provient d une dependance obsolete (inflight@1.0.6 et
//     glob@7.2.3) »
//
// Or `npm warn deprecated` ne fait echouer aucune installation. Rendre stderr
// etait juste — un echec muet est pire —, mais le CODE DE SORTIE fait foi, pas
// la presence de texte. C est la regle du module appliquee a elle-meme:
// mesurer ce qui echoue, pas ce qui parle.
//
// Deuxieme mesure, plus lourde, sur le meme run: la VRAIE cause de l echec
// etait la, lisible, et personne ne l a lue.
//
//   npm error code ENOSPC
//   npm error nospc ENOSPC: no space left on device, write
//   npm error nospc There appears to be insufficient space on your system.
//
// Aucune modification du code livre ne repare un disque plein. Le pipeline a
// pourtant renvoye ce texte au modele neuf fois. Verifie sur l hote au moment
// de l analyse: 99 % d occupation, et le volume de workspace podman est cree
// SANS quota (« Filesystem does not support Project Quota »), donc directement
// sur ce disque plein. Le sandbox n avait aucune reserve propre.
//
// C est, une fois de plus, une porte qui condamne le code pour quelque chose
// qu elle n a jamais mesure.
// ---------------------------------------------------------------------------

/**
 * Lignes que npm ecrit sans qu aucune d elles ne decrive un echec.
 *
 * `npm error A complete log of this run can be found in: ...` en fait partie:
 * c est une note de journalisation emise A CHAQUE echec, elle ne dit jamais
 * POURQUOI. Seule, elle ne donne rien a corriger.
 */
const NPM_NOISE_PATTERNS: RegExp[] = [
  /^npm\s+warn\b/i,
  /^npm\s+notice\b/i,
  /^npm\s+error\s+A complete log of this run can be found in\b/i,
]

export function isNpmNoiseLine(line: string): boolean {
  const trimmed = line.trim()
  if (trimmed.length === 0) return false
  return NPM_NOISE_PATTERNS.some((pattern) => pattern.test(trimmed))
}

/**
 * Retire le bruit npm d une sortie destinee au CORRECTEUR.
 *
 * Conserve tout le reste a l identique — y compris les lignes qu on ne
 * reconnait pas: on ne retire que ce dont on est certain qu il ne decrit aucun
 * echec. Le compte des lignes ecartees est rendu, jamais cache.
 */
export function stripNpmNoise(output: string): { text: string; removed: number } {
  const lines = (output ?? '').split('\n')
  const kept: string[] = []
  let removed = 0
  for (const line of lines) {
    if (isNpmNoiseLine(line)) {
      removed += 1
      continue
    }
    kept.push(line)
  }
  return { text: kept.join('\n').trim(), removed }
}

/**
 * Pannes de RESSOURCE de l hote: aucune reecriture du code livre ne les repare.
 *
 * Etroit par construction — on ne veut pas requalifier en « environnement » une
 * vraie erreur de dependance ou de compilation.
 */
const NPM_RESOURCE_FAILURE_PATTERNS: RegExp[] = [
  /\bENOSPC\b/,
  /no space left on device/i,
  /insufficient space on your system/i,
  /\bENOMEM\b/,
  /\bEMFILE\b/,
  /\bEFBIG\b/i,
  /file too large/i,
]

export function isResourceExhaustionOutput(output: string | null | undefined): boolean {
  if (!output) return false
  return NPM_RESOURCE_FAILURE_PATTERNS.some((pattern) => pattern.test(output))
}

/**
 * Sortie d etape prete pour la boucle de correction.
 *
 * - Une etape qui a REUSSI n est pas touchee: son bruit ne va nulle part.
 * - Une panne de ressource est NOMMEE comme telle, pour que la porte
 *   d infrastructure la reconnaisse et arrete la boucle au lieu de demander
 *   neuf fois au modele de reparer un disque plein.
 * - Sinon, on rend le texte debruite. S il ne reste RIEN, on le dit: une etape
 *   qui n a produit que des avertissements n a decrit aucun defaut, et
 *   `isNonDiagnosticFailure` doit pouvoir le voir.
 */
export function normalizeNpmStepOutput(args: {
  output: string
  ok: boolean
}): string {
  if (args.ok) return args.output
  const { text, removed } = stripNpmNoise(args.output)

  if (isResourceExhaustionOutput(text)) {
    return [
      'RESSOURCE HOTE EPUISEE — installation impossible, ce n est pas un defaut du code livre.',
      text,
    ].join('\n')
  }

  if (text.length === 0) {
    return removed > 0
      ? `[SORTIE VIDE] apres retrait de ${removed} ligne(s) d avertissement npm (npm warn / npm notice),`
        + ' il ne reste aucune description d echec. Rien ici ne decrit le code livre.'
      : args.output
  }

  return text
}
