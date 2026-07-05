/**
 * Tests pour cyber/jwtForger — forge JWTs (alg=none, HS256) + crack dict.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  forgeAlgNone,
  forgeHs256,
  crackHs256,
  JWT_WEAK_SECRETS,
} from '../services/cyber/jwtForger.ts'

describe('forgeAlgNone', () => {
  test('produit un JWT 3-parts avec signature vide', () => {
    const r = forgeAlgNone({ sub: 'alice', admin: true })
    const parts = r.token.split('.')
    assert.equal(parts.length, 3)
    assert.equal(parts[2], '') // signature vide
    assert.equal(r.signaturePart, '')
  })

  test('header alg=none + typ=JWT', () => {
    const r = forgeAlgNone({ sub: '1' })
    assert.equal(r.header.alg, 'none')
    assert.equal(r.header.typ, 'JWT')
  })

  test('payload préservé', () => {
    const payload = { sub: 'alice', role: 'admin', extra: { nested: true } }
    const r = forgeAlgNone(payload)
    assert.deepEqual(r.payload, payload)
  })

  test('pedagogy non vide + CVE référencée', () => {
    const r = forgeAlgNone({ sub: 'x' })
    assert.ok(r.pedagogy.length > 0)
    assert.ok(r.pedagogy.some((p) => p.includes('CVE 2015-9235')))
  })

  test('base64url sans padding', () => {
    const r = forgeAlgNone({ sub: 'x' })
    const parts = r.token.split('.')
    // base64url ne doit pas contenir = + /
    assert.ok(!parts[0].includes('='))
    assert.ok(!parts[0].includes('+'))
    assert.ok(!parts[0].includes('/'))
    assert.ok(!parts[1].includes('='))
  })
})

describe('forgeHs256', () => {
  test('produit un JWT 3-parts avec signature non-vide', async () => {
    const r = await forgeHs256({ sub: 'alice' }, 'topsecret')
    const parts = r.token.split('.')
    assert.equal(parts.length, 3)
    assert.ok(parts[2].length > 0)
    assert.equal(r.signaturePart, parts[2])
  })

  test('header alg=HS256', async () => {
    const r = await forgeHs256({ sub: '1' }, 'k')
    assert.equal(r.header.alg, 'HS256')
  })

  test('même secret + même payload → même token (déterministe)', async () => {
    const a = await forgeHs256({ sub: 'alice' }, 'secret')
    const b = await forgeHs256({ sub: 'alice' }, 'secret')
    assert.equal(a.token, b.token)
  })

  test('secret différent → signature différente', async () => {
    const a = await forgeHs256({ sub: 'alice' }, 'secret-A')
    const b = await forgeHs256({ sub: 'alice' }, 'secret-B')
    assert.notEqual(a.signaturePart, b.signaturePart)
  })

  test('payload différent → signature différente', async () => {
    const a = await forgeHs256({ sub: 'alice' }, 'k')
    const b = await forgeHs256({ sub: 'bob' }, 'k')
    assert.notEqual(a.signaturePart, b.signaturePart)
  })

  test('pedagogy mentionne secret confidentiality', async () => {
    const r = await forgeHs256({ sub: '1' }, 'k')
    assert.ok(r.pedagogy.some((p) => p.toLowerCase().includes('secret')))
  })
})

describe('crackHs256', () => {
  test('secret dans wordlist → trouvé', async () => {
    const forged = await forgeHs256({ sub: 'alice' }, 'admin')
    const r = await crackHs256(forged.token, ['wrong', 'admin', 'extra'])
    assert.equal(r.found, true)
    assert.equal(r.secret, 'admin')
    assert.equal(r.attempts, 2) // s'arrête au trouvé
  })

  test('secret absent → not found', async () => {
    const forged = await forgeHs256({ sub: 'x' }, 'rare-secret-12345')
    const r = await crackHs256(forged.token, ['wrong1', 'wrong2'])
    assert.equal(r.found, false)
    assert.equal(r.attempts, 2)
  })

  test('token malformé (pas 3 parts) → attempts 0', async () => {
    const r = await crackHs256('not.a.real.token', ['x'])
    assert.equal(r.found, false)
    assert.equal(r.attempts, 0)
  })

  test('durationMs présent', async () => {
    const forged = await forgeHs256({ sub: 'x' }, 'k')
    const r = await crackHs256(forged.token, ['x'])
    assert.ok(typeof r.durationMs === 'number')
  })

  test('crack contre JWT_WEAK_SECRETS', async () => {
    const forged = await forgeHs256({ sub: 'alice' }, 'secret')
    const r = await crackHs256(forged.token, [...JWT_WEAK_SECRETS])
    assert.equal(r.found, true)
    assert.equal(r.secret, 'secret')
  })
})

describe('JWT_WEAK_SECRETS', () => {
  test('contient classiques', () => {
    assert.ok(JWT_WEAK_SECRETS.includes('secret'))
    assert.ok(JWT_WEAK_SECRETS.includes('admin'))
    assert.ok(JWT_WEAK_SECRETS.includes('changeme'))
  })

  test('taille raisonnable', () => {
    assert.ok(JWT_WEAK_SECRETS.length >= 15)
  })
})
