// Viewer autonome: un seul fichier HTML, ouvrable par lien direct.
//
// Le piege mesure en direct au premier essai: un projet contient presque
// toujours `</script>`. Sans echappement, la balise du PROJET ferme le bloc
// JSON de la page, et le viewer affiche sa propre charge utile en texte brut.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { buildCodeViewerHtml } from '../services/codeViewerHtml.ts'

const PROJECT = [
  {
    name: 'index.html',
    language: 'html',
    content: '<!doctype html><html><head><title>Convertisseur</title></head><body><h1>Convertisseur</h1><script src="script.js"></script></body></html>',
  },
  { name: 'style.css', language: 'css', content: 'body{font-family:Inter}' },
  { name: 'src/script.js', language: 'javascript', content: "console.log('ok')" },
  { name: 'assets/bundle.json', language: 'json', content: '{"assets":[]}' },
]

describe('codeViewerHtml — page autonome', () => {
  const html = buildCodeViewerHtml({
    files: PROJECT,
    title: 'Convertisseur',
    subtitle: 'run 971',
    previewHtml: '<!doctype html><html><body><h1>Convertisseur</h1></body></html>',
  })

  test('est un document complet et se suffit a lui-meme', () => {
    assert.match(html, /^<!doctype html>/)
    assert.match(html, /<title>Convertisseur<\/title>/)
    // Aucune ressource externe: la page doit vivre hors ligne et au bout du tunnel.
    assert.doesNotMatch(html, /<script[^>]+src=["']http/i)
    assert.doesNotMatch(html, /<link[^>]+href=["']http/i)
  })

  test("le </script> du PROJET ne ferme pas le bloc JSON de la page", () => {
    // Si l echappement saute, ce motif reapparait tel quel et la page casse.
    const payloadStart = html.indexOf('id="aurora-files"')
    const payloadEnd = html.indexOf('</script>', payloadStart)
    const payload = html.slice(payloadStart, payloadEnd)
    assert.equal(payload.includes('</script>'), false)
    assert.match(payload, /\\u003c\/script/)
  })

  test('embarque l arborescence, dossiers compris', () => {
    const rows = JSON.parse(
      html.match(/id="aurora-rows">([\s\S]*?)<\/script>/)![1].replace(/\\u003c/g, '<'),
    )
    const dirs = rows.filter((row: { kind: string }) => row.kind === 'dir').map((row: { path: string }) => row.path)
    assert.deepEqual(dirs.sort(), ['assets', 'src'])
    const paths = rows.map((row: { path: string }) => row.path)
    assert.ok(paths.includes('src/script.js'))
    // Les tailles sont deja formatees pour l affichage.
    const file = rows.find((row: { path: string }) => row.path === 'style.css')
    assert.match(String(file.size), /o$/)
  })

  test('embarque un rendu jouable du projet web', () => {
    const preview = JSON.parse(html.match(/id="aurora-preview">([\s\S]*?)<\/script>/)![1].replace(/\\u003c/g, '<'))
    assert.equal(typeof preview, 'string')
    assert.match(preview, /Convertisseur/)
  })

  test('un projet sans page web reste consultable', () => {
    const backend = buildCodeViewerHtml({
      files: [{ name: 'main.py', language: 'python', content: 'print(1)' }],
      title: 'Script',
    })
    const preview = JSON.parse(backend.match(/id="aurora-preview">([\s\S]*?)<\/script>/)![1])
    assert.equal(preview, null)
    assert.match(backend, /aurora-rows/)
  })

  test('le titre est echappe: un nom de projet ne peut pas injecter de balise', () => {
    const hostile = buildCodeViewerHtml({ files: PROJECT, title: '<img src=x onerror=alert(1)>' })
    assert.doesNotMatch(hostile, /<img src=x onerror/)
    assert.match(hostile, /&lt;img src=x onerror/)
  })
})
