import type {
  ProjectImportGraph,
  ProjectImportKind,
  ProjectTreeFile,
} from './codeProjectTree.ts'

function compareProjectPath(a: string, b: string) {
  if (a === b) return 0
  return a < b ? -1 : 1
}

function dirname(path: string) {
  const index = path.lastIndexOf('/')
  return index === -1 ? '' : path.slice(0, index)
}

function sanitizePathSegment(segment: string) {
  return segment.replace(/[\u0000-\u001f<>:\"|?*]/g, '_').trim()
}

const IMPORT_EXTENSIONS = [
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.css',
  '.scss',
  '.json',
  '.vue',
  '.svelte',
  '.astro',
]

const IMPORT_PATTERNS: Array<{
  regex: RegExp
  kind: ProjectImportKind
}> = [
  { regex: /\bimport\s+(?:type\s+)?(?:[^'"]+\s+from\s*)?['"]([^'"]+)['"]/g, kind: 'static' },
  { regex: /\bexport\s+(?:type\s+)?[^'"]+\s+from\s*['"]([^'"]+)['"]/g, kind: 'static' },
  { regex: /\brequire\(\s*['"]([^'"]+)['"]\s*\)/g, kind: 'require' },
  { regex: /\bimport\(\s*['"]([^'"]+)['"]\s*\)/g, kind: 'dynamic' },
]

function normalizeRelativeImportPath(fromPath: string, specifier: string) {
  const stack = dirname(fromPath).split('/').filter(Boolean)
  for (const rawPart of specifier.split('/')) {
    if (!rawPart || rawPart === '.') continue
    if (rawPart === '..') {
      if (stack.length === 0) return null
      stack.pop()
      continue
    }
    const part = sanitizePathSegment(rawPart)
    if (!part || part === '.' || part === '..') return null
    stack.push(part)
  }
  return stack.join('/')
}

function hasImportExtension(path: string) {
  return IMPORT_EXTENSIONS.some((extension) => path.endsWith(extension))
}

function resolveRelativeImport(fromPath: string, specifier: string, fileSet: Set<string>) {
  const base = normalizeRelativeImportPath(fromPath, specifier)
  if (!base) return null

  const candidates = [base]
  if (!hasImportExtension(base)) {
    for (const extension of IMPORT_EXTENSIONS) candidates.push(`${base}${extension}`)
    for (const extension of IMPORT_EXTENSIONS) candidates.push(`${base}/index${extension}`)
  }

  return candidates.find((candidate) => fileSet.has(candidate)) ?? null
}

function classifyImportKind(matchText: string, defaultKind: ProjectImportKind) {
  if (defaultKind !== 'static') return defaultKind
  return /\bimport\s*['"]/.test(matchText) ? 'side_effect' : 'static'
}

export function buildImportGraph(files: ProjectTreeFile[]): ProjectImportGraph {
  const nodes = files.map((file) => file.path).sort(compareProjectPath)
  const fileSet = new Set(nodes)
  const edges: ProjectImportEdge[] = []

  for (const file of files) {
    if (file.encoding === 'base64') continue
    for (const pattern of IMPORT_PATTERNS) {
      pattern.regex.lastIndex = 0
      let match: RegExpExecArray | null
      while ((match = pattern.regex.exec(file.content)) !== null) {
        const specifier = match[1]
        if (!specifier) continue
        const external = !specifier.startsWith('.')
        const resolvedPath = external ? null : resolveRelativeImport(file.path, specifier, fileSet)
        edges.push({
          from: file.path,
          specifier,
          resolvedPath,
          kind: classifyImportKind(match[0], pattern.kind),
          external,
        })
      }
    }
  }

  edges.sort((a, b) =>
    compareProjectPath(a.from, b.from)
    || compareProjectPath(a.specifier, b.specifier)
    || compareProjectPath(a.resolvedPath ?? '', b.resolvedPath ?? ''),
  )

  return {
    nodes,
    edges,
    unresolved: edges.filter((edge) => !edge.external && !edge.resolvedPath),
  }
}
