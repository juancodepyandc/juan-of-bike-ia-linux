// Non-regression du run 971 — « l excellence ne tenait pas sur le simple ».
//
// Brief: « un petit truc tout simple », un convertisseur Celsius/Fahrenheit en
// direct, pour une collegienne. Le pipeline a livre EXACTEMENT ce qui etait
// demande (conversion a la frappe, sans bouton, Inter, variables CSS, clamp())
// puis l a declare en ECHEC pour trois raisons, toutes fausses:
//
//   1. le manifest d assets ecrit par Aurora elle-meme reference son propre
//      pont local en http://127.0.0.1:3001/api/... -> securite 0 -> bloquant;
//   2. la porte visuelle appliquait le gabarit « landing marketing premium »
//      (6 sections, galerie, rotation 3D au scroll) a un outil a une page;
//   3. un simple ecart de design-spec faisait basculer `phase` a 'error' alors
//      que le sandbox etait vert et le score a 100.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { evaluateVisualFidelity } from '../services/codeVisualFidelity.ts'
import { resolveVisualAmbition } from '../services/codeVisualFidelityProfiles.ts'
import { isDeliveryRunnable } from '../services/codeValidationScoring.ts'
import { compositeStaticCritic } from '../services/codeStaticCritics.ts'
import { isStaticCritiqueBlocking } from '../services/codeValidationScoring.ts'
import type { CodeIntent } from '../services/codeIntent.ts'
import type { CodeSandboxResult } from '../services/codeSandbox.ts'

const UTILITY_BRIEF = "Salut, j'aurais besoin d'un petit truc tout simple : une page web unique pour convertir des temperatures, Celsius vers Fahrenheit et l'inverse. Rien d'autre, pas de compte, pas de base de donnees, juste la page."
const SHOWCASE_BRIEF = "je me lance dans un vrai site pour ma marque de cafe, une page d'accueil qui donne envie"
const APP_BRIEF = 'un dashboard admin pour suivre les commandes, back-office interne'

const STATIC: CodeIntent = { projectType: 'static_web' } as unknown as CodeIntent
const SPA: CodeIntent = { projectType: 'spa_react' } as unknown as CodeIntent

// La page reellement livree par le run 971, reduite a ce que la porte mesure.
const CONVERTER_HTML = `<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Convertisseur de Temperature</title><link rel="stylesheet" href="style.css"></head>
<body><div class="container"><h1>Convertisseur de Temperature</h1>
<div class="converter"><div class="input-group"><label for="celsius">Celsius</label>
<input type="number" id="celsius"><span class="result" id="celsius-result">0F</span></div></div>
</div><script src="script.js"></script></body></html>`

const CONVERTER_CSS = `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700&display=swap');
:root { --bg-primary: oklch(100% 0.01 280); --accent: oklch(65% 0.15 280); --border-radius: 12px;
--shadow: 0 4px 12px rgba(0,0,0,0.05); --transition: all 0.2s cubic-bezier(0.16,1,0.3,1); }
body { font-family: 'Inter', sans-serif; background: var(--bg-primary); display: flex;
align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
.container { max-width: 800px; border-radius: var(--border-radius); padding: clamp(32px, 8vw, 64px);
box-shadow: var(--shadow); backdrop-filter: blur(10px); }
input { border-radius: 12px; transition: var(--transition); }
input:hover { border-color: var(--accent); }
${'.filler { color: #222; }\n'.repeat(60)}`

function file(name: string, content: string, language: string) {
  return { name, language, content }
}

const CONVERTER_FILES = [
  file('index.html', CONVERTER_HTML, 'html'),
  file('style.css', CONVERTER_CSS, 'css'),
  file('script.js', "document.getElementById('celsius').addEventListener('input', () => {})", 'javascript'),
]

describe('calibration — le genre du projet decide de la barre', () => {
  test('un outil a une page est reconnu comme outil', () => {
    assert.equal(resolveVisualAmbition(UTILITY_BRIEF, STATIC, CONVERTER_FILES), 'utility')
  })

  test('un site de marque reste juge comme vitrine', () => {
    assert.equal(resolveVisualAmbition(SHOWCASE_BRIEF, SPA, CONVERTER_FILES), 'showcase')
  })

  test('un back-office est juge comme application', () => {
    assert.equal(resolveVisualAmbition(APP_BRIEF, SPA, []), 'application')
  })

  test('un projet muet et minuscule n est pas une vitrine', () => {
    assert.equal(resolveVisualAmbition('fais une page', STATIC, CONVERTER_FILES), 'utility')
  })
})

