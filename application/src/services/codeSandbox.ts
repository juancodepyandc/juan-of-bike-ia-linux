import { fsWriteText, getWorkspacePath, runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeFile, CodeSandboxResult, CodeSandboxStepResult, DetectedLanguage } from './codeSandboxTypes.ts'
import { detectStructuredManifestIssue, normalizeSandboxFiles, writeSandboxFiles } from './codeSandboxFiles.ts'
import { buildCommandsForLanguage, detectDominantLanguage, generateLaunchSh } from './codeSandboxCommands.ts'
import { runNodeInstallWithAutoRepair } from './codeSandboxRegistryRepair.ts'
import { withToolchainDiagnostics } from './codeToolchainDiagnostics.ts'
import { buildAcceptanceCriteriaStep } from './codeAcceptanceCriteria.ts'
import { buildSandboxIsolationStep, detectPodmanIsolation, wrapCommandForPodman } from './codeSandboxIsolation.ts'
import { buildSandboxGcStep, collectCodeSandboxGarbage } from './codeSandboxGc.ts'
import { runSandboxIsolationProbes } from './codeSandboxIsolationProbes.ts'
import {
  buildSandboxGpuStep,
  detectPodmanGpuSupport,
  detectSandboxGpuRequirement,
  noSandboxGpuRequired,
} from './codeSandboxGpu.ts'
import { cleanupSandboxWorkspaceVolume, prepareSandboxWorkspaceVolume } from './codeSandboxWorkspace.ts'

export type { CodeFile, CodeSandboxResult, CodeSandboxStepResult } from './codeSandboxTypes.ts'

