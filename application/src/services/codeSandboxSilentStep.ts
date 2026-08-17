// ---------------------------------------------------------------------------
// codeSandboxSilentStep — instrumenter l echec qui ne dit rien.
//
// Depuis le run 1171, une etape de sandbox echouait en produisant ZERO octet.
// La consequence etait traitee (`interrupted`, jamais un verdict de qualite),
// mais il ne restait AUCUN element pour trouver la cause: ni le code de sortie
// (le pont le renvoie pourtant, et le pipeline le jetait), ni l etat de la
// machine a cet instant.
//
// La cause principale est desormais fermee en amont (codeCommandStderr: stderr
// etait purement et simplement perdu). Ce module traite le RESTE: si, stderr
// fusionne, une etape se tait encore, alors le processus a ete tue sans pouvoir
// ecrire — et la seule chose qui puisse le dire est le code de sortie plus
// l etat memoire au moment precis de l echec.
//
// On ne PRETEND rien: on releve, on horodate, on nomme les codes connus. Une
// etape ainsi annotee reste NON DIAGNOSTIQUE (voir SILENT_STEP_MARKER).
// ---------------------------------------------------------------------------

import { SILENT_STEP_MARKER } from './codeInfrastructureFailure.ts'

export type HostMemorySnapshot = {
  memAvailableKb: number | null
  memTotalKb: number | null
  swapFreeKb: number | null
  /** `some avg10` de /proc/pressure/memory: 0 = aucune attente sur la memoire. */
  pressureSome10: number | null
  raw: string
}

/** Commande de releve: lecture pure de /proc, aucun effet de bord, ~10 ms. */
export const HOST_SNAPSHOT_COMMAND = {
  executable: 'sh',
  args: [
    '-c',
    'cat /proc/meminfo 2>&1; echo "--- pressure ---"; cat /proc/pressure/memory 2>&1',
  ],
  timeoutMs: 10_000,
}

function readMeminfoKb(raw: string, key: string): number | null {
  const match = raw.match(new RegExp(`^${key}:\\s+(\\d+)\\s+kB`, 'mi'))
  return match ? Number(match[1]) : null
}

export function parseHostMemorySnapshot(raw: string): HostMemorySnapshot {
  const pressure = raw.match(/^some\s+avg10=([\d.]+)/mi)
  return {
    memAvailableKb: readMeminfoKb(raw, 'MemAvailable'),
    memTotalKb: readMeminfoKb(raw, 'MemTotal'),
    swapFreeKb: readMeminfoKb(raw, 'SwapFree'),
    pressureSome10: pressure ? Number(pressure[1]) : null,
    raw,
  }
}

/**
 * Codes de sortie qui NOMMENT la cause d un silence.
 *
 * Volontairement court: on ne nomme que ce dont la signification est certaine.
 * Un code inconnu est rendu tel quel plutot que devine.
 */
export function describeExitCode(exitCode: number | null | undefined): string {
  if (exitCode === null || exitCode === undefined) return 'code de sortie inconnu'
  switch (exitCode) {
    case 124:
      return 'code 124 — delai depasse, le processus a ete arrete avant d avoir fini'
    case 125:
      return 'code 125 — podman lui-meme n a pas pu lancer le conteneur'
    case 126:
      return 'code 126 — commande trouvee mais non executable'
    case 127:
      return 'code 127 — commande introuvable dans le conteneur'
    case 137:
      return 'code 137 — processus TUE (SIGKILL): plafond memoire du conteneur ou OOM killer de l hote'
    case 139:
      return 'code 139 — SIGSEGV'
    case 143:
      return 'code 143 — SIGTERM'
    default:
      return `code ${exitCode}`
  }
}

function formatMib(kb: number | null): string {
  return kb === null ? 'inconnu' : `${Math.round(kb / 1024)} Mio`
}

/**
 * Le texte substitue a une sortie vide. Commence TOUJOURS par le marqueur, ce
 * qui preserve la classification « non diagnostique ».
 */
export function formatSilentStepDiagnostic(args: {
  label: string
  exitCode: number | null | undefined
  snapshot: HostMemorySnapshot | null
  at?: Date
}): string {
  const lines = [
    `${SILENT_STEP_MARKER} « ${args.label} » a echoue sans ecrire un seul octet.`,
    `Instant: ${(args.at ?? new Date()).toISOString()}`,
    `Sortie: ${describeExitCode(args.exitCode)}`,
  ]
  if (args.snapshot) {
    lines.push(
      `Memoire hote a cet instant: disponible ${formatMib(args.snapshot.memAvailableKb)}`
        + ` / total ${formatMib(args.snapshot.memTotalKb)}`
        + ` · swap libre ${formatMib(args.snapshot.swapFreeKb)}`
        + ` · pression memoire some avg10 = ${args.snapshot.pressureSome10 ?? 'inconnue'}`,
    )
  } else {
    lines.push('Memoire hote a cet instant: releve impossible.')
  }
  lines.push(
    'stderr est deja fusionne dans stdout en amont: ce silence n est donc PAS une perte de canal.',
    'Rien ici ne decrit le code livre — cette etape ne peut fonder aucune correction.',
  )
  return lines.join('\n')
}

type SnapshotRunner = (
  executable: string,
  args: string[],
  cwd: string,
  timeoutMs?: number,
) => Promise<{ ok: boolean; output: string }>

/** Releve l etat machine. Ne jette jamais: une instrumentation ne casse rien. */
export async function captureHostMemorySnapshot(
  cwd: string,
  runner: SnapshotRunner,
): Promise<HostMemorySnapshot | null> {
  try {
    const result = await runner(
      HOST_SNAPSHOT_COMMAND.executable,
      HOST_SNAPSHOT_COMMAND.args,
      cwd,
      HOST_SNAPSHOT_COMMAND.timeoutMs,
    )
    if (!result?.output) return null
    return parseHostMemorySnapshot(result.output)
  } catch {
    return null
  }
}

/**
 * Sortie definitive d une etape: inchangee si elle a parle, instrumentee sinon.
 */
export async function annotateStepOutput(args: {
  label: string
  output: string
  ok: boolean
  exitCode: number | null | undefined
  cwd: string
  runner: SnapshotRunner
}): Promise<string> {
  const trimmed = (args.output ?? '').trim()
  if (args.ok || trimmed.length > 0) return args.output
  const snapshot = await captureHostMemorySnapshot(args.cwd, args.runner)
  return formatSilentStepDiagnostic({ label: args.label, exitCode: args.exitCode, snapshot })
}
