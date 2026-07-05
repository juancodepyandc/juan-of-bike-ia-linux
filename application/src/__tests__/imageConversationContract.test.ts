import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildImageAutocorrectionContract,
  buildImageConversationContext,
  classifyImageEditRequest,
  findLastUserPrompt,
  resolveImageConversationStyle,
} from '../services/imageConversationContract.ts'
import type { ConversationSession } from '../stores/moduleHistoryStore.ts'

describe('imageConversationContract', () => {
  test('neutralise le style technique sur une retouche photo humaine avec personnage ajoute', () => {
    const resolved = resolveImageConversationStyle({
      style: 'technical_render',
      prompt: 'sur la photo ajoute une mascotte nommee Kora comme une amie avec une main sur l epaule, peau naturelle',
      hasReference: true,
      isEditIntent: true,
    })

    assert.equal(resolved.style, 'none')
    assert.match(resolved.overrideReason ?? '', /retouche photo humaine/i)
  })

  test('conserve le style technique pour un vrai sujet mecanique', () => {
    const resolved = resolveImageConversationStyle({
      style: 'technical_render',
      prompt: 'rendu technique CAD d un connecteur mecanique avec cables visibles',
      hasReference: true,
      isEditIntent: true,
    })

    assert.equal(resolved.style, 'technical_render')
    assert.equal(resolved.overrideReason, null)
  })

  test('classifie les grandes familles de retouche sans nom propre special', () => {
    const traits = classifyImageEditRequest(
      'change le decor en cirque, ajoute une mascotte amie, tee shirt rouge, short noir, personne assise, enleve la couronne',
      true,
    )

    assert.equal(traits.humanPhotoEdit, true)
    assert.equal(traits.addedCharacter, true)
    assert.equal(traits.socialInteraction, true)
    assert.equal(traits.decorChange, true)
    assert.equal(traits.outfitEdit, true)
    assert.equal(traits.poseEdit, true)
    assert.equal(traits.removalOrReplace, true)
    assert.equal(traits.personRemovalOrReplace, false)
  })

  test('ne transforme pas une contrainte de preservation en suppression', () => {
    const traits = classifyImageEditRequest(
      'change la tenue en tee shirt rouge et short noir sans changer le corps et sans modifier le visage',
      true,
    )

    assert.equal(traits.outfitEdit, true)
    assert.equal(traits.removalOrReplace, false)
  })

  test('garde les vrais retraits dans le contrat generique', () => {
    const traits = classifyImageEditRequest('meme photo sans la couronne et remplace le fond par une plage', true)

    assert.equal(traits.removalOrReplace, true)
    assert.equal(traits.personRemovalOrReplace, false)
  })

  test('classe une suppression de personne comme retrait complet du corps et des habits', () => {
    const traits = classifyImageEditRequest('suppression complete de l homme metis et ajout de Happy sur son epaule', true)

    assert.equal(traits.removalOrReplace, true)
    assert.equal(traits.personRemovalOrReplace, true)
  })

  test('ne classe pas une personne a preserver comme personnage ajoute', () => {
    const traits = classifyImageEditRequest('ecris AURORA sur le panneau en gardant la personne identique', true)

    assert.equal(traits.humanPhotoEdit, true)
    assert.equal(traits.addedCharacter, false)
  })

  test('contrat encode preservation, personnage, relation, decor, tenue, pose et retrait', () => {
    const contract = buildImageAutocorrectionContract({
      prompt: 'refais la photo avec une mascotte nommee Kora comme deux amis, main sur l epaule, dans un cirque colore, tee shirt rouge, short noir, assise, enleve la couronne, sans effet granit sur la peau',
      hasReference: true,
      conversationContext: 'USER: la peau etait granitee\nASSISTANT: [previous image output]',
    })

    assert.match(contract, /Skin must remain natural camera skin/i)
    assert.match(contract, /ADDED CHARACTER \/ ENTITY INTEGRATION/i)
    assert.match(contract, /hand on the shoulder/i)
    assert.match(contract, /DECOR \/ BACKGROUND CHANGE/i)
    assert.match(contract, /OUTFIT \/ COLOR EDIT/i)
    assert.match(contract, /POSE \/ COMPOSITION EDIT/i)
    assert.match(contract, /REMOVAL \/ REPLACEMENT EDIT/i)
    assert.match(contract, /Previous user corrections are constraints/i)
  })

  test('contrat de suppression de personne interdit les vetements restants', () => {
    const contract = buildImageAutocorrectionContract({
      prompt: 'suppression complete de l homme metis et ajout de Happy sur son epaule, il ne doit rester aucune chemise',
      hasReference: true,
    })

    assert.match(contract, /remove every visible part of that target/i)
    assert.match(contract, /shirt fabric, straps, accessories/i)
    assert.match(contract, /Do not let added characters sit on clothing/i)
    assert.match(contract, /no oversized shoulder, expanded chest, widened torso/i)
    assert.match(contract, /MULTI-STAGE PERSON REMOVAL \+ CHARACTER PLACEMENT/i)
    assert.match(contract, /pass 1 removes the person and all garments/i)
    assert.match(contract, /pass 2 reconstructs the revealed background and real remaining anatomy/i)
    assert.match(contract, /pass 3 places the new character with correct scale\/contact/i)
    assert.match(contract, /tiny, floating, generic, or sitting on removed-person remnants/i)
  })

  test('retrouve le dernier prompt utilisateur d une session', () => {
    const session: ConversationSession = {
      id: 'session-test',
      module: 'image',
      title: 'Test',
      createdAt: 1,
      updatedAt: 3,
      messages: [
        { role: 'user', content: 'premier prompt', timestamp: 1 },
        { role: 'assistant', content: '[image:one]', timestamp: 2 },
        { role: 'user', content: 'corrige la mascotte horizontale', timestamp: 3 },
      ],
    }

    assert.equal(findLastUserPrompt(session), 'corrige la mascotte horizontale')
  })

  test('compacte le contexte recent sans exposer les URL image longues', () => {
    const context = buildImageConversationContext([
      { role: 'user', content: 'ajoute une mascotte' },
      { role: 'assistant', content: '[image:blob:http://localhost/very-long-url] style:none' },
    ])

    assert.match(context, /USER: ajoute une mascotte/)
    assert.match(context, /\[previous image output\]/)
    assert.doesNotMatch(context, /blob:http/)
  })
})
