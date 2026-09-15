import type { OllamaMessage } from '../types/app.ts'
import {
  type CodeIntent,
  type CodeProjectType,
  classifyPivotKindHeuristic,
} from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'

const FOLLOW_UP_CONTEXT_TOKENS = 16_384

// ---------------------------------------------------------------------------
// Smart clarification filter - suppress vague or useless questions
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
 * Vague questions waste user time - the module should make assumptions instead.
 */
export function isVagueClarification(question: string | null): boolean {
  if (!question) return true
  if (question.length < 15) return true
  if (question.length > 500) return true
  return VAGUE_QUESTION_PATTERNS.some((pattern) => pattern.test(question))
}

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
 * - 'critical'  -> block the user with a dialog (choice would ruin the output)
 * - 'optional'  -> auto-proceed with a documented assumption
 * - 'skip'      -> question is vague / boilerplate, ignore entirely
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
  // Vague boilerplate -> skip, always. (Keeps parity with isVagueClarification.)
  if (VAGUE_QUESTION_PATTERNS.some((pattern) => pattern.test(trimmed))) return 'skip'

  // If the question references any non-reversible decision, treat as critical.
  if (CRITICAL_DECISION_TOKENS.some((pattern) => pattern.test(trimmed))) {
    return 'critical'
  }
  // Otherwise optional - the module can make a sensible assumption.
  return 'optional'
}

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
  // Heuristically guess project type from file names.
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
    `Langages: ${[...langs].join(', ') || '-'}`,
    `Frameworks probables: ${[...frameworks].join(', ') || '-'}`,
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
    const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
    const response = await resilientOllamaGenerate(model, instruction, {
      timeoutMs: 120_000,
      firstByteTimeoutMs: 90_000,
      signal,
      neverMemorySkip: true, // v85c : follow-up analysis must run for continuity
      num_ctx: FOLLOW_UP_CONTEXT_TOKENS,
    })
    const raw = response?.response?.trim() || ''
    // Extract the first JSON object in the response (models sometimes wrap in prose).
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
