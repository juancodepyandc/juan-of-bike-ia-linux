// Shared contracts and weighted report builder for the active static critics.

import type { CodeIntent } from './codeIntent.ts'

export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeProject = {
  files: CodeFile[]
  /** Identifiant unique de la génération (utile pour la trace). */
  generationId: string
  /** Métadonnées libres. */
  meta?: Record<string, unknown>
}

export type CritiqueAxis =
  | 'compile'        // tsc / pyflakes / cargo check
  | 'lint'           // eslint / ruff
  | 'tests'          // npm test / pytest
  | 'fidelity'       // vis-à-vis de l'intent (brand, features)
  | 'runtime'        // l'app démarre sans throw
  | 'preview'        // CDP screenshot fidélité visuelle
  | 'security'       // analyse statique sécurité minimale
  | 'accessibility'  // axe-core / lighthouse
  | 'perf'           // lighthouse perf score

export type CritiqueIssue = {
  axis: CritiqueAxis
  severity: 'info' | 'warn' | 'error' | 'block'
  message: string
  /** Optional pointer to the file:line. */
  location?: { file: string; line?: number }
  /** Hint that the patcher can read in its next prompt. */
  suggestion?: string
}

export type CritiqueReport = {
  /** Score per axis, in [0..1]. */
  scores: Record<CritiqueAxis, number>
  /** Overall score (weighted mean). */
  overallScore: number
  /** Issues detected — sorted by severity descending. */
  issues: CritiqueIssue[]
  /** True when at least one block-level issue. */
  hasBlocker: boolean
}

// Security, runtime and compilation carry the strongest acceptance signal.
const AXIS_WEIGHTS: Record<CritiqueAxis, number> = {
  compile: 2.5,
  runtime: 2.5,
  security: 2.5,
  fidelity: 1.5,
  tests: 1.2,
  preview: 1,
  accessibility: 1,
  lint: 0.8,
  perf: 0.6,
}

export type CriticFn = (project: CodeProject, intent: CodeIntent) => Promise<CritiqueReport>

function emptyScores(): Record<CritiqueAxis, number> {
  return { compile: 0, lint: 0, tests: 0, fidelity: 0, runtime: 0, preview: 0, security: 0, accessibility: 0, perf: 0 }
}

/**
 * Aggregate raw signals into a CritiqueReport.
 * - `axisScores`: 0..1 per axis. Missing axes default to 1 (assume OK if no signal).
 * - `issues`: optional — used to bump hasBlocker.
 */
export function buildReport(axisScores: Partial<Record<CritiqueAxis, number>>, issues: CritiqueIssue[] = []): CritiqueReport {
  const scores = emptyScores()
  let totalWeight = 0
  let weightedSum = 0
  for (const axis of Object.keys(AXIS_WEIGHTS) as CritiqueAxis[]) {
    const score = clamp01(axisScores[axis] ?? 1)
    scores[axis] = score
    totalWeight += AXIS_WEIGHTS[axis]
    weightedSum += score * AXIS_WEIGHTS[axis]
  }
  const sortedIssues = [...issues].sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
  let overall = totalWeight > 0 ? weightedSum / totalWeight : 0
  // Pénalité dure : un blocker cap l'overall à 0.5 (un blocker doit
  // VRAIMENT empêcher d'atteindre le seuil expert quel que soit le reste).
  // Un blocker = "ce code ne peut pas être exporté en l'état" (eval, secret
  // en dur, SQL injection, parens non équilibrés).
  if (issues.some((i) => i.severity === 'block')) {
    overall = Math.min(overall, 0.5)
  }
  return {
    scores,
    overallScore: overall,
    issues: sortedIssues,
    hasBlocker: issues.some((i) => i.severity === 'block'),
  }
}

function severityRank(s: CritiqueIssue['severity']): number {
  switch (s) {
    case 'block': return 4
    case 'error': return 3
    case 'warn': return 2
    case 'info': return 1
  }
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}
