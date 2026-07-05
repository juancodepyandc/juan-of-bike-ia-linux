// Vérificateur "have-i-been-pwned" offline :
//  - liste de patterns extraits de breaches connus (RockYou, LinkedIn,
//    Yahoo, Adobe) sans télécharger les 10 GB des hashes officiels.
//  - check par préfixe de hash SHA-1 (k-anonymity, comme HIBP API mais
//    sans réseau) — l'app peut ensuite pinger l'API officielle.
//  - audit "credential reuse" : détecte si le mot de passe est une
//    variante simple d'un identifiant donné.
//
// Module éducatif : ne pas se substituer à un vrai check HIBP en prod.

const TOP_BREACHED_PASSWORDS = new Set([
  '123456', 'password', '12345678', '1234567890', 'qwerty', '111111',
  '123456789', 'abc123', 'password1', '123123', 'admin', 'letmein',
  'monkey', 'dragon', 'sunshine', 'iloveyou', 'princess', '1234',
  'football', 'shadow', 'master', 'superman', 'qwerty123', 'welcome',
  'azerty', 'azerty123', 'motdepasse', 'soleil', 'doudou', 'amour',
  'bonjour', 'francais', 'paris', 'france', 'cheri', 'cherie',
])

const COMMON_TRANSFORMS = [
  { from: 'a', to: '@' },
  { from: 'o', to: '0' },
  { from: 'i', to: '1' },
  { from: 'e', to: '3' },
  { from: 's', to: '$' },
  { from: 'l', to: '!' },
]

export type BreachReport = {
  /** True si le mot de passe (ou une variante triviale) est dans la liste. */
  isBreached: boolean
  /** Variante exacte trouvée si différente de l'original. */
  matchedAs: string | null
  /** Type de transformation détecté. */
  transformation: 'exact' | 'leet' | 'suffix' | 'prefix' | 'capitalized' | null
  /** Recommandations. */
  recommendations: string[]
}

export function checkBreached(password: string): BreachReport {
  if (!password) {
    return { isBreached: false, matchedAs: null, transformation: null, recommendations: [] }
  }
  const lower = password.toLowerCase()
  if (TOP_BREACHED_PASSWORDS.has(lower)) {
    return {
      isBreached: true,
      matchedAs: lower,
      transformation: 'exact',
      recommendations: [
        'Ce mot de passe est dans les Top 10 des breaches mondiales.',
        'Changer IMMÉDIATEMENT partout où il est utilisé.',
        'Activer 2FA.',
        'Utiliser un gestionnaire de mots de passe.',
      ],
    }
  }
  // Capitalisation
  if (TOP_BREACHED_PASSWORDS.has(password.charAt(0).toLowerCase() + password.slice(1).toLowerCase())) {
    return {
      isBreached: true,
      matchedAs: password,
      transformation: 'capitalized',
      recommendations: ['Mettre une majuscule au début ne protège pas — base reste dans les breaches.'],
    }
  }
  // Leet : inverse les transformations courantes
  let deLeeted = lower
  for (const t of COMMON_TRANSFORMS) deLeeted = deLeeted.split(t.to).join(t.from)
  if (TOP_BREACHED_PASSWORDS.has(deLeeted)) {
    return {
      isBreached: true,
      matchedAs: deLeeted,
      transformation: 'leet',
      recommendations: ['Le leetspeak (a→@, o→0…) est connu des wordlists modernes.'],
    }
  }
  // Suffix numérique
  const suffixMatch = /^(.+?)(\d{1,4})$/.exec(lower)
  if (suffixMatch && TOP_BREACHED_PASSWORDS.has(suffixMatch[1])) {
    return {
      isBreached: true,
      matchedAs: suffixMatch[1],
      transformation: 'suffix',
      recommendations: ['Ajouter "123" / "2024" ne suffit pas — pattern bien connu des crackers.'],
    }
  }
  // Prefix
  const prefixMatch = /^(\d{1,4})(.+)$/.exec(lower)
  if (prefixMatch && TOP_BREACHED_PASSWORDS.has(prefixMatch[2])) {
    return {
      isBreached: true,
      matchedAs: prefixMatch[2],
      transformation: 'prefix',
      recommendations: ['Préfixer par des chiffres est un pattern habituel.'],
    }
  }
  return { isBreached: false, matchedAs: null, transformation: null, recommendations: [] }
}

/**
 * Détecte credential reuse : password contient l'identifiant (username,
 * email) ou trivial dérivé.
 */
export function checkCredentialReuse(password: string, identifier: string): { reused: boolean; warning: string | null } {
  if (!password || !identifier) return { reused: false, warning: null }
  const pw = password.toLowerCase()
  const id = identifier.toLowerCase().split('@')[0] // strip domain si email
  if (id.length < 3) return { reused: false, warning: null }
  if (pw.includes(id)) {
    return { reused: true, warning: `Le mot de passe contient le username/email "${id}" — trivial à deviner.` }
  }
  // Reverse
  const reversed = id.split('').reverse().join('')
  if (pw.includes(reversed) && reversed.length >= 4) {
    return { reused: true, warning: `Le mot de passe contient l'identifiant inversé "${reversed}".` }
  }
  return { reused: false, warning: null }
}

/**
 * Vrai HIBP utilise un check k-anonymity : envoie les 5 premiers hex du hash
 * SHA-1 et reçoit la liste de tous les hashes commençant par ce préfixe.
 * Comparaison locale du suffixe.
 *
 * Cette fonction prépare le PRÉFIXE à envoyer (suffix gardé local).
 */
export async function preparePwnedRangeQuery(password: string): Promise<{ prefix: string; suffix: string } | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null
  const enc = new TextEncoder()
  const data = enc.encode(password)
  const buf = await crypto.subtle.digest('SHA-1', data)
  const hex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('').toUpperCase()
  return {
    prefix: hex.slice(0, 5),
    suffix: hex.slice(5),
  }
}

/**
 * Match un suffixe parmi une réponse HIBP-style (lignes "SUFFIXE:count").
 * Renvoie le count d'occurrences si trouvé, 0 sinon.
 */
export function matchPwnedSuffix(localSuffix: string, hibpResponse: string): number {
  const lines = hibpResponse.split(/\r?\n/)
  for (const line of lines) {
    const [suffix, count] = line.split(':')
    if (suffix?.toUpperCase() === localSuffix.toUpperCase()) {
      return parseInt(count, 10) || 0
    }
  }
  return 0
}
