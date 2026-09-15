const enc = new TextEncoder()
const dec = new TextDecoder()

export function caesarShift(text: string, shift: number) {
  const s = ((shift % 26) + 26) % 26
  return text
    .split('')
    .map((ch) => {
      const code = ch.charCodeAt(0)
      if (code >= 65 && code <= 90) return String.fromCharCode(((code - 65 + s) % 26) + 65)
      if (code >= 97 && code <= 122) return String.fromCharCode(((code - 97 + s) % 26) + 97)
      return ch
    })
    .join('')
}

export function rot13(text: string) {
  return caesarShift(text, 13)
}

export function atbash(text: string) {
  return text
    .split('')
    .map((ch) => {
      const code = ch.charCodeAt(0)
      if (code >= 65 && code <= 90) return String.fromCharCode(90 - (code - 65))
      if (code >= 97 && code <= 122) return String.fromCharCode(122 - (code - 97))
      return ch
    })
    .join('')
}

export function vigenere(text: string, key: string, decrypt = false) {
  if (!key) return text
  const clean = key.replace(/[^a-zA-Z]/g, '').toLowerCase()
  if (!clean) return text
  let ki = 0
  return text
    .split('')
    .map((ch) => {
      const code = ch.charCodeAt(0)
      const isUpper = code >= 65 && code <= 90
      const isLower = code >= 97 && code <= 122
      if (!isUpper && !isLower) return ch
      const k = clean.charCodeAt(ki % clean.length) - 97
      ki += 1
      const base = isUpper ? 65 : 97
      const shift = decrypt ? (26 - k) : k
      return String.fromCharCode(((code - base + shift) % 26) + base)
    })
    .join('')
}

/**
 * Zigzag des rangees pour `n` unites de texte. Extrait pour que le
 * chiffrement et le dechiffrement partagent EXACTEMENT le meme parcours.
 */
function railPattern(n: number, rails: number): number[] {
  const pattern: number[] = []
  let row = 0
  let dir = 1
  for (let i = 0; i < n; i++) {
    pattern.push(row)
    if (row === 0) dir = 1
    else if (row === rails - 1) dir = -1
    row += dir
  }
  return pattern
}

/**
 * Chiffre de la haie (rail fence).
 *
 * On decoupe en POINTS DE CODE (`[...text]`) des deux cotes. L ancienne
 * version chiffrait avec `for...of` (points de code) mais dechiffrait avec
 * `text.length` / `text[i]` (unites UTF-16): des que le texte contenait un
 * caractere hors BMP — le moindre emoji — les deux cotes ne comptaient pas
 * le meme nombre de cases et l aller-retour rendait des demi-substituts.
 * Mesure avant correction: 254 aller-retours casses sur 280 des que le texte
 * portait un emoji (ASCII et BMP: 0 sur 700).
 */
export function railFence(text: string, rails: number, decrypt = false) {
  if (rails <= 1) return text
  const units = [...text]
  const pattern = railPattern(units.length, rails)
  if (!decrypt) {
    const fence: string[][] = Array.from({ length: rails }, () => [])
    pattern.forEach((r, i) => fence[r].push(units[i]))
    return fence.flat().join('')
  }
  const rowSizes = Array.from({ length: rails }, (_, r) => pattern.filter((p) => p === r).length)
  const cursors: number[] = []
  let acc = 0
  for (const size of rowSizes) { cursors.push(acc); acc += size }
  return pattern.map((r) => units[cursors[r]++]).join('')
}

export function frequencyAnalysis(text: string) {
  const freq = new Map<string, number>()
  let total = 0
  for (const ch of text.toLowerCase()) {
    if (ch >= 'a' && ch <= 'z') {
      freq.set(ch, (freq.get(ch) || 0) + 1)
      total += 1
    }
  }
  const result = Array.from({ length: 26 }, (_, i) => {
    const letter = String.fromCharCode(97 + i)
    const count = freq.get(letter) || 0
    return { letter, count, percent: total ? (count / total) * 100 : 0 }
  })
  return { distribution: result, total }
}

const EN_FREQ: Record<string, number> = {
  a: 8.2, b: 1.5, c: 2.8, d: 4.3, e: 12.7, f: 2.2, g: 2.0, h: 6.1, i: 7.0, j: 0.2,
  k: 0.8, l: 4.0, m: 2.4, n: 6.7, o: 7.5, p: 1.9, q: 0.1, r: 6.0, s: 6.3, t: 9.1,
  u: 2.8, v: 1.0, w: 2.4, x: 0.2, y: 2.0, z: 0.1,
}

