/**
 * Tests pour services/coworkPlanDependencyAnalyzer — DAG des actions cowork.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeDependencies,
  executionWaves,
} from '../services/coworkPlanDependencyAnalyzer.ts'
import type { CoworkAction, CoworkPlan } from '../services/coworkTypes.ts'

function plan(actions: CoworkAction[]): CoworkPlan {
  return { reasoning: 'r', expectedOutcome: 'o', actions }
}

describe('analyzeDependencies — graphe vide', () => {
  test('plan vide → 0 nodes, criticalPath vide', () => {
    const r = analyzeDependencies(plan([]))
    assert.equal(r.nodes.length, 0)
    assert.deepEqual(r.criticalPath, [])
    assert.equal(r.criticalPathMs, 0)
    assert.equal(r.sequentialDurationMs, 0)
  })
})

describe('analyzeDependencies — indépendances', () => {
  test('2 actions indépendantes → initialFront contient les 2', () => {
    const r = analyzeDependencies(plan([
      { kind: 'reply', message: 'a' },
      { kind: 'reply', message: 'b' },
    ]))
    assert.equal(r.initialFront.length, 2)
    assert.equal(r.edges.length, 0)
  })

  test('2 read_file sur paths différents → indépendants', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'read_file', path: 'b.ts' },
    ]))
    assert.equal(r.edges.length, 0)
  })
})

describe('analyzeDependencies — dépendances détectées', () => {
  test('read → write sur même path : write dépend de read', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
    ]))
    assert.equal(r.edges.length, 1)
    assert.equal(r.edges[0].from, 0)
    assert.equal(r.edges[0].to, 1)
    assert.ok(r.edges[0].reason.includes('write-after-read'))
  })

  test('write → read sur même path : read dépend de write', () => {
    const r = analyzeDependencies(plan([
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'read_file', path: 'a.ts' },
    ]))
    assert.equal(r.edges.length, 1)
    assert.ok(r.edges[0].reason.includes('read-after-write'))
  })

  test('write → write : 2e dépend du 1er', () => {
    const r = analyzeDependencies(plan([
      { kind: 'write_file', path: 'a.ts', content: '1' },
      { kind: 'write_file', path: 'a.ts', content: '2' },
    ]))
    assert.equal(r.edges.length, 1)
    assert.ok(r.edges[0].reason.includes('write-after-write'))
  })

  test('finish dépend de toutes les actions précédentes (sauf think)', () => {
    const r = analyzeDependencies(plan([
      { kind: 'reply', message: 'a' },
      { kind: 'think', topic: 't', thought: '...' },
      { kind: 'finish', summary: 'done' },
    ]))
    const finishNode = r.nodes[2]
    // finish dépend de reply (0), pas de think (1)
    assert.ok(finishNode.dependsOn.includes(0))
    assert.ok(!finishNode.dependsOn.includes(1))
  })

  test('vision_describe dépend de la screenshot browser précédente', () => {
    const r = analyzeDependencies(plan([
      { kind: 'browser', operation: 'screenshot' },
      { kind: 'vision_describe', imageDataUrl: 'data:...' },
    ]))
    assert.equal(r.nodes[1].dependsOn[0], 0)
  })
})

describe('analyzeDependencies — chemin critique', () => {
  test('chaîne read → write → finish → critical path complet', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'finish', summary: 'done' },
    ]))
    assert.deepEqual(r.criticalPath, [0, 1, 2])
    assert.ok(r.criticalPathMs > 0)
  })

  test('actions parallèles indépendantes → critical path = 1 action', () => {
    const r = analyzeDependencies(plan([
      { kind: 'reply', message: 'a' },
      { kind: 'reply', message: 'b' },
    ]))
    // critical path inclut une seule action (les 2 sont en parallèle)
    assert.equal(r.criticalPath.length, 1)
  })

  test('sequential >= critical (sans parallélisme aide pas)', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
    ]))
    assert.ok(r.sequentialDurationMs >= r.criticalPathMs)
  })

  test('actions parallèles → sequential > critical', () => {
    const r = analyzeDependencies(plan([
      { kind: 'reply', message: 'a' },
      { kind: 'reply', message: 'b' },
      { kind: 'reply', message: 'c' },
    ]))
    assert.ok(r.sequentialDurationMs > r.criticalPathMs)
  })
})

describe('analyzeDependencies — initialFront', () => {
  test('finish seule en tête → seule action en front', () => {
    const r = analyzeDependencies(plan([
      { kind: 'finish', summary: 'done' },
    ]))
    assert.deepEqual(r.initialFront, [0])
  })

  test('plusieurs actions indépendantes → toutes dans initialFront', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a' },
      { kind: 'read_file', path: 'b' },
      { kind: 'read_file', path: 'c' },
    ]))
    assert.deepEqual(r.initialFront, [0, 1, 2])
  })
})

describe('executionWaves', () => {
  test('chaîne séquentielle → 1 action par vague', () => {
    const a = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'finish', summary: 'done' },
    ]))
    const waves = executionWaves(a)
    assert.equal(waves.length, 3)
    for (const w of waves) assert.equal(w.length, 1)
  })

  test('indépendants → 1 seule vague avec toutes les actions', () => {
    const a = analyzeDependencies(plan([
      { kind: 'reply', message: '1' },
      { kind: 'reply', message: '2' },
      { kind: 'reply', message: '3' },
    ]))
    const waves = executionWaves(a)
    assert.equal(waves.length, 1)
    assert.equal(waves[0].length, 3)
  })

  test('mixte : 2 indépendants + 1 dépendant → 2 vagues', () => {
    const a = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' }, // 0
      { kind: 'read_file', path: 'b.ts' }, // 1
      { kind: 'write_file', path: 'a.ts', content: 'x' }, // 2 dépend de 0
    ]))
    const waves = executionWaves(a)
    assert.equal(waves.length, 2)
    assert.ok(waves[0].includes(0))
    assert.ok(waves[0].includes(1))
    assert.deepEqual(waves[1], [2])
  })

  test('plan vide → 0 vague', () => {
    const a = analyzeDependencies(plan([]))
    const waves = executionWaves(a)
    assert.equal(waves.length, 0)
  })
})

describe('analyzeDependencies — durées', () => {
  test('chaque node a durationMs > 0', () => {
    const r = analyzeDependencies(plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'reply', message: 'x' },
    ]))
    for (const n of r.nodes) {
      assert.ok(n.durationMs > 0, `${n.action.kind} durée 0`)
    }
  })
})
