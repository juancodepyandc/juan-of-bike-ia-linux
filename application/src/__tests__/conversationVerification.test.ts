import { test } from 'node:test'
import assert from 'node:assert/strict'
import { normalizeVerification, verifyRefinedResponse } from '../services/conversationVerification.ts'

const review = { score: 71, confidence: 68, verdict: 'refine', summary: 'Needs correction.' }

test('incomplete or malformed judgments never manufacture a score', () => {
  for (const input of [null, {}, { score: 95 }, { ...review, confidence: NaN }, { ...review, verdict: 'unknown' }, { ...review, verified: false }]) {
    const result = normalizeVerification(input)
    assert.equal(result.verified, false)
    assert.equal(result.score, 0)
    assert.equal(result.confidence, 0)
  }
})

test('valid judgments preserve measured scores and sanitize optional fields', () => {
  const result = normalizeVerification({ ...review, summary: {}, strengths: ['clear', 5], corrections: null })
  assert.equal(result.score, 71)
  assert.equal(result.confidence, 68)
  assert.equal(result.verified, true)
  assert.deepEqual(result.strengths, ['clear'])
})

test('a revision receives only the score assigned to the revised text', async () => {
  let checked = ''
  const result = await verifyRefinedResponse('Draft', normalizeVerification(review), async () => 'Revised', async (text) => {
    checked = text
    return { score: 63, confidence: 60, verdict: 'refine' }
  })
  assert.equal(checked, 'Revised')
  assert.equal(result.finalText, 'Revised')
  assert.equal(result.verification.score, 63)
  assert.equal(result.verification.verdict, 'refine')
})

test('an unreadable second judgment leaves the revised answer unverified', async () => {
  const result = await verifyRefinedResponse('Draft', normalizeVerification(review), async () => 'Revised', async () => ({}))
  assert.equal(result.verification.verified, false)
  assert.equal(result.verification.score, 0)
})

test('an empty or unchanged revision preserves the original evaluation', async () => {
  const original = normalizeVerification(review)
  for (const revision of ['', '   ', 'Draft']) {
    const result = await verifyRefinedResponse('Draft', original, async () => revision, async () => assert.fail('unexpected verification'))
    assert.equal(result.finalText, 'Draft')
    assert.equal(result.verification, original)
  }
})
