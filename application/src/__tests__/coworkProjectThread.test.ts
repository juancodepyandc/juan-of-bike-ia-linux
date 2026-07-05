import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CoworkActionEvent } from '../services/coworkTypes.ts'

const {
  buildCoworkProjectThreadSection,
  createEmptyCoworkProjectThread,
  diffCoworkProjectArtifacts,
  updateCoworkProjectThreadFromEvents,
} = await import('../services/coworkProjectThread.ts')

function connectorStart(
  at: number,
  connector: string,
  action: string,
  params: Record<string, unknown> = {},
): CoworkActionEvent {
  return {
    kind: 'info',
    message: `Action ${connector}.${action}`,
    detail: JSON.stringify({ kind: 'connector', connector, action, params }),
    at,
    actionKind: 'connector',
  }
}

function connectorDone(at: number, detail: string): CoworkActionEvent {
  return {
    kind: 'success',
    message: 'Action terminee',
    detail,
    at,
    actionKind: 'connector',
  }
}

describe('coworkProjectThread', () => {
  test('suit une chaine image, retouche, modele 3D puis jeu avec versions et parents', () => {
    const empty = createEmptyCoworkProjectThread()
    const imageThread = updateCoworkProjectThreadFromEvents(empty, {
      userPrompt: 'genere une photo de personnage cyberpunk',
      assistantReply: 'Image creee : output/imagegen/cyberpunk.png',
      events: [
        connectorStart(1_000, 'aurora_image', 'generate', {
          prompt: 'personnage cyberpunk',
        }),
        connectorDone(2_500, 'Image creee : output/imagegen/cyberpunk.png'),
      ],
    })

    assert.equal(imageThread.artifacts.length, 1)
    const image = imageThread.artifacts[0]
    assert.equal(image.kind, 'image')
    assert.equal(image.version, 1)
    assert.equal(image.path, 'output/imagegen/cyberpunk.png')
    assert.equal(imageThread.activeArtifactId, image.id)
    assert.equal(imageThread.stages[0].durationMs, 1_500)

    const retouchedThread = updateCoworkProjectThreadFromEvents(imageThread, {
      userPrompt: 'modifie celle-ci avec un manteau rouge',
      assistantReply: 'Nouvelle version : output/imagegen/cyberpunk_v2.png',
      events: [
        connectorStart(3_000, 'aurora_image', 'img2img', {
          prompt: 'manteau rouge',
          image_path: 'output/imagegen/cyberpunk.png',
        }),
        connectorDone(4_200, 'Nouvelle version : output/imagegen/cyberpunk_v2.png'),
      ],
    })

    const images = retouchedThread.artifacts.filter((artifact) => artifact.kind === 'image')
    assert.equal(images.length, 2)
    const imageV2 = images[1]
    assert.equal(imageV2.version, 2)
    assert.equal(imageV2.supersedesId, image.id)
    assert.ok(imageV2.parentIds?.includes(image.id))
    assert.equal(retouchedThread.activeArtifactId, imageV2.id)
    assert.equal(retouchedThread.artifacts.find((artifact) => artifact.id === image.id)?.active, false)

    const modelThread = updateCoworkProjectThreadFromEvents(retouchedThread, {
      userPrompt: 'modelise celui-ci en 3D',
      assistantReply: 'Modele exporte : output/3d/cyberpunk.glb',
      events: [
        connectorStart(5_000, 'aurora_3d', 'generate', {
          prompt: 'modele 3D fidele au personnage',
          image_path: 'output/imagegen/cyberpunk_v2.png',
        }),
        connectorDone(8_000, 'Modele exporte : output/3d/cyberpunk.glb'),
      ],
    })

    const model = modelThread.artifacts.find((artifact) => artifact.kind === 'model3d')
    assert.ok(model)
    assert.equal(model.path, 'output/3d/cyberpunk.glb')
    assert.ok(model.parentIds?.includes(imageV2.id))
    assert.equal(modelThread.activeArtifactId, model.id)
    assert.equal(modelThread.artifacts.filter((artifact) => artifact.active).length, 1)

    const gameThread = updateCoworkProjectThreadFromEvents(modelThread, {
      userPrompt: 'via ce modele 3d fais en le personnage principal d un jeu',
      assistantReply: 'Jeu cree et teste : output/games/cyberpunk/index.html',
      events: [
        connectorStart(9_000, 'aurora_code', 'generate', {
          prompt: 'jeu action autour du personnage principal cyberpunk',
          model_path: 'output/3d/cyberpunk.glb',
        }),
        connectorDone(12_400, 'Jeu cree et teste : output/games/cyberpunk/index.html'),
      ],
    })

    const game = gameThread.artifacts.find((artifact) => artifact.kind === 'game')
    assert.ok(game)
    assert.equal(game.path, 'output/games/cyberpunk/index.html')
    assert.ok(game.parentIds?.includes(model.id))
    assert.equal(gameThread.activeArtifactId, game.id)

    const newArtifacts = diffCoworkProjectArtifacts(modelThread, gameThread)
    assert.deepEqual(newArtifacts.map((artifact) => artifact.id), [game.id])

    const section = buildCoworkProjectThreadSection(gameThread)
    assert.match(section, /Fil projet Cowork/)
    assert.match(section, new RegExp(game.id))
    assert.match(section, /3D\/image -> jeu/)
    assert.match(section, /artefact actif/i)
  })

  test('retrouve un chemin dans la reponse finale quand le connecteur ne le repete pas', () => {
    const thread = updateCoworkProjectThreadFromEvents(undefined, {
      userPrompt: 'genere une image de vaisseau',
      assistantReply: 'Termine, apercu disponible : output/imagegen/vaisseau.png',
      events: [
        connectorStart(10, 'aurora_image', 'generate', { prompt: 'vaisseau' }),
        connectorDone(20, 'Generation terminee'),
      ],
    })

    assert.equal(thread.artifacts[0]?.path, 'output/imagegen/vaisseau.png')
    assert.equal(thread.activeArtifactId, thread.artifacts[0]?.id)
  })
})
