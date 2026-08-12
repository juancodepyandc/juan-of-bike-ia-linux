// Le juge doit lire les contraintes de style du BRIEF.
//
// Mesure reelle (run 1021): la livraison a ete refusee a 65/100 parce que le
// juge exigeait « Transformations 3D (rotateY/X, perspective) » et « Animation
// pilotee par scroll » — d une cliente qui ecrit « je veux pas que ca fasse
// gadget ». Le juge reclamait le gadget refuse.
//
// Le risque du correctif est evident et c est lui qu on teste le plus: ouvrir
// une porte de sortie universelle. Le juge doit rester SEVERE, simplement
// severe sur les bons criteres.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  GADGET_CHECK_IDS,
  describeStyleConstraints,
  resolveStyleConstraints,
} from '../services/codeStyleConstraints.ts'
import { evaluateVisualFidelity } from '../services/codeVisualFidelity.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

// Deux extraits du brief REEL, colles: il porte les deux informations a la
// fois — c est une vitrine de marque ET une demande de retenue. Les separer
// changerait le genre juge (une page seule et courte passe pour un outil).
const BRULERIE = "je me lance dans un vrai site pour ma marque de cafe, une page d'accueil qui donne envie. Des animations discretes c'est cool (un peu de mouvement au scroll, les cafes qui apparaissent progressivement) mais je veux pas que ca fasse gadget, faut que ca reste elegant."
const NEUTRE = "je me lance dans un vrai site pour ma marque de cafe, une page d'accueil qui donne envie avec nos 3-4 cafes du moment"

const SHOWCASE: CodeIntent = { projectType: 'static_web' } as unknown as CodeIntent

describe('contraintes de style — lecture du brief', () => {
  test('« je veux pas que ca fasse gadget » etablit la retenue', () => {
    const constraints = resolveStyleConstraints(BRULERIE)
    assert.equal(constraints.restraint, true)
    assert.ok(constraints.evidence.length > 0)
    assert.match(constraints.evidence.join(' '), /gadget/)
  })

  test('« sobre », « discret », « epure » l etablissent aussi', () => {
    for (const brief of ['je veux un site sobre', 'des effets discrets', 'un design epure']) {
      assert.equal(resolveStyleConstraints(brief).restraint, true, brief)
    }
  })

  test('« elegant » SEUL ne suffit pas: ce serait une porte de sortie universelle', () => {
    assert.equal(resolveStyleConstraints('je veux un site elegant et moderne').restraint, false)
    assert.equal(resolveStyleConstraints('un beau site premium haut de gamme').restraint, false)
  })

  test('un brief muet n active rien', () => {
    assert.equal(resolveStyleConstraints('').restraint, false)
    assert.equal(resolveStyleConstraints(NEUTRE).restraint, false)
  })

  test('la contrainte se JUSTIFIE en citant le brief', () => {
    const described = describeStyleConstraints(resolveStyleConstraints(BRULERIE))
    assert.match(described, /RETENUE/)
    assert.match(described, /gadget/)
  })
})

// Page riche mais SOBRE: finition soignee, aucun effet spectaculaire.
const SOBER_PAGE = `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet"><title>Brulerie</title>
<style>
:root{--terracotta:#b45309;--olive:#4d7c0f}
body{font-family:Inter;background:linear-gradient(180deg,#fffdf9,#f5efe6);color:#1c1917}
.card{border-radius:14px;box-shadow:0 4px 12px rgba(0,0,0,.06);transition:transform .2s}
.card:hover{transform:translateY(-2px)}
h1{font-size:clamp(32px,5vw,56px)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
@keyframes reveal{from{opacity:0}to{opacity:1}}
.reveal{animation:reveal .6s ease}
</style></head><body>
<section><h1>Brulerie Nomade</h1><img src="/hero.avif" alt="grains" width="800" height="600"></section>
<section class="grid"><div class="card"><img src="/c1.avif" alt="cafe" width="400" height="300"><h2>Ethiopie</h2><p>chocolat noir, agrumes</p></div></section>
<section><h2>Notre histoire</h2><p>Torrefaction en petits lots dans notre atelier lyonnais depuis 2019, en direct-trade avec les producteurs.</p></section>
<section><h2>Marches</h2><p>Croix-Rousse le samedi, Presqu'ile le mercredi.</p></section>
<section><h2>Abonnement</h2><p>Tous les 15 jours ou tous les mois.</p></section>
<section><h2>Contact</h2><p>Ecrivez-nous.</p></section>
<script>new IntersectionObserver(()=>{}).observe(document.body)</script>
</body></html>`

const POOR_PAGE = '<!doctype html><html lang="fr"><head><title>x</title></head><body><h1>Bienvenue</h1><ul><li>a</li><li>b</li></ul></body></html>'

describe('contraintes de style — la porte reste severe', () => {
  test('sous retenue, les criteres gadget ne sont plus NOTES', () => {
    const report = evaluateVisualFidelity([{ name: 'index.html', language: 'html', content: SOBER_PAGE }], SHOWCASE, null, BRULERIE)
    for (const id of GADGET_CHECK_IDS) {
      assert.equal(report.checks.some((check) => check.id === id), false, `${id} ne doit plus etre exige`)
    }
    assert.equal(report.styleConstraints?.restraint, true)
  })

  test('une page sobre MAIS soignee passe', () => {
    const report = evaluateVisualFidelity([{ name: 'index.html', language: 'html', content: SOBER_PAGE }], SHOWCASE, null, BRULERIE)
    assert.equal(report.passed, true, `score ${report.score}, echecs: ${report.failedChecks.join(', ')}`)
  })

  test('une page PAUVRE reste refusee, meme avec un brief sobre', () => {
    // C est le test qui compte: la retenue ne doit jamais devenir une excuse.
    const report = evaluateVisualFidelity([{ name: 'index.html', language: 'html', content: POOR_PAGE }], SHOWCASE, null, BRULERIE)
    assert.equal(report.passed, false)
    assert.equal(report.failedChecks.includes('min_sections'), true)
  })

  test('un brief neutre garde EXACTEMENT le comportement d avant', () => {
    const report = evaluateVisualFidelity([{ name: 'index.html', language: 'html', content: SOBER_PAGE }], SHOWCASE, null, NEUTRE)
    for (const id of GADGET_CHECK_IDS) {
      assert.equal(report.checks.some((check) => check.id === id), true, `${id} doit rester exige sans contrainte`)
    }
    assert.equal(report.styleConstraints, undefined)
  })

  test('la finition est notee PLUS severement sous retenue', () => {
    const files = [{ name: 'index.html', language: 'html', content: SOBER_PAGE }]
    const sober = evaluateVisualFidelity(files, SHOWCASE, null, BRULERIE)
    const neutral = evaluateVisualFidelity(files, SHOWCASE, null, NEUTRE)
    const weightOf = (report: typeof sober, id: string) => report.checks.find((check) => check.id === id)?.weight ?? 0
    assert.ok(weightOf(sober, 'premium_fonts') > weightOf(neutral, 'premium_fonts'))
    assert.ok(weightOf(sober, 'has_hover') > weightOf(neutral, 'has_hover'))
  })

  test('le resume dit que la barre a change, et pourquoi', () => {
    const report = evaluateVisualFidelity([{ name: 'index.html', language: 'html', content: SOBER_PAGE }], SHOWCASE, null, BRULERIE)
    assert.match(report.summary, /[Rr]etenue demandee par le brief/)
  })
})
