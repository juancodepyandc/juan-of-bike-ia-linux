import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  runAutonomousInvestigation,
  KNOWLEDGE_BASE_THREATS,
} from '../services/cyber/autonomousInvestigator.ts'

describe('AutonomousInvestigatorEngine', () => {
  test('KNOWLEDGE_BASE_THREATS contient des vulnérabilités critiques avec EPSS et MITRE', () => {
    assert.ok(KNOWLEDGE_BASE_THREATS.length >= 3)
    for (const t of KNOWLEDGE_BASE_THREATS) {
      assert.ok(t.cveId.startsWith('CVE-'))
      assert.ok(t.cvssScore >= 7.0)
      assert.ok(t.epssProbability > 0 && t.epssProbability <= 1.0)
      assert.ok(t.mitreTechniques.length >= 1)
    }
  })

  test('runAutonomousInvestigation génère un dossier complet avec hypothèses et roadmap P0/P1/P2', () => {
    const dossier = runAutonomousInvestigation('OpenSSH Signal Handler Race Condition')
    assert.ok(dossier.investigationId.startsWith('INV-'))
    assert.ok(dossier.threatIntelMatches.length >= 1)
    assert.ok(dossier.hypothesesRanked.length >= 3)
    assert.ok(dossier.timeline.length >= 4)
    assert.ok(dossier.actionableRoadmap.immediateP0.length >= 2)
    assert.ok(dossier.actionableRoadmap.structuralP1.length >= 2)
    assert.ok(dossier.actionableRoadmap.detectionRulesP2.length >= 2)
    assert.ok(dossier.exportPayload.content.includes('Dossier d\'Investigation Autonome'))
  })
})
