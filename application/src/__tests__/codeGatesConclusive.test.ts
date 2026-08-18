import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { scoreAccessibility } from '../services/codeAccessibilityGate.ts'
import { scorePerformance } from '../services/codePerformanceGate.ts'
import { checkComposition } from '../services/codeCompositionGate.ts'
import { buildExpertEngineeringContractBlock } from '../services/codeSystemPromptContracts.ts'

// FAMILLE: une ABSENCE DE VIOLATION comptait comme une PRESENCE DE QUALITE.
//
// Mesure, page entierement vide, AVANT correction:
//   accessibilite  76/100   (seuil 80 — a quatre points de passer)
//   performance    62/100
//   composition    OK, aucun echec
//
// Sans image, aucune image ne manque d alternative. Sans controle, aucun n est
// inatteignable. Sans section, rien ne se chevauche. Les portes ne mesuraient
// pas la qualite: elles constataient n avoir rien trouve a redire.

const BLANK_A11Y = { documentLang: '', imagesWithoutName: [], controlsWithoutName: [], fieldsWithoutLabel: [], headingLevels: [], lowContrastSamples: [], unreachableByKeyboard: [] }
const BLANK_PERF = { firstContentfulPaint: 0, domInteractive: 0, layoutShift: 0, domNodes: 0, transferredBytes: 0, longTasks: 0, imagesWithoutDimensions: 0 }
const BLANK_COMP = { overlaps: [], sections: [], emojiIcons: [], viewportWidth: 1440 }

describe('portes: le vide ne vaut pas satisfaction', () => {
  test('accessibilite: une page vide ne recolte plus 76/100', () => {
    const verdict = scoreAccessibility(BLANK_A11Y)
    assert.equal(verdict.score, 0)
    assert.ok(verdict.checks.filter((c) => c.conclusive === false).length >= 5)
  })

  test('performance: une page qui n a jamais peint ne recolte plus 62/100', () => {
    const verdict = scorePerformance(BLANK_PERF)
    assert.equal(verdict.score, 0)
    // Rien ne bouge, rien ne pese, rien n occupe le thread: ce n est pas de la performance.
    for (const id of ['layout_stability', 'image_dimensions', 'dom_weight', 'payload_weight', 'main_thread']) {
      assert.equal(verdict.checks.find((c) => c.id === id)?.conclusive, false, id)
    }
  })

  test('composition: une page vide n est plus « OK, aucun echec »', () => {
    const report = checkComposition(BLANK_COMP)
    assert.equal(report.ok, false, 'elle n a pas ete mesuree, donc elle n est pas reussie')
    assert.deepEqual(report.failedChecks, [], 'et elle n est pas accusee non plus')
  })
})

describe('portes: une page REELLE reste jugee, sans complaisance', () => {
  test('accessibilite juge encore un vrai defaut', () => {
    const verdict = scoreAccessibility({ ...BLANK_A11Y, documentLang: 'fr', headingLevels: [1, 2, 2, 3], imagesWithoutName: ['hero.jpg'] })
    assert.ok(verdict.failedChecks.includes('images_have_name'))
    assert.ok(verdict.score > 0 && verdict.score < 100)
  })

  test('performance juge encore une page lente', () => {
    const slow = { firstContentfulPaint: 6000, domInteractive: 9000, layoutShift: 0.4, domNodes: 6000, transferredBytes: 9_000_000, longTasks: 12, imagesWithoutDimensions: 9 }
    const verdict = scorePerformance(slow)
    assert.ok(verdict.failedChecks.length >= 4, `echecs: ${verdict.failedChecks.join(',')}`)
    assert.ok(verdict.score < 50)
  })

  test('composition juge encore une icone emoji', () => {
    const report = checkComposition({ overlaps: [], sections: [{ name: 'hero', fill: 0.6 }], emojiIcons: ['🚀'], viewportWidth: 1440 })
    assert.equal(report.ok, false)
    assert.ok(report.failedChecks.includes('real_iconography'))
  })

  test('composition saine reste OK', () => {
    const report = checkComposition({ overlaps: [], sections: [{ name: 'hero', fill: 0.6 }, { name: 'about', fill: 0.5 }], emojiIcons: [], viewportWidth: 1440 })
    assert.equal(report.ok, true)
  })
})

describe('contrat de generation: prevenir les familles de typage vivantes', () => {
  // BALAYAGE (runs v113+): TS7006 (12), TS2367 (6), TS2339+TS2322 (25).
  // Chacune a une cause commune, et chacune se PREVIENT a la generation —
  // la reparer apres coup coute une passe de modele.
  const contract = buildExpertEngineeringContractBlock({
    projectType: 'spa_react', complexity: 'complex', features: [], assetPlan: null,
  } as never)

  test('TS7006: les parametres de rappel doivent etre annotes', () => {
    assert.match(contract, /Aucun parametre implicitement `any`/)
    assert.match(contract, /\.map\/\.filter\/\.reduce/)
  })

  test('TS2367: un statut ne se compare pas a un libelle d affichage', () => {
    // Mesure: union '"pending" | "preparing" | "sent"' comparee a '"envoyé"'.
    assert.match(contract, /union de statuts/i)
    assert.match(contract, /table de traduction separee/)
  })

  test('TS2339/TS2322: la donnee doit satisfaire le type qui la declare', () => {
    assert.match(contract, /n itere pas dessus comme sur un tableau/)
    assert.match(contract, /tous les champs requis de son interface/)
  })
})
