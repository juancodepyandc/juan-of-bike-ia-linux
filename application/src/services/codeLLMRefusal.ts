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
  /AURORA_CODE_VFS\/1/i,
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
  // Autres langages : une ligne de code n'est jamais une excuse, même si elle contient une phrase
  // d'erreur en français (`print("je ne peux pas diviser par zéro")`).
  /^\s*def\s+\w+\s*\(/m,                       // Python
  /^\s*(?:from\s+[\w.]+\s+)?import\s+[\w.*{]/m,   // Python, JS, Java, Kotlin
  /^\s*#include\s*[<"]/m,                         // C, C++
  /^\s*(?:pub\s+)?fn\s+\w+\s*[(<]/m,              // Rust
  /^\s*package\s+[\w.]+/m,                        // Go, Java, Kotlin
  /^\s*func\s+\w+\s*\(/m,                        // Go, Swift
  /^\s*(?:public|private|protected)\s+(?:static\s+)?[\w<>[\]]+\s+\w+\s*\(/m, // Java, C#
  /^\s*(?:let|var)\s+\w+\s*=/m,                   // JS, Swift
  /^\s*(?:if|for|while)\s*\(?.*\)?\s*[:{]\s*$/m, // blocs de contrôle (minuscules : « If you like: » reste de la prose)
  /^\s*[a-z_]\w*\s*=\s*[\w("'[{-]/m,           // affectation
]

// Une excuse de modèle OUVRE sa réponse (« Je suis désolé, mais… », « I'm sorry, but… »).
// Une phrase semblable plus loin dans un texte long est un contenu, pas un refus.
const REFUSAL_OPENING_CHARS = 400

/**
 * Detects if LLM output is a refusal/apology instead of actual code.
 * Returns true if content is a refusal message.
 */
export function isLLMRefusal(content: string): boolean {
  if (!content || content.trim().length < 20) return false
  const trimmed = content.trim()

  // If content has clear code structure, it's not a refusal
  if (LLM_REFUSAL_NEGATIVE_PATTERNS.some((p) => p.test(trimmed))) return false

  // A refusal opens the answer; the same phrase deep inside a long text is content.
  const opening = trimmed.slice(0, REFUSAL_OPENING_CHARS)
  if (!LLM_REFUSAL_PATTERNS.some((p) => p.test(opening))) return false

  // Check against refusal patterns
  const matchCount = LLM_REFUSAL_PATTERNS.filter((p) => p.test(trimmed)).length
  if (matchCount >= 2) return true

  // Single match + short content (< 800 chars) + no code → likely refusal
  if (matchCount >= 1 && trimmed.length < 800) return true

  return false
}

/** Extensions of files that hold prose rather than source code. */
const PROSE_EXTENSIONS = new Set(['md', 'markdown', 'txt', 'text', 'rst', ''])

function extensionOf(name: string): string {
  const base = name.replace(/\\/g, '/').split('/').pop() || ''
  const dot = base.lastIndexOf('.')
  return dot <= 0 ? '' : base.slice(dot + 1).toLowerCase()
}

/**
 * The delivered file that is a model refusal, if any.
 *
 * Only a prose file can be a refusal. A source file (`.py`, `.js`, `.html`…) is code: an error
 * message it prints — « je ne peux pas diviser par zéro » — is data, and used to zero the score of
 * a whole working project. A project that also contains real code is not a refusal either: a
 * README that says « cette démo ne peut pas tourner sans clé » documents the code.
 */
export function findRefusalFile<T extends { name: string; content: string }>(files: T[]): T | undefined {
  const hasSourceCode = files.some((file) => !PROSE_EXTENSIONS.has(extensionOf(file.name)) && file.content.trim().length > 0)
  if (hasSourceCode) return undefined
  return files.find((file) => PROSE_EXTENSIONS.has(extensionOf(file.name)) && isLLMRefusal(file.content))
}
