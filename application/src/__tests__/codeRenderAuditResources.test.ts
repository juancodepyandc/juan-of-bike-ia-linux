import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

// @ts-expect-error — harnais .mjs sans types, importe pour ce qu il fait
import { describeFailedResources } from '../../scripts/code_harness/render_audit.mjs'

// MESURE (run v129, premier `done` de la serie):
//   FAIL runtime-no-error: Failed to load resource: the server responded with
//                          a status of 404 (Not Found)
//   rendu 60/100 (seuil 70) echecs=runtime_clean,...
//   passe ciblee (runtime_clean): 8 fichiers corriges
//   rendu apres passe esthetique: 60/100 -> livrable precedent conserve
//
// La porte condamnait le rendu sans jamais nommer la ressource. Le correcteur a
// donc modifie 8 fichiers a l aveugle, pour zero point. Le message console du
// navigateur ne porte pas l URL: il faut ecouter les REQUETES.

const files = [{ name: 'index.html' }, { name: 'assets/logo.png' }]

describe('audit de rendu: nommer la ressource, et dire quoi en faire', () => {
  test('un fichier absent du livrable est nomme, et le conseil est realisable', () => {
    const [message] = describeFailedResources([{ status: 404, url: 'http://127.0.0.1:5173/assets/hero.jpg' }], files)
    assert.match(message, /\/assets\/hero\.jpg/)
    assert.match(message, /n est PAS livre/)
    assert.match(message, /Emets-le, ou retire la reference/)
  })

  test('un fichier PRESENT mais introuvable a l execution oriente vers le chemin', () => {
    const [message] = describeFailedResources([{ status: 404, url: 'http://127.0.0.1:5173/assets/logo.png' }], files)
    assert.match(message, /EST livre/)
    assert.match(message, /chemin ou la base d URL/)
  })

  test('un APPEL RESEAU ne recoit pas le conseil irrealisable « emets ce fichier »', () => {
    // `/api/orders` n est pas un fichier a livrer. Lui dire de l emettre serait
    // exactement la famille de conseils inachevables que ce module ferme.
    const [message] = describeFailedResources(
      [{ status: 0, url: 'http://127.0.0.1:5173/api/orders', detail: 'net::ERR_CONNECTION_REFUSED' }],
      files,
    )
    assert.doesNotMatch(message, /Emets-le/)
    assert.match(message, /Appel reseau/)
    assert.match(message, /donnees locales de repli/)
  })

  test('les doublons sont fusionnes: une ressource, un diagnostic', () => {
    const out = describeFailedResources([
      { status: 404, url: 'http://x/a.png' },
      { status: 404, url: 'http://x/a.png' },
      { status: 404, url: 'http://x/b.png' },
    ], files)
    assert.equal(out.length, 2)
  })

  test('aucune requete en echec: aucun diagnostic invente', () => {
    assert.deepEqual(describeFailedResources([], files), [])
    assert.deepEqual(describeFailedResources(undefined, files), [])
  })
})
