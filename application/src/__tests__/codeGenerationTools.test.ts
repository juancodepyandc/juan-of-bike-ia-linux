import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  executeCodeGenerationTool,
  executeCodeGenerationToolSequence,
} from '../services/codeGenerationTools.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, content, language }
}

describe('codeGenerationTools', () => {
  test('write_file puis read_file travaillent dans le VFS projet', async () => {
    const written = await executeCodeGenerationTool([], {
      kind: 'write_file',
      path: './src/App.tsx',
      language: 'tsx',
      content: 'export function App() { return null }',
    })
    assert.equal(written.ok, true)
    assert.equal(written.files[0].name, 'src/App.tsx')

    const read = await executeCodeGenerationTool(written.files, { kind: 'read_file', path: 'src/App.tsx' })
    assert.equal(read.ok, true)
    assert.match(read.content ?? '', /function App/)
  })

  test('bloque les chemins hors projet et les fichiers secrets', async () => {
    const outside = await executeCodeGenerationTool([], { kind: 'write_file', path: '../x.ts', content: 'x' })
    const secret = await executeCodeGenerationTool([], { kind: 'write_file', path: '.env', content: 'TOKEN=x' })

    assert.equal(outside.ok, false)
    assert.equal(outside.error, 'path_must_stay_in_project')
    assert.equal(secret.ok, false)
    assert.equal(secret.error, 'secret_file_blocked')
  })

  test('apply_patch remplace uniquement la premiere occurrence par defaut', async () => {
    const initial = [file('src/a.ts', 'const a = 1\nconst a = 1\n', 'typescript')]
    const patched = await executeCodeGenerationTool(initial, {
      kind: 'apply_patch',
      path: 'src/a.ts',
      search: 'const a = 1',
      replace: 'const a = 2',
    })

    assert.equal(patched.ok, true)
    assert.equal(patched.files[0].content, 'const a = 2\nconst a = 1\n')
  })

  test('execute une sequence et stoppe au premier echec', async () => {
    const result = await executeCodeGenerationToolSequence([], [
      { kind: 'write_file', path: 'src/a.ts', content: 'one' },
      { kind: 'apply_patch', path: 'src/a.ts', search: 'one', replace: 'two' },
      { kind: 'read_file', path: 'missing.ts' },
      { kind: 'write_file', path: 'never.ts', content: 'x' },
    ])

    assert.deepEqual(result.results.map((entry) => entry.ok), [true, true, false])
    assert.equal(result.files.some((entry) => entry.name === 'never.ts'), false)
    assert.equal(result.files[0].content, 'two')
  })

  test('run_command exige un runner WS7 explicite', async () => {
    const blocked = await executeCodeGenerationTool([], { kind: 'run_command', command: 'npm test' })
    const delegated = await executeCodeGenerationTool([], { kind: 'run_command', command: 'npm test', reason: 'validation' }, async (command, reason) => ({
      ok: true,
      output: `${reason}:${command}`,
    }))

    assert.equal(blocked.ok, false)
    assert.equal(blocked.error, 'run_command_requires_ws7_runner')
    assert.equal(delegated.ok, true)
    assert.equal(delegated.output, 'validation:npm test')
  })
})
