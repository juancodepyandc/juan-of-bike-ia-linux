import test from 'node:test'
import assert from 'node:assert/strict'

import {
  detectStreamLanguage,
  instrumentPreviewHtml,
} from '../views/auroraV1CodeHelpers.ts'

test('detectStreamLanguage route les prompts courants', () => {
  assert.equal(detectStreamLanguage('script python flask', ''), 'python')
  assert.equal(detectStreamLanguage('app rust cargo', ''), 'rust')
  assert.equal(detectStreamLanguage('page html', ''), 'markup')
  assert.equal(detectStreamLanguage('composant React TypeScript', ''), 'typescript')
  assert.equal(detectStreamLanguage('script javascript .js', ''), 'javascript')
})

test('detectStreamLanguage reconnait le HTML depuis la sortie', () => {
  assert.equal(detectStreamLanguage('', '<!DOCTYPE html><html></html>'), 'markup')
})

test('instrumentPreviewHtml injecte le marqueur de preview dans head/html/fallback', () => {
  const withHead = instrumentPreviewHtml('<html><head></head><body>ok</body></html>')
  assert.match(withHead, /source: 'aurora-code-preview'/)
  assert.match(withHead, /<head><script>/)

  const withHtmlOnly = instrumentPreviewHtml('<html><body>ok</body></html>')
  assert.match(withHtmlOnly, /<html><script>/)

  const fragment = instrumentPreviewHtml('<main>ok</main>')
  assert.match(fragment, /^<script>/)
  assert.match(fragment, /<main>ok<\/main>$/)
})
