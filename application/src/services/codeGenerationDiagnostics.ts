import type { CodeIntent } from './codeIntent.ts'
import type { ErrorCategory } from './codeAutoCorrection.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import { isLLMRefusal } from './codeLLMRefusal.ts'
import { detectNonCodePlanningNarrative } from './codeGeneratedFileParser.ts'
import { clipText } from './codePipelineRuntime.ts'

export function buildEmptyGenerationDiagnostic(content: string, intent: CodeIntent, outputRetryCount: number) {
  const trimmed = content.trim()

  if (!trimmed) {
    return [
      `Le modele n a retourne aucun contenu exploitable pour le projet ${intent.projectType}.`,
      `Tentatives de regeneration effectuees: ${outputRetryCount}.`,
    ].join(' ')
  }

  if (isLLMRefusal(trimmed)) {
    return [
      'Le modele a repondu par un refus ou une excuse au lieu de livrer des fichiers de code.',
      `Apercu: ${clipText(trimmed, 500)}`,
    ].join(' ')
  }

  const planningIssue = detectNonCodePlanningNarrative(trimmed)
  if (planningIssue) {
    return [
      'Le modele est reste bloque en mode analyse/preflight au lieu de livrer des fichiers executables.',
      planningIssue,
      `Apercu brut: ${clipText(trimmed, 700)}`,
    ].join(' ')
  }

  return [
    'Le modele a bien produit du texte, mais pas dans un format de fichiers parseable par Aurora.',
    'Le contrat de sortie a donc ete juge invalide.',
    `Apercu brut: ${clipText(trimmed, 700)}`,
  ].join(' ')
}

export function detectEnvironmentBlocker(
  sandboxResult: CodeSandboxResult,
  errorCategories: ErrorCategory[],
): string | null {
  if (sandboxResult.ok) return null

  if (errorCategories.includes('runtime_unavailable')) {
    const autoInstallFailure = sandboxResult.steps.find((step) => step.command.startsWith('auto-install:') && !step.ok)
    if (autoInstallFailure) {
      return `${autoInstallFailure.command.replace('auto-install:', '')} n a pas pu etre prepare automatiquement`
    }

    const missingCommand = sandboxResult.steps
      .filter((step) => !step.ok)
      .map((step) => step.output.match(/Failed to spawn command\s+([^\s:]+)/i)?.[1])
      .find(Boolean)

    if (missingCommand) {
      return `commande ${missingCommand} absente du poste local`
    }

    return 'runtime ou toolchain absente'
  }

  if (/reste indisponible apres preparation automatique/i.test(sandboxResult.summary)) {
    return sandboxResult.summary
  }

  return null
}
