import type { CodeIntent } from './codeIntent.ts'
import type { CritiqueReport } from './codeMultiPassCritique.ts'
import type { CodeSandboxResult, CodeSandboxStepResult } from './codeSandbox.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { computeContentQualityScore } from './codeQualityGates.ts'

function extractAcceptanceScore(sandboxResult: CodeSandboxResult): number | null {
  for (const step of sandboxResult.steps) {
    if (step.command !== 'internal:acceptance-criteria') continue
    const match = /acceptance-score=(\d+)/.exec(step.output)
    if (!match) continue
    return Math.max(0, Math.min(100, Number(match[1])))
  }
  return null
}

/** Calculate a granular score from sandbox results AND content quality. */
export function computeSandboxScore(
  sandboxResult: CodeSandboxResult,
  files: CodeFile[],
  intent: CodeIntent,
): number {
  const contentScore = computeContentQualityScore(files, intent)
  if (contentScore === 0) return 0
  if (contentScore <= 10) return contentScore

  const acceptanceScore = extractAcceptanceScore(sandboxResult)
  if (acceptanceScore !== null) {
    return Math.min(contentScore, acceptanceScore)
  }

  if (sandboxResult.ok) {
    return Math.min(100, contentScore)
  }

  const totalSteps = sandboxResult.steps.length
  if (totalSteps === 0) return Math.min(contentScore, 50)
  const passingSteps = sandboxResult.steps.filter((step) => step.ok).length
  const passRatio = passingSteps / totalSteps
  const baseScore = Math.round(passRatio * 80)
  const failingOutputs = sandboxResult.steps.filter((step) => !step.ok).map((step) => step.output).join('\n')
  let bonus = 0
  if (/warning/i.test(failingOutputs) && !/error/i.test(failingOutputs)) bonus += 10
  if (/compiled/i.test(failingOutputs) || /built/i.test(failingOutputs)) bonus += 5
  return Math.min(99, baseScore + bonus)
}

export function isStaticCritiqueBlocking(report: CritiqueReport): boolean {
  if (report.hasBlocker) return true
  if (report.issues.some((issue) => issue.severity === 'error')) return true
  if (report.scores.compile < 1) return true
  if (report.scores.security < 0.85) return true
  if (report.scores.lint < 0.65) return true
  return false
}

export function formatStaticCritiqueReport(report: CritiqueReport): string {
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

export function withStaticCritiqueStep(
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
