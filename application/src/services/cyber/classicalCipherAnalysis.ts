// Analyse cryptographique classique : détection automatique du chiffrement
// utilisé (César, Vigenère, ROT, transposition, XOR), analyse de fréquence,
// score de chi-square contre la distribution FR, casse automatique.
//
// Niveau "CTF easy" — pédagogique. Pas pour casser des clés modernes.

const FR_LETTER_FREQ: Record<string, number> = {
  a: 0.0814, b: 0.0090, c: 0.0334, d: 0.0367, e: 0.1715, f: 0.0107,
  g: 0.0087, h: 0.0074, i: 0.0758, j: 0.0061, k: 0.0007, l: 0.0548,
  m: 0.0297, n: 0.0709, o: 0.0582, p: 0.0290, q: 0.0136, r: 0.0655,
  s: 0.0791, t: 0.0724, u: 0.0631, v: 0.0167, w: 0.0004, x: 0.0042,
  y: 0.0033, z: 0.0014,
}

const EN_LETTER_FREQ: Record<string, number> = {
  a: 0.0816, b: 0.0149, c: 0.0278, d: 0.0425, e: 0.1270, f: 0.0223,
  g: 0.0202, h: 0.0609, i: 0.0697, j: 0.0015, k: 0.0077, l: 0.0403,
  m: 0.0241, n: 0.0675, o: 0.0751, p: 0.0193, q: 0.0010, r: 0.0599,
  s: 0.0633, t: 0.0906, u: 0.0276, v: 0.0098, w: 0.0236, x: 0.0015,
  y: 0.0197, z: 0.0007,
}

export type LetterFrequency = Record<string, number>

/** Renvoie les fréquences relatives des 26 lettres latines. */
export function frequencyAnalysis(text: string): LetterFrequency {
  const counts: LetterFrequency = {}
  for (let c = 'a'.charCodeAt(0); c <= 'z'.charCodeAt(0); c += 1) counts[String.fromCharCode(c)] = 0
  let total = 0
  for (const ch of text.toLowerCase()) {
    if (ch >= 'a' && ch <= 'z') {
      counts[ch] += 1
      total += 1
    }
  }
  if (total === 0) return counts
  for (const k of Object.keys(counts)) counts[k] /= total
  return counts
}

/** Index de coïncidence (Kasiski). Texte FR : ~0.0778, EN : ~0.0667, random : 0.0385. */
export function indexOfCoincidence(text: string): number {
  const counts: Record<string, number> = {}
  let total = 0
  for (const ch of text.toLowerCase()) {
    if (ch >= 'a' && ch <= 'z') {
      counts[ch] = (counts[ch] ?? 0) + 1
      total += 1
    }
  }
  if (total < 2) return 0
  let sum = 0
  for (const n of Object.values(counts)) sum += n * (n - 1)
  return sum / (total * (total - 1))
}

/** Chi-square vs distribution attendue. Plus le score est bas, mieux. */
export function chiSquareScore(text: string, lang: 'fr' | 'en' = 'fr'): number {
  const observed = frequencyAnalysis(text)
  const expected = lang === 'fr' ? FR_LETTER_FREQ : EN_LETTER_FREQ
  let chi = 0
  let totalLetters = 0
  for (const ch of text.toLowerCase()) if (ch >= 'a' && ch <= 'z') totalLetters += 1
  for (const letter of Object.keys(expected)) {
    const exp = (expected[letter] ?? 0) * totalLetters
    const obs = (observed[letter] ?? 0) * totalLetters
    if (exp > 0) chi += ((obs - exp) ** 2) / exp
  }
  return chi
}

export type CipherDetection = {
  /** Probabilité estimée [0..1] (plus haut = plus probable). */
  probability: number
  /** Cipher détecté. */
  type: 'plaintext-fr' | 'plaintext-en' | 'caesar' | 'rot13' | 'rot47' | 'atbash' | 'vigenere' | 'transposition' | 'xor' | 'base64' | 'base32' | 'hex' | 'binary' | 'unknown'
  /** Hint additionnel (clé estimée, période…). */
  hint?: string
}

const BASE64_RE = /^[A-Za-z0-9+/=\s]+$/
const BASE32_RE = /^[A-Z2-7=\s]+$/
const HEX_RE = /^[0-9a-fA-F\s]+$/
const BIN_RE = /^[01\s]+$/

