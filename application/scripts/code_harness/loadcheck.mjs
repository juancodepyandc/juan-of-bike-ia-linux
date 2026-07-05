// Smoke test: does the orchestrator module graph load under Node with the shims?
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

const mem = new Map()
const ls = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => mem.set(k, String(v)),
  removeItem: (k) => mem.delete(k),
  clear: () => mem.clear(),
  key: (i) => Array.from(mem.keys())[i] ?? null,
  get length() { return mem.size },
}
const noop = () => {}
globalThis.localStorage = ls
globalThis.window = {
  location: { hostname: 'localhost', href: 'http://localhost/', origin: 'http://localhost' },
  localStorage: ls, addEventListener: noop, removeEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop, removeEventListener: noop }),
}
globalThis.document = {
  documentElement: { setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } },
  body: { setAttribute: noop }, addEventListener: noop,
  createElement: () => ({ setAttribute: noop, style: {}, appendChild: noop }), querySelector: () => null,
}

register('./hooks.mjs', import.meta.url)

try {
  const orch = await import(pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href)
  const store = await import(pathToFileURL(path.resolve('src/stores/appStore.ts')).href)
  console.log('LOAD OK')
  console.log('orchestrateCodeGeneration:', typeof orch.orchestrateCodeGeneration)
  console.log('codeModel:', store.useAppStore.getState().codeModel)
  console.log('visionModel:', store.useAppStore.getState().visionModel)
  console.log('mainModel:', store.useAppStore.getState().mainModel)
} catch (e) {
  console.error('LOAD FAIL:', e && e.stack ? e.stack : e)
  process.exit(1)
}
