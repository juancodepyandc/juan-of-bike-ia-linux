import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildNegativePrompt,
  isHumanRemovalTarget,
  parseImageIntent,
  resolveReferenceDenoise,
} from '../utils/imagePromptParser.ts'

describe('parseImageIntent - suppressions', () => {
  test('retire les concepts interdits du prompt positif', () => {
    const result = parseImageIntent('meme image mais sans le chat')

    assert.deepEqual(result.removals, ['chat'])
    assert.equal(result.cleanedPrompt, 'meme image')
    assert.equal(result.isEditIntent, true)
    assert.equal(result.editMode, 'remove_element')
    assert.equal(result.editContract.label, 'suppression et reconstruction')
  })

  test('separe les suppressions multiples', () => {
    const result = parseImageIntent('sans cape ni masque ni armure')

    assert.deepEqual(result.removals.sort(), ['armure', 'cape', 'masque'].sort())
  })

  test('dedoublonne les suppressions sans tenir compte de la casse', () => {
    const result = parseImageIntent('sans Chat et sans chat')

    assert.equal(result.removals.length, 1)
  })

  test('un vetement de l homme ne compte pas comme suppression de l homme', () => {
    assert.equal(isHumanRemovalTarget("t-shirt noir de l'homme"), false)
    assert.equal(isHumanRemovalTarget("uniquement le t-shirt noir de l'homme"), false)
    assert.equal(isHumanRemovalTarget("l'homme"), true)
  })

  test('une contrainte sans nudite ne devient pas une operation de suppression', () => {
    const result = parseImageIntent('scene drole sans nudite', { hasReference: true })

    assert.equal(result.editMode, 'create')
    assert.deepEqual(result.removals, [])
  })

  test('une contrainte pas de doublon ne devient pas une operation de suppression', () => {
    const result = parseImageIntent('ajoute Goldorak, pas de doublon', { hasReference: true })

    assert.equal(result.editMode, 'add_element')
    assert.deepEqual(result.removals, [])
  })
})

