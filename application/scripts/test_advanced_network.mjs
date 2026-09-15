import { installHeadlessCodeEnv } from './code_harness/harness_env.mjs'

installHeadlessCodeEnv()

async function main() {
  console.log('[network-test] Lancement de la validation du moteur réseau haute précision...')

  const { AdvancedNetworkEngine } = await import('../src/services/cyber/advancedNetworkEngine.ts')

  // 1. Test de calibration de la ligne de base et suppression du Jitter
  const rawLatencySamples = [45, 48, 47, 50, 46, 49, 180, 47, 52, 46, 48, 500] // Avec 2 anomalies de routage (180ms et 500ms)
  console.log('\n=== TEST 1 : Filtrage de Gigue (Jitter) & Détection d\'Anomalies ===')
  console.log(`- Échantillons bruts : [${rawLatencySamples.join(', ')}] ms`)

  const filteredSamples = AdvancedNetworkEngine.filterNetworkOutliers(rawLatencySamples)
  console.log(`- Échantillons assainis (IQR) : [${filteredSamples.join(', ')}] ms`)

  const baseline = AdvancedNetworkEngine.calibrateNetworkBaseline(filteredSamples)
  console.log(`- Latence moyenne calibrée : ${baseline.meanLatencyMs} ms`)
  console.log(`- Médiane : ${baseline.medianLatencyMs} ms`)
  console.log(`- Écart-type : ${baseline.standardDeviationMs} ms`)
  console.log(`- Percentile p95 : ${baseline.baselineP95Ms} ms`)
  console.log(`- Score de fiabilité réseau : ${baseline.networkReliabilityScore}/100`)

  // 2. Test de décomposition temporelle (Network Waterfall)
  console.log('\n=== TEST 2 : Décomposition Précise des Phases Réseau (Waterfall) ===')
  const waterfall = AdvancedNetworkEngine.analyzeNetworkTiming(120, false)
  console.log(`- Durée totale : ${waterfall.totalDurationMs} ms`)
  console.log(`  * Résolution DNS : ${waterfall.dnsLookupMs} ms`)
  console.log(`  * Poignée de main TCP : ${waterfall.tcpHandshakeMs} ms`)
  console.log(`  * Négociation TLS : ${waterfall.tlsNegotiationMs} ms`)
  console.log(`  * Temps jusqu'au premier octet (TTFB) : ${waterfall.timeToFirstByteMs} ms`)
  console.log(`  * Téléchargement contenu : ${waterfall.contentDownloadMs} ms`)

  // 3. Test de cadence adaptative (Adaptive Backoff)
  console.log('\n=== TEST 3 : Calcul de Backoff Adaptatif Anti-Saturation ===')
  for (let attempt = 0; attempt < 4; attempt++) {
    const delay = AdvancedNetworkEngine.calculateAdaptiveBackoffMs(attempt, 150, 2000)
    console.log(`  Tentative ${attempt + 1} -> Délai adaptatif calculé : ${delay} ms`)
  }

  const success =
    filteredSamples.length < rawLatencySamples.length &&
    baseline.networkReliabilityScore >= 90 &&
    waterfall.totalDurationMs === 120

  console.log('\n=============================================================')
  console.log(`RÉSULTAT DU TEST RÉSEAU : ${success ? 'SUCCÈS PARFAIT' : 'ÉCHEC'}`)
  console.log('=============================================================')
}

main().catch((err) => {
  console.error('[network-test] Erreur :', err)
  process.exit(1)
})
