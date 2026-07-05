/**
 * Tests pour cyber/cryptoVulnerabilities — catalogue de vulnérabilités crypto +
 * détecteur ECB blocs dupliqués + constant-time compare.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  CRYPTO_VULNERABILITIES,
  findVulnerability,
  vulnerabilitiesByCategory,
  vulnerabilitiesAtLeast,
  detectEcbDuplicateBlocks,
  constantTimeEqual,
} from '../services/cyber/cryptoVulnerabilities.ts'

describe('CRYPTO_VULNERABILITIES catalogue', () => {
  test('taille raisonnable (≥ 5)', () => {
    assert.ok(CRYPTO_VULNERABILITIES.length >= 5)
  })

  test('chaque vuln a id/title/severity/category', () => {
    for (const v of CRYPTO_VULNERABILITIES) {
      assert.ok(v.id)
      assert.ok(v.title)
      assert.ok(['info', 'low', 'medium', 'high', 'critical'].includes(v.severity))
      assert.ok(v.category)
    }
  })

  test('ids uniques', () => {
    const ids = CRYPTO_VULNERABILITIES.map((v) => v.id)
    assert.equal(new Set(ids).size, ids.length)
  })
})

describe('findVulnerability', () => {
  test('id existant → renvoie la vuln', () => {
    const first = CRYPTO_VULNERABILITIES[0]
    const r = findVulnerability(first.id)
    assert.equal(r?.id, first.id)
  })

  test('id inconnu → undefined', () => {
    assert.equal(findVulnerability('nonexistent-vuln-id-xxx'), undefined)
  })
})

describe('vulnerabilitiesByCategory', () => {
  test('filtre par catégorie', () => {
    const sample = CRYPTO_VULNERABILITIES[0].category
    const r = vulnerabilitiesByCategory(sample)
    assert.ok(r.length >= 1)
    assert.ok(r.every((v) => v.category === sample))
  })
})

describe('vulnerabilitiesAtLeast', () => {
  test('critical → renvoie uniquement critical', () => {
    const r = vulnerabilitiesAtLeast('critical')
    assert.ok(r.every((v) => v.severity === 'critical'))
  })

  test('low → renvoie low + medium + high + critical', () => {
    const r = vulnerabilitiesAtLeast('low')
    assert.ok(r.every((v) => ['low', 'medium', 'high', 'critical'].includes(v.severity)))
    // Aucun "info"
    assert.ok(r.every((v) => v.severity !== 'info'))
  })

  test('info → tous', () => {
    const r = vulnerabilitiesAtLeast('info')
    assert.equal(r.length, CRYPTO_VULNERABILITIES.length)
  })
})

describe('detectEcbDuplicateBlocks', () => {
  test('2 blocs identiques de 16 bytes (32 hex chars) → duplicate', () => {
    const block = 'a'.repeat(32)
    const cipher = block + block
    const r = detectEcbDuplicateBlocks(cipher)
    assert.equal(r.hasDuplicates, true)
    assert.equal(r.duplicateBlocks, 1)
  })

  test('blocs uniques → pas de duplicate', () => {
    const cipher = 'a'.repeat(32) + 'b'.repeat(32) + 'c'.repeat(32)
    const r = detectEcbDuplicateBlocks(cipher)
    assert.equal(r.hasDuplicates, false)
    assert.equal(r.duplicateBlocks, 0)
  })

  test('3 blocs identiques → 2 duplicates', () => {
    const block = 'a'.repeat(32)
    const r = detectEcbDuplicateBlocks(block + block + block)
    assert.equal(r.duplicateBlocks, 2)
  })

  test('longueur non alignée sur 16 bytes → false', () => {
    const r = detectEcbDuplicateBlocks('aabbcc')
    assert.equal(r.hasDuplicates, false)
  })

  test('whitespace stripped', () => {
    const block = 'a'.repeat(32)
    const r = detectEcbDuplicateBlocks(`${block}  ${block}  `)
    assert.equal(r.hasDuplicates, true)
  })

  test('blockSize 8 bytes (16 hex) → custom block size', () => {
    const r = detectEcbDuplicateBlocks('aabbccdd' + 'aabbccdd' + 'aabbccdd', 4)
    assert.equal(r.hasDuplicates, true)
  })
})

describe('constantTimeEqual', () => {
  test('strings identiques → true', () => {
    assert.equal(constantTimeEqual('hello', 'hello'), true)
  })

  test('strings différentes même longueur → false', () => {
    assert.equal(constantTimeEqual('hello', 'world'), false)
  })

  test('longueurs différentes → false', () => {
    assert.equal(constantTimeEqual('a', 'ab'), false)
    assert.equal(constantTimeEqual('hello', 'hellooo'), false)
  })

  test('vides → true', () => {
    assert.equal(constantTimeEqual('', ''), true)
  })

  test('un vide + un non-vide → false', () => {
    assert.equal(constantTimeEqual('', 'a'), false)
    assert.equal(constantTimeEqual('b', ''), false)
  })

  test('unicode supporté', () => {
    assert.equal(constantTimeEqual('café', 'café'), true)
    assert.equal(constantTimeEqual('café', 'cafe'), false)
  })
})
