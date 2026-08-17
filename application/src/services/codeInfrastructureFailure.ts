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
  /sandbox ws7 indisponible/i,
  /image conteneur absente/i,
  /isolation sandbox indisponible/i,
  /podman (?:rootless )?(?:est )?indisponible/i,
  /workspace conteneurise/i,
  // Ressource de l HOTE epuisee. Run 1191: `npm error code ENOSPC / no space
  // left on device` renvoye NEUF fois au modele comme s il s agissait d un
  // defaut du code. Mesure a l analyse: disque hote a 99 %, et le volume de
  // workspace podman cree SANS quota (le systeme de fichiers ne supporte pas
  // le Project Quota) — le sandbox n avait donc aucune reserve propre.
  // Aucune reecriture de composant React ne libere un octet.
  /ressource hote epuisee/i,
  /\bENOSPC\b/,
  /no space left on device/i,
  /insufficient space on your system/i,
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
/**
 * Une etape qui echoue SANS RIEN DIRE n a rien mesure.
 *
 * Run 1171: la derniere etape en echec etait « Installer les dependances », et
 * sa sortie faisait ZERO octet. Verifications faites sur le livrable reel:
 *
 *   npm install sur l hote                       -> exit 0, 153 paquets, 5 s
 *   npm install sous les memes drapeaux podman   -> exit 0
 *   (reseau slirp4netns, keep-id, read-only, tmpfs 256m, memory 2g,
 *    pids 256, fsize 512 Mio, volume nomme)
 *
 * Le projet s installe. Le pipeline a pourtant livre `phase: error`, donc un
 * verdict de QUALITE, sur une etape dont il ne reste aucune trace.
 *
 * Une sortie vide ne decrit aucun defaut, ne se donne a aucun correcteur, et ne
 * se repare pas: c est la definition meme, dans ce module, d une validation qui
 * n a pas pu s executer. Le precedent est ecrit noir sur blanc dans
 * codeSandboxIsolation.ts: un plafond RLIMIT_FSIZE mal converti faisait echouer
 * `npm install` en EFBIG « avec une sortie vide cote pipeline, donc sans
 * diagnostic possible ».
 *
 * On ne PRETEND pas connaitre la cause. On refuse seulement de transformer une
 * absence de mesure en condamnation du code.
 */
/**
 * Prefixe d une etape qui a echoue SANS RIEN DIRE, et dont on a releve le
 * contexte machine a l instant exact de l echec (code de sortie, memoire
 * disponible, pression memoire).
 *
 * Ces lignes decrivent la MACHINE, jamais le code livre: une etape marquee
 * ainsi reste non diagnostique — on ne peut toujours pas en tirer une
 * correction. Elles servent a l humain et au journal, pas au correcteur.
 */
export const SILENT_STEP_MARKER = '[SORTIE VIDE]'

export function isNonDiagnosticFailure(output: string | null | undefined): boolean {
  if (!output || output.trim().length === 0) return true
  // Une sortie vide RESTE une sortie vide une fois annotee du contexte machine.
  // Sans cette ligne, instrumenter l echec silencieux le reclasserait en defaut
  // de code — on aurait paye la mesure pour perdre la conclusion.
  return output.trim().startsWith(SILENT_STEP_MARKER)
}

export function isSandboxInfrastructureFailure(result: SandboxLike | null | undefined): boolean {
  if (!result || result.ok) return false
  if (isInfrastructureFailureMessage(result.summary)) return true
  const steps = result.steps ?? []
  if (steps.length === 0) return false
  const failing = steps.filter((step) => !step.ok)
  if (failing.length === 0) return false
  // Toutes les etapes en echec pointent une panne reseau/bridge, ou n ont rien
  // produit du tout — dans les deux cas, rien n a ete mesure sur le code.
  return failing.every((step) => isInfrastructureFailureMessage(step.output) || isNonDiagnosticFailure(step.output))
}

/** Note livree a l utilisateur: la degradation ne doit jamais etre silencieuse. */
export function buildInfrastructureFailureNote(summary: string | null | undefined): string {
  return [
    '## VALIDATION INDISPONIBLE',
    `La validation sandbox n a pas pu s executer: ${summary || 'infrastructure injoignable'}.`,
    'Ce n est PAS un defaut du code livre: le juge lui-meme n a pas repondu.',
    'Les passes de correction sont donc arretees — corriger du code ne repare pas une panne d infrastructure,',
    'et les passes precedentes degradaient le livrable en cherchant une faute inexistante.',
    // On NOMMAIT une cause qu on n avait pas mesuree (« bridge arrete ou reseau
    // coupe »). Verification au run 1151: le bridge etait vivant, health 200.
    // Une note qui affirme une cause non mesuree envoie chercher au mauvais
    // endroit — exactement le travers que ce module corrige partout ailleurs.
    'Cause exacte non mesuree ici: un appel de validation n a pas abouti, ou une etape a echoue',
    'sans produire la moindre sortie — dans les deux cas il ne reste rien a diagnostiquer.',
    'Pistes, par ordre de cout: contention pendant que le modele occupe la machine, delai depasse',
    'sur un appel long, ou service indisponible. Relance la validation pour obtenir un verdict reel.',
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
