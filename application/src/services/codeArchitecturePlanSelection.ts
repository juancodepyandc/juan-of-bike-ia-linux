import type { CodeIntent } from './codeIntent.ts'
import {
  type CodeArchitecturePlan,
  parseArchitecturePlanJson,
} from './codeArchitecturePlan.ts'
import { projectTypeConformityPenalty } from './codeProjectTypeStackContract.ts'

export type ArchitecturePlanCandidateScore = {
  index: number
  ok: boolean
  score: number
  errors: string[]
  serialized: string | null
}

export function getArchitecturePlanCandidateCount(intent: CodeIntent) {
  return intent.complexity === 'complex' || intent.complexity === 'enterprise' ? 2 : 1
}

export function scoreArchitecturePlan(plan: CodeArchitecturePlan) {
  const requiredFiles = plan.files.filter((file) => file.required).length
  const dependencySignal = plan.stack.dependencies.length + plan.stack.scripts.length
  const executionSignal = [
    ...plan.execution.install,
    ...plan.execution.dev,
    ...plan.execution.build,
    ...plan.execution.test,
    plan.execution.preview,
  ].filter(Boolean).length

  return (
    plan.summary.length / 80
    + requiredFiles * 4
    + plan.files.length * 2
    + dependencySignal * 2
    + executionSignal * 3
    + plan.dataFlow.length * 2
    + plan.generationOrder.length
    + plan.validation.length * 3
    + plan.risks.length * 2
    + plan.design.ux.length
    + plan.design.responsive.length
  )
}

/**
 * Selection du meilleur candidat.
 *
 * `intent` est optionnel pour rester retro-compatible, mais quand il est fourni
 * la conformite au type de projet PENALISE le score. Sans cela, le scoreur
 * favorise mecaniquement les plans les plus lourds: un plan Next.js battait un
 * plan statique correct sur une intention `static_web`, simplement parce qu il
 * avait plus de fichiers et plus de dependances.
 */
export function selectBestArchitecturePlan(rawCandidates: string[], intent?: CodeIntent) {
  const scored: ArchitecturePlanCandidateScore[] = rawCandidates.map((raw, index) => {
    const parsed = parseArchitecturePlanJson(raw)
    return parsed.ok
      ? {
          index,
          ok: true,
          score: scoreArchitecturePlan(parsed.plan)
            - (intent ? projectTypeConformityPenalty(parsed.plan, intent) : 0),
          errors: [],
          serialized: parsed.serialized,
        }
      : {
          index,
          ok: false,
          score: 0,
          errors: parsed.errors,
          serialized: null,
        }
  })

  const selected = scored
    .filter((candidate) => candidate.ok && candidate.serialized)
    .sort((a, b) => b.score - a.score || a.index - b.index)[0] ?? null

  return {
    selected,
    scored,
  }
}