describe('calibration — le convertisseur du run 971 passe, sans rien inventer', () => {
  const report = evaluateVisualFidelity(CONVERTER_FILES, STATIC, null, UTILITY_BRIEF)

  test('il est juge sur la barre OUTIL et il passe', () => {
    assert.equal(report.ambition, 'utility')
    assert.equal(report.passed, true, `score ${report.score}, echecs: ${report.failedChecks.join(', ')}`)
  })

  test('on ne lui reclame plus hero, galerie, parallaxe ni 3D', () => {
    for (const absurd of ['min_sections', 'has_images', 'has_3d_transforms', 'has_scroll_driven', 'has_layered_gradients']) {
      assert.equal(report.failedChecks.includes(absurd), false, `${absurd} ne devrait pas etre exige d un outil`)
      assert.equal(report.checks.some((check) => check.id === absurd), false, `${absurd} ne devrait pas etre note`)
    }
  })

  test('la finition reste exigee: elle, elle a du sens pour un outil', () => {
    for (const kept of ['premium_fonts', 'has_css_vars', 'has_clamp', 'has_modern_layout', 'no_flat_card_cluster']) {
      assert.equal(report.checks.some((check) => check.id === kept), true, `${kept} doit rester note`)
    }
  })

  test('la barre appliquee est nommee dans le resume', () => {
    assert.match(report.summary, /outil/)
  })
})

describe('calibration — la vitrine ne perd rien', () => {
  test('une page pauvre reste refusee quand on vend une marque', () => {
    const poor = [file('index.html', '<!DOCTYPE html><html><body><h1>Bienvenue</h1></body></html>', 'html')]
    const report = evaluateVisualFidelity(poor, STATIC, null, SHOWCASE_BRIEF)
    assert.equal(report.ambition, 'showcase')
    assert.equal(report.passed, false)
    assert.equal(report.failedChecks.includes('min_sections'), true)
  })
})

describe('securite — une adresse de boucle locale n est pas un endpoint expose', () => {
  test("le manifest d assets d Aurora ne bloque plus la livraison", async () => {
    const manifest = JSON.stringify({
      assets: [{ previewUrl: 'http://127.0.0.1:3001/api/code/assets/file/x/images/hero.avif' }],
    }, null, 2)
    const report = await compositeStaticCritic(
      { generationId: 't', files: [...CONVERTER_FILES, file('assets/aurora-asset-bundle.json', manifest, 'json')] },
      STATIC,
    )
    assert.equal(report.scores.security, 1)
    assert.equal(isStaticCritiqueBlocking(report), false)
  })

  test('un vrai endpoint distant en http reste signale', async () => {
    const bad = file('api.js', "fetch('http://exemple.com/api/login', { method: 'POST' })", 'javascript')
    const report = await compositeStaticCritic({ generationId: 't', files: [bad] }, STATIC)
    assert.equal(report.issues.some((issue) => /non-TLS/.test(issue.message)), true)
  })
})

describe('livraison — un ecart de style ne rend pas un projet inexecutable', () => {
  const step = (label: string, command: string, ok: boolean) => ({ label, command, ok, output: '' })

  test('sandbox vert + ecart design-spec => livrable executable', () => {
    const result = {
      ok: false,
      summary: 'Ecart design-spec (component).',
      steps: [step('Build', 'npm run build', true), step('Design-spec', 'design-spec-gate', false)],
    } as unknown as CodeSandboxResult
    assert.equal(isDeliveryRunnable(result), true)
  })

  test('une vraie etape en echec reste un echec', () => {
    const result = {
      ok: false,
      summary: 'build casse',
      steps: [step('Build', 'npm run build', false), step('Design-spec', 'design-spec-gate', false)],
    } as unknown as CodeSandboxResult
    assert.equal(isDeliveryRunnable(result), false)
  })

  test('aucun sandbox => pas de livraison', () => {
    assert.equal(isDeliveryRunnable(null), false)
  })
})
