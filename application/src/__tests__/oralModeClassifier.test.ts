/**
 * Tests pour services/oralModeClassifier — classifieur LLM oral vs écrit BAC.
 */
import { test, describe, before, after } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyOralMode,
  classificationToPromptBlock,
  type OralClassification,
} from '../services/oralModeClassifier.ts'

// Stub global.fetch pour les tests (le service appelle fetch())
const realFetch = globalThis.fetch
let fetchMock: ((url: any, init?: any) => Promise<any>) | null = null

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
})

after(() => {
  globalThis.fetch = realFetch
})

function mockLLM(content: string) {
  fetchMock = async () => ({
    ok: true,
    json: async () => ({ message: { content } }),
  })
}

function mockFetchError() {
  fetchMock = async () => { throw new Error('network down') }
}

describe('classifyOralMode — fallback paths', () => {
  test('prompt + sample vides → fallback français écrit', async () => {
    fetchMock = null
    const r = await classifyOralMode({ userPrompt: '', uploadedTextSample: '' })
    assert.equal(r.is_oral, false)
    assert.equal(r.language, 'français')
    assert.equal(r.format, 'written')
    assert.equal(r.fallback, true)
  })

  test('LLM erreur réseau → fallback', async () => {
    mockFetchError()
    const r = await classifyOralMode({ userPrompt: 'oral en anglais', uploadedTextSample: '' })
    assert.equal(r.fallback, true)
    assert.equal(r.is_oral, false)
  })

  test('LLM JSON invalide → fallback', async () => {
    mockLLM('not a JSON at all')
    const r = await classifyOralMode({ userPrompt: 'oral 10 min', uploadedTextSample: '' })
    assert.equal(r.fallback, true)
  })
})

describe('classifyOralMode — parsing LLM réponse', () => {
  test('JSON valide oral anglais mixed → parsé correctement', async () => {
    mockLLM('{"is_oral":true,"language":"anglais","format":"mixed","duration_min":10,"inverse_language":false,"reasoning":"oral mixte explicite"}')
    const r = await classifyOralMode({ userPrompt: 'oral anglais 10 min', uploadedTextSample: '' })
    assert.equal(r.is_oral, true)
    assert.equal(r.language, 'anglais')
    assert.equal(r.format, 'mixed')
    assert.equal(r.duration_min, 10)
    assert.equal(r.inverse_language, false)
  })

  test('JSON entouré de markdown fences → parsé', async () => {
    mockLLM('```json\n{"is_oral":true,"language":"russe","format":"full","duration_min":8,"inverse_language":false,"reasoning":"oral russe"}\n```')
    const r = await classifyOralMode({ userPrompt: 'oral russe', uploadedTextSample: '' })
    assert.equal(r.is_oral, true)
    assert.equal(r.language, 'russe')
  })

  test('ISO code "en" normalisé → "anglais"', async () => {
    mockLLM('{"is_oral":true,"language":"en","format":"full","duration_min":10,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.equal(r.language, 'anglais')
  })

  test('ISO code "ja" → "japonais"', async () => {
    mockLLM('{"is_oral":true,"language":"ja","format":"full","duration_min":5,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.equal(r.language, 'japonais')
  })

  test('matière confondue "philo" → ramené à "français"', async () => {
    mockLLM('{"is_oral":true,"language":"philosophie","format":"full","duration_min":20,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'grand oral philo', uploadedTextSample: '' })
    assert.equal(r.language, 'français')
  })

  test('format invalide → "written"', async () => {
    mockLLM('{"is_oral":false,"language":"français","format":"bogus_format","duration_min":0,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.equal(r.format, 'written')
  })

  test('duration_min clampée [0..180]', async () => {
    mockLLM('{"is_oral":true,"language":"français","format":"full","duration_min":9999,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.ok(r.duration_min <= 180)
  })

  test('cohérence : is_oral=true + format="written" → format upgrade "full"', async () => {
    mockLLM('{"is_oral":true,"language":"français","format":"written","duration_min":10,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.equal(r.format, 'full')
  })

  test('cohérence : is_oral=false + format="full" → is_oral upgrade true', async () => {
    mockLLM('{"is_oral":false,"language":"français","format":"full","duration_min":10,"inverse_language":false,"reasoning":"x"}')
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.equal(r.is_oral, true)
  })

  test('inverse_language=true conservé', async () => {
    mockLLM('{"is_oral":false,"language":"japonais","format":"written","duration_min":0,"inverse_language":true,"reasoning":"traduction JA→FR"}')
    const r = await classifyOralMode({ userPrompt: 'traduis ce JP', uploadedTextSample: '' })
    assert.equal(r.inverse_language, true)
  })
})

describe('classifyOralMode — robustesse', () => {
  test('reasoning très long tronqué à 300 chars', async () => {
    const long = 'X'.repeat(500)
    mockLLM(`{"is_oral":true,"language":"français","format":"full","duration_min":10,"inverse_language":false,"reasoning":"${long}"}`)
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' })
    assert.ok(r.reasoning.length <= 300)
  })

  test('AbortSignal annule l appel', async () => {
    fetchMock = (_url, init) => new Promise((_, reject) => {
      const sig = (init as any)?.signal
      if (sig?.aborted) reject(new Error('aborted'))
      else sig?.addEventListener('abort', () => reject(new Error('aborted')))
    })
    const ctrl = new AbortController()
    ctrl.abort()
    const r = await classifyOralMode({ userPrompt: 'x', uploadedTextSample: '' }, { signal: ctrl.signal })
    assert.equal(r.fallback, true)
  })
})

describe('classificationToPromptBlock', () => {
  function makeCls(over: Partial<OralClassification> = {}): OralClassification {
    return {
      is_oral: true,
      language: 'anglais',
      format: 'full',
      duration_min: 10,
      inverse_language: false,
      reasoning: 'test',
      ...over,
    }
  }

  test('mode écrit → bloc court mentionne ÉCRIT', () => {
    const block = classificationToPromptBlock(makeCls({ is_oral: false, format: 'written' }))
    assert.ok(block.includes('écrit'))
    assert.ok(!block.includes('MODE ORAL'))
  })

  test('mode oral full → bloc complet avec consignes', () => {
    const block = classificationToPromptBlock(makeCls())
    assert.ok(block.includes('MODE ORAL'))
    assert.ok(block.includes('anglais') || block.includes('ANGLAIS'))
    assert.ok(block.includes('10 min'))
  })

  test('mode mixed → mention questions_relance', () => {
    const block = classificationToPromptBlock(makeCls({ format: 'mixed' }))
    assert.ok(block.includes('questions_relance'))
  })

  test('mode russe → mention RUSSE en upper', () => {
    const block = classificationToPromptBlock(makeCls({ language: 'russe' }))
    assert.ok(block.includes('RUSSE'))
  })

  test('duration_min=0 → fallback à 10 dans le bloc', () => {
    const block = classificationToPromptBlock(makeCls({ duration_min: 0 }))
    assert.ok(block.includes('10'))
  })

  test('bloc terminé par "=== FIN ANALYSE ==="', () => {
    const block = classificationToPromptBlock(makeCls())
    assert.ok(block.trim().endsWith('=== FIN ANALYSE ==='))
  })
})
