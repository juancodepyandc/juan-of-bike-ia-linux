import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildSandboxIsolationProbeCommands,
  runSandboxIsolationProbes,
  sandboxHostSentinelPath,
} from '../services/codeSandboxIsolationProbes.ts'

describe('codeSandboxIsolationProbes', () => {
  test('buildSandboxIsolationProbeCommands construit les probes host-read, pids, fsize et disque sous Podman', () => {
    const commands = buildSandboxIsolationProbeCommands('/tmp/aurora/ws')

    assert.deepEqual(commands.map((command) => command.label), [
      'Preuve isolation host-read',
      'Preuve quota pids',
      'Preuve quota taille fichier',
      'Preuve quota disque workspace',
    ])
    assert.ok(commands.every((command) => command.executable === 'podman'))
    assert.ok(commands.every((command) => {
      const networkIndex = command.args.indexOf('--network')
      return networkIndex >= 0 && command.args[networkIndex + 1] === 'none'
    }))
    assert.ok(commands.every((command) => command.args.includes('--pids-limit')))
  })

  test('sandboxHostSentinelPath place la sentinelle hors du sandbox monte', () => {
    assert.equal(
      sandboxHostSentinelPath('/tmp/aurora/ws'),
      '/tmp/aurora/AURORA_HOST_SENTINEL_tmp_aurora_ws',
    )
  })

  test('les scripts de probe cherchent les regressions attendues', () => {
    const [hostRead, pids, fsize, disk] = buildSandboxIsolationProbeCommands('/tmp/aurora/ws')
    const hostScript = hostRead.args.at(-1) ?? ''
    const pidsScript = pids.args.at(-1) ?? ''
    const fsizeScript = fsize.args.at(-1) ?? ''
    const diskScript = disk.args.at(-1) ?? ''

    assert.match(hostScript, /AURORA_HOST_SENTINEL/)
    assert.match(pidsScript, /while \[ "\$started" -lt 400 \]/)
    assert.match(pidsScript, /kill -0 "\$pid"/)
    assert.match(pidsScript, /exit 2/)
    assert.match(fsizeScript, /dd if=\/dev\/zero/)
    assert.match(fsizeScript, /count=2048/)
    assert.match(diskScript, /aurora-disk-quota-probe/)
    assert.match(diskScript, /while \[ "\$i" -lt 384 \]/)
    assert.match(diskScript, /bs=3M/)
  })

  test('runSandboxIsolationProbes cree puis nettoie la sentinelle host et stoppe au premier echec', async () => {
    const seen: string[] = []
    const writes: string[] = []
    const removals: string[] = []
    const result = await runSandboxIsolationProbes(
      '/tmp/aurora/ws',
      async (_executable, args) => {
        const label = args.some((arg) => arg.includes('AURORA_HOST_SENTINEL')) ? 'host' : 'next'
        seen.push(label)
        return {
          ok: label === 'host',
          exitCode: label === 'host' ? 0 : 1,
          output: label,
          command: args.join(' '),
        }
      },
      {
        writeText: async (path) => { writes.push(path) },
        removeDirAll: async (path) => { removals.push(path) },
      },
    )

    assert.equal(result.ok, false)
    assert.equal(result.steps.length, 2)
    assert.deepEqual(seen, ['host', 'next'])
    assert.deepEqual(writes, ['/tmp/aurora/AURORA_HOST_SENTINEL_tmp_aurora_ws'])
    assert.deepEqual(removals, writes)
  })

  test('runSandboxIsolationProbes echoue sans lancer Podman si la sentinelle ne peut pas etre creee', async () => {
    let commandRuns = 0
    const result = await runSandboxIsolationProbes(
      '/tmp/aurora/ws',
      async () => {
        commandRuns += 1
        return { ok: true, exitCode: 0, output: '', command: 'unexpected' }
      },
      {
        writeText: async () => { throw new Error('disk denied') },
        removeDirAll: async () => undefined,
      },
    )

    assert.equal(result.ok, false)
    assert.equal(commandRuns, 0)
    assert.equal(result.steps[0]?.label, 'Preuve isolation host-read sentinel')
    assert.match(result.steps[0]?.output ?? '', /disk denied/)
  })
})
