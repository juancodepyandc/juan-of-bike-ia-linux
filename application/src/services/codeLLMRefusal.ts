// ---------------------------------------------------------------------------
// LLM refusal detection
// Extracted from codeOrchestrator.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

const LLM_REFUSAL_PATTERNS = [
  /je (suis d[eé]sol[eé]|ne (peux|suis) pas|m'excuse)/i,
  /i('m| am) (sorry|unable|not able)/i,
  /i (can'?t|cannot|could not|wouldn'?t) (help|assist|generate|create|produce|provide|write|code)/i,
  /je ne (peux|suis) pas (aider|g[eé]n[eé]rer|cr[eé]er|produire|[eé]crire)/i,
  /pas aider [àa] g[eé]n[eé]rer/i,
  /contredit les directives/i,
  /ne respecte pas le format/i,
  /d[eé]passe mes capacit[eé]s/i,
  /beyond my (capabilities|ability)/i,
  /i (don'?t|do not) (have|possess) the ability/i,
  /contre les (r[eè]gles|directives|politiques)/i,
  /against (my |the )?(rules|guidelines|policies)/i,
  /je vous sugg[eè]re plut[oô]t/i,
  /i (would |)suggest (instead|rather|you)/i,
  /examiner attentivement vos instructions/i,
  /review your instructions/i,
]

const LLM_REFUSAL_NEGATIVE_PATTERNS = [
  /```\w+\n/,           // Contains code blocks → probably not a refusal
  /--- FICHIER:/i,      // Contains file markers → structured output
  /--- FILE:/i,
  /import\s+\{/,        // Actual code patterns
  /export\s+(default\s+)?/,
  /function\s+\w+/,
  /class\s+\w+/,
  /const\s+\w+\s*=/,
  /<html/i,
  /<!DOCTYPE/i,
  // v85d : modern SFC / Astro idioms — these are CODE, never a refusal. Without
  // them a valid .astro/.vue/.svelte file (frontmatter, <style>, <template>)
  // could be flagged as a refusal and the whole project scored 0.
  /<template[\s>]/i,
  /<style[\s>]/i,
  /<script[\s>]/i,
  /Astro\.(props|glob|url|request)/,
  /getCollection\s*\(/,
  /^---\s*$/m,
]

/**
 * Detects if LLM output is a refusal/apology instead of actual code.
 * Returns true if content is a refusal message.
 */
export function isLLMRefusal(content: string): boolean {
  if (!content || content.trim().length < 20) return false
  const trimmed = content.trim()

  // If content has clear code structure, it's not a refusal
  if (LLM_REFUSAL_NEGATIVE_PATTERNS.some((p) => p.test(trimmed))) return false

  // Check against refusal patterns
  const matchCount = LLM_REFUSAL_PATTERNS.filter((p) => p.test(trimmed)).length
  if (matchCount >= 2) return true

  // Single match + short content (< 800 chars) + no code → likely refusal
  if (matchCount >= 1 && trimmed.length < 800) return true

  return false
}
