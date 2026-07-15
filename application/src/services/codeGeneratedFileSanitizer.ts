// ---------------------------------------------------------------------------
// Generated file sanitization
// Extracted from codeOrchestrator.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestrator.ts'

export type LocalNodeManifest = {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
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

function stripJsonCommentsAndTrailingCommas(content: string) {
  let out = ''
  let inString = false
  let quote = ''
  let escaped = false
  let inLineComment = false
  let inBlockComment = false

  for (let index = 0; index < content.length; index += 1) {
    const ch = content[index]
    const next = content[index + 1]

    if (inLineComment) {
      if (ch === '\n' || ch === '\r') {
        inLineComment = false
        out += ch
      }
      continue
    }

    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false
        index += 1
      }
      continue
    }

    if (inString) {
      out += ch
      if (escaped) {
        escaped = false
      } else if (ch === '\\') {
        escaped = true
      } else if (ch === quote) {
        inString = false
        quote = ''
      }
      continue
    }

    if (ch === '"' || ch === "'") {
      inString = true
      quote = ch
      out += ch
      continue
    }

    if (ch === '/' && next === '/') {
      inLineComment = true
      index += 1
      continue
    }

    if (ch === '/' && next === '*') {
      inBlockComment = true
      index += 1
      continue
    }

    out += ch
  }

  return out.replace(/,\s*([}\]])/g, '$1')
}

function isStructuredMachineFile(filename: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  return normalized.endsWith('.json')
    || normalized.endsWith('.toml')
    || normalized.endsWith('.yaml')
    || normalized.endsWith('.yml')
}

export function tryParseJson(content: string) {
  try {
    return JSON.parse(content) as Record<string, unknown>
  } catch {
    try {
      const repaired = stripJsonCommentsAndTrailingCommas(content)
      if (repaired === content) return null
      return JSON.parse(repaired) as Record<string, unknown>
    } catch {
      return null
    }
  }
}

const SAFE_VITE_VERSION = '^8.1.3'
const SAFE_VITE_REACT_PLUGIN_VERSION = '^5.1.2'

function repairKnownManifestDependencyNames(manifest: Record<string, unknown>) {
  let next: Record<string, unknown> = { ...manifest }
  const renameMap: Record<string, string> = {
    'react-three-fiber': '@react-three/fiber',
    'react-three/drei': '@react-three/drei',
    'react-three/postprocessing': '@react-three/postprocessing',
  }

  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const deps = next[section]
    if (!deps || typeof deps !== 'object' || Array.isArray(deps)) continue
    const repairedDeps: Record<string, unknown> = { ...(deps as Record<string, unknown>) }
    for (const [wrongName, correctName] of Object.entries(renameMap)) {
      if (!(wrongName in repairedDeps)) continue
      repairedDeps[correctName] = repairedDeps[correctName] || repairedDeps[wrongName]
      delete repairedDeps[wrongName]
    }
    next[section] = repairedDeps
  }

  if (manifestUsesPackage(next, 'vite') || manifestUsesPackage(next, '@vitejs/plugin-react') || manifestHasViteScript(next)) {
    next = movePackageToDevDependency(next, 'vite', SAFE_VITE_VERSION)
    next = movePackageToDevDependency(next, '@vitejs/plugin-react', SAFE_VITE_REACT_PLUGIN_VERSION)
  }

  return next
}

function repairGeneratedTsConfig(config: Record<string, unknown>) {
  const compilerOptions =
    config.compilerOptions && typeof config.compilerOptions === 'object' && !Array.isArray(config.compilerOptions)
      ? { ...(config.compilerOptions as Record<string, unknown>) }
      : {}

  compilerOptions.noUnusedLocals = false
  compilerOptions.noUnusedParameters = false

  return {
    ...config,
    compilerOptions,
  }
}

function repairGeneratedTypeScriptContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  if (!/\.[cm]?[jt]sx?$/.test(normalized)) return content

  let next = content

  // React 19 exposes a readonly ref overload when useRef<T>(null) is used with
  // non-nullable T. Generated R3F code frequently assigns to ref.current during
  // scene setup, so the ref must include null in its type parameter.
  next = next.replace(
    /\buseRef<((?:THREE\.)?(?:Mesh|Group|Object3D|InstancedMesh|PerspectiveCamera|OrthographicCamera|Camera|Scene|DirectionalLight|PointLight|SpotLight|AmbientLight|Line|Points|Sprite))>\(null\)/g,
    'useRef<$1 | null>(null)',
  )

  // Common Zustand shape emitted by local models: the store type only accepts a
  // concrete resources array, but components call setResources(prev => ...).
  next = next.replace(
    /setResources:\s*\(resources:\s*THREE\.Mesh\[\]\)\s*=>\s*void/g,
    'setResources: (resources: THREE.Mesh[] | ((prev: THREE.Mesh[]) => THREE.Mesh[])) => void',
  )
  next = next.replace(
    /setResources:\s*\(resources\)\s*=>\s*set\(\{\s*resources\s*\}\)/g,
    "setResources: (resources) => set((state) => ({ resources: typeof resources === 'function' ? resources(state.resources) : resources }))",
  )

  if (/\binterface\s+TableProps\s*<\s*TData\s*>/.test(next) || /\bconst\s+Table\s*=\s*<\s*TData\b/.test(next)) {
    next = next.replace(/\baccessorKey:\s*string\b/g, 'accessorKey?: keyof TData | string')
    next = next.replace(/key=\{column\.accessorKey\}/g, 'key={String(column.accessorKey || column.header)}')
    next = next.replace(
      /row\[column\.accessorKey\s+as\s+keyof\s+TData\]/g,
      '(column.accessorKey ? row[column.accessorKey as keyof TData] : undefined)',
    )
  }

  return next
}

export function sanitizeGeneratedFileContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  const cleaned = stripFormattingArtifacts(content)

  if (normalized.endsWith('.json')) {
    const parsed = tryParseJson(cleaned)
    if (parsed) {
      const next = normalized === 'package.json'
        ? repairKnownManifestDependencyNames(parsed)
        : normalized.endsWith('tsconfig.json') || normalized.endsWith('tsconfig.node.json')
          ? repairGeneratedTsConfig(parsed)
          : parsed
      return `${JSON.stringify(next, null, 2)}\n`
    }
  }

  if (isStructuredMachineFile(normalized)) {
    return cleaned
  }

  return repairGeneratedTypeScriptContent(filename, cleaned)
}

function upsertPackageDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
  force = false,
) {
  const deps = manifest.dependencies && typeof manifest.dependencies === 'object' && !Array.isArray(manifest.dependencies)
    ? { ...(manifest.dependencies as Record<string, unknown>) }
    : {}

  if (force || !(dependencyName in deps)) {
    deps[dependencyName] = version
  }

  return { ...manifest, dependencies: deps }
}

export function upsertPackageDevDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
  force = false,
) {
  const devDeps = manifest.devDependencies && typeof manifest.devDependencies === 'object' && !Array.isArray(manifest.devDependencies)
    ? { ...(manifest.devDependencies as Record<string, unknown>) }
    : {}

  if (force || !(dependencyName in devDeps)) {
    devDeps[dependencyName] = version
  }

  return { ...manifest, devDependencies: devDeps }
}

export function manifestUsesPackage(manifest: Record<string, unknown>, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const deps = manifest[section]
    if (deps && typeof deps === 'object' && !Array.isArray(deps) && dependencyName in deps) {
      return true
    }
  }
  return false
}

function manifestHasViteScript(manifest: Record<string, unknown>) {
  const scripts = manifest.scripts
  if (!scripts || typeof scripts !== 'object' || Array.isArray(scripts)) return false
  return Object.values(scripts as Record<string, unknown>).some((script) => /\bvite\b/.test(String(script)))
}

function movePackageToDevDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
) {
  let next: Record<string, unknown> = { ...manifest }
  for (const section of ['dependencies', 'optionalDependencies'] as const) {
    const deps = next[section]
    if (!deps || typeof deps !== 'object' || Array.isArray(deps) || !(dependencyName in deps)) continue
    const repairedDeps = { ...(deps as Record<string, unknown>) }
    delete repairedDeps[dependencyName]
    next = { ...next, [section]: repairedDeps }
  }
  return upsertPackageDevDependency(next, dependencyName, version, true)
}

const NODE_BUILTIN_IMPORTS = new Set([
  'assert', 'buffer', 'child_process', 'cluster', 'crypto', 'dns', 'events', 'fs',
  'http', 'https', 'net', 'os', 'path', 'process', 'querystring', 'readline',
  'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url', 'util', 'vm', 'zlib',
])

const COMMON_PACKAGE_IMPORT_VERSIONS: Record<string, string> = {
  '@monaco-editor/react': '^4.7.0',
  '@react-spring/three': '^9.7.5',
  '@react-three/drei': '^10.7.7',
  '@react-three/fiber': '^9.6.1',
  '@react-three/postprocessing': '^3.0.4',
  '@vitejs/plugin-react': SAFE_VITE_REACT_PLUGIN_VERSION,
  'framer-motion': '^11.18.2',
  'lucide-react': '^0.468.0',
  'monaco-editor': '^0.52.2',
  'react': '^19.2.0',
  'react-dom': '^19.2.0',
  'react-icons': '^5.5.0',
  'react-router-dom': '^7.13.2',
  'three': '^0.183.2',
  'zustand': '^5.0.2',
}

function packageNameFromImportSpecifier(specifier: string): string | null {
  if (!specifier || specifier.startsWith('.') || specifier.startsWith('/') || specifier.startsWith('#')) return null
  if (specifier.startsWith('node:')) return null
  const parts = specifier.split('/')
  const packageName = specifier.startsWith('@') && parts.length >= 2
    ? `${parts[0]}/${parts[1]}`
    : parts[0]
  if (NODE_BUILTIN_IMPORTS.has(packageName)) return null
  return packageName
}

