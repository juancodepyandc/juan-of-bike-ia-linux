import { runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeFile, CodeSandboxStepResult } from './codeSandboxTypes.ts'

export type SandboxGpuRequirement = {
  required: boolean
  reasons: string[]
}

export type SandboxGpuStatus = {
  ok: boolean
  required: boolean
  mode: 'not-required' | 'podman-cdi' | 'unavailable'
  reason: string
  device: string | null
}

type CommandRunner = typeof runWorkspaceCommand

const NVIDIA_CDI_DEVICE = 'nvidia.com/gpu=all'

const GPU_SIGNALS: Array<[RegExp, string]> = [
  [/\b(cuda|nvidia|nvidia-smi|torch\.cuda|cupy|numba\.cuda|cudnn|nvcc)\b/i, 'CUDA/NVIDIA'],
  [/\b(webgpu|navigator\.gpu|gpucompute|wgpu)\b/i, 'WebGPU'],
  [/\b(webgl2?|WebGLRenderer|getContext\(["']webgl2?["']\)|@react-three\/fiber|three\.?js)\b/i, 'WebGL/Three.js'],
  [/\b(vulkan|opencl|compute shader|shader compute)\b/i, 'GPU compute'],
]

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function collectGpuReasons(label: string, text: string, reasons: Set<string>) {
  for (const [pattern, reason] of GPU_SIGNALS) {
    if (pattern.test(text)) reasons.add(`${label}:${reason}`)
  }
}

export function detectSandboxGpuRequirement(prompt: string, files: CodeFile[]): SandboxGpuRequirement {
  const reasons = new Set<string>()
  collectGpuReasons('prompt', prompt, reasons)
  for (const file of files) {
    collectGpuReasons(file.name, file.content.slice(0, 80_000), reasons)
  }
  return {
    required: reasons.size > 0,
    reasons: [...reasons].sort(),
  }
}

export function buildPodmanGpuArgs(enabled: boolean): string[] {
  return enabled
    ? ['--security-opt', 'label=disable', '--device', NVIDIA_CDI_DEVICE]
    : []
}

export async function detectPodmanGpuSupport(
  cwd: string,
  runner: CommandRunner = runWorkspaceCommand,
): Promise<SandboxGpuStatus> {
  const hostGpu = await runner('nvidia-smi', ['-L'], cwd, 10_000).catch((error) => ({
    ok: false,
    exitCode: 1,
    output: errorMessage(error),
    command: 'nvidia-smi -L',
  }))
  if (!hostGpu.ok) {
    return {
      ok: false,
      required: true,
      mode: 'unavailable',
      reason: `GPU NVIDIA hote indisponible ou pilote absent: ${hostGpu.output}`,
      device: null,
    }
  }

  const cdiList = await runner('nvidia-ctk', ['cdi', 'list'], cwd, 10_000).catch((error) => ({
    ok: false,
    exitCode: 1,
    output: errorMessage(error),
    command: 'nvidia-ctk cdi list',
  }))
  if (!cdiList.ok) {
    return {
      ok: false,
      required: true,
      mode: 'unavailable',
      reason: `nvidia-container-toolkit/CDI indisponible: ${cdiList.output}`,
      device: null,
    }
  }

  if (!new RegExp(`(^|\\s)${NVIDIA_CDI_DEVICE.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\s|$)`).test(cdiList.output)) {
    return {
      ok: false,
      required: true,
      mode: 'unavailable',
      reason: `Spec CDI NVIDIA absente pour ${NVIDIA_CDI_DEVICE}. Generez-la avec nvidia-ctk cdi generate hors generation.`,
      device: null,
    }
  }

  return {
    ok: true,
    required: true,
    mode: 'podman-cdi',
    reason: `GPU expose au conteneur via CDI ${NVIDIA_CDI_DEVICE}.`,
    device: NVIDIA_CDI_DEVICE,
  }
}

export function buildSandboxGpuStep(
  requirement: SandboxGpuRequirement,
  status: SandboxGpuStatus,
): CodeSandboxStepResult {
  return {
    label: 'GPU sandbox WS7',
    command: 'internal:sandbox-gpu',
    ok: status.ok,
    output: [
      `required=${requirement.required ? 'oui' : 'non'}`,
      `mode=${status.mode}`,
      `device=${status.device ?? 'aucun'}`,
      `reasons=${requirement.reasons.join(', ') || 'aucun'}`,
      status.reason,
    ].join('\n'),
  }
}

export function noSandboxGpuRequired(): SandboxGpuStatus {
  return {
    ok: true,
    required: false,
    mode: 'not-required',
    reason: 'Aucun signal GPU detecte dans le brief ou les fichiers.',
    device: null,
  }
}