const FR_FREQ: Record<string, number> = {
  a: 7.6, b: 0.9, c: 3.3, d: 3.7, e: 14.7, f: 1.1, g: 0.9, h: 0.7, i: 7.5, j: 0.5,
  k: 0.1, l: 5.5, m: 3.0, n: 7.1, o: 5.4, p: 3.0, q: 1.4, r: 6.6, s: 7.9, t: 7.2,
  u: 6.3, v: 1.6, w: 0.1, x: 0.4, y: 0.3, z: 0.1,
}

export function suggestCaesarShift(text: string, lang: 'en' | 'fr' = 'fr') {
  const target = lang === 'fr' ? FR_FREQ : EN_FREQ
  let bestShift = 0
  let bestScore = Infinity
  for (let shift = 0; shift < 26; shift++) {
    const decoded = caesarShift(text, -shift)
    const { distribution } = frequencyAnalysis(decoded)
    let chi = 0
    for (const row of distribution) {
      const expected = (target[row.letter] || 0.1)
      const diff = row.percent - expected
      chi += (diff * diff) / Math.max(expected, 0.5)
    }
    if (chi < bestScore) { bestScore = chi; bestShift = shift }
  }
  return { bestShift, bestScore, suggestion: caesarShift(text, -bestShift) }
}

/**
 * Encodage base64 d un texte UTF-8.
 *
 * L ancienne version, `btoa(unescape(encodeURIComponent(text)))`, LEVAIT une
 * `URIError: URI malformed` des que le texte contenait un substitut isole —
 * exactement ce que produit un `slice()` au milieu d un emoji, cas courant
 * quand l interface tronque un message. Le laboratoire plantait au lieu de
 * chiffrer. `TextEncoder` applique la substitution U+FFFD prevue par la norme
 * et ne jette jamais. Au passage on sort de `escape`/`unescape`, retires de
 * la norme (Annexe B).
 */
export function toBase64(text: string) {
  const bytes = enc.encode(text)
  let bin = ''
  for (const b of bytes) bin += String.fromCharCode(b)
  return btoa(bin)
}

export function fromBase64(b64: string) {
  try {
    const bin = atob(b64.trim())
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return dec.decode(bytes)
  } catch { return '' }
}

export function toHex(text: string) {
  return Array.from(enc.encode(text)).map((b) => b.toString(16).padStart(2, '0')).join('')
}

export function fromHex(hex: string) {
  const clean = hex.replace(/[^0-9a-fA-F]/g, '')
  if (clean.length % 2) return ''
  const bytes = new Uint8Array(clean.length / 2)
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(clean.substr(i * 2, 2), 16)
  return dec.decode(bytes)
}

export function toBinary(text: string) {
  return Array.from(enc.encode(text)).map((b) => b.toString(2).padStart(8, '0')).join(' ')
}

export function fromBinary(binary: string) {
  const chunks = binary.trim().split(/\s+/)
  const bytes = new Uint8Array(chunks.length)
  for (let i = 0; i < chunks.length; i++) bytes[i] = parseInt(chunks[i], 2) || 0
  return dec.decode(bytes)
}

/**
 * Alphabet morse international, recommandation UIT-R M.1677-1.
 *
 * L ancienne table s arretait aux 26 lettres et aux 10 chiffres: toute
 * ponctuation etait jetee en silence par `toMorse` (`"a,b"` rendait `"ab"`
 * a l aller-retour, la virgule disparue sans un mot). La table couvre
 * desormais la ponctuation normalisee de la recommandation, plus les
 * lettres accentuees prevues pour le francais — un laboratoire francophone
 * qui code "operateur prive de creme" doit retrouver son texte.
 */
const MORSE_MAP: Record<string, string> = {
  a: '.-', b: '-...', c: '-.-.', d: '-..', e: '.', f: '..-.', g: '--.', h: '....',
  i: '..', j: '.---', k: '-.-', l: '.-..', m: '--', n: '-.', o: '---', p: '.--.',
  q: '--.-', r: '.-.', s: '...', t: '-', u: '..-', v: '...-', w: '.--', x: '-..-',
  y: '-.--', z: '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--',
  '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
  // Ponctuation UIT-R M.1677-1.
  '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
  '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
  ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
  '"': '.-..-.', '$': '...-..-', '@': '.--.-.',
  // Lettres accentuees (memes codes que la tradition telegraphique FR).
  é: '..-..', è: '.-..-', à: '.--.-', ù: '..--', ç: '-.-..', ü: '..--', ö: '---.',
}

export function toMorse(text: string) {
  return text.toLowerCase().split('').map((ch) => {
    if (ch === ' ') return '/'
    return MORSE_MAP[ch] || ''
  }).filter(Boolean).join(' ')
}

