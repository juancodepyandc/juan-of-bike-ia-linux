import type { CodeFile } from './codeOrchestrator.ts'
import { selectCodeProjectMemoryPromptContext } from './codeProjectMemory.ts'
import { fingerprintCodeFiles, loadOrBuildCodeProjectMemory } from './codeProjectMemoryPersistence.ts'

export type CodeIncrementalPatchScope = {
  fingerprint: string
  targetFiles: string[]
  protectedFiles: string[]
  reasonsByPath: Record<string, string[]>
}

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

export function buildCodeIncrementalPatchScope(args: {
  prompt: string
  files: CodeFile[]
  maxTargetFiles?: number
}): CodeIncrementalPatchScope {
  const memory = loadOrBuildCodeProjectMemory(args.files)
  const selected = selectCodeProjectMemoryPromptContext({
    memory,
    prompt: args.prompt,
    maxFiles: args.maxTargetFiles ?? 8,
  })
  const targetSet = new Set(selected.map((entry) => normalizePath(entry.file.path)))
  const reasonsByPath: Record<string, string[]> = {}
  for (const entry of selected) reasonsByPath[entry.file.path] = entry.reasons
  return {
    fingerprint: fingerprintCodeFiles(args.files),
    targetFiles: selected.map((entry) => entry.file.path),
    protectedFiles: args.files
      .map((file) => file.name)
      .filter((path) => !targetSet.has(normalizePath(path)))
      .sort((a, b) => a.localeCompare(b)),
    reasonsByPath,
  }
}

export function formatCodeIncrementalPatchScope(scope: CodeIncrementalPatchScope) {
  if (scope.targetFiles.length === 0) {
    return 'Aucun fichier cible fiable detecte. Lis le contexte avant de patcher et evite toute reecriture globale.'
  }
  const targets = scope.targetFiles.map((path) => {
    const reasons = scope.reasonsByPath[path]?.join(',') || 'score'
    return `- ${path} (${reasons})`
  })
  const protectedPreview = scope.protectedFiles.slice(0, 20).map((path) => `- ${path}`)
  return [
    `Fingerprint index: ${scope.fingerprint}`,
    'Fichiers cibles autorises pour la modification:',
    ...targets,
    '',
    'Fichiers proteges: ne pas modifier sauf necessite explicitement justifiee par la demande:',
    ...protectedPreview,
    scope.protectedFiles.length > protectedPreview.length
      ? `- ... ${scope.protectedFiles.length - protectedPreview.length} autre(s) fichier(s) protege(s)`
      : '',
  ].filter(Boolean).join('\n')
}

export function assertCodePatchNonRegression(args: {
  before: CodeFile[]
  after: CodeFile[]
  scope: CodeIncrementalPatchScope
}) {
  const afterByPath = new Map(args.after.map((file) => [normalizePath(file.name), file]))
  const errors: string[] = []
  for (const path of args.scope.protectedFiles) {
    const before = args.before.find((file) => normalizePath(file.name) === normalizePath(path))
    const after = afterByPath.get(normalizePath(path))
    if (!before) continue
    if (!after) {
      errors.push(`protected_file_removed:${path}`)
    } else if (after.content !== before.content || after.language !== before.language) {
      errors.push(`protected_file_modified:${path}`)
    }
  }
  return { ok: errors.length === 0, errors }
}
