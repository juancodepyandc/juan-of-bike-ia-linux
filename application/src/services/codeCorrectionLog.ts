import type { CodeFile } from './codeOrchestrator.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { CorrectionPass } from './codeAutoCorrection.ts'
import { prioritizeCompileErrors } from './codeMissingModuleCompletion.ts'

export function normalizedFilesChanged(currentFiles: CodeFile[], normalizedFiles?: CodeFile[]): boolean {
  if (!normalizedFiles || normalizedFiles.length === 0) return false
  return normalizedFiles.length !== currentFiles.length
    || normalizedFiles.some((file, index) =>
      file.name !== currentFiles[index]?.name || file.content !== currentFiles[index]?.content,
    )
}

export function collectFailingStepOutputs(sandboxResult: CodeSandboxResult): string[] {
  return sandboxResult.steps.filter((step) => !step.ok).map((step) => step.output)
}

export function truncateCorrectionErrors(sandboxResult: CodeSandboxResult): string[] {
  // Ordre causal: un module introuvable rend tout typage du fichier impossible.
  // Sans cela, la boucle traite des TS2339 pendant que des fichiers manquent.
  return collectFailingStepOutputs(sandboxResult).map(prioritizeCompileErrors).map((output) => output.length > 1500
    ? `${output.slice(0, 1000)}\n...[tronque: ${output.length} chars total]...\n${output.slice(-400)}`
    : output)
}

export function compactCorrectionLog(correctionLog: CorrectionPass[]): void {
  if (correctionLog.length <= 4) return

  for (let index = 0; index < correctionLog.length - 4; index++) {
    const old = correctionLog[index]
    if (old.errors.length > 1 || (old.errors[0] && old.errors[0].length > 200)) {
      correctionLog[index] = {
        ...old,
        errors: [`[passe archivee: ${old.errors.length} erreurs, score ${old.score}%]`],
      }
    }
  }
}
