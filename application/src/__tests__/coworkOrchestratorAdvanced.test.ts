/**
 * Advanced orchestrator integration tests :
 * - exact event sequence ordering (no out-of-order surprises)
 * - mixed verdicts in a single run (block + confirm + allow)
 * - complete audit trail per scenario
 * - history payload includes data so the LLM can synthesize on next iter
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkOrchestratorAdvanced.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { orchestrateCoworkRun } = await import('../services/coworkOrchestrator.ts')
import type {
  CoworkAction,
  CoworkActionEvent,
  CoworkActionResult,
  CoworkCapability,
  CoworkPlan,
  CoworkRuntime,
} from '../services/coworkTypes.ts'
import type {
  ExecuteFn,
  PlannerFn,
  ConfirmFn,
  AuditFn,
  OrchestratorDeps,
} from '../services/coworkOrchestrator.ts'

const RUNTIME: CoworkRuntime = 'tauri-desktop'
const WS = '/c/Users/me/aurora'
const CAPS: CoworkCapability[] = [
  { id: 'filesystem', label: 'fs', description: 'fs', enabled: true, destructive: true },
  { id: 'shell', label: 'shell', description: 'shell', enabled: true, destructive: true },
]

function defaults(planQueue: CoworkPlan[], over: Partial<OrchestratorDeps> = {}): {
  deps: OrchestratorDeps
  events: CoworkActionEvent[]
  audit: Parameters<AuditFn>[0][]
} {
  const events: CoworkActionEvent[] = []
  const audit: Parameters<AuditFn>[0][] = []
  const queue = [...planQueue]
  const deps: OrchestratorDeps = {
    plan: over.plan ?? (async () => queue.shift() ?? { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'finish', summary: 'no plan' }] }),
    execute: over.execute ?? (async (a) => ({ ok: true, output: `mock(${a.kind})`, durationMs: 1 })),
    confirm: over.confirm ?? (async () => 'approved'),
    audit: over.audit ?? ((e) => { audit.push(e) }),
    getSettings: over.getSettings ?? (() => ({ trustMode: false, dangerMode: false })),
  }
  return { deps, events, audit }
}

// ---------------------------------------------------------------------------
// Exact event sequence ordering
// ---------------------------------------------------------------------------

describe('event sequence ordering — exact', () => {
  test('reply + finish : info Planification, info Plan #1, info Estimation, info reply, success reply, info finish, success finish, success summary', async () => {
    const plan: CoworkPlan = {
      reasoning: 'simple', expectedOutcome: 'salut',
      actions: [{ kind: 'reply', message: 'salut' }, { kind: 'finish', summary: 'fait' }],
    }
    const { deps, events } = defaults([plan])
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    const messages = events.map((e) => `${e.kind}:${e.message.slice(0, 40)}`)
    // Expected exact order :
    // 0 info:Planification…
    // 1 info:Plan #1 — 2 action(s)
    // 2 info:Estimation pre-flight (cost/duration/risk pre-emit)
    // 3 info:Reponse Aurora                    (info before each action)
    // 4 success:Reponse Aurora → OK (1ms)      (success after)
    // 5 info:Termine — fait                    (info before finish)
    // 6 success:Termine — fait → OK (1ms)      (success after finish)
    // 7 success:Termine — 2 action(s) reussie  (final summary)
    assert.equal(events.length, 8, `expected 8 events, got ${events.length}: ${messages.join(' | ')}`)
    assert.equal(events[0].kind, 'info')
    assert.match(events[0].message, /Planification/)
    assert.equal(events[1].kind, 'info')
    assert.match(events[1].message, /Plan #1/)
    assert.equal(events[2].kind, 'info')
    assert.match(events[2].message, /Estimation/)
    assert.equal(events[3].kind, 'info')
    assert.match(events[3].message, /Reponse Aurora/)
    assert.equal(events[4].kind, 'success')
    assert.match(events[4].message, /Reponse Aurora.+OK/)
    assert.equal(events[5].kind, 'info')
    assert.match(events[5].message, /Termine/)
    assert.equal(events[6].kind, 'success')
    assert.match(events[6].message, /OK/)
    assert.equal(events[7].kind, 'success')
    assert.match(events[7].message, /Termine.*reussie/)
  })

  test('failure between two successes triggers recovery before finish', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'first' },
        { kind: 'read_file', path: 'src/missing.ts' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'fallback after read failure' },
        { kind: 'finish', summary: 'fait apres recuperation' },
      ],
    }
    const { deps, events } = defaults([plan, recovery], {
      execute: async (a) => {
        if (a.kind === 'read_file') return { ok: false, error: 'ENOENT', durationMs: 5 }
        return { ok: true, output: 'mock', durationMs: 1 }
      },
    })
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    // Sequence : Plan/Plan #1, info+success reply, info+ERROR read_file, info+success finish, final
    const kinds = events.map((e) => e.kind)
    // Find the read_file pair (path is normalized to absolute via safety)
    const readFileInfoIdx = events.findIndex((e) => /Lire .*missing/.test(e.message))
    assert.ok(readFileInfoIdx >= 0, `expected read_file info event, got: ${events.map((e) => e.message).join(' | ')}`)
    assert.equal(events[readFileInfoIdx].kind, 'info')
    assert.equal(events[readFileInfoIdx + 1].kind, 'error')
    assert.match(events[readFileInfoIdx + 1].message, /ECHEC/)
    const staleFinish = events.find((e) => /Termine.*fait\s*(?:→|$)/.test(e.message))
    assert.equal(staleFinish, undefined, 'stale finish from plan #1 must not run after failure')
    const recoveryWarn = events.find((e) => e.kind === 'warn' && /change de strategie/i.test(e.message))
    assert.ok(recoveryWarn)
    const finishOk = events.find((e) => e.kind === 'success' && /Termine.+fait apres recuperation/.test(e.message))
    assert.ok(finishOk, 'recovery finish must emit success')
    // Final summary includes the synthetic recovery think step as an OK action.
    const final = events[events.length - 1]
    assert.match(final.message, /4 action.+reussie.+1 echouee/)
    assert.deepEqual(kinds.filter((k) => k === 'error').length, 1)
  })

  test('block in middle : info+error block, then recovery plan finishes', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'before' },
        { kind: 'shell', command: 'sudo', args: ['ls'] },  // block
        { kind: 'finish', summary: 'after block' },
      ],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'fallback after block' },
        { kind: 'finish', summary: 'after block recovery' },
      ],
    }
    const { deps, events, audit } = defaults([plan, recovery])
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    // Block emits error event with "bloquee"
    const blockedEvt = events.find((e) => e.kind === 'error' && /bloquee/.test(e.message))
    assert.ok(blockedEvt)
    const staleFinish = events.find((e) => /Termine.*after block\s*(?:→|$)/.test(e.message))
    assert.equal(staleFinish, undefined)
    const finishEvt = events.find((e) => e.kind === 'success' && /Termine.+after block recovery/.test(e.message))
    assert.ok(finishEvt)
    // Audit trail records the first reply, the block, then the fallback actions.
    const decisions = audit.map((a) => a.decision)
    assert.deepEqual(decisions, ['allow', 'block', 'allow', 'allow'])
  })
})

// ---------------------------------------------------------------------------
// Mixed verdicts in single run + complete audit trail
// ---------------------------------------------------------------------------

describe('mixed verdicts run : block + confirm + allow', () => {
  test('shell sudo (block) + write_file (confirm approved) + reply (allow) + finish', async () => {
    const plan: CoworkPlan = {
      reasoning: 'mixed', expectedOutcome: 'multi-verdict',
      actions: [
        { kind: 'shell', command: 'sudo', args: ['rm', '-rf', '/'] },  // block
        { kind: 'write_file', path: '.env', content: 'TOKEN=x' },       // confirm (sensitive)
        { kind: 'reply', message: 'done' },                             // allow
        { kind: 'finish', summary: 'done' },                            // allow
      ],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback after block', expectedOutcome: 'multi-verdict',
      actions: [
        { kind: 'write_file', path: '.env', content: 'TOKEN=x' },
        { kind: 'reply', message: 'done' },
        { kind: 'finish', summary: 'done' },
      ],
    }
    let confirmCalls = 0
    let executeCalls = 0
    const { deps, events, audit } = defaults([plan, recovery], {
      confirm: async () => { confirmCalls++; return 'approved' },
      execute: async (a) => {
        executeCalls++
        // sudo must NEVER reach the executor (blocked first)
        if (a.kind === 'shell' && a.command === 'sudo') {
          throw new Error('block bypass!')
        }
        return { ok: true, output: a.kind, durationMs: 1 }
      },
    })
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p1' })

    // Audit trail in order :
    // 1. block sudo
    // 2. confirm write_file (decision recorded as 'confirm', approved)
    // 3. allow reply
    // 4. allow finish
    assert.equal(audit.length, 4)
    assert.deepEqual(audit.map((a) => a.decision), ['block', 'confirm', 'allow', 'allow'])
    assert.equal(audit[0].action.kind, 'shell')
    assert.equal(audit[1].action.kind, 'write_file')
    assert.equal(audit[2].action.kind, 'reply')
    assert.equal(audit[3].action.kind, 'finish')

    // Each entry has the promptId
    for (const a of audit) {
      assert.equal(a.promptId, 'p1')
    }

    // sudo never executed
    assert.equal(confirmCalls, 1, 'confirm called exactly once for write_file')
    assert.equal(executeCalls, 3, 'execute called 3 times (write_file + reply + finish)')
  })

  test('confirm-skip in middle : audit shows skipped, history records skipped', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'first' },
        { kind: 'write_file', path: '.env', content: 'x' },  // confirm (sensitive)
        { kind: 'reply', message: 'after skip' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'fallback after skip' },
        { kind: 'finish', summary: 'fait apres skip' },
      ],
    }
    const { deps, events, audit } = defaults([plan, recovery], {
      confirm: async () => 'skipped',
    })
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p2' })

    assert.deepEqual(audit.map((a) => a.decision), ['allow', 'skipped', 'allow', 'allow'])
    assert.equal(events.some((e) => /Reponse Aurora/.test(e.message) && /"message": "after skip"/.test(e.detail || '')), false)
    // Skipped event in stream
    const skipEvt = events.find((e) => e.kind === 'warn' && /Saute/.test(e.message))
    assert.ok(skipEvt, 'skip event must appear')
  })
})

// ---------------------------------------------------------------------------
// History payload — the LLM must see the actual data on next iteration
// ---------------------------------------------------------------------------

describe('history payload : data flows to subsequent planner calls', () => {
  test('plan #2 receives plan #1 read_file output in history', async () => {
    const plan1: CoworkPlan = {
      reasoning: 'lis le fichier', expectedOutcome: '...',
      actions: [{ kind: 'read_file', path: 'src/data.json' }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'synthese', expectedOutcome: 'reponse',
      actions: [
        { kind: 'reply', message: 'analyse complete' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCall = 0
    const historyPayloads: Array<Array<{ action: CoworkAction; result: CoworkActionResult }>> = []
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        plannerCall++
        // Snapshot history at each call
        historyPayloads.push(ctx.history.map((e) => ({ action: { ...e.action } as CoworkAction, result: { ...e.result } })))
        return [plan1, plan2][plannerCall - 1]
      },
      execute: async (a) => {
        if (a.kind === 'read_file') {
          return { ok: true, output: '{"users": ["alice", "bob"]}', data: { users: ['alice', 'bob'] }, durationMs: 1 }
        }
        return { ok: true, output: a.kind, durationMs: 1 }
      },
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const events: CoworkActionEvent[] = []
    await orchestrateCoworkRun('analyse', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    // Plan #1 sees empty history
    assert.equal(historyPayloads[0].length, 0)
    // Plan #2 sees plan #1's read_file with its output + data
    assert.equal(historyPayloads[1].length, 1)
    const entry = historyPayloads[1][0]
    assert.equal(entry.action.kind, 'read_file')
    assert.equal(entry.result.ok, true)
    assert.match(entry.result.output ?? '', /alice/)
    assert.deepEqual(entry.result.data, { users: ['alice', 'bob'] })
  })
})

// ---------------------------------------------------------------------------
// Final summary correctness
// ---------------------------------------------------------------------------

describe('final summary count', () => {
  test('counts OK and KO correctly on mixed run', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: '1' },             // ok
        { kind: 'reply', message: '2' },             // ok
        { kind: 'read_file', path: 'missing' },     // KO
        { kind: 'finish', summary: 'fin' },         // ok
      ],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'finish', summary: 'fin apres recuperation' },
      ],
    }
    const { deps, events } = defaults([plan, recovery], {
      execute: async (a) => {
        if (a.kind === 'read_file') return { ok: false, error: 'ENOENT', durationMs: 5 }
        return { ok: true, durationMs: 1 }
      },
    })
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    const final = events[events.length - 1]
    assert.match(final.message, /4 action.+reussie.+1 echouee/)
  })
})
