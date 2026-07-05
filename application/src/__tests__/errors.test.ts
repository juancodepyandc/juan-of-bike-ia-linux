/**
 * Tests pour utils/errors — extracteur de messages d'erreur résilient + safeParseJson.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { getErrorMessage, toError, safeParseJson } from '../utils/errors.ts'

describe('getErrorMessage', () => {
  test('Error → message extrait', () => {
    assert.equal(getErrorMessage(new Error('oups')), 'oups')
  })

  test('string → string trimmée', () => {
    assert.equal(getErrorMessage('  failure  '), 'failure')
  })

  test('null / undefined → fallback', () => {
    assert.equal(getErrorMessage(null), 'Erreur inconnue.')
    assert.equal(getErrorMessage(undefined), 'Erreur inconnue.')
  })

  test('fallback custom', () => {
    assert.equal(getErrorMessage(null, 'rien à dire'), 'rien à dire')
  })

  test('object avec .message', () => {
    assert.ok(getErrorMessage({ message: 'API down' }).includes('API down'))
  })

  test('object avec .error', () => {
    assert.ok(getErrorMessage({ error: 'unauthorized' }).includes('unauthorized'))
  })

  test('object avec .detail nested', () => {
    assert.ok(getErrorMessage({ detail: { message: 'nested' } }).includes('nested'))
  })

  test('Array d erreurs → concaténation', () => {
    const msg = getErrorMessage([new Error('a'), new Error('b')])
    assert.ok(msg.includes('a'))
    assert.ok(msg.includes('b'))
  })

  test('retire "Error:" préfixe', () => {
    assert.equal(getErrorMessage('Error: payload'), 'payload')
  })

  test('messages dupliqués → dédoublonnage', () => {
    const msg = getErrorMessage([new Error('same'), 'same'])
    // ne doit pas avoir "same | same"
    const parts = msg.split('|').map(s => s.trim())
    assert.equal(new Set(parts).size, parts.length)
  })

  test('event.listen not allowed → message Tauri friendly', () => {
    const msg = getErrorMessage('event.listen not allowed for window')
    assert.ok(msg.includes('Tauri'))
  })

  test('timeout pendant la generation image → préfixé', () => {
    const msg = getErrorMessage('timeout pendant la generation image après 60s')
    assert.ok(msg.startsWith('Le rendu image a depasse'))
  })

  test('whitespace réduit', () => {
    assert.equal(getErrorMessage('multi   space   word'), 'multi space word')
  })
})

describe('toError', () => {
  test('Error → renvoie tel quel', () => {
    const e = new Error('original')
    assert.equal(toError(e), e)
  })

  test('string → wrap en Error', () => {
    const e = toError('boom')
    assert.ok(e instanceof Error)
    assert.equal(e.message, 'boom')
  })

  test('null → Error avec fallback', () => {
    const e = toError(null, 'no detail')
    assert.equal(e.message, 'no detail')
  })
})

describe('safeParseJson', () => {
  function mockResponse(opts: { ok?: boolean; status?: number; text: string }): Response {
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      text: async () => opts.text,
    } as Response
  }

  test('JSON valide → parse', async () => {
    const r = mockResponse({ text: '{"hello":"world"}' })
    const result = await safeParseJson<{ hello: string }>(r)
    assert.equal(result.hello, 'world')
  })

  test('réponse vide → {}', async () => {
    const r = mockResponse({ text: '' })
    const result = await safeParseJson(r)
    assert.deepEqual(result, {})
  })

  test('réponse HTML → throw avec contexte', async () => {
    const r = mockResponse({ text: '<!DOCTYPE html><html>...</html>' })
    await assert.rejects(safeParseJson(r), /HTML au lieu de JSON/)
  })

  test('status >= 400 → throw avec status', async () => {
    const r = mockResponse({ ok: false, status: 500, text: 'internal error' })
    await assert.rejects(safeParseJson(r), /500/)
  })

  test('JSON invalide → throw', async () => {
    const r = mockResponse({ text: 'not-json-at-all' })
    await assert.rejects(safeParseJson(r), /non-JSON/)
  })

  test('label dans le message d erreur', async () => {
    const r = mockResponse({ ok: false, status: 404, text: 'not found' })
    await assert.rejects(safeParseJson(r, 'Voice TTS'), /Voice TTS/)
  })
})