function acceptanceFailureResult(
  sandboxRoot: string,
  steps: CodeSandboxStepResult[],
  lang: DetectedLanguage,
  workingFiles: CodeFile[],
): CodeSandboxResult {
  return {
    ok: false,
    rootPath: sandboxRoot,
    summary: 'Les tests d acceptation derives du brief ont echoue.',
    question: null,
    steps,
    detectedLanguage: lang,
    normalizedFiles: workingFiles,
  }
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/** Dossier utilisateur cote hote: sert a monter les chaines Kotlin/Swift. */
function sandboxHomeDir(): string {
  const proc = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process
  return proc?.env?.HOME || proc?.env?.USERPROFILE || '~'
}

export async function runCodeSandboxValidation({
  files,
  prompt,
  setPhase,
  setProgress,
}: {
  files: CodeFile[]
  prompt: string
  setPhase?: (detail: string, progress: number) => void
  setProgress?: (detail: string) => void
}) {
  let sandboxRoot = 'sandbox-unresolved'
  let workspaceVolumePrepared = false
  const steps: CodeSandboxStepResult[] = []
  const normalizedSandbox = normalizeSandboxFiles(files)
  let workingFiles = normalizedSandbox.files
  let lang: DetectedLanguage = detectDominantLanguage(workingFiles)

  // Auto-generation d'un launcher Linux si absent
  const launchScript = generateLaunchSh(workingFiles, lang)
  if (launchScript) {
    workingFiles = [...workingFiles, launchScript]
    steps.push({
      label: `Auto-generation ${launchScript.name}`,
      command: 'internal:generate-launch-script',
      ok: true,
      output: `Fichier ${launchScript.name} genere automatiquement pour lancement local.`,
    })
  }

  try {
    const workspacePath = await getWorkspacePath()
    const sandboxBasePath = `${workspacePath}/output/code-sandbox`
    try {
      const gcResult = await collectCodeSandboxGarbage(sandboxBasePath)
      if (gcResult.removed.length > 0) {
        steps.push(buildSandboxGcStep(gcResult))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      steps.push({
        label: 'GC sandboxes WS7',
        command: 'internal:sandbox-gc',
        ok: true,
        output: `GC non bloquant indisponible: ${message}`,
      })
    }

    sandboxRoot = `${sandboxBasePath}/${Date.now()}`

    setProgress?.('Creation du bac de validation isole...')
    setPhase?.('Creation du bac de validation isole...', 88)
    await writeSandboxFiles(sandboxRoot, workingFiles)
    await fsWriteText(`${sandboxRoot}/AURORA_PROMPT.txt`, prompt)

    if (normalizedSandbox.notes.length > 0) {
      steps.push({
        label: 'Normalisation locale',
        command: 'internal:normalize-files',
        ok: true,
        output: normalizedSandbox.notes.join('\n'),
      })
    }

    const manifestIssue = detectStructuredManifestIssue(workingFiles)
    if (manifestIssue) {
      steps.push({
        label: 'Validation des manifests',
        command: 'internal:manifest-validation',
        ok: false,
        output: manifestIssue,
      })
      return {
        ok: false,
        rootPath: sandboxRoot,
        summary: manifestIssue,
        question: null,
        steps,
        detectedLanguage: lang,
        normalizedFiles: workingFiles,
      } satisfies CodeSandboxResult
    }

    lang = detectDominantLanguage(workingFiles)
    const commands = withToolchainDiagnostics(lang, workingFiles, buildCommandsForLanguage(lang, workingFiles))

    if (commands.length === 0) {
      const acceptanceStep = buildAcceptanceCriteriaStep(prompt, workingFiles)
      steps.push(acceptanceStep)
      if (!acceptanceStep.ok) return acceptanceFailureResult(sandboxRoot, steps, lang, workingFiles)

      return {
        ok: true,
        rootPath: sandboxRoot,
        summary: 'Livraison structurelle prete. Aucun plan de validation automatique n etait applicable pour cette stack.',
        question: 'La livraison est prete dans le sandbox. Veux-tu maintenant l exporter vers un projet cible ou repartir sur une nouvelle iteration ?',
        steps,
        detectedLanguage: lang,
        normalizedFiles: workingFiles,
      } satisfies CodeSandboxResult
    }

    const isolationStatus = await detectPodmanIsolation(sandboxRoot)
    const isolationStep = buildSandboxIsolationStep(isolationStatus)
    steps.push(isolationStep)
    if (!isolationStatus.ok) {
      return {
        ok: false,
        rootPath: sandboxRoot,
        summary: `Validation conteneurisee WS7 indisponible: ${isolationStatus.reason}`,
        question: null,
        steps,
        detectedLanguage: lang,
        normalizedFiles: workingFiles,
      } satisfies CodeSandboxResult
    }

    const workspaceVolume = await prepareSandboxWorkspaceVolume(sandboxRoot, lang)
    steps.push(...workspaceVolume.steps)
    workspaceVolumePrepared = workspaceVolume.created
    if (!workspaceVolume.ok) {
      return {
        ok: false,
        rootPath: sandboxRoot,
        summary: `Sandbox WS7 indisponible (${workspaceVolume.failedStage ?? 'preparation'}): ${workspaceVolume.reason ?? 'cause inconnue'}.`,
        question: null,
        steps,
        detectedLanguage: lang,
        normalizedFiles: workingFiles,
      } satisfies CodeSandboxResult
    }

    // Les preuves tournent dans l image QUI VA EXECUTER LE CODE. Construites
    // avec `unknown`, elles retombaient sur une image debian jamais provisionnee
    // par Aurora: echec systematique, sur chaque run, avec une sortie vide.
    const isolationProbes = await runSandboxIsolationProbes(sandboxRoot, lang)
    steps.push(...isolationProbes.steps)
    if (!isolationProbes.ok) {
      return {
        ok: false,
        rootPath: sandboxRoot,
        summary: 'Les preuves d isolation WS7 ont echoue.',
        question: null,
        steps,
        detectedLanguage: lang,
        normalizedFiles: workingFiles,
      } satisfies CodeSandboxResult
    }

    const gpuRequirement = detectSandboxGpuRequirement(prompt, workingFiles)
    const gpuStatus = gpuRequirement.required
      ? await detectPodmanGpuSupport(sandboxRoot)
      : noSandboxGpuRequired()
    if (gpuRequirement.required) {
      steps.push(buildSandboxGpuStep(gpuRequirement, gpuStatus))
      if (!gpuStatus.ok) {
        return {
          ok: false,
          rootPath: sandboxRoot,
          summary: `Validation GPU WS7 indisponible: ${gpuStatus.reason}`,
          question: null,
          steps,
          detectedLanguage: lang,
          normalizedFiles: workingFiles,
        } satisfies CodeSandboxResult
      }
    }

    for (let index = 0; index < commands.length; index += 1) {
      const command = commands[index]
      const runnableCommand = wrapCommandForPodman(command, lang, sandboxRoot, { gpu: gpuStatus.mode === 'podman-cdi', homeDir: sandboxHomeDir() })
      const progress = Math.min(96, 90 + Math.round(((index + 1) / commands.length) * 6))
      setProgress?.(`${command.label} dans le sandbox...`)
      setPhase?.(`${command.label} dans le sandbox...`, progress)

      if (lang === 'node' && /installer les dependances/i.test(command.label)) {
        const installRun = await runNodeInstallWithAutoRepair(runnableCommand, workingFiles, sandboxRoot, {
          buildRegistryLookupCommand: (packageName) => wrapCommandForPodman({
            label: `Resolution registre npm ${packageName}`,
            executable: 'npm',
            args: ['view', packageName, 'versions', '--json'],
            timeoutMs: 120_000,
          }, lang, sandboxRoot, { gpu: gpuStatus.mode === 'podman-cdi', homeDir: sandboxHomeDir() }),
          afterWrite: async () => {
            const sync = await prepareSandboxWorkspaceVolume(sandboxRoot, lang, { gpu: gpuStatus.mode === 'podman-cdi', homeDir: sandboxHomeDir() })
            if (!sync.ok) {
              throw new Error('Resynchronisation du workspace quota WS7 impossible apres correction npm.')
            }
            return sync.steps
          },
        })
        workingFiles = installRun.files
        steps.push(...installRun.steps)

        if (!installRun.ok) {
          return {
            ok: false,
            rootPath: sandboxRoot,
            summary: `${command.label} a echoue dans le sandbox.`,
            question: null,
            steps,
            detectedLanguage: lang,
            normalizedFiles: workingFiles,
          } satisfies CodeSandboxResult
        }

        continue
      }

      const result = await runWorkspaceCommand(runnableCommand.executable, runnableCommand.args, sandboxRoot, command.timeoutMs)
      // MEMORY-SAFE: Truncate step output to prevent accumulating megabytes of logs in RAM
      const rawOutput = result.output.trim()
      const cappedOutput = rawOutput.length > 8000 ? `${rawOutput.slice(0, 4000)}\n...[tronque: ${rawOutput.length} chars]...\n${rawOutput.slice(-3000)}` : rawOutput
      steps.push({
        label: command.label,
        command: result.command,
        ok: result.ok,
        output: cappedOutput,
      })

      if (!result.ok && !command.optional) {
        const trimmedOutput = result.output.trim()
        const environmentFailure = /Failed to spawn command|program not found|command not found|is not recognized as an internal or external command/i.test(trimmedOutput)
        return {
          ok: false,
          rootPath: sandboxRoot,
          summary: environmentFailure
            ? `${command.label} a echoue dans le sandbox. Echec d environnement detecte autour de ${command.executable}.`
            : `${command.label} a echoue dans le sandbox.`,
          question: null,
          steps,
          detectedLanguage: lang,
          normalizedFiles: workingFiles,
        } satisfies CodeSandboxResult
      }
    }

    const acceptanceStep = buildAcceptanceCriteriaStep(prompt, workingFiles)
    steps.push(acceptanceStep)
    if (!acceptanceStep.ok) return acceptanceFailureResult(sandboxRoot, steps, lang, workingFiles)

    return {
      ok: true,
      rootPath: sandboxRoot,
      summary: 'Le livrable a passe la validation isolee du sandbox.',
      question: 'La simulation isolee a reussi. Veux-tu maintenant exporter ces fichiers vers un projet cible ou repartir sur une autre iteration ?',
      steps,
      detectedLanguage: lang,
      normalizedFiles: workingFiles,
    } satisfies CodeSandboxResult
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    steps.push({
      label: 'Exception sandbox',
      command: 'internal:sandbox',
      ok: false,
      output: message,
    })

    return {
      ok: false,
      rootPath: sandboxRoot,
      summary: `Validation sandbox interrompue: ${message}`,
      question: null,
      steps,
      detectedLanguage: lang,
      normalizedFiles: workingFiles,
    } satisfies CodeSandboxResult
  } finally {
    if (workspaceVolumePrepared) {
      const cleanup = await cleanupSandboxWorkspaceVolume(sandboxRoot).catch((error) => ({
        label: 'Nettoyage volume workspace WS7',
        command: 'podman volume rm',
        ok: false,
        output: error instanceof Error ? error.message : String(error),
      }))
      steps.push(cleanup)
    }
  }
}
