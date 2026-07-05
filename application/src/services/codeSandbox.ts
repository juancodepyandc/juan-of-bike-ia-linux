import { fsMkdir, fsWriteText, getWorkspacePath, runWorkspaceCommand } from '../hooks/useTauri'

type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeSandboxStepResult = {
  label: string
  command: string
  ok: boolean
  output: string
}

export type CodeSandboxResult = {
  ok: boolean
  rootPath: string
  summary: string
  question: string | null
  steps: CodeSandboxStepResult[]
  detectedLanguage: string
  normalizedFiles?: CodeFile[]
}

type ValidationCommand = {
  label: string
  executable: string
  args: string[]
  timeoutMs?: number
  /** If true, failure is logged but does not abort the pipeline */
  optional?: boolean
}

// ---------------------------------------------------------------------------
// OS helpers
// ---------------------------------------------------------------------------

function isWindows(): boolean {
  return typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent)
}

function nodeExecutable(name: 'npm' | 'pnpm' | 'yarn' | 'bun') {
  if (isWindows()) {
    if (name === 'bun') return 'bun.exe'
    return `${name}.cmd`
  }
  return name
}

// ---------------------------------------------------------------------------
// Runtime availability + auto-install
// ---------------------------------------------------------------------------

/** Returns true if the given command is available on PATH. */
async function checkRuntimeAvailable(cmd: string, cwd: string): Promise<boolean> {
  const finder = isWindows() ? 'where' : 'which'
  const result = await runWorkspaceCommand(finder, [cmd], cwd, 10_000).catch(() => ({ ok: false, exitCode: 1, output: '', command: '' }))
  return result.ok
}

type AutoInstallSpec = {
  winget?: string
  apt?: string
  brew?: string
  npm?: string
  /** Fallback message when no auto-installer is available */
  message?: string
}

