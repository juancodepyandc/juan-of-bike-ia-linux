// ---------------------------------------------------------------------------
// Code Orchestrator — Multi-phase pipeline with model routing
// Equivalent of conversationOrchestrator.ts but specialized for code generation
// ---------------------------------------------------------------------------

import type { OllamaMessage } from '../types/app'
import {
  resilientOllamaChat,
  resilientOllamaChatStream,
  resilientOllamaGenerate,
  type RecoveryEvent,
} from './ollamaResilience'
import {
  type CodeIntent,
  type CodeIntentContext,
  type CodeProjectType,
  type BrandProfile,
  buildArchitecturePlanningPrompt,
  classifyCodeIntent,
  classifyPivotKindHeuristic,
  hasExplicitStackMention,
} from './codeIntent'
import {
  buildArchitecteSystemPrompt,
  buildCodeurSystemPrompt,
  buildAuditeurSystemPrompt,
} from './codeSystemPrompts'
import {
  buildAutonomousAssumptionNotes,
  buildCodeMissionDossier,
  buildDraftRegenerationPrompt,
  buildRescueRegenerationPrompt,
  reviewGeneratedCodeDraft,
  serializeCodeMissionDossier,
  type CodeMissionDossier,
} from './codeMissionControl'
import {
  type CorrectionStrategy,
  type CorrectionPass,
  type ErrorCategory,
  buildCorrectionStrategy,
  shouldContinueLoop,
  classifyErrors,
} from './codeAutoCorrection'
import { searchForSolution, researchBestPractices } from './codeResearch'
import { runCodeSandboxValidation, type CodeSandboxResult, type CodeSandboxStepResult } from './codeSandbox'
import { analyzeStuckCorrection, buildReasoningInstructions } from './codeReasoningEngine'
import {
  runCodePreflight,
  serializeCodePreflightReport,
  type CodePreflightReport,
} from './codePreflight'
import { withTimeout } from './llmTimebox'
import { getBridgeUrl } from '../utils/runtime'
import { buildAuroraInlineSvgDataUri } from './codeVisualFallbacks.ts'

// Fetch real subject images: logo, product, lifestyle (for brand pages).

import { searchReferenceImages, probeExtension } from './auroraExtensionBridge'
import { evaluateBrandFidelity, type BrandFidelityReport } from './codeFidelityGate'
import { compositeStaticCritic } from './codeStaticCritics'
import type { CritiqueReport } from './codeMultiPassCritique'

type SubjectImage = { dataUrl: string; source?: string; query?: string }

/**
 * Build up to 4 image search queries for the subject. Brand pages reuse the
 * canonical brand image queries (logo, product, lifestyle); generic subjects
 * fall back to the canonical name + variants.
 */
function buildSubjectImageQueries(intent: CodeIntent): string[] {
  const subject = intent.assetPlan?.subject
  const objectMentions = intent.assetPlan?.objectMentions || []

  const queries: string[] = []

  if (subject?.source === 'brand' && subject.brandProfile?.imageQueries?.length) {
    // Brand path — use the curated queries (logo / product / lifestyle / detail).
    queries.push(...subject.brandProfile.imageQueries.slice(0, 4))
  } else if (subject?.canonical) {
    queries.push(subject.canonical)
    queries.push(`${subject.canonical} photo`)
    queries.push(`${subject.canonical} produit`)
  } else if (objectMentions.length > 0) {
    queries.push(objectMentions[0])
    if (objectMentions[1]) queries.push(objectMentions[1])
  }

  // Deduplicate while preserving order.
  return Array.from(new Set(queries.map((q) => q.trim()).filter(Boolean))).slice(0, 4)
}

/**
 * v71 multi-image fetch.
 *
 * Strategy:
 *   1) Probe the Aurora-Connect extension. When connected, ask it to perform
 *      `searchReferenceImages` with each query — those URLs come from a real
 *      browser tab (Google Images / DuckDuckGo) so they are fresher than what
 *      the Python bridge can search. We then download each URL to a data URL
 *      so the result survives any later save-as.
 *   2) For each remaining query (or all of them if the extension is absent),
 *      POST `/api/web/image` to the local Python bridge — same path as before.
 *   3) Fallback to deterministic inline SVG only if the previous two failed
 *      for a given query.
 *
 * Returns the resolved images in priority order. Empty array on full failure.
 */
