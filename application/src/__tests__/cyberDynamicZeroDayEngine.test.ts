import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  analyzeDynamicVulnerabilities,
  FUNDAMENTAL_INVARIANTS,
} from '../services/cyber/dynamicZeroDayEngine.ts'

describe('DynamicZeroDayEngine', () => {
  test('FUNDAMENTAL_INVARIANTS contient les 5 piliers de sécurité fondamentaux', () => {
    assert.ok(FUNDAMENTAL_INVARIANTS.length >= 5)
    for (const inv of FUNDAMENTAL_INVARIANTS) {
      assert.ok(inv.name.length > 5)
      assert.ok(inv.formalDefinition.length > 10)
      assert.ok(inv.violationMechanism.length > 10)
      assert.ok(inv.defensePrinciple.length > 10)
    }
  })

  test('analyzeDynamicVulnerabilities déduit une condition de course sans liste statique', () => {
    const asyncCode = `
      async function transfer(u1, u2, val) {
        const a = await db.get(u1);
        if (a.balance >= val) {
          await gateway.pay(val);
          await db.update(u1, a.balance - val);
        }
      }
    `
    const session = analyzeDynamicVulnerabilities(asyncCode, 'typescript')
    assert.ok(session.hypotheses.length >= 1)
    const raceHyp = session.hypotheses.find((h) => h.invariantCategory === 'concurrency-atomicity')
    assert.ok(raceHyp, 'Doit déduire une hypothèse de concurrence / TOCTOU')
    assert.ok(raceHyp.defenseInvariant.includes('transaction'))
    assert.ok(session.generatedFuzzInputs.length >= 1)
    assert.ok(session.synthesizedDefenseCode.includes('secureExecutionWrapper'))
  })

  test('analyzeDynamicVulnerabilities déduit une faille de mémoire sur du code C pointeurs', () => {
    const memCode = `
      void free_pkt(struct pkt *p) {
        free(p->data);
        free(p);
      }
      int handle(const char *buf) {
        return current_p->cb(buf);
      }
    `
    const session = analyzeDynamicVulnerabilities(memCode, 'c')
    const memHyp = session.hypotheses.find((h) => h.invariantCategory === 'memory-safety')
    assert.ok(memHyp, 'Doit déduire une hypothèse de mémoire UAF/BOF')
  })
})
