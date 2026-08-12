import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildStructuredEmissionInstructions,
  isStructuredProjectEmission,
  parseProjectTreeEmission,
  serializeProjectTreeEmission,
  STRUCTURED_PROJECT_EMISSION_HEADER,
} from '../services/codeProjectEmission.ts'
import { parseCodeFiles, parseCodeFilesWithReport } from '../services/codeGeneratedFileParser.ts'
import { extractGeneratedFiles } from '../services/codeOutputFiles.ts'
import { detectProtocolLeakMarker, salvageProtocolLeaks } from '../services/codeProtocolLeakGuard.ts'

// Forme EXACTE emise par qwen3-coder au run 1061: la ligne de version encadree,
// les en-tetes de fichier NUS, les marqueurs de fin encadres. 15 534 octets
// livres tels quels dans un fichier « main.js », et neuf passes de correction
// brulees sur une erreur de syntaxe qui n existait pas.
const RUN_1061_SHAPE = [
  '<<<AURORA_CODE_VFS/1>>>',
  'AURORA_FILE {"path":"src/App.tsx","length":123,"encoding":"utf8","language":"tsx"}',
  "import React from 'react'",
  '',
  'export default function App() {',
  '  return <main>Brulerie Nomade</main>',
  '}',
  '<<<AURORA_END>>>',
  'AURORA_FILE {"path":"src/styles/global.css","length":123,"encoding":"utf8","language":"css"}',
  ':root { --olive: #6b705c; }',
  '<<<AURORA_END>>>',
  '',
].join('\n')

describe('protocole VFS — le parseur lit ce que le modele ecrit', () => {
  test('en-tetes de fichier NUS: le conteneur du run 1061 se deballe en vrais fichiers', () => {
    assert.equal(isStructuredProjectEmission(RUN_1061_SHAPE), true)
    const files = parseCodeFiles(RUN_1061_SHAPE)
    assert.deepEqual(files.map((f) => f.name), ['src/App.tsx', 'src/styles/global.css'])
    assert.match(files[0].content, /export default function App/)
    assert.equal(files[1].content.trim(), ':root { --olive: #6b705c; }')
    // Le defaut historique: UN fichier « main.js » contenant tout le protocole.
    assert.equal(files.some((f) => f.name === 'main.js'), false)
  })

  test('la longueur declaree fausse (recopiee de l exemple) ne perd aucun fichier', () => {
    const { issues } = parseCodeFilesWithReport(RUN_1061_SHAPE)
    assert.equal(issues.every((i) => i.type === 'recovered_length_mismatch'), true)
  })

  test('forme encadree et marqueur de fin nu restent lisibles', () => {
    const stream = [
      STRUCTURED_PROJECT_EMISSION_HEADER,
      '<<<AURORA_FILE {"path":"a.ts","length":11,"encoding":"utf8"}>>>',
      'const a = 1',
      'AURORA_END',
      'AURORA_FILE {"path":"b.ts","length":11,"encoding":"utf8"}',
      'const b = 2',
      '<<<AURORA_END>>>',
      '',
    ].join('\n')
    const parsed = parseProjectTreeEmission(stream)
    assert.deepEqual(parsed.tree.files.map((f) => f.path), ['a.ts', 'b.ts'])
    assert.equal(parsed.tree.files[0].content, 'const a = 1')
    assert.equal(parsed.tree.files[1].content, 'const b = 2')
    assert.deepEqual(parsed.issues, [])
  })

  test('round-trip serialise/parse inchange, en-tete encadre compris', () => {
    const emitted = serializeProjectTreeEmission([
      { path: 'src/index.ts', content: 'export const x = 1\n' },
      { path: 'README.md', content: '# titre\n' },
    ])
    assert.ok(emitted.startsWith(STRUCTURED_PROJECT_EMISSION_HEADER))
    assert.ok(emitted.includes('AURORA_CODE_VFS/1'))
    const parsed = parseProjectTreeEmission(emitted)
    assert.deepEqual(parsed.issues, [])
    const byPath = new Map(parsed.tree.files.map((f) => [f.path, f.content]))
    assert.equal(byPath.get('src/index.ts'), 'export const x = 1\n')
    assert.equal(byPath.get('README.md'), '# titre\n')
  })

  test('un `AURORA_FILE {` cite en MILIEU de ligne ne coupe pas un fichier', () => {
    const body = 'const doc = "voir AURORA_FILE {path} dans la doc"\nexport {}'
    const emitted = serializeProjectTreeEmission([{ path: 'src/doc.ts', content: body }])
    const parsed = parseProjectTreeEmission(emitted)
    assert.equal(parsed.tree.files.length, 1)
    assert.equal(parsed.tree.files[0].content, body)
  })

  test('la consigne decrit les trois marqueurs sous la MEME forme', () => {
    const instructions = buildStructuredEmissionInstructions()
    assert.ok(instructions.includes(STRUCTURED_PROJECT_EMISSION_HEADER))
    assert.ok(instructions.includes('<<<AURORA_FILE '))
    assert.ok(instructions.includes('<<<AURORA_END>>>'))
    // L asymetrie d origine: une ligne de version NUE a cote de marqueurs
    // encadres. C est elle que le modele a « corrigee » a sa facon.
    assert.equal(/Commence par AURORA_CODE_VFS\/1/.test(instructions), false)
  })
})

