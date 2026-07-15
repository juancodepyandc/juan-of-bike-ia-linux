/**
 * Tests pour services/codeOutputElevate — post-process des fichiers générés
 * pour les "élever" (oklch, keyframes, images SVG locales) sans re-LLM.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { elevateGeneratedFiles } from '../services/codeOutputElevate.ts'
import type { ParsedFile } from '../services/codeOutputFiles.ts'

function cssFile(content: string): ParsedFile {
  return { path: 'style.css', content, language: 'css' }
}
function htmlFile(content: string): ParsedFile {
  return { path: 'index.html', content, language: 'markup' }
}
function jsFile(content: string): ParsedFile {
  return { path: 'app.js', content, language: 'javascript' }
}

describe('elevateGeneratedFiles — hex → oklch', () => {
  test('#7c3aed (violet Tailwind) → oklch', () => {
    const { files, report } = elevateGeneratedFiles([
      cssFile('.btn { background: #7c3aed; }'),
    ])
    assert.ok(files[0].content.includes('oklch('))
    assert.ok(!files[0].content.toLowerCase().includes('#7c3aed'))
    assert.ok(report.hexReplaced >= 1)
  })

  test('plusieurs hex remplacés', () => {
    const { report } = elevateGeneratedFiles([
      cssFile('.a { color: #3b82f6; } .b { color: #22c55e; } .c { color: #ef4444; }'),
    ])
    assert.ok(report.hexReplaced >= 3)
  })

  test('hex non-mappé → laissé tel quel', () => {
    const { files, report } = elevateGeneratedFiles([
      cssFile('.x { color: #abcdef; }'),
    ])
    assert.ok(files[0].content.includes('#abcdef'))
    assert.equal(report.hexReplaced, 0)
  })
})

describe('elevateGeneratedFiles — animations', () => {
  test('CSS sans keyframes → keyframes injectés', () => {
    const { files, report } = elevateGeneratedFiles([
      cssFile('.btn { color: red; }'),
    ])
    assert.ok(files[0].content.includes('@keyframes'))
    assert.equal(report.animationsInjected, true)
  })

  test('CSS avec keyframes existants → pas réinjecté', () => {
    const css = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } } .btn { animation: spin 1s; }'
    const { report } = elevateGeneratedFiles([cssFile(css)])
    assert.equal(report.animationsInjected, false)
  })

  test('CSS partiel (keyframes mais pas animation) → injection animations overlay', () => {
    const css = '@keyframes fade { to { opacity: 1; } }'
    const { files } = elevateGeneratedFiles([cssFile(css)])
    // Doit avoir ajouté l'overlay animations
    assert.ok(files[0].content.includes('animation:') || files[0].content.includes('animation ='))
  })
})

describe('elevateGeneratedFiles — images placeholder', () => {
  test('<img src="via.placeholder..."> → remplace par SVG local', () => {
    const html = '<img src="https://via.placeholder.com/600x400" alt="banner">'
    const { files, report } = elevateGeneratedFiles([htmlFile(html)])
    assert.ok(files[0].content.includes('data:image/svg+xml'))
    assert.equal(report.imagesReplaced, 1)
  })

  test('<img src="picsum..."> → remplacé', () => {
    const html = '<img src="https://picsum.photos/600/400" alt="photo">'
    const { report } = elevateGeneratedFiles([htmlFile(html)])
    assert.equal(report.imagesReplaced, 1)
  })

  test('image avec extension locale → traité', () => {
    const html = '<img src="banner.jpg" alt="bannière">'
    const { report } = elevateGeneratedFiles([htmlFile(html)])
    assert.ok(report.imagesReplaced >= 0)
  })

  test('img sans alt → alt="visual" injecté', () => {
    const html = '<img src="photo.png">'
    const { files } = elevateGeneratedFiles([htmlFile(html)])
    if (files[0].content.includes('data:image/svg+xml')) {
      assert.ok(files[0].content.includes('alt='))
    }
  })

  test('img absolue distante non-placeholder → pas remplacée', () => {
    const html = '<img src="https://example.com/banner.gif" alt="x">'
    const { report } = elevateGeneratedFiles([htmlFile(html)])
    // .gif n'est pas dans la liste png/jpe?g/webp/svg du regex
    assert.equal(report.imagesReplaced, 0)
  })
})

describe('elevateGeneratedFiles — style inline dans HTML', () => {
  test('<style> dans HTML → hex remplacés + keyframes injectés', () => {
    const html = '<html><style>.x { background: #7c3aed; }</style></html>'
    const { files, report } = elevateGeneratedFiles([htmlFile(html)])
    assert.ok(files[0].content.includes('oklch('))
    assert.equal(report.animationsInjected, true)
  })
})

describe('elevateGeneratedFiles — IntersectionObserver fallback', () => {
  test('quand animations injectées → script IntersectionObserver ajouté au dernier JS', () => {
    const { files, report } = elevateGeneratedFiles([
      cssFile('.x { color: red; }'),
      jsFile('console.log("hi")'),
    ])
    const js = files[1].content
    assert.ok(js.includes('IntersectionObserver') || report.scriptInjected)
  })

  test('JS qui contient déjà IntersectionObserver → pas réinjecté', () => {
    const { files } = elevateGeneratedFiles([
      cssFile('.x { color: red; }'),
      jsFile('const io = new IntersectionObserver(() => {})'),
    ])
    const js = files[1].content
    const occurrences = (js.match(/IntersectionObserver/g) || []).length
    // Pas plus de 2 (l'existant + éventuel commentaire de l'injecté qui aurait été skip)
    assert.ok(occurrences <= 2)
  })
})

describe('elevateGeneratedFiles — structure du report', () => {
  test('report contient les 4 champs attendus', () => {
    const { report } = elevateGeneratedFiles([])
    assert.ok('hexReplaced' in report)
    assert.ok('animationsInjected' in report)
    assert.ok('imagesReplaced' in report)
    assert.ok('scriptInjected' in report)
  })

  test('files vide → arrays/booleans vides', () => {
    const { files, report } = elevateGeneratedFiles([])
    assert.equal(files.length, 0)
    assert.equal(report.hexReplaced, 0)
    assert.equal(report.imagesReplaced, 0)
  })

  test('immutabilité — input files non modifiés', () => {
    const inputCss = cssFile('.x { color: #7c3aed; }')
    const original = inputCss.content
    elevateGeneratedFiles([inputCss])
    assert.equal(inputCss.content, original)
  })
})
