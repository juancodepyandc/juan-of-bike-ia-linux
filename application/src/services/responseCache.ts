// Response cache pour les questions répétées dans la même session.
//
// Demande du handoff : "Cache des réponses pour questions identiques
// récentes". Objectif : si Juan repose la même question 30s plus tard (parce
// que la première réponse a été coupée par une coupure réseau), on sert le
// même contenu plutôt que de re-frapper le LLM.
//
// Stratégies de match :
//   - exact   : hash FNV-1a sur la normalisation du prompt
//   - fuzzy   : signature en sorted-token set, Jaccard ≥ 0.92
//
// LRU bornée + TTL. Pure compute.

import { tokenize } from './conversationMemory.ts'

export type CacheEntry = {
  /** Hash strict du prompt normalisé. */
  exactKey: string
  /** Set des tokens distincts (signature fuzzy). */
  tokenSet: string[]
  /** Réponse stockée. */
  response: string
  /** Coût économisé (USD), pour télémétrie. */
  savedCostUsd: number
  /** ISO date de mise en cache. */
  cachedAt: string
  /** Compteur de hits. */
  hits: number
}

export type CacheStats = {
  size: number
  totalHits: number
  totalSavedUsd: number
}

export type CacheOptions = {
  maxEntries?: number
  /** TTL en secondes. 0 = pas d'expiration. */
  ttlSeconds?: number
  /** Seuil Jaccard pour le match fuzzy. */
  fuzzyThreshold?: number
}

const DEFAULTS: Required<CacheOptions> = {
  maxEntries: 128,
  ttlSeconds: 600, // 10 min
  fuzzyThreshold: 0.92,
}

function fnv1a(text: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0).toString(16)
}

function normalisePrompt(prompt: string): string {
  return prompt.trim().toLowerCase().normalize('NFC')
}

export class ResponseCache {
  private opts: Required<CacheOptions>
  private entries: CacheEntry[] = []

  constructor(opts: CacheOptions = {}) {
    this.opts = { ...DEFAULTS, ...opts }
  }

  /**
   * Look up a cached response. Returns null if no match (or expired).
   * Side effect: bumps hit counter on success.
   */
  get(prompt: string, now: Date = new Date()): CacheEntry | null {
    const exact = fnv1a(normalisePrompt(prompt))
    const tokens = uniqueTokens(prompt)
    this.evictExpired(now)
    // Exact match first.
    let hit = this.entries.find((e) => e.exactKey === exact)
    if (!hit && tokens.size > 0) {
      // Fuzzy fallback.
      let bestScore = 0
      let bestEntry: CacheEntry | null = null
      for (const entry of this.entries) {
        const score = jaccard(tokens, new Set(entry.tokenSet))
        if (score > bestScore) {
          bestScore = score
          bestEntry = entry
        }
      }
      if (bestEntry && bestScore >= this.opts.fuzzyThreshold) hit = bestEntry
    }
    if (!hit) return null
    hit.hits += 1
    // Move to front of LRU.
    this.entries = [hit, ...this.entries.filter((e) => e !== hit)]
    return hit
  }

  set(prompt: string, response: string, savedCostUsd = 0, now: Date = new Date()): void {
    const exact = fnv1a(normalisePrompt(prompt))
    const existing = this.entries.find((e) => e.exactKey === exact)
    if (existing) {
      existing.response = response
      existing.cachedAt = now.toISOString()
      existing.savedCostUsd += savedCostUsd
      return
    }
    const entry: CacheEntry = {
      exactKey: exact,
      tokenSet: Array.from(uniqueTokens(prompt)),
      response,
      savedCostUsd,
      cachedAt: now.toISOString(),
      hits: 0,
    }
    this.entries.unshift(entry)
    while (this.entries.length > this.opts.maxEntries) this.entries.pop()
  }

  /** Drop entries older than ttl. */
  evictExpired(now: Date = new Date()): number {
    if (this.opts.ttlSeconds <= 0) return 0
    const cutoff = now.getTime() - this.opts.ttlSeconds * 1000
    const before = this.entries.length
    this.entries = this.entries.filter((e) => new Date(e.cachedAt).getTime() > cutoff)
    return before - this.entries.length
  }

  /** Empty the cache (e.g. when settings change or user explicit). */
  clear(): void {
    this.entries = []
  }

  stats(): CacheStats {
    return {
      size: this.entries.length,
      totalHits: this.entries.reduce((a, e) => a + e.hits, 0),
      totalSavedUsd: this.entries.reduce((a, e) => a + e.savedCostUsd, 0),
    }
  }
}

function uniqueTokens(text: string): Set<string> {
  return new Set(tokenize(text))
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1
  if (a.size === 0 || b.size === 0) return 0
  let inter = 0
  for (const x of a) if (b.has(x)) inter += 1
  return inter / (a.size + b.size - inter)
}
