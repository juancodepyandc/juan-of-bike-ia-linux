/**
 * Unit tests for detectSubjectKind utility.
 * Run: node --experimental-strip-types src/__tests__/subjectDetection.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { detectSubjectKind, SUBJECT_HINTS } from '../utils/subjectDetection.ts'

describe('detectSubjectKind — philosophy', () => {
  test('philo keyword', () => {
    assert.equal(detectSubjectKind('philo'), 'philo')
  })

  test('kant', () => {
    assert.equal(detectSubjectKind('kant et la morale'), 'philo')
  })

  test('existentialisme', () => {
    assert.equal(detectSubjectKind('sartre existentialisme'), 'philo')
  })

  test('dissertation theme', () => {
    assert.equal(detectSubjectKind('dissertation sur la liberté'), 'philo')
  })
})

describe('detectSubjectKind — histoire', () => {
  test('napoleon', () => {
    assert.equal(detectSubjectKind('napoleon et l empire'), 'histoire')
  })

  test('revolution', () => {
    assert.equal(detectSubjectKind('la revolution francaise 1789'), 'histoire')
  })

  test('moyen age', () => {
    assert.equal(detectSubjectKind('chevaliers du moyen age'), 'histoire')
  })
})

describe('detectSubjectKind — maths', () => {
  test('maths keyword', () => {
    assert.equal(detectSubjectKind('maths'), 'maths')
  })

  test('equation', () => {
    assert.equal(detectSubjectKind('resoudre une equation du second degre'), 'maths')
  })

  test('trigonometrie', () => {
    assert.equal(detectSubjectKind('trigo', 'sin cos tan'), 'maths')
  })

  test('pythagore', () => {
    assert.equal(detectSubjectKind('theoreme de pythagore'), 'maths')
  })

  test('integrale', () => {
    assert.equal(detectSubjectKind('calcul integrale'), 'maths')
  })
})

describe('detectSubjectKind — informatique', () => {
  test('python', () => {
    assert.equal(detectSubjectKind('python'), 'informatique')
  })

  test('algorithme', () => {
    assert.equal(detectSubjectKind('algorithme de tri'), 'informatique')
  })

  test('javascript', () => {
    assert.equal(detectSubjectKind('javascript', 'async await'), 'informatique')
  })

  test('docker', () => {
    assert.equal(detectSubjectKind('docker et kubernetes'), 'informatique')
  })
})

describe('detectSubjectKind — science', () => {
  test('physique', () => {
    assert.equal(detectSubjectKind('physique quantique'), 'science')
  })

  test('biologie', () => {
    assert.equal(detectSubjectKind('biologie cellulaire'), 'science')
  })

  test('adn', () => {
    assert.equal(detectSubjectKind('structure de l adn'), 'science')
  })
})

describe('detectSubjectKind — general fallback', () => {
  test('unrecognized topic → general', () => {
    assert.equal(detectSubjectKind('recettes de cuisine'), 'general')
  })

  test('empty string → general', () => {
    assert.equal(detectSubjectKind(''), 'general')
  })
})

describe('detectSubjectKind — accent tolerance', () => {
  test('détection with accents works', () => {
    // "économie" should still match via stripAccents
    assert.equal(detectSubjectKind('économie et marchés financiers'), 'economie')
  })

  test('géographie accent', () => {
    assert.equal(detectSubjectKind('géographie des territoires'), 'geo')
  })
})

describe('SUBJECT_HINTS', () => {
  test('has an entry for every SubjectKind', () => {
    const kinds = ['philo', 'histoire', 'geo', 'maths', 'science', 'langue', 'litterature', 'informatique', 'economie', 'art', 'general']
    for (const kind of kinds) {
      assert.ok(SUBJECT_HINTS[kind as keyof typeof SUBJECT_HINTS], `Missing hint for ${kind}`)
    }
  })
})
