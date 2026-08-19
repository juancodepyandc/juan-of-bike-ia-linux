import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatSecurityReport,
  formatSigmaFile,
  formatYaraFile,
} from '../services/cyber/cyberOutputManager.ts'
import {
  auditWebEndpoint,
  RECOMMENDED_SECURITY_HEADERS,
} from '../services/cyber/webEndpointAuditor.ts'

describe('CyberOutputManager', () => {
  test('formatSigmaFile produit un payload avec nom de fichier et YAML valides', () => {
    const p = formatSigmaFile('Detect Port Scan Burst', 'title: Port Scan\nlevel: medium')
    assert.equal(p.category, 'rules')
    assert.ok(p.filename.startsWith('sigma_detect_port_scan_burst_'))
    assert.ok(p.filename.endsWith('.yml'))
    assert.equal(p.format, 'yaml')
    assert.ok(p.content.includes('title: Port Scan'))
  })

  test('formatYaraFile produit un payload avec extension .yar', () => {
    const p = formatYaraFile('UAF Shellcode Stub', 'rule UAF_Stub { condition: true }')
    assert.equal(p.category, 'rules')
    assert.ok(p.filename.startsWith('yara_uaf_shellcode_stub_'))
    assert.ok(p.filename.endsWith('.yar'))
    assert.equal(p.format, 'yara')
  })

  test('formatSecurityReport génère un rapport markdown structuré avec métadonnées', () => {
    const p = formatSecurityReport(
      'https://site-rep.vercel.app',
      'Synthèse de l audit de sécurité.',
      [{ title: 'En-têtes HTTP', body: 'Tous les en-têtes sont vérifiés.' }],
    )
    assert.equal(p.category, 'reports')
    assert.equal(p.format, 'markdown')
    assert.ok(p.content.includes('# Rapport d\'Audit & Recommandations'))
    assert.ok(p.content.includes('https://site-rep.vercel.app'))
  })
})

describe('WebEndpointAuditor', () => {
  test('auditWebEndpoint évalue les en-têtes et calcule un score cohérent', () => {
    const result = auditWebEndpoint('https://site-rep.vercel.app', {
      'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
      'X-Content-Type-Options': 'nosniff',
    })

    assert.equal(result.targetUrl, 'https://site-rep.vercel.app')
    assert.ok(result.securityScore >= 10 && result.securityScore <= 100)
    assert.ok(result.dosResilienceScore >= 50, 'Résilience DoS calculée')
    assert.ok(result.headersAnalysis.length === Object.keys(RECOMMENDED_SECURITY_HEADERS).length)
    assert.ok(result.recommendedHardening.vercelJsonConfig.includes('Content-Security-Policy'))
    assert.ok(result.recommendedHardening.nextConfigJs.includes('securityHeaders'))
    assert.ok(result.recommendedHardening.middlewareRateLimit.includes('middleware'))
    assert.ok(result.exportPayload.content.length > 50, 'Rapport d audit généré dans l export payload')
  })
})
