// ---------------------------------------------------------------------------
// Code Auto-Correction Engine — Rule-based escalation without fixed limits
// Equivalent of the 3D module's buildMeshCorrectionStrategy
// ---------------------------------------------------------------------------

import type { CodeSandboxResult } from './codeSandbox'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ErrorCategory =
  | 'syntax'
  | 'type_error'
  | 'import_missing'
  | 'dependency_missing'
  | 'runtime_unavailable'
  | 'runtime_crash'
  | 'test_failure'
  | 'build_failure'
  | 'config_error'
  | 'permission_error'
  | 'timeout'
  | 'unknown'

export type CorrectionLevel =
  | 'quick_fix'
  | 'targeted_repair'
  | 'partial_rewrite'
  | 'rewrite'
  | 'strategy_change'

export type CorrectionStrategy = {
  level: CorrectionLevel
  escalation: number
  instructions: string
  /** Whether to switch model at this level */
  switchModel: boolean
  /** Whether to search the web for solutions */
  searchWeb: boolean
}

export type CorrectionPass = {
  attempt: number
  score: number
  errors: string[]
  strategy: CorrectionLevel | 'initial'
  modelUsed: string
  resolved: boolean
}

// ---------------------------------------------------------------------------
// Error classification — deterministic pattern matching
// ---------------------------------------------------------------------------

const ERROR_PATTERNS: Array<{ pattern: RegExp; category: ErrorCategory }> = [
  // Syntax
  { pattern: /SyntaxError/i, category: 'syntax' },
  { pattern: /unexpected token/i, category: 'syntax' },
  { pattern: /expected.*got/i, category: 'syntax' },
  { pattern: /parse error/i, category: 'syntax' },
  { pattern: /IndentationError/i, category: 'syntax' },

  // Type errors
  { pattern: /TypeError/i, category: 'type_error' },
  { pattern: /type.*is not assignable/i, category: 'type_error' },
  { pattern: /Property.*does not exist/i, category: 'type_error' },
  { pattern: /Cannot find name/i, category: 'type_error' },
  { pattern: /error TS\d+/i, category: 'type_error' },

  // Import/Module
  { pattern: /Cannot find module/i, category: 'import_missing' },
  { pattern: /Module not found/i, category: 'import_missing' },
  { pattern: /ModuleNotFoundError/i, category: 'import_missing' },
  { pattern: /ImportError/i, category: 'import_missing' },
  { pattern: /No module named/i, category: 'import_missing' },
  { pattern: /Could not resolve/i, category: 'import_missing' },
  { pattern: /unresolved import/i, category: 'import_missing' },

  // Dependency
  { pattern: /npm ERR!/i, category: 'dependency_missing' },
  { pattern: /npm error code EJSONPARSE/i, category: 'config_error' },
  { pattern: /JSONParseError/i, category: 'config_error' },
  { pattern: /Invalid package\.json/i, category: 'config_error' },
  { pattern: /must be actual JSON/i, category: 'config_error' },
  { pattern: /Failed to parse JSON data/i, category: 'config_error' },
  { pattern: /pip.*install/i, category: 'dependency_missing' },
  { pattern: /cargo.*could not compile/i, category: 'dependency_missing' },
  { pattern: /ENOENT.*package\.json/i, category: 'dependency_missing' },
  { pattern: /peer dep/i, category: 'dependency_missing' },

  // Missing runtime / toolchain
  { pattern: /Failed to spawn command/i, category: 'runtime_unavailable' },
  { pattern: /program not found/i, category: 'runtime_unavailable' },
  { pattern: /command not found/i, category: 'runtime_unavailable' },
  { pattern: /is not recognized as an internal or external command/i, category: 'runtime_unavailable' },
  { pattern: /reste indisponible apres preparation automatique/i, category: 'runtime_unavailable' },
  { pattern: /runtime .* introuvable/i, category: 'runtime_unavailable' },

  // Runtime
  { pattern: /ReferenceError/i, category: 'runtime_crash' },
  { pattern: /RangeError/i, category: 'runtime_crash' },
  { pattern: /null is not an object/i, category: 'runtime_crash' },
  { pattern: /undefined is not/i, category: 'runtime_crash' },
  { pattern: /segmentation fault/i, category: 'runtime_crash' },
  { pattern: /panic/i, category: 'runtime_crash' },
  { pattern: /SIGABRT/i, category: 'runtime_crash' },
  { pattern: /core dumped/i, category: 'runtime_crash' },
  { pattern: /stack overflow/i, category: 'runtime_crash' },

  // Test failures
  { pattern: /FAIL/i, category: 'test_failure' },
  { pattern: /AssertionError/i, category: 'test_failure' },
  { pattern: /Expected.*received/i, category: 'test_failure' },
  { pattern: /test.*failed/i, category: 'test_failure' },

  // Build
  { pattern: /Build failed/i, category: 'build_failure' },
  { pattern: /error\[E\d+\]/i, category: 'build_failure' },
  { pattern: /compilation.*failed/i, category: 'build_failure' },
  { pattern: /linker.*error/i, category: 'build_failure' },

  // Config
  { pattern: /EACCES/i, category: 'permission_error' },
  { pattern: /permission denied/i, category: 'permission_error' },

  // Timeout
  { pattern: /timeout/i, category: 'timeout' },
  { pattern: /ETIMEDOUT/i, category: 'timeout' },
]

