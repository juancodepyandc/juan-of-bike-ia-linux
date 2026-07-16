import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_SEMANTIC_INTENT_SCHEMA_VERSION,
  buildSemanticIntentClassifierMessages,
  classifyCodeIntentWithSemanticModel,
  parseSemanticIntentClassifierResponse,
} from '../services/codeSemanticIntentClassifier.ts'

describe('codeSemanticIntentClassifier', () => {
  test('construit un prompt JSON strict pour le modele semantique', () => {
    const messages = buildSemanticIntentClassifierMessages('cree un noyau OS')
    const content = messages.map((message) => message.content).join('\n')

    assert.match(content, /JSON strict/)
    assert.match(content, new RegExp(CODE_SEMANTIC_INTENT_SCHEMA_VERSION.replace(/\//g, '\\/')))
    assert.match(content, /os_kernel/)
  })

  test('parse une classification schema-valide et rejette les types inconnus', () => {
    const valid = parseSemanticIntentClassifierResponse(JSON.stringify({
      schemaVersion: CODE_SEMANTIC_INTENT_SCHEMA_VERSION,
      projectType: 'distributed_system',
      confidence: 0.92,
      languages: ['go'],
      frameworks: ['docker-compose'],
      features: ['raft'],
      rationale: 'multi node',
    }))
    const invalid = parseSemanticIntentClassifierResponse(JSON.stringify({
      schemaVersion: CODE_SEMANTIC_INTENT_SCHEMA_VERSION,
      projectType: 'space_station',
      confidence: 0.9,
    }))

    assert.equal(valid.ok, true)
    assert.equal(valid.ok && valid.value.projectType, 'distributed_system')
    assert.equal(invalid.ok, false)
  })

  test('applique le modele semantique ou retombe sur le fallback deterministe', async () => {
    const semantic = await classifyCodeIntentWithSemanticModel({
      prompt: 'cree un systeme distribue multi noeuds avec consensus',
      modelClient: async () => ({ message: { content: JSON.stringify({
        schemaVersion: CODE_SEMANTIC_INTENT_SCHEMA_VERSION,
        projectType: 'distributed_system',
        confidence: 0.88,
        languages: ['go'],
        frameworks: ['docker-compose'],
        features: ['consensus'],
        rationale: 'explicit distributed system',
      }) } }),
    })
    const fallback = await classifyCodeIntentWithSemanticModel({
      prompt: 'cree un systeme distribue multi noeuds avec consensus',
      minConfidence: 0.95,
      modelClient: async () => ({ message: { content: '{"bad":true}' } }),
    })

    assert.equal(semantic.source, 'semantic_model')
    assert.equal(semantic.intent.projectType, 'distributed_system')
    assert.equal(semantic.intent.testCommand, 'docker compose run --rm tests')
    assert.equal(fallback.source, 'fallback')
    assert.equal(fallback.intent.projectType, 'distributed_system')
  })
})
