/**
 * Tests for the long-term conversation memory + intent router + response cache.
 * Run: node --experimental-strip-types --test src/__tests__/conversationMemoryRouter.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  addMemory,
  createMemoryStore,
  prune,
  removeMemory,
  retrieve,
  tokenize,
  touch,
} from '../services/conversationMemory.ts'
import { listModules, routeIntent } from '../services/intentRouter.ts'
import { ResponseCache } from '../services/responseCache.ts'

const T0 = new Date('2026-05-17T10:00:00Z')

describe('tokenize FR', () => {
  test('strips accents and stopwords', () => {
    const t = tokenize('La physique du pendule à grand angle')
    assert.ok(t.includes('physique'))
    assert.ok(t.includes('pendule'))
    assert.ok(t.includes('grand'))
    assert.ok(!t.includes('du'))
    assert.ok(!t.includes('la'))
  })

  test('rejects very short and empty', () => {
    assert.deepEqual(tokenize(''), [])
    assert.deepEqual(tokenize('  '), [])
  })

  test('removes diacritics so "ecole" matches "école"', () => {
    assert.deepEqual(tokenize('école').sort(), tokenize('ecole').sort())
  })
})

describe('memory store CRUD', () => {
  test('add then retrieve by content', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'Juan est en STI2D/SIN', tags: ['user'], importance: 0.9 }, T0)
    const out = retrieve(store, 'qu est-ce que Juan etudie ?', T0)
    assert.ok(out.length >= 1)
    assert.ok(out[0].entry.text.toLowerCase().includes('sti2d'))
  })

  test('dedup on same kind + text', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'pendule simple OK', importance: 0.5 }, T0)
    store = addMemory(store, { kind: 'fact', text: 'pendule simple OK', importance: 0.5 }, T0)
    assert.equal(store.entries.length, 1)
    assert.equal(store.entries[0].usageCount, 1)
  })

  test('remove updates doc frequency', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'argon2 better than bcrypt' }, T0)
    const id = store.entries[0].id
    const dfBefore = store.documentFrequency['argon2']
    assert.equal(dfBefore, 1)
    store = removeMemory(store, id)
    assert.equal(store.entries.length, 0)
    assert.equal(store.documentFrequency['argon2'], undefined)
  })

  test('touch bumps last used and usage', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'test data' }, T0)
    const id = store.entries[0].id
    const future = new Date(T0.getTime() + 3600_000)
    store = touch(store, id, future)
    assert.equal(store.entries[0].usageCount, 1)
    assert.equal(store.entries[0].lastUsedAt, future.toISOString())
  })

  test('retrieval respects requireTagsAny filter', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'pendule physique', tags: ['phys'] }, T0)
    store = addMemory(store, { kind: 'fact', text: 'TLS handshake', tags: ['cyber'] }, T0)
    const out = retrieve(store, 'TLS', T0, { requireTagsAny: ['cyber'] })
    assert.equal(out.length, 1)
    assert.ok(out[0].entry.tags.includes('cyber'))
  })

  test('prune drops old entries but keeps pinned', () => {
    let store = createMemoryStore()
    const ancient = new Date('2020-01-01')
    store = addMemory(store, { kind: 'pinned', text: 'sticky note' }, ancient)
    store = addMemory(store, { kind: 'fact', text: 'old fact' }, ancient)
    store = prune(store, { maxAgeDays: 30, now: T0 })
    assert.equal(store.entries.length, 1)
    assert.equal(store.entries[0].kind, 'pinned')
  })

  test('prune enforces maxEntries', () => {
    let store = createMemoryStore()
    for (let i = 0; i < 50; i += 1) {
      store = addMemory(store, { kind: 'fact', text: `entry ${i}`, importance: i / 50 }, T0)
    }
    store = prune(store, { maxEntries: 10, now: T0 })
    assert.ok(store.entries.length <= 10)
  })

  test('BM25 préfère le doc court contenant le terme au doc long le contenant pareil', () => {
    let store = createMemoryStore()
    // Doc court : 4 tokens, contient "pendule"
    store = addMemory(store, { kind: 'fact', text: 'le pendule physique court', importance: 0.5 }, T0)
    // Doc long : 30 tokens, contient "pendule" une fois mais dilué dans du bruit
    const longText = 'optique chimie thermo electronique informatique algorithme reseau capteur '
      + 'microcontroleur led resistance condensateur diode bobine moteur transistor amplificateur '
      + 'pendule physique long et beaucoup d autres concepts physiques varies'
    store = addMemory(store, { kind: 'fact', text: longText, importance: 0.5 }, T0)
    const out = retrieve(store, 'pendule', T0, { limit: 2 })
    // Le doc court doit ranker plus haut grâce à la normalisation BM25 par longueur.
    assert.equal(out[0].entry.text, 'le pendule physique court', `top doc ${out[0].entry.text}`)
  })

  test('BM25 score = 0 quand aucun token query ne match', () => {
    let store = createMemoryStore()
    store = addMemory(store, { kind: 'fact', text: 'pendule physique', importance: 0.5 }, T0)
    const out = retrieve(store, 'optique chimie', T0)
    // 0 match → score = recency boost seulement (très faible) ou 0
    assert.ok(out.length === 0 || out[0].score < 0.2)
  })

  test('BM25 boost les termes rares (IDF)', () => {
    let store = createMemoryStore()
    // 4 docs contiennent "physique" → IDF faible
    for (let i = 0; i < 4; i += 1) {
      store = addMemory(store, { kind: 'fact', text: `physique cours ${i}`, importance: 0.5 }, T0)
    }
    // 1 doc contient "argon2id" → IDF élevé
    store = addMemory(store, { kind: 'fact', text: 'argon2id sécurité', importance: 0.5 }, T0)
    const r1 = retrieve(store, 'argon2id', T0)
    const r2 = retrieve(store, 'physique', T0)
    // Le top score sur "argon2id" doit être > top score sur "physique" (terme rare > terme commun)
    assert.ok(r1[0].score > r2[0].score, `argon2id ${r1[0].score} vs physique ${r2[0].score}`)
  })
})

describe('intent router', () => {
  test('code keywords route to code module', () => {
    const r = routeIntent("écris-moi une fonction Python qui calcule la TVA")
    assert.equal(r.moduleId, 'code')
    assert.ok(r.confidence > 0.2)
  })

  test('3d keywords route to 3d module', () => {
    const r = routeIntent('génère un modèle 3D PBR de samouraï low poly')
    assert.equal(r.moduleId, '3d')
  })

  test('learning + BAC routes to learning', () => {
    const r = routeIntent("crée-moi un quiz BAC STI2D sur l'énergie")
    assert.equal(r.moduleId, 'learning')
  })

  test('cyber + Argon2 routes to cyber', () => {
    const r = routeIntent('compare Argon2 et bcrypt côté sécurité')
    assert.equal(r.moduleId, 'cyber')
  })

  test('simulator + pendule routes to simulator', () => {
    const r = routeIntent('simule un pendule double avec amortissement')
    assert.equal(r.moduleId, 'simulator')
  })

  test('cowork + commit-push routes to cowork', () => {
    const r = routeIntent('commit et push tout vers GitHub')
    assert.equal(r.moduleId, 'cowork')
  })

  test('vide / salutation tombe sur conversation', () => {
    const r = routeIntent('salut comment ça va')
    assert.equal(r.moduleId, 'conversation')
  })

  test('ambiguous flagged when two profiles tie closely', () => {
    // Equal weight from image and code profiles.
    const r = routeIntent('image code')
    assert.ok(r.ambiguous, `top=${r.moduleId} conf=${r.confidence} second=${r.scores[1]?.moduleId}/${r.scores[1]?.score}`)
  })

  test('hint mentions matched pattern', () => {
    const r = routeIntent('refactor cette classe TypeScript')
    assert.ok(r.hint.toLowerCase().includes('code'))
  })

  test('sticky bias from context', () => {
    const r1 = routeIntent('encore une variante', ['[module:image] discuté plus tôt'])
    assert.equal(r1.moduleId, 'image')
  })

  test('listModules exposes 11 entries', () => {
    assert.equal(listModules().length, 11)
  })
})

describe('response cache', () => {
  test('returns cached response on identical prompt', () => {
    const cache = new ResponseCache({ ttlSeconds: 0 })
    cache.set('Quelle est la capitale de la France ?', 'Paris', 0.001)
    const hit = cache.get('Quelle est la capitale de la France ?')
    assert.ok(hit)
    assert.equal(hit.response, 'Paris')
    assert.equal(hit.hits, 1)
  })

  test('fuzzy hit on reordered tokens', () => {
    const cache = new ResponseCache({ ttlSeconds: 0, fuzzyThreshold: 0.5 })
    cache.set('explique le pendule simple physique', 'voilà...')
    const hit = cache.get('physique simple pendule explique')
    assert.ok(hit)
  })

  test('different prompts → no hit', () => {
    const cache = new ResponseCache({ ttlSeconds: 0 })
    cache.set('A', 'rep A')
    assert.equal(cache.get('B'), null)
  })

  test('LRU eviction when over maxEntries', () => {
    const cache = new ResponseCache({ maxEntries: 3, ttlSeconds: 0 })
    cache.set('p1', 'r1')
    cache.set('p2', 'r2')
    cache.set('p3', 'r3')
    cache.set('p4', 'r4')
    assert.equal(cache.stats().size, 3)
    assert.equal(cache.get('p1'), null)
    assert.ok(cache.get('p4'))
  })

  test('TTL expiry honoured', () => {
    const cache = new ResponseCache({ ttlSeconds: 60 })
    const t1 = new Date('2026-05-17T12:00:00Z')
    const t2 = new Date('2026-05-17T12:02:00Z')
    cache.set('q', 'a', 0, t1)
    assert.equal(cache.get('q', t2), null)
  })

  test('stats sum savedCostUsd', () => {
    const cache = new ResponseCache({ ttlSeconds: 0 })
    cache.set('q1', 'a', 0.5)
    cache.set('q2', 'b', 1.5)
    assert.equal(cache.stats().totalSavedUsd, 2)
  })

  test('clear empties store', () => {
    const cache = new ResponseCache()
    cache.set('q', 'a')
    cache.clear()
    assert.equal(cache.stats().size, 0)
  })
})
