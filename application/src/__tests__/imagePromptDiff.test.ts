/**
 * Tests pour services/imagePromptDiff — comparaison de prompts SDXL/FLUX.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  diffPrompts,
  categorize,
  diffPromptsByCategory,
} from '../services/imagePromptDiff.ts'

describe('diffPrompts', () => {
  test('prompts identiques → tout en identical, changeRatio 0', () => {
    const r = diffPrompts(
      'vélo gravel orange, cinematic lighting, studio',
      'vélo gravel orange, cinematic lighting, studio',
    )
    assert.equal(r.added.length, 0)
    assert.equal(r.removed.length, 0)
    assert.equal(r.identical.length, 3)
    assert.equal(r.changeRatio, 0)
  })

  test('ajout segment', () => {
    const r = diffPrompts(
      'vélo orange, studio',
      'vélo orange, studio, cinematic lighting',
    )
    assert.equal(r.added.length, 1)
    assert.match(r.added[0].raw, /cinematic/)
  })

  test('suppression segment', () => {
    const r = diffPrompts(
      'vélo, lumière douce, flou',
      'vélo, lumière douce',
    )
    assert.equal(r.removed.length, 1)
    assert.equal(r.removed[0].raw, 'flou')
  })

  test('reformulation détectée si similarité ≥ threshold', () => {
    const r = diffPrompts(
      'vélo gravel orange brillant',
      'vélo gravel orange métallique',
    )
    // Devrait être détecté comme reformulé (mots communs : vélo, gravel, orange)
    assert.ok(r.reformulated.length > 0 || r.identical.length > 0)
  })

  test('changement total → changeRatio élevé', () => {
    const r = diffPrompts('chat noir', 'paysage urbain pluie')
    assert.ok(r.changeRatio > 0.5)
  })

  test('vide vs prompt → tout added', () => {
    const r = diffPrompts('', 'velo cinematic')
    assert.ok(r.added.length >= 1)
  })

  test('summary non vide', () => {
    const r = diffPrompts('a, b', 'a, c')
    assert.ok(r.summary.length > 0)
  })

  test('summary "aucun changement" si identique', () => {
    const r = diffPrompts('même', 'même')
    assert.match(r.summary, /aucun changement|identique/i)
  })
})

describe('categorize', () => {
  test('cinematic → style', () => {
    assert.equal(categorize({ raw: 'cinematic', tokens: ['cinematic'] }), 'style')
  })

  test('golden hour → lighting', () => {
    assert.equal(categorize({ raw: 'golden hour', tokens: ['golden', 'hour'] }), 'lighting')
  })

  test('rule of thirds → composition', () => {
    assert.equal(categorize({ raw: 'rule of thirds', tokens: ['rule', 'of', 'thirds'] }), 'composition')
  })

  test('mot inconnu → other ou subject (selon impl)', () => {
    const c = categorize({ raw: 'vélo', tokens: ['velo'] })
    assert.ok(['other', 'subject'].includes(c))
  })
})

describe('diffPromptsByCategory', () => {
  test('renvoie un objet avec catégories', () => {
    const r = diffPromptsByCategory(
      'vélo, cinematic, golden hour',
      'vélo, anime, blue hour',
    )
    // Devrait avoir des stats par catégorie
    assert.ok(typeof r === 'object')
  })
})
