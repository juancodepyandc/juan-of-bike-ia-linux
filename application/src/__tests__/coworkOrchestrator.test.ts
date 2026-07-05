/**
 * Integration tests for the orchestrator (orchestrateCoworkRun) with a mock
 * planner / executor / confirmation. Validates the full agentic loop
 * behavior end-to-end without touching real LLMs or the filesystem.
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkOrchestrator.test.ts
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

// ---------------------------------------------------------------------------
// Helpers : build mock deps with sensible defaults
// ---------------------------------------------------------------------------

function makeMocks(opts: {
  planQueue: CoworkPlan[]
  executor?: ExecuteFn
  confirmer?: ConfirmFn
  auditor?: AuditFn
  trustMode?: boolean
  dangerMode?: boolean
  fullyUnlocked?: boolean
}): { deps: OrchestratorDeps; events: CoworkActionEvent[]; auditCalls: Parameters<AuditFn>[0][] } {
  const planQueue = [...opts.planQueue]
  const events: CoworkActionEvent[] = []
  const auditCalls: Parameters<AuditFn>[0][] = []

  const plan: PlannerFn = async (_ctx) => {
    if (planQueue.length === 0) throw new Error('plan queue empty (test bug or unexpected re-plan)')
    return planQueue.shift()!
  }

  const execute: ExecuteFn = opts.executor ?? (async (action) => ({
    ok: true,
    output: `mock execution of ${action.kind}`,
    durationMs: 1,
  }))

  const confirm: ConfirmFn = opts.confirmer ?? (async () => 'approved')

  const audit: AuditFn = opts.auditor ?? ((entry) => { auditCalls.push(entry) })

  return {
    deps: {
      plan,
      execute,
      confirm,
      audit,
      getSettings: () => ({
        trustMode: opts.trustMode ?? false,
        dangerMode: opts.dangerMode ?? false,
        fullyUnlocked: opts.fullyUnlocked,
      }),
    },
    events,
    auditCalls,
  }
}

// ---------------------------------------------------------------------------
// Happy path : single plan with reply + finish
// ---------------------------------------------------------------------------

describe('happy path : single plan ends with finish', () => {
  test('emits planification + plan #1 + reply OK + finish OK + summary', async () => {
    const plan: CoworkPlan = {
      reasoning: 'salutation triviale',
      expectedOutcome: 'salut rendu',
      actions: [
        { kind: 'reply', message: 'salut !' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const { deps, events, auditCalls } = makeMocks({ planQueue: [plan] })

    const result = await orchestrateCoworkRun(
      'dis bonjour',
      RUNTIME,
      CAPS,
      WS,
      deps,
      { onEvent: (e) => events.push(e), promptId: 'p-test-1' },
    )

    assert.equal(result.finished, true)
    assert.equal(result.iterations, 1)

    // Event sequence : Planification, Plan #1, info reply, success reply,
    // info finish, success finish, final summary success
    const kinds = events.map((e) => e.kind)
    assert.ok(kinds.includes('info'))
    assert.ok(kinds.includes('success'))
    assert.equal(kinds.filter((k) => k === 'error').length, 0, 'no errors expected')

    // Audit must record reply + finish (both allow)
    assert.equal(auditCalls.length, 2)
    assert.equal(auditCalls[0].decision, 'allow')
    assert.equal(auditCalls[0].action.kind, 'reply')
    assert.equal(auditCalls[1].action.kind, 'finish')

    // Final event mentions "Termine"
    const last = events[events.length - 1]
    assert.match(last.message, /Termine/)
  })
})

// ---------------------------------------------------------------------------
// Empty prompt
// ---------------------------------------------------------------------------

describe('empty prompt is rejected fast', () => {
  test('emits warn "Demande vide", no planner call', async () => {
    let plannerCalls = 0
    const deps: OrchestratorDeps = {
      plan: async () => { plannerCalls++; throw new Error('should not call') },
      execute: async () => ({ ok: true, durationMs: 0 }),
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('   ', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, false)
    assert.equal(r.iterations, 0)
    assert.equal(plannerCalls, 0)
    assert.match(events[0].message, /vide/i)
  })
})

// ---------------------------------------------------------------------------
// Confirm flow : approved / skipped / aborted
// ---------------------------------------------------------------------------

describe('confirm flow', () => {
  test('approved : execute proceeds', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'shell', command: 'someweirdtool', args: [] },  // confirms
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let confirmCalls = 0
    const { deps, events, auditCalls } = makeMocks({
      planQueue: [plan],
      confirmer: async () => { confirmCalls++; return 'approved' },
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true)
    assert.equal(confirmCalls, 1)
    assert.equal(auditCalls[0].decision, 'confirm')
  })

  test('skipped : action is not executed, recovery plan can finish', async () => {
    const plan1: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'shell', command: 'someweirdtool', args: [] },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'action sautee, fallback rendu' },
        { kind: 'finish', summary: 'fait apres skip' },
      ],
    }
    let executeCalls = 0
    const { deps, events, auditCalls } = makeMocks({
      planQueue: [plan1, plan2],
      confirmer: async () => 'skipped',
      executor: async (a) => {
        executeCalls++
        // The skipped action shouldn't be passed to execute
        assert.notEqual(a.kind, 'shell', 'skipped action must not be executed')
        return { ok: true, durationMs: 0 }
      },
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    assert.equal(executeCalls, 2, 'only fallback reply + finish should reach the executor')
    const skipAudit = auditCalls.find((a) => a.decision === 'skipped')
    assert.ok(skipAudit, 'must log skipped in audit')
  })

  test('aborted : run halts, no further action', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'shell', command: 'someweirdtool', args: [] },
        { kind: 'reply', message: 'unreachable' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let executeCalls = 0
    const { deps, events, auditCalls } = makeMocks({
      planQueue: [plan],
      confirmer: async () => 'aborted',
      executor: async () => { executeCalls++; return { ok: true, durationMs: 0 } },
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, false, 'aborted should not finish')
    assert.equal(executeCalls, 0, 'no action executes after abort')
    assert.ok(auditCalls.some((a) => a.decision === 'aborted'))
    assert.ok(events.some((e) => /interrompu/i.test(e.message)))
  })
})

// ---------------------------------------------------------------------------
// Block flow : action validates as block, execution skipped, history records
// ---------------------------------------------------------------------------

describe('block flow', () => {
  test('shell sudo without danger mode : block, then replan', async () => {
    const plan1: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'shell', command: 'sudo', args: ['ls'] },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'commande bloquee, fallback non destructif rendu' },
        { kind: 'finish', summary: 'fait apres block' },
      ],
    }
    let executeCalls = 0
    const { deps, events, auditCalls } = makeMocks({
      planQueue: [plan1, plan2],
      executor: async (a) => {
        executeCalls++
        assert.notEqual(a.kind, 'shell', 'sudo must not reach the executor')
        return { ok: true, durationMs: 0 }
      },
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true, 'fallback plan should finish after blocked shell')
    assert.equal(r.iterations, 2)
    assert.equal(executeCalls, 2, 'only fallback reply + finish execute')
    const blocked = auditCalls.find((a) => a.decision === 'block')
    assert.ok(blocked)
    assert.ok(events.some((e) => e.kind === 'error' && /bloquee/i.test(e.message)))
    assert.ok(events.some((e) => /replannifie/i.test(e.message)))
  })
})

// ---------------------------------------------------------------------------
// Loop detection : same plan signature twice -> bail
// ---------------------------------------------------------------------------

describe('loop detection', () => {
  test('same plan twice -> "boucle detectee"', async () => {
    const same: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [{ kind: 'reply', message: 'rebouclage' }],  // no finish, will re-plan
    }
    const sameAgain: CoworkPlan = {
      reasoning: 'autre raison',
      expectedOutcome: 'autre objectif',
      actions: [{ kind: 'reply', message: 'rebouclage' }],  // identical signature
    }
    const { deps, events } = makeMocks({ planQueue: [same, sameAgain] })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, false)
    assert.equal(r.iterations, 2)
    assert.ok(events.some((e) => /boucle detectee/i.test(e.message)))
  })

  test('same failing plan -> recovery hint, then alternative plan can finish', async () => {
    const failing: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'shell', command: 'git', args: ['status'] }],
    }
    const recovery: CoworkPlan = {
      reasoning: 'fallback',
      expectedOutcome: 'reply',
      actions: [
        { kind: 'reply', message: 'fallback apres echec shell' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const { deps, events } = makeMocks({
      planQueue: [failing, failing, recovery],
      executor: async (a) => {
        if (a.kind === 'shell') return { ok: false, error: 'stream did not contain valid UTF-8', durationMs: 5 }
        return { ok: true, output: a.kind, durationMs: 1 }
      },
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 3)
    assert.ok(events.some((e) => /replannification alternative/i.test(e.message)))
    assert.ok(events.some((e) => /fallback apres echec shell/.test(e.detail || e.message)))
  })
})

// ---------------------------------------------------------------------------
// Abort signal : signal aborted before run starts -> immediate stop
// ---------------------------------------------------------------------------

describe('abort signal propagation', () => {
  test('signal already aborted at start -> warn, no plan call', async () => {
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async () => { planCalls++; return { reasoning: 'r', expectedOutcome: 'o', actions: [] } },
      execute: async () => ({ ok: true, durationMs: 0 }),
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const ctrl = new AbortController()
    ctrl.abort()
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, {
      onEvent: (e) => events.push(e),
      signal: ctrl.signal,
      promptId: 'p',
    })
    assert.equal(r.finished, false)
    assert.equal(planCalls, 0, 'planner not called when already aborted')
    assert.ok(events.some((e) => /Annule/i.test(e.message)))
  })

  test('planner throws abort error -> graceful warn, not error', async () => {
    const deps: OrchestratorDeps = {
      plan: async () => { throw new Error('AbortError: aborted') },
      execute: async () => ({ ok: true, durationMs: 0 }),
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const ctrl = new AbortController()
    ctrl.abort()
    const events: CoworkActionEvent[] = []
    await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, {
      onEvent: (e) => events.push(e),
      signal: ctrl.signal,
      promptId: 'p',
    })
    // Either "Annule par l utilisateur" (top of loop) or "Annule pendant la
    // planification" (planner throw) — both are acceptable warns.
    const annuleMsg = events.find((e) => /Annule/i.test(e.message))
    assert.ok(annuleMsg, 'must emit annule warning')
    assert.equal(annuleMsg!.kind, 'warn')
  })
})

// ---------------------------------------------------------------------------
// Multi-iteration : plan without finish -> re-plan with history
// ---------------------------------------------------------------------------

describe('multi-iteration with history', () => {
  test('first plan no finish, second plan finishes', async () => {
    const plan1: CoworkPlan = {
      reasoning: 'r1', expectedOutcome: 'o1',
      actions: [{ kind: 'reply', message: 'step 1' }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'r2', expectedOutcome: 'o2',
      actions: [
        { kind: 'reply', message: 'step 2' },
        { kind: 'finish', summary: 'done' },
      ],
    }
    let plannerCalls = 0
    const historySnapshots: number[] = []
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        plannerCalls++
        // Snapshot the history length at the moment the planner is called.
        historySnapshots.push(ctx.history.length)
        return [plan1, plan2][plannerCalls - 1]
      },
      execute: async (action) => ({ ok: true, output: action.kind, durationMs: 1 }),
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    assert.equal(plannerCalls, 2)
    // First planner call : empty history. Second : 1 entry from plan1.
    assert.deepEqual(historySnapshots, [0, 1])
  })
})

// ---------------------------------------------------------------------------
// Trust mode : confirm verdicts become allow, no confirmation function call
// ---------------------------------------------------------------------------

describe('trust mode short-circuits confirmations', () => {
  test('write_file with trust mode : execute without confirm()', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'write_file', path: 'foo.txt', content: 'hello' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let confirmCalls = 0
    const { deps, events } = makeMocks({
      planQueue: [plan],
      confirmer: async () => { confirmCalls++; return 'aborted' },  // would abort if reached
      trustMode: true,
    })
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true, 'should finish under trust mode')
    assert.equal(confirmCalls, 0, 'confirm() must not be called under trust mode')
  })

  test('trust mode warns before executing an accepted destructive risk', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'write_file', path: '/tmp/heavy-project/report.md', content: 'ok' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let confirmCalls = 0
    let executedWrite = false
    const { deps, events } = makeMocks({
      planQueue: [plan],
      confirmer: async () => { confirmCalls++; return 'aborted' },
      executor: async (action) => {
        if (action.kind === 'write_file') executedWrite = true
        return { ok: true, output: action.kind, durationMs: 1 }
      },
      trustMode: true,
    })

    const r = await orchestrateCoworkRun('ecris hors workspace', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-risk' })

    assert.equal(r.finished, true)
    assert.equal(confirmCalls, 0, 'trust mode must not open the confirm dialog')
    assert.equal(executedWrite, true, 'destructive action should still execute')
    assert.ok(events.some((e) => (
      e.kind === 'warn'
      && /risque accepte/i.test(e.message)
      && /trust mode/i.test(e.detail || '')
    )), 'accepted risk warning must be emitted before execution')
  })

  test('fullyUnlocked warns but still routes catastrophic delete to executor', async () => {
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'delete_file', path: '/' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let confirmCalls = 0
    let executedDeletePath = ''
    const { deps, events } = makeMocks({
      planQueue: [plan],
      confirmer: async () => { confirmCalls++; return 'aborted' },
      executor: async (action) => {
        if (action.kind === 'delete_file') executedDeletePath = action.path
        return { ok: true, output: action.kind, durationMs: 1 }
      },
      fullyUnlocked: true,
    })

    const r = await orchestrateCoworkRun('supprime tout', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-unlocked' })

    assert.equal(r.finished, true)
    assert.equal(confirmCalls, 0, 'fullyUnlocked must not open the confirm dialog')
    assert.equal(executedDeletePath, '/', 'delete action should reach the executor in the mock')
    assert.ok(events.some((e) => (
      e.kind === 'warn'
      && /risque accepte/i.test(e.message)
      && /Deverrouille/i.test(e.detail || '')
    )), 'fully unlocked risk warning must be emitted before execution')
  })
})

// ---------------------------------------------------------------------------
// Executor failure : run replans before finishing
// ---------------------------------------------------------------------------

describe('executor failure does not crash the run', () => {
  test('failing read_file : error event, recovery hint, then alternative plan finishes', async () => {
    const plan1: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'read_file', path: 'src/missing.ts' },
        { kind: 'reply', message: 'tentative de lecture' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'fallback', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'J ai utilise un fallback apres fichier introuvable.' },
        { kind: 'finish', summary: 'fait apres recuperation' },
      ],
    }
    let plannerCalls = 0
    let executedReplyFromPlan1 = false
    const { deps, events, auditCalls } = makeMocks({
      planQueue: [plan1, plan2],
      executor: async (a) => {
        if (a.kind === 'read_file') return { ok: false, error: 'file not found', durationMs: 5 }
        if (a.kind === 'reply' && a.message === 'tentative de lecture') executedReplyFromPlan1 = true
        return { ok: true, durationMs: 1 }
      },
    })
    deps.plan = async (ctx) => {
      plannerCalls++
      if (plannerCalls === 2) {
        assert.ok(ctx.history.some((h) => h.action.kind === 'think' && /recuperation apres echec/i.test(h.action.topic)))
      }
      return [plan1, plan2][plannerCalls - 1]
    }
    const r = await orchestrateCoworkRun('test', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p' })
    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    assert.equal(executedReplyFromPlan1, false, 'must not run stale reply/finish after failed read')
    assert.ok(events.some((e) => e.kind === 'error' && /ECHEC/i.test(e.message)))
    assert.ok(events.some((e) => /change de strategie/i.test(e.message)))
    assert.equal(auditCalls[0].result?.ok, false)
    assert.match(auditCalls[0].result?.error || '', /file not found/)
  })
})

// ---------------------------------------------------------------------------
// v82m0 — under_extraction annotation (per-card extraction quality flag)
// ---------------------------------------------------------------------------

const { annotateUnderExtraction } = await import('../services/coworkOrchestrator.ts')
import type { CoworkHistoryEntry } from '../services/coworkOrchestrator.ts'

function buildExtractEntry(opts: {
  ok?: boolean
  cards_processed?: number | null | undefined
  items?: unknown[] | null | undefined
  mode?: string
  kind?: 'browser' | 'reply'
  operation?: 'extract_structured' | 'analyze_page'
}): CoworkHistoryEntry {
  const action: CoworkAction = opts.kind === 'reply'
    ? { kind: 'reply', message: 'x' }
    : {
        kind: 'browser',
        operation: opts.operation ?? 'extract_structured',
        payload: opts.mode === undefined
          ? {}
          : { mode: opts.mode },
      } as CoworkAction
  const data: Record<string, unknown> = {}
  if (opts.cards_processed !== undefined) data.cards_processed = opts.cards_processed as never
  if (opts.items !== undefined) data.items = opts.items as never
  return {
    action,
    result: { ok: opts.ok ?? true, data, durationMs: 1 },
  }
}

describe('annotateUnderExtraction (v82m0) — quality-of-extraction flag', () => {
  test('cards_processed=10 + items.length=4 → under_extraction:true (4 < 5)', () => {
    const e = buildExtractEntry({ cards_processed: 10, items: new Array(4).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, true, 'must flag when 4 < 10*0.5')
  })

  test('cards_processed=5 + items.length=4 → no flag (4 >= 2.5 threshold)', () => {
    const e = buildExtractEntry({ cards_processed: 5, items: new Array(4).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, '4 >= 5*0.5 means healthy extraction')
  })

  test('cards_processed=10 + items.length=5 → no flag (boundary 5 >= 5)', () => {
    const e = buildExtractEntry({ cards_processed: 10, items: new Array(5).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'boundary equality must NOT flag')
  })

  test('cards_processed=20 + items.length=9 → under_extraction:true (9 < 10)', () => {
    const e = buildExtractEntry({ cards_processed: 20, items: new Array(9).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, true)
  })

  test('cards_processed undefined → no flag', () => {
    const e = buildExtractEntry({ items: new Array(0).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'missing cards_processed → no signal')
  })

  test('items missing → no flag', () => {
    const e = buildExtractEntry({ cards_processed: 10, mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'missing items → no signal')
  })

  test('items=null → no flag', () => {
    const e = buildExtractEntry({ cards_processed: 10, items: null, mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'null items → no signal')
  })

  test('cards_processed=4 (below 5 floor) + items=0 → no flag', () => {
    const e = buildExtractEntry({ cards_processed: 4, items: [], mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'sub-5 cards_processed has no statistical weight')
  })

  test('mode missing → no flag (gate by mode=card_iteration)', () => {
    const e = buildExtractEntry({ cards_processed: 10, items: new Array(2).fill({}) })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'mode is the per-card flag gate')
  })

  test('mode=free (not card_iteration) → no flag', () => {
    const e = buildExtractEntry({ cards_processed: 10, items: new Array(2).fill({}), mode: 'free' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('result.ok=false → no flag (failure already surfaced as KO)', () => {
    const e = buildExtractEntry({ ok: false, cards_processed: 10, items: new Array(2).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'KO entries must not be flagged')
  })

  test('action kind != browser → no flag', () => {
    const e = buildExtractEntry({ kind: 'reply' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('browser.analyze_page → no flag', () => {
    const e = buildExtractEntry({
      cards_processed: 10,
      items: new Array(2).fill({}),
      mode: 'card_iteration',
      operation: 'analyze_page',
    })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined, 'only extract_structured carries this telemetry')
  })

  test('cards_processed non-finite (NaN) → no flag', () => {
    const e = buildExtractEntry({ cards_processed: NaN, items: new Array(2).fill({}), mode: 'card_iteration' })
    annotateUnderExtraction(e)
    assert.equal(e.under_extraction, undefined)
  })
})

// ---------------------------------------------------------------------------
// v82m3 — annotateHostBaselineDrift : header-driven escalation.
// Threshold = -15.0pp ; sets under_extraction:true + reason='host_baseline_drift'
// when result.data.headers['X-Host-Yield-Delta-Pct'] <= -15.0.
// ---------------------------------------------------------------------------

const {
  annotateHostBaselineDrift,
  HOST_BASELINE_DRIFT_THRESHOLD_PP,
  HOST_BASELINE_DRIFT_REASON,
} = await import('../services/coworkOrchestrator.ts')

function buildEntryWithHeaders(opts: {
  ok?: boolean
  mode?: string
  headers?: Record<string, unknown> | undefined | null
  kind?: 'browser' | 'reply'
  operation?: 'extract_structured' | 'analyze_page'
}): CoworkHistoryEntry {
  const action: CoworkAction = opts.kind === 'reply'
    ? { kind: 'reply', message: 'x' }
    : {
        kind: 'browser',
        operation: opts.operation ?? 'extract_structured',
        payload: opts.mode === undefined ? {} : { mode: opts.mode },
      } as CoworkAction
  const data: Record<string, unknown> = {}
  if (opts.headers !== undefined) data.headers = opts.headers as never
  return {
    action,
    result: { ok: opts.ok ?? true, data, durationMs: 1 },
  }
}

describe('annotateHostBaselineDrift (v82m3) — header-driven escalation', () => {
  test('delta=-20.0 → under_extraction:true + reason=host_baseline_drift', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '-20.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, true)
    assert.equal(e.reason, HOST_BASELINE_DRIFT_REASON)
  })

  test('delta exactly at threshold (-15.0) → no flag (boundary exclusive — strict <)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '-15.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined, '-15.0 >= -15.0 means no escalation (strict <)')
  })

  test('delta just past threshold (-15.1) → flag set', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '-15.1' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, true)
    assert.equal(e.reason, HOST_BASELINE_DRIFT_REASON)
  })

  test('delta=-10.0 (above threshold) → no flag', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '-10.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined, '-10.0 > -15.0 threshold means no escalation')
    assert.equal(e.reason, undefined)
  })

  test('delta=+5.0 (positive — host improving) → no flag', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '+5.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('header absent → no flag (no-op)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Cards-Processed': '10' },  // other headers present, ours absent
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('headers field absent → no flag (no-op)', () => {
    const e = buildEntryWithHeaders({ mode: 'card_iteration' })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('headers field null → no flag (no-op, no throw)', () => {
    const e = buildEntryWithHeaders({ mode: 'card_iteration', headers: null })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('header value malformed ("abc") → no flag (graceful ignore)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': 'not-a-number' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('header value Infinity → no flag (isFinite gate)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': 'Infinity' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('lowercased header key still matched (intermediary case-folding)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      headers: { 'x-host-yield-delta-pct': '-25.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, true)
    assert.equal(e.reason, HOST_BASELINE_DRIFT_REASON)
  })

  test('result.ok=false → no flag (failure already KO)', () => {
    const e = buildEntryWithHeaders({
      ok: false,
      mode: 'card_iteration',
      headers: { 'X-Host-Yield-Delta-Pct': '-30.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('mode != card_iteration → no flag (gate-by-mode)', () => {
    const e = buildEntryWithHeaders({
      mode: 'free',
      headers: { 'X-Host-Yield-Delta-Pct': '-30.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('action kind != browser → no flag', () => {
    const e = buildEntryWithHeaders({ kind: 'reply' })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('browser.analyze_page → no flag (only extract_structured)', () => {
    const e = buildEntryWithHeaders({
      mode: 'card_iteration',
      operation: 'analyze_page',
      headers: { 'X-Host-Yield-Delta-Pct': '-30.0' },
    })
    annotateHostBaselineDrift(e)
    assert.equal(e.under_extraction, undefined)
  })

  test('threshold constant exposed = -15.0pp', () => {
    assert.equal(HOST_BASELINE_DRIFT_THRESHOLD_PP, -15.0)
  })

  test('reason marker constant exposed', () => {
    assert.equal(HOST_BASELINE_DRIFT_REASON, 'host_baseline_drift')
  })
})

// ---------------------------------------------------------------------------
// v82m3 — orchestrator end-to-end : X-Host-Yield-Delta-Pct propagated into
// history.under_extraction for the next planner iteration.
// ---------------------------------------------------------------------------

describe('orchestrator host-baseline-drift propagation (v82m3)', () => {
  test('delta=-20 in result.data.headers flags under_extraction on next ctx', async () => {
    const planA: CoworkPlan = {
      reasoning: 'extract', expectedOutcome: 'feed',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { mode: 'card_iteration', intent: 'feed' } },
      ],
    }
    const planB: CoworkPlan = {
      reasoning: 'reply', expectedOutcome: 'r',
      actions: [
        { kind: 'reply', message: 'voici' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCtx2: { history?: CoworkHistoryEntry[] } | null = null
    const events: CoworkActionEvent[] = []
    const planQueue = [planA, planB]
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        planCalls++
        if (planCalls === 2) plannerCtx2 = { history: ctx.history as CoworkHistoryEntry[] }
        if (planQueue.length === 0) throw new Error('plan queue empty')
        return planQueue.shift()!
      },
      execute: async (action) => {
        if (action.kind === 'browser' && action.operation === 'extract_structured') {
          // Healthy yield (5/10 = 0.5 not under), but delta header below
          // threshold → host_baseline_drift path fires alone.
          return {
            ok: true,
            data: {
              cards_processed: 10,
              items: new Array(7).fill({}),  // 7 >= 5, NOT under by yield-ratio
              headers: { 'X-Host-Yield-Delta-Pct': '-25.0' },
            },
            output: 'mock',
            durationMs: 5,
          }
        }
        return { ok: true, durationMs: 1 }
      },
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    await orchestrateCoworkRun('feed', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-m3' })
    const histEntry = plannerCtx2?.history?.find(
      (h) => h.action.kind === 'browser' && (h.action as { operation?: string }).operation === 'extract_structured',
    )
    assert.ok(histEntry, 'extract entry must reach planner ctx 2')
    assert.equal(histEntry!.under_extraction, true, 'header-driven escalation must flag under_extraction')
    assert.equal(histEntry!.reason, 'host_baseline_drift')
  })

  test('healthy delta (-10) leaves under_extraction unset', async () => {
    const planA: CoworkPlan = {
      reasoning: 'extract', expectedOutcome: 'feed',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { mode: 'card_iteration', intent: 'feed' } },
      ],
    }
    const planB: CoworkPlan = {
      reasoning: 'reply', expectedOutcome: 'r',
      actions: [
        { kind: 'reply', message: 'ok' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCtx2: { history?: CoworkHistoryEntry[] } | null = null
    const events: CoworkActionEvent[] = []
    const planQueue = [planA, planB]
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        planCalls++
        if (planCalls === 2) plannerCtx2 = { history: ctx.history as CoworkHistoryEntry[] }
        if (planQueue.length === 0) throw new Error('plan queue empty')
        return planQueue.shift()!
      },
      execute: async (action) => {
        if (action.kind === 'browser' && action.operation === 'extract_structured') {
          return {
            ok: true,
            data: {
              cards_processed: 10,
              items: new Array(7).fill({}),
              headers: { 'X-Host-Yield-Delta-Pct': '-10.0' },
            },
            output: 'mock',
            durationMs: 5,
          }
        }
        return { ok: true, durationMs: 1 }
      },
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    await orchestrateCoworkRun('feed', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-m3b' })
    const histEntry = plannerCtx2?.history?.find(
      (h) => h.action.kind === 'browser' && (h.action as { operation?: string }).operation === 'extract_structured',
    )
    assert.ok(histEntry)
    assert.equal(histEntry!.under_extraction, undefined, '-10 above -15 threshold must NOT flag')
    assert.equal(histEntry!.reason, undefined)
  })

  test('header absent leaves under_extraction unset (no-op)', async () => {
    const planA: CoworkPlan = {
      reasoning: 'extract', expectedOutcome: 'feed',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { mode: 'card_iteration', intent: 'feed' } },
      ],
    }
    const planB: CoworkPlan = {
      reasoning: 'reply', expectedOutcome: 'r',
      actions: [
        { kind: 'reply', message: 'ok' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCtx2: { history?: CoworkHistoryEntry[] } | null = null
    const events: CoworkActionEvent[] = []
    const planQueue = [planA, planB]
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        planCalls++
        if (planCalls === 2) plannerCtx2 = { history: ctx.history as CoworkHistoryEntry[] }
        if (planQueue.length === 0) throw new Error('plan queue empty')
        return planQueue.shift()!
      },
      execute: async (action) => {
        if (action.kind === 'browser' && action.operation === 'extract_structured') {
          return {
            ok: true,
            data: {
              cards_processed: 10,
              items: new Array(7).fill({}),
              // headers field intentionally absent
            },
            output: 'mock',
            durationMs: 5,
          }
        }
        return { ok: true, durationMs: 1 }
      },
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    await orchestrateCoworkRun('feed', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-m3c' })
    const histEntry = plannerCtx2?.history?.find(
      (h) => h.action.kind === 'browser' && (h.action as { operation?: string }).operation === 'extract_structured',
    )
    assert.ok(histEntry)
    assert.equal(histEntry!.under_extraction, undefined, 'no header → no flag')
  })
})

// ---------------------------------------------------------------------------
// v82m0 — orchestrator end-to-end : under_extraction propagated into the
// history that the planner receives on the NEXT iteration.
// ---------------------------------------------------------------------------

describe('orchestrator history propagation (v82m0)', () => {
  test('low-yield card_iteration sets under_extraction true on next planner ctx', async () => {
    const planA: CoworkPlan = {
      reasoning: 'extract', expectedOutcome: 'feed extrait',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { mode: 'card_iteration', intent: 'feed' } },
      ],
    }
    const planB: CoworkPlan = {
      reasoning: 'reply', expectedOutcome: 'reponse',
      actions: [
        { kind: 'reply', message: 'voici' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCtx2: { history?: CoworkHistoryEntry[] } | null = null
    const events: CoworkActionEvent[] = []
    const auditCalls: Parameters<AuditFn>[0][] = []
    const planQueue = [planA, planB]
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        planCalls++
        if (planCalls === 2) plannerCtx2 = { history: ctx.history as CoworkHistoryEntry[] }
        if (planQueue.length === 0) throw new Error('plan queue empty')
        return planQueue.shift()!
      },
      execute: async (action) => {
        if (action.kind === 'browser' && action.operation === 'extract_structured') {
          return {
            ok: true,
            data: { cards_processed: 10, items: [{ a: 1 }, { a: 2 }] },
            output: 'mock',
            durationMs: 5,
          }
        }
        return { ok: true, output: `mock execution of ${action.kind}`, durationMs: 1 }
      },
      confirm: async () => 'approved',
      audit: (e) => auditCalls.push(e),
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    const r = await orchestrateCoworkRun('feed', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-m0' })
    assert.equal(r.finished, true)
    assert.ok(plannerCtx2, 'second plan call must have happened')
    const histEntry = plannerCtx2!.history?.find(
      (h) => h.action.kind === 'browser' && (h.action as { operation?: string }).operation === 'extract_structured',
    )
    assert.ok(histEntry, 'extract_structured history entry must be present on planner ctx 2')
    assert.equal(histEntry!.under_extraction, true, 'planner sees the under_extraction flag on the next iteration')
  })

  test('healthy yield does NOT set under_extraction on next planner ctx', async () => {
    const planA: CoworkPlan = {
      reasoning: 'extract', expectedOutcome: 'feed',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { mode: 'card_iteration', intent: 'feed' } },
      ],
    }
    const planB: CoworkPlan = {
      reasoning: 'reply', expectedOutcome: 'r',
      actions: [
        { kind: 'reply', message: 'ok' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    let plannerCtx2: { history?: CoworkHistoryEntry[] } | null = null
    const events: CoworkActionEvent[] = []
    const planQueue = [planA, planB]
    let planCalls = 0
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        planCalls++
        if (planCalls === 2) plannerCtx2 = { history: ctx.history as CoworkHistoryEntry[] }
        if (planQueue.length === 0) throw new Error('plan queue empty')
        return planQueue.shift()!
      },
      execute: async (action) => {
        if (action.kind === 'browser' && action.operation === 'extract_structured') {
          return {
            ok: true,
            data: { cards_processed: 5, items: new Array(4).fill({}) },
            output: 'mock',
            durationMs: 5,
          }
        }
        return { ok: true, durationMs: 1 }
      },
      confirm: async () => 'approved',
      getSettings: () => ({ trustMode: false, dangerMode: false }),
    }
    await orchestrateCoworkRun('feed', RUNTIME, CAPS, WS, deps, { onEvent: (e) => events.push(e), promptId: 'p-m0b' })
    const histEntry = plannerCtx2?.history?.find(
      (h) => h.action.kind === 'browser' && (h.action as { operation?: string }).operation === 'extract_structured',
    )
    assert.ok(histEntry, 'history must include extract entry')
    assert.equal(histEntry!.under_extraction, undefined, 'healthy 4/5 yield must NOT flag')
  })
})
