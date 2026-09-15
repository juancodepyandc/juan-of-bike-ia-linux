import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { RedBlackTree } from '../services/treeAlgorithmEngine.ts'

describe('Code Module — Advanced Data Structures & Invariants', () => {
  it('maintient les invariants de l arbre Rouge-Noir apres 500 insertions pseudo-aleatoires', () => {
    const tree = new RedBlackTree<number>()
    const values: number[] = []

    // Linear Congruential Generator for reproducible pseudo-random numbers
    let seed = 42
    for (let i = 0; i < 500; i++) {
      seed = (seed * 1664525 + 1013904223) % 4294967296
      values.push(seed % 10000)
    }

    for (const v of values) {
      tree.insert(v)
      const audit = tree.verifyRedBlackInvariants()
      if (!audit.valid) {
        assert.fail(`Invariant brise lors de l insertion de ${v}: ${audit.errors.join(', ')}`)
      }
    }

    const finalAudit = tree.verifyRedBlackInvariants()
    assert.equal(finalAudit.valid, true)
    assert.equal(finalAudit.errors.length, 0)
  })
})
