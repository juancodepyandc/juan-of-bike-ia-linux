import type { CodeFile, DetectedLanguage, ValidationCommand } from './codeSandboxTypes.ts'
import { detectPackageManager, findFile, hasExtension, parseJsonSafely } from './codeSandboxFiles.ts'
import { isWindows, nodeExecutable } from './codeSandboxRuntime.ts'
import { auroraPythonExecutable } from './codePythonEnvironment.ts'

type PackageManifest = {
  scripts?: Record<string, string>
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  packageManager?: string
}

function hasTypeScript(files: CodeFile[]): boolean {
  return hasExtension(files, '.ts')
    || hasExtension(files, '.tsx')
    || !!findFile(files, 'tsconfig.json')
}

function hasPython(files: CodeFile[]): boolean {
  return hasExtension(files, '.py')
    || !!findFile(files, 'pyproject.toml')
    || !!findFile(files, 'requirements.txt')
}

function hasRust(files: CodeFile[]): boolean {
  return !!findFile(files, 'Cargo.toml') || hasExtension(files, '.rs')
}

function packageManifest(files: CodeFile[]): PackageManifest | null {
  const packageFile = findFile(files, 'package.json')
  return packageFile ? parseJsonSafely<PackageManifest>(packageFile.content) : null
}

function buildTypeScriptDiagnostic(files: CodeFile[]): ValidationCommand[] {
  if (!hasTypeScript(files)) return []
  const manifest = packageManifest(files)
  const scripts = manifest?.scripts ?? {}
  if (scripts.typecheck) {
    const manager = detectPackageManager(files, manifest)
    return [{
      label: 'Diagnostic tsc/typecheck',
      executable: nodeExecutable(manager),
      args: manager === 'yarn' ? ['typecheck'] : ['run', 'typecheck'],
      timeoutMs: 5 * 60_000,
      optional: true,
    }]
  }
  return [{
    label: 'Diagnostic tsc --noEmit',
    executable: isWindows() ? 'npx.cmd' : 'npx',
    args: ['tsc', '--noEmit', '--pretty', 'false'],
    timeoutMs: 5 * 60_000,
    optional: true,
  }]
}

function buildPythonDiagnostic(files: CodeFile[]): ValidationCommand[] {
  if (!hasPython(files)) return []
  return [{
    label: 'Diagnostic ruff',
    executable: auroraPythonExecutable(),
    args: ['-m', 'ruff', 'check', '.'],
    timeoutMs: 5 * 60_000,
    optional: true,
  }]
}

function buildRustDiagnostic(files: CodeFile[]): ValidationCommand[] {
  if (!hasRust(files)) return []
  return [{
    label: 'Diagnostic cargo clippy',
    executable: 'cargo',
    args: ['clippy', '--all-targets', '--all-features', '--', '-D', 'warnings'],
    timeoutMs: 10 * 60_000,
    optional: true,
  }]
}

export function buildToolchainDiagnosticCommands(lang: DetectedLanguage, files: CodeFile[]): ValidationCommand[] {
  if (lang === 'node' || lang === 'typescript-standalone') return buildTypeScriptDiagnostic(files)
  if (lang === 'python') return buildPythonDiagnostic(files)
  if (lang === 'rust') return buildRustDiagnostic(files)
  return [
    ...buildTypeScriptDiagnostic(files),
    ...buildPythonDiagnostic(files),
    ...buildRustDiagnostic(files),
  ]
}

function insertAfterLastSetup(commands: ValidationCommand[], diagnostics: ValidationCommand[]): ValidationCommand[] {
  let insertAt = 0
  for (let i = 0; i < commands.length; i += 1) {
    if (/installer|install|creer (?:le )?(?:venv|environnement)/i.test(commands[i].label)) {
      insertAt = i + 1
    }
  }
  return [...commands.slice(0, insertAt), ...diagnostics, ...commands.slice(insertAt)]
}

export function withToolchainDiagnostics(
  lang: DetectedLanguage,
  files: CodeFile[],
  commands: ValidationCommand[],
): ValidationCommand[] {
  const diagnostics = buildToolchainDiagnosticCommands(lang, files)
  if (diagnostics.length === 0) return commands
  if (lang === 'node' || lang === 'python' || lang === 'typescript-standalone') {
    return insertAfterLastSetup(commands, diagnostics)
  }
  return [...commands, ...diagnostics]
}
