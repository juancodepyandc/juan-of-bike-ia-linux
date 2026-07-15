import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildSandboxGcStep,
  collectCodeSandboxGarbage,
  planSandboxGarbageCollection,
} from '../services/codeSandboxGc.ts'

describe('codeSandboxGc', () => {
  test('planSandboxGarbageCollection supprime les sandboxes ages et les sentinelles host', () => {
    const plan = planSandboxGarbageCollection([
      '1700000000000',
      '1700003600000',
      'AURORA_HOST_SENTINEL_tmp_aurora_ws',
      'README',
      'active-lock',
    ], {
      nowMs: 1700090000000,
      maxAgeMs: 24 * 60 * 60 * 1000,
    })

    assert.deepEqual(plan.remove, ['AURORA_HOST_SENTINEL_tmp_aurora_ws', '1700000000000'])
    assert.ok(plan.keep.includes('1700003600000'))
    assert.ok(plan.keep.includes('README'))
    assert.ok(plan.keep.includes('active-lock'))
  })

  test('planSandboxGarbageCollection borne le nombre de sandboxes conserves', () => {
    const plan = planSandboxGarbageCollection([
      '1700000000000',
      '1700000001000',
      '1700000002000',
      '1700000003000',
    ], {
      nowMs: 1700000004000,
      maxAgeMs: 60_000,
      maxEntries: 2,
    })

    assert.deepEqual(plan.remove, ['1700000001000', '1700000000000'])
    assert.deepEqual(plan.keep, ['1700000003000', '1700000002000'])
  })

  test('planSandboxGarbageCollection ne supprime jamais le sandbox actif', () => {
    const plan = planSandboxGarbageCollection([
      '1700000000000',
      '1700000001000',
    ], {
      nowMs: 1700090000000,
      activeName: '1700000000000',
    })

    assert.deepEqual(plan.remove, ['1700000001000'])
    assert.ok(plan.keep.includes('1700000000000'))
  })

  test('collectCodeSandboxGarbage supprime uniquement le plan calcule', async () => {
    const removed: string[] = []
    const result = await collectCodeSandboxGarbage('/tmp/aurora/code-sandbox', {
      nowMs: 1700090000000,
    }, {
      listDir: async () => ['1700000000000', '1700090000000', 'notes'],
      removeDirAll: async (path) => { removed.push(path) },
    })

    assert.deepEqual(result.removed, ['1700000000000'])
    assert.deepEqual(removed, ['/tmp/aurora/code-sandbox/1700000000000'])
    assert.equal(buildSandboxGcStep(result).ok, true)
    assert.match(buildSandboxGcStep(result).output, /removed=1/)
  })
})
