#!/usr/bin/env node
// Real react-markdown 10, remark-gfm and React 19 server rendering of the real Cowork helpers
// (Node type stripping). Checks what reaches the DOM of a Cowork bubble; no browser, no bridge.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const {
  coworkMarkdownOptions,
  keepCoworkLinks,
  linkifyNotions,
  notionFromHref,
} = await import('../src/utils/coworkNotionLinks.ts')

const DEFAULT_OPTIONS = { remarkPlugins: [remarkGfm] }

/** Static markup of ReactMarkdown; any React warning (unknown DOM prop, empty src…) fails the test. */
function render(markdown, options = DEFAULT_OPTIONS) {
  const warnings = []
  const original = console.error
  console.error = (...args) => { warnings.push(args.map(String).join(' ')) }
  let html
  try {
    html = renderToStaticMarkup(createElement(ReactMarkdown, options, markdown))
  } finally {
    console.error = original
  }
  assert.deepEqual(warnings, [], 'React warned while rendering')
  return html
}

/** Exactly what Bubble renders for an assistant turn. */
const bubble = (content) => render(linkifyNotions(content), coworkMarkdownOptions)

test('the defect: by default react-markdown blanks the notion href, so a click reloads the page', () => {
  assert.equal(render(linkifyNotions('Voir [[photosynthèse]].')), '<p>Voir <a href="">photosynthèse</a>.</p>')
})

test('keepCoworkLinks keeps the notion href and leaves every other URL to the default sanitising', () => {
  const html = render(linkifyNotions([
    'Voir [[photosynthèse]].',
    '[js](javascript:alert(1)) [JS](JaVaScRiPt:alert(1)) [vb](vbscript:msgbox) [donnée](data:text/html,x) [fichier](file:///etc/passwd)',
    '[web](https://example.org/a?b=1) [mail](mailto:a@example.org) [relatif](./doc.md) [ancre](#section)',
  ].join('\n\n')), { ...DEFAULT_OPTIONS, urlTransform: keepCoworkLinks })
  assert.match(html, /<a href="cowork:\/\/explain\/photosynth%C3%A8se">photosynthèse<\/a>/)
  for (const label of ['js', 'JS', 'vb', 'donnée', 'fichier']) {
    assert.match(html, new RegExp(`<a href="">${label}</a>`), label)
  }
  assert.doesNotMatch(html, /javascript:|vbscript:|data:|file:/i)
  assert.match(html, /<a href="https:\/\/example\.org\/a\?b=1">web<\/a>/)
  assert.match(html, /<a href="mailto:a@example\.org">mail<\/a>/)
  assert.match(html, /<a href="\.\/doc\.md">relatif<\/a>/)
  assert.match(html, /<a href="#section">ancre<\/a>/)
})

test('only the href of a link that names a notion escapes the default sanitising', () => {
  const a = { type: 'element', tagName: 'a', properties: {}, children: [] }
  const img = { type: 'element', tagName: 'img', properties: {}, children: [] }
  assert.equal(keepCoworkLinks('cowork://explain/onde', 'href', a), 'cowork://explain/onde')
  assert.equal(keepCoworkLinks('cowork://explain/onde', 'src', img), '')
  for (const url of ['cowork://explain/', 'cowork://explain/%20', 'cowork://other/onde', 'COWORK://explain/onde']) {
    assert.equal(keepCoworkLinks(url, 'href', a), '', url)
  }
})

test('a Cowork bubble renders each notion as a button carrying its label, with no navigable URL', () => {
  const html = bubble('Voir [[photosynthèse]] et [[ loi d’Ohm (U=RI) ]], puis [le cours](https://example.org).')
  assert.match(html, /<button type="button" class="cowork-notion" title="Expliquer « photosynthèse »" data-cowork-notion="photosynthèse">photosynthèse<\/button>/)
  assert.match(html, /data-cowork-notion="loi d’Ohm \(U=RI\)">loi d’Ohm \(U=RI\)<\/button>/)
  assert.match(html, /<a href="https:\/\/example\.org">le cours<\/a>/)
  assert.doesNotMatch(html, /cowork:/)
})

test('a notion with an unbalanced parenthesis still becomes a button', () => {
  // encodeURIComponent keeps "(": the destination used to end early and the raw markdown stayed visible.
  const html = bubble('Rappel : [[loi (U=RI]].')
  assert.match(html, /data-cowork-notion="loi \(U=RI">loi \(U=RI<\/button>/)
  assert.doesNotMatch(html, /\]\(|cowork:/)
})

test('a raw notion link with a malformed escape renders and decodes without throwing', () => {
  assert.throws(() => decodeURIComponent('Th%C3%A9orie%ZZ'), URIError) // what the old click handler called
  const html = bubble('[Théorie](cowork://explain/Th%C3%A9orie%ZZ) et [cassé](cowork://explain/%E0%A4%A)')
  assert.match(html, /data-cowork-notion="Théorie%ZZ">Théorie<\/button>/)
  // micromark escapes the lone "%" of the destination: the label is the verbatim malformed escape.
  assert.match(html, /data-cowork-notion="%E0%A4%25A">cassé<\/button>/)
  assert.doesNotMatch(html, /cowork:/)
})

test('notionFromHref decodes labels and returns null when the href names no notion', () => {
  assert.equal(notionFromHref('cowork://explain/photosynth%C3%A8se'), 'photosynthèse')
  assert.equal(notionFromHref('cowork://explain/loi%20%28U%3DRI'), 'loi (U=RI')
  assert.equal(notionFromHref('cowork://explain/Th%C3%A9orie%ZZ'), 'Théorie%ZZ')
  assert.equal(notionFromHref('cowork://explain/100%'), '100%')
  for (const href of [undefined, null, '', 'https://example.org', 'cowork://explain/', 'cowork://explain/%20%20']) {
    assert.equal(notionFromHref(href), null, String(href))
  }
})

test('linkifyNotions leaves markers that name nothing as text', () => {
  for (const text of ['[[a]]', '[[   ]]', '[[onde\nmécanique]]', `[[${'x'.repeat(81)}]]`]) {
    assert.equal(linkifyNotions(text), text)
  }
  assert.equal(linkifyNotions('[[ ondes ]]'), '[ondes](cowork://explain/ondes)')
})

test('without notions, a bubble renders exactly what react-markdown renders by default', () => {
  const markdown = [
    'Texte[^1] avec [lien](https://example.org "titre"), <https://auto.example>, www.example.com et `code`.',
    '| a | b |\n|---|---|\n| 1 | [x](http://example.org/x) |',
    '[^1]: Note [retour](#haut).',
  ].join('\n\n')
  assert.equal(bubble(markdown), render(markdown))
})
