// Wi-Fi handshake sim — simulateur pédagogique d'attaque WPA2 4-way handshake.
//
// PRINCIPE :
//   - WPA2-PSK utilise PBKDF2 sur la passphrase pour dériver la PMK (Pairwise
//     Master Key) : PMK = PBKDF2(passphrase, SSID, 4096, 32 bytes).
//   - Le 4-way handshake échange deux nonces (ANonce, SNonce) + AP MAC + STA
//     MAC + PMK pour calculer la PTK. Les 2 derniers messages contiennent un
//     MIC HMAC-SHA1 de la passphrase candidate.
//   - Un attaquant capture le handshake (.pcap) puis brute-force : pour
//     chaque candidate passphrase, derive PMK → PTK → MIC, compare au MIC
//     capturé. Match = passphrase trouvée.
//
// Ce module SIMULE ce processus côté browser :
//   - on calcule la vraie PBKDF2 via WebCrypto (donc pas un faux scoring).
//   - on génère un faux handshake "capturé" depuis une vraie passphrase secrète.
//   - on essaie un dictionnaire de candidates et on cherche le match.
//
// Module strictement pédagogique. Ne s'utilise PAS sur un vrai handshake
// capturé d'un réseau qui ne t'appartient pas.

export type SimHandshake = {
  ssid: string
  /** Hash hex de la PMK secrète (pour pédagogie — un vrai handshake stocke le MIC, pas le PMK). */
  pmkHash: string
  /** SSID + 4-way nonces capturés (fictifs). */
  apMac: string
  staMac: string
  aNonce: string
  sNonce: string
  capturedAt: number
}

export type CrackResult = {
  found: boolean
  passphrase?: string
  attempts: number
  durationMs: number
  /** Liste des tentatives faites (pour log/UI). */
  log: Array<{ candidate: string; matched: boolean }>
}

/**
 * Dérive la PMK WPA2 à partir d'une passphrase + SSID.
 * PMK = PBKDF2-HMAC-SHA1(passphrase, ssid, 4096, 32).
 */
export async function derivePMK(passphrase: string, ssid: string): Promise<Uint8Array> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('WebCrypto SubtleCrypto requis pour dériver la PMK.')
  }
  const enc = new TextEncoder()
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    enc.encode(passphrase),
    { name: 'PBKDF2' },
    false,
    ['deriveBits'],
  )
  const bits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: enc.encode(ssid),
      iterations: 4096,
      hash: 'SHA-1',
    },
    keyMaterial,
    256, // 32 bytes
  )
  return new Uint8Array(bits)
}

/**
 * Hash hex d'un buffer (utile pour comparer PMK).
 */
export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Forge un faux handshake "capturé" à partir d'une vraie passphrase.
 * On stocke le hash de la PMK pour permettre la comparaison sans stocker
 * la passphrase elle-même (réaliste — un vrai handshake contient juste les
 * messages + MIC, pas la PMK).
 */
export async function forgeCapturedHandshake(passphrase: string, ssid: string): Promise<SimHandshake> {
  const pmk = await derivePMK(passphrase, ssid)
  const pmkHash = bytesToHex(pmk)
  // Nonces et MACs fictifs (mais déterministes selon SSID pour reproductibilité demo).
  const seed = ssid.split('').reduce((h, c) => ((h << 5) - h + c.charCodeAt(0)) | 0, 0)
  const genHex = (n: number, offset: number): string => {
    let s = ''
    for (let i = 0; i < n; i += 1) {
      const b = (Math.abs(seed * 31 + offset + i * 7) % 256)
      s += b.toString(16).padStart(2, '0')
    }
    return s
  }
  return {
    ssid,
    pmkHash,
    apMac: ['00', '11', '22', '33', '44', '55'].join(':'),
    staMac: ['aa', 'bb', 'cc', 'dd', 'ee', 'ff'].join(':'),
    aNonce: genHex(32, 100),
    sNonce: genHex(32, 200),
    capturedAt: Date.now(),
  }
}

/**
 * Tente de cracker un handshake avec un dictionnaire.
 * Retourne le résultat + log des tentatives.
 */
export async function crackHandshake(
  handshake: SimHandshake,
  dictionary: string[],
  options: { signal?: AbortSignal; onProgress?: (i: number, total: number, candidate: string) => void } = {},
): Promise<CrackResult> {
  const start = performance.now()
  const log: CrackResult['log'] = []
  let found: string | undefined
  for (let i = 0; i < dictionary.length; i += 1) {
    if (options.signal?.aborted) break
    const candidate = dictionary[i]
    options.onProgress?.(i, dictionary.length, candidate)
    try {
      const pmk = await derivePMK(candidate, handshake.ssid)
      const matched = bytesToHex(pmk) === handshake.pmkHash
      log.push({ candidate, matched })
      if (matched) {
        found = candidate
        break
      }
    } catch {
      log.push({ candidate, matched: false })
    }
  }
  return {
    found: !!found,
    passphrase: found,
    attempts: log.length,
    durationMs: performance.now() - start,
    log,
  }
}

/**
 * Dictionnaire pédagogique court (top 20 mots de passe WiFi communs).
 * Inclut volontairement plusieurs candidats susceptibles d'être la cible
 * du forgeCapturedHandshake demo (eg. "motdepasse").
 */
export const DEMO_DICTIONARY: readonly string[] = [
  'password', '12345678', 'qwerty12', 'admin123', 'motdepasse',
  'azerty12', 'soleil123', 'bonjour1', 'internet1', 'wifi1234',
  'monwifi123', 'freebox1', 'orange12', 'sfr-wifi1', 'livebox',
  'changeme', 'welcome1', 'iloveyou', 'football', 'aurorawifi',
]
