import type { CodeFile } from './codeOrchestrator.ts'
import { buildProjectTree } from './codeProjectTree.ts'
import type { CodeGenerationQueueItem } from './codeGenerationQueue.ts'

export type CodeProjectMemoryFile = {
  path: string
  language: string
  size: number
  imports: string[]
  importedBy: string[]
  symbols: string[]
  terms: string[]
  embedding?: number[]
}

export type CodeProjectMemory = {
  files: CodeProjectMemoryFile[]
  byPath: Map<string, CodeProjectMemoryFile>
}

export type CodeProjectMemorySelection = {
  file: CodeProjectMemoryFile
  score: number
  reasons: string[]
}

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function dirname(path: string) {
  const index = path.lastIndexOf('/')
  return index < 0 ? '' : path.slice(0, index)
}

function words(input: string) {
  const found = input
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .match(/[a-z0-9_]{3,}/g) ?? []
  const synonyms: Record<string, string[]> = {
    auth: ['login', 'session', 'user'],
    connexion: ['auth', 'login', 'session'],
    utilisateur: ['user', 'account', 'profile'],
    profil: ['profile', 'user', 'account'],
    facturation: ['billing', 'invoice', 'invoices'],
    facture: ['invoice', 'billing'],
    invoices: ['billing', 'invoice'],
    devise: ['currency', 'money', 'price'],
    prix: ['price', 'pricing', 'currency'],
    paiement: ['payment', 'checkout', 'billing'],
    panier: ['cart', 'basket', 'checkout'],
  }
  return [...new Set(found.flatMap((term) => [term, ...(synonyms[term] ?? [])]))].slice(0, 120)
}

export function buildLocalCodeEmbedding(input: string, dimensions = 64) {
  const vector = Array.from({ length: dimensions }, () => 0)
  for (const term of words(input)) {
    let hash = 2166136261
    for (let i = 0; i < term.length; i++) {
      hash ^= term.charCodeAt(i)
      hash = Math.imul(hash, 16777619)
    }
    vector[Math.abs(hash) % dimensions] += 1
  }
  const norm = Math.hypot(...vector)
  return norm > 0 ? vector.map((value) => Number((value / norm).toFixed(6))) : vector
}

function cosineSimilarity(left: number[] | undefined, right: number[]) {
  if (!left?.length || left.length !== right.length) return 0
  let score = 0
  for (let i = 0; i < left.length; i++) score += left[i] * right[i]
  return score
}

function extractSymbols(content: string) {
  const symbols = new Set<string>()
  const declaration = /\b(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var)\s+([A-Za-z_$][\w$]*)/g
  let match: RegExpExecArray | null
  while ((match = declaration.exec(content)) !== null) symbols.add(match[1])

  const exportList = /\bexport\s*\{([^}]+)\}/g
  while ((match = exportList.exec(content)) !== null) {
    for (const part of match[1].split(',')) {
      const name = part.trim().split(/\s+as\s+/i)[0]?.trim()
      if (name) symbols.add(name)
    }
  }
  return [...symbols].slice(0, 80)
}

function isConfigPath(path: string) {
  return path === 'package.json'
    || path.endsWith('/package.json')
    || /(^|\/)(vite|tsconfig|tailwind|postcss|eslint)\.config\./.test(path)
}

export function buildCodeProjectMemory(files: CodeFile[]): CodeProjectMemory {
  const tree = buildProjectTree(files.map((file) => ({
    path: file.name,
    content: file.content,
    language: file.language,
  })))
  const importsByPath = new Map<string, Set<string>>()
  const importedByPath = new Map<string, Set<string>>()

  for (const edge of tree.importGraph.edges) {
    if (!edge.resolvedPath) continue
    if (!importsByPath.has(edge.from)) importsByPath.set(edge.from, new Set())
    importsByPath.get(edge.from)!.add(edge.resolvedPath)
    if (!importedByPath.has(edge.resolvedPath)) importedByPath.set(edge.resolvedPath, new Set())
    importedByPath.get(edge.resolvedPath)!.add(edge.from)
  }

  const memoryFiles = tree.files.map((file) => {
    const path = normalizePath(file.path)
    const symbols = extractSymbols(file.content)
    return {
      path: file.path,
      language: file.language,
      size: file.size,
      imports: [...(importsByPath.get(file.path) ?? [])],
      importedBy: [...(importedByPath.get(file.path) ?? [])],
      symbols,
      terms: [...new Set([...words(file.path), ...words(symbols.join(' ')), ...words(file.content).slice(0, 80)])],
      embedding: buildLocalCodeEmbedding(`${file.path}\n${symbols.join('\n')}\n${file.content}`),
      normalizedPath: path,
    }
  })

  const publicFiles = memoryFiles.map(({ normalizedPath: _normalizedPath, ...file }) => file)
  return {
    files: publicFiles,
    byPath: new Map(publicFiles.map((file) => [normalizePath(file.path), file])),
  }
}

function scoreFile(file: CodeProjectMemoryFile, args: {
  targetPath: string
  prompt: string
  itemImports: string[]
  includeConfigs?: boolean
}) {
  const target = normalizePath(args.targetPath)
  const path = normalizePath(file.path)
  const promptTerms = new Set(words(args.prompt))
  const promptEmbedding = buildLocalCodeEmbedding(args.prompt)
  const reasons: string[] = []
  let score = 0

  if (path === target) { score += 160; reasons.push('target') }
  if (args.includeConfigs !== false && isConfigPath(path)) { score += 35; reasons.push('config') }
  if (dirname(path) && dirname(path) === dirname(target)) { score += 18; reasons.push('same_dir') }
  if (file.imports.some((entry) => normalizePath(entry) === target)) { score += 36; reasons.push('imports_target') }
  if (file.importedBy.some((entry) => normalizePath(entry) === target)) { score += 48; reasons.push('target_imports_file') }

  for (const expectedImport of args.itemImports) {
    const cleaned = normalizePath(expectedImport).replace(/^\.\//, '')
    if (cleaned && (path.includes(cleaned) || cleaned.includes(path.replace(/\.[^.]+$/, '')))) {
      score += 55
      reasons.push('plan_import')
      break
    }
  }

  const termMatches = file.terms.filter((term) => promptTerms.has(term)).length
  if (termMatches > 0) {
    score += Math.min(30, termMatches * 4)
    reasons.push('prompt_terms')
  }

  const embeddingScore = cosineSimilarity(file.embedding, promptEmbedding)
  if (embeddingScore >= 0.18) {
    score += Math.min(24, Math.round(embeddingScore * 24))
    reasons.push('embedding')
  }

  return { score, reasons }
}

export function selectCodeProjectMemoryContext(args: {
  memory: CodeProjectMemory
  item: CodeGenerationQueueItem
  prompt: string
  maxFiles?: number
}): CodeProjectMemorySelection[] {
  const selected = args.memory.files
    .map((file) => ({ file, ...scoreFile(file, {
      targetPath: args.item.path,
      prompt: args.prompt,
      itemImports: args.item.imports,
      includeConfigs: true,
    }) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.file.path.localeCompare(b.file.path))

  return selected.slice(0, args.maxFiles ?? 8)
}

export function selectCodeProjectMemoryPromptContext(args: {
  memory: CodeProjectMemory
  prompt: string
  maxFiles?: number
}): CodeProjectMemorySelection[] {
  return args.memory.files
    .map((file) => ({ file, ...scoreFile(file, {
      targetPath: '',
      prompt: args.prompt,
      itemImports: [],
      includeConfigs: false,
    }) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.file.path.localeCompare(b.file.path))
    .slice(0, args.maxFiles ?? 8)
}
