// TLS Certificate inspector — parse les éléments lisibles d'un certificat
// PEM et émet un verdict de sécurité (algo, expiration, SAN, issuer chain).
//
// Approche : on n'utilise PAS de lib lourde — on parse minimalement le PEM
// pour extraire les champs ASN.1 lisibles via regex + base64 décodage. Pour
// les détails complets (signature verify, vérification chaîne complète),
// nécessite un backend ; ce module donne le verdict côté UI pour pédagogie.

export type CertVerdict = 'recommended' | 'acceptable' | 'expiring-soon' | 'expired' | 'weak-algo' | 'self-signed' | 'unknown'

export type CertReport = {
  /** PEM blocs détectés. */
  pemBlocks: number
  /** Pour le premier certificat : champs extraits. */
  subject: string | null
  issuer: string | null
  serial: string | null
  /** Format ISO. */
  notBefore: string | null
  notAfter: string | null
  /** Hours until expiration (negative if expired). */
  hoursUntilExpire: number | null
  /** Algorithmes détectés via signature. */
  signatureAlgorithm: string | null
  /** Subject Alternative Names extraits du raw. */
  subjectAltNames: string[]
  /** Issues identifiées. */
  issues: Array<{ severity: 'info' | 'warn' | 'error' | 'critical'; message: string }>
  verdict: CertVerdict
}

// Liste de signature algos faibles (par OID ou string-match).
const WEAK_ALGOS = ['MD5', 'SHA-1', 'SHA1', 'md5WithRSA', 'sha1WithRSA']
const STRONG_ALGOS = ['SHA-256', 'SHA-384', 'SHA-512', 'ECDSA', 'Ed25519']

/**
 * Décode base64 → Uint8Array (browser + Node compatible).
 */
function b64ToBytes(b64: string): Uint8Array | null {
  try {
    if (typeof atob !== 'undefined') {
      const bin = atob(b64)
      const out = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i)
      return out
    }
    if (typeof Buffer !== 'undefined') {
      const buf = Buffer.from(b64, 'base64')
      return new Uint8Array(buf)
    }
    return null
  } catch {
    return null
  }
}

declare const Buffer: undefined | { from: (data: string, encoding: string) => Uint8Array }

/**
 * Extrait les blocs PEM (-----BEGIN CERTIFICATE----- ... -----END CERTIFICATE-----).
 */
function extractPemBlocks(input: string): string[] {
  const blocks: string[] = []
  const re = /-----BEGIN CERTIFICATE-----\s*([\s\S]+?)\s*-----END CERTIFICATE-----/g
  let m: RegExpExecArray | null
  while ((m = re.exec(input)) !== null) {
    blocks.push(m[1].replace(/\s+/g, ''))
  }
  return blocks
}

/**
 * Parse minimal ASN.1 d'un cert X.509 pour extraire les champs principaux.
 * Pour pédagogie — un vrai parser ASN.1 est trop volumineux pour le bundle.
 * On utilise une approche heuristique : on cherche les patterns connus dans
 * les bytes lisibles (commonName via OID 2.5.4.3, validity dates en UTCTime/GeneralizedTime).
 */
function parseCertBytes(bytes: Uint8Array): {
  subject: string | null
  issuer: string | null
  serial: string | null
  notBefore: string | null
  notAfter: string | null
  signatureAlgorithm: string | null
  subjectAltNames: string[]
} {
  // Helper : convertit bytes en hex pour debug et serial.
  const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')

  // OID 2.5.4.3 = commonName (encodé en bytes ASN.1 : 06 03 55 04 03 + value).
  // Cherche pattern 0x06 0x03 0x55 0x04 0x03 (commonName OID) suivi du tag string + length + value.
  const subject = extractCommonName(bytes, false)
  const issuer = extractCommonName(bytes, true)

  // Validity dates : UTCTime = 0x17 (13 chars YYMMDDHHMMSSZ), GeneralizedTime = 0x18 (15 chars).
  const dates = extractValidityDates(bytes)

  // Serial : approximation — premier INTEGER après le tbsCertificate version.
  const serialMatch = hex.match(/308[0-9a-f]{3}([0-9a-f]{2,40})/)
  const serial = serialMatch ? serialMatch[1].slice(0, 32).toUpperCase() : null

  // Signature algorithm : OID 1.2.840.113549.1.1.x (RSA signatures).
  const sigAlgo = detectSignatureAlgorithm(bytes)

  // SAN : OID 2.5.29.17. Extrait les DNS names visibles.
  const sans = extractSAN(bytes)

  return { subject, issuer, serial, notBefore: dates.notBefore, notAfter: dates.notAfter, signatureAlgorithm: sigAlgo, subjectAltNames: sans }
}

