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
  isNonDiagnosticFailure,
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

// --- Provisionnement du sandbox (2026-08-10) -------------------------------
// Deuxieme run reel: 7 passes de correction, scores plats (40/25/33/33/33/33/33),
// toutes sur « Quota disque total WS7 indisponible pour le workspace
// conteneurise ». Meme erreur de categorie que `fetch failed` — le juge n a pas
// pu etre CONSTRUIT — mais une signature que le classifieur ne couvrait pas.
describe('pannes de PROVISIONNEMENT du sandbox', () => {
  test('le quota WS7 indisponible est une panne d infrastructure', () => {
    assert.equal(
      isSandboxInfrastructureFailure({
        ok: false,
        summary: 'Quota disque total WS7 indisponible pour le workspace conteneurise.',
        steps: [{ ok: false, output: '' }],
      }),
      true,
    )
  })

  test('isolation podman indisponible aussi', () => {
    assert.equal(isInfrastructureFailureMessage('Isolation sandbox indisponible sur cet hote'), true)
  })

  test('une vraie erreur de build reste un echec de code', () => {
    assert.equal(
      isSandboxInfrastructureFailure({
        ok: false,
        summary: 'Build echoue',
        steps: [{ ok: false, output: 'vite build: Could not resolve ./missing.vue' }],
      }),
      false,
    )
  })
})

// Le diagnostic du sandbox a ete rendu PRECIS (il accusait le quota disque
// alors que la vraie cause etait une image conteneur absente, `--pull=never`
// interdisant le telechargement). Le classifieur doit suivre le nouveau libelle,
// sinon la boucle de correction recommencerait a bruler des passes.
describe('diagnostic sandbox precis', () => {
  test('le nouveau libelle reste classe comme infrastructure', () => {
    assert.equal(
      isSandboxInfrastructureFailure({
        ok: false,
        summary: 'Sandbox WS7 indisponible (init): image conteneur absente en local pour "node".',
        steps: [{ ok: false, output: 'Error: image not known' }],
      }),
      true,
    )
  })

  test('l image absente est reconnue comme cause d environnement', () => {
    assert.equal(isInfrastructureFailureMessage('image conteneur absente en local pour "node"'), true)
  })
})

// ---------------------------------------------------------------------------
// Run 1171 — condamner sur une etape qui n a rien dit.
//
// Derniere etape en echec: « Installer les dependances », sortie de ZERO octet.
// Verifie sur le livrable reel (output/code/audit_v119/): npm install passe sur
// l hote (exit 0, 153 paquets, 5 s) ET sous les memes drapeaux podman (exit 0).
// Le pipeline sortait pourtant `phase: error` — un verdict de QUALITE — sur une
// etape dont il ne restait aucune trace.
// ---------------------------------------------------------------------------
describe('une etape qui echoue sans rien dire n a rien mesure', () => {
  test('sortie vide = validation empechee, pas defaut de code', () => {
    assert.equal(isNonDiagnosticFailure(''), true)
    assert.equal(isNonDiagnosticFailure('   \n '), true)
    assert.equal(isNonDiagnosticFailure(undefined), true)
    assert.equal(isNonDiagnosticFailure('error TS2322: Type X is not assignable'), false)
  })

  test('le cas reel du run 1171 devient `interrupted`, pas `error`', () => {
    const sandbox = {
      ok: false,
      summary: 'Installer les dependances a echoue dans le sandbox.',
      steps: [
        { ok: true, label: 'Isolation sandbox WS7', output: 'ok' },
        { ok: true, label: 'Preuve quota pids', output: 'ok' },
        { ok: false, label: 'Installer les dependances', output: '' },
      ],
    }
    assert.equal(isSandboxInfrastructureFailure(sandbox), true)
  })

  test('une VRAIE erreur de build reste un defaut de code', () => {
    const sandbox = {
      ok: false,
      summary: 'Verifier build a echoue dans le sandbox.',
      steps: [
        { ok: true, label: 'Installer les dependances', output: 'added 153 packages' },
        { ok: false, label: 'Verifier build', output: "src/pages/AdminPage.tsx(20,9): error TS2353: Object literal may only specify known properties" },
      ],
    }
    assert.equal(isSandboxInfrastructureFailure(sandbox), false)
  })

  test('une etape muette a cote d une erreur lisible ne blanchit pas le code', () => {
    const sandbox = {
      ok: false,
      summary: 'echecs multiples',
      steps: [
        { ok: false, label: 'Installer les dependances', output: '' },
        { ok: false, label: 'Verifier build', output: 'error TS2339: Property x does not exist' },
      ],
    }
    assert.equal(isSandboxInfrastructureFailure(sandbox), false)
  })
})
