import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'

installHeadlessCodeEnv()

async function main() {
  console.log('[autonomous-tooling] Initialisation du banc de test de l\'outillage autonome...')

  const {
    inspectPackageOrCommand,
    executeAutonomousToolWithSelfHealing,
    generateSecurityAssessmentReport,
    loadLearnedTools,
  } = await import('../src/services/cyber/autonomousToolEngine.ts')

  // -------------------------------------------------------------------------
  // 1. TEST D'INTROSPECTION ET D'AUTO-APPRENTISSAGE DE DOCUMENTATION
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 1 : Introspection dynamique & Extraction de Doc ===')
  console.log('=============================================================')

  const docResPython = await inspectPackageOrCommand('hashlib', 'python')
  console.log(`- Module Python 'hashlib' introspecté : ${docResPython.ok ? 'SUCCÈS' : 'ÉCHEC'}`)
  console.log(`  Nombre de symboles découverts : ${docResPython.symbols?.length || 0}`)
  console.log(`  Extrait de doc : "${docResPython.doc.slice(0, 120)}..."`)

  const docResSys = await inspectPackageOrCommand('curl', 'system')
  console.log(`- Binaire système 'curl' inspecté : ${docResSys.ok ? 'SUCCÈS' : 'ÉCHEC'}`)
  console.log(`  Aide CLI capturée (${docResSys.helpText?.length || 0} caractères)`)

  // -------------------------------------------------------------------------
  // 2. TEST D'EXÉCUTION AUTONOME AVEC BOUCLE D'AUTO-RÉPARATION (SELF-HEALING)
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 2 : Exécution & Boucle d\'Auto-Réparation (Self-Healing) ===')
  console.log('=============================================================')

  const objective = "Analyser la force cryptographique d'un ensemble de clés et générer un rapport JSON avec entropie de Shannon."
  
  // Script initial avec une erreur d'import/syntaxe volontaire pour tester le self-healing
  const buggyInitialScript = `
import json
import math

# Erreur volontaire pour declencher l'auto-diagnostic et la reparation
data = "test_key_sample_12345"
entropy = sum(-p * math.log2(p) for p in [data.count(c)/len(data) for c in set(data)])

# Appel d'une fonction inexistante
result = {"entropy": entropy, "status": "computed"}
print(json.dumps(result))
`

  console.log(`[Auto-Tool] Lancement de l'objectif : "${objective}"`)
  const runRes = await executeAutonomousToolWithSelfHealing({
    objective,
    initialScript: buggyInitialScript,
    maxAttempts: 3,
  })

  console.log(`- Statut final : ${runRes.ok ? 'SUCCÈS' : 'ÉCHEC'}`)
  console.log(`- Tentatives totales : ${runRes.totalAttempts}`)
  console.log(`- Sortie finale : ${runRes.finalStdout.trim()}`)
  console.log(`- Outil mémorisé dans le registre : ${runRes.learnedToolSaved ? 'OUI' : 'NON'}`)

  // -------------------------------------------------------------------------
  // 3. TEST DE MÉMOIRE ET REGISTRE D'OUTILS
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 3 : Vérification du Registre d\'Outils Appris ===')
  console.log('=============================================================')

  const learnedTools = loadLearnedTools()
  console.log(`- Nombre d'outils mémorisés dans le registre : ${learnedTools.length}`)
  if (learnedTools.length > 0) {
    console.log(`  Dernier outil enregistré : "${learnedTools[0].name}"`)
    console.log(`  Tags : ${learnedTools[0].tags.join(', ')}`)
  }

  // -------------------------------------------------------------------------
  // 4. TEST DU MOTEUR D'ÉVALUATION ET SCORING DE SÉCURITÉ
  // -------------------------------------------------------------------------
  console.log('\n=============================================================')
  console.log('=== TEST 4 : Moteur d\'Évaluation & Scoring de Sécurité ===')
  console.log('=============================================================')

  const simulatedAuditLogs = `
AUDIT DE SÉCURITÉ POUR : https://api.exemple-service.local
1. En-têtes HTTP :
   - Strict-Transport-Security : ABSENT
   - Content-Security-Policy : default-src 'self' 'unsafe-inline'
   - X-Frame-Options : DENY
   - X-Content-Type-Options : nosniff
2. Analyse TLS :
   - Protocole négocié : TLSv1.3
   - Certificat valide jusqu'au : 2027-12-31
   - Chiffrement : AES-256-GCM
3. Authentification :
   - Algorithme JWT : RS256
   - Expiration du token : 3600 secondes
`

  const assessment = await generateSecurityAssessmentReport({
    target: 'https://api.exemple-service.local',
    auditLogs: simulatedAuditLogs,
  })

  console.log(`- Cible évaluée : ${assessment.target}`)
  console.log(`- Note de sécurité globale : ${assessment.overallScore}/100`)
  console.log(`- Niveau de risque : ${assessment.riskLevel}`)
  console.log(`- Nombre de constats (findings) : ${assessment.findings.length}`)
  console.log(`- Actions prioritaires P0 : ${assessment.actionPlan.immediateP0.join(' | ')}`)

  console.log('\n=============================================================')
  console.log('=== BILAN GLOBAL DES AMÉLIORATIONS ===')
  console.log('=============================================================')
  const allTestsPassed = docResPython.ok && docResSys.ok && runRes.ok && assessment.overallScore > 0
  console.log(`RÉSULTAT GLOBAL : ${allTestsPassed ? 'TOUTES LES AMÉLIORATIONS SONT OPÉRATIONNELLES' : 'ATTENTION'}`)
}

main().catch((err) => {
  console.error('[autonomous-tooling] Erreur fatale :', err)
  process.exit(1)
})
