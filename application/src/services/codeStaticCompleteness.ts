import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'

// --- 5. Deliverable completeness critic ------------------------------------

export function normalizedProjectPaths(project: CodeProject): string[] {
  return project.files.map((f) => f.name.replace(/\\/g, '/').toLowerCase())
}

function isCliLikeIntent(intent: CodeIntent): boolean {
  if (!intent.projectType) return false
  return intent.projectType.startsWith('cli_')
    || intent.projectType.startsWith('system_')
    || intent.projectType === 'script'
    || intent.projectType === 'data_python'
}

function isStaticUiIntent(intent: CodeIntent): boolean {
  if (!intent.projectType) return false
  return intent.projectType === 'static_web' || intent.projectType === 'game_web'
}

function minimumConcreteFiles(intent: CodeIntent): number {
  const expected = Math.max(1, intent.estimatedFileCount || 1)
  if (isStaticUiIntent(intent)) return expected >= 4 ? 3 : Math.min(3, expected)
  if (isCliLikeIntent(intent)) return expected >= 5 ? 4 : Math.min(3, expected)
  if (intent.needsDevServer || intent.needsBundling || intent.projectType.startsWith('spa_')) {
    return expected >= 10 ? Math.max(6, Math.min(8, Math.floor(expected * 0.35))) : Math.min(6, expected)
  }
  return expected >= 10 ? Math.max(5, Math.min(8, Math.floor(expected * 0.35))) : Math.min(4, expected)
}

function deliverableCompletenessIssues(project: CodeProject, intent: CodeIntent): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  if (!intent.projectType || !intent.estimatedFileCount) return issues
  const paths = normalizedProjectPaths(project)
  const fileCount = project.files.length
  const minFiles = minimumConcreteFiles(intent)
  const expected = Math.max(1, intent.estimatedFileCount || 1)

  if (expected >= 5 && fileCount < minFiles) {
    issues.push({
      axis: 'fidelity',
      severity: fileCount <= 1 ? 'block' : 'error',
      message: `Livrable trop petit: ${fileCount} fichier(s) pour environ ${expected} attendus par l'intention ${intent.projectType}`,
      suggestion: `Generer au moins ${minFiles} fichiers reels: point d'entree, configuration, styles, logique metier, donnees/services et verification locale.`,
    })
  }

  if ((intent.needsDevServer || intent.needsBundling || intent.projectType.startsWith('spa_'))
      && !paths.some((p) => p.endsWith('package.json'))) {
    issues.push({
      axis: 'runtime',
      severity: 'block',
      message: `${intent.projectType}: package.json manquant pour une livraison dev-server/tunnel`,
      suggestion: 'Ajouter package.json avec scripts dev/build/preview et dependances declarees.',
    })
  }

  if (intent.projectType === 'desktop_tauri') {
    const hasTauriShell = paths.some((p) => p === 'src-tauri/cargo.toml' || p.endsWith('/src-tauri/cargo.toml'))
      && paths.some((p) => p === 'src-tauri/tauri.conf.json' || p.endsWith('/src-tauri/tauri.conf.json'))
      && paths.some((p) => p === 'src-tauri/src/main.rs' || p.endsWith('/src-tauri/src/main.rs'))
    if (!hasTauriShell) {
      issues.push({
        axis: 'runtime',
        severity: 'block',
        message: 'Application Tauri incomplete: shell Rust/config Tauri manquant',
        suggestion: 'Ajouter src-tauri/Cargo.toml, src-tauri/tauri.conf.json et src-tauri/src/main.rs.',
      })
    }
  }

  if (isCliLikeIntent(intent) && expected >= 5) {
    const joined = project.files.map((f) => f.content).join('\n')
    const hasCliParser = /argparse|click\.|commander|yargs|clap::|cobra\.Command|flag\.|--help/i.test(joined)
    const hasVerification = paths.some((p) => /(^|\/)(test|tests|__tests__)\//.test(p) || /\.test\./.test(p))
      || /pytest|node --test|cargo test|go test|unittest/i.test(joined)
    if (!hasCliParser) {
      issues.push({
        axis: 'fidelity',
        severity: 'error',
        message: 'CLI complete sans parser d arguments / --help detectable',
        suggestion: 'Ajouter un parser CLI, --help, erreurs lisibles et codes de sortie coherents.',
      })
    }
    if (!hasVerification) {
      issues.push({
        axis: 'tests',
        severity: 'warn',
        message: 'CLI complete sans test ni script de verification local detectable',
        suggestion: 'Ajouter tests ou script de verification reproductible.',
      })
    }
  }

  return issues
}

export const deliverableCompletenessCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = deliverableCompletenessIssues(project, intent)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  return buildReport({
    fidelity: Math.max(0, 1 - blockers * 0.5 - errors * 0.25 - warns * 0.05),
    runtime: blockers > 0 ? 0 : 1,
    tests: Math.max(0, 1 - warns * 0.1),
  }, issues)
}
