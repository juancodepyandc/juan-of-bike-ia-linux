import { ollamaGenerate } from '../hooks/useTauri'
import { DEFAULT_CODE_MODEL } from '../config/models'

/**
 * Generates a concise French session title (3-6 words) using the LLM.
 *
 * Falls back to a deterministic extraction from the prompt if the LLM
 * call fails or returns garbage.
 */
export async function generateSessionTitle(
  prompt: string,
  projectType: string,
  frameworks: string[],
): Promise<string> {
  const trimmed = prompt.trim()
  if (!trimmed) return 'Nouvelle session'

  try {
    const frameworkList = frameworks.length > 0 ? frameworks.join(', ') : ''
    const context = [projectType, frameworkList].filter(Boolean).join(' avec ')

    const systemPrompt = [
      'Genere un titre COURT (3-6 mots) pour cette session de code.',
      context ? `Contexte: ${context}.` : '',
      'Reponds UNIQUEMENT le titre, sans guillemets ni ponctuation finale.',
      'Exemples: Dashboard React admin, API FastAPI auth JWT, CLI Rust analyseur, Landing page portfolio',
      '',
      `Demande: ${trimmed.slice(0, 120)}`,
    ].join('\n')

    const result = await ollamaGenerate(DEFAULT_CODE_MODEL, systemPrompt)
    const raw: string = (result?.response ?? '').trim()

    const title = sanitizeTitle(raw)
    if (title) return title
  } catch {
    // LLM unavailable — fall through to deterministic fallback
  }

  return fallbackTitle(trimmed, projectType, frameworks)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Strip quotes, trailing dots, and clamp to a reasonable length. */
function sanitizeTitle(raw: string): string {
  let text = raw
    .replace(/^["'`]+|["'`]+$/g, '')  // surrounding quotes
    .replace(/[.!?:]+$/, '')           // trailing punctuation
    .replace(/\n.*/s, '')              // keep only first line
    .trim()

  // Reject empty, too short, or suspiciously long results
  if (text.length < 3 || text.length > 60) return ''

  // Reject if it looks like the model returned an explanation instead of a title
  if (text.split(/\s+/).length > 8) return ''

  // Capitalize first letter
  text = text.charAt(0).toUpperCase() + text.slice(1)
  return text
}

/** Build a deterministic title from the prompt when the LLM is unavailable. */
function fallbackTitle(
  prompt: string,
  projectType: string,
  frameworks: string[],
): string {
  // Strategy 1: combine projectType + first framework
  if (projectType && frameworks.length > 0) {
    const combo = `${capitalize(projectType)} ${frameworks[0]}`
    if (combo.length <= 40) return combo
  }

  // Strategy 2: use projectType alone if meaningful
  if (projectType && projectType.length >= 3) {
    return capitalize(projectType)
  }

  // Strategy 3: extract first meaningful words from the prompt
  const stopwords = new Set([
    'je', 'tu', 'il', 'nous', 'vous', 'ils',
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'au', 'aux',
    'et', 'ou', 'mais', 'donc', 'car', 'ni',
    'que', 'qui', 'quoi', 'dont',
    'pour', 'par', 'avec', 'dans', 'sur', 'en', 'ce', 'cette', 'ces',
    'mon', 'ton', 'son', 'ma', 'ta', 'sa',
    'veux', 'voudrais', 'peux', 'pourrais', 'fais', 'faire',
    'cree', 'creer', 'genere', 'generer', 'ecris', 'ecrire',
    'moi', 'me', 'se', 'si', 'est', 'sont', 'a', 'ai',
  ])

  const words = prompt
    .replace(/[^a-zA-ZÀ-ÿ0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 1 && !stopwords.has(w.toLowerCase()))
    .slice(0, 5)

  if (words.length > 0) {
    const title = words.join(' ')
    return capitalize(title.length > 45 ? title.slice(0, 42) + '...' : title)
  }

  return 'Session code'
}

function capitalize(text: string): string {
  const t = text.trim()
  if (!t) return t
  return t.charAt(0).toUpperCase() + t.slice(1)
}
