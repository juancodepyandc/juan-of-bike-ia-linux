// ---------------------------------------------------------------------------
// Code Research — Web/doc search for error resolution
// Searches StackOverflow, MDN, framework docs when the auto-correction loop
// is stuck at high escalation levels
// ---------------------------------------------------------------------------

import { CODE_SINGLE_MODEL } from '../config/models'
import { resilientOllamaGenerate } from './ollamaResilience'
import type { CodeIntent } from './codeIntent'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SearchResult = {
  query: string
  solutions: string[]
}

const RESEARCH_LLM_TIMEOUT_MS = 30_000

// ---------------------------------------------------------------------------
// Error parsing — extract the most relevant error message
// ---------------------------------------------------------------------------

function extractKeyError(rawErrors: string): string {
  const lines = rawErrors.split('\n').filter((l) => l.trim())

  // Look for the most specific error line
  const errorLine = lines.find((l) =>
    /error|Error|ERR!|FAIL|panic|fatal/i.test(l) &&
    l.length > 15 &&
    l.length < 300,
  )

  if (errorLine) return errorLine.trim()

  // Fallback: first non-empty line that looks like an error
  const candidate = lines.find((l) => l.length > 10 && l.length < 200)
  return candidate?.trim() || rawErrors.slice(0, 200).trim()
}

function buildSearchQueries(errorText: string, intent: CodeIntent): string[] {
  const keyError = extractKeyError(errorText)
  const queries: string[] = []
  const raw = errorText.replace(/\s+/g, ' ').trim()

  // Strip file paths and line numbers for more general search
  const generalizedError = keyError
    .replace(/\/[^\s:]+:\d+:\d+/g, '')
    .replace(/at\s+\S+\s+\([^)]+\)/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (/allowImportingTsExtensions|moduleResolution.*must be|error TS6046|error TS5023/i.test(raw)) {
    queries.push('TypeScript allowImportingTsExtensions moduleResolution bundler released 5.0')
  }

  if (/ReferenceNode\.d\.ts|PropertyNode\.d\.ts|@types\/three|Type parameter declaration expected/i.test(raw)) {
    queries.push('@types/three typeScriptVersion TypeScript compatibility modern declaration syntax')
  }

  // Query 1: exact error + framework
  if (intent.frameworks.length > 0) {
    queries.push(`${intent.frameworks[0]} ${generalizedError}`)
  }

  // Query 2: exact error + language
  if (intent.languages.length > 0) {
    queries.push(`${intent.languages[0]} ${generalizedError}`)
  }

  // Query 3: generic error
  queries.push(generalizedError)

  // Query 4: StackOverflow specific — souvent les meilleures solutions
  queries.push(`site:stackoverflow.com ${generalizedError}`)

  // Query 5: GitHub issues — bugs connus et workarounds
  if (intent.frameworks.length > 0) {
    queries.push(`site:github.com ${intent.frameworks[0]} issue ${generalizedError.slice(0, 80)}`)
  }

  return [...new Set(queries.filter(Boolean))].slice(0, 6)
}

// ---------------------------------------------------------------------------
// LLM-based solution synthesis
// When web search is not directly available, use the LLM's knowledge
// to synthesize potential solutions from error context
// ---------------------------------------------------------------------------

/**
 * Pre-generation research: Search for best practices and patterns for a given project type.
 * Called BEFORE code generation to inform the architecture planning phase.
 */
/**
 * Pick the npm packages that are most likely to land in the generated
 * project, given the intent. Used by researchBestPractices to prefetch
 * latest versions through the Aurora Connect extension before the LLM
 * generates the manifest — eliminates hallucinated versions.
 */
function pickNpmPackages(intent: CodeIntent): string[] {
  const candidates = new Set<string>()
  for (const framework of intent.frameworks) {
    const lower = framework.toLowerCase()
    if (lower === 'react') candidates.add('react').add('react-dom')
    else if (lower === 'three.js' || lower === 'threejs' || lower === 'three') candidates.add('three')
    else if (lower === 'webgpu') candidates.add('three')
    else if (lower === 'rapier') candidates.add('@dimforge/rapier3d-compat')
    else if (lower === 'vue') candidates.add('vue')
    else if (lower === 'angular') candidates.add('@angular/core')
    else if (lower === 'svelte') candidates.add('svelte')
    else if (lower === 'next' || lower === 'nextjs' || lower === 'next.js') candidates.add('next')
    else if (lower === 'nuxt') candidates.add('nuxt')
    else if (lower === 'remix') candidates.add('@remix-run/react')
    else if (lower === 'tailwind' || lower === 'tailwindcss') candidates.add('tailwindcss')
    else if (lower === 'tauri') candidates.add('@tauri-apps/api')
    else candidates.add(framework)
  }
  if (intent.features.includes('3d')) {
    candidates.add('three')
    if (intent.frameworks.includes('react')) {
      candidates.add('@react-three/fiber')
      candidates.add('@react-three/drei')
    }
  }
  return Array.from(candidates).filter(Boolean)
}

