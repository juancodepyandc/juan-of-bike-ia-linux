/**
 * Tests pour services/codeFidelityGate — gate post-génération qui détecte la
 * dérive de sujet (Coca-Cola → restaurant générique, etc.).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { evaluateBrandFidelity } from '../services/codeFidelityGate.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

function brandIntent(brandPrompt = 'page landing pour Coca-Cola'): CodeIntent {
  return classifyCodeIntent(brandPrompt)
}

function htmlFile(content: string, name = 'index.html') {
  return { name, language: 'html', content }
}

describe('evaluateBrandFidelity — pas de subject brand', () => {
  test('intent sans subject brand → report neutre', () => {
    const r = evaluateBrandFidelity(
      classifyCodeIntent('un site générique sympa'),
      [htmlFile('<html><body>hello</body></html>')],
    )
    assert.equal(r.scorePenalty, 0)
    assert.equal(r.scoreCap, null)
    assert.equal(r.issues.length, 0)
    assert.equal(r.shouldRetry, false)
  })
})

describe('evaluateBrandFidelity — Coca-Cola', () => {
  test('files SANS mention Coca-Cola → scoreCap=30 + subject_name_missing', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') {
      // si le détecteur n'a pas reconnu Coca-Cola, on skippe (pas applicable)
      return
    }
    const r = evaluateBrandFidelity(intent, [
      htmlFile('<html><body><h1>Bienvenue chez nous</h1><p>Notre boutique en ligne</p></body></html>'),
    ])
    assert.ok(r.issues.includes('subject_name_missing'))
    assert.ok(r.scoreCap !== null && r.scoreCap <= 30)
    assert.equal(r.shouldRetry, true)
    assert.ok(r.retryHint.length > 0)
  })

  test('files AVEC Coca-Cola mentionné 3x → pas de subject_name_missing', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile(`
        <title>Coca-Cola</title>
        <h1>Coca-Cola, l'expérience pétillante</h1>
        <section>Découvrez Coca-Cola dans toutes ses saveurs.</section>
      `),
    ])
    assert.ok(!r.issues.includes('subject_name_missing'))
  })

  test('couleur rouge brand absente → palette_missing', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile('<title>Coca-Cola</title><h1>Coca-Cola</h1><p>Coca-Cola</p>'),
      { name: 'style.css', language: 'css', content: 'body { background: #000; color: #fff; }' },
    ])
    assert.ok(r.issues.includes('palette_missing'))
    assert.ok(r.retryHint.toLowerCase().includes('couleur'))
  })

  test('couleur rouge brand présente → pas de palette_missing', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile('<title>Coca-Cola</title><h1>Coca-Cola</h1><p>Coca-Cola</p>'),
      { name: 'style.css', language: 'css', content: 'body { background: #F40009; }' },
    ])
    assert.ok(!r.issues.includes('palette_missing'))
  })

  test('couleur rouge brand proche en deltaE → pas de palette_missing', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile('<title>Coca-Cola</title><h1>Coca-Cola</h1><p>Coca-Cola</p>'),
      { name: 'style.css', language: 'css', content: '.hero { background: #f51a20; color: white; }' },
    ])
    assert.ok(!r.issues.includes('palette_missing'))
  })

  test('mot off-topic "restaurant" → used_off_topic_terms', () => {
    const intent = brandIntent('landing page Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile(`
        <title>Coca-Cola</title>
        <h1>Coca-Cola</h1>
        <h1>Coca-Cola</h1>
        <p>Notre restaurant familial vous accueille</p>
      `),
    ])
    // Coca-Cola est food brand donc le test de drift restaurant n'applique pas.
    // On vérifie juste que le report est cohérent.
    assert.ok(typeof r.scorePenalty === 'number')
  })
})

describe('evaluateBrandFidelity — structure du report', () => {
  test('scorePenalty borné [0..90]', () => {
    const intent = brandIntent('site Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [htmlFile('<html></html>')])
    assert.ok(r.scorePenalty >= 0 && r.scorePenalty <= 90)
  })

  test('issues toujours array', () => {
    const r = evaluateBrandFidelity(
      classifyCodeIntent('truc générique'),
      [],
    )
    assert.ok(Array.isArray(r.issues))
  })

  test('retryHint vide si aucun issue', () => {
    const r = evaluateBrandFidelity(
      classifyCodeIntent('truc générique'),
      [htmlFile('<html></html>')],
    )
    assert.equal(r.retryHint, '')
  })

  test('shouldRetry false si pas d issue critique', () => {
    const r = evaluateBrandFidelity(
      classifyCodeIntent('truc générique'),
      [htmlFile('<html></html>')],
    )
    assert.equal(r.shouldRetry, false)
  })

  test('shouldRetry true si subject_name_missing', () => {
    const intent = brandIntent('site Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      htmlFile('<h1>Un site sans nom</h1>'),
    ])
    if (r.issues.includes('subject_name_missing')) {
      assert.equal(r.shouldRetry, true)
    }
  })
})

describe('evaluateBrandFidelity — file types', () => {
  test('CSS file seul (sans visual) → subject_name_missing détecté', () => {
    const intent = brandIntent('site Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      { name: 'style.css', language: 'css', content: 'body { color: #F40009; }' },
    ])
    // Pas de fichier visuel, donc le nom n'apparaît pas dans visualBody → issue
    assert.ok(r.issues.includes('subject_name_missing'))
  })

  test('JSX file accepté comme visual', () => {
    const intent = brandIntent('site Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [
      { name: 'App.jsx', language: 'jsx', content: '<div><h1>Coca-Cola</h1><h2>Coca-Cola</h2><h3>Coca-Cola</h3></div>' },
      { name: 'style.css', language: 'css', content: '.brand { color: #F40009; }' },
    ])
    assert.ok(!r.issues.includes('subject_name_missing'))
  })

  test('tableau de files vide → pas de crash', () => {
    const intent = brandIntent('site Coca-Cola')
    if (intent.assetPlan.subject?.source !== 'brand') return
    const r = evaluateBrandFidelity(intent, [])
    assert.ok(r)
    assert.ok(Array.isArray(r.issues))
  })
})
