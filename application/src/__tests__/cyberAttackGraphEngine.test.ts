import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ENTERPRISE_SYSTEMIC_GRAPH,
  computeBlastRadius,
} from '../services/cyber/attackGraphEngine.ts'

describe('AttackGraphEngine', () => {
  test('Le graphe d entreprise modélise nœuds, arêtes et chemins d attaque', () => {
    assert.ok(ENTERPRISE_SYSTEMIC_GRAPH.nodes.length >= 6, 'Au moins 6 nœuds')
    assert.ok(ENTERPRISE_SYSTEMIC_GRAPH.edges.length >= 6, 'Au moins 6 arêtes')
    assert.ok(ENTERPRISE_SYSTEMIC_GRAPH.attackPaths.length >= 2, 'Au moins 2 chemins d attaque')
  })

  test('computeBlastRadius calcule la portée et les actifs critiques exposés', () => {
    const radius = computeBlastRadius('dmz-web', ENTERPRISE_SYSTEMIC_GRAPH)
    assert.ok(radius.reachableNodes.includes('int-api'), 'int-api doit être joignable depuis dmz-web')
    assert.ok(radius.reachableNodes.includes('db-customer'), 'db-customer doit être joignable par pivot')
    assert.ok(radius.totalImpact > 0, 'Impact supérieur à 0')
    assert.ok(Array.isArray(radius.highRiskAssets), 'Liste des actifs critiques')
  })
})
