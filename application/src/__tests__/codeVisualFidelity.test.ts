/**
 * Tests pour services/codeVisualFidelity — gate qualité visuelle code généré.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  evaluateVisualFidelity,
  buildVisualFidelityCritique,
} from '../services/codeVisualFidelity.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const VISUAL_INTENT = classifyCodeIntent('landing page HTML CSS')
const NON_VISUAL_INTENT = classifyCodeIntent('script python ligne commande')

function html(content: string) {
  return { name: 'index.html', language: 'markup', content }
}
function css(content: string) {
  return { name: 'style.css', language: 'css', content }
}
function js(content: string) {
  return { name: 'app.js', language: 'javascript', content }
}

// Ces tests mesurent la barre VITRINE (richesse editoriale, profondeur,
// mouvement). Depuis la calibration par genre, le brief doit le declarer:
// une page seule et minuscule serait sinon jugee comme un OUTIL.
const SHOWCASE_BRIEF = 'landing page vitrine pour promouvoir notre marque'

describe('evaluateVisualFidelity — non-visual bypass', () => {
  test('projet non visuel → score 100 + bypass', () => {
    const r = evaluateVisualFidelity([{ name: 'main.py', language: 'python', content: 'print(1)' }], NON_VISUAL_INTENT)
    assert.equal(r.score, 100)
    assert.equal(r.passed, true)
  })
})

describe('evaluateVisualFidelity — pas de HTML/CSS', () => {
  test('aucun HTML/CSS → score 0', () => {
    const r = evaluateVisualFidelity([], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.equal(r.score, 0)
    assert.equal(r.passed, false)
    assert.ok(r.failedChecks.includes('has_markup'))
  })
})

describe('evaluateVisualFidelity — page scolaire (rejet)', () => {
  test('"Bienvenue" + fond rouge plat → bloque (scolaire)', () => {
    const page = `<html><body><h1>Bienvenue chez X</h1><p>Lorem</p></body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.failedChecks.includes('no_scolaire_title'))
    assert.equal(r.passed, false)
  })

  test('page minimaliste sans rien → score bas', () => {
    const page = `<html><body><h1>Test</h1></body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.score < 30)
    assert.equal(r.passed, false)
  })
})

describe('evaluateVisualFidelity — page premium acceptée', () => {
  test('page riche avec gradients/animations/SVG → passed', () => {
    const page = `
<html><head>
<link rel="preconnect" href="https://fonts.googleapis.com">
<style>
:root { --bg: #fff; --fg: #000; --accent: #ff6a3d; }
body { font-family: Inter, sans-serif; font-size: clamp(1rem, 2vw, 1.5rem); }
.hero { background: linear-gradient(135deg, #ff6a3d, #c44); border-radius: 24px; }
.card { display: grid; grid-template-columns: 1fr 1fr; transition: transform 240ms cubic-bezier(0.32, 0.72, 0, 1); transform: rotateY(30deg) perspective(800px); }
.card:hover { transform: translateY(-4px); }
.blob { filter: blur(120px); background: radial-gradient(circle, rgba(255,106,61,0.5), transparent); position: absolute; }
.hero-glass { backdrop-filter: blur(20px); }
@keyframes fadeUp { from { opacity: 0 } to { opacity: 1 } }
.fade-up { animation: fadeUp 0.8s cubic-bezier(0.19,1,0.22,1); }
.bg-layered { background: linear-gradient(red, blue), linear-gradient(orange, yellow); }
.parallax { position: sticky; --p: 0; }
</style>
</head><body>
<svg width="100" height="100" viewBox="0 0 100 100"><path d="M50 0 L 100 100 L 0 100 Z" fill="orange"/><circle cx="50" cy="50" r="20" fill="red"/></svg>
<section><h1>Titre premier</h1><img src="hero.jpg"></section>
<section><h2>Deuxième</h2><img src="alt.jpg"></section>
<section><h2>Troisième</h2><img src="x.jpg"></section>
<section><h2>Quatrième</h2><img src="y.jpg"></section>
<section><h2>Cinquième</h2></section>
<section><h2>Sixième</h2></section>
<script>
const io = new IntersectionObserver(() => {})
requestAnimationFrame(() => {})
</script>
</body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.score >= 70, `score ${r.score}`)
  })
})

describe('evaluateVisualFidelity — checks individuels', () => {
  test('détection polices premium (Inter)', () => {
    const page = '<html><body><style>body { font-family: Inter; }</style></body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'premium_fonts')
    assert.equal(check?.passed, true)
  })

  test('détection gradient', () => {
    const page = '<html><body><style>.x { background: linear-gradient(red, blue); }</style></body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_gradient')
    assert.equal(check?.passed, true)
  })

  test('détection IntersectionObserver dans JS', () => {
    const r = evaluateVisualFidelity([
      html('<html><body><style>@keyframes f {}</style></body></html>'),
      js('const io = new IntersectionObserver(() => {})'),
    ], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_animations')
    assert.equal(check?.passed, true)
  })

  test('détection backdrop-filter', () => {
    const page = '<html><body><style>.nav { backdrop-filter: blur(20px); }</style></body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_depth')
    assert.equal(check?.passed, true)
  })

  test('flat colored card cluster → échec bloquant', () => {
    const page = `
<html><body>
<div style="background:red"><span>texte 1</span></div>
<div style="background:red"><span>texte 2</span></div>
<div style="background:red"><span>texte 3</span></div>
</body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.failedChecks.includes('no_flat_card_cluster'))
    assert.equal(r.passed, false)
  })

  test('compteur de sections', () => {
    const page = '<html><body>' + Array.from({ length: 7 }, () => '<section>x</section>').join('') + '</body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'min_sections')
    assert.equal(check?.passed, true)
  })

  test('compteur d images (img + background-image)', () => {
    const page = `<html><body><img src="a.jpg"><div style="background-image: url(b.jpg)"></div></body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_images')
    assert.equal(check?.passed, true)
  })

  test('SVG inline travaillé (>=120 chars)', () => {
    const svgInner = '<path d="M0 0 L 100 100 L 0 100 Z" fill="#ff6a3d"/><circle cx="50" cy="50" r="20" fill="#3aa4ff" stroke="#000"/><rect x="0" y="0" width="20" height="20" fill="green"/><polygon points="0,0 100,0 50,100" fill="orange"/>'
    const page = `<html><body><svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">${svgInner}</svg></body></html>`
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_inline_svg')
    assert.equal(check?.passed, true)
  })

  test('transformations 3D détectées', () => {
    const page = '<html><body><style>.x { transform: rotateY(45deg) perspective(800px); }</style></body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_3d_transforms')
    assert.equal(check?.passed, true)
  })

  test('layered gradients détectés', () => {
    const page = '<html><body><style>.x { background: linear-gradient(red, blue), linear-gradient(orange, yellow); }</style></body></html>'
    const r = evaluateVisualFidelity([html(page)], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    const check = r.checks.find((c) => c.id === 'has_layered_gradients')
    assert.equal(check?.passed, true)
  })
})

describe('evaluateVisualFidelity — score & summary', () => {
  test('score ∈ [0..100]', () => {
    const r = evaluateVisualFidelity([html('<html><body>x</body></html>')], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.score >= 0 && r.score <= 100)
  })

  test('floor = 70 par défaut', () => {
    const r = evaluateVisualFidelity([html('<html></html>')], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.equal(r.floor, 70)
  })

  test('summary inclut score', () => {
    const r = evaluateVisualFidelity([html('<html></html>')], VISUAL_INTENT, null, SHOWCASE_BRIEF)
    assert.ok(r.summary.includes(String(r.score)))
  })
})

describe('buildVisualFidelityCritique', () => {
  test('passed=true → renvoie ""', () => {
    const r = buildVisualFidelityCritique({
      score: 80, passed: true, floor: 70, checks: [], failedChecks: [], summary: 'ok',
    })
    assert.equal(r, '')
  })

  test('passed=false → critique contient label des checks échoués', () => {
    const r = buildVisualFidelityCritique({
      score: 30, passed: false, floor: 70,
      checks: [{ id: 'min_sections', label: 'Au moins 6 sections', passed: false, weight: 12 }],
      failedChecks: ['min_sections'],
      summary: 'pauvre',
    })
    assert.ok(r.includes('REGENERATION OBLIGATOIRE'))
    assert.ok(r.includes('Au moins 6 sections'))
  })

  test('failed no_flat_card_cluster → mention "ECHEC CRITIQUE"', () => {
    const r = buildVisualFidelityCritique({
      score: 30, passed: false, floor: 70,
      checks: [{ id: 'no_flat_card_cluster', label: 'pas de cartes plates', passed: false, weight: 14 }],
      failedChecks: ['no_flat_card_cluster'],
      summary: 'mauvais',
    })
    assert.ok(r.includes('ECHEC CRITIQUE'))
  })

  test('contient mention starter template à reprendre', () => {
    const r = buildVisualFidelityCritique({
      score: 30, passed: false, floor: 70,
      checks: [{ id: 'min_sections', label: 'x', passed: false, weight: 10 }],
      failedChecks: ['min_sections'],
      summary: 'x',
    })
    assert.ok(r.includes('STARTER TEMPLATE') || r.includes('squelette'))
  })

  test('score actuel + floor inclus', () => {
    const r = buildVisualFidelityCritique({
      score: 45, passed: false, floor: 70,
      checks: [{ id: 'x', label: 'y', passed: false, weight: 1 }],
      failedChecks: ['x'],
      summary: 's',
    })
    assert.ok(r.includes('45'))
    assert.ok(r.includes('70'))
  })
})