export function classifyErrors(sandboxResult: CodeSandboxResult): ErrorCategory[] {
  const categories: ErrorCategory[] = []
  const allOutput = sandboxResult.steps
    .filter((s) => !s.ok)
    .map((s) => s.output)
    .join('\n')

  for (const { pattern, category } of ERROR_PATTERNS) {
    if (pattern.test(allOutput) && !categories.includes(category)) {
      categories.push(category)
    }
  }

  if (categories.length === 0) {
    categories.push('unknown')
  }

  return categories
}

// ---------------------------------------------------------------------------
// Correction strategy builder — deterministic, rule-based
// ---------------------------------------------------------------------------

export function buildCorrectionStrategy(
  errorCategories: ErrorCategory[],
  attempt: number,
  correctionLog: CorrectionPass[],
): CorrectionStrategy {
  // Calculate escalation level based on attempt and progress
  const recentScores = correctionLog.slice(-3).map((p) => p.score)
  const isStagnating = recentScores.length >= 3 &&
    Math.max(...recentScores) - Math.min(...recentScores) < 10

  let escalation: number
  if (isStagnating) {
    // Jump escalation when stagnating
    escalation = Math.min(5, attempt)
  } else {
    escalation = Math.min(5, Math.ceil(attempt / 2))
  }

  // Past attempt 5 we stay at escalation 5 ("strategy_change"). To make every
  // attempt bring a GENUINELY different approach (user rule: "plusieurs
  // passes differentes"), we rotate the angle of attack in a 4-step cycle.
  // The base CorrectionStrategy is produced below at level 5; here we just
  // store the rotation so we can append a specific twist to the instructions.
  let rotationInstructions: string | null = null
  if (attempt > 5) {
    const rotationIndex = (attempt - 6) % 4
    switch (rotationIndex) {
      case 0:
        rotationInstructions = [
          'VARIATION 1 — Reecriture complete avec recherche web obligatoire:',
          '- Utilise EXPLICITEMENT les solutions trouvees en ligne',
          '- Reecris chaque fichier a partir des best practices actuelles',
          '- Ne reutilise AUCUNE ligne de code des passes precedentes',
        ].join('\n')
        break
      case 1:
        rotationInstructions = [
          'VARIATION 2 — Changement de stack/framework:',
          '- Le framework actuel cause des problemes recurrents. Change-le.',
          '- Ex: React SPA → Next.js ; Flask → FastAPI ; Express → Fastify',
          '- Ex: TypeScript complex → JavaScript simple',
          '- Garde l intention metier identique, change les outils.',
        ].join('\n')
        break
      case 2:
        rotationInstructions = [
          'VARIATION 3 — Minimum viable radical:',
          '- Reduis le projet AU STRICT MINIMUM pour que la demande principale marche',
          '- Supprime TOUT ce qui est optionnel (tests, config avancee, lint, docs)',
          '- Un seul fichier si possible, ou deux maximum',
          '- Pas de dependances autres que la stdlib si possible',
        ].join('\n')
        break
      case 3:
        rotationInstructions = [
          'VARIATION 4 — Repartir du plan d architecture:',
          '- Oublie les fichiers actuels qui ne passent pas le sandbox',
          '- Reprends le PLAN original point par point',
          '- Code chaque fichier de maniere defensive (try/catch, null-checks, fallbacks)',
          '- Verifie chaque import apres chaque fichier ecrit',
        ].join('\n')
        break
    }
  }

  if (errorCategories.includes('runtime_unavailable')) {
    return {
      level: 'targeted_repair',
      escalation: 1,
      instructions: [
        'Le blocage actuel vient de l environnement et non du code.',
        'Ne reecris pas les fichiers tant que le runtime, compilateur ou package manager manque.',
        'Verifie uniquement les scripts et commandes declares pour qu ils soient coherents avec la stack.',
        'Priorise la detection d un runtime absent, d un binaire manquant ou d une installation incomplete.',
        'Recherche en ligne les instructions d installation pour le runtime manquant.',
      ].join('\n'),
      switchModel: false,
      searchWeb: true,
    }
  }

  // Level 1: Quick fix — simple syntax/import errors
  // TOUJOURS rechercher en ligne — meme les erreurs simples peuvent cacher
  // des incompatibilites de version ou des bugs connus
  if (escalation <= 1 && errorCategories.every((c) => c === 'syntax' || c === 'import_missing' || c === 'type_error')) {
    return {
      level: 'quick_fix',
      escalation,
      instructions: buildQuickFixInstructions(errorCategories),
      switchModel: false,
      searchWeb: true,
    }
  }

  // Level 2: Targeted repair — dependency/config issues
  if (escalation <= 2) {
    return {
      level: 'targeted_repair',
      escalation,
      instructions: buildTargetedRepairInstructions(errorCategories),
      switchModel: escalation >= 2,
      searchWeb: true,
    }
  }

  // Level 3: Partial rewrite — runtime/build errors with web search
  if (escalation <= 3) {
    return {
      level: 'partial_rewrite',
      escalation,
      instructions: buildPartialRewriteInstructions(errorCategories),
      switchModel: true,
      searchWeb: true,
    }
  }

  // Level 4: Full rewrite
  if (escalation <= 4) {
    return {
      level: 'rewrite',
      escalation,
      instructions: [
        'Les corrections precedentes ont echoue a resoudre les problemes.',
        'Reecris COMPLETEMENT les fichiers problematiques.',
        'Simplifie l\'architecture si necessaire.',
        'Utilise des patterns eprouves et stables.',
        'Verifie chaque import, chaque type, chaque dependance.',
      ].join('\n'),
      switchModel: false,  // Pas de swap VRAM — cause #1 de crash PC
      searchWeb: true,
    }
  }

  // Level 5: Strategy change — completely different approach
  const baseInstructions = [
    'TOUTES les tentatives precedentes ont echoue.',
    'Change COMPLETEMENT d\'approche:',
    '- Simplifie radicalement l\'architecture',
    '- Utilise des librairies/frameworks differents si possible',
    '- Reduis le nombre de fichiers au minimum',
    '- Privilegie la fonctionnalite sur l\'elegance',
    '- Si le framework cause des problemes, utilise une alternative plus simple',
    '- Si les tests echouent, corrige ou simplifie les tests',
  ].join('\n')
  return {
    level: 'strategy_change',
    escalation,
    instructions: rotationInstructions
      ? `${baseInstructions}\n\n${rotationInstructions}`
      : baseInstructions,
    // IMPORTANT: pas de switchModel. Swapper un 30B coder ↔ 67B planner ↔ 26B
    // analyzer entre deux passes force un rechargement VRAM qui crashe le PC
    // (Memory Guard documente). On reste sur le code model pour tout.
    switchModel: false,
    searchWeb: true,
  }
}

