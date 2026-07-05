// KDF cost analyzer — explique pourquoi Argon2 > bcrypt > PBKDF2 > sha256 nu
// pour stocker des mots de passe.
//
// Pour STI2D/SIN : c'est exactement le genre de question qui tombe en NSI/SIN
// cybersécurité ("citez deux fonctions de dérivation adaptatives"). Ce module
// donne les chiffres concrets sans devoir lancer un benchmark.
//
// Hypothèses de coût attaquant (mises à jour 2026) :
//   - sha256 GPU : ~ 50 GH/s sur RTX 5090
//   - bcrypt(cost=12) GPU : ~ 100 H/s sur Hashcat à plein régime
//   - argon2id moderate (m=64MiB, t=3, p=1) : ~ 50 H/s même avec ASIC,
//     borné par la bande passante mémoire
//
// Tous chiffres = ordre de grandeur, pas garantie cryptographique.

export type KdfAlgorithm =
  | 'sha256'
  | 'sha512'
  | 'md5'
  | 'pbkdf2-sha256'
  | 'pbkdf2-sha512'
  | 'bcrypt'
  | 'scrypt'
  | 'argon2i'
  | 'argon2d'
  | 'argon2id'

export type KdfParams = {
  algorithm: KdfAlgorithm
  /** Itérations (PBKDF2). */
  iterations?: number
  /** Cost factor (bcrypt). 2^cost rounds. */
  bcryptCost?: number
  /** Cost N (scrypt). */
  scryptN?: number
  scryptR?: number
  scryptP?: number
  /** Memory in KiB (Argon2). */
  memoryKib?: number
  /** Iterations (Argon2). */
  timeCost?: number
  /** Parallelism (Argon2). */
  parallelism?: number
}

export type KdfRecommendation =
  | 'banned'        // ne JAMAIS utiliser pour des mots de passe
  | 'legacy'        // OK historiquement, doit migrer
  | 'acceptable'    // utilisable si bien paramétré
  | 'recommended'   // OWASP 2024+ recommandation

export type KdfAssessment = {
  algorithm: KdfAlgorithm
  recommendation: KdfRecommendation
  hashesPerSecondAttacker: number
  hashesPerSecondLegit: number
  /** Coût en dollars pour casser une charset/longueur. Approximation cloud GPU. */
  attackCostUSD: (charsetSize: number, length: number) => number
  /** Texte explicatif rendu dans la fiche cours. */
  explanation: string
  /** Références BO/OWASP. */
  references: string[]
}

// --- Coût attaquant par algo (hash/s) -----------------------------------------
//
// Sources :
//   - Hashcat benchmark 2024 sur RTX 4090
//   - https://hashcat.net/wiki/doku.php?id=performance
//   - OWASP Password Storage Cheat Sheet (Oct 2024)
const ATTACKER_SPEEDS: Record<KdfAlgorithm, (p: KdfParams) => number> = {
  md5: () => 1.6e11,                                       // 160 GH/s
  sha256: () => 5e10,                                      // 50 GH/s
  sha512: () => 1.5e10,                                    // 15 GH/s
  'pbkdf2-sha256': (p) => 5e10 / Math.max(1, p.iterations ?? 600_000),
  'pbkdf2-sha512': (p) => 1.5e10 / Math.max(1, p.iterations ?? 210_000),
  bcrypt: (p) => 2e6 / Math.pow(2, Math.max(0, (p.bcryptCost ?? 12) - 5)),
  scrypt: (p) => {
    // Coût mémoire qui pénalise l'attaquant.
    const N = p.scryptN ?? 2 ** 17
    const r = p.scryptR ?? 8
    const memKb = (128 * N * r) / 1024
    // Approx empirique : chaque 64 MiB ≈ /10× sur GPU.
    return 5e8 / Math.max(1, Math.pow(10, memKb / 65536))
  },
  argon2i: (p) => argon2Speed(p),
  argon2d: (p) => argon2Speed(p),
  argon2id: (p) => argon2Speed(p),
}

function argon2Speed(p: KdfParams): number {
  const m = Math.max(1, p.memoryKib ?? 65536)
  const t = Math.max(1, p.timeCost ?? 3)
  const par = Math.max(1, p.parallelism ?? 1)
  // 50 H/s × (mémoire de référence 64MiB / mémoire utilisée) × 1/t × 1/√p
  return (50 * (65536 / m)) / t / Math.sqrt(par)
}

