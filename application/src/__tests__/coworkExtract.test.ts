/**
 * v82l7 — Tests for the `browser.extract_structured` action (comprehension-based
 * extraction via Ollama, introduced in v82l6).
 *
 * Goal:
 *   - validateAction (safety) accepts extract_structured as a non-destructive
 *     read-only browser op (it doesn't mutate the page, it only forwards the
 *     scraped text to /api/cowork/extract-structured for LLM JSON shaping).
 *   - validateAction (parser) accepts the action shape, with or without payload.
 *   - planSignature DOES dedup two identical extract_structured calls (same
 *     intent), but DOES NOT dedup two distinct intents — different intents
 *     must yield different signatures so the planner can chain them.
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkExtract.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

import { validateAction as validateSafety } from '../services/coworkSafety.ts'
import {
  validateAction as validateParse,
  planSignature,
} from '../services/coworkPlanParser.ts'
import type { CoworkPlan } from '../services/coworkTypes.ts'

const WS = '/c/Users/me/aurora'
const RT_DESKTOP = 'tauri-desktop'
const RT_WEB = 'web-desktop'
const RT_MOBILE = 'web-mobile'

// ---------------------------------------------------------------------------
// Safety gate (coworkSafety.validateAction)
// ---------------------------------------------------------------------------

describe('extract_structured — safety verdict', () => {
  test('extract_structured is allowed on web-desktop', () => {
    const v = validateSafety(
      { kind: 'browser', operation: 'extract_structured', payload: { intent: 'foo' } },
      RT_WEB,
      WS,
    )
    assert.equal(v.decision, 'allow')
    assert.equal(v.destructive, false)
  })

  test('extract_structured is allowed on tauri-desktop', () => {
    const v = validateSafety(
      { kind: 'browser', operation: 'extract_structured', payload: { intent: 'liste cours' } },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'allow')
  })

  test('extract_structured is allowed on web-mobile (read-only)', () => {
    // Mobile lockdown blocks DESTRUCTIVE actions ; extract_structured only
    // reads the active tab text + calls Ollama, so it must remain available
    // to mobile users (e.g. a phone using the bridge through the extension).
    const v = validateSafety(
      { kind: 'browser', operation: 'extract_structured', payload: { intent: 'prix produits' } },
      RT_MOBILE,
      WS,
    )
    assert.equal(v.decision, 'allow')
  })

  test('extract_structured allowed even without payload (intent provided later)', () => {
    // The bridge enforces the intent-required rule (returns 400 if missing).
    // The safety gate is purely about whether the action is destructive ; it
    // doesn't revalidate semantics.
    const v = validateSafety(
      { kind: 'browser', operation: 'extract_structured' },
      RT_WEB,
      WS,
    )
    assert.equal(v.decision, 'allow')
  })
})

// ---------------------------------------------------------------------------
// Parser gate (coworkPlanParser.validateAction)
// ---------------------------------------------------------------------------

describe('extract_structured — parser validation', () => {
  test('parses with intent payload', () => {
    const r = validateParse({
      kind: 'browser',
      operation: 'extract_structured',
      payload: { intent: 'liste des cours du jour avec heure et salle' },
    })
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.action.kind, 'browser')
      assert.equal(r.action.kind === 'browser' && r.action.operation, 'extract_structured')
    }
  })

  test('parses without payload (defaults to empty)', () => {
    const r = validateParse({ kind: 'browser', operation: 'extract_structured' })
    assert.equal(r.ok, true)
  })

  test('parses with includeImage + model overrides', () => {
    const r = validateParse({
      kind: 'browser',
      operation: 'extract_structured',
      payload: {
        intent: 'tableau des matchs avec score',
        includeImage: true,
        model: 'qwen3-vl:8b',
      },
    })
    assert.equal(r.ok, true)
  })

  test('all 11 browser operations valid (incl. extract_structured)', () => {
    // Mirror of the analogous assertion in coworkBrowserAndMeshy.test.ts —
    // bumped to 11 ops once extract_structured was registered in v82l7.
    const ops = [
      'list_tabs', 'get_active_tab', 'read_dom', 'read_html',
      'click', 'fill', 'eval', 'screenshot', 'navigate',
      'analyze_page', 'extract_structured',
    ]
    for (const op of ops) {
      const r = validateParse({ kind: 'browser', operation: op })
      assert.equal(r.ok, true, `operation ${op} should be valid`)
    }
  })

  test('rejects unknown operation that resembles extract_structured', () => {
    const r = validateParse({ kind: 'browser', operation: 'extract_unstructured' })
    assert.equal(r.ok, false)
  })
})

// ---------------------------------------------------------------------------
// planSignature dedup behavior — different intents must produce different
// signatures so the orchestrator's loop-detection doesn't bail out on
// legitimate chained extraction calls.
// ---------------------------------------------------------------------------

describe('extract_structured — plan signature dedup', () => {
  function planFor(intent: string): CoworkPlan {
    return {
      reasoning: 'extract',
      expectedOutcome: 'items extracted',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { intent } },
        { kind: 'finish', summary: 'done' },
      ],
    }
  }

  test('same intent → identical signature (legitimate dedup)', () => {
    const a = planSignature(planFor('liste des cours du jour'))
    const b = planSignature(planFor('liste des cours du jour'))
    assert.equal(a, b)
  })

  test('different intents → different signatures', () => {
    const a = planSignature(planFor('liste des cours du jour'))
    const b = planSignature(planFor('prix des produits avec devise'))
    assert.notEqual(a, b, 'distinct intents must yield distinct plan signatures')
  })

  test('intent + includeImage flag → different signatures', () => {
    // includeImage:true triggers a vision-capable model on the bridge ; the
    // signature must reflect the payload shape so a re-plan that toggles
    // image inclusion isn't dismissed as a duplicate.
    const without: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'e',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { intent: 'cours' } },
      ],
    }
    const withImg: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'e',
      actions: [
        { kind: 'browser', operation: 'extract_structured', payload: { intent: 'cours', includeImage: true } },
      ],
    }
    assert.notEqual(planSignature(without), planSignature(withImg))
  })

  test('extract_structured signature differs from analyze_page', () => {
    // Two distinct browser ops on the same page must never collide, even
    // if their payloads happen to look similar.
    const extractPlan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'e',
      actions: [{ kind: 'browser', operation: 'extract_structured', payload: { intent: 'x' } }],
    }
    const analyzePlan: CoworkPlan = {
      reasoning: 'r', expectedOutcome: 'e',
      actions: [{ kind: 'browser', operation: 'analyze_page', payload: { intent: 'x' } }],
    }
    assert.notEqual(planSignature(extractPlan), planSignature(analyzePlan))
  })
})

// ---------------------------------------------------------------------------
// v82l8 — Live wire-call integration test.
//
// Hits the real bridge at /api/cowork/extract-structured with a synthetic HTML
// blob and asserts the LLM returns at least one item. Skipped when the bridge
// isn't reachable (CI / fresh checkout / dev box without Ollama running).
//
// The test is generous on timeout (60s) because qwen3:14b can take 20-40s to
// warm up on the first call. The blob is intentionally trivial so a competent
// LLM cannot legitimately return items=[] — if the assertion fires, either
// Ollama is degraded or the bridge prompt is broken.
//
// Bridge URL : honors AURORA_BRIDGE_URL env, falls back to localhost:3001.
// To run : `node --experimental-strip-types --test src/__tests__/coworkExtract.test.ts`
//   - if bridge up : the test runs and asserts items.length >= 1
//   - if bridge down : test.skip via the bridgeAvailable preflight
// ---------------------------------------------------------------------------

const BRIDGE_URL = process.env.AURORA_BRIDGE_URL || 'http://localhost:3001'

async function bridgeAvailable(): Promise<boolean> {
  try {
    const r = await fetch(`${BRIDGE_URL}/api/health`, {
      signal: AbortSignal.timeout(2000),
    })
    return r.ok
  } catch {
    return false
  }
}

describe('extract_structured — live bridge integration', () => {
  test('POST /api/cowork/extract-structured returns items[] for synthetic HTML', { timeout: 90_000 }, async (t) => {
    const up = await bridgeAvailable()
    if (!up) {
      t.skip(`bridge not reachable at ${BRIDGE_URL} — start it with: python application/bridge_server.py`)
      return
    }
    // v82l9 — slightly fattened blob with a clearly homogeneous schema (3
    // entries, identical "name : value" shape). A competent LLM cannot
    // legitimately return items=[] OR items with heterogeneous keys.
    const html = '<ul><li>Alpha: 10</li><li>Beta: 20</li><li>Gamma: 30</li></ul>'
    const intent = 'extract pairs of name and value from the list'
    const t0 = Date.now()
    const r = await fetch(`${BRIDGE_URL}/api/cowork/extract-structured`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, html_or_text: html }),
      signal: AbortSignal.timeout(85_000),
    })
    const latencyMs = Date.now() - t0
    assert.equal(r.ok, true, `bridge returned ${r.status}`)
    const data = await r.json() as {
      ok?: boolean
      items?: Array<Record<string, unknown>>
      schema?: string
      notes?: string
      model?: string
      error?: string
    }
    assert.equal(data.ok, true, `bridge ok=false: ${data.error || 'no error msg'}`)
    assert.ok(Array.isArray(data.items), 'items must be an array')
    // Tighter than v82l8 : the synthetic blob has exactly 3 entries, the LLM
    // should pick all of them up. Allow >=2 to absorb a single LLM hiccup.
    assert.ok(
      data.items!.length >= 2,
      `expected >=2 items for 3-entry blob, got ${data.items!.length} (notes=${data.notes}, model=${data.model}, latency=${latencyMs}ms)`,
    )
    const first = data.items![0]
    assert.ok(first && typeof first === 'object', 'first item must be an object')
    const keys = Object.keys(first)
    assert.ok(keys.length >= 1, 'first item must have at least one key')
    // v82l9 — homogeneous schema check : all items must share at least ONE key
    // with the first one. Catches the failure mode where the LLM returns
    // [{name:'Alpha'}, {value:10}, {label:'Beta'}] (one key per item, no
    // pairing) — that's the LLM not understanding the "pair" intent.
    if (data.items!.length >= 2) {
      const firstKeys = new Set(keys)
      const sharedWithSecond = Object.keys(data.items![1]).some((k) => firstKeys.has(k))
      assert.ok(
        sharedWithSecond,
        `items must share at least one key (homogeneous schema). first=${JSON.stringify(first)} second=${JSON.stringify(data.items![1])}`,
      )
    }
    // Smoke-print the result for the human running the test live.
    console.log(`[live-extract] model=${data.model || '?'} items=${data.items!.length} latency=${latencyMs}ms`)
  })

  // -------------------------------------------------------------------------
  // v82lb — Vision routing wire-test.
  //
  // Pass 6 (v82l9 / v82la) wired the planner to emit `includeImage:true` on
  // EX17. This test closes the loop on the BRIDGE side : when the executor
  // forwards `imageDataUrl`, the handler must switch model from qwen3:14b
  // to qwen3-vl:8b. We assert that via the `model` field exposed in the
  // response payload (added in v82l8, documented in v82lb).
  //
  // The synthetic image is a 1x1 transparent PNG — it carries zero useful
  // signal, so the LLM may legitimately return items=[]. That's fine ;
  // we only care about the routing decision. The assertions are :
  //   1. ok === true (handler didn't 4xx/5xx)
  //   2. model contains 'vl' (qwen3-vl:8b or any future vision tag)
  //   3. items is an array (shape contract preserved)
  //
  // Skipped cleanly when the bridge is down OR when the bridge response
  // omits the `model` field (forward-compat — older bridges before v82l8
  // didn't expose it).
  // -------------------------------------------------------------------------
  test('imageDataUrl payload routes to a vision-capable model', { timeout: 90_000 }, async (t) => {
    const up = await bridgeAvailable()
    if (!up) {
      t.skip(`bridge not reachable at ${BRIDGE_URL} — start it with: python application/bridge_server.py`)
      return
    }
    // 1x1 transparent PNG (smallest valid PNG dataUrl). Carries no semantic
    // info ; the test is about the routing decision, not the LLM output.
    const tinyPng = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
    const intent = 'describe what you see in the image'
    const t0 = Date.now()
    const r = await fetch(`${BRIDGE_URL}/api/cowork/extract-structured`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, imageDataUrl: tinyPng }),
      signal: AbortSignal.timeout(85_000),
    })
    const latencyMs = Date.now() - t0
    assert.equal(r.ok, true, `bridge returned ${r.status}`)
    const data = await r.json() as {
      ok?: boolean
      items?: unknown
      model?: string
      error?: string
    }
    assert.equal(data.ok, true, `bridge ok=false: ${data.error || 'no error msg'}`)
    assert.ok(Array.isArray(data.items), 'items must be an array (shape contract)')
    if (typeof data.model !== 'string' || data.model.length === 0) {
      // Forward-compat : older bridge revs (pre-v82l8) didn't expose model.
      // If we're talking to one of those, skip the routing assertion rather
      // than fail — log a follow-up note for pass 8.
      t.skip(`bridge does not expose 'model' in response — pass 8 ticket: bump bridge to v82l8+ to enable vision-routing assertion (latency=${latencyMs}ms)`)
      return
    }
    // Core assertion : the model must be a vision-capable variant. We accept
    // any tag containing 'vl' (qwen3-vl, qwen2-vl, llama3-vl, ...) so this
    // test survives a future model swap without churn.
    assert.ok(
      data.model.toLowerCase().includes('vl'),
      `expected vision-capable model (containing 'vl'), got '${data.model}' (latency=${latencyMs}ms). The bridge handler MUST switch from qwen3:14b to qwen3-vl:8b when imageDataUrl is present.`,
    )
    console.log(`[live-extract-vision] model=${data.model} latency=${latencyMs}ms`)
  })

  // -------------------------------------------------------------------------
  // v82lb — image_b64 alias compat.
  //
  // The bridge handler accepts both `imageDataUrl` (camelCase) and the
  // snake_case alias `image_b64`. This test verifies the alias actually
  // triggers the same vision-routing path, so Python/planner callers that
  // emit the snake_case form aren't silently routed to the text-only model.
  // -------------------------------------------------------------------------
  test('image_b64 alias also routes to a vision-capable model', { timeout: 90_000 }, async (t) => {
    const up = await bridgeAvailable()
    if (!up) {
      t.skip(`bridge not reachable at ${BRIDGE_URL}`)
      return
    }
    const tinyPng = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
    const r = await fetch(`${BRIDGE_URL}/api/cowork/extract-structured`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent: 'describe', image_b64: tinyPng }),
      signal: AbortSignal.timeout(85_000),
    })
    assert.equal(r.ok, true, `bridge returned ${r.status}`)
    const data = await r.json() as { ok?: boolean; model?: string; error?: string }
    assert.equal(data.ok, true, `bridge ok=false: ${data.error || 'no error msg'}`)
    if (typeof data.model !== 'string' || data.model.length === 0) {
      t.skip(`bridge pre-v82lb without 'model' in response — pass 8 ticket: bump bridge`)
      return
    }
    assert.ok(
      data.model.toLowerCase().includes('vl'),
      `image_b64 alias must route to vision model, got '${data.model}'`,
    )
  })
})
