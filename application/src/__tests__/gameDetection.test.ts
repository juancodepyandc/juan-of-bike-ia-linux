/**
 * Unit tests for game detection utilities.
 * Run: node --experimental-strip-types src/__tests__/gameDetection.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { detectKnownGame, classifyGameKind, containsSignal, KNOWN_GAMES } from '../utils/gameDetection.ts'

describe('containsSignal', () => {
  test('exact match', () => {
    assert.ok(containsSignal('snake game', 'snake'))
  })

  test('word boundary respected — partial match rejected', () => {
    // "snakepit" should NOT match "snake" token since it's not on a word boundary
    assert.ok(!containsSignal('snakepit', 'snake'))
  })

  test('multi-word signal', () => {
    assert.ok(containsSignal('je veux un jeu de pong', 'jeu de pong'))
  })

  test('case insensitive', () => {
    assert.ok(containsSignal('SNAKE', 'snake'))
  })

  test('empty signal returns false', () => {
    assert.ok(!containsSignal('snake', ''))
  })
})

describe('detectKnownGame — positive matches', () => {
  test('snake', () => {
    const result = detectKnownGame('je veux faire un jeu snake')
    assert.ok(result, 'Should detect snake')
    assert.equal(result!.canonical, 'Snake')
  })

  test('tetris', () => {
    const result = detectKnownGame('crée un jeu de tetris')
    assert.ok(result)
    assert.equal(result!.canonical, 'Tetris')
  })

  test('flappy bird', () => {
    const result = detectKnownGame('flappy bird clone')
    assert.ok(result)
    assert.equal(result!.canonical, 'Flappy Bird')
  })

  test('pong', () => {
    const result = detectKnownGame('un jeu de pong classique')
    assert.ok(result)
    assert.equal(result!.canonical, 'Pong')
  })

  test('casse-briques', () => {
    const result = detectKnownGame('fais un casse-briques')
    assert.ok(result)
    assert.equal(result!.canonical, 'Breakout / Arkanoid')
  })

  test('pacman', () => {
    const result = detectKnownGame('jeu pacman avec labyrinthe')
    assert.ok(result)
    assert.equal(result!.canonical, 'Pac-Man')
  })

  test('space invaders', () => {
    const result = detectKnownGame('space invaders retro')
    assert.ok(result)
    assert.equal(result!.canonical, 'Space Invaders')
  })

  test('2048', () => {
    const result = detectKnownGame('jeu 2048 fusion de cases')
    assert.ok(result)
    assert.equal(result!.canonical, '2048')
  })

  test('demineur', () => {
    const result = detectKnownGame('crée un demineur')
    assert.ok(result)
    assert.equal(result!.canonical, 'Minesweeper / Demineur')
  })

  test('endless runner / dino', () => {
    const result = detectKnownGame('un dino endless runner')
    assert.ok(result)
    assert.equal(result!.canonical, 'Chrome Dino / Endless Runner')
  })

  test('tower defense', () => {
    const result = detectKnownGame('tower defense avec vagues')
    assert.ok(result)
    assert.equal(result!.canonical, 'Tower Defense')
  })

  test('platformer', () => {
    const result = detectKnownGame('jeu de plateforme mario like')
    assert.ok(result)
    assert.equal(result!.canonical, 'Platformer 2D')
  })
})

describe('detectKnownGame — negative matches', () => {
  test('unknown game → null', () => {
    assert.equal(detectKnownGame('un jeu de strategie spatiale'), null)
  })

  test('empty string → null', () => {
    assert.equal(detectKnownGame(''), null)
  })

  test('vague game request → null', () => {
    assert.equal(detectKnownGame('crée un jeu'), null)
  })
})

describe('classifyGameKind', () => {
  test('known game → clone', () => {
    const { gameKind, knownGame } = classifyGameKind('jeu snake', true)
    assert.equal(gameKind, 'clone')
    assert.ok(knownGame)
    assert.equal(knownGame!.canonical, 'Snake')
  })

  test('creative keyword → creative', () => {
    const { gameKind } = classifyGameKind('un jeu original de ma propre invention', true)
    assert.equal(gameKind, 'creative')
  })

  test('long description → creative', () => {
    // More than 12 words without a known token = creative
    const longDesc = 'un jeu ou le joueur explore un monde souterrain en collectant des cristaux magiques'
    const { gameKind } = classifyGameKind(longDesc, true)
    assert.equal(gameKind, 'creative')
  })

  test('short vague request → generic', () => {
    const { gameKind } = classifyGameKind('un jeu', true)
    assert.equal(gameKind, 'generic')
  })

  test('not a game request → generic', () => {
    const { gameKind } = classifyGameKind('snake', false)
    assert.equal(gameKind, 'generic')
  })
})

describe('KNOWN_GAMES completeness', () => {
  test('all entries have required fields', () => {
    for (const game of KNOWN_GAMES) {
      assert.ok(game.canonical, `Missing canonical in ${JSON.stringify(game)}`)
      assert.ok(Array.isArray(game.tokens) && game.tokens.length > 0, `No tokens for ${game.canonical}`)
      assert.ok(game.genre, `Missing genre for ${game.canonical}`)
      assert.ok(game.controls, `Missing controls for ${game.canonical}`)
      assert.ok(game.winLoseCondition, `Missing win/lose for ${game.canonical}`)
    }
  })

  test('13 known games defined', () => {
    assert.equal(KNOWN_GAMES.length, 13)
  })
})
