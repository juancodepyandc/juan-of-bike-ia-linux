// JWT decoder/inspector — décode header + payload sans valider la signature.
// Catégorise les vulnérabilités courantes (alg:none, faiblesses cryptiques)
// et expose les claims pour audit OSINT défensif.
//
// Module pédagogique — ne JAMAIS utiliser pour valider un JWT en production.

export type JwtHeader = {
  alg: string
  typ?: string
  kid?: string
  [key: string]: unknown
}

export type JwtPayload = {
  iss?: string
  sub?: string
  aud?: string | string[]
  exp?: number
  iat?: number
  nbf?: number
  jti?: string
  [key: string]: unknown
}

export type JwtInspection = {
  header: JwtHeader | null
  payload: JwtPayload | null
  signature: string | null
  /** Issues détectées. */
  issues: Array<{ severity: 'info' | 'warn' | 'error' | 'block'; message: string }>
  /** True si le token est expiré (exp dans le passé). */
  expired: boolean
  /** True si pas encore valide (nbf dans le futur). */
  notYetValid: boolean
  /** Âge en heures depuis iat. */
  ageHours: number | null
}

/**
 * Base64url decode (sans padding) → texte UTF-8.
 */
function base64urlDecode(b64url: string): string | null {
  try {
    const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((b64url.length + 3) % 4)
    if (typeof atob !== 'undefined') {
      const bin = atob(b64.slice(0, b64.length - (b64.length % 4 || 0)))
      const bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
      return new TextDecoder('utf-8').decode(bytes)
    }
    // Fallback Node.
    if (typeof Buffer !== 'undefined') return Buffer.from(b64url, 'base64url').toString('utf-8')
    return null
  } catch {
    return null
  }
}

declare const Buffer: undefined | { from: (data: string, encoding: string) => { toString: (enc: string) => string } }

/**
 * Inspecte un JWT — retourne header/payload décodés + issues OWASP.
 */
export function inspectJwt(token: string, now: Date = new Date()): JwtInspection {
  const parts = token.split('.')
  const issues: JwtInspection['issues'] = []
  if (parts.length !== 3) {
    return {
      header: null, payload: null, signature: null,
      issues: [{ severity: 'block', message: 'Token JWT mal formé (3 parties séparées par . attendues)' }],
      expired: false, notYetValid: false, ageHours: null,
    }
  }
  const [headerB64, payloadB64, signature] = parts

  let header: JwtHeader | null = null
  let payload: JwtPayload | null = null
  try {
    const headerJson = base64urlDecode(headerB64)
    if (headerJson) header = JSON.parse(headerJson)
  } catch {
    issues.push({ severity: 'block', message: 'Header JWT illisible (base64 ou JSON invalide)' })
  }
  try {
    const payloadJson = base64urlDecode(payloadB64)
    if (payloadJson) payload = JSON.parse(payloadJson)
  } catch {
    issues.push({ severity: 'block', message: 'Payload JWT illisible' })
  }

  // OWASP rules.
  if (header) {
    if (header.alg === 'none' || header.alg === 'None' || header.alg === 'NONE') {
      issues.push({ severity: 'block', message: 'alg=none — un attaquant peut forger n\'importe quel token' })
    }
    if (header.alg === 'HS256' && header.kid && typeof header.kid === 'string' && header.kid.includes('..')) {
      issues.push({ severity: 'error', message: 'kid contient ".." — risque path traversal côté serveur' })
    }
    if (header.alg && /^(MD5|SHA1)$/i.test(header.alg)) {
      issues.push({ severity: 'error', message: `Algorithme ${header.alg} obsolète` })
    }
    if (!header.typ) {
      issues.push({ severity: 'info', message: 'Header sans typ:JWT explicite' })
    }
  }

  let expired = false
  let notYetValid = false
  let ageHours: number | null = null

  if (payload) {
    const nowSec = Math.floor(now.getTime() / 1000)
    if (payload.exp != null) {
      if (typeof payload.exp !== 'number') {
        issues.push({ severity: 'warn', message: 'exp claim n\'est pas numérique' })
      } else if (payload.exp < nowSec) {
        expired = true
        issues.push({ severity: 'warn', message: `Token expiré depuis ${((nowSec - payload.exp) / 3600).toFixed(1)}h` })
      }
    } else {
      issues.push({ severity: 'warn', message: 'Pas de claim exp — token sans expiration' })
    }
    if (payload.nbf != null && typeof payload.nbf === 'number' && payload.nbf > nowSec) {
      notYetValid = true
      issues.push({ severity: 'warn', message: 'Token nbf dans le futur — pas encore valide' })
    }
    if (payload.iat != null && typeof payload.iat === 'number') {
      ageHours = (nowSec - payload.iat) / 3600
      if (ageHours > 24 * 365) {
        issues.push({ severity: 'warn', message: `Token âgé de ${(ageHours / 24).toFixed(0)} jours — anormalement vieux` })
      }
    }
    if (!payload.iss) issues.push({ severity: 'info', message: 'Pas de claim iss (émetteur)' })
    if (!payload.aud) issues.push({ severity: 'info', message: 'Pas de claim aud (audience)' })
    if (!payload.sub) issues.push({ severity: 'info', message: 'Pas de claim sub (sujet)' })
    // Détection d'informations sensibles dans les claims.
    for (const key of Object.keys(payload)) {
      if (/password|secret|api[_-]?key|token/i.test(key)) {
        issues.push({ severity: 'error', message: `Claim "${key}" contient potentiellement un secret en clair` })
      }
    }
  }

  return {
    header,
    payload,
    signature: signature || null,
    issues,
    expired,
    notYetValid,
    ageHours,
  }
}

/**
 * Récap court pour l'UI.
 */
export function summariseJwt(inspection: JwtInspection): string {
  if (!inspection.header || !inspection.payload) return 'JWT invalide'
  const parts: string[] = []
  parts.push(`alg=${inspection.header.alg}`)
  if (inspection.payload.iss) parts.push(`iss=${inspection.payload.iss}`)
  if (inspection.payload.sub) parts.push(`sub=${inspection.payload.sub}`)
  if (inspection.expired) parts.push('EXPIRÉ')
  if (inspection.notYetValid) parts.push('NOT-YET-VALID')
  return parts.join(' • ')
}
