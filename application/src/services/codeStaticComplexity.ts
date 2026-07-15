import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'

// --- Cyclomatic complexity critic (wraps codeStructuralAnalysis) -----------

/**
 * Critic qui pénalise les fonctions trop complexes (CC > 20). Permet de
 * bloquer une PR sur du code "complexity bomb" qu'un humain ne pourra pas
 * réviser.
 */
export const complexityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const { analyzeCyclomaticComplexity } = await import('./codeStructuralAnalysis.ts')
  const issues: CritiqueIssue[] = []
  let totalFns = 0
  let badFns = 0
  for (const file of project.files) {
    const fns = analyzeCyclomaticComplexity(file.content, file.language)
    totalFns += fns.length
    for (const fn of fns) {
      if (fn.rating === 'ingérable') {
        badFns += 1
        issues.push({
          axis: 'lint',
          severity: 'block',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} ingérable`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Découper la fonction en sous-fonctions (< 10 branches par fonction).',
        })
      } else if (fn.rating === 'très-complexe') {
        badFns += 1
        issues.push({
          axis: 'lint',
          severity: 'error',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} très complexe`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Visez CC < 20.',
        })
      } else if (fn.rating === 'complexe') {
        issues.push({
          axis: 'lint',
          severity: 'warn',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} complexe`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Envisager un découpage.',
        })
      }
    }
  }
  const ratio = totalFns === 0 ? 0 : badFns / totalFns
  const score = Math.max(0, 1 - ratio)
  return buildReport({ lint: score }, issues)
}
