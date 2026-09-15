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

function ensureCompatiblePackageManifest(files: CodeFile[]) {
  const packageFile = findFile(files, 'package.json')
  if (!packageFile) return { files, notes: [] as string[] }
  const manifest = parseJsonSafely<NodePackageManifest>(packageFile.content)
  if (!manifest) return { files, notes: [] as string[] }

  const hasVite = files.some((f) => /(^|\/)vite\.config\.(?:ts|js|mjs)$/i.test(f.name) || /(^|\/)index\.html$/i.test(f.name))
  let changed = false
  const scripts = { ...(manifest.scripts || {}) } as Record<string, string>
  const deps = { ...(manifest.dependencies || {}) } as Record<string, string>
  const devDeps = { ...(manifest.devDependencies || {}) } as Record<string, string>

  if (hasVite && (deps['react-scripts'] || (scripts.build && scripts.build.includes('react-scripts')))) {
    delete deps['react-scripts']
    delete deps['@testing-library/jest-dom']
    delete deps['@testing-library/react']
    delete deps['@testing-library/user-event']
    delete deps['@types/jest']
    delete deps['web-vitals']
    if (deps['@types/node']) deps['@types/node'] = '^20.11.0'
    if (devDeps['@types/node']) devDeps['@types/node'] = '^20.11.0'
    if (!devDeps.vite) devDeps.vite = '^5.4.14'
    if (!devDeps['@vitejs/plugin-react']) devDeps['@vitejs/plugin-react'] = '^4.3.4'
    if (!devDeps.typescript && !deps.typescript) devDeps.typescript = '^5.3.3'
    scripts.dev = 'vite'
    scripts.build = 'tsc && vite build'
    scripts.preview = 'vite preview'
    changed = true
  }

  const KNOWN_BUILTINS = new Set(['fs', 'path', 'os', 'child_process', 'crypto', 'http', 'https', 'events', 'stream', 'util', 'url', 'assert'])

  for (const file of files) {
    if (!/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    const matches = file.content.matchAll(/\b(?:import\s+(?:[\w*\s{},]+from\s+)?|from\s+)['"]([^.'"/][^'"]*|@[^'"]+)['"]/g)
    for (const match of matches) {
      const raw = match[1]
      const pkgName = raw.startsWith('@') ? raw.split('/').slice(0, 2).join('/') : raw.split('/')[0]
      if (KNOWN_BUILTINS.has(pkgName) || pkgName.startsWith('node:')) continue
      if (!deps[pkgName] && !devDeps[pkgName]) {
        deps[pkgName] = pkgName === 'react-beautiful-dnd' ? '^13.1.8' : 'latest'
        if (pkgName === 'react-beautiful-dnd' && !devDeps['@types/react-beautiful-dnd']) {
          devDeps['@types/react-beautiful-dnd'] = '^13.1.8'
        }
        changed = true
      }
    }
  }

  if (!changed) return { files, notes: [] as string[] }

  const updatedManifest = { ...manifest, scripts, dependencies: deps, devDependencies: devDeps }
  const updatedFile = { ...packageFile, content: `${JSON.stringify(updatedManifest, null, 2)}\n` }
  return {
    files: upsertSandboxFile(files, updatedFile),
    notes: ['package.json aligne sur Vite (react-scripts remplace par vite & @vitejs/plugin-react)'],
  }
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

  const alignedManifest = ensureCompatiblePackageManifest(normalizedFiles)
  notes.push(...alignedManifest.notes)

  const isolatedTypeScript = ensureIsolatedTypeScriptProject(alignedManifest.files)
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
  // L'ancienne version retirait `/^[./\\]+/` : elle otait bien les prefixes
  // `./` et `/`, mais elle DECAPITAIT aussi tous les fichiers caches.
  // `.gitignore` devenait `gitignore`, `.env` devenait `env`, `.npmrc`
  // devenait `npmrc` — dans CHAQUE projet livre. Un `.gitignore` sans point
  // n'ignore rien, un `.env` sans point n'est pas charge : le fichier est la,
  // il a l'air correct, et il est inerte. Constate sur la generation reelle du
  // 24/08/2026 (`output/code/sandbox/1787598849366/gitignore`).
  //
  // On raisonne desormais par SEGMENT de chemin plutot que par prefixe :
  // un segment vide (`//`), un `.` et un `..` sont ecartes — ce qui neutralise
  // la remontee de repertoire — et tout autre segment est conserve tel quel,
  // point initial compris.
  const segments = String(filePath).replace(/\\/g, '/').split('/')
  const gardes: string[] = []
  for (const segment of segments) {
    if (segment === '' || segment === '.' || segment === '..') continue
    gardes.push(segment)
  }
  return gardes.join('/')
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
