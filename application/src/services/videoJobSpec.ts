/**
 * VideoJobSpec — miroir TypeScript du contrat canonique défini côté Python
 * dans `application/python-services/video_job_spec.py`.
 *
 * IMPORTANT parité : le `spec_hash` calculé ici DOIT être byte-à-byte
 * identique à celui produit par `VideoJobSpec.spec_hash()` en Python pour
 * une spec équivalente. Toute divergence est un bug de parité — traqué par
 * `src/__tests__/videoSpecParity.test.ts` qui charge des fixtures générées
 * par Python et vérifie que ce module produit les mêmes hashes.
 *
 * Discipline commune (identique côté Python) :
 *   - clés triées,
 *   - séparateurs sans espace : `,` et `:`,
 *   - non-ASCII conservé (pas d'échappement `\u`),
 *   - floats arrondis à 6 décimales,
 *   - `created_at` exclu du hash,
 *   - SHA-256 hex minuscule.
 */

export const SPEC_VERSION = 1

export interface VideoJobSpec {
  prompt: string
  prompt_composed: string
  negative_prompt: string | null
  width: number
  height: number
  delivered_width: number
  delivered_height: number
  num_frames: number
  fps: number
  model_id: string
  num_inference_steps: number
  guidance_scale: number
  quality_mode: 'auto' | 'balanced' | 'premium'
  force_strategy: 'auto' | 'wan5b' | 'ltx'
  motion_interp: 0 | 1 | 2
  profile: string
  seed: number
  image_path: string | null
  spec_version: number
  created_at: number
}

// ── canonicalisation ────────────────────────────────────────────────────

/** Sérialisation canonique (miroir de json.dumps sort_keys+separators sans espace). */
function canonicalStringify(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') {
    // Python round() renvoie un int/float ; l'arrondi 6 décimales est
    // appliqué AVANT ; ici on formate. Utilise JSON.stringify pour rester
    // conforme au dialecte JSON standard (mais pas la notation scientifique
    // pour les entiers).
    return JSON.stringify(value)
  }
  if (typeof value === 'string') {
    // Doit produire le même échappement que Python `ensure_ascii=False`.
    // JSON.stringify ne échappe pas non-ASCII par défaut — ok.
    return JSON.stringify(value)
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalStringify).join(',') + ']'
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value as Record<string, unknown>).sort()
    const parts: string[] = []
    for (const k of keys) {
      const v = (value as Record<string, unknown>)[k]
      parts.push(JSON.stringify(k) + ':' + canonicalStringify(v))
    }
    return '{' + parts.join(',') + '}'
  }
  return 'null'
}

/** Retourne une représentation canonique (mêmes règles que Python), hors created_at. */
export function toCanonicalDict(spec: VideoJobSpec): Record<string, unknown> {
  const d: Record<string, unknown> = { ...spec }
  delete d.created_at
  // Arrondit tous les floats à 6 décimales (miroir de la boucle Python).
  for (const k of Object.keys(d)) {
    const v = d[k]
    if (typeof v === 'number' && !Number.isInteger(v)) {
      d[k] = Math.round(v * 1e6) / 1e6
    }
  }
  return d
}

// ── sha256 ──────────────────────────────────────────────────────────────
//
// Pas de dépendance externe (les artefacts front peuvent tourner en Vite
// dev, dans Node --test, dans Tauri). Implémentation SHA-256 pure.
// Petite (~120 lignes) mais suffisante et testée par la parité elle-même
// (le fixture Python valide le hash byte-à-byte, donc toute erreur dans
// cet SHA-256 casse le test — c'est la garantie).

function rotr(n: number, x: number): number {
  return ((x >>> n) | (x << (32 - n))) >>> 0
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
])

function sha256(bytes: Uint8Array): string {
  const l = bytes.length
  const withOne = new Uint8Array(l + 1 + ((56 - ((l + 1) % 64) + 64) % 64) + 8)
  withOne.set(bytes)
  withOne[l] = 0x80
  const bitLen = BigInt(l) * 8n
  const dv = new DataView(withOne.buffer)
  dv.setBigUint64(withOne.length - 8, bitLen)

  const H = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ])

  const W = new Uint32Array(64)
  for (let i = 0; i < withOne.length; i += 64) {
    for (let t = 0; t < 16; t += 1) W[t] = dv.getUint32(i + t * 4)
    for (let t = 16; t < 64; t += 1) {
      const s0 = rotr(7, W[t - 15]) ^ rotr(18, W[t - 15]) ^ (W[t - 15] >>> 3)
      const s1 = rotr(17, W[t - 2]) ^ rotr(19, W[t - 2]) ^ (W[t - 2] >>> 10)
      W[t] = (W[t - 16] + s0 + W[t - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, h] = H
    for (let t = 0; t < 64; t += 1) {
      const S1 = rotr(6, e) ^ rotr(11, e) ^ rotr(25, e)
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + S1 + ch + K[t] + W[t]) >>> 0
      const S0 = rotr(2, a) ^ rotr(13, a) ^ rotr(22, a)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (S0 + maj) >>> 0
      h = g
      g = f
      f = e
      e = (d + temp1) >>> 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) >>> 0
    }
    H[0] = (H[0] + a) >>> 0
    H[1] = (H[1] + b) >>> 0
    H[2] = (H[2] + c) >>> 0
    H[3] = (H[3] + d) >>> 0
    H[4] = (H[4] + e) >>> 0
    H[5] = (H[5] + f) >>> 0
    H[6] = (H[6] + g) >>> 0
    H[7] = (H[7] + h) >>> 0
  }

  return Array.from(H)
    .map((n) => n.toString(16).padStart(8, '0'))
    .join('')
}

function utf8Encode(s: string): Uint8Array {
  // Uses TextEncoder when available (Node 22 + browsers all have it).
  return new TextEncoder().encode(s)
}

export function specHash(spec: VideoJobSpec): string {
  const canonical = toCanonicalDict(spec)
  const payload = canonicalStringify(canonical)
  return sha256(utf8Encode(payload))
}