// --- Coût utilisateur (1 hash) -------------------------------------------------
// Approxime ce qu'un Cortex-A78 ou un i7 12e gen prend pour faire UNE dérivation.
const LEGIT_SPEEDS: Record<KdfAlgorithm, (p: KdfParams) => number> = {
  md5: () => 5e6,
  sha256: () => 2e6,
  sha512: () => 1.5e6,
  'pbkdf2-sha256': (p) => 5e5 / Math.max(1, p.iterations ?? 600_000) * 1000,
  'pbkdf2-sha512': (p) => 1.5e5 / Math.max(1, p.iterations ?? 210_000) * 1000,
  bcrypt: (p) => 1000 / Math.pow(2, Math.max(0, (p.bcryptCost ?? 12) - 8)),
  scrypt: () => 1, // ~ 1 hash / 100 ms à params raisonnables
  argon2i: (p) => 2 / Math.max(1, (p.timeCost ?? 3)) * (65536 / Math.max(1, p.memoryKib ?? 65536)),
  argon2d: (p) => 2 / Math.max(1, (p.timeCost ?? 3)) * (65536 / Math.max(1, p.memoryKib ?? 65536)),
  argon2id: (p) => 2 / Math.max(1, (p.timeCost ?? 3)) * (65536 / Math.max(1, p.memoryKib ?? 65536)),
}

const RECOMMENDATION_BY_ALGO: Record<KdfAlgorithm, KdfRecommendation> = {
  md5: 'banned',
  sha256: 'banned',
  sha512: 'banned',
  'pbkdf2-sha256': 'legacy',
  'pbkdf2-sha512': 'legacy',
  bcrypt: 'acceptable',
  scrypt: 'acceptable',
  argon2i: 'acceptable',
  argon2d: 'acceptable',
  argon2id: 'recommended',
}

const EXPLANATIONS: Record<KdfAlgorithm, string> = {
  md5: "MD5 est cryptographiquement cassé (collisions trouvées en quelques secondes). Avec un GPU moderne, on teste 160 milliards de mots de passe par seconde. Interdit pour les mots de passe — même salé.",
  sha256: "SHA-256 est un hash CRYPTOGRAPHIQUE solide (collision difficile), mais TROP RAPIDE pour stocker un mot de passe : 50 milliards d'essais/s sur RTX 5090. Conçu pour vérifier l'intégrité d'un fichier, pas pour ralentir un brute-force.",
  sha512: "Comme SHA-256 mais 64 bits. Légèrement moins rapide sur GPU (15 GH/s), toujours pas adapté aux mots de passe.",
  'pbkdf2-sha256': "PBKDF2 = SHA-256 répété N fois. OWASP 2024 recommande N ≥ 600 000. Mieux que SHA nu mais n'utilise PAS de mémoire ↦ vulnérable aux ASIC/GPU.",
  'pbkdf2-sha512': "Variante 512 bits. OWASP recommande N ≥ 210 000.",
  bcrypt: "bcrypt = Blowfish-based KDF, cost=2^c rounds. Bon historiquement mais : (a) limité à 72 octets, (b) pas de paramètre mémoire. cost=12 minimum en 2024.",
  scrypt: "scrypt force l'attaquant à utiliser beaucoup de RAM (paramètre N×r×128 octets). Bonne défense contre les ASIC. Paramètres recommandés : N=2^17, r=8, p=1.",
  argon2i: "Argon2i — variante 'side-channel safe', pour clés de chiffrement. Pour les mots de passe, préférer argon2id.",
  argon2d: "Argon2d — accès mémoire data-dependent, plus rapide mais sensible aux side-channels. Pour les contextes serveur sans side-channel uniquement.",
  argon2id: "Argon2id = gagnant du Password Hashing Competition 2015. Hybride i+d, mémoire-hard. Paramètres OWASP 2024 : m=64MiB, t=3, p=1.",
}

const REFERENCES: Record<KdfAlgorithm, string[]> = {
  md5: ['RFC 1321 (1992)', 'OWASP: Banned for passwords', 'Stevens 2009 — collisions pratiques'],
  sha256: ['FIPS 180-4', 'OWASP Cheat Sheet 2024'],
  sha512: ['FIPS 180-4'],
  'pbkdf2-sha256': ['RFC 8018', 'OWASP Password Storage Oct 2024'],
  'pbkdf2-sha512': ['RFC 8018'],
  bcrypt: ['Provos & Mazières 1999 — A Future-Adaptable Password Scheme', 'OpenBSD spec'],
  scrypt: ['RFC 7914', 'Percival 2009'],
  argon2i: ['RFC 9106', 'PHC 2015'],
  argon2d: ['RFC 9106'],
  argon2id: ['RFC 9106', 'OWASP Top Recommendation 2024'],
}