async function autoInstallRuntime(spec: AutoInstallSpec, cwd: string): Promise<{ ok: boolean; output: string }> {
  if (isWindows() && spec.winget) {
    const result = await runWorkspaceCommand('winget', ['install', '--silent', '--accept-source-agreements', '--accept-package-agreements', spec.winget], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  const os = typeof navigator !== 'undefined' ? navigator.userAgent : ''

  if (/macintosh|mac os x/i.test(os) && spec.brew) {
    const result = await runWorkspaceCommand('brew', ['install', spec.brew], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  if (/linux/i.test(os) && spec.apt) {
    const result = await runWorkspaceCommand('sudo', ['apt-get', 'install', '-y', spec.apt], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  if (spec.npm) {
    const npm = nodeExecutable('npm')
    const result = await runWorkspaceCommand(npm, ['install', '-g', ...spec.npm.split(' ')], cwd, 5 * 60_000)
    return { ok: result.ok, output: result.output }
  }

  return { ok: false, output: spec.message ?? 'Aucun installeur disponible pour ce runtime.' }
}

function isLocalExecutablePath(executable: string) {
  return executable.startsWith('./')
    || executable.startsWith('.\\')
    || executable.includes('/')
    || executable.includes('\\')
}

function normalizeExecutableName(executable: string) {
  return executable
    .trim()
    .replace(/\.cmd$/i, '')
    .replace(/\.bat$/i, '')
    .replace(/\.exe$/i, '')
    .toLowerCase()
}

function getExecutableRuntimeSpec(executable: string): { cmd: string; install: AutoInstallSpec } | null {
  if (isLocalExecutablePath(executable)) return null

  switch (normalizeExecutableName(executable)) {
    case 'node':
    case 'npm':
    case 'npx':
      return {
        cmd: isWindows() ? 'node.exe' : 'node',
        install: {
          winget: 'OpenJS.NodeJS.LTS',
          apt: 'nodejs npm',
          brew: 'node',
          message: 'Installez Node.js LTS pour executer npm, npx et les scripts JavaScript.',
        },
      }
    case 'pnpm':
      return {
        cmd: isWindows() ? 'pnpm.cmd' : 'pnpm',
        install: { npm: 'pnpm', message: 'PNPM est requis pour cette validation.' },
      }
    case 'yarn':
      return {
        cmd: isWindows() ? 'yarn.cmd' : 'yarn',
        install: { npm: 'yarn', message: 'Yarn est requis pour cette validation.' },
      }
    case 'bun':
      return {
        cmd: isWindows() ? 'bun.exe' : 'bun',
        install: {
          winget: 'Oven-sh.Bun',
          brew: 'bun',
          message: 'Installez Bun pour executer cette stack.',
        },
      }
    case 'python':
    case 'pip':
    case 'pytest':
      return {
        cmd: 'python',
        install: {
          winget: 'Python.Python.3.12',
          apt: 'python3 python3-venv python3-pip',
          brew: 'python',
          message: 'Python 3 avec venv et pip est requis pour cette validation.',
        },
      }
    case 'cargo':
    case 'rustc':
      return {
        cmd: 'cargo',
        install: {
          winget: 'Rustlang.Rust.MSVC',
          apt: 'cargo rustc',
          brew: 'rust',
          message: 'Rust et Cargo sont requis pour cette validation.',
        },
      }
    case 'go':
      return {
        cmd: 'go',
        install: {
          winget: 'GoLang.Go',
          apt: 'golang-go',
          brew: 'go',
          message: 'Go est requis pour cette validation.',
        },
      }
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function parseJsonSafely<T>(content: string) {
  try {
    return JSON.parse(stripFormattingArtifacts(content)) as T
  } catch {
    return null
  }
}

function stripFormattingArtifacts(content: string) {
  let current = content
    .replace(/^\uFEFF/, '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()

  for (let index = 0; index < 3; index += 1) {
    const next = current
      .replace(/^```[\w.-]*\s*\r?\n/, '')
      .replace(/\r?\n```$/, '')
      .trim()

    if (next === current) break
    current = next
  }

  return current
}

function normalizeStructuredFileContent(file: CodeFile) {
  const normalized = file.name.replace(/\\/g, '/').toLowerCase()
  const cleaned = stripFormattingArtifacts(file.content)

  if (normalized.endsWith('.json')) {
    const parsed = parseJsonSafely<Record<string, unknown>>(cleaned)
    if (parsed) {
      return `${JSON.stringify(parsed, null, 2)}\n`
    }
  }

  if (normalized.endsWith('.json') || normalized.endsWith('.toml') || normalized.endsWith('.yaml') || normalized.endsWith('.yml')) {
    return cleaned
  }

  return file.content
}

function normalizeSandboxFiles(files: CodeFile[]) {
  const notes: string[] = []
  const normalizedFiles = files.map((file) => {
    const nextContent = normalizeStructuredFileContent(file)
    if (nextContent !== file.content) {
      notes.push(`${file.name} nettoye automatiquement avant validation`)
    }
    return nextContent === file.content ? file : { ...file, content: nextContent }
  })

  const isolatedTypeScript = ensureIsolatedTypeScriptProject(normalizedFiles)
  notes.push(...isolatedTypeScript.notes)

  return { files: isolatedTypeScript.files, notes }
}

type NodePackageManifest = {
  name?: string
  version?: string
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
}

type NodeDependencySection = 'dependencies' | 'devDependencies' | 'optionalDependencies' | 'peerDependencies'

type RegistryTarget = {
  packageName: string
  requestedSpec: string
}

// MEMORY-SAFE: LRU-like cache with max entries to prevent unbounded growth
const NPM_VERSION_CACHE = new Map<string, string[]>()
const NPM_VERSION_CACHE_MAX = 50

function npmCacheSet(key: string, value: string[]) {
  if (NPM_VERSION_CACHE.size >= NPM_VERSION_CACHE_MAX) {
    // Remove oldest entry (first inserted)
    const firstKey = NPM_VERSION_CACHE.keys().next().value
    if (firstKey !== undefined) NPM_VERSION_CACHE.delete(firstKey)
  }
  NPM_VERSION_CACHE.set(key, value)
}

function upsertSandboxFile(files: CodeFile[], nextFile: CodeFile) {
  const normalizedTarget = nextFile.name.replace(/\\/g, '/').toLowerCase()
  const existingIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === normalizedTarget)
  if (existingIndex < 0) {
    return [...files, nextFile]
  }

  return files.map((file, index) => (index === existingIndex ? nextFile : file))
}

function hasTypeScriptSources(files: CodeFile[]) {
  return files.some((file) => /\.(mts|cts|ts|tsx)$/i.test(file.name))
}

function hasJavaScriptSources(files: CodeFile[]) {
  return files.some((file) => /\.(js|jsx|mjs|cjs)$/i.test(file.name))
}

function hasJsxSources(files: CodeFile[]) {
  return files.some((file) => /\.(tsx|jsx)$/i.test(file.name))
}

function hasHtmlEntry(files: CodeFile[]) {
  return files.some((file) => /\.(html|htm)$/i.test(file.name))
}

function normalizeFileLookupName(name: string) {
  return name.replace(/\\/g, '/').toLowerCase()
}

function buildSandboxTypeScriptConfig(files: CodeFile[], manifest: NodePackageManifest | null) {
  const normalizedNames = files.map((file) => normalizeFileLookupName(file.name))
  if (normalizedNames.includes('tsconfig.json')) {
    return null
  }

  const scripts = manifest?.scripts && typeof manifest.scripts === 'object'
    ? Object.values(manifest.scripts).filter((value): value is string => typeof value === 'string')
    : []
  const hasTypeScriptDependency = Boolean(
    manifest && (
      getDependencySpecFromManifest(manifest, 'typescript')
      || getDependencySpecFromManifest(manifest, 'ts-node')
      || getDependencySpecFromManifest(manifest, 'tsx')
    ),
  )
  const needsTypeScriptConfig = hasTypeScriptSources(files)
    || (hasTypeScriptDependency && hasJavaScriptSources(files))
    || scripts.some((script) => /\btsc\b|\bts-node\b|\btsx\b/i.test(script))

  if (!needsTypeScriptConfig) {
    return null
  }

  const hasReact = Boolean(
    manifest && (
      getDependencySpecFromManifest(manifest, 'react')
      || getDependencySpecFromManifest(manifest, 'preact')
      || getDependencySpecFromManifest(manifest, '@types/react')
    ),
  )
  const usesBrowserLibs = hasReact || hasJsxSources(files) || hasHtmlEntry(files)
  const include = [
    '**/*.ts',
    '**/*.tsx',
    '**/*.mts',
    '**/*.cts',
  ]

  if (hasJavaScriptSources(files)) {
    include.push('**/*.js', '**/*.jsx', '**/*.mjs', '**/*.cjs')
  }

  const compilerOptions: Record<string, unknown> = {
    target: 'ES2020',
    module: 'ESNext',
    moduleResolution: 'node',
    noEmit: true,
    skipLibCheck: true,
    strict: false,
    isolatedModules: true,
    esModuleInterop: true,
    allowSyntheticDefaultImports: true,
    resolveJsonModule: true,
    forceConsistentCasingInFileNames: true,
    typeRoots: ['./node_modules/@types'],
  }

  if (hasJavaScriptSources(files)) {
    compilerOptions.allowJs = true
    compilerOptions.checkJs = false
  }

  if (usesBrowserLibs) {
    compilerOptions.lib = ['ES2020', 'DOM', 'DOM.Iterable']
  } else {
    compilerOptions.lib = ['ES2020']
  }

  if (hasReact || hasJsxSources(files)) {
    compilerOptions.jsx = 'react-jsx'
  }

  return {
    name: 'tsconfig.json',
    language: 'json',
    content: `${JSON.stringify({
      compilerOptions,
      include,
      exclude: ['node_modules', 'dist', 'build', '.next', '.turbo', 'coverage', 'target', 'src-tauri'],
    }, null, 2)}\n`,
  } satisfies CodeFile
}

function ensureIsolatedTypeScriptProject(files: CodeFile[]) {
  const packageFile = findFile(files, 'package.json')
  const manifest = packageFile ? parseJsonSafely<NodePackageManifest>(packageFile.content) : null
  const tsconfig = buildSandboxTypeScriptConfig(files, manifest)
  if (!tsconfig) {
    return { files, notes: [] as string[] }
  }

  return {
    files: upsertSandboxFile(files, tsconfig),
    notes: [
      'tsconfig.json genere automatiquement pour isoler la validation TypeScript du sandbox et eviter les heritages du workspace parent',
    ],
  }
}

function isRemoteDependencySpec(spec: string) {
  const normalized = spec.trim().toLowerCase()
  return normalized === ''
    || normalized === '*'
    || normalized === 'latest'
    || normalized.startsWith('workspace:')
    || normalized.startsWith('file:')
    || normalized.startsWith('link:')
    || normalized.startsWith('git+')
    || normalized.startsWith('git://')
    || normalized.startsWith('github:')
    || normalized.startsWith('http://')
    || normalized.startsWith('https://')
    || normalized.startsWith('npm:')
}

function splitRegistryTarget(specifier: string): RegistryTarget | null {
  const cleaned = specifier.trim().replace(/[.'"]+$/g, '')
  const splitIndex = cleaned.lastIndexOf('@')
  if (splitIndex <= 0 || splitIndex >= cleaned.length - 1) {
    return null
  }

  return {
    packageName: cleaned.slice(0, splitIndex),
    requestedSpec: cleaned.slice(splitIndex + 1),
  }
}

function parseNpmTargetError(output: string): RegistryTarget | null {
  const match = output.match(/No matching version found for ([^\s]+)\.?/i)
  if (!match) {
    return null
  }
  return splitRegistryTarget(match[1])
}

function parseSemver(version: string) {
  const match = version.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?$/)
  if (!match) {
    return null
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    raw: version.trim(),
    prerelease: /-/.test(version.trim()),
  }
}

function compareSemver(left: string, right: string) {
  const a = parseSemver(left)
  const b = parseSemver(right)
  if (!a || !b) return left.localeCompare(right)
  if (a.major !== b.major) return a.major - b.major
  if (a.minor !== b.minor) return a.minor - b.minor
  if (a.patch !== b.patch) return a.patch - b.patch
  if (a.prerelease === b.prerelease) return 0
  return a.prerelease ? -1 : 1
}

function parseRequestedMajor(spec: string) {
  const match = spec.match(/(\d+)(?:\.\d+)?(?:\.\d+)?/)
  if (!match) {
    return null
  }
  return Number(match[1])
}

function getDependencySpecFromManifest(manifest: NodePackageManifest, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const value = manifest[section]
    if (value && typeof value === 'object' && dependencyName in value) {
      const spec = (value as Record<string, unknown>)[dependencyName]
      if (typeof spec === 'string') {
        return spec
      }
    }
  }
  return null
}

function inferPreferredMajor(
  dependencyName: string,
  requestedSpec: string,
  manifest: NodePackageManifest,
) {
  const requestedMajor = parseRequestedMajor(requestedSpec)
  if (requestedMajor !== null) {
    return requestedMajor
  }

  if (dependencyName === '@types/react') {
    return parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react') || '')
  }

  if (dependencyName === '@types/react-dom') {
    return parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react-dom') || '')
      ?? parseRequestedMajor(getDependencySpecFromManifest(manifest, 'react') || '')
  }

  return null
}

function choosePublishedVersion(
  versions: string[],
  dependencyName: string,
  requestedSpec: string,
  manifest: NodePackageManifest,
) {
  const parsedVersions = versions
    .map((version) => parseSemver(version))
    .filter((value): value is NonNullable<typeof value> => Boolean(value))
    .filter((value) => !value.prerelease)
    .sort((left, right) => compareSemver(left.raw, right.raw))

  if (parsedVersions.length === 0) {
    return null
  }

  const preferredMajor = inferPreferredMajor(dependencyName, requestedSpec, manifest)
  if (preferredMajor !== null) {
    const sameMajor = parsedVersions.filter((version) => version.major === preferredMajor)
    if (sameMajor.length > 0) {
      return sameMajor[sameMajor.length - 1].raw
    }
  }

  return parsedVersions[parsedVersions.length - 1].raw
}

function formatResolvedDependencySpec(originalSpec: string, resolvedVersion: string) {
  const trimmed = originalSpec.trim()
  if (trimmed.startsWith('^')) return `^${resolvedVersion}`
  if (trimmed.startsWith('~')) return `~${resolvedVersion}`
  if (/^[<>=|]/.test(trimmed)) return `^${resolvedVersion}`
  return resolvedVersion
}

async function fetchPublishedVersions(packageName: string, cwd: string) {
  const cacheKey = packageName.toLowerCase()
  const cached = NPM_VERSION_CACHE.get(cacheKey)
  if (cached) {
    return cached
  }

  const npm = nodeExecutable('npm')
  const result = await runWorkspaceCommand(npm, ['view', packageName, 'versions', '--json'], cwd, 120_000)
  if (!result.ok) {
    return []
  }

  const parsed = parseJsonSafely<unknown>(result.output)
  const versions = Array.isArray(parsed)
    ? parsed.filter((value): value is string => typeof value === 'string')
    : typeof parsed === 'string'
      ? [parsed]
      : []

  npmCacheSet(cacheKey, versions)
  return versions
}

function updateManifestDependency(
  manifest: NodePackageManifest,
  packageName: string,
  nextSpec: string,
) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const current = manifest[section]
    if (current && typeof current === 'object' && packageName in current) {
      ;(current as Record<string, string>)[packageName] = nextSpec
      return section
    }
  }
  return null
}

function replacePackageFile(files: CodeFile[], nextManifest: NodePackageManifest) {
  return files.map((file) => {
    if (file.name.replace(/\\/g, '/').toLowerCase() !== 'package.json') {
      return file
    }
    return {
      ...file,
      content: `${JSON.stringify(nextManifest, null, 2)}\n`,
    }
  })
}

async function repairNodeDependencyFromRegistry(
  files: CodeFile[],
  cwd: string,
  target: RegistryTarget,
) {
  if (isRemoteDependencySpec(target.requestedSpec)) {
    return null
  }

  const packageFile = findFile(files, 'package.json')
  if (!packageFile) {
    return null
  }

  const manifest = parseJsonSafely<NodePackageManifest>(packageFile.content)
  if (!manifest) {
    return null
  }

  const currentSpec = getDependencySpecFromManifest(manifest, target.packageName)
  if (!currentSpec || currentSpec.trim() !== target.requestedSpec.trim()) {
    return null
  }

  const versions = await fetchPublishedVersions(target.packageName, cwd)
  const resolvedVersion = choosePublishedVersion(versions, target.packageName, target.requestedSpec, manifest)
  if (!resolvedVersion) {
    return null
  }

  const nextSpec = formatResolvedDependencySpec(target.requestedSpec, resolvedVersion)
  if (nextSpec === currentSpec) {
    return null
  }

  const section = updateManifestDependency(manifest, target.packageName, nextSpec)
  if (!section) {
    return null
  }

  return {
    files: replacePackageFile(files, manifest),
    note: `${target.packageName} corrige automatiquement via le registre npm: ${currentSpec} -> ${nextSpec} (${section})`,
  }
}

async function runNodeInstallWithAutoRepair(
  command: ValidationCommand,
  files: CodeFile[],
  cwd: string,
) {
  const steps: CodeSandboxStepResult[] = []
  let workingFiles = files
  const maxAttempts = 4

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const result = await runWorkspaceCommand(command.executable, command.args, cwd, command.timeoutMs)
    steps.push({
      label: attempt === 1 ? command.label : `${command.label} (retry ${attempt})`,
      command: `${command.executable} ${command.args.join(' ')}`.trim(),
      ok: result.ok,
      output: result.output,
    })

    if (result.ok) {
      return { ok: true, files: workingFiles, steps }
    }

    const target = parseNpmTargetError(result.output)
    if (!target) {
      return { ok: false, files: workingFiles, steps }
    }

    const repaired = await repairNodeDependencyFromRegistry(workingFiles, cwd, target)
    if (!repaired) {
      return { ok: false, files: workingFiles, steps }
    }

    workingFiles = repaired.files
    await writeSandboxFiles(cwd, workingFiles)
    steps.push({
      label: `Correction registre npm (${target.packageName})`,
      command: `npm view ${target.packageName} versions --json`,
      ok: true,
      output: repaired.note,
    })
  }

  return { ok: false, files: workingFiles, steps }
}

function detectStructuredManifestIssue(files: CodeFile[]) {
  for (const file of files) {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (!normalized.endsWith('.json')) continue

    const parsed = parseJsonSafely<Record<string, unknown>>(file.content)
    if (!parsed) {
      return `${file.name} est invalide: JSON attendu sans backticks markdown ni texte parasite.`
    }

    if (normalized === 'package.json') {
      if (typeof parsed.name !== 'string' || parsed.name.trim().length === 0) {
        return 'package.json est invalide: le champ "name" est manquant ou vide.'
      }
    }
  }

  return null
}

function findFile(files: CodeFile[], name: string) {
  return files.find((file) => file.name.toLowerCase() === name.toLowerCase())
}

function hasExtension(files: CodeFile[], ext: string) {
  return files.some((file) => file.name.toLowerCase().endsWith(ext))
}

function hasPythonTests(files: CodeFile[]) {
  return files.some((file) => /(^tests\/|^test_|_test\.py$|^conftest\.py$)/i.test(file.name.replace(/\\/g, '/')))
}

function detectPackageManager(files: CodeFile[], packageJson: { packageManager?: string } | null) {
  const packageManager = packageJson?.packageManager?.split('@')[0]
  if (packageManager === 'pnpm' || findFile(files, 'pnpm-lock.yaml')) return 'pnpm'
  if (packageManager === 'yarn' || findFile(files, 'yarn.lock')) return 'yarn'
  if (packageManager === 'bun' || findFile(files, 'bun.lockb') || findFile(files, 'bun.lock')) return 'bun'
  return 'npm'
}

function sanitizeRelativePath(filePath: string) {
  return filePath.replace(/^[./\\]+/, '').replace(/\.\.(\/|\\)/g, '').replace(/\\/g, '/')
}

// ---------------------------------------------------------------------------
// Language-specific command builders
// ---------------------------------------------------------------------------

function buildNodeCommands(files: CodeFile[]): ValidationCommand[] {
  const packageFile = findFile(files, 'package.json')
  const packageJson = packageFile ? parseJsonSafely<{ packageManager?: string; scripts?: Record<string, string> }>(packageFile.content) : null
  const scripts = packageJson?.scripts || {}
  const manager = detectPackageManager(files, packageJson)
  const executable = nodeExecutable(manager)
  const commands: ValidationCommand[] = [
    { label: 'Installer les dependances', executable, args: ['install'], timeoutMs: 10 * 60_000 },
  ]

  for (const scriptName of ['build', 'test', 'lint']) {
    if (scripts[scriptName]) {
      commands.push({
        label: `Verifier ${scriptName}`,
        executable,
        args: manager === 'yarn' ? [scriptName] : ['run', scriptName],
        timeoutMs: 10 * 60_000,
      })
    }
  }

  return commands
}

function buildPythonCommands(files: CodeFile[]): ValidationCommand[] {
  const venvPython = isWindows() ? '.venv\\Scripts\\python.exe' : '.venv/bin/python'
  const commands: ValidationCommand[] = [
    { label: 'Creer le venv de sandbox', executable: 'python', args: ['-m', 'venv', '.venv'], timeoutMs: 3 * 60_000 },
  ]

  if (findFile(files, 'requirements.txt')) {
    commands.push({ label: 'Installer requirements', executable: venvPython, args: ['-m', 'pip', 'install', '-r', 'requirements.txt'], timeoutMs: 10 * 60_000 })
  } else if (findFile(files, 'pyproject.toml') || findFile(files, 'setup.py')) {
    commands.push({ label: 'Installer le projet', executable: venvPython, args: ['-m', 'pip', 'install', '-e', '.'], timeoutMs: 10 * 60_000 })
  }

  if (hasPythonTests(files)) {
    commands.push({ label: 'Installer pytest', executable: venvPython, args: ['-m', 'pip', 'install', 'pytest'], timeoutMs: 5 * 60_000 })
    commands.push({ label: 'Lancer pytest', executable: venvPython, args: ['-m', 'pytest'], timeoutMs: 10 * 60_000 })
  } else {
    commands.push({ label: 'Compiler le projet Python', executable: venvPython, args: ['-m', 'compileall', '.'], timeoutMs: 4 * 60_000 })
  }

  return commands
}

function buildRustCommands(): ValidationCommand[] {
  return [{ label: 'Verifier Cargo', executable: 'cargo', args: ['check'], timeoutMs: 10 * 60_000 }]
}

function buildGoCommands(): ValidationCommand[] {
  return [{ label: 'Lancer les tests Go', executable: 'go', args: ['test', './...'], timeoutMs: 10 * 60_000 }]
}

function buildJavaCommands(files: CodeFile[]): ValidationCommand[] {
  const hasMaven = !!findFile(files, 'pom.xml')
  const hasGradle = !!findFile(files, 'build.gradle') || !!findFile(files, 'build.gradle.kts')

  if (hasMaven) {
    return [{ label: 'Build Maven', executable: 'mvn', args: ['compile', '-q'], timeoutMs: 10 * 60_000 }]
  }
  if (hasGradle) {
    const gradle = isWindows() ? 'gradlew.bat' : './gradlew'
    return [{ label: 'Build Gradle', executable: gradle, args: ['build', '--quiet'], timeoutMs: 10 * 60_000 }]
  }

  // Plain .java files — find the main class name
  const mainFile = files.find((file) => file.name.endsWith('.java') && /public\s+static\s+void\s+main/.test(file.content))
  const mainClass = mainFile ? mainFile.name.replace(/\.java$/, '').replace(/.*[/\\]/, '') : 'Main'
  return [
    { label: 'Compiler Java', executable: 'javac', args: ['*.java'], timeoutMs: 5 * 60_000 },
    { label: 'Executer Java', executable: 'java', args: [mainClass], timeoutMs: 5 * 60_000 },
  ]
}

function buildCCommands(files: CodeFile[]): ValidationCommand[] {
  const hasMakefile = !!findFile(files, 'Makefile') || !!findFile(files, 'makefile')
  if (hasMakefile) {
    return [{ label: 'Build Make (C)', executable: 'make', args: [], timeoutMs: 5 * 60_000 }]
  }

  const outExe = isWindows() ? 'out.exe' : './out'
  const cFiles = files.filter((file) => file.name.endsWith('.c')).map((file) => file.name)

  return [
    { label: 'Compiler C (gcc)', executable: 'gcc', args: ['-o', isWindows() ? 'out.exe' : 'out', ...cFiles], timeoutMs: 5 * 60_000 },
    { label: 'Executer le binaire', executable: outExe, args: [], timeoutMs: 2 * 60_000 },
  ]
}

function buildCppCommands(files: CodeFile[]): ValidationCommand[] {
  const hasCmake = !!findFile(files, 'CMakeLists.txt')
  if (hasCmake) {
    return [
      { label: 'CMake configure', executable: 'cmake', args: ['-B', 'build', '-S', '.'], timeoutMs: 5 * 60_000 },
      { label: 'CMake build', executable: 'cmake', args: ['--build', 'build'], timeoutMs: 10 * 60_000 },
    ]
  }

  const outExe = isWindows() ? 'out.exe' : './out'
  const cppFiles = files.filter((file) => file.name.endsWith('.cpp') || file.name.endsWith('.cc')).map((file) => file.name)

  return [
    { label: 'Compiler C++ (g++)', executable: 'g++', args: ['-o', isWindows() ? 'out.exe' : 'out', ...cppFiles], timeoutMs: 5 * 60_000 },
    { label: 'Executer le binaire', executable: outExe, args: [], timeoutMs: 2 * 60_000 },
  ]
}

function buildBashCommands(files: CodeFile[]): ValidationCommand[] {
  const mainSh = files.find((file) => file.name.endsWith('.sh'))
  if (!mainSh) return []
  return [{ label: 'Executer le script Bash', executable: 'bash', args: [mainSh.name], timeoutMs: 5 * 60_000 }]
}

function buildRubyCommands(files: CodeFile[]): ValidationCommand[] {
  const commands: ValidationCommand[] = []
  if (findFile(files, 'Gemfile')) {
    commands.push({ label: 'Bundle install', executable: 'bundle', args: ['install'], timeoutMs: 10 * 60_000 })
  }
  const mainRb = files.find((file) => file.name === 'main.rb' || file.name.endsWith('.rb'))
  if (mainRb) {
    commands.push({ label: 'Executer Ruby', executable: 'ruby', args: [mainRb.name], timeoutMs: 5 * 60_000 })
  }
  return commands
}

function buildPhpCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((file) => file.name === 'index.php' || file.name === 'main.php' || file.name.endsWith('.php'))
  if (!main) return []
  return [{ label: 'Executer PHP', executable: 'php', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildTypeScriptStandaloneCommands(files: CodeFile[]): ValidationCommand[] {
  const npm = nodeExecutable('npm')
  const main = files.find((file) => file.name === 'main.ts' || file.name === 'index.ts' || file.name.endsWith('.ts'))
  if (!main) return []
  return [
    { label: 'Installer ts-node', executable: npm, args: ['install', '-g', 'ts-node', 'typescript'], timeoutMs: 5 * 60_000, optional: true },
    { label: 'Executer TypeScript', executable: 'npx', args: ['ts-node', main.name], timeoutMs: 5 * 60_000 },
  ]
}

function buildSqlCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((file) => file.name.endsWith('.sql'))
  if (!main) return []
  return [{ label: 'Valider SQL (sqlite3)', executable: 'sqlite3', args: [':memory:', `.read ${main.name}`], timeoutMs: 2 * 60_000 }]
}

function buildDartCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'pubspec.yaml')) {
    return [
      { label: 'Dart pub get', executable: 'dart', args: ['pub', 'get'], timeoutMs: 5 * 60_000 },
      { label: 'Executer Dart', executable: 'dart', args: ['run'], timeoutMs: 5 * 60_000 },
    ]
  }
  const main = files.find((file) => file.name.endsWith('.dart'))
  if (!main) return []
  return [{ label: 'Executer Dart', executable: 'dart', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildKotlinCommands(files: CodeFile[]): ValidationCommand[] {
  const kt = files.find((file) => file.name.endsWith('.kt'))
  if (!kt) return []
  return [
    { label: 'Compiler Kotlin', executable: 'kotlinc', args: [kt.name, '-include-runtime', '-d', 'out.jar'], timeoutMs: 10 * 60_000 },
    { label: 'Executer Kotlin', executable: 'java', args: ['-jar', 'out.jar'], timeoutMs: 5 * 60_000 },
  ]
}

function buildCSharpCommands(files: CodeFile[]): ValidationCommand[] {
  if (files.some((f) => f.name.endsWith('.csproj'))) {
    return [
      { label: 'Restaurer les dependances .NET', executable: 'dotnet', args: ['restore'], timeoutMs: 5 * 60_000 },
      { label: 'Build .NET', executable: 'dotnet', args: ['build', '--no-restore'], timeoutMs: 10 * 60_000 },
    ]
  }
  const main = files.find((f) => f.name.endsWith('.cs'))
  if (!main) return []
  return [{ label: 'Compiler C#', executable: 'dotnet-script', args: [main.name], timeoutMs: 5 * 60_000, optional: true }]
}

function buildSwiftCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'Package.swift')) {
    return [{ label: 'Build Swift Package', executable: 'swift', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.swift'))
  if (!main) return []
  return [{ label: 'Executer Swift', executable: 'swift', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildZigCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'build.zig')) {
    return [{ label: 'Build Zig', executable: 'zig', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.zig'))
  if (!main) return []
  return [{ label: 'Executer Zig', executable: 'zig', args: ['run', main.name], timeoutMs: 5 * 60_000 }]
}

function buildLuaCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => f.name.endsWith('.lua'))
  if (!main) return []
  return [{ label: 'Executer Lua', executable: 'lua', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildElixirCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'mix.exs')) {
    return [
      { label: 'Mix deps.get', executable: 'mix', args: ['deps.get'], timeoutMs: 5 * 60_000 },
      { label: 'Mix compile', executable: 'mix', args: ['compile'], timeoutMs: 10 * 60_000 },
    ]
  }
  const main = files.find((f) => f.name.endsWith('.exs') || f.name.endsWith('.ex'))
  if (!main) return []
  return [{ label: 'Executer Elixir', executable: 'elixir', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildHaskellCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'stack.yaml')) {
    return [{ label: 'Stack build', executable: 'stack', args: ['build'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.hs'))
  if (!main) return []
  return [
    { label: 'Compiler Haskell', executable: 'ghc', args: ['-o', 'out', main.name], timeoutMs: 10 * 60_000 },
    { label: 'Executer Haskell', executable: isWindows() ? 'out.exe' : './out', args: [], timeoutMs: 5 * 60_000 },
  ]
}

function buildScalaCommands(files: CodeFile[]): ValidationCommand[] {
  if (findFile(files, 'build.sbt')) {
    return [{ label: 'SBT compile', executable: 'sbt', args: ['compile'], timeoutMs: 10 * 60_000 }]
  }
  const main = files.find((f) => f.name.endsWith('.scala'))
  if (!main) return []
  return [{ label: 'Executer Scala', executable: 'scala', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildRCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => /\.[rR]$/.test(f.name))
  if (!main) return []
  return [{ label: 'Executer R', executable: 'Rscript', args: [main.name], timeoutMs: 5 * 60_000 }]
}

function buildPowerShellCommands(files: CodeFile[]): ValidationCommand[] {
  const main = files.find((f) => /\.(ps1|psm1)$/i.test(f.name))
  if (!main) return []
  // pwsh (PowerShell Core, cross-platform) is the modern default. On Windows
  // we fall back to powershell.exe (Windows PowerShell 5.1) if pwsh is absent.
  const exe = isWindows() ? 'pwsh' : 'pwsh'
  return [
    {
      label: 'Executer PowerShell',
      executable: exe,
      args: ['-NoProfile', '-NonInteractive', '-File', main.name],
      timeoutMs: 5 * 60_000,
    },
  ]
}

// ---------------------------------------------------------------------------
// Language detection + runtime specs
// ---------------------------------------------------------------------------

type DetectedLanguage =
  | 'node' | 'python' | 'rust' | 'go'
  | 'java' | 'c' | 'cpp' | 'bash' | 'ruby' | 'php'
  | 'typescript-standalone' | 'sql' | 'dart' | 'kotlin'
  | 'csharp' | 'swift' | 'zig' | 'lua' | 'elixir'
  | 'haskell' | 'scala' | 'r' | 'powershell'
  | 'unknown'

// ---------------------------------------------------------------------------
// Auto-generation de lancement.bat si le LLM ne l a pas inclus
// ---------------------------------------------------------------------------

function generateLaunchBat(files: CodeFile[], lang: DetectedLanguage): CodeFile | null {
  const hasLaunchBat = files.some((f) => /^(launch|lancement)\.bat$/i.test(f.name.replace(/.*[/\\]/, '')))
  if (hasLaunchBat) return null

  let script = ''
  switch (lang) {
    case 'node': {
      const manifest = findFile(files, 'package.json')
      let devScript = 'npm start'
      if (manifest) {
        try {
          const parsed = JSON.parse(manifest.content)
          if (parsed.scripts?.dev) devScript = 'npm run dev'
          else if (parsed.scripts?.start) devScript = 'npm start'
          else if (parsed.scripts?.serve) devScript = 'npm run serve'
          else if (parsed.main) devScript = `node ${parsed.main}`
        } catch { /* ignore parse error */ }
      }
      script = [
        '@echo off',
        'chcp 65001 >nul 2>&1',
        'echo === Installation des dependances ===',
        'call npm install',
        'if errorlevel 1 (',
        '  echo [ERREUR] npm install a echoue. Verifiez que Node.js est installe.',
        '  pause',
        '  exit /b 1',
        ')',
        'echo === Lancement du projet ===',
        `call ${devScript}`,
        'pause',
      ].join('\r\n')
      break
    }
    case 'python': {
      const mainPy = files.find((f) => /main\.py$/i.test(f.name)) || files.find((f) => /app\.py$/i.test(f.name))
      const entry = mainPy ? mainPy.name.replace(/\\/g, '/') : 'main.py'
      const hasRequirements = !!findFile(files, 'requirements.txt')
      script = [
        '@echo off',
        'chcp 65001 >nul 2>&1',
        ...(hasRequirements ? [
          'echo === Installation des dependances ===',
          'pip install -r requirements.txt',
        ] : []),
        'echo === Lancement du projet ===',
        `python ${entry}`,
        'pause',
      ].join('\r\n')
      break
    }
    case 'rust':
      script = '@echo off\r\nchcp 65001 >nul 2>&1\r\necho === Build et lancement ===\r\ncargo run\r\npause'
      break
    case 'go':
      script = '@echo off\r\nchcp 65001 >nul 2>&1\r\necho === Lancement ===\r\ngo run .\r\npause'
      break
    case 'java':
      script = '@echo off\r\nchcp 65001 >nul 2>&1\r\necho === Compilation et lancement ===\r\njavac *.java && java Main\r\npause'
      break
    case 'c':
      script = '@echo off\r\nchcp 65001 >nul 2>&1\r\necho === Compilation et lancement ===\r\ngcc -o out.exe *.c && out.exe\r\npause'
      break
    case 'cpp':
      script = '@echo off\r\nchcp 65001 >nul 2>&1\r\necho === Compilation et lancement ===\r\ng++ -o out.exe *.cpp && out.exe\r\npause'
      break
    case 'typescript-standalone':
      script = [
        '@echo off',
        'chcp 65001 >nul 2>&1',
        'echo === Installation de ts-node ===',
        'call npm install -g ts-node typescript',
        'echo === Lancement ===',
        'ts-node index.ts',
        'pause',
      ].join('\r\n')
      break
    default:
      return null
  }

  return { name: 'lancement.bat', language: 'batch', content: script }
}

function detectDominantLanguage(files: CodeFile[]): DetectedLanguage {
  if (findFile(files, 'package.json')) return 'node'
  if (findFile(files, 'pyproject.toml') || findFile(files, 'requirements.txt') || findFile(files, 'setup.py') || hasExtension(files, '.py')) return 'python'
  if (findFile(files, 'Cargo.toml')) return 'rust'
  if (findFile(files, 'go.mod')) return 'go'
  if (findFile(files, 'pom.xml') || findFile(files, 'build.gradle') || findFile(files, 'build.gradle.kts') || hasExtension(files, '.java')) return 'java'
  if (hasExtension(files, '.kt')) return 'kotlin'
  if (hasExtension(files, '.cpp') || hasExtension(files, '.cc') || findFile(files, 'CMakeLists.txt')) return 'cpp'
  if (hasExtension(files, '.c') && !hasExtension(files, '.cpp')) return 'c'
  if (hasExtension(files, '.sh')) return 'bash'
  if (findFile(files, 'Gemfile') || hasExtension(files, '.rb')) return 'ruby'
  if (hasExtension(files, '.php')) return 'php'
  if (hasExtension(files, '.dart') || findFile(files, 'pubspec.yaml')) return 'dart'
  if (hasExtension(files, '.sql')) return 'sql'
  if (hasExtension(files, '.cs') || findFile(files, 'Program.cs')) return 'csharp'
  if (hasExtension(files, '.swift')) return 'swift'
  if (hasExtension(files, '.zig') || findFile(files, 'build.zig')) return 'zig'
  if (hasExtension(files, '.lua')) return 'lua'
  if (hasExtension(files, '.ex') || hasExtension(files, '.exs') || findFile(files, 'mix.exs')) return 'elixir'
  if (hasExtension(files, '.hs') || findFile(files, 'stack.yaml')) return 'haskell'
  if (hasExtension(files, '.scala') || findFile(files, 'build.sbt')) return 'scala'
  if (hasExtension(files, '.r') || hasExtension(files, '.R')) return 'r'
  if (hasExtension(files, '.ps1') || hasExtension(files, '.psm1')) return 'powershell'
  // TypeScript standalone (no package.json — handled above via node)
  if (findFile(files, 'tsconfig.json') || hasExtension(files, '.ts')) return 'typescript-standalone'
  return 'unknown'
}

function getRuntimeSpec(lang: DetectedLanguage): { cmd: string; install: AutoInstallSpec } | null {
  switch (lang) {
    case 'node':
      return {
        cmd: isWindows() ? 'node.exe' : 'node',
        install: {
          winget: 'OpenJS.NodeJS.LTS',
          apt: 'nodejs npm',
          brew: 'node',
          message: 'Installez Node.js LTS pour executer cette stack.',
        },
      }
    case 'python':
      return {
        cmd: 'python',
        install: {
          winget: 'Python.Python.3.12',
          apt: 'python3 python3-venv python3-pip',
          brew: 'python',
          message: 'Python 3 avec venv et pip est requis pour cette validation.',
        },
      }
    case 'rust':
      return {
        cmd: 'cargo',
        install: {
          winget: 'Rustlang.Rust.MSVC',
          apt: 'cargo rustc',
          brew: 'rust',
          message: 'Rust et Cargo sont requis pour cette validation.',
        },
      }
    case 'go':
      return {
        cmd: 'go',
        install: {
          winget: 'GoLang.Go',
          apt: 'golang-go',
          brew: 'go',
          message: 'Go est requis pour cette validation.',
        },
      }
    case 'java':
    case 'kotlin':
      return {
        cmd: 'java',
        install: { winget: 'Microsoft.OpenJDK.21', apt: 'openjdk-21-jdk', brew: 'openjdk@21' },
      }
    case 'c':
    case 'cpp':
      return {
        cmd: isWindows() ? 'gcc' : 'g++',
        install: {
          winget: 'GnuWin32.GnuWin32',
          apt: 'build-essential',
          brew: 'gcc',
          message: 'Installez GCC/G++ ou Visual Studio Build Tools.',
        },
      }
    case 'bash':
      return {
        cmd: 'bash',
        install: { message: 'Bash est disponible nativement sur Linux/Mac. Sur Windows, activez WSL.' },
      }
    case 'ruby':
      return { cmd: 'ruby', install: { winget: 'RubyInstallerTeam.Ruby.3.3', apt: 'ruby', brew: 'ruby' } }
    case 'php':
      return { cmd: 'php', install: { winget: 'PHP.PHP', apt: 'php', brew: 'php' } }
    case 'dart':
      return { cmd: 'dart', install: { winget: 'Google.Dart', apt: 'dart', brew: 'dart' } }
    case 'sql':
      return { cmd: 'sqlite3', install: { winget: 'SQLite.SQLite', apt: 'sqlite3', brew: 'sqlite3' } }
    case 'typescript-standalone':
      return { cmd: 'npx', install: { npm: 'ts-node typescript' } }
    case 'csharp':
      return { cmd: 'dotnet', install: { winget: 'Microsoft.DotNet.SDK.8', apt: 'dotnet-sdk-8.0', brew: 'dotnet' } }
    case 'swift':
      return { cmd: 'swift', install: { apt: 'swift', brew: 'swift', message: 'Installez Swift depuis swift.org.' } }
    case 'zig':
      return { cmd: 'zig', install: { winget: 'zig.zig', apt: 'zig', brew: 'zig' } }
    case 'lua':
      return { cmd: 'lua', install: { winget: 'DEVCOM.Lua', apt: 'lua5.4', brew: 'lua' } }
    case 'elixir':
      return { cmd: 'elixir', install: { winget: 'ElixirLang.Elixir', apt: 'elixir', brew: 'elixir' } }
    case 'haskell':
      return { cmd: 'ghc', install: { apt: 'ghc', brew: 'ghc', message: 'Installez GHC via ghcup.haskell.org.' } }
    case 'scala':
      return { cmd: 'scala', install: { brew: 'scala', message: 'Installez Scala via sdkman ou coursier.' } }
    case 'r':
      return { cmd: 'Rscript', install: { winget: 'RProject.R', apt: 'r-base', brew: 'r' } }
    case 'powershell':
      return {
        cmd: 'pwsh',
        install: {
          winget: 'Microsoft.PowerShell',
          apt: 'powershell',
          brew: 'powershell',
          message: 'PowerShell 7+ (pwsh) requis. Sur Windows, Windows PowerShell 5.1 est natif mais pwsh est preferable.',
        },
      }
    default:
      return null
  }
}

function buildCommandsForLanguage(lang: DetectedLanguage, files: CodeFile[]): ValidationCommand[] {
  switch (lang) {
    case 'node': return buildNodeCommands(files)
    case 'python': return buildPythonCommands(files)
    case 'rust': return buildRustCommands()
    case 'go': return buildGoCommands()
    case 'java': return buildJavaCommands(files)
    case 'kotlin': return buildKotlinCommands(files)
    case 'c': return buildCCommands(files)
    case 'cpp': return buildCppCommands(files)
    case 'bash': return buildBashCommands(files)
    case 'ruby': return buildRubyCommands(files)
    case 'php': return buildPhpCommands(files)
    case 'dart': return buildDartCommands(files)
    case 'sql': return buildSqlCommands(files)
    case 'typescript-standalone': return buildTypeScriptStandaloneCommands(files)
    case 'csharp': return buildCSharpCommands(files)
    case 'swift': return buildSwiftCommands(files)
    case 'zig': return buildZigCommands(files)
    case 'lua': return buildLuaCommands(files)
    case 'elixir': return buildElixirCommands(files)
    case 'haskell': return buildHaskellCommands(files)
    case 'scala': return buildScalaCommands(files)
    case 'r': return buildRCommands(files)
    case 'powershell': return buildPowerShellCommands(files)
    default: return []
  }
}

// ---------------------------------------------------------------------------
// File writing
// ---------------------------------------------------------------------------

async function writeSandboxFiles(rootPath: string, files: CodeFile[]) {
  await fsMkdir(rootPath)

  // Collect all unique directories to create
  const dirs = new Set<string>()
  for (const file of files) {
    const relativePath = sanitizeRelativePath(file.name)
    const parts = relativePath.split('/')
    if (parts.length > 1) {
      // Build nested directory paths
      for (let depth = 1; depth < parts.length; depth++) {
        dirs.add(`${rootPath}/${parts.slice(0, depth).join('/')}`)
      }
    }
  }

  // Create subdirectories first (sorted so parents come before children)
  const sortedDirs = [...dirs].sort()
  for (const dir of sortedDirs) {
    await fsMkdir(dir)
  }

  // Write files
  for (const file of files) {
    const relativePath = sanitizeRelativePath(file.name)
    await fsWriteText(`${rootPath}/${relativePath}`, file.content)
  }
}

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

  // Auto-generation de lancement.bat si absent
  const launchBat = generateLaunchBat(workingFiles, lang)
  if (launchBat) {
    workingFiles = [...workingFiles, launchBat]
    steps.push({
      label: 'Auto-generation lancement.bat',
      command: 'internal:generate-launch-bat',
      ok: true,
      output: 'Fichier lancement.bat genere automatiquement pour lancement en un clic.',
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
