/**
 * Tests for the Cowork plan estimator + saved plans store.
 * Run: node --experimental-strip-types --test src/__tests__/coworkPlanEstimator.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  addSavedPlan,
  bumpSavedPlanUsage,
  createSavedPlanIndex,
  dryRunPlan,
  estimateAction,
  estimatePlan,
  LOCAL_OLLAMA_COST_MODEL,
  removeSavedPlan,
  searchSavedPlans,
} from '../services/coworkPlanEstimator.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

const plan = (actions: CoworkAction[]): CoworkPlan => ({
  reasoning: 'r', actions, expectedOutcome: 'o',
})

describe('estimateAction', () => {
  test('read_file cheap and safe', () => {
    const c = estimateAction({ kind: 'read_file', path: 'a.txt' })
    assert.equal(c.usd, 0)
    assert.ok(c.riskScore < 0.2)
  })

  test('shell rm -rf flagged as dangerous', () => {
    const c = estimateAction({ kind: 'shell', command: 'rm -rf /', args: [] })
    assert.ok(c.riskScore >= 0.9, `risk ${c.riskScore}`)
    assert.ok(c.notes.some((n) => n.toLowerCase().includes('dangereuse')))
  })

  test('write outside workspace bumps risk', () => {
    const safe = estimateAction({ kind: 'write_file', path: 'src/file.ts', content: 'x' })
    const risky = estimateAction({ kind: 'write_file', path: '/etc/passwd', content: 'x' })
    assert.ok(risky.riskScore > safe.riskScore)
  })

  test('fetch localhost is cheaper than fetch external', () => {
    const local = estimateAction({ kind: 'fetch', url: 'http://localhost:3001/api' })
    const ext = estimateAction({ kind: 'fetch', url: 'https://api.openai.com/v1' })
    assert.equal(local.usd, 0)
    assert.ok(ext.usd > 0)
  })

  test('voice_speak duration scales with text length', () => {
    const short = estimateAction({ kind: 'voice_speak', text: 'salut' })
    const long = estimateAction({ kind: 'voice_speak', text: 'a'.repeat(150) })
    assert.ok(long.durationMs > short.durationMs)
  })

  test('local Ollama cost model produces 0 USD on LLM ops', () => {
    const c = estimateAction({ kind: 'think_long', topic: 't', prompt: 'p'.repeat(500) }, LOCAL_OLLAMA_COST_MODEL)
    assert.equal(c.usd, 0)
  })
})

describe('estimatePlan', () => {
  test('aggregates across action list', () => {
    const p = plan([
      { kind: 'read_file', path: 'a' },
      { kind: 'read_file', path: 'b' },
      { kind: 'finish', summary: 'fini' },
    ])
    const est = estimatePlan(p)
    assert.equal(est.actionCount, 3)
    assert.ok(est.totalDurationMs > 0)
    assert.equal(est.byCategory.read, 2)
  })

  test('needsConfirmation when ≥ 6 steps', () => {
    const p = plan(Array.from({ length: 7 }, (_, i) => ({ kind: 'read_file', path: `f${i}` })))
    const est = estimatePlan(p)
    assert.equal(est.needsConfirmation, true)
  })

  test('needsConfirmation when worst risk ≥ 0.7', () => {
    const p = plan([{ kind: 'shell', command: 'rm -rf /tmp', args: [] }])
    const est = estimatePlan(p)
    assert.equal(est.needsConfirmation, true)
  })

  test('trivial plan flag', () => {
    const p = plan([{ kind: 'reply', message: 'salut' }])
    const est = estimatePlan(p)
    assert.equal(est.trivial, true)
  })

  test('reports risky actions individually', () => {
    const p = plan([
      { kind: 'shell', command: 'echo ok', args: [] },
      { kind: 'delete_file', path: 'a.txt' },
    ])
    const est = estimatePlan(p)
    assert.ok(est.riskyActions.length >= 1)
  })
})

describe('dryRunPlan', () => {
  test('produces one step per action with summary', () => {
    const p = plan([
      { kind: 'reply', message: 'salut' },
      { kind: 'shell', command: 'ls', args: ['-la'] },
    ])
    const steps = dryRunPlan(p)
    assert.equal(steps.length, 2)
    assert.equal(steps[0].kind, 'reply')
    assert.ok(steps[0].summary.includes('salut'))
    assert.equal(steps[1].kind, 'shell')
  })
})

describe('Saved plans store', () => {
  test('add/remove round-trip', () => {
    let idx = createSavedPlanIndex()
    idx = addSavedPlan(idx, { name: 'routine matin', description: '', tags: ['matin'], plan: plan([]) })
    assert.equal(idx.plans.length, 1)
    const planId = idx.plans[0].id
    idx = removeSavedPlan(idx, planId)
    assert.equal(idx.plans.length, 0)
  })

  test('bump usage updates runCount + lastRunAt', () => {
    let idx = createSavedPlanIndex()
    idx = addSavedPlan(idx, { name: 'x', description: '', tags: [], plan: plan([]) })
    const id = idx.plans[0].id
    assert.equal(idx.plans[0].runCount, 0)
    assert.equal(idx.plans[0].lastRunAt, null)
    idx = bumpSavedPlanUsage(idx, id)
    assert.equal(idx.plans[0].runCount, 1)
    assert.ok(idx.plans[0].lastRunAt)
  })

  test('searchSavedPlans matches across name, description, tags', () => {
    let idx = createSavedPlanIndex()
    idx = addSavedPlan(idx, { name: 'deploy front', description: 'build + push', tags: ['ci'], plan: plan([]) })
    idx = addSavedPlan(idx, { name: 'aurora check', description: 'sanity', tags: ['debug'], plan: plan([]) })
    assert.equal(searchSavedPlans(idx, 'deploy').length, 1)
    assert.equal(searchSavedPlans(idx, 'build').length, 1)
    assert.equal(searchSavedPlans(idx, 'ci').length, 1)
    assert.equal(searchSavedPlans(idx, 'nope').length, 0)
    assert.equal(searchSavedPlans(idx, '').length, 2)
  })

  test('index version pinned', () => {
    const idx = createSavedPlanIndex()
    assert.equal(idx.version, 1)
  })
})

