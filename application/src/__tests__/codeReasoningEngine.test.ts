import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { buildReasoningInstructions, type ReasoningResult } from '../services/codeReasoningEngine.ts'

describe('codeReasoningEngine', () => {
  test('les instructions de simplification restent conservatrices', () => {
    const reasoning: ReasoningResult = {
      rootCause: 'abstraction fragile autour du routeur',
      suggestion: 'remplacer l adaptateur fautif',
      architectureChange: 'resserrer le routeur',
      simplificationNeeded: true,
      alternativeStack: 'Fastify',
    }

    const instructions = buildReasoningInstructions(reasoning)

    assert.match(instructions, /SIMPLIFICATION STRUCTURELLE CONSERVATRICE/)
    assert.match(instructions, /Conserve les fichiers, tests, scripts, endpoints et exports publics/)
    assert.match(instructions, /sans reduire le perimetre/)
    assert.doesNotMatch(instructions, /Reduis le nombre de fichiers|strict minimum|code inline|Stack alternative recommandee/i)
  })
})
