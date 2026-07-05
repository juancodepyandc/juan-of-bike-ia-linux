/**
 * Unit tests for inferTitle utility.
 * Run: node --experimental-strip-types src/__tests__/titleInference.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { inferTitle, capitalize } from '../utils/titleInference.ts'

describe('capitalize', () => {
  test('capitalizes first letter', () => {
    assert.equal(capitalize('hello world'), 'Hello world')
  })

  test('handles empty string', () => {
    assert.equal(capitalize(''), '')
  })

  test('trims whitespace', () => {
    assert.equal(capitalize('  hello  '), 'Hello')
  })

  test('preserves already capitalized', () => {
    assert.equal(capitalize('Python'), 'Python')
  })
})

describe('inferTitle — empty/blank input', () => {
  test('returns default for empty string', () => {
    assert.equal(inferTitle(''), 'Nouvelle conversation')
  })

  test('returns default for whitespace only', () => {
    assert.equal(inferTitle('   '), 'Nouvelle conversation')
  })
})

describe('inferTitle — app creation pattern', () => {
  test('cree une application X → X capitalized', () => {
    const result = inferTitle('crée une application de gestion de stock')
    assert.equal(result, 'De gestion de stock')
  })

  test('fais un script python', () => {
    const result = inferTitle('fais un script python pour parser des CSV')
    assert.equal(result, 'Python pour parser des CSV')
  })

  test('génère une app mobile', () => {
    const result = inferTitle('génère une app mobile de suivi fitness')
    assert.equal(result, 'Mobile de suivi fitness')
  })

  test('développe un site e-commerce', () => {
    const result = inferTitle('développe un site e-commerce pour vêtements')
    assert.equal(result, 'E-commerce pour vêtements')
  })
})

describe('inferTitle — image/media pattern', () => {
  test('image de X → X', () => {
    const result = inferTitle('génère une image de chat siamois')
    assert.equal(result, 'Chat siamois')
  })

  test('photo du chien', () => {
    const result = inferTitle('photo du golden retriever')
    assert.equal(result, 'Golden retriever')
  })

  test('portrait de la reine', () => {
    const result = inferTitle('portrait de la reine elizabéth')
    assert.equal(result, 'Reine elizabéth')
  })
})

describe('inferTitle — article pattern', () => {
  test('un X at start', () => {
    const result = inferTitle('un résumé du chapitre 3')
    assert.equal(result, 'Résumé du chapitre 3')
  })

  test('une X at start', () => {
    const result = inferTitle('une liste de courses pour la semaine')
    assert.equal(result, 'Liste de courses pour la semaine')
  })
})

describe('inferTitle — generic fallback', () => {
  test('short phrase → capitalised as-is', () => {
    const result = inferTitle('bonjour comment ca va')
    assert.equal(result, 'Bonjour comment ca va')
  })

  test('stops at comma', () => {
    const result = inferTitle('récapitulatif des ventes, données brutes')
    assert.equal(result, 'Récapitulatif des ventes')
  })

  test('stops at period', () => {
    const result = inferTitle('analyse du marché. Données Q1.')
    assert.equal(result, 'Analyse du marché')
  })

  test('truncates at 50 chars with ellipsis', () => {
    const long = 'ceci est une phrase tres longue qui depasse largement cinquante caracteres'
    const result = inferTitle(long)
    assert.ok(result.endsWith('...'), `Expected ellipsis, got: ${result}`)
    assert.ok(result.length <= 53, `Too long: ${result.length} chars`)
  })
})
