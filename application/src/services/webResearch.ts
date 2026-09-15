/**
 * webResearch — la recherche du module conversation, en vrai.
 *
 * Ce que faisait le module avant : le prompt système annonçait « Tu as accès
 * à la recherche web », et l'étape appelée « Recherche » demandait au modèle
 * d'énumérer ce qu'il croyait savoir. Aucune requête ne sortait de la
 * machine. Une réponse sur un sujet postérieur à l'entraînement était donc
 * inventée avec l'aplomb d'une réponse sourcée, et il n'y avait rien à
 * montrer à l'utilisateur.
 *
 * Ce fichier fait sortir les requêtes : le pont expose déjà
 * /api/web/search, /api/web/extract et /api/web/images (crawl4ai_search.py,
 * avec repli DuckDuckGo HTML). On les enchaîne — plan de requêtes, recherche,
 * lecture des meilleures pages, images, vidéos — et on renvoie à la fois le
 * contexte à donner au modèle ET la liste des sites visités à afficher.
 *
 * Chaque étape rappelle `onSource` pour que l'interface montre le site au
 * moment où il est consulté, pas à la fin.
 */
import { getBridgeUrl } from '../utils/runtime.ts'
import { ollamaGenerate } from '../hooks/useTauri.ts'
import { domainOf, parseVideoEmbed } from '../utils/mediaLinks.ts'
import type { WebSource } from '../types/app.ts'

export type { WebSource }

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

let sourceCounter = 0
function nextSourceId(): string {
  sourceCounter += 1
  return `src-${sourceCounter}-${Date.now().toString(36)}`
}

function bridge(url?: string): string {
  return (url ?? getBridgeUrl()).replace(/\/$/, '')
}

