// ---------------------------------------------------------------------------
// codeInfrastructureFailure — distingue « le code est casse » de « le juge est
// injoignable ».
//
// Mesure sur un run reel de 55 minutes (167 evenements, chronometre depuis les
// horodatages du flux NDJSON):
//
//   8 passes de correction, TOUTES a score 0, TOUTES sur la meme erreur:
//   `fetch failed`. La validation sandbox passe par le bridge; le bridge etait
//   arrete. Le pipeline a donc demande huit fois au modele de corriger du code
//   a cause d une panne d infrastructure que AUCUNE modification de code ne
//   pouvait resoudre.
//
// Le cout ne se limite pas au temps perdu (~17 minutes de passes de correction,
// escalade `targeted_repair` -> `rewrite` -> `strategy_change` x4, 30 fichiers
// reecrits). La qualite a REGRESSE pendant l operation: le score lint est passe
// de 95 % a 85 % puis 80 %, le modele degradant du code correct en cherchant
// une faute inexistante.
//
// Une validation qui n a pas pu S EXECUTER ne dit rien sur le code. La traiter
// comme un echec de code est une erreur de categorie, et c est la source de
// gaspillage la plus chere mesuree sur ce module.
// ---------------------------------------------------------------------------

/**
 * Signatures d une panne d INFRASTRUCTURE: le juge n a pas pu etre atteint ou
 * n a pas pu demarrer. Volontairement etroit — on ne veut surtout pas classer
 * une vraie erreur de compilation ou de test comme « environnement ».
 */
const INFRASTRUCTURE_PATTERNS: RegExp[] = [
  /\bfetch failed\b/i,
  /\bECONNREFUSED\b/i,
  /\bECONNRESET\b/i,
  /\bEHOSTUNREACH\b/i,
  /\bENETUNREACH\b/i,
  /\bEAI_AGAIN\b/i,
  /\bsocket hang up\b/i,
  /network (?:error|request failed)/i,
  /bridge (?:injoignable|unreachable|non joignable)/i,
  /failed to fetch/i,
  // Provisionnement du sandbox: le juge n a pas pu etre CONSTRUIT. Meme erreur
  // de categorie que le reseau, signature differente — un run reel a brule sept
  // passes sur « Quota disque total WS7 indisponible » avant qu on la couvre.
  /quota disque total ws7 indisponible/i,
  /isolation sandbox indisponible/i,
  /podman (?:rootless )?(?:est )?indisponible/i,
  /workspace conteneurise/i,
]

/**
 * L erreur empeche-t-elle le jugement lui-meme, plutot que de decrire un defaut
 * du code livre ?
 */
export function isInfrastructureFailureMessage(message: string | null | undefined): boolean {
  if (!message) return false
  return INFRASTRUCTURE_PATTERNS.some((pattern) => pattern.test(message))
}

export type SandboxLike = {
  ok: boolean
  summary?: string
  steps?: Array<{ ok: boolean; output?: string; label?: string }>
}

/**
 * Le sandbox a-t-il ECHOUE A S EXECUTER (plutot qu execute puis rejete) ?
 *
 * Exige que le resultat soit en echec ET qu aucune etape n ait reellement
 * reussi a juger le code: si des etapes sont passees, le verdict porte bien sur
 * le livrable et la boucle de correction a du sens.
 */
export function isSandboxInfrastructureFailure(result: SandboxLike | null | undefined): boolean {
  if (!result || result.ok) return false
  if (isInfrastructureFailureMessage(result.summary)) return true
  const steps = result.steps ?? []
  if (steps.length === 0) return false
  const failing = steps.filter((step) => !step.ok)
  if (failing.length === 0) return false
  // Toutes les etapes en echec pointent une panne reseau/bridge.
  return failing.every((step) => isInfrastructureFailureMessage(step.output))
}

/** Note livree a l utilisateur: la degradation ne doit jamais etre silencieuse. */
export function buildInfrastructureFailureNote(summary: string | null | undefined): string {
  return [
    '## VALIDATION INDISPONIBLE',
    `La validation sandbox n a pas pu s executer: ${summary || 'infrastructure injoignable'}.`,
    'Ce n est PAS un defaut du code livre: le juge lui-meme etait injoignable (bridge arrete ou reseau coupe).',
    'Les passes de correction sont donc arretees — corriger du code ne repare pas une panne d infrastructure,',
    'et les passes precedentes degradaient le livrable en cherchant une faute inexistante.',
    'Relance la validation une fois le bridge redemarre pour obtenir un verdict reel.',
  ].join('\n')
}

/**
 * Traite une panne d infrastructure detectee en boucle de validation: previent
 * les consommateurs, joint la note a la livraison, et rend le score courant.
 * Retourne null si le resultat n est PAS une panne d infrastructure.
 */
export function handleSandboxInfrastructureFailure<F>(args: {
  result: SandboxLike & { summary?: string }
  files: F[]
  notes: string
  score: number
  onValidationUpdate: (r: never) => void
  onFilesUpdate: (files: F[], notes: string) => void
  setPhase: (detail: string, progress: number) => void
}): { notes: string } | null {
  if (!isSandboxInfrastructureFailure(args.result)) return null
  args.onValidationUpdate(args.result as never)
  const notes = `${args.notes ? `${args.notes}\n\n` : ''}${buildInfrastructureFailureNote(args.result.summary)}`
  args.onFilesUpdate(args.files, notes)
  args.setPhase('Validation indisponible (infrastructure) — livraison sans passe de correction.', 92)
  return { notes }
}