async function fetchSubjectImages(intent: CodeIntent): Promise<SubjectImage[]> {
  const queries = buildSubjectImageQueries(intent)
  if (queries.length === 0) return []

  const out: SubjectImage[] = []
  const seen = new Set<string>()

  // Step 1 — try the extension when reachable.
  let extensionReachable = false
  try {
    const ext = await probeExtension(AbortSignal.timeout(3000))
    extensionReachable = ext !== null
  } catch {
    extensionReachable = false
  }

  if (extensionReachable) {
    for (const query of queries) {
      try {
        const result = await searchReferenceImages(query, { limit: 3, signal: AbortSignal.timeout(15_000) })
        if (!result.ok || result.data.length === 0) continue
        // Keep the first image we manage to download for each query.
        for (const candidate of result.data) {
          if (!candidate.url || seen.has(candidate.url)) continue
          seen.add(candidate.url)
          const dataUrl = await downloadAsDataUrl(candidate.url)
          if (dataUrl) {
            out.push({ dataUrl, source: candidate.url, query })
            break
          }
        }
      } catch {
        // try next query
      }
    }
  }

  // Step 2 — for any query that didn't yield an image yet, ask the Python bridge.
  const yieldedQueries = new Set(out.map((img) => img.query))
  const bridge = getBridgeUrl()
  for (const query of queries) {
    if (yieldedQueries.has(query)) continue
    try {
      const resp = await fetch(`${bridge}/api/web/image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, width: 1600, height: 900 }),
        signal: AbortSignal.timeout(22_000),
      })
      if (resp.ok) {
        const ct = resp.headers.get('content-type') || ''
        if (!ct.includes('text/html')) {
          const data = await resp.json() as { ok?: boolean; dataUrl?: string; source?: string }
          if (data?.ok && data?.dataUrl && !out.some((img) => img.dataUrl === data.dataUrl)) {
            out.push({ dataUrl: data.dataUrl, source: data.source ?? `bridge:${query}`, query })
            yieldedQueries.add(query)
          }
        }
      }
    } catch {
      // try next query
    }
  }

  // Step 3 — deterministic local fallback for any remaining slot.
  const stillMissing = queries.filter((q) => !yieldedQueries.has(q))
  for (const query of stillMissing) {
    out.push({
      dataUrl: buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 }),
      source: `inline-svg:${query}`,
      query,
    })
  }

  // Deduplicate by dataUrl prefix in case two queries hit the same image.
  const finalOut: SubjectImage[] = []
  const dataUrlSeen = new Set<string>()
  for (const img of out) {
    const fingerprint = img.dataUrl.slice(0, 256)
    if (dataUrlSeen.has(fingerprint)) continue
    dataUrlSeen.add(fingerprint)
    finalOut.push(img)
    if (finalOut.length >= 4) break
  }
  return finalOut
}

// Enrich brand profile via bridge: Wikipedia summary + Ollama JSON extraction.
// Returns profile (colors, keywords, design vibe) or null for fallback generic page.
async function fetchBrandProfileFromBridge(brandName: string): Promise<BrandProfile | null> {
  const bridge = getBridgeUrl()
  try {
    const resp = await fetch(`${bridge}/api/brand/enrich`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand: brandName }),
      signal: AbortSignal.timeout(50_000),
    })
    if (!resp.ok) return null
    const data = await resp.json() as {
      ok?: boolean
      profile?: {
        primaryColor?: string
        secondaryColor?: string
        tertiaryColor?: string
        productKeywords?: unknown
        designVibe?: string
        typoVibe?: string
        imageQueries?: unknown
        productShape?: string
      }
    }
    if (!data?.ok || !data.profile) return null
    const p = data.profile
    if (!p.primaryColor || !p.designVibe) return null
    if (!Array.isArray(p.productKeywords) || !Array.isArray(p.imageQueries)) return null

    // Sanitise — keep only string entries, cap to reasonable lengths.
    const productKeywords = (p.productKeywords as unknown[])
      .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
      .slice(0, 6)
    const imageQueries = (p.imageQueries as unknown[])
      .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
      .slice(0, 4)

    if (productKeywords.length === 0 || imageQueries.length === 0) return null

    const VALID_SHAPES = new Set([
      'can', 'bottle', 'phone', 'tablet', 'laptop',
      'shoe', 'car', 'watch', 'bag', 'headphones',
      'controller', 'console', 'card', 'cup', 'logo', 'building',
    ])
    const productShape = (typeof p.productShape === 'string' && VALID_SHAPES.has(p.productShape))
      ? p.productShape as BrandProfile['productShape']
      : 'logo'

    return {
      primaryColor: p.primaryColor,
      secondaryColor: typeof p.secondaryColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(p.secondaryColor)
        ? p.secondaryColor : undefined,
      tertiaryColor: typeof p.tertiaryColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(p.tertiaryColor)
        ? p.tertiaryColor : undefined,
      productKeywords,
      designVibe: p.designVibe,
      typoVibe: typeof p.typoVibe === 'string' && p.typoVibe.length > 0 ? p.typoVibe : 'sans-serif modern',
      imageQueries,
      productShape,
    }
  } catch {
    return null
  }
}

async function downloadAsDataUrl(url: string): Promise<string | null> {
  try {
    const resp = await fetch(url, { redirect: 'follow', signal: AbortSignal.timeout(15_000) })
    if (!resp.ok) return null
    const blob = await resp.blob()
    if (blob.size < 1024) return null
    return await blobToDataUrl(blob)
  } catch {
    return null
  }
}

function blobToDataUrl(blob: Blob): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(blob)
  })
}

/**
 * After the Codeur has produced the full content, swap each literal marker
 * (`PLACEHOLDER_SUBJECT_IMG`, `PLACEHOLDER_SUBJECT_IMG_1`...`_N`) with its
 * real data URL so `<img>` tags load immediately.
 *
 * The first image is bound to both `PLACEHOLDER_SUBJECT_IMG` (legacy single
 * marker, used by older prompts) and `PLACEHOLDER_SUBJECT_IMG_1`. Markers
 * 2..N map to images[1..N-1]. Markers without a matching image are stripped
 * to a transparent 1x1 GIF data URL so the page never shows a broken icon.
 */
function applySubjectImagePlaceholder(content: string, intent: CodeIntent): string {
  const stash = intent as unknown as { __subjectImageDataUrls?: string[]; __subjectImageDataUrl?: string }
  const images = stash.__subjectImageDataUrls && stash.__subjectImageDataUrls.length > 0
    ? stash.__subjectImageDataUrls
    : (stash.__subjectImageDataUrl ? [stash.__subjectImageDataUrl] : [])

  // Build a fallback URL pyramid even when the bridge yielded zero images.
  // Order : local brand-keyword SVG → local subject-canonical SVG
  // → transparent 1x1 GIF (last resort, never broken icon).
  // intent.brand n'existe pas sur CodeIntent — la marque vit dans assetPlan.subject
  // (subject.canonical = "Pepsi", "iphone 15", etc.). On garde une chaîne unique.
  const subjectKw =
    intent.assetPlan?.subject?.canonical ||
    'modern product'
  const brandKw = subjectKw
  const TRANSPARENT_GIF =
    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  const fallbackPool: string[] = images.length > 0
    ? images
    : [
        buildAuroraInlineSvgDataUri(subjectKw, { width: 1600, height: 900 }),
        buildAuroraInlineSvgDataUri(brandKw, { width: 1200, height: 800 }),
        TRANSPARENT_GIF,
      ]

  let next = content

  // Substitute numbered markers first (greedy: _6 before _1 to avoid prefix overlap).
  for (let idx = 6; idx >= 1; idx--) {
    const marker = `PLACEHOLDER_SUBJECT_IMG_${idx}`
    if (!next.includes(marker)) continue
    const url = fallbackPool[(idx - 1) % fallbackPool.length] ?? fallbackPool[0]
    next = next.split(marker).join(url)
  }

  // Then the legacy unnumbered marker — bind to the first url.
  if (next.includes('PLACEHOLDER_SUBJECT_IMG')) {
    next = next.split('PLACEHOLDER_SUBJECT_IMG').join(fallbackPool[0])
  }

  return next
}

/**
 * Follow-up merge: keep every existing file unless the model re-emitted it.
 * Compares by normalised path so "./src/app.js" and "src/app.js" match.
 */
function mergeExistingWithUpdates(existing: CodeFile[], updates: CodeFile[]): CodeFile[] {
  const norm = (p: string) => p.replace(/^\.\//, '').replace(/\\/g, '/').trim().toLowerCase()
  const updatedNames = new Set(updates.map((f) => norm(f.name)))
  const kept = existing.filter((f) => !updatedNames.has(norm(f.name)))
  return [...kept, ...updates]
}

// ---------------------------------------------------------------------------
// Smart clarification filter — suppress vague or useless questions
// ---------------------------------------------------------------------------

const VAGUE_QUESTION_PATTERNS = [
  /could you (please )?(clarify|specify|explain|elaborate)/i,
  /pouvez.vous (pr[eé]ciser|clarifier|expliquer)/i,
  /what (exactly|specifically) (do you|would you)/i,
  /que (voulez|souhaitez|voudriez).vous (dire|exactement|pr[eé]cis[eé]ment)/i,
  /can you (provide|give) more (detail|information|context)/i,
  /what (kind|type|sort) of/i,
  /are you looking for/i,
  /what do you mean by/i,
]

/**
 * Returns true if a clarification question is too vague to be useful.
 * Vague questions waste user time — the module should make assumptions instead.
 */
export function isVagueClarification(question: string | null): boolean {
  if (!question) return true
  if (question.length < 15) return true
  if (question.length > 500) return true
  return VAGUE_QUESTION_PATTERNS.some((pattern) => pattern.test(question))
}

/**
 * Auto-generate a smart assumption instead of asking a vague question.
 * The code module should be autonomous — prefer assumptions over questions.
 */
export function buildAutonomousAssumption(prompt: string, intent: CodeIntent): string {
  return buildAutonomousAssumptionNotes(prompt, intent)
}

// ---------------------------------------------------------------------------
// Clarification severity — replaces the binary vague/not-vague filter with a
// three-level scale so CodeView can decide whether to block the user with a
// dialog (critical) or auto-proceed with a clear assumption (optional/skip).
// ---------------------------------------------------------------------------

export type ClarificationSeverity = 'critical' | 'optional' | 'skip'

// Critical tokens: the question mentions a non-reversible, stack-forking
// decision the module genuinely cannot make on its own without risking a
// wasted generation. Examples: choice between incompatible stacks,
// presence/absence of authentication, data persistence vs. none.
const CRITICAL_DECISION_TOKENS = [
  /\b(stack|framework|langage|language)\b.*\b(react|vue|angular|svelte|python|flask|django|fastapi|node|express|rust|go|java)\b/i,
  /\b(authentification|authentication|login|connexion)\b/i,
  /\b(base de donn[ée]es|database|db|mongodb|postgres|mysql|sqlite)\b/i,
  /\b(paiement|payment|stripe|checkout)\b/i,
  /\b(mobile|desktop|web|api|cli)\b.*\b(ou|or|vs|versus)\b.*\b(mobile|desktop|web|api|cli)\b/i,
  /\b(self[- ]?host|cloud|serverless)\b/i,
  /\b(multi[- ]?tenant|single[- ]?tenant)\b/i,
]

/**
 * Classify a clarification question the task intelligence layer emitted.
 * - 'critical'  → block the user with a dialog (choice would ruin the output)
 * - 'optional'  → auto-proceed with a documented assumption
 * - 'skip'      → question is vague / boilerplate, ignore entirely
 */
export function classifyClarificationSeverity(
  question: string | null | undefined,
  _intent: CodeIntent,
  _prompt: string,
): ClarificationSeverity {
  if (!question) return 'skip'
  const trimmed = question.trim()
  if (trimmed.length < 15) return 'skip'
  if (trimmed.length > 500) return 'skip'
  // Vague boilerplate → skip, always. (Keeps parity with isVagueClarification.)
  if (VAGUE_QUESTION_PATTERNS.some((pattern) => pattern.test(trimmed))) return 'skip'

  // If the question references any non-reversible decision, treat as critical.
  if (CRITICAL_DECISION_TOKENS.some((pattern) => pattern.test(trimmed))) {
    return 'critical'
  }
  // Otherwise optional — the module can make a sensible assumption.
  return 'optional'
}

// ---------------------------------------------------------------------------
// Follow-up intent analyzer — turns a short follow-up prompt like
// "la meme chose en python" into a full FollowUpAnalysis that the pipeline
// uses to decide whether to reuse existing files, pivot the stack, or
// start fresh. Combines an LLM pass with a pure heuristic fallback.
// ---------------------------------------------------------------------------

export type FollowUpKind = 'increment' | 'pivot_platform' | 'pivot_feature' | 'fresh_start' | 'clarify_only'

export type FollowUpAnalysis = {
  kind: FollowUpKind
  reformulatedPrompt: string
  pivotReason: string | null
  shouldResetFiles: boolean
  criticalUnknowns: string[]
  migrationSummary: string | null
  previousProjectType: CodeProjectType | null
  previousLanguages: string[]
  previousFrameworks: string[]
}

function summarizeExistingFiles(existingFiles: CodeFile[]): {
  projectType: CodeProjectType | null
  languages: string[]
  frameworks: string[]
  digest: string
} {
  if (existingFiles.length === 0) {
    return { projectType: null, languages: [], frameworks: [], digest: '' }
  }
  const langs = new Set<string>()
  const frameworks = new Set<string>()
  for (const file of existingFiles) {
    langs.add(file.language)
    const lowerName = file.name.toLowerCase()
    const lowerContent = file.content.slice(0, 1200).toLowerCase()
    if (/react|jsx|tsx/.test(lowerContent) || /package\.json/.test(lowerName)) frameworks.add('react')
    if (/vue /.test(lowerContent) || /\.vue$/.test(lowerName)) frameworks.add('vue')
    if (/flask/.test(lowerContent)) frameworks.add('flask')
    if (/fastapi/.test(lowerContent)) frameworks.add('fastapi')
    if (/django/.test(lowerContent)) frameworks.add('django')
    if (/express\(\)/.test(lowerContent)) frameworks.add('express')
    if (/tauri/.test(lowerContent) || /tauri\.conf\.json/.test(lowerName)) frameworks.add('tauri')
    if (/electron/.test(lowerContent)) frameworks.add('electron')
    if (/three/.test(lowerContent) || /WebGL/.test(file.content.slice(0, 600))) frameworks.add('three.js')
  }
  // Heuristically guess project type from file names
  const names = existingFiles.map((f) => f.name.toLowerCase())
  let projectType: CodeProjectType | null = null
  if (names.some((n) => n === 'index.html' || n.endsWith('/index.html'))) projectType = 'static_web'
  if (names.some((n) => n.endsWith('tauri.conf.json'))) projectType = 'desktop_tauri'
  if (names.some((n) => n === 'app.py' || n.endsWith('/app.py'))) {
    projectType = frameworks.has('fastapi') ? 'api_fastapi' : frameworks.has('flask') ? 'api_flask' : 'cli_python'
  }
  if (names.some((n) => n === 'manage.py')) projectType = 'api_django'
  if (names.some((n) => n === 'package.json')) {
    if (frameworks.has('react')) projectType = 'spa_react'
    else if (frameworks.has('vue')) projectType = 'spa_vue'
    else if (frameworks.has('express')) projectType = 'api_express'
  }
  const biggest = [...existingFiles].sort((a, b) => b.content.length - a.content.length)[0]
  const digestLines = [
    `Fichiers: ${existingFiles.slice(0, 8).map((f) => f.name).join(', ')}${existingFiles.length > 8 ? ` (+${existingFiles.length - 8})` : ''}`,
    `Langages: ${[...langs].join(', ') || '—'}`,
    `Frameworks probables: ${[...frameworks].join(', ') || '—'}`,
    biggest ? `Extrait ${biggest.name}:\n${biggest.content.slice(0, 600)}` : '',
  ].filter(Boolean)
  return {
    projectType,
    languages: [...langs],
    frameworks: [...frameworks],
    digest: digestLines.join('\n'),
  }
}

function buildFollowUpHeuristic(
  newPrompt: string,
  conversationHistory: OllamaMessage[],
  existingFiles: CodeFile[],
  filesSummary: ReturnType<typeof summarizeExistingFiles>,
): FollowUpAnalysis {
  const kind = classifyPivotKindHeuristic(
    newPrompt,
    conversationHistory.length > 0,
    existingFiles.length > 0,
  )
  const lastUserTurn = [...conversationHistory].reverse().find((m) => m.role === 'user')?.content?.trim() || ''
  const lastAssistantHint = [...conversationHistory].reverse().find((m) => m.role === 'assistant')?.content?.slice(0, 280) || ''
  const previousGoal = lastUserTurn.slice(0, 600)

  let reformulated = newPrompt.trim()
  let migrationSummary: string | null = null

  if (kind === 'pivot_platform' && previousGoal) {
    const previousStackLabel = [
      filesSummary.projectType ? `type ${filesSummary.projectType}` : '',
      filesSummary.languages.length ? `langages ${filesSummary.languages.join('/')}` : '',
      filesSummary.frameworks.length ? `frameworks ${filesSummary.frameworks.join('/')}` : '',
    ].filter(Boolean).join(', ') || 'stack precedent'
    reformulated = [
      `Objectif metier (conserve du projet precedent): ${previousGoal}`,
      `Nouvelle demande explicite: ${newPrompt.trim()}`,
      'Conserve le MEME concept fonctionnel, change UNIQUEMENT la stack demandee.',
    ].join('\n')
    migrationSummary = [
      `Migration demandee. Stack precedente: ${previousStackLabel}.`,
      lastAssistantHint ? `Resume du projet precedent: ${lastAssistantHint.replace(/\s+/g, ' ')}` : '',
      `Nouveau prompt: ${newPrompt.trim()}`,
    ].filter(Boolean).join('\n')
  } else if (kind === 'increment' && previousGoal) {
    reformulated = [
      `Contexte projet en cours: ${previousGoal}`,
      `Nouvelle instruction (patch incremental): ${newPrompt.trim()}`,
    ].join('\n')
  } else if (kind === 'pivot_feature' && previousGoal) {
    reformulated = [
      `Evolution majeure demandee sur le projet existant.`,
      `Contexte: ${previousGoal}`,
      `Demande: ${newPrompt.trim()}`,
    ].join('\n')
  }

  return {
    kind,
    reformulatedPrompt: reformulated,
    pivotReason: kind === 'pivot_platform' ? 'Stack explicitement changee par l utilisateur.' : null,
    shouldResetFiles: kind === 'pivot_platform' || kind === 'fresh_start',
    criticalUnknowns: [],
    migrationSummary,
    previousProjectType: filesSummary.projectType,
    previousLanguages: filesSummary.languages,
    previousFrameworks: filesSummary.frameworks,
  }
}

/**
 * Analyze a follow-up prompt against the running conversation and the set
 * of existing files. Returns a `FollowUpAnalysis` the pipeline uses to
 * decide whether to reuse files, pivot the stack, or reclassify from
 * scratch. Falls back to a pure heuristic if the LLM call fails.
 */
export async function analyzeFollowUpIntent(params: {
  newPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  model: string
  signal?: AbortSignal
}): Promise<FollowUpAnalysis> {
  const { newPrompt, conversationHistory, existingFiles, model, signal } = params
  const filesSummary = summarizeExistingFiles(existingFiles)

  // Short-circuit when there is genuinely nothing to look back on.
  if (conversationHistory.length === 0 && existingFiles.length === 0) {
    return buildFollowUpHeuristic(newPrompt, conversationHistory, existingFiles, filesSummary)
  }

  const historyDigest = conversationHistory.slice(-6).map((m) => {
    const role = m.role === 'user' ? 'User' : 'Assistant'
    const content = (m.content || '').slice(0, 350).replace(/\s+/g, ' ')
    return `${role}: ${content}`
  }).join('\n')

  const filesBlock = filesSummary.digest
    ? `## Fichiers existants\n${filesSummary.digest}`
    : '## Fichiers existants: aucun'

  const instruction = [
    'Tu es un Analyste de Continuite de Mission pour un pipeline de generation de code.',
    'Analyse si la NOUVELLE demande utilisateur est :',
    '- "increment"      : simple modification/ajout sur le MEME projet existant (garder la stack actuelle).',
    '- "pivot_platform" : meme CONCEPT mais sur une autre stack/langage/plateforme (ex: HTML -> Python, web -> mobile).',
    '- "pivot_feature"  : evolution fonctionnelle majeure sur la meme stack.',
    '- "fresh_start"    : sujet totalement different, aucune continuite.',
    '- "clarify_only"   : prompt ambigu au point qu un choix critique est necessaire avant tout code.',
    '',
    'Si la demande est un pivot_platform : retourne aussi un resume factuel (1-2 phrases) du CONCEPT metier du projet precedent, SANS reproduire le code, pour guider la reecriture dans la nouvelle stack.',
    '',
    'Retourne UNIQUEMENT un JSON strict (pas de markdown) :',
    '{',
    '  "intentKind": "increment" | "pivot_platform" | "pivot_feature" | "fresh_start" | "clarify_only",',
    '  "reformulatedPrompt": "prompt reformule auto-suffisant en francais qui integre le contexte implicite",',
    '  "pivotReason": "string ou null",',
    '  "shouldResetFiles": true | false,',
    '  "criticalUnknowns": ["question precise 1", "question precise 2"],',
    '  "migrationSummary": "string ou null (concept metier du projet precedent, sans code)"',
    '}',
    '',
    filesBlock,
    '',
    '## Historique recent',
    historyDigest || '(aucun)',
    '',
    `## Nouvelle demande`,
    newPrompt.trim(),
  ].join('\n')

  try {
    const response = await resilientOllamaGenerate(model, instruction, {
      timeoutMs: 120_000,
      firstByteTimeoutMs: 90_000,
      signal,
      neverMemorySkip: true, // v85c : follow-up analysis must run for continuity
      num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
    })
    const raw = response?.response?.trim() || ''
    // Extract the first JSON object in the response (models sometimes wrap in prose)
    const jsonMatch = raw.match(/\{[\s\S]*\}/)
    if (!jsonMatch) throw new Error('no JSON in follow-up analysis response')
    const parsed = JSON.parse(jsonMatch[0]) as Partial<{
      intentKind: FollowUpKind
      reformulatedPrompt: string
      pivotReason: string | null
      shouldResetFiles: boolean
      criticalUnknowns: string[]
      migrationSummary: string | null
    }>
    const kind = (parsed.intentKind ?? 'increment') as FollowUpKind
    const reformulated = (parsed.reformulatedPrompt || newPrompt).trim() || newPrompt
    return {
      kind,
      reformulatedPrompt: reformulated,
      pivotReason: parsed.pivotReason ?? null,
      shouldResetFiles: Boolean(parsed.shouldResetFiles) || kind === 'pivot_platform' || kind === 'fresh_start',
      criticalUnknowns: Array.isArray(parsed.criticalUnknowns)
        ? parsed.criticalUnknowns.filter((q): q is string => typeof q === 'string' && q.trim().length > 0).slice(0, 3)
        : [],
      migrationSummary: parsed.migrationSummary ?? null,
      previousProjectType: filesSummary.projectType,
      previousLanguages: filesSummary.languages,
      previousFrameworks: filesSummary.frameworks,
    }
  } catch (err) {
    console.warn('[CodeOrchestrator] analyzeFollowUpIntent LLM failed, falling back to heuristic:', err)
    return buildFollowUpHeuristic(newPrompt, conversationHistory, existingFiles, filesSummary)
  }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeOrchestrationPhase =
  | 'intent'
  | 'preflight'
  | 'planning'
  | 'generation'
  | 'validation'
  | 'correction'
  | 'research'
  | 'dev_server'
  | 'done'
  | 'error'

export type CodeOrchestrationResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  intent: CodeIntent
  preflightReport: CodePreflightReport | null
  correctionLog: CorrectionPass[]
  phase: CodeOrchestrationPhase
  architecturePlan: string | null
  totalAttempts: number
  finalScore: number
  recoveryEvents: RecoveryEvent[]
  /** Follow-up analysis — null when no conversation context was available. */
  followUp: FollowUpAnalysis | null
  /**
   * v73: design polish report attached when the project produced visual
   * output. Lets the UI surface a badge ("Design 82/100 — manque clamp(),
   * @keyframes") instead of leaving the score buried in retry logs.
   */
  designReport?: DesignPolishReport | null
}

export type PhaseCallback = (detail: string, progress: number) => void

// ---------------------------------------------------------------------------
// Model routing
// ---------------------------------------------------------------------------

/**
 * Expert-model architecture: un modele code dominant pour TOUT le pipeline.
 * Plus de swap VRAM, plus de fallback vers un petit modele.
 * Les differents comportements sont obtenus via les System Prompts
 * (Architecte, Codeur, Auditeur) — pas en changeant de modele.
 */
function selectModel(
  _phase: 'planning' | 'generation' | 'review' | 'correction',
  _intent: CodeIntent,
  _escalationLevel: number,
  configuredCodeModel: string,
): string {
  return configuredCodeModel
}

// ---------------------------------------------------------------------------
// Shared constants — declared early so all functions can reference them
// ---------------------------------------------------------------------------

const DOCUMENTATION_EXTENSIONS_EARLY = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
const PREFLIGHT_PHASE_TIMEOUT_MS = 55_000
const RESEARCH_PHASE_TIMEOUT_MS = 25_000
const STREAM_GENERATION_TOTAL_TIMEOUT_MS = 2_700_000
const PLANNING_TIMEOUT_MS = 900_000
const CORRECTION_TIMEOUT_MS = 1_200_000
const PLANNING_FIRST_BYTE_TIMEOUT_MS = 720_000
const GENERATION_FIRST_BYTE_TIMEOUT_MS = 900_000
const CORRECTION_FIRST_BYTE_TIMEOUT_MS = 900_000
const CODE_PLANNING_CONTEXT_TOKENS = 16_384
const CODE_EXPERT_CONTEXT_TOKENS = 24_576
const CODE_EXPERT_OUTPUT_TOKENS = 16_000

const INTERACTIVE_3D_FIDELITY_MAX_PASSES = 4

/**
 * Deterministic playability check for a generated web game. Looks at the actual
 * HTML/JS for the essentials any playable game must have, cross-referenced with
 * what the brief asked for (keyboard vs pointer controls). Returns the missing
 * essentials plus a correction hint the auto-correction pass can act on.
 */
export function checkGamePlayability(
  files: CodeFile[],
  prompt: string,
): { ok: boolean; missing: string[]; hint: string } {
  const code = files
    .filter((f) => /\.(html?|m?[jt]sx?)$/i.test(f.name))
    .map((f) => f.content)
    .join('\n')
  if (!code.trim()) return { ok: true, missing: [], hint: '' }
  const lc = code.toLowerCase()
  const promptL = prompt.toLowerCase()
  const missing: string[] = []

  // 1) Game loop.
  const hasLoop = /requestanimationframe/i.test(code) || /setinterval\s*\(/i.test(code)
  if (!hasLoop) missing.push('boucle de jeu (requestAnimationFrame)')

  // 2) Keyboard controls when the brief asks for them.
  const wantsKeyboard =
    /\b(clavier|fl[eè]ches?|touche|touches|espace|wasd|arrow|keyboard|spacebar|saut|sauter|jump|d[eé]plac)/i.test(
      promptL,
    )
  const hasKeyboard =
    /addeventlistener\s*\(\s*['"]key(down|up|press)['"]/i.test(code) ||
    /on(keydown|keyup|keypress)\s*=/i.test(lc) ||
    /\.onkey(down|up|press)\b/i.test(lc)
  if (wantsKeyboard && !hasKeyboard) missing.push('gestion clavier (addEventListener keydown/keyup)')

  // 3) Pointer/touch controls when the brief asks for them and there is no keyboard.
  const wantsPointer = /\b(souris|clic|cliquer|tap|toucher|tactile|mouse|click|pointer)\b/i.test(promptL)
  const hasPointer =
    /addeventlistener\s*\(\s*['"](click|mousedown|mousemove|mouseup|pointerdown|pointermove|touchstart|touchmove)['"]/i.test(
      code,
    )
  if (wantsPointer && !wantsKeyboard && !hasPointer) missing.push('gestion souris/tactile')

  // 4) A canvas game must actually obtain a drawing context.
  if (/<canvas/i.test(code) && !/getcontext\s*\(/i.test(lc)) missing.push('rendu canvas (getContext)')

  // 5) A self-rescheduling game loop must actually be kicked off, not just
  // defined. Weak models routinely write
  //   function gameLoop(){ … requestAnimationFrame(gameLoop) }
  // but never call it → the canvas stays frozen/blank. Detect the loop function
  // by its self-reschedule, then require it to be invoked at least once more
  // (a direct call OR a second requestAnimationFrame(name) that kicks it off).
  const loopFn = code.match(/function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{[\s\S]*?requestAnimationFrame\s*\(\s*\1\b/)
  if (loopFn) {
    const name = loopFn[1]
    const directCalls = (code.match(new RegExp(`\\b${name}\\s*\\(`, 'g')) || []).length // includes the declaration
    const rafKicks = (code.match(new RegExp(`requestAnimationFrame\\s*\\(\\s*${name}\\b`, 'g')) || []).length
    if (directCalls <= 1 && rafKicks <= 1) missing.push("démarrage de la boucle (la fonction de boucle n'est jamais appelée)")
  }

  // 6) Features explicitly named in the brief must actually appear in the code.
  if (/particule|particle/i.test(promptL) && !/particule|particle/i.test(lc)) missing.push('effets de particules')
  // Named collectibles (coins / pièces / gems …) — a frequent omission: the
  // brief asks for coins to collect but the game ships without any. Require an
  // actual collection STRUCTURE (array or iteration), not just the substring —
  // a leftover `allCoinsCollected` boolean must not count as "coins present".
  const wantsCollectibles = /\b(pi[eè]ces?|coins?|gemmes?|gems?|[eé]toiles?|stars?)\b|\bcollect|\bramass/i.test(promptL)
  const COLLECTIBLE = '(?:coins?|pi[eè]ces?|gemmes?|gems?|[eé]toiles?|stars?|collectibles?|pickups?)'
  const hasCollectibles =
    new RegExp(`\\b${COLLECTIBLE}\\s*[=:]\\s*\\[`, 'i').test(code) ||
    new RegExp(`\\b${COLLECTIBLE}\\s*\\.\\s*(?:forEach|map|filter|length|push|splice|some|every)`, 'i').test(code) ||
    new RegExp(`\\b${COLLECTIBLE}\\s*\\[`, 'i').test(code)
  if (wantsCollectibles && !hasCollectibles) missing.push('objets à collecter (pièces/coins)')

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  const hint = [
    'JEU NON JOUABLE — ajoute ces éléments ESSENTIELS sans rien retirer du reste :',
    ...missing.map((m) => `- ${m}`),
    '',
    'Le joueur DOIT pouvoir contrôler le jeu immédiatement avec les contrôles demandés :',
    "- clavier : addEventListener('keydown'/'keyup') qui met à jour l'état du joueur, avec",
    '  preventDefault() sur les flèches et la barre d\'espace pour ne pas scroller la page ;',
    '- une boucle requestAnimationFrame avec delta-time (60 FPS) ;',
    '- un HUD qui affiche en continu le score et les vies ;',
    '- des collisions réellement résolues (repositionner le joueur sur la plateforme, pas un simple flag) ;',
    '- les écrans démarrage / game over / victoire câblés aux vraies conditions de jeu.',
  ].join('\n')
  return { ok: false, missing, hint }
}

/**
 * v89b: conservative bracket-balance scanner for JavaScript. Skips string
 * literals (', ", `) and comments so brackets inside them don't count. A
 * truncated file ("... for (let i = 0; i") ends with unclosed brackets → not
 * balanced. Used to catch JS that was cut off mid-generation (num_predict
 * budget) and would throw "Unexpected end of input" at load, killing the page.
 * Returns true when balanced (or trivially empty) — only a CLEAR imbalance is a
 * signal, to avoid false-positives on otherwise-valid code.
 */
function jsBracketsBalanced(code: string): boolean {
  if (!code.trim()) return true
  let paren = 0
  let brace = 0
  let bracket = 0
  let str: string | null = null
  let lineComment = false
  let blockComment = false
  for (let i = 0; i < code.length; i++) {
    const c = code[i]
    const next = code[i + 1]
    if (lineComment) {
      if (c === '\n') lineComment = false
      continue
    }
    if (blockComment) {
      if (c === '*' && next === '/') {
        blockComment = false
        i++
      }
      continue
    }
    if (str) {
      if (c === '\\') {
        i++
      } else if (c === str) {
        str = null
      }
      continue
    }
    if (c === '/' && next === '/') {
      lineComment = true
      i++
      continue
    }
    if (c === '/' && next === '*') {
      blockComment = true
      i++
      continue
    }
    if (c === '"' || c === "'" || c === '`') {
      str = c
      continue
    }
    if (c === '(') paren++
    else if (c === ')') paren--
    else if (c === '{') brace++
    else if (c === '}') brace--
    else if (c === '[') bracket++
    else if (c === ']') bracket--
    if (paren < 0 || brace < 0 || bracket < 0) return false
  }
  return paren === 0 && brace === 0 && bracket === 0 && !str && !blockComment
}

/**
 * v89b: deterministic integrity gate for a static_web page, mirroring
 * checkGamePlayability. A page can be "substantial" in bytes (>= 4000 chars of
 * HTML+CSS) yet be a NON-FUNCTIONAL SHELL — e.g. <script src="script.js"> with
 * no script.js in the file set, a <canvas> with no getContext anywhere, a
 * <tbody> "populated by JS" with no JS at all. The accept-after-1-pass shortcut
 * used to ship exactly that. This gate detects the hard, unambiguous failures
 * and surfaces them so the correction pass generates the missing logic.
 */
export function checkWebPageIntegrity(
  files: CodeFile[],
  prompt: string,
): { ok: boolean; missing: string[]; hint: string } {
  const htmlFiles = files.filter((f) => /\.html?$/i.test(f.name))
  if (htmlFiles.length === 0) return { ok: true, missing: [], hint: '' }
  const html = htmlFiles.map((f) => f.content).join('\n')

  // Basenames of every file we actually shipped (path-insensitive lookup).
  const shipped = new Set(
    files.map((f) => f.name.replace(/\\/g, '/').split('/').pop()?.toLowerCase()).filter(Boolean) as string[],
  )
  const missing: string[] = []

  // 1) Local <script src>/<link href> that points at a file we DIDN'T ship.
  //    External (http/protocol-relative/data) and in-page anchors are ignored.
  const refRe = /<(?:script\b[^>]*\bsrc|link\b[^>]*\bhref)\s*=\s*["']([^"']+)["']/gi
  let m: RegExpExecArray | null
  const danglingRefs: string[] = []
  while ((m = refRe.exec(html)) !== null) {
    const url = m[1].trim()
    if (/^(?:https?:)?\/\//i.test(url) || url.startsWith('data:') || url.startsWith('#') || url.startsWith('mailto:')) continue
    const base = url.split(/[?#]/)[0].split('/').pop()?.toLowerCase() || ''
    if (!/\.(?:m?js|css)$/i.test(base)) continue
    if (!shipped.has(base)) danglingRefs.push(url)
  }
  for (const r of danglingRefs) missing.push(`fichier local référencé mais absent du projet : ${r}`)

  // All application JS actually present = external .js files + inline <script>
  // bodies, MINUS the Tailwind config object (config, not app logic).
  const externalJs = files.filter((f) => /\.m?js$/i.test(f.name)).map((f) => f.content).join('\n')
  const inlineJs = Array.from(html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi))
    .map((x) => x[1])
    .join('\n')
  const appJs = `${externalJs}\n${inlineJs}`.replace(/tailwind\.config\s*=\s*\{[\s\S]*?\}\s*;?/i, '')
  const hasRealJs =
    /\b(?:function\b|=>|addEventListener|querySelector|getElementById|setInterval|setTimeout|requestAnimationFrame|getContext|fetch\s*\(|new\s+\w|class\s+\w)\b/i.test(appJs)

  // 1b) Referenced/shipped JS that is truncated or syntactically broken
  //     (unbalanced brackets) → the page throws at load and nothing runs.
  //     This is the num_predict-truncation failure mode ("...for (let i = 0; i").
  for (const f of files.filter((x) => /\.m?js$/i.test(x.name))) {
    if (!jsBracketsBalanced(f.content)) {
      missing.push(`JavaScript tronqué ou invalide (${f.name} — parenthèses/accolades non équilibrées) : la page plantera au chargement`)
    }
  }
  if (inlineJs.trim() && !jsBracketsBalanced(inlineJs)) {
    missing.push('script inline tronqué ou invalide (parenthèses/accolades non équilibrées)')
  }

  // 2) A <canvas> that never obtains a drawing context → blank chart.
  if (/<canvas/i.test(html) && !/getContext\s*\(/i.test(appJs)) {
    missing.push('canvas sans rendu (aucun getContext) — le(s) graphique(s) restent blancs')
  }

  // 3) A container explicitly waiting for JS injection, with no JS present.
  const hasEmptyDynamicContainer =
    /populated?\s+by\s+js|rempli\s+par\s+js|will\s+be\s+(?:populated|added|generated)|injected?\s+by\s+js/i.test(html) ||
    /<tbody\b[^>]*>\s*(?:<!--[\s\S]*?-->)?\s*<\/tbody>/i.test(html)
  if (hasEmptyDynamicContainer && !hasRealJs) {
    missing.push("contenu dynamique jamais injecté (table/liste vide) — aucune logique JavaScript présente")
  }

  // 4) The brief demands interactivity but the page ships zero application JS.
  const wantsInteractivity =
    /\b(setinterval|temps\s*r[eé]el|live|interactif|tri(?:able|er)?|filtr|recherche|toggle|bascul|convertisseur|calcul|graphique|chart|dashboard|tableau\s+de\s+bord|anim)\b/i.test(
      prompt.toLowerCase(),
    )
  if (wantsInteractivity && !hasRealJs) {
    missing.push("logique JavaScript applicative absente alors que le brief exige de l'interactivité")
  }

  // 5) JS that targets element ids ABSENT from the HTML (and not created by JS)
  //    → getElementById(...) returns null and the feature silently dies (blank
  //    chart, dead control). Real failure: JS read #today-pnl-chart while the
  //    canvas was id="pnl-chart" → initCharts threw → every chart stayed blank.
  //    Only static string-literal ids are checked; concatenated/dynamic ids
  //    (getElementById('row-' + i)) never match and are never flagged.
  const knownIds = new Set<string>()
  for (const m of html.matchAll(/\bid\s*=\s*["']([^"']+)["']/gi)) knownIds.add(m[1])
  // ids the JS itself creates (innerHTML templates, .id =, setAttribute('id',…)).
  for (const m of appJs.matchAll(/\bid\s*=\s*["']([^"'\s]+)["']/gi)) knownIds.add(m[1])
  for (const m of appJs.matchAll(/\.id\s*=\s*["']([^"'\s]+)["']/g)) knownIds.add(m[1])
  for (const m of appJs.matchAll(/setAttribute\(\s*["']id["']\s*,\s*["']([^"'\s]+)["']/g)) knownIds.add(m[1])
  const referencedIds = new Set<string>()
  for (const m of appJs.matchAll(/getElementById\(\s*["']([A-Za-z][\w-]*)["']\s*\)/g)) referencedIds.add(m[1])
  for (const m of appJs.matchAll(/querySelector(?:All)?\(\s*["']#([A-Za-z][\w-]*)["']\s*\)/g)) referencedIds.add(m[1])
  const danglingIds = [...referencedIds].filter((id) => !knownIds.has(id))
  if (danglingIds.length > 0) {
    missing.push(
      `le JavaScript cible des éléments inexistants dans le HTML (#${danglingIds.slice(0, 6).join(', #')}) — corrige les id pour que ces fonctionnalités (graphiques/contrôles) marchent`,
    )
  }

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  const hint = [
    'PAGE NON FONCTIONNELLE — la structure HTML est là mais la logique manque. Corrige SANS rien retirer du HTML/CSS existant :',
    ...missing.map((x) => `- ${x}`),
    '',
    "Génère le fichier JavaScript référencé (ex: script.js) — ou intègre le <script> inline dans index.html — avec TOUTE la logique attendue :",
    "- remplir et mettre à jour le DOM (peupler chaque <tbody>/liste vide, pas de placeholder) ;",
    "- chaque <canvas> doit obtenir son contexte (getContext) et être DESSINÉ (graphique + donut) ;",
    "- les mises à jour temps réel via setInterval (cours qui bougent) ;",
    "- tri des colonnes au clic, recherche/filtre, convertisseur de devises, toggle de thème persistant (localStorage), calcul du P&L ;",
    "- toutes les données simulées en JavaScript pur, aucune dépendance réseau.",
    "Le fichier doit RÉELLEMENT exister dans le projet et être chargé par index.html.",
  ].join('\n')
  return { ok: false, missing, hint }
}

export function checkInteractive3DFidelity(
  files: CodeFile[],
  prompt: string,
  intent?: CodeIntent,
): { ok: boolean; missing: string[]; hint: string } {
  const code = files
    .filter((file) => /\.(html?|css|m?[jt]sx?|vue|svelte)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')
  if (!code.trim()) return { ok: true, missing: [], hint: '' }

  const codeLower = code.toLowerCase()
  const promptLower = prompt.toLowerCase()
  const missing: string[] = []

  const wants3D =
    intent?.features.includes('3d')
    || intent?.assetPlan?.wants3D
    || /\b(3d|three\.?js|r3f|webgl|space|spaceship|vaisseau|station spatiale|asteroid|planet|orbital|cockpit|simulateur|simulator)\b/i.test(promptLower)
  const has3D =
    /@react-three\/fiber|@react-three\/drei|<Canvas\b|new\s+THREE\.|WebGLRenderer|three\/examples/i.test(code)

  if (!wants3D && !has3D) return { ok: true, missing: [], hint: '' }

  const wantsKeyboard =
    /\b(wasd|clavier|keyboard|key(?:down|up)|touches?|fleches?|arrows?|shift|boost|espace|space|pilotage|piloter|fly|voler|thrust|propulsion)\b/i.test(promptLower)
  const hasKeyboard =
    /\baddEventListener\s*\(\s*['"]key(?:down|up|press)['"]|onKeyDown|onKeyUp|KeyboardControls|useKeyboardControls|\.onkey(?:down|up|press)\b/i.test(code)
  const hasFrameMovement =
    /\b(useFrame|requestAnimationFrame|setInterval)\b/i.test(code)
    && /\b(position\.(?:x|y|z|set)|camera\.position|velocity|speed|thrust|boost|acceleration|delta)\b/i.test(code)
  if (wantsKeyboard && (!hasKeyboard || !hasFrameMovement)) {
    missing.push('pilotage clavier/WASD relie a un mouvement 3D par frame')
  }

  const wantsMinimap = /\b(minimap|mini-map|radar|scanner map|carte tactique)\b/i.test(promptLower)
  const radarLooksRandom =
    /\bradar[\s\S]{0,900}\bMath\.random\s*\(/i.test(code)
    || /\bblip[\s\S]{0,400}\bMath\.random\s*\(/i.test(code)
  const hasMinimap =
    /\b(minimap|mini-map|radar|blip|scanline|tactical-map|tacticalMap)\b/i.test(code)
    && /<svg\b|<canvas\b|\.map\s*\(|position/i.test(code)
  if (wantsMinimap && (!hasMinimap || radarLooksRandom)) {
    missing.push('minimap/radar avec positions ou blips reels, pas des points aleatoires')
  }

  const wantsWorldInteractions =
    /\b(collect|collecter|resource|ressource|resources|minerai|mineral|minerals|dock|docking|scanner?|scan|mission|objectif|objective)\b/i.test(promptLower)
  const hasSpatialCheck =
    /\b(distanceTo|raycaster|intersect|intersectsSphere|collision|collid|Math\.hypot|Vector3|Box3|Sphere)\b/i.test(code)
  const hasDomainAction =
    /\b(collect|resource|ressource|minerai|mineral|dock|docking|scan|scanner|mission|objective|cargo|inventory)\b/i.test(code)
  if (wantsWorldInteractions && (!hasSpatialCheck || !hasDomainAction)) {
    missing.push('collecte/scan/docking relies a des tests spatiaux, pas seulement a du texte HUD')
  }

  const wantsDynamicHud =
    /\b(hud|energy|energie|shield|fuel|minerals|resources|mission|score|cargo|inventory)\b/i.test(promptLower)
    || wantsWorldInteractions
  const hasDynamicHud =
    /\bset(?:Energy|Fuel|Shield|Minerals|Resources|Score|Mission|Cargo|Inventory)\s*\(|useReducer\s*\(|dispatch\s*\(/.test(code)
  if (wantsDynamicHud && wantsWorldInteractions && !hasDynamicHud) {
    missing.push('HUD dynamique mis a jour par les interactions')
  }

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  return {
    ok: false,
    missing,
    hint: [
      'FIDELITE 3D INTERACTIVE INSUFFISANTE - la scene compile peut-etre, mais elle ne realise pas le brief.',
      ...missing.map((item) => `- ${item}`),
      '',
      'Correction attendue:',
      "- ajouter un etat de vaisseau/joueur (position, velocity, fuel/energy, cargo) pilote par keydown/keyup et useFrame(delta) ;",
      '- afficher une minimap/radar derivee des positions reelles des objets si le brief la demande ;',
      '- implementer scan/collect/docking avec distanceTo, raycaster, collision ou volumes 3D ;',
      '- connecter ces interactions au HUD et aux objectifs de mission ;',
      '- garder le rendu React Three Fiber propre, avec HUD HTML hors Canvas ou via Html de drei.',
    ].join('\n'),
  }
}

// ---------------------------------------------------------------------------
// LLM Refusal Detection — catches when model refuses instead of generating code
// ---------------------------------------------------------------------------

const LLM_REFUSAL_PATTERNS = [
  /je (suis d[eé]sol[eé]|ne (peux|suis) pas|m'excuse)/i,
  /i('m| am) (sorry|unable|not able)/i,
  /i (can'?t|cannot|could not|wouldn'?t) (help|assist|generate|create|produce|provide|write|code)/i,
  /je ne (peux|suis) pas (aider|g[eé]n[eé]rer|cr[eé]er|produire|[eé]crire)/i,
  /pas aider [àa] g[eé]n[eé]rer/i,
  /contredit les directives/i,
  /ne respecte pas le format/i,
  /d[eé]passe mes capacit[eé]s/i,
  /beyond my (capabilities|ability)/i,
  /i (don'?t|do not) (have|possess) the ability/i,
  /contre les (r[eè]gles|directives|politiques)/i,
  /against (my |the )?(rules|guidelines|policies)/i,
  /je vous sugg[eè]re plut[oô]t/i,
  /i (would |)suggest (instead|rather|you)/i,
  /examiner attentivement vos instructions/i,
  /review your instructions/i,
]

const LLM_REFUSAL_NEGATIVE_PATTERNS = [
  /```\w+\n/,           // Contains code blocks → probably not a refusal
  /--- FICHIER:/i,      // Contains file markers → structured output
  /--- FILE:/i,
  /import\s+\{/,        // Actual code patterns
  /export\s+(default\s+)?/,
  /function\s+\w+/,
  /class\s+\w+/,
  /const\s+\w+\s*=/,
  /<html/i,
  /<!DOCTYPE/i,
  // v85d : modern SFC / Astro idioms — these are CODE, never a refusal. Without
  // them a valid .astro/.vue/.svelte file (frontmatter, <style>, <template>)
  // could be flagged as a refusal and the whole project scored 0.
  /<template[\s>]/i,
  /<style[\s>]/i,
  /<script[\s>]/i,
  /Astro\.(props|glob|url|request)/,
  /getCollection\s*\(/,
  /^---\s*$/m,
]

/**
 * Detects if LLM output is a refusal/apology instead of actual code.
 * Returns true if content is a refusal message.
 */
export function isLLMRefusal(content: string): boolean {
  if (!content || content.trim().length < 20) return false
  const trimmed = content.trim()

  // If content has clear code structure, it's not a refusal
  if (LLM_REFUSAL_NEGATIVE_PATTERNS.some((p) => p.test(trimmed))) return false

  // Check against refusal patterns
  const matchCount = LLM_REFUSAL_PATTERNS.filter((p) => p.test(trimmed)).length
  if (matchCount >= 2) return true

  // Single match + short content (< 800 chars) + no code → likely refusal
  if (matchCount >= 1 && trimmed.length < 800) return true

  return false
}

/**
 * Computes a content quality score independent of sandbox results.
 * Penalizes: refusals, too-short files, placeholder content, missing structure.
 */
function computeContentQualityScore(files: CodeFile[], intent: CodeIntent): number {
  if (files.length === 0) return 0

  // Check for refusal in any file
  const refusalFile = files.find((f) => isLLMRefusal(f.content))
  if (refusalFile) return 0

  // Check for generic fallback files (reponse.txt)
  const allGeneric = files.every((f) => /^(reponse|bloc-\d+)\.(txt|text)$/i.test(f.name))
  if (allGeneric) return 5

  // Check for actual code files
  const codeFiles = files.filter((f) => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return !DOCUMENTATION_EXTENSIONS_EARLY.has(ext)
  })
  if (codeFiles.length === 0) return 10

  // Average content length check
  const avgLen = codeFiles.reduce((sum, f) => sum + f.content.length, 0) / codeFiles.length
  if (avgLen < 50) return 20

  // Basic structure check for web projects
  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    const hasHtml = files.some((f) => /\.html?$/i.test(f.name))
    if (!hasHtml) return 40
  }

  // Design polish gate: pour les projets visibles (web/UI), penaliser quand le
  // CSS+HTML produit ne respecte pas le design contract (pas de variables CSS,
  // pas de gradients, pas de transitions, pas de Google Fonts premium, pas
  // d animations). Le user a explicitement dit "designs pousses tout le temps"
  // donc une UI scolaire = score plafonne a 60 = trigger correction loop.
  if (isVisualProjectType(intent.projectType)) {
    const designScore = computeDesignPolishScore(files)
    if (designScore < 50) return 55
    if (designScore < 70) return 75
  }

  return 100 // Content looks structurally valid
}

function isVisualProjectType(type: string): boolean {
  return type === 'static_web'
    || type === 'spa_react'
    || type === 'spa_vue'
    || type === 'spa_angular'
    || type === 'spa_svelte'
    || type === 'ssr_nextjs'
    || type === 'ssr_nuxt'
    || type === 'ssr_remix'
    || type === 'fullstack_mern'
    || type === 'fullstack_nextjs'
    || type === 'fullstack_django'
    || type === 'fullstack_rails'
    || type === 'desktop_electron'
    || type === 'desktop_tauri'
    || type === 'mobile_rn'
    || type === 'mobile_flutter'
    || type === 'game_web'
}

/**
 * Score 0-100 of how "premium" the generated visual code looks. Pure
 * heuristic — checks for the design tokens / patterns the design contract
 * demands. Used to gate the auto-correction loop: a < 70 score triggers
 * a regeneration with explicit "ce que tu as fait est trop scolaire" hint.
 */
function computeDesignPolishScore(files: CodeFile[]): number {
  return computeDesignPolishReport(files).score
}

/**
 * v66: returns BOTH the numerical score AND the list of premium signals
 * that the LLM did not include. Used by the correction loop to send a
 * targeted retry instruction ("ajoute @keyframes + backdrop-filter +
 * clamp()") instead of a vague "fais un design plus pousse".
 */
export type DesignPolishReport = {
  score: number
  missing: string[]
  penalties: string[]
}

export function computeDesignPolishReportPublic(files: CodeFile[]): DesignPolishReport {
  return computeDesignPolishReport(files)
}

function computeDesignPolishReport(files: CodeFile[]): DesignPolishReport {
  const visualBlob = files
    .filter((f) => /\.(html?|css|s?css|less|tsx?|jsx?|vue|svelte|astro)$/i.test(f.name)) // v85d : +astro
    .map((f) => f.content)
    .join('\n')
    .toLowerCase()

  if (visualBlob.length < 200) {
    return {
      score: 30,
      missing: ['contenu visuel insuffisant — moins de 200 caracteres de CSS/HTML detectes'],
      penalties: [],
    }
  }

  let score = 0
  const missing: string[] = []
  // Premium signals (label, regex, points)
  const checks: Array<{ label: string; pattern: RegExp; points: number }> = [
    { label: 'CSS variables / design tokens (--color-*, --space-*, etc.)', pattern: /--[a-z-]+:\s*/i, points: 12 },
    { label: 'police premium Google Fonts (Inter / Manrope / Satoshi / DM Sans / Space Grotesk / Plus Jakarta)', pattern: /inter|manrope|satoshi|dm sans|space grotesk|plus jakarta|bricolage|bangers/i, points: 10 },
    { label: 'gradients (linear-gradient / radial-gradient / conic-gradient)', pattern: /(linear|radial|conic)-gradient/i, points: 12 },
    { label: 'transitions explicites (transition: ... 250ms cubic-bezier)', pattern: /transition:\s*[^;]+\d+ms/i, points: 8 },
    { label: '@keyframes (animations CSS)', pattern: /@keyframes\s+\w+/i, points: 10 },
    { label: 'backdrop-filter blur (glassmorphism)', pattern: /backdrop-filter\s*:\s*blur/i, points: 10 },
    { label: 'clamp() pour les tailles responsive', pattern: /clamp\s*\(/i, points: 8 },
    { label: 'box-shadow multi-layer composite', pattern: /box-shadow\s*:[^;]*,[^;]*\d/i, points: 8 },
    { label: 'utilisation de var(--*) (variables CSS appliquees)', pattern: /var\(--[a-z]/i, points: 6 },
    { label: 'layout moderne grid ou flex', pattern: /display\s*:\s*(grid|flex)/i, points: 6 },
    { label: 'hover states (:hover {)', pattern: /:hover\s*\{/i, points: 5 },
  ]

  for (const { label, pattern, points } of checks) {
    if (pattern.test(visualBlob)) {
      score += points
    } else {
      missing.push(`${label} (${points} pts manquants)`)
    }
  }

  // Palette richness bonus: count distinct hex colors
  const hexes = new Set((visualBlob.match(/#[0-9a-f]{6}/g) || []))
  if (hexes.size >= 5) score += 5
  else if (hexes.size >= 3) score += 3
  else missing.push(`palette riche (${hexes.size} couleurs hex distinctes seulement, vise 5+)`)

  // Penalties: scolaire markers
  const penalties: string[] = []
  if (/font-family\s*:\s*["']?(arial|times new roman|sans-serif)\s*[;,"']/i.test(visualBlob)) {
    score -= 15
    penalties.push('police par defaut (Arial / Times / sans-serif) — utilise une Google Fonts premium')
  }
  if (/<table[^>]*>\s*<tr/i.test(visualBlob) && !/role="grid"/i.test(visualBlob)) {
    score -= 10
    penalties.push('layout en <table> — utilise CSS grid ou flexbox')
  }
  if (/(background|color)\s*:\s*(blue|red|green|yellow|black|white)\s*;/i.test(visualBlob)) {
    score -= 5
    penalties.push('couleur basique (blue/red/green) — utilise un hex code premium ou une variable CSS')
  }
  if (/<button[^>]*>(?:[^<]*?)<\/button>/.test(visualBlob)
    && !/button\s*\{[\s\S]*?(background|border-radius|transition)/i.test(visualBlob)) {
    score -= 8
    penalties.push('bouton sans style (pas de background, border-radius, ou transition) — restyle-le')
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    missing,
    penalties,
  }
}

/**
 * v66: build a targeted retry prompt that tells the LLM exactly what was
 * missing in the previous output. Used when computeDesignPolishReport
 * reports a score < 70 — the orchestrator can re-stream with this added
 * to the user prompt to push the LLM in the right direction.
 */
export function buildDesignRetryHint(report: DesignPolishReport): string {
  const lines: string[] = [
    '═══════════════════════════════════════════════════════════',
    'AUDIT DESIGN — ton output precedent est ENCORE TROP SCOLAIRE',
    `Score: ${report.score}/100 (seuil minimum: 70)`,
    '═══════════════════════════════════════════════════════════',
    '',
  ]
  if (report.missing.length > 0) {
    lines.push('Ce que tu as OUBLIE (a ajouter imperativement):')
    for (const item of report.missing.slice(0, 8)) {
      lines.push(`  ✗ ${item}`)
    }
    lines.push('')
  }
  if (report.penalties.length > 0) {
    lines.push('Ce que tu as MAL FAIT (a corriger):')
    for (const item of report.penalties) {
      lines.push(`  ⚠ ${item}`)
    }
    lines.push('')
  }
  lines.push(
    'Refais le projet COMPLET avec TOUS ces points corriges.',
    'INTERDICTION absolue de relivrer du HTML qui ressemblerait a un tutoriel debutant.',
    '═══════════════════════════════════════════════════════════',
  )
  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// File parsing
// ---------------------------------------------------------------------------

export function parseCodeFiles(content: string): CodeFile[] {
  const files: CodeFile[] = []
  const parts = content.split(/---\s*(?:FICHIER|FILE):\s*(.+?)\s*---/i)

  if (parts.length > 1) {
    for (let index = 1; index < parts.length; index += 2) {
      const name = parts[index].trim()
      const code = sanitizeGeneratedFileContent(name, cleanCodeBlock(parts[index + 1] || ''))
      if (!name || !code) continue
      files.push({ name, language: detectLanguage(name), content: code })
    }
  }

  if (files.length === 0) {
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g
    let match: RegExpExecArray | null
    let blockIndex = 1
    while ((match = codeBlockRegex.exec(content)) !== null) {
      let language = match[1] || 'txt'
      const blockContent = match[2].trim()
      if (!blockContent) continue

      // Smart language detection: if the tag is generic (markdown, text, txt)
      // but content looks like actual code, override the tag
      if (['markdown', 'md', 'text', 'txt', ''].includes(language.toLowerCase())) {
        const detectedLang = detectContentLanguage(blockContent)
        if (detectedLang) language = detectedLang
      }

      const ext = langToExt(language)
      const name = inferFileName(blockContent, ext, blockIndex)
      files.push({ name, language, content: sanitizeGeneratedFileContent(name, blockContent) })
      blockIndex += 1
    }
  }

  if (files.length === 0 && content.trim()) {
    // If the content is a refusal, return empty — do NOT create reponse.txt with garbage
    if (isLLMRefusal(content)) {
      return []
    }

    if (detectNonCodePlanningNarrative(content)) {
      return []
    }

    // Last resort: check if the raw content IS code (LLM forgot code fences)
    const detectedLang = detectContentLanguage(content.trim())
    if (detectedLang) {
      const ext = langToExt(detectedLang)
      files.push({ name: `main.${ext}`, language: detectedLang, content: sanitizeGeneratedFileContent(`main.${ext}`, cleanCodeBlock(content)) })
    } else {
      // Only create reponse.txt if content is substantial and not a refusal
      const cleaned = cleanCodeBlock(content)
      if (cleaned.length > 100) {
        files.push({ name: 'reponse.txt', language: 'text', content: sanitizeGeneratedFileContent('reponse.txt', cleaned) })
      }
    }
  }

  return files
}

function cleanCodeBlock(text: string) {
  let t = text.replace(/\r\n/g, '\n').trim()
  // A file segment (the text between two `--- FICHIER: … ---` markers) usually
  // wraps the code in a markdown fence. Models sometimes append a stray closing
  // fence and even extra ```css / ```bash blocks AFTER the file's real code —
  // the next file's content emitted without its own separator. The old strip
  // (one leading + one trailing fence) left that junk in the file, which breaks
  // it: a trailing "```css" inside game.js throws
  //   Uncaught SyntaxError: Unexpected identifier 'css'
  // and the whole script (the game) never runs. When the segment is
  // fence-wrapped, keep ONLY the first fenced block's body.
  const opening = t.match(/^```[\w.+#-]*[ \t]*\n/)
  if (opening) {
    const body = t.slice(opening[0].length)
    const closeIdx = body.search(/\n```[ \t]*(?:\n|$)/)
    if (closeIdx !== -1) return body.slice(0, closeIdx).trim()
    // No closing fence — drop the opener and fall through to line cleanup.
    t = body
  }
  // Strip any remaining standalone markdown fence lines (opener or closer).
  t = t.replace(/^[ \t]*```[\w.+#-]*[ \t]*$/gm, '').trim()
  return t
}

function stripFormattingArtifacts(content: string) {
  let current = content
    .replace(/^\uFEFF/, '')
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .trim()

  for (let index = 0; index < 3; index += 1) {
    const next = current
      .replace(/^```[\w.-]*\s*\r?\n/, '')
      .replace(/\r?\n```$/, '')
      .trim()

    if (next === current) break
    current = next
  }

  return current
}

function stripJsonCommentsAndTrailingCommas(content: string) {
  let out = ''
  let inString = false
  let quote = ''
  let escaped = false
  let inLineComment = false
  let inBlockComment = false

  for (let index = 0; index < content.length; index += 1) {
    const ch = content[index]
    const next = content[index + 1]

    if (inLineComment) {
      if (ch === '\n' || ch === '\r') {
        inLineComment = false
        out += ch
      }
      continue
    }

    if (inBlockComment) {
      if (ch === '*' && next === '/') {
        inBlockComment = false
        index += 1
      }
      continue
    }

    if (inString) {
      out += ch
      if (escaped) {
        escaped = false
      } else if (ch === '\\') {
        escaped = true
      } else if (ch === quote) {
        inString = false
        quote = ''
      }
      continue
    }

    if (ch === '"' || ch === "'") {
      inString = true
      quote = ch
      out += ch
      continue
    }

    if (ch === '/' && next === '/') {
      inLineComment = true
      index += 1
      continue
    }

    if (ch === '/' && next === '*') {
      inBlockComment = true
      index += 1
      continue
    }

    out += ch
  }

  return out.replace(/,\s*([}\]])/g, '$1')
}

function isStructuredMachineFile(filename: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  return normalized.endsWith('.json')
    || normalized.endsWith('.toml')
    || normalized.endsWith('.yaml')
    || normalized.endsWith('.yml')
}

function tryParseJson(content: string) {
  try {
    return JSON.parse(content) as Record<string, unknown>
  } catch {
    try {
      const repaired = stripJsonCommentsAndTrailingCommas(content)
      if (repaired === content) return null
      return JSON.parse(repaired) as Record<string, unknown>
    } catch {
      return null
    }
  }
}

const SAFE_VITE_VERSION = '^8.1.3'
const SAFE_VITE_REACT_PLUGIN_VERSION = '^5.1.2'

function repairKnownManifestDependencyNames(manifest: Record<string, unknown>) {
  let next: Record<string, unknown> = { ...manifest }
  const renameMap: Record<string, string> = {
    'react-three-fiber': '@react-three/fiber',
    'react-three/drei': '@react-three/drei',
    'react-three/postprocessing': '@react-three/postprocessing',
  }

  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const deps = next[section]
    if (!deps || typeof deps !== 'object' || Array.isArray(deps)) continue
    const repairedDeps: Record<string, unknown> = { ...(deps as Record<string, unknown>) }
    for (const [wrongName, correctName] of Object.entries(renameMap)) {
      if (!(wrongName in repairedDeps)) continue
      repairedDeps[correctName] = repairedDeps[correctName] || repairedDeps[wrongName]
      delete repairedDeps[wrongName]
    }
    next[section] = repairedDeps
  }

  if (manifestUsesPackage(next, 'vite') || manifestUsesPackage(next, '@vitejs/plugin-react') || manifestHasViteScript(next)) {
    next = movePackageToDevDependency(next, 'vite', SAFE_VITE_VERSION)
    next = movePackageToDevDependency(next, '@vitejs/plugin-react', SAFE_VITE_REACT_PLUGIN_VERSION)
  }

  return next
}

function repairGeneratedTsConfig(config: Record<string, unknown>) {
  const compilerOptions =
    config.compilerOptions && typeof config.compilerOptions === 'object' && !Array.isArray(config.compilerOptions)
      ? { ...(config.compilerOptions as Record<string, unknown>) }
      : {}

  compilerOptions.noUnusedLocals = false
  compilerOptions.noUnusedParameters = false

  return {
    ...config,
    compilerOptions,
  }
}

function repairGeneratedTypeScriptContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  if (!/\.[cm]?[jt]sx?$/.test(normalized)) return content

  let next = content

  // React 19 exposes a readonly ref overload when useRef<T>(null) is used with
  // non-nullable T. Generated R3F code frequently assigns to ref.current during
  // scene setup, so the ref must include null in its type parameter.
  next = next.replace(
    /\buseRef<((?:THREE\.)?(?:Mesh|Group|Object3D|InstancedMesh|PerspectiveCamera|OrthographicCamera|Camera|Scene|DirectionalLight|PointLight|SpotLight|AmbientLight|Line|Points|Sprite))>\(null\)/g,
    'useRef<$1 | null>(null)',
  )

  // Common Zustand shape emitted by local models: the store type only accepts a
  // concrete resources array, but components call setResources(prev => ...).
  next = next.replace(
    /setResources:\s*\(resources:\s*THREE\.Mesh\[\]\)\s*=>\s*void/g,
    'setResources: (resources: THREE.Mesh[] | ((prev: THREE.Mesh[]) => THREE.Mesh[])) => void',
  )
  next = next.replace(
    /setResources:\s*\(resources\)\s*=>\s*set\(\{\s*resources\s*\}\)/g,
    "setResources: (resources) => set((state) => ({ resources: typeof resources === 'function' ? resources(state.resources) : resources }))",
  )

  if (/\binterface\s+TableProps\s*<\s*TData\s*>/.test(next) || /\bconst\s+Table\s*=\s*<\s*TData\b/.test(next)) {
    next = next.replace(/\baccessorKey:\s*string\b/g, 'accessorKey?: keyof TData | string')
    next = next.replace(/key=\{column\.accessorKey\}/g, 'key={String(column.accessorKey || column.header)}')
    next = next.replace(
      /row\[column\.accessorKey\s+as\s+keyof\s+TData\]/g,
      '(column.accessorKey ? row[column.accessorKey as keyof TData] : undefined)',
    )
  }

  return next
}

function sanitizeGeneratedFileContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  const cleaned = stripFormattingArtifacts(content)

  if (normalized.endsWith('.json')) {
    const parsed = tryParseJson(cleaned)
    if (parsed) {
      const next = normalized === 'package.json'
        ? repairKnownManifestDependencyNames(parsed)
        : normalized.endsWith('tsconfig.json') || normalized.endsWith('tsconfig.node.json')
          ? repairGeneratedTsConfig(parsed)
          : parsed
      return `${JSON.stringify(next, null, 2)}\n`
    }
  }

  if (isStructuredMachineFile(normalized)) {
    return cleaned
  }

  return repairGeneratedTypeScriptContent(filename, cleaned)
}

function upsertPackageDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
  force = false,
) {
  const deps = manifest.dependencies && typeof manifest.dependencies === 'object' && !Array.isArray(manifest.dependencies)
    ? { ...(manifest.dependencies as Record<string, unknown>) }
    : {}

  if (force || !(dependencyName in deps)) {
    deps[dependencyName] = version
  }

  return { ...manifest, dependencies: deps }
}

function upsertPackageDevDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
  force = false,
) {
  const devDeps = manifest.devDependencies && typeof manifest.devDependencies === 'object' && !Array.isArray(manifest.devDependencies)
    ? { ...(manifest.devDependencies as Record<string, unknown>) }
    : {}

  if (force || !(dependencyName in devDeps)) {
    devDeps[dependencyName] = version
  }

  return { ...manifest, devDependencies: devDeps }
}

function manifestUsesPackage(manifest: Record<string, unknown>, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const deps = manifest[section]
    if (deps && typeof deps === 'object' && !Array.isArray(deps) && dependencyName in deps) {
      return true
    }
  }
  return false
}

function manifestHasViteScript(manifest: Record<string, unknown>) {
  const scripts = manifest.scripts
  if (!scripts || typeof scripts !== 'object' || Array.isArray(scripts)) return false
  return Object.values(scripts as Record<string, unknown>).some((script) => /\bvite\b/.test(String(script)))
}

function movePackageToDevDependency(
  manifest: Record<string, unknown>,
  dependencyName: string,
  version: string,
) {
  let next: Record<string, unknown> = { ...manifest }
  for (const section of ['dependencies', 'optionalDependencies'] as const) {
    const deps = next[section]
    if (!deps || typeof deps !== 'object' || Array.isArray(deps) || !(dependencyName in deps)) continue
    const repairedDeps = { ...(deps as Record<string, unknown>) }
    delete repairedDeps[dependencyName]
    next = { ...next, [section]: repairedDeps }
  }
  return upsertPackageDevDependency(next, dependencyName, version, true)
}

const NODE_BUILTIN_IMPORTS = new Set([
  'assert', 'buffer', 'child_process', 'cluster', 'crypto', 'dns', 'events', 'fs',
  'http', 'https', 'net', 'os', 'path', 'process', 'querystring', 'readline',
  'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url', 'util', 'vm', 'zlib',
])

const COMMON_PACKAGE_IMPORT_VERSIONS: Record<string, string> = {
  '@monaco-editor/react': '^4.7.0',
  '@react-spring/three': '^9.7.5',
  '@react-three/drei': '^10.7.7',
  '@react-three/fiber': '^9.6.1',
  '@react-three/postprocessing': '^3.0.4',
  '@vitejs/plugin-react': SAFE_VITE_REACT_PLUGIN_VERSION,
  'framer-motion': '^11.18.2',
  'lucide-react': '^0.468.0',
  'monaco-editor': '^0.52.2',
  'react': '^19.2.0',
  'react-dom': '^19.2.0',
  'react-icons': '^5.5.0',
  'react-router-dom': '^7.13.2',
  'three': '^0.183.2',
  'zustand': '^5.0.2',
}

function packageNameFromImportSpecifier(specifier: string): string | null {
  if (!specifier || specifier.startsWith('.') || specifier.startsWith('/') || specifier.startsWith('#')) return null
  if (specifier.startsWith('node:')) return null
  const parts = specifier.split('/')
  const packageName = specifier.startsWith('@') && parts.length >= 2
    ? `${parts[0]}/${parts[1]}`
    : parts[0]
  if (NODE_BUILTIN_IMPORTS.has(packageName)) return null
  return packageName
}

function collectBarePackageImports(sourceBlob: string): Set<string> {
  const packages = new Set<string>()
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(sourceBlob)) !== null) {
      const packageName = packageNameFromImportSpecifier(match[1])
      if (packageName) packages.add(packageName)
    }
  }
  return packages
}

function repairPackageManifestFromSourceImports(files: CodeFile[]) {
  const packageIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex < 0) return files

  const packageFile = files[packageIndex]
  let manifest = tryParseJson(stripFormattingArtifacts(packageFile.content))
  if (!manifest) return files

  const sourceBlob = files
    .filter((file) => /\.(tsx?|jsx?|vue|svelte|astro)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')

  manifest = repairKnownManifestDependencyNames(manifest)

  const usesR3f = /@react-three\/(fiber|drei|postprocessing)/.test(sourceBlob)
  if (usesR3f) {
    const reactSpec = readManifestDependencySpec(manifest as LocalNodeManifest, 'react')
    // v89b: parseSpecVersion(...)?.major is number | undefined; normalise the
    // unparseable case to null so an unknown React version defaults to React 19
    // (same as the no-spec branch) instead of silently skipping the upgrade.
    const reactMajor = (reactSpec ? parseSpecVersion(reactSpec)?.major : null) ?? null
    const useReact19 = reactMajor === null || reactMajor >= 19

    if (useReact19) {
      manifest = upsertPackageDependency(manifest, 'react', '^19.2.0', true)
      manifest = upsertPackageDependency(manifest, 'react-dom', '^19.2.0', true)
      manifest = upsertPackageDevDependency(manifest, '@types/react', '^19.0.0', true)
      manifest = upsertPackageDevDependency(manifest, '@types/react-dom', '^19.0.0', true)
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', '^9.6.1', true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', '^10.7.7', true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', '^3.0.4', true)
      }
    } else {
      manifest = upsertPackageDependency(manifest, '@react-three/fiber', '^8.18.0', true)
      manifest = upsertPackageDependency(manifest, '@react-three/drei', '^9.122.0', true)
      if (/@react-three\/postprocessing/.test(sourceBlob)) {
        manifest = upsertPackageDependency(manifest, '@react-three/postprocessing', '^2.16.3', true)
      }
    }
  }

  const requiredDeps: Array<[RegExp, string, string]> = [
    [/@react-spring\/three/, '@react-spring/three', '^9.7.5'],
    [/framer-motion/, 'framer-motion', '^11.18.2'],
  ]

  for (const [pattern, dependencyName, version] of requiredDeps) {
    if (pattern.test(sourceBlob)) {
      manifest = upsertPackageDependency(manifest, dependencyName, version)
    }
  }

  for (const packageName of collectBarePackageImports(sourceBlob)) {
    if (packageName === 'vite') {
      manifest = movePackageToDevDependency(manifest, 'vite', SAFE_VITE_VERSION)
      continue
    }
    if (packageName === '@vitejs/plugin-react') {
      manifest = movePackageToDevDependency(manifest, '@vitejs/plugin-react', SAFE_VITE_REACT_PLUGIN_VERSION)
      manifest = movePackageToDevDependency(manifest, 'vite', SAFE_VITE_VERSION)
      continue
    }
    const version = COMMON_PACKAGE_IMPORT_VERSIONS[packageName]
    if (version) {
      manifest = upsertPackageDependency(manifest, packageName, version)
    }
    if (packageName === '@monaco-editor/react') {
      manifest = upsertPackageDependency(manifest, 'monaco-editor', COMMON_PACKAGE_IMPORT_VERSIONS['monaco-editor'])
    }
  }

  const nextContent = `${JSON.stringify(manifest, null, 2)}\n`
  if (nextContent === packageFile.content) return files

  return files.map((file, index) => (index === packageIndex ? { ...file, content: nextContent } : file))
}

function sanitizeGeneratedFiles(files: CodeFile[]) {
  const sanitized = files.map((file) => ({
    ...file,
    content: sanitizeGeneratedFileContent(file.name, file.content),
  }))
  return repairPackageManifestFromSourceImports(sanitized)
}

export function normalizeGeneratedCodeFilesForTest(files: CodeFile[]) {
  return sanitizeGeneratedFiles(files)
}

function detectLanguage(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const map: Record<string, string> = {
    c: 'c', cc: 'cpp', cpp: 'cpp', cs: 'csharp', css: 'css', dart: 'dart',
    ex: 'elixir', go: 'go', h: 'c', hpp: 'cpp', hs: 'haskell', html: 'html',
    java: 'java', js: 'javascript', json: 'json', jsx: 'javascript', kt: 'kotlin',
    lua: 'lua', md: 'markdown', mjs: 'javascript', php: 'php', py: 'python',
    r: 'r', rb: 'ruby', rs: 'rust', scala: 'scala', scss: 'scss', sh: 'bash',
    sql: 'sql', swift: 'swift', svelte: 'svelte', toml: 'toml', ts: 'typescript',
    tsx: 'typescript', txt: 'text', vue: 'vue', xml: 'xml', yaml: 'yaml',
    yml: 'yaml', zig: 'zig', dockerfile: 'dockerfile',
  }
  return map[ext] || 'text'
}

/**
 * Detect the actual programming language from content patterns.
 * Used when the LLM tags a code block as "markdown" or "text" but
 * the content is actually HTML/CSS/JS/Python/etc.
 */
function detectContentLanguage(content: string): string | null {
  const trimmed = content.slice(0, 500)

  // HTML detection
  if (/<!DOCTYPE\s+html/i.test(trimmed) || /<html[\s>]/i.test(trimmed) || /<head[\s>]/i.test(trimmed)) {
    return 'html'
  }

  // CSS detection
  if (/^[\s]*[.#@][\w-]+\s*\{/m.test(trimmed) || /:\s*(flex|grid|block|none|auto|inherit);/i.test(trimmed)) {
    return 'css'
  }

  // JavaScript/TypeScript detection
  if (/^(import|export|const|let|var|function|class|async)\s/m.test(trimmed)) {
    if (/:\s*(string|number|boolean|void|any|Promise<)/m.test(trimmed)) {
      return 'typescript'
    }
    return 'javascript'
  }

  // Python detection
  if (/^(def |class |import |from .+ import |if __name__)/m.test(trimmed)) {
    return 'python'
  }

  // JSON detection
  if (/^\s*\{[\s\S]*"[\w]+"\s*:/m.test(trimmed)) {
    return 'json'
  }

  // Rust detection
  if (/^(use |fn |pub |mod |struct |impl |enum )/m.test(trimmed)) {
    return 'rust'
  }

  // Go detection
  if (/^package\s+\w+/m.test(trimmed) || /^func\s+/m.test(trimmed)) {
    return 'go'
  }

  return null
}

/**
 * Try to infer a meaningful file name from the content.
 * Falls back to bloc-N.ext if no pattern matches.
 */
function inferFileName(content: string, ext: string, index: number): string {
  const trimmed = content.slice(0, 300)

  // HTML with a title → use a meaningful name
  if (ext === 'html') return index === 1 ? 'index.html' : `page-${index}.html`
  if (ext === 'css') return index === 1 ? 'style.css' : `style-${index}.css`

  // JS with common patterns
  if (ext === 'js' || ext === 'ts') {
    if (/addEventListener.*DOMContentLoaded/i.test(trimmed) || /document\.(getElementById|querySelector)/i.test(trimmed)) {
      return index === 1 ? 'script.js' : `script-${index}.js`
    }
    if (/express\(\)|createServer|app\.listen/i.test(trimmed)) return 'server.js'
    if (/export default function|export default class/i.test(trimmed)) return `component-${index}.${ext}`
    return index === 1 ? `main.${ext}` : `module-${index}.${ext}`
  }

  // Python
  if (ext === 'py') {
    if (/FastAPI|Flask|Django/i.test(trimmed)) return 'app.py'
    if (/if __name__/i.test(trimmed)) return 'main.py'
    return index === 1 ? `main.py` : `module_${index}.py`
  }

  // JSON — likely package.json or config
  if (ext === 'json') {
    if (/"name"\s*:/.test(trimmed) && /"version"\s*:/.test(trimmed)) return 'package.json'
    if (/"compilerOptions"/i.test(trimmed)) return 'tsconfig.json'
    return `config-${index}.json`
  }

  return `bloc-${index}.${ext}`
}

function langToExt(language: string) {
  const map: Record<string, string> = {
    bash: 'sh', c: 'c', cpp: 'cpp', csharp: 'cs', css: 'css', dart: 'dart',
    dockerfile: 'Dockerfile', elixir: 'ex', go: 'go', haskell: 'hs', html: 'html',
    java: 'java', javascript: 'js', json: 'json', kotlin: 'kt', lua: 'lua',
    markdown: 'md', php: 'php', python: 'py', r: 'r', ruby: 'rb', rust: 'rs',
    scala: 'scala', scss: 'scss', sql: 'sql', svelte: 'svelte', swift: 'swift',
    text: 'txt', toml: 'toml', typescript: 'ts', vue: 'vue', xml: 'xml',
    yaml: 'yml', zig: 'zig',
  }
  return map[language.toLowerCase()] || language.toLowerCase()
}

export function serializeCodeFiles(files: CodeFile[]) {
  return files.map((f) => [
    `--- FICHIER: ${f.name} ---`,
    `\`\`\`${f.language}`,
    f.content,
    '```',
  ].join('\n')).join('\n\n')
}

export function extractNotes(content: string) {
  const parts = content.split(/---\s*NOTES\s*---/i)
  return parts.length < 2 ? '' : parts.slice(1).join('\n').trim()
}

function clipText(text: string, maxLength = 2400) {
  const normalized = text.trim()
  return normalized.length <= maxLength
    ? normalized
    : `${normalized.slice(0, maxLength)}\n...[sortie tronquee]`
}

const NON_CODE_PLANNING_PATTERNS = [
  /(^|\n)\s*Projet detecte\b/i,
  /(^|\n)\s*Type:\s*/i,
  /(^|\n)\s*Complexite:\s*/i,
  /(^|\n)\s*Frameworks?:\s*/i,
  /(^|\n)\s*Features?:\s*/i,
  /(^|\n)\s*Stack:\s*/i,
  /(^|\n)\s*Dev server:\s*/i,
  /(^|\n)\s*Preflight local\b/i,
  /(^|\n)\s*Contraintes locales:\s*/i,
  /(^|\n)\s*A inspecter d abord:\s*/i,
]

function detectNonCodePlanningNarrative(content: string) {
  const trimmed = stripFormattingArtifacts(content)
  if (!trimmed) return null
  if (/---\s*(?:FICHIER|FILE):\s*/i.test(trimmed)) return null
  if (/```[\w.+-]+\s*\r?\n[\s\S]*?```/i.test(trimmed)) return null
  if (isLLMRefusal(trimmed)) return null
  if (detectContentLanguage(trimmed)) return null

  const matchCount = NON_CODE_PLANNING_PATTERNS.filter((pattern) => pattern.test(trimmed)).length
  if (matchCount < 2) return null

  return 'La sortie est un diagnostic, un preflight ou un plan narratif au lieu de vrais fichiers de code.'
}

function buildEmptyGenerationDiagnostic(content: string, intent: CodeIntent, outputRetryCount: number) {
  const trimmed = content.trim()

  if (!trimmed) {
    return [
      `Le modele n a retourne aucun contenu exploitable pour le projet ${intent.projectType}.`,
      `Tentatives de regeneration effectuees: ${outputRetryCount}.`,
    ].join(' ')
  }

  if (isLLMRefusal(trimmed)) {
    return [
      'Le modele a repondu par un refus ou une excuse au lieu de livrer des fichiers de code.',
      `Apercu: ${clipText(trimmed, 500)}`,
    ].join(' ')
  }

  const planningIssue = detectNonCodePlanningNarrative(trimmed)
  if (planningIssue) {
    return [
      'Le modele est reste bloque en mode analyse/preflight au lieu de livrer des fichiers executables.',
      planningIssue,
      `Apercu brut: ${clipText(trimmed, 700)}`,
    ].join(' ')
  }

  return [
    'Le modele a bien produit du texte, mais pas dans un format de fichiers parseable par Aurora.',
    'Le contrat de sortie a donc ete juge invalide.',
    `Apercu brut: ${clipText(trimmed, 700)}`,
  ].join(' ')
}

function getModelShortName(model: string) {
  const tail = model.split('/').pop() || model
  return tail.split(':')[0]
}

function detectEnvironmentBlocker(
  sandboxResult: CodeSandboxResult,
  errorCategories: ErrorCategory[],
): string | null {
  if (sandboxResult.ok) return null

  if (errorCategories.includes('runtime_unavailable')) {
    const autoInstallFailure = sandboxResult.steps.find((step) => step.command.startsWith('auto-install:') && !step.ok)
    if (autoInstallFailure) {
      return `${autoInstallFailure.command.replace('auto-install:', '')} n a pas pu etre prepare automatiquement`
    }

    const missingCommand = sandboxResult.steps
      .filter((step) => !step.ok)
      .map((step) => step.output.match(/Failed to spawn command\s+([^\s:]+)/i)?.[1])
      .find(Boolean)

    if (missingCommand) {
      return `commande ${missingCommand} absente du poste local`
    }

    return 'runtime ou toolchain absente'
  }

  if (/reste indisponible apres preparation automatique/i.test(sandboxResult.summary)) {
    return sandboxResult.summary
  }

  return null
}

function isArchitecturePlanUsable(plan: string | null) {
  if (!plan) return false

  const sectionHits = [
    /###\s*comprehension/i.test(plan),
    /###\s*stack/i.test(plan),
    /###\s*fichiers a generer/i.test(plan),
    /###\s*commandes/i.test(plan) || /###\s*commandes d installation/i.test(plan),
  ].filter(Boolean).length
  const listedFiles = (plan.match(/`[^`\n]+\.[a-z0-9]+`/gi) || []).length

  return sectionHits >= 2 && listedFiles >= 2 && plan.trim().length > 180
}

// ---------------------------------------------------------------------------
// Pipeline phases
// ---------------------------------------------------------------------------

/** Phase 1: Classify intent (deterministic, no LLM) */
function runIntentPhase(
  prompt: string,
  setPhase: PhaseCallback,
  context?: CodeIntentContext,
): CodeIntent {
  setPhase('Classification du projet...', 5)
  return classifyCodeIntent(prompt, context)
}

/** Phase 1.5: Local preflight — inspect machine, workspace and current project before coding */
async function runPreflightPhase(
  prompt: string,
  intent: CodeIntent,
  existingFiles: CodeFile[],
  configuredCodeModel: string,
  setPhase: PhaseCallback,
): Promise<CodePreflightReport | null> {
  try {
    setPhase('Preflight local: analyse machine, outils et fichiers existants...', 8)
    return await withTimeout(runCodePreflight({
      prompt,
      intent,
      existingFiles,
      model: selectModel('planning', intent, 0, configuredCodeModel),
      setPhase: (detail, progress) => setPhase(detail, Math.max(8, Math.min(18, progress))),
    }), {
      label: 'Code preflight',
      timeoutMs: PREFLIGHT_PHASE_TIMEOUT_MS,
    })
  } catch (error) {
    setPhase('Preflight local indisponible — poursuite avec les informations connues...', 12)
    return null
  }
}

/** Phase 2: Deep reasoning + architecture planning (LLM — ALWAYS runs) */
async function runPlanningPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onRecovery?: (event: RecoveryEvent) => void,
): Promise<string | null> {
  const model = selectModel('planning', intent, 0, configuredCodeModel)
  setPhase(`Architecte en reflexion (${getModelShortName(model)})...`, 10)
  // Injecter le system prompt ARCHITECTE dans le prompt
  const planPrompt = [
    buildArchitecteSystemPrompt(intent),
    '',
    '---',
    '',
    buildArchitecturePlanningPrompt(prompt, intent),
    preflightReport
      ? [
          '### PREFLIGHT LOCAL OBLIGATOIRE',
          'Le plan doit s appuyer sur ce diagnostic local avant toute decision de stack ou de configuration.',
          serializeCodePreflightReport(preflightReport),
        ].join('\n')
      : '',
  ].filter(Boolean).join('\n\n')

  // Le planning a un vrai budget pour les apps complexes. Si le modele echoue
  // malgre tout, les contrats deterministes prennent le relais.
  try {
    const response = await resilientOllamaGenerate(model, planPrompt, {
      timeoutMs: PLANNING_TIMEOUT_MS,
      firstByteTimeoutMs: PLANNING_FIRST_BYTE_TIMEOUT_MS,
      // v85c : architecte prompt is several thousand tokens; 8192 holds it
      // without risking the VRAM OOM that 16384 flirted with on a 16 GB card.
      num_ctx: CODE_PLANNING_CONTEXT_TOKENS,
      neverMemorySkip: true, // v85c : never refuse to plan on transient RAM pressure
      onRecoveryAttempt: (ev) => {
        // Ne log que les events critiques, pas les retries normaux
        if (ev.action !== 'retry') {
          setPhase(`Architecte — ${ev.action}...`, 16)
          onRecovery?.(ev)
        }
      },
    })
    const plan = response?.response?.trim()
    if (plan && isArchitecturePlanUsable(plan)) {
      setPhase('Plan d architecture pret — lancement de la generation...', 25)
      return plan
    }
    if (plan?.length) {
      setPhase('Plan insuffisant — le Codeur operera en autonomie...', 22)
    }
    return null
  } catch (planError) {
    // Planning echoue — ce n'est PAS un echec critique, le Codeur peut operer seul
    const msg = planError instanceof Error ? planError.message : String(planError)
    console.warn('[CodeOrchestrator] Planning skipped:', msg)
    setPhase('Architecte indisponible — generation directe par le Codeur...', 25)
    return null
  }
}

/** Context forwarded to the Codeur when the orchestrator has resolved a pivot. */
export type GenerationPivotContext = {
  kind: FollowUpKind
  migrationSummary: string | null
}

/** Phase 3: Code generation (streaming) */
async function runGenerationPhase(
  prompt: string,
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  architecturePlan: string | null,
  missionDossier: CodeMissionDossier | null,
  conversationHistory: OllamaMessage[],
  existingFiles: CodeFile[],
  contextImages: string[],
  configuredCodeModel: string,
  escalationLevel: number,
  setPhase: PhaseCallback,
  onToken: (token: string) => void,
  onRecovery?: (event: RecoveryEvent) => void,
  signal?: AbortSignal,
  pivotContext?: GenerationPivotContext,
): Promise<string> {
  setPhase('Generation du code en direct...', 35)
  const model = selectModel('generation', intent, escalationLevel, configuredCodeModel)

  // System prompt CODEUR pour la phase de generation.
  // v68: passer le prompt au builder pour activer la variante starter la plus
  // pertinente (saas/portfolio/ecommerce/dashboard/landing) detectee depuis
  // les mots-cles du prompt user.
  const messages: OllamaMessage[] = [
    { role: 'system', content: buildCodeurSystemPrompt(intent, prompt) },
  ]

  if (preflightReport) {
    messages.push({
      role: 'system',
      content: [
        '## PREFLIGHT LOCAL DU MODULE CODE',
        '',
        serializeCodePreflightReport(preflightReport),
        '',
        'Tu dois t appuyer sur ce preflight avant de fixer les versions, la stack, les scripts et les fichiers de configuration.',
        'Ne code jamais a l aveugle si le preflight indique quoi inspecter ou reutiliser.',
      ].join('\n'),
    })
  }

  // Add architecture plan as detailed implementation guide (capped to protect context window)
  if (architecturePlan) {
    // v85c : 12000 -> 7000. On a 16 GB / 16384-ctx budget the plan competes
    // with the system prompt + existing files for input room; 7000 chars
    // (~1750 tokens) is enough to guide generation without starving output.
    const cappedPlan = architecturePlan.length > 7000
      ? `${architecturePlan.slice(0, 7000)}\n...[plan tronque]`
      : architecturePlan
    messages.push({
      role: 'system',
      content: [
        '## PLAN D IMPLEMENTATION DETAILLE (cree par l architecte — SUIS-LE STRICTEMENT)',
        '',
        cappedPlan,
        '',
        'INSTRUCTIONS:',
        '- Genere TOUS les fichiers listes dans le plan, dans l ordre indique',
        '- Respecte les dependances et versions specifiees',
        '- Inclus un fichier README.md avec les commandes d installation et de lancement',
        '- Le design DOIT correspondre aux specs UX du plan',
        '- Chaque fichier doit etre COMPLET et fonctionnel',
      ].join('\n'),
    })
  } else {
    // No plan available — add minimal README instruction
    messages.push({
      role: 'system',
      content: [
        'INSTRUCTION SUPPLEMENTAIRE:',
        '- Genere un fichier README.md qui explique comment installer et lancer le projet',
        '- Le README doit contenir: description, pre-requis, installation, lancement, structure du projet',
      ].join('\n'),
    })
  }

  if (missionDossier) {
    messages.push({
      role: 'system',
      content: [
        '## DOSSIER EXECUTIF DU MODULE CODE',
        '',
        serializeCodeMissionDossier(missionDossier),
        '',
        'Respecte ce dossier avant toute optimisation locale ou toute improvisation.',
      ].join('\n'),
    })
  }

  // Add conversation history (capped to avoid context overflow)
  const recentHistory = conversationHistory.length > 8
    ? conversationHistory.slice(-8)
    : conversationHistory
  messages.push(...recentHistory)

  // Pivot-aware context: when the user asked for a platform pivot we do NOT
  // show the old code (that is exactly what made the model keep generating
  // HTML when the user asked for Python). Instead we inject a MIGRATION
  // block describing the business concept to carry over, and leave the
  // Codeur free to produce the new stack from scratch.
  if (pivotContext && pivotContext.kind === 'pivot_platform') {
    messages.push({
      role: 'user',
      content: [
        '## MIGRATION DE PROJET — PIVOT DE STACK DEMANDE',
        'L utilisateur a demande de REFAIRE LE MEME CONCEPT sur une autre stack / un autre langage.',
        'Ne reutilise PAS la stack precedente. Reimplemente le concept AU PROPRE, idiomatique, dans la nouvelle stack.',
        pivotContext.migrationSummary
          ? `\n### Concept metier a conserver\n${pivotContext.migrationSummary}`
          : '',
        '',
        '### REGLES',
        '- Genere un projet neuf, complet, idiomatique dans la nouvelle stack.',
        '- NE PRODUIS PAS de fichiers HTML/CSS/JS si la nouvelle stack est Python / Go / Rust / Java / etc.',
        '- NE PRODUIS PAS de fichier Python si la nouvelle stack est web pure. Suis RIGOUREUSEMENT le projet detecte.',
        '- Respecte le format de sortie `--- FICHIER: chemin ---` pour chaque fichier complet.',
        '- Inclure un README.md decrivant comment installer et lancer le nouveau projet.',
      ].filter(Boolean).join('\n'),
    })
  } else if (existingFiles.length > 0) {
    // Classic follow-up (increment / pivot_feature / no pivot): we show the
    // existing files so the Codeur patches them surgically.
    // v85c : budget-based inclusion. The old fixed 4000-char/file cap meant a
    // real project (a 12k-char index.html) was only shown up to char 4000 —
    // so the model "preserved" by REGENERATING a leaner file (a live test
    // showed index.html shrink 17.5k -> 10.7k on a simple modification). We
    // show each file in full until a ~13000-char pool is exhausted — enough to
    // show typical files verbatim (so modifications preserve them) while
    // keeping the follow-up prompt within the 12288 generation window so the
    // output still has room. Overflow files are truncated with a keep-note.
    let fileBudget = 13000
    const fileBlocks: string[] = []
    let shownCount = 0
    for (const f of existingFiles) {
      if (fileBudget <= 400) break
      const perCap = Math.min(f.content.length, Math.max(2000, fileBudget))
      const body = f.content.length > perCap
        ? `${f.content.slice(0, perCap)}\n...[fichier tronque: ${f.content.length} chars — le reste est conserve, NE le supprime pas]`
        : f.content
      fileBlocks.push(`--- FICHIER: ${f.name} ---\n\`\`\`${f.language}\n${body}\n\`\`\``)
      fileBudget -= body.length
      shownCount += 1
    }
    const omitted = existingFiles.length - shownCount
    messages.push({
      role: 'user',
      content: [
        '## CONTEXTE DU PROJET EXISTANT (tu es en mode "suite de conversation")',
        'Ce projet a deja ete genere. La nouvelle instruction utilisateur est une modification / ajout / retrait, PAS une demande de reconstruction.',
        pivotContext?.kind === 'pivot_feature'
          ? 'Mode: evolution majeure d une feature existante. Garde la meme stack, mais autorise des reecritures consequentes des fichiers concernes.'
          : '',
        '',
        '### REGLES DE MODIFICATION',
        '- Analyse l intention: ajout (nouvelle section/feature), retrait (section a enlever), changement (couleur/texte/comportement), refactor (structure interne).',
        '- Ne touche QUE ce qui est demande. Ne refactore rien qui fonctionne deja. Ne regenere pas les fichiers inchanges.',
        '- REGLE: quand tu retournes un fichier modifie, REPRENDS tout son contenu d origine et n applique QUE le changement demande. Ne resume pas, ne supprime aucune section existante qui n est pas explicitement visee par la demande.',
        '- Pour CHAQUE fichier que tu RETOURNES, il doit etre COMPLET (pas de diff, pas de ...).',
        '- Si un fichier ne change pas, NE le retourne PAS — il sera conserve automatiquement.',
        '- Si un fichier est renomme, fais-le proprement (retourner l ancien fichier vide n a aucun effet, retourner le nouveau nom suffit — l orchestrateur gere le delta).',
        '- Conserve imperativement: palette, typographie, structure globale, conventions de nommage, style des animations, ET tout le contenu existant non vise par la demande.',
        '- Si la modification demande une section ou un asset qui n existe pas encore, cree-le en respectant le style deja etabli (meme font, meme vocabulaire d animations, meme espacement).',
        '',
        '### FICHIERS DEJA EN PLACE (a reprendre INTEGRALEMENT quand tu les modifies):',
        ...fileBlocks,
        omitted > 0
          ? `...et ${omitted} autre(s) fichier(s) non montre(s) ici — ils restent en place, NE les supprime pas.`
          : '',
        'IMPORTANT: Chaque fichier que tu retournes doit etre COMPLET et reprendre tout l existant + la modification. Les fichiers non retournes sont conserves intacts.',
        'IMPORTANT: Tu es en mode SUITE, pas en mode creation from scratch — reutilise ce qui est deja construit.',
      ].filter(Boolean).join('\n\n'),
    })
  }

  // Add user prompt
  // v62: pour les projets visuels, on prefixe le user prompt avec un rappel
  // EXPLICITE du design contract afin que le LLM ne l ecrase pas avec ses
  // habitudes "tutoriel". Le system prompt contient deja le contract complet
  // mais les LLMs locaux (qwen3-coder, llama4:scout) tendent a se concentrer
  // sur la derniere consigne — donc on remet le coup de marteau juste avant
  // la demande effective.
  const designReminder = isVisualProjectType(intent.projectType)
    ? [
        '',
        '═══════════════════════════════════════════════════════════════',
        'RAPPEL DESIGN POUSSE — NON NEGOCIABLE',
        '═══════════════════════════════════════════════════════════════',
        '- Hero full-height (min-height:100vh) avec headline clamp(2.8rem, 6vw, 5.5rem) bold + visuel a droite (SVG inline / canvas / mesh gradient).',
        '- Mesh gradient en arriere-plan hero (2-3 blobs filter:blur(120px) absolute, animes via @keyframes).',
        '- Police Google Fonts premium (Inter / Manrope / Satoshi / DM Sans / Space Grotesk / Plus Jakarta) avec preconnect.',
        '- 7+ sections distinctes: nav fixed (backdrop-blur au scroll), hero, features grid 3 cols, showcase/gallery, testimonials/numbers, CTA final, footer 4 cols.',
        '- 7+ micro-interactions parmi: scroll reveal IntersectionObserver, nav qui change au scroll, parallax hero, hover cards (scale 1.02 + zoom image + overlay), counters anime, magnetic buttons, blob mousemove, stagger fade-in, gradient mesh anime, marquee carousel.',
        '- Mode sombre/clair avec data-theme + localStorage + prefers-color-scheme.',
        '- CSS variables completes (--color-*, --space-*, --radius-*, --shadow-*, --duration-*, --ease-*).',
        '- Glassmorphism (backdrop-filter:blur 14px) et shadows composites multi-layer.',
        '',
        'INTERDICTIONS qui declenchent un REJET et regeneration:',
        '- <h1>Bienvenue</h1> sans style. background:blue uni. boutons sans radius/transition.',
        '- font-family Arial/Times/sans-serif default.',
        '- table comme layout. zero animation. <img> casse.',
        '═══════════════════════════════════════════════════════════════',
        '',
        'DEMANDE UTILISATEUR (a traiter avec design pousse):',
      ].join('\n')
    : ''
  // Anti-skeleton clause. With a plan + dossier in context, local models can
  // emit a SKELETON that just mirrors the plan headings
  // (the live test dropped from ~13k chars solo to ~3.8k in the pipeline). This
  // forces complete, fleshed-out code for every file/section.
  const completenessDirective = [
    '═══════════════════════════════════════════════════════════════',
    'COMPLÉTUDE — NON NÉGOCIABLE',
    '- Génère le code COMPLET et INTÉGRAL de CHAQUE fichier. Pas de squelette,',
    '  pas de résumé du plan, pas de commentaire "<!-- section ici -->" ou "// à compléter".',
    '- CHAQUE section/fonctionnalité demandée est ENTIÈREMENT implémentée : vrai',
    '  contenu (textes réels, pas "lorem"), styles complets, et le JS qui la fait fonctionner.',
    '- Toute interactivité demandée (toggle, accordéon, onglets, carrousel, panier…)',
    '  DOIT avoir son JavaScript complet et fonctionnel (addEventListener, handlers).',
    '- Si tu références un fichier local (style.css, script.js), tu DOIS le générer aussi,',
    '  COMPLET. Ne laisse jamais un <link>/<script> pointer vers un fichier absent.',
    '- Si tu utilises des classes utilitaires Tailwind, inclus <script src="https://cdn.tailwindcss.com"></script>',
    '  dans le <head> ; sinon écris du vrai CSS qui style réellement la page (jamais d\'écran nu).',
    '- Vise un résultat RICHE : pour une page/app complète, plusieurs centaines de lignes.',
    '═══════════════════════════════════════════════════════════════',
    '',
  ].join('\n')
  const userMessage: OllamaMessage = {
    role: 'user',
    content: `${completenessDirective}${designReminder ? `${designReminder}\n` : ''}${prompt}`,
  }
  if (contextImages.length > 0) {
    userMessage.images = contextImages
  }
  messages.push(userMessage)

  // Use array chunks instead of string concatenation to avoid O(n²) memory usage
  // String concatenation creates a new string for every token → can crash on large outputs
  const contentChunks: string[] = []
  const generationSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)])
    : AbortSignal.timeout(STREAM_GENERATION_TOTAL_TIMEOUT_MS)
  try {
  // v85c : explicit context + output budget, TUNED FOR 16 GB VRAM. The old
  // code passed nothing → Ollama's ~4096 default truncated the stacked CODEUR
  // prompt + plan + existing files, giving simplistic, cut-off projects. The
  // first oversized attempt went too far and OOM'd on the SECOND
  // pipeline run (VRAM tighter) → the resilience layer learned a high memory
  // floor → memory_guard then skipped the model on every retry (storm). 12288
  // expert context starts high and is reduced by resilience if memory is tight.
  // headroom, so it never OOMs → no learned-floor cascade. Big projects are
  // built iteratively across turns, not crammed into one window. Resilience
  // still degrades to 4096/2048 on any OOM and shrinks num_predict with it.
  await resilientOllamaChatStream(
    model,
    messages,
    (token) => {
      contentChunks.push(token)
      onToken(token)
    },
    () => { /* done — resolved by the promise wrapper inside resilient */ },
    {
      signal: generationSignal,
      // Preset officiel Qwen3-Coder (temp 0.7 / top_p 0.8 / top_k 20 / repeat 1.05),
      // abaisse a 0.3 pour du code plus deterministe sans etrangler l'echantillonnage.
      // NB: l'ancien top_p 0.1 etait a la fois trop etroit (boucles de repetition sur
      // un MoE) ET jamais transmis par la couche de resilience — donc sans effet.
      temperature: 0.3,
      top_p: 0.8,
      top_k: 20,
      repeat_penalty: 1.05,
      // Large enough for the system prompt + plan + existing files + a real
      // multi-file output; resilience reduces it if the local runtime OOMs.
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      num_predict: CODE_EXPERT_OUTPUT_TOKENS,
      firstByteTimeoutMs: GENERATION_FIRST_BYTE_TIMEOUT_MS,
      neverMemorySkip: true, // v85c : the routed code model must always run
      onRecoveryAttempt: (ev) => {
        setPhase(`Generation — auto-reparation: ${ev.action}...`, 38)
        onRecovery?.(ev)
      },
    },
  )
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === 'AbortError' && !signal?.aborted
    if (timedOut) {
      setPhase('Generation time-boxee — poursuite avec le draft partiel...', 44)
      const partialContent = contentChunks.join('')
      // Detect truncation: if the last file section has an unclosed code block, it was cut mid-generation
      const lastFileMarker = partialContent.lastIndexOf('--- FICHIER:')
      if (lastFileMarker > 0) {
        const afterMarker = partialContent.slice(lastFileMarker)
        const openBlocks = (afterMarker.match(/```\w+/g) || []).length
        const closeBlocks = (afterMarker.match(/\n```\s*$/gm) || []).length
        if (openBlocks > closeBlocks) {
          // Truncated file — close it so at least the complete files are parseable
          return partialContent + '\n```\n'
        }
      }
      return partialContent
    }
    throw error
  }

  return contentChunks.join('')
}

/** Calculate a granular score from sandbox results AND content quality */
function computeSandboxScore(sandboxResult: CodeSandboxResult, files: CodeFile[], intent: CodeIntent): number {
  // Content quality gate — if the content itself is garbage, sandbox pass is irrelevant
  const contentScore = computeContentQualityScore(files, intent)
  if (contentScore === 0) return 0   // Refusal or empty → 0% no matter what
  if (contentScore <= 10) return contentScore // Generic/docs-only → cap at 10%

  if (sandboxResult.ok) {
    // Sandbox passed, but cap by content quality
    return Math.min(100, contentScore)
  }

  const totalSteps = sandboxResult.steps.length
  if (totalSteps === 0) return Math.min(contentScore, 50)
  const passingSteps = sandboxResult.steps.filter((s) => s.ok).length
  // Base score from passing ratio (0-80 range)
  const passRatio = passingSteps / totalSteps
  const baseScore = Math.round(passRatio * 80)
  // Bonus points for partial success indicators in failing steps
  const failingOutputs = sandboxResult.steps.filter((s) => !s.ok).map((s) => s.output).join('\n')
  let bonus = 0
  if (/warning/i.test(failingOutputs) && !/error/i.test(failingOutputs)) bonus += 10
  if (/compiled/i.test(failingOutputs) || /built/i.test(failingOutputs)) bonus += 5
  return Math.min(99, baseScore + bonus)
}

function isStaticCritiqueBlocking(report: CritiqueReport): boolean {
  if (report.hasBlocker) return true
  if (report.issues.some((issue) => issue.severity === 'error')) return true
  if (report.scores.compile < 1) return true
  if (report.scores.security < 0.85) return true
  if (report.scores.lint < 0.65) return true
  return false
}

function formatStaticCritiqueReport(report: CritiqueReport): string {
  const scoreLine = [
    `overall=${Math.round(report.overallScore * 100)}%`,
    `compile=${Math.round(report.scores.compile * 100)}%`,
    `lint=${Math.round(report.scores.lint * 100)}%`,
    `security=${Math.round(report.scores.security * 100)}%`,
    `accessibility=${Math.round(report.scores.accessibility * 100)}%`,
  ].join(' | ')

  const issues = report.issues.slice(0, 20).map((issue) => {
    const where = issue.location
      ? `${issue.location.file}${issue.location.line ? `:${issue.location.line}` : ''}`
      : 'projet'
    const suggestion = issue.suggestion ? ` Suggestion: ${issue.suggestion}` : ''
    return `[${issue.severity}] ${where} - ${issue.message}.${suggestion}`
  })

  return [
    scoreLine,
    report.hasBlocker ? 'blocker=true' : 'blocker=false',
    issues.length > 0 ? issues.join('\n') : 'Aucun probleme statique bloquant detecte.',
  ].join('\n')
}

function withStaticCritiqueStep(
  sandboxResult: CodeSandboxResult,
  report: CritiqueReport,
): CodeSandboxResult {
  const blocking = isStaticCritiqueBlocking(report)
  const output = formatStaticCritiqueReport(report)
  const staticStep: CodeSandboxStepResult = {
    label: 'Critique statique Aurora',
    command: 'internal:static-critique',
    ok: !blocking,
    output,
  }

  if (!blocking) {
    return {
      ...sandboxResult,
      steps: [...sandboxResult.steps, staticStep],
    }
  }

  const staticSummary = 'La critique statique a detecte des erreurs de syntaxe, structure, securite ou complexite.'
  return {
    ...sandboxResult,
    ok: false,
    summary: sandboxResult.ok
      ? staticSummary
      : `${sandboxResult.summary}\n${staticSummary}`,
    steps: [...sandboxResult.steps, staticStep],
  }
}

/** Phase 4 + 5: Validation + Auto-correction loop */
async function runValidationAndCorrectionLoop(
  prompt: string,
  initialFiles: CodeFile[],
  intent: CodeIntent,
  preflightReport: CodePreflightReport | null,
  missionDossier: CodeMissionDossier,
  architecturePlan: string | null,
  configuredCodeModel: string,
  setPhase: PhaseCallback,
  onFilesUpdate: (files: CodeFile[], notes: string) => void,
  onValidationUpdate: (result: CodeSandboxResult) => void,
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void,
  signal?: AbortSignal,
): Promise<{
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  correctionLog: CorrectionPass[]
  totalAttempts: number
  finalScore: number
}> {
  let currentFiles = initialFiles
  let currentNotes = ''
  let sandboxResult: CodeSandboxResult | null = null
  const correctionLog: CorrectionPass[] = []
  let attempt = 0
  let lastScore = 0
  let rescueRegenerationUsed = false

  while (true) {
    attempt += 1

    // Check abort
    if (signal?.aborted) break

    // Validate in sandbox
    setPhase(`Sandbox passe ${attempt} — validation en cours...`, Math.min(85, 60 + attempt * 4))
    sandboxResult = await runCodeSandboxValidation({
      files: currentFiles,
      prompt,
      setPhase,
      setProgress: (detail) => setPhase(detail, Math.min(90, 65 + attempt * 4)),
    })

    if (sandboxResult.normalizedFiles && sandboxResult.normalizedFiles.length > 0) {
      const normalizedChanged = sandboxResult.normalizedFiles.length !== currentFiles.length
        || sandboxResult.normalizedFiles.some((file, index) =>
          file.name !== currentFiles[index]?.name || file.content !== currentFiles[index]?.content,
        )
      if (normalizedChanged) {
        currentFiles = sandboxResult.normalizedFiles
        onFilesUpdate(currentFiles, currentNotes)
      }
    }

    setPhase(`Sandbox passe ${attempt} - critique statique du code...`, Math.min(90, 66 + attempt * 4))
    const staticReport = await compositeStaticCritic({
      generationId: `validation-${attempt}`,
      files: currentFiles,
    }, intent)
    sandboxResult = withStaticCritiqueStep(sandboxResult, staticReport)

    const interactive3D = checkInteractive3DFidelity(currentFiles, prompt, intent)
    if (!interactive3D.ok && attempt <= INTERACTIVE_3D_FIDELITY_MAX_PASSES) {
      const fidelitySummary = 'La fidelite 3D interactive demandee est incomplete.'
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? fidelitySummary
          : `${sandboxResult.summary}\n${fidelitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Fidelite 3D interactive',
            command: 'interactive-3d-fidelity-gate',
            ok: false,
            output: interactive3D.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - fidelite 3D incomplete (${interactive3D.missing.join(', ')})...`,
        Math.min(90, 68 + attempt * 4),
      )
    }

    // Deterministic visual gates: a sandbox can say "ok" while a web page is a
    // non-functional shell or a game has no input/game loop. These gates must
    // run before score/strategy calculation so the correction pass can fix them.
    const gamePlay =
      intent.projectType === 'game_web'
        ? checkGamePlayability(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!gamePlay.ok) {
      const playabilitySummary = `Jeu incomplet: ${gamePlay.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? playabilitySummary
          : `${sandboxResult.summary}\n${playabilitySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Jouabilité',
            command: 'playability-gate',
            ok: false,
            output: gamePlay.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - jeu incomplet (${gamePlay.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    const webIntegrity =
      intent.projectType === 'static_web'
        ? checkWebPageIntegrity(currentFiles, prompt)
        : { ok: true, missing: [] as string[], hint: '' }
    if (!webIntegrity.ok) {
      const integritySummary = `Page non fonctionnelle: ${webIntegrity.missing.join(', ')}.`
      sandboxResult = {
        ...sandboxResult,
        ok: false,
        summary: sandboxResult.ok
          ? integritySummary
          : `${sandboxResult.summary}\n${integritySummary}`,
        steps: [
          ...sandboxResult.steps,
          {
            label: 'Intégrité page',
            command: 'web-integrity-gate',
            ok: false,
            output: webIntegrity.hint,
          },
        ],
      }
      setPhase(
        `Passe ${attempt} - page non fonctionnelle (${webIntegrity.missing.join(', ')}) - correction ciblee...`,
        Math.min(90, 70 + attempt * 4),
      )
    }

    onValidationUpdate(sandboxResult)

    // Calculate score using granular formula + content quality gate
    const currentScore = computeSandboxScore(sandboxResult, currentFiles, intent)

    const errorCategories = sandboxResult.ok ? [] : classifyErrors(sandboxResult)
    const strategy = sandboxResult.ok
      ? null
      : buildCorrectionStrategy(errorCategories, attempt, correctionLog)

    // Trim agressif : on garde max 1.5KB par erreur pour la passe courante
    // (la passe courante est celle que le LLM va lire, donc on a besoin de
    // details). On tronque plus serre que 5KB pour proteger la RAM sur les
    // longues boucles.
    const truncatedErrors = sandboxResult.steps
      .filter((s) => !s.ok)
      .map((s) => s.output.length > 1500
        ? `${s.output.slice(0, 1000)}\n...[tronque: ${s.output.length} chars total]...\n${s.output.slice(-400)}`
        : s.output)

    const pass: CorrectionPass = {
      attempt,
      score: currentScore,
      errors: truncatedErrors,
      strategy: attempt === 1 ? 'initial' : (strategy?.level ?? 'initial'),
      modelUsed: configuredCodeModel,
      resolved: sandboxResult.ok,
    }
    correctionLog.push(pass)

    // Memory release : resume les passes > 4 en arriere en une ligne. Sans ca
    // un long run de 10 passes accumule 10 × 3-5KB d erreurs + retries +
    // metadata qui finit par saturer la RAM (cause #2 de crash PC).
    if (correctionLog.length > 4) {
      for (let i = 0; i < correctionLog.length - 4; i++) {
        const old = correctionLog[i]
        if (old.errors.length > 1 || (old.errors[0] && old.errors[0].length > 200)) {
          correctionLog[i] = {
            ...old,
            errors: [`[passe archivee: ${old.errors.length} erreurs, score ${old.score}%]`],
          }
        }
      }
    }

    // Push real-time update to UI
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    if (sandboxResult.ok) {
      lastScore = 100
      break
    }

    // Environment blocker detection: the sandbox reports that a runtime or
    // toolchain is missing. The user rule is "JAMAIS arreter tant qu il n
    // atteint pas son but" — so we DO NOT break here anymore. Instead we
    // surface the blocker as a warning note on the pass and keep iterating;
    // the Auditeur / web research can still rewrite the project to use a
    // different stack that does not require the missing tool.
    const environmentBlocker = detectEnvironmentBlocker(sandboxResult, errorCategories)
    if (environmentBlocker) {
      pass.errors = [
        `[Blocage environnement detecte - ${environmentBlocker}]`,
        ...pass.errors,
      ]
      setPhase(`Passe ${attempt} - ${environmentBlocker} (le module essaie une stack alternative)...`, Math.min(92, 70 + attempt * 3))
    }

    const localRepair = attemptLocalFileRepair(currentFiles, sandboxResult)
    if (localRepair) {
      currentFiles = localRepair.files
      currentNotes = `${currentNotes ? `${currentNotes}\n\n` : ''}Auto-reparation locale: ${localRepair.reason}`
      onFilesUpdate(currentFiles, currentNotes)
      setPhase(`Passe ${attempt} - auto-reparation locale appliquee.`, Math.min(93, 71 + attempt * 3))
      lastScore = currentScore
      continue
    }

    // Check if we should continue — only exits on score=100 or true infinite
    // loop (same exact error 8+ times). No "plateau" cutoff anymore.
    if (!shouldContinueLoop(correctionLog, attempt, errorCategories)) {
      lastScore = currentScore
      const reason = currentScore >= 100
        ? 'livraison validee a 100%'
        : `boucle infinie detectee sur la meme erreur apres ${attempt} passes`
      setPhase(`Arret de la boucle : ${reason}.`, 92)
      break
    }

    // Auto-correction attempt with clear status
    const correctionModel = selectModel('correction', intent, strategy!.escalation, configuredCodeModel)
    pass.modelUsed = correctionModel
    pass.strategy = strategy!.level
    // Update UI with mutated pass
    onCorrectionLogUpdate([...correctionLog], attempt, currentScore)

    const strategyLabel = strategy!.level.replace(/_/g, ' ')
    const modelShort = getModelShortName(correctionModel)
    setPhase(`Passe ${attempt} — ${strategyLabel} via ${modelShort}...`, Math.min(92, 70 + attempt * 3))

    // At high escalation, search the web for solutions
    let researchContext = ''
    if (strategy!.searchWeb) {
      setPhase(`Passe ${attempt} — recherche de solutions en ligne...`, Math.min(93, 72 + attempt * 3))
      const failingErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
        .join('\n')
      try {
        researchContext = await withTimeout(searchForSolution(failingErrors, intent, configuredCodeModel), {
          label: 'Code correction research',
          timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
        })
      } catch {
        researchContext = ''
      }
    }

    // Analyse de cause racine — activee DES la passe 2 pour comprendre
    // chaque erreur en profondeur, pas seulement quand on est bloque
    let reasoningContext = ''
    const recentScores = correctionLog.slice(-3).map((pass) => pass.score)
    const isFlatlining = recentScores.length >= 3 && Math.max(...recentScores) - Math.min(...recentScores) <= 4
    if (attempt >= 2 || isFlatlining) {
      setPhase(`Passe ${attempt} — analyse de la cause racine...`, Math.min(93, 73 + attempt * 3))
      const currentErrors = sandboxResult.steps
        .filter((s) => !s.ok)
        .map((s) => s.output)
      const reasoning = await analyzeStuckCorrection(
        prompt,
        correctionLog,
        intent,
        currentErrors,
        configuredCodeModel,
      )
      if (reasoning) {
        reasoningContext = buildReasoningInstructions(reasoning)
        setPhase(`Passe ${attempt} — cause identifiee: ${reasoning.rootCause.slice(0, 80)}...`, Math.min(93, 74 + attempt * 3))
      }
    }

    // Regeneration de secours: repart de zero quand strategy_change ou rewrite
    // Autorisee toutes les 4 passes pour ne pas boucler mais donner plusieurs chances
    const rescueEligible = (strategy!.level === 'rewrite' || strategy!.level === 'strategy_change')
      && (!rescueRegenerationUsed || attempt % 4 === 0)
    if (rescueEligible) {
      rescueRegenerationUsed = true
      const failingErrors = sandboxResult.steps
        .filter((step) => !step.ok)
        .map((step) => step.output)
      const rescuePrompt = buildRescueRegenerationPrompt({
        originalPrompt: prompt,
        missionDossier,
        architecturePlan,
        failingSummary: sandboxResult.summary,
        failingErrors,
        reasoningContext,
      })

      setPhase(`Passe ${attempt} â€” regeneration de secours complete...`, Math.min(94, 75 + attempt * 3))
      const rescueResponse = await resilientOllamaGenerate(correctionModel, rescuePrompt, {
        timeoutMs: CORRECTION_TIMEOUT_MS,
        firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
        signal,
        num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
        neverMemorySkip: true,
        onRecoveryAttempt: (ev) => {
          setPhase(`Passe ${attempt} â€” sauvetage Ollama: ${ev.action}...`, Math.min(94, 76 + attempt * 3))
        },
      })

      const rescueContent = rescueResponse?.response?.trim() || ''
      const rescueFiles = parseCodeFiles(rescueContent)
      if (rescueFiles.length > 0 && !validateOutputMatchesIntent(rescueFiles, intent)) {
        currentFiles = rescueFiles
        currentNotes = extractNotes(rescueContent)
        onFilesUpdate(currentFiles, currentNotes)
        lastScore = currentScore
        continue
      }
    }

    // Build correction messages
    const correctionMessages = buildCorrectionMessages({
      prompt,
      files: currentFiles,
      validationResult: sandboxResult,
      strategy: strategy!,
      researchContext,
      reasoningContext,
      missionDossier,
      architecturePlan,
      preflightReport,
      intent,
    })

    setPhase(`Passe ${attempt} — ${modelShort} corrige le code...`, Math.min(94, 74 + attempt * 3))
    const repairResponse = await resilientOllamaChat(correctionModel, correctionMessages, 0.05, {
      timeoutMs: CORRECTION_TIMEOUT_MS,
      firstByteTimeoutMs: CORRECTION_FIRST_BYTE_TIMEOUT_MS,
      signal,
      num_ctx: CODE_EXPERT_CONTEXT_TOKENS,
      neverMemorySkip: true,
      onRecoveryAttempt: (ev) => {
        setPhase(`Passe ${attempt} — auto-reparation Ollama: ${ev.action}...`, Math.min(94, 75 + attempt * 3))
      },
    })
    const repairedContent = repairResponse?.message?.content?.trim() || ''
    const repairedFiles = parseCodeFiles(repairedContent)

    if (repairedFiles.length === 0) {
      // Correction produced nothing usable — continue to next strategy
      setPhase(`Passe ${attempt} — correction vide, tentative suivante...`, Math.min(94, 75 + attempt * 3))
      continue
    }

    // Validate the MERGED result, not the correction payload alone. v89b: a
    // legitimate single-file fix (e.g. the model returns only the repaired
    // script.js) used to be rejected here for "index.html absent" — index.html
    // already exists in currentFiles and is preserved by the merge, so the fix
    // was thrown away and the broken/truncated file kept. Validate what we'd
    // actually ship.
    const mergedCandidate = mergeExistingWithUpdates(currentFiles, repairedFiles)
    const correctionIssue = validateOutputMatchesIntent(mergedCandidate, intent)
    if (correctionIssue) {
      setPhase(`Passe ${attempt} — correction invalide (${correctionIssue.slice(0, 50)}...), on garde les fichiers actuels...`, Math.min(94, 76 + attempt * 3))
      continue
    }

    currentFiles = mergedCandidate
    currentNotes = extractNotes(repairedContent)
    onFilesUpdate(currentFiles, currentNotes)
    lastScore = currentScore
  }

  return {
    files: currentFiles,
    notes: currentNotes,
    sandboxResult,
    correctionLog,
    totalAttempts: attempt,
    finalScore: lastScore,
  }
}

// ---------------------------------------------------------------------------
// Correction message builder
// ---------------------------------------------------------------------------

function buildCorrectionMessages({
  prompt,
  files,
  validationResult,
  strategy,
  researchContext,
  reasoningContext,
  missionDossier,
  architecturePlan,
  preflightReport,
  intent,
}: {
  prompt: string
  files: CodeFile[]
  validationResult: CodeSandboxResult
  strategy: CorrectionStrategy
  researchContext: string
  reasoningContext?: string
  missionDossier: CodeMissionDossier
  architecturePlan: string | null
  preflightReport: CodePreflightReport | null
  /** v72: required to evaluate the brand fidelity gate inside the correction prompt. */
  intent: CodeIntent
}): OllamaMessage[] {
  const failingSteps = validationResult.steps
    .filter((step) => !step.ok)
    .slice(0, 5)
    .map((step) => [
      `Step: ${step.label}`,
      `Command: ${step.command}`,
      `Output: ${clipText(step.output || 'aucune sortie exploitable')}`,
    ].join('\n'))
    .join('\n\n')

  // Injecter le system prompt AUDITEUR IMPITOYABLE
  const systemLines = [
    buildAuditeurSystemPrompt(),
    '',
    '---',
    '',
    `Strategie: ${strategy.level} (escalation ${strategy.escalation})`,
    `Instructions: ${strategy.instructions}`,
    '',
    'Avant de toucher au code applicatif, determine si l echec vient du code, d une config locale manquante, d un script faux, d une incompatibilite de version, d un type moderne ou d un runtime absent.',
    'Si le projet utilise TypeScript, verifie d abord tsconfig.json, la version de typescript, les options du compilateur et les types installes.',
    'Ajoute ou corrige les fichiers de configuration locaux obligatoires quand ils manquent, au lieu d heriter implicitement d un dossier parent.',
    'Conserve les fichiers qui n ont pas besoin de changer.',
  ]

  if (/package\.json|json valide|actual JSON|EJSONPARSE|JSONParseError/i.test(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE ABSOLUE:',
      '- Corrige les fichiers JSON machine avant toute autre chose.',
      '- package.json doit etre un JSON strict, sans ```json, sans commentaires, sans explication autour.',
    )
  }

  if (isTypeScriptCompatibilityFailure(validationResult.summary + '\n' + failingSteps)) {
    systemLines.push(
      '',
      'PRIORITE COMPATIBILITE TYPESCRIPT:',
      '- Cherche une incompatibilite entre la version de typescript, tsconfig.json et les declarations .d.ts installees.',
      '- Si typescript est trop ancien pour les types/config actuels, monte la version du compilateur a un niveau compatible.',
      '- Si tsconfig.json manque, cree une configuration locale explicite au lieu de laisser tsc remonter dans les dossiers parents.',
    )
  }

  if (strategy.level === 'rewrite' || strategy.level === 'strategy_change') {
    systemLines.push(
      '',
      'ATTENTION: Les corrections precedentes ont echoue.',
      strategy.level === 'strategy_change'
        ? 'Change completement d approche: simplifie l architecture, utilise des patterns differents, change de librairies si necessaire.'
        : 'Reecris les fichiers problematiques completement. Ne te contente pas de patcher.',
    )
  }

  const userLines = [
    `Mission originale:\n${prompt}`,
    `Le sandbox a echoue:\n${validationResult.summary}`,
    failingSteps ? `Erreurs:\n${failingSteps}` : '',
    `Dossier executif:\n${serializeCodeMissionDossier(missionDossier)}`,
    architecturePlan ? `Plan d architecture de reference:\n${clipText(architecturePlan, 2200)}` : '',
    preflightReport ? `Preflight local:\n${serializeCodePreflightReport(preflightReport)}` : '',
  ]

  if (researchContext) {
    userLines.push(`\nSolutions trouvees en ligne:\n${researchContext}`)
  }

  if (reasoningContext) {
    userLines.push(`\n${reasoningContext}`)
  }

  // v67: si le projet est visuel (web/UI) ET le design polish est faible,
  // injecter le retry hint cible AVANT la consigne de correction. Le LLM
  // verra alors clairement quels patterns design il a oublies, en plus
  // des erreurs sandbox.
  const isVisual = files.length > 0 && files.some((f) => /\.(html?|css|s?css|tsx?|jsx?|vue|svelte)$/i.test(f.name))
  if (isVisual) {
    const designReport = computeDesignPolishReport(files)
    if (designReport.score < 70) {
      userLines.push('', buildDesignRetryHint(designReport))
    }
  }

  // v72: brand fidelity retry hint — quand le sujet est une marque connue
  // ET la gate de fidelite signale `shouldRetry`, injecter le hint cible
  // avec les regles violees pour que la correction ne se contente pas de
  // patcher la sandbox mais aussi reverrouille le sujet/palette/markers.
  const brandSubject = intent.assetPlan?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const brandReport = evaluateBrandFidelity(intent, files)
    if (brandReport.shouldRetry || brandReport.scorePenalty >= 15 || brandReport.scoreCap !== null) {
      const hintBlock = [
        '## RAPPEL VERROUILLAGE SUJET (FIDELITE BRAND ECHOUEE)',
        '',
        `Le sujet de cette page est ${brandSubject.canonical}. La gate de fidelite a detecte ces violations:`,
        brandReport.retryHint || '(pas de detail)',
        '',
        'A appliquer dans cette passe de correction:',
        `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, <h1> du hero, et au moins 3 sections.`,
        brandSubject.brandProfile.primaryColor ? `- La couleur ${brandSubject.brandProfile.primaryColor} doit etre presente dans les CSS variables et utilisee pour les CTAs/accents.` : '',
        brandSubject.brandProfile.productKeywords.length ? `- Au moins 2 mots-cles produit (${brandSubject.brandProfile.productKeywords.slice(0, 4).join(', ')}) doivent apparaitre dans les titres ou paragraphes.` : '',
        '- Les markers PLACEHOLDER_SUBJECT_IMG / _1 / _2 doivent etre utilises dans les balises <img>.',
        '- Pas de derive vers un sujet adjacent (restaurant generique, blog editorial, SaaS abstrait).',
      ].filter(Boolean).join('\n')
      userLines.push('', hintBlock)
    }
  }

  userLines.push(
    '',
    'Corrige le projet complet. Modifie seulement ce qui est necessaire.',
    `\nFichiers actuels:\n${serializeCodeFiles(files)}`,
  )

  return [
    { role: 'system', content: systemLines.join('\n') },
    { role: 'user', content: userLines.filter(Boolean).join('\n\n') },
  ]
}

// ---------------------------------------------------------------------------
// Output validation — detect when LLM produced docs instead of code
// ---------------------------------------------------------------------------

const DOCUMENTATION_EXTENSIONS = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])
const WEB_CODE_EXTENSIONS = new Set(['html', 'htm', 'css', 'scss', 'less', 'js', 'jsx', 'ts', 'tsx', 'vue', 'svelte', 'astro'])
const API_CODE_EXTENSIONS = new Set(['py', 'js', 'ts', 'go', 'rs', 'java', 'rb', 'php', 'cs', 'ex', 'kt'])
const WEB_RUNTIME_MANIFESTS = new Set([
  'go.mod',
  'go.sum',
  'pom.xml',
  'build.gradle',
  'build.gradle.kts',
  'composer.json',
  'gemfile',
  'requirements.txt',
  'manage.py',
])

function validateStructuredFiles(files: CodeFile[]): string | null {
  for (const file of files) {
    const normalized = file.name.replace(/\\/g, '/').toLowerCase()
    if (!normalized.endsWith('.json')) continue

    const parsed = tryParseJson(stripFormattingArtifacts(file.content))
    if (!parsed) {
      return `${file.name} n est pas un JSON valide. Les fichiers machine comme package.json doivent etre du JSON pur, sans backticks markdown ni texte parasite.`
    }

    if (normalized === 'package.json') {
      const packageName = parsed.name
      if (typeof packageName !== 'string' || packageName.trim().length === 0) {
        return 'package.json est present mais son champ "name" est invalide ou vide.'
      }
    }
  }

  return null
}

type LocalNodeManifest = {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  [key: string]: unknown
}

function upsertGeneratedFile(files: CodeFile[], nextFile: CodeFile) {
  const normalizedTarget = nextFile.name.replace(/\\/g, '/').toLowerCase()
  const existingIndex = files.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === normalizedTarget)
  if (existingIndex < 0) {
    return [...files, nextFile]
  }

  return files.map((file, index) => (index === existingIndex ? nextFile : file))
}

function readManifestDependencySpec(manifest: LocalNodeManifest, dependencyName: string) {
  for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
    const collection = manifest[section]
    if (collection && typeof collection === 'object' && dependencyName in collection) {
      const value = (collection as Record<string, unknown>)[dependencyName]
      if (typeof value === 'string') {
        return value
      }
    }
  }

  return null
}

function parseSpecVersion(spec: string) {
  const match = spec.match(/(\d+)(?:\.(\d+))?(?:\.(\d+))?/)
  if (!match) return null

  return {
    major: Number(match[1]),
    minor: Number(match[2] || '0'),
    patch: Number(match[3] || '0'),
  }
}

function isVersionBelow(spec: string, minimumMajor: number, minimumMinor: number) {
  const version = parseSpecVersion(spec)
  if (!version) return false
  if (version.major !== minimumMajor) {
    return version.major < minimumMajor
  }
  return version.minor < minimumMinor
}

function isTypeScriptCompatibilityFailure(rawOutput: string) {
  return /ReferenceNode\.d\.ts|PropertyNode\.d\.ts|@types\/three|type parameter declaration expected|error TS1139|error TS6046|Unknown compiler option 'allowImportingTsExtensions'|moduleResolution' option must be/i.test(rawOutput)
}

function repairLocalTypeScriptCompatibility(files: CodeFile[], failingOutput: string) {
  if (!isTypeScriptCompatibilityFailure(failingOutput)) {
    return null
  }

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) {
    return null
  }

  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content)) as LocalNodeManifest | null
  if (!manifest) {
    return null
  }

  const currentTypeScriptSpec = readManifestDependencySpec(manifest, 'typescript')
  if (currentTypeScriptSpec && !isVersionBelow(currentTypeScriptSpec, 5, 2)) {
    return null
  }

  const nextManifest: LocalNodeManifest = {
    ...manifest,
    devDependencies: {
      ...((manifest.devDependencies && typeof manifest.devDependencies === 'object')
        ? manifest.devDependencies
        : {}),
      typescript: '^5.2.0',
    },
  }

  const nextFiles = upsertGeneratedFile(files, {
    ...packageFile,
    content: `${JSON.stringify(nextManifest, null, 2)}\n`,
  })

  return {
    files: nextFiles,
    reason: currentTypeScriptSpec
      ? `mise a niveau automatique de TypeScript (${currentTypeScriptSpec} -> ^5.2.0) pour resoudre une incompatibilite compilateur/types`
      : 'ajout automatique de TypeScript ^5.2.0 pour resoudre une incompatibilite compilateur/types',
  }
}

function attemptLocalFileRepair(files: CodeFile[], sandboxResult: CodeSandboxResult) {
  const failingOutput = sandboxResult.steps
    .filter((step) => !step.ok)
    .map((step) => step.output)
    .join('\n')

  const sanitizedFiles = sanitizeGeneratedFiles(files)
  const changed = sanitizedFiles.some((file, index) =>
    file.name !== files[index]?.name || file.content !== files[index]?.content,
  )

  if (changed) {
    const structuredIssue = validateStructuredFiles(sanitizedFiles)
    if (!structuredIssue) {
      return {
        files: sanitizedFiles,
        reason: 'normalisation locale des fichiers machine et dependances declarees',
      }
    }
  }

  return repairLocalTypeScriptCompatibility(sanitizedFiles, failingOutput)
}

function validateOutputMatchesIntent(files: CodeFile[], intent: CodeIntent): string | null {
  if (files.length === 0) return 'Aucun fichier genere.'

  // Check for LLM refusal in any file content
  const refusalFile = files.find((f) => isLLMRefusal(f.content))
  if (refusalFile) {
    return `Le fichier "${refusalFile.name}" contient un refus du modele au lieu de code source. Le modele doit GENERER du code, pas s excuser.`
  }

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())

  // Check if ALL files are documentation (no code files at all)
  const allDocs = files.every((f) => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return DOCUMENTATION_EXTENSIONS.has(ext)
  })
  if (allDocs) {
    return 'Tous les fichiers sont des documents (md, txt) — aucun code source. Le module doit produire des FICHIERS DE CODE, pas de documentation.'
  }

  // Check if files have generic fallback names (bloc-1, module-2, script-3)
  // — means the model did not follow the required file header contract.
  const allGeneric = files.every((f) => isSyntheticFallbackFile(f.name))
  if (allGeneric) {
    return 'Les fichiers ont des noms generiques (bloc-1, module-2, script-3) — le format --- FICHIER: nom.ext --- n a pas ete suivi. Regenere avec des chemins reels comme package.json, index.html, src/App.tsx.'
  }

  const structuredIssue = validateStructuredFiles(files)
  if (structuredIssue) {
    return structuredIssue
  }

  if (intent.projectType === 'desktop_tauri') {
    const hasTauriFolder = normalizedNames.some((name) => name.startsWith('src-tauri/'))
    const hasCargoManifest = normalizedNames.some((name) => name === 'src-tauri/cargo.toml')
    const hasTauriConfig = normalizedNames.some((name) => name === 'src-tauri/tauri.conf.json')
    const hasRustEntry = normalizedNames.some((name) => /^src-tauri\/src\/.+\.rs$/i.test(name))
    const hasFrontendEntry = normalizedNames.some((name) =>
      name === 'package.json'
      || name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasTauriFolder || !hasCargoManifest || !hasTauriConfig || !hasRustEntry || !hasFrontendEntry) {
      return 'Projet desktop Tauri detecte mais la sortie ne contient pas une vraie structure applicative native complete (frontend + src-tauri + Rust + config Tauri).'
    }
  }

  if (intent.projectType === 'desktop_electron') {
    const hasPackageJson = normalizedNames.includes('package.json')
    const hasElectronMain = normalizedNames.some((name) =>
      /(^|\/)(main|electron\.main|background)\.(js|ts)$/i.test(name),
    )
    const hasRenderer = normalizedNames.some((name) =>
      name === 'index.html'
      || /^src\/.+\.(ts|tsx|js|jsx|html|css)$/i.test(name),
    )

    if (!hasPackageJson || !hasElectronMain || !hasRenderer) {
      return 'Projet desktop Electron detecte mais la sortie ne contient pas une vraie structure desktop complete (package.json + process principal Electron + renderer).'
    }
  }

  // Web project should have at least one HTML or framework file
  const isWebProject = intent.projectType.startsWith('spa_') ||
    intent.projectType.startsWith('ssr_') ||
    intent.projectType === 'static_web' ||
    intent.projectType === 'game_web'

  if (isWebProject) {
    const unexpectedRuntimeFiles = normalizedNames.filter((name) =>
      name.startsWith('src-tauri/')
      || WEB_RUNTIME_MANIFESTS.has(name)
      || name.endsWith('.go')
      || name.endsWith('.rs'),
    )

    if (!intent.projectType.startsWith('fullstack_') && unexpectedRuntimeFiles.length > 0) {
      return `Projet web detecte (${intent.projectType}) mais la sortie embarque des runtimes hors sujet (${unexpectedRuntimeFiles.slice(0, 3).join(', ')}). Regenerer un vrai projet web, pas du Go/Rust/backend parasite.`
    }

    const hasWebFile = files.some((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() || ''
      return WEB_CODE_EXTENSIONS.has(ext)
    })
    if (!hasWebFile) {
      return `Projet web detecte (${intent.projectType}) mais aucun fichier web (html, css, js, tsx...) trouve. Genere les vrais fichiers source du projet.`
    }

    if (intent.projectType === 'static_web') {
      const hasIndexHtml = normalizedNames.includes('index.html')
      // v85d : a static_web brief sometimes yields a richer framework project
      // (Astro / Vue / Svelte SFC). That is valid, more-complex web output — it
      // just needs a build step instead of a raw index.html. Accept it rather
      // than burning 3 retries (a 12B rarely downgrades to plain HTML on retry,
      // so rejecting just wastes time before the best-attempt fallback delivers
      // the same Astro project anyway).
      const hasFrameworkWebEntry = normalizedNames.some((name) =>
        /\.(astro|vue|svelte)$/i.test(name)
        || /^src\/pages\//i.test(name)
        || /astro\.config\.(mjs|js|ts)$/i.test(name))
      const hasRuntimeReadyJavascript = normalizedNames.some((name) => /\.(js|mjs|cjs)$/i.test(name))
      const hasRawTypeScriptOnly = normalizedNames.some((name) => /\.(ts|tsx)$/i.test(name)) && !hasRuntimeReadyJavascript

      if (!hasIndexHtml && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais `index.html` est absent. La preview et le lancement navigateur ont besoin d un vrai point d entree HTML.'
      }

      if (hasRawTypeScriptOnly && !hasFrameworkWebEntry) {
        return 'Page web statique detectee mais la sortie contient du TypeScript brut sans JavaScript transpile. Fournis une page HTML/CSS/JS directement executable.'
      }
    }

    if (intent.projectType.startsWith('spa_') || intent.projectType.startsWith('ssr_')) {
      const hasPackageManifest = normalizedNames.some((name) => name.endsWith('package.json'))
      if (!hasPackageManifest) {
        return `Projet ${intent.projectType} detecte mais aucun package.json n est present. Le dev server et la preview ne pourront pas demarrer correctement.`
      }
    }
  }

  // API project should have actual server code
  const isApiProject = intent.projectType.startsWith('api_') || intent.projectType.startsWith('fullstack_')
  if (isApiProject) {
    const hasCodeFile = files.some((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase() || ''
      return API_CODE_EXTENSIONS.has(ext)
    })
    if (!hasCodeFile) {
      return `Projet API detecte (${intent.projectType}) mais aucun fichier code serveur trouve. Genere les vrais fichiers source.`
    }
  }

  // Check if files are too small (likely stubs or descriptions)
  const avgContentLength = files.reduce((sum, f) => sum + f.content.length, 0) / files.length
  if (avgContentLength < 50 && files.length <= 2) {
    return 'Les fichiers generes sont trop courts (< 50 caracteres en moyenne) — probablement des stubs. Genere du code complet et fonctionnel.'
  }

  return null // Output looks valid
}

type ProjectRunbook = {
  installSteps: string[]
  runSteps: string[]
}

function buildProjectRunbook(files: CodeFile[], intent: CodeIntent): ProjectRunbook {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const hasIndexHtml = normalizedNames.includes('index.html')
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    return {
      installSteps: ['Aucune installation requise.'],
      runSteps: [
        hasIndexHtml ? 'Ouvrir `index.html` dans un navigateur.' : 'Le projet doit fournir un `index.html` pour la preview.',
      ],
    }
  }

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const installSteps = ['```bash', 'npm install', '```']
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      installSteps.push('', '```bash', 'cargo build', '```')
    }
    return {
      installSteps,
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    return {
      installSteps: hasRequirements
        ? ['```bash', 'pip install -r requirements.txt', '```']
        : ['Installer Python 3.11+ puis les dependances du projet.'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    const resolvedRunCommand = runCommand || 'cargo run'
    return {
      installSteps: ['```bash', 'cargo build', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    const resolvedRunCommand = runCommand || 'go run .'
    return {
      installSteps: ['```bash', 'go mod tidy', '```'],
      runSteps: ['```bash', resolvedRunCommand, '```'],
    }
  }

  return {
    installSteps: ['Voir les fichiers de configuration du projet pour les dependances exactes.'],
    runSteps: ['Consulter le code livre et le README pour lancer manuellement le projet.'],
  }
}

function buildLinuxLaunchScriptLines(files: CodeFile[], intent: CodeIntent): string[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.some((name) => name.endsWith('package.json'))
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))
  const pythonEntry = files.find((file) => /(^|\/)(main|app)\.py$/i.test(file.name.replace(/\\/g, '/')))
  const runCommand = intent.devCommand || intent.buildCommand

  if (intent.projectType === 'static_web') return []

  if (
    intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType === 'fullstack_mern'
    || intent.projectType === 'fullstack_nextjs'
    || intent.projectType === 'desktop_electron'
    || intent.projectType === 'desktop_tauri'
    || intent.projectType === 'api_express'
    || intent.projectType === 'cli_node'
    || intent.projectType === 'library_npm'
    || hasPackageJson
  ) {
    const resolvedRunCommand = runCommand || (hasPackageJson ? 'npm start' : 'npm run dev')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'if ! command -v npm >/dev/null 2>&1; then echo "Node.js avec npm est requis." >&2; exit 1; fi',
      'if [ ! -d "node_modules" ]; then npm install; fi',
    ]
    if (intent.projectType === 'desktop_tauri' && hasCargo) {
      lines.push('if ! command -v cargo >/dev/null 2>&1; then echo "Rust/Cargo est requis pour Tauri." >&2; exit 1; fi')
    }
    lines.push(resolvedRunCommand)
    return lines
  }

  if (
    intent.projectType === 'api_fastapi'
    || intent.projectType === 'api_django'
    || intent.projectType === 'api_flask'
    || intent.projectType === 'fullstack_django'
    || intent.projectType === 'cli_python'
    || intent.projectType === 'data_python'
  ) {
    const resolvedRunCommand = runCommand || (pythonEntry ? `python ${pythonEntry.name}` : 'python main.py')
    const lines = [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v python >/dev/null 2>&1 || { echo "Python est requis." >&2; exit 1; }',
    ]
    if (hasRequirements) lines.push('python -m pip install -r requirements.txt')
    lines.push(resolvedRunCommand)
    return lines
  }

  if (intent.projectType === 'api_actix' || intent.projectType === 'cli_rust' || intent.projectType === 'system_rust' || intent.projectType === 'library_crate') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v cargo >/dev/null 2>&1 || { echo "Rust/Cargo est requis." >&2; exit 1; }',
      runCommand || 'cargo run',
    ]
  }

  if (intent.projectType === 'api_gin' || intent.projectType === 'cli_go') {
    return [
      '#!/usr/bin/env bash',
      'set -euo pipefail',
      'cd "$(dirname "$0")"',
      'command -v go >/dev/null 2>&1 || { echo "Go est requis." >&2; exit 1; }',
      'go mod tidy',
      runCommand || 'go run .',
    ]
  }

  return []
}

function generateLinuxLaunchScript(files: CodeFile[], intent: CodeIntent): CodeFile | null {
  const hasLaunchScript = files.some((f) => /^(start|launch|lancement)\.(sh|bat)$/i.test(f.name.replace(/.*[/\\]/, '')))
  if (hasLaunchScript) return null

  const lines = buildLinuxLaunchScriptLines(files, intent)
  if (lines.length === 0) return null

  return {
    name: 'start.sh',
    language: 'bash',
    content: lines.join('\n'),
  }
}

/**
 * Some local models spray Tailwind utility
 * classes (flex, grid, text-5xl, bg-…) WITHOUT including Tailwind and without
 * generating the matching CSS → an unstyled BLACK page. If an HTML file uses
 * Tailwind utilities but ships no Tailwind, inject the Play CDN + a dark-mode
 * config so the page actually renders. No-op when the model wrote real CSS or
 * already included Tailwind.
 */
function ensureTailwindCDN(files: CodeFile[], projectType?: string): CodeFile[] {
  // A canvas game is self-styled (inline <style> + canvas draw calls) and never
  // needs Tailwind. The utility-class heuristic below false-positives on plain
  // class names like "container", injecting a ~2 KB marketing theme + an external
  // CDN script as dead weight. Skip it for games entirely.
  if (projectType === 'game_web') return files
  const TW_UTIL = /class="[^"]*\b(flex|grid|hidden|container|mx-auto|justify-\w+|items-\w+|text-(xs|sm|base|lg|xl|\dxl|center|fg|accent)|bg-[a-z]+(-\d{2,3})?|[pmgw][xytblr]?-\d|gap-\d|rounded(-\w+)?|shadow(-\w+)?|font-(bold|semibold|medium)|grid-cols-\d)\b/
  const HAS_TW = /cdn\.tailwindcss\.com|@tailwind\b/
  // v85g : local models spray SEMANTIC Tailwind tokens (bg-surface, text-fg,
  // text-fg-dim, bg-accent, shadow-2…) that need a config to be defined —
  // without it the classes resolve to NOTHING → unstyled/black page. We inject
  // the Play CDN + a CSS-variable theme + a Tailwind config that defines that
  // exact vocabulary, with light/dark wired to [data-theme="dark"]/.dark AND
  // prefers-color-scheme, so the page renders styled and the dark toggle works.
  const inject = [
    '<style data-aurora-theme>',
    ':root{--c-surface:255 255 255;--c-surface-elevated:248 247 245;--c-card:255 255 255;--c-fg:23 23 23;--c-fg-dim:90 92 100;--c-fg-mute:140 142 150;--c-line:230 230 234;--c-accent:124 92 255;--c-accent-soft:139 110 255}',
    '[data-theme="dark"],.dark{--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}',
    '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--c-surface:12 11 16;--c-surface-elevated:24 24 30;--c-card:22 22 28;--c-fg:240 240 245;--c-fg-dim:170 172 180;--c-fg-mute:120 122 130;--c-line:42 42 50;--c-accent:160 140 255;--c-accent-soft:175 155 255}}',
    'body{background:rgb(var(--c-surface));color:rgb(var(--c-fg));transition:background .3s ease,color .3s ease}',
    '</style>',
    '<script src="https://cdn.tailwindcss.com"></script>',
    '<script>tailwind.config={darkMode:["selector",\'[data-theme="dark"]\'],theme:{extend:{colors:{'
    + 'surface:{DEFAULT:"rgb(var(--c-surface) / <alpha-value>)",elevated:"rgb(var(--c-surface-elevated) / <alpha-value>)"},'
    + 'card:"rgb(var(--c-card) / <alpha-value>)",line:"rgb(var(--c-line) / <alpha-value>)",'
    + 'fg:{DEFAULT:"rgb(var(--c-fg) / <alpha-value>)",dim:"rgb(var(--c-fg-dim) / <alpha-value>)",mute:"rgb(var(--c-fg-mute) / <alpha-value>)"},'
    + 'accent:{DEFAULT:"rgb(var(--c-accent) / <alpha-value>)",soft:"rgb(var(--c-accent-soft) / <alpha-value>)"}},'
    + 'boxShadow:{2:"0 4px 16px rgb(0 0 0 / 0.08)",3:"0 12px 32px rgb(0 0 0 / 0.14)"}}}};</script>',
  ].join('\n')
  return files.map((f) => {
    if (!/\.html?$/i.test(f.name)) return f
    const c = f.content
    if (!TW_UTIL.test(c) || HAS_TW.test(c)) return f
    let next = c
    if (/<\/head>/i.test(next)) next = next.replace(/<\/head>/i, `${inject}\n</head>`)
    else if (/<head[^>]*>/i.test(next)) next = next.replace(/<head[^>]*>/i, (m) => `${m}\n${inject}`)
    else next = `${inject}\n${next}`
    return { ...f, content: next }
  })
}

function ensureSpaIndexHtml(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.includes('index.html')) return files

  const entry = [
    'src/main.tsx',
    'src/main.jsx',
    'src/main.ts',
    'src/main.js',
    'src/index.tsx',
    'src/index.jsx',
    'src/index.ts',
    'src/index.js',
    'main.tsx',
    'main.jsx',
    'main.ts',
    'main.js',
    'index.tsx',
    'index.jsx',
    'index.ts',
    'index.js',
  ].find((candidate) => normalizedNames.includes(candidate))

  if (!entry) return files

  const title = intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
  const html = [
    '<!doctype html>',
    '<html lang="en">',
    '  <head>',
    '    <meta charset="UTF-8" />',
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
    `    <title>${title}</title>`,
    '  </head>',
    '  <body>',
    '    <div id="root"></div>',
    `    <script type="module" src="/${entry}"></script>`,
    '  </body>',
    '</html>',
    '',
  ].join('\n')

  return [
    ...files,
    {
      name: 'index.html',
      language: 'html',
      content: html,
    },
  ]
}

function ensureSpaViteConfig(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  if (!intent.projectType.startsWith('spa_')) return files

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  if (normalizedNames.some((name) => /^vite\.config\.(?:ts|js|mjs|mts)$/.test(name))) return files

  return [
    ...files,
    {
      name: 'vite.config.ts',
      language: 'typescript',
      content: [
        "import { defineConfig } from 'vite'",
        "import react from '@vitejs/plugin-react'",
        '',
        'export default defineConfig({',
        '  plugins: [react()],',
        '  server: {',
        "    host: '127.0.0.1',",
        '    port: 5173,',
        '  },',
        '})',
        '',
      ].join('\n'),
    },
  ]
}

function fileSet(files: CodeFile[]) {
  return new Set(files.map((file) => file.name.replace(/\\/g, '/').toLowerCase()))
}

function projectUsesTailwindTooling(files: CodeFile[]) {
  const names = fileSet(files)
  if ([...names].some((name) => /(^|\/)tailwind\.config\.(?:js|cjs|mjs|ts)$/.test(name))) return true
  if (files.some((file) => /@tailwind\b|@apply\b/.test(file.content))) return true

  const packageFile = files.find((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (!packageFile) return false
  const manifest = tryParseJson(stripFormattingArtifacts(packageFile.content))
  return Boolean(manifest && manifestUsesPackage(manifest, 'tailwindcss'))
}

function ensureTailwindTooling(files: CodeFile[]) {
  if (!projectUsesTailwindTooling(files)) return files
  const names = fileSet(files)
  let nextFiles = files

  const packageIndex = nextFiles.findIndex((file) => file.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  if (packageIndex >= 0) {
    const manifest = tryParseJson(stripFormattingArtifacts(nextFiles[packageIndex].content))
    if (manifest) {
      let nextManifest = upsertPackageDevDependency(manifest, 'tailwindcss', '^3.4.17', true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'postcss', '^8.5.6', true)
      nextManifest = upsertPackageDevDependency(nextManifest, 'autoprefixer', '^10.4.21', true)
      nextFiles = nextFiles.map((file, index) => index === packageIndex
        ? { ...file, content: `${JSON.stringify(nextManifest, null, 2)}\n` }
        : file)
    }
  }

  if (names.has('postcss.config.js') || names.has('postcss.config.cjs') || names.has('postcss.config.mjs')) {
    return nextFiles
  }

  return [
    ...nextFiles,
    {
      name: 'postcss.config.js',
      language: 'javascript',
      content: [
        'export default {',
        '  plugins: {',
        '    tailwindcss: {},',
        '    autoprefixer: {},',
        '  },',
        '}',
        '',
      ].join('\n'),
    },
  ]
}

function isSyntheticFallbackFile(name: string): boolean {
  const normalized = name.replace(/\\/g, '/').toLowerCase()
  return /^(?:module|script|style|page|bloc)-\d+\.[a-z0-9]+$/.test(normalized)
    || /^output\.[a-z0-9]+$/.test(normalized)
    || /^reponse\.(?:txt|text|md)$/.test(normalized)
}

function stripSyntheticFallbackFiles(files: CodeFile[], intent: CodeIntent): CodeFile[] {
  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasStructuredProject =
    normalizedNames.includes('package.json')
    || normalizedNames.includes('index.html')
    || normalizedNames.some((name) => name.startsWith('src/'))

  if (!hasStructuredProject) return files

  const shouldStrip = intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType.startsWith('api_')
    || intent.needsDevServer
    || intent.needsBundling

  if (!shouldStrip) return files
  return files.filter((file) => !isSyntheticFallbackFile(file.name))
}

function upsertProjectSupportFiles(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile[] {
  const strippedFiles = ensureTailwindCDN(files, intent.projectType).filter((file) => {
    const name = file.name.replace(/\\/g, '/').toLowerCase()
    return name !== 'readme.md' && name !== 'lancement.bat' && name !== 'start.sh'
  })
  const baseFiles = ensureSpaViteConfig(
    ensureSpaIndexHtml(stripSyntheticFallbackFiles(strippedFiles, intent), intent),
    intent,
  )
  const supportedFiles = ensureTailwindTooling(baseFiles)

  const nextFiles = [...supportedFiles, generateReadme(supportedFiles, intent, prompt, architecturePlan)]
  const launchScript = generateLinuxLaunchScript(supportedFiles, intent)
  if (launchScript) nextFiles.push(launchScript)

  return nextFiles
}

export function upsertProjectSupportFilesForTest(
  files: CodeFile[],
  intent: CodeIntent,
  prompt = '',
  architecturePlan: string | null = null,
) {
  return upsertProjectSupportFiles(files, intent, prompt, architecturePlan)
}

// ---------------------------------------------------------------------------
// Main orchestration entry point
// ---------------------------------------------------------------------------

export async function orchestrateCodeGeneration({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  visionModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onRecoveryEvent,
  onFollowUpAnalysis,
  signal,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (USER_FILE_0 → data:image/jpeg;base64,...) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  visionModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onRecoveryEvent?: (event: RecoveryEvent) => void
  /** Fires as soon as the follow-up analyzer has decided the pivot kind. */
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  signal?: AbortSignal
}): Promise<CodeOrchestrationResult> {
  const generationModel = contextImages.length > 0 ? visionModel : configuredCodeModel
  const recoveryEvents: RecoveryEvent[] = []
  const trackRecovery = (ev: RecoveryEvent) => {
    recoveryEvents.push(ev)
    onRecoveryEvent?.(ev)
  }

  // Top-level crash guard — the pipeline NEVER crashes the app
  try {
    return await runFullPipeline({
      prompt,
      enrichedPrompt,
      conversationHistory,
      existingFiles,
      contextImages,
      userFileDataUrls,
      configuredCodeModel,
      generationModel,
      setPhase,
      onToken,
      onFilesUpdate,
      onValidationUpdate,
      onCorrectionLogUpdate,
      onFollowUpAnalysis,
      trackRecovery,
      recoveryEvents,
      signal,
    })
  } catch (fatalError) {
    // Absolute last resort — return error state instead of crashing
    const msg = fatalError instanceof Error ? fatalError.message : String(fatalError)
    console.error('[CodeOrchestrator] Pipeline fatal error (app NOT crashed):', msg)
    setPhase(`Erreur pipeline: ${msg.slice(0, 100)}`, 0)
    return {
      files: [],
      notes: `Erreur fatale du pipeline: ${msg}`,
      sandboxResult: null,
      intent: classifyCodeIntent(enrichedPrompt),
      preflightReport: null,
      correctionLog: [],
      phase: 'error',
      architecturePlan: null,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp: null,
    }
  }
}

// ---------------------------------------------------------------------------
// Full pipeline implementation (isolated for crash-proof wrapping)
// ---------------------------------------------------------------------------

async function runFullPipeline({
  prompt,
  enrichedPrompt,
  conversationHistory,
  existingFiles,
  contextImages,
  userFileDataUrls,
  configuredCodeModel,
  generationModel,
  setPhase,
  onToken,
  onFilesUpdate,
  onValidationUpdate,
  onCorrectionLogUpdate,
  onFollowUpAnalysis,
  trackRecovery,
  recoveryEvents,
  signal,
}: {
  prompt: string
  enrichedPrompt: string
  conversationHistory: OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  /** Map of placeholder → data URL for user-attached files (forwarded from orchestrateCodeGeneration) */
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  generationModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  trackRecovery: (event: RecoveryEvent) => void
  recoveryEvents: RecoveryEvent[]
  signal?: AbortSignal
}): Promise<CodeOrchestrationResult> {
  // Phase 0: Follow-up intent analysis — only runs when there is prior context.
  // Turns "la meme chose en python" into a reformulated prompt + pivotKind so
  // the rest of the pipeline does not accidentally carry a stale HTML project.
  const hasContext = conversationHistory.length > 0 || existingFiles.length > 0
  const followUp: FollowUpAnalysis | null = hasContext
    ? await (async () => {
        setPhase('Analyse du contexte de la discussion...', 3)
        try {
          return await analyzeFollowUpIntent({
            newPrompt: prompt,
            conversationHistory,
            existingFiles,
            model: configuredCodeModel,
            signal,
          })
        } catch (err) {
          console.warn('[CodeOrchestrator] follow-up analysis failed, continuing without:', err)
          return null
        }
      })()
    : null

  if (followUp) {
    onFollowUpAnalysis?.(followUp)
    setPhase(
      `Mode: ${followUp.kind}${followUp.pivotReason ? ` — ${followUp.pivotReason.slice(0, 60)}` : ''}`,
      5,
    )
  }

  // The prompt the remaining phases reason on is the reformulation when the
  // analyzer produced one. Keep the original `prompt`/`enrichedPrompt` for
  // places that need the raw user text.
  const reformulatedPrompt = followUp?.reformulatedPrompt?.trim() || prompt
  const reformulatedEnriched = followUp && followUp.reformulatedPrompt && followUp.reformulatedPrompt !== prompt
    ? `${enrichedPrompt}\n\n## REFORMULATION CONTEXTUELLE\n${followUp.reformulatedPrompt}`
    : enrichedPrompt

  // If the analyzer decided we are pivoting platforms or starting fresh,
  // drop the existing files so the Codeur does not see the old HTML while
  // the user actually asked for a Python backend. The migration summary
  // captures the business concept to carry over.
  const effectiveExistingFiles = followUp?.shouldResetFiles ? [] : existingFiles

  // Phase 1: Intent classification (deterministic) — enriched with follow-up context.
  const intentContext: CodeIntentContext | undefined = followUp
    ? {
        previousProjectType: followUp.previousProjectType ?? undefined,
        previousLanguages: followUp.previousLanguages,
        previousFrameworks: followUp.previousFrameworks,
        pivotKind: followUp.kind === 'clarify_only' ? 'increment' : followUp.kind,
      }
    : undefined
  const intent = runIntentPhase(reformulatedEnriched, setPhase, intentContext)

  // Phase 1.5: Deterministic + model-assisted preflight before any code generation
  const preflightReport = await runPreflightPhase(
    prompt,
    intent,
    existingFiles,
    configuredCodeModel,
    setPhase,
  )

  // Phase 1.75: Research best practices (non-blocking, enriches planning context)
  // Label is contextualized by the asset plan so the user understands WHY it takes time
  // ("recherche de references premium" >> "recherche generique").
  const ap = intent.assetPlan
  const researchPhaseLabel = ap?.researchQueries.length
    ? `Recherche de references visuelles en ligne (${ap.researchQueries.slice(0, 2).join(' | ')})... cela peut prendre jusqu a 30s`
    : ap?.wantsPremiumLook
      ? 'Recherche de tendances de design premium... cela peut prendre jusqu a 30s'
      : 'Recherche des meilleures pratiques pour ce type de projet...'
  setPhase(researchPhaseLabel, 14)
  let bestPracticesContext = ''
  try {
    bestPracticesContext = await withTimeout(researchBestPractices(prompt, intent, configuredCodeModel), {
      label: 'Code research best practices',
      timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
    })
    if (bestPracticesContext) {
      setPhase('Meilleures pratiques trouvees — integration dans la planification...', 16)
    }
  } catch {
    // Research is non-blocking — continue without it
  }

  // v77 — DYNAMIC BRAND ENRICHMENT. When the user prompt mentions a brand we
  // don't have in the in-memory dictionary (Lipton, Heineken, Audi, ...),
  // the codeIntent classifier marks the subject as `inferred_brand` with no
  // profile. We call the bridge `/api/brand/enrich` here to fetch a real
  // BrandProfile from Wikipedia + Ollama before the planning phase, so the
  // rest of the pipeline (image queries, productShape recipe, palette lock)
  // works the same way for ANY brand, not just our 47 cached ones.
  //
  // v84r FIX : on SKIP cette phase pour les prompts qui ressemblent à un brief
  // technique simple (mots "simple", "minimal", "page HTML", "bouton",
  // "fonction", "calcul" etc.) — un titre "Bonjour Aurora" ne devrait pas
  // déclencher 60s de Wikipedia + Ollama. Le brand enrich reste actif pour
  // les vrais briefs "fais-moi le site de Coca-Cola" etc.
  const promptLower = prompt.toLowerCase()
  const looksLikeSimpleTechBrief = (
    prompt.length < 300 &&
    /\b(simple|minimal|basique|petit|petite|un\s+bouton|une\s+page|index\.html|une\s+fonction|calcul|console|cli|script)\b/i.test(promptLower) &&
    !/\b(comme|pour|de la marque|site de|brand|logo de)\b/i.test(promptLower)
  )
  if (ap?.subject?.source === 'inferred_brand' && !ap.subject.brandProfile && ap.subject.canonical && !looksLikeSimpleTechBrief) {
    setPhase(`Enrichissement dynamique du profil de marque "${ap.subject.canonical}" (Wikipedia + Ollama)...`, 13)
    try {
      const enriched = await withTimeout(
        fetchBrandProfileFromBridge(ap.subject.canonical),
        // v84r : 55s → 20s. Si Wikipedia tarde, on n'a pas le luxe d'attendre.
        // Le code peut commencer à streamer avec la palette générique.
        { label: 'Brand enrich (bridge)', timeoutMs: 20_000 },
      )
      if (enriched) {
        // Mutate the subject in place — the rest of the pipeline now sees a
        // full BrandProfile and treats the page as a brand page.
        ap.subject.brandProfile = enriched
        ;(ap.subject as { source: string }).source = 'brand'
        // Also re-run the brand-aware research query injection that
        // classifyCodeAssetPlan does for cached brands, so the bridge
        // image fetch picks up the right queries from the new profile.
        if (enriched.imageQueries?.length && ap.researchQueries) {
          for (const q of enriched.imageQueries.slice(0, 3).reverse()) {
            ap.researchQueries.unshift(q)
          }
        }
        setPhase(`Profil "${ap.subject.canonical}" enrichi (palette ${enriched.primaryColor}, produit ${enriched.productShape ?? 'logo'}).`, 14)
      } else {
        setPhase(`Pas de profil enrichi trouve pour "${ap.subject.canonical}" — generic fallback.`, 14)
      }
    } catch (err) {
      console.warn('[CodeOrchestrator] brand enrich failed:', err)
    }
  }

  // Phase 1.8: Real image fetch for the detected subject — data URLs are inlined
  // in the prompt so the LLM reuses them as <img src="..."> directly.
  // This is how "il doit vraiment telecharger une image" happens, and it survives
  // the user saving the project anywhere since it is a data URL, not a remote link.
  // v71: multi-image — brand pages need 3-4 distinct shots (logo, product,
  // lifestyle, detail), not a single hero photo. The orchestrator queries the
  // Aurora-Connect extension first (real browser tab), then the Python bridge,
  // then a deterministic local SVG fallback.
  let subjectImageBlock = ''
  // v84r : skip pour les briefs simples — pas besoin d'aller chercher 4 images
  // si le user demande juste "page HTML avec un bouton qui calcule X".
  const wantsRealImage = ap && (ap.wantsImages || ap.subject?.source === 'brand' || (ap.objectMentions?.length ?? 0) > 0)
  if (wantsRealImage && !looksLikeSimpleTechBrief) {
    const isBrand = ap.subject?.source === 'brand'
    setPhase(
      isBrand
        ? 'Recuperation des images officielles de la marque (logo + produit + lifestyle)...'
        : 'Telechargement d images reelles du sujet (peut prendre 10-30s)...',
      17,
    )
    try {
      const images = await withTimeout(
        fetchSubjectImages(intent),
        { label: 'Subject images fetch (multi)', timeoutMs: 45_000 },
      )
      // Cap each data URL at ~280KB so we don't blow up the prompt — the Codeur
      // only needs the image to load at runtime, not to read its bytes during
      // planning. Anything longer is dropped silently.
      const acceptable = images.filter((img) => img.dataUrl.length <= 350_000)
      if (acceptable.length > 0) {
        const dataUrls = acceptable.map((img) => img.dataUrl)
        ;(intent as any).__subjectImageDataUrls = dataUrls
        // Keep the legacy single-marker field for any older prompt path.
        ;(intent as any).__subjectImageDataUrl = dataUrls[0]

        const sourcesLine = acceptable
          .map((img, idx) => `  ${idx + 1}. ${img.query || 'subject'} -> ${img.source || 'unknown'}`)
          .join('\n')
        subjectImageBlock = [
          `## IMAGES REELLES DU SUJET (telechargees pour toi en amont — ${acceptable.length})`,
          `- ${acceptable.length} photo(s) / illustration(s) du sujet ont ete trouvees et converties en data URLs.`,
          '- Tu DOIS les utiliser DIRECTEMENT dans la page avec ces markers literaux:',
          '  - `PLACEHOLDER_SUBJECT_IMG`     -> image principale (hero / produit central).',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_1`   -> image principale (alias du marker non numerote).' : '',
          acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_2`   -> image secondaire (lifestyle / contexte).' : '',
          acceptable.length >= 3 ? '  - `PLACEHOLDER_SUBJECT_IMG_3`   -> image tertiaire (detail / texture / variante).' : '',
          acceptable.length >= 4 ? '  - `PLACEHOLDER_SUBJECT_IMG_4`   -> image complementaire (gallery).' : '',
          '- Au build final, chaque marker sera remplace par la data URL correspondante.',
          '- Tu peux reutiliser le meme marker plusieurs fois (hero + showcase + footer). Tout marker sans image associee sera neutralise.',
          '- Sources originales:',
          sourcesLine,
        ].filter(Boolean).join('\n')
        setPhase(
          isBrand
            ? `${acceptable.length} image(s) de la marque telechargees — injection dans le prompt...`
            : `${acceptable.length} image(s) du sujet telechargees — injection dans le prompt...`,
          19,
        )
      } else if (images.length > 0) {
        console.warn('[CodeOrchestrator] All fetched subject images exceed the 350KB inline budget — skipping.')
      }
    } catch (err) {
      // Non-blocking: we continue without a real image. The Codeur falls back to
      // its usual SVG-inline strategy thanks to the "PAS D IMAGES CASSEES" rules.
      console.warn('[CodeOrchestrator] Subject image fetch failed:', err)
    }
  }

  // Inject brand profile into planning context: colors, keywords, design vibe.
  let brandProfileBlock = ''
  const brandSubject = ap?.subject
  if (brandSubject?.source === 'brand' && brandSubject.brandProfile) {
    const profile = brandSubject.brandProfile
    const palette: string[] = []
    if (profile.primaryColor) palette.push(`primaire ${profile.primaryColor}`)
    if (profile.secondaryColor) palette.push(`secondaire ${profile.secondaryColor}`)
    if (profile.tertiaryColor) palette.push(`tertiaire ${profile.tertiaryColor}`)
    brandProfileBlock = [
      `## PROFIL DE MARQUE — ${brandSubject.canonical}`,
      `- Domaine: ${brandSubject.domain ?? 'inconnu'}.`,
      palette.length ? `- Palette canonique: ${palette.join(', ')}.` : '',
      profile.productKeywords.length ? `- Produits / mots-cles: ${profile.productKeywords.join(', ')}.` : '',
      profile.designVibe ? `- Vibe visuel: ${profile.designVibe}.` : '',
      profile.typoVibe ? `- Typo: ${profile.typoVibe}.` : '',
      `- Le plan d architecture et le code DOIVENT respecter cette identite. Les couleurs du starter generique ne s appliquent pas.`,
    ].filter(Boolean).join('\n')
  }

  // Phase 2: Deep reasoning + architecture planning via llama4.
  const planningExtras: string[] = []
  if (bestPracticesContext) planningExtras.push(`## MEILLEURES PRATIQUES TROUVEES (a integrer dans le plan):\n${bestPracticesContext}`)
  // Brand profile injected before image block so architect plan uses colors/keywords.
  if (brandProfileBlock) planningExtras.push(brandProfileBlock)
  if (subjectImageBlock) planningExtras.push(subjectImageBlock)
  if (followUp?.migrationSummary && followUp.kind === 'pivot_platform') {
    planningExtras.push(`## MIGRATION DE PROJET (conserve le concept, change la stack)\n${followUp.migrationSummary}`)
  }
  const planningPrompt = planningExtras.length
    ? `${reformulatedEnriched}\n\n${planningExtras.join('\n\n')}`
    : reformulatedEnriched
  // Skip planning only for genuinely small visual one-offs. Complex visual work
  // (multi-page, 3D, simulator, whole-product briefs) needs the architect pass:
  // the user's target is a real engineered project, not a pretty single screen.
  const skipPlanningForVisual =
    (intent.projectType === 'static_web' || intent.projectType === 'game_web') &&
    !intent.needsArchitecturePlanning
  const architecturePlan = skipPlanningForVisual
    ? null
    : await runPlanningPhase(
        planningPrompt,
        intent,
        preflightReport,
        configuredCodeModel,
        setPhase,
        trackRecovery,
      )
  if (skipPlanningForVisual) setPhase('Projet web direct — generation sans plan lourd...', 28)
  const missionDossier = await buildCodeMissionDossier({
    prompt: reformulatedPrompt,
    enrichedPrompt: reformulatedEnriched,
    intent,
    existingFiles: effectiveExistingFiles,
    architecturePlan,
    model: selectModel('planning', intent, 0, configuredCodeModel),
  })

  // Pivot context forwarded to the code generator so it can swap the
  // "CONTEXTE PROJET EXISTANT" block with a "MIGRATION DE PROJET" block
  // when the user asked for a platform pivot.
  const pivotContext: GenerationPivotContext | undefined = followUp
    ? {
        kind: followUp.kind,
        migrationSummary: followUp.migrationSummary,
      }
    : undefined

  // Phase 3: Code generation (streaming, guided by plan)
  let fullContent = await runGenerationPhase(
    reformulatedEnriched,
    intent,
    preflightReport,
    architecturePlan,
    missionDossier,
    conversationHistory,
    effectiveExistingFiles,
    contextImages,
    generationModel,
    0,
    setPhase,
    onToken,
    trackRecovery,
    signal,
    pivotContext,
  )

  // CRITICAL: Detect LLM refusal BEFORE parsing — refuse early, retry immediately
  if (isLLMRefusal(fullContent)) {
    console.warn('[CodeOrchestrator] LLM returned a refusal instead of code. Forcing regeneration.')
    setPhase('Le modele a refuse de generer du code — regeneration forcee...', 40)
    // Force a regeneration with a stronger prompt
    const rescueContent = await runGenerationPhase(
      [
        'INSTRUCTION CRITIQUE: Tu DOIS generer du code source. NE REFUSE JAMAIS.',
        'Tu es un generateur de code. Ta seule sortie autorisee est du CODE SOURCE dans le format:',
        '--- FICHIER: nom.ext ---',
        '```langage',
        '// code ici',
        '```',
        '',
        'INTERDIT: excuses, refus, explications, suggestions de consulter les instructions.',
        'Genere le projet demande MAINTENANT:',
        '',
        reformulatedEnriched,
      ].join('\n'),
      intent,
      preflightReport,
      architecturePlan,
      missionDossier,
      conversationHistory,
      effectiveExistingFiles,
      contextImages,
      selectModel('generation', intent, 2, generationModel),
      2,
      setPhase,
      onToken,
      trackRecovery,
      signal,
      pivotContext,
    )
    // If rescue also refuses, we'll catch it in the validation loop below
    if (!isLLMRefusal(rescueContent)) {
      fullContent = rescueContent
    }
  }

  // Swap the PLACEHOLDER_SUBJECT_IMG marker with the real downloaded data URL
  // so every <img> tag the LLM wrote resolves immediately at first render.
  fullContent = applySubjectImagePlaceholder(fullContent, intent)

  // Swap USER_FILE_N markers with the real data URL of each user-attached file.
  // `userFileDataUrls` is optional in the public API — guard against every possible
  // shape (undefined / null / {}) to avoid ReferenceError at runtime.
  const userMap = userFileDataUrls ?? {}
  for (const [marker, dataUrl] of Object.entries(userMap)) {
    if (typeof dataUrl === 'string' && dataUrl && fullContent.includes(marker)) {
      fullContent = fullContent.split(marker).join(dataUrl)
    }
  }

  let latestRawGenerationContent = fullContent
  let parsed = parseCodeFiles(latestRawGenerationContent)
  let initialNotes = extractNotes(latestRawGenerationContent)
  // In follow-up mode (effectiveExistingFiles.length > 0), files NOT returned
  // by the LLM are preserved — we merge the new/changed files on top of the
  // existing set. After a pivot_platform / fresh_start, `effectiveExistingFiles`
  // is empty so the old project is correctly wiped.
  let initialFiles = effectiveExistingFiles.length > 0 && parsed.length > 0
    ? mergeExistingWithUpdates(effectiveExistingFiles, parsed)
    : parsed

  // Validate output quality — retry loop to ensure LLM produced actual code.
  // Complex briefs get more attempts and never downgrade to a tiny skeleton:
  // time is secondary to a complete, runnable project.
  const isExpertComplexProject = intent.complexity === 'complex' || intent.complexity === 'enterprise'
  const MAX_OUTPUT_RETRIES = isExpertComplexProject ? 6 : 3
  const MAX_NETWORK_ERRORS = isExpertComplexProject ? 4 : 2
  let outputRetry = 0
  let networkErrors = 0
  // v71 — track the latest brand fidelity report so we can apply the score
  // penalty/cap at the end of the orchestration.
  let latestBrandFidelity: BrandFidelityReport | null = null
  // v85c : remember the best non-empty attempt across the retry loop so the
  // pipeline NEVER returns 0 files when the model actually produced usable
  // code that a quality gate merely flagged. "Imparfait mais livré" > "rien".
  let bestAttempt: { files: CodeFile[]; notes: string; score: number } | null = null

  while (outputRetry < MAX_OUTPUT_RETRIES) {
    const draftReview = await reviewGeneratedCodeDraft({
      prompt,
      intent,
      files: initialFiles,
      architecturePlan,
      missionDossier,
      // v85c : CRITICAL — without this, the draft critique defaulted to
      // CODE_SINGLE_MODEL (qwen3-coder:30b, 20 GB) mid-pipeline, evicting the
      // routed generation model and forcing a CPU-spill +
      // reload thrash on every run. Pin it to the same model the rest of the
      // pipeline uses → true single-model coherence, no swap, far faster.
      model: configuredCodeModel,
    })
    // v71 — brand fidelity gate. Catches the "Coca-Cola → restaurant" drift
    // BEFORE the sandbox/correction loop wastes minutes on a wrong-subject
    // build. Only fires when the prompt has a brand subject; no-op otherwise.
    const brandSubject = intent.assetPlan?.subject
    const brandFidelity = evaluateBrandFidelity(intent, initialFiles)
    latestBrandFidelity = brandFidelity
    const brandIssueLine = brandFidelity.shouldRetry && brandFidelity.retryHint
      ? `Fidelite sujet (BRAND): ${brandFidelity.retryHint}`
      : null

    const issueNarrative = detectNonCodePlanningNarrative(latestRawGenerationContent)
    const issueIntent = validateOutputMatchesIntent(initialFiles, intent)
    const issueDraft = draftReview.verdict === 'regenerate'
      ? [
          draftReview.summary,
          ...draftReview.criticalIssues,
          ...draftReview.missingFiles,
        ].filter(Boolean).join(' | ')
      : null
    // v85d : the draft critique runs on the generation model,
    // which the audit found false-flags 'regenerate' on perfectly valid projects.
    // Trust the DETERMINISTIC gates (narrative / intent / brand) as primary;
    // let the LLM-judge force a retry ONLY when the output is also thin
    // (< 2 real code files) — otherwise it just burns retries on good output.
    const realCodeFileCount = initialFiles.filter((f) => {
      const e = f.name.split('.').pop()?.toLowerCase() || ''
      return !DOCUMENTATION_EXTENSIONS_EARLY.has(e)
    }).length
    const draftBlocks = issueDraft && realCodeFileCount < 2 ? issueDraft : null
    const outputIssue = issueNarrative || issueIntent || brandIssueLine || draftBlocks

    // v85c : track the best non-empty attempt (most files, then content score).
    if (initialFiles.length > 0) {
      const q = computeContentQualityScore(initialFiles, intent)
      if (!bestAttempt
        || initialFiles.length > bestAttempt.files.length
        || (initialFiles.length === bestAttempt.files.length && q > bestAttempt.score)) {
        bestAttempt = { files: initialFiles, notes: initialNotes, score: q }
      }
    }
    if (outputIssue) {
      console.warn(
        `[CodeOrchestrator] outputIssue @retry ${outputRetry} | files=${initialFiles.length} | `
        + `narrative=${!!issueNarrative} intentMismatch=${issueIntent ? JSON.stringify(issueIntent.slice(0, 80)) : false} `
        + `brand=${!!brandIssueLine} draftRegenerate=${!!issueDraft}`,
      )
    }
    if (!outputIssue) break // Output is valid code

    outputRetry++
    const escalation = outputRetry + 1
    const retryModel = selectModel('generation', intent, escalation, generationModel)
    const modelShort = retryModel.split(':')[0]

    setPhase(
      `Sortie incorrecte (tentative ${outputRetry}/${MAX_OUTPUT_RETRIES}) — regeneration via ${modelShort}...`,
      48 + outputRetry * 4,
    )

    // On brand drift: lock subject + palette + keywords in retry prompt.
    const brandRetryBlock = (brandFidelity.shouldRetry && brandSubject?.source === 'brand' && brandSubject.brandProfile)
      ? [
          '## VERROUILLAGE SUJET — REGLE INVIOLABLE',
          `Le sujet de cette page EST ${brandSubject.canonical}. Pas un sujet adjacent.`,
          '',
          'Violations detectees au tour precedent:',
          brandFidelity.retryHint || '(pas de detail)',
          '',
          'Pour ce nouveau tour, applique strictement:',
          `- Le mot "${brandSubject.canonical}" doit apparaitre dans <title>, dans le <h1> du hero, et dans au moins 3 sections.`,
          brandSubject.brandProfile.primaryColor ? `- Couleur primaire OBLIGATOIRE: ${brandSubject.brandProfile.primaryColor}. Utilise-la pour le hero, les CTAs et les accents.` : '',
          brandSubject.brandProfile.secondaryColor ? `- Couleur secondaire: ${brandSubject.brandProfile.secondaryColor}.` : '',
          brandSubject.brandProfile.productKeywords.length ? `- Mots-cles produit: ${brandSubject.brandProfile.productKeywords.join(', ')}. Au moins 2 dans les titres de section.` : '',
          brandSubject.brandProfile.designVibe ? `- Vibe visuel cible: ${brandSubject.brandProfile.designVibe}.` : '',
          '- Markers d images REELLES deja telechargees: PLACEHOLDER_SUBJECT_IMG, PLACEHOLDER_SUBJECT_IMG_1..4. Place-en au moins 2 dans la page.',
          '- INTERDIT: restaurant, menu du jour, blog culinaire, SaaS abstrait. C est une marque/produit emblematique, traite-la comme telle.',
        ].filter(Boolean).join('\n')
      : ''

    const retryPrompt = [
      `ERREUR CRITIQUE (tentative ${outputRetry + 1}): La sortie precedente etait INCORRECTE.`,
      `Probleme: ${outputIssue}`,
      '',
      brandRetryBlock,
      '',
      `DOSSIER EXECUTIF:\n${serializeCodeMissionDossier(missionDossier)}`,
      '',
      'RAPPEL ABSOLU:',
      '- Tu es un DEVELOPPEUR. Tu produis du CODE SOURCE, JAMAIS de la documentation.',
      '- Chaque fichier DOIT etre un VRAI fichier de code (html, css, js, py, etc.)',
      '- INTERDIT: fichiers .md, .txt, texte descriptif, listes de fonctionnalites',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? '- TA SORTIE PRECEDENTE ETAIT UN PLAN/PREFLIGHT. N envoie plus jamais de diagnostic: convertis directement la solution en fichiers.'
        : '',
      outputRetry >= 2 && !isExpertComplexProject
        ? '- SIMPLIFIE: produis le MINIMUM de fichiers necessaires pour que ca fonctionne'
        : '',
      outputRetry >= 2 && isExpertComplexProject
        ? '- NE SIMPLIFIE PAS LES FONCTIONNALITES: preserve le scope demande, corrige la structure et livre tous les fichiers necessaires.'
        : '',
      '',
      detectNonCodePlanningNarrative(latestRawGenerationContent)
        ? `SORTIE INTERDITE A NE PAS REPRODUIRE:\n${clipText(latestRawGenerationContent, 1400)}\n`
        : '',
      buildDraftRegenerationPrompt({
        originalPrompt: prompt,
        enrichedPrompt,
        missionDossier,
        draftReview,
        architecturePlan,
      }),
      '',
      architecturePlan ? `PLAN A SUIVRE:\n${architecturePlan.slice(0, 6000)}\n` : '',
      'Voici la demande originale. Genere les VRAIS FICHIERS DE CODE:',
      '',
      enrichedPrompt,
      '',
      'FORMAT OBLIGATOIRE (ne JAMAIS devier):',
      '--- FICHIER: nom_du_fichier.ext ---',
      '```langage',
      '// code source complet ici',
      '```',
      '',
      intent.projectType === 'static_web'
        ? 'Pour une page web, genere AU MINIMUM: index.html, style.css, et optionnellement script.js + README.md'
        : intent.projectType === 'desktop_tauri'
          ? 'Pour une application desktop Tauri, genere AU MINIMUM: package.json, src/*, src-tauri/Cargo.toml, src-tauri/tauri.conf.json, src-tauri/src/main.rs + README.md'
          : intent.projectType === 'desktop_electron'
            ? 'Pour une application desktop Electron, genere AU MINIMUM: package.json, main.ts|main.js, preload si utile, renderer src/* + README.md'
        : intent.projectType.startsWith('api_')
          ? 'Pour une API, genere les fichiers serveur: routes, models, config, entry point + README.md'
          : 'Genere tous les fichiers source necessaires au projet + README.md',
    ].filter(Boolean).join('\n')

    let retryContent = ''
    try {
      retryContent = await runGenerationPhase(
        retryPrompt,
        intent,
        preflightReport,
        architecturePlan,
        missionDossier,
        conversationHistory,
        effectiveExistingFiles,
        contextImages,
        retryModel,
        escalation,
        setPhase,
        onToken,
        trackRecovery,
        signal,
        pivotContext,
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      if (/failed to fetch|network|TypeError|524|connection closed/i.test(msg)) {
        networkErrors += 1
        setPhase(`Erreur reseau (${networkErrors}/${MAX_NETWORK_ERRORS}) pendant la regeneration — tentative ${outputRetry}...`, 50 + outputRetry * 4)
        if (networkErrors >= MAX_NETWORK_ERRORS) {
          setPhase('Trop d erreurs reseau consecutives — arret propre du pipeline.', 96)
          break
        }
        // Short pause then let the outer loop retry once more.
        await new Promise((r) => setTimeout(r, 2000))
        continue
      }
      throw err
    }

    latestRawGenerationContent = retryContent
    const retryFiles = parseCodeFiles(retryContent)
    initialFiles = effectiveExistingFiles.length > 0 && retryFiles.length > 0
      ? mergeExistingWithUpdates(effectiveExistingFiles, retryFiles)
      : retryFiles
    initialNotes = extractNotes(retryContent)
  }

  // v85c : if the retry loop exhausted while flagging issues but an earlier
  // attempt DID produce usable files, deliver the best one (with a quality
  // note) instead of returning nothing. The quality gates become advisory,
  // not fatal — the user always gets a project they can iterate on.
  if (initialFiles.length === 0 && bestAttempt && bestAttempt.files.length > 0) {
    console.warn(`[CodeOrchestrator] retry loop exhausted — delivering best attempt (${bestAttempt.files.length} fichiers) instead of 0.`)
    initialFiles = bestAttempt.files
    initialNotes = bestAttempt.notes
      ? `${bestAttempt.notes}\n\n[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.`
      : '[Aurora] Livré malgré des réserves du contrôle qualité — un ajustement manuel peut être utile.'
  }

  if (initialFiles.length === 0) {
    const diagnostic = buildEmptyGenerationDiagnostic(latestRawGenerationContent, intent, outputRetry)
    return {
      files: [],
      notes: diagnostic,
      sandboxResult: null,
      intent,
      preflightReport,
      correctionLog: [],
      phase: 'error',
      architecturePlan,
      totalAttempts: 0,
      finalScore: 0,
      recoveryEvents,
      followUp,
    }
  }

  initialFiles = upsertProjectSupportFiles(initialFiles, intent, reformulatedEnriched, architecturePlan)

  onFilesUpdate(initialFiles, initialNotes)

  // Phase 4+5: Validation + auto-correction loop
  const validationResult = await runValidationAndCorrectionLoop(
    prompt,
    initialFiles,
    intent,
    preflightReport,
    missionDossier,
    architecturePlan,
    configuredCodeModel,
    setPhase,
    onFilesUpdate,
    onValidationUpdate,
    onCorrectionLogUpdate,
    signal,
  )

  const finalFiles = upsertProjectSupportFiles(validationResult.files, intent, reformulatedEnriched, architecturePlan)

  // v71 — re-evaluate the brand fidelity AFTER the validation loop has settled.
  // The auto-correction may have rewritten copy and undone an earlier brand
  // fix, so we score on the final files.
  const finalBrandFidelity = evaluateBrandFidelity(intent, finalFiles)
  let adjustedScore = validationResult.finalScore
  if (finalBrandFidelity.scoreCap !== null) {
    adjustedScore = Math.min(adjustedScore, finalBrandFidelity.scoreCap)
  }
  if (finalBrandFidelity.scorePenalty > 0) {
    adjustedScore = Math.max(0, adjustedScore - finalBrandFidelity.scorePenalty)
  }

  const augmentedNotes = finalBrandFidelity.retryHint
    ? `${validationResult.notes}\n\n## FIDELITE SUJET\n${finalBrandFidelity.retryHint}`
    : validationResult.notes

  // Suppress the latestBrandFidelity warning when no longer used after the
  // post-loop re-evaluation. (Keeps the linter quiet without losing state
  // we may want to surface in a future iteration.)
  void latestBrandFidelity

  // Compute design polish report for visual project types (badge for UI).
  const designReport = isVisualProjectType(intent.projectType)
    ? computeDesignPolishReport(finalFiles)
    : null

  return {
    files: finalFiles,
    notes: augmentedNotes,
    sandboxResult: validationResult.sandboxResult,
    intent,
    preflightReport,
    correctionLog: validationResult.correctionLog,
    // Expert delivery contract: files are not enough. A project is done only
    // when the sandbox and deterministic quality gates agree it is runnable.
    phase: validationResult.sandboxResult?.ok ? 'done' : 'error',
    architecturePlan,
    totalAttempts: validationResult.totalAttempts,
    finalScore: adjustedScore,
    recoveryEvents,
    followUp,
    designReport,
  }
}

// ---------------------------------------------------------------------------
// README auto-generation — ensures every project has install/run instructions
// ---------------------------------------------------------------------------

function generateReadme(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile {
  const fileList = files
    .filter((f) => f.name.toLowerCase() !== 'readme.md')
    .map((f) => `- \`${f.name}\` — ${f.language}`)
    .join('\n')

  const normalizedNames = files.map((file) => file.name.replace(/\\/g, '/').toLowerCase())
  const hasPackageJson = normalizedNames.includes('package.json')
  const hasRequirements = normalizedNames.includes('requirements.txt')
  const hasCargo = normalizedNames.some((name) => name.endsWith('cargo.toml'))

  const installSteps: string[] = []
  if (hasPackageJson) {
    installSteps.push('```bash', 'npm install', '```')
  }
  if (hasRequirements) {
    installSteps.push('```bash', 'pip install -r requirements.txt', '```')
  }
  if (hasCargo) {
    installSteps.push('```bash', 'cargo build', '```')
  }
  if (installSteps.length === 0) {
    if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
      installSteps.push('Aucune installation requise — ouvrir `index.html` dans un navigateur.')
    } else {
      installSteps.push('Voir les dependances dans les fichiers de configuration du projet.')
    }
  }

  const runSteps: string[] = []
  if (intent.devCommand) {
    runSteps.push('```bash', intent.devCommand, '```')
  } else if (intent.projectType === 'static_web') {
    runSteps.push('Ouvrir `index.html` dans un navigateur web.')
  } else if (hasPackageJson) {
    runSteps.push('```bash', 'npm start', '```')
  } else if (files.some((f) => f.name === 'app.py' || f.name === 'main.py')) {
    const entry = files.find((f) => f.name === 'app.py') ? 'app.py' : 'main.py'
    runSteps.push('```bash', `python ${entry}`, '```')
  }

  const runbook = buildProjectRunbook(files, intent)

  // Extract dependencies from plan if available
  let depsSection = ''
  if (architecturePlan) {
    const depsMatch = architecturePlan.match(/###\s*DEPENDANCES[^\n]*\n([\s\S]*?)(?=###|$)/i)
    if (depsMatch?.[1]?.trim()) {
      depsSection = `## Dependances\n\n${depsMatch[1].trim()}\n\n`
    }
  }

  const content = [
    `# ${intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}`,
    '',
    `> ${prompt.slice(0, 200)}${prompt.length > 200 ? '...' : ''}`,
    '',
    '## Structure du projet',
    '',
    fileList,
    '',
    depsSection,
    '## Installation',
    '',
    runbook.installSteps.join('\n'),
    '',
    '## Lancement',
    '',
    runbook.runSteps.join('\n'),
    '',
    '## Raccourci de lancement',
    '',
    'Le fichier `start.sh` est fourni quand un demarrage automatise est possible sur Linux/macOS.',
    '',
    '---',
    '*Genere par Aurora IA — Module Code*',
  ].join('\n')

  return {
    name: 'README.md',
    language: 'markdown',
    content,
  }
}
