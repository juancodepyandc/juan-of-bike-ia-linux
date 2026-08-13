import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeSandboxStepResult, DetectedLanguage } from './codeSandboxTypes.ts'
import {
  buildPodmanSandboxVolumeCreateArgs,
  buildPodmanSandboxVolumeCreateArgsWithoutQuota,
  buildPodmanSandboxVolumeRemoveArgs,
  buildPodmanSandboxWorkspaceInitArgs,
  DEFAULT_SANDBOX_QUOTAS,
  sandboxWorkspaceVolumeName,
  type PodmanSandboxOptions,
} from './codeSandboxIsolation.ts'

type CommandRunner = typeof runWorkspaceCommand

export type SandboxWorkspaceResult = {
  ok: boolean
  created: boolean
  volumeName: string
  steps: CodeSandboxStepResult[]
  /** Etape reellement fautive, pour ne pas accuser le quota a tort. */
  failedStage?: 'volume' | 'init'
  /** Diagnostic actionnable (image absente, etc.). */
  reason?: string
  /**
   * Le volume a-t-il RECU un quota de taille ? Sur un systeme de fichiers sans
   * Project Quota, Aurora cree deliberement le volume sans lui. Exiger ensuite
   * la preuve de ce quota reviendrait a faire contredire par une porte une
   * decision deja prise en amont — et a condamner la livraison pour une
   * propriete que personne n a demandee.
   */
  quotaEnforced: boolean
}

function commandLine(executable: string, args: string[]) {
  return `${executable} ${args.join(' ')}`.trim()
}

function resultStep(
  label: string,
  executable: string,
  args: string[],
  result: Awaited<ReturnType<CommandRunner>>,
): CodeSandboxStepResult {
  return {
    label,
    command: result.command || commandLine(executable, args),
    ok: result.ok,
    output: result.output,
  }
}

export async function prepareSandboxWorkspaceVolume(
  sandboxRoot: string,
  lang: DetectedLanguage,
  options: PodmanSandboxOptions = {},
  runner: CommandRunner = runWorkspaceCommand,
): Promise<SandboxWorkspaceResult> {
  const volumeName = sandboxWorkspaceVolumeName(sandboxRoot)
  const steps: CodeSandboxStepResult[] = []
  const createArgs = buildPodmanSandboxVolumeCreateArgs(sandboxRoot)
  let create = await runner('podman', createArgs, sandboxRoot, 30_000)
  let quotaEnforced = create.ok
  let effectiveArgs = createArgs

  // Le quota disque est la SEULE garantie qui depende du systeme de fichiers.
  // S il est refuse, on ne sacrifie pas les autres (reseau coupe, racine en
  // lecture seule, plafond de PID, memoire, CPU): on cree le volume sans lui et
  // on l ecrit noir sur blanc dans l etape.
  // Le repli ne peut PAS dependre du message d erreur: `/api/command/run` du
  // bridge renvoie `output: ""` sur echec (exitCode 125 seul). Mesure directe:
  // `podman volume create --opt o=size=768m` -> exitCode 125, output vide;
  // la meme commande sans `--opt` -> exitCode 0. Tester le libelle laissait donc
  // la degradation inerte, et un run reel a brule SEPT passes de correction sur
  // « Quota disque total WS7 indisponible » — une panne d environnement que
  // corriger le code ne repare jamais.
  // Le quota disque est une garantie SOUPLE: si sa creation echoue, quelle que
  // soit la raison, on reessaie sans lui plutot que de perdre toute l isolation.
  if (!create.ok) {
    effectiveArgs = buildPodmanSandboxVolumeCreateArgsWithoutQuota(sandboxRoot)
    create = await runner('podman', effectiveArgs, sandboxRoot, 30_000)
    quotaEnforced = false
  }

  steps.push({
    label: 'Quota disque workspace WS7',
    command: create.command || commandLine('podman', effectiveArgs),
    ok: create.ok,
    output: create.ok
      ? [
          `volume=${volumeName}`,
          quotaEnforced
            ? `workspace-size=${DEFAULT_SANDBOX_QUOTAS.workspaceSize}`
            : `workspace-size=NON APPLIQUE (le systeme de fichiers ne supporte pas le Project Quota); les autres confinements restent actifs`,
          create.output,
        ].join('\n')
      : create.output,
  })
  if (!create.ok) return { ok: false, created: false, volumeName, steps, quotaEnforced, failedStage: 'volume', reason: 'creation du volume refusee' }

  const initArgs = buildPodmanSandboxWorkspaceInitArgs(lang, sandboxRoot, DEFAULT_SANDBOX_QUOTAS, options)
  const init = await runner('podman', initArgs, sandboxRoot, 60_000)
  steps.push(resultStep('Initialisation workspace quota WS7', 'podman', initArgs, init))
  if (!init.ok) {
    // `--pull=never` interdit de telecharger: si l image du langage n est pas
    // deja locale, l init echoue avec « image not known ». Le dire, plutot que
    // de laisser l appelant accuser le quota disque — un message trompeur
    // envoie chercher le probleme au mauvais endroit (c est arrive).
    const missingImage = /image not known|no such image|unable to find image/i.test(init.output || '')
    return {
      ok: false, created: true, volumeName, steps, quotaEnforced, failedStage: 'init',
      reason: missingImage
        ? `image conteneur absente en local pour "${lang}" — lancez "podman pull" pour ce langage (--pull=never interdit le telechargement pendant une generation)`
        : `initialisation du workspace echouee: ${(init.output || '').slice(0, 160)}`,
    }
  }

  return { ok: true, created: true, volumeName, steps, quotaEnforced }
}

export async function cleanupSandboxWorkspaceVolume(
  sandboxRoot: string,
  runner: CommandRunner = runWorkspaceCommand,
): Promise<CodeSandboxStepResult> {
  const removeArgs = buildPodmanSandboxVolumeRemoveArgs(sandboxRoot)
  const result = await runner('podman', removeArgs, sandboxRoot, 30_000)
  return resultStep('Nettoyage volume workspace WS7', 'podman', removeArgs, result)
}
