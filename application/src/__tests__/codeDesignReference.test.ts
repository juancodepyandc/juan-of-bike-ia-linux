/**
 * Tests pour services/codeDesignReference — détection variant + ref design.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectSubjectVariant,
  buildPremiumDesignReferenceBlock,
  PREMIUM_HTML_REFERENCE,
  THREE_D_SCENE_REFERENCE,
} from '../services/codeDesignReference.ts'

describe('PREMIUM_HTML_REFERENCE / THREE_D_SCENE_REFERENCE', () => {
  test('PREMIUM_HTML_REFERENCE est un HTML doctype', () => {
    assert.ok(PREMIUM_HTML_REFERENCE.startsWith('<!DOCTYPE html>'))
    assert.ok(PREMIUM_HTML_REFERENCE.length > 1000)
  })

  test('THREE_D_SCENE_REFERENCE contient three.js', () => {
    assert.ok(THREE_D_SCENE_REFERENCE.startsWith('<!DOCTYPE html>'))
    assert.ok(/three/i.test(THREE_D_SCENE_REFERENCE))
  })
})

describe('detectSubjectVariant', () => {
  test('"desktop app electron" → desktop', () => {
    assert.equal(detectSubjectVariant('desktop app electron'), 'desktop')
  })

  test('"react native mobile" → mobile', () => {
    assert.equal(detectSubjectVariant('react native mobile app'), 'mobile')
  })

  test('"scene three.js webgl" → 3d_scene', () => {
    assert.equal(detectSubjectVariant('scene three.js webgl'), '3d_scene')
  })

  test('"jeu tetris" → game', () => {
    assert.equal(detectSubjectVariant('jeu tetris arcade'), 'game')
  })

  test('"dashboard admin analytics" → dashboard', () => {
    assert.equal(detectSubjectVariant('dashboard admin analytics'), 'dashboard')
  })

  test('"boutique ecommerce" → ecommerce', () => {
    assert.equal(detectSubjectVariant('boutique ecommerce avec panier'), 'ecommerce')
  })

  test('"portfolio developer" → portfolio', () => {
    assert.equal(detectSubjectVariant('portfolio developer freelance'), 'portfolio')
  })

  test('"saas pricing platform" → saas', () => {
    assert.equal(detectSubjectVariant('saas pricing platform pro'), 'saas')
  })

  test('"landing page hero" → landing', () => {
    assert.equal(detectSubjectVariant('landing page hero CTA'), 'landing')
  })

  test('prompt sans match → null', () => {
    assert.equal(detectSubjectVariant('un truc random sans contexte'), null)
  })

  test('case-insensitive', () => {
    assert.equal(detectSubjectVariant('PORTFOLIO'), 'portfolio')
  })

  test('desktop prioritaire sur landing', () => {
    assert.equal(detectSubjectVariant('desktop app avec landing'), 'desktop')
  })

  test('game prioritaire sur landing', () => {
    assert.equal(detectSubjectVariant('jeu tetris avec page accueil'), 'game')
  })

  test('3d_scene prioritaire sur game', () => {
    assert.equal(detectSubjectVariant('three.js jeu 3d'), '3d_scene')
  })
})

describe('buildPremiumDesignReferenceBlock', () => {
  test('sans prompt → bloc avec REFERENCE DESIGN', () => {
    const r = buildPremiumDesignReferenceBlock()
    assert.ok(r.includes('REFERENCE DESIGN'))
    assert.ok(r.length > 200)
  })

  test('avec promptHint "landing" → variant détecté + section', () => {
    const r = buildPremiumDesignReferenceBlock('landing page coca')
    assert.ok(r.length > 200)
  })

  test('avec prompt 3d → THREE_D_SCENE_REFERENCE utilisé', () => {
    const r = buildPremiumDesignReferenceBlock('scene three.js avec orbit controls')
    assert.ok(r.includes('STARTER THREE.JS') || r.includes('three'))
  })

  test('avec prompt landing → reference standard HTML', () => {
    const r = buildPremiumDesignReferenceBlock('landing page')
    assert.ok(r.includes('STARTER HTML') || r.includes('NIVEAU'))
  })

  test('forcedVariant=brand_landing override la détection', () => {
    const r = buildPremiumDesignReferenceBlock('coca-cola', 'brand_landing')
    assert.ok(r.length > 200)
  })

  test('forcedVariant inconnu → ignoré', () => {
    const r = buildPremiumDesignReferenceBlock('landing', 'nonexistent_variant')
    // Doit toujours fonctionner avec la détection prompt
    assert.ok(r.includes('REFERENCE DESIGN'))
  })

  test('3d_scene → bullets ESM importmap mentionnés', () => {
    const r = buildPremiumDesignReferenceBlock('three.js scene webgl')
    assert.ok(r.includes('importmap') || r.includes('three@'))
  })

  test('reference non-3d → bullets oklch palette', () => {
    const r = buildPremiumDesignReferenceBlock('landing classique')
    assert.ok(r.includes('oklch') || r.includes('Inter') || r.includes('palette'))
  })
})

describe('buildPremiumDesignReferenceBlock — déterminisme', () => {
  test('mêmes args → même output', () => {
    const a = buildPremiumDesignReferenceBlock('portfolio')
    const b = buildPremiumDesignReferenceBlock('portfolio')
    assert.equal(a, b)
  })

  test('args différents → outputs différents', () => {
    const a = buildPremiumDesignReferenceBlock('three.js')
    const b = buildPremiumDesignReferenceBlock('landing')
    assert.notEqual(a, b)
  })
})