// ---------------------------------------------------------------------------
// Instruction builders per level
// ---------------------------------------------------------------------------

function buildQuickFixInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = ['Correction rapide des erreurs detectees:']

  if (categories.includes('syntax')) {
    lines.push('- Corrige les erreurs de syntaxe (parentheses, accolades, points-virgules)')
  }
  if (categories.includes('import_missing')) {
    lines.push('- Corrige les imports manquants ou mal orthographies')
    lines.push('- Verifie que tous les modules importes existent dans le projet')
  }
  if (categories.includes('type_error')) {
    lines.push('- Corrige les erreurs de type (types manquants, incompatibles)')
    lines.push('- Ajoute les declarations de type necessaires')
  }

  return lines.join('\n')
}

function buildTargetedRepairInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = ['Reparation ciblee des erreurs:']

  if (categories.includes('dependency_missing')) {
    lines.push('- Verifie que package.json / requirements.txt contient toutes les dependances')
    lines.push('- Ajoute les dependances manquantes avec les versions correctes')
  }
  if (categories.includes('config_error')) {
    lines.push('- Corrige les fichiers de configuration invalides, surtout package.json, tsconfig.json et les manifests JSON')
    lines.push('- Les fichiers JSON doivent etre du JSON pur: aucun backtick markdown, aucun commentaire, aucune explication autour')
  }
  if (categories.includes('runtime_unavailable')) {
    lines.push('- Le probleme principal est un runtime ou binaire absent: ne refactorise pas le code pour masquer ce symptome')
    lines.push('- Corrige seulement les scripts ou commandes declares si une incoherence evidente existe')
  }
  if (categories.includes('config_error')) {
    lines.push('- Verifie la configuration (tsconfig, vite.config, webpack, etc.)')
    lines.push('- Corrige les options incompatibles')
  }
  if (categories.includes('runtime_crash')) {
    lines.push('- Corrige les erreurs de reference (variables non definies)')
    lines.push('- Ajoute les verifications null/undefined necessaires')
  }

  lines.push('- Ne touche PAS aux fichiers qui fonctionnent deja')

  return lines.join('\n')
}

