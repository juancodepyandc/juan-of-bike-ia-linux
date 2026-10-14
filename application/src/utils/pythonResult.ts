/** Read complete top-level JSON objects among progress logs, including pretty JSON. */
export function parsePythonResult<T = Record<string, unknown>>(output: string): T | null {
  let start = -1, depth = 0, quoted = false, escaped = false
  let last: T | null = null
  let outcome: T | null = null
  for (let i = 0; i < output.length; i++) {
    const char = output[i]
    if (start < 0) {
      if (char !== '{') continue
      start = i; depth = 1; quoted = false; escaped = false
      continue
    }
    if (quoted) {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === '"') quoted = false
      continue
    }
    if (char === '"') quoted = true
    else if (char === '{') depth++
    else if (char === '}' && --depth === 0) {
      try {
        const parsed = JSON.parse(output.slice(start, i + 1))
        last = parsed as T
        if (['ok', 'error', 'path', 'final_mesh', 'acceptance_ok', 'livraison'].some(key => key in parsed)) outcome = last
      } catch { /* log, not JSON */ }
      start = -1
    }
  }
  return outcome ?? last
}