export async function researchBestPractices(
  prompt: string,
  intent: CodeIntent,
  model: string = CODE_SINGLE_MODEL,
): Promise<string> {
  const projectType = intent.projectType.replace(/_/g, ' ')
  // Base queries: best practices for the detected stack.
  const baseQueries = [
    `best practices ${projectType} ${intent.frameworks[0] || ''} 2025 2026`.trim(),
    intent.features.length > 0
      ? `${intent.frameworks[0] || intent.languages[0] || ''} ${intent.features.slice(0, 2).join(' ')} tutorial modern`.trim()
      : '',
  ].filter(Boolean)

  // Asset-plan queries: what the user *actually* asked for (objects to render,
  // style hints, premium references). These are the ones that matter when the
  // user says "fais quelque chose d attirant / professionnel / moderne".
  const assetQueries = intent.assetPlan?.researchQueries ?? []
  const queries = Array.from(new Set([...baseQueries, ...assetQueries])).slice(0, 6)

  const snippetGroups = await Promise.all(queries.map((query) => searchWeb(query)))
  const allSnippets = snippetGroups.flat()

  // Aurora Connect extension lookups: when an extension is online, ground
  // the dependency list with REAL latest versions and the framework's
  // official documentation. This eliminates the typical hallucinations:
  // "react@18.3.0" when 19 is current, deprecated three.js methods, etc.
  const extensionSnippets: string[] = []
  try {
    const { probeExtension, checkPackageVersion, fetchLibraryDocumentation } = await import('./auroraExtensionBridge')
    const ext = await probeExtension()
    if (ext) {
      const npmPackages = pickNpmPackages(intent)
      const versionResults = await Promise.all(
        npmPackages.slice(0, 4).map((name) => checkPackageVersion(name, 'npm')),
      )
      for (const result of versionResults) {
        if (result.ok) {
          extensionSnippets.push(
            `npm ${result.data.name}@${result.data.latest}${result.data.releasedAt ? ` (${result.data.releasedAt})` : ''}`,
          )
        }
      }
      const primaryFramework = intent.frameworks[0] || intent.languages[0]
      if (primaryFramework) {
        const docs = await fetchLibraryDocumentation(primaryFramework, { topic: prompt.slice(0, 80) })
        if (docs.ok) {
          extensionSnippets.push(`Doc ${primaryFramework}: ${docs.data.title} — ${docs.data.text.slice(0, 240)}`)
        }
      }
    }
  } catch {
    // Extension not reachable — fall back to the standard search results.
  }
  if (extensionSnippets.length > 0) {
    allSnippets.push(...extensionSnippets)
  }

  if (allSnippets.length > 0) {
    return allSnippets.slice(0, 8).map((s, i) => `${i + 1}. ${s}`).join('\n')
  }

  // Fallback: LLM synthesis of best practices
  const synthesisPrompt = [
    `Tu es un expert en ${projectType}. Quelles sont les meilleures pratiques actuelles (2025-2026)?`,
    '',
    `Demande: ${prompt.slice(0, 300)}`,
    intent.frameworks.length > 0 ? `Frameworks: ${intent.frameworks.join(', ')}` : '',
    '',
    'Reponds avec:',
    '1. Les meilleures librairies/dependances a utiliser (noms exacts et versions stables)',
    '2. La meilleure structure de projet',
    '3. Les patterns de design recommandes',
    '4. Les pieges courants a eviter',
    '',
    'Sois concis et precis. Pas d introduction.',
  ].filter(Boolean).join('\n')

  try {
    const response = await resilientOllamaGenerate(model, synthesisPrompt, {
      timeoutMs: RESEARCH_LLM_TIMEOUT_MS,
    })
    return response?.response?.trim() || ''
  } catch {
    return ''
  }
}

