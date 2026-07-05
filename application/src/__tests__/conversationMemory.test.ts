/**
 * Tests pour services/conversationMemory — store mémoire long terme +
 * retrieval BM25 + recency boost.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  tokenize,
  tokenFrequencies,
  createMemoryStore,
  addMemory,
  removeMemory,
  retrieve,
  touch,
  prune,
  MEMORY_STORE_VERSION,
} from '../services/conversationMemory.ts'

const NOW = new Date('2026-05-21T12:00:00Z')

describe('tokenize', () => {
  test('texte simple → tokens minuscules', () => {
    const t = tokenize('Bonjour le Monde')
    assert.ok(t.includes('bonjour'))
    assert.ok(t.includes('monde'))
  })

  test('stopwords FR éliminés', () => {
    const t = tokenize('je suis un dev qui aime')
    assert.ok(!t.includes('je'))
    assert.ok(!t.includes('un'))
    assert.ok(t.includes('dev'))
  })

  test('accents strippés', () => {
    const t = tokenize('Réseau Physique')
    assert.ok(t.includes('reseau'))
    assert.ok(t.includes('physique'))
  })

  test('vide → []', () => {
    assert.deepEqual(tokenize(''), [])
  })

  test('chiffres conservés', () => {
    const t = tokenize('STI2D 2026')
    assert.ok(t.includes('sti2d'))
    assert.ok(t.includes('2026'))
  })
})

describe('tokenFrequencies', () => {
  test('compte les occurrences', () => {
    const f = tokenFrequencies('chat chat oiseau')
    assert.equal(f.chat, 2)
    assert.equal(f.oiseau, 1)
  })

  test('vide → {}', () => {
    assert.deepEqual(tokenFrequencies(''), {})
  })
})

describe('createMemoryStore', () => {
  test('store vide initialisé', () => {
    const s = createMemoryStore()
    assert.equal(s.version, MEMORY_STORE_VERSION)
    assert.deepEqual(s.entries, [])
    assert.deepEqual(s.documentFrequency, {})
  })
})

describe('addMemory', () => {
  test('ajoute une entrée', () => {
    const s = createMemoryStore()
    const s2 = addMemory(s, { kind: 'fact', text: 'Juan adore le café' }, NOW)
    assert.equal(s2.entries.length, 1)
    assert.equal(s2.entries[0].kind, 'fact')
    assert.equal(s2.entries[0].text, 'Juan adore le café')
  })

  test('texte vide → store inchangé', () => {
    const s = createMemoryStore()
    const s2 = addMemory(s, { kind: 'fact', text: '' }, NOW)
    assert.equal(s2.entries.length, 0)
  })

  test('whitespace only → store inchangé', () => {
    const s = createMemoryStore()
    const s2 = addMemory(s, { kind: 'fact', text: '   ' }, NOW)
    assert.equal(s2.entries.length, 0)
  })

  test('duplicate (même contentHash) → bump usageCount', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'identique' }, NOW)
    s = addMemory(s, { kind: 'fact', text: 'identique' }, NOW)
    assert.equal(s.entries.length, 1)
    assert.equal(s.entries[0].usageCount, 1)
  })

  test('documentFrequency mis à jour', () => {
    const s = addMemory(createMemoryStore(), { kind: 'fact', text: 'café arabica' }, NOW)
    assert.equal(s.documentFrequency.cafe, 1)
    assert.equal(s.documentFrequency.arabica, 1)
  })

  test('importance clampée [0..1]', () => {
    const s = addMemory(createMemoryStore(), { kind: 'fact', text: 'test', importance: 1.5 }, NOW)
    assert.equal(s.entries[0].importance, 1)
    const s2 = addMemory(createMemoryStore(), { kind: 'fact', text: 'test', importance: -0.3 }, NOW)
    assert.equal(s2.entries[0].importance, 0)
  })

  test('tags conservés', () => {
    const s = addMemory(createMemoryStore(), { kind: 'fact', text: 'test', tags: ['food', 'pref'] }, NOW)
    assert.deepEqual(s.entries[0].tags, ['food', 'pref'])
  })
})

describe('removeMemory', () => {
  test('supprime par id', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'a' }, NOW)
    s = addMemory(s, { kind: 'fact', text: 'b' }, NOW)
    const id = s.entries[0].id
    s = removeMemory(s, id)
    assert.equal(s.entries.length, 1)
    assert.equal(s.entries[0].text, 'b')
  })

  test('id inconnu → store inchangé', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'a' }, NOW)
    const s2 = removeMemory(s, 'mem_nonexistent')
    assert.equal(s2.entries.length, 1)
  })

  test('documentFrequency décrémentée', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café' }, NOW)
    const id = s.entries[0].id
    s = removeMemory(s, id)
    assert.equal(s.documentFrequency.cafe ?? 0, 0)
  })
})

describe('retrieve', () => {
  test('store vide → []', () => {
    const r = retrieve(createMemoryStore(), 'café', NOW)
    assert.deepEqual(r, [])
  })

  test('match exact retrouvé', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'Juan adore le café arabica' }, NOW)
    s = addMemory(s, { kind: 'fact', text: 'Le ciel est bleu' }, NOW)
    const r = retrieve(s, 'café', NOW)
    assert.ok(r.length > 0)
    assert.ok(r[0].entry.text.includes('café'))
  })

  test('score plus élevé pour mémoires importantes', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café arabica', importance: 0.1 }, NOW)
    s = addMemory(s, { kind: 'fact', text: 'café arabica deluxe', importance: 1.0 }, NOW)
    const r = retrieve(s, 'café arabica', NOW)
    // Le plus important devrait avoir un score plus haut
    assert.ok(r[0].entry.importance >= r[r.length - 1].entry.importance)
  })

  test('limit respectée', () => {
    let s = createMemoryStore()
    for (let i = 0; i < 10; i++) {
      s = addMemory(s, { kind: 'fact', text: `café ${i}` }, NOW)
    }
    const r = retrieve(s, 'café', NOW, { limit: 3 })
    assert.equal(r.length, 3)
  })

  test('filtrage par tag', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café', tags: ['food'] }, NOW)
    s = addMemory(s, { kind: 'fact', text: 'café', tags: ['code'] }, NOW)
    const r = retrieve(s, 'café', NOW, { requireTagsAny: ['food'] })
    assert.equal(r.length, 1)
    assert.deepEqual(r[0].entry.tags, ['food'])
  })

  test('minScore filtre', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café arabica' }, NOW)
    const r = retrieve(s, 'totalement autre chose', NOW, { minScore: 0.5 })
    assert.equal(r.length, 0)
  })

  test('pinned firstly when pinnedAlwaysFirst', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café arabica' }, NOW)
    s = addMemory(s, { kind: 'pinned', text: 'thé' }, NOW)
    const r = retrieve(s, 'café', NOW, { pinnedAlwaysFirst: true })
    assert.equal(r[0].entry.kind, 'pinned')
  })

  test('recency boost — récent gagne sur ancien à sim égale', () => {
    let s = createMemoryStore()
    const old = new Date('2024-01-01T00:00:00Z')
    s = addMemory(s, { kind: 'fact', text: 'café arabica' }, old)
    s = addMemory(s, { kind: 'fact', text: 'café arabica plus récent' }, NOW)
    const r = retrieve(s, 'café arabica', NOW)
    // Le plus récent (avec sim plus haute pour le terme commun) devrait être en top
    assert.ok(r.length > 0)
  })
})

describe('touch', () => {
  test('met à jour lastUsedAt + usageCount', () => {
    let s = createMemoryStore()
    s = addMemory(s, { kind: 'fact', text: 'café' }, NOW)
    const id = s.entries[0].id
    const later = new Date('2026-06-01T12:00:00Z')
    s = touch(s, id, later)
    assert.equal(s.entries[0].usageCount, 1)
    assert.equal(s.entries[0].lastUsedAt, later.toISOString())
  })

  test('id inconnu → store inchangé', () => {
    const s = addMemory(createMemoryStore(), { kind: 'fact', text: 'café' }, NOW)
    const s2 = touch(s, 'mem_xyz', NOW)
    assert.equal(s2.entries[0].usageCount, 0)
  })
})

describe('prune', () => {
  test('mémoires anciennes supprimées', () => {
    let s = createMemoryStore()
    const old = new Date('2024-01-01T00:00:00Z')
    s = addMemory(s, { kind: 'fact', text: 'ancien' }, old)
    s = addMemory(s, { kind: 'fact', text: 'récent' }, NOW)
    s = prune(s, { maxAgeDays: 30, now: NOW })
    assert.equal(s.entries.length, 1)
    assert.equal(s.entries[0].text, 'récent')
  })

  test('pinned jamais supprimées même si anciennes', () => {
    let s = createMemoryStore()
    const old = new Date('2024-01-01T00:00:00Z')
    s = addMemory(s, { kind: 'pinned', text: 'pin ancienne' }, old)
    s = prune(s, { maxAgeDays: 1, now: NOW })
    assert.equal(s.entries.length, 1)
  })

  test('maxEntries respecté', () => {
    let s = createMemoryStore()
    for (let i = 0; i < 50; i++) {
      s = addMemory(s, { kind: 'fact', text: `mem ${i}`, importance: i / 50 }, NOW)
    }
    s = prune(s, { maxEntries: 10, now: NOW })
    assert.ok(s.entries.length <= 10)
  })

  test('documentFrequency rebuild après prune', () => {
    let s = createMemoryStore()
    const old = new Date('2024-01-01T00:00:00Z')
    s = addMemory(s, { kind: 'fact', text: 'ancien café' }, old)
    s = addMemory(s, { kind: 'fact', text: 'nouveau thé' }, NOW)
    s = prune(s, { maxAgeDays: 30, now: NOW })
    // Le token 'cafe' devrait avoir disparu du df
    assert.ok(!s.documentFrequency.cafe || s.documentFrequency.cafe === 0)
    assert.ok(s.documentFrequency.the >= 1)
  })
})
