// Multi-pass LLM critique loop pour codeOrchestrator.
//
// Demande du handoff "expert uplift" :
//   "Multi-pass : génération → critique LLM → patch → re-test (boucle 3x max)"
//
// Ce module gère LE LOOP, pas l'invocation LLM elle-même (injectable). Permet :
//   - de tester la logique de bouclage sans dépendre d'un modèle,
//   - de paramétrer le nombre max de passes, les critères d'arrêt,
//   - de produire une "trace de critique" auditable pour l'UI ("Aurora a vu
//     N défauts, en a corrigé M").
//
// Le scoring est multi-axes : compile, lint, fidelity (vs intent), runtime,
// preview. Un pass est considéré ENCORE INSATISFAISANT si un axe critique
// est sous son seuil.

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

export type CritiqueThresholds = {
  /** Axes that MUST be at this minimum or higher. */
  required: Partial<Record<CritiqueAxis, number>>
  /** Overall score required to stop iterating. */
  overall: number
}

export const DEFAULT_THRESHOLDS: CritiqueThresholds = {
  required: { compile: 1.0, runtime: 0.9, fidelity: 0.7 },
  overall: 0.85,
}

// Poids par axe. Security & runtime sont prioritaires : une appli sécurisée
// mais moche vaut mieux qu'une appli jolie mais corrompue. Compile reste
// le plus élevé (sans compile, rien ne tourne).
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

// --- Critic + Patcher contracts --------------------------------------------
//
// The actual implementations live elsewhere (codeOrchestrator hooks). This
// module only consumes them.

export type CriticFn = (project: CodeProject, intent: CodeIntent) => Promise<CritiqueReport>
export type PatcherFn = (project: CodeProject, intent: CodeIntent, report: CritiqueReport) => Promise<CodeProject>

// --- Loop runner ------------------------------------------------------------
export type CritiqueLoopOptions = {
  /** Maximum passes before giving up. Default 3 (handoff spec). */
  maxPasses?: number
  thresholds?: CritiqueThresholds
  /** Abort signal (e.g. user clicked "stop"). */
  signal?: AbortSignal
  /** Emit a progress event after each pass. */
  onPass?: (pass: PassEvent) => void
  /** If true, keep iterating even when threshold met (rarely useful). */
  alwaysExhaust?: boolean
}

export type PassEvent = {
  pass: number
  totalPasses: number
  report: CritiqueReport
  thresholdMet: boolean
  willContinue: boolean
}

export type CritiqueLoopResult = {
  finalProject: CodeProject
  finalReport: CritiqueReport
  passesUsed: number
  thresholdMet: boolean
  /** History of reports (one per pass). */
  history: Array<{ pass: number; report: CritiqueReport }>
  /** Why we stopped. */
  stopReason: 'threshold-met' | 'max-passes' | 'aborted' | 'no-improvement'
  /** Improvement per pass (next - prev). Negative = regression. */
  scoreDeltas: number[]
}

/**
 * Run the generate→critique→patch loop. The initial generation should already
 * have happened — pass `initial` here.
 *
 * Aborts immediately if the signal is already triggered. Tracks per-pass
 * scoreDeltas so the orchestrator can flag patches that REGRESS (instructive
 * sign that the patcher prompt is broken).
 */
