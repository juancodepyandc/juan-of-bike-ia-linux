import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { scoreRenderedAesthetics } from '../services/codeRenderedAestheticScore.ts'

// MESURE (corpus des 33 runs archives, verdicts de rendu):
//   runtime_clean EN ECHEC :  4 runs, score moyen 22/100
//   runtime_clean OK       : 10 runs, score moyen 78/100
// Les trois runs a 10/100 (v93, v110, v120) echouent EXACTEMENT les memes sept
// criteres — tous. Ce n est pas une page laide, c est une page qui n a pas
// rendu: six criteres de STYLE se declaraient en echec sans avoir rien mesure.

const BLANK = {
  fontSizeScale: [], fontFamilies: [], images: 0, canvases: 0,
  distinctShadows: 0, distinctRadii: 0, sections: 0, interactive: 0, documentHeight: 150,
}

const RICH = {
  fontSizeScale: [48, 32, 20, 16], fontFamilies: ['Inter'], images: 4, canvases: 0,
  distinctShadows: 3, distinctRadii: 2, sections: 6, interactive: 8, documentHeight: 3200,
}

describe('note de rendu: ne pas confondre « laid » et « n a pas rendu »', () => {
  test('page blanche + erreur runtime: le STYLE n est pas mesure', () => {
    const verdict = scoreRenderedAesthetics({ desktop: BLANK, consoleErrors: ['ReferenceError: x is not defined'] })
    assert.equal(verdict.styleMeasured, false)
    assert.deepEqual(verdict.failedChecks, ['runtime_clean'], 'seul le critere qui a MESURE quelque chose accuse')
    assert.equal(verdict.passed, false, 'une page cassee ne passe jamais')
    assert.match(verdict.critique, /chargement/i)
  })

  test('les criteres de style sont marques non concluants, pas en echec', () => {
    const verdict = scoreRenderedAesthetics({ desktop: BLANK, consoleErrors: ['boom'] })
    const style = verdict.checks.filter((c) => c.id !== 'runtime_clean')
    assert.ok(style.every((c) => c.conclusive === false), 'aucun n a pu mesurer')
    assert.equal(verdict.checks.find((c) => c.id === 'runtime_clean')?.conclusive, true)
  })

  test('une page BLANCHE ne gagne plus le critere « pas un grand vide »', () => {
    // Regression: `documentHeight <= 900` etait vrai quand il n y a RIEN, donc
    // content_density passait grace au vide qu il est cense reprocher.
    const verdict = scoreRenderedAesthetics({ desktop: BLANK })
    const density = verdict.checks.find((c) => c.id === 'content_density')
    assert.equal(density?.passed, false)
  })

  test('page rendue et saine: le style est mesure et la note tient', () => {
    const verdict = scoreRenderedAesthetics({ desktop: RICH })
    assert.equal(verdict.styleMeasured, true)
    assert.equal(verdict.score, 100)
    assert.equal(verdict.passed, true)
    assert.deepEqual(verdict.failedChecks, [])
  })

  test('page rendue mais laide: la note de style reste un VRAI verdict', () => {
    const ugly = { ...RICH, fontSizeScale: [16, 16], fontFamilies: ['times new roman'], images: 0, distinctShadows: 0, distinctRadii: 0, interactive: 1 }
    const verdict = scoreRenderedAesthetics({ desktop: ugly })
    assert.equal(verdict.styleMeasured, true, 'la page a rendu: on la juge')
    assert.ok(verdict.score < 70)
    assert.ok(verdict.failedChecks.includes('display_typography'))
    assert.ok(verdict.failedChecks.includes('visual_content'))
  })

  test('page rendue AVEC erreur runtime: le style reste mesure et compte', () => {
    const verdict = scoreRenderedAesthetics({ desktop: RICH, consoleErrors: ['404'] })
    assert.equal(verdict.styleMeasured, true)
    assert.deepEqual(verdict.failedChecks, ['runtime_clean'])
    assert.equal(verdict.passed, false, 'l erreur runtime interdit toujours le succes')
  })
})
