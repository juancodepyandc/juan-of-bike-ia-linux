import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildStructuredEmissionInstructions,
  isStructuredProjectEmission,
  parseProjectTreeEmission,
  serializeProjectTreeEmission,
} from '../services/codeProjectEmission.ts'

describe('codeProjectEmission — round-trip robuste', () => {
  test('preserve backticks imbriques, YAML/SQL --- et marqueurs internes', () => {
    const trickyTs = [
      'const markdown = `',
      '```ts',
      'console.log("nested fence")',
      '```',
      '`',
      'const marker = "<<<AURORA_END>>>"',
      'export { markdown, marker }',
    ].join('\n')
    const trickyYaml = [
      '---',
      'name: aurora',
      'steps:',
      '  - run: echo "--- not a separator"',
      '---',
    ].join('\n')
    const trickySql = [
      'CREATE TABLE notes (body text);',
      "INSERT INTO notes VALUES ('---');",
      "INSERT INTO notes VALUES ('```sql');",
    ].join('\n')

    const emitted = serializeProjectTreeEmission([
      { path: 'src/index.ts', content: trickyTs },
      { path: 'config/app.yaml', content: trickyYaml },
      { path: 'db/schema.sql', content: trickySql },
    ])
    const result = parseProjectTreeEmission(emitted)

    assert.equal(result.issues.length, 0)
    assert.equal(isStructuredProjectEmission(emitted), true)
    assert.equal(result.tree.files.find((file) => file.path === 'src/index.ts')?.content, trickyTs)
    assert.equal(result.tree.files.find((file) => file.path === 'config/app.yaml')?.content, trickyYaml)
    assert.equal(result.tree.files.find((file) => file.path === 'db/schema.sql')?.content, trickySql)
  })

  test('preserve les binaires base64 et les dossiers multi-niveaux', () => {
    const emitted = serializeProjectTreeEmission([
      { path: 'assets/models/ship.glb', content: 'Z2xiLWJpbmFyeQ==', encoding: 'base64', mime: 'model/gltf-binary' },
      { path: 'src/components/Ship.tsx', content: 'export function Ship(){ return null }' },
    ])
    const result = parseProjectTreeEmission(emitted)

    assert.equal(result.issues.length, 0)
    assert.deepEqual(result.tree.directories.map((dir) => dir.path), [
      'assets',
      'assets/models',
      'src',
      'src/components',
    ])
    assert.equal(result.tree.files.find((file) => file.path.endsWith('.glb'))?.encoding, 'base64')
    assert.equal(result.tree.files.find((file) => file.path.endsWith('.glb'))?.mime, 'model/gltf-binary')
  })

  test('deduplique les collisions apres parsing du protocole brut', () => {
    const first = 'one'
    const second = 'two'
    const raw = [
      'AURORA_CODE_VFS/1',
      `<<<AURORA_FILE {"path":"src/App.tsx","length":${first.length},"encoding":"utf8"}>>>`,
      first,
      '<<<AURORA_END>>>',
      `<<<AURORA_FILE {"path":"src/App.tsx","length":${second.length},"encoding":"utf8"}>>>`,
      second,
      '<<<AURORA_END>>>',
    ].join('\n')
    const result = parseProjectTreeEmission(`${raw}\n`)

    assert.equal(result.issues.length, 0)
    assert.deepEqual(result.tree.files.map((file) => file.path), ['src/App.tsx', 'src/App__2.tsx'])
    assert.equal(result.tree.collisions[0].reason, 'duplicate')
  })
})

describe('codeProjectEmission — erreurs detectees', () => {
  test('rejette une longueur declaree incoherente sans avaler le fichier suivant', () => {
    const valid = serializeProjectTreeEmission([{ path: 'ok.ts', content: 'export const ok = true' }])
    const broken = [
      'AURORA_CODE_VFS/1',
      '<<<AURORA_FILE {"path":"broken.ts","length":2,"encoding":"utf8"}>>>',
      'abcdef',
      '<<<AURORA_END>>>',
      valid,
    ].join('\n')
    const result = parseProjectTreeEmission(broken)

    assert.equal(result.issues.some((issue) => issue.type === 'missing_end_marker'), true)
    assert.equal(result.tree.files.some((file) => file.path === 'broken.ts'), false)
    assert.equal(result.tree.files.some((file) => file.path === 'ok.ts'), true)
  })

  test('expose les instructions du contrat a longueur declaree', () => {
    const instructions = buildStructuredEmissionInstructions()

    assert.ok(instructions.includes('length'))
    assert.ok(instructions.includes('base64'))
    assert.ok(instructions.includes('N utilise pas de fences markdown'))
  })
})
