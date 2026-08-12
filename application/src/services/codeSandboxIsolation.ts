import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeSandboxStepResult, DetectedLanguage, ValidationCommand } from './codeSandboxTypes.ts'
import { buildPodmanGpuArgs } from './codeSandboxGpu.ts'
import { buildSandboxNetworkPolicy, podmanEnvArgs } from './codeSandboxNetworkPolicy.ts'

export type SandboxIsolationStatus = {
  ok: boolean
  mode: 'podman-rootless' | 'unavailable'
  reason: string
  rootless: boolean
  cgroupVersion: string | null
}

export type SandboxQuotaProfile = {
  memory: string
  cpus: string
  pidsLimit: string
  fileSizeBlocks: string
  tmpfsSize: string
  workspaceSize: string
}

export type PodmanSandboxOptions = {
  gpu?: boolean
  /** Racine du dossier utilisateur, pour retrouver les chaines Kotlin/Swift. */
  homeDir?: string
}

export const DEFAULT_SANDBOX_QUOTAS: SandboxQuotaProfile = {
  memory: '2g',
  cpus: '2',
  pidsLimit: '256',
  fileSizeBlocks: '1048576',
  tmpfsSize: '256m',
  workspaceSize: '768m',
}

const CONTAINER_WORKSPACE_PATH = '/workspace'
const CONTAINER_INPUT_PATH = '/aurora-input'

import {
  imageOverrideForToolchain,
  toolchainMountForLanguage,
  toolchainPodmanArgs,
} from './codeSandboxToolchains.ts'

const LANGUAGE_IMAGES: Partial<Record<DetectedLanguage, string>> = {
  node: 'docker.io/library/node:22-bookworm-slim',
  'typescript-standalone': 'docker.io/library/node:22-bookworm-slim',
  python: 'docker.io/library/python:3.12-slim',
  rust: 'docker.io/library/rust:1-bookworm',
  go: 'docker.io/library/golang:1.23-bookworm',
  java: 'docker.io/library/eclipse-temurin:21',
  c: 'docker.io/library/gcc:14',
  cpp: 'docker.io/library/gcc:14',
}

type CommandRunner = typeof runWorkspaceCommand

export function parsePodmanIsolationInfo(output: string): Pick<SandboxIsolationStatus, 'rootless' | 'cgroupVersion'> {
  const [rootlessRaw, cgroupRaw] = output.trim().split(/\s+/)
  return {
    rootless: /^true$/i.test(rootlessRaw),
    cgroupVersion: cgroupRaw || null,
  }
}

/**
 * Repli sur `podman info --format json`.
 *
 * Le gabarit Go n a pas le meme nom de champ selon la version de Podman: 4.9.3
 * expose `.Host.CgroupsVersion` et refuse `.Host.CgroupVersion` avec une erreur
 * de template. Une isolation qui depend d un nom de champ instable finit
 * fail-closed en permanence sur un hote parfaitement capable — c est exactement
 * ce qui est arrive. Les cles JSON, elles, sont stables.
 */
export function parsePodmanIsolationJson(output: string): Pick<SandboxIsolationStatus, 'rootless' | 'cgroupVersion'> | null {
  try {
    const parsed = JSON.parse(output) as {
      host?: { security?: { rootless?: boolean }; cgroupVersion?: string }
    }
    const host = parsed?.host
    if (!host) return null
    return {
      rootless: host.security?.rootless === true,
      cgroupVersion: typeof host.cgroupVersion === 'string' ? host.cgroupVersion : null,
    }
  } catch {
    return null
  }
}

