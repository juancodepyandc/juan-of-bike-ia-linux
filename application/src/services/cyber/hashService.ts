const enc = new TextEncoder()

async function subtleHash(algo: 'SHA-1' | 'SHA-256' | 'SHA-384' | 'SHA-512', text: string) {
  const buf = await crypto.subtle.digest(algo, enc.encode(text))
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

export function sha1(text: string) { return subtleHash('SHA-1', text) }
export function sha256(text: string) { return subtleHash('SHA-256', text) }
export function sha384(text: string) { return subtleHash('SHA-384', text) }
export function sha512(text: string) { return subtleHash('SHA-512', text) }

// MD5 pure-JS (pédagogique, obsolète — montrer la fragilité)
export function md5(text: string): string {
  function addUnsigned(x: number, y: number) {
    const lsw = (x & 0xffff) + (y & 0xffff)
    const msw = (x >> 16) + (y >> 16) + (lsw >> 16)
    return (msw << 16) | (lsw & 0xffff)
  }
  function rotL(n: number, s: number) { return (n << s) | (n >>> (32 - s)) }
  function F(x: number, y: number, z: number) { return (x & y) | (~x & z) }
  function G(x: number, y: number, z: number) { return (x & z) | (y & ~z) }
  function H(x: number, y: number, z: number) { return x ^ y ^ z }
  function I(x: number, y: number, z: number) { return y ^ (x | ~z) }
  function FF(a: number, b: number, c: number, d: number, x: number, s: number, t: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(F(b, c, d), x), t))
    return addUnsigned(rotL(a, s), b)
  }
  function GG(a: number, b: number, c: number, d: number, x: number, s: number, t: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(G(b, c, d), x), t))
    return addUnsigned(rotL(a, s), b)
  }
  function HH(a: number, b: number, c: number, d: number, x: number, s: number, t: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(H(b, c, d), x), t))
    return addUnsigned(rotL(a, s), b)
  }
  function II(a: number, b: number, c: number, d: number, x: number, s: number, t: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(I(b, c, d), x), t))
    return addUnsigned(rotL(a, s), b)
  }
  function convertToWordArray(str: string) {
    const msg: number[] = []
    const bytes = enc.encode(str)
    const len = bytes.length
    const numberOfWords = (((len + 8) >>> 6) + 1) * 16
    for (let i = 0; i < numberOfWords; i++) msg[i] = 0
    for (let i = 0; i < len; i++) msg[i >> 2] |= bytes[i] << ((i % 4) * 8)
    msg[len >> 2] |= 0x80 << ((len % 4) * 8)
    msg[numberOfWords - 2] = len * 8
    return msg
  }
  function wordToHex(n: number) {
    let s = ''
    for (let i = 0; i < 4; i++) s += ((n >> (i * 8)) & 0xff).toString(16).padStart(2, '0')
    return s
  }
  const x = convertToWordArray(text)
  let a = 0x67452301, b = 0xefcdab89, c = 0x98badcfe, d = 0x10325476
  const S: number[][] = [
    [7, 12, 17, 22],
    [5, 9, 14, 20],
    [4, 11, 16, 23],
    [6, 10, 15, 21],
  ]
  const K = [
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391,
  ]
  for (let i = 0; i < x.length; i += 16) {
    const aa = a, bb = b, cc = c, dd = d
    for (let j = 0; j < 16; j++) {
      const s = S[0][j % 4]
      if (j === 0) a = FF(a, b, c, d, x[i + j], s, K[j])
      else if (j % 4 === 0) { a = FF(a, b, c, d, x[i + j], s, K[j]) }
      else if (j % 4 === 1) { d = FF(d, a, b, c, x[i + j], S[0][1], K[j]) }
      else if (j % 4 === 2) { c = FF(c, d, a, b, x[i + j], S[0][2], K[j]) }
      else { b = FF(b, c, d, a, x[i + j], S[0][3], K[j]) }
    }
    for (let j = 0; j < 16; j++) {
      const idx = (5 * j + 1) % 16
      if (j % 4 === 0) { a = GG(a, b, c, d, x[i + idx], S[1][0], K[16 + j]) }
      else if (j % 4 === 1) { d = GG(d, a, b, c, x[i + idx], S[1][1], K[16 + j]) }
      else if (j % 4 === 2) { c = GG(c, d, a, b, x[i + idx], S[1][2], K[16 + j]) }
      else { b = GG(b, c, d, a, x[i + idx], S[1][3], K[16 + j]) }
    }
    for (let j = 0; j < 16; j++) {
      const idx = (3 * j + 5) % 16
      if (j % 4 === 0) { a = HH(a, b, c, d, x[i + idx], S[2][0], K[32 + j]) }
      else if (j % 4 === 1) { d = HH(d, a, b, c, x[i + idx], S[2][1], K[32 + j]) }
      else if (j % 4 === 2) { c = HH(c, d, a, b, x[i + idx], S[2][2], K[32 + j]) }
      else { b = HH(b, c, d, a, x[i + idx], S[2][3], K[32 + j]) }
    }
    for (let j = 0; j < 16; j++) {
      const idx = (7 * j) % 16
      if (j % 4 === 0) { a = II(a, b, c, d, x[i + idx], S[3][0], K[48 + j]) }
      else if (j % 4 === 1) { d = II(d, a, b, c, x[i + idx], S[3][1], K[48 + j]) }
      else if (j % 4 === 2) { c = II(c, d, a, b, x[i + idx], S[3][2], K[48 + j]) }
      else { b = II(b, c, d, a, x[i + idx], S[3][3], K[48 + j]) }
    }
    a = addUnsigned(a, aa); b = addUnsigned(b, bb); c = addUnsigned(c, cc); d = addUnsigned(d, dd)
  }
  return wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)
}

