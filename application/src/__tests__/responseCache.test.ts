/**
 * Tests pour services/responseCache — LRU + TTL + fuzzy match (Jaccard).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { ResponseCache } from '../services/responseCache.ts'

describe('ResponseCache — exact match', () => {
  test('miss avant set', () => {
    const c = new ResponseCache()
    assert.equal(c.get('hello'), null)
  })

  test('hit après set', () => {
    const c = new ResponseCache()
    c.set('hello', 'world response')
    const hit = c.get('hello')
    assert.ok(hit)
    assert.equal(hit?.response, 'world response')
  })

  test('match insensitive à la casse / whitespace', () => {
    const c = new ResponseCache()
    c.set('Hello World', 'r1')
    const hit = c.get('  hello world  ')
    assert.ok(hit)
    assert.equal(hit?.response, 'r1')
  })

  test('hit bump le compteur', () => {
    const c = new ResponseCache()
    c.set('q', 'r')
    c.get('q')
    c.get('q')
    const hit = c.get('q')
    assert.equal(hit?.hits, 3)
  })
})

describe('ResponseCache — fuzzy match', () => {
  test('Jaccard ≥ threshold → hit', () => {
    const c = new ResponseCache({ fuzzyThreshold: 0.5 })
    c.set('comment fonctionne le système solaire planètes', 'r1')
    const hit = c.get('comment marche le système solaire planètes')
    assert.ok(hit, 'devrait matcher en fuzzy')
  })

  test('Jaccard < threshold → miss', () => {
    const c = new ResponseCache({ fuzzyThreshold: 0.9 })
    c.set('comment fonctionne le système solaire', 'r1')
    const hit = c.get('comment fonctionne un moteur thermique')
    assert.equal(hit, null)
  })

  test('exact pris en priorité sur fuzzy', () => {
    const c = new ResponseCache({ fuzzyThreshold: 0.3 })
    c.set('a b c d', 'fuzzy-target')
    c.set('a b c d e f g', 'exact-target')
    const hit = c.get('a b c d e f g')
    assert.equal(hit?.response, 'exact-target')
  })
})

describe('ResponseCache — TTL', () => {
  test('entrée expirée après ttl', () => {
    const c = new ResponseCache({ ttlSeconds: 60 })
    const t0 = new Date('2026-05-20T10:00:00Z')
    c.set('q', 'r', 0, t0)
    const tooLate = new Date('2026-05-20T10:02:00Z') // +120s
    assert.equal(c.get('q', tooLate), null)
  })

  test('entrée encore valide avant ttl', () => {
    const c = new ResponseCache({ ttlSeconds: 60 })
    const t0 = new Date('2026-05-20T10:00:00Z')
    c.set('q', 'r', 0, t0)
    const t1 = new Date('2026-05-20T10:00:30Z') // +30s
    assert.ok(c.get('q', t1))
  })

  test('evictExpired renvoie le nombre supprimé', () => {
    const c = new ResponseCache({ ttlSeconds: 60 })
    const t0 = new Date('2026-05-20T10:00:00Z')
    c.set('a', '1', 0, t0)
    c.set('b', '2', 0, t0)
    const t1 = new Date('2026-05-20T10:02:00Z')
    assert.equal(c.evictExpired(t1), 2)
    assert.equal(c.stats().size, 0)
  })

  test('ttl=0 désactive expiration', () => {
    const c = new ResponseCache({ ttlSeconds: 0 })
    const t0 = new Date('2026-05-20T10:00:00Z')
    c.set('q', 'r', 0, t0)
    const tFuture = new Date('2030-01-01T00:00:00Z')
    assert.ok(c.get('q', tFuture))
  })
})

describe('ResponseCache — LRU eviction', () => {
  test('eviction au-delà de maxEntries', () => {
    const c = new ResponseCache({ maxEntries: 3 })
    c.set('a', '1')
    c.set('b', '2')
    c.set('c', '3')
    c.set('d', '4') // évince le plus vieux
    assert.equal(c.stats().size, 3)
    assert.equal(c.get('a'), null) // 'a' évincé
    assert.ok(c.get('d'))
  })

  test('hit remonte en tête LRU', () => {
    const c = new ResponseCache({ maxEntries: 3 })
    c.set('a', '1')
    c.set('b', '2')
    c.set('c', '3')
    c.get('a') // 'a' devient le plus récent
    c.set('d', '4') // évince le plus vieux qui est maintenant 'b'
    assert.ok(c.get('a'))
    assert.equal(c.get('b'), null)
  })
})

describe('ResponseCache — stats / clear', () => {
  test('stats compte size/hits/savedUsd', () => {
    const c = new ResponseCache()
    c.set('q1', 'r1', 0.01)
    c.set('q2', 'r2', 0.02)
    c.get('q1')
    c.get('q1')
    const s = c.stats()
    assert.equal(s.size, 2)
    assert.equal(s.totalHits, 2)
    assert.ok(Math.abs(s.totalSavedUsd - 0.03) < 1e-9)
  })

  test('clear vide tout', () => {
    const c = new ResponseCache()
    c.set('a', '1')
    c.set('b', '2')
    c.clear()
    assert.equal(c.stats().size, 0)
  })

  test('re-set même prompt → update + savedCost cumulé', () => {
    const c = new ResponseCache()
    c.set('q', 'r1', 0.01)
    c.set('q', 'r2', 0.02)
    assert.equal(c.stats().size, 1)
    assert.ok(Math.abs(c.stats().totalSavedUsd - 0.03) < 1e-9)
    assert.equal(c.get('q')?.response, 'r2')
  })
})
