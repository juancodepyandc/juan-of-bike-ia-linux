import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractCodeWebSearchSnippets,
  searchCodeWebReferences,
} from '../services/codeWebResearchClient.ts'

describe('codeWebResearchClient', () => {
  test('lit le format texte du bridge', () => {
    assert.deepEqual(extractCodeWebSearchSnippets({
      results: 'Premier resultat suffisamment detaille\nSecond resultat suffisamment detaille',
    }), [
      'Premier resultat suffisamment detaille',
      'Second resultat suffisamment detaille',
    ])
  })

  test('lit les lignes structurees et les deduplique', () => {
    const snippet = 'Reference officielle suffisamment detaillee'
    assert.deepEqual(extractCodeWebSearchSnippets({ resultsList: [
      { snippet },
      { title: 'Titre de reference suffisamment detaille' },
      { snippet },
    ] }), [snippet, 'Titre de reference suffisamment detaille'])
  })

  test('lit une enveloppe data', () => {
    assert.deepEqual(extractCodeWebSearchSnippets({
      data: { results: [{ content: 'Documentation primaire suffisamment detaillee' }] },
    }), ['Documentation primaire suffisamment detaillee'])
  })

  test('appelle uniquement la route bridge', async () => {
    let calledUrl = ''
    const snippets = await searchCodeWebReferences('webgl accessibility', {
      bridgeUrl: 'http://bridge.test/',
      fetchImpl: async (input, init) => {
        calledUrl = String(input)
        assert.deepEqual(JSON.parse(String(init?.body)), { query: 'webgl accessibility', limit: 3 })
        return new Response(JSON.stringify({ results: 'Guide WebGL officiel suffisamment detaille' }))
      },
      limit: 3,
    })
    assert.equal(calledUrl, 'http://bridge.test/api/web/search')
    assert.deepEqual(snippets, ['Guide WebGL officiel suffisamment detaille'])
  })

  test('retourne vide sur HTML ou erreur HTTP', async () => {
    assert.deepEqual(await searchCodeWebReferences('query', {
      fetchImpl: async () => new Response('<html>proxy error</html>'),
    }), [])
    assert.deepEqual(await searchCodeWebReferences('query', {
      fetchImpl: async () => new Response('down', { status: 503 }),
    }), [])
  })

  test('retourne vide sans requete pour une query vide', async () => {
    let called = false
    const result = await searchCodeWebReferences('   ', {
      fetchImpl: async () => {
        called = true
        return new Response()
      },
    })
    assert.equal(called, false)
    assert.deepEqual(result, [])
  })
})
