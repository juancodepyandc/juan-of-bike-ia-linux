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
import { buildCodeViewerHtml } from '../services/codeViewerHtml.ts'

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

describe('codeViewerIndex — la page doit REELLEMENT s executer', () => {
  // Bug vecu: `join('\n')` ecrit dans un template literal TS devient un vrai
  // retour a la ligne dans le script emis -> « Invalid or unexpected token »,
  // page morte, zero carte. Les tests de contenu passaient tous: seul un parse
  // du script emis l aurait vu. Ce garde vaut pour les deux pages viewer.
  function inlineScriptOf(html: string): string {
    return html.match(/<script>([\s\S]*?)<\/script>/)![1]
  }

  test('le script du hub est du JavaScript valide', () => {
    const html = buildCodeViewerIndexHtml(buildCodeViewerIndex([
      entry('run-1', 1, { buildOk: false, buildErrors: ['a.tsx(1,2): error TS1002'] }),
    ]))
    assert.doesNotThrow(() => new Function(inlineScriptOf(html)))
  })

  test('le script de la page autonome est du JavaScript valide', () => {
    const html = buildCodeViewerHtml({
      files: [{ name: 'index.html', language: 'html', content: '<h1>x</h1>' }],
      title: 'x',
      previewHtml: '<h1>x</h1>',
    })
    assert.doesNotThrow(() => new Function(inlineScriptOf(html)))
  })

  test('aucun retour a la ligne brut ne casse une chaine du script', () => {
    const html = buildCodeViewerIndexHtml(buildCodeViewerIndex([entry('run-1', 1)]))
    const script = inlineScriptOf(html)
    // Une chaine ouverte et jamais fermee sur la meme ligne = escape avalee.
    for (const [index, line] of script.split('\n').entries()) {
      const singles = (line.match(/(?<!\\)'/g) ?? []).length
      assert.equal(singles % 2, 0, `ligne ${index + 1} du script: quote non fermee -> ${line.trim().slice(0, 70)}`)
    }
  })
})
