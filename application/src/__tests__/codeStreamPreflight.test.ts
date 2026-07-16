import assert from 'node:assert/strict'
import { afterEach, describe, test } from 'node:test'

import { checkCodeBridgeReady } from '../stores/codeStreamPreflight.ts'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
})

describe('Code stream preflight', () => {
  test('propose une relance portable lorsque le bridge est indisponible', async () => {
    globalThis.fetch = (() => Promise.reject(new Error('ECONNREFUSED'))) as typeof fetch

    const issue = await checkCodeBridgeReady()

    assert.ok(issue)
    assert.match(issue.suggestion, /lanceur de ta plateforme/)
    assert.match(issue.suggestion, /bridge_doctor\.py/)
    assert.doesNotMatch(issue.suggestion, /\.bat\b/i)
  })
})