async function postJson(
  path: string,
  body: unknown,
  options: { bridgeUrl?: string; fetchImpl?: FetchLike; timeoutMs?: number; signal?: AbortSignal },
): Promise<unknown> {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis)
  const timeoutMs = Math.max(1_000, Math.min(120_000, options.timeoutMs ?? 30_000))
  // On combine l'abort utilisateur (bouton stop) et le timeout : sans ça,
  // arrêter la génération laissait la recherche tourner en fond.
  const timeout = AbortSignal.timeout(timeoutMs)
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout
  const response = await fetchImpl(`${bridge(options.bridgeUrl)}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const text = await response.text()
  // Le pont éteint renvoie la page d'index de Vite : du HTML, pas du JSON.
  if (!text || text.trimStart().startsWith('<')) throw new Error('reponse non JSON')
  return JSON.parse(text)
}

// ---------------------------------------------------------------------------
// Décider s'il faut chercher
// ---------------------------------------------------------------------------

/** Demande explicite de recherche : l'utilisateur le dit avec ses mots. */
const EXPLICIT_RE = /\b(cherche|recherche|google|sur le web|sur internet|en ligne|source|sources|sourc[eé]|r[eé]f[eé]rence|lien|liens|site|sites|article|articles|actualit[eé]|news|derni[eè]res? nouvelles?|documente|documentation officielle)\b/i

/** Sujets que la mémoire d'un modèle ne peut pas couvrir de façon fiable. */
const VOLATILE_RE = /\b(aujourd hui|aujourd'hui|hier|demain|ce matin|cette semaine|ce mois|cette ann[eé]e|en ce moment|actuel|actuelle|actuellement|maintenant|r[eé]cent|r[eé]cente|derni[eè]re version|derni[eè]re mise [aà] jour|prix|tarif|co[uû]te|combien co[uû]te|m[eé]t[eé]o|cours de|bourse|classement|r[eé]sultat|score|sortie|date de sortie|qui a gagn[eé]|202[4-9]|203\d)\b/i

/** Une réponse fausse sur ces sujets se voit tout de suite : on va vérifier. */
const FACTUAL_RE = /\b(qui est|qui sont|c est quoi|qu est-ce que|quelle est|quel est|o[uù] se trouve|combien|quand|statistiques?|chiffres?|population|biographie)\b/i

export type WebResearchDecision = {
  search: boolean
  reason: string
}

/**
 * Faut-il sortir sur le web pour cette demande ?
 *
 * `mode` vient de l'interrupteur de l'interface : 'on' force (l'utilisateur a
 * cliqué sur le globe), 'off' interdit (travail hors ligne, ou question sur
 * le code de l'utilisateur), 'auto' laisse décider l'heuristique.
 */
export function decideWebResearch(
  userInput: string,
  mode: 'auto' | 'on' | 'off' = 'auto',
): WebResearchDecision {
  const text = (userInput || '').trim()
  if (mode === 'off') return { search: false, reason: 'recherche web desactivee' }
  if (!text) return { search: false, reason: 'demande vide' }
  if (mode === 'on') return { search: true, reason: 'recherche forcee par l utilisateur' }

  const lower = text.toLowerCase()
  if (EXPLICIT_RE.test(lower)) return { search: true, reason: 'demande explicite de sources' }
  if (VOLATILE_RE.test(lower)) return { search: true, reason: 'information datee ou changeante' }
  if (/https?:\/\//i.test(text)) return { search: true, reason: 'une URL est citee dans la demande' }
  // Une question factuelle un peu longue mérite une vérification externe ;
  // « salut » ou « merci » n'ont rien à chercher.
  if (FACTUAL_RE.test(lower) && text.split(/\s+/).length >= 4) {
    return { search: true, reason: 'question factuelle verifiable' }
  }
  return { search: false, reason: 'connaissance interne suffisante' }
}

// ---------------------------------------------------------------------------
// Plan de requêtes
// ---------------------------------------------------------------------------

function fallbackQueries(userInput: string): string[] {
  const cleaned = userInput
    .replace(/[?!.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned ? [cleaned.slice(0, 180)] : []
}

/**
 * Traduit la demande en 1 à 3 requêtes de moteur.
 *
 * Envoyer la phrase de l'utilisateur telle quelle marche mal : « tu peux me
 * dire où en est le projet Artemis et si le lancement a bougé ? » n'est pas
 * une requête. On demande au modèle de la réécrire, et on retombe sur la
 * phrase nettoyée si le modèle est injoignable.
 */
export async function planSearchQueries(
  userInput: string,
  model: string,
  options: { maxQueries?: number; signal?: AbortSignal; generate?: typeof ollamaGenerate } = {},
): Promise<string[]> {
  const max = Math.max(1, Math.min(3, options.maxQueries ?? 2))
  const generate = options.generate ?? ollamaGenerate
  const prompt = `Transforme la demande en ${max} requete(s) de moteur de recherche.

Regles:
- Une requete par ligne, rien d autre. Pas de numerotation, pas de guillemets.
- Mots-cles denses, pas de phrase complete, pas de question.
- Garde la langue de la demande.
- Si un nom propre, une version ou une date est cite, il doit apparaitre.

Demande: ${userInput.slice(0, 600)}`

  try {
    const raw = await generate(model, prompt)
    const text = String((raw as { response?: string })?.response ?? '')
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<think>[\s\S]*$/g, '')
    const lines = text
      .split('\n')
      .map((line) => line.replace(/^\s*[-*\d.)\]]+\s*/, '').replace(/^["'«]|["'»]$/g, '').trim())
      .filter((line) => line.length >= 3 && line.length <= 200 && !/^(voici|requ[eê]te)/i.test(line))
    const unique: string[] = []
    for (const line of lines) {
      if (!unique.some((q) => q.toLowerCase() === line.toLowerCase())) unique.push(line)
      if (unique.length >= max) break
    }
    if (unique.length > 0) return unique
  } catch {
    /* modele injoignable : on garde la phrase nettoyee */
  }
  return fallbackQueries(userInput)
}

// ---------------------------------------------------------------------------
// Appels au pont
// ---------------------------------------------------------------------------

type RawResult = { title?: unknown; url?: unknown; snippet?: unknown }

function normalizeResults(payload: unknown): Array<{ title: string; url: string; snippet: string }> {
  if (!payload || typeof payload !== 'object') return []
  const record = payload as Record<string, unknown>
  const list = Array.isArray(record.resultsList)
    ? record.resultsList
    : Array.isArray(record.results)
      ? record.results
      : []
  const out: Array<{ title: string; url: string; snippet: string }> = []
  for (const row of list as RawResult[]) {
    if (!row || typeof row !== 'object') continue
    const url = typeof row.url === 'string' ? row.url.trim() : ''
    if (!/^https?:\/\//i.test(url)) continue
    out.push({
      url,
      title: typeof row.title === 'string' && row.title.trim() ? row.title.trim() : domainOf(url),
      snippet: typeof row.snippet === 'string' ? row.snippet.trim() : '',
    })
  }
  return out
}

export type WebCallOptions = {
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
  timeoutMs?: number
}

/** Résultats de recherche bruts pour une requête. */
export async function webSearch(
  query: string,
  limit = 6,
  options: WebCallOptions = {},
): Promise<Array<{ title: string; url: string; snippet: string }>> {
  if (!query.trim()) return []
  try {
    const payload = await postJson('/api/web/search', { query, limit }, { ...options, timeoutMs: options.timeoutMs ?? 35_000 })
    return normalizeResults(payload).slice(0, limit)
  } catch {
    return []
  }
}

/** Contenu texte d'une page. Vide si le site refuse ou dépasse le délai. */
export async function webExtract(
  url: string,
  options: WebCallOptions & { prompt?: string } = {},
): Promise<string> {
  try {
    const payload = await postJson(
      '/api/web/extract',
      { url, prompt: options.prompt ?? '' },
      { ...options, timeoutMs: options.timeoutMs ?? 35_000 },
    ) as Record<string, unknown>
    if (payload?.ok === false) return ''
    for (const key of ['content', 'markdown', 'text', 'extracted']) {
      const value = payload?.[key]
      if (typeof value === 'string' && value.trim().length > 80) return value.trim()
    }
    return ''
  } catch {
    return ''
  }
}

export type WebImage = {
  url: string
  thumb?: string
  alt?: string
  sourcePage?: string
  license?: string
  width?: number
  height?: number
}

/** Photos réellement affichables, avec leur page d'origine. */
export async function webImages(
  query: string,
  limit = 6,
  options: WebCallOptions = {},
): Promise<WebImage[]> {
  if (!query.trim()) return []
  try {
    const payload = await postJson('/api/web/images', { query, limit }, { ...options, timeoutMs: options.timeoutMs ?? 35_000 }) as Record<string, unknown>
    const list = Array.isArray(payload?.images) ? payload.images : []
    const out: WebImage[] = []
    for (const row of list as Array<Record<string, unknown>>) {
      const url = typeof row?.url === 'string' ? row.url : ''
      if (!/^https?:\/\//i.test(url)) continue
      out.push({
        url,
        thumb: typeof row.thumb === 'string' ? row.thumb : undefined,
        alt: typeof row.alt === 'string' ? row.alt : undefined,
        sourcePage: typeof row.sourcePage === 'string' ? row.sourcePage : undefined,
        license: typeof row.license === 'string' ? row.license : undefined,
        width: typeof row.width === 'number' ? row.width : undefined,
        height: typeof row.height === 'number' ? row.height : undefined,
      })
      if (out.length >= limit) break
    }
    return out
  } catch {
    return []
  }
}

/** Vidéos lisibles dans la conversation (YouTube/Vimeo/Dailymotion). */
export async function webVideos(
  query: string,
  limit = 4,
  options: WebCallOptions = {},
): Promise<Array<{ url: string; title: string; thumb?: string }>> {
  const results = await webSearch(`${query} video`, limit * 3, options)
  const out: Array<{ url: string; title: string; thumb?: string }> = []
  for (const row of results) {
    const embed = parseVideoEmbed(row.url)
    if (!embed) continue
    if (out.some((v) => v.url === row.url)) continue
    out.push({ url: row.url, title: row.title, thumb: embed.thumbUrl ?? undefined })
    if (out.length >= limit) break
  }
  return out
}

// ---------------------------------------------------------------------------
// Recherche complète
// ---------------------------------------------------------------------------

export type WebResearchOptions = {
  userInput: string
  model: string
  mode?: 'auto' | 'on' | 'off'
  /** Nombre de requêtes envoyées au moteur. */
  maxQueries?: number
  /** Résultats gardés par requête. */
  perQuery?: number
  /** Pages dont on lit réellement le contenu (le reste reste en extrait). */
  maxPagesRead?: number
  /** Chercher aussi des photos et des vidéos à afficher. */
  wantMedia?: boolean
  signal?: AbortSignal
  bridgeUrl?: string
  fetchImpl?: FetchLike
  /** Appelée à chaque changement d'état d'une source (affichage en direct). */
  onSource?: (source: WebSource) => void
  /** Appelée quand le plan de requêtes est prêt. */
  onQueries?: (queries: string[]) => void
  /** Progression lisible pour la barre d'étapes. */
  onProgress?: (label: string, detail: string) => void
  /** Injection de test. */
  deps?: {
    planQueries?: typeof planSearchQueries
    search?: typeof webSearch
    extract?: typeof webExtract
    images?: typeof webImages
    videos?: typeof webVideos
  }
}

export type WebResearchResult = {
  searched: boolean
  reason: string
  queries: string[]
  sources: WebSource[]
  /** Bloc à coller dans le prompt système, déjà numéroté pour les citations. */
  context: string
}

const MAX_CONTENT_CHARS = 2_400
const MAX_CONTEXT_CHARS = 9_000

function buildContext(sources: WebSource[]): string {
  const pages = sources.filter((s) => s.kind === 'page')
  if (pages.length === 0) return ''
  const blocks: string[] = []
  let total = 0
  for (const source of pages) {
    const body = (source.content || source.snippet || '').slice(0, MAX_CONTENT_CHARS).trim()
    if (!body) continue
    const block = `[${source.rank}] ${source.title}\nURL: ${source.url}\n${body}`
    if (total + block.length > MAX_CONTEXT_CHARS) break
    blocks.push(block)
    total += block.length
  }
  return blocks.join('\n\n---\n\n')
}

/**
 * Recherche complète : plan de requêtes, moteur, lecture des meilleures
 * pages, médias. Ne lève jamais — un web injoignable rend `searched: false`
 * et le tour continue sur la connaissance interne, en le disant.
 */
export async function runWebResearch(options: WebResearchOptions): Promise<WebResearchResult> {
  const {
    userInput,
    model,
    mode = 'auto',
    maxQueries = 2,
    perQuery = 5,
    maxPagesRead = 3,
    wantMedia = true,
    signal,
    onSource,
    onQueries,
    onProgress,
    deps = {},
  } = options

  const decision = decideWebResearch(userInput, mode)
  if (!decision.search) {
    return { searched: false, reason: decision.reason, queries: [], sources: [], context: '' }
  }

  const planQueries = deps.planQueries ?? planSearchQueries
  const search = deps.search ?? webSearch
  const extract = deps.extract ?? webExtract
  const images = deps.images ?? webImages
  const videos = deps.videos ?? webVideos
  const call: WebCallOptions = { bridgeUrl: options.bridgeUrl, fetchImpl: options.fetchImpl, signal }

  onProgress?.('Recherche', 'Formulation des requetes.')
  const queries = await planQueries(userInput, model, { maxQueries, signal })
  if (queries.length === 0) {
    return { searched: false, reason: 'aucune requete exploitable', queries: [], sources: [], context: '' }
  }
  onQueries?.(queries)

  const sources: WebSource[] = []
  const seen = new Set<string>()

  for (const query of queries) {
    if (signal?.aborted) break
    onProgress?.('Recherche', `Moteur : « ${query} »`)
    const results = await search(query, perQuery, call)
    for (const row of results) {
      const key = row.url.replace(/#.*$/, '')
      if (seen.has(key)) continue
      seen.add(key)
      const source: WebSource = {
        id: nextSourceId(),
        url: row.url,
        domain: domainOf(row.url),
        title: row.title,
        snippet: row.snippet,
        kind: 'page',
        status: 'found',
        query,
        rank: sources.filter((s) => s.kind === 'page').length + 1,
        fetchedAt: Date.now(),
      }
      sources.push(source)
      onSource?.({ ...source })
    }
  }

  if (sources.length === 0) {
    return {
      searched: false,
      reason: 'le moteur n a rien renvoye (pont eteint ou reseau coupe)',
      queries,
      sources: [],
      context: '',
    }
  }

  // Lecture réelle des meilleures pages : un extrait de moteur fait deux
  // lignes, ce qui suffit à citer mais pas à répondre.
  const toRead = sources.filter((s) => s.kind === 'page').slice(0, Math.max(0, maxPagesRead))
  for (const source of toRead) {
    if (signal?.aborted) break
    source.status = 'reading'
    onProgress?.('Lecture', `Ouverture de ${source.domain}`)
    onSource?.({ ...source })
    const content = await extract(source.url, { ...call, prompt: userInput.slice(0, 300) })
    if (content) {
      source.content = content.slice(0, MAX_CONTENT_CHARS)
      source.status = 'read'
    } else {
      // Pas d'échec silencieux : la carte reste, marquée comme illisible.
      source.status = 'failed'
    }
    onSource?.({ ...source })
  }

  if (wantMedia && !signal?.aborted) {
    onProgress?.('Medias', 'Recherche de photos et de videos.')
    const mediaQuery = queries[0]
    const [photos, clips] = await Promise.all([
      images(mediaQuery, 6, call).catch(() => []),
      videos(mediaQuery, 3, call).catch(() => []),
    ])
    for (const photo of photos) {
      if (seen.has(photo.url)) continue
      seen.add(photo.url)
      const source: WebSource = {
        id: nextSourceId(),
        url: photo.url,
        domain: domainOf(photo.sourcePage || photo.url),
        title: photo.alt || 'Image',
        snippet: '',
        kind: 'image',
        status: 'found',
        query: mediaQuery,
        thumb: photo.thumb || photo.url,
        sourcePage: photo.sourcePage,
        license: photo.license,
        fetchedAt: Date.now(),
      }
      sources.push(source)
      onSource?.({ ...source })
    }
    for (const clip of clips) {
      if (seen.has(clip.url)) continue
      seen.add(clip.url)
      const source: WebSource = {
        id: nextSourceId(),
        url: clip.url,
        domain: domainOf(clip.url),
        title: clip.title,
        snippet: '',
        kind: 'video',
        status: 'found',
        query: mediaQuery,
        thumb: clip.thumb,
        fetchedAt: Date.now(),
      }
      sources.push(source)
      onSource?.({ ...source })
    }
  }

  return {
    searched: true,
    reason: decision.reason,
    queries,
    sources,
    context: buildContext(sources),
  }
}

/** Consigne de citation ajoutée au prompt système quand des sources existent. */
export function buildCitationInstructions(result: WebResearchResult): string {
  if (!result.searched || !result.context) return ''
  const list = result.sources
    .filter((s) => s.kind === 'page' && s.rank)
    .map((s) => `[${s.rank}] ${s.domain} — ${s.title}`)
    .join('\n')
  return `
SOURCES WEB CONSULTEES A L INSTANT (${new Date().toLocaleDateString('fr-FR')}) :
${list}

CONTENU DES SOURCES :
${result.context}

REGLES DE SOURCAGE:
- Ces extraits viennent du web maintenant : ils priment sur ta memoire en cas de contradiction.
- Cite la source entre crochets juste apres l affirmation qu elle soutient : [1], [2].
- N invente aucune reference : n utilise que les numeros ci-dessus.
- Si les sources ne repondent pas a la question, dis-le au lieu de combler avec ta memoire.`
}
