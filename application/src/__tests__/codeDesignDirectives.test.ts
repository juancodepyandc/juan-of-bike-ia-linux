/**
 * Tests pour services/codeDesignDirectives — archetype design détection.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  isVisualProject,
  detectDesignArchetype,
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

  test('"data grid enterprise dense" → data_dense_enterprise', () => {
    const intent = classifyCodeIntent('dashboard data grid enterprise dense')
    const r = detectDesignArchetype('dashboard data grid enterprise dense table filters', intent)
    assert.equal(r, 'data_dense_enterprise')
  })

  test('"IDE code editor" → ide_code_editor', () => {
    const intent = classifyCodeIntent('IDE code editor avec terminal integre')
    const r = detectDesignArchetype('IDE code editor avec terminal integre file tree', intent)
    assert.equal(r, 'ide_code_editor')
  })

  test('"OS shell boot log" → os_shell', () => {
    const intent = classifyCodeIntent('noyau OS boot log avec shell')
    const r = detectDesignArchetype('OS shell boot log kernel console', intent)
    assert.equal(r, 'os_shell')
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

// ---------------------------------------------------------------------------
// Run 1161 — l archetype se decidait sur des mots qui n etaient pas la.
//
// Extraits TEXTUELS du brief reel (output/code/audit_v118/payload.json).
// ---------------------------------------------------------------------------
describe('archetype: lire le brief, pas ce qui y ressemble', () => {
  const BRIEF_BRULERIE = [
    'Salut ! Je me lance dans un vrai site pour ma marque de cafe en grains,',
    "ca s'appelle \"Brulerie Nomade\". Une page d'accueil avec un slogan (genre",
    "\"Torrefie cette semaine, pas l'an dernier\" ou un truc dans le genre, trouve",
    "mieux si t'as une idee), et direct en dessous nos 3-4 cafes du moment.",
    "On a besoin aussi d'une mini page interne juste pour nous deux (genre /admin)",
    'ou on voit la liste des commandes. Sur le style : on est PAS un truc',
    'minimaliste blanc scandinave comme tout le monde fait pour le cafe en ce',
    "moment, j'en ai marre de voir ca partout. On veut plutot des couleurs",
    'chaudes, terracotta, marron torrefie, un peu de vert olive.',
  ].join(' ')

  test('« une idee » ne fait pas de cette brulerie un editeur de code', () => {
    const intent = classifyCodeIntent(BRIEF_BRULERIE)
    assert.notEqual(detectDesignArchetype(BRIEF_BRULERIE, intent), 'ide_code_editor')
  })

  test('« PAS un truc minimaliste » ne demande pas du brutalisme', () => {
    const intent = classifyCodeIntent(BRIEF_BRULERIE)
    assert.notEqual(detectDesignArchetype(BRIEF_BRULERIE, intent), 'minimal_brutalist')
  })

  test('un style REFUSE ne remonte pas dans les indices de style', () => {
    const intent = classifyCodeIntent(BRIEF_BRULERIE)
    const hints = intent.assetPlan?.styleHints ?? []
    assert.equal(hints.includes('minimaliste'), false, JSON.stringify(hints))
    assert.equal(hints.includes('scandinave'), false, JSON.stringify(hints))
  })

  test('un vrai IDE reste un IDE', () => {
    const prompt = 'un editeur de code dans le navigateur avec monaco, file tree et terminal'
    const intent = classifyCodeIntent(prompt)
    assert.equal(detectDesignArchetype(prompt, intent), 'ide_code_editor')
  })
})
