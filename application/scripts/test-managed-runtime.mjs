#!/usr/bin/env node
// Node 24 executes the actual TypeScript hook; React and runtime I/O are fixtures.
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { after, test } from 'node:test'

const hookUrl = new URL('../src/hooks/useManagedRuntime.ts', import.meta.url).href
const fixtureKey = Symbol.for('aurora.test.managed-runtime')
const fixturePrelude = `const fixture = () => globalThis[Symbol.for('aurora.test.managed-runtime')];`
const fixtureSources = new Map([
  ['react', 'export const useCallback = (callback) => callback;'],
  ['app-store', `${fixturePrelude}
    export const useAppStore = () => fixture().store;
    useAppStore.getState = () => ({ hardware: fixture().hardware });`],
  ['module-log', `${fixturePrelude}
    export const useModuleLogStore = () => ({ log: (...args) => fixture().logs.push(args) });`],
  ['tauri', `${fixturePrelude}
    export async function runtimeEnsureService(service) {
      fixture().ensured.push(service);
      return fixture().ensureResults.get(service) ?? { id: service, running: true, detail: 'Fixture ready' };
    }
    export async function runtimeInspectServices() {
      fixture().inspections += 1;
      return ['ollama', 'comfyui'].map(id => ({ id, running: false }));
    }
    export async function runtimePrepareOllamaModel(model) { fixture().models.push(model); }
    export async function runtimeReleaseService(service, model) {
      fixture().released.push({ service, model });
      return { id: service, running: false, detail: 'Fixture released' };
    }`],
  ['models', `
    export const AUXILIARY_ANALYSIS_MODEL = 'fixture:analysis';
    export const DEFAULT_MAIN_MODEL = 'fixture:main';
    export const resolveConfiguredModel = (model) => model;
    export const selectAdaptiveReasoningModel = () => 'fixture:main';
    export const shouldAvoidHeavyReasoningModel = () => false;`],
])
const fixtureImports = new Map([
  [new URL('../src/stores/appStore.ts', import.meta.url).href, 'app-store'],
  [new URL('../src/stores/moduleLogStore.ts', import.meta.url).href, 'module-log'],
  [new URL('../src/hooks/useTauri.ts', import.meta.url).href, 'tauri'],
  [new URL('../src/config/models.ts', import.meta.url).href, 'models'],
])

const moduleHooks = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === hookUrl) {
      const fixture = specifier === 'react' ? 'react' : fixtureImports.get(new URL(specifier, hookUrl).href)
      if (fixture) return { url: `fixture:managed-runtime/${fixture}`, shortCircuit: true }
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    const prefix = 'fixture:managed-runtime/'
    if (url.startsWith(prefix)) {
      const source = fixtureSources.get(url.slice(prefix.length))
      assert.ok(source, `Unknown module fixture: ${url}`)
      return { format: 'module', source, shortCircuit: true }
    }
    return nextLoad(url, context)
  },
})

const { useManagedRuntime } = await import(hookUrl)

function setup() {
  const state = {
    hardware: {}, logs: [], ensured: [], released: [], models: [], inspections: 0,
    ensureResults: new Map(), jobs: new Map(), runtimeTask: {}, merged: [], pruned: 0,
  }
  state.store = {
    addGenerationJob(job) { state.jobs.set(job.id, structuredClone(job)) },
    setGenerationJob(id, patch) { state.jobs.set(id, { ...state.jobs.get(id), ...structuredClone(patch) }) },
    mergeRuntimeService(service, info) { state.merged.push({ service, ...structuredClone(info) }) },
    pruneGenerationJobs() { state.pruned += 1 },
    setRuntimeTask(patch) { state.runtimeTask = { ...state.runtimeTask, ...structuredClone(patch) } },
    setRuntimeServices(services) { state.runtimeServices = structuredClone(services) },
    setServices(services) { state.services = structuredClone(services) },
  }
  globalThis[fixtureKey] = state
  return { state, executeWithRuntime: useManagedRuntime().executeWithRuntime }
}

function finalJob(state) {
  assert.equal(state.jobs.size, 1)
  return [...state.jobs.values()][0]
}

