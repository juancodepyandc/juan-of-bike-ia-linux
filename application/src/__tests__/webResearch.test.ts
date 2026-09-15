/**
 * Tests de la recherche web du module conversation.
 *
 * Ce qui est verifie ici tient en une phrase : quand le module dit qu'il a
 * cherche, il a cherche. Avant, l'etape « Recherche » demandait au modele
 * d'enumerer ce qu'il croyait savoir, aucune requete ne quittait la machine,
 * et le prompt systeme annoncait quand meme « Tu as acces a la recherche
 * web ». Les tests couvrent donc : la decision de sortir, les sources
 * remontees, le passage a l'etat « lue », et le cas ou le pont est eteint.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCitationInstructions,
  decideWebResearch,
  runWebResearch,
  type WebResearchResult,
} from '../services/webResearch.ts'

const planQueries = async () => ['requete test']

function fakeSearch(rows: Array<{ title: string; url: string; snippet: string }>) {
  return async () => rows
}

describe('decideWebResearch', () => {
  test('l interrupteur de l utilisateur prime sur l heuristique', () => {
    assert.equal(decideWebResearch('salut', 'on').search, true)
    assert.equal(decideWebResearch('quelles sont les dernieres actualites', 'off').search, false)
  })

  test('demande explicite de sources', () => {
    assert.equal(decideWebResearch('cherche des sources sur le sujet').search, true)
    assert.equal(decideWebResearch('donne-moi des liens').search, true)
  })

  test('information datee : la memoire du modele ne suffit pas', () => {
    assert.equal(decideWebResearch('quel est le prix du cuivre en ce moment').search, true)
    assert.equal(decideWebResearch('quelle est la derniere version de Blender').search, true)
  })

  test('une URL dans la demande declenche la lecture', () => {
    assert.equal(decideWebResearch('resume https://example.com/article').search, true)
  })

  test('bavardage et demandes creatives ne sortent pas sur le reseau', () => {
    assert.equal(decideWebResearch('salut ca va').search, false)
    assert.equal(decideWebResearch('ecris-moi un poeme sur la pluie').search, false)
  })

  test('mode auto : question factuelle assez longue', () => {
    assert.equal(decideWebResearch('qui est le maire de Bordeaux').search, true)
    // Trop court pour valoir une sortie reseau.
    assert.equal(decideWebResearch('combien').search, false)
  })
})

describe('runWebResearch', () => {
  const baseRows = [
    { title: 'Article A', url: 'https://a.fr/page', snippet: 'extrait A' },
    { title: 'Article B', url: 'https://b.fr/page', snippet: 'extrait B' },
  ]

  test('sans decision de recherche, aucun appel reseau', async () => {
    let called = 0
    const result = await runWebResearch({
      userInput: 'salut',
      model: 'test',
      mode: 'auto',
      deps: {
        planQueries,
        search: async () => { called += 1; return baseRows },
        extract: async () => '',
        images: async () => [],
        videos: async () => [],
      },
    })
    assert.equal(result.searched, false)
    assert.equal(called, 0, 'le moteur ne doit pas etre appele')
    assert.deepEqual(result.sources, [])
  })

  test('les sources sont numerotees et remontees en direct', async () => {
    const seen: string[] = []
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      wantMedia: false,
      onSource: (source) => seen.push(`${source.domain}:${source.status}`),
      deps: {
        planQueries,
        search: fakeSearch(baseRows),
        extract: async () => 'Contenu complet de la page, bien plus long que le simple extrait du moteur de recherche.',
        images: async () => [],
        videos: async () => [],
      },
    })

    assert.equal(result.searched, true)
    assert.equal(result.sources.length, 2)
    assert.deepEqual(result.sources.map((s) => s.rank), [1, 2])
    assert.deepEqual(result.sources.map((s) => s.domain), ['a.fr', 'b.fr'])
    // Chaque page passe par « trouvee », puis « lecture », puis « lue ».
    assert.ok(seen.includes('a.fr:found'))
    assert.ok(seen.includes('a.fr:reading'))
    assert.ok(seen.includes('a.fr:read'))
    assert.ok(result.sources.every((s) => s.status === 'read'))
  })

  test('une page illisible reste affichee, marquee en echec', async () => {
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      wantMedia: false,
      maxPagesRead: 1,
      deps: {
        planQueries,
        search: fakeSearch(baseRows),
        // Site qui refuse : chaine vide.
        extract: async () => '',
        images: async () => [],
        videos: async () => [],
      },
    })
    assert.equal(result.sources[0].status, 'failed')
    assert.equal(result.sources.length, 2, 'la source en echec n est pas effacee')
    // L extrait du moteur sert encore de contexte, faute de page lue.
    assert.match(result.context, /extrait A/)
  })

  test('les doublons d URL sont ecartes', async () => {
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      wantMedia: false,
      maxPagesRead: 0,
      deps: {
        planQueries: async () => ['q1', 'q2'],
        search: fakeSearch([...baseRows, { title: 'Doublon', url: 'https://a.fr/page#section', snippet: 'x' }]),
        extract: async () => '',
        images: async () => [],
        videos: async () => [],
      },
    })
    // Deux requetes renvoient les memes liens : on garde 2 sources, pas 6.
    assert.equal(result.sources.length, 2)
  })

  test('pont eteint : on le dit, on n invente pas une recherche', async () => {
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      deps: {
        planQueries,
        search: async () => [],
        extract: async () => '',
        images: async () => [],
        videos: async () => [],
      },
    })
    assert.equal(result.searched, false)
    assert.match(result.reason, /pont eteint|rien renvoye/)
    assert.equal(result.context, '')
  })

  test('photos et videos deviennent des sources affichables', async () => {
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      maxPagesRead: 0,
      deps: {
        planQueries,
        search: fakeSearch(baseRows),
        extract: async () => '',
        images: async () => [{
          url: 'https://upload.wikimedia.org/x.jpg',
          thumb: 'https://upload.wikimedia.org/x-thumb.jpg',
          alt: 'Une photo',
          sourcePage: 'https://commons.wikimedia.org/wiki/File:x.jpg',
          license: 'CC BY-SA 3.0',
        }],
        videos: async () => [{ url: 'https://youtu.be/dQw4w9WgXcQ', title: 'Un documentaire' }],
      },
    })
    const image = result.sources.find((s) => s.kind === 'image')
    const video = result.sources.find((s) => s.kind === 'video')
    assert.ok(image, 'photo absente')
    assert.equal(image.license, 'CC BY-SA 3.0')
    assert.equal(image.sourcePage, 'https://commons.wikimedia.org/wiki/File:x.jpg')
    assert.ok(video, 'video absente')
    // Les medias ne sont pas numerotes : on ne cite pas une photo comme une
    // source de texte.
    assert.equal(image.rank, undefined)
  })

  test('l abandon utilisateur arrete la recherche', async () => {
    const controller = new AbortController()
    controller.abort()
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      signal: controller.signal,
      deps: {
        planQueries,
        search: fakeSearch(baseRows),
        extract: async () => 'texte',
        images: async () => [],
        videos: async () => [],
      },
    })
    assert.equal(result.sources.length, 0)
  })
})

describe('buildCitationInstructions', () => {
  test('sans recherche, aucune consigne de citation', () => {
    const empty: WebResearchResult = { searched: false, reason: 'x', queries: [], sources: [], context: '' }
    assert.equal(buildCitationInstructions(empty), '')
  })

  test('la consigne liste les numeros disponibles et interdit les autres', async () => {
    const result = await runWebResearch({
      userInput: 'cherche des sources sur le sujet',
      model: 'test',
      wantMedia: false,
      deps: {
        planQueries,
        search: fakeSearch([{ title: 'Article A', url: 'https://a.fr/page', snippet: 'extrait assez long pour compter' }]),
        extract: async () => '',
        images: async () => [],
        videos: async () => [],
      },
    })
    const instructions = buildCitationInstructions(result)
    assert.match(instructions, /\[1\] a\.fr/)
    assert.match(instructions, /N invente aucune reference/)
    // Le modele doit savoir que le web prime sur sa memoire.
    assert.match(instructions, /priment sur ta memoire/)
  })
})
