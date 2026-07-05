/**
 * flashcardVerification — second-pass fact-check on AI-generated flashcards.
 *
 * Why: the user explicitly said "pas de fausses cartes". The current pipeline
 * generates flashcards in one LLM call grounded on Wikipedia + DuckDuckGo
 * extracts, which already cuts hallucinations down — but it's a single shot
 * and the model can still slip a wrong date, a confused author, or a
 * hallucinated formula. This module re-reads each card against the same
 * sources and either:
 *   - confirms it (verified)
 *   - flags it as general knowledge (no source coverage, but plausible)
 *   - flags it as uncertain (suspicious but not provably wrong)
 *   - rejects it (provably wrong vs. sources)
 *
 * Verified + general + uncertain are kept (with a status badge).
 * Rejected cards are discarded and reported so the UI can surface "X cards
 * removed during fact-check".
 */

import { ollamaChat } from '../hooks/useTauri'
import type { Flashcard } from '../stores/flashcardsStore'
import type { LearningSource } from './learningResearch'

export type VerificationStatus = 'verified' | 'general' | 'uncertain' | 'contradicted'

export type CardVerificationResult = {
  cardIndex: number
  status: VerificationStatus
  citedSources: number[]
  reasoning: string
  /** When the card is contradicted, what specifically the model thinks is wrong. */
  contradiction?: string
  /** When the model can produce a corrected card it overrides the original. */
  correctedFront?: string
  correctedBack?: string
}

export type FlashcardVerificationReport = {
  totalProcessed: number
  verified: number
  general: number
  uncertain: number
  rejected: number
  results: CardVerificationResult[]
}

type RawDraft = Partial<Flashcard> & {
  front?: string
  back?: string
  summary?: string
  example?: string
  formula?: string
  quote?: string
  quoteAuthor?: string
}

const VERIFICATION_SYSTEM_PROMPT = `Tu es un correcteur factuel rigoureux. Pour chaque fiche fournie tu dois decider parmi:
- "verified" : la fiche est expressement couverte par AU MOINS UNE source fournie.
- "general" : la fiche est plausible et bien formee mais aucune source ne la couvre directement (connaissance generale acceptable).
- "uncertain" : la fiche contient une affirmation qui te semble douteuse sans pouvoir la trancher.
- "contradicted" : une source fournie contredit clairement la fiche (date fausse, auteur faux, formule fausse, citation faussement attribuee, definition erronee, etc.).

Quand la fiche est "contradicted", tu fournis un correctif court ("correctedFront" et/ou "correctedBack"). Sinon ces champs sont absents.

Ta sortie est UN UNIQUE objet JSON sous la forme:
{ "results": [ { "cardIndex": <int>, "status": "...", "citedSources": [<int>...], "reasoning": "1-2 phrases", "contradiction": "...", "correctedFront": "...", "correctedBack": "..." } ] }

Regles strictes:
- "citedSources" est la liste des indices [S1, S2, ...] des sources qui couvrent la fiche (vide si "general").
- N invente PAS de source. Si aucune source ne couvre la fiche, status = "general" (pas "verified").
- Si tu hesites entre "uncertain" et "contradicted", choisis "contradicted" UNIQUEMENT quand une source liste explicitement la bonne valeur.
- Reponds en francais, JSON uniquement, aucun texte avant/apres.`

function buildSourcesBlock(sources: LearningSource[]): string {
  if (sources.length === 0) return 'Aucune source externe — verifie sur la base de la coherence interne uniquement.'
  return sources
    .map((source, index) => {
      const origin =
        source.origin === 'wikipedia-fr'
          ? 'Wikipedia FR'
          : source.origin === 'wikipedia-en'
            ? 'Wikipedia EN'
            : source.origin === 'duckduckgo'
              ? 'DuckDuckGo'
              : 'Synthese'
      const url = source.url ? ` (${source.url})` : ''
      return `[S${index + 1}] ${origin} — ${source.title}${url}\n  ${source.extract}`
    })
    .join('\n\n')
}

function buildCardsBlock(cards: RawDraft[]): string {
  return cards
    .map((card, index) => {
      const lines: string[] = [`Fiche ${index} :`]
      if (card.front) lines.push(`  Recto: ${card.front}`)
      if (card.back) lines.push(`  Verso: ${card.back}`)
      if (card.summary) lines.push(`  Resume: ${card.summary}`)
      if (card.example) lines.push(`  Exemple: ${card.example}`)
      if (card.formula) lines.push(`  Formule: ${card.formula}`)
      if (card.quote) {
        const author = card.quoteAuthor ? ` — ${card.quoteAuthor}` : ''
        lines.push(`  Citation: "${card.quote}"${author}`)
      }
      if (card.dates && Array.isArray(card.dates) && card.dates.length > 0) {
        lines.push(`  Dates: ${card.dates.map((d) => `${d.year}=${d.event}`).join(' | ')}`)
      }
      return lines.join('\n')
    })
    .join('\n\n')
}