after(() => {
  moduleHooks.deregister()
  delete globalThis[fixtureKey]
})

test('photo input succeeds with Ollama only and never starts ComfyUI', async () => {
  const { state, executeWithRuntime } = setup()
  const requestedServices = Object.freeze(['ollama'])
  let runs = 0
  const result = await executeWithRuntime({
    module: '3d', title: 'Existing photo reference', services: requestedServices,
    ollamaModel: 'fixture:vision',
    job: async ({ setPhase }) => {
      runs += 1
      setPhase('Reference photo checked', 60)
      return 'verified-photo-result'
    },
  })
  assert.equal(result, 'verified-photo-result')
  assert.equal(runs, 1)
  assert.deepEqual(state.ensured, ['ollama'])
  assert.deepEqual(state.released, [{ service: 'ollama', model: 'fixture:vision' }])
  assert.deepEqual(state.models, ['fixture:vision'])
  assert.deepEqual(requestedServices, ['ollama'])
  assert.equal(finalJob(state).status, 'done')
  assert.equal(state.pruned, 1)
})

test('late ComfyUI and CUDA failure clean both services without retrying', async () => {
  const { state, executeWithRuntime } = setup()
  const requestedServices = Object.freeze(['ollama'])
  let runs = 0
  await assert.rejects(executeWithRuntime({
    module: '3d', title: 'CUDA failure after late ComfyUI startup', services: requestedServices,
    job: async ({ ensureService }) => {
      runs += 1
      await ensureService('comfyui')
      // The connection wording is recoverable alone; CUDA must take precedence.
      throw new Error('CUDA unavailable: connection refused by the GPU runtime')
    },
  }), /CUDA unavailable/)
  assert.equal(runs, 1)
  assert.deepEqual(state.ensured, ['ollama', 'comfyui'])
  assert.deepEqual(state.released.map(({ service }) => service), ['ollama', 'comfyui'])
  assert.equal(state.logs.filter(([, kind]) => kind === 'retry').length, 0)
  assert.deepEqual(requestedServices, ['ollama'])
  assert.deepEqual(finalJob(state).services, ['ollama', 'comfyui'])
  assert.equal(finalJob(state).status, 'error')
  assert.equal(state.runtimeTask.phase, 'error')
  assert.equal(state.pruned, 1)
})

test('a service that reports running false cannot execute the generation job', async () => {
  const { state, executeWithRuntime } = setup()
  state.ensureResults.set('ollama', { id: 'ollama', running: false, detail: 'Service indisponible apres demarrage' })
  let runs = 0
  await assert.rejects(executeWithRuntime({
    module: '3d', title: 'Startup did not produce a running service', services: ['ollama'],
    ollamaModel: 'fixture:vision',
    job: async () => { runs += 1 },
  }), /ollama: Service indisponible apres demarrage/)
  assert.equal(runs, 0)
  assert.deepEqual(state.models, [])
  assert.deepEqual(state.ensured, ['ollama'])
  assert.deepEqual(state.released.map(({ service }) => service), ['ollama'])
  assert.equal(finalJob(state).status, 'error')
  assert.equal(state.pruned, 1)
})

test('successful late ComfyUI startup cleans both services and preserves caller lists', async () => {
  const { state, executeWithRuntime } = setup()
  const requestedServices = Object.freeze(['ollama'])
  const result = await executeWithRuntime({
    module: '3d', title: 'Successful late ComfyUI startup', services: requestedServices,
    job: async ({ ensureService }) => {
      await ensureService('comfyui')
      return 'verified-generated-result'
    },
  })
  assert.equal(result, 'verified-generated-result')
  assert.deepEqual(state.ensured, ['ollama', 'comfyui'])
  assert.deepEqual(state.released.map(({ service }) => service), ['ollama', 'comfyui'])
  assert.deepEqual(requestedServices, ['ollama'])
  assert.deepEqual(finalJob(state).services, ['ollama', 'comfyui'])
  assert.deepEqual(state.runtimeTask.services, ['ollama', 'comfyui'])
  assert.equal(finalJob(state).status, 'done')
  assert.deepEqual(state.services, { ollama: false, comfyui: false })
  assert.equal(state.pruned, 1)
})
