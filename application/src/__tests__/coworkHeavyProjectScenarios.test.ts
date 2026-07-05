/**
 * Heavy Cowork project scenarios.
 *
 * This intentionally simulates the kind of multi-turn mission Juan described:
 * research -> create a real code project in a generated folder -> test it ->
 * later reject it -> inspect/delete/verify -> rebuild from a different base.
 *
 * The executor is an in-memory filesystem. No real files are created/deleted.
 */
import { describe, test } from 'node:test'
import assert from 'node:assert/strict'

const { orchestrateCoworkRun } = await import('../services/coworkOrchestrator.ts')
import type {
  CoworkActionEvent,
  CoworkActionResult,
  CoworkCapability,
  CoworkPlan,
  CoworkRuntime,
} from '../services/coworkTypes.ts'
import type { ExecuteFn, OrchestratorDeps } from '../services/coworkOrchestrator.ts'

const RUNTIME: CoworkRuntime = 'tauri-desktop'
const WS = '/workspace'
const CAPS: CoworkCapability[] = [
  { id: 'filesystem', label: 'fs', description: 'fs', enabled: true, destructive: true },
  { id: 'shell', label: 'shell', description: 'shell', enabled: true, destructive: true },
  { id: 'fetch', label: 'fetch', description: 'fetch', enabled: true, destructive: false },
]

type FakeFsState = {
  files: Map<string, string>
  deletedRoots: string[]
  shellRuns: string[]
  webSearches: string[]
}

function makeDeps(plans: CoworkPlan[], execute: ExecuteFn, events: CoworkActionEvent[], confirmCounter: { count: number }): OrchestratorDeps {
  const queue = [...plans]
  return {
    plan: async () => queue.shift() ?? { reasoning: 'empty', expectedOutcome: 'done', actions: [{ kind: 'finish', summary: 'empty' }] },
    execute,
    confirm: async () => {
      confirmCounter.count += 1
      return 'approved'
    },
    audit: () => undefined,
    getSettings: () => ({ trustMode: false, dangerMode: true }),
  }
}

function createFakeProjectExecutor(state: FakeFsState): ExecuteFn {
  return async (action) => {
    switch (action.kind) {
      case 'think':
        return ok(action.thought)
      case 'web_search':
        state.webSearches.push(action.query)
        return ok('1. State machines for UI workflows\n2. Event-sourced task stores\n3. Node test runner docs', {
          hits: [
            { title: 'State machines for UI workflows', url: 'https://example.test/state-machines' },
            { title: 'Event-sourced task stores', url: 'https://example.test/event-sourcing' },
          ],
        })
      case 'write_file': {
        state.files.set(abs(action.path), action.content)
        return ok(`wrote ${action.path}`, { path: abs(action.path), bytes: action.content.length })
      }
      case 'read_file': {
        const content = state.files.get(abs(action.path))
        return content === undefined
          ? { ok: false, error: `missing ${action.path}`, durationMs: 1 }
          : ok(content, { path: abs(action.path), bytes: content.length })
      }
      case 'list_dir': {
        const root = abs(action.path)
        const entries = [...state.files.keys()]
          .filter((path) => path.startsWith(root + '/') || path === root)
          .map((path) => path.slice(root.length + 1).split('/')[0])
          .filter(Boolean)
          .filter((value, index, array) => array.indexOf(value) === index)
          .sort()
        return ok(entries.join('\n'), { path: root, entries, count: entries.length })
      }
      case 'delete_file': {
        const root = abs(action.path)
        const before = state.files.size
        for (const key of [...state.files.keys()]) {
          if (key === root || key.startsWith(root + '/')) state.files.delete(key)
        }
        state.deletedRoots.push(root)
        return ok(`deleted ${before - state.files.size} file(s)`, { path: root })
      }
      case 'shell': {
        const cwd = abs(action.cwd || WS)
        const line = `${action.command} ${action.args.join(' ')}`.trim()
        state.shellRuns.push(`${cwd}> ${line}`)
        if (/node$/i.test(action.command) && action.args.includes('--test')) {
          return runNodeTest(state, cwd)
        }
        if (/npm$/i.test(action.command) && action.args.includes('test')) {
          return runNodeTest(state, cwd)
        }
        return ok(`ran ${line}`)
      }
      case 'reply':
        return ok(action.message)
      case 'finish':
        return ok(action.summary)
      default:
        return ok(action.kind)
    }
  }
}

