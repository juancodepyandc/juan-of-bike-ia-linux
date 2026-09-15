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
  if (!/^[A-Za-z0-9_-]+$/.test(b64url) || b64url.length % 4 === 1) return null
  try {
    const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - b64url.length % 4) % 4)
    let bytes: Uint8Array
    if (typeof atob !== 'undefined') {
      const bin = atob(b64)
      bytes = new Uint8Array(bin.length)
      for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
    } else if (typeof Buffer !== 'undefined') {
      bytes = Uint8Array.from(Buffer.from(b64, 'base64'))
    } else {
      return null
    }
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    return null
  }
}

declare const Buffer: undefined | { from: (data: string, encoding: string) => Iterable<number> }

function decodeObject(segment: string): Record<string, unknown> | null {
  const json = base64urlDecode(segment)
  if (json === null) return null
  try {
    const value: unknown = JSON.parse(json)
    return value !== null && typeof value === 'object' && !Array.isArray(value)
      ? value as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

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
  const decodedHeader = decodeObject(headerB64)
  const payload = decodeObject(payloadB64) as JwtPayload | null
  if (!decodedHeader) {
    issues.push({ severity: 'block', message: 'Header JWT illisible (base64 ou JSON invalide)' })
  } else if (typeof decodedHeader.alg !== 'string' || !decodedHeader.alg.trim()) {
    issues.push({ severity: 'block', message: 'Header JWT invalide : alg doit être une chaîne non vide' })
  } else {
    header = decodedHeader as JwtHeader
  }
  if (!payload) {
    issues.push({ severity: 'block', message: 'Payload JWT illisible' })
  }

  // OWASP rules.
  if (header) {
    if (header.alg.toLowerCase() === 'none') {
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
    const nowSec = now.getTime() / 1000
    if (payload.exp != null) {
      if (typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) {
        issues.push({ severity: 'warn', message: 'exp claim n\'est pas numérique' })
      } else if (payload.exp <= nowSec) {
        expired = true
        issues.push({ severity: 'warn', message: `Token expiré depuis ${((nowSec - payload.exp) / 3600).toFixed(1)}h` })
      }
    } else {
      issues.push({ severity: 'warn', message: 'Pas de claim exp — token sans expiration' })
    }
    for (const claim of ['nbf', 'iat'] as const) {
      if (payload[claim] != null && (typeof payload[claim] !== 'number' || !Number.isFinite(payload[claim]))) {
        issues.push({ severity: 'warn', message: `${claim} claim n'est pas numérique et fini` })
      }
    }
    if (payload.nbf != null && typeof payload.nbf === 'number' && Number.isFinite(payload.nbf) && payload.nbf > nowSec) {
      notYetValid = true
      issues.push({ severity: 'warn', message: 'Token nbf dans le futur — pas encore valide' })
    }
    if (payload.iat != null && typeof payload.iat === 'number' && Number.isFinite(payload.iat)) {
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
  if (typeof inspection.payload.iss === 'string' && inspection.payload.iss) parts.push(`iss=${inspection.payload.iss}`)
  if (typeof inspection.payload.sub === 'string' && inspection.payload.sub) parts.push(`sub=${inspection.payload.sub}`)
  if (inspection.expired) parts.push('EXPIRÉ')
  if (inspection.notYetValid) parts.push('NOT-YET-VALID')
  return parts.join(' • ')
}