function parseVerificationResults(raw: string, cardCount: number): CardVerificationResult[] {
  const match = raw.match(/\{[\s\S]*\}/)
  if (!match) return []
  try {
    const parsed = JSON.parse(match[0]) as { results?: unknown }
    const arr = Array.isArray(parsed.results) ? parsed.results : []
    const out: CardVerificationResult[] = []
    for (const item of arr) {
      if (!item || typeof item !== 'object') continue
      const obj = item as Record<string, unknown>
      const idx = typeof obj.cardIndex === 'number' ? obj.cardIndex : -1
      if (idx < 0 || idx >= cardCount) continue
      const status = (typeof obj.status === 'string' ? obj.status : 'uncertain') as VerificationStatus
      if (!['verified', 'general', 'uncertain', 'contradicted'].includes(status)) continue
      const cited = Array.isArray(obj.citedSources)
        ? (obj.citedSources as unknown[])
            .map((s) => Number(s))
            .filter((n) => Number.isFinite(n) && n > 0)
        : []
      out.push({
        cardIndex: idx,
        status,
        citedSources: cited,
        reasoning: typeof obj.reasoning === 'string' ? obj.reasoning.slice(0, 400) : '',
        contradiction: typeof obj.contradiction === 'string' ? obj.contradiction.slice(0, 400) : undefined,
        correctedFront: typeof obj.correctedFront === 'string' ? obj.correctedFront.slice(0, 600) : undefined,
        correctedBack: typeof obj.correctedBack === 'string' ? obj.correctedBack.slice(0, 1200) : undefined,
      })
    }
    return out
  } catch {
    return []
  }
}

/**
 * Run the verification pass.
 *
 * On `auditModel` mismatch / failure / missing Ollama: returns a fallback
 * report where every card is marked "general" — the cards are still
 * delivered to the user, just without a verified badge.
 */
export async function verifyFlashcards({
  cards,
  sources,
  auditModel,
  signal,
}: {
  cards: RawDraft[]
  sources: LearningSource[]
  /** Use the same Ollama model the deck was generated with — typically the user's main LLM. */
  auditModel: string
  signal?: AbortSignal
}): Promise<FlashcardVerificationReport> {
  if (cards.length === 0) {
    return { totalProcessed: 0, verified: 0, general: 0, uncertain: 0, rejected: 0, results: [] }
  }

  const userMessage = [
    'Voici les sources factuelles disponibles:',
    '',
    buildSourcesBlock(sources),
    '',
    'Voici les fiches a verifier:',
    '',
    buildCardsBlock(cards),
    '',
    'Renvoie UNIQUEMENT le JSON {"results":[...]}.',
  ].join('\n')

  let raw = ''
  try {
    const response = await ollamaChat(
      auditModel,
      [
        { role: 'system', content: VERIFICATION_SYSTEM_PROMPT },
        { role: 'user', content: userMessage },
      ],
      undefined,
      { signal },
    )
    raw = (response as { message?: { content?: string } })?.message?.content ?? ''
    if (!raw) return fallbackReport(cards.length)
  } catch {
    return fallbackReport(cards.length)
  }

  const results = parseVerificationResults(raw, cards.length)
  if (results.length === 0) return fallbackReport(cards.length)

  // Make sure every card got an entry — if the model skipped some, fill with "general".
  const seen = new Set(results.map((r) => r.cardIndex))
  for (let i = 0; i < cards.length; i++) {
    if (!seen.has(i)) {
      results.push({
        cardIndex: i,
        status: 'general',
        citedSources: [],
        reasoning: 'Non evaluee par le correcteur — conservee comme connaissance generale.',
      })
    }
  }
  results.sort((a, b) => a.cardIndex - b.cardIndex)

  return summarizeReport(results)
}

function fallbackReport(cardCount: number): FlashcardVerificationReport {
  const results: CardVerificationResult[] = Array.from({ length: cardCount }, (_, i) => ({
    cardIndex: i,
    status: 'general' as VerificationStatus,
    citedSources: [],
    reasoning: 'Verification automatique indisponible — fiche conservee sans badge.',
  }))
  return {
    totalProcessed: cardCount,
    verified: 0,
    general: cardCount,
    uncertain: 0,
    rejected: 0,
    results,
  }
}

function summarizeReport(results: CardVerificationResult[]): FlashcardVerificationReport {
  const counters = { verified: 0, general: 0, uncertain: 0, rejected: 0 }
  for (const result of results) {
    if (result.status === 'verified') counters.verified += 1
    else if (result.status === 'general') counters.general += 1
    else if (result.status === 'uncertain') counters.uncertain += 1
    else if (result.status === 'contradicted') counters.rejected += 1
  }
  return {
    totalProcessed: results.length,
    ...counters,
    results,
  }
}

/**
 * Apply the verification report to a list of card drafts:
 *   - drops contradicted cards
 *   - applies corrected front/back when provided
 *   - attaches `verification` metadata so the UI can render badges
 *
 * Returns the kept cards plus a summary message ready for the UI.
 */
export function applyVerificationReport<T extends RawDraft>(
  cards: T[],
  report: FlashcardVerificationReport,
): { cards: Array<T & { verification?: CardVerificationResult }>; summary: string } {
  const kept: Array<T & { verification?: CardVerificationResult }> = []
  for (let i = 0; i < cards.length; i++) {
    const result = report.results.find((r) => r.cardIndex === i)
    if (!result) {
      kept.push({ ...cards[i] } as T & { verification?: CardVerificationResult })
      continue
    }
    if (result.status === 'contradicted' && !result.correctedFront && !result.correctedBack) {
      // No correction possible — drop the card.
      continue
    }
    const card = { ...cards[i] } as T & { verification?: CardVerificationResult }
    if (result.correctedFront) card.front = result.correctedFront
    if (result.correctedBack) card.back = result.correctedBack
    card.verification = result
    kept.push(card)
  }
  const dropped = report.totalProcessed - kept.length
  const summary = [
    `${report.verified} verifiees`,
    `${report.general} gen.`,
    report.uncertain > 0 ? `${report.uncertain} incertaines` : '',
    dropped > 0 ? `${dropped} retirees` : '',
  ]
    .filter(Boolean)
    .join(' · ')
  return { cards: kept, summary }
}
