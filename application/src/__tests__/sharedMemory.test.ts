/**
 * Tests pour services/sharedMemory — store en mémoire cross-module avec
 * eviction LRU + helpers spécifiques module.
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { sharedMemory } from '../services/sharedMemory.ts'

beforeEach(() => {
  sharedMemory.clear()
})

describe('sharedMemory — get / set / has / delete', () => {
  test('get sur clé absente → undefined', () => {
    assert.equal(sharedMemory.get('image_test_abc'), undefined)
  })

  test('set + get → renvoie la valeur', () => {
    sharedMemory.set('image_test_abc', { url: 'foo.png' })
    const v = sharedMemory.get<{ url: string }>('image_test_abc')
    assert.equal(v?.url, 'foo.png')
  })

  test('has true après set', () => {
    sharedMemory.set('a:b', 1)
    assert.equal(sharedMemory.has('a:b'), true)
  })

  test('delete enlève la clé', () => {
    sharedMemory.set('a:b', 1)
    assert.equal(sharedMemory.delete('a:b'), true)
    assert.equal(sharedMemory.has('a:b'), false)
  })

  test('delete d une clé absente → false', () => {
    assert.equal(sharedMemory.delete('inexistant:x'), false)
  })

  test('clear vide tout', () => {
    sharedMemory.set('a:1', 1)
    sharedMemory.set('b:2', 2)
    sharedMemory.clear()
    assert.equal(sharedMemory.size, 0)
  })
})

describe('sharedMemory — module helpers', () => {
  test('keysForModule filtre par préfixe "_" et ":"', () => {
    sharedMemory.set('image_result_a', 1)
    sharedMemory.set('image:other', 2)
    sharedMemory.set('code_result_x', 3)
    const keys = sharedMemory.keysForModule('image')
    assert.equal(keys.length, 2)
    assert.ok(keys.includes('image_result_a'))
    assert.ok(keys.includes('image:other'))
  })

  test('clearModule supprime tout le module', () => {
    sharedMemory.set('image_a_1', 1)
    sharedMemory.set('image_b_2', 2)
    sharedMemory.set('code_c_3', 3)
    sharedMemory.clearModule('image')
    assert.equal(sharedMemory.keysForModule('image').length, 0)
    assert.equal(sharedMemory.has('code_c_3'), true)
  })

  test('setModuleResult/getModuleResult — clé construite cohérente', () => {
    sharedMemory.setModuleResult('image', 'hash123', { ok: true })
    const r = sharedMemory.getModuleResult<{ ok: boolean }>('image', 'hash123')
    assert.equal(r?.ok, true)
  })

  test('setRealityAnalysis/getRealityAnalysis', () => {
    sharedMemory.setRealityAnalysis('h-1', { feasible: true })
    const a = sharedMemory.getRealityAnalysis<{ feasible: boolean }>('h-1')
    assert.equal(a?.feasible, true)
  })
})

describe('sharedMemory — LRU eviction', () => {
  test('eviction au-delà de 128 entries', () => {
    // STORE_MAX_SIZE = 128
    for (let i = 0; i < 130; i++) {
      sharedMemory.set(`m_test_${i}`, i)
    }
    assert.equal(sharedMemory.size, 128)
    // La première (0) doit avoir été évincée
    assert.equal(sharedMemory.has('m_test_0'), false)
    // Les dernières sont encore là
    assert.equal(sharedMemory.has('m_test_129'), true)
  })

  test('overwrite ne déclenche pas d eviction', () => {
    sharedMemory.set('m_test_x', 1)
    sharedMemory.set('m_test_x', 2)
    assert.equal(sharedMemory.size, 1)
    assert.equal(sharedMemory.get('m_test_x'), 2)
  })
})

describe('sharedMemory — keys & size', () => {
  test('keys retourne toutes les clés', () => {
    sharedMemory.set('a:1', 1)
    sharedMemory.set('b:2', 2)
    const k = sharedMemory.keys().sort()
    assert.deepEqual(k, ['a:1', 'b:2'])
  })

  test('size reflète le nombre d entries', () => {
    assert.equal(sharedMemory.size, 0)
    sharedMemory.set('a:1', 1)
    sharedMemory.set('b:2', 2)
    assert.equal(sharedMemory.size, 2)
  })
})
