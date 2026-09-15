import { ollamaGenerate } from '../hooks/useTauri.ts'
import { resilientOllamaGenerate } from './ollamaResilience.ts'
import { withTimeout } from './llmTimebox.ts'

function tryParseJson<T>(candidate: string): T | null {
  try {
    return JSON.parse(candidate) as T
  } catch {
    return null
  }
}

export function extractFirstJsonBlock<T>(text: string): T | null {
  if (!text.trim()) return null

  // Strip markdown code fences that models sometimes add
  const cleaned = text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '').trim()

  const direct = tryParseJson<T>(cleaned)
  if (direct) return direct

  // Try to find the outermost balanced braces
  const objectMatch = cleaned.match(/\{[\s\S]*\}/)
  if (objectMatch) {
    const parsed = tryParseJson<T>(objectMatch[0])
    if (parsed) return parsed
  }

  const arrayMatch = cleaned.match(/\[[\s\S]*\]/)
  if (arrayMatch) {
    const parsed = tryParseJson<T>(arrayMatch[0])
    if (parsed) return parsed
  }

  return null
}

export async function generateJsonFromModel<T>(
  model: string,
  prompt: string,
  fallback: T,
  options?: {
    timeoutMs?: number
    firstByteTimeoutMs?: number
    resilient?: boolean
    num_ctx?: number
  },
): Promise<T> {
  try {
    const responsePromise = options?.resilient
      ? resilientOllamaGenerate(model, prompt, {
          timeoutMs: options.timeoutMs,
          firstByteTimeoutMs: options.firstByteTimeoutMs,
          num_ctx: options.num_ctx,
        })
      : ollamaGenerate(model, prompt, {
          num_ctx: options?.num_ctx,
          firstByteTimeoutMs: options?.firstByteTimeoutMs,
        })

    const response = options?.timeoutMs && !options?.resilient
      ? await withTimeout(responsePromise, {
          label: `JSON generation (${model})`,
          timeoutMs: options.timeoutMs,
        })
      : await responsePromise

    const parsed = extractFirstJsonBlock<T>(response?.response || '')
    return parsed ?? fallback
  } catch {
    return fallback
  }
}
