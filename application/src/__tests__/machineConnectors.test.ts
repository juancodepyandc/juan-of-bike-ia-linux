/**
 * Tests pour services/machineConnectors — pure helpers (platformHintForLLM,
 * remoteContextBlock). Les API SSH/fetch sont testées via mock.
 */
import { test, describe, before, after } from 'node:test'
import assert from 'node:assert/strict'
import {
  platformHintForLLM,
  remoteContextBlock,
  listTargets,
  saveTarget,
  deleteTarget,
  keygen,
  tcpProbe,
  type MachineTarget,
} from '../services/machineConnectors.ts'

const realFetch = globalThis.fetch
let fetchMock: ((url: any, init?: any) => Promise<any>) | null = null

before(() => {
  globalThis.fetch = ((url: any, init?: any) => {
    if (fetchMock) return fetchMock(url, init)
    return Promise.reject(new Error('no mock'))
  }) as any
  // btoa polyfill if absent
  if (typeof globalThis.btoa !== 'function') {
    globalThis.btoa = (s: string) => Buffer.from(s, 'binary').toString('base64')
  }
})

after(() => {
  globalThis.fetch = realFetch
})

function mockJson(body: unknown) {
  fetchMock = async () => ({ ok: true, json: async () => body })
}

describe('platformHintForLLM — par platform', () => {
  function target(over: Partial<MachineTarget> = {}): MachineTarget {
    return { name: 'pi', host: '192.168.1.1', user: 'pi', ...over }
  }

  test('raspberry_pi → mention RPi.GPIO', () => {
    const r = platformHintForLLM(target({ platform: 'raspberry_pi' }))
    assert.ok(r.includes('Raspberry') || r.includes('RPi'))
    assert.ok(r.includes('ARM'))
  })

  test('linux_x86 → Linux x86_64', () => {
    const r = platformHintForLLM(target({ platform: 'linux_x86' }))
    assert.ok(r.includes('x86_64'))
  })

  test('linux_arm → Linux ARM', () => {
    const r = platformHintForLLM(target({ platform: 'linux_arm' }))
    assert.ok(r.includes('ARM'))
  })

  test('linux_wsl → mention WSL', () => {
    const r = platformHintForLLM(target({ platform: 'linux_wsl' }))
    assert.ok(r.includes('WSL'))
  })

  test('macos → mention BSD/Homebrew', () => {
    const r = platformHintForLLM(target({ platform: 'macos' }))
    assert.ok(r.toLowerCase().includes('macos') || r.includes('BSD') || r.includes('Homebrew'))
  })

  test('unknown → fallback portable', () => {
    const r = platformHintForLLM(target({ platform: 'unknown' }))
    assert.ok(r.toLowerCase().includes('portable') || r.length > 0)
  })

  test('platform_hints custom → utilisé en priorité', () => {
    const r = platformHintForLLM(target({ platform: 'raspberry_pi', platform_hints: 'custom hint X' }))
    assert.ok(r.includes('custom hint X'))
  })

  test('platform absent → fallback', () => {
    const r = platformHintForLLM(target())
    assert.ok(r.length > 0)
  })
})

describe('remoteContextBlock', () => {
  test('target null → ""', () => {
    assert.equal(remoteContextBlock(null), '')
  })

  test('target avec name/host/user → bloc structuré', () => {
    const r = remoteContextBlock({ name: 'pi', host: '192.168.1.1', user: 'pi' })
    assert.ok(r.includes('Remote target: pi'))
    assert.ok(r.includes('pi@192.168.1.1'))
  })

  test('port par défaut 22 si non spécifié', () => {
    const r = remoteContextBlock({ name: 'pi', host: '1.1.1.1', user: 'root' })
    assert.ok(r.includes(':22'))
  })

  test('port custom respecté', () => {
    const r = remoteContextBlock({ name: 'pi', host: '1.1.1.1', user: 'root', port: 2222 })
    assert.ok(r.includes(':2222'))
  })

  test('deploy_path custom respecté', () => {
    const r = remoteContextBlock({ name: 'x', host: 'h', user: 'u', deploy_path: '/srv/app' })
    assert.ok(r.includes('/srv/app'))
  })

  test('deploy_path par défaut ~ user', () => {
    const r = remoteContextBlock({ name: 'x', host: 'h', user: 'juan' })
    assert.ok(r.includes('juan/aurora_deploys'))
  })

  test('preview_url_base inclus si défini', () => {
    const r = remoteContextBlock({ name: 'x', host: 'h', user: 'u', preview_url_base: 'http://h:3000' })
    assert.ok(r.includes('http://h:3000'))
  })

  test('preview_url_base absent → ligne omise', () => {
    const r = remoteContextBlock({ name: 'x', host: 'h', user: 'u' })
    assert.ok(!r.includes('preview at'))
  })

  test('mention "Code/output you generate"', () => {
    const r = remoteContextBlock({ name: 'x', host: 'h', user: 'u' })
    assert.ok(r.includes('uploaded') || r.includes('Code/output'))
  })
})

describe('listTargets', () => {
  test('réponse ok → renvoie targets[]', async () => {
    mockJson({ ok: true, targets: [{ name: 't1', host: 'h', user: 'u' }] })
    const r = await listTargets()
    assert.equal(r.length, 1)
    assert.equal(r[0].name, 't1')
  })

  test('réponse ok=false → []', async () => {
    mockJson({ ok: false, targets: [] })
    const r = await listTargets()
    assert.deepEqual(r, [])
  })
})

describe('saveTarget / deleteTarget / keygen / tcpProbe', () => {
  test('saveTarget renvoie le target', async () => {
    mockJson({ ok: true, name: 'saved' })
    const r = await saveTarget({ name: 'x', host: 'h', user: 'u' })
    assert.ok(r)
  })

  test('deleteTarget renvoie { ok }', async () => {
    mockJson({ ok: true })
    const r = await deleteTarget('x')
    assert.equal(r.ok, true)
  })

  test('keygen renvoie public_key + instructions', async () => {
    mockJson({ ok: true, private_key_path: '/x/.ssh/id_ed25519', public_key: 'ssh-ed25519 AAAA...', instructions: 'paste here' })
    const r = await keygen()
    assert.equal(r.ok, true)
    assert.ok(r.public_key?.startsWith('ssh-ed25519'))
  })

  test('tcpProbe renvoie rtt', async () => {
    mockJson({ ok: true, rtt_ms: 23 })
    const r = await tcpProbe('1.1.1.1', 22)
    assert.equal(r.ok, true)
    assert.equal(r.rtt_ms, 23)
  })
})
