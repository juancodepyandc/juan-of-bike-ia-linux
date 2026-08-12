// Une panne d infrastructure ne detruit pas le travail deja produit.
//
// Run 1041: 32 fichiers ecrits, puis « Ollama: toutes les tentatives epuisees
// (3) [...] Derniere erreur: fetch failed » (machine a 0 octet de RAM libre).
// Le gestionnaire fatal renvoyait `files: []`. Tout perdu.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { buildInterruptedDelivery, buildInterruptedResult } from '../services/codeInterruptedDelivery.ts'
import { createFileStateCapture } from '../services/codeFileStateCapture.ts'
import { TRANSPORT_BACKOFF_MS, isTransportFailure } from '../services/codeTransportBackoff.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const FATAL_1041 = 'Ollama: toutes les tentatives epuisees (3). Modeles testes: qwen3-coder:30b, qwen3-coder:30b, qwen3-coder:30b. Derniere erreur: fetch failed'
const FILES = [{ name: 'src/App.tsx', language: 'typescript', content: 'export const App = () => null' }]

describe('travail interrompu — le message du run 1041', () => {
  test('est reconnu comme une panne d infrastructure', () => {
    const delivery = buildInterruptedDelivery(FATAL_1041, FILES, 'notes precedentes')
    assert.equal(delivery.infrastructure, true)
    assert.match(delivery.cause, /infrastructure/)
  })

  test('les notes disent que ce n est PAS un verdict de qualite', () => {
    const delivery = buildInterruptedDelivery(FATAL_1041, FILES, 'notes precedentes')
    assert.match(delivery.notes, /aucune conclusion sur sa qualite/)
    assert.match(delivery.notes, /notes precedentes/)
  })

  test('une vraie erreur de pipeline reste distinguee d une panne reseau', () => {
    const delivery = buildInterruptedDelivery('TypeError: undefined is not a function', FILES, '')
    assert.equal(delivery.infrastructure, false)
    assert.match(delivery.cause, /erreur du pipeline/)
  })

  test('le resultat porte la phase « interrupted », ni done ni error', () => {
    const delivery = buildInterruptedDelivery(FATAL_1041, FILES, '')
    const result = buildInterruptedResult(delivery, FILES, { projectType: 'spa_react' } as unknown as CodeIntent, [])
    assert.equal(result.phase, 'interrupted')
    assert.equal(result.files.length, 1)
    // Une interruption ne doit pas se faire passer pour une reussite notee.
    assert.equal(result.finalScore, 0)
    assert.equal(result.sandboxResult, null)
  })
})

describe('capture d etat — un lot vide n efface jamais le travail', () => {
  test('conserve le dernier lot non vide', () => {
    const seen: number[] = []
    const capture = createFileStateCapture([], (files) => seen.push(files.length))
    capture.capture(FILES, 'premier jet')
    capture.capture([], 'lot vide')
    assert.equal(capture.snapshot().files.length, 1)
    assert.equal(capture.snapshot().notes, 'premier jet')
    // Le callback d origine reste appele pour TOUS les lots: on preserve l etat
    // sans masquer d evenement a l interface.
    assert.deepEqual(seen, [1, 0])
  })

  test('part des fichiers existants quand la generation est une reprise', () => {
    const capture = createFileStateCapture(FILES, () => {})
    assert.equal(capture.snapshot().files.length, 1)
  })
})

describe('resilience Ollama — attendre un service qui revient', () => {
  test('le message du run 1041 est classe « transport »', () => {
    assert.equal(isTransportFailure(FATAL_1041), true)
    assert.equal(isTransportFailure('ECONNREFUSED'), true)
    // Un refus du modele n est PAS un probleme de transport: on ne doit pas
    // s acharner des dizaines de secondes sur une erreur qui se repetera.
    assert.equal(isTransportFailure('model requires more system memory'), false)
    assert.equal(isTransportFailure('invalid prompt'), false)
  })

  test('l attente cumulee couvre un rechargement de modele', () => {
    // L ancien bareme totalisait ~7 s; sous pression memoire un rechargement
    // prend des dizaines de secondes — c est ainsi qu on a perdu 32 fichiers.
    const total = TRANSPORT_BACKOFF_MS.reduce((a, b) => a + b, 0)
    assert.ok(total >= 60_000, `attente cumulee trop courte: ${total} ms`)
    assert.ok(TRANSPORT_BACKOFF_MS.length >= 5)
  })
})
