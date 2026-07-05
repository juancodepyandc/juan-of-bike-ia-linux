/**
 * Tests for the 5 OSINT/culture connectors added in v7:
 * hibp, abuseipdb, discogs, igdb, openlibrary.
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkOSINTAndCulture.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { CONNECTORS, buildConnectorBriefForLLM } = await import('../services/coworkConnectors.ts')
const { DEFAULT_SETTINGS } = await import('../services/coworkSettings.ts')

const NEW_IDS = ['hibp', 'abuseipdb', 'discogs', 'igdb', 'openlibrary'] as const

describe('5 new OSINT/culture connectors registered', () => {
  for (const id of NEW_IDS) {
    test(`${id}: meta + actions present`, () => {
      const meta = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(meta, `${id}: missing meta`)
      assert.ok(meta.label && meta.label.length > 0)
      assert.ok(meta.docUrl)
      assert.ok(meta.actions.length > 0)
    })
    test(`${id}: semantic info present`, () => {
      const meta = CONNECTORS[id as keyof typeof CONNECTORS]
      assert.ok(meta.purpose, `${id}: purpose missing`)
      assert.ok((meta.whenToUse?.length ?? 0) > 0, `${id}: whenToUse empty`)
    })
    test(`${id}: in DEFAULT_SETTINGS`, () => {
      const cfg = DEFAULT_SETTINGS.connectors[id as keyof typeof DEFAULT_SETTINGS.connectors]
      assert.ok(cfg, `${id}: not in default connectors`)
    })
  }
})

describe('HIBP cyber connector', () => {
  test('actions cover breaches + pwned password', () => {
    const ops = CONNECTORS.hibp.actions.map((a) => a.name)
    assert.ok(ops.includes('breached_account'))
    assert.ok(ops.includes('pwned_password'))
    assert.ok(ops.includes('all_breaches'))
  })
  test('purpose mentions fuite/leak', () => {
    assert.match(CONNECTORS.hibp.purpose!, /fuite|leak|compromis|pwned/i)
  })
})

describe('AbuseIPDB cyber connector', () => {
  test('actions check + blacklist + report', () => {
    const ops = CONNECTORS.abuseipdb.actions.map((a) => a.name)
    assert.ok(ops.includes('check'))
    assert.ok(ops.includes('blacklist'))
    assert.ok(ops.includes('report'))
  })
  test('purpose mentions IP reputation', () => {
    assert.match(CONNECTORS.abuseipdb.purpose!, /reputation|ip|abus/i)
  })
})

describe('Discogs music connector', () => {
  test('actions search + release + artist', () => {
    const ops = CONNECTORS.discogs.actions.map((a) => a.name)
    assert.ok(ops.includes('search'))
    assert.ok(ops.includes('release'))
    assert.ok(ops.includes('artist'))
  })
  test('whenToUse mentions vinyl/album', () => {
    const wt = (CONNECTORS.discogs.whenToUse ?? []).join(' ').toLowerCase()
    assert.match(wt, /vinyle|album|musique/)
  })
})

describe('IGDB games connector', () => {
  test('actions search_games + top_rated + platforms', () => {
    const ops = CONNECTORS.igdb.actions.map((a) => a.name)
    assert.ok(ops.includes('search_games'))
    assert.ok(ops.includes('top_rated'))
    assert.ok(ops.includes('platforms'))
  })
  test('apiKeyLabel mentions ClientID:Bearer (Twitch OAuth)', () => {
    assert.match(CONNECTORS.igdb.apiKeyLabel, /ClientID|Client.?ID|Bearer/i)
  })
})

describe('OpenLibrary public connector', () => {
  test('apiKeyLabel mentions aucune', () => {
    assert.match(CONNECTORS.openlibrary.apiKeyLabel, /aucune/i)
  })
  test('actions search + book + author', () => {
    const ops = CONNECTORS.openlibrary.actions.map((a) => a.name)
    assert.ok(ops.includes('search'))
    assert.ok(ops.includes('book'))
    assert.ok(ops.includes('author'))
  })
  test('purpose mentions livres/books', () => {
    assert.match(CONNECTORS.openlibrary.purpose!, /livre|book|ebook/i)
  })
})

describe('semantic brief routes new connectors correctly', () => {
  test('HIBP brief mentions fuite/leak', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'hibp', quotaExhausted: false }])
    assert.match(brief, /fuite|leak|pwned|compromis/i)
  })
  test('AbuseIPDB brief mentions IP', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'abuseipdb', quotaExhausted: false }])
    assert.match(brief, /ip|reputation|abus/i)
  })
  test('Discogs brief mentions vinyl/music', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'discogs', quotaExhausted: false }])
    assert.match(brief, /vinyle|album|musique|discographie/i)
  })
  test('IGDB brief mentions games', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'igdb', quotaExhausted: false }])
    assert.match(brief, /jeu|game|console/i)
  })
  test('OpenLibrary brief mentions books', () => {
    const brief = buildConnectorBriefForLLM([{ id: 'openlibrary', quotaExhausted: false }])
    assert.match(brief, /livre|book|auteur|isbn/i)
  })
})

describe('total connector count >= 49', () => {
  test('44 v6 + 5 v7 new = 49 total', () => {
    const count = Object.keys(CONNECTORS).length
    assert.ok(count >= 49, `expected >=49, got ${count}`)
  })
})
