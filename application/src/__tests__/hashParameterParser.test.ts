/**
 * Tests pour cyber/hashParameterParser — parse + audit OWASP 2024 des hashes adaptatifs.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  parseArgon2,
  parseBcrypt,
  parseScrypt,
  auditHash,
} from '../services/cyber/hashParameterParser.ts'

describe('parseArgon2', () => {
  test('argon2id v=19 m=65536 t=3 p=1 parsé', () => {
    const r = parseArgon2('$argon2id$v=19$m=65536,t=3,p=1$c2FsdA$ZGlnZXN0')
    assert.ok(r)
    assert.equal(r!.variant, 'id')
    assert.equal(r!.version, 19)
    assert.equal(r!.memoryKib, 65536)
    assert.equal(r!.timeCost, 3)
    assert.equal(r!.parallelism, 1)
    assert.equal(r!.salt, 'c2FsdA')
    assert.equal(r!.digest, 'ZGlnZXN0')
  })

  test('argon2i parsé', () => {
    const r = parseArgon2('$argon2i$v=19$m=4096,t=3,p=1$abc$def')
    assert.equal(r?.variant, 'i')
  })

  test('argon2d parsé', () => {
    const r = parseArgon2('$argon2d$v=19$m=4096,t=3,p=1$abc$def')
    assert.equal(r?.variant, 'd')
  })

  test('format invalide → null', () => {
    assert.equal(parseArgon2('$invalid$'), null)
    assert.equal(parseArgon2('$argon2id$v=19$m=BAD,t=3,p=1$a$b'), null)
  })

  test('chaîne arbitraire → null', () => {
    assert.equal(parseArgon2('not a hash'), null)
  })
})

describe('parseBcrypt', () => {
  test('$2b$12$... → variant 2b + cost 12', () => {
    // saltAndDigest doit faire exactement 53 chars dans l'alphabet bcrypt
    const r = parseBcrypt('$2b$12$' + 'a'.repeat(53))
    assert.ok(r)
    assert.equal(r!.variant, '2b')
    assert.equal(r!.cost, 12)
    assert.equal(r!.saltAndDigest.length, 53)
  })

  test('variantes 2a/2x/2y', () => {
    assert.equal(parseBcrypt('$2a$10$' + 'a'.repeat(53))?.variant, '2a')
    assert.equal(parseBcrypt('$2y$11$' + 'b'.repeat(53))?.variant, '2y')
  })

  test('cost à 1 chiffre → null (regex demande 2 chiffres)', () => {
    assert.equal(parseBcrypt('$2b$5$' + 'a'.repeat(53)), null)
  })

  test('format invalide → null', () => {
    assert.equal(parseBcrypt('$2b$xx$short'), null)
  })
})

describe('parseScrypt', () => {
  test('$scrypt$N=131072,r=8,p=1 → parsé', () => {
    const r = parseScrypt('$scrypt$N=131072,r=8,p=1$salt$digest')
    assert.ok(r)
    assert.equal(r!.N, 131072)
    assert.equal(r!.r, 8)
    assert.equal(r!.p, 1)
  })

  test('format invalide → null', () => {
    assert.equal(parseScrypt('$scrypt$N=BAD$x$y'), null)
  })
})

describe('auditHash — verdict OWASP', () => {
  test('argon2id m=65536 t=3 → recommended', () => {
    const r = auditHash('$argon2id$v=19$m=65536,t=3,p=1$salt$digest')
    assert.equal(r.algorithm, 'argon2id')
    assert.equal(r.verdict, 'recommended')
  })

  test('argon2id m=4096 t=3 → undersized (< 19 MiB)', () => {
    const r = auditHash('$argon2id$v=19$m=4096,t=3,p=1$salt$digest')
    assert.equal(r.verdict, 'undersized')
    assert.ok(r.recommendations.some((rec) => rec.includes('19 MiB')))
  })

  test('argon2i (pas id) → recommandation variant', () => {
    const r = auditHash('$argon2i$v=19$m=65536,t=3,p=1$salt$digest')
    assert.ok(r.recommendations.some((rec) => rec.includes('argon2id')))
  })

  test('bcrypt cost=12 → acceptable', () => {
    const r = auditHash('$2b$12$' + 'a'.repeat(53))
    assert.equal(r.algorithm, 'bcrypt')
    assert.equal(r.verdict, 'acceptable')
  })

  test('bcrypt cost=8 → undersized', () => {
    const r = auditHash('$2b$08$' + 'a'.repeat(53))
    assert.equal(r.verdict, 'undersized')
  })

  test('bcrypt $2a$ → recommandation migration $2b$', () => {
    const r = auditHash('$2a$12$' + 'a'.repeat(53))
    assert.ok(r.recommendations.some((rec) => rec.includes('2b')))
  })

  test('scrypt N=131072 → recommended (≥ 2^17)', () => {
    const r = auditHash('$scrypt$N=131072,r=8,p=1$s$d')
    assert.equal(r.algorithm, 'scrypt')
    assert.equal(r.verdict, 'recommended')
  })

  test('scrypt N=1024 → undersized', () => {
    const r = auditHash('$scrypt$N=1024,r=8,p=1$s$d')
    assert.equal(r.verdict, 'undersized')
  })

  test('MD5 nu (32 hex) → banned', () => {
    const r = auditHash('5d41402abc4b2a76b9719d911017c592')
    assert.equal(r.verdict, 'banned')
    assert.ok(r.recommendations.some((rec) => rec.includes('MD5')))
  })

  test('SHA-1 nu (40 hex) → banned', () => {
    const r = auditHash('aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d')
    assert.equal(r.verdict, 'banned')
  })

  test('SHA-256 nu (64 hex) → banned', () => {
    const r = auditHash('2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824')
    assert.equal(r.verdict, 'banned')
    assert.ok(r.recommendations.some((rec) => rec.includes('SHA-256')))
  })

  test('format inconnu → banned + parsed null', () => {
    const r = auditHash('totally-random-string-not-a-hash')
    assert.equal(r.verdict, 'banned')
    assert.equal(r.parsed, null)
  })
})
