/**
 * Tests pour utils/modelContext — limites contextuelles Ollama par modèle.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getModelContextLimit, getContextUsage } from '../utils/modelContext.ts'

describe('getModelContextLimit', () => {
  test('vide → fallback 8192', () => {
    assert.equal(getModelContextLimit(''), 8192)
  })

  test('modèle inconnu → fallback', () => {
    assert.equal(getModelContextLimit('totally-unknown-model:xl'), 8192)
  })

  test('llama4:scout → 128000', () => {
    assert.equal(getModelContextLimit('llama4:scout'), 128000)
  })

  test('llama-3 / llama3 → 128000', () => {
    assert.equal(getModelContextLimit('llama-3.1:70b'), 128000)
    assert.equal(getModelContextLimit('llama3:8b'), 128000)
  })

  test('qwen3.8 → 262144', () => {
    assert.equal(getModelContextLimit('orcarouter/Qwen3.8-27B-Uncensored'), 262144)
    assert.equal(getModelContextLimit('qwen3.8:27b'), 262144)
  })

  test('qwen3 → 32768', () => {
    assert.equal(getModelContextLimit('qwen3:30b'), 32768)
  })

  test('qwen3-coder → 32768', () => {
    assert.equal(getModelContextLimit('qwen3-coder:32b'), 32768)
  })

  test('mistral / nemo → 32768', () => {
    assert.equal(getModelContextLimit('mistral:7b'), 32768)
    assert.equal(getModelContextLimit('mistral-nemo:12b'), 32768)
  })

  test('gemma → 8192', () => {
    assert.equal(getModelContextLimit('gemma2:9b'), 8192)
  })

  test('phi-3 → 16384', () => {
    assert.equal(getModelContextLimit('phi-3:14b'), 16384)
    assert.equal(getModelContextLimit('phi3'), 16384)
  })

  test('deepseek → 65536', () => {
    assert.equal(getModelContextLimit('deepseek-coder-v2'), 65536)
  })

  test('codestral → 32768', () => {
    assert.equal(getModelContextLimit('codestral:22b'), 32768)
  })

  test('case insensitive', () => {
    assert.equal(getModelContextLimit('LLAMA3:8B'), 128000)
    assert.equal(getModelContextLimit('Qwen3:32B'), 32768)
  })
})

describe('getContextUsage', () => {
  test('thread vide → 0 tokens', () => {
    const u = getContextUsage('llama3', 0)
    assert.equal(u.tokens, 0)
    assert.equal(u.ratio, 0)
    assert.equal(u.level, 'safe')
  })

  test('ratio = tokens / limit', () => {
    // 16384 chars ≈ 4096 tokens, limite 32768 (qwen3) → ratio 0.125
    const u = getContextUsage('qwen3:32b', 16384)
    assert.equal(u.tokens, 4096)
    assert.equal(u.limit, 32768)
    assert.ok(Math.abs(u.ratio - 0.125) < 0.001)
    assert.equal(u.level, 'safe')
  })

  test('level safe < 0.75', () => {
    const u = getContextUsage('llama3', 8192 * 4 * 0.5) // 50% of 8192
    assert.equal(u.level, 'safe')
  })

  test('level warn entre 0.75 et 0.95', () => {
    const limit = getModelContextLimit('gemma2') // 8192
    const chars = Math.floor(limit * 4 * 0.85) // 85%
    const u = getContextUsage('gemma2', chars)
    assert.equal(u.level, 'warn')
  })

  test('level danger > 0.95', () => {
    const limit = getModelContextLimit('gemma2') // 8192
    const chars = Math.floor(limit * 4 * 0.98) // 98%
    const u = getContextUsage('gemma2', chars)
    assert.equal(u.level, 'danger')
  })

  test('1 token = 4 chars (approximation)', () => {
    const u = getContextUsage('llama3', 400)
    assert.equal(u.tokens, 100)
  })
})
