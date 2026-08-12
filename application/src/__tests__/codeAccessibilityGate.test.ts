// Accessibilite mesuree au RENDU.
//
// Un critic source existe deja (4 regles regex). Il est aveugle a ce qui
// n existe qu apres mise en page: le contraste calcule, l ordre des titres, la
// langue du document, le nom accessible d un bouton dont le libelle vient d une
// variable. Ce module note ce que le navigateur a mesure — il ne mesure rien
// lui-meme, donc il se teste sans navigateur.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  CONTRAST_AA,
  findHeadingOrderIssues,
  scoreAccessibility,
  type AccessibilityMetrics,
} from '../services/codeAccessibilityGate.ts'

const perfect: AccessibilityMetrics = {
  documentLang: 'fr',
  imagesWithoutName: [],
  controlsWithoutName: [],
  fieldsWithoutLabel: [],
  headingLevels: [1, 2, 2, 3],
  lowContrastSamples: [],
  unreachableByKeyboard: [],
}

describe('accessibilite — hierarchie de titres', () => {
  test('une hierarchie saine ne signale rien', () => {
    assert.deepEqual(findHeadingOrderIssues([1, 2, 3, 2, 3]), [])
  })

  test('un h1 manquant est signale', () => {
    assert.match(findHeadingOrderIssues([2, 3]).join(' '), /aucun <h1>/)
  })

  test('un saut de niveau est signale avec les deux niveaux', () => {
    assert.match(findHeadingOrderIssues([1, 2, 5]).join(' '), /saut de <h2> a <h5>/)
  })

  test('une page sans aucun titre est signalee', () => {
    assert.deepEqual(findHeadingOrderIssues([]), ['aucun titre dans la page'])
  })
})

describe('accessibilite — notation', () => {
  test('une page irreprochable atteint 100 et passe', () => {
    const verdict = scoreAccessibility(perfect)
    assert.equal(verdict.score, 100)
    assert.equal(verdict.ok, true)
    assert.deepEqual(verdict.failedChecks, [])
    assert.match(verdict.critique, /rien a signaler/)
  })

  test('une page sans rien tombe a 0 et echoue', () => {
    const verdict = scoreAccessibility({
      documentLang: '',
      imagesWithoutName: ['img.hero'],
      controlsWithoutName: ['button'],
      fieldsWithoutLabel: ['input#email'],
      headingLevels: [2, 5],
      lowContrastSamples: [{ text: 'texte gris', ratio: 1.66 }],
      unreachableByKeyboard: ['div.card'],
    })
    assert.equal(verdict.score, 0)
    assert.equal(verdict.ok, false)
    assert.equal(verdict.failedChecks.length, 7)
  })

  test('la critique nomme le pire contraste avec sa valeur', () => {
    const verdict = scoreAccessibility({
      ...perfect,
      lowContrastSamples: [{ text: 'presque lisible', ratio: 3.9 }, { text: 'illisible', ratio: 1.66 }],
    })
    assert.match(verdict.critique, /illisible/)
    assert.match(verdict.critique, /1\.66:1/)
  })

  test('un seul defaut ne fait pas echouer toute la page', () => {
    // Le seuil doit laisser passer un livrable globalement accessible: une
    // porte qui refuse tout ne serait jamais lue.
    const verdict = scoreAccessibility({ ...perfect, unreachableByKeyboard: ['div'] })
    assert.equal(verdict.ok, true)
    assert.deepEqual(verdict.failedChecks, ['keyboard_reachable'])
  })

  test('les manques graves font basculer sous le seuil', () => {
    const verdict = scoreAccessibility({
      ...perfect,
      controlsWithoutName: ['button'],
      fieldsWithoutLabel: ['input'],
    })
    assert.equal(verdict.ok, false)
  })

  test('la critique dit COMMENT corriger, sans toucher au design', () => {
    const verdict = scoreAccessibility({ ...perfect, imagesWithoutName: ['img'] })
    assert.match(verdict.critique, /alt/)
    assert.match(verdict.critique, /sans rien changer au design/)
  })

  test('le seuil AA du texte normal reste la reference', () => {
    assert.equal(CONTRAST_AA, 4.5)
  })
})
