// Scanner lexical leger pour les critics statiques.
// Il masque les commentaires, strings, templates et regex en gardant les
// retours ligne, afin que les analyses structurelles travaillent sur le code.

export type BracketBalanceResult = {
  ok: boolean
  diff: number
  kind: string
}

type LexState = 'code' | 'line-comment' | 'block-comment' | 'single' | 'double' | 'template' | 'regex'

const REGEX_PREFIX_TAIL_RE = /\b(?:return|throw|case|delete|typeof|void|yield|await|in|of)\s*$/

function maskedChar(ch: string): string {
  return ch === '\n' || ch === '\r' ? ch : ' '
}

function canStartRegexLiteral(lastSignificant: string, codeTail: string): boolean {
  if (!lastSignificant) return true
  if ('([{=,:;!&|?{}+-*%^~<>'.includes(lastSignificant)) return true
  return REGEX_PREFIX_TAIL_RE.test(codeTail)
}

/**
 * Remplace les zones non-code par des espaces, tout en conservant la longueur
 * et les retours ligne. Les templates sont masques en entier: cela evite que
 * `${...}` perturbe les heuristiques de balance d'accolades.
 */
export function maskCodeLiterals(content: string): string {
  let state: LexState = 'code'
  let out = ''
  let escaped = false
  let regexCharClass = false
  let lastSignificant = ''
  let codeTail = ''

  const appendCode = (ch: string) => {
    out += ch
    codeTail = (codeTail + ch).slice(-64)
    if (!/\s/.test(ch)) lastSignificant = ch
  }

  for (let i = 0; i < content.length; i += 1) {
    const ch = content[i]
    const next = content[i + 1] ?? ''

    if (state === 'line-comment') {
      out += maskedChar(ch)
      if (ch === '\n') state = 'code'
      continue
    }

    if (state === 'block-comment') {
      out += maskedChar(ch)
      if (ch === '*' && next === '/') {
        out += ' '
        i += 1
        state = 'code'
      }
      continue
    }

    if (state === 'single' || state === 'double' || state === 'template') {
      out += maskedChar(ch)
      if (escaped) {
        escaped = false
        continue
      }
      if (ch === '\\') {
        escaped = true
        continue
      }
      if ((state === 'single' && ch === "'") || (state === 'double' && ch === '"') || (state === 'template' && ch === '`')) {
        state = 'code'
      }
      continue
    }

    if (state === 'regex') {
      out += maskedChar(ch)
      if (escaped) {
        escaped = false
        continue
      }
      if (ch === '\\') {
        escaped = true
        continue
      }
      if (ch === '[') {
        regexCharClass = true
        continue
      }
      if (ch === ']') {
        regexCharClass = false
        continue
      }
      if (ch === '/' && !regexCharClass) {
        state = 'code'
        regexCharClass = false
      }
      if (ch === '\n') {
        state = 'code'
        regexCharClass = false
      }
      continue
    }

    if (ch === '/' && next === '/') {
      out += '  '
      i += 1
      state = 'line-comment'
      continue
    }
    if (ch === '/' && next === '*') {
      out += '  '
      i += 1
      state = 'block-comment'
      continue
    }
    if (ch === "'") {
      out += ' '
      state = 'single'
      escaped = false
      continue
    }
    if (ch === '"') {
      out += ' '
      state = 'double'
      escaped = false
      continue
    }
    if (ch === '`') {
      out += ' '
      state = 'template'
      escaped = false
      continue
    }
    if (ch === '/' && next !== '/' && next !== '*' && canStartRegexLiteral(lastSignificant, codeTail)) {
      out += ' '
      state = 'regex'
      escaped = false
      regexCharClass = false
      continue
    }

    appendCode(ch)
  }

  return out
}

export function findMatchingBraceLine(lines: string[], startLine: number): number {
  const maskedLines = maskCodeLiterals(lines.join('\n')).split('\n')
  let depth = 0
  let started = false
  for (let i = startLine; i < maskedLines.length; i += 1) {
    for (const ch of maskedLines[i]) {
      if (ch === '{') {
        depth += 1
        started = true
      } else if (ch === '}') {
        depth -= 1
        if (started && depth === 0) return i
      }
    }
  }
  return -1
}

export function bracketBalanceIgnoringLiterals(content: string): BracketBalanceResult {
  const stripped = maskCodeLiterals(content)
  const pairs: Array<[string, string, string]> = [
    ['(', ')', 'parens'],
    ['[', ']', 'brackets'],
    ['{', '}', 'braces'],
  ]
  for (const [open, close, kind] of pairs) {
    let depth = 0
    for (const ch of stripped) {
      if (ch === open) depth += 1
      else if (ch === close) depth -= 1
      if (depth < 0) return { ok: false, diff: depth, kind }
    }
    if (depth !== 0) return { ok: false, diff: depth, kind }
  }
  return { ok: true, diff: 0, kind: '' }
}
