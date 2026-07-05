// Rainbow table demo — précompute des hashes de mots de passe communs et
// permet à l'utilisateur de coller un hash pour voir s'il est dans la
// table. Pédagogie : pourquoi le SALT casse les rainbow tables.

const PASSWORDS: readonly string[] = [
  '123456', 'password', '12345678', 'qwerty', '111111',
  '123456789', 'abc123', 'password1', '123123', 'admin',
  'letmein', 'monkey', 'dragon', 'sunshine', 'iloveyou',
  'princess', '1234', 'football', 'shadow', 'master',
  'superman', 'qwerty123', 'welcome', 'azerty', 'azerty123',
  'motdepasse', 'soleil', 'doudou', 'amour', 'bonjour',
  'francais', 'paris', 'france', 'cheri', 'cherie',
  'admin123', 'root', 'toor', 'changeme', 'pass',
  'test', 'guest', 'login', 'demo', 'temp',
  'computer', 'thomas', 'nicolas', 'martin', 'julien',
]

export type HashAlgo = 'MD5' | 'SHA-1' | 'SHA-256' | 'SHA-512'

export type RainbowEntry = {
  plaintext: string
  hash: string
  algo: HashAlgo
}

export type LookupResult = {
  found: boolean
  plaintext?: string
  algo?: HashAlgo
  ms: number
}

/**
 * MD5 (non dispo dans WebCrypto). Implémentation compacte (RFC 1321) pour
 * pédagogie. Bytes → bytes hex string.
 *
 * Source : adapté de la lib JS publique compacte md5.js (Joseph Myers, BSD).
 */
function md5(message: string): string {
  // Constantes de l'algo MD5.
  const r = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
  ]
  const k: number[] = []
  for (let i = 0; i < 64; i += 1) {
    k.push((Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000)) | 0)
  }

  // Pad message.
  const bytes: number[] = []
  for (let i = 0; i < message.length; i += 1) {
    const c = message.charCodeAt(i)
    if (c < 128) bytes.push(c)
    else if (c < 2048) {
      bytes.push(192 | (c >> 6))
      bytes.push(128 | (c & 63))
    } else {
      bytes.push(224 | (c >> 12))
      bytes.push(128 | ((c >> 6) & 63))
      bytes.push(128 | (c & 63))
    }
  }
  const origLen = bytes.length
  bytes.push(0x80)
  while (bytes.length % 64 !== 56) bytes.push(0)
  const bitLen = origLen * 8
  for (let i = 0; i < 4; i += 1) bytes.push((bitLen >>> (8 * i)) & 0xff)
  for (let i = 0; i < 4; i += 1) bytes.push(0)

  let a0 = 0x67452301
  let b0 = 0xefcdab89
  let c0 = 0x98badcfe
  let d0 = 0x10325476

  for (let off = 0; off < bytes.length; off += 64) {
    const m: number[] = []
    for (let i = 0; i < 16; i += 1) {
      m.push(
        bytes[off + i * 4] |
        (bytes[off + i * 4 + 1] << 8) |
        (bytes[off + i * 4 + 2] << 16) |
        (bytes[off + i * 4 + 3] << 24)
      )
    }
    let a = a0, b = b0, c = c0, d = d0
    for (let i = 0; i < 64; i += 1) {
      let f = 0
      let g = 0
      if (i < 16)      { f = (b & c) | (~b & d); g = i }
      else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16 }
      else if (i < 48) { f = b ^ c ^ d;          g = (3 * i + 5) % 16 }
      else             { f = c ^ (b | ~d);       g = (7 * i) % 16 }
      const temp = d
      d = c
      c = b
      const sum = (a + f + k[i] + m[g]) | 0
      b = (b + ((sum << r[i]) | (sum >>> (32 - r[i])))) | 0
      a = temp
    }
    a0 = (a0 + a) | 0
    b0 = (b0 + b) | 0
    c0 = (c0 + c) | 0
    d0 = (d0 + d) | 0
  }
  const toHex = (n: number): string => {
    let s = ''
    for (let i = 0; i < 4; i += 1) {
      s += ((n >> (i * 8)) & 0xff).toString(16).padStart(2, '0')
    }
    return s
  }
  return toHex(a0) + toHex(b0) + toHex(c0) + toHex(d0)
}

/**
 * SHA via WebCrypto (md5 fait à la main).
 */
async function hashWeb(message: string, algo: 'SHA-1' | 'SHA-256' | 'SHA-512'): Promise<string> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return ''
  const buf = await crypto.subtle.digest(algo, new TextEncoder().encode(message))
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Build a rainbow table : pour chaque password + chaque algo, calcule le hash.
 */
let cachedTable: RainbowEntry[] | null = null
export async function buildRainbowTable(): Promise<RainbowEntry[]> {
  if (cachedTable) return cachedTable
  const out: RainbowEntry[] = []
  for (const pw of PASSWORDS) {
    out.push({ plaintext: pw, hash: md5(pw), algo: 'MD5' })
    out.push({ plaintext: pw, hash: await hashWeb(pw, 'SHA-1'), algo: 'SHA-1' })
    out.push({ plaintext: pw, hash: await hashWeb(pw, 'SHA-256'), algo: 'SHA-256' })
  }
  cachedTable = out
  return out
}

/**
 * Lookup : trouve le plaintext d'un hash dans la table.
 */
export async function lookupHash(rawHash: string): Promise<LookupResult> {
  const hash = rawHash.trim().toLowerCase().replace(/[^0-9a-f]/g, '')
  if (!hash) return { found: false, ms: 0 }
  const start = performance.now()
  const table = await buildRainbowTable()
  for (const entry of table) {
    if (entry.hash === hash) {
      return { found: true, plaintext: entry.plaintext, algo: entry.algo, ms: performance.now() - start }
    }
  }
  return { found: false, ms: performance.now() - start }
}

/**
 * Demo : montre la défense via SALT. Si on ajoute un salt random à un
 * password, le hash n'est plus dans la rainbow table.
 */
export async function hashWithSalt(password: string, salt: string, algo: 'SHA-256' = 'SHA-256'): Promise<string> {
  return hashWeb(salt + password, algo)
}

/**
 * Génère un salt random 16 bytes hex.
 */
export function generateSalt(): string {
  if (typeof crypto === 'undefined') return Math.random().toString(36).slice(2, 18)
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

export const RAINBOW_PASSWORDS = PASSWORDS
