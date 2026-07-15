import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { analyzeCyclomaticComplexity } from './codeStructuralAnalysis.ts'
import { countLines, isPyLike, isTsLike } from './codeStaticCriticShared.ts'

// --- 3. Structure critic ---------------------------------------------------
// Fonctions trop longues, fichier énorme, callback hell, magic numbers
// répétés — indicateurs structurels d'une génération mal pensée.

function countFunctions(content: string, lang: string): { count: number; maxLength: number } {
  const analyzed = analyzeCyclomaticComplexity(content, lang)
  if (analyzed.length > 0) {
    return {
      count: analyzed.length,
      maxLength: Math.max(...analyzed.map((fn) => fn.endLine - fn.startLine + 1)),
    }
  }
  if (isTsLike(lang)) {
    const declRe = /\b(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s+)?\([^)]*\)\s*=>|\w+\s*\([^)]*\)\s*{)/g
    const matches = content.match(declRe) ?? []
    // Approximation : taille = total / count.
    const lines = countLines(content)
    return { count: matches.length, maxLength: matches.length > 0 ? Math.round(lines / matches.length) : lines }
  }
  if (isPyLike(lang)) {
    const lines = content.split(/\r?\n/)
    const defs: number[] = []
    for (let i = 0; i < lines.length; i += 1) {
      if (/^def\s+\w+/.test(lines[i])) defs.push(i)
    }
    if (defs.length === 0) return { count: 0, maxLength: lines.length }
    const gaps: number[] = []
    for (let i = 0; i < defs.length - 1; i += 1) gaps.push(defs[i + 1] - defs[i])
    gaps.push(lines.length - defs[defs.length - 1])
    return { count: defs.length, maxLength: Math.max(...gaps) }
  }
  return { count: 1, maxLength: countLines(content) }
}

function fileStructureIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const lines = countLines(file.content)
  if (lines > 1500) {
    issues.push({
      axis: 'lint',
      severity: 'error',
      message: `${file.name}: fichier énorme (${lines} lignes)`,
      location: { file: file.name },
      suggestion: 'Découper en plusieurs modules.',
    })
  } else if (lines > 600) {
    issues.push({
      axis: 'lint',
      severity: 'warn',
      message: `${file.name}: fichier long (${lines} lignes)`,
      location: { file: file.name },
      suggestion: 'Envisager un découpage.',
    })
  }
  const fn = countFunctions(file.content, file.language)
  if (fn.count > 0 && fn.maxLength > 200) {
    issues.push({
      axis: 'lint',
      severity: 'warn',
      message: `${file.name}: fonction de plus de 200 lignes`,
      location: { file: file.name },
      suggestion: 'Extraire des helpers ou des sous-fonctions.',
    })
  }
  // TS : promesses non-await suspectes
  if (isTsLike(file.language)) {
    const fetchOrphan = /^(?!\s*(?:await|return|void)\s)(?:\s*)fetch\s*\(/m
    if (fetchOrphan.test(file.content) && !/\.then\s*\(/.test(file.content)) {
      issues.push({
        axis: 'runtime',
        severity: 'warn',
        message: `${file.name}: fetch() sans await ni .then`,
        location: { file: file.name },
        suggestion: 'Préfixer par await ou void si fire-and-forget intentionnel.',
      })
    }
  }
  return issues
}

export const structureCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileStructureIssues)
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  const score = Math.max(0, 1 - errors * 0.15 - warns * 0.05)
  return buildReport({ lint: score }, issues)
}
