/**
 * v77zp: validate motion pipeline orchestration (testable units).
 *
 * The bridge / Tauri write paths can't be exercised in node --test, so the
 * coverage focuses on:
 *   - computeMotionJsonPath() conventions
 *   - resolveMotionFromPrompt() decision tree (parsed vs preset fallback)
 *
 * Run: node --experimental-strip-types src/__tests__/motionPipeline.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  computeMotionJsonPath,
  resolveMotionFromPrompt,
} from '../services/motionPipeline.ts'

describe('computeMotionJsonPath — sidecar path convention', () => {
  test('joins outputDir + runId with _motion.json suffix', () => {
    const p = computeMotionJsonPath('/tmp/aurora/runs', 'r123')
    assert.equal(p, '/tmp/aurora/runs/r123_motion.json')
  })

  test('normalizes Windows backslashes to forward slashes', () => {
    const p = computeMotionJsonPath('C:\\tmp\\aurora', 'job_42')
    assert.equal(p, 'C:/tmp/aurora/job_42_motion.json')
  })

  test('strips trailing slashes in outputDir', () => {
    const p = computeMotionJsonPath('/var/runs/', 'x')
    assert.equal(p, '/var/runs/x_motion.json')
  })

  test('sanitizes runId — disallowed chars become underscores', () => {
    const p = computeMotionJsonPath('/tmp', 'a/b\\c d')
    assert.match(p, /a_b_c_d_motion\.json$/)
  })

  test('throws on empty outputDir', () => {
    assert.throws(() => computeMotionJsonPath('', 'r1'), /required/)
  })

  test('throws on empty runId', () => {
    assert.throws(() => computeMotionJsonPath('/tmp', ''), /required/)
  })
})

describe('resolveMotionFromPrompt — parsed wins over preset fallback', () => {
  test('parsed sequence wins over preset', () => {
    const r = resolveMotionFromPrompt(
      'le perso marche puis saute',
      { subjectKind: 'character', systemClass: 'generic' },
    )
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.source, 'parsed')
      assert.equal(r.descriptor.source, 'custom')
    }
  })

  test('non-motion prompt → falls back to first preset for intent', () => {
    const r = resolveMotionFromPrompt(
      'a beautiful elf warrior with intricate armor',
      { subjectKind: 'character', systemClass: 'generic' },
    )
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.source, 'preset')
      assert.equal(r.descriptor.source, 'preset')
      assert.match(r.descriptor.id, /character\./)
    }
  })

  test('object subject without system class → no presets, ok=false', () => {
    const r = resolveMotionFromPrompt(
      'a generic object',
      { subjectKind: 'object', systemClass: 'generic' },
    )
    assert.equal(r.ok, false)
    if (!r.ok) {
      assert.match(r.reason, /no preset/i)
    }
  })

  test('mechanism gear_train → mechanism preset', () => {
    const r = resolveMotionFromPrompt(
      'a gear train with two gears',
      { subjectKind: 'mechanism', systemClass: 'gear_train' },
    )
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.source, 'preset')
      assert.match(r.descriptor.id, /gear_mesh|character\./)
    }
  })

  test('mechanism prompt parsed → custom wins', () => {
    const r = resolveMotionFromPrompt(
      'engrenage qui tourne puis charniere qui s ouvre',
      { subjectKind: 'mechanism', systemClass: 'gear_train' },
    )
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.source, 'parsed')
    }
  })

  test('vehicle prompt non-parseable → vehicle preset', () => {
    const r = resolveMotionFromPrompt(
      'a sleek sports car',
      { subjectKind: 'vehicle', systemClass: 'generic' },
    )
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.source, 'preset')
      assert.match(r.descriptor.id, /vehicle\./)
    }
  })
})
