// Verrouille la tolerance de `apply_patch` aux blancs.
//
// Panne reelle: apres 36 fichiers emis et 46 minutes de run, le pipeline meurt
// sur `agentic_retry_failed:patch_search_not_found`. `apply_patch` exigeait une
// sous-chaine EXACTE, or le modele reconstitue le bloc a chercher de memoire:
// une indentation de 2 au lieu de 4 espaces, une tabulation convertie ou un
// espace en fin de ligne suffisaient a le faire echouer alors que le texte
// etait bien present.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { applyPatchToContent, findPatchTarget } from '../services/codePatchMatching.ts'

const FILE = [
  'function greet(name) {',
  '    const message = `Bonjour ${name}`;',
  '    console.log(message);',
  '}',
].join('\n')

describe('findPatchTarget', () => {
  test('trouve une correspondance exacte', () => {
    const m = findPatchTarget(FILE, '    console.log(message);')
    assert.ok(m)
    assert.equal(m.strategy, 'exact')
  })

  test('trouve malgre une SUR-indentation, impossible en correspondance stricte', () => {
    // 8 espaces la ou le fichier en a 4: aucune sous-chaine exacte possible.
    const search = '        console.log(message);'
    assert.equal(FILE.includes(search), false, 'le cas doit bien etre inexact')
    const m = findPatchTarget(FILE, search)
    assert.ok(m, 'une sur-indentation doit rester trouvable')
    assert.equal(m.strategy, 'whitespace_insensitive')
  })

  test('trouve malgre une tabulation a la place des espaces', () => {
    assert.ok(findPatchTarget(FILE, '\tconsole.log(message);'))
  })

  test('trouve malgre un espace de fin de ligne', () => {
    assert.ok(findPatchTarget(FILE, '    console.log(message);   '))
  })

  test('trouve un bloc multi-lignes mal re-indente', () => {
    const search = 'const message = `Bonjour ${name}`;\nconsole.log(message);'
    assert.ok(findPatchTarget(FILE, search))
  })

  test('ne trouve PAS un texte reellement absent', () => {
    assert.equal(findPatchTarget(FILE, 'console.error(oops);'), null)
  })

  test('ne confond pas deux identifiants proches', () => {
    assert.equal(findPatchTarget(FILE, 'console.log(messages);'), null)
  })
})

describe('applyPatchToContent', () => {
  test('remplace en preservant le reste du fichier a l identique', () => {
    const r = applyPatchToContent(FILE, '  console.log(message);', '    return message;')
    assert.equal(r.ok, true)
    assert.match(r.content, /return message;/)
    assert.match(r.content, /function greet\(name\) \{/, 'le reste du fichier doit etre intact')
    assert.doesNotMatch(r.content, /console\.log/)
  })

  test('conserve le comportement `all` sur correspondance stricte', () => {
    const src = 'a; a; a;'
    const r = applyPatchToContent(src, 'a;', 'b;', true)
    assert.equal(r.content, 'b; b; b;')
  })

  test('echoue proprement quand la cible est absente', () => {
    const r = applyPatchToContent(FILE, 'introuvable', 'x')
    assert.equal(r.ok, false)
    assert.equal(r.content, FILE, 'le fichier ne doit pas etre modifie')
  })

  test('une correspondance exacte reste prioritaire', () => {
    const r = applyPatchToContent(FILE, '    console.log(message);', 'X')
    assert.equal(r.strategy, 'exact')
  })
})
