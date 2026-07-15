import type { CodeFile, CritiqueIssue } from './codeMultiPassCritique.ts'

export type StaticRule = {
  pattern: RegExp
  message: string
  severity: CritiqueIssue['severity']
  suggestion: string
  appliesTo: (file: CodeFile) => boolean
}

// --- Helpers ---------------------------------------------------------------

const TS_LIKE = ['ts', 'tsx', 'jsx', 'js', 'typescript', 'javascript']
const PY_LIKE = ['py', 'python']
const HTML_LIKE = ['html', 'htm']
const CSS_LIKE = ['css', 'scss']

export function isTsLike(lang: string): boolean {
  return TS_LIKE.includes(lang.toLowerCase())
}
export function isPyLike(lang: string): boolean {
  return PY_LIKE.includes(lang.toLowerCase())
}
export function isHtmlLike(lang: string): boolean {
  return HTML_LIKE.includes(lang.toLowerCase())
}
export function isCssLike(lang: string): boolean {
  return CSS_LIKE.includes(lang.toLowerCase())
}

export function countLines(content: string): number {
  return content.split(/\r?\n/).length
}

export function normalizedName(name: string): string {
  return name.replace(/\\/g, '/').replace(/^\.\//, '').toLowerCase()
}
