/**
 * Budget de contexte de la conversation : ce que le modèle voit vraiment, combien de jetons cela
 * coûte, et jusqu'où cette machine peut aller.
 *
 * Avant : l'historique entier partait avec une fenêtre fixe de 32 768 jetons. Au-delà, Ollama
 * coupe le DÉBUT du prompt sans prévenir — les instructions système disparaissaient en premier,
 * et la conversation « repartait de zéro ». Rien n'était compté.
 *
 * Maintenant :
 * - le profil du modèle est lu dans Ollama (`/api/show`) : contexte d'entraînement et taille du
 *   cache KV par jeton, en ne comptant que les couches à attention complète des architectures
 *   hybrides (Qwen 3.5/3.6, Qwen3-Next : une couche sur quatre) ;
 * - le plafond soutenable est le plus grand palier dont le cache tient dans le budget mémoire ;
 * - les jetons sont estimés avec un rapport caractères/jeton recalibré à chaque réponse sur le
 *   compte réel renvoyé par Ollama (`prompt_eval_count`) ;
 * - quand l'historique dépasse, les échanges les plus anciens sont remplacés par un résumé abrégé
 *   explicite, jamais par une coupure muette : les instructions et la demande restent entières ;
 * - la fenêtre envoyée monte par paliers, pour qu'Ollama ne recharge pas le modèle à chaque tour.
 */

export type ContextRole = 'system' | 'user' | 'assistant'
export type ContextMessage = { role: ContextRole; content: string; images?: string[] }

export type ModelContextProfile = {
  model: string
  /** contexte d'entraînement annoncé par le modèle */
  trainedContext: number | null
  /** octets de cache KV par jeton en f16, couches à attention complète seulement */
  kvBytesPerToken: number | null
  fullAttentionLayers: number | null
  source: 'ollama' | 'unknown'
}

export type ContextPlan = {
  messages: ContextMessage[]
  /** num_ctx à envoyer */
  window: number
  /** plus grande fenêtre soutenable ici (budget mémoire du cache et contexte du modèle) */
  ceiling: number
  trainedContext: number | null
  estimatedPromptTokens: number
  /** échanges anciens remplacés par le résumé abrégé */
  compactedMessages: number
  /** mémoire du cache KV à la fenêtre choisie (Gio), si le profil est connu */
  kvGiBAtWindow: number | null
  charsPerToken: number
}

// le flux de chat impose déjà num_ctx >= 16 384 (useTauri.ollamaChatStream)
export const CONTEXT_TIERS = [16384, 32768, 65536, 131072, 262144] as const
const GIB = 1024 ** 3
/** Budget par défaut du cache KV : la moitié de la VRAM d'une carte de 16 Go, le reste allant aux poids. */
export const DEFAULT_KV_BUDGET_BYTES = 6 * GIB
const KV_BUDGET_KEY = 'aurora-conversation-kv-budget-gib'
const RATIO_KEY = 'aurora-conversation-chars-per-token'
/** Valeur de départ mesurée sur du français avec les tokeniseurs Qwen, remplacée dès la première réponse. */
export const DEFAULT_CHARS_PER_TOKEN = 3.3
const SAFETY = 0.92

const numberOrNull = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value
  if (Array.isArray(value)) {
    const numbers = value.filter((v): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0)
    return numbers.length ? Math.max(...numbers) : null
  }
  return null
}

/** Profil lu dans le `model_info` d'Ollama. Rien n'est inventé : un champ absent reste inconnu. */
export function profileFromModelInfo(model: string, info: Record<string, unknown> | null | undefined): ModelContextProfile {
  if (!info) return { model, trainedContext: null, kvBytesPerToken: null, fullAttentionLayers: null, source: 'unknown' }
  const arch = typeof info['general.architecture'] === 'string' ? (info['general.architecture'] as string) : ''
  const get = (key: string) => numberOrNull(info[`${arch}.${key}`])
  const layers = get('block_count')
  const interval = get('full_attention_interval')
  const kvHeads = get('attention.head_count_kv')
  const heads = get('attention.head_count')
  const embedding = get('embedding_length')
  const keyLength = get('attention.key_length') ?? (embedding && heads ? embedding / heads : null)
  const valueLength = get('attention.value_length') ?? keyLength
  const fullLayers = layers ? (interval ? Math.ceil(layers / interval) : layers) : null
  const kvBytesPerToken = fullLayers && kvHeads && keyLength && valueLength
    ? fullLayers * kvHeads * (keyLength + valueLength) * 2
    : null
  return { model, trainedContext: get('context_length'), kvBytesPerToken, fullAttentionLayers: fullLayers, source: 'ollama' }
}

const profileCache = new Map<string, Promise<ModelContextProfile>>()

/** Profil du modèle via le pont (ou Ollama local), mis en cache par modèle. */
export function fetchModelContextProfile(
  model: string,
  fetcher: (model: string) => Promise<Record<string, unknown> | null> = defaultShowFetcher,
): Promise<ModelContextProfile> {
  const cached = profileCache.get(model)
  if (cached) return cached
  const pending = fetcher(model)
    .then((info) => profileFromModelInfo(model, info))
    .catch(() => profileFromModelInfo(model, null))
  profileCache.set(model, pending)
  return pending
}

async function defaultShowFetcher(model: string): Promise<Record<string, unknown> | null> {
  const { getBridgeUrl } = await import('../utils/runtime.ts')
  const bridge = getBridgeUrl()
  const endpoints = [bridge ? `${bridge}/proxy/ollama/api/show` : '', 'http://127.0.0.1:11434/api/show'].filter(Boolean)
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model }),
      })
      if (!response.ok) continue
      const body = await response.json() as { model_info?: Record<string, unknown> }
      if (body?.model_info) return body.model_info
    } catch {
      // point d'entrée suivant
    }
  }
  return null
}