/**
 * Détecte le type de chiffre par heuristiques cumulatives.
 */
export function detectCipher(text: string, expectedLang: 'fr' | 'en' = 'fr'): CipherDetection {
  if (!text || text.length < 4) return { probability: 0, type: 'unknown' }

  // Binary (testé en premier — set très restreint).
  const noSpaces = text.replace(/\s/g, '')
  if (noSpaces.length >= 16 && BIN_RE.test(text) && noSpaces.length % 8 === 0) {
    return { probability: 0.92, type: 'binary' }
  }
  // Hex (testé AVANT base64 car les hex strings matchent aussi le set base64).
  if (noSpaces.length > 12 && noSpaces.length % 2 === 0 && /^[0-9a-fA-F]+$/.test(noSpaces)) {
    return { probability: 0.85, type: 'hex' }
  }
  // Base32 : alphabet 2-7 + A-Z + '=', toujours majuscule.
  if (noSpaces.length >= 16 && noSpaces.length % 8 === 0 && BASE32_RE.test(text) && /[2-7]/.test(noSpaces)) {
    return { probability: 0.82, type: 'base32' }
  }
  // Base64 ?
  if (text.length > 16 && BASE64_RE.test(text) && text.length % 4 === 0 && /[+/=]|[A-Z]/.test(text)) {
    return { probability: 0.85, type: 'base64' }
  }

  // Index de coïncidence : FR ≈ 0.078, EN ≈ 0.067, Vigenère ≈ 0.04..0.05.
  const ic = indexOfCoincidence(text)
  // Seuil chi² tolérant : sur des textes courts, le chi² peut atteindre 60-80
  // sans pour autant être chiffré.
  const PLAIN_CHI_THRESHOLD = 150
  if (ic > 0.063) {
    const chiFr = chiSquareScore(text, 'fr')
    const chiEn = chiSquareScore(text, 'en')
    if (chiFr < chiEn && chiFr < PLAIN_CHI_THRESHOLD) return { probability: 0.9, type: 'plaintext-fr' }
    if (chiEn < chiFr && chiEn < PLAIN_CHI_THRESHOLD) return { probability: 0.9, type: 'plaintext-en' }
    // Atbash : test rapide — si atbash(text) a un chi² faible, c'est atbash.
    const atbashed = applyAtbash(text)
    const chiAtbash = Math.min(chiSquareScore(atbashed, 'fr'), chiSquareScore(atbashed, 'en'))
    if (chiAtbash < PLAIN_CHI_THRESHOLD) {
      return { probability: 0.78, type: 'atbash' }
    }
    // ROT47 : si l'input contient surtout des caractères ASCII printables non-alpha
    // (33..126), tester rot47.
    if (/[!@#$%^&*()+=<>?]/.test(text)) {
      const rot47ed = applyRot47(text)
      const chiR47 = Math.min(chiSquareScore(rot47ed, 'fr'), chiSquareScore(rot47ed, 'en'))
      if (chiR47 < PLAIN_CHI_THRESHOLD) {
        return { probability: 0.72, type: 'rot47' }
      }
    }
    // Sinon : monoalphabétique (César/ROT). On rapporte le shift de
    // CHIFFREMENT (cohérent avec crackCaesar).
    const decryptShift = guessCaesarShift(text, expectedLang)
    const encryptShift = (26 - decryptShift) % 26
    if (encryptShift === 13) return { probability: 0.8, type: 'rot13', hint: 'shift=13' }
    return { probability: 0.7, type: 'caesar', hint: `shift=${encryptShift}` }
  }
  if (ic > 0.045 && ic <= 0.063) {
    // Vigenère probable. Estime la période par Kasiski simplifié.
    const period = guessVigenerePeriod(text)
    return { probability: 0.7, type: 'vigenere', hint: `période ≈ ${period}` }
  }
  if (ic < 0.045) {
    // IC très bas : XOR multi-clé, ou compression/encryption moderne.
    return { probability: 0.5, type: 'xor', hint: 'IC très bas' }
  }
  return { probability: 0.3, type: 'unknown' }
}

/**
 * Cherche le décalage César qui minimise le chi-square vs lang attendu.
 */
export function guessCaesarShift(text: string, lang: 'fr' | 'en' = 'fr'): number {
  let bestShift = 0
  let bestChi = Infinity
  for (let s = 0; s < 26; s += 1) {
    const shifted = caesarShift(text, s)
    const chi = chiSquareScore(shifted, lang)
    if (chi < bestChi) {
      bestChi = chi
      bestShift = s
    }
  }
  return bestShift
}

/** Atbash : A↔Z, B↔Y, ... (involutif, self-inverse). */
export function applyAtbash(text: string): string {
  return text.replace(/[a-zA-Z]/g, (ch) => {
    const base = ch >= 'a' && ch <= 'z' ? 97 : 65
    return String.fromCharCode(base + (25 - (ch.charCodeAt(0) - base)))
  })
}

/** ROT47 : shift de 47 sur l'ASCII printable (33..126). Self-inverse. */
export function applyRot47(text: string): string {
  let out = ''
  for (const ch of text) {
    const code = ch.charCodeAt(0)
    if (code >= 33 && code <= 126) {
      out += String.fromCharCode(33 + ((code - 33 + 47) % 94))
    } else out += ch
  }
  return out
}

/** Décode base32 (RFC 4648). Renvoie texte UTF-8 ou null. */
export function decodeBase32(text: string): string | null {
  const clean = text.toUpperCase().replace(/[^A-Z2-7]/g, '')
  if (clean.length === 0) return null
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = 0
  let bitCount = 0
  const out: number[] = []
  for (const ch of clean) {
    const idx = alphabet.indexOf(ch)
    if (idx === -1) return null
    bits = (bits << 5) | idx
    bitCount += 5
    if (bitCount >= 8) {
      bitCount -= 8
      out.push((bits >> bitCount) & 0xff)
    }
  }
  try {
    return new TextDecoder('utf-8').decode(new Uint8Array(out))
  } catch {
    return null
  }
}

/** Décode binary (groups de 8 bits séparés). */
export function decodeBinary(text: string): string | null {
  const clean = text.replace(/\s/g, '')
  if (clean.length === 0 || clean.length % 8 !== 0 || !/^[01]+$/.test(clean)) return null
  let out = ''
  for (let i = 0; i < clean.length; i += 8) {
    const code = parseInt(clean.slice(i, i + 8), 2)
    out += String.fromCharCode(code)
  }
  return out
}

/** Applique un décalage César. shift positif = décalage vers la fin. */
export function caesarShift(text: string, shift: number): string {
  const s = ((shift % 26) + 26) % 26
  return text.replace(/[a-zA-Z]/g, (ch) => {
    const base = ch >= 'a' && ch <= 'z' ? 97 : 65
    return String.fromCharCode(((ch.charCodeAt(0) - base + s) % 26) + base)
  })
}

/**
 * Estime la période d'un Vigenère par Kasiski simplifié : cherche le k
 * (entre 2 et 12) qui maximise l'IC moyen des sous-séquences "tous les k".
 */
export function guessVigenerePeriod(text: string, maxPeriod = 12): number {
  const clean = text.toLowerCase().replace(/[^a-z]/g, '')
  const FR_IC = 0.0778
  // Recense tous les k qui produisent un IC sub ≈ FR_IC (texte FR retrouvé).
  // Prend le PLUS PETIT pour éviter qu'un multiple soit choisi (k=6 a un IC
  // similaire à k=3 parce que sample tous les 6 = sample tous les 3 sur 2
  // décalages distincts).
  const candidates: Array<{ k: number; avgIc: number }> = []
  for (let k = 2; k <= maxPeriod; k += 1) {
    let avgIc = 0
    for (let off = 0; off < k; off += 1) {
      let sub = ''
      for (let i = off; i < clean.length; i += k) sub += clean[i]
      avgIc += indexOfCoincidence(sub)
    }
    avgIc /= k
    candidates.push({ k, avgIc })
  }
  // Trie : meilleur IC, puis (à IC quasi-égal ±5%) plus petit k.
  candidates.sort((a, b) => b.avgIc - a.avgIc)
  if (candidates.length === 0) return 1
  const topIc = candidates[0].avgIc
  const close = candidates.filter((c) => c.avgIc >= topIc * 0.95)
  close.sort((a, b) => a.k - b.k)
  return close[0].k
}

/**
 * Casse complète d'un César : retourne le texte décalé optimal pour
 * la langue cible. `shift` retourné = shift de CHIFFREMENT original
 * (positif applique +s pour encrypter, -s pour décrypter).
 */
export function crackCaesar(ciphertext: string, lang: 'fr' | 'en' = 'fr'): { plaintext: string; shift: number; chiSquare: number } {
  // guessCaesarShift renvoie le shift à appliquer pour DÉCHIFFRER.
  // Le shift de chiffrement original est donc (26 - decryptShift) % 26.
  const decryptShift = guessCaesarShift(ciphertext, lang)
  const plaintext = caesarShift(ciphertext, decryptShift)
  const encryptShift = (26 - decryptShift) % 26
  return { plaintext, shift: encryptShift, chiSquare: chiSquareScore(plaintext, lang) }
}

/** Décode base64. Pour le ciphertext analysis. Marche en browser (atob)
 * comme en Node. */
export function decodeBase64(text: string): string | null {
  try {
    const t = text.trim()
    // Path Node : Buffer dispo. Path browser : atob.
    if (typeof Buffer !== 'undefined') return Buffer.from(t, 'base64').toString('utf-8')
    const binary = atob(t)
    // UTF-8 decode via TextDecoder
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
    return new TextDecoder('utf-8').decode(bytes)
  } catch {
    return null
  }
}

/** Décode hex. */
export function decodeHex(text: string): string | null {
  const clean = text.replace(/\s/g, '')
  if (clean.length % 2 !== 0) return null
  try {
    if (typeof Buffer !== 'undefined') return Buffer.from(clean, 'hex').toString('utf-8')
    const bytes = new Uint8Array(clean.length / 2)
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16)
    }
    return new TextDecoder('utf-8').decode(bytes)
  } catch {
    return null
  }
}

