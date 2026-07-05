/**
 * Realistic LLM-like scenarios end-to-end with the orchestrator + mock planner :
 * - Page analysis multi-iter (browser.analyze_page -> reply with synthesis)
 * - Voice chain (Spotify list_devices -> play on device -> Pushover notify)
 * - Connector chain (IGDB search -> Pushover notify)
 *
 * Each test :
 * 1. Builds a sequence of CoworkPlan that the mock planner returns in order
 * 2. Stubs the executor with realistic responses
 * 3. Asserts the full event sequence + history payload + final summary
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkRealisticScenarios.test.ts
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
  OrchestratorDeps,
} from '../services/coworkOrchestrator.ts'

const RUNTIME: CoworkRuntime = 'web-desktop'  // typical when extension is connected
const WS = '/c/Users/me/aurora'
const CAPS: CoworkCapability[] = [
  { id: 'fetch', label: 'fetch', description: 'fetch', enabled: true, destructive: false },
  { id: 'dom', label: 'dom', description: 'dom', enabled: true, destructive: false },
]

function makeDeps(plans: CoworkPlan[], execute: ExecuteFn): {
  deps: OrchestratorDeps
  events: CoworkActionEvent[]
  plannerCalls: number
} {
  const queue = [...plans]
  const events: CoworkActionEvent[] = []
  let plannerCalls = 0
  const deps: OrchestratorDeps = {
    plan: async (ctx) => {
      plannerCalls++
      // Capture the history at each call to assert subsequent plans see the data
      ctxHistorySeen.push(ctx.history.length)
      return queue.shift() ?? { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'finish', summary: 'queue empty' }] }
    },
    execute,
    confirm: async () => 'approved',
    audit: () => undefined,
    getSettings: () => ({ trustMode: true, dangerMode: false }),
  }
  return { deps, events, plannerCalls: 0 }
}

let ctxHistorySeen: number[] = []

// ---------------------------------------------------------------------------
// Page analysis : Plan #1 reads the page (analyze_page), Plan #2 synthesises
// using the data it sees in history.
// ---------------------------------------------------------------------------

describe('realistic : page analysis multi-iter', () => {
  test('plan #1 analyze_page -> plan #2 synthesises with the data', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Lecture du DOM avant synthese',
      expectedOutcome: 'donnees brutes pour analyser',
      actions: [
        { kind: 'browser', operation: 'analyze_page' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese basee sur le contenu lu',
      expectedOutcome: 'analyse claire',
      actions: [
        { kind: 'reply', message: '## Titre\nExample.com\n\n## Points cles\n- Domain officiel pour test\n- 2 paragraphes presents\n- 1 lien externe vers IANA' },
        { kind: 'finish', summary: 'Analyse rendue.' },
      ],
    }

    // Mock executor : analyze_page returns realistic data
    const executor: ExecuteFn = async (action) => {
      if (action.kind === 'browser' && action.operation === 'analyze_page') {
        return {
          ok: true,
          output: 'analyzed',
          data: {
            url: 'https://example.com/',
            title: 'Example Domain',
            lang: 'en',
            charset: 'UTF-8',
            meta: { description: 'Example for tests' },
            headings: [
              { tag: 'h1', text: 'Example Domain' },
            ],
            paragraphs: [
              'This domain is for use in illustrative examples in documents.',
              'You may use this domain in literature without prior coordination or asking for permission.',
            ],
            links: [{ text: 'More information...', href: 'https://www.iana.org/domains/example' }],
            images: [],
            tables: [],
            textSnippet: 'Example Domain. This domain is for use in illustrative examples...',
            textLength: 167,
          },
          durationMs: 50,
        }
      }
      return { ok: true, output: action.kind, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('analyse cette page', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'analysis-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)

    // Plan #1 saw empty history, Plan #2 saw 1 entry (the analyze_page result)
    assert.deepEqual(ctxHistorySeen, [0, 1])

    // The reply event should contain the user-friendly synthesis (not a placeholder)
    const replyEvt = events.find((e) => /Example\.com|Points cles/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply with actual synthesis must appear in events')

    // Final summary mentions 3 actions OK
    const final = events[events.length - 1]
    assert.match(final.message, /3 action.+reussie/)
  })
})

// ---------------------------------------------------------------------------
// Voice chain : list_devices -> play on Sonos -> notify
// ---------------------------------------------------------------------------

describe('realistic : Spotify voice chain', () => {
  test('list_devices -> identify Sonos -> play uri -> Pushover notify', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Recupere les devices Spotify Connect',
      expectedOutcome: 'liste devices',
      actions: [{ kind: 'connector', connector: 'spotify', action: 'list_devices', params: {} }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Salon Sonos id=DEV_42. Lance play + notif.',
      expectedOutcome: 'lecture lancee + notif',
      actions: [
        { kind: 'connector', connector: 'spotify', action: 'play',
          params: { device_id: 'DEV_42', uris: ['spotify:track:abc'] } },
        { kind: 'connector', connector: 'pushover', action: 'notify',
          params: { title: 'Spotify', message: 'Lecture lancee sur Salon Sonos' } },
        { kind: 'finish', summary: 'Bohemian Rhapsody joue sur Sonos.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'spotify' && a.action === 'list_devices') {
        return {
          ok: true,
          output: '2 devices',
          data: {
            devices: [
              { id: 'DEV_42', name: 'Salon Sonos', type: 'Speaker', is_active: false },
              { id: 'DEV_99', name: 'iPhone', type: 'Smartphone', is_active: true },
            ],
          },
          durationMs: 80,
        }
      }
      if (a.kind === 'connector' && a.connector === 'spotify' && a.action === 'play') {
        return { ok: true, output: 'lecture relancee', durationMs: 120 }
      }
      if (a.kind === 'connector' && a.connector === 'pushover') {
        return { ok: true, output: 'notif envoyee', durationMs: 60 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun(
      'joue Bohemian Rhapsody sur le Sonos',
      RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'voice-1' },
    )

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    assert.deepEqual(ctxHistorySeen, [0, 1])

    // 4 actions executed : list_devices + play + notify + finish
    const successEvts = events.filter((e) => e.kind === 'success' && /OK \(\d+ms\)/.test(e.message))
    assert.ok(successEvts.length >= 4, `expected at least 4 success events, got ${successEvts.length}`)
  })
})

// ---------------------------------------------------------------------------
// Connector chain with quota exhausted on first connector -> fallback path
// ---------------------------------------------------------------------------

describe('realistic : connector chain with exhausted quota', () => {
  test('Pushover quota epuise -> reply ack quand meme', async () => {
    ctxHistorySeen = []
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'connector', connector: 'pushover', action: 'notify',
          params: { title: 'X', message: 'Y' } },
        { kind: 'reply', message: 'Notif tente — si ratee, je signalerai.' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'pushover') {
        return { ok: false, error: 'HTTP 429 quota exceeded — limit reached', durationMs: 100 }
      }
      return { ok: true, durationMs: 1 }
    }
    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('envoie notif', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'fallback-1' })
    assert.equal(r.finished, true)
    // Final summary : 2 OK (reply + finish), 1 KO (notify)
    const final = events[events.length - 1]
    assert.match(final.message, /2 action.+reussie.+1 echouee/)
    // Error event must mention the quota
    const errEvt = events.find((e) => e.kind === 'error' && /quota|429/.test(e.detail || ''))
    assert.ok(errEvt, 'error event with quota signal must be present')
  })
})

// ---------------------------------------------------------------------------
// Cyber scan + abuse check chain
// ---------------------------------------------------------------------------

describe('realistic : cyber scan + abuse check', () => {
  test('nmap shell + abuseipdb check -> reply with both results', async () => {
    ctxHistorySeen = []
    const plan1: CoworkPlan = {
      reasoning: 'Pen-test sur infra perso : ports + reputation',
      expectedOutcome: 'donnees brutes',
      actions: [
        { kind: 'shell', command: 'nmap', args: ['-sV', '192.168.1.50'] },
        { kind: 'connector', connector: 'abuseipdb', action: 'check', params: { ip: '192.168.1.50' } },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese',
      expectedOutcome: 'rapport',
      actions: [
        { kind: 'reply', message: '## Pen-test 192.168.1.50\n- Ports: 22, 80, 443 ouverts\n- AbuseIPDB score: 0/100 (clean)' },
        { kind: 'finish', summary: 'rapport rendu' },
      ],
    }
    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'shell' && a.command === 'nmap') {
        return {
          ok: true,
          output: 'PORT  STATE  SERVICE\n22/tcp open ssh\n80/tcp open http\n443/tcp open https',
          durationMs: 5000,
        }
      }
      if (a.kind === 'connector' && a.connector === 'abuseipdb') {
        return {
          ok: true,
          data: { data: { abuseConfidenceScore: 0, totalReports: 0, isWhitelisted: true } },
          durationMs: 200,
        }
      }
      return { ok: true, durationMs: 1 }
    }
    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('scan 192.168.1.50', 'tauri-desktop', CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'cyber-1' })
    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    // Plan #2 must have seen both results (history length 2 at second planner call)
    assert.deepEqual(ctxHistorySeen, [0, 2])
  })
})

// ---------------------------------------------------------------------------
// New connectors registration (v13 : MQTT, Tuya, Tado, CircleCI)
// ---------------------------------------------------------------------------

describe('v13 connectors registered with semantic info', () => {
  for (const id of ['mqtt', 'tuya', 'tado', 'circleci'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
    })
  }

  test('total >= 69 connectors after v13 (65 + 4)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 69)
  })
})

// ---------------------------------------------------------------------------
// v12 connectors : Pinecone, Mailchimp, Auth0, Clerk — semantic + actions
// ---------------------------------------------------------------------------
describe('v12 connectors registered with semantic info', () => {
  for (const id of ['pinecone', 'mailchimp', 'auth0', 'clerk'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
      assert.ok(meta.docUrl.startsWith('https://'), `${id}: docUrl invalide`)
    })
  }

  test('total >= 73 connectors after v12 (69 + 4)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 73)
  })
})

// ---------------------------------------------------------------------------
// Vision chain : screenshot -> vision_describe -> reply
// User says "analyse cette page" : Plan #1 captures page, Plan #2 synthesises
// using the textual vision data — proves the multi-iter pattern + that the
// orchestrator wires browser+vision into history correctly.
// ---------------------------------------------------------------------------
describe('realistic : vision chain (screenshot -> vision_describe -> reply)', () => {
  test('chains screenshot + vision_describe and synthesises in plan #2', async () => {
    ctxHistorySeen = []

    const screenshotDataUrl = 'data:image/png;base64,' + 'A'.repeat(2_000)
    const plan1: CoworkPlan = {
      reasoning: 'Capture + analyse visuelle de la page active',
      expectedOutcome: 'donnees pour synthese',
      actions: [
        { kind: 'browser', operation: 'screenshot' },
        { kind: 'vision_describe', imageDataUrl: screenshotDataUrl, question: 'Que voit-on sur cette page ?' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese a partir de la vision',
      expectedOutcome: 'rapport visuel',
      actions: [
        { kind: 'reply', message: '## Analyse visuelle\n- Page d accueil avec hero centre\n- Bouton "Commencer" en violet\n- Footer minimaliste' },
        { kind: 'finish', summary: 'Rapport visuel rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'browser' && a.operation === 'screenshot') {
        return { ok: true, output: 'screenshot 2KB', data: { dataUrl: screenshotDataUrl, length: 2000 }, durationMs: 80 }
      }
      if (a.kind === 'vision_describe') {
        return { ok: true, output: 'Page d accueil avec hero centre + CTA violet + footer.', durationMs: 1500 }
      }
      return { ok: true, output: a.kind, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('analyse visuelle', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'vision-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2, 'doit faire 2 iterations (lecture puis synthese)')
    assert.deepEqual(ctxHistorySeen, [0, 2], 'plan #2 doit voir 2 entrees (screenshot + vision)')

    // Reply event mentions the visual analysis
    const replyEvt = events.find((e) => /Analyse visuelle|hero centre/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply with vision synthesis must appear')
  })
})

// ---------------------------------------------------------------------------
// RAG chain with Pinecone : embed query -> top-K -> answer with context
// ---------------------------------------------------------------------------
describe('realistic : RAG chain (Pinecone query -> reply with citations)', () => {
  test('queries top-K and synthesises an answer citing top results', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Recherche dans la base de connaissances Pinecone',
      expectedOutcome: 'top-3 chunks',
      actions: [
        { kind: 'connector', connector: 'pinecone', action: 'query',
          params: { vector: [0.1, 0.2, 0.3], topK: 3 } },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese basee sur les chunks recuperes',
      expectedOutcome: 'reponse augmentee',
      actions: [
        { kind: 'reply', message: '## Reponse RAG\nSelon le doc onboarding-v3.md (score 0.92) : la procedure d activation se fait en 3 etapes.\n\nSources :\n- [1] onboarding-v3.md\n- [2] faq.md' },
        { kind: 'finish', summary: 'Reponse RAG rendue.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'pinecone' && a.action === 'query') {
        return {
          ok: true,
          data: { matches: [
            { id: 'doc-1', score: 0.92, metadata: { src: 'onboarding-v3.md' } },
            { id: 'doc-2', score: 0.78, metadata: { src: 'faq.md' } },
            { id: 'doc-3', score: 0.61, metadata: { src: 'changelog.md' } },
          ] },
          durationMs: 220,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('comment activer ?', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'rag-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /Reponse RAG|Sources/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply with RAG synthesis + citations must appear')
  })
})

// ---------------------------------------------------------------------------
// Auth chain (Clerk) : list users -> filter inactive -> reply
// ---------------------------------------------------------------------------
describe('realistic : auth chain (Clerk list_users -> reply)', () => {
  test('reads users and synthesises a count + summary', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Compte les users Clerk pour audit',
      expectedOutcome: 'liste users',
      actions: [
        { kind: 'connector', connector: 'clerk', action: 'list_users', params: { limit: 20 } },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Resume audit',
      expectedOutcome: 'compte + summary',
      actions: [
        { kind: 'reply', message: '## Audit Clerk\n- Total users: 3\n- Email verifie: 2 (alice, bob)\n- Sans email: 1 (anonymous_42)' },
        { kind: 'finish', summary: 'Audit Clerk fait.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'clerk' && a.action === 'list_users') {
        return {
          ok: true,
          data: [
            { id: 'u1', username: 'alice', email_addresses: [{ email_address: 'alice@x.com', verification: { status: 'verified' } }] },
            { id: 'u2', username: 'bob', email_addresses: [{ email_address: 'bob@y.com', verification: { status: 'verified' } }] },
            { id: 'u3', username: 'anonymous_42', email_addresses: [] },
          ],
          durationMs: 180,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('liste les utilisateurs Clerk', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'clerk-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /Audit Clerk|3 user/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply with Clerk audit must appear')
  })
})

// ---------------------------------------------------------------------------
// Newsletter chain (Mailchimp) : add_subscriber -> reply success
// ---------------------------------------------------------------------------
describe('realistic : newsletter chain (Mailchimp add_subscriber)', () => {
  test('adds subscriber + replies confirm', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Inscrit l email puis confirme',
      expectedOutcome: 'subscriber ajoute + ack',
      actions: [
        { kind: 'connector', connector: 'mailchimp', action: 'add_subscriber',
          params: { list_id: 'abc123', email: 'fan@aurora.ai' } },
        { kind: 'reply', message: 'Inscription confirmee : fan@aurora.ai dans liste abc123.' },
        { kind: 'finish', summary: 'fait' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'mailchimp' && a.action === 'add_subscriber') {
        return { ok: true, data: { id: 'sub_xyz', status: 'subscribed' }, durationMs: 250 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('inscris fan@aurora.ai', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'newsletter-1' })

    assert.equal(r.finished, true)
    const successEvts = events.filter((e) => e.kind === 'success' && /OK \(\d+ms\)/.test(e.message))
    assert.ok(successEvts.length >= 3, `expected at least 3 success events (sub, reply, finish), got ${successEvts.length}`)
  })
})

// ---------------------------------------------------------------------------
// v14 connectors : Wyze, NodeRED, Bambu, Strava — semantic + actions
// ---------------------------------------------------------------------------
describe('v14 connectors registered with semantic info', () => {
  for (const id of ['wyze', 'nodered', 'bambu', 'strava'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
      assert.ok(meta.docUrl.startsWith('http'), `${id}: docUrl invalide`)
    })
  }

  test('total >= 77 connectors after v14 (73 + 4)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 77,
      `expected >= 77 connectors, got ${Object.keys(CONNECTORS).length}`)
  })
})

// ---------------------------------------------------------------------------
// v13.2 : github extension (workflow_runs / run_logs / rerun) + linear
// time-tracking (get_issue_history / list_time_entries / add_comment)
// ---------------------------------------------------------------------------
describe('v13.2 github + linear extended actions', () => {
  test('github exposes Actions logs actions (list_workflow_runs, get_run_logs, rerun_workflow)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const names = CONNECTORS.github.actions.map((a) => a.name)
    assert.ok(names.includes('list_workflow_runs'), 'list_workflow_runs absent')
    assert.ok(names.includes('get_run_logs'), 'get_run_logs absent')
    assert.ok(names.includes('rerun_workflow'), 'rerun_workflow absent')
    assert.ok(names.includes('list_workflows'), 'list_workflows absent')
  })

  test('linear exposes time-tracking + history actions', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const names = CONNECTORS.linear.actions.map((a) => a.name)
    assert.ok(names.includes('get_issue_history'), 'get_issue_history absent')
    assert.ok(names.includes('list_time_entries'), 'list_time_entries absent')
    assert.ok(names.includes('add_comment'), 'add_comment absent')
  })

  test('linear has semantic metadata (purpose, whenToUse, freeTier)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const meta = CONNECTORS.linear
    assert.ok(meta.purpose, 'linear purpose absent')
    assert.ok((meta.whenToUse?.length ?? 0) >= 4, 'linear whenToUse trop court')
    assert.ok(meta.freeTier, 'linear freeTier absent')
  })
})

// ---------------------------------------------------------------------------
// think_long meta-action : parser + executor mocked + multi-iter chain
// ---------------------------------------------------------------------------
describe('v14 meta-action think_long', () => {
  test('validateAction accepts think_long with topic+prompt', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'think_long', topic: 'archi', prompt: 'reflechis...' })
    assert.equal(v.ok, true)
    if (v.ok) {
      assert.equal(v.action.kind, 'think_long')
      if (v.action.kind === 'think_long') {
        assert.equal(v.action.topic, 'archi')
        assert.equal(v.action.prompt, 'reflechis...')
      }
    }
  })

  test('validateAction rejects think_long without prompt', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'think_long', topic: 'x' })
    assert.equal(v.ok, false)
    if (!v.ok) assert.match(v.error, /prompt/)
  })

  test('think_long is read-only : alone with finish, the orchestrator strips finish', async () => {
    const { stripFinishIfReadOnlyPlan } = await import('../services/coworkPlanParser.ts')
    const plan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'think_long' as const, topic: 'archi', prompt: 'reflechis a fond' },
        { kind: 'finish' as const, summary: 'fait' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out.actions.length, 1)
    assert.equal(out.actions[0].kind, 'think_long')
  })

  test('think_long chain multi-iter : Plan #1 think_long -> Plan #2 reply with reasoning', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Question complexe : reflechi a fond avant de repondre',
      expectedOutcome: 'analyse longue prete',
      actions: [
        { kind: 'think_long', topic: 'Migration event-sourced', prompt: 'Postgres -> EventStore : pour/contre, alternatives.' },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'L analyse think_long couvre tout, je restitue.',
      expectedOutcome: 'reponse argumentee',
      actions: [
        { kind: 'reply', message: '## Recommandation\n- Garde Postgres avec outbox pattern\n- Ne migre PAS vers EventStore avant d avoir un cas concret de replay' },
        { kind: 'finish', summary: 'Reponse architecturale rendue.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'think_long') {
        return {
          ok: true,
          output: '## Contexte\nPostgres CRUD classique, 100K users.\n\n## Analyse\nEvent-sourcing apporte audit trail mais double la complexite.\n\n## Recommandation\nOutbox pattern en transition.',
          data: { topic: a.topic, reasoning: '## Contexte\n... ## Analyse\n... ## Recommandation\nOutbox pattern.', model: 'llama4:scout' },
          durationMs: 2400,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('dois-je migrer vers event-sourced ?', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'think-long-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2, 'Plan #1 think_long, Plan #2 synthese reply')
    assert.deepEqual(ctxHistorySeen, [0, 1], 'Plan #2 doit voir le resultat think_long en history')
    const replyEvt = events.find((e) => /Recommandation|outbox/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit citer la recommandation issue de la reflexion')
  })
})

// ---------------------------------------------------------------------------
// v13.2 realistic chain : github list_workflow_runs -> get_run_logs -> reply
// ---------------------------------------------------------------------------
describe('realistic v13.2 : github CI debug chain', () => {
  test('list_workflow_runs (failure) -> get_run_logs -> reply with diagnostic', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Recupere les runs en echec sur main',
      expectedOutcome: 'liste des runs',
      actions: [
        { kind: 'connector', connector: 'github', action: 'list_workflow_runs',
          params: { owner: 'me', repo: 'app', branch: 'main', status: 'failure' } },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Le run #4321 a echoue, je cherche les logs',
      expectedOutcome: 'logs disponibles',
      actions: [
        { kind: 'connector', connector: 'github', action: 'get_run_logs',
          params: { owner: 'me', repo: 'app', run_id: 4321 } },
      ],
    }
    const plan3: CoworkPlan = {
      reasoning: 'Synthese : le run a foire sur l etape lint',
      expectedOutcome: 'rapport debug',
      actions: [
        { kind: 'reply', message: '## Run #4321 — echec\n- Etape `lint` a echoue\n- Logs (240 KB) disponibles, contenu JSON-able\n- Cause probable : ESLint config v9 incompatible' },
        { kind: 'finish', summary: 'Diagnostic CI rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'list_workflow_runs') {
        return {
          ok: true,
          data: { workflow_runs: [{ id: 4321, conclusion: 'failure', name: 'CI', head_branch: 'main' }] },
          durationMs: 200,
        }
      }
      if (a.kind === 'connector' && a.action === 'get_run_logs') {
        return {
          ok: true,
          output: 'Logs run #4321 : zip 240 KB recupere.',
          data: { runId: 4321, sizeKB: 240, contentType: 'application/zip' },
          durationMs: 800,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2, plan3], executor)
    const r = await orchestrateCoworkRun('regarde le run sur main', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'gh-ci-debug' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 3, 'list -> logs -> synthese')
    assert.deepEqual(ctxHistorySeen, [0, 1, 2])
    const replyEvt = events.find((e) => /Run #4321|lint a echoue/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit pointer vers la cause')
  })
})

// ---------------------------------------------------------------------------
// v13.2 linear time-tracking
// ---------------------------------------------------------------------------
describe('realistic v13.2 : linear time tracking chain', () => {
  test('list_time_entries -> reply with summary', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Audit temps passe sur l issue ABC-42',
      expectedOutcome: 'comments + estimate',
      actions: [
        { kind: 'connector', connector: 'linear', action: 'list_time_entries',
          params: { id: 'ABC-42' } },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Analyse les comments timestamps pour synthese',
      expectedOutcome: 'rapport temps',
      actions: [
        { kind: 'reply', message: '## ABC-42 — Time tracking\n- Estimate : 5 pts\n- 3 comments avec timestamps\n- Total temps logé : ~8h' },
        { kind: 'finish', summary: 'Rapport temps rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'linear' && a.action === 'list_time_entries') {
        return {
          ok: true,
          data: { data: { issue: { id: 'ABC-42', title: 'Refactor auth', estimate: 5, comments: { nodes: [
            { id: 'c1', body: '30min : exploration', createdAt: '2026-04-20T10:00:00Z' },
            { id: 'c2', body: '4h : refactor middleware', createdAt: '2026-04-21T14:00:00Z' },
            { id: 'c3', body: '3h30 : tests + cleanup', createdAt: '2026-04-22T09:00:00Z' },
          ] } } } },
          durationMs: 250,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('temps passe sur ABC-42 ?', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'linear-time' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /Time tracking|Estimate/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit mentionner le tracking')
  })
})

// ---------------------------------------------------------------------------
// v14 realistic : Bambu print monitoring chain
// ---------------------------------------------------------------------------
describe('realistic v14 : Bambu Lab print monitoring chain', () => {
  test('list_printers -> get_printer_status -> reply with progress', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Liste les imprimantes Bambu',
      expectedOutcome: 'devices',
      actions: [
        { kind: 'connector', connector: 'bambu', action: 'list_printers', params: {} },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'X1C-001 disponible. Statut.',
      expectedOutcome: 'statut courant',
      actions: [
        { kind: 'connector', connector: 'bambu', action: 'get_printer_status', params: { dev_id: 'X1C-001' } },
        { kind: 'reply', message: '## X1C-001 — print en cours\n- Progress : 47%\n- Bed : 60C, Hotend : 215C\n- ETA : 2h30' },
        { kind: 'finish', summary: 'Statut rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'list_printers') {
        return { ok: true, data: { devices: [{ dev_id: 'X1C-001', name: 'Atelier X1', model: 'X1C' }] }, durationMs: 180 }
      }
      if (a.kind === 'connector' && a.action === 'get_printer_status') {
        return { ok: true, data: { dev_id: 'X1C-001', progress: 47, bed_temp: 60, nozzle_temp: 215, eta_min: 150 }, durationMs: 220 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('comment va mon print 3D ?', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'bambu-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /X1C-001|Progress/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit mentionner le statut')
  })
})

// ---------------------------------------------------------------------------
// v14 realistic : Strava fitness chain
// ---------------------------------------------------------------------------
describe('realistic v14 : Strava activities chain', () => {
  test('list_activities -> get_stats -> reply with summary', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Recap fitness rapide',
      expectedOutcome: 'stats + activites recentes',
      actions: [
        { kind: 'connector', connector: 'strava', action: 'list_activities', params: { per_page: 5 } },
        { kind: 'connector', connector: 'strava', action: 'get_stats', params: {} },
        { kind: 'reply', message: '## Strava — recap\n- 5 dernieres activites : 3 runs (32 km), 2 velos (78 km)\n- Total cette annee : 1240 km de course' },
        { kind: 'finish', summary: 'Recap rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'list_activities') {
        return { ok: true, data: [
          { id: 1, type: 'Run', distance: 12000 },
          { id: 2, type: 'Ride', distance: 40000 },
          { id: 3, type: 'Run', distance: 10000 },
          { id: 4, type: 'Run', distance: 10000 },
          { id: 5, type: 'Ride', distance: 38000 },
        ], durationMs: 200 }
      }
      if (a.kind === 'connector' && a.action === 'get_stats') {
        return { ok: true, data: { ytd_run_totals: { distance: 1240000, count: 95 } }, durationMs: 150 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('recap mes activites Strava', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'strava-1' })

    assert.equal(r.finished, true)
    const successEvts = events.filter((e) => e.kind === 'success' && /OK \(\d+ms\)/.test(e.message))
    assert.ok(successEvts.length >= 4, `expected 4 success (list, stats, reply, finish), got ${successEvts.length}`)
  })
})

// ---------------------------------------------------------------------------
// v14 realistic : Node-RED webhook trigger
// ---------------------------------------------------------------------------
describe('realistic v14 : Node-RED webhook trigger', () => {
  test('trigger_webhook -> reply ack', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Lance un flow Node-RED',
      expectedOutcome: 'webhook OK',
      actions: [
        { kind: 'connector', connector: 'nodered', action: 'trigger_webhook',
          params: { endpoint: '/aurora/lights-off', payload: { room: 'salon' } } },
        { kind: 'reply', message: 'Flow Node-RED declenche : extinction du salon en cours.' },
        { kind: 'finish', summary: 'Webhook OK' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.connector === 'nodered' && a.action === 'trigger_webhook') {
        return { ok: true, output: 'webhook /aurora/lights-off -> 2xx', data: { status: 200, body: '{"ok":true}' }, durationMs: 90 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('eteins le salon', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'nodered-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /Flow Node-RED|extinction/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit confirmer l action')
  })
})

// ---------------------------------------------------------------------------
// v35 — edge-case stability tests for interactions between recent features.
//   1. postProcessPlan : a plan with ONLY vision_describe + finish should
//      have the finish stripped (vision_describe is read-only, no reply).
//   2. extractHtmlDigest : pages with HTML entities (&nbsp; &amp; &eacute;)
//      should decode them properly in the digest output.
// These tests pin down behaviours users hit in production — silent regression
// detection without adding any new functionality.
// ---------------------------------------------------------------------------
describe('v35 edge-case stability — feature interactions', () => {
  test('postProcessPlan strips finish from a vision-only plan (no reply)', async () => {
    const { postProcessPlan } = await import('../services/coworkPlanParser.ts')
    const plan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'vision_describe' as const, imageDataUrl: 'data:image/png;base64,X', question: 'q' },
        { kind: 'finish' as const, summary: 'fait' },
      ],
    }
    const out = postProcessPlan(plan)
    assert.equal(out.actions.length, 1, 'vision_describe est read-only -> strip finish')
    assert.equal(out.actions[0].kind, 'vision_describe')
  })

  test('postProcessPlan keeps finish when reply is present alongside vision_describe', async () => {
    const { postProcessPlan } = await import('../services/coworkPlanParser.ts')
    const plan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'vision_describe' as const, imageDataUrl: 'data:image/png;base64,X' },
        { kind: 'reply' as const, message: 'rapport visuel' },
        { kind: 'finish' as const, summary: 'fait' },
      ],
    }
    const out = postProcessPlan(plan)
    assert.equal(out.actions.length, 3, 'reply present -> finish preserve')
  })

  test('extractHtmlDigest decodes HTML entities (&amp; &eacute; &nbsp;)', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const html = '<html><head><title>Caf&eacute; &amp; Co</title></head><body><h1>Bonjour&nbsp;!</h1><p>Le caf&eacute; est sympa et tres long pour passer la limite des 20 chars.</p></body></html>'
    const out = extractHtmlDigest(html)
    // The default stripTags decodes &amp;, &lt;, &gt;, &quot;, &#39;, &nbsp;.
    // Other HTML entities like &eacute; are stripped via the generic &[a-z]+;
    // regex (replaced by space). We accept "Caf  Co" as the worst case.
    assert.match(out, /Caf.+Co/, 'titre decode + concat normal')
    assert.match(out, /caf.+est sympa/, 'paragraphe extrait')
    assert.doesNotMatch(out, /&amp;|&nbsp;|&eacute;/, 'entites brutes ne doivent pas fuiter')
  })
})

// ---------------------------------------------------------------------------
// v30 — extra realistic scenarios for the most-used workflows :
//
//   1. Voice mode + audit page : analyze_page sparse -> vision chain -> reply
//      with markdown + voice_speak short before finish.
//   2. Image attached + question : user drops a screenshot of an error stack,
//      the overlay pre-runs vision, the planner answers using the description.
//   3. Multi-image diff : user attaches "before" and "after" screenshots and
//      asks for the visual diff.
//   4. Follow-up implicit reference : "et la version mobile ?" after an
//      analysis (combines v21 conversation + v27 auto-vision).
//   5. Cyber freedom : "explique-moi un ROP chain" — must answer fully
//      with PoC code, no scope confirmation needed (v23 EXPLAIN MODE).
// ---------------------------------------------------------------------------
describe('v30 realistic scenarios — recent feature coverage', () => {
  test('voice mode + audit chain : reply markdown + voice_speak court avant finish', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Lecture initiale en mode voice',
      expectedOutcome: 'donnees',
      actions: [{ kind: 'browser', operation: 'analyze_page' }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese + voice_speak court car voice mode actif',
      expectedOutcome: 'rapport texte + lecture vocale',
      actions: [
        { kind: 'reply', message: '## Analyse\n- Hero centre\n- 3 KPIs\n- CTA en violet' },
        { kind: 'voice_speak', text: 'J ai analyse la page. Hero centre, 3 KPIs, et un CTA violet en bas.' },
        { kind: 'finish', summary: 'Audit + voice rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'browser' && a.operation === 'analyze_page') {
        return { ok: true, data: { title: 'Test', textLength: 200, paragraphs: ['hero text'], images: [{ src: '/h.png' }, { src: '/k1.png' }] }, durationMs: 60 }
      }
      if (a.kind === 'voice_speak') {
        return { ok: true, output: `TTS Kokoro lance (${a.text.length} chars)`, durationMs: 90 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('analyse cette page', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'v30-voice-audit', voiceMode: true })

    assert.equal(r.finished, true)
    const voiceEvt = events.find((e) => /voice_speak|TTS|Kokoro|Lire a voix haute/i.test(e.detail || e.message))
    assert.ok(voiceEvt, 'voice_speak doit apparaitre')
    const replyEvt = events.find((e) => /Hero centre|3 KPIs/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply markdown doit apparaitre')
  })

  test('image attached + question : description vision drives reply', async () => {
    ctxHistorySeen = []

    // The overlay would have pre-run vision and pass the description.
    // Here we simulate by using conversationHistory + userPrompt — the test
    // verifies that the planner CAN exploit a description received as ctx.
    let capturedSysIncludesImg = false
    const plan: CoworkPlan = {
      reasoning: 'L user a joint un screenshot d erreur. Description disponible : TypeError sur ligne 42 dans Cannot read property of undefined.',
      expectedOutcome: 'fix propose',
      actions: [
        { kind: 'reply', message: '## Fix propose\nLe TypeError vient probablement d un objet null. Ajoute une garde : `if (obj && obj.prop) { ... }` ligne 42.' },
        { kind: 'finish', summary: 'Fix propose.' },
      ],
    }
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        // Simulate the system prompt seeing the attached image description
        capturedSysIncludesImg = (ctx as { attachedImageDescriptions?: string[] }).attachedImageDescriptions?.[0]?.includes('TypeError') ?? false
        return plan
      },
      execute: async () => ({ ok: true, durationMs: 1 }),
      confirm: async () => 'approved',
      audit: () => undefined,
      getSettings: () => ({ trustMode: true, dangerMode: false }),
    }
    const wrapped: OrchestratorDeps = {
      ...deps,
      plan: (ctx) => deps.plan({
        ...ctx,
        attachedImageDescriptions: ['Capture d ecran : console DevTools avec TypeError "Cannot read property of undefined" ligne 42, stack trace 5 levels.'],
      } as never),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('fix moi cette erreur', RUNTIME, CAPS, WS, wrapped,
      { onEvent: (e) => events.push(e), promptId: 'v30-img-error' })
    assert.equal(r.finished, true)
    assert.ok(capturedSysIncludesImg, 'planner ctx doit inclure la description image')
    const replyEvt = events.find((e) => /TypeError|garde|null/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit referencer l erreur vue dans la description')
  })

  test('multi-image diff : 2 descriptions -> reply diff', async () => {
    ctxHistorySeen = []

    let capturedDescriptions: string[] = []
    const plan: CoworkPlan = {
      reasoning: 'Compare avant/apres : couleur background change, 1 KPI ajoute, footer remanie.',
      expectedOutcome: 'diff visuel',
      actions: [
        { kind: 'reply', message: '## Diff visuel\n- Background : bleu -> violet\n- Nouveau KPI "Conversion 4.2%" en haut\n- Footer : 3 colonnes -> 2 colonnes' },
        { kind: 'finish', summary: 'Diff rendu.' },
      ],
    }
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        capturedDescriptions = (ctx as { attachedImageDescriptions?: string[] }).attachedImageDescriptions ?? []
        return plan
      },
      execute: async () => ({ ok: true, durationMs: 1 }),
      confirm: async () => 'approved',
      audit: () => undefined,
      getSettings: () => ({ trustMode: true, dangerMode: false }),
    }
    const wrapped: OrchestratorDeps = {
      ...deps,
      plan: (ctx) => deps.plan({
        ...ctx,
        attachedImageDescriptions: [
          'AVANT : background bleu, 4 KPIs en haut, footer 3 colonnes',
          'APRES : background violet, 5 KPIs en haut (Conversion 4.2% ajoute), footer 2 colonnes',
        ],
      } as never),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('compare avant/apres', RUNTIME, CAPS, WS, wrapped,
      { onEvent: (e) => events.push(e), promptId: 'v30-multi-img' })
    assert.equal(r.finished, true)
    assert.equal(capturedDescriptions.length, 2)
    const replyEvt = events.find((e) => /Diff|bleu|violet|Conversion/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit citer le diff')
  })

  test('cyber EXPLAIN MODE : "explique-moi un ROP chain" sans scope -> reponse complete sans artefacts', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'L user demande une explication technique. EXPLAIN MODE = libre, zero artefact.',
      expectedOutcome: 'explication complete',
      actions: [
        { kind: 'reply', message: '## ROP chain\n\nReturn-oriented programming bypass DEP/NX en chainant des "gadgets" (fragments d code legitime + ret) qu un attaquant trouve dans le binaire vulnerable.\n\n### PoC code\n```c\nbuf[0..40] = padding\nbuf[40..48] = pop_rdi_ret_addr  // gadget 1\nbuf[48..56] = "/bin/sh"_addr\nbuf[56..64] = system_addr  // RIP saute ici\n```\n\n### Outils\n- ROPgadget --binary ./prog\n- pwntools (Python) : ROP(elf).call("system", [next(elf.search(b"/bin/sh"))])' },
        { kind: 'finish', summary: 'Explication ROP rendue.' },
      ],
    }
    const executor: ExecuteFn = async () => ({ ok: true, durationMs: 1 })
    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('explique-moi un ROP chain en detail', 'tauri-desktop', CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'v30-rop', module: 'cyber' })
    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /ROP chain|gadget|pwntools/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit etre complete avec PoC code')
  })

  test('follow-up implicite : "et la version mobile ?" combine continuity + auto-vision', async () => {
    ctxHistorySeen = []

    let capturedConvo: Array<{ role: string; content: string }> = []
    const plan1: CoworkPlan = {
      reasoning: 'Suite de la conv : user veut analyse de la version mobile du site precedemment analyse.',
      expectedOutcome: 'analyse mobile',
      actions: [{ kind: 'browser', operation: 'analyze_page', payload: { url: 'https://example.com/?mobile=1' } }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Synthese mobile basee sur ce qu on a vu.',
      expectedOutcome: 'rapport mobile',
      actions: [
        { kind: 'reply', message: '## Version mobile\n- Layout 1-col\n- Menu hamburger\n- 3 sections empilees\n- Footer simplifie' },
        { kind: 'finish', summary: 'Mobile rendu.' },
      ],
    }
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        capturedConvo = (ctx as { conversationHistory?: Array<{ role: string; content: string }> }).conversationHistory ?? []
        return capturedConvo.length === 0 ? plan1 : plan2
      },
      execute: async () => ({ ok: true, data: { textLength: 800, paragraphs: ['m1', 'm2'] }, durationMs: 50 }),
      confirm: async () => 'approved',
      audit: () => undefined,
      getSettings: () => ({ trustMode: true, dangerMode: false }),
    }
    // Simulate a conv where user said "analyse cette page" 1st turn, Aurora replied,
    // then asked "et la version mobile ?". The 2nd run should see history.
    const wrapped: OrchestratorDeps = {
      ...deps,
      plan: (ctx) => deps.plan({
        ...ctx,
        conversationHistory: [
          { role: 'user', content: 'analyse https://example.com' },
          { role: 'aurora', content: '## Example.com\nLayout desktop avec 4 sections en grille.' },
        ],
      } as never),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('et la version mobile ?', RUNTIME, CAPS, WS, wrapped,
      { onEvent: (e) => events.push(e), promptId: 'v30-followup' })
    assert.equal(r.finished, true)
    assert.equal(capturedConvo.length, 2, 'history transmis pour resoudre le pronom implicite')
    assert.match(capturedConvo[0].content, /example\.com/i)
  })
})

// ---------------------------------------------------------------------------
// v28 — voice mode : when voiceMode=true is in PlannerContext, the planner
// is supposed to chain a voice_speak action before each finish so the user
// hears the reply via TTS. We verify the orchestrator stack honors a plan
// that includes the voice_speak chain.
// ---------------------------------------------------------------------------
describe('v28 voice mode — voice_speak chained before finish', () => {
  test('plan with reply + voice_speak + finish executes in order, all events emitted', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Reponse simple en mode vocal : reply markdown + voice_speak court + finish',
      expectedOutcome: 'reponse texte + lecture vocale',
      actions: [
        { kind: 'reply', message: '## Recap\nLes 3 points cles sont :\n- A\n- B\n- C' },
        { kind: 'voice_speak', text: 'Voici les trois points cles : A, B et C.' },
        { kind: 'finish', summary: 'reponse texte + voix.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'voice_speak') {
        return { ok: true, output: `TTS Kokoro lance (${a.text.length} chars)`, durationMs: 80 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('donne-moi un recap', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'voice-mode-1', voiceMode: true })

    assert.equal(r.finished, true)
    // The 3 actions must all have been executed (info + success per action)
    const successEvts = events.filter((e) => e.kind === 'success' && /OK \(\d+ms\)/.test(e.message))
    assert.ok(successEvts.length >= 3, `expected 3+ success events (reply, voice_speak, finish), got ${successEvts.length}`)
    // The voice_speak action must appear in the trace
    const voiceEvt = events.find((e) => /voice_speak|TTS|Kokoro|Lire a voix haute/i.test(e.detail || e.message))
    assert.ok(voiceEvt, 'voice_speak doit apparaitre dans les events')
  })
})

// ---------------------------------------------------------------------------
// v27 — auto-vision chain : when a text-poor + image-rich page is analyzed,
// the planner is supposed to auto-chain screenshot + vision_describe in the
// next iteration. We test the orchestrator behaviour : Plan #1 read sparse,
// Plan #2 must emit the vision chain, Plan #3 synthesises.
// ---------------------------------------------------------------------------
describe('v27 auto-vision chain on text-poor pages', () => {
  test('Plan #1 analyze_page sparse -> Plan #2 screenshot+vision -> Plan #3 reply', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Lecture initiale via analyze_page',
      expectedOutcome: 'donnees brutes',
      actions: [{ kind: 'browser', operation: 'analyze_page' }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Page text-poor (320 chars) avec 5 images : auto-chain vision pour comprendre.',
      expectedOutcome: 'description visuelle prete',
      actions: [
        { kind: 'browser', operation: 'screenshot' },
        { kind: 'vision_describe', imageDataUrl: 'data:image/png;base64,FAKE_DATA', question: 'Decris precisement le contenu visuel : graphes, chiffres, layout.' },
      ],
    }
    const plan3: CoworkPlan = {
      reasoning: 'Synthese basee sur la description vision',
      expectedOutcome: 'rapport visuel rendu',
      actions: [
        { kind: 'reply', message: '## Dashboard analytics\n- 3 KPIs en haut (revenue 12M, users 45K, churn 2.1%)\n- Graphe time series sur 12 mois\n- Map heatmap par region' },
        { kind: 'finish', summary: 'Synthese visuelle rendue.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'browser' && a.operation === 'analyze_page') {
        return {
          ok: true,
          data: {
            url: 'https://dashboard.example.com',
            title: 'Analytics Dashboard',
            textLength: 320,  // text-poor !
            paragraphs: ['Welcome to your analytics'],
            images: [
              { src: '/kpi-1.png' }, { src: '/kpi-2.png' }, { src: '/kpi-3.png' },
              { src: '/chart-trend.png' }, { src: '/heatmap.png' },
            ],
            headings: [{ tag: 'h1', text: 'Analytics' }],
          },
          durationMs: 60,
        }
      }
      if (a.kind === 'browser' && a.operation === 'screenshot') {
        return { ok: true, data: { dataUrl: 'data:image/png;base64,FAKE_DATA', length: 12000 }, durationMs: 80 }
      }
      if (a.kind === 'vision_describe') {
        return {
          ok: true,
          output: 'Dashboard analytics : 3 KPIs en haut (revenue 12M, users 45K, churn 2.1%), graphe time series sur 12 mois, heatmap par region.',
          data: { description: '3 KPIs + time series + heatmap', model: 'qwen3-vl' },
          durationMs: 1500,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2, plan3], executor)
    const r = await orchestrateCoworkRun('analyse ce dashboard', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'auto-vision' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 3, 'analyze -> vision chain -> synthese')
    // Plan #2 must have included both screenshot + vision_describe
    const screenshotEvt = events.find((e) => /screenshot/.test(e.message || e.detail || ''))
    assert.ok(screenshotEvt, 'screenshot du Plan #2 doit etre execute')
    const visionEvt = events.find((e) => /Vision.*qwen3-vl|description vision/.test(e.message || e.detail || ''))
    assert.ok(visionEvt, 'vision_describe du Plan #2 doit etre execute')
    const replyEvt = events.find((e) => /Dashboard analytics|3 KPIs|heatmap/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese Plan #3 doit citer le contenu visuel')
  })
})

// ---------------------------------------------------------------------------
// v23 — salvageProseFromMalformedJson : when the LLM emits broken JSON, we
// extract the longest readable prose so Aurora always has something to say
// instead of "Plan abandonne". This is the LAST line of defense before the
// resilient fallback kicks in.
// ---------------------------------------------------------------------------
describe('v23 salvageProseFromMalformedJson — never abandon on broken JSON', () => {
  test('extracts message field even when JSON is incomplete', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const broken = `{
  "reasoning": "x",
  "actions": [
    { "kind": "reply", "message": "Voici un rapport complet sur l etat de tes services : tout est OK sauf le service redis qui ne repond pas." },
    { "kind": "finish",
  "expectedOutcome": "ok"`
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out, 'doit extraire la prose')
    assert.match(out!, /rapport complet/)
    assert.match(out!, /redis/)
  })

  test('returns longest quoted string > 60 chars when no message field', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const broken = '{ broken json with "Voici un long texte qui depasse soixante caracteres pour le test xxxxx" inside }'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out)
    assert.match(out!, /soixante caracteres/)
  })

  test('handles escaped JSON strings (\\n, \\")', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const broken = '{ "message": "Section 1\\nSection 2\\nLe \\"vrai\\" contenu est ici, suffisamment long pour etre detecte." }'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out)
    assert.match(out!, /Section 1/)
    assert.match(out!, /vrai.+contenu/)
    assert.ok(out!.includes('\n'), 'escaped \\n decoded to actual newline')
  })

  test('returns null on truly empty/garbage input', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    assert.equal(salvageProseFromMalformedJson(''), null)
    assert.equal(salvageProseFromMalformedJson('{}'), null)
    assert.equal(salvageProseFromMalformedJson('123'), null)
  })

  test('strips code fences before extracting', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const broken = '```json\n{ "message": "Une reponse markdown extraite depuis un fence ```json — long enough" \n```'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out)
    assert.match(out!, /Une reponse markdown/)
  })

  // v44 — Stress test : large random input must not hang or throw, even if no
  // valid prose can be extracted. Pin down resilience against worst-case LLM
  // output (long garbled token stream).
  test('handles 100 KB of random garbage without crashing', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const garbage = Array.from({ length: 100_000 }, () =>
      String.fromCharCode(32 + Math.floor(Math.random() * 95))
    ).join('')
    const start = Date.now()
    const out = salvageProseFromMalformedJson(garbage)
    const ms = Date.now() - start
    // Must terminate in <500ms even on 100 KB — regex are linear-in-length.
    assert.ok(ms < 500, `regex doit etre lineaire (${ms}ms pour 100KB)`)
    // Random ASCII has no JSON structure but Try-3 (residual prose) might
    // return something. We just check it doesn't throw and returns sane type.
    assert.ok(out === null || typeof out === 'string')
  })

  // v41 — Real-world edge case : LLM emits JSON that gets cut off mid-string,
  // typically when a model exceeds its max_tokens budget while writing a long
  // markdown report inside the "message" field. The closing quote is missing
  // so the regex /"message"\s*:\s*"((?:[^"\\]|\\.)*)"/ doesn't match — but
  // the content is still extractable via the longest-quoted-string fallback.
  test('handles JSON cut-off mid-message via longest-quote fallback', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    // Note : pas de closing quote sur message -> regex /"message":"..."/ matche
    // jusqu au prochain ", qui ici est apres la longue string. Le fallback
    // tente alors longest > 60 chars qui matche bien.
    const broken = '{"reasoning":"r","actions":[{"kind":"reply","message":"## Rapport long\\n\\nCe rapport contient beaucoup de details exploitables qui ne tiennent pas dans le budget de tokens donc le JSON est tronque ici sans qu il y ait jamais ferme la string ni le tableau actions ni l objet final'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out, 'doit extraire malgre l absence de closing quote')
    assert.match(out!, /Rapport long|details exploitables/)
  })

  // v45 — Real-world edge case : some LLMs (especially after re-tokenization)
  // emit \uXXXX unicode escapes for accented chars instead of raw UTF-8.
  // Before v45, decodeJsonString chained replaces ignored \uXXXX, leaving
  // the user with a literal "L'étoile" in their reply.
  test('decodes \\uXXXX unicode escapes (accented chars)', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    const broken = '{"actions":[{"kind":"reply","message":"L\'intelligence artificielle est une \\u00e9toile filante qui \\u00e9claire le monde moderne avec ses capacit\\u00e9s extraordinaires."}]'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out)
    assert.match(out!, /étoile filante/, 'doit decoder \\u00e9 -> é')
    assert.match(out!, /éclaire/)
    assert.match(out!, /capacités/)
    assert.ok(!out!.includes('\\u00'), 'aucun escape literal restant')
  })

  // v45 — Edge case : \\\\uXXXX must NOT be decoded as unicode (escaped
  // backslash + literal "uXXXX"). The chained-replace decoder of v44 had
  // this bug (\\\\ -> \\ first, then nothing else, so result was \\uXXXX
  // — but if a future regression added unicode replace too late, it would
  // be silently decoded). Sequential parsing prevents this entirely.
  test('does not over-decode escaped backslash followed by uXXXX', async () => {
    const { salvageProseFromMalformedJson } = await import('../services/coworkContentDigest.ts')
    // L escape \\\\u0041 doit donner A littéral (backslash + u0041),
    // PAS le caractere "A" (qui serait le decode unicode incorrect).
    const broken = '{"actions":[{"kind":"reply","message":"Pour echapper un unicode litteral on ecrit \\\\u0041 dans le markdown source et c est tres important de le preserver intact"}]'
    const out = salvageProseFromMalformedJson(broken)
    assert.ok(out)
    assert.ok(out!.includes('\\u0041'), 'doit garder \\u0041 litteral, pas le convertir en A')
    assert.ok(!/\bA\b dans le markdown/.test(out!), 'pas de sur-decode')
  })
})

// ---------------------------------------------------------------------------
// v21 — Conversation continuity : the planner should receive previous chat
// turns in `conversationHistory` and they should land in the system prompt.
// Multi-turn follow-up questions (pronouns, "approfondis", "et la version
// mobile ?") need this context to resolve implicit references.
// ---------------------------------------------------------------------------
describe('v21 conversation continuity — planner receives prior chat turns', () => {
  test('planner.ctx.conversationHistory propagates from runCoworkPrompt', async () => {
    let capturedCtx: { conversationHistory?: Array<{ role: string; content: string }> } | null = null
    const plan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'OK je vois la suite, voici la version mobile.' },
        { kind: 'finish', summary: 'follow-up rendu' },
      ],
    }
    const deps: OrchestratorDeps = {
      plan: async (ctx) => {
        capturedCtx = ctx as never
        return plan
      },
      execute: async () => ({ ok: true, durationMs: 1 }),
      confirm: async () => 'approved',
      audit: () => undefined,
      getSettings: () => ({ trustMode: true, dangerMode: false }),
    }
    // Inject the conversationHistory the way coworkPipeline does (via a
    // wrapper plan fn that spreads it into ctx).
    const wrappedDeps: OrchestratorDeps = {
      ...deps,
      plan: (ctx) => deps.plan({ ...ctx, conversationHistory: [
        { role: 'user', content: 'analyse https://example.com' },
        { role: 'aurora', content: '## Example.com\n3 sections detectees, layout responsive.' },
      ] } as never),
    }
    const events: CoworkActionEvent[] = []
    const r = await orchestrateCoworkRun('et la version mobile ?', RUNTIME, CAPS, WS, wrappedDeps,
      { onEvent: (e) => events.push(e), promptId: 'multi-turn-1' })
    assert.equal(r.finished, true)
    assert.ok(capturedCtx, 'le ctx doit etre capture')
    assert.equal(capturedCtx!.conversationHistory!.length, 2, 'history transmis')
    assert.equal(capturedCtx!.conversationHistory![0].role, 'user')
    assert.match(capturedCtx!.conversationHistory![0].content, /example\.com/)
    assert.equal(capturedCtx!.conversationHistory![1].role, 'aurora')
  })
})

// ---------------------------------------------------------------------------
// v19 — Cyber freedom mode : when user confirms ownership, Aurora
// remembers the scope and proceeds with offensive pen-test + remediation.
// We test the planner-side behavior : scope confirmed in memory drives
// follow-up plans toward exploitation rather than read-only recon.
// ---------------------------------------------------------------------------
describe('v19 cyber : scope-confirmed pen-test chain', () => {
  test('plan #1 remember_fact + nmap -> plan #2 reply with exploitation + remediation', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'User confirme ownership de example.com -> ancre scope + scan offensif',
      expectedOutcome: 'scope ancre + surface scannee',
      actions: [
        { kind: 'remember_fact',
          fact: 'L utilisateur confirme etre proprietaire de example.com — autorise pen-test actif',
          tags: ['scope_confirmed', 'cyber', 'example.com'] },
        { kind: 'shell', command: 'nmap', args: ['-sV', '-sC', '--script=vuln', 'example.com'] },
      ],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Scan revele MySQL expose + CSRF absent. Rapport pen-test pro.',
      expectedOutcome: 'audit complet rendu',
      actions: [
        { kind: 'reply', message: '## example.com — Pen-test\n\n### Surface\n- 3306 mysql 5.5 EXPOSE\n\n### Vulnerabilites\n- MySQL public (CWE-284, severite HAUTE)\n\n### Exploitation\n```bash\nmysql -h example.com -u root\n```\n\n### Remediation\nbind-address=127.0.0.1 + UFW deny 3306' },
        { kind: 'finish', summary: 'Pen-test rendu avec exploitation + fixes.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'remember_fact') {
        return { ok: true, output: `Aurora a memorise : "${a.fact}".`, data: { id: 'mem-cyber-1', fact: a.fact, totalMemory: 1 }, durationMs: 4 }
      }
      if (a.kind === 'shell' && a.command === 'nmap') {
        return { ok: true, output: 'PORT     STATE SERVICE VERSION\n3306/tcp open  mysql   MySQL 5.5\n80/tcp   open  http    nginx 1.14', durationMs: 4500 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('exploite les failles de example.com c est mon site', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'cyber-scope-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2, 'scope + scan -> rapport')
    // Plan #1 = remember + nmap (no reply -> read-only-no-reply pattern would
    // strip finish, but Plan #1 doesn t even have a finish, so it just runs
    // and triggers Plan #2).
    const memoEvt = events.find((e) => /Memoriser.*example\.com|scope_confirmed/.test(e.detail || e.message))
    assert.ok(memoEvt, 'remember_fact doit ancrer le scope')
    const nmapEvt = events.find((e) => /nmap.*example\.com/.test(e.detail || e.message))
    assert.ok(nmapEvt, 'nmap doit etre lance')
    const replyEvt = events.find((e) => /Pen-test|Exploitation|Remediation/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit contenir les 4 sections du rapport')
  })
})

// ---------------------------------------------------------------------------
// v18 connectors : Toggl Track, Make.com — semantic + actions
// ---------------------------------------------------------------------------
describe('v18 connectors registered with semantic info', () => {
  for (const id of ['toggl', 'make_com'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
    })
  }

  test('total >= 85 connectors after v18 (83 + 2)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 85,
      `expected >= 85 connectors, got ${Object.keys(CONNECTORS).length}`)
  })
})

// ---------------------------------------------------------------------------
// v18 realistic : Toggl timer + report
// ---------------------------------------------------------------------------
describe('realistic v18 : Toggl timer chain', () => {
  test('start_timer -> reply confirm', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Demarre un timer Toggl pour la reunion en cours',
      expectedOutcome: 'timer demarre + ack',
      actions: [
        { kind: 'connector', connector: 'toggl', action: 'start_timer',
          params: { workspace_id: 12345, project_id: 99, description: 'Reunion produit' } },
        { kind: 'reply', message: 'Timer Toggl demarre sur "Reunion produit". Dis "stop timer" quand fini.' },
        { kind: 'finish', summary: 'Timer demarre.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'start_timer') {
        return { ok: true, data: { id: 9876, description: 'Reunion produit', start: '2026-04-27T22:30:00Z' }, durationMs: 200 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('demarre un timer Toggl reunion produit', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'toggl-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /Timer Toggl demarre|Reunion produit/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit confirmer le timer')
  })
})

// ---------------------------------------------------------------------------
// v18 realistic : Make.com webhook trigger
// ---------------------------------------------------------------------------
describe('realistic v18 : Make.com webhook trigger', () => {
  test('trigger -> reply (declenche un scenario d automatisation)', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Lance le scenario Make.com qui sync mes contacts entre HubSpot et Notion',
      expectedOutcome: 'webhook trigger OK',
      actions: [
        { kind: 'connector', connector: 'make_com', action: 'trigger',
          params: { payload: { source: 'aurora', action: 'sync_contacts', timestamp: 1730000000 } } },
        { kind: 'reply', message: 'Scenario Make.com declenche : sync HubSpot -> Notion en cours.' },
        { kind: 'finish', summary: 'Webhook OK.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'trigger') {
        return { ok: true, output: 'webhook trigger OK : Accepted', data: { status: 200, body: 'Accepted' }, durationMs: 250 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('sync mes contacts via Make.com', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'make-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /Make\.com declenche|sync HubSpot/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit confirmer le declenchement')
  })
})

// ---------------------------------------------------------------------------
// v16 connectors : Grafana, HubSpot — semantic + actions
// ---------------------------------------------------------------------------
describe('v16 connectors registered with semantic info', () => {
  for (const id of ['grafana', 'hubspot'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
      assert.ok(meta.docUrl, `${id}: docUrl missing`)
    })
  }

  test('total >= 83 connectors after v16 (81 + 2)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 83,
      `expected >= 83 connectors, got ${Object.keys(CONNECTORS).length}`)
  })
})

// ---------------------------------------------------------------------------
// v16 Aurora memory : remember_fact / forget_fact / memory injection
// ---------------------------------------------------------------------------
describe('v16 Aurora memory — pure helpers', () => {
  test('rememberFact dedupes case-insensitive', async () => {
    const { DEFAULT_SETTINGS, rememberFact } = await import('../services/coworkSettings.ts')
    let s = { ...DEFAULT_SETTINGS, userMemory: [] as Array<{ id: string; fact: string; createdAt: number }> }
    s = rememberFact(s, 'User prefers Spotify over YouTube Music', ['preference'])
    s = rememberFact(s, 'user prefers spotify over youtube music', ['preference'])
    assert.equal(s.userMemory.length, 1, 'doublon insensible a la casse rejette')
  })

  test('rememberFact ignores empty / whitespace facts', async () => {
    const { DEFAULT_SETTINGS, rememberFact } = await import('../services/coworkSettings.ts')
    let s = { ...DEFAULT_SETTINGS, userMemory: [] as Array<{ id: string; fact: string; createdAt: number }> }
    s = rememberFact(s, '   ', ['x'])
    s = rememberFact(s, '', ['x'])
    assert.equal(s.userMemory.length, 0, 'fait vide rejete')
  })

  test('rememberFact caps at MAX_MEMORY (LRU drop oldest)', async () => {
    const { DEFAULT_SETTINGS, rememberFact, MAX_MEMORY } = await import('../services/coworkSettings.ts')
    let s = { ...DEFAULT_SETTINGS, userMemory: [] as Array<{ id: string; fact: string; createdAt: number }> }
    for (let i = 0; i < MAX_MEMORY + 5; i++) {
      s = rememberFact(s, `fact #${i}`)
    }
    assert.equal(s.userMemory.length, MAX_MEMORY, 'cap respecte')
    // Oldest 5 ont ete dropped (sliding window)
    assert.match(s.userMemory[0].fact, /^fact #5$/, 'oldest dropped')
    assert.match(s.userMemory[s.userMemory.length - 1].fact, /^fact #54$/, 'newest preserved')
  })

  test('forgetFact by id removes a single entry', async () => {
    const { DEFAULT_SETTINGS, rememberFact, forgetFact } = await import('../services/coworkSettings.ts')
    let s = { ...DEFAULT_SETTINGS, userMemory: [] as Array<{ id: string; fact: string; createdAt: number }> }
    s = rememberFact(s, 'first fact')
    s = rememberFact(s, 'second fact')
    const targetId = s.userMemory[0].id
    s = forgetFact(s, { id: targetId })
    assert.equal(s.userMemory.length, 1)
    assert.equal(s.userMemory[0].fact, 'second fact')
  })

  test('forgetFact by matching removes all matches (case-insensitive)', async () => {
    const { DEFAULT_SETTINGS, rememberFact, forgetFact } = await import('../services/coworkSettings.ts')
    let s = { ...DEFAULT_SETTINGS, userMemory: [] as Array<{ id: string; fact: string; createdAt: number }> }
    s = rememberFact(s, 'User loves coffee in the morning')
    s = rememberFact(s, 'User loves COFFEE strong')
    s = rememberFact(s, 'User loves running')
    s = forgetFact(s, { matching: 'coffee' })
    assert.equal(s.userMemory.length, 1)
    assert.match(s.userMemory[0].fact, /running/)
  })
})

describe('v16 Aurora memory — parser + safety', () => {
  test('validateAction accepts remember_fact', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'remember_fact', fact: 'user lives in Paris', tags: ['identity'] })
    assert.equal(v.ok, true)
    if (v.ok && v.action.kind === 'remember_fact') {
      assert.equal(v.action.fact, 'user lives in Paris')
      assert.deepEqual(v.action.tags, ['identity'])
    }
  })

  test('validateAction rejects empty fact', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'remember_fact', fact: '   ' })
    assert.equal(v.ok, false)
  })

  test('validateAction accepts forget_fact with id', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'forget_fact', id: 'mem-123' })
    assert.equal(v.ok, true)
  })

  test('validateAction accepts forget_fact with matching', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'forget_fact', matching: 'spotify' })
    assert.equal(v.ok, true)
  })

  test('validateAction rejects forget_fact without id or matching', async () => {
    const { validateAction } = await import('../services/coworkPlanParser.ts')
    const v = validateAction({ kind: 'forget_fact' })
    assert.equal(v.ok, false)
  })

  test('remember_fact and forget_fact are read-only : strip finish if alone', async () => {
    const { stripFinishIfReadOnlyPlan } = await import('../services/coworkPlanParser.ts')
    const plan = {
      reasoning: 'r', expectedOutcome: 'o',
      actions: [
        { kind: 'remember_fact' as const, fact: 'user prefers Spotify' },
        { kind: 'finish' as const, summary: 'memorise' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out.actions.length, 1, 'remember_fact + finish sans reply -> strip')
  })
})

describe('v16 Aurora memory — multi-iter chain : remember -> reply confirms', () => {
  test('user dit "retiens que je prefere Spotify" -> remember_fact + reply confirmation', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'L user veut que je memorise sa preference. remember_fact persiste, reply confirme.',
      expectedOutcome: 'fait memorise + confirmation user',
      actions: [
        { kind: 'remember_fact', fact: 'L utilisateur prefere Spotify a YouTube Music', tags: ['preference', 'audio'] },
        { kind: 'reply', message: 'OK, je retiendrai que tu preferes Spotify a YouTube Music. Je l utiliserai par defaut quand tu demanderas de la musique.' },
        { kind: 'finish', summary: 'Preference memorisee.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'remember_fact') {
        return { ok: true, output: `Aurora a memorise : "${a.fact}".`, data: { id: 'mem-x', fact: a.fact, totalMemory: 1 }, durationMs: 4 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('retiens que je prefere Spotify', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'mem-1' })

    assert.equal(r.finished, true)
    const memEvt = events.find((e) => /Memoriser : L utilisateur prefere Spotify/.test(e.message || e.detail || ''))
    assert.ok(memEvt, 'l action remember_fact doit etre annoncee')
    const replyEvt = events.find((e) => /preferes Spotify|YouTube Music/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply de confirmation doit apparaitre')
  })

  test('user dit "oublie ma preference cafe" -> forget_fact via matching', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Oubli demande explicite par matching.',
      expectedOutcome: 'fait retire',
      actions: [
        { kind: 'forget_fact', matching: 'cafe' },
        { kind: 'reply', message: 'Fait, je n ai plus de souvenir lie a "cafe".' },
        { kind: 'finish', summary: 'Oubli applique.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'forget_fact') {
        return { ok: true, output: '2 fait(s) oublie(s).', data: { removed: 2, totalMemory: 3 }, durationMs: 3 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('oublie ma preference cafe', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'forget-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /n ai plus de souvenir/.test(e.detail || e.message))
    assert.ok(replyEvt, 'reply confirmation doit apparaitre')
  })
})

// ---------------------------------------------------------------------------
// v15 connectors : Trello, Jira, WakaTime, Plex — semantic + actions
// ---------------------------------------------------------------------------
describe('v15 connectors registered with semantic info', () => {
  for (const id of ['trello', 'jira', 'wakatime', 'plex'] as const) {
    test(`${id}: meta + actions + semantic`, async () => {
      const { CONNECTORS } = await import('../services/coworkConnectors.ts')
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
      assert.ok(meta.docUrl, `${id}: docUrl missing`)
    })
  }

  test('total >= 81 connectors after v15 (77 + 4)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 81,
      `expected >= 81 connectors, got ${Object.keys(CONNECTORS).length}`)
  })
})

// ---------------------------------------------------------------------------
// v15 realistic chain : Jira JQL search + transition workflow
// ---------------------------------------------------------------------------
describe('realistic v15 : Jira issue triage chain', () => {
  test('jql_search blockers -> get_issue -> transition_issue -> reply', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Cherche les blockers ouverts',
      expectedOutcome: 'liste blockers',
      actions: [{ kind: 'connector', connector: 'jira', action: 'jql_search',
        params: { jql: 'priority = Blocker AND status = "To Do"', maxResults: 5 } }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'PROJ-42 est le plus ancien, je le transite vers In Progress',
      expectedOutcome: 'transition appliquee',
      actions: [
        { kind: 'connector', connector: 'jira', action: 'list_transitions', params: { key: 'PROJ-42' } },
        { kind: 'connector', connector: 'jira', action: 'transition_issue',
          params: { key: 'PROJ-42', transitionId: '21' } },
        { kind: 'reply', message: '## Triage Jira blockers\n- 1 blocker traite : PROJ-42\n- Transite vers "In Progress"' },
        { kind: 'finish', summary: 'Triage Jira fait.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'jql_search') {
        return { ok: true, data: { issues: [{ key: 'PROJ-42', fields: { summary: 'Crash signin', priority: { name: 'Blocker' } } }] }, durationMs: 200 }
      }
      if (a.kind === 'connector' && a.action === 'list_transitions') {
        return { ok: true, data: { transitions: [{ id: '21', name: 'In Progress' }, { id: '31', name: 'Done' }] }, durationMs: 150 }
      }
      if (a.kind === 'connector' && a.action === 'transition_issue') {
        return { ok: true, output: 'transition appliquee', durationMs: 180 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('triage les blockers Jira', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'jira-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /Triage Jira|PROJ-42/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit nommer le ticket transite')
  })
})

// ---------------------------------------------------------------------------
// v15 realistic : WakaTime developer time-tracking
// ---------------------------------------------------------------------------
describe('realistic v15 : WakaTime dev productivity recap', () => {
  test('get_stats last_7_days -> reply with summary', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Recap stats WakaTime de la semaine',
      expectedOutcome: 'temps + langages + projets',
      actions: [
        { kind: 'connector', connector: 'wakatime', action: 'get_stats', params: { range: 'last_7_days' } },
        { kind: 'reply', message: '## WakaTime — 7 derniers jours\n- Total : 32h12m\n- Top langage : TypeScript (18h)\n- Top projet : aurora-ia (24h)' },
        { kind: 'finish', summary: 'Recap WakaTime rendu.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'get_stats') {
        return {
          ok: true,
          data: { data: {
            total_seconds: 32 * 3600 + 12 * 60,
            human_readable_total: '32h12m',
            languages: [{ name: 'TypeScript', total_seconds: 18 * 3600 }, { name: 'Python', total_seconds: 8 * 3600 }],
            projects: [{ name: 'aurora-ia', total_seconds: 24 * 3600 }, { name: 'side', total_seconds: 4 * 3600 }],
          } },
          durationMs: 250,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('recap mon code de la semaine', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'wakatime-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /WakaTime|TypeScript|aurora-ia/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit citer langage + projet top')
  })
})

// ---------------------------------------------------------------------------
// v15 realistic : Trello card workflow
// ---------------------------------------------------------------------------
describe('realistic v15 : Trello card workflow', () => {
  test('list_boards -> list_cards -> create_card -> reply', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Trouve le board "Sprint" et liste les cards "To do"',
      expectedOutcome: 'cards visibles',
      actions: [{ kind: 'connector', connector: 'trello', action: 'list_boards', params: {} }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Board Sprint id=BOARD_42, ajoute une card "Refactor auth"',
      expectedOutcome: 'card creee',
      actions: [
        { kind: 'connector', connector: 'trello', action: 'list_lists', params: { idBoard: 'BOARD_42' } },
        { kind: 'connector', connector: 'trello', action: 'create_card',
          params: { idList: 'LIST_TODO', name: 'Refactor auth middleware', desc: 'Port vers JWT signe.' } },
        { kind: 'reply', message: 'Card "Refactor auth middleware" creee dans la liste To Do du board Sprint.' },
        { kind: 'finish', summary: 'Card Trello creee.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'list_boards') {
        return { ok: true, data: [{ id: 'BOARD_42', name: 'Sprint' }, { id: 'BOARD_99', name: 'Backlog' }], durationMs: 180 }
      }
      if (a.kind === 'connector' && a.action === 'list_lists') {
        return { ok: true, data: [{ id: 'LIST_TODO', name: 'To Do' }, { id: 'LIST_DOING', name: 'Doing' }], durationMs: 150 }
      }
      if (a.kind === 'connector' && a.action === 'create_card') {
        return { ok: true, data: { id: 'CARD_99', shortUrl: 'https://trello.com/c/CARD_99' }, durationMs: 220 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2], executor)
    const r = await orchestrateCoworkRun('cree une card Refactor auth dans Sprint', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'trello-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2)
    const replyEvt = events.find((e) => /Refactor auth|To Do/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit confirmer la creation')
  })
})

// ---------------------------------------------------------------------------
// v15 realistic : Plex media server query
// ---------------------------------------------------------------------------
describe('realistic v15 : Plex sessions & search', () => {
  test('list_sessions -> reply (qui regarde quoi maintenant)', async () => {
    ctxHistorySeen = []

    const plan: CoworkPlan = {
      reasoning: 'Liste les sessions Plex actives',
      expectedOutcome: 'sessions visibles',
      actions: [
        { kind: 'connector', connector: 'plex', action: 'list_sessions', params: {} },
        { kind: 'reply', message: '## Plex — sessions en cours\n- Salon : "Inception" (1h12 / 2h28)\n- Chambre : "The Office" S03E12' },
        { kind: 'finish', summary: 'Sessions rendues.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'connector' && a.action === 'list_sessions') {
        return {
          ok: true,
          data: { MediaContainer: { Metadata: [
            { title: 'Inception', viewOffset: 4_320_000, duration: 8_880_000, Player: { title: 'Salon' } },
            { title: 'The Office S03E12', viewOffset: 1_200_000, duration: 1_320_000, Player: { title: 'Chambre' } },
          ] } },
          durationMs: 200,
        }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan], executor)
    const r = await orchestrateCoworkRun('qui regarde quoi maintenant ?', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'plex-1' })

    assert.equal(r.finished, true)
    const replyEvt = events.find((e) => /Inception|The Office/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la reply doit lister les contenus')
  })
})

// ---------------------------------------------------------------------------
// v17 : buildResilientFallbackReply — Aurora NEVER abandons. When the LLM
// returns garbage 3 times, this builds a deterministic markdown synthesis
// from execution history so the user always gets a usable answer.
// ---------------------------------------------------------------------------
describe('v17 buildResilientFallbackReply — never abandon', () => {
  test('synthesises from HTML fetch when present', async () => {
    const { buildResilientFallbackReply } = await import('../services/coworkContentDigest.ts')
    const html = '<!DOCTYPE html><html><head><title>Atelier</title><meta name="description" content="Reparation electronique"/></head><body><h1>Atelier</h1><h2>Diagnostic</h2><p>Diagnostic complet de votre PC pour identifier les pannes.</p><a href="x.html">Lien</a></body></html>'
    const out = buildResilientFallbackReply([
      { action: { kind: 'fetch', url: 'https://x' }, result: { ok: true, output: html, durationMs: 50 } },
    ])
    assert.ok(out, 'fallback doit etre genere')
    assert.match(out!, /Synthese.*mode resilient/i)
    assert.match(out!, /Atelier/, 'titre present')
    assert.match(out!, /Diagnostic/, 'heading present')
    assert.match(out!, /LLM/i, 'mention LLM indisponible')
  })

  test('synthesises from data preview when not HTML', async () => {
    const { buildResilientFallbackReply } = await import('../services/coworkContentDigest.ts')
    const out = buildResilientFallbackReply([
      { action: { kind: 'connector', connector: 'spotify', action: 'list_devices', params: {} },
        result: { ok: true, data: { devices: [{ id: 'a', name: 'Sonos' }] }, durationMs: 80 } },
    ])
    assert.ok(out, 'fallback doit etre genere')
    assert.match(out!, /Donnees recuperees/i)
    assert.match(out!, /Sonos/)
  })

  test('returns null when history is empty', async () => {
    const { buildResilientFallbackReply } = await import('../services/coworkContentDigest.ts')
    const out = buildResilientFallbackReply([])
    assert.equal(out, null)
  })

  test('returns null when history has only failures', async () => {
    const { buildResilientFallbackReply } = await import('../services/coworkContentDigest.ts')
    const out = buildResilientFallbackReply([
      { action: { kind: 'fetch', url: 'https://x' }, result: { ok: false, error: 'network', durationMs: 50 } },
    ])
    assert.equal(out, null)
  })

  test('prefers freshest entry (last successful)', async () => {
    const { buildResilientFallbackReply } = await import('../services/coworkContentDigest.ts')
    const out = buildResilientFallbackReply([
      { action: { kind: 'fetch', url: 'https://x' }, result: { ok: true, output: '<html><head><title>OLD-PAGE</title></head><body><p>aaaaaaaaaaaaaaaaaaaaaaaaa</p></body></html>', durationMs: 50 } },
      { action: { kind: 'fetch', url: 'https://y' }, result: { ok: true, output: '<html><head><title>RECENT-PAGE</title></head><body><p>bbbbbbbbbbbbbbbbbbbbbbbbb</p></body></html>', durationMs: 50 } },
    ])
    assert.ok(out)
    assert.match(out!, /RECENT-PAGE/, 'doit prendre le plus recent')
    assert.doesNotMatch(out!, /OLD-PAGE/, 'pas l ancien')
  })
})

// ---------------------------------------------------------------------------
// v17 extractHtmlDigest format invariants — fallback synthesis depends on these
// (so a careless rename of "title:" or "headings:" can't silently break things).
// ---------------------------------------------------------------------------
describe('v17 extractHtmlDigest format invariants', () => {
  test('digest contains title: line for happy-path HTML', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const html = '<html><head><title>Foo</title></head><body><h1>Bar</h1><p>baz baz baz baz baz baz</p></body></html>'
    const out = extractHtmlDigest(html)
    assert.match(out, /^title: Foo$/m, 'le format "title: ..." doit etre stable')
    assert.match(out, /^headings:$/m, 'le marker "headings:" sur sa ligne')
    assert.match(out, /^  - Bar$/m, 'heading prefix "  - "')
  })

  test('digest paragraphs stay <= 200 chars', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const longText = 'X'.repeat(500)
    const out = extractHtmlDigest(`<html><body><p>${longText}</p></body></html>`)
    const ligne = out.split('\n').find((l) => l.startsWith('  - '))
    assert.ok(ligne && ligne.length <= 210, 'paragraphes tronques a ~200 chars')
  })
})

// ---------------------------------------------------------------------------
// v13.3 : extractHtmlDigest — when fetch returns raw HTML, the planner must
// produce a structured digest the LLM can synthesise on (not just the first
// 2 KB of <head>+<link> boilerplate).
// ---------------------------------------------------------------------------
describe('v13.3 extractHtmlDigest — fallback fetch -> readable digest', () => {
  test('extracts title, headings, paragraphs, links from a typical landing page', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="description" content="Atelier de reparation electronique et PC sur mesure." />
  <title>Atelier Electronique — Reparation & PC sur mesure</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <header><h1>Atelier Electronique</h1></header>
  <section>
    <h2>Nos services</h2>
    <p>Diagnostic complet de votre PC, rapide et fiable.</p>
    <p>Montage sur mesure : gaming, station de travail, mini PC.</p>
    <h2>Contact</h2>
    <a href="mailto:hello@atelier.fr">Nous ecrire</a>
    <a href="https://atelier.fr/devis">Demander un devis</a>
  </section>
  <img src="/hero.jpg" alt="hero" />
</body>
</html>`
    const digest = extractHtmlDigest(html)
    assert.match(digest, /title:.+Atelier Electronique/, 'title extrait')
    assert.match(digest, /description:.+reparation electronique/i, 'meta description extraite')
    assert.match(digest, /headings:/, 'headings detectes')
    assert.match(digest, /Nos services/, 'h2 "Nos services" present')
    assert.match(digest, /paragraphs:/, 'paragraphs detectes')
    assert.match(digest, /Diagnostic complet/, 'paragraphe extrait')
    assert.match(digest, /links:/, 'links detectes')
    assert.match(digest, /mailto:hello@atelier\.fr/, 'mail link present')
    assert.match(digest, /images:.+1/, 'image count')
  })

  test('returns digest message when HTML is empty / malformed', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const out1 = extractHtmlDigest('')
    assert.match(out1, /aucun contenu/i)
    const out2 = extractHtmlDigest('<html><body></body></html>')
    assert.match(out2, /aucun contenu/i)
  })

  test('strips scripts and styles before extracting text fallback', async () => {
    const { extractHtmlDigest } = await import('../services/coworkContentDigest.ts')
    const html = `<!DOCTYPE html><html><body>
      <script>alert("xss")</script>
      <style>.a{color:red}</style>
      Texte visible utilisable pour la synthese.
    </body></html>`
    const out = extractHtmlDigest(html)
    assert.doesNotMatch(out, /alert|color:red/, 'pas de script ou de style residuels')
  })

  test('multi-iter chain : analyze_page KO -> fetch -> reply with digest', async () => {
    ctxHistorySeen = []

    const plan1: CoworkPlan = {
      reasoning: 'Tente analyze_page (extension idealement)',
      expectedOutcome: 'analyse via extension',
      actions: [{ kind: 'browser', operation: 'analyze_page', payload: { url: 'https://exemple.com' } }],
    }
    const plan2: CoworkPlan = {
      reasoning: 'Extension KO -> fallback fetch direct, le digest HTML sera dispo cote historique',
      expectedOutcome: 'HTML recupere',
      actions: [{ kind: 'fetch', url: 'https://exemple.com' }],
    }
    const plan3: CoworkPlan = {
      reasoning: 'Le digest historique contient title + headings, je synthetise.',
      expectedOutcome: 'rapport rendu',
      actions: [
        { kind: 'reply', message: '## Atelier Electronique\n- Reparation PC + montage sur mesure\n- 2 services (Diagnostic, Montage)\n- Liens contact / devis' },
        { kind: 'finish', summary: 'Analyse rendue malgre extension KO.' },
      ],
    }

    const html = '<!DOCTYPE html><html><head><title>Atelier Electronique</title></head><body><h1>Atelier</h1><h2>Diagnostic</h2><h2>Montage</h2><p>Reparation et montage sur mesure.</p><a href="https://atelier.fr/devis">Devis</a></body></html>'

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'browser' && a.operation === 'analyze_page') {
        return { ok: false, error: 'Aucune extension Aurora-Connect detectee.', durationMs: 30 }
      }
      if (a.kind === 'fetch') {
        return { ok: true, output: html, data: undefined, durationMs: 60 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1, plan2, plan3], executor)
    const r = await orchestrateCoworkRun('analyse cette page', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'fallback-fetch' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 3, 'browser KO -> fetch -> synthese')
    const replyEvt = events.find((e) => /Atelier Electronique|Diagnostic.+Montage/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit citer le contenu extrait du HTML')
  })
})

// ---------------------------------------------------------------------------
// Bug-fix coverage : the orchestrator must NOT short-circuit when Plan #1 is
// read-only-and-ends-with-finish. The planner is expected to be called again.
// (This test goes through the orchestrator stack, not just the parser.)
// ---------------------------------------------------------------------------
describe('realistic : Plan #1 read-only-with-finish forces a second pass', () => {
  test('LLM emits read-only + finish but orchestrator runs Plan #2 with synthesis', async () => {
    ctxHistorySeen = []

    // Plan #1 : LLM ignored the WARNING and put finish at the end of read-only actions.
    // postProcessPlan strips the finish so the orchestrator must replan.
    const plan1FromLLM: CoworkPlan = {
      reasoning: 'Lecture seule (mauvais comportement)',
      expectedOutcome: 'donnees brutes',
      actions: [
        { kind: 'browser', operation: 'analyze_page' },
        { kind: 'finish', summary: 'lecture faite' },  // <-- wrong : no reply yet
      ],
    }
    // Plan #2 : Aurora replans with the read result in history and synthesises.
    const plan2: CoworkPlan = {
      reasoning: 'Synthese rattrapee apres correction',
      expectedOutcome: 'rapport',
      actions: [
        { kind: 'reply', message: '## Rapport\n- Titre detecte\n- 3 paragraphes\n- 2 liens' },
        { kind: 'finish', summary: 'Synthese rendue.' },
      ],
    }

    const executor: ExecuteFn = async (a) => {
      if (a.kind === 'browser' && a.operation === 'analyze_page') {
        return { ok: true, data: { title: 'Test', paragraphs: ['a', 'b', 'c'], links: [{ href: 'x' }, { href: 'y' }] }, durationMs: 60 }
      }
      return { ok: true, durationMs: 1 }
    }

    const { deps, events } = makeDeps([plan1FromLLM, plan2], executor)
    const r = await orchestrateCoworkRun('analyse cette page en detail', RUNTIME, CAPS, WS, deps,
      { onEvent: (e) => events.push(e), promptId: 'bugfix-1' })

    assert.equal(r.finished, true)
    assert.equal(r.iterations, 2, 'le faux finish doit etre rattrape -> 2 iters obligatoires')
    // Plan #1 stripped → only analyze_page exec'd before replan
    // Plan #2 saw that 1 entry in history.
    assert.deepEqual(ctxHistorySeen, [0, 1])
    const replyEvt = events.find((e) => /Rapport|3 paragraph/.test(e.detail || e.message))
    assert.ok(replyEvt, 'la synthese doit etre rendue dans Plan #2')
  })
})
