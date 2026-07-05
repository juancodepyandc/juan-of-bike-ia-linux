// Mémoire long terme pour la conversation Aurora.
//
// L'orchestrateur convo possède déjà un buffer de messages "courte fenêtre".
// Ce module gère la mémoire qui SURVIT entre sessions : faits importants,
// préférences, résumés de conversations passées. Récupérable par similarité
// sans dépendance à un modèle d'embeddings — on utilise du bag-of-words FR +
// TF-IDF cosine, ce qui marche très bien à cette échelle (≤ 1000 mémoires).
//
// Pure compute : pas de DOM, pas de fetch, pas de Date.now() en code chaud
// (le caller fournit la clock pour les tests).

export type MemoryKind =
  | 'fact'         // information atomique sur l'user/le projet
  | 'preference'   // "Juan préfère le tutoiement"
  | 'summary'      // résumé condensé d'une convo passée
  | 'tool_result'  // résultat d'une action passée à retenir
  | 'pinned'       // épinglé par l'user — toujours dans la fenêtre

export type MemoryEntry = {
  id: string
  kind: MemoryKind
  text: string
  tags: string[]
  /** Importance ∈ [0..1]. Pondère la similarité. */
  importance: number
  /** Création (ISO). */
  createdAt: string
  /** Dernière utilisation (ISO). */
  lastUsedAt: string | null
  /** Compteur d'utilisations. */
  usageCount: number
  /** Hash du contenu, pour dédup. */
  contentHash: string
  /** Token frequencies — pré-calculées au store. */
  tokens: Record<string, number>
}

export type MemoryStore = {
  version: number
  entries: MemoryEntry[]
  /** Document frequency par token — pour TF-IDF rapide. */
  documentFrequency: Record<string, number>
}

export const MEMORY_STORE_VERSION = 1
const MAX_TOKEN_LENGTH = 40

// --- Tokenizer FR léger -----------------------------------------------------
const STOPWORDS_FR = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux', 'à', 'a', 'et', 'ou',
  'pour', 'par', 'sur', 'sous', 'avec', 'sans', 'dans', 'en', 'ce', 'cet', 'cette', 'ces',
  'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'me', 'te', 'se', 'mon',
  'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses', 'est', 'sont', 'être', 'avoir',
  'que', 'qui', 'quoi', 'quand', 'où', 'comment', 'pourquoi', 'plus', 'moins', 'pas',
  'ne', 'si', 'mais', 'donc', 'car', 'ni', 'or', 'puis', 'aussi',
])

export function tokenize(text: string): string[] {
  if (!text) return []
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // strip diacritics — "physique" == "Physique"
    .split(/[^a-z0-9_]+/)
    .filter((t) => t.length >= 2 && t.length <= MAX_TOKEN_LENGTH && !STOPWORDS_FR.has(t))
}

export function tokenFrequencies(text: string): Record<string, number> {
  const out: Record<string, number> = {}
  for (const tok of tokenize(text)) {
    out[tok] = (out[tok] ?? 0) + 1
  }
  return out
}

// FNV-1a hash for content dedup.
function hashContent(text: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return (h >>> 0).toString(16)
}

// --- Store API --------------------------------------------------------------
export function createMemoryStore(): MemoryStore {
  return { version: MEMORY_STORE_VERSION, entries: [], documentFrequency: {} }
}

export type AddMemoryDraft = {
  kind: MemoryKind
  text: string
  tags?: string[]
  importance?: number
}

/** Insère une mémoire. Si un duplicate (même contentHash) existe, bump usageCount. */
export function addMemory(store: MemoryStore, draft: AddMemoryDraft, now: Date = new Date()): MemoryStore {
  const text = draft.text.trim()
  if (text.length === 0) return store
  const contentHash = hashContent(`${draft.kind}::${text}`)
  const existing = store.entries.find((e) => e.contentHash === contentHash)
  if (existing) {
    return {
      ...store,
      entries: store.entries.map((e) => e === existing ? { ...e, usageCount: e.usageCount + 1, lastUsedAt: now.toISOString() } : e),
    }
  }
  const tokens = tokenFrequencies(text)
  const entry: MemoryEntry = {
    id: `mem_${now.getTime().toString(36)}_${contentHash.slice(0, 6)}`,
    kind: draft.kind,
    text,
    tags: draft.tags ?? [],
    importance: clamp01(draft.importance ?? 0.5),
    createdAt: now.toISOString(),
    lastUsedAt: null,
    usageCount: 0,
    contentHash,
    tokens,
  }
  const df = { ...store.documentFrequency }
  for (const tok of Object.keys(tokens)) df[tok] = (df[tok] ?? 0) + 1
  return { ...store, entries: [...store.entries, entry], documentFrequency: df }
}

