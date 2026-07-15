import type { CodeFile } from '../services/codeOrchestrator.ts'
import type { CodeStreamState } from './codeStreamTypes.ts'

/**
 * ETA from pipeline progress. `progressPct` is a 0..100 figure the
 * orchestrator emits per phase. We project total runtime from the elapsed
 * fraction and damp the remaining estimate so it never jumps wildly up.
 */
export function computeEta(
  startedAt: number | null,
  prog: number,
  prevRemaining: number | null,
): { remaining: number | null; total: number | null } {
  if (!startedAt || prog <= 2) return { remaining: prevRemaining, total: null }
  const elapsed = (Date.now() - startedAt) / 1000
  const frac = Math.min(0.98, prog / 100)
  const total = elapsed / frac
  let remaining = Math.max(0, total - elapsed)
  // Damp upward jitter : allow the estimate to fall freely but only creep up.
  if (prevRemaining !== null && remaining > prevRemaining + 8) {
    remaining = prevRemaining + 8
  }
  return { remaining: Math.round(remaining), total: Math.round(total) }
}

/** Coarse phase bucket for banner colours, derived from the detail string. */
export function phaseFromDetail(detail: string, prog: number): CodeStreamState['phase'] {
  const d = detail.toLowerCase()
  if (/marque|brand/.test(d)) return 'brand'
  if (/recherche|research|reference|inspiration|meilleures pratiques/.test(d)) return 'research'
  if (/plan|architecture|preflight|dossier|contexte de la discussion|analyse/.test(d)) return 'planning'
  if (/validation|sandbox|correction|test|verif/.test(d)) return 'validation'
  if (prog >= 30 && prog < 90) return 'streaming'
  if (prog >= 90) return 'validation'
  return 'planning'
}

/** Short assistant turn summarising what was produced (keeps history light). */
export function summariseDelivery(files: CodeFile[], score: number): string {
  const names = files.slice(0, 12).map((f) => f.name).join(', ')
  const extra = files.length > 12 ? ` (+${files.length - 12})` : ''
  return `Projet livré — ${files.length} fichier(s) : ${names}${extra}. Score ${score}%.`
}
