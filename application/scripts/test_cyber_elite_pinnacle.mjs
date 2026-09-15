import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'

installHeadlessCodeEnv()

async function main() {
  console.log('[cyber-pinnacle] Lancement de la validation des 5 piliers d\'excellence suprême...')

  // -------------------------------------------------------------------------
  // 1. TEST DU MOTEUR DE RECHERCHE ET DÉCOUVERTE 0-DAY PAR INVARIANTS
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 1 : Découverte 0-Day par Invariants Fondamentaux ===')
  console.log('=============================================================')

  const { discoverNovelVulnerabilities } = await import('../src/services/cyber/zeroDayDiscoveryEngine.ts')

  const sampleArch = `
Architecture Microservices :
1. Reverse Proxy Envoy recevant les requêtes HTTP/2 et les désérialisant vers un backend Go en gRPC.
2. Découpage des requêtes sans normalisation stricte des en-têtes Content-Length vs chunked.
3. Cache Redis partagé sans préfixage par tenant.
`

  const zeroDayReport = await discoverNovelVulnerabilities({
    targetDescription: 'Passerelle API Microservices Envoy / gRPC / Redis',
    architectureOrCode: sampleArch,
  })

  console.log(`- Architecture analysée : ${zeroDayReport.targetArchitecture}`)
  console.log(`- Invariants audités : ${zeroDayReport.totalInvariantsAudited}`)
  console.log(`- Hypothèses 0-day formulées : ${zeroDayReport.hypothesesFormulated.length}`)
  if (zeroDayReport.hypothesesFormulated.length > 0) {
    const h = zeroDayReport.hypothesesFormulated[0]
    console.log(`  [Hypothèse 1] : ${h.title}`)
    console.log(`  Invariant violé : ${h.invariantViolated} (CVSS estimé: ${h.estimatedCvss})`)
    console.log(`  Défense proactive : ${h.proactiveDefensePrinciple}`)
  }

  // -------------------------------------------------------------------------
  // 2. TEST DE SYNCHRONISATION DU CATALOGUE CISA KEV & FIRST EPSS
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 2 : Renseignement sur les Menaces CISA KEV / EPSS ===')
  console.log('=============================================================')

  const { auditComponentsAgainstCisaKev } = await import('../src/services/cyber/cisaKevSyncEngine.ts')

  const auditedStack = [
    { name: 'Apache Log4j', version: '2.14.1' },
    { name: 'Palo Alto Networks PAN-OS', version: '10.2.3' },
    { name: 'React', version: '19.0.0' },
  ]

  const kevReport = auditComponentsAgainstCisaKev(auditedStack)
  console.log(`- Composants vérifiés : ${kevReport.totalComponentsChecked}`)
  console.log(`- Vulnérabilités KEV actives identifiées : ${kevReport.activeKevMatchesCount}`)
  console.log(`- Liens avec des campagnes de rançongiciels : ${kevReport.ransomwareLinkedCount}`)
  console.log(`- Score EPSS maximal : ${kevReport.highestEpssScore}`)
  kevReport.matches.forEach((m) => {
    console.log(`  -> [${m.component}] : ${m.kevEntry.cveId} (${m.urgencyLevel}) - ${m.remediationRecommendation}`)
  })

  // -------------------------------------------------------------------------
  // 3. TEST DE CRYPTOGRAPHIE POST-QUANTIQUE (NIST PQC) & NONCE REUSE
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 3 : Cryptanalyse Post-Quantique (NIST PQC) ===')
  console.log('=============================================================')

  const { auditQuantumReadiness, checkEcdsaNonceReuse } = await import('../src/services/cyber/postQuantumCryptoAudit.ts')

  const cryptoStack = ['RSA-2048', 'ECDSA-SECP256R1', 'ML-KEM-768 (Kyber)', 'AES-256-GCM']
  const pqcReport = auditQuantumReadiness(cryptoStack)
  console.log(`- Score de préparation quantique : ${pqcReport.overallQuantumReadinessScore}/100`)
  console.log(`- Statut de conformité : ${pqcReport.status}`)

  const sig1 = { r: '0x3a19ff89', s: '0x9924aa12', z: 'msg1_hash' }
  const sig2 = { r: '0x3a19ff89', s: '0x7741bb88', z: 'msg2_hash' }
  const nonceAudit = checkEcdsaNonceReuse(sig1, sig2)
  console.log(`- Détection réutilisation de nonce ECDSA : ${nonceAudit.isVulnerable ? 'FAILLE CRITIQUE DÉTECTÉE' : 'SÉCURISÉ'}`)
  console.log(`  Détail : ${nonceAudit.explanation}`)

  // -------------------------------------------------------------------------
  // 4. TEST DE DÉCEPTION DÉFENSIVE & JETONS CANARIS (HONEYTOKENS)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 4 : Moteur de Déception & Honeytokens Dynamiques ===')
  console.log('=============================================================')

  const { DynamicHoneytokenEngine } = await import('../src/services/cyber/dynamicHoneytokenEngine.ts')

  const honeyApiKey = DynamicHoneytokenEngine.generateHoneytoken('API_KEY', 'AWS Production Master Key Decoy', 'src/config/aws.env')
  console.log(`- Jeton piège généré : ${honeyApiKey.tokenId} (${honeyApiKey.name})`)
  console.log(`  Emplacement appât : ${honeyApiKey.decoyLocation}`)

  // Simulation d'une tentative d'intrusion utilisant le jeton leurre
  const triggerAlert = DynamicHoneytokenEngine.evaluateAccessAttempt(honeyApiKey.tokenValue, '198.51.100.42', 'Nmap Vuln Scanner v7')
  console.log(`- Alerte intrusion générée : ${triggerAlert ? 'OUI' : 'NON'}`)
  if (triggerAlert) {
    console.log(`  Sévérité : ${triggerAlert.severity}`)
    console.log(`  IP suspecte interceptée : ${triggerAlert.sourceIp}`)
    console.log(`  Action immédiate : ${triggerAlert.recommendedImmediateAction}`)
  }

  // -------------------------------------------------------------------------
  // 5. TEST DE DURCISSEMENT BINAIRE & ANALYSE DE SÉCURITÉS ELF
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 5 : Audit de Durcissement Binaire (ELF / PE) ===')
  console.log('=============================================================')

  const { auditBinaryHardening } = await import('../src/services/cyber/binarySecurityAuditor.ts')

  const hardenedBinaryReport = auditBinaryHardening({
    binaryName: 'aurora_kernel_daemon',
    hasPie: true,
    hasStackCanary: true,
    hasNx: true,
    hasRelro: 'FULL',
    hasFortifySource: true,
    importedSymbols: ['snprintf', 'fgets', 'malloc'],
  })

  console.log(`- Binaire audité : ${hardenedBinaryReport.binaryName}`)
  console.log(`- Score de durcissement binaire : ${hardenedBinaryReport.hardeningScore}/100`)
  console.log(`- Verdict global : ${hardenedBinaryReport.overallVerdict}`)
  console.log(`- Protections actives : ${hardenedBinaryReport.mitigations.filter(m => m.isEnabled).length}/${hardenedBinaryReport.mitigations.length}`)

  console.log('\n=============================================================')
  console.log('=== BILAN FINAL DES 5 PILIERS D\'EXCELLENCE SUPRÊME ===')
  console.log('=============================================================')
  const allPinnacleSuccess =
    zeroDayReport.hypothesesFormulated.length > 0 &&
    kevReport.activeKevMatchesCount >= 2 &&
    pqcReport.overallQuantumReadinessScore > 0 &&
    nonceAudit.isVulnerable === true &&
    triggerAlert !== null &&
    hardenedBinaryReport.hardeningScore === 100

  console.log(`RÉSULTAT GLOBAL : ${allPinnacleSuccess ? 'SUCCÈS PARFAIT — 10/10 ATTEINT SUR L\'ENSEMBLE DU SPECTRE CYBER' : 'ATTENTION'}`)
}

main().catch((err) => {
  console.error('[cyber-pinnacle] Erreur fatale :', err)
  process.exit(1)
})
