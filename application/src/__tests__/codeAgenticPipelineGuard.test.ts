import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath: string) {
  return readFileSync(new URL(`../services/${relativePath}`, import.meta.url), 'utf8')
}

describe('code agentic pipeline guard', () => {
  test('ne contient plus de chemin de generation monolithique', () => {
    const pipeline = [
      source('codeOrchestrator.ts'),
      source('codePipelinePhases.ts'),
      source('codeGenerationOutputRetry.ts'),
    ].join('\n')

    assert.doesNotMatch(pipeline, /runGenerationPhase/)
    assert.doesNotMatch(pipeline, /fallback generation directe/i)
    assert.doesNotMatch(pipeline, /generation directe par le Codeur/i)
  })

  test('conserve le scope pendant tous les retries', () => {
    const retry = source('codeGenerationOutputRetry.ts')
    assert.doesNotMatch(retry, /SIMPLIFIE: produis le MINIMUM/i)
    assert.match(retry, /preserve le scope demande/)
    assert.match(retry, /runAgenticGenerationPhase/)
  })

  test('rend le plan JSON obligatoire avant execution WS3', () => {
    const orchestrator = source('codeOrchestrator.ts')
    const phases = source('codePipelinePhases.ts')
    assert.doesNotMatch(orchestrator, /skipPlanningForVisual/)
    assert.match(orchestrator, /isArchitecturePlanUsable\(architecturePlan\)/)
    assert.match(phases, /architecture_plan_invalid/)
    assert.match(phases, /generation bloquee/)
  })
})
