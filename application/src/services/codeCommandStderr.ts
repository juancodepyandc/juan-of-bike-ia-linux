// ---------------------------------------------------------------------------
// codeCommandStderr — rendre AUDIBLE une commande qui echoue.
//
// Mesure directe sur le pont vivant (aucune supposition), le 2026-08-17:
//
//   POST /api/command/run  sh -c 'echo SUR_STDOUT; echo SUR_STDERR 1>&2; exit 3'
//     -> { exitCode: 3, output: "SUR_STDOUT\n" }        stderr JAMAIS transmis
//
//   POST /api/command/run  podman run --pull=never <image absente> true
//     -> { exitCode: 125, output: "" }                  ZERO octet
//
//   npm install (react@^99.0.0) sur l hote:
//     stdout = 0 octet · stderr = 318 octets · exit 1
//     stderr: « npm error notarget No matching version found for react@^99.0.0 »
//
// Le pont ne renvoie que `result.stdout`. Or npm, podman, tsc et vite ecrivent
// leurs ERREURS sur stderr. Consequence exacte, mesuree: une etape de sandbox en
// echec arrive au pipeline avec une sortie VIDE — la signature du « npm install
// muet » traquee depuis le run 1171.
//
// Elle n etait pas liee a la charge. Elle est liee a l ECHEC: un install qui
// REUSSIT ecrit son resume sur stdout (« added 153 packages »), donc parle; un
// install qui ECHOUE ecrit tout sur stderr, donc se tait. A froid l install
// reussissait — c est pourquoi la panne n a jamais ete reproductible a froid.
//
// Le meme mecanisme est deja documente deux fois dans ce module, sans avoir ete
// relie a cette panne: `buildPodmanImageExistsArgs` (« le pont ne transmet que
// stdout, donc une erreur podman arrive VIDE ») et le `RLIMIT_FSIZE` mal
// converti (« echec EFBIG avec une sortie vide cote pipeline »). Troisieme
// occurrence: on traite la cause, pas l occurrence.
//
// Le pont appartient a l utilisateur et n est pas modifie ici. La fusion se fait
// donc cote appelant, par un shell hote: `sh -c 'exec <cmd> 2>&1'`. `exec`
// evite un processus de plus et laisse le code de sortie passer intact.
//
// PORTEE VOLONTAIREMENT ETROITE: on ne fusionne QUE les commandes dont la sortie
// est du texte de diagnostic libre (install, build, test, lint). Surtout PAS
// celles dont la sortie est analysee comme structure (`podman info --format
// json`, `npm view --json`): un avertissement sur stderr casserait le parse et
// ferait tomber l isolation entiere. Un correctif qui casse ailleurs n en est
// pas un.
// ---------------------------------------------------------------------------

export type MergeableCommand = {
  executable: string
  args: string[]
}

/** Le shell hote sait-il fusionner ? (POSIX oui; cmd.exe n est pas traite ici.) */
export function supportsStderrMerge(platform?: string): boolean {
  const resolved = platform
    ?? (globalThis as { process?: { platform?: string } }).process?.platform
    ?? 'linux'
  return resolved !== 'win32'
}

/**
 * Guillemets POSIX surs: tout est litteral entre apostrophes, et une apostrophe
 * se ferme, s echappe, se rouvre. Aucun caractere du contenu n est interprete —
 * ce qui compte ici, car les arguments podman contiennent deja des `-lc '...'`
 * imbriques, des `&&`, des accolades de `find -exec` et des chemins absolus.
 */
export function shellQuote(value: string): string {
  return `'${value.replace(/'/g, "'\\''")}'`
}

export function buildMergedStderrShellLine(executable: string, args: string[]): string {
  const quoted = [executable, ...args].map(shellQuote).join(' ')
  return `exec ${quoted} 2>&1`
}

/** La commande est-elle DEJA une enveloppe de fusion ? (idempotence) */
export function isMergedStderrCommand(command: MergeableCommand): boolean {
  return command.executable === 'sh'
    && command.args[0] === '-c'
    && /2>&1\s*$/.test(command.args[1] ?? '')
}

/**
 * Renvoie la meme commande, mais dont stderr arrive melange a stdout.
 *
 * Conserve tous les autres champs (label, timeoutMs, optional...) — c est un
 * changement de TRANSPORT, pas de semantique.
 */
export function withMergedStderr<T extends MergeableCommand>(command: T, platform?: string): T {
  if (!supportsStderrMerge(platform)) return command
  if (isMergedStderrCommand(command)) return command
  return {
    ...command,
    executable: 'sh',
    args: ['-c', buildMergedStderrShellLine(command.executable, command.args)],
  }
}

/**
 * Libelle lisible de la commande d ORIGINE.
 *
 * Sans lui, chaque etape s afficherait comme un `sh -c 'exec ...'` de 900
 * caracteres: le transport masquerait la commande, et la trace deviendrait
 * illisible pour l humain comme pour le correcteur.
 */
export function describeCommand(command: MergeableCommand): string {
  return `${command.executable} ${command.args.join(' ')}`.trim()
}