describe('garde de fuite de protocole — un conteneur ne sort jamais deguise en fichier', () => {
  test('detecte les marqueurs de tete, ignore les citations internes', () => {
    assert.equal(detectProtocolLeakMarker(RUN_1061_SHAPE), '<<<AURORA_CODE_VFS/1>>>')
    assert.equal(detectProtocolLeakMarker('AURORA_FILE {"path":"a.ts"}\nx'), 'AURORA_FILE {')
    assert.equal(detectProtocolLeakMarker('const m = "<<<AURORA_END>>>"\n'), null)
    assert.equal(detectProtocolLeakMarker('export const x = 1'), null)
  })

  test('un conteneur deguise en main.js est deballe, jamais livre tel quel', () => {
    const { files, leaks } = salvageProtocolLeaks([
      { name: 'main.js', language: 'javascript', content: RUN_1061_SHAPE },
      { name: 'package.json', language: 'json', content: '{"name":"x"}' },
    ])
    assert.equal(files.some((f) => f.name === 'main.js'), false)
    assert.deepEqual(
      files.map((f) => f.name).sort(),
      ['package.json', 'src/App.tsx', 'src/styles/global.css'],
    )
    assert.equal(leaks.length, 1)
    assert.equal(leaks[0].disposition, 'unpacked')
    assert.deepEqual(leaks[0].recovered, ['src/App.tsx', 'src/styles/global.css'])
  })

  test('un conteneur indeballable est ECARTE, pas livre comme du code', () => {
    const broken = '<<<AURORA_CODE_VFS/1>>>\ntexte libre sans aucun en-tete de fichier\n'
    const { files, leaks } = salvageProtocolLeaks([
      { name: 'main.js', language: 'javascript', content: broken },
      { name: 'index.html', language: 'markup', content: '<!DOCTYPE html><html></html>' },
    ])
    assert.deepEqual(files.map((f) => f.name), ['index.html'])
    assert.equal(leaks[0].disposition, 'dropped')
  })

  test('un fichier qui CITE un marqueur en son sein reste intact', () => {
    const cited = 'const marker = "<<<AURORA_END>>>"\nexport { marker }'
    const { files, leaks } = salvageProtocolLeaks([{ name: 'src/m.ts', language: 'typescript', content: cited }])
    assert.deepEqual(leaks, [])
    assert.equal(files[0].content, cited)
  })

  test('aucun parseur public ne rend un fichier commencant par un marqueur', () => {
    for (const files of [
      parseCodeFiles(RUN_1061_SHAPE),
      extractGeneratedFiles(RUN_1061_SHAPE).map((f) => ({ name: f.path, content: f.content })),
    ]) {
      assert.ok(files.length >= 2)
      for (const file of files) assert.equal(detectProtocolLeakMarker(file.content), null)
    }
  })
})
