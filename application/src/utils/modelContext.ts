/**
 * v82hn : limites contextuelles connues par modèle Ollama.
 * Approximation utilisée pour warner l'user quand le thread approche
 * de la limite. Les valeurs proviennent de Ollama / model cards.
 *
 * Si le modèle n'est pas listé, fallback à 8192 tokens (sécurité
 * conservative — la plupart des modèles font au moins ça).
 */

const KNOWN: Array<{ pattern: RegExp; ctxTokens: number }> = [
  // Qwen 3.8 : 262k natif
  { pattern: /qwen3\.8|qwen38/i, ctxTokens: 262144 },
  // Qwen3 / Qwen3-Coder : 32k natif, 128k via YaRN.
  { pattern: /qwen3-?32b|qwen3:32b|qwen3-coder/i, ctxTokens: 32768 },
  { pattern: /qwen3/i, ctxTokens: 32768 },
  // Llama 3.x : 128k context.
  { pattern: /llama-?3|llama4/i, ctxTokens: 128000 },
  // Mistral / Mistral-Nemo : 32k typique.
  { pattern: /mistral|nemo/i, ctxTokens: 32768 },
  // Gemma 3 : 8k typique.
  { pattern: /gemma3?:?\d/i, ctxTokens: 8192 },
  // Gemma 2 : 8k.
  { pattern: /gemma/i, ctxTokens: 8192 },
  // Phi-3 : 4k ou 128k selon variante.
  { pattern: /phi-?3|phi3/i, ctxTokens: 16384 },
  // DeepSeek : 64k.
  { pattern: /deepseek/i, ctxTokens: 65536 },
  // Codestral : 32k.
  { pattern: /codestral/i, ctxTokens: 32768 },
]

const FALLBACK_CTX = 8192

export function getModelContextLimit(model: string): number {
  if (!model) return FALLBACK_CTX
  for (const { pattern, ctxTokens } of KNOWN) {
    if (pattern.test(model)) return ctxTokens
  }
  return FALLBACK_CTX
}

/**
 * Renvoie le ratio (0-1) du thread vs limite. >0.85 = warning.
 */
export function getContextUsage(model: string, totalChars: number): {
  tokens: number
  limit: number
  ratio: number
  level: 'safe' | 'warn' | 'danger'
} {
  const tokens = Math.ceil(totalChars / 4)
  const limit = getModelContextLimit(model)
  const ratio = limit > 0 ? tokens / limit : 0
  const level = ratio > 0.95 ? 'danger' : ratio > 0.75 ? 'warn' : 'safe'
  return { tokens, limit, ratio, level }
}