/**
 * Assess a KDF configuration. Returns the attacker hashes/s, legit hashes/s,
 * recommendation, and a cost projection lambda.
 */
export function assessKdf(params: KdfParams): KdfAssessment {
  const speedAtk = ATTACKER_SPEEDS[params.algorithm](params)
  const speedLeg = LEGIT_SPEEDS[params.algorithm](params)
  const algo = params.algorithm
  return {
    algorithm: algo,
    recommendation: RECOMMENDATION_BY_ALGO[algo],
    hashesPerSecondAttacker: speedAtk,
    hashesPerSecondLegit: speedLeg,
    attackCostUSD: (charsetSize: number, length: number) => attackCost(speedAtk, charsetSize, length),
    explanation: EXPLANATIONS[algo],
    references: REFERENCES[algo],
  }
}

/**
 * Estimate $ to brute-force a password of `length` chars over a `charsetSize`
 * alphabet, with the given attacker speed. Assumes the attacker rents AWS
 * p4d.24xlarge ($32.77/h) and tries half the keyspace on average.
 */
export function attackCost(hashesPerSecond: number, charsetSize: number, length: number): number {
  if (charsetSize <= 1 || length <= 0) return 0
  const keyspace = Math.pow(charsetSize, length) / 2
  const seconds = keyspace / hashesPerSecond
  const hours = seconds / 3600
  const HOURLY_RATE_USD = 32.77 / 8 // approx 8 GPUs per node
  return hours * HOURLY_RATE_USD
}

/**
 * Pretty-print a USD amount with abbreviations.
 */
export function formatUsd(amount: number): string {
  if (!Number.isFinite(amount)) return '∞'
  if (amount < 0.01) return '< 1¢'
  if (amount < 1) return `${(amount * 100).toFixed(1)}¢`
  if (amount < 1e3) return `$${amount.toFixed(2)}`
  if (amount < 1e6) return `$${(amount / 1e3).toFixed(1)}k`
  if (amount < 1e9) return `$${(amount / 1e6).toFixed(1)}M`
  if (amount < 1e12) return `$${(amount / 1e9).toFixed(1)}B`
  return `$${(amount / 1e12).toExponential(1)}T`
}

/**
 * Compare two configurations side by side. Useful for the lab UI's "Argon2 vs
 * bcrypt" demo screen.
 */
export type KdfComparison = {
  a: KdfAssessment
  b: KdfAssessment
  attackerSpeedRatio: number
  costAdvantageA: (charsetSize: number, length: number) => number
  verdict: string
}

export function compareKdf(a: KdfParams, b: KdfParams): KdfComparison {
  const aa = assessKdf(a)
  const bb = assessKdf(b)
  return {
    a: aa,
    b: bb,
    attackerSpeedRatio: aa.hashesPerSecondAttacker / Math.max(1e-12, bb.hashesPerSecondAttacker),
    costAdvantageA: (cs: number, len: number) => aa.attackCostUSD(cs, len) / Math.max(1e-12, bb.attackCostUSD(cs, len)),
    verdict: aa.hashesPerSecondAttacker < bb.hashesPerSecondAttacker
      ? `${aa.algorithm} ralentit l'attaquant ${(bb.hashesPerSecondAttacker / Math.max(1e-12, aa.hashesPerSecondAttacker)).toFixed(0)}× plus que ${bb.algorithm}.`
      : `${bb.algorithm} ralentit l'attaquant ${(aa.hashesPerSecondAttacker / Math.max(1e-12, bb.hashesPerSecondAttacker)).toFixed(0)}× plus que ${aa.algorithm}.`,
  }
}

/** OWASP 2024 references — used to populate sliders' defaults. */
export const OWASP_2024_DEFAULTS = {
  argon2id: { algorithm: 'argon2id' as const, memoryKib: 65536, timeCost: 3, parallelism: 1 },
  bcrypt: { algorithm: 'bcrypt' as const, bcryptCost: 12 },
  pbkdf2: { algorithm: 'pbkdf2-sha256' as const, iterations: 600_000 },
  scrypt: { algorithm: 'scrypt' as const, scryptN: 2 ** 17, scryptR: 8, scryptP: 1 },
} as const