export async function runCritiqueLoop(
  initial: CodeProject,
  intent: CodeIntent,
  critic: CriticFn,
  patcher: PatcherFn,
  opts: CritiqueLoopOptions = {},
): Promise<CritiqueLoopResult> {
  const max = Math.max(1, opts.maxPasses ?? 3)
  const thresholds = opts.thresholds ?? DEFAULT_THRESHOLDS
  const history: CritiqueLoopResult['history'] = []
  const scoreDeltas: number[] = []
  let project = initial
  let lastReport: CritiqueReport | null = null
  let lastOverall: number | null = null
  let stopReason: CritiqueLoopResult['stopReason'] = 'max-passes'

  for (let i = 0; i < max; i += 1) {
    if (opts.signal?.aborted) {
      stopReason = 'aborted'
      break
    }
    const report = await critic(project, intent)
    history.push({ pass: i + 1, report })
    if (lastOverall != null) scoreDeltas.push(report.overallScore - lastOverall)

    const thresholdMet = meetsThresholds(report, thresholds)
    const event: PassEvent = {
      pass: i + 1,
      totalPasses: max,
      report,
      thresholdMet,
      willContinue: !thresholdMet && i + 1 < max && !opts.signal?.aborted,
    }
    opts.onPass?.(event)
    lastReport = report

    if (thresholdMet && !opts.alwaysExhaust) {
      stopReason = 'threshold-met'
      break
    }

    // Detect regression: 2 consecutive STRICTLY negative deltas → stop early
    // (patcher is making things worse). Stagnation (delta === 0) is allowed —
    // the next pass might break through.
    if (scoreDeltas.length >= 2) {
      const last2 = scoreDeltas.slice(-2)
      if (last2.every((d) => d < -1e-6)) {
        stopReason = 'no-improvement'
        break
      }
    }

    if (i + 1 >= max) {
      stopReason = 'max-passes'
      break
    }

    lastOverall = report.overallScore
    project = await patcher(project, intent, report)
  }

  return {
    finalProject: project,
    finalReport: lastReport ?? {
      scores: emptyScores(),
      overallScore: 0,
      issues: [],
      hasBlocker: false,
    },
    passesUsed: history.length,
    thresholdMet: lastReport ? meetsThresholds(lastReport, thresholds) : false,
    history,
    stopReason,
    scoreDeltas,
  }
}

function meetsThresholds(report: CritiqueReport, thresholds: CritiqueThresholds): boolean {
  if (report.hasBlocker) return false
  if (report.overallScore < thresholds.overall) return false
  for (const [axisKey, minScore] of Object.entries(thresholds.required)) {
    const axis = axisKey as CritiqueAxis
    if (report.scores[axis] < (minScore ?? 0)) return false
  }
  return true
}

function emptyScores(): Record<CritiqueAxis, number> {
  return { compile: 0, lint: 0, tests: 0, fidelity: 0, runtime: 0, preview: 0, security: 0, accessibility: 0, perf: 0 }
}

// --- Helpers to build CritiqueReport from raw signals ----------------------

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

// --- Framework detection by feature vector (replaces keyword classifier) ----
//
// Le handoff demande "Detection du framework requis par le brief: si user dit
// 'page web' → static, si 'todo app' → react+vite, etc. Le classifier actuel
// est keyword-based, passe en embedding."
//
// On reste sans embedding model (poids) mais on remplace le `if/else` linéaire
// par un classifier par feature-vector + tf-idf inverse — plus robuste aux
// reformulations.

export type FrameworkBucket =
  | 'static-html'
  | 'react-vite'
  | 'vue-vite'
  | 'svelte-kit'
  | 'next-app'
  | 'tauri-rust'
  | 'python-script'
  | 'python-fastapi'
  | 'node-cli'
  | 'arduino-c'
  | 'p5js-sketch'
  | 'three-scene'

type FrameworkFeature = {
  bucket: FrameworkBucket
  patterns: Array<{ tokens: string[]; weight: number }>
  /** Bonus when ALL tokens of one cluster appear together. */
  clusterBonus?: Array<{ tokens: string[]; bonus: number }>
}

