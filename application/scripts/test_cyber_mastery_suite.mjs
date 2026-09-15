import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'

installHeadlessCodeEnv()

async function main() {
  console.log('[cyber-mastery] Initialisation de la suite complète d\'évaluation Cybersécurité...')

  // -------------------------------------------------------------------------
  // 1. TEST DE LA BOUCLE FERMÉE D'AUDIT ET REMÉDIATION (CLOSED-LOOP PATCH)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 1 : Boucle Fermée de Remédiation & Zéro-Régression ===')
  console.log('=============================================================')

  const { verifySsrfClosedLoop, verifyTimingAttackClosedLoop } = await import('../src/services/cyber/closedLoopPatchEngine.ts')

  const ssrfResult = verifySsrfClosedLoop()
  console.log(`- Validation SSRF en boucle fermée : ${ssrfResult.ok ? 'SUCCÈS' : 'ÉCHEC'}`)
  console.log(`  Vulnérabilité neutralisée : ${ssrfResult.vulnerabilityResolved ? 'OUI' : 'NON'}`)
  console.log(`  Trafic nominal préservé : ${ssrfResult.nominalFunctionPreserved ? 'OUI' : 'NON'}`)
  console.log(`  Certificat délivré : ${ssrfResult.remediationCertificate?.certificateId} (${ssrfResult.remediationCertificate?.status})`)

  const timingResult = verifyTimingAttackClosedLoop()
  console.log(`- Validation Attaque Temporelle : ${timingResult.ok ? 'SUCCÈS' : 'ÉCHEC'}`)
  console.log(`  Comparaison en temps constant O(1) : ${timingResult.vulnerabilityResolved ? 'VALIDÉ' : 'ÉCHEC'}`)

  // -------------------------------------------------------------------------
  // 2. TEST DE FUZZING COGNITIF ET ANALYSE AUX LIMITES
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 2 : Moteur de Fuzzing Cognitif & Analyse aux Limites ===')
  console.log('=============================================================')

  const { executeCognitiveFuzzing } = await import('../src/services/cyber/cognitiveFuzzingEngine.ts')

  // Simulation d'un parseur JSON sécurisé avec validation de profondeur et d'assainissement
  const mockJsonParser = (input) => {
    const raw = typeof input === 'object' ? JSON.stringify(input) : String(input)
    if (raw.length > 10000) throw new Error("Entrée rejetée : Dépassement de taille maximale autorisée.")
    const depth = (raw.match(/\[/g) || []).length
    if (depth > 50) throw new Error("Entrée rejetée : Profondeur de nidification maximale dépassée.")
    if (raw.includes('\\x00') || raw.includes('\\u0000')) throw new Error("Entrée rejetée : Caractères d'octets nuls interdits.")
    return JSON.parse(raw)
  }

  const fuzzReport = executeCognitiveFuzzing('JSON_PARSER', mockJsonParser)
  console.log(`- Cible analysée : ${fuzzReport.targetType}`)
  console.log(`- Vecteurs aux limites testés : ${fuzzReport.totalVectorsTested}`)
  console.log(`- Score de résilience du parseur : ${fuzzReport.resilienceScore}/100`)
  console.log(`- Verdict de robustesse : ${fuzzReport.overallVerdict}`)

  // -------------------------------------------------------------------------
  // 3. TEST DU GRAPHE D'ATTAQUE RELATIONNEL ET CHEMINS CRITIQUES
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 3 : Graphe d\'Attaque Dynamique & Points de Coupure ===')
  console.log('=============================================================')

  const { computeCriticalAttackPath } = await import('../src/services/cyber/dynamicAttackGraphOrchestrator.ts')

  const sampleGraph = {
    nodes: [
      { id: 'node-ext', label: 'Passerelle Web Publique (Ingress)', type: 'EXTERNAL_ASSET', isCompromised: false, isCriticalAsset: false },
      { id: 'node-app', label: 'Microservice API Backend', type: 'DMZ_SERVICE', cvssVulnerability: 8.8, epssProbability: 0.85, isCompromised: false, isCriticalAsset: false },
      { id: 'node-db', label: 'Cluster Base de Données Clients', type: 'DATABASE', isCompromised: false, isCriticalAsset: true },
    ],
    edges: [
      { id: 'edge-1', sourceNodeId: 'node-ext', targetNodeId: 'node-app', protocol: 'HTTPS', mitreTechnique: 'T1190 (Exploit Public App)', weight: 2, isBlockedByDefense: false },
      { id: 'edge-2', sourceNodeId: 'node-app', targetNodeId: 'node-db', protocol: 'PostgreSQL', mitreTechnique: 'T1021 (Remote Services)', weight: 3, isBlockedByDefense: false },
    ],
  }

  const attackPath = computeCriticalAttackPath(sampleGraph, 'node-ext')
  console.log(`- Chemin critique calculé : ${attackPath.pathFound ? 'DÉTECTÉ' : 'NON DÉTECTÉ'}`)
  console.log(`  Étapes d'attaque identifiées : ${attackPath.steps.length}`)
  console.log(`  Point de coupure prioritaire (Chokepoint) : [${attackPath.chokepoints.join(', ')}]`)
  console.log(`  Action recommandée : ${attackPath.remediationAction}`)

  // -------------------------------------------------------------------------
  // 4. TEST DE GESTION DES SESSIONS & REPRISE 2FA (HUMAN-IN-THE-LOOP)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 4 : Gestionnaire de Session & Pause/Reprise 2FA ===')
  console.log('=============================================================')

  const { SessionStateManager } = await import('../src/services/cyber/sessionStateManager.ts')

  const session = SessionStateManager.createSession('https://auth.portail-securise.local/login', 'Saisie identifiants')
  console.log(`- Session créée : ${session.sessionId} (Statut: ${session.status})`)

  // Simulation d'une pause en attente de code 2FA
  const paused = SessionStateManager.pauseFor2FA(session.sessionId, 'Veuillez saisir le code reçu par SMS au 06******89')
  console.log(`- Session mise en pause 2FA : ${paused?.status} (${paused?.otpPromptMessage})`)

  // Simulation de la reprise après saisie utilisateur
  const resumed = SessionStateManager.resumeWithOtp(session.sessionId, '749201')
  console.log(`- Session reprise après saisie OTP : ${resumed?.status} (${resumed?.currentStepDescription})`)

  const completed = SessionStateManager.completeSession(session.sessionId, { userId: 'usr_9941', token: 'jwt_mock_valid' })
  console.log(`- Session finalisée : ${completed?.status}`)

  SessionStateManager.clearSession(session.sessionId)

  // -------------------------------------------------------------------------
  // 5. TEST DE L'ESCOUADE MULTI-AGENTS (WAR ROOM COLLABORATIVE)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 5 : Escouade Multi-Agents Cyber (War Room) ===')
  console.log('=============================================================')

  const { executeMultiAgentWarRoomMission } = await import('../src/services/cyber/multiAgentWarRoomOrchestrator.ts')
  const { DEFAULT_MAIN_MODEL } = await import('../src/config/models.ts')

  const warRoomMission = await executeMultiAgentWarRoomMission({
    targetScope: 'Infrastructure Cloud Hybride (Kubernetes Ingress & Passerelles API)',
    objective: 'Auditer l\'exposition des annotations Ingress, formuler la remédiation et vérifier l\'absence de régression.',
    modelOverride: DEFAULT_MAIN_MODEL,
  })

  console.log(`- Mission War Room : ${warRoomMission.missionId}`)
  console.log(`- Statut de la mission : ${warRoomMission.isComplete ? 'TERMINÉE AVEC SUCCÈS' : 'EN COURS'}`)
  console.log(`- Score de sécurité global : ${warRoomMission.overallSecurityScore}/100`)
  console.log(`- Nombre d'interventions d'agents : ${warRoomMission.transcript.length}`)
  warRoomMission.transcript.forEach((msg) => {
    console.log(`  [${msg.agentName}] : ${msg.content.slice(0, 100)}...`)
  })

  console.log('\n=============================================================')
  console.log('=== BILAN FINAL DU TEST D\'EXCELLENCE CYBER ===')
  console.log('=============================================================')
  const allSuccess = ssrfResult.ok && timingResult.ok && fuzzReport.resilienceScore >= 70 && attackPath.pathFound && completed?.status === 'COMPLETED' && warRoomMission.isComplete
  console.log(`RÉSULTAT GLOBAL : ${allSuccess ? 'EXCELLENCE TOTALE — TOUS LES COMPOSANTS SONT AU MAXIMUM' : 'ATTENTION'}`)
}

main().catch((err) => {
  console.error('[cyber-mastery] Erreur fatale :', err)
  process.exit(1)
})
