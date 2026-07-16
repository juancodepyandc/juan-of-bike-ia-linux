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
}

export type PodmanSandboxOptions = {
  gpu?: boolean
}

export const DEFAULT_SANDBOX_QUOTAS: SandboxQuotaProfile = {
  memory: '2g',
  cpus: '2',
  pidsLimit: '256',
  fileSizeBlocks: '1048576',
  tmpfsSize: '256m',
}

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

  const info = await runner('podman', ['info', '--format', '{{.Host.Security.Rootless}} {{.Host.CgroupVersion}}'], cwd, 10_000).catch((error) => ({
    ok: false,
    exitCode: 1,
    output: error instanceof Error ? error.message : String(error),
    command: 'podman info',
  }))
  if (!info.ok) {
    return {
      ok: false,
      mode: 'unavailable',
      reason: `Podman ne fournit pas ses informations rootless/cgroup: ${info.output}`,
      rootless: false,
      cgroupVersion: null,
    }
  }

  const parsed = parsePodmanIsolationInfo(info.output)
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
      `quotas=memory:${DEFAULT_SANDBOX_QUOTAS.memory},cpus:${DEFAULT_SANDBOX_QUOTAS.cpus},pids:${DEFAULT_SANDBOX_QUOTAS.pidsLimit},fsize:${DEFAULT_SANDBOX_QUOTAS.fileSizeBlocks},tmpfs:${DEFAULT_SANDBOX_QUOTAS.tmpfsSize}`,
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

function containerExecutable(executable: string): string {
  return executable.replace(/\.cmd$/i, '').replace(/\.exe$/i, '')
}

export function buildPodmanSandboxArgs(
  command: ValidationCommand,
  lang: DetectedLanguage,
  sandboxRoot: string,
  quotas: SandboxQuotaProfile = DEFAULT_SANDBOX_QUOTAS,
  options: PodmanSandboxOptions = {},
): string[] {
  const networkPolicy = buildSandboxNetworkPolicy(command)
  return [
    'run',
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
    '--volume',
    `${sandboxRoot}:/workspace:rw,Z`,
    '--workdir',
    '/workspace',
    imageForLanguage(lang),
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
