// Catalogue de vulnérabilités cryptographiques courantes — version éducative
// uniquement. Aucune charge utile exploitable, seulement la pédagogie.
//
// Les "demos" servent de support visuel pour la lab view : montrer pourquoi
// ECB déchire les images, comment un padding oracle révèle un octet par
// requête, etc. Tout est en mémoire dans la page.
//
// CLAUDE.md du module : défensif / éducatif uniquement.

export type VulnSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical'

export type CryptoVulnerability = {
  id: string
  title: string
  severity: VulnSeverity
  category:
    | 'mode-confidentialite'
    | 'integrite'
    | 'reuse'
    | 'parametre-faible'
    | 'protocole'
    | 'side-channel'
  /** Pourquoi c'est cassé. Vulgarisation niveau STI2D. */
  description: string
  /** Détail technique avec équations / pseudo-code. */
  technical: string
  /** Comment se défendre. */
  remediation: string
  /** CVE/CVSS/référence académique. */
  references: string[]
  /** Données illustratives pour la démo (toujours sûres). */
  demo?: {
    label: string
    /** Texte ou image base64 ou structure attendue par la vue. */
    payload: string
  }
}

export const CRYPTO_VULNERABILITIES: readonly CryptoVulnerability[] = [
  {
    id: 'aes-ecb-pattern-leak',
    title: 'AES-ECB : fuites de motifs',
    severity: 'high',
    category: 'mode-confidentialite',
    description:
      "Le mode ECB chiffre chaque bloc indépendamment avec la MÊME clé. Deux blocs identiques en clair donnent deux blocs identiques chiffrés. Sur une image, les zones uniformes restent visibles après chiffrement.",
    technical:
      "C_i = E_K(P_i). Aucune dépendance entre blocs ↦ patterns conservés. Démonstration célèbre : 'ECB penguin' (image de Tux chiffrée en ECB).",
    remediation:
      "Utiliser CBC + IV aléatoire pour la confidentialité héritée, ou mieux : GCM, ChaCha20-Poly1305 (AEAD).",
    references: ['NIST SP 800-38A', 'OWASP Cryptographic Storage'],
    demo: { label: 'Image Tux ECB vs CBC', payload: 'tux-ecb-vs-cbc-svg' },
  },
  {
    id: 'cbc-padding-oracle',
    title: 'CBC : padding oracle',
    severity: 'critical',
    category: 'integrite',
    description:
      "Un serveur qui répond 'padding invalide' vs 'pas trouvé' permet de déchiffrer 1 octet par ~128 requêtes. AES-CBC sans MAC = vulnérable.",
    technical:
      "Padding PKCS#7 : l'attaquant joue avec l'IV ou le bloc précédent pour faire valider chaque octet du dernier bloc. Itération : 1 octet × 16 / bloc / 128 tentatives.",
    remediation:
      "Encrypt-then-MAC avec un MAC à temps constant, ou AEAD (GCM, ChaCha20-Poly1305). Renvoyer une erreur uniforme côté serveur.",
    references: ['Vaudenay 2002', 'POODLE CVE-2014-3566'],
  },
  {
    id: 'ctr-nonce-reuse',
    title: 'CTR/GCM : réutilisation du nonce',
    severity: 'critical',
    category: 'reuse',
    description:
      "En CTR (donc GCM), réutiliser le même nonce avec la même clé révèle le XOR des deux clairs. Pour GCM : la clé d'authentification fuit aussi ↦ forge possible.",
    technical:
      "C1 ⊕ C2 = P1 ⊕ P2. Pour GCM : H = AES_K(0). Deux messages avec le même nonce ↦ système d'équations linéaires en H résolu sur GF(2^128).",
    remediation:
      "Compteur croissant ou nonce aléatoire 96 bits dédié. Re-keyer avant 2^32 messages par clé. Préférer XChaCha20-Poly1305 si nonces aléatoires.",
    references: ['Joux 2006', 'NIST SP 800-38D'],
  },
  {
    id: 'rsa-textbook-no-padding',
    title: 'RSA "textbook" sans padding',
    severity: 'high',
    category: 'parametre-faible',
    description:
      "RSA brut (c = m^e mod n) est déterministe ET malléable. Mêmes clairs ↦ mêmes chiffrés. Multiplier le chiffré par 2^e mod n multiplie le clair par 2.",
    technical:
      "Manque d'IND-CPA. Solution : OAEP (Optimal Asymmetric Encryption Padding) pour le chiffrement, PSS pour la signature.",
    remediation:
      "Toujours utiliser RSA-OAEP (chiffrement) ou RSA-PSS (signature). Préférer Curve25519/Ed25519 si possible.",
    references: ['PKCS#1 v2.2', 'Bleichenbacher 1998'],
  },
  {
    id: 'sha1-collision',
    title: 'SHA-1 : collisions pratiques',
    severity: 'high',
    category: 'integrite',
    description:
      "SHAttered (2017) a produit deux PDF avec le même hash SHA-1. Coût : ~110 GPU-an ↦ accessible aux États. Signatures et certificats SHA-1 = obsolètes.",
    technical:
      "Attaque par construction de collisions identiques préfixe + diff suffix, exploitant la structure Merkle-Damgård + faiblesses différentielles.",
    remediation:
      "Migrer vers SHA-256 ou SHA-3. Pour les vieux protocoles : Blake2b ou Blake3.",
    references: ['Stevens et al. 2017 — SHAttered', 'NIST deprecation 2011'],
  },
  {
    id: 'tls-downgrade-renegotiate',
    title: 'TLS : downgrade et renegotiation',
    severity: 'high',
    category: 'protocole',
    description:
      "Un attaquant MITM force le client à utiliser TLS 1.0/SSL 3.0 (POODLE, FREAK). Anciennes cipher suites = vulnérables.",
    technical:
      "Pendant la phase ClientHello, l'attaquant intercepte et modifie la liste des versions et ciphers supportés.",
    remediation:
      "TLS 1.3 minimum côté serveur, désactiver TLS 1.0/1.1, mode strict. HSTS + Cert Transparency.",
    references: ['RFC 8446 — TLS 1.3', 'POODLE CVE-2014-3566', 'FREAK CVE-2015-0204'],
  },
  {
    id: 'jwt-alg-none',
    title: 'JWT : alg=none',
    severity: 'critical',
    category: 'protocole',
    description:
      "Certaines bibliothèques JWT acceptent un token avec `alg: 'none'`, ce qui désactive la signature ↦ un attaquant forge n'importe quel token.",
    technical:
      "Le header `{\"alg\":\"none\"}` indique 'pas de signature'. Si le serveur ne whitelist pas explicitement les algorithmes, il accepte des tokens forgés.",
    remediation:
      "Toujours configurer la lib JWT avec une whitelist (`['HS256', 'RS256']`). Préférer Paseto si possible.",
    references: ['Auth0 advisory 2015', 'OWASP JWT Cheat Sheet'],
  },
  {
    id: 'timing-attack-string-compare',
    title: 'Comparaison de chaînes : timing attack',
    severity: 'medium',
    category: 'side-channel',
    description:
      "`==` ou `strcmp` court-circuite à la première différence. La durée varie selon le nombre de caractères corrects ↦ permet de deviner un secret octet par octet sur le réseau (millions de requêtes).",
    technical:
      "for (let i = 0; i < min; i++) if (a[i] !== b[i]) return false  ← branchement non-constant.",
    remediation:
      "Utiliser `crypto.timingSafeEqual` (Node) ou équivalent constant-time. Toujours hasher les secrets côté serveur.",
    references: ['Brumley & Boneh 2003', 'crypto.timingSafeEqual'],
  },
  {
    id: 'random-math-random',
    title: 'Aléa non-cryptographique (`Math.random`)',
    severity: 'high',
    category: 'parametre-faible',
    description:
      "Math.random() utilise xorshift128+ — prévisible avec 5 sorties (Klochkov 2015). Inutilisable pour tokens, mots de passe, sels.",
    technical:
      "Le générateur a un état interne de 128 bits récupérable par solveur linéaire à partir de quelques tirages.",
    remediation:
      "Toujours `crypto.getRandomValues(new Uint32Array(n))` ou `crypto.randomBytes(n)` côté Node.",
    references: ['ES2015 spec', 'Klochkov et al. 2015'],
  },
  {
    id: 'argon2-low-memory',
    title: 'Argon2 sous-paramétré (m < 19 MiB)',
    severity: 'medium',
    category: 'parametre-faible',
    description:
      "Argon2 perd son avantage 'memory-hard' si la mémoire est trop faible. Avec m=4MiB, un ASIC retrouve la vitesse d'un GPU.",
    technical:
      "Coût attaquant ∝ 1/m × 1/t. Pour neutraliser un attaquant avec budget $10k, viser m ≥ 64MiB.",
    remediation:
      "OWASP 2024 : argon2id m=64MiB, t=3, p=1. Si trop coûteux ↦ m=19MiB, t=2 minimum.",
    references: ['RFC 9106', 'OWASP Password Storage 2024'],
  },
]

