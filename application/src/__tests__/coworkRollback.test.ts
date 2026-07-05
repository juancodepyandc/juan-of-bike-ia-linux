/**
 * Tests rollback du cowork planner.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  checkRollbackReadiness,
  generateRollbackPlan,
  type ExecutionRecord,
} from '../services/coworkPlanRollback.ts'
import type { CoworkAction, CoworkActionResult, CoworkPlan } from '../services/coworkTypes.ts'

const ok = (output = 'ok'): CoworkActionResult => ({ ok: true, output, durationMs: 1 })

describe('Rollback — write/edit/delete', () => {
  test('write_file nouveau → delete_file', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'write_file', path: 'new.ts', content: 'x' }, result: ok() }],
      preActionStates: { 'new.ts': { content: '', existed: false } },
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions.length, 1)
    assert.equal(r.actions[0].kind, 'delete_file')
    assert.equal((r.actions[0] as { path: string }).path, 'new.ts')
    assert.equal(r.fullyReversible, true)
  })

  test('write_file overwrite → write_file avec contenu original', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'write_file', path: 'a.ts', content: 'new' }, result: ok() }],
      preActionStates: { 'a.ts': { content: 'original', existed: true } },
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions[0].kind, 'write_file')
    assert.equal((r.actions[0] as { content: string }).content, 'original')
  })

  test('edit_file → edit_file inversé (oldText/newText swappés)', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'edit_file', path: 'a.ts', oldText: 'foo', newText: 'bar' }, result: ok() }],
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions[0].kind, 'edit_file')
    assert.equal((r.actions[0] as { oldText: string }).oldText, 'bar')
    assert.equal((r.actions[0] as { newText: string }).newText, 'foo')
  })

  test('delete_file avec preState → write_file restore', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'delete_file', path: 'a.ts' }, result: ok() }],
      preActionStates: { 'a.ts': { content: 'rescued', existed: true } },
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions[0].kind, 'write_file')
    assert.equal((r.actions[0] as { content: string }).content, 'rescued')
  })

  test('delete_file sans preState → irréversible', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'delete_file', path: 'a.ts' }, result: ok() }],
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.fullyReversible, false)
    assert.equal(r.irreversible.length, 1)
  })

  test('shell → irréversible + reply d\'alerte', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'shell', command: 'rm', args: ['-rf', '/tmp/x'] }, result: ok() }],
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.fullyReversible, false)
    assert.ok(r.actions.some((a) => a.kind === 'reply' && (a as { message: string }).message.includes('shell')))
  })

  test('action en échec n\'est pas rollback', () => {
    const record: ExecutionRecord = {
      pairs: [
        { action: { kind: 'write_file', path: 'a.ts', content: 'x' }, result: { ok: false, durationMs: 1 } },
        { action: { kind: 'write_file', path: 'b.ts', content: 'y' }, result: ok() },
      ],
      preActionStates: { 'b.ts': { content: '', existed: false } },
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions.length, 1)
    assert.equal((r.actions[0] as { path: string }).path, 'b.ts')
  })

  test('rollback LIFO : dernière action rollback en premier', () => {
    const record: ExecutionRecord = {
      pairs: [
        { action: { kind: 'write_file', path: 'a.ts', content: 'x' }, result: ok() },
        { action: { kind: 'write_file', path: 'b.ts', content: 'y' }, result: ok() },
        { action: { kind: 'write_file', path: 'c.ts', content: 'z' }, result: ok() },
      ],
      preActionStates: {
        'a.ts': { content: '', existed: false },
        'b.ts': { content: '', existed: false },
        'c.ts': { content: '', existed: false },
      },
    }
    const r = generateRollbackPlan(record)
    assert.equal((r.actions[0] as { path: string }).path, 'c.ts')
    assert.equal((r.actions[1] as { path: string }).path, 'b.ts')
    assert.equal((r.actions[2] as { path: string }).path, 'a.ts')
  })

  test('remember_fact → forget_fact', () => {
    const record: ExecutionRecord = {
      pairs: [{ action: { kind: 'remember_fact', fact: 'Juan aime le sport' }, result: ok() }],
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions[0].kind, 'forget_fact')
  })

  test('read-only ops produisent aucun rollback', () => {
    const record: ExecutionRecord = {
      pairs: [
        { action: { kind: 'read_file', path: 'a.ts' }, result: ok() },
        { action: { kind: 'list_dir', path: 'src' }, result: ok() },
      ],
    }
    const r = generateRollbackPlan(record)
    assert.equal(r.actions.length, 0)
    assert.equal(r.fullyReversible, true)
  })
})

describe('Rollback readiness check', () => {
  const plan = (actions: CoworkAction[]): CoworkPlan => ({ reasoning: '', expectedOutcome: '', actions })

  test('write sans read préalable → warning', () => {
    const p = plan([{ kind: 'write_file', path: 'a.ts', content: 'x' }])
    const c = checkRollbackReadiness(p)
    assert.equal(c.rollbackReady, false)
    assert.equal(c.warnings.length, 1)
  })

  test('read puis write sur même path → rollback ready', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'write_file', path: 'a.ts', content: 'x' },
    ])
    const c = checkRollbackReadiness(p)
    assert.equal(c.rollbackReady, true)
  })

  test('delete sans read → warning', () => {
    const p = plan([{ kind: 'delete_file', path: 'a.ts' }])
    const c = checkRollbackReadiness(p)
    assert.equal(c.rollbackReady, false)
  })
})
