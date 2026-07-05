/**
 * Tests pour coworkPlanDependencyAnalyzer.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeDependencies,
  executionWaves,
} from '../services/coworkPlanDependencyAnalyzer.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

const plan = (actions: CoworkAction[]): CoworkPlan => ({
  reasoning: 'r', actions, expectedOutcome: 'o',
})

describe('coworkPlanDependencyAnalyzer — barre expert', () => {
  test('read-then-write sur même path → dépendance', () => {
    const p = plan([
      { kind: 'read_file', path: 'src/a.ts' },
      { kind: 'write_file', path: 'src/a.ts', content: 'modified' },
    ])
    const r = analyzeDependencies(p)
    assert.equal(r.edges.length, 1)
    assert.equal(r.edges[0].from, 0)
    assert.equal(r.edges[0].to, 1)
    assert.match(r.edges[0].reason, /write-after-read/)
  })

  test('actions sur paths différents → aucune dépendance', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'read_file', path: 'b.ts' },
      { kind: 'read_file', path: 'c.ts' },
    ])
    const r = analyzeDependencies(p)
    assert.equal(r.edges.length, 0)
    assert.equal(r.initialFront.length, 3)
  })

  test('finish dépend de toutes les actions précédentes', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'b.ts', content: 'x' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = analyzeDependencies(p)
    assert.equal(r.nodes[2].dependsOn.length, 2)
  })

  test('think ignoré dans les dépendances de finish', () => {
    const p = plan([
      { kind: 'think', topic: 'plan', thought: '...' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = analyzeDependencies(p)
    assert.equal(r.nodes[1].dependsOn.length, 0)
  })

  test('chemin critique = somme des durées sur la séquence dépendante', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'read_file', path: 'a.ts' },
    ])
    const r = analyzeDependencies(p)
    assert.deepEqual(r.criticalPath, [0, 1, 2])
    assert.ok(r.criticalPathMs > 0)
    assert.ok(r.criticalPathMs <= r.sequentialDurationMs)
  })

  test('parallélisable : minDurationMs < sequentialDurationMs', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'read_file', path: 'b.ts' },
      { kind: 'read_file', path: 'c.ts' },
      { kind: 'read_file', path: 'd.ts' },
    ])
    const r = analyzeDependencies(p)
    assert.ok(r.minDurationMs < r.sequentialDurationMs)
  })

  test('plan vide → aucun edge, criticalPath vide', () => {
    const p = plan([])
    const r = analyzeDependencies(p)
    assert.equal(r.edges.length, 0)
    assert.equal(r.criticalPath.length, 0)
    assert.equal(r.criticalPathMs, 0)
  })

  test('executionWaves regroupe les actions indépendantes', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'read_file', path: 'b.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = analyzeDependencies(p)
    const waves = executionWaves(r)
    assert.equal(waves.length, 3)
    assert.deepEqual(waves[0], [0, 1])
    assert.deepEqual(waves[1], [2])
    assert.deepEqual(waves[2], [3])
  })
})
