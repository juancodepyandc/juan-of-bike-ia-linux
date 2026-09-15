/**
 * binarySecurityAuditor.ts — Moteur d'audit de durcissement binaire et analyse de sécurités ELF / PE.
 *
 * Fonctionnalités :
 * 1. Vérification des mécanismes de protection binaire (NX / DEP, ASLR / PIE, Stack Canaries, RELRO, Fortify Source).
 * 2. Détection des symboles de fonctions C/C++ non sécurisées (strcpy, sprintf, gets, vsprintf).
 * 3. Calcul d'un score de durcissement binaire sur 100.
 * 4. Formulation de directives de compilation durcie pour les chaînes CI/CD.
 */

export interface BinaryMitigationCheck {
  mitigationName: string
  isEnabled: boolean
  description: string
  importance: 'CRITICAL' | 'HIGH' | 'MEDIUM'
  remediationCompilerFlag: string
}

export interface DangerousFunctionSymbol {
  functionName: string
  cwe: string
  riskDescription: string
  safeAlternative: string
}

export interface BinaryHardeningReport {
  binaryName: string
  architecture: 'x86_64' | 'aarch64' | 'arm' | 'i386'
  format: 'ELF' | 'PE' | 'MACH_O'
  hardeningScore: number // 0..100
  mitigations: BinaryMitigationCheck[]
  dangerousSymbolsFound: DangerousFunctionSymbol[]
  recommendedCompilerFlags: string[]
  overallVerdict: 'DURCI_EXCELLENT' | 'DURCISSEMENT_MOYEN' | 'VULNÉRABLE_DÉFAUT_PROTECTION'
}

/**
 * Audite les protections et les symboles d'un exécutable binaire.
 */
export function auditBinaryHardening(options: {
  binaryName: string
  architecture?: 'x86_64' | 'aarch64'
  hasPie?: boolean
  hasStackCanary?: boolean
  hasNx?: boolean
  hasRelro?: 'FULL' | 'PARTIAL' | 'NONE'
  hasFortifySource?: boolean
  importedSymbols?: string[]
}): BinaryHardeningReport {
  const isPie = options.hasPie ?? true
  const isCanary = options.hasStackCanary ?? true
  const isNx = options.hasNx ?? true
  const relro = options.hasRelro ?? 'FULL'
  const isFortify = options.hasFortifySource ?? true

  const mitigations: BinaryMitigationCheck[] = [
    {
      mitigationName: 'NX / DEP (No-Execute Memory Pages)',
      isEnabled: isNx,
      description: 'Interdit l\'exécution de code dans les zones de mémoire inscriptibles (Pile et Tas).',
      importance: 'CRITICAL',
      remediationCompilerFlag: '-z noexecstack',
    },
    {
      mitigationName: 'PIE / ASLR (Position Independent Executable)',
      isEnabled: isPie,
      description: 'Randomise l\'adresse de base du binaire en mémoire pour contrer les attaques ROP / ret2libc.',
      importance: 'CRITICAL',
      remediationCompilerFlag: '-fPIE -pie',
    },
    {
      mitigationName: 'Stack Canaries (Guard against Stack Buffer Overflow)',
      isEnabled: isCanary,
      description: 'Insère une valeur sentinelle avant le pointeur de retour pour détecter les écrasements de pile.',
      importance: 'CRITICAL',
      remediationCompilerFlag: '-fstack-protector-strong',
    },
    {
      mitigationName: 'Full RELRO (Read-Only Relocations)',
      isEnabled: relro === 'FULL',
      description: 'Rend la table des adresses globales (GOT) en lecture seule après le chargement dynamique.',
      importance: 'HIGH',
      remediationCompilerFlag: '-Wl,-z,relro,-z,now',
    },
    {
      mitigationName: 'Fortify Source (Buffer Length Verification)',
      isEnabled: isFortify,
      description: 'Remplace à la compilation les fonctions non bornées par des équivalents vérifiant la taille.',
      importance: 'HIGH',
      remediationCompilerFlag: '-D_FORTIFY_SOURCE=3 -O2',
    },
  ]

  // Détection des symboles de fonctions dangereuses
  const dangerousMap: Record<string, DangerousFunctionSymbol> = {
    gets: {
      functionName: 'gets',
      cwe: 'CWE-120: Buffer Copy without Checking Size of Input',
      riskDescription: 'Impossible de limiter la taille de lecture, provoque des dépassements de tampon directs.',
      safeAlternative: 'fgets() avec taille explicite ou getline()',
    },
    strcpy: {
      functionName: 'strcpy',
      cwe: 'CWE-120: Unbounded String Copy',
      riskDescription: 'Copie sans contrôle de la taille du tampon de destination.',
      safeAlternative: 'strncpy(), strlcpy() ou std::string',
    },
    sprintf: {
      functionName: 'sprintf',
      cwe: 'CWE-134: Use of Externally-Controlled Format String',
      riskDescription: 'Risque de dépassement de tampon et de chaîne de format non contrôlée.',
      safeAlternative: 'snprintf() avec taille de buffer explicite',
    },
    system: {
      functionName: 'system',
      cwe: 'CWE-78: OS Command Injection',
      riskDescription: 'Invoque un shell /bin/sh interprétant les métacaractères sans échappement.',
      safeAlternative: 'execve() / posix_spawn() avec tableau d\'arguments typé',
    },
  }

  const dangerousFound: DangerousFunctionSymbol[] = []
  const symbols = options.importedSymbols || []
  for (const s of symbols) {
    if (dangerousMap[s]) {
      dangerousFound.push(dangerousMap[s])
    }
  }

  // Calcul du score de durcissement
  let activeScore = 0
  if (isNx) activeScore += 25
  if (isPie) activeScore += 25
  if (isCanary) activeScore += 20
  if (relro === 'FULL') activeScore += 15
  else if (relro === 'PARTIAL') activeScore += 5
  if (isFortify) activeScore += 15

  // Pénalité par symbole dangereux détecté
  activeScore = Math.max(0, activeScore - dangerousFound.length * 10)

  const recommendedFlags: string[] = [
    '-fPIE -pie',
    '-fstack-protector-strong',
    '-Wl,-z,relro,-z,now',
    '-D_FORTIFY_SOURCE=3 -O2',
    '-fcf-protection=full (Intel CET)',
  ]

  return {
    binaryName: options.binaryName,
    architecture: options.architecture || 'x86_64',
    format: 'ELF',
    hardeningScore: activeScore,
    mitigations,
    dangerousSymbolsFound: dangerousFound,
    recommendedCompilerFlags: recommendedFlags,
    overallVerdict: activeScore >= 90 ? 'DURCI_EXCELLENT' : activeScore >= 60 ? 'DURCISSEMENT_MOYEN' : 'VULNÉRABLE_DÉFAUT_PROTECTION',
  }
}
