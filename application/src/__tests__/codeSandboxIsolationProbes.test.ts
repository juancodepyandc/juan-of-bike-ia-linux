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
      'node',
      async (_executable, args) => {
        if (args[0] === 'image' && args[1] === 'exists') {
          return { ok: true, exitCode: 0, output: '', command: args.join(' ') }
        }
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
      'node',
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

  // Cause racine de la serie de runs qui n atteignaient jamais `done`: les
  // preuves etaient bati es avec `unknown` -> image `debian:bookworm-slim`, que
  // Aurora ne provisionne pas. Echec systematique, sortie VIDE (podman ecrit sur
  // stderr, que le pont ne transmet pas), et `isDeliveryRunnable` a false.
  test('les preuves tournent dans l image qui execute REELLEMENT le code', () => {
    const node = buildSandboxIsolationProbeCommands('/tmp/aurora/ws', 'node')
    const python = buildSandboxIsolationProbeCommands('/tmp/aurora/ws', 'python')
    assert.ok(node.every((c) => c.args.includes('docker.io/library/node:22-bookworm-slim')))
    assert.ok(python.every((c) => c.args.includes('docker.io/library/python:3.12-slim')))
    assert.equal(node.some((c) => c.args.some((a) => a.includes('debian'))), false)
  })

  test('image absente = panne d INSTALLATION nommee, jamais un verdict sur le code', async () => {
    const result = await runSandboxIsolationProbes(
      '/tmp/aurora/ws',
      'node',
      async (_executable, args) => {
        if (args[0] === 'image' && args[1] === 'exists') {
          // `podman image exists` n ecrit rien: le verdict est le code de sortie.
          return { ok: false, exitCode: 1, output: '', command: args.join(' ') }
        }
        throw new Error('aucune preuve ne doit tourner sans image')
      },
      { writeText: async () => undefined, removeDirAll: async () => undefined },
    )

    assert.equal(result.ok, false)
    assert.equal(result.steps.length, 1)
    assert.match(result.steps[0].output, /image conteneur absente en local/)
    assert.match(result.steps[0].output, /node:22-bookworm-slim/)
    assert.match(result.steps[0].output, /PAS un defaut du code livre/)
  })

  test('un echec sans sortie est NOMME au lieu d etre rendu vide', async () => {
    const result = await runSandboxIsolationProbes(
      '/tmp/aurora/ws',
      'node',
      async (_executable, args) => (args[0] === 'image' && args[1] === 'exists'
        ? { ok: true, exitCode: 0, output: '', command: args.join(' ') }
        : { ok: false, exitCode: 125, output: '', command: args.join(' ') }),
      { writeText: async () => undefined, removeDirAll: async () => undefined },
    )

    assert.equal(result.ok, false)
    assert.notEqual(result.steps[0].output.trim(), '')
    assert.match(result.steps[0].output, /echec sans sortie \(code 125\)/)
    assert.match(result.steps[0].output, /stderr/)
  })
})
