// ---------------------------------------------------------------------------
// Code intent complexity estimation
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeComplexity } from './codeIntentTypes.ts'
import { MULTIPAGE_SIGNALS } from './codeIntentSignals.ts'
import { containsSignal, normalizeSignalText } from './codeIntentSignalUtils.ts'

const COMPLEXITY_SIGNALS: Record<CodeComplexity, string[]> = {
  trivial: ['simple', 'basique', 'hello world', 'exemple', 'example', 'demo', 'test'],
  simple: ['petit', 'small', 'script', 'utilitaire', 'utility', 'helper', 'fonction', 'function'],
  moderate: ['moyen', 'medium', 'composant', 'component', 'module', 'service', 'feature'],
  complex: ['complet', 'complete', 'application', 'app', 'projet', 'project', 'systeme', 'system'],
  enterprise: ['entreprise', 'enterprise', 'production', 'scalable', 'microservices', 'architecture', 'plateforme', 'platform', 'saas', 'large'],
}

export function estimateComplexity(prompt: string): CodeComplexity {
  const lower = normalizeSignalText(prompt)
  const wordCount = lower.split(/\s+/).length

  // Check from most complex to least
  for (const keyword of COMPLEXITY_SIGNALS.enterprise) {
    if (containsSignal(lower, keyword)) return 'enterprise'
  }

  // Multipage signals always bump to at least complex
  for (const signal of MULTIPAGE_SIGNALS) {
    if (containsSignal(lower, signal)) return 'complex'
  }

  for (const keyword of COMPLEXITY_SIGNALS.complex) {
    if (containsSignal(lower, keyword)) return 'complex'
  }

  // Word count heuristic
  if (wordCount > 80) return 'complex'
  if (wordCount > 40) return 'moderate'

  for (const keyword of COMPLEXITY_SIGNALS.moderate) {
    if (containsSignal(lower, keyword)) return 'moderate'
  }

  for (const keyword of COMPLEXITY_SIGNALS.simple) {
    if (containsSignal(lower, keyword)) return 'simple'
  }

  for (const keyword of COMPLEXITY_SIGNALS.trivial) {
    if (containsSignal(lower, keyword)) return 'trivial'
  }

  return 'moderate'
}

// ---------------------------------------------------------------------------
// Asset plan — heuristic analysis of the user brief
