import type { CodeFile, CodeProject, CriticFn, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'
import { bracketBalanceIgnoringLiterals } from './codeLexicalAnalysis.ts'
import { isHtmlLike, isPyLike, isTsLike } from './codeStaticCriticShared.ts'
import { parseCodeWithTreeSitter, resolveTreeSitterLanguage } from './codeTreeSitterAst.ts'

// --- 1. Syntax sanity critic -----------------------------------------------
// WS8: validite syntaxique par AST REEL (tree-sitter) pour les langages
// supportes, avec repli sur l analyse lexicale (equilibrage de blocs ignorant
// les litteraux) quand le langage n est pas couvert ou que le WASM est
// indisponible. Remplace l illusion "bracket-balance regex" par un vrai parse.

function bracketBalance(content: string): { ok: boolean; diff: number; kind: string } {
  return bracketBalanceIgnoringLiterals(content)
}

/**
 * Verdict de validite syntaxique par AST.
 * - { handled:true, error:true }  -> le parser a trouve une erreur de syntaxe.
 * - { handled:true, error:false } -> le parser confirme un code valide.
 * - { handled:false }             -> AST indisponible (langage non couvert ou
 *   WASM non charge): l appelant retombe sur l analyse lexicale.
 */
async function astSyntaxOutcome(file: CodeFile): Promise<{
  handled: boolean
  error: boolean
  grammar: string
  where: string
}> {
  const lang = resolveTreeSitterLanguage(file.name, file.language)
  if (!lang) return { handled: false, error: false, grammar: '', where: '' }
  const parsed = await parseCodeWithTreeSitter(file.content, lang)
  if (!parsed.ok) return { handled: false, error: false, grammar: lang, where: '' }
  // La position exacte change tout: « erreur de syntaxe » faisait relire 200
  // lignes au modele, « ligne 34 colonne 25, pres de <tel texte> » se corrige.
  const at = parsed.errorLocation
  const where = at
    ? `:${at.line}:${at.column} — ${at.kind === 'MISSING' ? 'element manquant' : 'jeton inattendu'}${at.snippet ? ` pres de: ${at.snippet}` : ''}`
    : ''
  return { handled: true, error: parsed.hasError, grammar: lang, where }
}

// Le JSX n est pas du JavaScript pour un compteur de blocs: dans un texte JSX,
// `'` `"` `{` `(` sont des CARACTERES. Un compteur lexical ne peut pas etre sur
// sur du JSX — mesure reelle: 5 composants React valides declares "parens non
// equilibres" a cause d apostrophes francaises (« Rue de l'Atelier »), 9 passes
// de correction perdues a chasser un bug inexistant. Quand l AST manque sur un
// fichier JSX, on SIGNALE sans BLOQUER: une heuristique qui ne sait pas lire la
// langue du fichier n a pas le droit de mettre la note de compilation a zero.
function isJsxLikeFile(file: CodeFile): boolean {
  return /\.[jt]sx$/i.test(file.name) || /^(tsx|jsx)$/i.test(file.language || '')
}

function lexicalBracketIssues(file: CodeFile): CritiqueIssue[] {
  if (!isTsLike(file.language) && !isHtmlLike(file.language)) return []
  const bal = bracketBalance(file.content)
  if (bal.ok) return []
  const jsx = isJsxLikeFile(file)
  return [{
    axis: 'compile',
    severity: jsx ? 'warn' : 'block',
    message: jsx
      ? `${file.name}: ${bal.kind} possiblement non équilibrés (diff ${bal.diff}, analyse lexicale sans AST — non bloquant sur du JSX)`
      : `${file.name}: ${bal.kind} non équilibrés (diff ${bal.diff})`,
    location: { file: file.name },
    suggestion: 'Vérifie les blocs ouverts/fermés.',
  }]
}

function nonBracketSyntaxIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
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
  const issues: CritiqueIssue[] = []
  for (const file of project.files) {
    // Verifications non-syntaxiques (fichier vide, import incomplet, indent Python).
    issues.push(...nonBracketSyntaxIssues(file))

    // Validite syntaxique: AST reel prioritaire, repli lexical si indisponible.
    const ast = await astSyntaxOutcome(file)
    if (ast.handled) {
      if (ast.error) {
        issues.push({
          axis: 'compile',
          severity: 'block',
          message: `${file.name}${ast.where} — erreur de syntaxe (analyse AST tree-sitter ${ast.grammar})`,
          location: { file: file.name },
          suggestion: ast.where
            ? 'Corrige a CETTE position: la ligne et la colonne viennent du parser, elles sont exactes.'
            : 'Le fichier ne parse pas comme du code valide — corrige la syntaxe.',
        })
      }
    } else {
      issues.push(...lexicalBracketIssues(file))
    }
  }
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const filesChecked = project.files.length || 1
  // Score proportional to # of clean files.
  const score = blockers > 0 ? 0 : Math.max(0, 1 - (errors / filesChecked) * 0.5)
  return buildReport({ compile: score }, issues)
}
