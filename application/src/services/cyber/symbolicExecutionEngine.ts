/**
 * symbolicExecutionEngine.ts — Pont d'Exécution Symbolique AST/CFG/SSA & Solveur SMT Z3
 * relié au moteur unifié `symbolicZeroDayEngine.ts` (Harnais KLEECopilot/SAILOR & Z3).
 */

export {
  type SymbolicVariable,
  type SymbolicPath,
  type SymbolicExecutionReport,
  type ControlFlowGraph,
  type SymbolicHarnessSpec,
  type ExistingSurfaceFinding,
  buildStructuralAstAndCfg,
  synthesizeSymbolicHarness,
  auditExistingSecuritySurface,
  exploreCfgSymbolicPaths,
  runSymbolicExecution,
  runSymbolicExecutionWithZ3,
  runUnifiedSymbolicZeroDayAnalysis,
} from '../symbolicZeroDayEngine.ts'
