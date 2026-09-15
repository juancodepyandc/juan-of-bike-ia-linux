import type { AssistantTurnVerification } from '../types/app.ts'

export function verificationNonFaite(reason: string): AssistantTurnVerification {
  return {
    verified: false,
    score: 0,
    confidence: 0,
    verdict: 'ready',
    summary: `Aucune verification : ${reason}.`,
    strengths: [],
    corrections: [],
    unsupportedClaims: [],
    missingPoints: [],
  }
}

export function normalizeVerification(input: unknown): AssistantTurnVerification {
  const value = input && typeof input === 'object' ? input as Record<string, unknown> : {}
  const verdict = value.verdict
  if (
    value.__verification_absente__ === true
    || value.verified === false
    || typeof value.score !== 'number' || !Number.isFinite(value.score)
    || typeof value.confidence !== 'number' || !Number.isFinite(value.confidence)
    || (verdict !== 'ready' && verdict !== 'refine' && verdict !== 'blocked')
  ) {
    return verificationNonFaite('le verificateur n a pas rendu de jugement complet et lisible')
  }
  const strings = (items: unknown): string[] => Array.isArray(items)
    ? items.filter((item): item is string => typeof item === 'string')
    : []
  return {
    verified: true,
    score: Math.max(0, Math.min(100, value.score)),
    confidence: Math.max(0, Math.min(100, value.confidence)),
    verdict,
    summary: typeof value.summary === 'string' && value.summary.trim() ? value.summary.trim() : 'Verification terminee.',
    strengths: strings(value.strengths),
    corrections: strings(value.corrections),
    unsupportedClaims: strings(value.unsupportedClaims),
    missingPoints: strings(value.missingPoints),
  }
}

/** The verifier must evaluate the actual replacement text before it receives a score. */
export async function verifyRefinedResponse(
  draft: string,
  verification: AssistantTurnVerification,
  refine: () => Promise<string>,
  verify: (text: string) => Promise<unknown>,
): Promise<{ finalText: string; verification: AssistantTurnVerification }> {
  const refined = (await refine()).trim()
  if (!refined || refined === draft) return { finalText: draft, verification }
  return { finalText: refined, verification: normalizeVerification(await verify(refined)) }
}
