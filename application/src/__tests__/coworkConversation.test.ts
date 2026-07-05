import { describe, test } from 'node:test'
import assert from 'node:assert/strict'

const {
  resolveCoworkConversationFrame,
  buildCoworkConversationSection,
} = await import('../services/coworkConversation.ts')

describe('coworkConversation', () => {
  test('classe un ordre direct comme mission executable', () => {
    const frame = resolveCoworkConversationFrame(
      'corrige le module cowork et teste la version application',
      [],
    )

    assert.equal(frame.mode, 'ordre_direct')
    assert.equal(frame.shouldExecute, true)
    assert.equal(frame.effectivePrompt, 'corrige le module cowork et teste la version application')
  })

  test('fusionne une suite courte avec la derniere mission actionnable', () => {
    const frame = resolveCoworkConversationFrame('reprends et fais le vraiment fonctionner', [
      {
        role: 'user',
        content: 'corrige le systeme conversationnel du cowork pour qu il execute les ordres',
      },
      {
        role: 'aurora',
        content: 'Je vais regarder le cowork.',
      },
    ])

    assert.equal(frame.mode, 'suite_de_mission')
    assert.equal(frame.shouldExecute, true)
    assert.match(frame.effectivePrompt, /corrige le systeme conversationnel/)
    assert.match(frame.effectivePrompt, /reprends et fais le vraiment fonctionner/)
  })

  test('classe les suites media naturelles comme demandes executables', () => {
    for (const prompt of [
      'modelise celui-ci en 3D',
      'transforme cette image en modele 3D',
      'via ce modele 3d fais en le personnage principal d un jeu',
      'construis un jeu autour de ce personnage',
      'utilise nmap pour scanner mon reseau local autorise',
    ]) {
      const frame = resolveCoworkConversationFrame(prompt, [
        { role: 'user', content: 'genere une photo de personnage cyberpunk' },
        { role: 'aurora', content: 'Image creee : output/imagegen/cyberpunk.png' },
      ])

      assert.equal(frame.shouldExecute, true, `shouldExecute pour: ${prompt}`)
      assert.notEqual(frame.mode, 'discussion', `pas discussion pour: ${prompt}`)
    }
  })

  test('garde une discussion simple en mode conversation', () => {
    const frame = resolveCoworkConversationFrame('merci', [])

    assert.equal(frame.mode, 'discussion')
    assert.equal(frame.shouldExecute, false)
  })

  test('classe une demande d accompagnement comme executable (pas une simple discussion)', () => {
    for (const prompt of [
      'écoute, je suis débordé en ce moment, aide-moi à m\'organiser pour la semaine',
      'planifie ma semaine de révision du bac',
      'conseille-moi pour gérer mon budget ce mois-ci',
      'aide-moi à réfléchir à ma reconversion professionnelle',
    ]) {
      const frame = resolveCoworkConversationFrame(prompt, [])
      assert.equal(frame.mode, 'accompagnement', `mode pour: ${prompt}`)
      assert.equal(frame.shouldExecute, true, `shouldExecute pour: ${prompt}`)
    }
  })

  test('le cadre accompagnement interdit de commencer par une question', () => {
    const frame = resolveCoworkConversationFrame('aide-moi à m\'organiser pour la semaine', [])
    const section = buildCoworkConversationSection(frame)
    assert.match(section, /ACCOMPAGNEMENT/)
    assert.match(section, /NE COMMENCE PAS par une question/)
  })

  test('expose un cadre lisible pour le prompt systeme', () => {
    const frame = resolveCoworkConversationFrame('continue', [
      { role: 'user', content: 'analyse les fichiers du projet cowork' },
    ])
    const section = buildCoworkConversationSection(frame)

    assert.match(section, /Cadre conversationnel Cowork/)
    assert.match(section, /Execution attendue: oui/)
    assert.match(section, /Objectif effectif fusionne/)
  })
})
