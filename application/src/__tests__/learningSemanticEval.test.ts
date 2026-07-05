/**
 * Tests pour services/learningSemanticEval — évaluateur sémantique LLM
 * (avec fallback heuristic bag-of-words).
 */
import { test, describe, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { evaluateAnswerSemantically } from '../services/learningSemanticEval.ts'

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
  fetchMock = async () => ({ ok: true, json: async () => ({ message: { content } }) })
}

function mockFetchError() {
  fetchMock = async () => { throw new Error('network down') }
}

describe('evaluateAnswerSemantically — quick paths', () => {
  test('réponse vide → score 0', async () => {
    fetchMock = null
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'la France est une république', userAnswer: '',
    })
    assert.equal(r.score, 0)
    assert.equal(r.ok, false)
  })

  test('réponse whitespace → score 0', async () => {
    fetchMock = null
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'attendu', userAnswer: '   \n  ',
    })
    assert.equal(r.score, 0)
  })

  test('match littéral exact → score 100 (pas de LLM)', async () => {
    fetchMock = null  // Personne ne devrait être appelé
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'Paris', userAnswer: 'Paris',
    })
    assert.equal(r.score, 100)
    assert.equal(r.ok, true)
  })

  test('match littéral ignore accents/casse/ponctuation', async () => {
    fetchMock = null
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'République Française', userAnswer: 'republique francaise',
    })
    assert.equal(r.score, 100)
  })

  test('match littéral ignore espaces multiples', async () => {
    fetchMock = null
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'mot1 mot2', userAnswer: 'mot1   mot2',
    })
    assert.equal(r.score, 100)
  })
})

describe('evaluateAnswerSemantically — LLM JSON parsing', () => {
  test('JSON valide → score + feedback parsés', async () => {
    mockLLM('{"score": 85, "feedback": "Bien", "weak_concepts": ["x"]}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'attendu', userAnswer: 'différent mais correct',
    })
    assert.equal(r.score, 85)
    assert.equal(r.ok, true)
    assert.equal(r.feedback, 'Bien')
    assert.deepEqual(r.weakConcepts, ['x'])
  })

  test('score clampé [0..100]', async () => {
    mockLLM('{"score": 150, "feedback": "F", "weak_concepts": []}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.equal(r.score, 100)
  })

  test('score négatif → clampé à 0', async () => {
    mockLLM('{"score": -10, "feedback": "F", "weak_concepts": []}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.equal(r.score, 0)
  })

  test('JSON dans markdown fence → extrait', async () => {
    mockLLM('```json\n{"score": 75, "feedback": "OK", "weak_concepts": []}\n```')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.equal(r.score, 75)
  })

  test('score=70 exactement → ok=true', async () => {
    mockLLM('{"score": 70, "feedback": "limite", "weak_concepts": []}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.equal(r.ok, true)
  })

  test('score=69 → ok=false', async () => {
    mockLLM('{"score": 69, "feedback": "limite", "weak_concepts": []}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.equal(r.ok, false)
  })

  test('feedback trop long tronqué à 400', async () => {
    const longFeedback = 'X'.repeat(600)
    mockLLM(`{"score": 50, "feedback": "${longFeedback}", "weak_concepts": []}`)
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.ok(r.feedback.length <= 400)
  })

  test('weak_concepts limité à 5', async () => {
    const concepts = Array.from({ length: 10 }, (_, i) => `"c${i}"`).join(',')
    mockLLM(`{"score": 50, "feedback": "f", "weak_concepts": [${concepts}]}`)
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.ok(r.weakConcepts.length <= 5)
  })

  test('weak_concepts non-string filtrés', async () => {
    mockLLM('{"score": 50, "feedback": "f", "weak_concepts": ["valid", 42, true, "autre"]}')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'a', userAnswer: 'b',
    })
    assert.deepEqual(r.weakConcepts, ['valid', 'autre'])
  })
})

describe('evaluateAnswerSemantically — fallback heuristic', () => {
  test('LLM erreur réseau → fallback bag-of-words', async () => {
    mockFetchError()
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'la photosynthese chlorophylle plante',
      userAnswer: 'photosynthese plante chlorophylle',
    })
    assert.ok(r.error)
    assert.ok(r.score >= 70)  // bag-of-words devrait être > 70 (overlap fort)
  })

  test('fallback indique source dans feedback', async () => {
    mockFetchError()
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'attendu mot', userAnswer: 'totalement different',
    })
    assert.ok(r.feedback.includes('eval LLM indisponible') || r.feedback.includes('LLM'))
  })

  test('LLM HTTP non-ok → fallback', async () => {
    fetchMock = async () => ({ ok: false, status: 500, json: async () => ({}) })
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'photosynthese plante eau', userAnswer: 'lumiere oxygene',
    })
    assert.ok(r.error)
    assert.ok(r.error.includes('500'))
  })

  test('LLM JSON non parsable → fallback', async () => {
    mockLLM('pas du json du tout')
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'attendu mot', userAnswer: 'mot attendu test',
    })
    assert.ok(r.error)
    assert.equal(r.error, 'parse-fail')
  })

  test('fallback bag-of-words : 0 overlap → score bas', async () => {
    mockFetchError()
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'photosynthese chlorophylle',
      userAnswer: 'azure cloudflare',
    })
    assert.ok(r.score < 30)
  })

  test('fallback : expected vide → score 50 par défaut', async () => {
    mockFetchError()
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: '', userAnswer: 'truc',
    })
    // expected="" → après norm aucun word ≥3 chars → expWords vide → score 50
    assert.equal(r.score, 50)
  })
})

describe('evaluateAnswerSemantically — timeout override', () => {
  test('timeoutMs très court → fallback réseau via timeout', async () => {
    // Fetch ne résoudra jamais → abort via timeoutMs
    fetchMock = (_url, init) => new Promise((_, reject) => {
      const sig = (init as any)?.signal
      sig?.addEventListener('abort', () => reject(new Error('aborted')))
    })
    const r = await evaluateAnswerSemantically({
      question: 'Q', expected: 'photosynthese plante eau', userAnswer: 'lumiere oxygene',
    }, { timeoutMs: 50 })
    assert.ok(r.error)
  })
})
