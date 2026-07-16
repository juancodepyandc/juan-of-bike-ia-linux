import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  decodeBase64ToBytes,
  encodeBytesToBase64,
  joinProjectRoot,
  roundTripProjectTreeOnFs,
  writeCodeFilesToDirectory,
  type CodeProjectFs,
} from '../services/codeProjectWriter.ts'
import { parseProjectTreeEmission, serializeProjectTreeEmission } from '../services/codeProjectEmission.ts'

function createMemoryFs(): CodeProjectFs & {
  dirs: Set<string>
  text: Map<string, string>
  binary: Map<string, number[]>
} {
  const dirs = new Set<string>()
  const text = new Map<string, string>()
  const binary = new Map<string, number[]>()

  return {
    dirs,
    text,
    binary,
    async mkdir(path: string) {
      dirs.add(path)
    },
    async writeText(path: string, content: string) {
      text.set(path, content)
    },
    async writeBinary(path: string, bytes: number[]) {
      binary.set(path, bytes)
    },
    async readText(path: string) {
      const content = text.get(path)
      if (content == null) throw new Error(`missing text ${path}`)
      return content
    },
    async readBinary(path: string) {
      const content = binary.get(path)
      if (content == null) throw new Error(`missing binary ${path}`)
      return content
    },
  }
}

describe('codeProjectWriter — round-trip filesystem', () => {
  test('parse -> write -> read preserve textes pieges et arborescence', async () => {
    const content = [
      '---',
      'const fence = "```"',
      'const marker = "<<<AURORA_END>>>"',
      'export { fence, marker }',
    ].join('\n')
    const parsed = parseProjectTreeEmission(serializeProjectTreeEmission([
      { path: 'src/deep/App.ts', content, language: 'typescript' },
      { path: 'Dockerfile', content: 'FROM node:22-alpine' },
    ]))
    const fs = createMemoryFs()
    const result = await roundTripProjectTreeOnFs(parsed.tree, '/tmp/aurora project', fs)

    assert.equal(result.writeResult.files.length, 2)
    assert.equal(fs.dirs.has('/tmp/aurora project/src'), true)
    assert.equal(fs.dirs.has('/tmp/aurora project/src/deep'), true)
    assert.equal(result.readTree.files.find((file) => file.path === 'src/deep/App.ts')?.content, content)
    assert.equal(result.readTree.files.find((file) => file.path === 'Dockerfile')?.content, 'FROM node:22-alpine')
  })

  test('ecrit les fichiers base64 en binaire et les relit sans perte', async () => {
    const bytes = [0, 1, 2, 250, 255]
    const base64 = encodeBytesToBase64(bytes)
    const parsed = parseProjectTreeEmission(serializeProjectTreeEmission([
      { path: 'assets/blob.wasm', content: base64, encoding: 'base64', mime: 'application/wasm' },
    ]))
    const fs = createMemoryFs()
    const result = await roundTripProjectTreeOnFs(parsed.tree, '/tmp/bin', fs)

    assert.deepEqual(fs.binary.get('/tmp/bin/assets/blob.wasm'), bytes)
    assert.equal(result.readTree.files[0].content, base64)
    assert.deepEqual(decodeBase64ToBytes(base64), bytes)
  })

  test('joint les chemins sous la racine sans perdre le dossier recovered', () => {
    assert.equal(joinProjectRoot('/tmp/root/', 'recovered/secret.ts'), '/tmp/root/recovered/secret.ts')
    assert.equal(joinProjectRoot('/tmp/root', '/src/App.tsx'), '/tmp/root/src/App.tsx')
  })

  test('writeCodeFilesToDirectory: nesting a n niveaux + ecriture binaire (backing de la sauvegarde Workspace)', async () => {
    const bytes = [10, 20, 30, 200]
    const fs = createMemoryFs()
    const result = await writeCodeFilesToDirectory(
      [
        { name: 'src/deep/nested/App.tsx', content: 'export const App = () => null' },
        { name: 'public/logo.png', content: encodeBytesToBase64(bytes), encoding: 'base64' },
        { name: 'README.md', content: '# Projet' },
      ],
      '/tmp/proj',
      fs,
    )

    assert.equal(result.files.length, 3)
    // nesting multi-niveaux cree (l ancienne boucle manuelle ne gerait qu un niveau)
    assert.equal(fs.dirs.has('/tmp/proj/src/deep/nested'), true)
    assert.equal(fs.text.get('/tmp/proj/src/deep/nested/App.tsx'), 'export const App = () => null')
    // fichier base64 ecrit en BINAIRE (l ancienne boucle l aurait corrompu en texte)
    assert.deepEqual(fs.binary.get('/tmp/proj/public/logo.png'), bytes)
    assert.equal(fs.text.has('/tmp/proj/public/logo.png'), false)
  })
})
