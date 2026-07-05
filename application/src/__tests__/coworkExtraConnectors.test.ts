/**
 * Tests for the 5 image/maps/finance/research connectors added in v10:
 * stability_ai, mapbox, coingecko, polygon, perplexity.
 *
 * Plus parser fuzzing : robustness on realistic LLM outputs (markdown stray,
 * prefix prose, trailing comma, partial JSON).
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkExtraConnectors.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { CONNECTORS, buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
const { DEFAULT_SETTINGS } = await import('../services/coworkSettings.ts')
const { parsePlan, extractJsonObject } = await import('../services/coworkPlanParser.ts')

const NEW_IDS = ['stability_ai', 'mapbox', 'coingecko', 'polygon', 'perplexity'] as const

describe('5 new image/maps/finance/research connectors', () => {
  for (const id of NEW_IDS) {
    test(`${id}: registered with meta + actions + semantic`, () => {
      const meta = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.label && meta.label.length > 0)
      assert.ok(meta.docUrl)
      assert.ok(meta.actions.length > 0)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse empty`)
    })
    test(`${id}: in DEFAULT_SETTINGS`, () => {
      const cfg = DEFAULT_SETTINGS.connectors[id as keyof typeof DEFAULT_SETTINGS.connectors]
      assert.ok(cfg, `${id}: not in default connectors`)
      assert.equal(cfg.enabled, false)
    })
  }
})

describe('Stability AI image gen specifics', () => {
  test('actions cover sd3/ultra/upscale', () => {
    const ops = CONNECTORS.stability_ai.actions.map((a) => a.name)
    assert.ok(ops.includes('generate_sd3'))
    assert.ok(ops.includes('generate_ultra'))
    assert.ok(ops.includes('upscale'))
  })
  test('fallback to local image module', () => {
    const fb = CONNECTORS.stability_ai.fallback
    assert.ok(fb)
    assert.equal(fb!.kind, 'local-module')
    assert.equal(fb!.target, 'image')
  })
})

describe('Mapbox specifics', () => {
  test('actions cover geocode/reverse/directions', () => {
    const ops = CONNECTORS.mapbox.actions.map((a) => a.name)
    assert.ok(ops.includes('geocode'))
    assert.ok(ops.includes('reverse'))
    assert.ok(ops.includes('directions'))
  })
  test('fallback to OSM', () => {
    const fb = CONNECTORS.mapbox.fallback
    assert.ok(fb)
    assert.equal(fb!.target, 'openstreetmap')
  })
})

describe('CoinGecko crypto specifics', () => {
  test('actions cover simple_price/market_chart/trending/global', () => {
    const ops = CONNECTORS.coingecko.actions.map((a) => a.name)
    for (const op of ['simple_price', 'market_chart', 'trending', 'global']) {
      assert.ok(ops.includes(op), `${op} missing in coingecko`)
    }
  })
  test('apiKeyLabel mentions aucune ou Pro Key', () => {
    assert.match(CONNECTORS.coingecko.apiKeyLabel, /aucune|Pro/i)
  })
})

describe('Polygon stocks/forex specifics', () => {
  test('actions cover ticker_details/snapshot/aggregates/list_tickers', () => {
    const ops = CONNECTORS.polygon.actions.map((a) => a.name)
    for (const op of ['ticker_details', 'snapshot', 'aggregates', 'list_tickers']) {
      assert.ok(ops.includes(op), `${op} missing in polygon`)
    }
  })
})

describe('Perplexity research specifics', () => {
  test('actions cover chat + sonar', () => {
    const ops = CONNECTORS.perplexity.actions.map((a) => a.name)
    assert.ok(ops.includes('chat'))
    assert.ok(ops.includes('sonar'))
  })
  test('fallback to mainModel local LLM', () => {
    const fb = CONNECTORS.perplexity.fallback
    assert.ok(fb)
    assert.equal(fb!.kind, 'local-llm')
    assert.equal(fb!.target, 'mainModel')
  })
})

describe('semantic brief routes new connectors correctly', () => {
  test('Stability AI brief mentions image/SD3', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'stability_ai', quotaExhausted: false }])
    assert.match(brief, /image|sd3|stable diffusion/i)
  })
  test('Mapbox brief mentions itineraire/geocode', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'mapbox', quotaExhausted: false }])
    assert.match(brief, /itineraire|geocode|directions/i)
  })
  test('CoinGecko brief mentions crypto/bitcoin', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'coingecko', quotaExhausted: false }])
    assert.match(brief, /crypto|bitcoin|btc|coin/i)
  })
  test('Polygon brief mentions action/stock/bourse', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'polygon', quotaExhausted: false }])
    assert.match(brief, /action|stock|bourse|sp500|forex/i)
  })
  test('Perplexity brief mentions recherche/factuel', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'perplexity', quotaExhausted: false }])
    assert.match(brief, /perplexity|recherche|factuel|citations/i)
  })
})

describe('total count', () => {
  test('>= 57 connectors after v10.2 (55 + datadog + sentry)', () => {
    const count = Object.keys(CONNECTORS).length
    assert.ok(count >= 57, `expected >=57, got ${count}`)
  })
})

describe('Datadog observability connector', () => {
  test('actions cover query_metric / list_monitors / list_logs / create_event', () => {
    const ops = CONNECTORS.datadog.actions.map((a) => a.name)
    for (const op of ['query_metric', 'list_monitors', 'list_logs', 'create_event']) {
      assert.ok(ops.includes(op), `${op} missing in datadog`)
    }
  })
  test('purpose mentions metrics/logs', () => {
    assert.match(CONNECTORS.datadog.purpose!, /metric|log|monitor/i)
  })
  test('apiKeyLabel mentions API:Application format', () => {
    assert.match(CONNECTORS.datadog.apiKeyLabel, /API.*Application|API.*App/i)
  })
})

describe('Sentry error tracking connector', () => {
  test('actions cover list_projects / list_issues / get_issue / resolve_issue', () => {
    const ops = CONNECTORS.sentry.actions.map((a) => a.name)
    for (const op of ['list_projects', 'list_issues', 'get_issue', 'resolve_issue']) {
      assert.ok(ops.includes(op), `${op} missing in sentry`)
    }
  })
  test('whenToUse mentions exception/crash', () => {
    const wt = (CONNECTORS.sentry.whenToUse ?? []).join(' ').toLowerCase()
    assert.match(wt, /exception|crash|erreur|stack/)
  })
})

describe('4 productivity/search/email/CDN connectors (v11)', () => {
  for (const id of ['habitica', 'algolia', 'sendgrid', 'cloudinary'] as const) {
    test(`${id}: meta + actions + semantic`, () => {
      const meta = CONNECTORS[id]
      assert.ok(meta)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
    })
  }

  test('Habitica RPG actions', () => {
    const ops = CONNECTORS.habitica.actions.map((a) => a.name)
    for (const op of ['list_tasks', 'create_task', 'score_up', 'user_stats']) {
      assert.ok(ops.includes(op), `${op} missing in habitica`)
    }
  })

  test('Algolia search actions', () => {
    const ops = CONNECTORS.algolia.actions.map((a) => a.name)
    for (const op of ['search', 'list_indexes', 'browse']) {
      assert.ok(ops.includes(op), `${op} missing in algolia`)
    }
  })

  test('SendGrid email actions', () => {
    const ops = CONNECTORS.sendgrid.actions.map((a) => a.name)
    assert.ok(ops.includes('send'))
    assert.ok(ops.includes('list_templates'))
  })

  test('Cloudinary CDN actions', () => {
    const ops = CONNECTORS.cloudinary.actions.map((a) => a.name)
    for (const op of ['list_resources', 'usage', 'transform_url']) {
      assert.ok(ops.includes(op), `${op} missing in cloudinary`)
    }
  })

  test('total connector count >= 61', () => {
    const count = Object.keys(CONNECTORS).length
    assert.ok(count >= 61, `expected >=61, got ${count}`)
  })
})

describe('4 vector-db/newsletter/auth connectors (v12)', () => {
  for (const id of ['pinecone', 'mailchimp', 'auth0', 'clerk'] as const) {
    test(`${id}: meta + actions + semantic`, () => {
      const meta = CONNECTORS[id]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
      assert.ok(meta.actions.length > 0, `${id}: actions missing`)
    })
  }

  test('Pinecone vector DB actions', () => {
    const ops = CONNECTORS.pinecone.actions.map((a) => a.name)
    for (const op of ['list_indexes', 'describe_index_stats', 'query', 'upsert', 'delete']) {
      assert.ok(ops.includes(op), `${op} missing in pinecone`)
    }
  })
  test('Pinecone purpose mentions RAG/embeddings', () => {
    assert.match(CONNECTORS.pinecone.purpose!, /RAG|embedding|vector|similarity/i)
  })

  test('Mailchimp newsletter actions', () => {
    const ops = CONNECTORS.mailchimp.actions.map((a) => a.name)
    for (const op of ['list_audiences', 'add_member', 'list_campaigns', 'send_campaign']) {
      assert.ok(ops.includes(op), `${op} missing in mailchimp`)
    }
  })

  test('Auth0 user management actions', () => {
    const ops = CONNECTORS.auth0.actions.map((a) => a.name)
    for (const op of ['list_users', 'get_user', 'create_user', 'list_roles']) {
      assert.ok(ops.includes(op), `${op} missing in auth0`)
    }
  })

  test('Clerk auth actions', () => {
    const ops = CONNECTORS.clerk.actions.map((a) => a.name)
    for (const op of ['list_users', 'get_user', 'list_orgs', 'ban_user']) {
      assert.ok(ops.includes(op), `${op} missing in clerk`)
    }
  })

  test('total connector count >= 65', () => {
    const count = Object.keys(CONNECTORS).length
    assert.ok(count >= 65, `expected >=65, got ${count}`)
  })

  test('semantic brief routes new connectors', () => {
    const brief = buildConnectorBriefForLLM([
      { id: 'pinecone', quotaExhausted: false },
      { id: 'mailchimp', quotaExhausted: false },
      { id: 'auth0', quotaExhausted: false },
      { id: 'clerk', quotaExhausted: false },
    ])
    assert.match(brief, /vector|RAG|embedding/i)
    assert.match(brief, /newsletter|mailing/i)
    assert.match(brief, /auth0|users/i)
    assert.match(brief, /clerk/i)
  })
})

// ===========================================================================
// Parser fuzzing — realistic LLM outputs that often break naive parsers.
// ===========================================================================

const VALID_PLAN_BODY = JSON.stringify({
  reasoning: 'r',
  expectedOutcome: 'o',
  actions: [{ kind: 'reply', message: 'salut' }, { kind: 'finish', summary: 'fait' }],
})

describe('parser fuzz : real-world LLM output shapes', () => {
  test('JSON wrapped in fenced ```json block', () => {
    const r = parsePlan('```json\n' + VALID_PLAN_BODY + '\n```')
    assert.equal(r.ok, true)
  })

  test('JSON wrapped in fenced block without language tag', () => {
    const r = parsePlan('```\n' + VALID_PLAN_BODY + '\n```')
    assert.equal(r.ok, true)
  })

  test('LLM prefixes "Voici votre plan :" before JSON', () => {
    const r = parsePlan('Voici votre plan :\n' + VALID_PLAN_BODY)
    assert.equal(r.ok, true)
  })

  test('LLM suffixes "J espere que cela aide !"', () => {
    const r = parsePlan(VALID_PLAN_BODY + '\n\nJ espere que cela aide !')
    assert.equal(r.ok, true)
  })

  test('JSON inside double fence blocks (markdown nested)', () => {
    const raw = 'Voici :\n```json\n' + VALID_PLAN_BODY + '\n```\n\nFin.'
    const r = parsePlan(raw)
    assert.equal(r.ok, true)
  })

  test('extractJsonObject handles plain string fallback', () => {
    const out = extractJsonObject('avant {"a":1} apres')
    assert.equal(out, '{"a":1}')
  })

  test('extractJsonObject prefers fenced block over bare', () => {
    // Both bare and fenced — fenced wins
    const out = extractJsonObject('text {"bare":true} more text\n```json\n{"fenced":true}\n```')
    assert.equal(out, '{"fenced":true}')
  })

  test('rejects pure prose with no JSON', () => {
    const r = parsePlan('I am sorry, I cannot help with that request.')
    assert.equal(r.ok, false)
  })

  test('rejects partial JSON (truncated)', () => {
    const r = parsePlan('{"reasoning":"r","actions":[{"kind"')
    assert.equal(r.ok, false)
  })

  test('rejects JSON5 trailing comma (we are strict)', () => {
    const r = parsePlan('{"reasoning":"r","expectedOutcome":"o","actions":[{"kind":"reply","message":"x"},]}')
    assert.equal(r.ok, false)
  })

  test('accepts JSON with extra unknown fields (ignored)', () => {
    const r = parsePlan(JSON.stringify({
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'reply', message: 'hi', extraField: 42 }],
      llmConfidence: 0.92,
    }))
    assert.equal(r.ok, true)
  })

  test('rejects array as root', () => {
    const r = parsePlan('[{"reasoning":"r"}]')
    assert.equal(r.ok, false)
  })

  test('rejects null as root', () => {
    const r = parsePlan('null')
    assert.equal(r.ok, false)
  })

  test('handles whitespace-heavy input', () => {
    const r = parsePlan('\n\n\n  ' + VALID_PLAN_BODY + '\n\n  \t')
    assert.equal(r.ok, true)
  })

  test('handles BOM at start (UTF-8)', () => {
    const r = parsePlan('﻿' + VALID_PLAN_BODY)
    assert.equal(r.ok, true)
  })

  test('rejects empty string', () => {
    assert.equal(parsePlan('').ok, false)
  })

  test('rejects whitespace-only', () => {
    assert.equal(parsePlan('   \n\t  ').ok, false)
  })
})

describe('parser fuzz : malformed action items', () => {
  test('rejects when one action has unknown kind even if others are valid', () => {
    const r = parsePlan(JSON.stringify({
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'ok' },
        { kind: 'self_destruct', why: 'lol' },
      ],
    }))
    assert.equal(r.ok, false)
  })

  test('rejects when an action is not an object (e.g. string)', () => {
    const r = parsePlan('{"reasoning":"r","expectedOutcome":"o","actions":["read /etc/passwd"]}')
    assert.equal(r.ok, false)
  })

  test('rejects when type fields have wrong types', () => {
    const r = parsePlan(JSON.stringify({
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'write_file', path: 'x.txt', content: 42 }],  // content as number
    }))
    assert.equal(r.ok, false)
  })

  test('shell with non-array args defaults gracefully (filters or empty)', () => {
    const r = parsePlan(JSON.stringify({
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'shell', command: 'git', args: 'status' }],  // string instead of array
    }))
    // Parser accepts and defaults args to []
    assert.equal(r.ok, true)
    if (r.ok && r.plan.actions[0].kind === 'shell') {
      assert.deepEqual(r.plan.actions[0].args, [])
    }
  })
})