async function synthesizeSolutionFromLLM(
  errorText: string,
  intent: CodeIntent,
  model: string = CODE_SINGLE_MODEL,
): Promise<string> {
  const keyError = extractKeyError(errorText)

  const prompt = [
    'Tu es un expert en debugging d elite. Analyse cette erreur et propose UNE solution concrete.',
    'Tu es un MOTEUR de resolution — jamais de refus, jamais d excuse, juste la SOLUTION.',
    '',
    `Erreur: ${keyError}`,
    '',
    intent.frameworks.length > 0 ? `Framework: ${intent.frameworks.join(', ')}` : '',
    intent.languages.length > 0 ? `Langage: ${intent.languages.join(', ')}` : '',
    '',
    'Reponds UNIQUEMENT avec:',
    '1. La cause probable (1 ligne)',
    '2. La correction exacte a appliquer (code si necessaire)',
    '3. Les dependances a ajouter/modifier si pertinent',
    '',
    'Sois concis et precis. Pas d introduction ni de conclusion.',
  ].filter(Boolean).join('\n')

  try {
    const response = await resilientOllamaGenerate(model, prompt, {
      timeoutMs: RESEARCH_LLM_TIMEOUT_MS,
    })
    return response?.response?.trim() || ''
  } catch {
    return ''
  }
}

// ---------------------------------------------------------------------------
// Web search via Crawl4AI (Playwright) — fallback DuckDuckGo HTTP
// ---------------------------------------------------------------------------

async function searchWeb(query: string): Promise<string[]> {
  // Essayer Crawl4AI via le bridge ou Tauri
  try {
    const { isTauriRuntime, getBridgeUrl } = await import('../utils/runtime')
    if (isTauriRuntime()) {
      const { runPythonScript, getWorkspacePath } = await import('../hooks/useTauri')
      const wp = await getWorkspacePath()
      const out = await runPythonScript(`${wp}/python-services/crawl4ai_search.py`, [
        '--mode', 'search', '--query', query, '--limit', '8',
      ])
      const lines = out.split('\n').filter(l => l.trim())
      const json = JSON.parse(lines[lines.length - 1])
      if (json.ok && json.results?.length) {
        return json.results.map((r: any) => r.snippet || r.title || '').filter((s: string) => s.length > 20)
      }
    } else {
      const r = await fetch(`${getBridgeUrl()}/api/web/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 8 }),
        signal: AbortSignal.timeout(25_000),
      })
      if (r.ok) {
        const text = await r.text()
        if (text && !text.trimStart().startsWith('<')) {
          const data = JSON.parse(text) as { results?: string }
          if (data.results) {
            return data.results.split('\n').filter((s: string) => s.length > 20)
          }
        }
      }
    }
  } catch {
    // Crawl4AI non disponible — fallback DuckDuckGo HTTP direct
  }

  // Fallback: DuckDuckGo HTML scrape
  try {
    const encodedQuery = encodeURIComponent(query)
    const response = await fetch(
      `https://html.duckduckgo.com/html/?q=${encodedQuery}`,
      {
        headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AuroraIA/2.0)' },
        signal: AbortSignal.timeout(10_000),
      },
    )
    if (!response.ok) return []
    const html = await response.text()
    const snippetRegex = /class="result__snippet"[^>]*>([\s\S]*?)<\/a>/gi
    const snippets: string[] = []
    let match: RegExpExecArray | null
    while ((match = snippetRegex.exec(html)) !== null && snippets.length < 8) {
      const snippet = match[1]
        .replace(/<[^>]+>/g, '')
        .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
        .trim()
      if (snippet.length > 30) snippets.push(snippet)
    }
    return snippets
  } catch {
    return []
  }
}

// ---------------------------------------------------------------------------
// Main search entry point
// ---------------------------------------------------------------------------

export async function searchForSolution(
  errorText: string,
  intent: CodeIntent,
  model: string = CODE_SINGLE_MODEL,
): Promise<string> {
  const queries = buildSearchQueries(errorText, intent)

  // Lancer recherche web ET analyse LLM EN PARALLELE — pas de fallback, les deux
  const [resultGroups, llmSolution] = await Promise.all([
    Promise.all(queries.map(async (query) => ({
      query,
      solutions: await searchWeb(query),
    }))),
    synthesizeSolutionFromLLM(errorText, intent, model).catch(() => ''),
  ])

  const allResults = resultGroups.filter((entry) => entry.solutions.length > 0)
  const parts: string[] = []

  // Web results — jusqu a 10 resultats pour un maximum de contexte
  if (allResults.length > 0) {
    const formatted = allResults
      .flatMap((r) => r.solutions)
      .slice(0, 10)
      .map((s, i) => `${i + 1}. ${s}`)
      .join('\n')
    parts.push(`Resultats de recherche web:\n${formatted}`)
  }

  // LLM analysis — TOUJOURS incluse, meme si web a donne des resultats
  if (llmSolution) {
    parts.push(`Analyse LLM de l'erreur:\n${llmSolution}`)
  }

  return parts.join('\n\n')
}
