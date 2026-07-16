import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createCodeGenerationSandboxRunner,
  runCodeGenerationCommandInSandbox,
} from '../services/codeGenerationCommandRunner.ts'
import type { CodeFile } from '../services/codeSandboxTypes.ts'

const files: CodeFile[] = [
  { name: 'package.json', language: 'json', content: '{"name":"demo","scripts":{"build":"node index.js"}}' },
  { name: 'index.js', language: 'javascript', content: 'console.log("ok")' },
]

function fakeOptions(records: string[] = []) {
  return {
    getWorkspacePathImpl: async () => '/tmp/aurora',
    writeFilesImpl: async (root: string, writtenFiles: CodeFile[]) => {
      records.push(`write:${root}:${writtenFiles.length}`)
    },
    detectIsolationImpl: async () => ({
      ok: true,
      mode: 'podman-rootless' as const,
      reason: 'Podman rootless avec cgroups v2 disponible.',
      rootless: true,
      cgroupVersion: 'v2',
    }),
    prepareWorkspaceImpl: async () => ({
      ok: true,
      created: true,
      steps: [{
        label: 'Initialisation workspace quota WS7',
        command: 'podman run init',
        ok: true,
        output: 'workspace pret',
      }],
    }),
    cleanupWorkspaceImpl: async () => ({
      label: 'Nettoyage volume workspace WS7',
      command: 'podman volume rm',
      ok: true,
      output: 'removed',
    }),
    runCommandImpl: async (executable: string, args: string[], cwd: string) => {
      records.push(`run:${executable}:${cwd}`)
      return {
        ok: true,
        exitCode: 0,
        output: args.join(' ').includes('npm run build') ? 'build ok' : 'unexpected',
        command: `${executable} ${args.join(' ')}`,
      }
    },
    now: () => 42,
  }
}

describe('codeGenerationCommandRunner', () => {
  test('execute run_command dans le sandbox WS7 Podman rootless', async () => {
    const records: string[] = []
    const result = await runCodeGenerationCommandInSandbox({
      command: 'npm run build',
      reason: 'validation',
      files,
      options: fakeOptions(records),
    })

    assert.equal(result.ok, true)
    assert.match(result.output, /Isolation sandbox WS7/)
    assert.match(result.output, /run_command WS3: validation/)
    assert.match(result.output, /build ok/)
    assert.deepEqual(records, [
      'write:/tmp/aurora/output/code-command-runner/42:2',
      'run:podman:/tmp/aurora/output/code-command-runner/42',
    ])
  })

  test('refuse dexecuter si lisolation WS7 est indisponible', async () => {
    const result = await runCodeGenerationCommandInSandbox({
      command: 'npm test',
      files,
      options: {
        ...fakeOptions(),
        detectIsolationImpl: async () => ({
          ok: false,
          mode: 'unavailable' as const,
          reason: 'Podman absent',
          rootless: false,
          cgroupVersion: null,
        }),
      },
    })

    assert.equal(result.ok, false)
    assert.match(result.output, /Podman absent/)
  })

  test('createCodeGenerationSandboxRunner ferme sur les fichiers VFS courants', async () => {
    const runner = createCodeGenerationSandboxRunner(fakeOptions())
    const result = await runner('npm run build', 'validation', files)

    assert.equal(result.ok, true)
    assert.match(result.output, /build ok/)
  })
})
