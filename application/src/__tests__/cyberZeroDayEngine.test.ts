import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ZERO_DAY_CATALOG,
  runFuzzingSimulation,
  type ZeroDayVulnerability,
} from '../services/cyber/zeroDayEngine.ts'

describe('ZeroDayEngine', () => {
  test('ZERO_DAY_CATALOG contient des vulnérabilités 0-day complètes et réalistes', () => {
    assert.ok(ZERO_DAY_CATALOG.length >= 4, 'Le catalogue doit contenir au moins 4 archétypes 0-day')
    for (const vuln of ZERO_DAY_CATALOG) {
      assert.ok(vuln.id.startsWith('0DAY-'), `L'ID doit commencer par 0DAY- : ${vuln.id}`)
      assert.ok(vuln.title.length > 5, 'Le titre doit être explicite')
      assert.ok(vuln.cwe.includes('CWE-'), 'La CWE doit être renseignée')
      assert.ok(vuln.cvss >= 7.0 && vuln.cvss <= 10.0, 'Le score CVSS doit être critique/élevé')
      assert.ok(vuln.vulnerableCode.length > 20, 'Le code vulnérable doit être complet')
      assert.ok(vuln.patchedCode.length > 20, 'Le code corrigé doit être complet')
      assert.ok(vuln.mitigationMatrix.compilerLevel.length > 0, 'La mitigation compilateur doit être définie')
      assert.ok(vuln.mitigationMatrix.osLevel.length > 0, 'La mitigation OS doit être définie')
      assert.ok(vuln.mitigationMatrix.detectionRule.length > 0, 'La règle de détection doit être définie')
      assert.ok(vuln.reproductionSteps.length >= 3, 'Au moins 3 étapes de reproduction nécessaires')
    }
  })

  test('runFuzzingSimulation génère des crashes déterministes et une couverture de code', () => {
    const result = runFuzzingSimulation('use-after-free', 1000)
    assert.equal(result.totalIterations, 1000)
    assert.ok(result.uniqueCrashes >= 1, 'Au moins un crash doit être détecté')
    assert.ok(result.codeCoveragePct >= 50 && result.codeCoveragePct <= 100, 'Couverture de code cohérente')
    assert.ok(result.fuzzSpeedIps > 1000, 'Vitesse de fuzzing en IPS positive')
    assert.ok(result.crashLogs.length > 0, 'Des logs de crash doivent être présents')
    assert.ok(result.crashLogs[0]?.faultAddress.startsWith('0x'), 'Adresse mémoire valide')
  })
})
