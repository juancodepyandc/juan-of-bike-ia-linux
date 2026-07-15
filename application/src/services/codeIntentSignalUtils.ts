// ---------------------------------------------------------------------------
// Code intent signal utilities
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

export function normalizeSignalText(text: string) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function escapeRegex(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function containsSignal(source: string, signal: string) {
  const normalizedSignal = normalizeSignalText(signal).trim()
  if (!normalizedSignal) return false

  const pattern = escapeRegex(normalizedSignal).replace(/\s+/g, '\\s+')
  return new RegExp(`(^|[^a-z0-9])${pattern}(?=[^a-z0-9]|$)`, 'i').test(source)
}

export function containsAnySignal(source: string, signals: Iterable<string>) {
  for (const signal of signals) {
    if (containsSignal(source, signal)) return true
  }
  return false
}
