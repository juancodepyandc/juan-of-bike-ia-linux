// Parse les paramètres d'un hash adaptatif depuis sa représentation textuelle.
// Argon2 et bcrypt ont leur cost paramétré dans la chaîne ($argon2id$v=19$m=65536,t=3,p=1$...).
// Ces paramètres déterminent la résistance au brute-force — donc cruciaux à
// extraire pour évaluer la sécurité d'une chaîne de hashing trouvée en audit.

export type Argon2Params = {
  variant: 'i' | 'd' | 'id'
  version: number
  memoryKib: number
  timeCost: number
  parallelism: number
  salt: string
  digest: string
}

export type BcryptParams = {
  variant: '2a' | '2b' | '2y' | '2x'
  cost: number
  saltAndDigest: string
}

export type ScryptParams = {
  N: number
  r: number
  p: number
  salt: string
  digest: string
}

/**
 * Parse une chaîne Argon2 standard ($argon2id$v=19$m=65536,t=3,p=1$salt$digest).
 * Retourne null si le format ne match pas.
 */
export function parseArgon2(hash: string): Argon2Params | null {
  const m = hash.match(/^\$argon2(i|d|id)\$v=(\d+)\$m=(\d+),t=(\d+),p=(\d+)\$([^$]+)\$([^$\s]+)$/)
  if (!m) return null
  return {
    variant: m[1] as Argon2Params['variant'],
    version: parseInt(m[2], 10),
    memoryKib: parseInt(m[3], 10),
    timeCost: parseInt(m[4], 10),
    parallelism: parseInt(m[5], 10),
    salt: m[6],
    digest: m[7],
  }
}

/**
 * Parse une chaîne bcrypt ($2b$12$saltAndDigest).
 */
export function parseBcrypt(hash: string): BcryptParams | null {
  const m = hash.match(/^\$(2[abxy])\$(\d{2})\$([./A-Za-z0-9]{53})$/)
  if (!m) return null
  return {
    variant: m[1] as BcryptParams['variant'],
    cost: parseInt(m[2], 10),
    saltAndDigest: m[3],
  }
}

/**
 * Parse scrypt PHC ($scrypt$N=131072,r=8,p=1$salt$digest).
 */
export function parseScrypt(hash: string): ScryptParams | null {
  const m = hash.match(/^\$scrypt\$N=(\d+),r=(\d+),p=(\d+)\$([^$]+)\$([^$\s]+)$/)
  if (!m) return null
  return {
    N: parseInt(m[1], 10),
    r: parseInt(m[2], 10),
    p: parseInt(m[3], 10),
    salt: m[4],
    digest: m[5],
  }
}

/**
 * Audit OWASP 2024 sur les paramètres d'un hash adaptatif. Retourne un
 * verdict avec recommandations concrètes.
 */
export type HashAudit = {
  algorithm: 'argon2id' | 'argon2i' | 'argon2d' | 'bcrypt' | 'scrypt' | 'unknown'
  verdict: 'banned' | 'undersized' | 'acceptable' | 'recommended'
  recommendations: string[]
  /** Paramètres extraits, pour le panneau d'analyse. */
  parsed: Argon2Params | BcryptParams | ScryptParams | null
}

export function auditHash(hash: string): HashAudit {
  const argon = parseArgon2(hash)
  if (argon) {
    const recs: string[] = []
    if (argon.variant !== 'id') {
      recs.push(`Variante ${argon.variant} : préférer argon2id (hybride, résistant aux side-channels).`)
    }
    if (argon.memoryKib < 19_456) {
      recs.push(`Mémoire ${argon.memoryKib} KiB < 19 MiB minimum OWASP 2024.`)
    } else if (argon.memoryKib < 65_536) {
      recs.push(`Mémoire ${argon.memoryKib} KiB < 64 MiB recommandé pour serveur typique.`)
    }
    if (argon.timeCost < 2) recs.push(`timeCost ${argon.timeCost} < 2 minimum OWASP.`)
    if (argon.parallelism < 1) recs.push(`parallelism ${argon.parallelism} doit être ≥ 1.`)

    const verdict: HashAudit['verdict'] =
      argon.memoryKib < 19_456 || argon.timeCost < 2 ? 'undersized'
      : argon.variant === 'id' && argon.memoryKib >= 65_536 && argon.timeCost >= 3 ? 'recommended'
      : 'acceptable'

    return {
      algorithm: ('argon2' + argon.variant) as HashAudit['algorithm'],
      verdict,
      recommendations: recs.length === 0 ? ['Configuration OWASP 2024 conforme.'] : recs,
      parsed: argon,
    }
  }

  const bc = parseBcrypt(hash)
  if (bc) {
    const recs: string[] = []
    if (bc.cost < 10) recs.push(`Cost ${bc.cost} < 10 : trop rapide, GPU crack-friendly.`)
    if (bc.cost < 12) recs.push(`Cost ${bc.cost} < 12 minimum OWASP 2024.`)
    if (bc.variant === '2a' || bc.variant === '2x') {
      recs.push(`Variante ${bc.variant} obsolète, migrer vers $2b$.`)
    }
    const verdict: HashAudit['verdict'] =
      bc.cost < 10 ? 'undersized'
      : bc.cost >= 12 && (bc.variant === '2b' || bc.variant === '2y') ? 'acceptable'
      : 'acceptable'
    return {
      algorithm: 'bcrypt',
      verdict,
      recommendations: recs.length === 0 ? ['Cost ≥ 12, variante moderne — conforme.'] : recs,
      parsed: bc,
    }
  }

  const sc = parseScrypt(hash)
  if (sc) {
    const recs: string[] = []
    if (sc.N < 2 ** 15) recs.push(`N=${sc.N} < 2^15 minimum RFC 7914.`)
    if (sc.N < 2 ** 17) recs.push(`N=${sc.N} < 2^17 recommandé.`)
    const verdict = sc.N < 2 ** 15 ? 'undersized' : sc.N >= 2 ** 17 ? 'recommended' : 'acceptable'
    return {
      algorithm: 'scrypt',
      verdict,
      recommendations: recs.length === 0 ? ['Paramètres conformes RFC 7914.'] : recs,
      parsed: sc,
    }
  }

  // Pattern MD5/SHA-1/SHA-256/SHA-512 nu (longueur hex)
  if (/^[a-fA-F0-9]{32}$/.test(hash)) return { algorithm: 'unknown', verdict: 'banned', recommendations: ['MD5 nu — banni pour mots de passe. Migrer vers Argon2id.'], parsed: null }
  if (/^[a-fA-F0-9]{40}$/.test(hash)) return { algorithm: 'unknown', verdict: 'banned', recommendations: ['SHA-1 nu — banni pour mots de passe.'], parsed: null }
  if (/^[a-fA-F0-9]{64}$/.test(hash)) return { algorithm: 'unknown', verdict: 'banned', recommendations: ['SHA-256 nu — trop rapide pour les mots de passe.'], parsed: null }
  if (/^[a-fA-F0-9]{128}$/.test(hash)) return { algorithm: 'unknown', verdict: 'banned', recommendations: ['SHA-512 nu — trop rapide pour les mots de passe.'], parsed: null }

  return {
    algorithm: 'unknown',
    verdict: 'banned',
    recommendations: ['Format inconnu — vérifier manuellement.'],
    parsed: null,
  }
}
