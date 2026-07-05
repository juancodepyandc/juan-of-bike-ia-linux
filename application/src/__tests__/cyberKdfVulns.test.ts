/**
 * Tests for KDF cost analyzer + crypto vulnerability catalog.
 * Run: node --experimental-strip-types --test src/__tests__/cyberKdfVulns.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  assessKdf,
  attackCost,
  compareKdf,
  formatUsd,
  OWASP_2024_DEFAULTS,
} from '../services/cyber/kdfCostAnalyzer.ts'
import {
  CRYPTO_VULNERABILITIES,
  constantTimeEqual,
  detectEcbDuplicateBlocks,
  findVulnerability,
  vulnerabilitiesAtLeast,
  vulnerabilitiesByCategory,
} from '../services/cyber/cryptoVulnerabilities.ts'

describe('KDF cost analyzer', () => {
  test('sha256 is banned, argon2id is recommended', () => {
    assert.equal(assessKdf({ algorithm: 'sha256' }).recommendation, 'banned')
    assert.equal(assessKdf(OWASP_2024_DEFAULTS.argon2id).recommendation, 'recommended')
  })

  test('argon2id ralentit l\'attaquant > 1e6× vs sha256 nu', () => {
    const cmp = compareKdf({ algorithm: 'sha256' }, OWASP_2024_DEFAULTS.argon2id)
    assert.ok(cmp.attackerSpeedRatio > 1e6, `ratio ${cmp.attackerSpeedRatio}`)
  })

  test('higher bcrypt cost → slower attacker', () => {
    const fast = assessKdf({ algorithm: 'bcrypt', bcryptCost: 8 })
    const slow = assessKdf({ algorithm: 'bcrypt', bcryptCost: 14 })
    assert.ok(slow.hashesPerSecondAttacker < fast.hashesPerSecondAttacker)
  })

  test('attackCost grows exponentially with length', () => {
    const speed = 1e10
    const c8 = attackCost(speed, 26, 8)
    const c10 = attackCost(speed, 26, 10)
    assert.ok(c10 / c8 > 100) // 26^2 ≈ 676
  })

  test('formatUsd handles 0 to trillions', () => {
    assert.equal(formatUsd(0), '< 1¢')
    assert.equal(formatUsd(0.005), '< 1¢')
    assert.equal(formatUsd(0.5), '50.0¢')
    assert.equal(formatUsd(42), '$42.00')
    assert.equal(formatUsd(5e3), '$5.0k')
    assert.equal(formatUsd(2e7), '$20.0M')
    assert.ok(formatUsd(1e15).startsWith('$1.0e'))
  })

  test('compareKdf verdict mentions winning algorithm', () => {
    const cmp = compareKdf({ algorithm: 'md5' }, OWASP_2024_DEFAULTS.argon2id)
    assert.ok(cmp.verdict.includes('argon2id'))
  })

  test('pbkdf2 attacker speed inversely related to iterations', () => {
    const low = assessKdf({ algorithm: 'pbkdf2-sha256', iterations: 1000 })
    const high = assessKdf({ algorithm: 'pbkdf2-sha256', iterations: 600_000 })
    assert.ok(high.hashesPerSecondAttacker < low.hashesPerSecondAttacker)
  })
})

describe('Crypto vulnerability catalog', () => {
  test('catalog has critical entries', () => {
    const critical = vulnerabilitiesAtLeast('critical')
    assert.ok(critical.length >= 3)
  })

  test('findVulnerability by id', () => {
    const v = findVulnerability('aes-ecb-pattern-leak')
    assert.ok(v)
    assert.equal(v.severity, 'high')
  })

  test('vulnerabilities by category', () => {
    const reuses = vulnerabilitiesByCategory('reuse')
    assert.ok(reuses.length >= 1)
    assert.ok(reuses.every((v) => v.category === 'reuse'))
  })

  test('every vuln has remediation + references', () => {
    for (const v of CRYPTO_VULNERABILITIES) {
      assert.ok(v.remediation.length > 10, `${v.id} remediation trop court`)
      assert.ok(v.references.length > 0, `${v.id} aucune référence`)
    }
  })
})

describe('ECB duplicate block detector', () => {
  test('detects identical 16-byte blocks', () => {
    const block = '00112233445566778899aabbccddeeff'
    const cipher = block + block + 'ffeeddccbbaa99887766554433221100'
    const res = detectEcbDuplicateBlocks(cipher, 16)
    assert.equal(res.hasDuplicates, true)
    assert.equal(res.duplicateBlocks, 1)
  })

  test('no duplicates returns clean', () => {
    const cipher = '00112233445566778899aabbccddeeffffeeddccbbaa99887766554433221100'
    assert.equal(detectEcbDuplicateBlocks(cipher, 16).hasDuplicates, false)
  })

  test('odd length returns no duplicates', () => {
    assert.equal(detectEcbDuplicateBlocks('abc', 16).hasDuplicates, false)
  })
})

import {
  auditHash,
  parseArgon2,
  parseBcrypt,
  parseScrypt,
} from '../services/cyber/hashParameterParser.ts'

describe('Hash parameter parser — barre expert', () => {
  test('parse Argon2id OWASP (m=65536, t=3, p=1)', () => {
    const hash = '$argon2id$v=19$m=65536,t=3,p=1$c2FsdHk$ZGlnZXN0'
    const p = parseArgon2(hash)
    assert.ok(p)
    assert.equal(p.variant, 'id')
    assert.equal(p.memoryKib, 65536)
    assert.equal(p.timeCost, 3)
    assert.equal(p.parallelism, 1)
  })

  test('parse Argon2i avec memoryKib custom', () => {
    const hash = '$argon2i$v=19$m=4096,t=2,p=1$abc$def'
    const p = parseArgon2(hash)
    assert.equal(p?.variant, 'i')
    assert.equal(p?.memoryKib, 4096)
  })

  test('parseArgon2 retourne null sur format invalide', () => {
    assert.equal(parseArgon2('not-a-hash'), null)
    assert.equal(parseArgon2('$argon2id$incomplete'), null)
  })

  test('parse bcrypt $2b$12$', () => {
    const hash = '$2b$12$EXRkfkdmXn2gzds2SSitu.MW9.gAVqa9eLS1//RYtYCmB1eLHg.9q'
    const p = parseBcrypt(hash)
    assert.ok(p)
    assert.equal(p.variant, '2b')
    assert.equal(p.cost, 12)
  })

  test('parse bcrypt cost variable', () => {
    const hash = '$2a$08$EXRkfkdmXn2gzds2SSitu.MW9.gAVqa9eLS1//RYtYCmB1eLHg.9q'
    const p = parseBcrypt(hash)
    assert.equal(p?.cost, 8)
    assert.equal(p?.variant, '2a')
  })

  test('parse scrypt PHC format', () => {
    const hash = '$scrypt$N=131072,r=8,p=1$abc$def'
    const p = parseScrypt(hash)
    assert.equal(p?.N, 131072)
    assert.equal(p?.r, 8)
    assert.equal(p?.p, 1)
  })

  test('audit Argon2id OWASP-conforme → recommended', () => {
    const r = auditHash('$argon2id$v=19$m=65536,t=3,p=1$abc$def')
    assert.equal(r.verdict, 'recommended')
    assert.equal(r.algorithm, 'argon2id')
  })

  test('audit Argon2id sous-paramétré (m=4096) → undersized', () => {
    const r = auditHash('$argon2id$v=19$m=4096,t=1,p=1$abc$def')
    assert.equal(r.verdict, 'undersized')
    assert.ok(r.recommendations.some((rec) => /memoire|memory|mémoire/i.test(rec)))
  })

  test('audit Argon2i suggère migrer vers id', () => {
    const r = auditHash('$argon2i$v=19$m=65536,t=3,p=1$abc$def')
    assert.ok(r.recommendations.some((rec) => /argon2id/.test(rec)))
  })

  test('audit bcrypt cost=8 → undersized', () => {
    const r = auditHash('$2b$08$EXRkfkdmXn2gzds2SSitu.MW9.gAVqa9eLS1//RYtYCmB1eLHg.9q')
    assert.equal(r.verdict, 'undersized')
  })

  test('audit bcrypt cost=12 modern → acceptable', () => {
    const r = auditHash('$2b$12$EXRkfkdmXn2gzds2SSitu.MW9.gAVqa9eLS1//RYtYCmB1eLHg.9q')
    assert.equal(r.verdict, 'acceptable')
  })

  test('audit SHA-256 nu (64 hex) → banned', () => {
    const r = auditHash('a'.repeat(64))
    assert.equal(r.verdict, 'banned')
  })

  test('audit MD5 nu (32 hex) → banned', () => {
    const r = auditHash('a'.repeat(32))
    assert.equal(r.verdict, 'banned')
  })

  test('audit format inconnu → banned avec recommandation', () => {
    const r = auditHash('not-a-recognised-hash')
    assert.equal(r.verdict, 'banned')
    assert.ok(r.recommendations.length > 0)
  })
})

describe('Constant-time compare', () => {
  test('true on equal strings', () => {
    assert.equal(constantTimeEqual('aurora', 'aurora'), true)
  })

  test('false on different content', () => {
    assert.equal(constantTimeEqual('aurora', 'aurorb'), false)
  })

  test('false on different length', () => {
    assert.equal(constantTimeEqual('aurora', 'aurora-'), false)
  })

  test('empty strings equal', () => {
    assert.equal(constantTimeEqual('', ''), true)
  })
})
