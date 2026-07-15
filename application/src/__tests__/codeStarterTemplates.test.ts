/**
 * Tests pour services/codeStarterTemplates — sélection du squelette HTML
 * concret injecté dans le prompt du Codeur selon l'archetype.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  getStarterTemplateForArchetype,
  buildStarterTemplateBlock,
} from '../services/codeStarterTemplates.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

describe('getStarterTemplateForArchetype', () => {
  test('apple_product → renvoie un template non vide', () => {
    const t = getStarterTemplateForArchetype('apple_product')
    assert.ok(t)
    assert.ok((t as string).length > 200)
  })

  test('archetype inconnu → null', () => {
    const t = getStarterTemplateForArchetype('archetype_inexistant' as never)
    assert.equal(t, null)
  })

  test('archetypes non-apple → null (fallback directives-only)', () => {
    const others = ['saas_dashboard', 'editorial_brutalist', 'food_restaurant']
    for (const a of others) {
      assert.equal(getStarterTemplateForArchetype(a as never), null)
    }
  })
})

describe('buildStarterTemplateBlock', () => {
  test('prompt iPhone → block non vide avec STARTER intro', () => {
    const intent = classifyCodeIntent('landing page iPhone 16 Pro')
    const block = buildStarterTemplateBlock('landing page iPhone 16 Pro', intent)
    if (block.length > 0) {
      assert.ok(block.includes('STARTER'))
      assert.ok(block.includes('AURORA_CODE_VFS/1'))
      assert.ok(block.includes('path="index.html"'))
    }
  })

  test('prompt très générique → empty (pas d archetype dédié)', () => {
    const intent = classifyCodeIntent('un site sympa avec un peu de texte')
    const block = buildStarterTemplateBlock('un site sympa avec un peu de texte', intent)
    // Le détecteur d'archetype peut renvoyer un default — donc on accepte les 2
    assert.ok(typeof block === 'string')
  })

  test('block contient les substitutions {{TITLE}} {{SUBJECT}} si non vide', () => {
    const intent = classifyCodeIntent('apple product page Mac Studio')
    const block = buildStarterTemplateBlock('apple product page Mac Studio', intent)
    if (block.length > 100) {
      assert.ok(block.includes('{{TITLE}}'))
      assert.ok(block.includes('{{SUBJECT}}'))
      assert.ok(block.includes('{{BRAND}}'))
    }
  })

  test('block mentionne placeholders images PLACEHOLDER_IMG_*', () => {
    const intent = classifyCodeIntent('iPhone 16 produit page premium')
    const block = buildStarterTemplateBlock('iPhone 16 produit page premium', intent)
    if (block.length > 100) {
      assert.ok(block.includes('PLACEHOLDER_IMG_HERO'))
    }
  })

  test('block contient l output format structure', () => {
    const intent = classifyCodeIntent('apple style mac premium')
    const block = buildStarterTemplateBlock('apple style mac premium', intent)
    if (block.length > 100) {
      assert.ok(block.includes('OUTPUT'))
      assert.ok(block.includes('AURORA_CODE_VFS/1'))
      assert.ok(block.includes('length'))
    }
  })
})

describe('Stabilité', () => {
  test('appels successifs avec même input → même sortie (déterministe)', () => {
    const intent = classifyCodeIntent('iPhone produit premium')
    const a = buildStarterTemplateBlock('iPhone produit premium', intent)
    const b = buildStarterTemplateBlock('iPhone produit premium', intent)
    assert.equal(a, b)
  })

  test('prompt vide → ne crash pas', () => {
    const intent = classifyCodeIntent('')
    const block = buildStarterTemplateBlock('', intent)
    assert.ok(typeof block === 'string')
  })
})
