import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { isCssLike, isHtmlLike, isTsLike, normalizedName } from './codeStaticCriticShared.ts'
import { normalizedProjectPaths } from './codeStaticCompleteness.ts'
import { describeGeneratedImportRemediation } from './codeCodegenDependencies.ts'

// --- 6. Project integrity critic ------------------------------------------
// Catches cross-file failures that a single-file syntax regex cannot see:
// missing local imports, missing linked assets, and Tailwind utility markup
// generated without Tailwind or matching CSS. These are common "looks like a
// project" failures that compile/run checks may find late after npm install.

const RESOLVABLE_EXTENSIONS = [
  '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
  '.json', '.css', '.scss', '.sass', '.less',
  '.html', '.htm', '.svg',
]

function dirnameOf(name: string): string {
  const normalized = normalizedName(name)
  const slash = normalized.lastIndexOf('/')
  return slash >= 0 ? normalized.slice(0, slash) : ''
}

function joinProjectPath(baseDir: string, specifier: string): string {
  const raw = `${baseDir ? `${baseDir}/` : ''}${specifier}`.replace(/\\/g, '/')
  const parts: string[] = []
  for (const part of raw.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/').toLowerCase()
}

function hasExplicitExtension(path: string): boolean {
  return /\.[a-z0-9]+$/i.test(path.split('/').pop() || '')
}

function resolveProjectImport(paths: Set<string>, fromFile: string, specifier: string): string | null {
  const requested = joinProjectPath(dirnameOf(fromFile), specifier)
  if (paths.has(requested)) return requested
  if (hasExplicitExtension(requested)) return null

  for (const ext of RESOLVABLE_EXTENSIONS) {
    const candidate = `${requested}${ext}`
    if (paths.has(candidate)) return candidate
  }
  for (const ext of RESOLVABLE_EXTENSIONS) {
    const candidate = `${requested}/index${ext}`
    if (paths.has(candidate)) return candidate
  }
  return null
}

function collectLocalSpecifiers(content: string): string[] {
  const specs: string[] = []
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"](\.[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"](\.[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(content)) !== null) {
      specs.push(match[1])
    }
  }
  return specs
}

const NODE_BUILTIN_IMPORTS = new Set([
  'assert', 'buffer', 'child_process', 'cluster', 'crypto', 'dns', 'events', 'fs',
  'http', 'https', 'net', 'os', 'path', 'process', 'querystring', 'readline',
  'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url', 'util', 'vm', 'zlib',
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

function collectBarePackageSpecifiers(content: string): string[] {
  const specs: string[] = []
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(content)) !== null) {
      const packageName = packageNameFromImportSpecifier(match[1])
      if (packageName) specs.push(packageName)
    }
  }
  return specs
}

function readManifestDependencyNames(project: CodeProject): Set<string> | null {
  const packageFile = project.files.find((f) => normalizedName(f.name) === 'package.json')
  if (!packageFile) return null
  try {
    const manifest = JSON.parse(packageFile.content) as Record<string, unknown>
    const names = new Set<string>()
    for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
      const deps = manifest[section]
      if (!deps || typeof deps !== 'object' || Array.isArray(deps)) continue
      for (const name of Object.keys(deps as Record<string, unknown>)) names.add(name)
    }
    return names
  } catch {
    return null
  }
}

