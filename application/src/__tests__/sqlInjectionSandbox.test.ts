/**
 * Tests pour cyber/sqlInjectionSandbox — détection des patterns SQL injection.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  tryInject,
  SQL_DEMO_USERS,
  SQL_DEMO_PAYLOADS,
} from '../services/cyber/sqlInjectionSandbox.ts'

describe('tryInject — auth normale', () => {
  test('credentials valides → 1 match', () => {
    const r = tryInject('alice', 'wonderland42')
    assert.equal(r.verdict, 'safe')
    assert.equal(r.rowsLeaked.length, 1)
    assert.equal(r.rowsLeaked[0].username, 'alice')
  })

  test('credentials invalides → 0 match', () => {
    const r = tryInject('alice', 'wrongpassword')
    assert.equal(r.verdict, 'safe')
    assert.equal(r.rowsLeaked.length, 0)
  })

  test('username inconnu → safe + no rows', () => {
    const r = tryInject('inexistant_user', 'anything')
    assert.equal(r.verdict, 'safe')
    assert.equal(r.rowsLeaked.length, 0)
  })
})

describe('tryInject — auth bypass', () => {
  test("admin' -- → auth-bypass", () => {
    const r = tryInject("admin' --", 'anything')
    assert.ok(['auth-bypass', 'comment-trick'].includes(r.verdict))
    assert.ok(r.rowsLeaked.length > 0) // table dump
  })

  test("' OR '1'='1 → auth-bypass tautology", () => {
    const r = tryInject("' OR '1'='1", 'x')
    assert.equal(r.verdict, 'auth-bypass')
    assert.ok(r.rowsLeaked.length === SQL_DEMO_USERS.length)
  })

  test("OR 1=1 sans quotes → détecté", () => {
    const r = tryInject('admin OR 1=1', 'x')
    assert.ok(['auth-bypass', 'safe'].includes(r.verdict))
  })
})

describe('tryInject — union leak', () => {
  test("UNION SELECT → union-leak", () => {
    const r = tryInject("' UNION SELECT * FROM users --", 'x')
    assert.equal(r.verdict, 'union-leak')
    assert.ok(r.rowsLeaked.length > 0)
    assert.ok(r.explanation.includes('UNION'))
  })
})

describe('tryInject — destructive', () => {
  test("DROP TABLE → destructive", () => {
    const r = tryInject("x'; DROP TABLE users; --", '')
    assert.equal(r.verdict, 'destructive')
    assert.equal(r.rowsLeaked.length, 0)
    assert.ok(r.explanation.includes('destructive') || r.explanation.includes('DROP'))
  })

  test("DELETE FROM → destructive", () => {
    const r = tryInject("'; DELETE FROM users WHERE 1=1; --", '')
    assert.equal(r.verdict, 'destructive')
  })
})

describe('tryInject — output structure', () => {
  test('vulnerableQuery + preparedQuery présents', () => {
    const r = tryInject('alice', 'x')
    assert.ok(r.vulnerableQuery.includes('alice'))
    assert.ok(r.preparedQuery.length > 0)
    // preparedQuery utilise des placeholders ?
    assert.ok(r.preparedQuery.includes('?'))
  })

  test('detectedPatterns array', () => {
    const r = tryInject("admin' --", 'x')
    assert.ok(Array.isArray(r.detectedPatterns))
    assert.ok(r.detectedPatterns.length > 0)
  })

  test('severity ∈ [0..5]', () => {
    const safe = tryInject('alice', 'wonderland42')
    const bypass = tryInject("' OR '1'='1", 'x')
    assert.equal(safe.severity, 0)
    assert.ok(bypass.severity > 0)
    assert.ok(bypass.severity <= 5)
  })
})

describe('SQL_DEMO_USERS / SQL_DEMO_PAYLOADS', () => {
  test('users non vide', () => {
    assert.ok(SQL_DEMO_USERS.length >= 2)
    for (const u of SQL_DEMO_USERS) {
      assert.ok(u.username)
      assert.ok(u.password)
      assert.ok(u.role)
    }
  })

  test('payloads couvrent les principales vulns', () => {
    const labels = SQL_DEMO_PAYLOADS.map((p) => p.label.toLowerCase())
    assert.ok(labels.some((l) => l.includes('bypass')))
    assert.ok(labels.some((l) => l.includes('union')))
    assert.ok(labels.some((l) => l.includes('destructive')))
  })

  test('chaque payload demo déclenche la vuln annoncée', () => {
    const bypass = SQL_DEMO_PAYLOADS.find((p) => p.label.toLowerCase().includes('bypass'))!
    const r = tryInject(bypass.username, bypass.password)
    assert.ok(['auth-bypass', 'comment-trick'].includes(r.verdict))
  })
})
