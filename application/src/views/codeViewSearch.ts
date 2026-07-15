export function countFileSearchMatches(content: string, query: string): number {
  if (!query) return 0
  try {
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const matches = content.match(new RegExp(escaped, 'gi'))
    return matches?.length ?? 0
  } catch {
    return 0
  }
}
