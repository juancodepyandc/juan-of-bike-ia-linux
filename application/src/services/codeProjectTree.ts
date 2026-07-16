// ---------------------------------------------------------------------------
// ProjectTree / VFS model
// Foundation for WS2: preserve the generated project as a structured tree
// instead of an opaque flat blob.
// ---------------------------------------------------------------------------

import { buildImportGraph } from './codeProjectImportGraph.ts'

export type CodeProjectFileEncoding = 'utf8' | 'base64'

export type ProjectTreeInputFile = {
  path?: string
  name?: string
  content: string
  language?: string
  encoding?: CodeProjectFileEncoding
  mime?: string
  size?: number
}

export type ProjectTreeFile = {
  path: string
  content: string
  language: string
  encoding: CodeProjectFileEncoding
  mime?: string
  size: number
  sourcePath?: string
}

export type ProjectTreeDirectory = {
  path: string
  depth: number
  children: string[]
}

export type ProjectPathCollisionReason =
  | 'duplicate'
  | 'case_insensitive_duplicate'
  | 'unsafe'
  | 'empty'

export type ProjectPathCollision = {
  originalPath: string
  normalizedPath: string
  resolvedPath: string
  reason: ProjectPathCollisionReason
}

export type ProjectImportKind = 'static' | 'side_effect' | 'require' | 'dynamic'

export type ProjectImportEdge = {
  from: string
  specifier: string
  resolvedPath: string | null
  kind: ProjectImportKind
  external: boolean
}

export type ProjectImportGraph = {
  nodes: string[]
  edges: ProjectImportEdge[]
  unresolved: ProjectImportEdge[]
}

export type ProjectTree = {
  files: ProjectTreeFile[]
  directories: ProjectTreeDirectory[]
  collisions: ProjectPathCollision[]
  importGraph: ProjectImportGraph
}

type NormalizedPath = {
  originalPath: string
  path: string
  unsafe: boolean
  empty: boolean
}

const EXT_TO_LANGUAGE: Record<string, string> = {
  astro: 'astro',
  bash: 'bash',
  c: 'c',
  cjs: 'javascript',
  cpp: 'cpp',
  cs: 'csharp',
  css: 'css',
  go: 'go',
  html: 'html',
  java: 'java',
  js: 'javascript',
  json: 'json',
  jsx: 'jsx',
  kt: 'kotlin',
  mjs: 'javascript',
  py: 'python',
  rb: 'ruby',
  rs: 'rust',
  scss: 'scss',
  sh: 'bash',
  sql: 'sql',
  svelte: 'svelte',
  toml: 'toml',
  ts: 'typescript',
  tsx: 'tsx',
  txt: 'text',
  vue: 'vue',
  wasm: 'wasm',
  xml: 'xml',
  yaml: 'yaml',
  yml: 'yaml',
}

const EXTENSIONLESS_LANGUAGES: Record<string, string> = {
  containerfile: 'dockerfile',
  dockerfile: 'dockerfile',
  gemfile: 'ruby',
  makefile: 'makefile',
  procfile: 'text',
}

const BINARY_EXTENSIONS = new Set([
  'avif',
  'bin',
  'gif',
  'glb',
  'gltf',
  'ico',
  'jpg',
  'jpeg',
  'mp3',
  'mp4',
  'ogg',
  'otf',
  'png',
  'ttf',
  'wasm',
  'webm',
  'webp',
  'woff',
  'woff2',
])


function compareProjectPath(a: string, b: string) {
  if (a === b) return 0
  return a < b ? -1 : 1
}

function fallbackRecoveredPath(index: number) {
  return `recovered/file-${index}.txt`
}

