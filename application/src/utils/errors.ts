function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function normalizeRuntimeMessage(message: string) {
  const compact = message.replace(/\s+/g, ' ').trim()

  if (/event\.listen not allowed/i.test(compact)) {
    return 'Flux Tauri non autorise pour cette fenetre — suivi degrade, le runtime sera relance automatiquement si necessaire.'
  }

  // IMPORTANT: do NOT rewrite ComfyUI / Ollama "ne repond pas" errors anymore.
  // The old wording ("Aurora relance le service image puis reprend la generation")
  // was misleading: nothing was actually being relaunched, the user was stuck
  // looping on the same error forever. We now preserve the raw diagnostic
  // (which contains the exact bridge / HTTP / tunnel cause) so you can act on it.

  if (/timeout pendant la generation image/i.test(compact)) {
    return 'Le rendu image a depasse le delai de surveillance. ' + compact
  }

  return compact
}

function collectMessages(value: unknown, bucket: string[]) {
  if (!value) {
    return
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (trimmed) {
      bucket.push(trimmed)
    }
    return
  }

  if (value instanceof Error) {
    if (value.message.trim()) {
      bucket.push(value.message.trim())
    }
    return
  }

  if (Array.isArray(value)) {
    value.forEach((entry) => collectMessages(entry, bucket))
    return
  }

  if (isRecord(value)) {
    for (const key of ['message', 'error', 'details', 'detail', 'cause']) {
      if (key in value) {
        collectMessages(value[key], bucket)
      }
    }

    try {
      const serialized = JSON.stringify(value)
      if (serialized && serialized !== '{}' && serialized !== '[]') {
        bucket.push(serialized)
      }
    } catch {
      // Ignore serialization issues.
    }
  }
}

export function getErrorMessage(error: unknown, fallback = 'Erreur inconnue.') {
  const messages: string[] = []
  collectMessages(error, messages)

  const normalized = messages
    .map((message) => normalizeRuntimeMessage(message.replace(/^Error:\s*/i, '').trim()))
    .filter(Boolean)

  if (normalized.length === 0) {
    return fallback
  }

  return [...new Set(normalized)].join(' | ')
}

export function toError(error: unknown, fallback = 'Erreur inconnue.') {
  return error instanceof Error ? error : new Error(getErrorMessage(error, fallback))
}

/**
 * Parse JSON d'une Response fetch de manière sûre.
 * Détecte les réponses HTML (erreur courante: proxy renvoie index.html au lieu de JSON)
 * et lance une erreur lisible au lieu de "Unexpected token '<'".
 */
export async function safeParseJson<T = unknown>(response: Response, label = 'API'): Promise<T> {
  const text = await response.text()

  if (!response.ok) {
    const detail = text ? `: ${text.slice(0, 280)}` : ''
    throw new Error(`${label} a retourne ${response.status}${detail}`)
  }

  if (!text || !text.trim()) {
    return {} as T
  }

  // Détection HTML: le proxy Vite ou le serveur peut retourner index.html
  const trimmed = text.trimStart()
  if (trimmed.startsWith('<') || trimmed.startsWith('<!')) {
    throw new Error(
      `${label}: reponse HTML au lieu de JSON (le service est peut-etre indisponible). ` +
      `Debut: ${trimmed.slice(0, 80)}...`
    )
  }

  try {
    return JSON.parse(text) as T
  } catch {
    throw new Error(
      `${label}: reponse non-JSON invalide. Debut: ${text.slice(0, 120)}...`
    )
  }
}
