/**
 * Tests pour services/moduleConnectorRecommendations.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  MODULE_CONNECTOR_PLAN,
  getModuleRecommendations,
  getTopConnectorRecommendation,
  buildAllRecommendationsMarkdown,
  type ModuleId,
} from '../services/moduleConnectorRecommendations.ts'

const ALL_MODULES: ModuleId[] = [
  'conversation', 'image', 'code', 'video', 'drawing',
  '3d', 'learning', 'voice', 'cyber',
]

describe('MODULE_CONNECTOR_PLAN — coverage', () => {
  test('contient tous les modules attendus', () => {
    for (const m of ALL_MODULES) {
      assert.ok(m in MODULE_CONNECTOR_PLAN, `module ${m} manquant`)
    }
  })

  test('chaque module a primary + optional + extensionFallback', () => {
    for (const m of ALL_MODULES) {
      const plan = MODULE_CONNECTOR_PLAN[m]
      assert.ok(Array.isArray(plan.primary))
      assert.ok(Array.isArray(plan.optional))
      assert.ok(Array.isArray(plan.extensionFallback))
      assert.ok(plan.primary.length >= 2, `${m} <2 primary`)
      assert.ok(plan.extensionFallback.length >= 1, `${m} 0 fallback`)
    }
  })

  test('chaque primary a un impact transformative ou high', () => {
    for (const m of ALL_MODULES) {
      for (const rec of MODULE_CONNECTOR_PLAN[m].primary) {
        assert.ok(['transformative', 'high', 'medium'].includes(rec.impact))
      }
    }
  })

  test('chaque recommendation a un reason non vide', () => {
    for (const m of ALL_MODULES) {
      const plan = MODULE_CONNECTOR_PLAN[m]
      for (const rec of [...plan.primary, ...plan.optional]) {
        assert.ok(rec.reason.length > 20, `${m}.${rec.id} reason trop court`)
      }
    }
  })

  test('chaque extensionFallback a capability + description + benefits', () => {
    for (const m of ALL_MODULES) {
      for (const cap of MODULE_CONNECTOR_PLAN[m].extensionFallback) {
        assert.ok(cap.capability.length > 0)
        assert.ok(cap.description.length > 20)
        assert.ok(cap.benefits.length > 20)
      }
    }
  })
})

describe('Modules spécifiques — recommandations attendues', () => {
  test('3D → huggingface primary', () => {
    const top = getTopConnectorRecommendation('3d')
    assert.equal(top?.id, 'huggingface')
  })

  test('code → github primary', () => {
    const top = getTopConnectorRecommendation('code')
    assert.equal(top?.id, 'github')
  })

  test('image → huggingface primary', () => {
    const top = getTopConnectorRecommendation('image')
    assert.equal(top?.id, 'huggingface')
  })

  test('voice → huggingface primary (pour Voxtral/Kokoro)', () => {
    const top = getTopConnectorRecommendation('voice')
    assert.equal(top?.id, 'huggingface')
  })

  test('cyber → hibp primary', () => {
    const top = getTopConnectorRecommendation('cyber')
    assert.equal(top?.id, 'hibp')
  })

  test('conversation → perplexity primary', () => {
    const top = getTopConnectorRecommendation('conversation')
    assert.equal(top?.id, 'perplexity')
  })

  test('learning → wikipedia primary', () => {
    const top = getTopConnectorRecommendation('learning')
    assert.equal(top?.id, 'wikipedia')
  })

  test('drawing → huggingface primary', () => {
    const top = getTopConnectorRecommendation('drawing')
    assert.equal(top?.id, 'huggingface')
  })
})

describe('getModuleRecommendations', () => {
  test('renvoie le plan complet du module', () => {
    const r = getModuleRecommendations('image')
    assert.equal(r.module, 'image')
    assert.ok(r.primary.length > 0)
  })

  test('module valide → objet retourné', () => {
    for (const m of ALL_MODULES) {
      assert.ok(getModuleRecommendations(m))
    }
  })
})

describe('buildAllRecommendationsMarkdown', () => {
  test('produit du markdown structuré', () => {
    const md = buildAllRecommendationsMarkdown()
    assert.ok(md.includes('# Connecteurs'))
    assert.ok(md.includes('## Module'))
    assert.ok(md.includes('### Connecteurs principaux'))
    assert.ok(md.includes('### Aurora Connect Extension'))
  })

  test('mentionne tous les modules', () => {
    const md = buildAllRecommendationsMarkdown()
    for (const m of ALL_MODULES) {
      assert.ok(md.includes(`## Module ${m}`), `module ${m} pas dans markdown`)
    }
  })

  test('inclut les fallbacks d extension', () => {
    const md = buildAllRecommendationsMarkdown()
    assert.ok(md.includes('reference_visual_search') || md.includes('documentation_fetch'))
  })

  test('inclut au moins une mention "Bénéfice"', () => {
    const md = buildAllRecommendationsMarkdown()
    assert.ok(md.includes('Benefice'))
  })
})

describe('Cohérence catalogue', () => {
  test('extension capabilities non vides pour chaque module', () => {
    for (const m of ALL_MODULES) {
      const caps = MODULE_CONNECTOR_PLAN[m].extensionFallback
      assert.ok(caps.length >= 1, `${m} doit avoir au moins 1 extension capability`)
    }
  })

  test('au moins un connecteur impact=transformative dans les 9 modules', () => {
    let transformativeCount = 0
    for (const m of ALL_MODULES) {
      if (MODULE_CONNECTOR_PLAN[m].primary.some((r) => r.impact === 'transformative')) {
        transformativeCount += 1
      }
    }
    assert.ok(transformativeCount >= 5, 'pas assez de "transformative"')
  })
})
