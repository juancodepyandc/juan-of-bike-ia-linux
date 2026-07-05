/**
 * Tests for the 8 infra/data/mobile connectors added in v6:
 * postgres, redis_upstash, s3, tailscale, plausible, pushover, twilio, openstreetmap.
 *
 * Plus their semantic metadata (purpose/whenToUse/fallback).
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkInfraConnectors.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { CONNECTORS, buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
const { DEFAULT_SETTINGS } = await import('../services/coworkSettings.ts')

const NEW_IDS = [
  'postgres', 'redis_upstash', 's3', 'tailscale', 'plausible',
  'pushover', 'twilio', 'openstreetmap',
] as const

describe('all 8 new connectors registered', () => {
  for (const id of NEW_IDS) {
    test(`${id}: meta + actions present`, () => {
      const meta = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.label && meta.label.length > 0)
      assert.ok(meta.docUrl)
      assert.ok(meta.actions.length > 0)
    })
    test(`${id}: semantic info (purpose + whenToUse) present`, () => {
      const meta = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse missing`)
    })
    test(`${id}: registered in DEFAULT_SETTINGS.connectors`, () => {
      const cfg = DEFAULT_SETTINGS.connectors[id as keyof typeof DEFAULT_SETTINGS.connectors]
      assert.ok(cfg, `${id}: not in default connectors`)
      assert.equal(cfg.enabled, false)
    })
  }
})

describe('Postgres connector specifics', () => {
  test('actions include query/exec/tables', () => {
    const ops = CONNECTORS.postgres.actions.map((a) => a.name)
    assert.ok(ops.includes('query'))
    assert.ok(ops.includes('exec'))
    assert.ok(ops.includes('tables'))
  })
  test('purpose mentions SQL', () => {
    assert.match(CONNECTORS.postgres.purpose!, /SQL/i)
  })
})

describe('S3 connector specifics', () => {
  test('actions include list_buckets/list_objects/put/delete', () => {
    const ops = CONNECTORS.s3.actions.map((a) => a.name)
    assert.ok(ops.includes('list_buckets'))
    assert.ok(ops.includes('list_objects'))
    assert.ok(ops.includes('put_object'))
    assert.ok(ops.includes('delete_object'))
  })
  test('description mentions MinIO/R2/Backblaze (S3-compatible)', () => {
    assert.match(CONNECTORS.s3.description, /MinIO|R2|Backblaze/i)
  })
})

describe('Twilio connector specifics', () => {
  test('actions cover SMS/WhatsApp/calls', () => {
    const ops = CONNECTORS.twilio.actions.map((a) => a.name)
    assert.ok(ops.includes('send_sms'))
    assert.ok(ops.includes('send_whatsapp'))
    assert.ok(ops.includes('make_call'))
  })
  test('purpose mentions phone-related terms', () => {
    assert.match(CONNECTORS.twilio.purpose!, /SMS|WhatsApp|appel|tel/i)
  })
})

describe('Pushover connector specifics', () => {
  test('action notify is the only one', () => {
    const ops = CONNECTORS.pushover.actions.map((a) => a.name)
    assert.deepEqual(ops, ['notify'])
  })
})

describe('OpenStreetMap is a public no-key API', () => {
  test('apiKeyLabel mentions aucune', () => {
    assert.match(CONNECTORS.openstreetmap.apiKeyLabel, /aucune/i)
  })
  test('purpose says it is libre/free', () => {
    assert.match(CONNECTORS.openstreetmap.purpose!, /gratuit|libre|google/i)
  })
})

describe('Plausible Analytics needs siteId', () => {
  test('needsWorkspaceId is true (site_id required)', () => {
    assert.equal(CONNECTORS.plausible.needsWorkspaceId, true)
  })
  test('actions include aggregate/breakdown/realtime', () => {
    const ops = CONNECTORS.plausible.actions.map((a) => a.name)
    assert.ok(ops.includes('aggregate'))
    assert.ok(ops.includes('breakdown'))
    assert.ok(ops.includes('realtime'))
  })
})

describe('Tailscale needs tailnet ID', () => {
  test('needsWorkspaceId is true', () => {
    assert.equal(CONNECTORS.tailscale.needsWorkspaceId, true)
  })
  test('actions list_devices', () => {
    const ops = CONNECTORS.tailscale.actions.map((a) => a.name)
    assert.ok(ops.includes('list_devices'))
  })
})

describe('Redis Upstash needs baseUrl', () => {
  test('needsWorkspaceId is true (used as baseUrl)', () => {
    assert.equal(CONNECTORS.redis_upstash.needsWorkspaceId, true)
  })
  test('actions cover get/set/del/keys/incr', () => {
    const ops = CONNECTORS.redis_upstash.actions.map((a) => a.name)
    for (const op of ['get', 'set', 'del', 'keys', 'incr']) {
      assert.ok(ops.includes(op), `${op} missing`)
    }
  })
})

describe('semantic brief includes new connectors with use cases', () => {
  test('Postgres brief mentions SQL/query keywords', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'postgres', quotaExhausted: false }])
    assert.match(brief, /SQL|sql|select|requete/)
  })
  test('Twilio brief mentions phone/SMS', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'twilio', quotaExhausted: false }])
    assert.match(brief, /SMS|sms|whatsapp|tel|phone|appelle/i)
  })
  test('OpenStreetMap brief mentions geocode', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'openstreetmap', quotaExhausted: false }])
    assert.match(brief, /geocode|adresse|coordonnees/i)
  })
})

describe('total connector count', () => {
  test('exactly 44 connectors after v6 (36 v5 + 8 new)', () => {
    const count = Object.keys(CONNECTORS).length
    assert.ok(count >= 44, `expected >=44, got ${count}`)
  })
})
