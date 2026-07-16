import type { CodeFile } from './codeOrchestrator.ts'
import { normalizeProjectPath } from './codeProjectTree.ts'

export type CodeGenerationToolAction =
  | { kind: 'write_file'; path: string; content: string; language?: string }
  | { kind: 'read_file'; path: string }
  | { kind: 'apply_patch'; path: string; search: string; replace: string; all?: boolean }
  | { kind: 'run_command'; command: string; reason?: string }

export type CodeGenerationToolResult = {
  ok: boolean
  kind: CodeGenerationToolAction['kind']
  files: CodeFile[]
  path?: string
  content?: string
  output?: string
  error?: string
}

export type CodeGenerationToolRunner = (command: string, reason: string | undefined, files: CodeFile[]) => Promise<{
  ok: boolean
  output: string
}>

const BLOCKED_PROJECT_FILENAMES = new Set(['.env', '.npmrc', '.pypirc'])

function normalizeToolPath(path: string): { ok: true; path: string } | { ok: false; error: string } {
  const trimmed = path.trim()
  if (!trimmed) return { ok: false, error: 'path_empty' }
  if (trimmed.includes('\0')) return { ok: false, error: 'path_contains_nul' }
  if (trimmed.startsWith('/') || /^[a-zA-Z]:[\\/]/.test(trimmed)) return { ok: false, error: 'path_must_be_relative' }
  if (trimmed.split(/[\\/]+/).includes('..')) return { ok: false, error: 'path_must_stay_in_project' }

  const normalized = normalizeProjectPath(trimmed)
  if (!normalized || normalized.startsWith('recovered/')) return { ok: false, error: 'path_unsafe' }
  const basename = normalized.split('/').pop()?.toLowerCase() || ''
  if (BLOCKED_PROJECT_FILENAMES.has(basename)) return { ok: false, error: 'secret_file_blocked' }
  return { ok: true, path: normalized }
}

function inferLanguage(path: string, explicit?: string) {
  if (explicit?.trim()) return explicit.trim()
  const ext = path.split('.').pop()?.toLowerCase()
  if (!ext || ext === path) return 'text'
  if (ext === 'js' || ext === 'mjs' || ext === 'cjs') return 'javascript'
  if (ext === 'ts') return 'typescript'
  if (ext === 'py') return 'python'
  return ext
}

function replaceFile(files: CodeFile[], next: CodeFile) {
  const output: CodeFile[] = []
  let replaced = false
  for (const file of files) {
    if (file.name === next.name) {
      output.push(next)
      replaced = true
    } else {
      output.push(file)
    }
  }
  if (!replaced) output.push(next)
  return output.sort((a, b) => a.name.localeCompare(b.name))
}

function findFile(files: CodeFile[], path: string) {
  return files.find((file) => file.name === path) ?? null
}

export async function executeCodeGenerationTool(
  files: CodeFile[],
  action: CodeGenerationToolAction,
  runner?: CodeGenerationToolRunner,
): Promise<CodeGenerationToolResult> {
  if (action.kind === 'run_command') {
    if (!runner) {
      return { ok: false, kind: action.kind, files, error: 'run_command_requires_ws7_runner' }
    }
    const result = await runner(action.command, action.reason, files)
    return { ok: result.ok, kind: action.kind, files, output: result.output, error: result.ok ? undefined : result.output }
  }

  const normalized = normalizeToolPath(action.path)
  if (!normalized.ok) return { ok: false, kind: action.kind, files, error: normalized.error }
  const path = normalized.path

  if (action.kind === 'read_file') {
    const file = findFile(files, path)
    return file
      ? { ok: true, kind: action.kind, files, path, content: file.content }
      : { ok: false, kind: action.kind, files, path, error: 'file_not_found' }
  }

  if (action.kind === 'write_file') {
    const next = { name: path, language: inferLanguage(path, action.language), content: action.content }
    return { ok: true, kind: action.kind, files: replaceFile(files, next), path, content: next.content }
  }

  const file = findFile(files, path)
  if (!file) return { ok: false, kind: action.kind, files, path, error: 'file_not_found' }
  if (!action.search) return { ok: false, kind: action.kind, files, path, error: 'patch_search_empty' }
  if (!file.content.includes(action.search)) {
    return { ok: false, kind: action.kind, files, path, error: 'patch_search_not_found' }
  }

  const content = action.all
    ? file.content.split(action.search).join(action.replace)
    : file.content.replace(action.search, action.replace)
  const next = { ...file, content }
  return { ok: true, kind: action.kind, files: replaceFile(files, next), path, content }
}

export async function executeCodeGenerationToolSequence(
  files: CodeFile[],
  actions: CodeGenerationToolAction[],
  runner?: CodeGenerationToolRunner,
) {
  const results: CodeGenerationToolResult[] = []
  let current = files
  for (const action of actions) {
    const result = await executeCodeGenerationTool(current, action, runner)
    results.push(result)
    if (!result.ok) break
    current = result.files
  }
  return { files: current, results }
}
