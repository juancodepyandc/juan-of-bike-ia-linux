// Verrouille le juge esthetique de RENDU.
//
// Cas reel qui a motive ce module: une landing Mercedes-Benz produite par le
// pipeline complet a ete notee 87/100 « Rendu visuel acceptable » par la porte
// source-statique. Ouverte dans Chromium, la meme page montrait un vide blanc
// d ~1 000 px, une typo maximale de 18 px sur 1440 px de large, des polices
// resolues en Helvetica Neue / Georgia (les defauts que le contrat interdit),
// zero image, et deux erreurs JavaScript au chargement.
//
// Le juge de rendu note cette page 18/100. Une porte qui lit la SOURCE est
// structurellement trompable: le CSS declare une typo premium, le navigateur
// affiche du 18 px.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  scoreRenderedAesthetics,
  type RenderedViewportMetrics,
} from '../services/codeRenderedAestheticScore.ts'

/** Metriques REELLES relevees sur la page livree (report.json de la capture). */
const MERCEDES_REEL: RenderedViewportMetrics = {
  fontFamilies: ['Helvetica Neue', 'Georgia'],
  distinctTextColors: 4,
  distinctBackgrounds: 2,
  fontSizeScale: [13, 16, 18],
  distinctRadii: 2,
  distinctShadows: 0,
  animatedElements: 41,
  sections: 4,
  images: 0,
  canvases: 0,
  interactive: 4,
  documentHeight: 2155,
}

const PREMIUM: RenderedViewportMetrics = {
  fontFamilies: ['Instrument Serif', 'Inter'],
  distinctTextColors: 3,
  distinctBackgrounds: 3,
  fontSizeScale: [12, 14, 16, 20, 28, 40, 72],
  distinctRadii: 3,
  distinctShadows: 4,
  animatedElements: 30,
  sections: 7,
  images: 6,
  canvases: 1,
  interactive: 14,
  documentHeight: 4200,
}

describe('scoreRenderedAesthetics — le cas reel', () => {
  test('la page notee 87/100 en source-statique echoue franchement au rendu', () => {
    const v = scoreRenderedAesthetics({
      desktop: MERCEDES_REEL,
      consoleErrors: ["ReferenceError: Lenis is not defined", "SyntaxError: Unexpected identifier 'email'"],
    })
    assert.equal(v.passed, false)
    assert.ok(v.score < 40, `attendu tres bas, obtenu ${v.score}`)
    for (const id of ['runtime_clean', 'display_typography', 'real_typeface', 'visual_content']) {
      assert.ok(v.failedChecks.includes(id), `${id} devrait echouer`)
    }
  })

  test('une page reellement premium passe', () => {
    const v = scoreRenderedAesthetics({ desktop: PREMIUM, consoleErrors: [] })
    assert.equal(v.passed, true, `echecs: ${v.failedChecks.join(',')}`)
    assert.ok(v.score >= 90, `score ${v.score}`)
  })
})

describe('scoreRenderedAesthetics — regles individuelles', () => {
  test('une page cassee au runtime ne peut JAMAIS passer, meme bien notee', () => {
    const v = scoreRenderedAesthetics({ desktop: PREMIUM, consoleErrors: ['ReferenceError: x'] })
    assert.equal(v.passed, false, 'une erreur runtime doit etre eliminatoire')
  })

  test('un titre en 18 px sur desktop est un echec de typographie d affichage', () => {
    const v = scoreRenderedAesthetics({ desktop: { ...PREMIUM, fontSizeScale: [13, 16, 18] }, consoleErrors: [] })
    assert.ok(v.failedChecks.includes('display_typography'))
  })

  test('les polices par defaut sont detectees comme absence de police choisie', () => {
    for (const fams of [['Helvetica Neue', 'Georgia'], ['Arial'], ['Times New Roman'], ['sans-serif']]) {
      const v = scoreRenderedAesthetics({ desktop: { ...PREMIUM, fontFamilies: fams }, consoleErrors: [] })
      assert.ok(v.failedChecks.includes('real_typeface'), fams.join('/'))
    }
  })

  test('une police premium reellement chargee passe la regle', () => {
    const v = scoreRenderedAesthetics({ desktop: { ...PREMIUM, fontFamilies: ['Instrument Serif', 'Arial'] }, consoleErrors: [] })
    assert.ok(!v.failedChecks.includes('real_typeface'))
  })

  test('une page sans aucun visuel echoue', () => {
    const v = scoreRenderedAesthetics({ desktop: { ...PREMIUM, images: 0, canvases: 0 }, consoleErrors: [] })
    assert.ok(v.failedChecks.includes('visual_content'))
  })

  test('la critique est actionnable et cite la mesure constatee', () => {
    const v = scoreRenderedAesthetics({ desktop: MERCEDES_REEL, consoleErrors: ['ReferenceError: Lenis is not defined'] })
    assert.match(v.critique, /RENDU REEL INSUFFISANT/)
    assert.match(v.critique, /18px/)
    assert.match(v.critique, /clamp\(/)
  })

  test('le score reste borne entre 0 et 100', () => {
    const v = scoreRenderedAesthetics({ desktop: MERCEDES_REEL, consoleErrors: [] })
    assert.ok(v.score >= 0 && v.score <= 100)
  })
})
