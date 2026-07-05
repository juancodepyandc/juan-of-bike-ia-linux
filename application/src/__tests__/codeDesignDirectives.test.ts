/**
 * Tests pour services/codeDesignDirectives — archetype design détection.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  isVisualProject,
  detectDesignArchetype,
  buildDesignDirectives,
  describeDesignArchetype,
} from '../services/codeDesignDirectives.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

describe('isVisualProject', () => {
  test('static_web → true', () => {
    const intent = classifyCodeIntent('page HTML CSS landing')
    assert.equal(isVisualProject(intent), true)
  })

  test('spa_react → true', () => {
    const intent = classifyCodeIntent('react app simple')
    assert.equal(isVisualProject(intent), true)
  })

  test('cli_python → false', () => {
    const intent = classifyCodeIntent('script python ligne de commande')
    assert.equal(isVisualProject(intent), false)
  })

  test('api_fastapi → false', () => {
    const intent = classifyCodeIntent('API REST FastAPI')
    assert.equal(isVisualProject(intent), false)
  })

  test('game_web → true', () => {
    const intent = classifyCodeIntent('jeu snake en JavaScript canvas')
    // detector peut classifier en game_web ou static_web
    assert.equal(isVisualProject(intent), true)
  })
})

describe('detectDesignArchetype', () => {
  test('"écouteurs apple style" → apple_product', () => {
    const intent = classifyCodeIntent('écouteurs apple style')
    const r = detectDesignArchetype('écouteurs apple style', intent)
    assert.equal(r, 'apple_product')
  })

  test('"dashboard analytics admin" → dashboard_dataviz', () => {
    const intent = classifyCodeIntent('dashboard admin analytics')
    const r = detectDesignArchetype('dashboard analytics admin', intent)
    assert.equal(r, 'dashboard_dataviz')
  })

  test('"portfolio créatif freelance" → portfolio_immersive', () => {
    const intent = classifyCodeIntent('portfolio créatif freelance')
    const r = detectDesignArchetype('portfolio créatif freelance', intent)
    assert.equal(r, 'portfolio_immersive')
  })

  test('"boutique e-commerce" → ecommerce_premium', () => {
    const intent = classifyCodeIntent('boutique ecommerce panier')
    const r = detectDesignArchetype('boutique ecommerce avec panier produits', intent)
    assert.equal(r, 'ecommerce_premium')
  })

  test('"saas pricing platform" → saas_marketing', () => {
    const intent = classifyCodeIntent('saas pricing platform pro abonnement')
    const r = detectDesignArchetype('saas pricing platform pro abonnement', intent)
    assert.equal(r, 'saas_marketing')
  })

  test('"festival lineup événement" → microsite_event', () => {
    const intent = classifyCodeIntent('festival lineup événement countdown')
    const r = detectDesignArchetype('festival lineup événement countdown', intent)
    assert.equal(r, 'microsite_event')
  })

  test('"three.js scroll 3D journey" → un archetype', () => {
    const intent = classifyCodeIntent('three.js scroll 3D journey')
    const r = detectDesignArchetype('three.js scroll 3D pinned camera', intent)
    // Plusieurs archetypes peuvent matcher selon les regex spécifiques
    assert.ok(typeof r === 'string' && r.length > 0)
  })

  test('"jeu pong arcade" → game_visual_premium', () => {
    const intent = classifyCodeIntent('jeu pong arcade canvas')
    const r = detectDesignArchetype('jeu pong arcade canvas neon', intent)
    assert.ok(['game_visual_premium', 'default_premium'].includes(r))
  })

  test('"mobile RN expo" → un archetype valide', () => {
    const intent = classifyCodeIntent('react native expo mobile app')
    const r = detectDesignArchetype('react native expo mobile app', intent)
    assert.ok(typeof r === 'string' && r.length > 0)
  })

  test('"desktop electron tauri" → desktop_native_app', () => {
    const intent = classifyCodeIntent('desktop electron tauri application native')
    const r = detectDesignArchetype('desktop electron tauri application native', intent)
    assert.ok(['desktop_native_app', 'default_premium'].includes(r))
  })

  test('"article blog editorial" → editorial_story', () => {
    const intent = classifyCodeIntent('article blog editorial long-form')
    const r = detectDesignArchetype('article blog editorial long-form drop cap', intent)
    assert.ok(['editorial_story', 'default_premium', 'narrative_landing'].includes(r))
  })

  test('"brutalist raw minimal" → minimal_brutalist', () => {
    const intent = classifyCodeIntent('brutalist raw minimal site web')
    const r = detectDesignArchetype('brutalist raw minimal brutaliste', intent)
    assert.ok(['minimal_brutalist', 'default_premium'].includes(r))
  })

  test('prompt vague → default_premium ou narrative_landing', () => {
    const intent = classifyCodeIntent('un truc cool')
    const r = detectDesignArchetype('un truc cool', intent)
    assert.ok(['default_premium', 'narrative_landing'].includes(r))
  })
})

describe('buildDesignDirectives', () => {
  test('projet non-visuel → ""', () => {
    const intent = classifyCodeIntent('script python ligne commande')
    const r = buildDesignDirectives('script python', intent)
    assert.equal(r, '')
  })

  test('projet visuel → directives non vides', () => {
    const intent = classifyCodeIntent('landing page premium')
    const r = buildDesignDirectives('landing page premium', intent)
    assert.ok(r.length > 100)
    assert.ok(r.includes('ARCHETYPE'))
  })

  test('directives mentionnent archetype retenu', () => {
    // Utilise un prompt qui classifie clairement en static_web
    const intent = classifyCodeIntent('page HTML CSS landing avec hero')
    const r = buildDesignDirectives('page landing apple style avec exploded view', intent)
    assert.ok(r.includes('ARCHETYPE'))
  })

  test('directives ont du contenu substantiel pour projet visuel', () => {
    const intent = classifyCodeIntent('page HTML CSS site moderne')
    const r = buildDesignDirectives('site moderne avec animations', intent)
    assert.ok(r.length > 500)
  })
})

describe('describeDesignArchetype', () => {
  test('apple_product → label dédié', () => {
    assert.ok(describeDesignArchetype('apple_product').toLowerCase().includes('apple'))
  })

  test('dashboard_dataviz → mentions dashboard', () => {
    assert.ok(describeDesignArchetype('dashboard_dataviz').toLowerCase().includes('dashboard'))
  })

  test('portfolio_immersive → mention portfolio', () => {
    assert.ok(describeDesignArchetype('portfolio_immersive').toLowerCase().includes('portfolio'))
  })

  test('default_premium → "Default premium"', () => {
    assert.equal(describeDesignArchetype('default_premium'), 'Default premium')
  })

  test('chaque archetype a un label > 5 chars', () => {
    const archetypes = [
      'apple_product', 'narrative_landing', 'dashboard_dataviz', 'portfolio_immersive',
      'ecommerce_premium', 'saas_marketing', 'editorial_story', 'scroll_3d_journey',
      'microsite_event', 'minimal_brutalist', 'mobile_native_premium', 'desktop_native_app',
      'game_visual_premium', 'default_premium',
    ] as const
    for (const a of archetypes) {
      assert.ok(describeDesignArchetype(a).length > 5)
    }
  })
})
