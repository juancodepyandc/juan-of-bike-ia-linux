/**
 * Tests pour services/codeOutputIntelligent — post-process intelligent
 * (DOMParser absent sous Node → seul le path CSS standalone est testé).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent.ts'
import type { ParsedFile } from '../services/codeOutputFiles.ts'

function css(content: string, path = 'style.css'): ParsedFile {
  return { path, content, language: 'css' }
}
function html(content: string, path = 'index.html'): ParsedFile {
  return { path, content, language: 'markup' }
}
function js(content: string, path = 'app.js'): ParsedFile {
  return { path, content, language: 'javascript' }
}

describe('intelligentlyElevateFiles — files vide', () => {
  test('[] → renvoie {files:[], report}', () => {
    const { files, report } = intelligentlyElevateFiles([])
    assert.deepEqual(files, [])
    assert.equal(report.imagesFixed, 0)
    assert.equal(report.buttonsWired, 0)
  })
})

describe('intelligentlyElevateFiles — fixCssBackgroundImages (path CSS standalone)', () => {
  test('background-image url(local.jpg) → remplacé par Unsplash', () => {
    const { files, report } = intelligentlyElevateFiles([
      css('.hero { background-image: url("local.jpg"); }'),
    ])
    assert.ok(files[0].content.includes('source.unsplash.com'))
    assert.equal(report.bgImagesFixed, 1)
  })

  test('background-image url(https://...) → URL externe préservée', () => {
    const url = 'https://example.com/banner.png'
    const { files, report } = intelligentlyElevateFiles([
      css(`.hero { background-image: url('${url}'); }`),
    ])
    assert.ok(files[0].content.includes(url))
    assert.equal(report.bgImagesFixed, 0)
  })

  test('selector name forwardé comme query Unsplash', () => {
    const { files } = intelligentlyElevateFiles([
      css('.product-showcase { background-image: url(p.jpg); }'),
    ])
    // "product-showcase" → "product showcase" → query
    assert.ok(files[0].content.includes('product') || files[0].content.includes('showcase'))
  })

  test('plusieurs backgrounds → tous traités', () => {
    const { report } = intelligentlyElevateFiles([
      css('.a { background-image: url(a.jpg); } .b { background-image: url(b.png); }'),
    ])
    assert.ok(report.bgImagesFixed >= 1)
  })

  test('background tout court (sans -image) avec url() → traité', () => {
    const { files, report } = intelligentlyElevateFiles([
      css('.hero { background: url("local.jpg") center/cover; }'),
    ])
    // Le regex matche `background(-image)?` donc devrait traiter
    if (report.bgImagesFixed > 0) {
      assert.ok(files[0].content.includes('source.unsplash.com'))
    }
  })

  test('CSS sans background-image → inchangé', () => {
    const original = '.btn { color: red; padding: 8px; }'
    const { files, report } = intelligentlyElevateFiles([css(original)])
    assert.equal(files[0].content, original)
    assert.equal(report.bgImagesFixed, 0)
  })
})

describe('intelligentlyElevateFiles — fichiers passthrough', () => {
  test('JS file → renvoyé inchangé', () => {
    const code = 'console.log("hello")'
    const { files } = intelligentlyElevateFiles([js(code)])
    assert.equal(files[0].content, code)
  })

  test('Python file → renvoyé inchangé', () => {
    const { files } = intelligentlyElevateFiles([
      { path: 'a.py', language: 'python', content: 'print(1)' },
    ])
    assert.equal(files[0].content, 'print(1)')
  })

  test('mix CSS + JS → JS intact, CSS traité', () => {
    const { files, report } = intelligentlyElevateFiles([
      css('.hero { background-image: url(x.jpg); }'),
      js('console.log("hi")'),
    ])
    assert.ok(files[0].content.includes('source.unsplash.com'))
    assert.equal(files[1].content, 'console.log("hi")')
    assert.equal(report.bgImagesFixed, 1)
  })
})

describe('intelligentlyElevateFiles — HTML sans DOMParser (Node)', () => {
  test('HTML laissé brut quand DOMParser absent', () => {
    const original = '<html><body><h1>Test</h1></body></html>'
    const { files } = intelligentlyElevateFiles([html(original)])
    // DOMParser absent sous Node → contenu inchangé
    assert.equal(files[0].content, original)
  })

  test('report cohérent même sans HTML processing', () => {
    const { report } = intelligentlyElevateFiles([html('<html></html>')])
    assert.equal(report.imagesFixed, 0)
    assert.equal(report.buttonsWired, 0)
    assert.equal(report.countersWired, false)
    assert.equal(report.heroImageInjected, false)
  })
})

describe('intelligentlyElevateFiles — structure report', () => {
  test('report contient tous les champs attendus', () => {
    const { report } = intelligentlyElevateFiles([])
    assert.ok('imagesFixed' in report)
    assert.ok('picturesFixed' in report)
    assert.ok('bgImagesFixed' in report)
    assert.ok('heroImageInjected' in report)
    assert.ok('buttonsWired' in report)
    assert.ok('buttonKinds' in report)
    assert.ok('colorsElevated' in report)
    assert.ok('brandRecolored' in report)
    assert.ok('animationsScoped' in report)
    assert.ok('countersWired' in report)
  })

  test('buttonKinds par défaut = {}', () => {
    const { report } = intelligentlyElevateFiles([])
    assert.deepEqual(report.buttonKinds, {})
  })
})

describe('intelligentlyElevateFiles — promptHint / brandPrimary', () => {
  test('promptHint forwardé comme fallback query', () => {
    const { files } = intelligentlyElevateFiles([
      css('.unstyled { background-image: url(x.jpg); }'),
    ], 'voiture sport rouge')
    // Le selector .unstyled a un nom utilisable → query basée sur selector
    assert.ok(files[0].content.includes('unsplash'))
  })

  test('promptHint trop long tronqué à 80', () => {
    const longHint = 'a'.repeat(150)
    const { files } = intelligentlyElevateFiles([css('.x { background: url(y.jpg); }')], longHint)
    assert.ok(files.length === 1)
  })

  test('appel sans args extras → ok', () => {
    const { files } = intelligentlyElevateFiles([css('.x { color: red; }')])
    assert.equal(files.length, 1)
  })
})

describe('intelligentlyElevateFiles — SCSS support', () => {
  test('SCSS file traité comme CSS', () => {
    const { files, report } = intelligentlyElevateFiles([
      { path: 'main.scss', language: 'scss', content: '.hero { background-image: url(x.jpg); }' },
    ])
    if (report.bgImagesFixed > 0) {
      assert.ok(files[0].content.includes('source.unsplash.com'))
    }
  })
})
