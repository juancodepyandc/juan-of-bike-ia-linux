// Cause-driven Code auto-correction engine.

import type { CodeSandboxResult } from './codeSandbox'
import { ERROR_PATTERNS, isCorrectionScoreClimbing } from './codeCorrectionErrorPatterns.ts'
import { MAX_CORRECTION_PASSES, MAX_LOCAL_REPAIR_PASSES, computeAdaptiveCorrectionBudget, countModelPasses } from './codeCorrectionBudget.ts'
export { MAX_CORRECTION_PASSES, MAX_LOCAL_REPAIR_PASSES, computeAdaptiveCorrectionBudget }
import { buildPartialRewriteInstructions, buildQuickFixInstructions, buildTargetedRepairInstructions } from './codeCorrectionInstructions.ts'
import { cycleGraceRemaining, detectCorrectionCycle, withCycleDirective } from './codeCorrectionCycle.ts'

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

export type CorrectionLocality =
  | 'single_file'
  | 'multi_file'
  | 'manifest'
  | 'environment'
  | 'test_suite'
  | 'unknown'

export type CorrectionHistorySignal = {
  stagnating: boolean
  repeatedErrorCount: number
  adaptiveBudget: number
}

export type CorrectionStrategy = {
  level: CorrectionLevel
  escalation: number
  cause: ErrorCategory
  locality: CorrectionLocality
  history: CorrectionHistorySignal
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
  /**
   * Passe resolue SANS modele (reparation locale deterministe).
   *
   * Le budget de correction existe pour borner les CHARGEMENTS DE MODELE — la
   * VRAM et la RAM sont la ressource rare, pas les passes. Une reparation
   * locale n en charge aucun. La compter revenait a mesurer autre chose que ce
   * que le plafond protege: mesure sur les runs v124/v125/v126, une passe
   * gratuite sur sept etait deja prelevee sur le budget du modele, et le
   * balayage des reparations deterministes en ajoute d autres.
   */
  localRepairOnly?: boolean
}

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

function normalizeErrorForHistory(error: string): string {
  return error.slice(0, 220).replace(/\s+/g, ' ').trim()
}

function countRepeatedTailErrors(correctionLog: CorrectionPass[]): number {
  const latest = normalizeErrorForHistory(correctionLog[correctionLog.length - 1]?.errors[0] ?? '')
  if (latest.length <= 10) return 0

  let count = 0
  for (let index = correctionLog.length - 1; index >= 0; index--) {
    const current = normalizeErrorForHistory(correctionLog[index]?.errors[0] ?? '')
    if (current !== latest) break
    count += 1
  }
  return count
}

function detectCorrectionLocality(categories: ErrorCategory[]): CorrectionLocality {
  if (categories.includes('runtime_unavailable')) return 'environment'
  if (categories.includes('config_error') || categories.includes('dependency_missing')) return 'manifest'
  if (categories.includes('test_failure')) return 'test_suite'
  if (categories.some((category) => category === 'build_failure' || category === 'runtime_crash' || category === 'timeout')) {
    return 'multi_file'
  }
  if (categories.some((category) => category === 'syntax' || category === 'type_error' || category === 'import_missing')) {
    return 'single_file'
  }
  return 'unknown'
}

function selectDominantCause(categories: ErrorCategory[]): ErrorCategory {
  const priority: ErrorCategory[] = [
    'runtime_unavailable', 'config_error', 'dependency_missing', 'build_failure',
    'runtime_crash', 'test_failure', 'type_error', 'import_missing',
    'syntax', 'timeout', 'permission_error', 'unknown',
  ]
  return priority.find((category) => categories.includes(category)) ?? categories[0] ?? 'unknown'
}


export function buildCorrectionDiagnosis(
  errorCategories: ErrorCategory[],
  correctionLog: CorrectionPass[],
): { cause: ErrorCategory; locality: CorrectionLocality; history: CorrectionHistorySignal } {
  const recentScores = correctionLog.slice(-3).map((pass) => pass.score)
  const stagnating = recentScores.length >= 3 && Math.max(...recentScores) - Math.min(...recentScores) <= 4
  return {
    cause: selectDominantCause(errorCategories),
    locality: detectCorrectionLocality(errorCategories),
    history: {
      stagnating,
      repeatedErrorCount: countRepeatedTailErrors(correctionLog),
      adaptiveBudget: computeAdaptiveCorrectionBudget(errorCategories, correctionLog),
    },
  }
}

