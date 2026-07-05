// Analyses structurelles avancées sur du code TS/JS/Python sans AST complet.
// Niveau "principal engineer" qui examine la PR pendant la code review.
//
// 4 analyses :
//   1. Complexité cyclomatique de McCabe (par fonction)
//   2. Dead code / variables non utilisées
//   3. Imports graph + détection de cycles
//   4. Halstead metrics (estimation effort + bugs prédits)

export type FunctionComplexity = {
  name: string
  startLine: number
  endLine: number
  cyclomaticComplexity: number
  /** Catégorie McCabe. */
  rating: 'simple' | 'modéré' | 'complexe' | 'très-complexe' | 'ingérable'
}

const TS_BRANCH_KEYWORDS = [
  'if', 'else if', 'else', 'for', 'while', 'do', 'case', 'catch',
  '&&', '||', '\\?\\?', '\\?[^.]',
]
const PY_BRANCH_KEYWORDS = [
  'if', 'elif', 'else', 'for', 'while', 'except', 'and', 'or',
]

function isTsLikeLang(lang: string): boolean {
  return ['ts', 'tsx', 'js', 'jsx', 'typescript', 'javascript'].includes(lang.toLowerCase())
}
function isPyLikeLang(lang: string): boolean {
  return ['py', 'python'].includes(lang.toLowerCase())
}

/**
 * Calcule la complexité cyclomatique par fonction. McCabe : 1 + nombre de
 * branches indépendantes dans le control flow.
 */
