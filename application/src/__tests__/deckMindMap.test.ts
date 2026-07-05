/**
 * Tests pour services/deckMindMap — flashcard deck → mind map tree.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDeckMindMap,
  describeDeckMindMap,
  evaluateMindMapQuality,
} from '../services/deckMindMap.ts'
import type { Flashcard, FlashcardDeck } from '../stores/flashcardsStore.ts'

function mkDeck(overrides: Partial<FlashcardDeck> = {}): FlashcardDeck {
  return {
    id: 'd1',
    subject: 'Test Subject',
    theme: 'Test Theme',
    level: 'intermediaire',
    createdAt: 0,
    updatedAt: 0,
    cardCount: 0,
    masteredCount: 0,
    ...overrides,
  }
}

function mkCard(overrides: Partial<Flashcard> = {}): Flashcard {
  return {
    id: 'c1',
    deckId: 'd1',
    kind: 'revision',
    front: 'Card front',
    back: 'Card back',
    tags: ['general'],
    box: 1,
    streak: 0,
    dueAt: 0,
    timesCorrect: 0,
    timesWrong: 0,
    createdAt: 0,
    ...overrides,
  }
}

describe('buildDeckMindMap', () => {
  test('deck vide → root sans enfants', () => {
    const m = buildDeckMindMap(mkDeck(), [])
    assert.equal(m.kind, 'subject')
    assert.equal(m.label, 'Test Subject')
    assert.equal(m.children?.length, 0)
  })

  test('1 carte → root + 1 thème + 1 carte', () => {
    const m = buildDeckMindMap(
      mkDeck({ subject: 'Maths' }),
      [mkCard({ tags: ['Algèbre'], front: 'Théorème de Pythagore' })],
    )
    assert.equal(m.kind, 'subject')
    assert.equal(m.children?.length, 1)
    const theme = m.children![0]
    assert.equal(theme.kind, 'theme')
    assert.equal(theme.label, 'Algèbre')
    assert.equal(theme.children?.length, 1)
    const card = theme.children![0]
    assert.equal(card.kind, 'card')
    assert.match(card.label, /Pythagore/)
  })

  test('groupement par tag primaire (le plus dense en tête)', () => {
    const cards: Flashcard[] = [
      mkCard({ id: 'a', tags: ['Histoire'] }),
      mkCard({ id: 'b', tags: ['Géo'] }),
      mkCard({ id: 'c', tags: ['Histoire'] }),
      mkCard({ id: 'd', tags: ['Histoire'] }),
    ]
    const m = buildDeckMindMap(mkDeck(), cards)
    // 3 Histoire + 1 Géo → Histoire en tête
    assert.equal(m.children?.[0].label, 'Histoire')
    assert.equal(m.children?.[0].children?.length, 3)
    assert.equal(m.children?.[1].label, 'Géo')
  })

  test('keyPoints exposés en grandchildren (max 3)', () => {
    const m = buildDeckMindMap(
      mkDeck(),
      [
        mkCard({
          tags: ['T'],
          front: 'F',
          keyPoints: [
            { label: 'P1' },
            { label: 'P2' },
            { label: 'P3' },
            { label: 'P4' },
            { label: 'P5' },
          ] as unknown as Flashcard['keyPoints'],
        }),
      ],
    )
    const card = m.children![0].children![0]
    assert.equal(card.children?.length, 3)
    assert.equal(card.children![0].kind, 'point')
  })

  test('cap 12 cartes par thème', () => {
    const cards = Array.from({ length: 20 }, (_, i) =>
      mkCard({ id: `c-${i}`, tags: ['Theme'], front: `Card ${i}` }),
    )
    const m = buildDeckMindMap(mkDeck(), cards)
    assert.equal(m.children?.[0].children?.length, 12)
  })

  test('tag manquant → fallback "General"', () => {
    const m = buildDeckMindMap(
      mkDeck(),
      [mkCard({ tags: [] })],
    )
    assert.equal(m.children?.[0].label, 'General')
  })

  test('label tronqué si trop long', () => {
    const longTitle = 'x'.repeat(80)
    const m = buildDeckMindMap(
      mkDeck(),
      [mkCard({ tags: ['T'], front: longTitle })],
    )
    const card = m.children![0].children![0]
    assert.ok(card.label.length <= 30)
    assert.ok(card.label.endsWith('…'))
  })
})

describe('describeDeckMindMap', () => {
  test('compte themes/cards/points', () => {
    const m = buildDeckMindMap(
      mkDeck(),
      [
        mkCard({ tags: ['A'], keyPoints: [{ label: 'p1' }, { label: 'p2' }] as unknown as Flashcard['keyPoints'] }),
        mkCard({ id: 'c2', tags: ['B'] }),
      ],
    )
    const stats = describeDeckMindMap(m)
    assert.equal(stats.themes, 2)
    assert.equal(stats.cards, 2)
    assert.equal(stats.points, 2)
  })

  test('mind map vide → tout à 0', () => {
    const m = buildDeckMindMap(mkDeck(), [])
    const stats = describeDeckMindMap(m)
    assert.equal(stats.themes, 0)
    assert.equal(stats.cards, 0)
    assert.equal(stats.points, 0)
  })
})

describe('evaluateMindMapQuality', () => {
  test('renvoie un rapport structuré', () => {
    const cards = [mkCard({ tags: ['X'] })]
    const m = buildDeckMindMap(mkDeck(), cards)
    const r = evaluateMindMapQuality(m, cards)
    assert.ok(typeof r === 'object')
  })
})
