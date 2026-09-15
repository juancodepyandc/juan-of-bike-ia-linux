/**
 * Tests pour cyber/jwtInspector — décodage JWT + audit OWASP.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { inspectJwt, summariseJwt } from '../services/cyber/jwtInspector.ts'

function base64url(s: string): string {
  return Buffer.from(s, 'utf-8')
    .toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function makeJwt(header: object, payload: object, signature = 'sig'): string {
  return `${base64url(JSON.stringify(header))}.${base64url(JSON.stringify(payload))}.${signature}`
}

const NOW = new Date('2026-05-20T10:00:00Z')
const NOW_SEC = Math.floor(NOW.getTime() / 1000)

describe('inspectJwt — token malformé', () => {
  test('vide → block', () => {
    const r = inspectJwt('', NOW)
    assert.ok(r.issues.some(i => i.severity === 'block'))
  })

  test('1 seul segment → block', () => {
    const r = inspectJwt('justonepart', NOW)
    assert.ok(r.issues.some(i => i.severity === 'block'))
    assert.equal(r.header, null)
  })

  test('2 segments → block', () => {
    const r = inspectJwt('aaa.bbb', NOW)
    assert.ok(r.issues.some(i => i.severity === 'block' && i.message.includes('mal formé')))
  })

  test('segments vides ou base64url invalide → block', () => {
    for (const token of ['..', '!.!.sig', 'a.a.sig', 'e30=.e30=.sig']) {
      assert.ok(inspectJwt(token, NOW).issues.some(i => i.severity === 'block'), token)
    }
  })

  test('header et payload doivent être des objets JSON', () => {
    for (const value of [null, [], 'text', 42, true]) {
      const part = base64url(JSON.stringify(value))
      const badHeader = inspectJwt(`${part}.${base64url('{}')}.sig`, NOW)
      const badPayload = inspectJwt(`${base64url('{"alg":"HS256"}')}.${part}.sig`, NOW)
      assert.equal(badHeader.header, null)
      assert.equal(badPayload.payload, null)
      assert.ok(badHeader.issues.some(i => i.severity === 'block'))
      assert.ok(badPayload.issues.some(i => i.severity === 'block'))
    }
  })

  test('alg manquant ou de type incorrect → block sans exception', () => {
    for (const alg of [undefined, null, '', ' ', 123, { toString: null }]) {
      const result = inspectJwt(makeJwt({ alg }, {}), NOW)
      assert.equal(result.header, null)
      assert.ok(result.issues.some(i => i.severity === 'block'))
    }
  })

  test('UTF-8 invalide dans une chaîne JSON → block', () => {
    const bytes = Buffer.concat([Buffer.from('{"sub":"'), Buffer.from([0xff]), Buffer.from('"}')])
    const token = `${base64url('{"alg":"HS256"}')}.${bytes.toString('base64url')}.sig`
    assert.equal(inspectJwt(token, NOW).payload, null)
  })
})

describe('inspectJwt — décodage', () => {
  test('header + payload bien décodés', () => {
    const token = makeJwt({ alg: 'HS256', typ: 'JWT' }, { sub: '123', iss: 'aurora' })
    const r = inspectJwt(token, NOW)
    assert.equal(r.header?.alg, 'HS256')
    assert.equal(r.payload?.sub, '123')
    assert.equal(r.payload?.iss, 'aurora')
  })

  test('préserve les claims Unicode, y compris les emojis', () => {
    const payload = { sub: 'élève 🙂', iss: 'école' }
    assert.deepEqual(inspectJwt(makeJwt({ alg: 'HS256' }, payload), NOW).payload, payload)
  })

  test('signature préservée', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: 'x' }, 'abc123')
    const r = inspectJwt(token, NOW)
    assert.equal(r.signature, 'abc123')
  })
})

describe('inspectJwt — failles OWASP', () => {
  test('alg=none → block', () => {
    const token = makeJwt({ alg: 'none', typ: 'JWT' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'block' && i.message.includes('alg=none')))
  })

  test('alg=NONE (uppercase) → block', () => {
    const token = makeJwt({ alg: 'NONE' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'block'))
  })

  test('alg=MD5 → error obsolète', () => {
    const token = makeJwt({ alg: 'MD5' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'error' && i.message.includes('obsolète')))
  })

  test('kid contient ".." → path traversal', () => {
    const token = makeJwt({ alg: 'HS256', kid: '../../etc/passwd' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.message.includes('path traversal')))
  })

  test('claim "password" → secret leak', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', password: 'leaked' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'error' && i.message.includes('password')))
  })

  test('claim "api_key" → secret leak', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', api_key: 'sk-xxx' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'error'))
  })

  test('header sans typ → info', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.severity === 'info' && i.message.includes('typ')))
  })
})

describe('inspectJwt — validité temporelle', () => {
  test('exp dans le passé → expired', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', exp: NOW_SEC - 3600 })
    const r = inspectJwt(token, NOW)
    assert.equal(r.expired, true)
    assert.ok(r.issues.some(i => i.message.includes('expiré')))
  })

  test('exp dans le futur → pas expired', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', exp: NOW_SEC + 3600 })
    const r = inspectJwt(token, NOW)
    assert.equal(r.expired, false)
  })

  test('exp à la date courante → expired', () => {
    assert.equal(inspectJwt(makeJwt({ alg: 'HS256' }, { exp: NOW_SEC }), NOW).expired, true)
  })

  test('respecte les fractions de seconde de NumericDate', () => {
    const now = new Date(NOW.getTime() + 750)
    assert.equal(inspectJwt(makeJwt({ alg: 'HS256' }, { exp: NOW_SEC + 0.5 }), now).expired, true)
    assert.equal(inspectJwt(makeJwt({ alg: 'HS256' }, { exp: NOW_SEC + 0.9 }), now).expired, false)
  })

  test('signale les dates non finies et les claims temporels non numériques', () => {
    const payload = base64url('{"exp":1e400,"nbf":"tomorrow","iat":1e400}')
    const result = inspectJwt(`${base64url('{"alg":"HS256"}')}.${payload}.sig`, NOW)
    for (const claim of ['exp', 'nbf', 'iat']) {
      assert.ok(result.issues.some(i => i.severity === 'warn' && i.message.startsWith(claim)))
    }
    assert.equal(result.ageHours, null)
    assert.equal(result.notYetValid, false)
  })

  test('nbf futur → notYetValid', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', exp: NOW_SEC + 3600, nbf: NOW_SEC + 1000 })
    const r = inspectJwt(token, NOW)
    assert.equal(r.notYetValid, true)
  })

  test('iat → ageHours calculé', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', exp: NOW_SEC + 3600, iat: NOW_SEC - 7200 })
    const r = inspectJwt(token, NOW)
    assert.ok(r.ageHours !== null)
    assert.ok(Math.abs((r.ageHours as number) - 2) < 0.01)
  })

  test('token > 1 an → warn', () => {
    const oneYearAgo = NOW_SEC - 365 * 24 * 3600 - 1
    const token = makeJwt({ alg: 'HS256' }, { sub: '1', exp: NOW_SEC + 3600, iat: oneYearAgo })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.message.includes('anormalement vieux')))
  })

  test('pas de exp → warn (sans expiration)', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: '1' })
    const r = inspectJwt(token, NOW)
    assert.ok(r.issues.some(i => i.message.includes('sans expiration')))
  })
})

describe('summariseJwt', () => {
  test('résume alg + iss + sub', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: 'alice', iss: 'aurora', exp: NOW_SEC + 3600 })
    const r = inspectJwt(token, NOW)
    const s = summariseJwt(r)
    assert.ok(s.includes('alg=HS256'))
    assert.ok(s.includes('iss=aurora'))
    assert.ok(s.includes('sub=alice'))
  })

  test('flag EXPIRÉ visible', () => {
    const token = makeJwt({ alg: 'HS256' }, { sub: 'alice', exp: NOW_SEC - 1 })
    const r = inspectJwt(token, NOW)
    assert.ok(summariseJwt(r).includes('EXPIRÉ'))
  })

  test('JWT invalide → "JWT invalide"', () => {
    const r = inspectJwt('foo.bar', NOW)
    assert.equal(summariseJwt(r), 'JWT invalide')
  })

  test('un claim de type objet ne fait pas planter le récapitulatif', () => {
    const token = makeJwt({ alg: 'HS256' }, { iss: { toString: null }, sub: { toString: null } })
    assert.equal(summariseJwt(inspectJwt(token, NOW)), 'alg=HS256')
  })
})
