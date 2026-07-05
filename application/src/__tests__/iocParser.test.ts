/**
 * Tests pour cyber/iocParser — extraction Indicators of Compromise.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { parseIocs, summariseIocs } from '../services/cyber/iocParser.ts'

describe('parseIocs — IPs', () => {
  test('IPv4 publique', () => {
    const iocs = parseIocs('Connexion depuis 185.220.101.42')
    const ip = iocs.find(i => i.kind === 'ipv4')
    assert.ok(ip)
    assert.equal(ip?.value, '185.220.101.42')
    assert.ok(ip?.tags.includes('public'))
  })

  test('IPv4 privée tagguée', () => {
    const iocs = parseIocs('Cible interne 192.168.1.50')
    const ip = iocs.find(i => i.kind === 'ipv4' && i.value === '192.168.1.50')
    assert.ok(ip?.tags.includes('private'))
  })

  test('IPv4 loopback 127.x → private', () => {
    const iocs = parseIocs('local 127.0.0.1')
    const ip = iocs.find(i => i.kind === 'ipv4' && i.value === '127.0.0.1')
    assert.ok(ip?.tags.includes('private'))
  })

  test('multiple IPs', () => {
    const iocs = parseIocs('C2 45.155.205.233 et backup 91.92.93.94')
    const ips = iocs.filter(i => i.kind === 'ipv4')
    assert.equal(ips.length, 2)
  })
})

describe('parseIocs — hashes', () => {
  test('SHA-256 détecté', () => {
    const sha = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    const iocs = parseIocs(`Payload hash: ${sha}`)
    const h = iocs.find(i => i.kind === 'sha256')
    assert.ok(h)
    assert.equal(h?.value.toLowerCase(), sha)
  })

  test('MD5 détecté', () => {
    const md5 = '9e107d9d372bb6826bd81d3542a419d6'
    const iocs = parseIocs(`MD5 dropper: ${md5}`)
    const h = iocs.find(i => i.kind === 'md5')
    assert.ok(h)
  })

  test('SHA-1 détecté', () => {
    const sha1 = 'a94a8fef8c0d61d2cb6b3d40b3d3ad3ff3ec0a9c'
    const iocs = parseIocs(`Hash SHA1: ${sha1}`)
    const h = iocs.find(i => i.kind === 'sha1')
    assert.ok(h)
  })
})

describe('parseIocs — CVE / MITRE', () => {
  test('CVE moderne', () => {
    const iocs = parseIocs('Référence à CVE-2024-1234.')
    const cve = iocs.find(i => i.kind === 'cve')
    assert.equal(cve?.value, 'CVE-2024-1234')
  })

  test('CVE 2024 → tag "recent"', () => {
    const iocs = parseIocs('Exploite CVE-2025-0001')
    const cve = iocs.find(i => i.kind === 'cve' && i.value === 'CVE-2025-0001')
    assert.ok(cve?.tags.includes('recent'))
  })

  test('MITRE technique avec sub-technique', () => {
    const iocs = parseIocs('Technique T1566.001 utilisée')
    const m = iocs.find(i => i.kind === 'mitre')
    assert.equal(m?.value, 'T1566.001')
  })

  test('MITRE technique sans sub', () => {
    const iocs = parseIocs('TA-T1059 PowerShell')
    const m = iocs.find(i => i.kind === 'mitre')
    assert.equal(m?.value, 'T1059')
  })
})

describe('parseIocs — URLs / domaines / emails', () => {
  test('URL http extracté + tag cleartext', () => {
    const iocs = parseIocs('Visite http://malicious-c2.xyz/login')
    const url = iocs.find(i => i.kind === 'url')
    assert.ok(url)
    assert.ok(url?.tags.includes('http-cleartext'))
  })

  test('URL avec IP comme host → ip-as-host', () => {
    const iocs = parseIocs('http://185.220.101.42/login.php')
    const url = iocs.find(i => i.kind === 'url')
    assert.ok(url?.tags.includes('ip-as-host'))
  })

  test('TLD suspect .tk', () => {
    const iocs = parseIocs('Domaine suspect aurora-secure-update.tk')
    const dom = iocs.find(i => i.kind === 'domain')
    assert.ok(dom)
    assert.ok(dom?.tags.some(t => t.includes('tld-suspect')))
  })

  test('Email détecté', () => {
    const iocs = parseIocs('Source : billing@aurora-secure-update.tk')
    const e = iocs.find(i => i.kind === 'email')
    assert.equal(e?.value, 'billing@aurora-secure-update.tk')
  })
})

describe('parseIocs — BTC', () => {
  test('Bitcoin address classique (1...)', () => {
    const iocs = parseIocs('Paie : 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
    const btc = iocs.find(i => i.kind === 'btc')
    assert.ok(btc)
  })
})

describe('parseIocs — déduplication & ordre', () => {
  test('Même IP deux fois → un seul IOC', () => {
    const iocs = parseIocs('192.168.1.1 et 192.168.1.1')
    const ips = iocs.filter(i => i.kind === 'ipv4')
    assert.equal(ips.length, 1)
  })

  test('Trié par position dans le texte source', () => {
    const txt = 'Premier 8.8.8.8 puis CVE-2024-1234 enfin email@x.com'
    const iocs = parseIocs(txt)
    for (let i = 1; i < iocs.length; i++) {
      assert.ok(iocs[i].start >= iocs[i - 1].start)
    }
  })

  test('Texte vide → tableau vide', () => {
    assert.deepEqual(parseIocs(''), [])
  })
})

describe('summariseIocs', () => {
  test('compte par kind', () => {
    // CVE regex demande \d{4,7} après l'année, donc les vrais formats CVE-YYYY-NNNN+.
    const iocs = parseIocs('8.8.8.8 et 1.1.1.1 + CVE-2024-1234 + CVE-2024-5678 + foo@bar.com')
    const summary = summariseIocs(iocs)
    assert.equal(summary.ipv4, 2)
    assert.equal(summary.cve, 2)
    assert.equal(summary.email, 1)
  })

  test('tableau vide → objet vide', () => {
    assert.deepEqual(summariseIocs([]), {})
  })
})
