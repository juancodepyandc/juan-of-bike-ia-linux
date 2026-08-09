// Verrouille la recuperation des charges utiles d actions WS3 abimees.
//
// Regression reelle: deux runs consecutifs sur un brief complexe sont morts sur
// `action_producer_failed:action_protocol_invalid:json_payload_invalid` APRES
// avoir deja ecrit 8 a 14 fichiers. Tout le projet etait perdu a cause d une
// seule reponse modele mal formee.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  repairJsonControlCharacters,
  salvageTruncatedWriteFile,
} from '../services/codeGenerationActionSalvage.ts'
import {
  CODE_GENERATION_ACTION_PROTOCOL_VERSION,
  parseCodeGenerationActions,
} from '../services/codeGenerationActionProtocol.ts'

describe('repairJsonControlCharacters', () => {
  test('re-echappe un vrai saut de ligne dans une chaine (cause dominante)', () => {
    const broken = '{"content":"line1\nline2"}'
    assert.throws(() => JSON.parse(broken))
    const repaired = repairJsonControlCharacters(broken)
    assert.equal(JSON.parse(repaired).content, 'line1\nline2')
  })

  test('re-echappe tabulations et retours chariot', () => {
    const broken = '{"content":"a\tb\rc"}'
    assert.throws(() => JSON.parse(broken))
    assert.equal(JSON.parse(repairJsonControlCharacters(broken)).content, 'a\tb\rc')
  })

  test('ne touche pas une charge deja valide', () => {
    const good = '{"kind":"write_file","path":"a.js","content":"const a = 1;\\nconst b = 2;"}'
    assert.deepEqual(JSON.parse(repairJsonControlCharacters(good)), JSON.parse(good))
  })

  test('preserve l espacement legal hors chaine', () => {
    const good = '{\n  "a": 1,\n  "b": 2\n}'
    assert.deepEqual(JSON.parse(repairJsonControlCharacters(good)), { a: 1, b: 2 })
  })

  test('ne casse pas un guillemet deja echappe', () => {
    const good = '{"content":"il a dit \\"bonjour\\""}'
    assert.equal(JSON.parse(repairJsonControlCharacters(good)).content, 'il a dit "bonjour"')
  })
})

describe('salvageTruncatedWriteFile', () => {
  test('recupere le fichier d une charge jamais refermee', () => {
    const body = 'export function App() {\n  return <main>contenu assez long pour etre credible</main>\n}'
    const truncated = `[{"kind":"write_file","path":"src/App.tsx","language":"tsx","content":"${body.replace(/\n/g, '\\n')}`
    const salvaged = salvageTruncatedWriteFile(truncated)
    assert.ok(salvaged)
    assert.equal(salvaged.path, 'src/App.tsx')
    assert.equal(salvaged.language, 'tsx')
    assert.match(salvaged.content, /export function App/)
    assert.equal(salvaged.truncated, true)
  })

  test('refuse un fragment trop court pour etre un fichier', () => {
    const truncated = '[{"kind":"write_file","path":"a.js","content":"const a'
    assert.equal(salvageTruncatedWriteFile(truncated), null)
  })

  test('refuse une charge sans write_file', () => {
    assert.equal(salvageTruncatedWriteFile('[{"kind":"read_file","path":"a.js"'), null)
  })
})

describe('parseCodeGenerationActions — chemins de recuperation', () => {
  test('un contenu avec de vrais sauts de ligne ne tue plus le run', () => {
    const raw = `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"index.html","language":"html","content":"<!doctype html>\n<html>\n<body>ok</body>\n</html>"}]`
    const parsed = parseCodeGenerationActions(raw)
    assert.equal(parsed.ok, true, `attendu ok, erreurs=${parsed.errors.join(',')}`)
    assert.equal(parsed.actions.length, 1)
    assert.equal(parsed.actions[0].path, 'index.html')
    assert.match(parsed.actions[0].content ?? '', /<!doctype html>/)
  })

  test('une charge tronquee livre le fichier partiel au lieu de tout perdre', () => {
    const body = 'body { margin: 0; padding: 0; font-family: Inter, sans-serif; background: #0a0a0c; }'
    const raw = `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"styles.css","language":"css","content":"${body}`
    const parsed = parseCodeGenerationActions(raw)
    assert.equal(parsed.ok, true, `attendu ok, erreurs=${parsed.errors.join(',')}`)
    assert.equal(parsed.actions[0].path, 'styles.css')
    assert.match(parsed.actions[0].content ?? '', /font-family/)
  })

  test('une charge valide reste parsee a l identique', () => {
    const raw = `${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\n[{"kind":"write_file","path":"a.js","content":"const a = 1;"}]`
    const parsed = parseCodeGenerationActions(raw)
    assert.equal(parsed.ok, true)
    assert.equal(parsed.actions[0].content, 'const a = 1;')
  })

  test('une charge vraiment inexploitable echoue toujours', () => {
    const parsed = parseCodeGenerationActions(`${CODE_GENERATION_ACTION_PROTOCOL_VERSION}\nceci n est pas du JSON`)
    assert.equal(parsed.ok, false)
  })
})
