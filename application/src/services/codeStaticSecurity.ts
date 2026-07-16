import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { isHtmlLike, isPyLike, isTsLike } from './codeStaticCriticShared.ts'
import { SECURITY_RULES } from './codeStaticSecurityRules.ts'

type TaintSink = {
  name: string
  severity: CritiqueIssue['severity']
  suggestion: string
}

const TAINT_SOURCE_RE = /\b(?:location(?:\.\w+)?|window\.location(?:\.\w+)?|document\.location(?:\.\w+)?|URLSearchParams|localStorage|sessionStorage|prompt\s*\(|process\.argv|Deno\.args|sys\.argv|os\.environ|input\s*\(|request\.(?:args|form|json|data|values|get_json)|flask\.request|req\.|params\.|query\.|body\.)\b/
const IDENT_RE = /\b[A-Za-z_$][\w$]*\b/g

function lineNumberAt(content: string, index: number): number {
  return content.slice(0, index).split(/\r?\n/).length
}

function cloneGlobal(pattern: RegExp): RegExp {
  const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`
  return new RegExp(pattern.source, flags)
}

function expressionUsesTaint(expr: string, tainted: Set<string>): boolean {
  if (TAINT_SOURCE_RE.test(expr)) return true
  let m: RegExpExecArray | null
  const re = new RegExp(IDENT_RE)
  while ((m = re.exec(expr)) != null) {
    if (tainted.has(m[0])) return true
  }
  return false
}

function assignmentParts(line: string): { name: string; expr: string } | null {
  const ts = /^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(.+)$/.exec(line)
  if (ts) return { name: ts[1], expr: ts[2] }
  const py = /^\s*([A-Za-z_]\w*)\s*=\s*(.+)$/.exec(line)
  if (py && !/^(?:if|while|for|return|import|from|class|def)\b/.test(py[1])) return { name: py[1], expr: py[2] }
  return null
}

function taintSinkForLine(line: string): TaintSink | null {
  if (/\b(?:eval|Function)\s*\(/.test(line)) {
    return {
      name: 'eval/new Function',
      severity: 'block',
      suggestion: 'Ne jamais executer une valeur issue de l utilisateur.',
    }
  }
  if (/(?:\.innerHTML\s*=|document\.write\s*\(|insertAdjacentHTML\s*\()/.test(line)) {
    return {
      name: 'DOM HTML sink',
      severity: 'error',
      suggestion: 'Utiliser textContent ou sanitiser explicitement avant insertion HTML.',
    }
  }
  if (/(?:fetch|axios|request|http\.get|requests\.get)\s*\(/.test(line)) {
    return {
      name: 'network URL sink',
      severity: 'error',
      suggestion: 'Valider la destination par allowlist avant tout appel reseau.',
    }
  }
  if (/(?:execute|query|raw)\s*\(/.test(line)) {
    return {
      name: 'SQL sink',
      severity: 'block',
      suggestion: 'Utiliser des requetes parametrees.',
    }
  }
  if (/(?:exec|spawn|os\.system|subprocess\.(?:run|Popen|call))\s*\(/.test(line)) {
    return {
      name: 'command sink',
      severity: 'block',
      suggestion: 'Passer des arguments separes sans shell, apres validation stricte.',
    }
  }
  if (/(?:window\.location|location\.href|location\.assign)\s*=/.test(line)) {
    return {
      name: 'redirect sink',
      severity: 'error',
      suggestion: 'Limiter les redirections aux destinations autorisees.',
    }
  }
  if (/\.setHeader\s*\(/.test(line)) {
    return {
      name: 'HTTP header sink',
      severity: 'error',
      suggestion: 'Refuser CR/LF et whitelister les valeurs de header.',
    }
  }
  return null
}

function detectTaintIssues(file: CodeFile): CritiqueIssue[] {
  if (!(isTsLike(file.language) || isHtmlLike(file.language) || isPyLike(file.language))) return []
  const issues: CritiqueIssue[] = []
  const tainted = new Set<string>()
  const lines = file.content.split(/\r?\n/)

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const assignment = assignmentParts(line)
    if (assignment && expressionUsesTaint(assignment.expr, tainted)) {
      tainted.add(assignment.name)
    }

    const sink = taintSinkForLine(line)
    if (!sink || !expressionUsesTaint(line, tainted)) continue
    issues.push({
      axis: 'security',
      severity: sink.severity,
      message: `${file.name}:${i + 1} — Data-flow taint: valeur utilisateur vers ${sink.name}`,
      location: { file: file.name, line: i + 1 },
      suggestion: sink.suggestion,
    })
  }

  return issues
}

function fileSecurityIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = detectTaintIssues(file)
  for (const rule of SECURITY_RULES) {
    if (!rule.appliesTo(file)) continue
    // Match sur le contenu complet — gère les patterns multi-lignes
    // (except:\npass, CSRF cross-form). Le numéro de ligne est calculé
    // depuis l'index du match dans le contenu.
    const re = cloneGlobal(rule.pattern)
    let m: RegExpExecArray | null
    while ((m = re.exec(file.content)) != null) {
      const lineNum = lineNumberAt(file.content, m.index)
      issues.push({
        axis: 'security',
        severity: rule.severity,
        message: `${file.name}:${lineNum} — ${rule.message}`,
        location: { file: file.name, line: lineNum },
        suggestion: rule.suggestion,
      })
      if (m[0].length === 0) re.lastIndex += 1
    }
  }
  return issues
}

export const securityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileSecurityIssues)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  let score = 1
  if (blockers > 0) score = 0
  else score = Math.max(0, 1 - errors * 0.2 - warns * 0.05)
  return buildReport({ security: score }, issues)
}
