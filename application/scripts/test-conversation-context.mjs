#!/usr/bin/env node
// Conversation : « un vrai suivi de conversation, me dire jusqu'à combien on peut utiliser de jetons ».
// L'historique entier partait avec une fenêtre fixe de 32 768 jetons ; au-delà Ollama coupait le
// DÉBUT du prompt — les instructions — sans prévenir. Vraies sources TypeScript.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  CONTEXT_TIERS, calibrate, charsPerToken, planContext, profileFromModelInfo, sustainableContext,
} from '../src/services/conversationContextBudget.ts'

// model_info réel d'Ollama pour orcarouter/Qwen3.8-27B-Uncensored (architecture hybride qwen35)
const QWEN35 = {
  'general.architecture': 'qwen35', 'qwen35.block_count': 65, 'qwen35.full_attention_interval': 4,
  'qwen35.attention.head_count': 24, 'qwen35.attention.head_count_kv': 4,
  'qwen35.attention.key_length': 256, 'qwen35.attention.value_length': 256,
  'qwen35.context_length': 262144, 'qwen35.embedding_length': 5120,
}
// deepseek-r1:32b (qwen2, attention complète sur toutes les couches)
const QWEN2 = {
  'general.architecture': 'qwen2', 'qwen2.block_count': 64, 'qwen2.attention.head_count': 40,
  'qwen2.attention.head_count_kv': 8, 'qwen2.embedding_length': 5120, 'qwen2.context_length': 131072,
}
const GIB = 1024 ** 3

test('the KV cost counts only full-attention layers of hybrid models', () => {
  const hybrid = profileFromModelInfo('qwen35', QWEN35)
  assert.equal(hybrid.fullAttentionLayers, 17)
  assert.equal(hybrid.kvBytesPerToken, 17 * 4 * (256 + 256) * 2)
  assert.equal(hybrid.trainedContext, 262144)
  const dense = profileFromModelInfo('qwen2', QWEN2)
  assert.equal(dense.kvBytesPerToken, 64 * 8 * (128 + 128) * 2)
})

test('the ceiling is the largest tier whose cache fits the memory budget and the model', () => {
  const hybrid = profileFromModelInfo('qwen35', QWEN35)
  assert.equal(sustainableContext(hybrid, 6 * GIB), 65536)      // 69 632 B/jeton : 92 k jetons tiennent
  assert.equal(sustainableContext(hybrid, 24 * GIB), 262144)
  const dense = profileFromModelInfo('qwen2', QWEN2)
  assert.equal(sustainableContext(dense, 6 * GIB), 16384)       // 262 144 B/jeton : 24 k jetons
  assert.equal(sustainableContext(profileFromModelInfo('x', null)), 32768)  // profil inconnu : valeur prudente
})

test('a short conversation goes through untouched in the smallest window', () => {
  const plan = planContext({
    system: { role: 'system', content: 'Tu es Aurora.' },
    history: [{ role: 'user', content: 'Bonjour' }, { role: 'assistant', content: 'Bonjour !' }],
    user: { role: 'user', content: 'Explique les intégrales.' },
    profile: profileFromModelInfo('qwen35', QWEN35),
    budgetBytes: 6 * GIB,
  })
  assert.equal(plan.compactedMessages, 0)
  assert.equal(plan.messages.length, 4)
  assert.equal(plan.window, CONTEXT_TIERS[0])
  assert.equal(plan.ceiling, 65536)
})

test('a long conversation keeps the instructions and the request whole and summarises the oldest turns', () => {
  const system = { role: 'system', content: 'INSTRUCTIONS : réponds en français, cite tes sources.' }
  const user = { role: 'user', content: 'Et donc, quelle est la conclusion ?' }
  const history = []
  for (let i = 0; i < 120; i += 1) {
    history.push({ role: 'user', content: `Question ${i} : ${'détail '.repeat(300)}` })
    history.push({ role: 'assistant', content: `Réponse ${i} : ${'explication '.repeat(500)}` })
  }
  const plan = planContext({ system, history, user, profile: profileFromModelInfo('qwen2', QWEN2), budgetBytes: 6 * GIB, ratio: 3.3 })
  assert.equal(plan.messages[0], system)                               // les instructions restent en tête
  assert.equal(plan.messages.at(-1), user)                             // la demande courante, entière
  assert.ok(plan.compactedMessages > 0)
  assert.equal(plan.messages[1].role, 'system')
  assert.match(plan.messages[1].content, /Résumé abrégé des \d+ message/)
  assert.match(plan.messages.at(-2).content, /^Réponse 119/)            // le dernier échange est gardé tel quel
  assert.ok(plan.estimatedPromptTokens <= plan.ceiling)
  assert.ok(plan.window <= plan.ceiling)
})

test('the characters-per-token ratio follows the counts Ollama really returns', () => {
  const model = `test-${Date.now()}`
  assert.equal(charsPerToken(model), 3.3)
  calibrate(model, 9000, 3000)                                          // 3,0 caractères par jeton mesurés
  assert.equal(charsPerToken(model), 3)
  calibrate(model, 8000, 2000)                                          // nouvelle mesure 4,0 : moyenne glissante
  assert.ok(charsPerToken(model) > 3 && charsPerToken(model) < 4)
})