function extractCommonName(bytes: Uint8Array, isIssuer: boolean): string | null {
  // OID 2.5.4.3 (commonName) = bytes [0x06, 0x03, 0x55, 0x04, 0x03].
  for (let i = 0; i < bytes.length - 8; i += 1) {
    if (bytes[i] === 0x06 && bytes[i + 1] === 0x03 && bytes[i + 2] === 0x55 && bytes[i + 3] === 0x04 && bytes[i + 4] === 0x03) {
      // Tag + length suit (PrintableString=0x13, UTF8String=0x0c, IA5String=0x16, T61String=0x14).
      const tag = bytes[i + 5]
      if (tag === 0x13 || tag === 0x0c || tag === 0x16 || tag === 0x14) {
        const len = bytes[i + 6]
        if (len > 0 && len < 200 && i + 7 + len <= bytes.length) {
          const val = String.fromCharCode(...bytes.slice(i + 7, i + 7 + len))
          // Issuer vient AVANT subject dans le tbsCertificate → 1ère occurrence = issuer.
          // On utilise un compteur simplifié.
          if (isIssuer) {
            return val
          }
          // Pour subject, on doit prendre la 2e (skip first occurrence).
          // Simplification : trouve la 2e occurrence.
          for (let j = i + 7 + len; j < bytes.length - 8; j += 1) {
            if (bytes[j] === 0x06 && bytes[j + 1] === 0x03 && bytes[j + 2] === 0x55 && bytes[j + 3] === 0x04 && bytes[j + 4] === 0x03) {
              const tag2 = bytes[j + 5]
              if (tag2 === 0x13 || tag2 === 0x0c || tag2 === 0x16 || tag2 === 0x14) {
                const len2 = bytes[j + 6]
                if (len2 > 0 && len2 < 200 && j + 7 + len2 <= bytes.length) {
                  return String.fromCharCode(...bytes.slice(j + 7, j + 7 + len2))
                }
              }
            }
          }
          return val // pas trouvé de 2e, retourne la 1ère.
        }
      }
    }
  }
  return null
}

function extractValidityDates(bytes: Uint8Array): { notBefore: string | null; notAfter: string | null } {
  // UTCTime = 0x17 + length (typ 0x0d=13) + YYMMDDHHMMSSZ.
  // GeneralizedTime = 0x18 + length (typ 0x0f=15) + YYYYMMDDHHMMSSZ.
  const dates: string[] = []
  for (let i = 0; i < bytes.length - 16; i += 1) {
    if (bytes[i] === 0x17 && bytes[i + 1] === 0x0d) {
      // UTCTime 13 chars
      const val = String.fromCharCode(...bytes.slice(i + 2, i + 15))
      const formatted = parseUtcTime(val)
      if (formatted) dates.push(formatted)
    } else if (bytes[i] === 0x18 && bytes[i + 1] === 0x0f) {
      // GeneralizedTime 15 chars
      const val = String.fromCharCode(...bytes.slice(i + 2, i + 17))
      const formatted = parseGeneralizedTime(val)
      if (formatted) dates.push(formatted)
    }
    if (dates.length >= 2) break
  }
  return {
    notBefore: dates[0] || null,
    notAfter: dates[1] || null,
  }
}

function parseUtcTime(s: string): string | null {
  // YYMMDDHHMMSSZ — YY < 50 → 20YY, sinon 19YY.
  const m = /^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})Z$/.exec(s)
  if (!m) return null
  const yy = parseInt(m[1], 10)
  const fullYear = yy < 50 ? 2000 + yy : 1900 + yy
  return `${fullYear}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`
}