export function removeMemory(store: MemoryStore, id: string): MemoryStore {
  const entry = store.entries.find((e) => e.id === id)
  if (!entry) return store
  const df = { ...store.documentFrequency }
  for (const tok of Object.keys(entry.tokens)) {
    const next = (df[tok] ?? 0) - 1
    if (next <= 0) delete df[tok]
    else df[tok] = next
  }
  return { ...store, entries: store.entries.filter((e) => e !== entry), documentFrequency: df }
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// --- TF-IDF cosine retrieval ------------------------------------------------
export type Retrieval = {
  entry: MemoryEntry
  score: number
  reason: 'similarity' | 'pinned' | 'tag-match' | 'recency'
}

export type RetrievalOptions = {
  /** Boost recency (decays by `recencyHalfLifeDays`). */
  recencyHalfLifeDays?: number
  /** Boost les pinned au-dessus de tout. */
  pinnedAlwaysFirst?: boolean
  /** Limite de résultats. */
  limit?: number
  /** Filtrage par tag (any-match). */
  requireTagsAny?: string[]
  /** Score minimum pour être retenu. */
  minScore?: number
}

/** Retrieve memories similar to `query`. BM25 + recency + importance boost. */
export function retrieve(store: MemoryStore, query: string, now: Date = new Date(), opts: RetrievalOptions = {}): Retrieval[] {
  const halfLife = opts.recencyHalfLifeDays ?? 14
  const limit = opts.limit ?? 5
  const minScore = opts.minScore ?? 0
  const queryTokens = tokenFrequencies(query)
  const D = Math.max(1, store.entries.length)

  // BM25 a besoin de la longueur moyenne des documents pour normaliser.
  let totalDocLength = 0
  for (const e of store.entries) {
    for (const c of Object.values(e.tokens)) totalDocLength += c
  }
  const avgDocLength = D > 0 ? totalDocLength / D : 1

  const scored: Retrieval[] = []

  for (const entry of store.entries) {
    if (opts.requireTagsAny && opts.requireTagsAny.length > 0 && !entry.tags.some((tag) => opts.requireTagsAny!.includes(tag))) {
      continue
    }
    const sim = bm25Score(queryTokens, entry.tokens, store.documentFrequency, D, avgDocLength)
    // Recency: exp(-Δdays / halfLife). 0 if never used → fall back to createdAt.
    const ref = entry.lastUsedAt ?? entry.createdAt
    const ageDays = (now.getTime() - new Date(ref).getTime()) / 86_400_000
    const recencyBoost = Math.exp(-Math.max(0, ageDays) / halfLife)
    const importanceBoost = 0.5 + 0.5 * entry.importance
    const score = sim * importanceBoost + 0.1 * recencyBoost
    if (score < minScore) continue
    const reason: Retrieval['reason'] = entry.kind === 'pinned'
      ? 'pinned'
      : (sim > 0 ? 'similarity' : (opts.requireTagsAny ? 'tag-match' : 'recency'))
    scored.push({ entry, score, reason })
  }

  scored.sort((a, b) => {
    if (opts.pinnedAlwaysFirst) {
      if (a.entry.kind === 'pinned' && b.entry.kind !== 'pinned') return -1
      if (b.entry.kind === 'pinned' && a.entry.kind !== 'pinned') return 1
    }
    return b.score - a.score
  })
  return scored.slice(0, limit)
}

// --- BM25 (Okapi) ----------------------------------------------------------
//
// Formule de Robertson/Spärck Jones (1995), avec k1=1.5 et b=0.75 (valeurs
// standard Lucene). Plus précis que le TF-IDF cosine pour la retrieval :
//   - sature la contribution d'un terme trop fréquent dans le doc (k1)
//   - normalise par la longueur du doc (b) — un terme dans un doc court
//     pèse plus qu'un terme dans un doc long
//   - garde l'IDF de TF-IDF pour les termes rares
//
// Référence : http://en.wikipedia.org/wiki/Okapi_BM25
const BM25_K1 = 1.5
const BM25_B = 0.75

function bm25Score(
  qTokens: Record<string, number>,
  dTokens: Record<string, number>,
  df: Record<string, number>,
  D: number,
  avgDocLength: number,
): number {
  let score = 0
  const docLength = Object.values(dTokens).reduce((a, b) => a + b, 0)
  for (const tok of Object.keys(qTokens)) {
    if (!dTokens[tok]) continue
    const dfTok = df[tok] ?? 1
    // IDF style BM25 (peut être négatif si dfTok > D/2 — on clamp ≥ 0 pour
    // éviter de pénaliser un terme commun dans plusieurs docs).
    const idf = Math.max(0, Math.log((D - dfTok + 0.5) / (dfTok + 0.5) + 1))
    const tf = dTokens[tok]
    const norm = tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * (docLength / Math.max(1, avgDocLength))))
    score += idf * norm
  }
  return score
}

/** Mark a memory as freshly used (bumps lastUsedAt + usageCount). */
export function touch(store: MemoryStore, id: string, now: Date = new Date()): MemoryStore {
  return {
    ...store,
    entries: store.entries.map((e) => e.id === id ? { ...e, lastUsedAt: now.toISOString(), usageCount: e.usageCount + 1 } : e),
  }
}

/** Drop memories below importance × usage threshold or unused for > prune days. */
export function prune(store: MemoryStore, opts: { maxEntries?: number; maxAgeDays?: number; now?: Date } = {}): MemoryStore {
  const max = opts.maxEntries ?? 500
  const maxAge = opts.maxAgeDays ?? 365
  const now = opts.now ?? new Date()
  const cutoff = now.getTime() - maxAge * 86_400_000

  const filtered = store.entries.filter((e) => {
    if (e.kind === 'pinned') return true
    const ref = e.lastUsedAt ?? e.createdAt
    return new Date(ref).getTime() > cutoff
  })
  // If still over budget, drop the lowest "importance * (1 + usage)" entries.
  if (filtered.length <= max) return rebuildDf({ ...store, entries: filtered })
  filtered.sort((a, b) => (b.importance * (1 + b.usageCount)) - (a.importance * (1 + a.usageCount)))
  return rebuildDf({ ...store, entries: filtered.slice(0, max) })
}

function rebuildDf(store: MemoryStore): MemoryStore {
  const df: Record<string, number> = {}
  for (const e of store.entries) {
    for (const tok of Object.keys(e.tokens)) df[tok] = (df[tok] ?? 0) + 1
  }
  return { ...store, documentFrequency: df }
}
