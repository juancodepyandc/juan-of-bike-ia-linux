import type { ErrorCategory } from './codeAutoCorrection.ts'

// ---------------------------------------------------------------------------
// Error classification — deterministic pattern matching
// ---------------------------------------------------------------------------

export const ERROR_PATTERNS: Array<{ pattern: RegExp; category: ErrorCategory }> = [
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

/**
 * Vrai si les 3 dernieres passes de correction montrent une progression NETTE et
 * strictement croissante (>= 5 pts au total). Sert a ne pas couper au budget
 * adaptatif un run qui atteint reellement son but — il continue jusqu'au plafond
 * dur machine. Sans ce credit, un projet complexe qui progresse encore serait
 * livre inacheve au meme titre qu'un run reellement bloque.
 */
export function isCorrectionScoreClimbing(correctionLog: Array<{ score: number }>): boolean {
  if (correctionLog.length < 3) return false
  const recent = correctionLog.slice(-3).map((pass) => pass.score)
  return recent[2] > recent[1] && recent[1] > recent[0] && recent[2] - recent[0] >= 5
}
