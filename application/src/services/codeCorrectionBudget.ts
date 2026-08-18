// ---------------------------------------------------------------------------
// codeCorrectionBudget — ce que le plafond de correction protege reellement.
//
// La ressource rare n est pas la passe: c est le CHARGEMENT DE MODELE (VRAM et
// RAM). Une reparation locale deterministe n en charge aucun, et se prelevait
// pourtant sur le meme budget. Mesure sur les runs v124/v125/v126: une passe
// gratuite sur sept etait deja retiree au modele, et le balayage des
// reparations deterministes (extension, outillage Tailwind) en ajoute.
//
// Les reparations locales gardent donc leur propre plafond: gratuites, mais
// pas illimitees — une reparation qui oscillerait tournerait sans fin.
// ---------------------------------------------------------------------------

import type { CorrectionPass, ErrorCategory } from './codeAutoCorrection.ts'

/** Plafond dur machine des passes qui chargent un modele. Jamais depasser. */
export const MAX_CORRECTION_PASSES = 10

/** Plafond propre aux reparations locales, qui ne chargent aucun modele. */
export const MAX_LOCAL_REPAIR_PASSES = 8

/** Passes ayant reellement charge un modele. */
export function countModelPasses(correctionLog: CorrectionPass[]): number {
  return correctionLog.filter((pass) => !pass.localRepairOnly).length
}

// Budget proportionnel a la taille du projet: un livrable de 30 fichiers
// recevait le meme budget qu un de 3. Le PLAFOND ne bouge pas — on repartit.
export function computeAdaptiveCorrectionBudget(
  errorCategories: ErrorCategory[],
  _correctionLog: CorrectionPass[] = [],
  fileCount = 0,
): number {
  const categories = errorCategories.length > 0 ? errorCategories : ['unknown' as ErrorCategory]
  let budget = fileCount > 0 && fileCount <= 3 ? 5 : fileCount > 10 ? 7 : 6

  if (categories.length >= 2) budget += 1
  const HEAVY: ErrorCategory[] = [
    'config_error', 'dependency_missing', 'test_failure', 'runtime_crash', 'build_failure', 'timeout', 'unknown',
  ]
  if (categories.some((category) => HEAVY.includes(category))) budget += 2

  return Math.max(4, Math.min(MAX_CORRECTION_PASSES, budget))
}
