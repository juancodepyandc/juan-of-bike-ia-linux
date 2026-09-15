import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { generateCyberAdvisory, type CyberAdvisoryRequest } from '../services/cyber/advisory.ts'

const request: CyberAdvisoryRequest = {
  model: 'local-test',
  request: 'Examine la configuration TLS de mon application.',
  target: 'https://example.test',
  targetType: 'URL',
  isWeb: true,
  stance: 'defense',
}

describe('analyse cyber à partir de la demande', () => {
  test('une réponse textuelle ne devient pas une preuve de vérification de la cible', async () => {
    const calls: string[] = []
    const result = await generateCyberAdvisory(request, async (model, prompt, options) => {
      calls.push(model)
      assert.ok(prompt.includes(request.target))
      assert.match(prompt, /Aucun outil n'a interrogé la cible/)
      assert.equal(options.num_ctx, 8192)
      return { response: '<think>draft</think>Voici les points à vérifier.' }
    })
    assert.deepEqual(calls, ['local-test'])
    assert.deepEqual(result, { content: 'Voici les points à vérifier.', basis: 'request_only', targetVerified: false })
  })

  test('une sortie vide ou uniquement interne échoue au lieu de déclarer un succès', async () => {
    for (const response of [undefined, '', '  ', '<think>draft</think>', '<think>draft']) {
      await assert.rejects(generateCyberAdvisory(request, async () => ({ response })), /Aucune analyse exploitable/)
    }
    await assert.rejects(generateCyberAdvisory(request, async () => null), /Aucune analyse exploitable/)
  })

  test('une panne de transport est propagée au flux d’erreur', async () => {
    const error = new Error('model unavailable')
    await assert.rejects(generateCyberAdvisory(request, async () => { throw error }), error)
  })

  test('le contexte local reste une analyse des seuls artefacts fournis', async () => {
    const result = await generateCyberAdvisory({ ...request, isWeb: false, target: 'src/server.ts' }, async (_model, prompt) => {
      assert.match(prompt, /artefacts effectivement fournis/)
      return { response: 'Extrait manquant.' }
    })
    assert.equal(result.targetVerified, false)
  })
})
