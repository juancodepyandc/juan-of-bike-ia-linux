// Verrouille la distinction « le code est casse » / « le juge est injoignable ».
//
// Mesure sur un run reel de 55 minutes (167 evenements, chronometre depuis les
// horodatages NDJSON): 8 passes de correction, TOUTES a score 0, TOUTES sur la
// meme erreur `fetch failed` — la validation sandbox passe par le bridge, et le
// bridge etait arrete. ~17 minutes brulees a demander au modele de corriger du
// code a cause d une panne d infrastructure, et le lint a REGRESSE de 95 % a
// 80 % pendant l operation.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildInfrastructureFailureNote,
  handleSandboxInfrastructureFailure,
  isInfrastructureFailureMessage,
  isSandboxInfrastructureFailure,
} from '../services/codeInfrastructureFailure.ts'

describe('isInfrastructureFailureMessage', () => {
  test('reconnait les pannes reseau/bridge observees', () => {
    for (const m of [
      'fetch failed',
      'connect ECONNREFUSED 127.0.0.1:3001',
      'socket hang up',
      'Failed to fetch',
      'bridge injoignable',
    ]) {
      assert.equal(isInfrastructureFailureMessage(m), true, m)
    }
  })

  test('ne confond PAS un vrai defaut de code avec une panne d infrastructure', () => {
    for (const m of [
      "SyntaxError: Unexpected token '}'",
      'error TS2339: Property x does not exist',
      'Test failed: expected 5 received -1',
      'ReferenceError: foo is not defined',
      'npm ERR! missing script: build',
    ]) {
      assert.equal(isInfrastructureFailureMessage(m), false, m)
    }
  })

  test('tolere null/vide', () => {
    assert.equal(isInfrastructureFailureMessage(null), false)
    assert.equal(isInfrastructureFailureMessage(''), false)
  })
})

describe('isSandboxInfrastructureFailure', () => {
  test('detecte le cas reel: summary "Validation sandbox interrompue: fetch failed"', () => {
    assert.equal(isSandboxInfrastructureFailure({
      ok: false,
      summary: 'Validation sandbox interrompue: fetch failed',
      steps: [{ ok: false, output: 'fetch failed' }],
    }), true)
  })

  test('un sandbox VERT n est jamais une panne d infrastructure', () => {
    assert.equal(isSandboxInfrastructureFailure({ ok: true, summary: 'ok', steps: [] }), false)
  })

  test('un echec de compilation reste un echec de CODE (la boucle doit tourner)', () => {
    assert.equal(isSandboxInfrastructureFailure({
      ok: false,
      summary: 'Compilation echouee',
      steps: [{ ok: false, output: "SyntaxError: Unexpected token '}'" }],
    }), false)
  })

  test('un echec mixte reste un echec de code: une seule etape reseau ne suffit pas', () => {
    assert.equal(isSandboxInfrastructureFailure({
      ok: false,
      summary: 'Echec',
      steps: [{ ok: false, output: 'fetch failed' }, { ok: false, output: 'SyntaxError: bad' }],
    }), false)
  })
})

describe('handleSandboxInfrastructureFailure', () => {
  test('sur panne: previent, joint la note, et rend les notes enrichies', () => {
    let validated = false
    let filesNotes: string | null = null
    let phase: string | null = null
    const out = handleSandboxInfrastructureFailure({
      result: { ok: false, summary: 'Validation sandbox interrompue: fetch failed', steps: [{ ok: false, output: 'fetch failed' }] },
      files: [{ name: 'index.html' }],
      notes: 'notes de base',
      score: 0,
      onValidationUpdate: () => { validated = true },
      onFilesUpdate: (_f, n) => { filesNotes = n },
      setPhase: (d) => { phase = d },
    })
    assert.ok(out)
    assert.equal(validated, true)
    assert.match(out.notes, /VALIDATION INDISPONIBLE/)
    assert.match(out.notes, /notes de base/)
    assert.equal(filesNotes, out.notes)
    assert.match(String(phase), /infrastructure/i)
  })

  test('sur echec de code: retourne null, la boucle de correction continue', () => {
    const out = handleSandboxInfrastructureFailure({
      result: { ok: false, summary: 'Compilation echouee', steps: [{ ok: false, output: 'SyntaxError' }] },
      files: [],
      notes: '',
      score: 0,
      onValidationUpdate: () => assert.fail('ne doit pas notifier'),
      onFilesUpdate: () => assert.fail('ne doit pas modifier'),
      setPhase: () => assert.fail('ne doit pas changer la phase'),
    })
    assert.equal(out, null)
  })
})

describe('buildInfrastructureFailureNote', () => {
  test('dit explicitement que ce n est pas un defaut du code', () => {
    const note = buildInfrastructureFailureNote('fetch failed')
    assert.match(note, /PAS un defaut du code/)
    assert.match(note, /fetch failed/)
  })
})
