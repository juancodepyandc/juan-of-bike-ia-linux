// Baril de re-exports du module Code: la surface publique historique de
// codeOrchestrator, extraite pour tenir la limite de 400 lignes par unite.
// Aucun consommateur n est touche — codeOrchestrator re-exporte ce baril.

export { isLLMRefusal } from './codeLLMRefusal.ts'
export { parseCodeFiles, serializeCodeFiles, extractNotes } from './codeGeneratedFileParser.ts'
export { normalizeGeneratedCodeFilesForTest } from './codeGeneratedFileSanitizer.ts'
export { upsertProjectSupportFilesForTest } from './codeProjectSupportFiles.ts'
export {
  buildDesignRetryHint, checkGamePlayability, checkInteractive3DFidelity,
  checkWebPageIntegrity, computeDesignPolishReportPublic,
} from './codeQualityGates.ts'
export type { DesignPolishReport } from './codeQualityGates.ts'
export {
  analyzeFollowUpIntent,
  classifyClarificationSeverity,
  isVagueClarification,
} from './codeFollowUpAnalysis.ts'
export type {
  ClarificationSeverity,
  FollowUpAnalysis,
  FollowUpKind,
} from './codeFollowUpAnalysis.ts'
export type {
  CodeFile,
  CodeOrchestrationPhase,
  CodeOrchestrationResult,
  PhaseCallback,
} from './codeOrchestratorTypes.ts'
