/**
 * Tests JWT inspector.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { inspectJwt, summariseJwt } from '../services/cyber/jwtInspector.ts'

// Helper : encode un JWT (sans signer pour les tests).
function b64url(obj: object): string {
  return Buffer.from(JSON.stringify(obj))
    .toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function makeToken(header: object, payload: object, sig = 'sigplaceholder'): string {
  return `${b64url(header)}.${b64url(payload)}.${sig}`
}

describe('JWT inspector', () => {
  test('JWT valide → header + payload décodés', () => {
    const token = makeToken({ alg: 'HS256', typ: 'JWT' }, { iss: 'aurora', sub: 'juan', exp: 2000000000 })
    const r = inspectJwt(token)
    assert.equal(r.header?.alg, 'HS256')
    assert.equal(r.payload?.iss, 'aurora')
  })

  test('alg=none détecté → blocker', () => {
    const token = makeToken({ alg: 'none' }, { sub: 'admin' })
    const r = inspectJwt(token)
    assert.ok(r.issues.some((i) => i.severity === 'block' && /alg=none|none/i.test(i.message)))
  })

  test('token expiré détecté', () => {
    const past = Math.floor(Date.now() / 1000) - 3600
    const token = makeToken({ alg: 'HS256', typ: 'JWT' }, { exp: past })
    const r = inspectJwt(token)
    assert.equal(r.expired, true)
    assert.ok(r.issues.some((i) => /expir/i.test(i.message)))
  })

  test('token sans exp → warning', () => {
    const token = makeToken({ alg: 'HS256', typ: 'JWT' }, { sub: 'user' })
    const r = inspectJwt(token)
    assert.ok(r.issues.some((i) => /Pas de claim exp/i.test(i.message)))
  })

  test('token nbf futur → notYetValid', () => {
    const future = Math.floor(Date.now() / 1000) + 7200
    const token = makeToken({ alg: 'HS256' }, { nbf: future, exp: future + 3600 })
    const r = inspectJwt(token)
    assert.equal(r.notYetValid, true)
  })

  test('algo obsolète MD5 → error', () => {
    const token = makeToken({ alg: 'MD5' }, { sub: 'x' })
    const r = inspectJwt(token)
    assert.ok(r.issues.some((i) => i.severity === 'error' && /obsolète/i.test(i.message)))
  })

  test('claim password en clair → error', () => {
    const token = makeToken({ alg: 'HS256' }, { sub: 'x', password: 'plain' })
    const r = inspectJwt(token)
    assert.ok(r.issues.some((i) => /password.*secret/i.test(i.message)))
  })

  test('format invalide → blocker', () => {
    const r = inspectJwt('not.a.jwt.too.many.parts')
    assert.ok(r.issues.some((i) => i.severity === 'block'))
  })

  test('JSON invalide dans header → block', () => {
    const r = inspectJwt('aGVsbG8=.eyJzdWIiOiJ4In0.sig')
    // "hello" base64 puis n'est pas un JSON
    assert.ok(r.issues.some((i) => i.severity === 'block'))
  })

  test('summariseJwt produit un récap', () => {
    const token = makeToken({ alg: 'HS256' }, { iss: 'aurora', sub: 'juan', exp: 2000000000 })
    const r = inspectJwt(token)
    const s = summariseJwt(r)
    assert.match(s, /alg=HS256/)
    assert.match(s, /iss=aurora/)
  })

  test('summariseJwt token expiré inclut EXPIRÉ', () => {
    const token = makeToken({ alg: 'HS256' }, { exp: 1 })
    const r = inspectJwt(token)
    assert.match(summariseJwt(r), /EXPIR/i)
  })

  test('ageHours calculé depuis iat', () => {
    const iat = Math.floor(Date.now() / 1000) - 3600 * 5
    const token = makeToken({ alg: 'HS256' }, { iat, exp: iat + 86400 })
    const r = inspectJwt(token)
    assert.ok(r.ageHours !== null && Math.abs(r.ageHours - 5) < 0.1)
  })
})
