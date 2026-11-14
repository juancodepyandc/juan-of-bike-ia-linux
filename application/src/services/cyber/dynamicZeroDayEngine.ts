/**
 * dynamicZeroDayEngine.ts — Pont d'Analyse Dynamique 0-Day par Premiers Principes
 * relié au moteur structurel AST/CFG/SSA & SMT/Z3 `symbolicZeroDayEngine.ts`.
 */

export {
  type SecurityInvariantCategory,
  type SecurityInvariant,
  type DynamicHypothesis,
  type DynamicReasoningSession,
  type ExistingSurfaceFinding,
  type EpistemicLessonEntry,
  FUNDAMENTAL_INVARIANTS,
  analyzeDynamicVulnerabilities,
  auditExistingSecuritySurface,
  getEpistemicLearningLedger,
  recordVerifiedInvariantLesson,
  runUnifiedSymbolicZeroDayAnalysis,
} from '../symbolicZeroDayEngine.ts'