describe('parseImageIntent - edition photo', () => {
  test('detecte un ajout cible', () => {
    const result = parseImageIntent('ajoute des lunettes rouges sur la personne')

    assert.equal(result.editMode, 'add_element')
    assert.ok(result.additions.some((item) => item.includes('lunettes rouges')))
    assert.ok(result.editContract.denoise && result.editContract.denoise >= 0.45)
  })

  test('detecte un remplacement cible', () => {
    const result = parseImageIntent('remplace le chapeau par une couronne doree')

    assert.equal(result.editMode, 'replace_element')
    assert.deepEqual(result.replacements, [{ from: 'chapeau', to: 'couronne doree' }])
  })

  test('traite sans changer le corps comme une contrainte de preservation', () => {
    const result = parseImageIntent('change la tenue en tee shirt rouge et short noir sans changer le corps', { hasReference: true })

    assert.equal(result.editMode, 'replace_element')
    assert.deepEqual(result.removals, [])
    assert.deepEqual(result.replacements, [{ from: 'tenue', to: 'tee shirt rouge et short noir' }])
    assert.ok(result.editContract.preserveLines.length > 0)
  })

  test('ne confond pas changement de pose et ajout cible', () => {
    const result = parseImageIntent('change la pose pour etre assise sur le sable, cadrage stable', { hasReference: true })

    assert.equal(result.editMode, 'composition_pose')
    assert.deepEqual(result.additions, [])
    assert.deepEqual(result.removals, [])
  })

  test('detecte le repositionnement d un objet comme edition de composition', () => {
    const result = parseImageIntent('deplace le barbecue plus a gauche sur la pelouse', { hasReference: true })

    assert.equal(result.editMode, 'composition_pose')
    assert.deepEqual(result.additions, [])
    assert.deepEqual(result.removals, [])
  })

  test('ajoute un element sans transformer une preservation du visage en suppression', () => {
    const result = parseImageIntent('ajoute une couronne doree sans modifier le visage', { hasReference: true })

    assert.equal(result.editMode, 'add_element')
    assert.deepEqual(result.removals, [])
    assert.deepEqual(result.additions, ['couronne doree'])
  })

  test('nettoie les editions composees suppression puis remplacement', () => {
    const result = parseImageIntent('enleve la couronne puis remplace le fond par une plage', { hasReference: true })

    assert.equal(result.editMode, 'remove_element')
    assert.deepEqual(result.removals, ['couronne'])
    assert.deepEqual(result.replacements, [{ from: 'fond', to: 'plage' }])
    assert.equal(result.cleanedPrompt, 'remplace le fond par une plage')
  })

  test('garde les deux obligations dans une edition composee suppression puis ajout', () => {
    const result = parseImageIntent('suppression complete de l homme metis et ajout du chat de Fairy Tail nomme Happy assis sur l epaule droite', { hasReference: true })

    assert.equal(result.editMode, 'remove_element')
    assert.deepEqual(result.removals, ['homme metis'])
    assert.deepEqual(result.additions, ['chat de Fairy Tail nomme Happy assis sur l epaule droite'])
    assert.match(result.cleanedPrompt, /ajout du chat de Fairy Tail/)
    assert.match(result.editContract.promptLines.join(' '), /vetements, chemise, bretelles/i)
    assert.match(result.editContract.negativeLines.join(' '), /chemise residuelle/i)
    assert.match(result.editContract.promptLines.join(' '), /ne jamais combler.*agrandissant l epaule/i)
    assert.match(result.editContract.negativeLines.join(' '), /epaule surdimensionnee/i)
  })

  test('detecte un changement de fond', () => {
    const result = parseImageIntent('change le fond en plage au coucher du soleil')

    assert.equal(result.editMode, 'background_change')
  })

  test('garder le decor inchange ne declenche pas background_change', () => {
    const result = parseImageIntent('change seulement le t-shirt en rouge, garder le visage et le decor inchanges', { hasReference: true })

    assert.notEqual(result.editMode, 'background_change')
  })

  test('detecte un changement de style', () => {
    const result = parseImageIntent('transforme cette photo en pixel art 16-bit')

    assert.equal(result.editMode, 'restyle')
  })

  test('detecte une edition de texte', () => {
    const result = parseImageIntent('ecris AURORA sur la pancarte')

    assert.equal(result.editMode, 'text_edit')
    assert.ok(result.editContract.denoise && result.editContract.denoise >= 0.6)
  })

  test('une contrainte negative de texte ne devient pas une edition de texte', () => {
    const result = parseImageIntent('scene de cirque avec projecteurs, aucune inscription')

    assert.equal(result.editMode, 'create')
    assert.equal(result.isEditIntent, false)
  })

  test('un prompt libre reste une creation', () => {
    const result = parseImageIntent('un paysage de montagne au matin')

    assert.equal(result.editMode, 'create')
    assert.equal(result.isEditIntent, false)
  })

  test('"avec" seul ne transforme pas une creation en retouche', () => {
    const result = parseImageIntent('portrait avec un chapeau rouge')

    assert.equal(result.editMode, 'create')
  })

  test('"avec exactement" dans une creation ne devient pas une retouche', () => {
    const result = parseImageIntent('scene de cirque avec exactement trois cubes lumineux, aucune inscription')

    assert.equal(result.editMode, 'create')
  })

  test('"avec" devient ajout quand une reference existe', () => {
    const result = parseImageIntent('avec des lunettes rouges', { hasReference: true })

    assert.equal(result.editMode, 'add_element')
  })

  test('"continue avec" reste une coherence de texture, pas un ajout', () => {
    const result = parseImageIntent("repare la pelouse et rends cette zone naturelle et continue avec l'herbe autour", { hasReference: true })

    assert.equal(result.editMode, 'repair_cleanup')
    assert.deepEqual(result.additions, [])
  })
})

describe('resolveReferenceDenoise', () => {
  test('preserve_refine reste doux meme si le slider est haut', () => {
    const result = parseImageIntent('meme photo, ameliore la nettete')

    assert.equal(result.editMode, 'preserve_refine')
    assert.ok(resolveReferenceDenoise(result, 0.7) <= 0.35)
  })

  test('suppression force une vraie reconstruction', () => {
    const result = parseImageIntent('meme image sans le vase')

    assert.ok(resolveReferenceDenoise(result, 0.3) >= 0.5)
  })

  test('conversion pixel art pousse assez fort la reference', () => {
    const result = parseImageIntent('transforme cette photo en pixel art')

    assert.ok(resolveReferenceDenoise(result, 0.3, 'pixel_art') >= 0.68)
  })
})

describe('buildNegativePrompt', () => {
  test('fusionne negative utilisateur et suppressions parsees', () => {
    const result = buildNegativePrompt('blurry, low quality', ['chat', 'pingouin'])

    assert.match(result, /blurry/)
    assert.match(result, /low quality/)
    assert.match(result, /chat/)
    assert.match(result, /pingouin/)
  })

  test('dedoublonne les collisions', () => {
    const result = buildNegativePrompt('blurry, chat', ['chat', 'pingouin'])
    const occurrences = (result.match(/chat/g) || []).length

    assert.equal(occurrences, 1)
  })
})
