import { fsMkdir, fsWriteText } from '../hooks/useTauri.ts'
import type { CodeFile } from './codeSandboxTypes.ts'

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

export function parseJsonSafely<T>(content: string) {
  try {
    return JSON.parse(stripFormattingArtifacts(content)) as T
  } catch {
    return null
  }
}

export function stripFormattingArtifacts(content: string) {
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

export function normalizeSandboxFiles(files: CodeFile[]) {
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

export type NodePackageManifest = {
  name?: string
  version?: string
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
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

export function getDependencySpecFromManifest(manifest: NodePackageManifest, dependencyName: string) {
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

export function detectStructuredManifestIssue(files: CodeFile[]) {
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

export function findFile(files: CodeFile[], name: string) {
  return files.find((file) => file.name.toLowerCase() === name.toLowerCase())
}

export function hasExtension(files: CodeFile[], ext: string) {
  return files.some((file) => file.name.toLowerCase().endsWith(ext))
}

export function hasPythonTests(files: CodeFile[]) {
  return files.some((file) => /(^tests\/|^test_|_test\.py$|^conftest\.py$)/i.test(file.name.replace(/\\/g, '/')))
}

export function detectPackageManager(files: CodeFile[], packageJson: { packageManager?: string } | null) {
  const packageManager = packageJson?.packageManager?.split('@')[0]
  if (packageManager === 'pnpm' || findFile(files, 'pnpm-lock.yaml')) return 'pnpm'
  if (packageManager === 'yarn' || findFile(files, 'yarn.lock')) return 'yarn'
  if (packageManager === 'bun' || findFile(files, 'bun.lockb') || findFile(files, 'bun.lock')) return 'bun'
  return 'npm'
}

export function sanitizeRelativePath(filePath: string) {
  return filePath.replace(/^[./\\]+/, '').replace(/\.\.(\/|\\)/g, '').replace(/\\/g, '/')
}

// ---------------------------------------------------------------------------
// File writing
// ---------------------------------------------------------------------------

export async function writeSandboxFiles(rootPath: string, files: CodeFile[]) {
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