function sanitizePathSegment(segment: string) {
  return segment
    .replace(/[\u0000-\u001f<>:"|?*]/g, '_')
    .trim()
}

function normalizeProjectPathDetailed(input: string, index: number): NormalizedPath {
  const originalPath = input
  const trimmed = input.trim()
  if (!trimmed) {
    const path = fallbackRecoveredPath(index)
    return { originalPath, path, unsafe: true, empty: true }
  }

  let unsafe = false
  let current = trimmed.replace(/\0/g, '').replace(/\\/g, '/')
  if (/^[a-zA-Z]:\//.test(current)) {
    unsafe = true
    current = current.replace(/^[a-zA-Z]:\//, '')
  }
  if (current.startsWith('/')) {
    unsafe = true
    current = current.replace(/^\/+/, '')
  }

  const parts: string[] = []
  for (const rawPart of current.split('/')) {
    if (!rawPart || rawPart === '.') continue
    if (rawPart === '..') {
      unsafe = true
      if (parts.length > 0) parts.pop()
      continue
    }

    const part = sanitizePathSegment(rawPart)
    if (!part || part === '.' || part === '..') {
      unsafe = true
      continue
    }
    if (part !== rawPart) unsafe = true
    parts.push(part)
  }

  if (parts.length === 0) {
    const path = fallbackRecoveredPath(index)
    return { originalPath, path, unsafe: true, empty: true }
  }

  const normalized = parts.join('/')
  const path = unsafe ? `recovered/${normalized}` : normalized
  return { originalPath, path, unsafe, empty: false }
}

export function normalizeProjectPath(input: string) {
  const normalized = normalizeProjectPathDetailed(input, 1)
  return normalized.empty ? null : normalized.path
}

function dirname(path: string) {
  const index = path.lastIndexOf('/')
  return index === -1 ? '' : path.slice(0, index)
}

function appendCollisionSuffix(path: string, index: number) {
  const slashIndex = path.lastIndexOf('/')
  const dir = slashIndex === -1 ? '' : path.slice(0, slashIndex + 1)
  const basename = slashIndex === -1 ? path : path.slice(slashIndex + 1)
  const dotIndex = basename.lastIndexOf('.')
  const hasExtension = dotIndex > 0
  if (!hasExtension) return `${dir}${basename}__${index}`
  return `${dir}${basename.slice(0, dotIndex)}__${index}${basename.slice(dotIndex)}`
}

function allocateUniquePath(path: string, seenExact: Set<string>, seenLower: Set<string>) {
  if (!seenExact.has(path) && !seenLower.has(path.toLowerCase())) {
    return { path, reason: null as ProjectPathCollisionReason | null }
  }

  const reason = seenExact.has(path) ? 'duplicate' : 'case_insensitive_duplicate'
  let index = 2
  let candidate = appendCollisionSuffix(path, index)
  while (seenExact.has(candidate) || seenLower.has(candidate.toLowerCase())) {
    index += 1
    candidate = appendCollisionSuffix(path, index)
  }
  return { path: candidate, reason: reason as ProjectPathCollisionReason }
}

function fileExtension(path: string) {
  const basename = path.split('/').pop() ?? path
  const dotIndex = basename.lastIndexOf('.')
  if (dotIndex < 0 || dotIndex === basename.length - 1) return ''
  return basename.slice(dotIndex + 1).toLowerCase()
}

function inferFileLanguage(path: string, hint?: string) {
  if (hint && hint.trim()) return hint.trim()
  const basename = (path.split('/').pop() ?? path).toLowerCase()
  if (basename in EXTENSIONLESS_LANGUAGES) return EXTENSIONLESS_LANGUAGES[basename]
  return EXT_TO_LANGUAGE[fileExtension(path)] ?? 'text'
}

function inferEncoding(path: string, explicit?: CodeProjectFileEncoding) {
  if (explicit === 'base64' || explicit === 'utf8') return explicit
  return BINARY_EXTENSIONS.has(fileExtension(path)) ? 'base64' : 'utf8'
}

function buildDirectories(files: ProjectTreeFile[]) {
  const directoryPaths = new Set<string>()
  const children = new Map<string, Set<string>>()

  const addChild = (parent: string, child: string) => {
    if (!children.has(parent)) children.set(parent, new Set())
    children.get(parent)!.add(child)
  }

  for (const file of files) {
    const parts = file.path.split('/')
    for (let index = 0; index < parts.length - 1; index += 1) {
      const dir = parts.slice(0, index + 1).join('/')
      const parent = parts.slice(0, index).join('/')
      directoryPaths.add(dir)
      addChild(parent, dir)
    }
    addChild(dirname(file.path), file.path)
  }

  return [...directoryPaths]
    .sort(compareProjectPath)
    .map((path) => ({
      path,
      depth: path.split('/').length,
      children: [...(children.get(path) ?? [])].sort(compareProjectPath),
    }))
}


export function buildProjectTree(inputFiles: ProjectTreeInputFile[]): ProjectTree {
  const files: ProjectTreeFile[] = []
  const collisions: ProjectPathCollision[] = []
  const seenExact = new Set<string>()
  const seenLower = new Set<string>()

  inputFiles.forEach((inputFile, index) => {
    const rawPath = inputFile.path ?? inputFile.name ?? ''
    const normalized = normalizeProjectPathDetailed(rawPath, index + 1)
    if (normalized.unsafe || normalized.empty) {
      collisions.push({
        originalPath: normalized.originalPath,
        normalizedPath: normalized.path,
        resolvedPath: normalized.path,
        reason: normalized.empty ? 'empty' : 'unsafe',
      })
    }

    const allocated = allocateUniquePath(normalized.path, seenExact, seenLower)
    if (allocated.reason) {
      collisions.push({
        originalPath: normalized.originalPath,
        normalizedPath: normalized.path,
        resolvedPath: allocated.path,
        reason: allocated.reason,
      })
    }
    seenExact.add(allocated.path)
    seenLower.add(allocated.path.toLowerCase())

    const encoding = inferEncoding(allocated.path, inputFile.encoding)
    files.push({
      path: allocated.path,
      content: inputFile.content,
      language: inferFileLanguage(allocated.path, inputFile.language),
      encoding,
      mime: inputFile.mime,
      size: inputFile.size ?? inputFile.content.length,
      sourcePath: rawPath && rawPath !== allocated.path ? rawPath : undefined,
    })
  })

  files.sort((a, b) => compareProjectPath(a.path, b.path))

  return {
    files,
    directories: buildDirectories(files),
    collisions,
    importGraph: buildImportGraph(files),
  }
}

export function projectTreeToCodeFiles(tree: ProjectTree) {
  return tree.files
    .filter((file) => file.encoding === 'utf8')
    .map((file) => ({
      name: file.path,
      language: file.language,
      content: file.content,
    }))
}