export function analyzeCyclomaticComplexity(content: string, lang: string): FunctionComplexity[] {
  const out: FunctionComplexity[] = []
  const lines = content.split(/\r?\n/)

  if (isTsLikeLang(lang)) {
    // Heuristique : trouve les déclarations de fonction par regex, puis
    // scanne le corps (balanced braces).
    const fnStart = /^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(|^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*\{|^\s+(\w+)\s*\([^)]*\)\s*\{|^\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{|^\s+(?:public|private|protected)\s+(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{/
    for (let i = 0; i < lines.length; i += 1) {
      const m = fnStart.exec(lines[i])
      if (!m) continue
      const name = m[1] || m[2] || m[3] || m[4] || m[5] || 'anonymous'
      const endLine = findClosingBrace(lines, i)
      if (endLine === -1) continue
      const body = lines.slice(i, endLine + 1).join('\n')
      const cc = countTsComplexity(body)
      out.push({
        name,
        startLine: i + 1,
        endLine: endLine + 1,
        cyclomaticComplexity: cc,
        rating: ratingFor(cc),
      })
    }
  } else if (isPyLikeLang(lang)) {
    // Python : `def name(`. Le bloc se termine quand l'indentation revient
    // au même niveau ou plus bas.
    for (let i = 0; i < lines.length; i += 1) {
      const m = /^(\s*)(?:async\s+)?def\s+(\w+)\s*\(/.exec(lines[i])
      if (!m) continue
      const indent = m[1].length
      const name = m[2]
      let end = i
      for (let j = i + 1; j < lines.length; j += 1) {
        const lm = /^(\s*)\S/.exec(lines[j])
        if (lm && lm[1].length <= indent) {
          end = j - 1
          break
        }
        end = j
      }
      const body = lines.slice(i, end + 1).join('\n')
      const cc = countPyComplexity(body)
      out.push({
        name,
        startLine: i + 1,
        endLine: end + 1,
        cyclomaticComplexity: cc,
        rating: ratingFor(cc),
      })
    }
  }

  return out
}

function findClosingBrace(lines: string[], startLine: number): number {
  let depth = 0
  let started = false
  for (let i = startLine; i < lines.length; i += 1) {
    for (const ch of lines[i]) {
      if (ch === '{') { depth += 1; started = true }
      else if (ch === '}') {
        depth -= 1
        if (started && depth === 0) return i
      }
    }
  }
  return -1
}

function countTsComplexity(body: string): number {
  // Strip strings + comments first.
  const stripped = body
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '')
    .replace(/`(?:\\.|[^`\\])*`/g, '``')
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
  let cc = 1
  const patterns: RegExp[] = [
    /\bif\s*\(/g,
    /\belse\s+if\s*\(/g,
    /\bfor\s*\(/g,
    /\bwhile\s*\(/g,
    /\bcase\s+/g,
    /\bcatch\s*\(/g,
    /&&/g,
    /\|\|/g,
    /\?\?/g,
    /\?[^.]/g, // ternaire ?, mais exclure ?. (optional chain)
  ]
  for (const p of patterns) {
    const matches = stripped.match(p)
    if (matches) cc += matches.length
  }
  return cc
}

function countPyComplexity(body: string): number {
  const stripped = body
    .replace(/#[^\n]*/g, '')
    .replace(/"""[\s\S]*?"""/g, '')
    .replace(/'''[\s\S]*?'''/g, '')
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
  let cc = 1
  const patterns: RegExp[] = [
    /\bif\s+/g,
    /\belif\s+/g,
    /\bfor\s+/g,
    /\bwhile\s+/g,
    /\bexcept\b/g,
    /\band\b/g,
    /\bor\b/g,
  ]
  for (const p of patterns) {
    const m = stripped.match(p)
    if (m) cc += m.length
  }
  return cc
}

function ratingFor(cc: number): FunctionComplexity['rating'] {
  if (cc <= 10) return 'simple'
  if (cc <= 20) return 'modéré'
  if (cc <= 40) return 'complexe'
  if (cc <= 60) return 'très-complexe'
  return 'ingérable'
}

// --- Dead code detector ---------------------------------------------------

export type DeadCodeIssue = {
  kind: 'unused-import' | 'unused-variable' | 'unreachable' | 'always-true' | 'always-false'
  symbol: string
  line: number
}

export function detectDeadCode(content: string, lang: string): DeadCodeIssue[] {
  const out: DeadCodeIssue[] = []
  if (!isTsLikeLang(lang)) return out
  const lines = content.split(/\r?\n/)

  // Imports : `import { X, Y } from 'lib'` ou `import X from 'lib'` ou `import * as X`
  const imports: Array<{ name: string; line: number }> = []
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const namedImport = /^import\s+(?:type\s+)?\{([^}]+)\}\s+from/.exec(line)
    if (namedImport) {
      const names = namedImport[1].split(',').map((s) => s.trim().split(/\s+as\s+/).pop()!.trim()).filter(Boolean)
      for (const n of names) imports.push({ name: n, line: i + 1 })
    }
    const defaultImport = /^import\s+(\w+)\s+from/.exec(line)
    if (defaultImport) imports.push({ name: defaultImport[1], line: i + 1 })
    const nsImport = /^import\s+\*\s+as\s+(\w+)\s+from/.exec(line)
    if (nsImport) imports.push({ name: nsImport[1], line: i + 1 })
  }

  // Strip ALL imports + comments + strings for usage detection.
  const stripped = content
    .replace(/^import[^;\n]*$/gm, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '')
    .replace(/`(?:\\.|[^`\\])*`/g, '``')
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/'(?:\\.|[^'\\])*'/g, "''")

  for (const imp of imports) {
    const re = new RegExp(`\\b${escapeReg(imp.name)}\\b`, 'g')
    const matches = stripped.match(re) ?? []
    if (matches.length === 0) {
      out.push({ kind: 'unused-import', symbol: imp.name, line: imp.line })
    }
  }

  // Always-true/false : `if (true)` `if (false)`
  for (let i = 0; i < lines.length; i += 1) {
    if (/\bif\s*\(\s*true\s*\)/.test(lines[i])) out.push({ kind: 'always-true', symbol: 'if (true)', line: i + 1 })
    if (/\bif\s*\(\s*false\s*\)/.test(lines[i])) out.push({ kind: 'always-false', symbol: 'if (false)', line: i + 1 })
  }

  // Unreachable : code après return/throw/continue/break à indent identique.
  for (let i = 0; i < lines.length - 1; i += 1) {
    const cur = lines[i]
    const next = lines[i + 1]
    const indent = (cur.match(/^\s*/) ?? [''])[0]
    const nextIndent = (next.match(/^\s*/) ?? [''])[0]
    if (indent !== nextIndent) continue
    if (next.trim().length === 0 || next.trim().startsWith('}') || next.trim().startsWith('//')) continue
    if (/^\s*(return|throw|continue|break)\b/.test(cur)) {
      out.push({ kind: 'unreachable', symbol: next.trim().slice(0, 40), line: i + 2 })
    }
  }
  return out
}

function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
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
  if (!isTsLikeLang(lang)) {
    return { n1: 0, n2: 0, N1: 0, N2: 0, vocabulary: 0, length: 0, volume: 0, difficulty: 0, effort: 0, predictedBugs: 0 }
  }
  const stripped = content
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '')
    .replace(/`(?:\\.|[^`\\])*`/g, '__t__')
    .replace(/"(?:\\.|[^"\\])*"/g, '__s__')
    .replace(/'(?:\\.|[^'\\])*'/g, '__s__')
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
