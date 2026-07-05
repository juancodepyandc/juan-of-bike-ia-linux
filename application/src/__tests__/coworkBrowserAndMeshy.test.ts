/**
 * Tests for browser action validation + Meshy connector metadata + semantic
 * brief generation for the planner.
 * Run: node --experimental-strip-types --test src/__tests__/coworkBrowserAndMeshy.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { validateAction } = await import('../services/coworkSafety.ts')
const { validateAction: parseValidate } = await import('../services/coworkPlanParser.ts')

const WS = '/c/Users/me/aurora'

describe('browser action — safety verdict', () => {
  test('list_tabs allow', () => {
    const v = validateAction({ kind: 'browser', operation: 'list_tabs' }, 'web-desktop', WS)
    assert.equal(v.decision, 'allow')
  })
  test('read_dom allow', () => {
    const v = validateAction({ kind: 'browser', operation: 'read_dom', payload: { selector: 'h1' } }, 'web-desktop', WS)
    assert.equal(v.decision, 'allow')
  })
  test('eval requires confirmation', () => {
    const v = validateAction({ kind: 'browser', operation: 'eval', payload: { script: 'return 1' } }, 'web-desktop', WS)
    assert.equal(v.decision, 'confirm')
    assert.equal(v.destructive, true)
  })
  test('navigate requires confirmation', () => {
    const v = validateAction({ kind: 'browser', operation: 'navigate', payload: { url: 'https://x.com' } }, 'web-desktop', WS)
    assert.equal(v.decision, 'confirm')
  })
  test('eval allow with trustMode', () => {
    const v = validateAction({ kind: 'browser', operation: 'eval', payload: { script: 'x' } }, 'web-desktop', WS, { trustMode: true })
    assert.equal(v.decision, 'allow')
  })
})

describe('browser action — parser validation', () => {
  test('list_tabs parses', () => {
    const r = parseValidate({ kind: 'browser', operation: 'list_tabs' })
    assert.equal(r.ok, true)
  })
  test('click with selector parses', () => {
    const r = parseValidate({ kind: 'browser', operation: 'click', payload: { selector: '.btn' } })
    assert.equal(r.ok, true)
  })
  test('unknown operation rejected', () => {
    const r = parseValidate({ kind: 'browser', operation: 'hack_planet' })
    assert.equal(r.ok, false)
  })
  test('missing operation rejected', () => {
    const r = parseValidate({ kind: 'browser' })
    assert.equal(r.ok, false)
  })
  test('all 10 operations valid (incl. analyze_page)', () => {
    const ops = ['list_tabs', 'get_active_tab', 'read_dom', 'read_html', 'click', 'fill', 'eval', 'screenshot', 'navigate', 'analyze_page']
    for (const op of ops) {
      const r = parseValidate({ kind: 'browser', operation: op })
      assert.equal(r.ok, true, `operation ${op} should be valid`)
    }
  })

  test('analyze_page parses without payload', () => {
    const r = parseValidate({ kind: 'browser', operation: 'analyze_page' })
    assert.equal(r.ok, true)
  })
})

describe('Meshy connector metadata', () => {
  test('meshy registered with semantic info', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const meshy = CONNECTORS.meshy
    assert.ok(meshy, 'meshy connector should be registered')
    assert.equal(meshy.label, 'Meshy AI (3D)')
    assert.ok(meshy.purpose, 'meshy must have a purpose for the planner')
    assert.match(meshy.purpose!, /3D/i)
    assert.ok(meshy.fallback, 'meshy must declare a local fallback')
    assert.equal(meshy.fallback!.kind, 'local-module')
    assert.equal(meshy.fallback!.target, 'three-d')
  })

  test('Meshy actions exposed', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const ops = CONNECTORS.meshy.actions.map((a) => a.name)
    assert.ok(ops.includes('text_to_3d'))
    assert.ok(ops.includes('image_to_3d'))
    assert.ok(ops.includes('text_to_texture'))
  })
})

describe('semantic brief for the planner', () => {
  test('builds list with purpose + whenToUse', async () => {
    const { buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
    const brief = buildConnectorBriefForLLM([
      { id: 'github', quotaExhausted: false },
      { id: 'meshy', quotaExhausted: false },
    ])
    assert.match(brief, /GitHub/)
    assert.match(brief, /Meshy/)
    assert.match(brief, /3D/)
    assert.match(brief, /mots-cles/)
  })

  test('quotaExhausted surface fallback note', async () => {
    const { buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
    const brief = buildConnectorBriefForLLM([
      { id: 'meshy', quotaExhausted: true },
    ])
    assert.match(brief, /QUOTA EPUISE/)
    assert.match(brief, /Hunyuan3D|three-d|module 3D local/i)
  })

  test('LLM connectors fallback to mainModel', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const fallbacks = ['openai', 'anthropic', 'mistral', 'groq', 'openrouter']
    for (const id of fallbacks) {
      const c = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(c.fallback, `${id} should have a fallback`)
      assert.equal(c.fallback!.kind, 'local-llm')
      assert.equal(c.fallback!.target, 'mainModel')
    }
  })

  test('image gen connectors fallback to image module', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    const replicate = CONNECTORS.replicate
    const horde = CONNECTORS.stable_horde
    assert.equal(replicate.fallback?.target, 'image')
    assert.equal(horde.fallback?.target, 'image')
  })

  test('empty list returns empty brief', async () => {
    const { buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
    assert.equal(buildConnectorBriefForLLM([]), '')
  })
})

describe('connector count', () => {
  test('at least 36 connectors registered (35 + meshy)', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    assert.ok(Object.keys(CONNECTORS).length >= 36, `expected >= 36, got ${Object.keys(CONNECTORS).length}`)
  })

  test('every connector has docUrl + actions[] non-empty', async () => {
    const { CONNECTORS } = await import('../services/coworkConnectors.ts')
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      assert.ok(meta.docUrl, `${id}: docUrl manquant`)
      assert.ok(meta.actions.length > 0, `${id}: actions[] vide`)
    }
  })
})
