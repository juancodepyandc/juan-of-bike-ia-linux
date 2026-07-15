import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { isHtmlLike, isTsLike, type StaticRule } from './codeStaticCriticShared.ts'

// --- 4. Accessibility critic (HTML / JSX) -----------------------------------

const A11Y_RULES: StaticRule[] = [
  {
    pattern: /<img\b(?![^>]*\balt\s*=)[^>]*>/i,
    message: 'Image sans attribut alt',
    severity: 'error',
    suggestion: 'Ajouter alt="" si décoratif, sinon une description.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<button\b(?![^>]*aria-label)[^>]*>\s*<(?:svg|i)\b/i,
    message: 'Bouton icon-only sans aria-label',
    severity: 'warn',
    suggestion: 'Ajouter aria-label décrivant l\'action.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<a\b(?![^>]*href)[^>]*onClick/i,
    message: '<a> sans href + onClick = pas accessible clavier',
    severity: 'error',
    suggestion: 'Utiliser <button> pour les actions, garder <a> pour la navigation.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<input\b(?![^>]*(?:aria-label|aria-labelledby|placeholder))[^>]*>/i,
    message: 'Input sans label ni aria-label ni placeholder',
    severity: 'warn',
    suggestion: 'Associer un <label htmlFor> ou ajouter aria-label.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
]

function fileA11yIssues(file: CodeFile): CritiqueIssue[] {
  const out: CritiqueIssue[] = []
  for (const rule of A11Y_RULES) {
    if (!rule.appliesTo(file)) continue
    const lines = file.content.split(/\r?\n/)
    for (let i = 0; i < lines.length; i += 1) {
      if (rule.pattern.test(lines[i])) {
        out.push({
          axis: 'accessibility',
          severity: rule.severity,
          message: `${file.name}:${i + 1} — ${rule.message}`,
          location: { file: file.name, line: i + 1 },
          suggestion: rule.suggestion,
        })
        break
      }
    }
  }
  return out
}

export const accessibilityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileA11yIssues)
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  const score = Math.max(0, 1 - errors * 0.15 - warns * 0.05)
  return buildReport({ accessibility: score }, issues)
}