function parseGeneralizedTime(s: string): string | null {
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})Z$/.exec(s)
  if (!m) return null
  return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`
}

function detectSignatureAlgorithm(bytes: Uint8Array): string | null {
  // OIDs courants pour signature :
  //   1.2.840.113549.1.1.5  = sha1WithRSAEncryption
  //   1.2.840.113549.1.1.11 = sha256WithRSAEncryption
  //   1.2.840.113549.1.1.12 = sha384WithRSAEncryption
  //   1.2.840.113549.1.1.13 = sha512WithRSAEncryption
  //   1.2.840.113549.1.1.4  = md5WithRSAEncryption (faible)
  //   1.2.840.10045.4.3.2   = ecdsa-with-SHA256
  //   1.2.840.10045.4.3.3   = ecdsa-with-SHA384
  //   1.3.101.112           = Ed25519
  // Encodés : 06 09 2a 86 48 86 f7 0d 01 01 XX pour la famille RSA.
  for (let i = 0; i < bytes.length - 11; i += 1) {
    if (
      bytes[i] === 0x06 && bytes[i + 1] === 0x09 &&
      bytes[i + 2] === 0x2a && bytes[i + 3] === 0x86 && bytes[i + 4] === 0x48 &&
      bytes[i + 5] === 0x86 && bytes[i + 6] === 0xf7 && bytes[i + 7] === 0x0d &&
      bytes[i + 8] === 0x01 && bytes[i + 9] === 0x01
    ) {
      const variant = bytes[i + 10]
      switch (variant) {
        case 0x04: return 'md5WithRSAEncryption'
        case 0x05: return 'sha1WithRSAEncryption'
        case 0x0b: return 'sha256WithRSAEncryption'
        case 0x0c: return 'sha384WithRSAEncryption'
        case 0x0d: return 'sha512WithRSAEncryption'
      }
    }
    // ECDSA family : 06 08 2a 86 48 ce 3d 04 03 XX
    if (
      bytes[i] === 0x06 && bytes[i + 1] === 0x08 &&
      bytes[i + 2] === 0x2a && bytes[i + 3] === 0x86 && bytes[i + 4] === 0x48 &&
      bytes[i + 5] === 0xce && bytes[i + 6] === 0x3d && bytes[i + 7] === 0x04 && bytes[i + 8] === 0x03
    ) {
      const variant = bytes[i + 9]
      switch (variant) {
        case 0x02: return 'ecdsa-with-SHA256'
        case 0x03: return 'ecdsa-with-SHA384'
        case 0x04: return 'ecdsa-with-SHA512'
      }
    }
    // Ed25519 : 06 03 2b 65 70
    if (bytes[i] === 0x06 && bytes[i + 1] === 0x03 && bytes[i + 2] === 0x2b && bytes[i + 3] === 0x65 && bytes[i + 4] === 0x70) {
      return 'Ed25519'
    }
  }
  return null
}

function extractSAN(bytes: Uint8Array): string[] {
  // OID 2.5.29.17 = 06 03 55 1d 11
  for (let i = 0; i < bytes.length - 5; i += 1) {
    if (bytes[i] === 0x06 && bytes[i + 1] === 0x03 && bytes[i + 2] === 0x55 && bytes[i + 3] === 0x1d && bytes[i + 4] === 0x11) {
      // Suivant : OCTET STRING (0x04) ou directement SEQUENCE (0x30) avec les SAN.
      // Cherche les patterns DNS name : tag 0x82 (context-specific [2] = dNSName) + length + value.
      const names: string[] = []
      for (let j = i + 5; j < Math.min(bytes.length - 2, i + 2000); j += 1) {
        if (bytes[j] === 0x82) {
          const len = bytes[j + 1]
          if (len > 0 && len < 100 && j + 2 + len <= bytes.length) {
            const val = String.fromCharCode(...bytes.slice(j + 2, j + 2 + len))
            // Validation grossière : caractères imprimables, points et tirets.
            if (/^[a-zA-Z0-9.*\-_]+$/.test(val) && val.includes('.') && val.length < 80) {
              names.push(val)
            }
          }
        }
      }
      if (names.length > 0) return names
    }
  }
  return []
}

/**
 * Analyse complète : PEM → CertReport.
 */
export function inspectCertificate(pemInput: string, now: Date = new Date()): CertReport {
  const blocks = extractPemBlocks(pemInput)
  const issues: CertReport['issues'] = []
  if (blocks.length === 0) {
    return {
      pemBlocks: 0,
      subject: null, issuer: null, serial: null,
      notBefore: null, notAfter: null, hoursUntilExpire: null,
      signatureAlgorithm: null, subjectAltNames: [],
      issues: [{ severity: 'critical', message: 'Aucun bloc PEM CERTIFICATE trouvé. Format attendu : -----BEGIN CERTIFICATE-----.' }],
      verdict: 'unknown',
    }
  }
  const first = b64ToBytes(blocks[0])
  if (!first) {
    return {
      pemBlocks: blocks.length,
      subject: null, issuer: null, serial: null,
      notBefore: null, notAfter: null, hoursUntilExpire: null,
      signatureAlgorithm: null, subjectAltNames: [],
      issues: [{ severity: 'critical', message: 'Décodage base64 du PEM échoué — bloc malformé.' }],
      verdict: 'unknown',
    }
  }
  const parsed = parseCertBytes(first)

  // Hours until expire.
  let hoursUntilExpire: number | null = null
  if (parsed.notAfter) {
    try {
      const exp = new Date(parsed.notAfter).getTime()
      hoursUntilExpire = (exp - now.getTime()) / 3600000
    } catch { /* parse fail */ }
  }

  // Issues + verdict.
  if (hoursUntilExpire !== null) {
    if (hoursUntilExpire < 0) {
      issues.push({ severity: 'critical', message: `Certificat expiré depuis ${(-hoursUntilExpire).toFixed(0)}h.` })
    } else if (hoursUntilExpire < 24 * 14) {
      issues.push({ severity: 'warn', message: `Expire dans ${(hoursUntilExpire / 24).toFixed(1)} jours — pense au renouvellement.` })
    }
  }

  if (parsed.signatureAlgorithm) {
    if (WEAK_ALGOS.some((w) => parsed.signatureAlgorithm!.includes(w))) {
      issues.push({ severity: 'critical', message: `Algorithme de signature ${parsed.signatureAlgorithm} obsolète (MD5/SHA-1 deprecated).` })
    }
  }

  if (parsed.subject && parsed.issuer && parsed.subject === parsed.issuer) {
    issues.push({ severity: 'warn', message: 'Certificat auto-signé (subject == issuer) — pas validé par une CA reconnue.' })
  }

  if (blocks.length === 1) {
    issues.push({ severity: 'info', message: 'Un seul certificat fourni — pas de chaîne complète (root + intermediates manquants).' })
  }

  if (parsed.subjectAltNames.length === 0 && parsed.subject) {
    issues.push({ severity: 'warn', message: 'Aucun SAN détecté — les navigateurs modernes exigent SAN, pas juste CN.' })
  }

  // Verdict global.
  let verdict: CertVerdict = 'recommended'
  if (issues.some((i) => i.severity === 'critical' && i.message.includes('expiré'))) verdict = 'expired'
  else if (issues.some((i) => i.severity === 'critical' && i.message.includes('obsolète'))) verdict = 'weak-algo'
  else if (issues.some((i) => i.message.includes('auto-signé'))) verdict = 'self-signed'
  else if (issues.some((i) => i.severity === 'warn' && i.message.includes('Expire dans'))) verdict = 'expiring-soon'
  else if (issues.length === 0 && parsed.signatureAlgorithm && STRONG_ALGOS.some((s) => parsed.signatureAlgorithm!.includes(s.replace('-', '')) || parsed.signatureAlgorithm!.includes(s))) verdict = 'recommended'
  else verdict = 'acceptable'

  return {
    pemBlocks: blocks.length,
    subject: parsed.subject,
    issuer: parsed.issuer,
    serial: parsed.serial,
    notBefore: parsed.notBefore,
    notAfter: parsed.notAfter,
    hoursUntilExpire,
    signatureAlgorithm: parsed.signatureAlgorithm,
    subjectAltNames: parsed.subjectAltNames,
    issues,
    verdict,
  }
}
