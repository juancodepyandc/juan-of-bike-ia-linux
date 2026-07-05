/**
 * Tests pour cyber/tlsCertInspector — surface PEM validation + edge cases.
 * Le parsing ASN.1/DER nécessite des vrais certificats binaires, donc
 * on focus sur les paths d'erreur et le format PEM.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { inspectCertificate } from '../services/cyber/tlsCertInspector.ts'

describe('inspectCertificate — edge cases d entrée', () => {
  test('chaîne vide → "Aucun bloc PEM" + verdict unknown', () => {
    const r = inspectCertificate('')
    assert.equal(r.pemBlocks, 0)
    assert.equal(r.verdict, 'unknown')
    assert.ok(r.issues.some((i) => i.severity === 'critical' && i.message.includes('PEM')))
  })

  test('texte non-PEM → "Aucun bloc PEM"', () => {
    const r = inspectCertificate('just random text without any PEM header')
    assert.equal(r.pemBlocks, 0)
    assert.equal(r.verdict, 'unknown')
  })

  test('PEM avec contenu base64 invalide → "Décodage échoué"', () => {
    const fake = '-----BEGIN CERTIFICATE-----\n!!!not-base64!!!\n-----END CERTIFICATE-----'
    const r = inspectCertificate(fake)
    // soit décodage échoue, soit le parse renvoie unknown
    assert.ok(r.verdict === 'unknown' || r.issues.length > 0)
  })

  test('structure CertReport complète sur entrée vide', () => {
    const r = inspectCertificate('')
    assert.equal(typeof r.pemBlocks, 'number')
    assert.ok(Array.isArray(r.subjectAltNames))
    assert.ok(Array.isArray(r.issues))
    assert.ok(typeof r.verdict === 'string')
  })

  test('PEM minimal valide (mais bytes non-cert) → ne crash pas', () => {
    // Vrais bytes base64 mais pas un certif valide
    const pem = '-----BEGIN CERTIFICATE-----\nMIIBkTCB+wIBADBSMQs=\n-----END CERTIFICATE-----'
    const r = inspectCertificate(pem)
    assert.equal(r.pemBlocks, 1)
    // Le parser peut renvoyer null partout mais ne doit pas crasher
    assert.ok(r)
  })

  test('plusieurs blocs PEM → pemBlocks compte correctement', () => {
    const pem = `-----BEGIN CERTIFICATE-----
MIIBkTCB+wIBADBSMQs=
-----END CERTIFICATE-----
-----BEGIN CERTIFICATE-----
MIICAjCCAWuCAQAw=
-----END CERTIFICATE-----`
    const r = inspectCertificate(pem)
    assert.equal(r.pemBlocks, 2)
  })

  test('hoursUntilExpire null si pas de notAfter parsé', () => {
    const r = inspectCertificate('')
    assert.equal(r.hoursUntilExpire, null)
  })

  test('subjectAltNames toujours array (default empty)', () => {
    const r = inspectCertificate('')
    assert.deepEqual(r.subjectAltNames, [])
  })

  test('chaîne whitespace seule → 0 blocs', () => {
    assert.equal(inspectCertificate('   \n\t  ').pemBlocks, 0)
  })

  test('verdict in enum CertVerdict', () => {
    const r = inspectCertificate('')
    const validVerdicts = ['recommended', 'acceptable', 'expiring-soon', 'expired', 'weak-algo', 'self-signed', 'unknown']
    assert.ok(validVerdicts.includes(r.verdict))
  })
})

describe('inspectCertificate — issues structure', () => {
  test('chaque issue a severity + message', () => {
    const r = inspectCertificate('')
    for (const i of r.issues) {
      assert.ok(['info', 'warn', 'critical'].includes(i.severity))
      assert.ok(typeof i.message === 'string')
      assert.ok(i.message.length > 0)
    }
  })

  test('PEM partial sans END → 0 blocs', () => {
    const partial = '-----BEGIN CERTIFICATE-----\nMIIB+wIBADBSMQs=\n'
    const r = inspectCertificate(partial)
    assert.equal(r.pemBlocks, 0)
  })
})