const MORSE_INVERSE: Record<string, string> = (() => {
  const out: Record<string, string> = {}
  // Premier gagnant: `ù` et `ü` partagent `..--`, on garde l entree initiale
  // pour que le decodage reste deterministe.
  for (const [k, v] of Object.entries(MORSE_MAP)) if (!(v in out)) out[v] = k
  return out
})()

export function fromMorse(morse: string) {
  return morse.trim().split(/\s+/).map((token) => {
    if (!token) return ''
    return token === '/' ? ' ' : (MORSE_INVERSE[token] ?? '')
  }).join('')
}

/**
 * Caracteres que `toMorse` ne sait pas transcrire. Rendre la perte visible
 * plutot que de la subir: l interface peut prevenir au lieu de livrer un
 * texte ampute sans explication.
 */
export function morseUnsupported(text: string): string[] {
  const out = new Set<string>()
  for (const ch of text.toLowerCase()) {
    if (ch === ' ' || ch === '\n' || ch === '\t') continue
    if (!(ch in MORSE_MAP)) out.add(ch)
  }
  return [...out]
}

// -------- AES-GCM via WebCrypto --------
export async function aesGcmEncrypt(plaintext: string, password: string) {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(plaintext))
  return {
    ciphertext: bytesToB64(new Uint8Array(ciphertext)),
    iv: bytesToHex(iv),
    salt: bytesToHex(salt),
  }
}

export async function aesGcmDecrypt(ciphertextB64: string, password: string, ivHex: string, saltHex: string) {
  const iv = hexToBytes(ivHex)
  const salt = hexToBytes(saltHex)
  const key = await deriveKey(password, salt)
  const bytes = b64ToBytes(ciphertextB64)
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, bytes)
  return dec.decode(plain)
}

async function deriveKey(password: string, salt: Uint8Array) {
  const material = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey'])
  // Cast: TS lib.dom récente type Uint8Array comme Uint8Array<ArrayBufferLike>,
  // mais SubtleCrypto.deriveKey attend un BufferSource basé sur ArrayBuffer pur.
  // Cast vers BufferSource compatible runtime.
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: salt as BufferSource, iterations: 200_000, hash: 'SHA-256' },
    material,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

// -------- RSA (OAEP encrypt / PSS sign) --------
export async function rsaGenerateKey(bits = 2048) {
  return crypto.subtle.generateKey(
    { name: 'RSA-OAEP', modulusLength: bits, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' },
    true,
    ['encrypt', 'decrypt'],
  ) as Promise<CryptoKeyPair>
}

export async function rsaEncrypt(publicKey: CryptoKey, plaintext: string) {
  const ct = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, publicKey, enc.encode(plaintext))
  return bytesToB64(new Uint8Array(ct))
}

export async function rsaDecrypt(privateKey: CryptoKey, ciphertextB64: string) {
  const pt = await crypto.subtle.decrypt({ name: 'RSA-OAEP' }, privateKey, b64ToBytes(ciphertextB64))
  return dec.decode(pt)
}

export async function exportKeyPem(key: CryptoKey, format: 'spki' | 'pkcs8') {
  const buf = await crypto.subtle.exportKey(format, key)
  const b64 = bytesToB64(new Uint8Array(buf))
  const label = format === 'spki' ? 'PUBLIC KEY' : 'PRIVATE KEY'
  const lines = b64.match(/.{1,64}/g)?.join('\n') || b64
  return `-----BEGIN ${label}-----\n${lines}\n-----END ${label}-----`
}

// -------- Diffie-Hellman pédagogique (petits primes, pas pour vrai usage) --------
export function modPow(base: bigint, exp: bigint, mod: bigint): bigint {
  let result = 1n
  let b = base % mod
  let e = exp
  while (e > 0n) {
    if (e & 1n) result = (result * b) % mod
    e >>= 1n
    b = (b * b) % mod
  }
  return result
}

export function dhDemo(p = 23n, g = 5n, aPriv = 6n, bPriv = 15n) {
  const A = modPow(g, aPriv, p)
  const B = modPow(g, bPriv, p)
  const sharedFromA = modPow(B, aPriv, p)
  const sharedFromB = modPow(A, bPriv, p)
  return { p, g, aPriv, bPriv, A, B, sharedFromA, sharedFromB, ok: sharedFromA === sharedFromB }
}

// -------- helpers bytes --------
function bytesToB64(b: Uint8Array) {
  let s = ''
  for (const byte of b) s += String.fromCharCode(byte)
  return btoa(s)
}
function b64ToBytes(b64: string) {
  const s = atob(b64)
  const out = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i)
  return out
}
function bytesToHex(b: Uint8Array) {
  return Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('')
}
function hexToBytes(hex: string) {
  const clean = hex.replace(/[^0-9a-fA-F]/g, '')
  const out = new Uint8Array(clean.length / 2)
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16)
  return out
}