export async function hmacSha256(key: string, message: string) {
  const keyObj = await crypto.subtle.importKey(
    'raw', enc.encode(key),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', keyObj, enc.encode(message))
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

// Hash identifier heuristique
export function identifyHash(hash: string): string[] {
  const clean = hash.trim().replace(/^0x/, '')
  const hexOnly = /^[0-9a-fA-F]+$/.test(clean)
  const candidates: string[] = []
  if (hexOnly) {
    switch (clean.length) {
      case 32: candidates.push('MD5', 'MD4', 'NTLM'); break
      case 40: candidates.push('SHA-1', 'RIPEMD-160'); break
      case 56: candidates.push('SHA-224', 'SHA3-224'); break
      case 64: candidates.push('SHA-256', 'SHA3-256', 'BLAKE2s-256'); break
      case 96: candidates.push('SHA-384', 'SHA3-384'); break
      case 128: candidates.push('SHA-512', 'SHA3-512', 'BLAKE2b-512'); break
      default: candidates.push('hex inconnu')
    }
  }
  if (clean.startsWith('$2a$') || clean.startsWith('$2b$') || clean.startsWith('$2y$')) candidates.push('bcrypt')
  if (clean.startsWith('$argon2')) candidates.push('argon2')
  if (clean.startsWith('$6$')) candidates.push('SHA512crypt')
  if (clean.startsWith('$5$')) candidates.push('SHA256crypt')
  if (clean.startsWith('$1$')) candidates.push('MD5crypt')
  if (candidates.length === 0) candidates.push('format inconnu')
  return candidates
}

let wordlistCache: string[] | null = null

export async function loadWordlist(): Promise<string[]> {
  if (wordlistCache) return wordlistCache
  try {
    const resp = await fetch('/cyber/wordlist.txt')
    const text = await resp.text()
    wordlistCache = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  } catch {
    wordlistCache = FALLBACK_WORDLIST
  }
  return wordlistCache
}

export async function crackSha256Dict(targetHex: string, onProgress?: (tried: number, total: number) => void) {
  const target = targetHex.trim().toLowerCase()
  const list = await loadWordlist()
  const suffixes = ['', '1', '!', '123', '2024', '2025', '2026']
  const total = list.length * suffixes.length
  let tried = 0
  for (const word of list) {
    for (const suf of suffixes) {
      const candidate = word + suf
      const h = await sha256(candidate)
      if (h === target) return { found: true, plaintext: candidate, tried }
      tried += 1
      if (onProgress && tried % 250 === 0) onProgress(tried, total)
    }
  }
  return { found: false, plaintext: null, tried }
}

// Fallback minimal utilisé si `wordlist.txt` indisponible
const FALLBACK_WORDLIST = [
  'password', '123456', 'qwerty', 'admin', 'letmein', 'welcome', 'monkey', 'dragon',
  'soleil', 'azerty', 'motdepasse', 'football', 'baseball', 'pokemon', 'iloveyou',
  'abc123', 'passw0rd', 'trustno1', 'master', 'sunshine', 'princess', 'superman',
]
