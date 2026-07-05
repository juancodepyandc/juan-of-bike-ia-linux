// v89b — locks the deterministic static_web integrity gate that prevents the
// "substantial page accept-after-1-pass" shortcut from shipping a NON-FUNCTIONAL
// shell (e.g. <script src="script.js"> with no script.js, a blank <canvas>, an
// empty JS-populated <tbody>). Regression guard for the real failure observed on
// the fintech-dashboard run (4 files, no .js, dead page).

// codeOrchestrator pulls in UI-flavoured modules that read browser globals at
// import time — shim them before importing, exactly like the headless harness.
const mem = new Map<string, string>()
const ls = {
  getItem: (k: string) => (mem.has(k) ? mem.get(k)! : null),
  setItem: (k: string, v: string) => void mem.set(k, String(v)),
  removeItem: (k: string) => void mem.delete(k),
  clear: () => mem.clear(),
  key: (i: number) => Array.from(mem.keys())[i] ?? null,
  get length() {
    return mem.size
  },
}
const noop = () => {}
;(globalThis as Record<string, unknown>).localStorage = ls
;(globalThis as Record<string, unknown>).window = {
  location: { hostname: 'localhost', href: 'http://localhost/', origin: 'http://localhost' },
  localStorage: ls,
  addEventListener: noop,
  removeEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop, removeEventListener: noop }),
}
;(globalThis as Record<string, unknown>).document = {
  documentElement: { setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } },
  body: { setAttribute: noop },
  addEventListener: noop,
  createElement: () => ({ setAttribute: noop, style: {}, appendChild: noop }),
  querySelector: () => null,
}

import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'

// codeOrchestrator imports the src/ TS graph with extensionless relative
// specifiers (e.g. './ollamaResilience'); Node's bare strip-types runner can't
// resolve those, so register the same resolve hook the headless harness uses,
// then load the module dynamically (after the hook is in place).
register('../../scripts/code_harness/hooks.mjs', import.meta.url)
const { checkWebPageIntegrity } = await import('../services/codeOrchestrator.ts')

const INTERACTIVE_PROMPT =
  'dashboard fintech temps réel, graphique live setInterval, tableau triable filtrable, convertisseur, toggle thème'

describe('checkWebPageIntegrity — static_web functional shell guard', () => {
  test('flags a <script src> referencing a file absent from the project', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><body><h1>App</h1><table><tbody id="t"></tbody></table>' +
          '<canvas id="c"></canvas><script src="script.js"></script></body></html>',
      },
      { name: 'style.css', content: 'body{color:#fff}' },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, false)
    assert.ok(r.missing.some((m) => /script\.js/.test(m)), 'should name the missing script.js')
    assert.ok(r.hint.length > 0)
  })

  test('flags a <canvas> with no getContext anywhere', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><body><canvas id="c"></canvas>' +
          '<script>const x = 1; document.title = "hi"</script></body></html>',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, false)
    assert.ok(r.missing.some((m) => /canvas/i.test(m)))
  })

  test('passes a healthy page: inline JS, getContext, populated table', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><head><link href="style.css" rel="stylesheet"></head><body>' +
          '<canvas id="c"></canvas><table><tbody id="t"></tbody></table>' +
          '<script>const ctx=document.getElementById("c").getContext("2d");' +
          'function draw(){ctx.fillRect(0,0,10,10)}setInterval(draw,1000);' +
          'document.getElementById("t").innerHTML="<tr><td>AAPL</td></tr>"</script></body></html>',
      },
      { name: 'style.css', content: 'body{color:#fff}' },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, true, `expected ok, got: ${r.missing.join(' | ')}`)
  })

  test('does not false-positive on a plain static landing page (no interactivity asked)', () => {
    const files = [{ name: 'index.html', content: '<!doctype html><html><body><h1>Hello</h1><p>Static.</p></body></html>' }]
    const r = checkWebPageIntegrity(files, 'une page vitrine simple statique')
    assert.equal(r.ok, true, `expected ok, got: ${r.missing.join(' | ')}`)
  })

  test('flags a truncated/unbalanced script.js (num_predict cut-off)', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><body><canvas id="c"></canvas><script src="script.js"></script></body></html>',
      },
      {
        name: 'script.js',
        // ends mid-statement with an unclosed paren — the real failure mode
        content:
          'const ctx = document.getElementById("c").getContext("2d");\n' +
          'function gen() {\n  const data = [];\n  for (let i = 0; i',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, false)
    assert.ok(r.missing.some((m) => /tronqu|équilibr/i.test(m)), 'should flag the truncated JS')
  })

  test('does not flag valid JS containing brackets inside strings/regex/templates', () => {
    const files = [
      {
        name: 'index.html',
        content: '<!doctype html><html><body><div id="x"></div><script src="app.js"></script></body></html>',
      },
      {
        name: 'app.js',
        content:
          'const re = /[a-z(){}]+/g;\n' +
          'const s = "a ( unbalanced { string ] paren";\n' +
          'const t = `tmpl ${1 + (2 * 3)} ) } ]`;\n' +
          'document.getElementById("x").addEventListener("click", () => { console.log(re, s, t) });',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, true, `expected ok, got: ${r.missing.join(' | ')}`)
  })

  test('flags JS targeting an element id absent from the HTML (dead feature)', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><body><canvas id="pnl-chart"></canvas><script src="app.js"></script></body></html>',
      },
      {
        name: 'app.js',
        // id mismatch: HTML has "pnl-chart", JS reads "today-pnl-chart" → null
        content:
          'function init(){ const ctx = document.getElementById("today-pnl-chart").getContext("2d"); ctx.fillRect(0,0,10,10); }\n' +
          'setInterval(init, 1000); init();',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, false)
    assert.ok(r.missing.some((m) => /today-pnl-chart|inexistants/i.test(m)), 'should flag the dangling id')
  })

  test('does not flag dynamic/concatenated ids or JS-created ids', () => {
    const files = [
      {
        name: 'index.html',
        content: '<!doctype html><html><body><div id="list"></div><script src="app.js"></script></body></html>',
      },
      {
        name: 'app.js',
        content:
          'const c = document.getElementById("list");\n' +
          'c.innerHTML = `<div id="row-1">x</div>`;\n' +
          'for (let i = 0; i < 3; i++) { const el = document.getElementById("row-" + i); if (el) el.textContent = i; }\n' +
          'document.querySelector("#list").addEventListener("click", () => {});',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, true, `expected ok, got: ${r.missing.join(' | ')}`)
  })

  test('ignores external CDN scripts (Tailwind) — only local files count', () => {
    const files = [
      {
        name: 'index.html',
        content:
          '<!doctype html><html><head><script src="https://cdn.tailwindcss.com"></script></head>' +
          '<body><h1>App</h1><script>document.querySelector("h1").addEventListener("click",()=>{})</script></body></html>',
      },
    ]
    const r = checkWebPageIntegrity(files, INTERACTIVE_PROMPT)
    assert.equal(r.ok, true, `expected ok, got: ${r.missing.join(' | ')}`)
  })
})
