/**
 * Tests pour cyber/wifiHandshakeSim — PBKDF2 WPA2 + forge handshake + crack dict.
 * Utilise WebCrypto via Node 24+ qui supporte crypto.subtle natif.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  derivePMK,
  bytesToHex,
  forgeCapturedHandshake,
  crackHandshake,
  DEMO_DICTIONARY,
} from '../services/cyber/wifiHandshakeSim.ts'

describe('bytesToHex', () => {
  test('vide → ""', () => {
    assert.equal(bytesToHex(new Uint8Array()), '')
  })

  test('1 byte', () => {
    assert.equal(bytesToHex(new Uint8Array([0xff])), 'ff')
  })

  test('plusieurs bytes', () => {
    assert.equal(bytesToHex(new Uint8Array([0xde, 0xad, 0xbe, 0xef])), 'deadbeef')
  })

  test('padding sur valeurs < 16', () => {
    assert.equal(bytesToHex(new Uint8Array([0x01, 0x0a])), '010a')
  })
})

describe('derivePMK', () => {
  test('produit 32 bytes', async () => {
    const pmk = await derivePMK('motdepasse', 'AuroraSSID')
    assert.equal(pmk.length, 32)
  })

  test('déterministe (mêmes inputs → même PMK)', async () => {
    const a = await derivePMK('hello', 'TestNet')
    const b = await derivePMK('hello', 'TestNet')
    assert.deepEqual(Array.from(a), Array.from(b))
  })

  test('SSID différent → PMK différente', async () => {
    const a = await derivePMK('same', 'NetA')
    const b = await derivePMK('same', 'NetB')
    assert.notDeepEqual(Array.from(a), Array.from(b))
  })

  test('passphrase différente → PMK différente', async () => {
    const a = await derivePMK('passA', 'SSID')
    const b = await derivePMK('passB', 'SSID')
    assert.notDeepEqual(Array.from(a), Array.from(b))
  })
})

describe('forgeCapturedHandshake', () => {
  test('structure complète', async () => {
    const h = await forgeCapturedHandshake('motdepasse', 'AuroraSSID')
    assert.equal(h.ssid, 'AuroraSSID')
    assert.equal(h.pmkHash.length, 64) // 32 bytes en hex = 64 chars
    assert.match(h.apMac, /^[0-9a-f:]{17}$/)
    assert.match(h.staMac, /^[0-9a-f:]{17}$/)
    assert.equal(h.aNonce.length, 64) // 32 bytes
    assert.equal(h.sNonce.length, 64)
    assert.ok(h.capturedAt > 0)
  })

  test('même SSID → même nonces déterministes', async () => {
    const a = await forgeCapturedHandshake('passA', 'NetX')
    const b = await forgeCapturedHandshake('passB', 'NetX')
    // Nonces déterministes par SSID (pour reproductibilité demo)
    assert.equal(a.aNonce, b.aNonce)
    assert.equal(a.sNonce, b.sNonce)
    // Mais pmkHash différent car passphrase différente
    assert.notEqual(a.pmkHash, b.pmkHash)
  })
})

describe('crackHandshake', () => {
  test('passphrase dans le dictionnaire → trouvée', async () => {
    const handshake = await forgeCapturedHandshake('motdepasse', 'AuroraSSID')
    const r = await crackHandshake(handshake, ['wrong1', 'motdepasse', 'wrong2'])
    assert.equal(r.found, true)
    assert.equal(r.passphrase, 'motdepasse')
    assert.equal(r.attempts, 2) // s'arrête au trouvé
  })

  test('passphrase absente → not found', async () => {
    const handshake = await forgeCapturedHandshake('rare-pass', 'SSID')
    const r = await crackHandshake(handshake, ['wrong1', 'wrong2', 'wrong3'])
    assert.equal(r.found, false)
    assert.equal(r.passphrase, undefined)
    assert.equal(r.attempts, 3)
  })

  test('log contient toutes les tentatives jusqu au succès', async () => {
    const handshake = await forgeCapturedHandshake('right', 'SSID')
    const r = await crackHandshake(handshake, ['wrong', 'right', 'extra'])
    assert.equal(r.log.length, 2)
    assert.equal(r.log[0].matched, false)
    assert.equal(r.log[1].matched, true)
  })

  test('durationMs présent', async () => {
    const handshake = await forgeCapturedHandshake('a', 'b')
    const r = await crackHandshake(handshake, ['x'])
    assert.ok(typeof r.durationMs === 'number')
    assert.ok(r.durationMs >= 0)
  })

  test('AbortSignal stoppe le crack', async () => {
    const handshake = await forgeCapturedHandshake('hidden', 'SSID')
    const ac = new AbortController()
    ac.abort()
    const r = await crackHandshake(handshake, ['a', 'b', 'c'], { signal: ac.signal })
    assert.equal(r.attempts, 0)
    assert.equal(r.found, false)
  })

  test('onProgress callback appelé', async () => {
    const handshake = await forgeCapturedHandshake('z', 'SSID')
    const progress: number[] = []
    await crackHandshake(handshake, ['a', 'b', 'c'], {
      onProgress: (i) => { progress.push(i) },
    })
    assert.deepEqual(progress, [0, 1, 2])
  })
})

describe('DEMO_DICTIONARY', () => {
  test('contient les classiques', () => {
    assert.ok(DEMO_DICTIONARY.includes('password'))
    assert.ok(DEMO_DICTIONARY.includes('12345678'))
    assert.ok(DEMO_DICTIONARY.includes('motdepasse'))
  })

  test('taille raisonnable pour démo', () => {
    assert.ok(DEMO_DICTIONARY.length >= 15)
    assert.ok(DEMO_DICTIONARY.length <= 100)
  })
})
