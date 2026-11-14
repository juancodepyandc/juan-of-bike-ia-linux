/**
 * closedLoopPatchEngine.ts — Pont de Remédiation en Boucle Fermée CEGIS & Preuve Formelle UNSAT
 * relié au moteur principal `../closedLoopPatchEngine.ts`.
 */

export {
  type VulnerabilityCategory,
  type VulnerabilityProof,
  type CegisIterationRecord,
  type PatchVerificationResult,
  evaluateStrictSsrfGuard,
  verifySsrfClosedLoop,
  verifyTimingAttackClosedLoop,
  verifyPosixAndNetworkClosedLoop,
  applyStructuralAstRemediation,
  executeClosedLoopCodeRemediation,
} from '../closedLoopPatchEngine.ts'