function runNodeTest(state: FakeFsState, cwd: string): CoworkActionResult {
  const packageJson = state.files.get(`${cwd}/package.json`)
  const source = [...state.files.keys()].find((path) => path.startsWith(`${cwd}/src/`))
  const testFile = [...state.files.keys()].find((path) => path.includes(`${cwd}/tests/`) || path.includes('.test.'))
  if (!packageJson || !source || !testFile) {
    return { ok: false, error: 'project missing package/source/test', durationMs: 5 }
  }
  const combined = `${packageJson}\n${state.files.get(source)}\n${state.files.get(testFile)}`
  if (/FAIL_TEST/.test(combined)) return { ok: false, error: 'simulated test failure', durationMs: 5 }
  return ok('TAP version 13\n# tests 4\n# pass 4\n# fail 0', { exitCode: 0, tests: 4 })
}

function ok(output = 'ok', data?: unknown): CoworkActionResult {
  return { ok: true, output, data, durationMs: 1 }
}

function abs(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/+/g, '/').replace(/\/$/, '')
  if (/^([a-z]:\/|\/)/i.test(normalized)) return normalized
  return `${WS}/${normalized.replace(/^\.\//, '')}`
}

describe('heavy project multi-turn Cowork scenario', () => {
  test('research -> generate/test project, then delete/verify/rebuild from a different base', async () => {
    const state: FakeFsState = {
      files: new Map(),
      deletedRoots: [],
      shellRuns: [],
      webSearches: [],
    }
    const executor = createFakeProjectExecutor(state)
    const classicDir = 'output/cowork-heavy/taskforge-classic'
    const eventDir = 'output/cowork-heavy/taskforge-event-store'

    const createPlan: CoworkPlan = {
      reasoning: 'Je cree un projet application apres recherche rapide sur les patterns utiles.',
      expectedOutcome: 'Projet cree dans un dossier dedie, puis teste au tour suivant.',
      actions: [
        { kind: 'web_search', query: 'state machine task planner architecture node test runner', limit: 3 },
        { kind: 'write_file', path: `${classicDir}/package.json`, content: '{"type":"module","scripts":{"test":"node --test tests/taskforge.test.js"}}' },
        { kind: 'write_file', path: `${classicDir}/src/taskforge.js`, content: 'export class TaskForge { constructor(){ this.tasks=[] } add(title){ this.tasks.push({ title, done:false }) } stats(){ return { total:this.tasks.length, done:this.tasks.filter(t=>t.done).length } } }' },
        { kind: 'write_file', path: `${classicDir}/tests/taskforge.test.js`, content: 'import test from "node:test"; import assert from "node:assert/strict"; import { TaskForge } from "../src/taskforge.js"; test("stats",()=>{ const app=new TaskForge(); app.add("ship"); assert.deepEqual(app.stats(), { total:1, done:0 }); });' },
        { kind: 'write_file', path: `${classicDir}/README.md`, content: '# TaskForge Classic\n\nSmall class-based task planner generated after research.' },
      ],
    }
    const verifyPlan: CoworkPlan = {
      reasoning: 'Les fichiers sont ecrits. Je teste et relis une source avant de finaliser.',
      expectedOutcome: 'Projet teste et verifie.',
      actions: [
        { kind: 'shell', command: 'node', args: ['--test', 'tests/taskforge.test.js'], cwd: classicDir },
        { kind: 'read_file', path: `${classicDir}/src/taskforge.js` },
        { kind: 'reply', message: '## Projet TaskForge Classic\n- Recherche initiale prise en compte\n- Dossier cree avec package.json, source, test et README\n- Verification : node --test passe avec 4 tests simules\n- Base : architecture classe mutable, volontairement simple mais fonctionnelle' },
        { kind: 'finish', summary: 'Projet Classic cree et teste.' },
      ],
    }

    const createEvents: CoworkActionEvent[] = []
    const confirmCounter = { count: 0 }
    const createDeps = makeDeps([createPlan, verifyPlan], executor, createEvents, confirmCounter)
    const createRun = await orchestrateCoworkRun(
      'cree un gros projet code autonome de gestion de taches, alimente toi par recherche, mets le dans un dossier et teste le',
      RUNTIME,
      CAPS,
      WS,
      createDeps,
      { onEvent: (event) => createEvents.push(event), promptId: 'heavy-create' },
    )

    assert.equal(createRun.finished, true)
    assert.equal(state.webSearches.length, 1, 'Cowork must research before generating')
    assert.ok(state.files.has(abs(`${classicDir}/package.json`)))
    assert.ok(state.files.has(abs(`${classicDir}/src/taskforge.js`)))
    assert.ok(state.files.has(abs(`${classicDir}/tests/taskforge.test.js`)))
    assert.ok(state.shellRuns.some((run) => run.includes('node --test')), 'project tests must run')
    assert.ok(createEvents.some((event) => /TaskForge Classic|node --test/.test(event.detail || event.message)), 'final answer must mention concrete verification')
    const classicSource = state.files.get(abs(`${classicDir}/src/taskforge.js`)) || ''

    const deletePlan: CoworkPlan = {
      reasoning: 'Le user rejette la sortie precedente. J inspecte, supprime, puis verifie que le dossier ancien a disparu.',
      expectedOutcome: 'Ancienne sortie supprimee et etat verifie avant reconstruction.',
      actions: [
        { kind: 'list_dir', path: classicDir, depth: 3 },
        { kind: 'delete_file', path: classicDir },
        { kind: 'list_dir', path: 'output/cowork-heavy', depth: 2 },
      ],
    }
    const rebuildPlan: CoworkPlan = {
      reasoning: 'Je repars sur une base differente : architecture fonctionnelle event-store au lieu de classe mutable.',
      expectedOutcome: 'Nouveau projet application cree, teste et verifie sur une base differente.',
      actions: [
        { kind: 'write_file', path: `${eventDir}/package.json`, content: '{"type":"module","scripts":{"test":"node --test tests/event-store.test.js"}}' },
        { kind: 'write_file', path: `${eventDir}/src/eventStore.js`, content: 'export function createStore(events=[]){ return { append:event=>createStore([...events,event]), snapshot:()=>events.reduce((state,event)=> event.type==="task.added" ? { ...state, tasks:[...state.tasks, { id:event.id, title:event.title, done:false }] } : event.type==="task.done" ? { ...state, tasks:state.tasks.map(t=>t.id===event.id ? { ...t, done:true } : t) } : state, { tasks:[] }) } }' },
        { kind: 'write_file', path: `${eventDir}/tests/event-store.test.js`, content: 'import test from "node:test"; import assert from "node:assert/strict"; import { createStore } from "../src/eventStore.js"; test("event snapshot",()=>{ const s=createStore().append({type:"task.added", id:"a", title:"ship"}).append({type:"task.done", id:"a"}); assert.equal(s.snapshot().tasks[0].done, true); });' },
        { kind: 'write_file', path: `${eventDir}/README.md`, content: '# TaskForge Event Store\n\nSecond base: immutable event-sourced state, replacing the class-based version.' },
        { kind: 'shell', command: 'node', args: ['--test', 'tests/event-store.test.js'], cwd: eventDir },
        { kind: 'read_file', path: `${eventDir}/src/eventStore.js` },
        { kind: 'reply', message: '## Nouvelle base TaskForge Event Store\n- Ancienne sortie inspectee, supprimee et verifiee\n- Rebuild complet dans un nouveau dossier\n- Architecture differente : event store immutable au lieu de classe mutable\n- Verification : node --test passe avec 4 tests simules' },
        { kind: 'finish', summary: 'Nouvelle base creee et testee apres suppression.' },
      ],
    }

    const rebuildEvents: CoworkActionEvent[] = []
    const rebuildDeps = makeDeps([deletePlan, rebuildPlan], executor, rebuildEvents, confirmCounter)
    const rebuildRun = await orchestrateCoworkRun(
      'ca ne me convient pas, supprime la sortie et recommence avec une base differente',
      RUNTIME,
      CAPS,
      WS,
      rebuildDeps,
      {
        onEvent: (event) => rebuildEvents.push(event),
        promptId: 'heavy-rebuild',
      },
    )

    assert.equal(rebuildRun.finished, true)
    assert.equal(confirmCounter.count, 1, 'delete_file must still require approval in preventive mode')
    assert.ok(state.deletedRoots.includes(abs(classicDir)), 'old project folder must be deleted')
    assert.equal([...state.files.keys()].some((path) => path.startsWith(abs(classicDir) + '/')), false, 'old project files must be gone')
    assert.ok(state.files.has(abs(`${eventDir}/package.json`)))
    assert.ok(state.files.has(abs(`${eventDir}/src/eventStore.js`)))
    assert.ok(state.files.has(abs(`${eventDir}/tests/event-store.test.js`)))
    assert.ok(state.shellRuns.some((run) => run.includes('event-store.test.js')), 'rebuilt project tests must run')
    const eventSource = state.files.get(abs(`${eventDir}/src/eventStore.js`)) || ''
    assert.notEqual(eventSource, classicSource, 'second base must not reuse the first implementation')
    assert.match(eventSource, /createStore|event\.type/, 'second base should be event-store style')
    assert.ok(rebuildEvents.some((event) => /Nouvelle base|Architecture differente/.test(event.detail || event.message)), 'final answer must explain the different base')
  })
})
