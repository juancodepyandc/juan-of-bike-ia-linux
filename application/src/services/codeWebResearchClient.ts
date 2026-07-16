import { getBridgeUrl } from '../utils/runtime.ts'

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeWebResearchOptions = {
  limit?: number
  timeoutMs?: number
  bridgeUrl?: string
  fetchImpl?: FetchLike
}

function useful(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 20
}

function rowText(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (!value || typeof value !== 'object') return ''
  const row = value as Record<string, unknown>
  for (const key of ['snippet', 'content', 'text', 'title']) {
    if (useful(row[key])) return String(row[key]).trim()
  }
  return ''
}

export function extractCodeWebSearchSnippets(payload: unknown, limit = 8): string[] {
  if (!payload || typeof payload !== 'object') return []
  const record = payload as Record<string, unknown>
  const nested = record.data && typeof record.data === 'object'
    ? record.data as Record<string, unknown>
    : null
  const candidates = [record.results, record.resultsList, nested?.results, nested?.resultsList]
  const snippets: string[] = []
  for (const candidate of candidates) {
    const rows = typeof candidate === 'string' ? candidate.split('\n') : candidate
    if (!Array.isArray(rows)) continue
    for (const row of rows) {
      const text = rowText(row)
      if (useful(text) && !snippets.includes(text)) snippets.push(text)
      if (snippets.length >= limit) return snippets
    }
  }
  return snippets
}

export async function searchCodeWebReferences(
  query: string,
  options: CodeWebResearchOptions = {},
): Promise<string[]> {
  if (!query.trim()) return []
  const limit = Math.max(1, Math.min(20, Math.round(options.limit ?? 8)))
  const timeoutMs = Math.max(1_000, Math.min(60_000, options.timeoutMs ?? 25_000))
  const bridgeUrl = (options.bridgeUrl ?? getBridgeUrl()).replace(/\/$/, '')
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis)
  try {
    const response = await fetchImpl(`${bridgeUrl}/api/web/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit }),
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (!response.ok) return []
    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return []
    return extractCodeWebSearchSnippets(JSON.parse(text), limit)
  } catch {
    return []
  }
}
