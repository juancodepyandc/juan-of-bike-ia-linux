import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { webcrypto } from 'node:crypto'

// Run the real store with controlled admission and model boundaries.
const source = fs.readFileSync(new URL('../src/stores/forgeQueueStore.ts', import.meta.url), 'utf8')
let storageOptions
let releaseAdmission
let pipelineCalls = 0
let admissionCalls = 0
const finishes = []
const stub = {
  zustand: { create: () => (init) => {
    let state
    const set = (patch) => { state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) } }
    const get = () => state
    state = init(set, get)
    return { getState: get, setState: set }
  } },
  'zustand/middleware': { persist: (init, options) => { storageOptions = options; return init } },
  '../utils/notificationBus.ts': Object.fromEntries(['emit', 'notifyError', 'notifyFinished', 'notifyQueueEnqueued', 'notifyQueueStarted', 'notifyStarted'].map(k => [k, () => {}])),
  './appStore.ts': { useAppStore: { getState: () => ({ mainModel: 'controlled-model' }) } },
  '../services/characterForge.ts': { runForgePipeline: async () => { pipelineCalls++; return { marker: 'saved-output' } } },
  '../services/pythonJobClient.ts': { cancelPythonJob: async () => true },
  '../utils/projectAdmission.ts': { acquireProject: async () => {
    admissionCalls++
    await new Promise(resolve => { releaseAdmission = resolve })
    return async status => { finishes.push(status) }
  } },
}
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
const exports = {}
vm.runInNewContext(output, { exports, require: id => { assert.ok(stub[id], id); return stub[id] }, crypto: webcrypto, setTimeout: callback => { callback(); return 0 }, console })
const store = exports.useForgeQueueStore
store.getState().enqueue('Controlled Forge')
await store.getState()._tick()
assert.equal(admissionCalls, 1, 'local reservation prevents two admissions for the same job')
assert.equal(pipelineCalls, 0, 'no model work before PC admission')
releaseAdmission()
for (let i = 0; i < 10; i++) await Promise.resolve()
assert.equal(pipelineCalls, 1)
assert.deepEqual(finishes, ['completed'])
assert.equal(storageOptions.partialize(store.getState()).jobs[0].result.marker, 'saved-output')

store.setState({ jobs: [{ id: 'interrupted', status: 'running', prompt: 'Unknown result', model: 'controlled-model', artifacts: { meta: { marker: 'checkpoint' } } }] })
exports.attachForgeQueueBootstrap()
assert.equal(store.getState().jobs[0].status, 'error')
assert.equal(store.getState().jobs[0].artifacts.meta.marker, 'checkpoint')
assert.equal(admissionCalls, 1, 'refresh cannot readmit unknown in-flight work')
assert.equal(pipelineCalls, 1)
store.setState({ jobs: [{ id: 'legacy', status: 'queued', startedAt: 1, prompt: 'Legacy interrupted', model: 'controlled-model' }] })
exports.attachForgeQueueBootstrap()
assert.equal(store.getState().jobs[0].status, 'error', 'old persisted running-to-queued jobs are not replayed')
console.log('Forge admission, duplicate ticks, retained outputs and interrupted reload: passed')
