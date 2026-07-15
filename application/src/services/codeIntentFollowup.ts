// ---------------------------------------------------------------------------
// Follow-up intent heuristics
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import {
  API_SIGNALS,
  DESKTOP_SIGNALS,
  FRAMEWORK_SIGNALS,
  GAME_SIGNALS,
  LANGUAGE_SIGNALS,
  MOBILE_SIGNALS,
  THREED_APP_SIGNALS,
  WEB_SIGNALS,
} from './codeIntentSignals.ts'
import { containsAnySignal, containsSignal, normalizeSignalText } from './codeIntentSignalUtils.ts'

export function hasExplicitStackMention(normalizedLower: string): boolean {
  // Frameworks
  for (const keyword of Object.keys(FRAMEWORK_SIGNALS)) {
    if (containsSignal(normalizedLower, keyword)) return true
  }
  // Languages
  for (const keyword of Object.keys(LANGUAGE_SIGNALS)) {
    if (containsSignal(normalizedLower, keyword)) return true
  }
  // Platform families
  if (containsAnySignal(normalizedLower, WEB_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, MOBILE_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, DESKTOP_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, API_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, GAME_SIGNALS)) return true
  if (containsAnySignal(normalizedLower, THREED_APP_SIGNALS)) return true
  return false
}

/**
 * Heuristic fallback (no LLM) that classifies a follow-up prompt into one of
 * four pivot kinds. Used when the LLM-driven `analyzeFollowUpIntent` fails
 * or is disabled. Based purely on lexical cues.
 */
export function classifyPivotKindHeuristic(
  newPrompt: string,
  hasHistory: boolean,
  hasExistingFiles: boolean,
): 'increment' | 'pivot_platform' | 'pivot_feature' | 'fresh_start' {
  const lower = normalizeSignalText(newPrompt).trim()

  // Without any history or files → always fresh_start.
  if (!hasHistory && !hasExistingFiles) return 'fresh_start'

  // Explicit pivot cues ("la meme chose mais en python", "refais en flask",
  // "convertis en mobile", "plutot en vue"…). Pair a pivot verb with a
  // stack/language mention and we treat it as a platform pivot.
  const pivotVerbs = [
    'meme chose', 'pareil', 'mais en', 'mais sur', 'mais pour',
    'plutot', 'plutôt', 'refais', 'refait', 'recommence',
    'convertis', 'convertir', 'transforme', 'transformer',
    'version', 'port', 'porte', 'migrer', 'migre',
    'same thing', 'instead', 'rewrite', 'convert', 'port to',
  ]
  const hasPivotVerb = pivotVerbs.some((verb) => lower.includes(verb))
  const hasStack = hasExplicitStackMention(lower)
  if (hasPivotVerb && hasStack) return 'pivot_platform'

  // A bare stack mention in a short follow-up without pivot verb is still
  // a platform pivot if the user was clearly working on another stack.
  if (hasStack && lower.split(/\s+/).length <= 8 && hasExistingFiles) {
    return 'pivot_platform'
  }

  // Very short follow-up without any stack mention → incremental patch.
  if (lower.length < 60 && hasExistingFiles) return 'increment'

  // Long, detailed prompt mentioning a stack → probably a new feature in
  // the same project (or occasionally a fresh start). Default to
  // pivot_feature so the classifier still runs on the fresh prompt.
  if (hasStack) return 'pivot_feature'

  // Otherwise default to incremental when there is an existing project.
  return hasExistingFiles ? 'increment' : 'fresh_start'
}
