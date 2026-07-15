import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { bracketBalanceIgnoringLiterals } from './codeLexicalAnalysis.ts'
import { isHtmlLike, isPyLike, isTsLike } from './codeStaticCriticShared.ts'

// --- 1. Syntax sanity critic -----------------------------------------------
// Vrai parser : non. Mais on attrape les classes d'erreurs visibles
// (parenthèses non équilibrées, JSX mal fermé, indent Python brisé,
// imports incomplets).

function bracketBalance(content: string): { ok: boolean; diff: number; kind: string } {
  return bracketBalanceIgnoringLiterals(content)
}

function syntaxIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  if (isTsLike(file.language) || isHtmlLike(file.language)) {
    const bal = bracketBalance(file.content)
    if (!bal.ok) {
      issues.push({
        axis: 'compile',
        severity: 'block',
        message: `${file.name}: ${bal.kind} non équilibrés (diff ${bal.diff})`,
        location: { file: file.name },
        suggestion: 'Vérifie les blocs ouverts/fermés.',
      })
    }
  }
  // Empty file = suspect.
  if (file.content.trim().length === 0) {
    issues.push({
      axis: 'compile',
      severity: 'error',
      message: `${file.name}: fichier vide`,
      location: { file: file.name },
    })
  }
  // Incomplete imports / dangling commas at top-level (TS).
  if (isTsLike(file.language)) {
    if (/import\s*{\s*$/m.test(file.content) || /import\s+from\s+['"]/.test(file.content)) {
      issues.push({
        axis: 'compile',
        severity: 'error',
        message: `${file.name}: import incomplet détecté`,
        location: { file: file.name },
        suggestion: "Termine la déclaration d'import.",
      })
    }
  }
  // Python : indentation mixte tab/space.
  if (isPyLike(file.language)) {
    if (/^\t/m.test(file.content) && /^ {2,}/m.test(file.content)) {
      issues.push({
        axis: 'compile',
        severity: 'error',
        message: `${file.name}: mélange tab + espaces`,
        location: { file: file.name },
        suggestion: 'Choisis tabs OU espaces, pas les deux.',
      })
    }
  }
  return issues
}

export const syntaxCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(syntaxIssues)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const filesChecked = project.files.length || 1
  // Score proportional to # of clean files.
  const score = blockers > 0 ? 0 : Math.max(0, 1 - (errors / filesChecked) * 0.5)
  return buildReport({ compile: score }, issues)
}