export function findVulnerability(id: string): CryptoVulnerability | undefined {
  return CRYPTO_VULNERABILITIES.find((v) => v.id === id)
}

export function vulnerabilitiesByCategory(category: CryptoVulnerability['category']): CryptoVulnerability[] {
  return CRYPTO_VULNERABILITIES.filter((v) => v.category === category)
}

export function vulnerabilitiesAtLeast(severity: VulnSeverity): CryptoVulnerability[] {
  const order: VulnSeverity[] = ['info', 'low', 'medium', 'high', 'critical']
  const min = order.indexOf(severity)
  return CRYPTO_VULNERABILITIES.filter((v) => order.indexOf(v.severity) >= min)
}

// --- ECB demo helper -------------------------------------------------------
/**
 * Détecte si un buffer de chiffrement aligne sur 16 octets a des blocs
 * dupliqués (signature ECB). Pédagogique uniquement.
 */
export function detectEcbDuplicateBlocks(cipherHex: string, blockSizeBytes = 16): { hasDuplicates: boolean; duplicateBlocks: number } {
  const clean = cipherHex.replace(/\s/g, '')
  if (clean.length % (blockSizeBytes * 2) !== 0) return { hasDuplicates: false, duplicateBlocks: 0 }
  const seen = new Set<string>()
  let dupes = 0
  for (let i = 0; i < clean.length; i += blockSizeBytes * 2) {
    const block = clean.slice(i, i + blockSizeBytes * 2)
    if (seen.has(block)) dupes += 1
    seen.add(block)
  }
  return { hasDuplicates: dupes > 0, duplicateBlocks: dupes }
}

// --- Constant-time string compare ------------------------------------------
/**
 * Comparaison à temps constant — pour montrer la défense contre `timing-attack-string-compare`.
 * Ne court-circuite jamais.
 */
export function constantTimeEqual(a: string, b: string): boolean {
  // Pad to equal length to keep iteration count stable (still leaks length).
  const len = Math.max(a.length, b.length)
  let diff = a.length ^ b.length
  for (let i = 0; i < len; i += 1) {
    const ca = i < a.length ? a.charCodeAt(i) : 0
    const cb = i < b.length ? b.charCodeAt(i) : 0
    diff |= ca ^ cb
  }
  return diff === 0
}