// Permet d'utiliser Buffer côté Node sans erreur TS quand types/node absent.
declare const Buffer: undefined | { from: (data: string, encoding: string) => { toString: (enc: string) => string } }

/**
 * Single-byte XOR : essaie toutes les clés 0..255 et garde celle qui produit
 * le texte le PLUS plausible.
 *
 * Le scoring : log-probabilité de chaque caractère selon la distribution
 * cible. Pour chaque char dans le décodage, on ajoute log(p[letter]). Le
 * meilleur key maximise ce score (= minimise -log p). C'est BEAUCOUP plus
 * robuste que le chi² qui suppose un texte long déjà similaire à la cible.
 *
 * Filtre additionnel : on rejette les keys qui produisent un ratio
 * lettres ASCII (a-z + A-Z + espace) < 80 %.
 */
export function crackSingleByteXor(buf: Uint8Array, lang: 'fr' | 'en' = 'fr'): { plaintext: string; key: number; score: number } {
  const freqRef = lang === 'fr' ? FR_LETTER_FREQ : EN_LETTER_FREQ
  // Précalcule les log-probabilités. Petite probabilité pour les lettres
  // hors-table (apostrophes, espaces) pour éviter -Infinity.
  const logProb: Record<string, number> = {}
  for (const k of Object.keys(freqRef)) logProb[k] = Math.log(Math.max(1e-6, freqRef[k]))
  const SPACE_LOG = Math.log(0.18) // espace ≈ 18 % d'un texte FR/EN
  const OTHER_LOG = Math.log(1e-6) // pénalise fortement le bruit

  let bestKey = 0
  let bestScore = -Infinity
  let bestText = ''
  for (let key = 0; key < 256; key += 1) {
    let text = ''
    let asciiLetters = 0
    for (const b of buf) {
      const c = b ^ key
      text += String.fromCharCode(c)
      if ((c >= 0x41 && c <= 0x5a) || (c >= 0x61 && c <= 0x7a) || c === 0x20) asciiLetters += 1
    }
    if (asciiLetters / buf.length < 0.8) continue
    let score = 0
    for (const ch of text.toLowerCase()) {
      if (ch >= 'a' && ch <= 'z') score += logProb[ch] ?? OTHER_LOG
      else if (ch === ' ') score += SPACE_LOG
      else score += OTHER_LOG
    }
    if (score > bestScore) {
      bestScore = score
      bestKey = key
      bestText = text
    }
  }
  return { plaintext: bestText, key: bestKey, score: bestScore }
}
