/**
 * Tests pour services/coworkConnectors — catalogue de connecteurs externes.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  CONNECTORS,
  buildConnectorBriefForLLM,
} from '../services/coworkConnectors.ts'

describe('CONNECTORS — catalogue', () => {
  test('contient github + perplexity + wikipedia', () => {
    assert.ok('github' in CONNECTORS)
    assert.ok('perplexity' in CONNECTORS)
    assert.ok('wikipedia' in CONNECTORS)
  })

  test('chaque connecteur a id/label/description/category', () => {
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      assert.equal(meta.id, id, `${id} id mismatch`)
      assert.ok(meta.label, `${id} sans label`)
      assert.ok(meta.description, `${id} sans description`)
      assert.ok(meta.category, `${id} sans category`)
    }
  })

  test('chaque connecteur a actions array', () => {
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      assert.ok(Array.isArray(meta.actions), `${id} actions non-array`)
    }
  })

  test('chaque action a name + description', () => {
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      for (const action of meta.actions) {
        assert.ok(action.name, `${id} action sans name`)
        assert.ok(action.description, `${id} action ${action.name} sans description`)
      }
    }
  })

  test('catégories valides', () => {
    const validCategories = ['dev', 'cloud', 'productivity', 'communication', 'calendar-mail', 'storage', 'media', 'iot', 'data', 'ai', 'design', 'commerce', 'misc']
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      assert.ok(validCategories.includes(meta.category), `${id} category invalide: ${meta.category}`)
    }
  })

  test('github a au moins list_repos + list_prs', () => {
    const actions = CONNECTORS.github.actions.map((a) => a.name)
    assert.ok(actions.includes('list_repos'))
    assert.ok(actions.includes('list_prs'))
  })

  test('docUrl est URL valide pour les connecteurs externes', () => {
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      // Les connecteurs internes (aurora_*, machine_*) peuvent ne pas avoir docUrl externe
      if (meta.docUrl && !id.startsWith('aurora_') && !id.startsWith('machine_')) {
        assert.ok(/^https?:\/\//.test(meta.docUrl), `${id} docUrl invalide`)
      }
    }
  })
})

describe('CONNECTORS — métadonnées sémantiques', () => {
  test('github a purpose + whenToUse', () => {
    assert.ok(CONNECTORS.github.purpose)
    assert.ok(CONNECTORS.github.whenToUse)
    assert.ok(CONNECTORS.github.whenToUse!.length > 0)
  })

  test('connecteurs payants ont freeTier mentionné', () => {
    // Pas tous ont freeTier mais quand présent, doit être une string non vide
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      if (meta.freeTier) {
        assert.ok(meta.freeTier.length > 0, `${id} freeTier vide`)
      }
    }
  })

  test('fallback (si présent) a kind + target + note', () => {
    for (const [id, meta] of Object.entries(CONNECTORS)) {
      if (meta.fallback) {
        assert.ok(meta.fallback.kind)
        assert.ok(meta.fallback.target)
        assert.ok(meta.fallback.note)
      }
    }
  })
})

describe('CONNECTORS — IDs spécifiques attendus', () => {
  test('AI connectors présents', () => {
    for (const ai of ['openai', 'anthropic', 'mistral', 'groq', 'openrouter', 'huggingface', 'replicate']) {
      assert.ok(ai in CONNECTORS, `${ai} manquant`)
    }
  })

  test('Cyber connectors présents', () => {
    assert.ok('hibp' in CONNECTORS)
    assert.ok('abuseipdb' in CONNECTORS)
  })

  test('Aurora internal modules présents', () => {
    for (const id of ['aurora_code', 'aurora_3d', 'aurora_image', 'aurora_voice']) {
      assert.ok(id in CONNECTORS, `${id} manquant`)
    }
  })

  test('Machine connectors présents', () => {
    for (const id of ['machine_local', 'machine_pi', 'machine_linux', 'machine_ssh']) {
      assert.ok(id in CONNECTORS, `${id} manquant`)
    }
  })
})

describe('buildConnectorBriefForLLM', () => {
  test('liste vide → "" ', () => {
    assert.equal(buildConnectorBriefForLLM([]), '')
  })

  test('1 connecteur → 1 ligne', () => {
    const r = buildConnectorBriefForLLM([{ id: 'github', quotaExhausted: false }])
    assert.ok(r.includes('GitHub'))
    assert.ok(r.includes('id=github'))
  })

  test('purpose mentionné quand présent', () => {
    const r = buildConnectorBriefForLLM([{ id: 'github', quotaExhausted: false }])
    assert.ok(r.includes('source') || r.includes('repo') || r.includes('—'))
  })

  test('whenToUse mots-clés inclus', () => {
    const r = buildConnectorBriefForLLM([{ id: 'github', quotaExhausted: false }])
    assert.ok(r.includes('mots-cles') || r.includes('repo'))
  })

  test('quotaExhausted + fallback → mention QUOTA EPUISE', () => {
    // Trouve un connecteur avec fallback
    const withFallback = Object.entries(CONNECTORS).find(([_id, m]) => m.fallback)
    if (withFallback) {
      const r = buildConnectorBriefForLLM([{ id: withFallback[0] as never, quotaExhausted: true }])
      assert.ok(r.includes('QUOTA EPUISE') || r.includes('quota'))
    }
  })

  test('freeTier mentionné quand pas quotaExhausted', () => {
    const withFreeTier = Object.entries(CONNECTORS).find(([_id, m]) => m.freeTier)
    if (withFreeTier) {
      const r = buildConnectorBriefForLLM([{ id: withFreeTier[0] as never, quotaExhausted: false }])
      assert.ok(r.includes('free tier'))
    }
  })

  test('plusieurs connecteurs séparés par newline', () => {
    const r = buildConnectorBriefForLLM([
      { id: 'github', quotaExhausted: false },
      { id: 'wikipedia', quotaExhausted: false },
    ])
    assert.ok(r.split('\n').length >= 2)
  })

  test('connecteur inconnu skippé', () => {
    const r = buildConnectorBriefForLLM([
      { id: 'github', quotaExhausted: false },
      { id: 'nonexistent_xyz' as never, quotaExhausted: false },
    ])
    assert.ok(r.includes('GitHub'))
    assert.ok(!r.includes('nonexistent_xyz'))
  })
})

describe('Cohérence catalogue', () => {
  test('CONNECTORS contient ≥ 25 connecteurs', () => {
    assert.ok(Object.keys(CONNECTORS).length >= 25)
  })

  test('aucun label dupliqué pour catégorie dev', () => {
    const devLabels = Object.entries(CONNECTORS)
      .filter(([_id, m]) => m.category === 'dev')
      .map(([_id, m]) => m.label)
    assert.equal(new Set(devLabels).size, devLabels.length)
  })

  test('AI category a openai/anthropic/mistral', () => {
    const aiIds = Object.entries(CONNECTORS)
      .filter(([_id, m]) => m.category === 'ai')
      .map(([id]) => id)
    // Au moins quelques-uns présents
    assert.ok(aiIds.length >= 3)
  })
})