export async function detectPodmanIsolation(
  cwd: string,
  runner: CommandRunner = runWorkspaceCommand,
): Promise<SandboxIsolationStatus> {
  const version = await runner('podman', ['--version'], cwd, 10_000).catch((error) => ({
    ok: false,
    exitCode: 1,
    output: error instanceof Error ? error.message : String(error),
    command: 'podman --version',
  }))
  if (!version.ok) {
    return {
      ok: false,
      mode: 'unavailable',
      reason: 'Podman rootless est indisponible sur cet hote. Installez-le hors generation avant dexecuter du code LLM.',
      rootless: false,
      cgroupVersion: null,
    }
  }

  // `CgroupsVersion` (avec le s) est le nom accepte par Podman 4.x; l ancien
  // `CgroupVersion` faisait echouer le template, donc l isolation se declarait
  // indisponible sur un hote pourtant conforme.
  const info = await runner('podman', ['info', '--format', '{{.Host.Security.Rootless}} {{.Host.CgroupsVersion}}'], cwd, 10_000).catch((error) => ({
    ok: false,
    exitCode: 1,
    output: error instanceof Error ? error.message : String(error),
    command: 'podman info',
  }))

  let parsed = info.ok ? parsePodmanIsolationInfo(info.output) : null
  // Un gabarit refuse (nom de champ different selon la version) ne doit pas
  // condamner l isolation: on retombe sur le JSON, dont les cles sont stables.
  if (!parsed || !parsed.cgroupVersion) {
    const jsonInfo = await runner('podman', ['info', '--format', 'json'], cwd, 10_000).catch((error) => ({
      ok: false,
      exitCode: 1,
      output: error instanceof Error ? error.message : String(error),
      command: 'podman info --format json',
    }))
    if (jsonInfo.ok) parsed = parsePodmanIsolationJson(jsonInfo.output) ?? parsed
  }

  if (!parsed) {
    return {
      ok: false,
      mode: 'unavailable',
      reason: `Podman ne fournit pas ses informations rootless/cgroup: ${info.output}`,
      rootless: false,
      cgroupVersion: null,
    }
  }
  if (!parsed.rootless) {
    return {
      ok: false,
      mode: 'unavailable',
      reason: 'Podman est present mais pas en mode rootless.',
      ...parsed,
    }
  }
  if (parsed.cgroupVersion !== 'v2') {
    return {
      ok: false,
      mode: 'unavailable',
      reason: `Podman rootless exige cgroups v2 pour les quotas, detecte: ${parsed.cgroupVersion ?? 'inconnu'}.`,
      ...parsed,
    }
  }

  return {
    ok: true,
    mode: 'podman-rootless',
    reason: 'Podman rootless avec cgroups v2 disponible.',
    ...parsed,
  }
}

export function buildSandboxIsolationStep(status: SandboxIsolationStatus): CodeSandboxStepResult {
  return {
    label: 'Isolation sandbox WS7',
    command: 'internal:sandbox-isolation',
    ok: status.ok,
    output: [
      `mode=${status.mode}`,
      `rootless=${status.rootless ? 'oui' : 'non'}`,
      `cgroup=${status.cgroupVersion ?? 'inconnu'}`,
      status.reason,
      `quotas=memory:${DEFAULT_SANDBOX_QUOTAS.memory},cpus:${DEFAULT_SANDBOX_QUOTAS.cpus},pids:${DEFAULT_SANDBOX_QUOTAS.pidsLimit},fsize:${DEFAULT_SANDBOX_QUOTAS.fileSizeBlocks},tmpfs:${DEFAULT_SANDBOX_QUOTAS.tmpfsSize},workspace:${DEFAULT_SANDBOX_QUOTAS.workspaceSize}`,
      'egress=none sauf commandes de registre reconnues; host_loopback=false',
    ].join('\n'),
  }
}

function imageForLanguage(lang: DetectedLanguage): string {
  return LANGUAGE_IMAGES[lang] ?? 'docker.io/library/debian:bookworm-slim'
}

function safeContainerName(sandboxRoot: string): string {
  const suffix = sandboxRoot.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(-48)
  return `aurora-code-${suffix || Date.now()}`
}

export function sandboxWorkspaceVolumeName(sandboxRoot: string): string {
  const suffix = sandboxRoot.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(-48)
  return `aurora-code-ws-${suffix || Date.now()}`
}

function containerExecutable(executable: string): string {
  return executable.replace(/\.cmd$/i, '').replace(/\.exe$/i, '')
}

function commonPodmanRunArgs(
  sandboxRoot: string,
  networkPolicy: ReturnType<typeof buildSandboxNetworkPolicy>,
  quotas: SandboxQuotaProfile,
  options: PodmanSandboxOptions,
): string[] {
  return [
    '--rm',
    '--pull=never',
    '--name',
    safeContainerName(sandboxRoot),
    '--network',
    networkPolicy.podmanNetwork,
    ...podmanEnvArgs(networkPolicy),
    '--userns',
    'keep-id',
    '--security-opt',
    'no-new-privileges',
    ...buildPodmanGpuArgs(Boolean(options.gpu)),
    '--cap-drop',
    'ALL',
    '--pids-limit',
    quotas.pidsLimit,
    '--memory',
    quotas.memory,
    '--cpus',
    quotas.cpus,
    '--ulimit',
    `fsize=${quotas.fileSizeBlocks}:${quotas.fileSizeBlocks}`,
    '--read-only',
    '--tmpfs',
    `/tmp:rw,nosuid,nodev,size=${quotas.tmpfsSize}`,
    '--tmpfs',
    `/home/aurora:rw,nosuid,nodev,size=${quotas.tmpfsSize}`,
  ]
}

