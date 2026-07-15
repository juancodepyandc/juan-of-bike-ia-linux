import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import {
  analyzeFollowUpIntent,
  classifyClarificationSeverity,
  isVagueClarification,
} from '../services/codeFollowUpAnalysis.ts'

describe('codeFollowUpAnalysis', () => {
  test('ignore les clarifications vagues', () => {
    assert.equal(isVagueClarification(null), true)
    assert.equal(isVagueClarification('Could you please clarify what kind of app you want?'), true)
    assert.equal(isVagueClarification('Dois-je utiliser React ou Vue pour cette application web ?'), false)
  })

  test('classe les questions critiques et optionnelles', () => {
    const intent = {} as CodeIntent

    assert.equal(
      classifyClarificationSeverity('Faut-il une authentification avec login ?', intent, 'app'),
      'critical',
    )
    assert.equal(
      classifyClarificationSeverity('Souhaites-tu un style clair ou sombre ?', intent, 'app'),
      'optional',
    )
    assert.equal(
      classifyClarificationSeverity('Could you please clarify what kind of app you want?', intent, 'app'),
      'skip',
    )
  })

  test('retourne fresh_start sans contexte ni fichiers', async () => {
    const analysis = await analyzeFollowUpIntent({
      newPrompt: 'cree une calculatrice web',
      conversationHistory: [],
      existingFiles: [],
      model: 'unused',
    })

    assert.equal(analysis.kind, 'fresh_start')
    assert.equal(analysis.shouldResetFiles, true)
    assert.deepEqual(analysis.previousLanguages, [])
  })
})
