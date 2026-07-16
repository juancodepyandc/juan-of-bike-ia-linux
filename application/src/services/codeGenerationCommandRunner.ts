import { getWorkspacePath, runWorkspaceCommand } from '../hooks/useTauri.ts'
import { detectDominantLanguage } from './codeSandboxCommands.ts'
import { normalizeSandboxFiles, writeSandboxFiles } from './codeSandboxFiles.ts'
import {
  buildSandboxIsolationStep,
  detectPodmanIsolation,
  wrapCommandForPodman,
} from './codeSandboxIsolation.ts'
import { cleanupSandboxWorkspaceVolume, prepareSandboxWorkspaceVolume } from './codeSandboxWorkspace.ts'
import type { CodeFile, DetectedLanguage, ValidationCommand } from './codeSandboxTypes.ts'
import type { CodeGenerationToolRunner } from './codeGenerationTools.ts'

type WorkspaceCommandRunner = typeof runWorkspaceCommand

export type CodeGenerationSandboxRunnerOptions = {
  getWorkspacePathImpl?: typeof getWorkspacePath
  runCommandImpl?: WorkspaceCommandRunner
  writeFilesImpl?: typeof writeSandboxFiles
  detectIsolationImpl?: typeof detectPodmanIsolation
  prepareWorkspaceImpl?: typeof prepareSandboxWorkspaceVolume
  cleanupWorkspaceImpl?: typeof cleanupSandboxWorkspaceVolume
  now?: () => number
}

function commandLine(executable: string, args: string[]) {
  return [executable, ...args].join(' ')
}

function capOutput(output: string) {
  const trimmed = output.trim()
  if (trimmed.length <= 8_000) return trimmed
  return `${trimmed.slice(0, 4_000)}\n...[tronque: ${trimmed.length} chars]...\n${trimmed.slice(-3_000)}`
}

function buildShellValidationCommand(command: string, reason?: string): ValidationCommand {
  return {
    label: reason ? `run_command WS3: ${reason}` : 'run_command WS3',
    executable: 'sh',
    args: ['-lc', command],
    timeoutMs: 120_000,
  }
}

function formatStep(label: string, command: string, ok: boolean, output: string) {
  return [`## ${label}`, `$ ${command}`, ok ? 'OK' : 'ECHEC', capOutput(output)].join('\n')
}

export async function runCodeGenerationCommandInSandbox({
  command,
  reason,
  files,
  options = {},
}: {
  command: string
  reason?: string
  files: CodeFile[]
  options?: CodeGenerationSandboxRunnerOptions
}) {
  const trimmedCommand = command.trim()
  if (!trimmedCommand) return { ok: false, output: 'run_command_empty' }
  if (trimmedCommand.includes('\0')) return { ok: false, output: 'run_command_contains_nul' }
  if (trimmedCommand.length > 500) return { ok: false, output: 'run_command_too_long' }
  if (files.length === 0) return { ok: false, output: 'run_command_requires_project_files' }

  const getPath = options.getWorkspacePathImpl ?? getWorkspacePath
  const runCommand = options.runCommandImpl ?? runWorkspaceCommand
  const writeFiles = options.writeFilesImpl ?? writeSandboxFiles
  const detectIsolation = options.detectIsolationImpl ?? detectPodmanIsolation
  const prepareWorkspace = options.prepareWorkspaceImpl ?? prepareSandboxWorkspaceVolume
  const cleanupWorkspace = options.cleanupWorkspaceImpl ?? cleanupSandboxWorkspaceVolume
  const now = options.now ?? Date.now

  const normalized = normalizeSandboxFiles(files)
  const workingFiles = normalized.files
  const lang: DetectedLanguage = detectDominantLanguage(workingFiles)
  const workspacePath = await getPath()
  const sandboxRoot = `${workspacePath}/output/code-command-runner/${now()}`
  const output: string[] = []
  let workspaceVolumePrepared = false

  try {
    await writeFiles(sandboxRoot, workingFiles)
    if (normalized.notes.length > 0) {
      output.push(formatStep('Normalisation locale', 'internal:normalize-files', true, normalized.notes.join('\n')))
    }

    const isolation = await detectIsolation(sandboxRoot, runCommand)
    const isolationStep = buildSandboxIsolationStep(isolation)
    output.push(formatStep(isolationStep.label, isolationStep.command, isolationStep.ok, isolationStep.output))
    if (!isolation.ok) return { ok: false, output: output.join('\n\n') }

    const prepared = await prepareWorkspace(sandboxRoot, lang, {}, runCommand)
    workspaceVolumePrepared = prepared.created
    output.push(...prepared.steps.map((step) => formatStep(step.label, step.command, step.ok, step.output)))
    if (!prepared.ok) return { ok: false, output: output.join('\n\n') }

    const validationCommand = buildShellValidationCommand(trimmedCommand, reason)
    const runnable = wrapCommandForPodman(validationCommand, lang, sandboxRoot)
    const result = await runCommand(runnable.executable, runnable.args, sandboxRoot, validationCommand.timeoutMs)
    output.push(formatStep(validationCommand.label, result.command || commandLine(runnable.executable, runnable.args), result.ok, result.output))
    return { ok: result.ok, output: output.join('\n\n') }
  } catch (error) {
    output.push(formatStep('Exception run_command WS3', 'internal:run-command', false, error instanceof Error ? error.message : String(error)))
    return { ok: false, output: output.join('\n\n') }
  } finally {
    if (workspaceVolumePrepared) {
      const cleanup = await cleanupWorkspace(sandboxRoot, runCommand).catch((error) => ({
        label: 'Nettoyage volume workspace WS7',
        command: 'podman volume rm',
        ok: false,
        output: error instanceof Error ? error.message : String(error),
      }))
      output.push(formatStep(cleanup.label, cleanup.command, cleanup.ok, cleanup.output))
    }
  }
}

export function createCodeGenerationSandboxRunner(
  options: CodeGenerationSandboxRunnerOptions = {},
): CodeGenerationToolRunner {
  return (command, reason, files) => runCodeGenerationCommandInSandbox({
    command,
    reason,
    files,
    options,
  })
}
