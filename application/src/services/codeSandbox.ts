import { fsWriteText, getWorkspacePath, runWorkspaceCommand } from '../hooks/useTauri.ts'
import type { CodeFile, CodeSandboxResult, CodeSandboxStepResult, DetectedLanguage } from './codeSandboxTypes.ts'
import { autoInstallRuntime, checkRuntimeAvailable, getExecutableRuntimeSpec } from './codeSandboxRuntime.ts'
import { detectStructuredManifestIssue, normalizeSandboxFiles, writeSandboxFiles } from './codeSandboxFiles.ts'
import { buildCommandsForLanguage, detectDominantLanguage, generateLaunchSh, getRuntimeSpec } from './codeSandboxCommands.ts'
import { runNodeInstallWithAutoRepair } from './codeSandboxRegistryRepair.ts'

export type { CodeFile, CodeSandboxResult, CodeSandboxStepResult } from './codeSandboxTypes.ts'

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

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
    sandboxRoot = `${workspacePath}/output/code-sandbox/${Date.now()}`

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
    const runtimeSpec = getRuntimeSpec(lang)

  // Ensure required runtime is available, auto-install if missing
  if (runtimeSpec) {
    const available = await checkRuntimeAvailable(runtimeSpec.cmd, sandboxRoot)
    if (!available) {
      setProgress?.(`Runtime ${runtimeSpec.cmd} introuvable — installation automatique...`)
      setPhase?.(`Installation automatique de ${runtimeSpec.cmd}...`, 89)
      const installResult = await autoInstallRuntime(runtimeSpec.install, sandboxRoot)
      steps.push({
        label: `Auto-install runtime (${runtimeSpec.cmd})`,
        command: `auto-install:${runtimeSpec.cmd}`,
        ok: installResult.ok,
        output: installResult.output,
      })
      const availableAfterInstall = installResult.ok && await checkRuntimeAvailable(runtimeSpec.cmd, sandboxRoot)
      if (!availableAfterInstall) {
        return {
          ok: false,
          rootPath: sandboxRoot,
          summary: `Le runtime ${runtimeSpec.cmd} reste indisponible apres preparation automatique. L environnement doit etre finalise avant de reprendre les corrections de code.`,
          question: null,
          steps,
          detectedLanguage: lang,
          normalizedFiles: workingFiles,
        } satisfies CodeSandboxResult
      }
      if (!installResult.ok) {
        return {
          ok: false,
          rootPath: sandboxRoot,
          summary: `Impossible d'installer le runtime ${runtimeSpec.cmd} automatiquement. ${runtimeSpec.install.message ?? ''}`,
          question: null,
          steps,
          detectedLanguage: lang,
          normalizedFiles: workingFiles,
        } satisfies CodeSandboxResult
      }
    }
  }

  const commands = buildCommandsForLanguage(lang, workingFiles)

  if (commands.length === 0) {
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

  for (let index = 0; index < commands.length; index += 1) {
    const command = commands[index]
    const progress = Math.min(96, 90 + Math.round(((index + 1) / commands.length) * 6))
    setProgress?.(`${command.label} dans le sandbox...`)
    setPhase?.(`${command.label} dans le sandbox...`, progress)

    if (lang === 'node' && /installer les dependances/i.test(command.label)) {
      const installRun = await runNodeInstallWithAutoRepair(command, workingFiles, sandboxRoot)
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

    const commandRuntime = getExecutableRuntimeSpec(command.executable)
    if (commandRuntime) {
      const commandAvailable = await checkRuntimeAvailable(commandRuntime.cmd, sandboxRoot)
      if (!commandAvailable) {
        setProgress?.(`Commande ${commandRuntime.cmd} introuvable - installation automatique...`)
        setPhase?.(`Preparation de ${commandRuntime.cmd} pour la validation...`, Math.min(95, progress))
        const installResult = await autoInstallRuntime(commandRuntime.install, sandboxRoot)
        steps.push({
          label: `Auto-install command (${commandRuntime.cmd})`,
          command: `auto-install:${commandRuntime.cmd}`,
          ok: installResult.ok,
          output: installResult.output,
        })
        const availableAfterInstall = installResult.ok && await checkRuntimeAvailable(commandRuntime.cmd, sandboxRoot)
        if (!availableAfterInstall) {
          return {
            ok: false,
            rootPath: sandboxRoot,
            summary: `La commande ${commandRuntime.cmd} reste indisponible apres preparation automatique. Le pipeline doit resoudre l environnement avant toute reparation de code.`,
            question: null,
            steps,
            detectedLanguage: lang,
            normalizedFiles: workingFiles,
          } satisfies CodeSandboxResult
        }
      }
    }

    const result = await runWorkspaceCommand(command.executable, command.args, sandboxRoot, command.timeoutMs)
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
  }
}
