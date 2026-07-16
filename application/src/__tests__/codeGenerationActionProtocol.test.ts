import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CODE_GENERATION_ACTION_PROTOCOL_VERSION,
  buildCodeGenerationActionInstructions,
  parseCodeGenerationActions,
} from '../services/codeGenerationActionProtocol.ts'
import type { CodeGenerationQueueItem } from '../services/codeGenerationQueue.ts'

function item(): CodeGenerationQueueItem {
  return {
    path: 'src/App.tsx',
    order: 1,
    required: true,
    role: 'application shell',
    language: 'tsx',
    imports: ['./main'],
    exports: ['App'],
    notes: ['UI complete'],
  }
}

describe('codeGenerationActionProtocol', () => {
  test('parse un tableau strict marque AURORA_CODE_ACTIONS/1', () => {
    const result = parseCodeGenerationActions([
      CODE_GENERATION_ACTION_PROTOCOL_VERSION,
      '[',
      '{"kind":"read_file","path":"src/App.tsx"},',
      '{"kind":"write_file","path":"src/App.tsx","language":"tsx","content":"export function App(){}"},',
      '{"kind":"apply_patch","path":"src/App.tsx","search":"App","replace":"Root","all":true},',
      '{"kind":"run_command","command":"npm run build","reason":"validation"}',
      ']',
    ].join('\n'))

    assert.equal(result.ok, true)
    assert.deepEqual(result.actions.map((action) => action.kind), [
      'read_file',
      'write_file',
      'apply_patch',
      'run_command',
    ])
    assert.equal(result.actions[1].kind === 'write_file' && result.actions[1].language, 'tsx')
  })

  test('accepte un objet actions et retire think/fences', () => {
    const result = parseCodeGenerationActions([
      '<think>raisonnement interne</think>',
      '```json',
      CODE_GENERATION_ACTION_PROTOCOL_VERSION,
      '{"actions":[{"kind":"write_file","path":"README.md","content":"ok"}]}',
      '```',
    ].join('\n'))

    assert.equal(result.ok, true)
    assert.equal(result.actions.length, 1)
    assert.equal(result.actions[0].kind, 'write_file')
  })

  test('rejette les sorties sans marqueur ou JSON invalide', () => {
    const missing = parseCodeGenerationActions('[{"kind":"write_file","path":"x","content":"y"}]')
    const invalid = parseCodeGenerationActions(`${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{]`)

    assert.equal(missing.ok, false)
    assert.deepEqual(missing.errors, ['protocol_marker_missing'])
    assert.equal(invalid.ok, false)
    assert.deepEqual(invalid.errors, ['json_payload_invalid'])
  })

  test('retourne les actions valides avec erreurs pour les entrees invalides', () => {
    const result = parseCodeGenerationActions([
      CODE_GENERATION_ACTION_PROTOCOL_VERSION,
      '{"actions":[',
      '{"kind":"write_file","path":"ok.ts","content":"export const ok = true"},',
      '{"kind":"write_file","path":"bad.ts"},',
      '{"kind":"unknown","path":"x"}',
      ']}',
    ].join('\n'))

    assert.equal(result.ok, false)
    assert.equal(result.actions.length, 1)
    assert.deepEqual(result.errors, ['action_1_content_missing', 'action_2_kind_invalid'])
  })

  test('expose les instructions specialisees pour un item de queue', () => {
    const instructions = buildCodeGenerationActionInstructions(item())

    assert.match(instructions, /AURORA_CODE_ACTIONS\/1/)
    assert.match(instructions, /src\/App\.tsx/)
    assert.match(instructions, /write_file/)
    assert.match(instructions, /Imports prevus: \.\/main/)
    assert.match(instructions, /Required: true/)
  })
})