const FRAMEWORK_FEATURES: FrameworkFeature[] = [
  {
    bucket: 'static-html',
    patterns: [
      { tokens: ['page', 'web'], weight: 3 },
      { tokens: ['site', 'vitrine'], weight: 3 },
      { tokens: ['html'], weight: 2 },
      { tokens: ['landing'], weight: 3 },
      { tokens: ['portfolio'], weight: 2 },
    ],
  },
  {
    bucket: 'react-vite',
    patterns: [
      { tokens: ['react'], weight: 3 },
      { tokens: ['todo', 'app'], weight: 5 },
      { tokens: ['dashboard'], weight: 3 },
      { tokens: ['component'], weight: 2 },
      { tokens: ['jsx'], weight: 2 },
      { tokens: ['hooks'], weight: 2 },
    ],
    clusterBonus: [{ tokens: ['react', 'vite'], bonus: 3 }],
  },
  {
    bucket: 'vue-vite',
    patterns: [
      { tokens: ['vue'], weight: 4 },
      { tokens: ['composition', 'api'], weight: 3 },
    ],
  },
  {
    bucket: 'svelte-kit',
    patterns: [
      { tokens: ['svelte'], weight: 4 },
      { tokens: ['kit'], weight: 2 },
    ],
  },
  {
    bucket: 'next-app',
    patterns: [
      { tokens: ['next', 'js'], weight: 5 },
      { tokens: ['nextjs'], weight: 5 },
      { tokens: ['ssr'], weight: 3 },
      { tokens: ['app', 'router'], weight: 3 },
    ],
  },
  {
    bucket: 'tauri-rust',
    patterns: [
      { tokens: ['tauri'], weight: 5 },
      { tokens: ['rust'], weight: 3 },
      { tokens: ['desktop'], weight: 2 },
    ],
  },
  {
    bucket: 'python-script',
    patterns: [
      { tokens: ['python'], weight: 3 },
      { tokens: ['script'], weight: 2 },
      { tokens: ['cli'], weight: 2 },
    ],
  },
  {
    bucket: 'python-fastapi',
    patterns: [
      { tokens: ['fastapi'], weight: 5 },
      { tokens: ['flask'], weight: 4 },
      { tokens: ['api', 'python'], weight: 3 },
    ],
  },
  {
    bucket: 'node-cli',
    patterns: [
      { tokens: ['node'], weight: 3 },
      { tokens: ['cli'], weight: 2 },
      { tokens: ['outil'], weight: 2 },
      { tokens: ['commander'], weight: 3 },
    ],
  },
  {
    bucket: 'arduino-c',
    patterns: [
      { tokens: ['arduino'], weight: 5 },
      { tokens: ['esp32'], weight: 5 },
      { tokens: ['microcontroleur'], weight: 5 },
      { tokens: ['gpio'], weight: 3 },
      { tokens: ['embarque'], weight: 3 },
    ],
  },
  {
    bucket: 'p5js-sketch',
    patterns: [
      { tokens: ['p5js'], weight: 5 },
      { tokens: ['p5'], weight: 3 },
      { tokens: ['sketch'], weight: 2 },
      { tokens: ['canvas', 'animation'], weight: 3 },
    ],
  },
  {
    bucket: 'three-scene',
    patterns: [
      { tokens: ['three', 'js'], weight: 5 },
      { tokens: ['threejs'], weight: 5 },
      { tokens: ['scene'], weight: 2 },
      { tokens: ['webgl'], weight: 3 },
    ],
  },
]

export type FrameworkClassification = {
  bucket: FrameworkBucket
  confidence: number
  scores: Array<{ bucket: FrameworkBucket; score: number }>
  matchedTokens: string[]
}

/**
 * Classify the brief into one of the framework buckets. Falls back to
 * static-html when nothing matches (handoff: "page web" → static).
 */
export function classifyFramework(brief: string): FrameworkClassification {
  const tokens = normaliseBrief(brief)
  const tokenSet = new Set(tokens)
  const scoreMap = new Map<FrameworkBucket, number>()
  const matched = new Set<string>()

  for (const feature of FRAMEWORK_FEATURES) {
    let s = 0
    for (const pat of feature.patterns) {
      if (pat.tokens.every((tok) => tokenSet.has(tok))) {
        s += pat.weight
        pat.tokens.forEach((t) => matched.add(t))
      }
    }
    if (feature.clusterBonus) {
      for (const cluster of feature.clusterBonus) {
        if (cluster.tokens.every((tok) => tokenSet.has(tok))) s += cluster.bonus
      }
    }
    scoreMap.set(feature.bucket, s)
  }

  const sorted = Array.from(scoreMap.entries())
    .map(([bucket, score]) => ({ bucket, score }))
    .sort((a, b) => b.score - a.score)

  const top = sorted[0]
  const total = sorted.reduce((acc, e) => acc + Math.max(0, e.score), 0)
  const confidence = top.score <= 0 ? 0.2 : top.score / Math.max(1, total)
  const bucket = top.score <= 0 ? 'static-html' : top.bucket

  return {
    bucket,
    confidence: top.score <= 0 ? 0.2 : confidence,
    scores: sorted,
    matchedTokens: Array.from(matched),
  }
}

function normaliseBrief(brief: string): string[] {
  if (!brief) return []
  return brief
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length >= 2)
}
