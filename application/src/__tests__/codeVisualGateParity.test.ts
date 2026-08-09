// Verrouille la parite de la porte visuelle WS9.
//
// Avant: la boucle du juge visuel vivait dans la couche vue
// (`codeViewVisualCorrectionLoop.ts`), donc SEULE l UI Tauri en beneficiait.
// Le CLI et le canal tunnel livraient sans aucune garde visuelle, alors que
// c est precisement la parite exigee entre canaux.
//
// La porte source-statique (`evaluateVisualFidelity`) ne demande ni navigateur
// ni serveur de dev: elle est desormais evaluee dans la finalisation du
// pipeline, donc sur les TROIS canaux, et elle compte dans le score livre.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  blendVisualFidelityIntoScore,
  finalizeCodePipelineDelivery,
} from '../services/codePipelineFinalization.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const UGLY_HTML = `<!doctype html><html><head><title>Page</title>
<link rel="stylesheet" href="style.css"></head>
<body><h1>Bienvenue</h1><p>Du texte.</p></body></html>`
const UGLY_CSS = `body { font-family: Arial; background: #fff; color: #000; }
h1 { color: blue; } p { margin-top: 10px; }`

function deliver(files: Array<{ name: string; language: string; content: string }>, prompt: string, score = 95) {
  return finalizeCodePipelineDelivery({
    files,
    notes: 'notes de base',
    score,
    intent: classifyCodeIntent(prompt),
    enrichedPrompt: prompt,
    architecturePlan: null,
    assetBundle: null,
  })
}

describe('WS9 — la porte visuelle est evaluee sur tous les canaux', () => {
  const PROMPT = 'landing page premium pour une marque de voitures, hero anime'

  test('la finalisation retourne desormais un rapport visuel', () => {
    const delivery = deliver(
      [
        { name: 'index.html', language: 'html', content: UGLY_HTML },
        { name: 'style.css', language: 'css', content: UGLY_CSS },
      ],
      PROMPT,
    )
    assert.ok(delivery.visualFidelity, 'le rapport visuel doit exister')
    assert.equal(typeof delivery.visualFidelity.score, 'number')
  })

  test('une page scolaire ne peut plus etre livree comme excellente', () => {
    const delivery = deliver(
      [
        { name: 'index.html', language: 'html', content: UGLY_HTML },
        { name: 'style.css', language: 'css', content: UGLY_CSS },
      ],
      PROMPT,
      95,
    )
    assert.equal(delivery.visualFidelity.passed, false, 'cette page doit echouer la porte')
    assert.ok(delivery.score < 95, `score non abaisse: ${delivery.score}`)
    assert.ok(delivery.score <= 84, `un rendu sous le seuil doit etre plafonne: ${delivery.score}`)
  })

  test('la critique precise part avec la livraison', () => {
    const delivery = deliver(
      [
        { name: 'index.html', language: 'html', content: UGLY_HTML },
        { name: 'style.css', language: 'css', content: UGLY_CSS },
      ],
      PROMPT,
    )
    assert.match(delivery.notes, /QUALITE VISUELLE/)
    assert.match(delivery.notes, /seuil/)
  })

  test('un projet non visuel n est pas penalise', () => {
    const prompt = 'script python qui parse un csv et sort un rapport'
    const delivery = deliver([{ name: 'main.py', language: 'python', content: 'print(1)\n' }], prompt, 90)
    assert.equal(delivery.score, 90, 'aucun projet non visuel ne doit perdre de points')
    assert.doesNotMatch(delivery.notes, /QUALITE VISUELLE/)
  })
})

describe('blendVisualFidelityIntoScore', () => {
  const report = (score: number, passed: boolean) => ({
    score, passed, floor: 70, checks: [], failedChecks: [], summary: '',
  }) as never

  test('un rendu qui echoue plafonne le score livre', () => {
    assert.ok(blendVisualFidelityIntoScore(100, report(30, false)) <= 84)
  })

  test('la correction du modele reste dominante sur un rendu correct', () => {
    const blended = blendVisualFidelityIntoScore(90, report(80, true))
    assert.ok(blended >= 85 && blended <= 90, `mixage inattendu: ${blended}`)
  })

  test('reste borne entre 0 et 100', () => {
    assert.ok(blendVisualFidelityIntoScore(0, report(0, false)) >= 0)
    assert.ok(blendVisualFidelityIntoScore(100, report(100, true)) <= 100)
  })
})
