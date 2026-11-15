#!/usr/bin/env node
// Animation ON : la référence montre le sujet AU REPOS. Run du 15/11/2026 : « Zig la hyène qui
// court » arrivait dans la ligne d'identité sous la forme « Zig the hyena running dynamically »,
// et FLUX dessinait Zig en pleine course malgré toutes les consignes de repos. Vraies sources.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { previewThreeDIntent, restReferenceAdditions, restStateRulesEn } from '../src/services/threeDIntent.ts'

const FULL = 'Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin qui nage'
const REST = 'Zig la hyène et Sharko le requin, version réaliste'
const ACTION = /running|qui court|qui nage|dynamic|sprint|stride/i

test('the identity handed to the reference paths is rebuilt from the subject at rest', () => {
  const intent = previewThreeDIntent(FULL)
  const before = intent.referencePromptAdditions.join('\n')
  const after = restReferenceAdditions(intent, REST).join('\n')
  assert.match(before, ACTION, 'the whole sentence carries the action into the identity')
  assert.doesNotMatch(after, ACTION)
  assert.match(after, /Visual description:/, 'the known characters keep their identity description')
})

test('the rest rules name the movement and, for a body, the rigging rest pose', () => {
  const body = restStateRulesEn({ sujet: REST, mouvement: 'Zig court et Sharko nage', corpsArticule: true }).join(' ')
  assert.match(body, /Zig court et Sharko nage/)
  assert.match(body, /REST POSE FOR RIGGING/)
  const chest = restStateRulesEn({ sujet: 'un coffre fermé', mouvement: "s'ouvre", corpsArticule: false }).join(' ')
  assert.doesNotMatch(chest, /REST POSE FOR RIGGING/)
})
