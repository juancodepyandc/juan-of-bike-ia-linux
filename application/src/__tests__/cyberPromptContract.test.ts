/**
 * Verrouille le contrat prompt du module Cyber : utile et direct dans le
 * sandbox, mais jamais ambigu sur une cible réelle non autorisée.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const hookSource = readFileSync(new URL('../hooks/useCyberViewLogic.ts', import.meta.url), 'utf8')

describe('Cyber prompt contract', () => {
  test('reste client-first et sandboxé', () => {
    assert.match(hookSource, /client-first/)
    assert.match(hookSource, /bac-à-sable PÉDAGOGIQUE LOCAL/)
    assert.match(hookSource, /cible réelle non explicitement autorisée/)
    assert.match(hookSource, /lab simulé ou en guide défensif/)
  })

  test('ne réintroduit pas le wording ambigu "sans filtre"', () => {
    assert.doesNotMatch(hookSource, /sans filtre/i)
  })
})
