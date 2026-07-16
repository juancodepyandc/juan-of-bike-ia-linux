import { maskCodeLiterals } from './codeLexicalAnalysis.ts'

const HALSTEAD_LANGUAGES = new Set([
  'ts', 'tsx', 'js', 'jsx', 'typescript', 'javascript', 'rs', 'rust', 'go', 'golang',
  'swift', 'kt', 'kts', 'kotlin', 'dart', 'java', 'cpp', 'cc', 'cxx', 'c++',
  'c', 'h', 'hpp', 'cs', 'csharp',
])

function supportsHalstead(language: string) {
  return HALSTEAD_LANGUAGES.has(language.toLowerCase())
}

// --- Import graph + cycle detection ---------------------------------------

export type ImportEdge = { from: string; to: string }
export type ImportGraph = {
  edges: ImportEdge[]
  cycles: string[][]
}

const IMPORT_PATH_RE = /^import[^'"]*from\s+['"]([^'"]+)['"]/gm

/**
 * Résout un import path relatif vers un nom de fichier connu.
 * - './b' + dossier 'src/' → 'src/b.ts' ou 'b.ts' selon ce qui existe.
 * - Tente plusieurs extensions et .index.
 */
function resolveImportPath(from: string, importPath: string, knownNames: Set<string>): string | null {
  if (!importPath.startsWith('.')) return null // skip externals
  const fromDir = from.replace(/[^/]+$/, '')
  // normalise '../' '.' '/'
  const candidate = (fromDir + importPath).replace(/\/\.\//g, '/').replace(/[^/]+\/\.\.\//g, '')
  const tries = [
    candidate,
    candidate + '.ts',
    candidate + '.tsx',
    candidate + '.js',
    candidate + '/index.ts',
  ]
  for (const t of tries) {
    if (knownNames.has(t)) return t
    // Cas test : files = [{name: 'a.ts', ...}], import './b' depuis a.ts → on cherche 'b.ts'.
    const stripDir = t.replace(/^\.\//, '')
    if (knownNames.has(stripDir)) return stripDir
  }
  return null
}

export function buildImportGraph(files: Array<{ name: string; content: string }>): ImportGraph {
  const edges: ImportEdge[] = []
  const knownNames = new Set(files.map((f) => f.name))
  for (const f of files) {
    let m: RegExpExecArray | null
    const re = new RegExp(IMPORT_PATH_RE)
    while ((m = re.exec(f.content)) != null) {
      const resolved = resolveImportPath(f.name, m[1], knownNames) ?? m[1]
      edges.push({ from: f.name, to: resolved })
    }
  }
  // Détection de cycles via DFS.
  const adj = new Map<string, string[]>()
  for (const e of edges) {
    if (!adj.has(e.from)) adj.set(e.from, [])
    adj.get(e.from)!.push(e.to)
  }
  const cycles: string[][] = []
  const WHITE = 0, GREY = 1, BLACK = 2
  const color = new Map<string, number>()
  const stack: string[] = []
  for (const node of adj.keys()) color.set(node, WHITE)

  function visit(u: string) {
    color.set(u, GREY)
    stack.push(u)
    for (const v of adj.get(u) ?? []) {
      if (color.get(v) === GREY) {
        const startIdx = stack.indexOf(v)
        if (startIdx >= 0) cycles.push([...stack.slice(startIdx), v])
      } else if (color.get(v) !== BLACK && adj.has(v)) {
        visit(v)
      }
    }
    stack.pop()
    color.set(u, BLACK)
  }
  for (const node of adj.keys()) {
    if (color.get(node) === WHITE) visit(node)
  }
  return { edges, cycles }
}

// --- Halstead metrics -----------------------------------------------------

const TS_OPERATORS = new Set([
  '+', '-', '*', '/', '%', '=', '==', '===', '!=', '!==', '<', '>', '<=', '>=',
  '&&', '||', '!', '?', ':', '&', '|', '^', '~', '<<', '>>', '>>>',
  '+=', '-=', '*=', '/=', '%=',
  '++', '--',
  '=>',
])

export type HalsteadMetrics = {
  /** Nombre d'opérateurs distincts. */
  n1: number
  /** Nombre d'opérandes distincts. */
  n2: number
  /** Nombre total d'opérateurs. */
  N1: number
  /** Nombre total d'opérandes. */
  N2: number
  vocabulary: number
  length: number
  /** Volume = length × log2(vocabulary). */
  volume: number
  /** Difficulty = (n1/2) × (N2/n2). */
  difficulty: number
  /** Effort = difficulty × volume. */
  effort: number
  /** Bugs prédits = volume / 3000 (Halstead). */
  predictedBugs: number
}

export function computeHalstead(content: string, lang: string): HalsteadMetrics {
  if (!supportsHalstead(lang)) {
    return { n1: 0, n2: 0, N1: 0, N2: 0, vocabulary: 0, length: 0, volume: 0, difficulty: 0, effort: 0, predictedBugs: 0 }
  }
  const stripped = maskCodeLiterals(content)
  const operatorsSeen = new Map<string, number>()
  const operandsSeen = new Map<string, number>()

  // Tokenize: opérateurs et identifiers + nombres.
  const opRegex = /([+\-*/%=!<>&|^~?:]+|\(|\)|\{|\}|\[|\]|;|,)/g
  const idRegex = /\b([A-Za-z_$][A-Za-z0-9_$]*)\b/g
  const numRegex = /\b(\d+(?:\.\d+)?)\b/g

  let m: RegExpExecArray | null
  while ((m = opRegex.exec(stripped)) != null) {
    const op = m[1]
    if (TS_OPERATORS.has(op) || op.length === 1) {
      operatorsSeen.set(op, (operatorsSeen.get(op) ?? 0) + 1)
    }
  }
  while ((m = idRegex.exec(stripped)) != null) {
    operandsSeen.set(m[1], (operandsSeen.get(m[1]) ?? 0) + 1)
  }
  while ((m = numRegex.exec(stripped)) != null) {
    operandsSeen.set(m[1], (operandsSeen.get(m[1]) ?? 0) + 1)
  }

  const n1 = operatorsSeen.size
  const n2 = operandsSeen.size
  const N1 = Array.from(operatorsSeen.values()).reduce((a, b) => a + b, 0)
  const N2 = Array.from(operandsSeen.values()).reduce((a, b) => a + b, 0)
  const vocabulary = n1 + n2
  const length = N1 + N2
  const volume = vocabulary > 0 ? length * Math.log2(vocabulary) : 0
  const difficulty = n2 > 0 ? (n1 / 2) * (N2 / n2) : 0
  const effort = difficulty * volume
  const predictedBugs = volume / 3000
  return { n1, n2, N1, N2, vocabulary, length, volume, difficulty, effort, predictedBugs }
}
