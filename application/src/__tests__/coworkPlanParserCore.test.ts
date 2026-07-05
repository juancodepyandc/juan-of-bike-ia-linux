/**
 * Tests pour services/coworkPlanParser — JSON parser + validation actions +
 * postProcessing du plan.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  parsePlan,
  extractJsonObject,
  validateAction,
  ensureFinishAction,
  stripFinishIfReadOnlyPlan,
  postProcessPlan,
  pickConnectorHintForHost,
} from '../services/coworkPlanParser.ts'
import type { CoworkPlan } from '../services/coworkTypes.ts'

describe('extractJsonObject', () => {
  test('JSON nu → renvoyé tel quel', () => {
    const r = extractJsonObject('{"a":1}')
    assert.equal(r, '{"a":1}')
  })

  test('JSON dans fence ```json → extrait', () => {
    const r = extractJsonObject('```json\n{"a":1}\n```')
    assert.equal(r, '{"a":1}')
  })

  test('JSON dans fence ``` simple → extrait', () => {
    const r = extractJsonObject('```\n{"a":1}\n```')
    assert.equal(r, '{"a":1}')
  })

  test('JSON entouré de texte → tronqué entre { et }', () => {
    const r = extractJsonObject('Voici le plan : {"a":1} et voilà.')
    assert.equal(r, '{"a":1}')
  })

  test('texte sans { → null', () => {
    assert.equal(extractJsonObject('pas de json ici'), null)
  })

  test('chaîne vide → null', () => {
    assert.equal(extractJsonObject(''), null)
  })
})

describe('validateAction', () => {
  test('reply valide', () => {
    const r = validateAction({ kind: 'reply', message: 'salut' })
    assert.equal(r.ok, true)
    if (r.ok) assert.equal(r.action.kind, 'reply')
  })

  test('reply sans message → erreur', () => {
    const r = validateAction({ kind: 'reply' })
    assert.equal(r.ok, false)
  })

  test('finish valide', () => {
    const r = validateAction({ kind: 'finish', summary: 'fin' })
    assert.equal(r.ok, true)
  })

  test('write_file valide', () => {
    const r = validateAction({ kind: 'write_file', path: 'a.txt', content: 'hi' })
    assert.equal(r.ok, true)
  })

  test('write_file sans content → erreur', () => {
    const r = validateAction({ kind: 'write_file', path: 'a.txt' })
    assert.equal(r.ok, false)
  })

  test('edit_file valide avec oldText/newText', () => {
    const r = validateAction({ kind: 'edit_file', path: 'a.ts', oldText: 'old', newText: 'new' })
    assert.equal(r.ok, true)
  })

  test('edit_file sans oldText → erreur', () => {
    const r = validateAction({ kind: 'edit_file', path: 'a.ts', newText: 'new' })
    assert.equal(r.ok, false)
  })

  test('shell valide avec args', () => {
    const r = validateAction({ kind: 'shell', command: 'ls', args: ['-la'] })
    assert.equal(r.ok, true)
  })

  test('shell args manquants → tableau vide accepté', () => {
    const r = validateAction({ kind: 'shell', command: 'ls' })
    assert.equal(r.ok, true)
    if (r.ok && r.action.kind === 'shell') {
      assert.deepEqual(r.action.args, [])
    }
  })

  test('list_dir avec depth optionnel', () => {
    const r = validateAction({ kind: 'list_dir', path: '/tmp', depth: 2 })
    assert.equal(r.ok, true)
  })

  test('kind manquant → erreur', () => {
    const r = validateAction({ message: 'hi' })
    assert.equal(r.ok, false)
  })

  test('null → erreur', () => {
    const r = validateAction(null)
    assert.equal(r.ok, false)
  })

  test('array → erreur', () => {
    const r = validateAction([])
    assert.equal(r.ok, false)
  })
})

describe('parsePlan', () => {
  test('plan complet valide', () => {
    const raw = JSON.stringify({
      reasoning: 'mon plan',
      expectedOutcome: 'tester',
      actions: [{ kind: 'reply', message: 'salut' }],
    })
    const r = parsePlan(raw)
    assert.equal(r.ok, true)
    if (r.ok) {
      assert.equal(r.plan.reasoning, 'mon plan')
      assert.equal(r.plan.actions.length, 1)
    }
  })

  test('réponse vide → erreur', () => {
    const r = parsePlan('')
    assert.equal(r.ok, false)
  })

  test('JSON invalide → erreur', () => {
    const r = parsePlan('{ "actions": [')
    assert.equal(r.ok, false)
  })

  test('reasoning manquant → erreur', () => {
    const raw = JSON.stringify({ expectedOutcome: 'x', actions: [{ kind: 'reply', message: 'hi' }] })
    const r = parsePlan(raw)
    assert.equal(r.ok, false)
  })

  test('actions vides → erreur', () => {
    const raw = JSON.stringify({ reasoning: 'x', expectedOutcome: 'y', actions: [] })
    const r = parsePlan(raw)
    assert.equal(r.ok, false)
  })

  test('action invalide → erreur avec indexn', () => {
    const raw = JSON.stringify({
      reasoning: 'x', expectedOutcome: 'y',
      actions: [{ kind: 'reply', message: 'ok' }, { kind: 'foo' }],
    })
    const r = parsePlan(raw)
    assert.equal(r.ok, false)
    if (!r.ok) assert.ok(r.error.includes('[1]'))
  })

  test('JSON dans fence ```json → parsé', () => {
    const raw = '```json\n' + JSON.stringify({
      reasoning: 'r', expectedOutcome: 'o',
      actions: [{ kind: 'finish', summary: 'done' }],
    }) + '\n```'
    const r = parsePlan(raw)
    assert.equal(r.ok, true)
  })
})

function plan(actions: CoworkPlan['actions']): CoworkPlan {
  return { reasoning: 'r', expectedOutcome: 'o', actions }
}

describe('ensureFinishAction', () => {
  test('plan sans finish → finish ajouté', () => {
    const p = plan([{ kind: 'reply', message: 'hi' }])
    const r = ensureFinishAction(p)
    assert.equal(r.actions[r.actions.length - 1].kind, 'finish')
  })

  test('plan avec finish → inchangé', () => {
    const p = plan([{ kind: 'reply', message: 'hi' }, { kind: 'finish', summary: 'done' }])
    const r = ensureFinishAction(p)
    assert.equal(r.actions.length, 2)
  })

  test('plan vide → inchangé', () => {
    const p = plan([])
    const r = ensureFinishAction(p)
    assert.equal(r.actions.length, 0)
  })

  test('finish summary = expectedOutcome par défaut', () => {
    const p = plan([{ kind: 'reply', message: 'hi' }])
    const r = ensureFinishAction(p)
    const last = r.actions[r.actions.length - 1]
    if (last.kind === 'finish') assert.equal(last.summary, 'o')
  })
})

describe('stripFinishIfReadOnlyPlan', () => {
  test('plan read-only + finish → finish strippé', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = stripFinishIfReadOnlyPlan(p)
    assert.equal(r.actions.length, 1)
    assert.equal(r.actions[0].kind, 'read_file')
  })

  test('plan avec reply → finish conservé', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'reply', message: 'synthese' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = stripFinishIfReadOnlyPlan(p)
    assert.equal(r.actions.length, 3)
  })

  test('plan write_file + finish → finish conservé (write n est pas read-only)', () => {
    const p = plan([
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = stripFinishIfReadOnlyPlan(p)
    assert.equal(r.actions.length, 2)
  })

  test('plan trop court → inchangé', () => {
    const p = plan([{ kind: 'finish', summary: 'done' }])
    const r = stripFinishIfReadOnlyPlan(p)
    assert.equal(r.actions.length, 1)
  })
})

describe('postProcessPlan', () => {
  test('plan read-only sans reply → finish strippé', () => {
    const p = plan([
      { kind: 'read_file', path: 'a.ts' },
      { kind: 'finish', summary: 'done' },
    ])
    const r = postProcessPlan(p)
    assert.equal(r.actions.length, 1)
  })

  test('plan write + reply mais sans finish → finish ajouté', () => {
    const p = plan([
      { kind: 'write_file', path: 'a.ts', content: 'x' },
      { kind: 'reply', message: 'fait' },
    ])
    const r = postProcessPlan(p)
    assert.equal(r.actions[r.actions.length - 1].kind, 'finish')
  })
})

describe('pickConnectorHintForHost', () => {
  test('linkedin.com → label LinkedIn', () => {
    const r = pickConnectorHintForHost('https://www.linkedin.com/feed')
    assert.equal(r?.label, 'LinkedIn')
    assert.equal(r?.connectorId, null)
  })

  test('reddit.com → connectorId reddit', () => {
    const r = pickConnectorHintForHost('https://reddit.com/r/dev')
    assert.equal(r?.connectorId, 'reddit')
  })

  test('github.com → connectorId github', () => {
    const r = pickConnectorHintForHost('https://github.com/user/repo')
    assert.equal(r?.connectorId, 'github')
  })

  test('x.com → label Twitter/X', () => {
    const r = pickConnectorHintForHost('https://x.com/elon')
    assert.equal(r?.label, 'Twitter/X')
  })

  test('sous-domaine → match suffix', () => {
    const r = pickConnectorHintForHost('https://m.facebook.com/feed')
    assert.equal(r?.label, 'Facebook')
  })

  test('hostname inconnu → null', () => {
    assert.equal(pickConnectorHintForHost('https://random-site.com'), null)
  })

  test('URL malformée → null', () => {
    assert.equal(pickConnectorHintForHost('pas une url'), null)
  })

  test('null/undefined → null', () => {
    assert.equal(pickConnectorHintForHost(null), null)
    assert.equal(pickConnectorHintForHost(undefined), null)
  })

  test('youtube.com → connectorId youtube', () => {
    const r = pickConnectorHintForHost('https://www.youtube.com/watch?v=x')
    assert.equal(r?.connectorId, 'youtube')
  })

  test('news.ycombinator.com → hackernews', () => {
    const r = pickConnectorHintForHost('https://news.ycombinator.com/')
    assert.equal(r?.connectorId, 'hackernews')
  })
})
