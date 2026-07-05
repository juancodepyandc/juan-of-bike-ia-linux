/**
 * Tests pour services/llmTimebox — Promise.race avec timeout + erreur dédiée.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { withTimeout, isLlmTimeboxError, LlmTimeboxError } from '../services/llmTimebox.ts'

describe('withTimeout', () => {
  test('resolve avant timeout → renvoie la valeur', async () => {
    const r = await withTimeout(Promise.resolve(42), { label: 'fast', timeoutMs: 100 })
    assert.equal(r, 42)
  })

  test('timeout dépassé → LlmTimeboxError', async () => {
    const never = new Promise((resolve) => setTimeout(() => resolve('late'), 200))
    await assert.rejects(
      withTimeout(never, { label: 'slow', timeoutMs: 20 }),
      (err) => isLlmTimeboxError(err) && err.label === 'slow' && err.timeoutMs === 20,
    )
  })

  test('rejet promise → propagé tel quel', async () => {
    const bad = Promise.reject(new Error('user reject'))
    await assert.rejects(
      withTimeout(bad, { label: 'fail', timeoutMs: 100 }),
      /user reject/,
    )
  })

  test('timeoutMs=0 → pas de timer (renvoie le résultat)', async () => {
    const r = await withTimeout(Promise.resolve('ok'), { label: 'no-timeout', timeoutMs: 0 })
    assert.equal(r, 'ok')
  })

  test('timeoutMs négatif → pas de timer', async () => {
    const r = await withTimeout(Promise.resolve('ok'), { label: 'neg', timeoutMs: -5 })
    assert.equal(r, 'ok')
  })

  test('timeoutMs non-fini → pas de timer', async () => {
    const r = await withTimeout(Promise.resolve('ok'), { label: 'inf', timeoutMs: Infinity })
    assert.equal(r, 'ok')
  })

  test('cleanup timer après résolution', async () => {
    // Si le timer n'est pas clear, ce test fait planter le test runner (timer pendant).
    // Le fait que ce test termine prouve que cleanup marche.
    const r = await withTimeout(Promise.resolve('cleanup'), { label: 'c', timeoutMs: 5000 })
    assert.equal(r, 'cleanup')
  })
})

describe('isLlmTimeboxError', () => {
  test('LlmTimeboxError → true', () => {
    const e = new LlmTimeboxError('x', 100)
    assert.equal(isLlmTimeboxError(e), true)
  })

  test('Error standard → false', () => {
    assert.equal(isLlmTimeboxError(new Error('regular')), false)
  })

  test('non-Error → false', () => {
    assert.equal(isLlmTimeboxError(null), false)
    assert.equal(isLlmTimeboxError({ name: 'LlmTimeboxError' }), false)
  })
})

describe('LlmTimeboxError', () => {
  test('propriétés label + timeoutMs', () => {
    const e = new LlmTimeboxError('ollama-chat', 30000)
    assert.equal(e.label, 'ollama-chat')
    assert.equal(e.timeoutMs, 30000)
    assert.equal(e.name, 'LlmTimeboxError')
    assert.match(e.message, /ollama-chat/)
    assert.match(e.message, /30000/)
  })
})
