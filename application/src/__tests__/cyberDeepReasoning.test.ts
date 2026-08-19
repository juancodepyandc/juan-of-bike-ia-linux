import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEEP_REASONING_PRESETS,
  DEEP_REASONING_PROMPT_SYSTEM,
} from '../services/cyber/cyberDeepReasoning.ts'

describe('CyberDeepReasoning', () => {
  test('Les scénarios de raisonnement cognitif contiennent des étapes dialectiques', () => {
    assert.ok(DEEP_REASONING_PRESETS.length >= 2, 'Au moins 2 scénarios pré-calculés')
    for (const sc of DEEP_REASONING_PRESETS) {
      assert.ok(sc.id.startsWith('reasoning-'), 'ID de scénario valide')
      assert.ok(sc.title.length > 5, 'Titre explicite')
      assert.ok(sc.steps.length >= 3, 'Au moins 3 étapes de raisonnement')
      for (const st of sc.steps) {
        assert.ok(st.redPerspective.length > 20, 'Perspective offensive détaillée')
        assert.ok(st.bluePerspective.length > 20, 'Perspective défensive détaillée')
        assert.ok(st.technicalInsight.length > 20, 'Insight technique présent')
        assert.ok(st.actionableChecklist.length >= 2, 'Au moins 2 points de checklist')
      }
    }
  })

  test('Le prompt système de raisonnement cognitif impose une structure rigoureuse', () => {
    assert.match(DEEP_REASONING_PROMPT_SYSTEM, /Surface & Modélisation/)
    assert.match(DEEP_REASONING_PROMPT_SYSTEM, /Anatomie de la Faille \/ 0-Day/)
    assert.match(DEEP_REASONING_PROMPT_SYSTEM, /Rayon d'Impact/)
    assert.match(DEEP_REASONING_PROMPT_SYSTEM, /Stratégie Défensive Multi-Couches/)
  })
})
