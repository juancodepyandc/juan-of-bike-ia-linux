/**
 * Tests pour cyber/rainbowTableDemo — pré-compute hashes + lookup + salt defense.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildRainbowTable,
  lookupHash,
  hashWithSalt,
  generateSalt,
  RAINBOW_PASSWORDS,
} from '../services/cyber/rainbowTableDemo.ts'

describe('buildRainbowTable', () => {
  test('contient au moins 3 algos × N passwords', async () => {
    const table = await buildRainbowTable()
    assert.ok(table.length >= 50 * 3) // 50 passwords × 3 algos
  })

  test('structure {plaintext, hash, algo}', async () => {
    const table = await buildRainbowTable()
    for (const entry of table.slice(0, 5)) {
      assert.ok(entry.plaintext)
      assert.ok(entry.hash)
      assert.ok(['MD5', 'SHA-1', 'SHA-256'].includes(entry.algo))
    }
  })

  test('cached entre appels', async () => {
    const a = await buildRainbowTable()
    const b = await buildRainbowTable()
    assert.equal(a, b) // même référence cache
  })

  test('SHA-256 hash 64 hex chars', async () => {
    const table = await buildRainbowTable()
    const sha256Entries = table.filter((e) => e.algo === 'SHA-256')
    for (const e of sha256Entries.slice(0, 3)) {
      assert.match(e.hash, /^[0-9a-f]{64}$/)
    }
  })

  test('SHA-1 hash 40 hex chars', async () => {
    const table = await buildRainbowTable()
    const sha1Entries = table.filter((e) => e.algo === 'SHA-1')
    for (const e of sha1Entries.slice(0, 3)) {
      assert.match(e.hash, /^[0-9a-f]{40}$/)
    }
  })

  test('MD5 hash 32 hex chars', async () => {
    const table = await buildRainbowTable()
    const md5Entries = table.filter((e) => e.algo === 'MD5')
    for (const e of md5Entries.slice(0, 3)) {
      assert.match(e.hash, /^[0-9a-f]{32}$/)
    }
  })
})

describe('lookupHash', () => {
  test('hash de "password" → found', async () => {
    // SHA-256("password") canonical
    const r = await lookupHash('5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8')
    assert.equal(r.found, true)
    assert.equal(r.plaintext, 'password')
    assert.equal(r.algo, 'SHA-256')
  })

  test('hash inconnu → not found', async () => {
    // Random hex 64 chars
    const r = await lookupHash('0000000000000000000000000000000000000000000000000000000000000000')
    assert.equal(r.found, false)
  })

  test('hash vide → not found', async () => {
    const r = await lookupHash('')
    assert.equal(r.found, false)
  })

  test('case insensitive', async () => {
    const r1 = await lookupHash('5E884898DA28047151D0E56F8DC6292773603D0D6AABBDD62A11EF721D1542D8')
    const r2 = await lookupHash('5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8')
    assert.equal(r1.found, r2.found)
  })

  test('caractères non-hex strippés', async () => {
    const r = await lookupHash('5e884898-da28-0471-51d0-e56f8dc62927:73603d0d6aabbdd62a11ef721d1542d8')
    assert.equal(r.found, true)
  })

  test('durée ms reportée', async () => {
    const r = await lookupHash('password-hash-fake')
    assert.ok(typeof r.ms === 'number')
    assert.ok(r.ms >= 0)
  })
})

describe('hashWithSalt — défense via salt', () => {
  test('hash salt + password → 64 hex', async () => {
    const r = await hashWithSalt('password', 'random-salt-xyz')
    assert.match(r, /^[0-9a-f]{64}$/)
  })

  test('hash NOT dans rainbow table (l intérêt du salt)', async () => {
    const salted = await hashWithSalt('password', 'random-salt-xyz')
    const lookup = await lookupHash(salted)
    assert.equal(lookup.found, false)
  })

  test('salt différent → hash différent (même password)', async () => {
    const a = await hashWithSalt('password', 'salt-A')
    const b = await hashWithSalt('password', 'salt-B')
    assert.notEqual(a, b)
  })

  test('même salt + même password → déterministe', async () => {
    const a = await hashWithSalt('hello', 'fixed-salt')
    const b = await hashWithSalt('hello', 'fixed-salt')
    assert.equal(a, b)
  })
})

describe('generateSalt', () => {
  test('produit 32 hex chars (16 bytes)', () => {
    const s = generateSalt()
    assert.match(s, /^[0-9a-f]{32}$/)
  })

  test('2 appels → salts différents (entropy)', () => {
    const a = generateSalt()
    const b = generateSalt()
    assert.notEqual(a, b)
  })
})

describe('RAINBOW_PASSWORDS', () => {
  test('contient classiques', () => {
    assert.ok(RAINBOW_PASSWORDS.includes('password'))
    assert.ok(RAINBOW_PASSWORDS.includes('123456'))
    assert.ok(RAINBOW_PASSWORDS.includes('azerty'))
    assert.ok(RAINBOW_PASSWORDS.includes('motdepasse'))
  })

  test('taille raisonnable', () => {
    assert.ok(RAINBOW_PASSWORDS.length >= 40)
    assert.ok(RAINBOW_PASSWORDS.length <= 100)
  })
})
