/**
 * Tests for the multi-pass critique loop + framework classifier.
 * Run: node --experimental-strip-types --test src/__tests__/codeMultiPassCritique.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildReport,
  classifyFramework,
  DEFAULT_THRESHOLDS,
  runCritiqueLoop,
} from '../services/codeMultiPassCritique.ts'
import type { CodeProject, CritiqueAxis, CritiqueReport } from '../services/codeMultiPassCritique.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const fakeIntent = {} as CodeIntent

const makeProject = (i = 0): CodeProject => ({
  generationId: `gen-${i}`,
  files: [{ name: 'index.tsx', language: 'tsx', content: 'export const X = 1\n'.repeat(i + 1) }],
})

describe('buildReport', () => {
  test('default axes all 1 → overall 1', () => {
    const r = buildReport({})
    assert.equal(r.overallScore, 1)
    assert.equal(r.hasBlocker, false)
  })

  test('block issue flags hasBlocker', () => {
    const r = buildReport({ compile: 0 }, [
      { axis: 'compile', severity: 'block', message: 'tsc fail' },
    ])
    assert.equal(r.hasBlocker, true)
  })

  test('weighted mean depends on axis weight', () => {
    const r = buildReport({ compile: 0, perf: 0.5 })
    // compile is weighted 2, perf 0.6. So overall < 1 but not too low.
    assert.ok(r.overallScore < 1)
    assert.ok(r.overallScore > 0)
  })

  test('issues sorted by severity desc', () => {
    const r = buildReport({}, [
      { axis: 'lint', severity: 'info', message: 'i' },
      { axis: 'compile', severity: 'block', message: 'b' },
      { axis: 'tests', severity: 'warn', message: 'w' },
    ])
    assert.equal(r.issues[0].severity, 'block')
    assert.equal(r.issues[r.issues.length - 1].severity, 'info')
  })
})

describe('runCritiqueLoop', () => {
  test('stops on threshold-met after first pass', async () => {
    const critic = async (): Promise<CritiqueReport> => buildReport({})
    const patcher = async (p: CodeProject) => p
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher)
    assert.equal(res.passesUsed, 1)
    assert.equal(res.thresholdMet, true)
    assert.equal(res.stopReason, 'threshold-met')
  })

  test('iterates up to max passes if never satisfied', async () => {
    const critic = async (): Promise<CritiqueReport> => buildReport({ compile: 0.5 })
    const patcher = async (p: CodeProject) => p
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, { maxPasses: 3 })
    assert.equal(res.passesUsed, 3)
    assert.equal(res.stopReason, 'max-passes')
  })

  test('patches between passes (project mutates)', async () => {
    let calls = 0
    const critic = async (p: CodeProject): Promise<CritiqueReport> => {
      calls += 1
      // First pass fails, second pass passes (simulate patcher succeeded).
      return calls === 1 ? buildReport({ compile: 0.3 }) : buildReport({})
    }
    const patcher = async (p: CodeProject) => ({ ...p, files: [{ ...p.files[0], content: 'fixed' }] })
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, { maxPasses: 3 })
    assert.equal(res.passesUsed, 2)
    assert.equal(res.finalProject.files[0].content, 'fixed')
  })

  test('abort signal short-circuits', async () => {
    const ctrl = new AbortController()
    ctrl.abort()
    const critic = async (): Promise<CritiqueReport> => buildReport({ compile: 0 })
    const patcher = async (p: CodeProject) => p
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, { signal: ctrl.signal })
    assert.equal(res.stopReason, 'aborted')
  })

  test('emits per-pass events', async () => {
    const events: number[] = []
    const critic = async (): Promise<CritiqueReport> => buildReport({ compile: 0.5 })
    const patcher = async (p: CodeProject) => p
    await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, {
      maxPasses: 2,
      onPass: (e) => events.push(e.pass),
    })
    assert.deepEqual(events, [1, 2])
  })

  test('stops on no-improvement when patcher regresses 2 passes', async () => {
    let pass = 0
    const critic = async (): Promise<CritiqueReport> => {
      pass += 1
      const scores: Partial<Record<CritiqueAxis, number>> = pass === 1
        ? { compile: 0.7 }
        : pass === 2 ? { compile: 0.5 } : { compile: 0.3 }
      return buildReport(scores)
    }
    const patcher = async (p: CodeProject) => p
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, { maxPasses: 5 })
    assert.equal(res.stopReason, 'no-improvement')
    assert.ok(res.passesUsed < 5)
  })

  test('blockers prevent threshold-met even with perfect scores elsewhere', async () => {
    const critic = async (): Promise<CritiqueReport> => buildReport({}, [
      { axis: 'security', severity: 'block', message: 'eval()' },
    ])
    const patcher = async (p: CodeProject) => p
    const res = await runCritiqueLoop(makeProject(), fakeIntent, critic, patcher, { maxPasses: 2 })
    assert.equal(res.thresholdMet, false)
  })
})

describe('classifyFramework', () => {
  test('"todo app react vite" → react-vite', () => {
    const r = classifyFramework('todo app en react avec vite')
    assert.equal(r.bucket, 'react-vite')
  })

  test('"page web simple html" → static-html', () => {
    const r = classifyFramework('page web simple en HTML')
    assert.equal(r.bucket, 'static-html')
  })

  test('"esp32 microcontroleur" → arduino-c', () => {
    const r = classifyFramework('programme pour ESP32 microcontroleur')
    assert.equal(r.bucket, 'arduino-c')
  })

  test('"fastapi endpoint" → python-fastapi', () => {
    const r = classifyFramework('crée un endpoint FastAPI')
    assert.equal(r.bucket, 'python-fastapi')
  })

  test('"scène three.js webgl" → three-scene', () => {
    const r = classifyFramework('une scène Three.js avec WebGL')
    assert.equal(r.bucket, 'three-scene')
  })

  test('fallback to static-html on unknown', () => {
    const r = classifyFramework('zorglub barbatruc')
    assert.equal(r.bucket, 'static-html')
    assert.ok(r.confidence <= 0.3)
  })

  test('confidence drops when ambiguous', () => {
    const r = classifyFramework('react ou vue ?')
    assert.ok(r.confidence < 0.9)
  })

  test('thresholds defaults sane', () => {
    assert.ok(DEFAULT_THRESHOLDS.overall > 0.8)
    assert.ok((DEFAULT_THRESHOLDS.required.compile ?? 0) === 1)
  })
})
