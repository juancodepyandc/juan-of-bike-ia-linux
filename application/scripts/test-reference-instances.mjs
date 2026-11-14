#!/usr/bin/env node
// Référence 3D : une image de référence montre le sujet au repos, une fois par objet demandé.
// Demande réelle du 13/11/2026 — « coffre avec une animation d'ouverture » — pour laquelle la
// recherche avait retenu une planche de six coffres à six stades d'ouverture.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { canUseVisualReference } from '../src/services/referenceVisualResearch.ts'
import { buildReferenceQueries } from '../src/services/threeDReferenceSupport.ts'

const SOUND = { usable: true, score: 90, pixelated: false, cluttered: false, exactEnough: true, notes: '' }
const INTENT = {
  researchQueries: ['treasure chest opening animation reference'],
  purpose: 'object', subjectKind: 'object', requiresDimensionalPrecision: false, systemClass: 'generic',
}

test('a sheet or a sequence of stages is never a reference, whatever its score', () => {
  assert.equal(canUseVisualReference(SOUND, 70), true)
  assert.equal(canUseVisualReference({ ...SOUND, isSheetOrSequence: true }, 70), false)
  assert.equal(canUseVisualReference({ ...SOUND, isSheetOrSequence: true, score: 100 }, 0, true, 6), false)
})

test('more instances than the request expects are refused; the expected number is accepted', () => {
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: 6 }, 70, false, 1), false)
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: 2 }, 70, false, 1), false)
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: 2 }, 70, false, 2), true)   // une paire demandée
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: 1 }, 70, false, 1), true)
  // un appelant qui ne connaît pas le nombre attendu ne refuse pas sur le seul compte
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: 2 }, 70), true)
  // un compte illisible ne vaut pas refus à lui seul
  assert.equal(canUseVisualReference({ ...SOUND, instanceCount: Number.NaN }, 70, false, 1), true)
})

test('the earlier acceptance rules still hold', () => {
  assert.equal(canUseVisualReference(null, 70), false)
  assert.equal(canUseVisualReference(null, 70, true), true)
  assert.equal(canUseVisualReference({ ...SOUND, wrongSubject: true }, 70, false, 1), false)
  assert.equal(canUseVisualReference({ ...SOUND, score: 40 }, 70, false, 1), false)
})

test('when the request describes a movement, image searches describe only the subject at rest', () => {
  const profile = {
    subjectLabel: 'coffre', restStateSubject: 'closed wooden chest', motionClause: "animation d'ouverture",
    appearanceQueries: ['closed wooden treasure chest isolated', 'wooden chest product photo white background'],
    expectedInstances: 1, requiredElements: [], forbiddenElements: [], preferIsolatedSubject: false,
    allowAdditionalSubjects: false, strictIdentity: false,
  }
  const queries = buildReferenceQueries("coffre avec une animation d'ouverture", INTENT, ['chest opening animation'], ['open the lid'], profile)
  assert.equal(queries[0], 'closed wooden chest')
  assert.ok(queries.includes('closed wooden treasure chest isolated'))
  for (const query of queries) {
    assert.doesNotMatch(query, /animation|opening|ouverture|open the lid/i, query)
  }
})

test('without a movement the request-derived searches are kept', () => {
  const profile = {
    subjectLabel: 'vase en forme de coeur', restStateSubject: 'heart-shaped vase', motionClause: '',
    appearanceQueries: [], expectedInstances: 1, requiredElements: [], forbiddenElements: [],
    preferIsolatedSubject: false, allowAdditionalSubjects: false, strictIdentity: false,
  }
  const queries = buildReferenceQueries('vase en forme de coeur', { ...INTENT, researchQueries: ['heart shaped ceramic vase'] }, ['vase coeur céramique'], [], profile)
  assert.ok(queries.includes('heart shaped ceramic vase'))
  assert.ok(queries.includes('vase coeur céramique'))
})
