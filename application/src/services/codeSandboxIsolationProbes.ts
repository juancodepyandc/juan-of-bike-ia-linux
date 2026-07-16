import { fsRemoveDirAll, fsWriteText, runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeSandboxStepResult, ValidationCommand } from './codeSandboxTypes.ts'
import { wrapCommandForPodman } from './codeSandboxIsolation.ts'

export type SandboxIsolationProbeResult = {
  ok: boolean
  steps: CodeSandboxStepResult[]
}

type CommandRunner = typeof runWorkspaceCommand
type ProbeFs = {
  writeText: typeof fsWriteText
  removeDirAll: typeof fsRemoveDirAll
}

const PROBE_TIMEOUT_MS = 30_000
const DEFAULT_PROBE_FS: ProbeFs = {
  writeText: fsWriteText,
  removeDirAll: fsRemoveDirAll,
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function normalizedRoot(root: string): string {
  return root.replace(/\/+$/, '')
}

export function sandboxHostSentinelName(sandboxRoot: string): string {
  const suffix = normalizedRoot(sandboxRoot)
    .replace(/[^a-z0-9]+/gi, '_')
    .replace(/^_|_$/g, '')
    .slice(-48)
  return `AURORA_HOST_SENTINEL_${suffix || 'root'}`
}

export function sandboxHostSentinelPath(sandboxRoot: string): string {
  const root = normalizedRoot(sandboxRoot)
  const parent = root.replace(/\/[^/]+$/, '')
  return `${parent}/${sandboxHostSentinelName(root)}`
}

function probeCommand(label: string, script: string): ValidationCommand {
  return {
    label,
    executable: 'sh',
    args: ['-lc', script],
    timeoutMs: PROBE_TIMEOUT_MS,
  }
}

export function buildSandboxIsolationProbeCommands(sandboxRoot: string): ValidationCommand[] {
  const sentinelName = sandboxHostSentinelName(sandboxRoot)
  const hostReadProbe = probeCommand(
    'Preuve isolation host-read',
    [
      `test ! -e /workspace/../${sentinelName}`,
      'test ! -e /home/juan/.ssh',
      'test ! -e /root/.ssh',
    ].join(' && '),
  )

  const forkProbe = probeCommand(
    'Preuve quota pids',
    [
      'trap \'for p in $(jobs -p); do kill "$p" 2>/dev/null; done\' EXIT',
      'started=0',
      'last_pid=',
      [
        'while [ "$started" -lt 400 ]; do',
        '(sleep 30) 2>/dev/null & pid=$!',
        'if [ -z "$pid" ] || [ "$pid" = "$last_pid" ] || ! kill -0 "$pid" 2>/dev/null; then exit 0; fi',
        'last_pid=$pid',
        'started=$((started + 1))',
        'done',
      ].join(' '),
      'exit 2',
    ].join('; '),
  )

  const fileSizeProbe = probeCommand(
    'Preuve quota taille fichier',
    [
      'probe=/workspace/aurora-fsize-probe.bin',
      'trap "rm -f $probe" EXIT',
      'dd if=/dev/zero of=$probe bs=1M count=2048 status=none && exit 2',
      'exit 0',
    ].join('; '),
  )

  const workspaceQuotaProbe = probeCommand(
    'Preuve quota disque workspace',
    [
      'probe_dir=/workspace/aurora-disk-quota-probe',
      'trap "rm -rf $probe_dir" EXIT',
      'mkdir -p "$probe_dir"',
      'i=0',
      [
        'while [ "$i" -lt 384 ]; do',
        'i=$((i + 1))',
        'dd if=/dev/zero of="$probe_dir/chunk-$i.bin" bs=3M count=1 status=none || exit 0',
        'done',
      ].join(' '),
      'exit 2',
    ].join('; '),
  )

  return [hostReadProbe, forkProbe, fileSizeProbe, workspaceQuotaProbe]
    .map((command) => wrapCommandForPodman(command, 'unknown', sandboxRoot))
}

export async function runSandboxIsolationProbes(
  sandboxRoot: string,
  runner: CommandRunner = runWorkspaceCommand,
  fs: ProbeFs = DEFAULT_PROBE_FS,
): Promise<SandboxIsolationProbeResult> {
  const steps: CodeSandboxStepResult[] = []
  const sentinelPath = sandboxHostSentinelPath(sandboxRoot)

  try {
    await fs.writeText(sentinelPath, `Aurora host isolation sentinel for ${sandboxRoot}\n`)
  } catch (error) {
    return {
      ok: false,
      steps: [{
        label: 'Preuve isolation host-read sentinel',
        command: 'internal:sandbox-host-sentinel',
        ok: false,
        output: `Creation sentinelle impossible: ${errorMessage(error)}`,
      }],
    }
  }

  try {
    for (const command of buildSandboxIsolationProbeCommands(sandboxRoot)) {
      const result = await runner(command.executable, command.args, sandboxRoot, command.timeoutMs).catch((error) => ({
        ok: false,
        exitCode: 1,
        output: errorMessage(error),
        command: `${command.executable} ${command.args.join(' ')}`,
      }))
      steps.push({
        label: command.label,
        command: result.command || `${command.executable} ${command.args.join(' ')}`,
        ok: result.ok,
        output: result.output,
      })
      if (!result.ok) return { ok: false, steps }
    }
    return { ok: true, steps }
  } finally {
    await fs.removeDirAll(sentinelPath).catch(() => undefined)
  }
}