export function buildPodmanSandboxVolumeCreateArgs(
  sandboxRoot: string,
  quotas: SandboxQuotaProfile = DEFAULT_SANDBOX_QUOTAS,
): string[] {
  return [
    'volume',
    'create',
    '--ignore',
    '--label',
    'aurora.role=code-sandbox-workspace',
    '--opt',
    `o=size=${quotas.workspaceSize}`,
    sandboxWorkspaceVolumeName(sandboxRoot),
  ]
}

/**
 * Meme volume, sans l option de taille.
 *
 * `--opt o=size=...` exige le Project Quota du systeme de fichiers. Sur un ext4
 * sans `prjquota`, sur overlayfs ou sur btrfs par defaut, Podman refuse net:
 * « volume options size and inodes not supported. Filesystem does not support
 * Project Quota ». Abandonner a cet endroit revient a desactiver TOUTE
 * l isolation (reseau, lecture seule, PID, memoire, CPU) pour un seul quota
 * disque non applicable. On sait donc creer le volume sans lui, en le disant.
 */
export function buildPodmanSandboxVolumeCreateArgsWithoutQuota(sandboxRoot: string): string[] {
  return [
    'volume',
    'create',
    '--ignore',
    '--label',
    'aurora.role=code-sandbox-workspace',
    sandboxWorkspaceVolumeName(sandboxRoot),
  ]
}

/** Le systeme de fichiers refuse-t-il les quotas de volume ? */
export function isVolumeQuotaUnsupportedError(output: string): boolean {
  return /project quota|options size and inodes not supported/i.test(output || '')
}

export function buildPodmanSandboxVolumeRemoveArgs(sandboxRoot: string): string[] {
  return ['volume', 'rm', '-f', sandboxWorkspaceVolumeName(sandboxRoot)]
}

export function buildPodmanSandboxWorkspaceInitArgs(
  lang: DetectedLanguage,
  sandboxRoot: string,
  quotas: SandboxQuotaProfile = DEFAULT_SANDBOX_QUOTAS,
  options: PodmanSandboxOptions = {},
): string[] {
  const networkPolicy = buildSandboxNetworkPolicy({
    label: 'Initialiser workspace sandbox',
    executable: 'sh',
    args: ['-lc', 'cp'],
  })
  return [
    'run',
    ...commonPodmanRunArgs(sandboxRoot, networkPolicy, quotas, options),
    '--volume',
    `${sandboxRoot}:${CONTAINER_INPUT_PATH}:ro,Z`,
    '--volume',
    `${sandboxWorkspaceVolumeName(sandboxRoot)}:${CONTAINER_WORKSPACE_PATH}:rw,z`,
    '--workdir',
    CONTAINER_WORKSPACE_PATH,
    imageForLanguage(lang),
    'sh',
    '-lc',
    `find ${CONTAINER_WORKSPACE_PATH} -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && cp -a ${CONTAINER_INPUT_PATH}/. ${CONTAINER_WORKSPACE_PATH}/`,
  ]
}

export function buildPodmanSandboxArgs(
  command: ValidationCommand,
  lang: DetectedLanguage,
  sandboxRoot: string,
  quotas: SandboxQuotaProfile = DEFAULT_SANDBOX_QUOTAS,
  options: PodmanSandboxOptions = {},
): string[] {
  const networkPolicy = buildSandboxNetworkPolicy(command)
  // Kotlin et Swift n ont pas d image dediee: on monte en lecture seule la
  // chaine installee dans le dossier prive d Aurora et on l ajoute au PATH.
  const mount = toolchainMountForLanguage(lang, options.homeDir ?? '~')
  return [
    'run',
    ...commonPodmanRunArgs(sandboxRoot, networkPolicy, quotas, options),
    ...toolchainPodmanArgs(mount),
    '--volume',
    `${sandboxWorkspaceVolumeName(sandboxRoot)}:${CONTAINER_WORKSPACE_PATH}:rw,z`,
    '--workdir',
    CONTAINER_WORKSPACE_PATH,
    imageOverrideForToolchain(lang) ?? imageForLanguage(lang),
    containerExecutable(command.executable),
    ...command.args,
  ]
}

export function wrapCommandForPodman(
  command: ValidationCommand,
  lang: DetectedLanguage,
  sandboxRoot: string,
  options: PodmanSandboxOptions = {},
): ValidationCommand {
  return {
    ...command,
    executable: 'podman',
    args: buildPodmanSandboxArgs(command, lang, sandboxRoot, DEFAULT_SANDBOX_QUOTAS, options),
  }
}
