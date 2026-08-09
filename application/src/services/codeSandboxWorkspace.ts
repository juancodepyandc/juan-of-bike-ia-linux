import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeSandboxStepResult, DetectedLanguage } from './codeSandboxTypes.ts'
import {
  buildPodmanSandboxVolumeCreateArgs,
  buildPodmanSandboxVolumeCreateArgsWithoutQuota,
  buildPodmanSandboxVolumeRemoveArgs,
  buildPodmanSandboxWorkspaceInitArgs,
  DEFAULT_SANDBOX_QUOTAS,
  isVolumeQuotaUnsupportedError,
  sandboxWorkspaceVolumeName,
  type PodmanSandboxOptions,
} from './codeSandboxIsolation.ts'

type CommandRunner = typeof runWorkspaceCommand

export type SandboxWorkspaceResult = {
  ok: boolean
  created: boolean
  volumeName: string
  steps: CodeSandboxStepResult[]
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
  if (!create.ok && isVolumeQuotaUnsupportedError(create.output)) {
    effectiveArgs = buildPodmanSandboxVolumeCreateArgsWithoutQuota(sandboxRoot)
    create = await runner('podman', effectiveArgs, sandboxRoot, 30_000)
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
  if (!create.ok) return { ok: false, created: false, volumeName, steps }

  const initArgs = buildPodmanSandboxWorkspaceInitArgs(lang, sandboxRoot, DEFAULT_SANDBOX_QUOTAS, options)
  const init = await runner('podman', initArgs, sandboxRoot, 60_000)
  steps.push(resultStep('Initialisation workspace quota WS7', 'podman', initArgs, init))
  if (!init.ok) return { ok: false, created: true, volumeName, steps }

  return { ok: true, created: true, volumeName, steps }
}

export async function cleanupSandboxWorkspaceVolume(
  sandboxRoot: string,
  runner: CommandRunner = runWorkspaceCommand,
): Promise<CodeSandboxStepResult> {
  const removeArgs = buildPodmanSandboxVolumeRemoveArgs(sandboxRoot)
  const result = await runner('podman', removeArgs, sandboxRoot, 30_000)
  return resultStep('Nettoyage volume workspace WS7', 'podman', removeArgs, result)
}
