import type { CodeFile, CodeSandboxStepResult } from './codeSandboxTypes.ts'

export type AcceptanceCategory =
  | 'structure'
  | 'fidelity'
  | 'functional'
  | 'robustness'

export type AcceptanceCriterionResult = {
  id: string
  label: string
  category: AcceptanceCategory
  ok: boolean
  detail: string
}

const CODE_LANGS = new Set([
  'ts', 'tsx', 'js', 'jsx', 'typescript', 'javascript', 'python', 'py',
  'rust', 'rs', 'go', 'java', 'cpp', 'c', 'swift', 'kotlin', 'dart',
  'html', 'css',
])

function isCodeFile(file: CodeFile): boolean {
  const lang = file.language.toLowerCase()
  if (CODE_LANGS.has(lang)) return true
  return /\.(tsx?|jsx?|py|rs|go|java|cpp|cc|cxx|c|swift|kt|dart|html|css)$/i.test(file.name)
}

function joinedCode(files: CodeFile[]): string {
  return files.filter(isCodeFile).map((file) => file.content).join('\n')
}

function hasCalculatorIntent(prompt: string): boolean {
  return /\b(calculatrice|calculator|calculette|four[-\s]?function|4[-\s]?function)\b/i.test(prompt)
}

function hasPlaceholderCode(code: string): boolean {
  return /\b(todo|fixme|placeholder|lorem ipsum|not implemented|coming soon|demo only|mock only)\b/i.test(code)
}

function calculatorCriteria(code: string): AcceptanceCriterionResult[] {
  const lower = code.toLowerCase()
  const hasState = /\b(useState|state|display|currentValue|current|accumulator|operator)\b/i.test(code)
  const hasCalculateFlow = /\b(calculate|compute|evaluate|equals|performOperation|switch\s*\(|case\s+['"`][+\-*/]['"`])\b/i.test(code)
  const hasArithmetic = [
    /[A-Za-z0-9_$)\]]\s*\+\s*[A-Za-z0-9_$([']/,
    /[A-Za-z0-9_$)\]]\s*-\s*[A-Za-z0-9_$([']/,
    /[A-Za-z0-9_$)\]]\s*\*\s*[A-Za-z0-9_$([']/,
    /[A-Za-z0-9_$)\]]\s*\/\s*[A-Za-z0-9_$([']/,
  ].filter((pattern) => pattern.test(code)).length
  const hasEquals = /=|equals|calculate|result|résultat/i.test(code)
  const hasClear = /\b(clear|reset|allClear|effacer|vider)\b|>\s*(?:AC|C)\s*</i.test(code)

  return [
    {
      id: 'calculator-state',
      label: 'La calculatrice conserve un etat de saisie/resultat',
      category: 'functional',
      ok: hasState,
      detail: hasState ? 'Etat detecte.' : 'Aucun etat de calcul/saisie detecte.',
    },
    {
      id: 'calculator-operations',
      label: 'Les quatre operations arithmetiques sont implementees en logique',
      category: 'functional',
      ok: hasCalculateFlow && hasArithmetic >= 4,
      detail: `Flux calcul=${hasCalculateFlow ? 'oui' : 'non'}, operations detectees=${hasArithmetic}/4.`,
    },
    {
      id: 'calculator-equals',
      label: 'Un flux de validation/resultat est present',
      category: 'functional',
      ok: hasEquals,
      detail: hasEquals ? 'Validation/resultat detecte.' : 'Aucun flux egal/resultat detecte.',
    },
    {
      id: 'calculator-clear',
      label: 'Un flux clear/reset est present',
      category: 'robustness',
      ok: hasClear || lower.includes('backspace'),
      detail: hasClear ? 'Clear/reset detecte.' : 'Aucun clear/reset detecte.',
    },
  ]
}

export function evaluateAcceptanceCriteria(prompt: string, files: CodeFile[]): AcceptanceCriterionResult[] {
  const code = joinedCode(files)
  const results: AcceptanceCriterionResult[] = [
    {
      id: 'has-source-code',
      label: 'Le livrable contient du code executable',
      category: 'structure',
      ok: files.some(isCodeFile) && code.trim().length > 0,
      detail: files.some(isCodeFile) ? 'Fichiers code detectes.' : 'Aucun fichier code executable detecte.',
    },
    {
      id: 'no-placeholder-code',
      label: 'Le livrable ne repose pas sur des placeholders',
      category: 'fidelity',
      ok: !hasPlaceholderCode(code),
      detail: hasPlaceholderCode(code) ? 'Placeholder/TODO detecte.' : 'Aucun placeholder evident.',
    },
  ]

  if (hasCalculatorIntent(prompt)) {
    results.push(...calculatorCriteria(code))
  }

  return results
}

export function scoreAcceptanceCriteria(results: AcceptanceCriterionResult[]): number {
  if (results.length === 0) return 100
  const passed = results.filter((result) => result.ok).length
  return Math.round((passed / results.length) * 100)
}

export function formatAcceptanceCriteria(results: AcceptanceCriterionResult[]): string {
  const score = scoreAcceptanceCriteria(results)
  const lines = results.map((result) => {
    const status = result.ok ? 'PASS' : 'FAIL'
    return `[${status}] ${result.id} (${result.category}) - ${result.label}. ${result.detail}`
  })
  return [`acceptance-score=${score}`, ...lines].join('\n')
}

export function buildAcceptanceCriteriaStep(prompt: string, files: CodeFile[]): CodeSandboxStepResult {
  const results = evaluateAcceptanceCriteria(prompt, files)
  return {
    label: 'Tests acceptation Aurora',
    command: 'internal:acceptance-criteria',
    ok: results.every((result) => result.ok),
    output: formatAcceptanceCriteria(results),
  }
}
