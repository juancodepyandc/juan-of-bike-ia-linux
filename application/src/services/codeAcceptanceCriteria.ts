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

const ARITH_OPS = ['+', '-', '*', '/'] as const
type ArithOp = (typeof ARITH_OPS)[number]

/**
 * Retourne le premier operateur arithmetique binaire d une expression courte
 * (entre deux operandes), ou null. Sert a comparer l operation REELLEMENT codee
 * a l operateur declare.
 */
function firstBinaryArithmeticOp(expr: string): ArithOp | null {
  // On ignore les operateurs unaires (ex: -1) en exigeant un operande a gauche.
  const match = expr.match(/[A-Za-z0-9_$)\]]\s*([+\-*/])\s*[A-Za-z0-9_$([]/)
  return match ? (match[1] as ArithOp) : null
}

/**
 * WS7 (non-gameable): detecte les operateurs INVERSES dans les deux idiomes
 * dominants de calculatrice — la table `'+' : (a,b) => a - b` et le
 * `case '+': return a - b`. Les criteres regex de PRESENCE laissaient passer une
 * calculatrice qui calcule FAUX (2+2=0). Ici, si un operateur declare est code
 * avec une operation differente, c est un echec. Conservateur: ne se declenche
 * que lorsqu un mapping operateur->expression est clairement analysable (pas de
 * faux positif sur du code non concerne). La verification COMPORTEMENTALE
 * complete (2+2=4 execute) releve du sandbox conteneurise WS7.
 */
export function detectInvertedCalculatorOperators(code: string): string[] {
  const errors: string[] = []
  for (const op of ARITH_OPS) {
    const opClass = op === '/' ? '\\/' : op === '*' ? '\\*' : op === '+' ? '\\+' : '-'
    // Idiome 1: table de fonctions  '<op>': (a, b) => <expr>
    const mapRe = new RegExp(`['"\\\`]${opClass}['"\\\`]\\s*:\\s*(?:function\\s*)?\\([^)]*\\)\\s*=>\\s*\\{?\\s*(?:return\\s+)?([^,;\\n}]+)`, 'g')
    // Idiome 2: switch  case '<op>': [return|x =] <expr>
    const caseRe = new RegExp(`case\\s*['"\\\`]${opClass}['"\\\`]\\s*:\\s*(?:return\\s+|[A-Za-z0-9_$.\\[\\]]+\\s*=\\s*)?([^;\\n]+)`, 'g')
    for (const re of [mapRe, caseRe]) {
      let m: RegExpExecArray | null
      while ((m = re.exec(code)) !== null) {
        const coded = firstBinaryArithmeticOp(m[1])
        if (coded && coded !== op) {
          errors.push(`operateur '${op}' code avec '${coded}' (${m[1].trim().slice(0, 40)})`)
        }
      }
    }
  }
  return errors
}

function calculatorCriteria(code: string): AcceptanceCriterionResult[] {
  const lower = code.toLowerCase()
  const invertedOperators = detectInvertedCalculatorOperators(code)
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
      label: 'Structure des quatre operations arithmetiques presente (structure, pas comportement)',
      category: 'structure',
      ok: hasCalculateFlow && hasArithmetic >= 4,
      detail: `Flux calcul=${hasCalculateFlow ? 'oui' : 'non'}, operations detectees=${hasArithmetic}/4.`,
    },
    {
      // WS7: correction arithmetique — un operateur declare mais code avec une
      // autre operation (2+2 qui soustrait) est un ECHEC, la ou la presence
      // regex seule laissait passer une calculatrice fausse a 100%.
      id: 'calculator-operator-correctness',
      label: 'Aucun operateur arithmetique inverse/mal cable detecte',
      category: 'functional',
      ok: invertedOperators.length === 0,
      detail: invertedOperators.length === 0
        ? 'Aucune inversion d operateur detectee.'
        : `Operateur(s) mal cable(s): ${invertedOperators.join(' ; ')}`,
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
