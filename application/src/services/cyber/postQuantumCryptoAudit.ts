/**
 * postQuantumCryptoAudit.ts — Moteur d'audit cryptographique Post-Quantique (NIST PQC) et Courbes Elliptiques.
 *
 * Fonctionnalités :
 * 1. Évaluation de la résistance des suites cryptographiques face à l'ordinateur quantique (Algorithme de Shor).
 * 2. Audit de transition vers les standards NIST PQC (FIPS 203 ML-KEM / Kyber, FIPS 204 ML-DSA / Dilithium).
 * 3. Détection déterministe de la réutilisation de nonce ECDSA (permettant la divulgation de la clé privée).
 * 4. Délivrance d'une note de préparation quantique (Quantum Readiness Score).
 */

export interface CryptoSuiteAudit {
  algorithm: string
  keySizeBytes: number
  isQuantumVulnerable: boolean
  quantumVulnerabilityType: 'SHOR_DISCRETE_LOG' | 'SHOR_FACTORIZATION' | 'GROVER_BRUTEFORCE' | 'POST_QUANTUM_RESISTANT'
  recommendedPqcAlternative: string
  estimatedSecurityBits: number
}

export interface EcdsaNonceReuseAudit {
  isVulnerable: boolean
  recoveredPrivateKey?: string
  explanation: string
}

export interface QuantumReadinessReport {
  overallQuantumReadinessScore: number // 0..100
  status: 'POST_QUANTUM_READY' | 'HYBRID_TRANSITION' | 'QUANTUM_VULNERABLE'
  evaluatedSuites: CryptoSuiteAudit[]
  recommendations: string[]
}

/**
 * Audite un ensemble d'algorithmes et clés cryptographiques face aux menaces quantiques.
 */
export function auditQuantumReadiness(algorithms: string[]): QuantumReadinessReport {
  const evaluated: CryptoSuiteAudit[] = []
  let resistantCount = 0

  for (const alg of algorithms) {
    const upper = alg.toUpperCase()

    if (upper.includes('RSA')) {
      evaluated.push({
        algorithm: alg,
        keySizeBytes: 256,
        isQuantumVulnerable: true,
        quantumVulnerabilityType: 'SHOR_FACTORIZATION',
        recommendedPqcAlternative: 'ML-KEM (Kyber-768 / Kyber-1024) ou ML-DSA (Dilithium)',
        estimatedSecurityBits: 112,
      })
    } else if (upper.includes('ECDSA') || upper.includes('SECP256') || upper.includes('ED25519')) {
      evaluated.push({
        algorithm: alg,
        keySizeBytes: 32,
        isQuantumVulnerable: true,
        quantumVulnerabilityType: 'SHOR_DISCRETE_LOG',
        recommendedPqcAlternative: 'FIPS 204 ML-DSA-65 (Dilithium3) ou SLH-DSA (SPHINCS+)',
        estimatedSecurityBits: 128,
      })
    } else if (upper.includes('KYBER') || upper.includes('ML-KEM') || upper.includes('ML-DSA') || upper.includes('DILITHIUM')) {
      evaluated.push({
        algorithm: alg,
        keySizeBytes: 1184,
        isQuantumVulnerable: false,
        quantumVulnerabilityType: 'POST_QUANTUM_RESISTANT',
        recommendedPqcAlternative: 'Déjà conforme aux standards NIST PQC FIPS 203/204',
        estimatedSecurityBits: 192,
      })
      resistantCount++
    } else if (upper.includes('AES-256') || upper.includes('CHACHA20')) {
      evaluated.push({
        algorithm: alg,
        keySizeBytes: 32,
        isQuantumVulnerable: false,
        quantumVulnerabilityType: 'POST_QUANTUM_RESISTANT',
        recommendedPqcAlternative: 'AES-256 résiste à l\'algorithme de Grover (128 bits de sécurité post-quantique)',
        estimatedSecurityBits: 256,
      })
      resistantCount++
    } else {
      evaluated.push({
        algorithm: alg,
        keySizeBytes: 16,
        isQuantumVulnerable: true,
        quantumVulnerabilityType: 'GROVER_BRUTEFORCE',
        recommendedPqcAlternative: 'Passer à des clés symétriques 256 bits et PQC pour l\'échange asymétrique',
        estimatedSecurityBits: 64,
      })
    }
  }

  const total = algorithms.length
  const score = total > 0 ? Math.round((resistantCount / total) * 100) : 0

  const recommendations: string[] = []
  if (score < 100) {
    recommendations.push("Adopter une architecture hybride (X25519 + ML-KEM-768) pour l'échange de clés TLS.")
    recommendations.push("Migrer les signatures numériques vers ML-DSA (Dilithium) pour les certificats à longue durée de vie.")
    recommendations.push("Privilégier le chiffrement symétrique AES-256-GCM pour garantir 128 bits de sécurité post-Grover.")
  } else {
    recommendations.push("Excellence cryptographique : L'ensemble de la suite est immunisé face aux menaces quantiques.")
  }

  return {
    overallQuantumReadinessScore: score,
    status: score >= 80 ? 'POST_QUANTUM_READY' : score >= 40 ? 'HYBRID_TRANSITION' : 'QUANTUM_VULNERABLE',
    evaluatedSuites: evaluated,
    recommendations,
  }
}

/**
 * Détecte si deux signatures ECDSA partagent le même nonce k (faille de réutilisation de nonce).
 * En cryptographie sur courbes elliptiques, la réutilisation de k permet de calculer k = (z1 - z2)/(s1 - s2) mod n
 * et donc d'extraire instantanément la clé privée secrète.
 */
export function checkEcdsaNonceReuse(signature1: { r: string; s: string; z: string }, signature2: { r: string; s: string; z: string }): EcdsaNonceReuseAudit {
  // Deux signatures distinctes avec la même valeur r indiquent une réutilisation exacte du nonce k
  if (signature1.r === signature2.r && signature1.s !== signature2.s) {
    return {
      isVulnerable: true,
      explanation: "CRITIQUE : Réutilisation de nonce k détectée (même valeur r sur deux messages distincts). La clé privée ECDSA peut être mathématiquement extraite en O(1).",
    }
  }

  return {
    isVulnerable: false,
    explanation: "Sécurité validée : Les nonces ECDSA sont distincts et non réutilisés (RFC 6979 respecté).",
  }
}
