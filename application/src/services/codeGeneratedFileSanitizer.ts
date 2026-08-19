// ---------------------------------------------------------------------------
// Generated file sanitization
// Extracted from codeOrchestrator.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import { repairEscapedNewlines } from './codeEscapedNewlines.ts'
import { repairGeneratedTsConfig } from './codeTsConfigPolicy.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import {
  getGeneratedNodeDependencySpec,
  getLegacyReactThreeDependencySpec,
} from './codeGeneratedDependencyPolicy.ts'
import { repairGeneratedTypeScriptContent } from './codeGeneratedTypeScriptRepair.ts'
import { isApostropheRepairable, repairFrenchApostrophes } from './codeApostropheRepair.ts'
import {
  parseSpecVersion,
  readManifestDependencySpec,
  type LocalNodeManifest,
} from './codeManifestVersion.ts'
export { isVersionBelow, readManifestDependencySpec } from './codeManifestVersion.ts'
export type { LocalNodeManifest } from './codeManifestVersion.ts'


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

const SAFE_VITE_VERSION = getGeneratedNodeDependencySpec('vite')
const SAFE_VITE_REACT_PLUGIN_VERSION = getGeneratedNodeDependencySpec('@vitejs/plugin-react')

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



export function sanitizeGeneratedFileContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  const cleaned = stripFormattingArtifacts(repairEscapedNewlines(filename, content).content)

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

  // Run 1051: 9 passes sur la meme apostrophe francaise, puis abandon. Cas
  // deterministe -> corrige ici, jamais confie a une passe probabiliste.
  const fixed = isApostropheRepairable(normalized) ? repairFrenchApostrophes(cleaned).code : cleaned
  return repairGeneratedTypeScriptContent(filename, fixed)
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

const COMMON_PACKAGE_IMPORTS = new Set([
  '@monaco-editor/react', '@react-spring/three', '@react-three/drei',
  '@react-three/fiber', '@react-three/postprocessing', '@vitejs/plugin-react',
  'framer-motion', 'lucide-react', 'monaco-editor', 'react', 'react-dom',
  'react-icons', 'react-router-dom', 'three', 'zustand',
])

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
      manifest = upsertPackageDependency(manifest, 'react', getGeneratedNodeDependencySpec('react'), true)
      manifest = upsertPackageDependency(manifest, 'react-dom', getGeneratedNodeDependencySpec('react-dom'), true)
      manifest = upsertPackageDevDependency(manifest, '@types/react', getGeneratedNodeDependencySpec('@types/react'), true)
      manifest = upsertPackageDevDependency(manifest, '@types/react-dom', getGeneratedNodeDependencySpec('@types/react-dom'), true)
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', getGeneratedNodeDependencySpec('@react-three/fiber'), true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', getGeneratedNodeDependencySpec('@react-three/drei'), true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', getGeneratedNodeDependencySpec('@react-three/postprocessing'), true)
      }
    } else {
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', getLegacyReactThreeDependencySpec('@react-three/fiber'), true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', getLegacyReactThreeDependencySpec('@react-three/drei'), true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', getLegacyReactThreeDependencySpec('@react-three/postprocessing'), true)
      }
    }
  }

  const requiredDeps: Array<[RegExp, string]> = [
    [/@react-spring\/three/, '@react-spring/three'],
    [/framer-motion/, 'framer-motion'],
  ]

  for (const [pattern, dependencyName] of requiredDeps) {
    if (pattern.test(sourceBlob)) {
      manifest = upsertPackageDependency(manifest, dependencyName, getGeneratedNodeDependencySpec(dependencyName))
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
    if (COMMON_PACKAGE_IMPORTS.has(packageName)) {
      manifest = upsertPackageDependency(manifest, packageName, getGeneratedNodeDependencySpec(packageName))
    }
    if (packageName === '@monaco-editor/react') {
      manifest = upsertPackageDependency(manifest, 'monaco-editor', getGeneratedNodeDependencySpec('monaco-editor'))
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