function withDiagnosis(
  strategy: Omit<CorrectionStrategy, 'cause' | 'locality' | 'history'>,
  diagnosis: ReturnType<typeof buildCorrectionDiagnosis>,
): CorrectionStrategy {
  return { ...strategy, ...diagnosis }
}

export function buildCorrectionStrategy(
  errorCategories: ErrorCategory[],
  attempt: number,
  correctionLog: CorrectionPass[],
): CorrectionStrategy {
  const diagnosis = buildCorrectionDiagnosis(errorCategories, correctionLog)
  // Calculate escalation level based on attempt and progress
  const isStagnating = diagnosis.history.stagnating

  // Asymetrie #5: l escalade suivait le NUMERO de passe. Un run qui PROGRESSE
  // changeait quand meme de modele toutes les 2 passes — chaque changement
  // recharge un gros modele, premiere cause de swap VRAM ici. On suit donc la
  // TRAJECTOIRE: qui progresse garde son modele, qui stagne escalade.
  const isClimbing = isCorrectionScoreClimbing(correctionLog)
  let escalation: number
  if (isStagnating) {
    escalation = Math.min(5, attempt)
  } else if (isClimbing) {
    // La progression paie: on ne touche a rien.
    escalation = Math.min(2, Math.ceil(attempt / 3))
  } else {
    escalation = Math.min(5, Math.ceil(attempt / 2))
  }

  if (diagnosis.history.repeatedErrorCount >= 3) {
    escalation = Math.max(escalation, 4)
  }

  // Au-dela de la passe 5 on reste a l escalade 5 en faisant tourner l angle de
  // diagnostic. Chaque variation preserve le perimetre demande: pas de MVP
  // reduit, pas de test supprime, pas de changement de stack.
  let rotationInstructions: string | null = null
  if (attempt > 5) {
    const rotationIndex = (attempt - 6) % 4
    switch (rotationIndex) {
      case 0:
        rotationInstructions = [
          'VARIATION 1 - Diagnostic preuve par preuve:',
          '- Relie chaque erreur a un fichier, symbole, commande ou dependance precise',
          '- Corrige la cause racine avant toute reecriture large',
          '- Conserve les tests, scripts, exports, endpoints et fichiers non impliques',
        ].join('\n')
        break
      case 1:
        rotationInstructions = [
          'VARIATION 2 - Isolation de frontiere dans la meme stack:',
          '- Isole le module, adaptateur, script ou manifest qui casse',
          '- Remplace uniquement une dependance incompatible si l erreur le prouve',
          '- Ne change pas de framework, langage ou architecture produit pour masquer le bug',
        ].join('\n')
        break
      case 2:
        rotationInstructions = [
          'VARIATION 3 - Patch minimal conservateur:',
          '- Modifie le plus petit ensemble de lignes qui explique l echec',
          '- Garde les fichiers de test, documentation, configuration et scripts existants',
          '- Une reduction de taille n est acceptable que si elle retire du code mort prouve',
        ].join('\n')
        break
      case 3:
        rotationInstructions = [
          'VARIATION 4 - Reconciliation avec le plan d architecture:',
          '- N ignore pas les fichiers actuels: compare-les au plan et repare les ecarts',
          '- Compare le PLAN original aux fichiers actuels point par point',
          '- Complete les contrats manquants sans retirer les capacites presentes',
          '- Verifie chaque import et API publique apres chaque fichier modifie',
        ].join('\n')
        break
    }
  }

  if (errorCategories.includes('runtime_unavailable')) {
    return withCycleDirective(withDiagnosis({
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
    }, diagnosis), correctionLog)
  }

  // Level 1: Quick fix — simple syntax/import errors
  // TOUJOURS rechercher en ligne — meme les erreurs simples peuvent cacher
  // des incompatibilites de version ou des bugs connus
  if (escalation <= 1 && errorCategories.every((c) => c === 'syntax' || c === 'import_missing' || c === 'type_error')) {
    return withCycleDirective(withDiagnosis({
      level: 'quick_fix',
      escalation,
      instructions: buildQuickFixInstructions(errorCategories),
      switchModel: false,
      searchWeb: true,
    }, diagnosis), correctionLog)
  }

  // Level 2: Targeted repair — dependency/config issues
  if (escalation <= 2) {
    return withCycleDirective(withDiagnosis({
      level: 'targeted_repair',
      escalation,
      instructions: buildTargetedRepairInstructions(errorCategories),
      switchModel: escalation >= 2,
      searchWeb: true,
    }, diagnosis), correctionLog)
  }

  // Level 3: Partial rewrite — runtime/build errors with web search
  if (escalation <= 3) {
    return withCycleDirective(withDiagnosis({
      level: 'partial_rewrite',
      escalation,
      instructions: buildPartialRewriteInstructions(errorCategories),
      switchModel: true,
      searchWeb: true,
    }, diagnosis), correctionLog)
  }

  // Level 4: Full rewrite
  if (escalation <= 4) {
    return withCycleDirective(withDiagnosis({
      level: 'rewrite',
      escalation,
      instructions: [
        'Les corrections precedentes ont echoue a resoudre les problemes.',
        'Reecris COMPLETEMENT les fichiers problematiques.',
        'Resserre l architecture sans retirer de fonctionnalite, test, script, endpoint ou export public.',
        'Utilise des patterns eprouves et stables.',
        'Verifie chaque import, chaque type, chaque dependance.',
      ].join('\n'),
      switchModel: false,  // Pas de swap VRAM — cause #1 de crash PC
      searchWeb: true,
    }, diagnosis), correctionLog)
  }

  // Level 5: Strategy change — completely different approach
  const baseInstructions = [
    'TOUTES les tentatives precedentes ont echoue.',
    'Change d angle de diagnostic sans reduire le produit:',
    `- Cause dominante: ${diagnosis.cause}`,
    `- Localite probable: ${diagnosis.locality}`,
    '- Preserve toutes les fonctionnalites, tests, docs, scripts, endpoints et exports publics',
    '- Ne change de librairie que si une incompatibilite locale est prouvee par l erreur',
    '- Si les tests echouent, traite-les comme contrat d acceptation et corrige le code',
  ].join('\n')
  return withCycleDirective(withDiagnosis({
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
  }, diagnosis), correctionLog)
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
 * Budget adaptatif plafonne par MAX_CORRECTION_PASSES pour proteger le PC. La
 * boucle s arrete quand :
 *   1. Score 100 → succes
 *   2. Meme erreur exacte 6+ fois consecutives → boucle prouvee impossible
 *   3. Budget adapte a la complexite atteint → diagnostic clair
 *
 * Le cap n est PAS un "plateau fixe a 45%" : il est atteint apres avoir
 * reellement tente 4 variations de strategie + recherche web + rescue.
 */


export function shouldContinueLoop(
  correctionLog: CorrectionPass[],
  _currentAttempt: number,
  _errorCategories: ErrorCategory[] = [],
  fileCount = 0,
): boolean {
  if (correctionLog.length === 0) return true
  const latestScore = correctionLog[correctionLog.length - 1].score

  // Score parfait → succes
  if (latestScore >= 100) return false

  // Seules les passes qui ont CHARGE UN MODELE sont prelevees sur le budget.
  const modelPasses = countModelPasses(correctionLog)
  const localRepairs = correctionLog.length - modelPasses
  // Les reparations locales restent bornees, sinon une reparation qui oscille
  // tournerait indefiniment — gratuitement, mais indefiniment.
  if (localRepairs >= MAX_LOCAL_REPAIR_PASSES) return false

  if (modelPasses >= MAX_CORRECTION_PASSES) return false // plafond dur machine, jamais depasser
  // Au budget adaptatif on ne coupe que si la progression ne paie plus (un run qui grimpe encore va jusqu'au plafond dur).
  if (modelPasses >= computeAdaptiveCorrectionBudget(_errorCategories, correctionLog, fileCount) && !isCorrectionScoreClimbing(correctionLog)) return false

  // Cycle: un defaut revenu apres avoir disparu, sans terrain gagne entre-temps.
  // Retenter le MEME traitement redonnerait le meme aller-retour (run 1171) —
  // mais s arreter net laisse le contrat incoherent. On accorde donc UNE passe
  // de plus, qui ne repete pas le traitement precedent: elle recoit la
  // fermeture transitive du contrat (codeTransitiveClosure) et doit trancher.
  // Grace epuisee = la fermeture n a pas suffi, s obstiner ne paiera pas.
  if (detectCorrectionCycle(correctionLog) && !cycleGraceRemaining(correctionLog)) return false

  // Boucle infinie reelle : meme erreur exacte qui revient 6+ fois consecutives.
  if (correctionLog.length >= 6) {
    const last6Errors = correctionLog.slice(-6).map((p) => p.errors[0] ?? '')
    const normalized = last6Errors.map(normalizeErrorForHistory)
    if (normalized.every((e) => e.length > 10 && e === normalized[0])) {
      return false
    }
  }

  return true
}
