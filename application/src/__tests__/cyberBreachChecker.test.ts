/**
 * Tests breach checker.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  checkBreached,
  checkCredentialReuse,
  matchPwnedSuffix,
  preparePwnedRangeQuery,
} from '../services/cyber/breachChecker.ts'

describe('Breach checker', () => {
  test('"password" → breached exact', () => {
    const r = checkBreached('password')
    assert.equal(r.isBreached, true)
    assert.equal(r.transformation, 'exact')
  })

  test('"123456" → breached exact', () => {
    const r = checkBreached('123456')
    assert.equal(r.isBreached, true)
  })

  test('"P@ssw0rd" → breached via leet', () => {
    const r = checkBreached('P@ssw0rd')
    assert.equal(r.isBreached, true)
    assert.equal(r.transformation, 'leet')
  })

  test('"password123" → breached suffix', () => {
    const r = checkBreached('password123')
    assert.equal(r.isBreached, true)
    assert.equal(r.transformation, 'suffix')
  })

  test('"Password" → breached capitalized', () => {
    const r = checkBreached('Password')
    assert.equal(r.isBreached, true)
  })

  test('mot de passe fort → non breached', () => {
    const r = checkBreached('K7$mPq2!nXvR9wL@')
    assert.equal(r.isBreached, false)
  })

  test('vide → non breached', () => {
    const r = checkBreached('')
    assert.equal(r.isBreached, false)
  })

  test('recommandations FR retournées', () => {
    const r = checkBreached('password')
    assert.ok(r.recommendations.length > 0)
    assert.ok(r.recommendations.some((rec) => /2FA|gestionnaire/.test(rec)))
  })
})

describe('Credential reuse', () => {
  test('mot de passe contient username → reuse', () => {
    const r = checkCredentialReuse('juanIsCool42', 'juan')
    assert.equal(r.reused, true)
  })

  test('email split sur @', () => {
    const r = checkCredentialReuse('rabuteauPassword!', 'rabuteau@gmail.com')
    assert.equal(r.reused, true)
  })

  test('mot de passe contient identifiant inversé', () => {
    const r = checkCredentialReuse('naujCool42', 'juan')
    assert.equal(r.reused, true)
  })

  test('password indépendant → non reused', () => {
    const r = checkCredentialReuse('K7$mPq2', 'username')
    assert.equal(r.reused, false)
  })

  test('identifiant trop court → ignoré', () => {
    const r = checkCredentialReuse('mypass', 'ab')
    assert.equal(r.reused, false)
  })
})

describe('HIBP k-anonymity helpers', () => {
  test('preparePwnedRangeQuery retourne prefix 5 chars + suffix', async () => {
    const r = await preparePwnedRangeQuery('password')
    if (r) {
      assert.equal(r.prefix.length, 5)
      assert.ok(r.suffix.length > 0)
      assert.match(r.prefix, /^[0-9A-F]+$/)
    }
  })

  test('matchPwnedSuffix parse response correctement', () => {
    const hibpResponse = 'ABCDEF123:5\n012345AAAA:42\n'
    const found = matchPwnedSuffix('012345AAAA', hibpResponse)
    assert.equal(found, 42)
  })

  test('matchPwnedSuffix retourne 0 si non trouvé', () => {
    const found = matchPwnedSuffix('NOTFOUND', 'ABC:5\nDEF:10\n')
    assert.equal(found, 0)
  })

  test('matchPwnedSuffix case-insensitive', () => {
    const found = matchPwnedSuffix('abc123', 'ABC123:7\n')
    assert.equal(found, 7)
  })
})
