/**
 * Live integration tests against PUBLIC APIs (no key required).
 * Gated by env var COWORK_LIVE_TESTS=1 so CI / offline runs skip them.
 *
 * Run: COWORK_LIVE_TESTS=1 node --experimental-strip-types --test src/__tests__/coworkLiveAPIs.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const LIVE = process.env.COWORK_LIVE_TESTS === '1'
const skip = LIVE ? false : true

describe('Live: Wikipedia opensearch', { skip }, () => {
  test('opensearch "Anthropic" returns 4-tuple [query, titles[], descs[], urls[]]', async () => {
    const r = await fetch('https://fr.wikipedia.org/w/api.php?action=opensearch&format=json&search=Anthropic&limit=3&origin=*', {
      signal: AbortSignal.timeout(15_000),
      headers: { 'User-Agent': 'AuroraIA-Cowork-tests' },
    })
    assert.equal(r.ok, true)
    const data = await r.json() as unknown
    // OpenSearch format: [query, titles[], descs[], urls[]]
    assert.ok(Array.isArray(data), 'response must be an array')
    const arr = data as unknown[]
    assert.equal(arr.length, 4, 'response must be 4-tuple')
    assert.equal(arr[0], 'Anthropic', 'first element is the query')
    assert.ok(Array.isArray(arr[1]), 'second element is titles array')
    assert.ok(Array.isArray(arr[3]), 'fourth element is urls array')
    const titles = arr[1] as string[]
    const urls = arr[3] as string[]
    assert.ok(titles.length > 0, 'must return at least one title')
    assert.equal(titles.length, urls.length, 'titles and urls must align')
    assert.match(urls[0], /^https:\/\/fr\.wikipedia\.org\/wiki\//, 'urls must point to fr.wikipedia.org/wiki/')
  })
})

describe('Live: OpenStreetMap Nominatim', { skip }, () => {
  test('search "Tour Eiffel" returns coords near 48.85, 2.29', async () => {
    const r = await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=2&q=Tour+Eiffel', {
      signal: AbortSignal.timeout(15_000),
      headers: { 'User-Agent': 'AuroraIA-Cowork-tests' },
    })
    assert.equal(r.ok, true)
    const data = await r.json() as Array<{ lat?: string; lon?: string; display_name?: string }>
    assert.ok(Array.isArray(data) && data.length > 0, 'must return at least one match')
    const first = data[0]
    assert.ok(first.lat && first.lon, 'must include lat+lon')
    const lat = parseFloat(first.lat!)
    const lon = parseFloat(first.lon!)
    assert.ok(Math.abs(lat - 48.858) < 0.01, `lat ${lat} must be near 48.858`)
    assert.ok(Math.abs(lon - 2.295) < 0.01, `lon ${lon} must be near 2.295`)
    assert.match(first.display_name || '', /Eiffel/i, 'display_name must mention Eiffel')
  })

  test('reverse 48.8588, 2.2945 gives "Tour Eiffel" in display_name', async () => {
    const r = await fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=48.8588&lon=2.2945', {
      signal: AbortSignal.timeout(15_000),
      headers: { 'User-Agent': 'AuroraIA-Cowork-tests' },
    })
    assert.equal(r.ok, true)
    const data = await r.json() as { display_name?: string; address?: { country?: string } }
    assert.ok(data.display_name, 'must include display_name')
    assert.match(data.address?.country || '', /France/i, 'country must be France')
  })
})

describe('Live: Open Library search', { skip }, () => {
  test('search "Marie Curie" returns books mentioning her in title/author', async () => {
    const r = await fetch('https://openlibrary.org/search.json?q=marie+curie&limit=10', {
      signal: AbortSignal.timeout(15_000),
    })
    assert.equal(r.ok, true)
    const data = await r.json() as { docs?: Array<{ title?: string; author_name?: string[] }> }
    assert.ok(data.docs && data.docs.length > 0, 'must return at least one doc')
    const matches = data.docs.filter((d) => /marie\s+curie/i.test(`${d.title ?? ''} ${(d.author_name ?? []).join(' ')}`))
    assert.ok(matches.length > 0, `at least one of ${data.docs.length} results must mention Marie Curie in title or author`)
  })
})

describe('Live: HIBP pwned_password (k-anonymity)', { skip }, () => {
  test('k-anonymity range API for prefix 21BD1 returns text body', async () => {
    // SHA-1("password") = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
    // Prefix : 5BAA6, suffix : 1E4C9B93F3F0682250B6CF8331B7EE68FD8
    const r = await fetch('https://api.pwnedpasswords.com/range/5BAA6', {
      signal: AbortSignal.timeout(15_000),
    })
    assert.equal(r.ok, true)
    const txt = await r.text()
    assert.ok(txt.length > 100, 'response must be a non-trivial list')
    assert.match(txt, /1E4C9B93F3F0682250B6CF8331B7EE68FD8/i, '"password" SHA-1 suffix must be in the range list (it is famously pwned)')
  })
})

describe('Live disabled', { skip: LIVE }, () => {
  test('placeholder when COWORK_LIVE_TESTS=0', () => {
    assert.ok(true)
  })
})
