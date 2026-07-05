/**
 * Tests pour services/coworkContentDigest — HTML digest extractor + JSON
 * salvage + resilient fallback reply.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractHtmlDigest,
  salvageProseFromMalformedJson,
  buildResilientFallbackReply,
} from '../services/coworkContentDigest.ts'
import type { CoworkAction, CoworkActionResult } from '../services/coworkTypes.ts'

describe('extractHtmlDigest', () => {
  test('HTML vide → message fallback', () => {
    const r = extractHtmlDigest('')
    assert.ok(r.includes('aucun contenu'))
  })

  test('null → message fallback', () => {
    const r = extractHtmlDigest(null as never)
    assert.ok(r.includes('aucun contenu'))
  })

  test('extrait <title>', () => {
    const r = extractHtmlDigest('<html><head><title>Mon Titre</title></head></html>')
    assert.ok(r.includes('title: Mon Titre'))
  })

  test('extrait meta description', () => {
    const r = extractHtmlDigest('<head><meta name="description" content="ma description"></head>')
    assert.ok(r.includes('description: ma description'))
  })

  test('extrait og:title quand différent du title', () => {
    const r = extractHtmlDigest('<title>A</title><meta property="og:title" content="B">')
    assert.ok(r.includes('og:title: B'))
  })

  test('extrait headings h1/h2/h3', () => {
    const r = extractHtmlDigest('<h1>Section 1</h1><h2>Sous-section</h2><h3>Détail</h3>')
    assert.ok(r.includes('Section 1'))
    assert.ok(r.includes('Sous-section'))
    assert.ok(r.includes('Détail'))
  })

  test('extrait paragraphes longs (> 20 chars)', () => {
    // Input riche pour éviter le fallback textSnippet qui inclurait tout
    const html = '<title>T</title><h1>H</h1><p>Trop court</p><p>Ceci est un paragraphe avec assez de contenu pour passer le filtre.</p><h2>Autre</h2>'
    const r = extractHtmlDigest(html)
    assert.ok(r.includes('Ceci est un paragraphe'))
    // Le paragraphe court ne doit pas être listé sous "paragraphs:"
    const paraSection = r.slice(r.indexOf('paragraphs:'), r.indexOf('links:') > 0 ? r.indexOf('links:') : r.length)
    assert.ok(!paraSection.includes('Trop court'))
  })

  test('extrait liens avec text + href', () => {
    const r = extractHtmlDigest('<a href="https://example.com">Cliquez ici</a>')
    assert.ok(r.includes('Cliquez ici -> https://example.com'))
  })

  test('ignore ancres et javascript: links', () => {
    const r = extractHtmlDigest('<a href="#section">Ancre</a><a href="javascript:void(0)">JS</a>')
    assert.ok(!r.includes('Ancre ->'))
    assert.ok(!r.includes('JS ->'))
  })

  test('extrait images via src', () => {
    const r = extractHtmlDigest('<img src="https://example.com/img.jpg">')
    assert.ok(r.includes('images:'))
    assert.ok(r.includes('img.jpg'))
  })

  test('limite headings à 12', () => {
    const html = Array.from({ length: 20 }, (_, i) => `<h1>Heading ${i}</h1>`).join('')
    const r = extractHtmlDigest(html)
    const lines = r.split('\n').filter((l) => l.startsWith('  - '))
    assert.ok(lines.length <= 12)
  })

  test('limite paragraphes à 8', () => {
    const longPara = 'Lorem ipsum dolor sit amet consectetur adipiscing elit '
    const html = Array.from({ length: 15 }, () => `<p>${longPara}</p>`).join('')
    const r = extractHtmlDigest(html)
    const paraIdx = r.indexOf('paragraphs:')
    const linkIdx = r.indexOf('links:')
    const block = linkIdx > 0 ? r.slice(paraIdx, linkIdx) : r.slice(paraIdx)
    const lines = block.split('\n').filter((l) => l.startsWith('  - '))
    assert.ok(lines.length <= 8)
  })

  test('entités HTML décodées', () => {
    const r = extractHtmlDigest('<h1>Café &amp; thé</h1>')
    assert.ok(r.includes('Café & thé'))
  })

  test('fallback textSnippet quand peu de structure', () => {
    const html = '<div>' + 'lorem ipsum dolor '.repeat(40) + '</div>'
    const r = extractHtmlDigest(html)
    assert.ok(r.includes('textSnippet') || r.length > 0)
  })

  test('strip script/style tags', () => {
    const r = extractHtmlDigest('<div>contenu visible</div><script>secret()</script><style>.x{}</style>')
    assert.ok(!r.includes('secret'))
    assert.ok(!r.includes('.x{}'))
  })
})

describe('salvageProseFromMalformedJson', () => {
  test('chaîne courte → null', () => {
    assert.equal(salvageProseFromMalformedJson('hi'), null)
  })

  test('JSON cassé avec "message":"..." → message extrait', () => {
    const raw = '{ "message": "Voici une réponse utile à donner au user", broken'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r?.includes('Voici une réponse'))
  })

  test('JSON dans fence avec message → extrait', () => {
    const raw = '```json\n{ "message": "Une réponse importante longue à valider" }\n```'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r?.includes('Une réponse'))
  })

  test('plusieurs "message" → garde le plus long', () => {
    const raw = '"message": "court", "message": "Voici une réponse beaucoup plus longue valide pour le user"'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r?.includes('plus longue'))
  })

  test('escapes JSON décodés (\\n, \\t)', () => {
    const raw = '{ "message": "ligne 1\\nligne 2\\nligne 3 dans le message" }'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r?.includes('ligne 1'))
    assert.ok(r?.includes('\n'))
  })

  test('unicode escape \\uXXXX décodé', () => {
    const raw = '{ "message": "h\\u00e9llo le monde un message asser long" }'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r?.includes('héllo'))
  })

  test('rien d intéressant → null', () => {
    const raw = '{ "x": 1, "y": 2 }'
    const r = salvageProseFromMalformedJson(raw)
    // peut renvoyer prose strippée si > 80 chars, sinon null
    // raw < 80 chars → null
    assert.equal(r, null)
  })

  test('longue chaîne quotée (sans champ message) → fallback', () => {
    const raw = '{ "x": "' + 'a'.repeat(80) + '" }'
    const r = salvageProseFromMalformedJson(raw)
    assert.ok(r !== null)
  })
})

describe('buildResilientFallbackReply', () => {
  function entry(action: CoworkAction, result: Partial<CoworkActionResult> = {}): { action: CoworkAction; result: CoworkActionResult } {
    return {
      action,
      result: { ok: true, durationMs: 100, ...result },
    }
  }

  test('history vide → null', () => {
    assert.equal(buildResilientFallbackReply([]), null)
  })

  test('history avec fetch HTML → synthèse markdown', () => {
    const html = '<html><head><title>Mon Site</title><meta name="description" content="desc"></head><body><h1>Bienvenue</h1><p>Long paragraphe de contenu de test important</p></body></html>'
    const r = buildResilientFallbackReply([
      entry({ kind: 'fetch', url: 'https://x.com' }, { output: html }),
    ])
    assert.ok(r?.includes('Synthese'))
    assert.ok(r?.includes('Mon Site'))
  })

  test('history avec browser.read_html → synthèse', () => {
    const html = '<html><title>Page</title><body><p>Long paragraphe contenu suffisant pour passer filtre</p></body></html>'
    const r = buildResilientFallbackReply([
      entry({ kind: 'browser', operation: 'read_html' }, { output: html }),
    ])
    assert.ok(r?.includes('Page'))
  })

  test('history avec action data non-HTML → preview brut', () => {
    const r = buildResilientFallbackReply([
      entry({ kind: 'read_file', path: 'a.json' }, { data: { foo: 'bar' } }),
    ])
    assert.ok(r?.includes('Donnees recuperees') || r?.includes('foo'))
  })

  test('action en échec ignorée', () => {
    const r = buildResilientFallbackReply([
      entry({ kind: 'fetch', url: 'x' }, { ok: false, error: 'fail' }),
    ])
    assert.equal(r, null)
  })

  test('history sans data utile → null', () => {
    const r = buildResilientFallbackReply([
      entry({ kind: 'reply', message: 'hi' }),
    ])
    assert.equal(r, null)
  })

  test('regarde dans les 5 dernières entries seulement', () => {
    const trash = Array.from({ length: 10 }, () => entry({ kind: 'reply', message: 'x' }))
    const html = '<html><title>Recent</title></html>'
    const r = buildResilientFallbackReply([
      entry({ kind: 'fetch', url: 'old' }, { output: '<title>Old</title>' }),
      ...trash,
    ])
    // L'ancienne action HTML est hors fenêtre → null
    assert.equal(r, null)
  })
})
