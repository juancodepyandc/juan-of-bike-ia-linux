// Shared headless environment for every non-browser entry point of the Code
// module (CLI harness + bridge NDJSON runner).
//
// Why shared: the whole point of the parity work is that CLI, tunnel and UI run
// the SAME pipeline. If each entry point re-declared its own shims and resolve
// hook, they would drift again — which is exactly the failure this module keeps
// paying for. One module, one setup, both callers.

import { register } from 'node:module'

/**
 * Installs the browser-ish globals the (UI-flavoured) service modules read at
 * import time, then registers the resolve hook that lets Node load the src/ TS
 * graph with its extensionless relative specifiers.
 *
 * Must be called BEFORE any dynamic import of the src/ graph.
 */
export function installHeadlessCodeEnv() {
  const mem = new Map()
  const localStorageShim = {
    getItem: (k) => (mem.has(k) ? mem.get(k) : null),
    setItem: (k, v) => mem.set(k, String(v)),
    removeItem: (k) => mem.delete(k),
    clear: () => mem.clear(),
    key: (i) => Array.from(mem.keys())[i] ?? null,
    get length() {
      return mem.size
    },
  }
  const noop = () => {}
  globalThis.localStorage = localStorageShim
  // `currentScript` n est pas cosmetique. Les modules compiles par Emscripten
  // (web-tree-sitter) commencent par:
  //     document = "object" == typeof window ? {currentScript: window.document.currentScript} : null
  // Un `window` sans `document` faisait donc LEVER ce module a l import, et
  // `parseCodeWithTreeSitter` retombait en silence sur l analyse lexicale: sur
  // les canaux CLI/tunnel, l AST reel etait mort depuis le premier jour du
  // harnais. Le shim declare donc `window.document` et `currentScript: null`.
  const documentShim = {
    currentScript: null,
    documentElement: { setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } },
    body: { setAttribute: noop },
    addEventListener: noop,
    createElement: () => ({ setAttribute: noop, style: {}, appendChild: noop }),
    querySelector: () => null,
  }
  globalThis.window = {
    location: { hostname: 'localhost', href: 'http://localhost/', origin: 'http://localhost' },
    localStorage: localStorageShim,
    document: documentShim,
    addEventListener: noop,
    removeEventListener: noop,
    matchMedia: () => ({ matches: false, addEventListener: noop, removeEventListener: noop }),
  }
  globalThis.document = documentShim

  register('./hooks.mjs', import.meta.url)
}

/**
 * Redirects every console channel to stderr.
 *
 * Mandatory for the NDJSON runner: the pipeline logs freely with console.log,
 * and a single stray log line on stdout would corrupt the event stream the
 * bridge parses line by line.
 */
export function routeConsoleToStderr() {
  const toStderr =
    (prefix) =>
    (...args) => {
      try {
        process.stderr.write(
          `${prefix} ${args
            .map((a) => (typeof a === 'string' ? a : (() => {
              try {
                return JSON.stringify(a)
              } catch {
                return String(a)
              }
            })()))
            .join(' ')}\n`,
        )
      } catch {
        /* logging must never break the pipeline */
      }
    }
  console.log = toStderr('[log]')
  console.info = toStderr('[info]')
  console.warn = toStderr('[warn]')
  console.debug = toStderr('[debug]')
  // console.error already goes to stderr — leave it alone.
}