function readNumber(key: string): number | null {
  try {
    const raw = globalThis.localStorage?.getItem(key)
    const value = raw ? Number(raw) : NaN
    return Number.isFinite(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

/** Budget mémoire du cache KV, réglable (Gio) ; par défaut 6 Gio. */
export function kvBudgetBytes(): number {
  const gib = readNumber(KV_BUDGET_KEY)
  return gib ? gib * GIB : DEFAULT_KV_BUDGET_BYTES
}

const ratios = new Map<string, number>()

export function charsPerToken(model: string): number {
  const cached = ratios.get(model)
  if (cached) return cached
  const stored = readNumber(`${RATIO_KEY}:${model}`)
  return stored ?? DEFAULT_CHARS_PER_TOKEN
}

/** Recalibre le rapport avec le compte réel d'Ollama (moyenne glissante pour lisser les écarts). */
export function calibrate(model: string, promptChars: number, promptTokens: number): number {
  if (!(promptChars > 0) || !(promptTokens > 0)) return charsPerToken(model)
  const measured = Math.min(8, Math.max(1.2, promptChars / promptTokens))
  const next = ratios.has(model) || readNumber(`${RATIO_KEY}:${model}`) ? 0.6 * charsPerToken(model) + 0.4 * measured : measured
  ratios.set(model, next)
  try { globalThis.localStorage?.setItem(`${RATIO_KEY}:${model}`, String(next)) } catch { /* conservé en mémoire */ }
  return next
}

export function estimateTokens(text: string, ratio: number = DEFAULT_CHARS_PER_TOKEN): number {
  return Math.ceil((text || '').length / Math.max(1, ratio))
}

/** Plus grand palier dont le cache tient dans le budget et que le modèle a appris. */
export function sustainableContext(profile: ModelContextProfile, budgetBytes: number = DEFAULT_KV_BUDGET_BYTES): number {
  const trained = profile.trainedContext ?? 32768
  const byMemory = profile.kvBytesPerToken ? Math.floor(budgetBytes / profile.kvBytesPerToken) : 32768
  const limit = Math.min(trained, byMemory)
  const tier = [...CONTEXT_TIERS].reverse().find((t) => t <= limit)
  return tier ?? CONTEXT_TIERS[0]
}

function messageTokens(message: ContextMessage, ratio: number): number {
  // une image envoyée au modèle de vision coûte environ un millier de jetons
  return estimateTokens(message.content, ratio) + 4 + (message.images?.length ?? 0) * 1000
}

function digestLine(message: ContextMessage): string {
  const limit = message.role === 'user' ? 240 : 360
  const text = message.content.replace(/\s+/g, ' ').trim()
  return `${message.role === 'user' ? 'UTILISATEUR' : 'ASSISTANT'} : ${text.length > limit ? `${text.slice(0, limit)}…` : text}`
}

/**
 * Messages à envoyer et fenêtre à demander. Les instructions et la demande courante sont toujours
 * entières ; les échanges récents passent tels quels tant qu'ils tiennent ; les plus anciens sont
 * résumés en tête, de façon explicite.
 */
export function planContext({
  system,
  history,
  user,
  profile,
  answerReserve = 6144,
  ratio = DEFAULT_CHARS_PER_TOKEN,
  budgetBytes = DEFAULT_KV_BUDGET_BYTES,
}: {
  system: ContextMessage
  history: ContextMessage[]
  user: ContextMessage
  profile: ModelContextProfile
  answerReserve?: number
  ratio?: number
  budgetBytes?: number
}): ContextPlan {
  const ceiling = sustainableContext(profile, budgetBytes)
  const reserve = Math.min(answerReserve, Math.floor(ceiling / 4))
  const fixed = messageTokens(system, ratio) + messageTokens(user, ratio) + reserve
  const room = Math.max(0, Math.floor(ceiling * SAFETY) - fixed)

  const kept: ContextMessage[] = []
  let used = 0
  let index = history.length - 1
  for (; index >= 0; index -= 1) {
    const cost = messageTokens(history[index], ratio)
    if (used + cost > room) break
    kept.unshift(history[index])
    used += cost
  }
  const dropped = history.slice(0, index + 1)

  let digest: ContextMessage | null = null
  if (dropped.length) {
    const digestRoom = Math.min(Math.floor(ceiling * 0.15), Math.max(0, room - used))
    const lines: string[] = []
    let digestTokens = 0
    for (let i = dropped.length - 1; i >= 0; i -= 1) {
      const line = digestLine(dropped[i])
      const cost = estimateTokens(line, ratio) + 1
      if (digestTokens + cost > digestRoom) break
      lines.unshift(line)
      digestTokens += cost
    }
    if (lines.length) {
      digest = {
        role: 'system',
        content: `Résumé abrégé des ${dropped.length} message(s) plus ancien(s) de cette conversation (leur texte complet `
          + `n'est plus dans le contexte ; ne prétends pas t'en souvenir mot pour mot) :\n${lines.join('\n')}`,
      }
      used += digestTokens + 20
    }
  }

  const messages = [system, ...(digest ? [digest] : []), ...kept, user]
  const estimatedPromptTokens = fixed - reserve + used
  const needed = estimatedPromptTokens + reserve
  const window = CONTEXT_TIERS.find((t) => t >= needed && t <= ceiling) ?? ceiling
  return {
    messages,
    window,
    ceiling,
    trainedContext: profile.trainedContext,
    estimatedPromptTokens,
    compactedMessages: dropped.length,
    kvGiBAtWindow: profile.kvBytesPerToken ? Math.round((profile.kvBytesPerToken * window / GIB) * 100) / 100 : null,
    charsPerToken: ratio,
  }
}
