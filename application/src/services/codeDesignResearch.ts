// ---------------------------------------------------------------------------
// codeDesignResearch — etape 1.6 du pipeline.
// Recherche en ligne des references visuelles SPECIFIQUES a l archetype detecte
// (Awwwards / SiteInspire / Dribbble / Behance / Land-book) + injecte un brief
// d inspiration concret dans le contexte du Codeur. Combine:
//   1. Knowledge base in-memory (references curees, palettes connues, libs)
//   2. Aurora web-search service (archetype + sujet)
//   3. Ollama synthesis pour fusionner refs + sujet en directives concretes.
// ---------------------------------------------------------------------------

import { CODE_SINGLE_MODEL } from '../config/models.ts'
import { resilientOllamaGenerate } from './ollamaResilience.ts'
import type { CodeIntent } from './codeIntent.ts'
import { detectDesignArchetype, type DesignArchetype } from './codeDesignDirectives.ts'
import { searchCodeWebReferences } from './codeWebResearchClient.ts'
import { ARCHETYPE_KB } from './codeDesignResearchCatalog.ts'

const DESIGN_RESEARCH_TIMEOUT_MS = 22_000
const PER_QUERY_TIMEOUT_MS = 10_000

// ---------------------------------------------------------------------------
// Knowledge base — curated references per archetype.
// Pas d invention: ces sites existent vraiment et sont des references actuelles
// dans la communaute design. Ils servent d ancres pour les recherches.
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Web search — reuse the search infra of codeResearch with a longer timeout
// budget when the goal is design research (more sources = better synthesis).
// ---------------------------------------------------------------------------

async function searchOneQuery(query: string): Promise<string[]> {
  return searchCodeWebReferences(query, { limit: 6, timeoutMs: PER_QUERY_TIMEOUT_MS })
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export type DesignResearchOutput = {
  archetype: DesignArchetype
  inspirationSites: string[]
  searchSnippets: string[]
  synthesisBrief: string
  /** Telemetry: which queries were executed (for the UI / debug surface). */
  executedQueries: string[]
}

/**
 * Run the design research pass. Returns:
 *  - the detected archetype
 *  - curated inspiration sites
 *  - web snippets pulled per archetype + subject
 *  - an Ollama-synthesized brief (1-page) the Codeur uses as inspiration
 *
 * All steps are time-boxed and non-blocking — if every search fails the
 * function still returns a valuable knowledge-base brief.
 */
export async function runDesignResearch(
  prompt: string,
  intent: CodeIntent,
  model: string = CODE_SINGLE_MODEL,
): Promise<DesignResearchOutput> {
  const archetype = detectDesignArchetype(prompt, intent)
  const kb = ARCHETYPE_KB[archetype]
  const subject = intent.assetPlan?.subject?.canonical || intent.assetPlan?.objectMentions?.[0] || ''

  // Build queries: archetype anchors + subject hybrid + brand if any.
  const queries = new Set<string>()
  for (const anchor of kb.searchAnchors) queries.add(anchor)
  if (subject) {
    queries.add(`${subject} product website inspiration`)
    queries.add(`${subject} hero section design 2025`)
  }
  const finalQueries = Array.from(queries).slice(0, 5)

  // Run searches in parallel with a global cap.
  const start = Date.now()
  const results = await Promise.allSettled(
    finalQueries.map((q) => searchOneQuery(q)),
  )
  const allSnippets: string[] = []
  for (const r of results) {
    if (r.status === 'fulfilled') {
      for (const snippet of r.value) {
        if (allSnippets.length < 14 && !allSnippets.includes(snippet)) {
          allSnippets.push(snippet)
        }
      }
    }
  }
  const elapsed = Date.now() - start

  // Synthesize a brief — even if the web returned nothing, the LLM uses the KB
  // and its own knowledge to produce inspiration concrete pour le Codeur.
  const synthesisPrompt = [
    'Tu es un Design Director senior. Tu prepares un brief inspiration pour un developpeur d elite.',
    `Archetype design: ${archetype.replace(/_/g, ' ')}.`,
    subject ? `Sujet: ${subject}.` : '',
    `Reference sites curees: ${kb.inspirationSites.join(', ')}.`,
    `Palette suggeree: ${kb.paletteHints.join(', ')}.`,
    `Librairies recommandees: ${kb.knownLibs.join(', ')}.`,
    '',
    allSnippets.length > 0
      ? `Snippets trouves en ligne:\n${allSnippets.slice(0, 8).map((s, i) => `${i + 1}. ${s}`).join('\n')}`
      : 'Aucun snippet web exploitable — utilise tes connaissances KB.',
    '',
    'Produis un brief clair en 8-12 lignes:',
    '- 3 references visuelles concretes (sites ou patterns) avec ce qu on doit emprunter (atmosphere, layout, palette, animation).',
    '- 4-6 elements visuels OBLIGATOIRES (hero, sections phare, micro-interactions specifiques).',
    '- 2-3 librairies CDN a inclure et leur role.',
    '- 1 piege courant a eviter pour ce type de page.',
    '',
    'Reponds en francais, precis, non generique. Pas d introduction, pas de conclusion.',
  ].filter(Boolean).join('\n')

  let synthesisBrief = ''
  try {
    const remaining = Math.max(8_000, DESIGN_RESEARCH_TIMEOUT_MS - elapsed)
    const response = await resilientOllamaGenerate(model, synthesisPrompt, {
      timeoutMs: remaining,
    })
    synthesisBrief = response?.response?.trim() || ''
  } catch {
    synthesisBrief = ''
  }

  // Fallback brief — if Ollama is down, still return a usable KB brief so the
  // Codeur receives concrete guidance.
  if (!synthesisBrief) {
    synthesisBrief = [
      `Inspiration ${archetype.replace(/_/g, ' ')}:`,
      `- Sites references: ${kb.inspirationSites.slice(0, 3).join(', ')}.`,
      `- Palette de depart (a moduler): ${kb.paletteHints.join(', ')}.`,
      `- Librairies a brancher: ${kb.knownLibs.join(', ')}.`,
      subject ? `- Sujet a illustrer: ${subject}.` : '',
      '- Vise un rendu studio premium (pas tutoriel).',
    ].filter(Boolean).join('\n')
  }

  return {
    archetype,
    inspirationSites: kb.inspirationSites,
    searchSnippets: allSnippets,
    synthesisBrief,
    executedQueries: finalQueries,
  }
}

/**
 * Serialise the research result into a system-prompt-friendly block.
 * Inserted by the orchestrator BETWEEN the existing best practices and the
 * planning phase — it focuses on visual direction, not technical patterns.
 */
export function serializeDesignResearch(research: DesignResearchOutput): string {
  return [
    `## RECHERCHE DESIGN — ARCHETYPE ${research.archetype.toUpperCase()}`,
    '',
    research.synthesisBrief,
    '',
    `Sites references curees (a etudier mentalement avant de coder): ${research.inspirationSites.join(', ')}.`,
    research.searchSnippets.length > 0
      ? `\nExtraits web (${research.searchSnippets.length} snippet(s)):\n${research.searchSnippets.slice(0, 6).map((s, i) => `${i + 1}. ${s}`).join('\n')}`
      : '',
    '',
    'INSTRUCTION: tu N AS PAS le droit de copier ces sites au pixel. Tu T INSPIRES (atmosphere, hierarchie typographique, mouvements, palette). Adapte au sujet de l utilisateur.',
  ].filter(Boolean).join('\n')
}
