/**
 * Compound-scene fidelity contract (UI path). Mirrors the Python composer
 * (faithful_scene_prompt.py) so the React UI keeps every requested facet of a
 * compound prompt — celebrity + decor + mechanical + fluids + luminous + motion
 * — instead of letting FLUX collapse the scene to its dominant noun.
 *
 * Run: node --experimental-strip-types --test src/__tests__/compoundSceneContract.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { buildCompoundSceneContract } from '../services/compoundScene.ts'

const COMPLEX = "Keanu Reeves en tenue de motard cyberpunk, debout pres d'une moto futuriste "
  + "a reacteur, dans une ruelle neo-tokyo sous la pluie battante ; des neons roses et bleus "
  + "se refletent dans les flaques, de la vapeur s'echappe, des etincelles jaillissent d'un "
  + "bras mecanique articule, de l'eau ruisselle, une helice de turbine tourne, blouson de cuir noir."

describe('buildCompoundSceneContract', () => {
  test('compound celebrity scene emits the fidelity contract', () => {
    const contract = buildCompoundSceneContract(COMPLEX, 'il leve le poing puis salue')
    assert.match(contract, /MULTI-ELEMENT FIDELITY CONTRACT/)
    assert.match(contract, /identity/i)
    assert.match(contract, /decor\/environment/i)
    assert.match(contract, /mechanical apparatus/i)
    assert.match(contract, /fluid\/atmospheric/i)
    assert.match(contract, /luminous\/emissive/i)
    assert.match(contract, /motion/i)
  })

  test('English compound scene also fires', () => {
    const contract = buildCompoundSceneContract(
      'Albert Einstein in a neon-lit workshop, steam rising, a spinning brass turbine, sparks, water dripping',
    )
    assert.match(contract, /MULTI-ELEMENT FIDELITY CONTRACT/)
    assert.match(contract, /mechanical/i)
    assert.match(contract, /luminous/i)
    assert.match(contract, /fluid/i)
  })

  test('French verb conjugations are caught (motion + luminous)', () => {
    const contract = buildCompoundSceneContract(
      "des engrenages tournent, le balancier oscille, des cristaux bioluminescents eclairent, de l'eau ruisselle",
    )
    assert.match(contract, /motion/i)
    assert.match(contract, /luminous/i)
  })

  test('isolated-character mode reframes scene facets as on-subject atmosphere', () => {
    const scene = buildCompoundSceneContract(COMPLEX, 'il leve le poing')
    const isolated = buildCompoundSceneContract(COMPLEX, 'il leve le poing', { isolated: true })
    // SCENE mode keeps the decor as a real background; ISOLATED reframes it ON the subject.
    assert.match(scene, /not replaced by a plain studio backdrop/i)
    assert.match(isolated, /ON and AROUND the subject|read THROUGH the subject/i)
    assert.match(isolated, /single riggable subject/i)
  })

  test('simple single-subject prompt is a no-op', () => {
    assert.equal(buildCompoundSceneContract('a red ceramic coffee mug'), '')
  })

  test('pure character with no scene is a no-op', () => {
    assert.equal(buildCompoundSceneContract('a fantasy elf warrior with a sword'), '')
  })
})
