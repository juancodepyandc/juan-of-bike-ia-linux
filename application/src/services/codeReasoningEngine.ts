// ---------------------------------------------------------------------------
// Code Reasoning Engine — LLM-powered error analysis for stuck corrections
// When the auto-correction loop stagnates, this module analyzes WHY and
// proposes cause-driven approaches instead of retrying blindly
// ---------------------------------------------------------------------------

import { CODE_SINGLE_MODEL } from '../config/models.ts'
import type { CorrectionPass } from './codeAutoCorrection.ts'
import type { CodeIntent } from './codeIntent.ts'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ReasoningResult = {
  rootCause: string
  suggestion: string
  architectureChange: string | null
  simplificationNeeded: boolean
  alternativeStack: string | null
}

// ---------------------------------------------------------------------------
// Build a diagnostic prompt from the correction history
// ---------------------------------------------------------------------------

function buildDiagnosticPrompt(
  originalPrompt: string,
  correctionLog: CorrectionPass[],
  intent: CodeIntent,
  currentErrors: string[],
): string {
  const historyLines = correctionLog.map((pass) => {
    const errSummary = pass.errors.length > 0
      ? pass.errors.map((e) => e.slice(0, 150)).join(' | ')
      : 'aucune erreur capturee'
    return `  Passe ${pass.attempt}: ${pass.strategy} — score ${pass.score}% — ${pass.resolved ? 'RESOLU' : 'ECHOUE'} — ${errSummary}`
  }).join('\n')

  return [
    'Tu es un architecte logiciel d elite specialise en diagnostic de bug et en resolution de problemes complexes.',
    'Tu DOIS analyser cette situation de debug en profondeur et proposer une solution CONCRETE.',
    'Tu es un MOTEUR de resolution — tu ne refuses JAMAIS, tu ne t excuses JAMAIS, tu RESOUS TOUJOURS.',
    '',
    '## Contexte du projet',
    `Demande originale: ${originalPrompt.slice(0, 500)}`,
    `Type de projet: ${intent.projectType}`,
    `Frameworks: ${intent.frameworks.join(', ') || 'aucun'}`,
    `Langages: ${intent.languages.join(', ') || 'non determine'}`,
    `Complexite: ${intent.complexity}`,
    '',
    '## Historique des corrections (toutes ont echoue ou stagne)',
    historyLines,
    '',
    '## Derniere erreur',
    currentErrors.slice(0, 3).map((e) => e.slice(0, 300)).join('\n---\n'),
    '',
    '## Methode de diagnostic',
    '1. Identifie le PATTERN d echec: est-ce toujours la meme erreur? Des erreurs differentes a chaque fois?',
    '2. Identifie la CAUSE RACINE: config, dependance, version, architecture, ou logique?',
    '3. Propose une solution qui CASSE le cycle d echec — pas un patch incremental',
    '4. Si le probleme est structural, recommande une simplification conservatrice qui preserve les capacites existantes',
    '',
    '## Ta reponse DOIT suivre ce format EXACTEMENT (JSON):',
    '{',
    '  "rootCause": "explication courte de la cause racine (1-2 phrases)",',
    '  "suggestion": "instruction concrete pour corriger (ce que le code doit faire differemment)",',
    '  "architectureChange": "changement architectural si necessaire, ou null",',
    '  "simplificationNeeded": true/false,',
    '  "alternativeStack": "alternative technique locale si la stack actuelle est prouvee incompatible, ou null"',
    '}',
    '',
    'IMPORTANT: Reponds UNIQUEMENT avec le JSON, rien d autre. JAMAIS de refus ni d excuse.',
  ].join('\n')
}

// ---------------------------------------------------------------------------
// Parse the LLM response — tolerant to formatting issues
// ---------------------------------------------------------------------------

function parseReasoningResponse(raw: string): ReasoningResult | null {
  try {
    // Try direct JSON parse
    const cleaned = raw.trim()
      .replace(/^```json?\s*/i, '')
      .replace(/\s*```$/, '')
      .trim()

    const parsed = JSON.parse(cleaned)
    return {
      rootCause: String(parsed.rootCause || 'Cause non determinee'),
      suggestion: String(parsed.suggestion || ''),
      architectureChange: parsed.architectureChange ? String(parsed.architectureChange) : null,
      simplificationNeeded: Boolean(parsed.simplificationNeeded),
      alternativeStack: parsed.alternativeStack ? String(parsed.alternativeStack) : null,
    }
  } catch {
    // Try to extract key fields with regex
    const rootCause = raw.match(/"rootCause"\s*:\s*"([^"]+)"/)?.[1]
    const suggestion = raw.match(/"suggestion"\s*:\s*"([^"]+)"/)?.[1]

    if (rootCause || suggestion) {
      return {
        rootCause: rootCause || 'Cause extraite partiellement',
        suggestion: suggestion || '',
        architectureChange: raw.match(/"architectureChange"\s*:\s*"([^"]+)"/)?.[1] || null,
        simplificationNeeded: /simplificationNeeded.*true/i.test(raw),
        alternativeStack: raw.match(/"alternativeStack"\s*:\s*"([^"]+)"/)?.[1] || null,
      }
    }

    return null
  }
}

// ---------------------------------------------------------------------------
// Main entry point — analyze stuck correction loop
// ---------------------------------------------------------------------------

export async function analyzeStuckCorrection(
  originalPrompt: string,
  correctionLog: CorrectionPass[],
  intent: CodeIntent,
  currentErrors: string[],
  model: string = CODE_SINGLE_MODEL,
): Promise<ReasoningResult | null> {
  const diagnosticPrompt = buildDiagnosticPrompt(
    originalPrompt,
    correctionLog,
    intent,
    currentErrors,
  )

  try {
    const { resilientOllamaGenerate } = await import('./ollamaResilience.ts')
    const response = await resilientOllamaGenerate(model, diagnosticPrompt, {
      timeoutMs: 60_000,
    })
    const raw = response?.response?.trim()
    if (!raw) return null

    return parseReasoningResponse(raw)
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Build correction instructions from reasoning result
// ---------------------------------------------------------------------------

export function buildReasoningInstructions(reasoning: ReasoningResult): string {
  const lines: string[] = [
    '## ANALYSE AUTOMATIQUE DU PROBLEME (Reasoning Engine)',
    '',
    `Cause racine identifiee: ${reasoning.rootCause}`,
  ]

  if (reasoning.suggestion) {
    lines.push('', `Action requise: ${reasoning.suggestion}`)
  }

  if (reasoning.architectureChange) {
    lines.push('', `Changement architectural: ${reasoning.architectureChange}`)
  }

  if (reasoning.simplificationNeeded) {
    lines.push(
      '',
      'SIMPLIFICATION STRUCTURELLE CONSERVATRICE:',
      '- Elimine seulement les abstractions inutiles reliees a la cause racine',
      '- Conserve les fichiers, tests, scripts, endpoints et exports publics existants',
      '- Utilise des patterns simples et eprouves sans reduire le perimetre fonctionnel',
      '- Prefere un import explicite et stable a une chaine d abstractions fragile',
    )
  }

  if (reasoning.alternativeStack) {
    lines.push('', `Alternative technique a evaluer sans reduire le perimetre: ${reasoning.alternativeStack}`)
  }

  lines.push(
    '',
    'APPLIQUE ces changements dans ta prochaine correction.',
    'Ne repete PAS les memes erreurs que les tentatives precedentes.',
  )

  return lines.join('\n')
}