function collectBarePackageImports(sourceBlob: string): Set<string> {
  const packages = new Set<string>()
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(sourceBlob)) !== null) {
      const packageName = packageNameFromImportSpecifier(match[1])
      if (packageName) packages.add(packageName)
    }
  }
  return packages
}

function repairPackageManifestFromSourceImports(files: CodeFile[]) {
  const packageIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex < 0) return files

  const packageFile = files[packageIndex]
  let manifest = tryParseJson(stripFormattingArtifacts(packageFile.content))
  if (!manifest) return files

  const sourceBlob = files
    .filter((file) => /\.(tsx?|jsx?|vue|svelte|astro)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')

  manifest = repairKnownManifestDependencyNames(manifest)

  const usesR3f = /@react-three\/(fiber|drei|postprocessing)/.test(sourceBlob)
  if (usesR3f) {
    const reactSpec = readManifestDependencySpec(manifest as LocalNodeManifest, 'react')
    // v89b: parseSpecVersion(...)?.major is number | undefined; normalise the
    // unparseable case to null so an unknown React version defaults to React 19
    // (same as the no-spec branch) instead of silently skipping the upgrade.
    const reactMajor = (reactSpec ? parseSpecVersion(reactSpec)?.major : null) ?? null
    const useReact19 = reactMajor === null || reactMajor >= 19

    if (useReact19) {
      manifest = upsertPackageDependency(manifest, 'react', '^19.2.0', true)
      manifest = upsertPackageDependency(manifest, 'react-dom', '^19.2.0', true)
      manifest = upsertPackageDevDependency(manifest, '@types/react', '^19.0.0', true)
      manifest = upsertPackageDevDependency(manifest, '@types/react-dom', '^19.0.0', true)
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', '^9.6.1', true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', '^10.7.7', true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', '^3.0.4', true)
      }
    } else {
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', '^8.18.0', true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', '^9.122.0', true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', '^2.16.3', true)
      }
    }
  }

  const requiredDeps: Array<[RegExp, string, string]> = [
    [/@react-spring\/three/, '@react-spring/three', '^9.7.5'],
    [/framer-motion/, 'framer-motion', '^11.18.2'],
  ]

  for (const [pattern, dependencyName, version] of requiredDeps) {
    if (pattern.test(sourceBlob)) {
      manifest = upsertPackageDependency(manifest, dependencyName, version)
    }
  }

  for (const packageName of collectBarePackageImports(sourceBlob)) {
    if (packageName === 'vite') {
      manifest = movePackageToDevDependency(manifest, 'vite', SAFE_VITE_VERSION)
      continue
    }
    if (packageName === '@vitejs/plugin-react') {
      manifest = movePackageToDevDependency(manifest, '@vitejs/plugin-react', SAFE_VITE_REACT_PLUGIN_VERSION)
      manifest = movePackageToDevDependency(manifest, 'vite', SAFE_VITE_VERSION)
      continue
    }
    const version = COMMON_PACKAGE_IMPORT_VERSIONS[packageName]
    if (version) {
      manifest = upsertPackageDependency(manifest, packageName, version)
    }
    if (packageName === '@monaco-editor/react') {
      manifest = upsertPackageDependency(manifest, 'monaco-editor', COMMON_PACKAGE_IMPORT_VERSIONS['monaco-editor'])
    }
  }

  const nextContent = `${JSON.stringify(manifest, null, 2)}\n`
  if (nextContent === packageFile.content) return files

  return files.map((file, index) => (index === packageIndex ? { ...file, content: nextContent } : file))
}

export function sanitizeGeneratedFiles(files: CodeFile[]) {
  const sanitized = files.map((file) => ({
    ...file,
    content: sanitizeGeneratedFileContent(file.name, file.content),
  }))
  return repairPackageManifestFromSourceImports(sanitized)
}

export function normalizeGeneratedCodeFilesForTest(files: CodeFile[]) {
  return sanitizeGeneratedFiles(files)
}

export function readManifestDependencySpec(manifest: LocalNodeManifest, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const collection = manifest[section]
    if (collection && typeof collection === 'object' && dependencyName in collection) {
      const value = (collection as Record<string, unknown>)[dependencyName]
      if (typeof value === 'string') {
        return value
      }
    }
  }

  return null
}

function parseSpecVersion(spec: string) {
  const match = spec.match(/(\d+)(?:\.(\d+))?(?:\.(\d+))?/)
  if (!match) return null

  return {
    major: Number(match[1]),
    minor: Number(match[2] || '0'),
    patch: Number(match[3] || '0'),
  }
}

export function isVersionBelow(spec: string, minimumMajor: number, minimumMinor: number) {
  const version = parseSpecVersion(spec)
  if (!version) return false
  if (version.major !== minimumMajor) {
    return version.major < minimumMajor
  }
  return version.minor < minimumMinor
}
