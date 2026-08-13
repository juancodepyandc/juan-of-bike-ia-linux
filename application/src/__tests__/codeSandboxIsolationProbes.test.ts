import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import {
  buildSandboxIsolationProbeCommands,
  runSandboxIsolationProbes,
  sandboxHostSentinelPath,
} from '../services/codeSandboxIsolationProbes.ts'

const okImage = (args: string[]) => ({ ok: true, exitCode: 0, output: '', command: args.join(' ') })
const isImageCheck = (args: string[]) => args[0] === 'image' && args[1] === 'exists'
const noFs = { writeText: async () => undefined, removeDirAll: async () => undefined }

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
    assert.match(pidsScript, /AURORA_PIDS_UNCAPPED/)
    assert.match(pidsScript, /exit 2/)
    assert.match(fsizeScript, /dd if=\/dev\/zero/)
    assert.match(fsizeScript, /count=2048/)
    assert.match(diskScript, /aurora-disk-quota-probe/)
    assert.match(diskScript, /while \[ "\$i" -lt 384 \]/)
    assert.match(diskScript, /bs=3M/)
  })

  // LE test qui manquait. Deux probes sur quatre etaient SYNTAXIQUEMENT INVALIDES
  // (corps de boucle joints par un espace au lieu de « ; »): `sh` sortait en 2 —
  // exactement le statut reserve a « confinement non applique ». Une erreur de
  // syntaxe etait donc rapportee comme une faille d isolation, sur chaque run.
  // Personne ne l a vu parce que personne n avait jamais fait LIRE ces scripts
  // par un shell.
  test('chaque script de probe est du shell VALIDE (sh -n)', () => {
    for (const command of buildSandboxIsolationProbeCommands('/tmp/aurora/ws', 'node')) {
      const script = command.args.at(-1) ?? ''
      assert.doesNotThrow(
        () => execFileSync('sh', ['-n', '-c', script], { stdio: 'pipe' }),
        `script invalide pour « ${command.label} »: ${script}`,
      )
    }
  })

  test('runSandboxIsolationProbes cree puis nettoie la sentinelle host et stoppe au premier echec', async () => {
    const seen: string[] = []
    const writes: string[] = []
    const removals: string[] = []
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      runner: async (_executable, args) => {
        if (isImageCheck(args)) return okImage(args)
        const label = args.some((arg) => arg.includes('AURORA_HOST_SENTINEL')) ? 'host' : 'next'
        seen.push(label)
        return {
          ok: label === 'host',
          exitCode: label === 'host' ? 0 : 1,
          output: label,
          command: args.join(' '),
        }
      },
      fs: {
        writeText: async (path) => { writes.push(path) },
        removeDirAll: async (path) => { removals.push(path) },
      },
    })

    assert.equal(result.ok, false)
    assert.equal(result.steps.length, 2)
    assert.deepEqual(seen, ['host', 'next'])
    assert.deepEqual(writes, ['/tmp/aurora/AURORA_HOST_SENTINEL_tmp_aurora_ws'])
    assert.deepEqual(removals, writes)
  })

  test('runSandboxIsolationProbes echoue sans lancer Podman si la sentinelle ne peut pas etre creee', async () => {
    let commandRuns = 0
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      runner: async () => {
        commandRuns += 1
        return { ok: true, exitCode: 0, output: '', command: 'unexpected' }
      },
      fs: {
        writeText: async () => { throw new Error('disk denied') },
        removeDirAll: async () => undefined,
      },
    })

    assert.equal(result.ok, false)
    assert.equal(commandRuns, 0)
    assert.equal(result.steps[0]?.label, 'Preuve isolation host-read sentinel')
    assert.match(result.steps[0]?.output ?? '', /disk denied/)
  })

  // Cause racine de la serie de runs qui n atteignaient jamais `done`: les
  // preuves etaient baties avec `unknown` -> image `debian:bookworm-slim`, que
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
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      runner: async (_executable, args) => {
        // `podman image exists` n ecrit rien: le verdict est le code de sortie.
        if (isImageCheck(args)) return { ok: false, exitCode: 1, output: '', command: args.join(' ') }
        throw new Error('aucune preuve ne doit tourner sans image')
      },
      fs: noFs,
    })

    assert.equal(result.ok, false)
    assert.equal(result.steps.length, 1)
    assert.match(result.steps[0].output, /image conteneur absente en local/)
    assert.match(result.steps[0].output, /node:22-bookworm-slim/)
    assert.match(result.steps[0].output, /PAS un defaut du code livre/)
  })

  test('un echec sans sortie est NOMME au lieu d etre rendu vide', async () => {
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      runner: async (_executable, args) => (isImageCheck(args)
        ? okImage(args)
        : { ok: false, exitCode: 125, output: '', command: args.join(' ') }),
      fs: noFs,
    })

    assert.equal(result.ok, false)
    assert.notEqual(result.steps[0].output.trim(), '')
    assert.match(result.steps[0].output, /echec sans sortie \(code 125\)/)
    assert.match(result.steps[0].output, /stderr/)
  })

  // Sur un systeme de fichiers sans Project Quota, Aurora cree DELIBEREMENT le
  // volume sans quota de taille. Exiger ensuite la preuve de ce quota fait
  // condamner la livraison pour une propriete que personne n a demandee.
  test('quota disque non demande = preuve NON APPLICABLE, pas un echec', async () => {
    const launched: string[] = []
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      workspaceQuotaEnforced: false,
      runner: async (_executable, args) => {
        if (isImageCheck(args)) return okImage(args)
        launched.push(String(args.at(-1)))
        return { ok: true, exitCode: 0, output: 'ok', command: args.join(' ') }
      },
      fs: noFs,
    })

    assert.equal(result.ok, true)
    assert.equal(launched.some((script) => script.includes('aurora-disk-quota-probe')), false)
    const skipped = result.steps.find((s) => s.label.includes('NON APPLICABLE'))
    assert.ok(skipped)
    assert.equal(skipped.ok, true)
    assert.match(skipped.output, /Project Quota/)
    assert.match(skipped.output, /on ne le declare pas acquis/)
    // Les autres confinements restent PROUVES, pas seulement declares.
    assert.ok(result.steps.some((s) => s.label === 'Preuve quota pids' && s.ok))
    assert.ok(result.steps.some((s) => s.label === 'Preuve quota taille fichier' && s.ok))
  })

  test('quota disque demande = preuve REELLEMENT executee', async () => {
    const launched: string[] = []
    const result = await runSandboxIsolationProbes('/tmp/aurora/ws', {
      lang: 'node',
      workspaceQuotaEnforced: true,
      runner: async (_executable, args) => {
        if (isImageCheck(args)) return okImage(args)
        launched.push(String(args.at(-1)))
        return { ok: true, exitCode: 0, output: 'ok', command: args.join(' ') }
      },
      fs: noFs,
    })

    assert.equal(result.ok, true)
    assert.equal(launched.some((script) => script.includes('aurora-disk-quota-probe')), true)
    assert.equal(result.steps.some((s) => s.label.includes('NON APPLICABLE')), false)
  })
})