function buildPartialRewriteInstructions(categories: ErrorCategory[]): string {
  const lines: string[] = [
    'Les corrections simples n\'ont pas suffi.',
    'Reecris les fichiers problematiques en profondeur:',
  ]

  if (categories.includes('build_failure')) {
    lines.push('- Revois completement la configuration de build')
    lines.push('- Verifie la compatibilite des versions de dependances')
  }
  if (categories.includes('test_failure')) {
    lines.push('- Corrige la logique metier pour faire passer les tests')
    lines.push('- Ou corrige les tests s ils sont incorrects')
  }
  if (categories.includes('runtime_crash')) {
    lines.push('- Refactorise la logique qui crash')
    lines.push('- Utilise des patterns plus defensifs')
  }

  lines.push('- Utilise les solutions trouvees en ligne si disponibles')

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Loop continuation logic — plateau detection
// ---------------------------------------------------------------------------

/**
 * Decide si la boucle d auto-correction doit continuer.
 *
 * COMPROMIS entre deux contraintes :
 *   - User rule : "jamais arreter tant qu il n atteint pas son but"
 *   - Realite materielle : chaque passe charge un modele + des processus
 *     sandbox. Apres ~10 passes, la memoire accumulee + les swaps modele
 *     peuvent crasher le PC (historique documente dans project_auroraIA.md).
 *
 * Cap absolu a MAX_CORRECTION_PASSES pour proteger le PC, avec rotation de
 * strategies agressive. La boucle s arrete quand :
 *   1. Score 100 → succes
 *   2. Meme erreur exacte 6+ fois consecutives → boucle prouvee impossible
 *   3. Cap absolu atteint → livraison en l etat avec diagnostic clair
 *
 * Le cap n est PAS un "plateau fixe a 45%" : il est atteint apres avoir
 * reellement tente 4 variations de strategie + recherche web + rescue.
 */
export const MAX_CORRECTION_PASSES = 10

export function shouldContinueLoop(
  correctionLog: CorrectionPass[],
  _currentAttempt: number,
  _errorCategories: ErrorCategory[] = [],
): boolean {
  if (correctionLog.length === 0) return true
  const latestScore = correctionLog[correctionLog.length - 1].score

  // Score parfait → succes
  if (latestScore >= 100) return false

  // Hard cap pour proteger le PC de l accumulation memoire + swaps VRAM
  if (correctionLog.length >= MAX_CORRECTION_PASSES) return false

  // Boucle infinie reelle : meme erreur exacte qui revient 6+ fois consecutives.
  if (correctionLog.length >= 6) {
    const last6Errors = correctionLog.slice(-6).map((p) => p.errors[0] ?? '')
    const normalized = last6Errors.map((e) => e.slice(0, 200).trim())
    if (normalized.every((e) => e.length > 10 && e === normalized[0])) {
      return false
    }
  }

  return true
}
