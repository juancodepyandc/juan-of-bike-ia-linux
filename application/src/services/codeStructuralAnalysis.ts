// Analyses structurelles avancées sur du code TS/JS/Python/Rust/Go/Java/C++/
// Swift/Kotlin/Dart avec scanner lexical partage.
// Niveau "principal engineer" qui examine la PR pendant la code review.
//
// 4 analyses :
//   1. Complexité cyclomatique de McCabe (par fonction)
//   2. Dead code / variables non utilisées
//   3. Imports graph + détection de cycles
//   4. Halstead metrics (estimation effort + bugs prédits)

import { findMatchingBraceLine, maskCodeLiterals } from './codeLexicalAnalysis.ts'
export { buildImportGraph, computeHalstead } from './codeStructuralMetrics.ts'
export type { HalsteadMetrics, ImportEdge, ImportGraph } from './codeStructuralMetrics.ts'

export type FunctionComplexity = {
  name: string
  startLine: number
  endLine: number
  cyclomaticComplexity: number
  /** Catégorie McCabe. */
  rating: 'simple' | 'modéré' | 'complexe' | 'très-complexe' | 'ingérable'
}

const CONTROL_FLOW_NAMES = new Set(['if', 'for', 'while', 'switch', 'catch', 'return', 'sizeof', 'new', 'delete', 'else'])

function isTsLikeLang(lang: string): boolean {
  return ['ts', 'tsx', 'js', 'jsx', 'typescript', 'javascript'].includes(lang.toLowerCase())
}
function isPyLikeLang(lang: string): boolean {
  return ['py', 'python'].includes(lang.toLowerCase())
}
function isRustLikeLang(lang: string): boolean {
  return ['rs', 'rust'].includes(lang.toLowerCase())
}
function isGoLikeLang(lang: string): boolean {
  return ['go', 'golang'].includes(lang.toLowerCase())
}
function isSwiftLikeLang(lang: string): boolean {
  return ['swift'].includes(lang.toLowerCase())
}
function isKotlinLikeLang(lang: string): boolean {
  return ['kt', 'kts', 'kotlin'].includes(lang.toLowerCase())
}
function isDartLikeLang(lang: string): boolean {
  return ['dart'].includes(lang.toLowerCase())
}
function isCFamilyLang(lang: string): boolean {
  return ['java', 'cpp', 'cc', 'cxx', 'c++', 'c', 'h', 'hpp', 'cs', 'csharp'].includes(lang.toLowerCase())
}
function isBraceFunctionLang(lang: string): boolean {
  return isTsLikeLang(lang)
    || isRustLikeLang(lang)
    || isGoLikeLang(lang)
    || isSwiftLikeLang(lang)
    || isKotlinLikeLang(lang)
    || isDartLikeLang(lang)
    || isCFamilyLang(lang)
}

function functionNameForLine(line: string, lang: string): string | null {
  if (isTsLikeLang(lang)) {
    const m = /^\s*(?:export\s+default\s+)?(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{|^\s+(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::[^{]+)?\s*\{|^\s+(?:(?:public|private|protected|static|override|readonly|async)\s+)*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::[^{]+)?\s*\{/.exec(line)
    return m ? (m[1] || m[2] || m[3] || m[4] || 'anonymous') : null
  }
  if (isRustLikeLang(lang)) {
    const m = /^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+([A-Za-z_]\w*)\s*(?:<[^>{}]*>)?\s*\(/.exec(line)
    return m?.[1] ?? null
  }
  if (isGoLikeLang(lang)) {
    const m = /^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(/.exec(line)
    return m?.[1] ?? null
  }
  if (isSwiftLikeLang(lang)) {
    const m = /^\s*(?:(?:public|private|internal|fileprivate|open|static|mutating|override|final|class)\s+)*func\s+([A-Za-z_]\w*)\s*\(/.exec(line)
    return m?.[1] ?? null
  }
  if (isKotlinLikeLang(lang)) {
    const m = /^\s*(?:(?:public|private|protected|internal|override|suspend|inline|tailrec|operator)\s+)*fun\s+(?:[A-Za-z_][\w.<>]*\.)?([A-Za-z_]\w*)\s*\(/.exec(line)
    return m?.[1] ?? null
  }
  if (isDartLikeLang(lang)) {
    const m = /^\s*(?:(?:static|external|async|sync)\s+)*(?:[A-Za-z_<>,?][\w<>,?\s]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:async\s*)?(?:\{|$)/.exec(line)
    return m && !CONTROL_FLOW_NAMES.has(m[1]) ? m[1] : null
  }
  if (isCFamilyLang(lang)) {
    const m = /^\s*(?:template\s*<[^>]+>\s*)?(?:(?:public|private|protected|static|final|virtual|override|inline|constexpr|const|async|extern|friend|synchronized|native|abstract)\s+)*(?:[\w:<>\[\],*&?\s]+\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:->\s*[\w:<>\[\],*&?\s]+)?\s*(?:\{|$)/.exec(line)
    return m && !CONTROL_FLOW_NAMES.has(m[1]) ? m[1] : null
  }
  return null
}

/**
 * Calcule la complexité cyclomatique par fonction. McCabe : 1 + nombre de
 * branches indépendantes dans le control flow.
 */
export function analyzeCyclomaticComplexity(content: string, lang: string): FunctionComplexity[] {
  const out: FunctionComplexity[] = []
  const lines = content.split(/\r?\n/)

  if (isBraceFunctionLang(lang)) {
    const maskedLines = maskCodeLiterals(content).split(/\r?\n/)
    for (let i = 0; i < lines.length; i += 1) {
      const name = functionNameForLine(maskedLines[i] ?? '', lang)
      if (!name) continue
      const endLine = findMatchingBraceLine(lines, i)
      if (endLine === -1) continue
      const body = lines.slice(i, endLine + 1).join('\n')
      const cc = countCStyleComplexity(body)
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

function countCStyleComplexity(body: string): number {
  const stripped = maskCodeLiterals(body)
  let cc = 1
  const patterns: RegExp[] = [
    /\bif\b/g,
    /\belse\s+if\b/g,
    /\bfor\b/g,
    /\bwhile\b/g,
    /\bcase\s+/g,
    /\bcatch\b/g,
    /\bmatch\b/g,
    /\bselect\b/g,
    /\bwhen\b/g,
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
