/**
 * Pure utility: infer a short conversational title from a user prompt.
 * No external dependencies -- fully testable in Node.js.
 */

export function capitalize(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return trimmed
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1)
}

/** Generate a concise contextual title from a user prompt (no LLM needed). */
export function inferTitle(promptText: string): string {
  if (!promptText || !promptText.trim()) return 'Nouvelle conversation'

  const text = promptText.trim()

  const appMatch = text.match(
    /(?:cr[ée]+|fai[st]|g[ée]n[eè]re|d[ée]veloppe)\s+(?:une?\s+)?(?:application|app|site|page|projet|api|script)\s+(.{3,40})/i,
  )
  if (appMatch) return capitalize(appMatch[1].replace(/\s*[,.].*$/, ''))

  const imageMatch = text.match(
    /(?:image|photo|portrait|dessin|illustration|rendu|video|vid[ée]o)\s+(?:de\s+la|de\s+les|des|du|d'|de)\s+(.{3,40})/i,
  )
  if (imageMatch) return capitalize(imageMatch[1].replace(/\s*[,.].*$/, ''))

  const articleMatch = text.match(/^(?:un[e]?\s+)(.{3,40})/i)
  if (articleMatch) return capitalize(articleMatch[1].replace(/\s*[,.].*$/, ''))

  const firstSegment = text.split(/[,.\n]/)[0].trim()
  if (firstSegment.length > 50) {
    const cut = firstSegment.slice(0, 50).replace(/\s+\S*$/, '')
    return capitalize(cut) + '...'
  }

  return capitalize(firstSegment) || 'Nouvelle conversation'
}