function missingPackageDependencyIssues(project: CodeProject): CritiqueIssue[] {
  const declared = readManifestDependencyNames(project)
  if (!declared) return []
  const issues: CritiqueIssue[] = []
  const seen = new Set<string>()

  for (const file of project.files) {
    if (!isTsLike(file.language) && !/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    for (const packageName of collectBarePackageSpecifiers(file.content)) {
      if (declared.has(packageName) || seen.has(packageName)) continue
      seen.add(packageName)
      issues.push({
        axis: 'compile',
        severity: 'block',
        message: `${file.name}: dependance npm importee mais absente du package.json (${packageName})`,
        location: { file: file.name },
        suggestion: `Ajouter ${packageName} dans dependencies/devDependencies ou remplacer l import par du code local livre.`,
      })
    }
  }

  return issues
}

function hasTailwindSetup(project: CodeProject): boolean {
  const paths = normalizedProjectPaths(project)
  if (paths.some((p) => /(^|\/)(tailwind\.config\.(?:js|cjs|mjs|ts)|postcss\.config\.(?:js|cjs|mjs|ts))$/.test(p))) {
    return true
  }
  const all = project.files.map((f) => f.content).join('\n')
  if (/cdn\.tailwindcss\.com/i.test(all)) {
    return true
  }
  const packageFile = project.files.find((f) => normalizedName(f.name) === 'package.json')
  if (!packageFile) return false
  try {
    const manifest = JSON.parse(packageFile.content) as {
      dependencies?: Record<string, unknown>
      devDependencies?: Record<string, unknown>
    }
    return Boolean(manifest.dependencies?.tailwindcss || manifest.devDependencies?.tailwindcss)
  } catch {
    return false
  }
}

function extractClassTokens(content: string): string[] {
  const tokens: string[] = []
  const classAttr = /\bclass(?:Name)?\s*=\s*["']([^"']+)["']/g
  let match: RegExpExecArray | null
  while ((match = classAttr.exec(content)) !== null) {
    tokens.push(...match[1].split(/\s+/).filter(Boolean))
  }
  return tokens
}

function isLikelyTailwindUtility(token: string): boolean {
  const normalized = token.replace(/^(?:sm|md|lg|xl|2xl|dark|hover|focus|active|disabled|group-hover|motion-safe|motion-reduce):/g, '')
  return /^(?:container|sr-only|flex|inline-flex|grid|hidden|block|relative|absolute|fixed|sticky|inset-|top-|right-|bottom-|left-|z-\d+|min-h-|max-w-|w-(?:\d|full|screen)|h-(?:\d|full|screen)|p[trblxy]?-\d+|m[trblxy]?-\d+|mx-auto|gap-\d+|space-[xy]-\d+|items-|justify-|content-|rounded(?:-|$)|border(?:-|$)|shadow(?:-|$)|bg-|text-|font-|leading-|tracking-|opacity-|transition|duration-|ease-|overflow-|object-|aspect-|scale-|translate-|rotate-|transform|from-|via-|to-|backdrop-|dark:bg-|dark:text-|dark:border-)/.test(normalized)
}

function linkedLocalAssetsMissing(project: CodeProject, paths: Set<string>): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const linkedFile = project.files.filter((file) => isHtmlLike(file.language) || isCssLike(file.language) || /\.(html?|css|scss)$/i.test(file.name))
  const refPattern = /(?:\b(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^"')]+)["']?\s*\))/gi
  const localAsset = /\.(?:css|m?js|jsx|tsx|png|jpe?g|webp|gif|svg|ico|woff2?|ttf|otf|mp3|wav|mp4|webm|glb|gltf)$/i

  for (const file of linkedFile) {
    let match: RegExpExecArray | null
    while ((match = refPattern.exec(file.content)) !== null) {
      const rawUrl = (match[1] || match[2] || '').trim()
      if (!rawUrl || /^(?:https?:)?\/\//i.test(rawUrl) || /^(?:data:|mailto:|tel:|#)/i.test(rawUrl)) continue
      const cleanUrl = rawUrl.split(/[?#]/)[0]
      if (!localAsset.test(cleanUrl)) continue
      if (!resolveProjectImport(paths, file.name, cleanUrl)) {
        issues.push({
          axis: 'runtime',
          severity: 'error',
          message: `${file.name}: ressource locale referencee mais absente (${rawUrl})`,
          location: { file: file.name },
          suggestion: 'Livrer le fichier reference ou remplacer par un SVG/data URL inline verifie.',
        })
      }
    }
  }
  return issues
}

function projectIntegrityIssues(project: CodeProject, intent: CodeIntent): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const paths = new Set(normalizedProjectPaths(project))

  for (const file of project.files) {
    if (!isTsLike(file.language) && !/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    for (const specifier of collectLocalSpecifiers(file.content)) {
      if (!resolveProjectImport(paths, file.name, specifier)) {
        // « Ajoute le fichier » est IMPOSSIBLE a suivre quand le fichier est un
        // artefact genere: seul un generateur le produit, et ce pipeline n en
        // execute aucun. Run 1111: neuf passes sur `./routeTree.gen`, diagnostic
        // juste a chaque fois, aucune action disponible pour le resoudre. Un
        // conseil irrealisable transforme une porte en piege.
        const generated = describeGeneratedImportRemediation({
          importPath: specifier,
          dependencyNames: [...(readManifestDependencyNames(project) ?? [])],
        })
        issues.push({
          axis: 'compile',
          severity: 'block',
          message: `${file.name}: import local introuvable (${specifier})`,
          location: { file: file.name },
          suggestion: generated ?? `Ajouter le fichier ${specifier} ou corriger le chemin d import.`,
        })
      }
    }
  }

  issues.push(...linkedLocalAssetsMissing(project, paths))
  issues.push(...missingPackageDependencyIssues(project))

  const projectType = intent.projectType || 'unknown'
  const visualProject = projectType === 'static_web'
    || projectType.startsWith('spa_')
    || projectType.startsWith('ssr_')
    || projectType.startsWith('fullstack_')
    || projectType === 'game_web'
  if (visualProject && !hasTailwindSetup(project)) {
    let utilityCount = 0
    const examples = new Set<string>()
    for (const file of project.files) {
      if (!isTsLike(file.language) && !isHtmlLike(file.language) && !/\.(tsx|jsx|html?)$/i.test(file.name)) continue
      for (const token of extractClassTokens(file.content)) {
        if (!isLikelyTailwindUtility(token)) continue
        utilityCount += 1
        if (examples.size < 6) examples.add(token)
      }
    }
    if (utilityCount >= 8) {
      issues.push({
        axis: 'preview',
        severity: 'error',
        message: `Classes Tailwind detectees sans configuration Tailwind (${utilityCount} utilities, ex: ${[...examples].join(', ')})`,
        suggestion: 'Ajouter tailwindcss + config/postcss et @tailwind utilities, ou remplacer par du CSS livre dans le projet.',
      })
    }
  }

  return issues
}

export const projectIntegrityCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = projectIntegrityIssues(project, intent)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  return buildReport({
    compile: blockers > 0 ? 0 : 1,
    runtime: Math.max(0, 1 - blockers * 0.6 - errors * 0.25),
    preview: Math.max(0, 1 - errors * 0.25 - warns * 0.05),
    fidelity: Math.max(0, 1 - errors * 0.15 - warns * 0.05),
  }, issues)
}
