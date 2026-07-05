/**
 * Tests batchés : utils/textFileExtract + utils/exportAnki (helpers purs).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatBytes,
  validateImageFile,
  readTextFile,
  MAX_TEXT_FILE_SIZE,
  MAX_IMAGE_FILE_SIZE,
} from '../utils/textFileExtract.ts'
import {
  exportAnkiTsv,
  buildStandaloneDeckHtml,
} from '../utils/exportAnki.ts'

describe('formatBytes', () => {
  test('< 1 KB → bytes', () => {
    assert.equal(formatBytes(500), '500 B')
  })

  test('< 1 MB → KB', () => {
    assert.equal(formatBytes(2048), '2 KB')
  })

  test('≥ 1 MB → MB', () => {
    assert.equal(formatBytes(5 * 1024 * 1024), '5.0 MB')
  })

  test('0 → "0 B"', () => {
    assert.equal(formatBytes(0), '0 B')
  })

  test('valeurs limites', () => {
    assert.equal(formatBytes(1023), '1023 B')
    assert.equal(formatBytes(1024), '1 KB')
    assert.equal(formatBytes(1024 * 1024), '1.0 MB')
  })
})

describe('validateImageFile', () => {
  test('image dans la limite → null', () => {
    const file = { name: 'img.png', size: 5 * 1024 * 1024 } as File
    assert.equal(validateImageFile(file), null)
  })

  test('image dépassant limite → message d erreur', () => {
    const file = { name: 'huge.png', size: 50 * 1024 * 1024 } as File
    const r = validateImageFile(file)
    assert.ok(r?.includes('trop volumineuse'))
    assert.ok(r?.includes('huge.png'))
  })

  test('limite exact = MAX_IMAGE_FILE_SIZE → OK', () => {
    const file = { name: 'edge.png', size: MAX_IMAGE_FILE_SIZE } as File
    assert.equal(validateImageFile(file), null)
  })
})

describe('readTextFile — types simples', () => {
  test('.txt → file.text()', async () => {
    const file = {
      name: 'note.txt',
      size: 100,
      type: 'text/plain',
      text: async () => 'Bonjour le monde',
    } as unknown as File
    const r = await readTextFile(file)
    assert.equal(r, 'Bonjour le monde')
  })

  test('.md → text() direct', async () => {
    const file = {
      name: 'doc.md',
      size: 50,
      type: 'text/markdown',
      text: async () => '# Titre',
    } as unknown as File
    const r = await readTextFile(file)
    assert.equal(r, '# Titre')
  })

  test('.markdown → text()', async () => {
    const file = {
      name: 'doc.markdown',
      size: 50,
      type: '',
      text: async () => 'contenu',
    } as unknown as File
    const r = await readTextFile(file)
    assert.equal(r, 'contenu')
  })

  test('content-type text/* → text()', async () => {
    const file = {
      name: 'note.unknown',
      size: 30,
      type: 'text/csv',
      text: async () => 'a,b,c',
    } as unknown as File
    const r = await readTextFile(file)
    assert.equal(r, 'a,b,c')
  })
})

describe('readTextFile — fichiers non supportés', () => {
  test('.doc → message non supporté', async () => {
    const file = { name: 'old.doc', size: 100, type: '' } as unknown as File
    const r = await readTextFile(file)
    assert.ok(r.includes('non supporté'))
    assert.ok(r.includes('.doc'))
  })

  test('.rtf → message non supporté', async () => {
    const file = { name: 'doc.rtf', size: 100, type: '' } as unknown as File
    const r = await readTextFile(file)
    assert.ok(r.includes('non supporté'))
  })

  test('.odt → message non supporté', async () => {
    const file = { name: 'libre.odt', size: 100, type: '' } as unknown as File
    const r = await readTextFile(file)
    assert.ok(r.includes('non supporté'))
  })
})

describe('readTextFile — taille', () => {
  test('fichier > 50 MB → message trop volumineux', async () => {
    const file = { name: 'huge.txt', size: 100 * 1024 * 1024, type: 'text/plain' } as unknown as File
    const r = await readTextFile(file)
    assert.ok(r.includes('trop volumineux'))
    assert.ok(r.includes('huge.txt'))
  })

  test('fichier exactement à la limite → OK', async () => {
    const file = {
      name: 'edge.txt',
      size: MAX_TEXT_FILE_SIZE,
      type: 'text/plain',
      text: async () => 'OK',
    } as unknown as File
    const r = await readTextFile(file)
    assert.equal(r, 'OK')
  })
})

describe('exportAnkiTsv', () => {
  const deck = {
    id: 'd1',
    subject: 'Maths',
    theme: 'Dérivées',
    description: 'desc',
    createdAt: 0,
    cards: [],
  } as any
  const cards = [
    { id: 'c1', kind: 'qa', front: 'Q1?', back: 'A1', tags: ['math', 'analyse'] },
    { id: 'c2', kind: 'qa', front: 'Q2?', back: 'A2', tags: [] },
  ] as any

  test('header Anki contient #deck + #notetype', () => {
    const tsv = exportAnkiTsv(deck, cards)
    assert.ok(tsv.includes('#separator:tab'))
    assert.ok(tsv.includes('#deck:Maths - Dérivées'))
    assert.ok(tsv.includes('#notetype:Basic'))
  })

  test('chaque card → ligne tabulée Front\\tBack\\tTags', () => {
    const tsv = exportAnkiTsv(deck, cards)
    const lines = tsv.split('\n').filter((l) => !l.startsWith('#'))
    assert.equal(lines.length, 2)
    assert.ok(lines[0].includes('Q1?'))
    assert.ok(lines[0].includes('\tA1\t'))
    assert.ok(lines[0].includes('math analyse'))
  })

  test('tags avec espaces → underscores', () => {
    const cardsWithSpaceTags = [
      { id: 'c3', kind: 'qa', front: 'Q', back: 'A', tags: ['tag avec espace'] },
    ] as any
    const tsv = exportAnkiTsv(deck, cardsWithSpaceTags)
    assert.ok(tsv.includes('tag_avec_espace'))
  })

  test('cards vide → seulement headers', () => {
    const tsv = exportAnkiTsv(deck, [])
    const lines = tsv.split('\n')
    assert.ok(lines.every((l) => l.startsWith('#')))
  })

  test('revision cards : newlines dans deepDive escapés → <br>', () => {
    const c = [{
      id: 'c', kind: 'revision', front: 'F', back: 'B',
      summary: 'L1\nL2',  // summary passe par escapeTsv
      tags: [],
    }] as any
    const tsv = exportAnkiTsv(deck, c)
    assert.ok(tsv.includes('<br>'))
  })
})

describe('buildStandaloneDeckHtml', () => {
  const deck = {
    id: 'd', subject: 'Hist', theme: 'WW2', description: 'la guerre',
    createdAt: 0, cards: [],
  } as any
  const cards = [
    { id: 'c1', kind: 'qa', front: 'Quand?', back: '1939-1945', tags: [] },
  ] as any

  test('renvoie HTML valide doctype', () => {
    const html = buildStandaloneDeckHtml(deck, cards)
    assert.ok(html.startsWith('<!doctype html>'))
    assert.ok(html.includes('<title>'))
  })

  test('titre = subject — theme', () => {
    const html = buildStandaloneDeckHtml(deck, cards)
    assert.ok(html.includes('Hist — WW2'))
  })

  test('cards rendues avec front + back', () => {
    const html = buildStandaloneDeckHtml(deck, cards)
    assert.ok(html.includes('Quand?'))
    assert.ok(html.includes('1939-1945'))
  })

  test('compteur cartes', () => {
    const html = buildStandaloneDeckHtml(deck, cards)
    assert.ok(html.includes('1 cartes'))
  })

  test('details/summary pour révéler', () => {
    const html = buildStandaloneDeckHtml(deck, cards)
    assert.ok(html.includes('<details>'))
    assert.ok(html.includes('Révéler la réponse'))
  })
})

describe('Anki TSV — revision cards', () => {
  test('revision card avec deepDive/whyItMatters → tout présent dans back', () => {
    const deck = { id: 'd', subject: 'Bio', theme: 'Mitose', description: '', createdAt: 0, cards: [] } as any
    const cards = [{
      id: 'c1', kind: 'revision', front: 'Mitose', back: 'résumé',
      deepDive: 'explication', whyItMatters: 'importance',
      keyPoints: [{ label: 'pt1', detail: 'd1' }],
      formula: 'F=ma',
      mnemonic: 'mémo',
      example: 'ex',
      quote: 'citation',
      quoteAuthor: 'auteur',
      tags: ['svt'],
    }] as any
    const tsv = exportAnkiTsv(deck, cards)
    assert.ok(tsv.includes('explication'))
    assert.ok(tsv.includes('importance'))
    assert.ok(tsv.includes('pt1'))
    assert.ok(tsv.includes('F=ma'))
    assert.ok(tsv.includes('mémo') || tsv.includes('m&eacute;mo'))
    assert.ok(tsv.includes('citation'))
  })
})
