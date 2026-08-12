// Le HUB: une adresse stable qui liste TOUT ce qui a ete genere.
//
// Le lien par run est jetable — il faut le retrouver, un par generation. Ce
// test verrouille ce qui rend le hub utilisable: l ordre, les pastilles qui ne
// mentent pas, et l echappement de la charge utile.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  buildCodeViewerIndex,
  buildCodeViewerIndexHtml,
  describePlatformFamily,
  platformsFromSimulationStages,
  CODE_VIEWER_INDEX_SCHEMA,
} from '../services/codeViewerIndex.ts'

const entry = (id: string, createdAt: number, extra = {}) => ({
  id, createdAt, title: `Projet ${id}`, fileCount: 3, bytes: 1200, ...extra,
})

describe('codeViewerIndex — index des projets', () => {
  test('le plus recent passe en premier', () => {
    const index = buildCodeViewerIndex([entry('a', 100), entry('c', 300), entry('b', 200)])
    assert.deepEqual(index.projects.map((p) => p.id), ['c', 'b', 'a'])
    assert.equal(index.schemaVersion, CODE_VIEWER_INDEX_SCHEMA)
  })

  test('un index vide reste une page valide', () => {
    const html = buildCodeViewerIndexHtml(buildCodeViewerIndex([]))
    assert.match(html, /^<!doctype html>/)
    assert.match(html, /Aucun projet genere/)
  })
})

describe('codeViewerIndex — les pastilles ne mentent pas', () => {
  test('une execution reelle prime sur une simple detection', () => {
    const platforms = platformsFromSimulationStages([
      { family: 'mobile_real', label: 'AVD', status: 'detected', realExecution: false },
      { family: 'mobile_real', label: 'AVD', status: 'executed', realExecution: true },
      { family: 'web', label: 'Chromium', status: 'executed', realExecution: true },
    ])
    const mobile = platforms.find((p) => p.family === 'mobile_real')!
    assert.equal(mobile.realExecution, true)
    assert.equal(mobile.status, 'executed')
    assert.equal(platforms.length, 2)
  })

  test('une plateforme seulement detectee garde son statut', () => {
    const [platform] = platformsFromSimulationStages([
      { family: 'embedded', label: 'Renode', status: 'unavailable', realExecution: false },
    ])
    assert.equal(platform.realExecution, false)
    assert.equal(platform.status, 'unavailable')
    assert.equal(platform.label, 'Embarque')
  })

  test('les familles connues ont un libelle lisible', () => {
    assert.equal(describePlatformFamily('mobile_real'), 'Mobile')
    assert.equal(describePlatformFamily('os_boot'), 'Systeme')
    assert.equal(describePlatformFamily('inconnu'), 'inconnu')
  })
})

describe('codeViewerIndex — page du hub', () => {
  const html = buildCodeViewerIndexHtml(buildCodeViewerIndex([
    entry('run-1', 2, { title: 'Convertisseur', platforms: [{ family: 'web', label: 'Web', status: 'executed', realExecution: true }] }),
    entry('run-2', 1, { title: '</script><img src=x>' }),
  ]))

  test('embarque un selecteur de projet et un retour a la liste', () => {
    assert.match(html, /id="picker"/)
    assert.match(html, /id="backList"/)
  })

  test("un titre hostile ne peut pas s echapper de la charge utile", () => {
    const payload = html.slice(html.indexOf('id="aurora-index"'), html.indexOf('</script>', html.indexOf('id="aurora-index"')))
    assert.equal(payload.includes('</script>'), false)
    assert.equal(payload.includes('<img src=x>'), false)
  })

  test('charge chaque projet a la demande, sans changer de page', () => {
    assert.match(html, /fetch\('\.\/' \+ id \+ '\/project\.json'/)
    assert.match(html, /history\.replaceState/)
  })
})
